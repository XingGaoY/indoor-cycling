"""Validated, local-only workout plan library. No trainer commands are issued here."""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4

from fastapi import Header, HTTPException

PURPOSES = {"warmup", "main", "recovery", "cooldown", "custom"}
MIN_WATTS, MAX_WATTS = 40, 500  # Planning bounds, NOT an approved FTMS device range.


def _integer(value, label, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{label} 必须是 {minimum}–{maximum} 的整数")
    return value


def _name(value, label, length=80):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= length:
        raise ValueError(f"{label} 长度必须在 1–{length} 个字符内")
    return value.strip()


def _leaf(item):
    if not isinstance(item, dict):
        raise ValueError("训练阶段必须是对象")
    kind = item.get("kind")
    if kind not in ("constant", "ramp"):
        raise ValueError("阶段模式必须是 constant 或 ramp")
    purpose = item.get("purpose", "main")
    if purpose not in PURPOSES:
        raise ValueError("未知阶段用途")
    result = {
        "kind": kind,
        "purpose": purpose,
        "name": _name(item.get("name"), "阶段名称", 60),
        "duration_s": _integer(item.get("duration_s"), "阶段时长（秒）", 10, 7200),
    }
    if kind == "constant":
        result["watts"] = _integer(item.get("watts"), "计划功率", MIN_WATTS, MAX_WATTS)
    else:
        result["start_watts"] = _integer(item.get("start_watts"), "起始功率", MIN_WATTS, MAX_WATTS)
        result["end_watts"] = _integer(item.get("end_watts"), "结束功率", MIN_WATTS, MAX_WATTS)
    return result


def validate_plan(payload):
    if not isinstance(payload, dict):
        raise ValueError("课程必须是对象")
    name = _name(payload.get("name"), "课程名称")
    note = payload.get("note", "")
    if not isinstance(note, str) or len(note) > 500:
        raise ValueError("备注不得超过 500 个字符")
    raw = payload.get("stages")
    if not isinstance(raw, list) or not 1 <= len(raw) <= 30:
        raise ValueError("课程必须包含 1–30 个阶段")
    stages = []
    total = 0
    for stage in raw:
        if not isinstance(stage, dict):
            raise ValueError("阶段必须是对象")
        if stage.get("kind") == "repeat":
            count = _integer(stage.get("repeat_count"), "重复次数", 1, 30)
            children = stage.get("steps")
            if not isinstance(children, list) or not 2 <= len(children) <= 10:
                raise ValueError("间歇组必须包含 2–10 个子阶段")
            steps = [_leaf(child) for child in children]
            group = {"kind": "repeat", "name": _name(stage.get("name"), "间歇组名称", 60),
                     "repeat_count": count, "steps": steps}
            total += count * sum(step["duration_s"] for step in steps)
            stages.append(group)
        else:
            leaf = _leaf(stage)
            total += leaf["duration_s"]
            stages.append(leaf)
    if total > 6 * 3600:
        raise ValueError("课程总时长不能超过六小时")
    return {"name": name, "note": note, "stages": stages}


def summarize(plan):
    length = 0
    leaf_count = 0
    for s in plan["stages"]:
        if s["kind"] == "repeat":
            length += s["repeat_count"] * sum(c["duration_s"] for c in s["steps"])
            leaf_count += s["repeat_count"] * len(s["steps"])
        else:
            length += s["duration_s"]
            leaf_count += 1
    return {"duration_s": length, "stage_count": leaf_count}


def _utc_now():
    return datetime.now(timezone.utc).isoformat()


class PlanStore:
    def __init__(self, db_path):
        self.db_path = Path(db_path)

    @contextmanager
    def db(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                connection.execute("""CREATE TABLE IF NOT EXISTS workout_plans (
                    id TEXT PRIMARY KEY, content TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
                connection.execute("""CREATE TABLE IF NOT EXISTS workout_settings (
                    key TEXT PRIMARY KEY, value TEXT)""")
                yield connection
        finally:
            connection.close()

    @staticmethod
    def from_row(row):
        result = json.loads(row["content"])
        result.update({"id": row["id"], "created_at": row["created_at"],
                       "updated_at": row["updated_at"]})
        return result

    def list(self):
        with self.db() as db:
            rows = db.execute("SELECT * FROM workout_plans ORDER BY updated_at DESC").fetchall()
            return [{**{k: p[k] for k in ("id", "name", "updated_at")},
                     **summarize(p)} for p in map(self.from_row, rows)]

    def get(self, plan_id):
        with self.db() as db:
            row = db.execute("SELECT * FROM workout_plans WHERE id=?", (plan_id,)).fetchone()
            return self.from_row(row) if row else None

    def create(self, payload):
        plan = validate_plan(payload)
        now = _utc_now()
        pid = uuid4().hex
        with self.db() as db:
            db.execute("INSERT INTO workout_plans VALUES (?,?,?,?)",
                       (pid, json.dumps(plan, ensure_ascii=False), now, now))
        return self.get(pid)

    def update(self, plan_id, payload):
        plan = validate_plan(payload)
        with self.db() as db:
            result = db.execute("UPDATE workout_plans SET content=?,updated_at=? WHERE id=?",
                                (json.dumps(plan, ensure_ascii=False), _utc_now(), plan_id))
            if not result.rowcount:
                return None
        return self.get(plan_id)

    def duplicate(self, plan_id):
        old = self.get(plan_id)
        if old is None:
            return None
        base = {k: old[k] for k in ("name", "note", "stages")}
        base["name"] = old["name"][:75] + " 副本"
        return self.create(base)

    def delete(self, plan_id):
        with self.db() as db:
            db.execute("DELETE FROM workout_settings WHERE key='selected_plan' AND value=?", (plan_id,))
            return db.execute("DELETE FROM workout_plans WHERE id=?", (plan_id,)).rowcount > 0

    def select(self, plan_id):
        with self.db() as db:
            if plan_id is not None and not db.execute("SELECT 1 FROM workout_plans WHERE id=?", (plan_id,)).fetchone():
                return False
            if plan_id is None:
                db.execute("DELETE FROM workout_settings WHERE key='selected_plan'")
            else:
                db.execute("INSERT INTO workout_settings VALUES ('selected_plan', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                           (plan_id,))
        return True

    def selected(self):
        with self.db() as db:
            row = db.execute("SELECT value FROM workout_settings WHERE key='selected_plan'").fetchone()
        return self.get(row["value"]) if row else None


def mount_plan_routes(app, authorize, db_path):
    """Register plan APIs against the application's existing token authentication."""
    def checked_store(token):
        authorize(token)
        return PlanStore(db_path())

    @app.get("/api/plans")
    def list_plans(x_cycling_token: str | None = Header(default=None)):
        return checked_store(x_cycling_token).list()

    @app.get("/api/plans/selected")
    def selected_plan(x_cycling_token: str | None = Header(default=None)):
        return checked_store(x_cycling_token).selected()

    @app.post("/api/plans/select")
    def select_plan(payload: dict, x_cycling_token: str | None = Header(default=None)):
        store = checked_store(x_cycling_token)
        plan_id = payload.get("id")
        if plan_id is not None and (not isinstance(plan_id, str) or len(plan_id) > 80):
            raise HTTPException(422, "无效的课程 ID")
        if not store.select(plan_id):
            raise HTTPException(404, "未找到课程")
        return store.selected()

    @app.post("/api/plans")
    def create_plan(payload: dict, x_cycling_token: str | None = Header(default=None)):
        store = checked_store(x_cycling_token)
        try:
            return store.create(payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/plans/{plan_id}")
    def get_plan(plan_id: str, x_cycling_token: str | None = Header(default=None)):
        plan = checked_store(x_cycling_token).get(plan_id)
        if plan is None:
            raise HTTPException(404, "未找到课程")
        return plan

    @app.put("/api/plans/{plan_id}")
    def update_plan(plan_id: str, payload: dict, x_cycling_token: str | None = Header(default=None)):
        store = checked_store(x_cycling_token)
        try:
            plan = store.update(plan_id, payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        if plan is None:
            raise HTTPException(404, "未找到课程")
        return plan

    @app.post("/api/plans/{plan_id}/duplicate")
    def duplicate_plan(plan_id: str, x_cycling_token: str | None = Header(default=None)):
        plan = checked_store(x_cycling_token).duplicate(plan_id)
        if plan is None:
            raise HTTPException(404, "未找到课程")
        return plan

    @app.delete("/api/plans/{plan_id}")
    def delete_plan(plan_id: str, x_cycling_token: str | None = Header(default=None)):
        if not checked_store(x_cycling_token).delete(plan_id):
            raise HTTPException(404, "未找到课程")
        return {"deleted": True}
