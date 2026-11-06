"""Tourplanung: Pläne speichern, Höhen aus dem Geländemodell."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401


def test_plan_crud_and_elevation(monkeypatch):
    from app import plan, elev
    import pytest
    from fastapi import HTTPException
    monkeypatch.setattr(elev, "terrain", lambda pts: [500 + 10 * i for i in range(len(pts))])
    r = plan.api_plan_elevation({"points": [[48, 8], [48.001, 8], [48.002, 8], [48.003, 8]]})
    assert r["up"] > 0 and r["down"] == 0 and r["max"] >= r["min"]
    with pytest.raises(HTTPException):
        plan.api_plan_elevation({"points": [[48, 8]]})
    pid = plan.api_plan_save({"name": "Testrunde", "sport": "hike", "pts": [[48, 8], [48.01, 8.01], [48.02, 8]], "km": 3.2, "up": 120, "est_h": 1.5})["id"]
    assert [p["name"] for p in plan.api_plans()] == ["Testrunde"]
    assert plan.api_plan_get(pid)["pts"][1] == [48.01, 8.01]
    plan.api_plan_save({"id": pid, "name": "Umbenannt", "pts": [[48, 8], [48.1, 8.1]]})
    assert plan.api_plans()[0]["name"] == "Umbenannt" and len(plan.api_plans()) == 1
    with pytest.raises(HTTPException):
        plan.api_plan_save({"name": "x", "pts": [[1, 1]]})
    plan.api_plan_delete = plan.api_plan_del
    plan.api_plan_del(pid)
    assert plan.api_plans() == []


def test_plan_guide_points():
    from app import plan, db
    import json
    gid = db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES('B','Gipfel',?,5,100)", (json.dumps([[48, 8], [48.01, 8.01, 900]]),))
    g = plan.api_plan_guide(gid)
    assert g["title"] == "Gipfel" and g["pts"] == [[48.0, 8.0], [48.01, 8.01]]
