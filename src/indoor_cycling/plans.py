"""Local workout plan catalog and zone-aware editor schema.

Pure plan data: NEVER sends an FTMS command or starts a training session.
Existing v1 absolute-watt stages remain readable/editable.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
from uuid import uuid4
from fastapi import Header, HTTPException

PURPOSES = {"warmup", "main", "recovery", "cooldown", "custom"}
MIN_WATTS, MAX_WATTS = 40, 500   # UI/editor only, NOT hardware limits.
# Widely used six-zone relative-power display (zone 6 intentionally open-ended).
POWER_ZONES = [
    {"zone": 1, "label": "恢复", "min_pct": 0, "max_pct": 55},
    {"zone": 2, "label": "耐力", "min_pct": 55, "max_pct": 75},
    {"zone": 3, "label": "节奏", "min_pct": 75, "max_pct": 90},
    {"zone": 4, "label": "阈值", "min_pct": 90, "max_pct": 105},
    {"zone": 5, "label": "VO₂", "min_pct": 105, "max_pct": 120},
    {"zone": 6, "label": "无氧", "min_pct": 120, "max_pct": None},
]
# Explicitly provisional display zones, based on max HR; not individualized.
HR_ZONES = [
    {"zone": 1, "min_pct": 50, "max_pct": 60},
    {"zone": 2, "min_pct": 60, "max_pct": 70},
    {"zone": 3, "min_pct": 70, "max_pct": 80},
    {"zone": 4, "min_pct": 80, "max_pct": 90},
    {"zone": 5, "min_pct": 90, "max_pct": 95},
    {"zone": 6, "min_pct": 95, "max_pct": 100},
]


def _integer(value, label, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{label} 必须是 {minimum}–{maximum} 的整数")
    return value


def _name(value, label, length=80):
    if not isinstance(value, str) or not 1 <= len(value.strip()) <= length:
        raise ValueError(f"{label} 长度必须在 1–{length} 个字符内")
    return value.strip()


def _zone_span(payload, label, minimum=1, maximum=6):
    if not isinstance(payload, dict):
        raise ValueError(f"{label} 必须是区间对象")
    low = _integer(payload.get("from"), label + " 起始", minimum, maximum)
    high = _integer(payload.get("to"), label + " 结束", minimum, maximum)
    return {"from": low, "to": high}


def _hr_band(payload):
    if not isinstance(payload, dict):
        raise ValueError("心率范围必须是区间对象")
    low = _integer(payload.get("from"), "心率下限 Z", 1, 6)
    high = _integer(payload.get("to"), "心率上限 Z", 1, 6)
    if low > high:
        raise ValueError("心率区间下限不能大于上限")
    return {"from": low, "to": high}


def _leaf(item):
    if not isinstance(item, dict):
        raise ValueError("训练阶段必须是对象")
    kind = item.get("kind")
    if kind not in ("constant", "ramp"):
        raise ValueError("阶段模式必须是 constant 或 ramp")
    purpose = item.get("purpose", "main")
    if purpose not in PURPOSES:
        raise ValueError("未知阶段用途")
    result = {"kind": kind, "purpose": purpose,
              "name": _name(item.get("name"), "阶段名称", 60),
              "duration_s": _integer(item.get("duration_s"), "阶段时长（秒）", 10, 7200)}
    # Relative FTP zones can be saved WITHOUT an invented FTP or absolute watts.
    if "power_zones" in item:
        zones = _zone_span(item["power_zones"], "功率区间")
        if kind == "constant" and zones["from"] != zones["to"]:
            raise ValueError("恒定功率阶段只能选择单个功率区间")
        result["power_zones"] = zones
    elif kind == "constant":
        result["watts"] = _integer(item.get("watts"), "计划功率", MIN_WATTS, MAX_WATTS)
    else:
        result["start_watts"] = _integer(item.get("start_watts"), "起始功率", MIN_WATTS, MAX_WATTS)
        result["end_watts"] = _integer(item.get("end_watts"), "结束功率", MIN_WATTS, MAX_WATTS)
    if "hr_zones" in item and item["hr_zones"] is not None:
        result["hr_zones"] = _hr_band(item["hr_zones"])
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


def _stage(name, minutes, zone, purpose="main", hr=None):
    stage = {"kind": "constant", "name": name, "purpose": purpose,
             "duration_s": minutes * 60, "power_zones": {"from": zone, "to": zone}}
    if hr is not None:
        stage["hr_zones"] = {"from": hr[0], "to": hr[1]}
    return stage


# Templates are embedded in source and copied into the user's own editable plans.
# Zone targets stay relative. No unmeasured FTP/HRmax or absolute watts are invented.
_PRESETS = [
    {"slug": "recovery-30", "name": "轻松恢复 · 30 分钟",
     "note": "低强度活动模板，按主观轻松程度调整；不是恢复保证。",
     "stages": [_stage("轻松开始", 5, 1, "warmup", (1, 2)),
                _stage("恢复骑行", 20, 1, "recovery", (1, 2)),
                _stage("放松", 5, 1, "cooldown", (1, 2))]},
    {"slug": "endurance-45", "name": "Z2 有氧 · 45 分钟",
     "note": "用于常规低强度有氧；骑行与跑步训练量不按时间一比一等价。",
     "stages": [_stage("热身", 8, 1, "warmup", (1, 2)),
                _stage("稳定耐力", 32, 2, "main", (2, 3)),
                _stage("冷身", 5, 1, "cooldown", (1, 2))]},
    {"slug": "tempo-40", "name": "节奏训练 · 40 分钟",
     "note": "强度高于 Z2 的结构示例，需有骑行适应后再考虑实践。",
     "stages": [_stage("热身", 10, 1, "warmup", (1, 2)),
                _stage("耐力", 5, 2, "main", (2, 3)),
                _stage("节奏", 15, 3, "main", (3, 4)),
                _stage("耐力", 5, 2, "recovery", (2, 3)),
                _stage("冷身", 5, 1, "cooldown", (1, 2))]},
    {"slug": "threshold-intervals-43", "name": "阈值间歇 · 43 分钟",
     "note": "示例模板，并非个人化处方；第一版只可编排，不能自动执行。",
     "stages": [_stage("热身", 10, 1, "warmup", (1, 2)),
                {"kind": "repeat", "name": "工作/恢复 × 4", "repeat_count": 4,
                 "steps": [_stage("工作", 4, 4, "main", (3, 5)),
                           _stage("恢复", 2, 1, "recovery", (1, 3))]},
                _stage("冷身", 9, 1, "cooldown", (1, 2))]},
]


def preset_catalog():
    return [{"slug": p["slug"], "name": p["name"], "note": p["note"],
             **summarize(p)} for p in _PRESETS]


def preset_by_slug(slug):
    for item in _PRESETS:
        if item["slug"] == slug:
            # Return only the user-editable plan document, never an internal template.
            return validate_plan({key: item[key] for key in ("name", "note", "stages")})
    return None


def validate_zone_settings(payload):
    if not isinstance(payload, dict):
        raise ValueError("区间设置必须是对象")
    result = {"ftp_w": None, "hr_max_bpm": None}
    for field, low, high in (("ftp_w", 60, 500), ("hr_max_bpm", 100, 230)):
        value = payload.get(field)
        if value is not None:
            result[field] = _integer(value, field, low, high)
    return result


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

    def get_zone_settings(self):
        with self.db() as db:
            row = db.execute("SELECT value FROM workout_settings WHERE key='zone_settings'").fetchone()
            return validate_zone_settings(json.loads(row["value"])) if row else validate_zone_settings({})

    def set_zone_settings(self, payload):
        value = validate_zone_settings(payload)
        with self.db() as db:
            db.execute("INSERT INTO workout_settings VALUES ('zone_settings', ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                       (json.dumps(value),))
        return value


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

    @app.get("/api/plans/presets")
    def get_presets(x_cycling_token: str | None = Header(default=None)):
        checked_store(x_cycling_token)
        return preset_catalog()

    @app.post("/api/plans/presets/{slug}/copy")
    def copy_preset(slug: str, x_cycling_token: str | None = Header(default=None)):
        store = checked_store(x_cycling_token)
        preset = preset_by_slug(slug)
        if preset is None:
            raise HTTPException(404, "预设课程不存在")
        return store.create(preset)

    @app.get("/api/plans/zones")
    def zones(x_cycling_token: str | None = Header(default=None)):
        return {"settings": checked_store(x_cycling_token).get_zone_settings(),
                "power": POWER_ZONES, "heart_rate": HR_ZONES}

    @app.put("/api/plans/zones")
    def set_zones(payload: dict, x_cycling_token: str | None = Header(default=None)):
        store = checked_store(x_cycling_token)
        try:
            return store.set_zone_settings(payload)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

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
