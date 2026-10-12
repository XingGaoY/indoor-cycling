"""Relative FTP/HR zones, safe template copying, and visual-editor API tests."""
import os

os.environ.setdefault("CYCLING_TOKEN", "test-only")

import pytest
from fastapi.testclient import TestClient

from indoor_cycling.plans import (
    PlanStore, HR_ZONES, POWER_ZONES, preset_catalog, preset_by_slug,
    summarize, validate_plan, validate_zone_settings,
)
from indoor_cycling import server


def test_four_editable_presets_have_expected_lengths():
    lengths = {"recovery-30": 1800, "endurance-45": 2700,
               "tempo-40": 2400, "threshold-intervals-43": 2580}
    catalog = preset_catalog()
    assert {row["slug"]: row["duration_s"] for row in catalog} == lengths
    for slug in lengths:
        plan = preset_by_slug(slug)
        assert summarize(plan)["duration_s"] == lengths[slug]
        assert all("watts" not in s for s in plan["stages"] if s["kind"] == "constant")
    assert preset_by_slug("unknown") is None


def test_relative_targets_do_not_require_invented_ftp():
    plan = validate_plan({
        "name": "测试 Z2", "stages": [{
            "kind": "constant", "name": "耐力", "duration_s": 900,
            "power_zones": {"from": 2, "to": 2},
            "hr_zones": {"from": 2, "to": 3},
        }]
    })
    assert "watts" not in plan["stages"][0]
    assert plan["stages"][0]["power_zones"]["from"] == 2
    assert len(POWER_ZONES) == len(HR_ZONES) == 6
    assert POWER_ZONES[-1]["max_pct"] is None


@pytest.mark.parametrize("bad_stage", [
    {"kind": "constant", "name": "无效", "duration_s": 300, "power_zones": {"from": 2, "to": 3}},
    {"kind": "constant", "name": "无效", "duration_s": 300, "power_zones": {"from": 0, "to": 0}},
    {"kind": "ramp", "name": "无效", "duration_s": 300, "power_zones": {"from": 1, "to": 7}},
    {"kind": "ramp", "name": "无效", "duration_s": 300, "power_zones": {"from": True, "to": 2}},
    {"kind": "constant", "name": "无效", "duration_s": 300, "watts": 100,
     "hr_zones": {"from": 5, "to": 4}},
])
def test_bad_zones_rejected(bad_stage):
    with pytest.raises(ValueError):
        validate_plan({"name": "测试", "stages": [bad_stage]})


def test_legacy_watt_data_stays_compatible():
    plan = validate_plan({"name": "旧课程", "stages": [
        {"kind": "constant", "name": "起步", "duration_s": 300, "watts": 90},
        {"kind": "ramp", "name": "坡度", "duration_s": 300,
         "start_watts": 70, "end_watts": 120},
    ]})
    assert plan["stages"][0]["watts"] == 90
    assert plan["stages"][1]["end_watts"] == 120


def test_zone_reference_nullable_and_persistent(tmp_path):
    store = PlanStore(tmp_path / "data.sqlite3")
    assert store.get_zone_settings() == {"ftp_w": None, "hr_max_bpm": None}
    assert store.set_zone_settings({"ftp_w": 185, "hr_max_bpm": 190}) == {
        "ftp_w": 185, "hr_max_bpm": 190}
    assert PlanStore(store.db_path).get_zone_settings()["ftp_w"] == 185
    assert store.set_zone_settings({}) == {"ftp_w": None, "hr_max_bpm": None}
    for bad in ({"ftp_w": 59}, {"hr_max_bpm": 231}, {"ftp_w": True}, {"ftp_w": "185"}):
        with pytest.raises(ValueError):
            validate_zone_settings(bad)


def test_presets_remain_templates_after_copy_and_edit(tmp_path):
    store = PlanStore(tmp_path / "data.sqlite3")
    preset = preset_by_slug("endurance-45")
    a = store.create(preset)
    b = store.create(preset)
    assert a["id"] != b["id"]
    updated = {k: a[k] for k in ("name", "note", "stages")}
    updated["name"] = "用户自定义"
    assert store.update(a["id"], updated)["name"] == "用户自定义"
    assert store.get(b["id"])["name"] == preset["name"]
    assert preset_by_slug("endurance-45")["name"] == preset["name"]


def test_presets_zones_api_and_editor(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "DB", tmp_path / "visual.sqlite3")
    h = {"X-Cycling-Token": "test-only"}
    with TestClient(server.app) as client:
        assert client.get("/api/plans/presets").status_code == 401
        assert client.get("/api/plans/zones").status_code == 401
        assert client.get("/api/plans/zones", headers=h).json()["settings"]["ftp_w"] is None
        assert len(client.get("/api/plans/presets", headers=h).json()) == 4
        assert client.put("/api/plans/zones", headers=h, json={"ftp_w": 59}).status_code == 422
        assert client.put("/api/plans/zones", headers=h,
                          json={"ftp_w": 185, "hr_max_bpm": None}).status_code == 200
        response = client.post("/api/plans/presets/endurance-45/copy", headers=h)
        assert response.status_code == 200, response.text
        assert response.json()["stages"][1]["power_zones"] == {"from": 2, "to": 2}
        assert client.post("/api/plans/presets/missing/copy", headers=h).status_code == 404
        html = client.get("/plans").text
        for expected in ("功率 Z1–Z6", "心率 Z1–Z6", "id=\"chart\"", "id=\"presets\"",
                         "pointerdown", "chartPointerDown", "训练计划"):
            assert expected in html


def test_timeline_shape_toolbar_and_uniform_time_scale():
    from indoor_cycling.plans_page import HTML
    from indoor_cycling.mobile import shell
    page = shell(HTML, "/plans")
    # Drawing contracts: one elapsed-time scale, no artificial per-stage width minimum.
    for shape in ("constant", "rise", "fall", "repeat"):
        assert 'data-shape="' + shape + '"' in page
    assert 'aria-label="形状工具栏"' in page
    assert "const x=left+minute*pxPerMinute" in page
    assert "w=d/60*pxPerMinute" in page
    assert "x=left+elapsed/60*pxPerMinute" in page
    assert "Math.max(62" not in page
    assert "id=\"zoomIn\"" in page and "id=\"zoomOut\"" in page
    assert "shortDuration" not in page or "块内" in page
    assert "stageDuration(s)" in page
    assert "targetLabel(s,zones)" in page
    assert "expandedGroups.has(s)" in page
    assert "id=\"palette\"" not in page
    assert "id=\"addConstant\"" not in page
