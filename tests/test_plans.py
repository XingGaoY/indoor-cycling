"""Workout library validation and API contracts, fully simulator-only."""
import os
os.environ.setdefault("CYCLING_TOKEN", "test-only")
import pytest
from fastapi.testclient import TestClient
from indoor_cycling.plans import PlanStore, validate_plan, summarize
from indoor_cycling import server


def example():
    return {
        "name": "示例间歇课程", "note": "不要自动执行",
        "stages": [
            {"kind": "ramp", "name": "热身", "purpose": "warmup", "duration_s": 480,
             "start_watts": 50, "end_watts": 110},
            {"kind": "constant", "name": "稳定", "purpose": "main", "duration_s": 600, "watts": 110},
            {"kind": "repeat", "name": "间歇", "repeat_count": 5, "steps": [
                {"kind": "constant", "name": "工作", "purpose": "main", "duration_s": 120, "watts": 140},
                {"kind": "constant", "name": "恢复", "purpose": "recovery", "duration_s": 120, "watts": 70}
            ]},
            {"kind": "ramp", "name": "冷身", "purpose": "cooldown", "duration_s": 300,
             "start_watts": 110, "end_watts": 50}
        ]
    }


def test_example_43_minutes_and_expansion():
    plan = validate_plan(example())
    assert summarize(plan) == {"duration_s": 2580, "stage_count": 13}


@pytest.mark.parametrize("change", [
    lambda p: p["stages"][0].update(duration_s=0),
    lambda p: p["stages"][0].update(duration_s=True),
    lambda p: p["stages"][0].update(start_watts=501),
    lambda p: p["stages"][2].update(repeat_count=0),
    lambda p: p["stages"][2]["steps"].append({"kind": "repeat", "name": "嵌套"}),
    lambda p: p.update(stages=[]),
])
def test_invalid_plan_rejected(change):
    p = example()
    change(p)
    with pytest.raises(ValueError):
        validate_plan(p)


def test_store_persists_and_duplicate_and_remove(tmp_path):
    store = PlanStore(tmp_path / "sessions.sqlite3")
    one = store.create(example())
    assert store.get(one["id"])["name"] == "示例间歇课程"
    assert store.list()[0]["duration_s"] == 2580
    assert store.select(one["id"])
    assert store.selected()["id"] == one["id"]
    duplicate = store.duplicate(one["id"])
    assert duplicate["id"] != one["id"]
    assert "副本" in duplicate["name"]
    newer = example()
    newer["name"] = "更新后的名字"
    assert store.update(one["id"], newer)["name"] == newer["name"]
    restarted = PlanStore(store.db_path)
    assert restarted.selected()["id"] == one["id"]
    assert restarted.delete(one["id"])
    assert restarted.selected() is None
    assert restarted.get(one["id"]) is None
    assert restarted.get(duplicate["id"]) is not None


def test_api_auth_crud_and_page(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DB", tmp_path / "api.sqlite3")
    headers = {"X-Cycling-Token": "test-only"}
    with TestClient(server.app) as client:
        assert client.get("/api/plans").status_code == 401
        assert client.get("/api/plans/selected", headers=headers).json() is None
        bad = example()
        bad["stages"][0]["duration_s"] = 0
        assert client.post("/api/plans", headers=headers, json=bad).status_code == 422
        created = client.post("/api/plans", headers=headers, json=example())
        assert created.status_code == 200, created.text
        pid = created.json()["id"]
        assert client.get("/api/plans", headers=headers).json()[0]["id"] == pid
        assert client.get("/api/plans/" + pid, headers=headers).status_code == 200
        assert client.post("/api/plans/select", headers=headers, json={"id": pid}).json()["id"] == pid
        assert client.post("/api/plans/select", headers=headers, json={"id": "unknown"}).status_code == 404
        assert client.post("/api/plans/" + pid + "/duplicate", headers=headers).status_code == 200
        assert client.delete("/api/plans/" + pid, headers=headers).status_code == 200
        assert client.get("/api/plans/selected", headers=headers).json() is None
        assert client.get("/api/plans/" + pid, headers=headers).status_code == 404
        assert client.get("/plans").status_code == 200
        assert '主导航' in client.get("/plans").text
        assert 'href="/plans"' in client.get("/").text
