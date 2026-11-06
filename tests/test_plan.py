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


def test_route_proxy(monkeypatch):
    from app import plan
    import pytest
    from fastapi import HTTPException
    calls = []

    class R:
        status_code = 200
        text = ""
        def json(self):
            return {"features": [{"geometry": {"coordinates": [[8.0, 48.0, 500.0], [8.01, 48.005, 520.0], [8.02, 48.01, 540.0]]},
                                  "properties": {"track-length": "2500", "filtered ascend": "45", "total-time": "1800"}}]}

    def fake_get(url, params=None, **k):
        calls.append((url, params))
        return R()
    monkeypatch.setattr(plan.requests, "get", fake_get)
    r = plan.api_plan_route({"a": [48.0, 8.0], "b": [48.01, 8.02], "profile": "mtb", "alt": 2})
    assert r["km"] == 2.5 and r["up"] == 45 and r["pts"][0] == [48.0, 8.0, 500.0] and len(r["pts"]) == 3
    url, prm = calls[0]
    assert url.startswith("https://brouter.de") and prm["lonlats"] == "8.0,48.0|8.02,48.01" and prm["profile"] == "mtb" and prm["alternativeidx"] == 2 and prm["format"] == "geojson"
    plan.api_plan_route({"a": [48.0, 8.0], "b": [48.01, 8.02], "profile": "mtb", "alt": 2})
    assert len(calls) == 1                                                            # zweite Anfrage aus dem Zwischenspeicher
    R.status_code, R.text = 400, "no track found"
    with pytest.raises(HTTPException):
        plan.api_plan_route({"a": [48.0, 8.0], "b": [48.5, 8.5]})
    pid = plan.api_plan_save({"name": "R", "pts": [[48, 8], [48.1, 8.1]], "wps": {"wp": [[48, 8], [48.1, 8.1]], "alt": {"x": 1}, "rt": True}})["id"]
    assert plan.api_plan_get(pid)["wps"]["alt"] == {"x": 1}


def test_plan_switch_and_test(monkeypatch):
    from app import plan, db
    import pytest
    from fastapi import HTTPException
    assert plan.enabled() and plan._brouter_url() == plan.BROUTER
    db.put("brouter_url", "http://10.0.0.5:17777/brouter/")
    assert plan._brouter_url() == "http://10.0.0.5:17777/brouter"          # Adresse gesetzt → eigener Server (alte Einstellung)
    db.put("plan_mode", "public")
    assert plan._brouter_url() == plan.BROUTER                              # ausdrücklich öffentlicher Dienst
    db.put("plan_mode", "local")
    assert plan._brouter_url() == "http://10.0.0.5:17777/brouter"

    class R:
        status_code, text = 200, '{"features": []}'
    monkeypatch.setattr(plan.requests, "get", lambda *a, **k: R())
    assert plan.api_plan_test({"url": "http://x:17777/brouter"})["ok"]
    R.status_code, R.text = 200, "datafile E5_N45.rd5 not found"
    r = plan.api_plan_test({})
    assert r["ok"] and r["warn"] and "E5_N45" in r["msg"]
    with pytest.raises(HTTPException):
        plan.api_plan_test({"url": "ftp://x"})

    def boom(*a, **k):
        raise OSError("refused")
    monkeypatch.setattr(plan.requests, "get", boom)
    assert not plan.api_plan_test({})["ok"]
    db.put("plan_enabled", "0")
    assert not plan.enabled()
    with pytest.raises(HTTPException) as e:
        plan.api_plan_route({"a": [48.0, 8.0], "b": [48.01, 8.02]})
    assert e.value.status_code == 403
    db.put("plan_enabled", "1")


def test_plan_api_gate():
    from app import main, db
    from fastapi.testclient import TestClient
    c = TestClient(main.app)
    db.put("plan_enabled", "0")
    try:
        assert c.get("/api/plans").status_code == 403
        assert c.get("/api/plan/guide/x").status_code == 403
    finally:
        db.put("plan_enabled", "1")
    assert c.get("/api/plans").status_code == 200
