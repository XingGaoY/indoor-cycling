"""Simulator-only HTTP dashboard; does NOT send BLE control commands."""
from __future__ import annotations

import asyncio
import os
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

DB = Path(os.environ.get("CYCLING_DB", str(Path.home() / ".local/share/indoor-cycling/sessions.sqlite3")))
TOKEN = os.environ.get("CYCLING_TOKEN", "")

class Trainer:
    def __init__(self):
        self.state = "idle"
        self.power = 90
        self.started = None
        self.elapsed = 0.0
        self.changed = time.monotonic()
        self.session_id = None
        self.lock = asyncio.Lock()

    def tick(self):
        now = time.monotonic()
        if self.state == "running":
            self.elapsed += now - self.changed
        self.changed = now

    def snapshot(self):
        return {"mode": "SIMULATOR", "state": self.state, "target_power_w": self.power,
                "actual_power_w": self.power if self.state == "running" else 0,
                "heart_rate_bpm": 125 if self.state == "running" else None,
                "cadence_rpm": 82 if self.state == "running" else 0,
                "elapsed_s": round(self.elapsed, 1), "session_id": self.session_id}

trainer = Trainer()


def initialize():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as db:
        db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT, duration_s REAL, final_state TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS samples (session_id TEXT, timestamp TEXT, elapsed_s REAL, target_power_w INTEGER, actual_power_w INTEGER, heart_rate_bpm INTEGER, cadence_rpm INTEGER)")

async def recorder():
    while True:
        await asyncio.sleep(1)
        async with trainer.lock:
            trainer.tick()
            if trainer.state != "running":
                continue
            snapshot = trainer.snapshot()
            with sqlite3.connect(DB) as db:
                db.execute("INSERT INTO samples VALUES (?,?,?,?,?,?,?)", (
                    trainer.session_id, datetime.now(timezone.utc).isoformat(), snapshot["elapsed_s"],
                    snapshot["target_power_w"], snapshot["actual_power_w"],
                    snapshot["heart_rate_bpm"], snapshot["cadence_rpm"]))

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    task = asyncio.create_task(recorder())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

app = FastAPI(title="Indoor Cycling (SIMULATOR)", lifespan=lifespan)


def authorize(token: str | None):
    # No anonymous access: set a strong token before starting the service.
    if not TOKEN or token != TOKEN:
        raise HTTPException(401, "Invalid controller token")

class Power(BaseModel):
    watts: int = Field(ge=40, le=150)

@app.get("/api/status")
async def status(x_cycling_token: str | None = Header(default=None)):
    authorize(x_cycling_token)
    async with trainer.lock:
        trainer.tick()
        return trainer.snapshot()

@app.post("/api/start")
async def start(x_cycling_token: str | None = Header(default=None)):
    authorize(x_cycling_token)
    async with trainer.lock:
        trainer.tick()
        if trainer.state == "running":
            return trainer.snapshot()
        if trainer.state in ("idle", "ended"):
            trainer.elapsed = 0
            trainer.started = datetime.now(timezone.utc).isoformat()
            trainer.session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            with sqlite3.connect(DB) as db:
                db.execute("INSERT INTO sessions(id,started_at) VALUES (?,?)", (trainer.session_id, trainer.started))
        trainer.state = "running"
        trainer.changed = time.monotonic()
        return trainer.snapshot()

@app.post("/api/pause")
async def pause(x_cycling_token: str | None = Header(default=None)):
    authorize(x_cycling_token)
    async with trainer.lock:
        trainer.tick()
        if trainer.state == "running":
            trainer.state = "paused"
        return trainer.snapshot()

@app.post("/api/stop")
async def stop(x_cycling_token: str | None = Header(default=None)):
    authorize(x_cycling_token)
    async with trainer.lock:
        trainer.tick()
        if trainer.session_id and trainer.state in ("running", "paused"):
            with sqlite3.connect(DB) as db:
                db.execute("UPDATE sessions SET ended_at=?, duration_s=?, final_state=? WHERE id=?",
                           (datetime.now(timezone.utc).isoformat(), trainer.elapsed, "ended", trainer.session_id))
        trainer.state = "ended"
        return trainer.snapshot()

@app.post("/api/power")
async def power(value: Power, x_cycling_token: str | None = Header(default=None)):
    authorize(x_cycling_token)
    async with trainer.lock:
        trainer.tick()
        trainer.power = value.watts
        return trainer.snapshot()

HTML = """<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<meta name='theme-color' content='#101827'><title>Indoor Cycling</title><link rel='manifest' href='/manifest.webmanifest'>
<style>body{font:16px system-ui;margin:0;background:#101827;color:white}.wrap{max-width:440px;margin:auto;padding:24px}article{background:#202c40;border-radius:16px;padding:18px;margin:14px 0}h1{font-size:22px}.big{font-size:38px;font-variant-numeric:tabular-nums}button,input{font:inherit;border-radius:9px;padding:12px}button{cursor:pointer;background:#457cf0;border:0;color:white;margin:4px}input{width:90%;box-sizing:border-box}small{color:#bdc8d8}.danger{background:#ad3445}</style>
<div class='wrap'><h1>Indoor Cycling <small>SIMULATOR</small></h1><article><label>控制令牌（保存在当前页面内存中）<input id='token' type='password' autocomplete='off' placeholder='CYCLING_TOKEN'></label></article>
<article><small>心率</small><div class='big' id='hr'>—</div><small>实际功率</small><div class='big' id='actual'>—</div><small>时长</small><div class='big' id='elapsed'>00:00</div><small id='state'>未连接</small></article>
<article><small>目标功率</small><div class='big'><span id='power'>90</span> W</div><button onclick='change(-5)'>−5 W</button><button onclick='change(5)'>+5 W</button></article>
<article><button onclick="command('start')">开始 / 恢复</button><button onclick="command('pause')">暂停</button><button class='danger' onclick="command('stop')">结束</button><p id='error'></p></article></div>
<script>
let latest=null;const token=()=>document.getElementById('token').value;
async function api(path,body){let response=await fetch('/api/'+path,{method:body===undefined?'GET':'POST',headers:{'X-Cycling-Token':token(),'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});if(!response.ok)throw new Error('HTTP '+response.status);return response.json()}
function draw(s){latest=s;document.getElementById('hr').textContent=s.heart_rate_bpm??'—';document.getElementById('actual').textContent=(s.actual_power_w??'—')+' W';document.getElementById('elapsed').textContent=new Date(s.elapsed_s*1000).toISOString().substring(11,19);document.getElementById('state').textContent=s.state;document.getElementById('power').textContent=s.target_power_w;document.getElementById('error').textContent=''}
async function command(op){try{draw(await api(op,{}))}catch(e){document.getElementById('error').textContent=e.message}}
async function change(step){if(!latest)return;try{draw(await api('power',{watts:Math.max(40,Math.min(150,latest.target_power_w+step))}))}catch(e){document.getElementById('error').textContent=e.message}}
setInterval(async()=>{if(!token())return;try{draw(await api('status'))}catch(e){document.getElementById('state').textContent='失去连接';document.getElementById('error').textContent=e.message}},1000);
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
</script></html>"""

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    return HTML

@app.get("/manifest.webmanifest")
async def manifest():
    return {"name":"Indoor Cycling","short_name":"Cycling","start_url":"/","display":"standalone", "background_color":"#101827","theme_color":"#101827"}

@app.get("/sw.js")
async def sw():
    from fastapi.responses import Response
    # Never cache sensor readings or control requests.
    return Response("self.addEventListener('install', e => self.skipWaiting());", media_type="application/javascript")
