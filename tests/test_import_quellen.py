"""3.31.0 – Import-Knopf je nach Uhr, Server: GET /api/import-quellen (Zepp, Garmin, Suunto, Marken aus „Meine Geräte“), Läufe von Garmin und Suunto als Jobs mit gemerktem
Ergebnis (ohne Zugangsdaten), Layout-Feld kopf.holen. Es wird NIE ein echtes Konto kontaktiert: garmin_sync, suunto_sync und export_zepp werden ersetzt."""
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401


def _by(d):
    return {q["kind"]: q for q in d["quellen"]}


def _wait(c):
    for _ in range(200):
        if not c.get("/api/jobs").json()["running"]:
            return c.get("/api/jobs").json()
        time.sleep(0.05)
    raise AssertionError("Job läuft noch")


def test_nichts_verbunden_und_nichts_angelegt():
    from app import devices
    d = devices.import_quellen()
    q = _by(d)
    assert list(q) == ["zepp", "garmin", "suunto"] and not any(x["verbunden"] or x["laeuft"] or x["letzter"] for x in q.values())
    assert q["garmin"]["label"] == "Garmin" and q["zepp"]["job"] == "export" and q["garmin"]["job"] == "garmin-import" and q["suunto"]["job"] == "suunto-import"
    assert d["geraete"] == [] and d["laeuft"] is None


def test_verbundene_konten_je_art():
    from app import db, devices
    db.put("zepp_token", "ZEPPGEHEIM123")
    assert [k for k, x in _by(devices.import_quellen()).items() if x["verbunden"]] == ["zepp"]
    db.put("garmin_tokens", json.dumps({"di_token": "GARMINGEHEIM"}))
    db.put("suunto_tokens", json.dumps({"access_token": "SUUNTOGEHEIM"}))
    d = devices.import_quellen()
    assert [k for k, x in _by(d).items() if x["verbunden"]] == ["zepp", "garmin", "suunto"]
    assert "GEHEIM" not in json.dumps(d)                                         # nie Zugangsdaten
    db.put("suunto_tokens", "")
    db.put("suunto_client_id", "x"); db.put("suunto_client_secret", "y"); db.put("suunto_key", "z")      # nur konfiguriert, nicht verbunden: zählt nicht
    assert not _by(devices.import_quellen())["suunto"]["verbunden"]


def test_marken_aus_meine_geraete(monkeypatch):
    from app import db, devices
    for n, k, a in (("Fenix", "garmin", 1), ("Vantage", "polar", 1), ("Altes Handy", "phone", 1), ("Alte Polar", "polar", 0), ("Spartan", "suunto", 1), ("Bip", "zepp", 1)):
        db.execute("INSERT INTO devices(name,kind,model,since,until,active,note,zsrc) VALUES(?,?,?,?,?,?,?,?)", (n, k, "", "", "", a, "", ""))
    g = devices.import_quellen()["geraete"]
    assert sorted((x["kind"], x["konto"]) for x in g) == [("garmin", True), ("phone", False), ("polar", False), ("suunto", True), ("zepp", True)]      # je Art einmal, nur aktive
    assert {x["kind"]: x["label"] for x in g}["polar"] == "Polar" and {x["kind"]: x["label"] for x in g}["phone"] == "Handy-Aufzeichnung"
    db.put("garmin_tokens", json.dumps({"di_token": "t"}))                       # verbundene Marke steht nicht mehr unter „ohne Konto“
    assert "garmin" not in [x["kind"] for x in devices.import_quellen()["geraete"]]


def test_garmin_lauf_merkt_ergebnis_ohne_zugangsdaten(monkeypatch):
    from app import db, devices
    db.put("garmin_tokens", json.dumps({"di_token": "GARMINGEHEIM"}))
    monkeypatch.setattr(devices, "garmin_sync", lambda limit=None: {"imported": 4, "dup": 1, "nogps": 2, "error": 0})
    assert devices.garmin_sync_lauf()["imported"] == 4
    l = _by(devices.import_quellen())["garmin"]["letzter"]
    assert l["ok"] is True and l["neu"] == 4 and l["uebernommen"] == 4 and l["dup"] == 1 and l["ohne_gps"] == 2 and l["fehler"] == 0 and l["ts"] > 0
    monkeypatch.setattr(devices, "garmin_sync", lambda limit=None: (_ for _ in ()).throw(devices.DeviceError("Anmeldung abgelehnt, Token GARMINGEHEIM ungültig")))
    with pytest.raises(devices.DeviceError):
        devices.garmin_sync_lauf()
    l = _by(devices.import_quellen())["garmin"]["letzter"]
    assert l["ok"] is False and l["code"] == "anmeldung" and "GARMINGEHEIM" not in json.dumps(l) and "GARMINGEHEIM" not in (db.get("garmin_last_run") or "")


def test_suunto_lauf_und_zepp_normalisiert(monkeypatch):
    from app import db, devices, sync
    db.put("suunto_tokens", json.dumps({"access_token": "SUUNTOGEHEIM"}))
    monkeypatch.setattr(devices, "suunto_sync", lambda limit=None: {"imported": 0, "dup": 0, "nogps": 0, "error": 0})
    devices.suunto_sync_lauf()
    assert _by(devices.import_quellen())["suunto"]["letzter"]["neu"] == 0
    monkeypatch.setattr(devices, "suunto_sync", lambda limit=None: (_ for _ in ()).throw(RuntimeError("Timeout SUUNTOGEHEIM")))
    with pytest.raises(RuntimeError):
        devices.suunto_sync_lauf()
    l = _by(devices.import_quellen())["suunto"]["letzter"]
    assert l["ok"] is False and l["code"] == "netz" and "SUUNTOGEHEIM" not in json.dumps(l)
    db.put("zepp_token", "x")
    monkeypatch.setattr(sync, "export_zepp", lambda limit=None: {"gesamt": 5, "neu": 2, "gps": 2, "ohne_gps": 1, "uebernommen": 1, "fehler": 0})
    sync.export_zepp_lauf()
    l = _by(devices.import_quellen())["zepp"]
    assert l["uebernimmt"] is False and l["letzter"]["neu"] == 2 and l["letzter"]["uebernommen"] == 1 and l["letzter"]["ohne_gps"] == 1 and l["letzter"]["gps"] == 2


def test_endpunkt_jobs_nacheinander_und_ein_lauf_zur_zeit(monkeypatch):
    from fastapi.testclient import TestClient
    from app import db, devices, main, sync
    gate = {"go": False, "calls": []}

    def garmin(limit=None):
        gate["calls"].append("garmin")
        while not gate["go"]:
            time.sleep(0.02)
        return {"imported": 2, "dup": 0, "nogps": 0, "error": 0}
    monkeypatch.setattr(devices, "garmin_sync", garmin)
    monkeypatch.setattr(devices, "suunto_sync", lambda limit=None: gate["calls"].append("suunto") or {"imported": 1, "dup": 0, "nogps": 0, "error": 0})
    monkeypatch.setattr(sync, "export_zepp", lambda limit=None: gate["calls"].append("zepp") or {"gesamt": 0, "neu": 0, "gps": 0, "ohne_gps": 0, "uebernommen": 0, "fehler": 0})
    db.put("garmin_tokens", json.dumps({"di_token": "t"}))
    with TestClient(main.app) as c:
        r = c.get("/api/import-quellen")
        assert r.status_code == 200 and _by(r.json())["garmin"]["verbunden"] and not _by(r.json())["garmin"]["laeuft"]
        assert c.post("/api/jobs/garmin-import").status_code == 200
        for _ in range(100):
            if gate["calls"]:
                break
            time.sleep(0.02)
        d = c.get("/api/import-quellen").json()
        assert _by(d)["garmin"]["laeuft"] and d["laeuft"] == "Garmin-Import" and not _by(d)["zepp"]["laeuft"]
        assert c.post("/api/jobs/suunto-import").status_code == 409 and c.post("/api/jobs/export").status_code == 409      # nie parallel
        assert c.post("/api/garmin/sync").status_code == 409
        gate["go"] = True
        assert _wait(c)["ok"] is True
        assert _by(c.get("/api/import-quellen").json())["garmin"]["letzter"]["neu"] == 2
        assert c.post("/api/jobs/suunto-import").status_code == 200
        _wait(c)
        assert gate["calls"] == ["garmin", "suunto"]
        assert c.post("/api/garmin/sync").status_code == 200                      # der Weg der Verwaltung läuft weiter (und merkt jetzt ebenfalls das Ergebnis)
        _wait(c)
        db.put("garmin_tokens", "")
        assert c.post("/api/garmin/sync").status_code == 400


def test_layout_feld_kopf_holen():
    from fastapi import HTTPException
    from app import layout
    assert layout.clean({"kopf": {"holen": False}}, "uebersicht")["kopf"] == {"holen": False}
    assert "kopf" not in layout.clean({"kopf": {"holen": True}}, "uebersicht") and "kopf" not in layout.clean({"kopf": {}}, "uebersicht")      # Standard (an) wird nicht gespeichert
    for bad in ({"holen": "nein"}, {"holen": 0}, {"x": True}, [True], "aus"):
        with pytest.raises(HTTPException):
            layout.clean({"kopf": bad}, "uebersicht")
    # die Ansicht (Behälter) führt das Feld mit
    doc = {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1, "kopf": {"holen": False}}}], "active": "standard", "rules": {}}
    assert layout.clean_container(doc, "uebersicht")["views"][0]["layout"]["kopf"] == {"holen": False}
