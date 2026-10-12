"""Simulated trainer dashboard with optional real BLE heart rate. No trainer writes."""
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
from .devices import Devices

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
devices = Devices(DB)

def live_snapshot():
    result = trainer.snapshot()
    sensor = devices.snapshot()
    selected = sensor['identifier'] is not None
    result['heart_rate_source'] = 'BLE' if selected else 'SIMULATOR'
    result['heart_rate_device'] = sensor
    if selected:
        result['heart_rate_bpm'] = sensor['heart_rate_bpm']
    return result


def initialize():
    DB.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB) as db:
        db.execute("CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, started_at TEXT NOT NULL, ended_at TEXT, duration_s REAL, final_state TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS samples (session_id TEXT, timestamp TEXT, elapsed_s REAL, target_power_w INTEGER, actual_power_w INTEGER, heart_rate_bpm INTEGER, cadence_rpm INTEGER)")

        columns = {row[1] for row in db.execute('PRAGMA table_info(samples)')}
        if 'heart_rate_source' not in columns:
            db.execute("ALTER TABLE samples ADD COLUMN heart_rate_source TEXT NOT NULL DEFAULT 'SIMULATOR'")
    devices.initialize()

async def recorder():
    while True:
        await asyncio.sleep(1)
        async with trainer.lock:
            trainer.tick()
            if trainer.state != "running":
                continue
            snapshot = live_snapshot()
            with sqlite3.connect(DB) as db:
                db.execute("INSERT INTO samples(session_id,timestamp,elapsed_s,target_power_w,actual_power_w,heart_rate_bpm,cadence_rpm,heart_rate_source) VALUES (?,?,?,?,?,?,?,?)", (
                    trainer.session_id, datetime.now(timezone.utc).isoformat(), snapshot["elapsed_s"],
                    snapshot["target_power_w"], snapshot["actual_power_w"],
                    snapshot["heart_rate_bpm"], snapshot["cadence_rpm"], snapshot["heart_rate_source"]))

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    task = asyncio.create_task(recorder())
    try:
        yield
    finally:
        await devices.disconnect()
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
        return live_snapshot()

@app.post("/api/start")
async def start(x_cycling_token: str | None = Header(default=None)):
    authorize(x_cycling_token)
    async with trainer.lock:
        trainer.tick()
        if trainer.state == "running":
            return live_snapshot()
        if trainer.state in ("idle", "ended"):
            trainer.elapsed = 0
            trainer.started = datetime.now(timezone.utc).isoformat()
            trainer.session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            with sqlite3.connect(DB) as db:
                db.execute("INSERT INTO sessions(id,started_at) VALUES (?,?)", (trainer.session_id, trainer.started))
        trainer.state = "running"
        trainer.changed = time.monotonic()
        return live_snapshot()

@app.post("/api/pause")
async def pause(x_cycling_token: str | None = Header(default=None)):
    authorize(x_cycling_token)
    async with trainer.lock:
        trainer.tick()
        if trainer.state == "running":
            trainer.state = "paused"
        return live_snapshot()

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
        return live_snapshot()

@app.post("/api/power")
async def power(value: Power, x_cycling_token: str | None = Header(default=None)):
    authorize(x_cycling_token)
    async with trainer.lock:
        trainer.tick()
        trainer.power = value.watts
        return live_snapshot()

class DeviceSelection(BaseModel):
    identifier: str = Field(min_length=1, max_length=128)

class SavedDevice(DeviceSelection):
    name: str = Field(min_length=1, max_length=100)

@app.get('/api/devices')
async def list_devices(x_cycling_token: str | None = Header(default=None)):
    authorize(x_cycling_token)
    return {'saved': devices.saved(), 'discovered': list(devices.discovered.values()), 'connection': devices.snapshot()}

@app.post('/api/devices/scan')
async def scan_devices(x_cycling_token: str | None = Header(default=None)):
    authorize(x_cycling_token)
    try:
        return await devices.scan()
    except Exception:
        raise HTTPException(503, '扫描失败，请检查 macOS 蓝牙权限与蓝牙开关')

@app.post('/api/devices/save')
async def save_device(value: SavedDevice, x_cycling_token: str | None = Header(default=None)):
    authorize(x_cycling_token)
    try:
        devices.save(value.identifier, value.name)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    return {'saved': devices.saved()}

@app.post('/api/devices/connect')
async def connect_device(value: DeviceSelection, x_cycling_token: str | None = Header(default=None)):
    authorize(x_cycling_token)
    try:
        await devices.connect(value.identifier)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception:
        raise HTTPException(503, devices.error or '连接失败')
    return devices.snapshot()

@app.post('/api/devices/disconnect')
async def disconnect_device(x_cycling_token: str | None = Header(default=None)):
    authorize(x_cycling_token)
    await devices.disconnect()
    return devices.snapshot()

@app.post('/api/devices/forget')
async def forget_device(value: DeviceSelection, x_cycling_token: str | None = Header(default=None)):
    authorize(x_cycling_token)
    await devices.forget(value.identifier)
    return {'saved': devices.saved()}

HTML = """<!doctype html><html lang='zh-CN'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>
<meta name='theme-color' content='#101827'><title>Indoor Cycling</title><link rel='manifest' href='/manifest.webmanifest'>
<style>body{font:16px system-ui;margin:0;background:#101827;color:white}.wrap{max-width:440px;margin:auto;padding:24px}article{background:#202c40;border-radius:16px;padding:18px;margin:14px 0}h1{font-size:22px}.big{font-size:38px;font-variant-numeric:tabular-nums}button,input{font:inherit;border-radius:9px;padding:12px}button{cursor:pointer;background:#457cf0;border:0;color:white;margin:4px}input{width:90%;box-sizing:border-box}small{color:#bdc8d8}.danger{background:#ad3445}</style>
<div class='wrap'><div class='eyebrow'>INDOOR CYCLING</div><h1>今天的训练</h1><p class='muted'>骑行台模拟模式 · 心率可连接真实设备</p><article><label>控制令牌（当前标签页会话内保存）<input id='token' type='password' autocomplete='off' placeholder='CYCLING_TOKEN'></label></article>
<article><small id='hrSource'>心率</small><div class='big' id='hr'>—</div><div class='metric-grid'><div><small>模拟功率</small><div class='big' id='actual'>—</div></div><div><small>训练时长</small><div class='big' id='elapsed'>00:00</div></div></div><small id='state'>未连接</small></article>
<article><small>目标功率</small><div class='big'><span id='power'>90</span> W</div><button onclick='change(-5)'>−5 W</button><button onclick='change(5)'>+5 W</button></article>
<article class="actions"><button onclick="command('start')">开始 / 恢复</button><button onclick="command('pause')">暂停</button><button class='danger' onclick="command('stop')">结束</button><p id='error'></p></article></div>
<script>
let latest=null;const token=()=>document.getElementById('token').value;document.getElementById('token').value=sessionStorage.getItem('cyclingToken')||'';document.getElementById('token').addEventListener('input',()=>sessionStorage.setItem('cyclingToken',token()));
async function api(path,body){let response=await fetch('/api/'+path,{method:body===undefined?'GET':'POST',headers:{'X-Cycling-Token':token(),'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});if(!response.ok)throw new Error('HTTP '+response.status);return response.json()}
function draw(s){latest=s;document.getElementById('hrSource').textContent=s.heart_rate_source==='BLE'?'真实心率 · '+(s.heart_rate_device.stale?'等待数据 / 数据过期':'蓝牙已连接'):'模拟心率';document.getElementById('hr').textContent=s.heart_rate_bpm??'—';document.getElementById('actual').textContent=(s.actual_power_w??'—')+' W';document.getElementById('elapsed').textContent=new Date(s.elapsed_s*1000).toISOString().substring(11,19);document.getElementById('state').textContent=({idle:'准备开始',running:'训练中',paused:'已暂停',ended:'已结束'}[s.state]||s.state);document.getElementById('power').textContent=s.target_power_w;document.getElementById('error').textContent=''}
async function command(op){try{draw(await api(op,{}))}catch(e){document.getElementById('error').textContent=e.message}}
async function change(step){if(!latest)return;try{draw(await api('power',{watts:Math.max(40,Math.min(150,latest.target_power_w+step))}))}catch(e){document.getElementById('error').textContent=e.message}}
setInterval(async()=>{if(!token())return;try{draw(await api('status'))}catch(e){document.getElementById('state').textContent='失去连接';document.getElementById('error').textContent=e.message}},1000);
if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>{});
</script></html>"""

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    from .mobile import shell
    return shell(HTML, "/")

@app.get("/manifest.webmanifest")
async def manifest():
    return {"name":"Indoor Cycling","short_name":"Cycling","start_url":"/","display":"standalone", "background_color":"#101827","theme_color":"#101827"}

@app.get("/sw.js")
async def sw():
    from fastapi.responses import Response
    # Never cache sensor readings or control requests.
    return Response("self.addEventListener('install', e => self.skipWaiting());", media_type="application/javascript")

@app.get('/devices', response_class=HTMLResponse)
async def device_page():
    from .device_page import HTML as device_html
    from .mobile import shell
    return shell(device_html, "/devices")

@app.get('/history', response_class=HTMLResponse)
async def history_page():
    from .mobile import HISTORY, shell
    return shell(HISTORY, '/history')

@app.get('/api/history')
async def history(x_cycling_token: str | None = Header(default=None)):
    authorize(x_cycling_token)
    with sqlite3.connect(DB) as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute("""SELECT id,started_at,ended_at,duration_s,
            EXISTS(SELECT 1 FROM samples WHERE session_id=sessions.id AND heart_rate_source='BLE') AS has_ble
            FROM sessions ORDER BY started_at DESC LIMIT 50""")]
