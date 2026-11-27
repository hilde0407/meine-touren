"""3.63.0 – Eigene Reisen (trip_custom): anlegen, ändern, löschen; erscheinen in /api/trips, im PDF-Zugriff und in der Zählung der Wiederherstellung;
Vorrang vor erkannten Reisen (keine doppelten Touren); Name leeren entfernt keine Reise; Sicherung enthält die Tabelle."""
import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest
from fastapi import HTTPException
from tests.test_core import fresh  # noqa: F401


def _seed(monkeypatch):
    from app import db, more2
    from app.gpxtools import TZ
    ts = lambda d, h=10: int(datetime.fromisoformat(f"{d}T{h:02d}:00:00").replace(tzinfo=TZ).timestamp())
    def add(i, d, lat, lng, h=10):
        db.execute("INSERT INTO tours(id,name,sport,start_ts,dist_m,up_m,dur_s,lat,lng) VALUES(?,?,?,?,?,?,?,?,?)", (i, f"Tour {i}", "hike", ts(d, h), 10000, 300, 3600, lat, lng))
    for k in range(10):                                            # Zuhause
        add(f"h{k}", f"2026-03-{k + 1:02d}", 48.1, 11.5)
    for k in range(5):                                             # erkannte Reise (5 Tage, Teneriffa)
        add(f"a{k}", f"2026-06-{k + 1:02d}", 28.0, -16.5)
    for k in range(3):                                             # Kurzreise Rostock, 3 Tage (unter der Mindestzahl)
        add(f"r{k}", f"2026-08-{k + 10:02d}", 54.1, 12.1)
    monkeypatch.setattr(more2, "cover_photo", lambda ids: None)
    return db, more2


def test_anlegen_aendern_loeschen_und_liste(monkeypatch):
    db, m = _seed(monkeypatch)
    names = lambda: [t["region"] for t in m.api_trips()]
    assert not any(t.get("custom") for t in m.api_trips())
    r = m.api_trip_create({"name": "Rostock", "tours": ["r0", "r1", "r2"]})
    tid = r["id"]
    assert tid.startswith("eigen-")
    t = next(x for x in m.api_trips() if x["id"] == tid)
    assert t["region"] == "Rostock" and t["custom"] and t["tours"] == ["r0", "r1", "r2"] and t["days"] == 3 and t["start"] == "2026-08-10" and t["end"] == "2026-08-12" and t["km"] == 30.0
    assert next(x for x in m.all_trips() if x["id"] == tid)["region"] == "Rostock"            # Quelle für Reise-Seite, PDF, Zählung
    # Zeitraum ohne Touren-Auswahl: alle Touren der Tage
    t2 = m.api_trip_create({"name": "Nur Zeitraum", "start": "2026-03-01", "end": "2026-03-03"})["id"]
    assert next(x for x in m.api_trips() if x["id"] == t2)["tours"] == ["h0", "h1", "h2"]
    # ändern
    m.api_trip_edit(tid, {"name": "Rostock 2026", "tours": ["r0", "r1"]})
    t = next(x for x in m.api_trips() if x["id"] == tid)
    assert t["region"] == "Rostock 2026" and t["tours"] == ["r0", "r1"] and t["end"] == "2026-08-11"
    # löschen: Touren bleiben
    m.api_trip_delete(tid)
    assert tid not in [x["id"] for x in m.api_trips()] and db.one("SELECT COUNT(*) n FROM tours")["n"] == 18
    with pytest.raises(HTTPException) as e:
        m.api_trip_delete(tid)
    assert e.value.status_code == 404


def test_pruefungen(monkeypatch):
    db, m = _seed(monkeypatch)
    bad = [{"name": "", "tours": ["r0"]}, {"name": "x"}, {"name": "x", "start": "2026-08-12", "end": "2026-08-10"}, {"name": "x", "start": "kaputt", "end": "2026-08-10"},
           {"name": "x", "tours": ["gibtsnicht"]}, {"name": "x", "start": "2030-01-01", "end": "2030-01-02"}, {"name": "x", "tours": "r0"}]
    for b in bad:
        with pytest.raises(HTTPException) as e:
            m.api_trip_create(b)
        assert e.value.status_code == 400, b
    m.api_trip_create({"name": "Eins", "tours": ["r0", "r1"]})
    with pytest.raises(HTTPException) as e:                       # eine Tour gehört höchstens zu einer eigenen Reise
        m.api_trip_create({"name": "Zwei", "tours": ["r1", "r2"]})
    assert e.value.status_code == 400 and "Eins" in e.value.detail
    assert db.one("SELECT COUNT(*) n FROM trip_custom")["n"] == 1


def test_vorrang_vor_erkannter_reise_keine_doppelten_touren(monkeypatch):
    db, m = _seed(monkeypatch)
    db.put("home_lat", "48.1"); db.put("home_lng", "11.5")
    auto = [t for t in m.api_trips() if t["id"] == "a0"]
    assert auto and auto[0]["tours"] == ["a0", "a1", "a2", "a3", "a4"] and not auto[0].get("custom")
    c = m.api_trip_create({"name": "Strand", "tours": ["a3", "a4"]})["id"]
    trips = m.api_trips()
    a = next(t for t in trips if t["id"] == "a0")
    assert a["tours"] == ["a0", "a1", "a2"] and a["days"] == 3 and a["km"] == 30.0                 # Kennung der erkannten Reise bleibt, die Touren der eigenen fehlen
    alle = [i for t in trips for i in t["tours"]]
    assert len(alle) == len(set(alle))                                                              # keine Tour in zwei Reisen
    m.api_trip_edit("a0", {"name": "Kanaren"})                                                       # Name der erkannten Reise bleibt gültig
    assert next(t for t in m.api_trips() if t["id"] == "a0")["region"] == "Kanaren"
    # alle Touren der erkannten Reise in eigener Reise: erkannte verschwindet; Löschen bringt sie zurück
    m.api_trip_delete(c)
    c2 = m.api_trip_create({"name": "Alles", "start": "2026-06-01", "end": "2026-06-05"})["id"]
    assert "a0" not in [t["id"] for t in m.api_trips()]
    m.api_trip_delete(c2)
    assert next(t for t in m.api_trips() if t["id"] == "a0")["tours"] == ["a0", "a1", "a2", "a3", "a4"]


def test_name_leeren_entfernt_keine_reise(monkeypatch):
    db, m = _seed(monkeypatch)
    db.put("home_lat", "48.1"); db.put("home_lng", "11.5")
    # erkannte Reise (5 Tage): Name leeren = automatischer Name, Reise bleibt
    m.api_trip_edit("a0", {"name": "Mein Name"})
    assert next(t for t in m.api_trips() if t["id"] == "a0")["region"] == "Mein Name"
    r = m.api_trip_edit("a0", {"name": "   ", "start": "", "end": ""})
    t = next(t for t in m.api_trips() if t["id"] == "a0")
    assert t["region"] != "Mein Name" and r["ok"]
    # Kurzreise (3 Tage), nur durch eigenen Namen sichtbar: Zurücksetzen/Leeren lässt sie nicht verschwinden
    db.put("trip_min_days", "4")
    m.build_trips()
    short = next((t for t in m.build_trips() if "r0" in t["tours"]), None)
    assert short and short["days"] == 3 and "r0" not in [x for t in m.api_trips() for x in t["tours"]]
    m.api_trip_edit(short["id"], {"name": "Rostock"})
    assert [t["region"] for t in m.api_trips() if short["id"] == t["id"]] == ["Rostock"]
    r = m.api_trip_edit(short["id"], {"name": ""})
    assert r["bleibt"] is True and short["id"] in [t["id"] for t in m.api_trips()]
    r = m.api_trip_edit(short["id"], {})
    assert short["id"] in [t["id"] for t in m.api_trips()]
    # eigene Reise braucht einen Namen
    c = m.api_trip_create({"name": "Eigen", "tours": ["h0", "h1"]})["id"]
    with pytest.raises(HTTPException):
        m.api_trip_edit(c, {"name": " "})
    assert next(t for t in m.api_trips() if t["id"] == c)["region"] == "Eigen"


def test_entfernen_nur_fuer_erkannte_und_wiederherstellen(monkeypatch):
    db, m = _seed(monkeypatch)
    db.put("home_lat", "48.1"); db.put("home_lng", "11.5")
    m.api_trip_hide("a0", {"hide": True})
    assert "a0" not in [t["id"] for t in m.api_trips()] and [t["id"] for t in m.api_trips(hidden=1)] == ["a0"]
    c = m.api_trip_create({"name": "Eigen", "tours": ["h0", "h1"]})["id"]
    assert c not in [t["id"] for t in m.api_trips(hidden=1)] and c in [t["id"] for t in m.api_trips()]
    with pytest.raises(HTTPException) as e:
        m.api_trip_hide(c, {"hide": True})
    assert e.value.status_code == 400
    m.api_trip_hide("a0", {"hide": False})
    assert "a0" in [t["id"] for t in m.api_trips()]


def test_zaehlung_und_sicherung(monkeypatch, tmp_path):
    db, m = _seed(monkeypatch)
    from app import wiederherstellung
    n0 = wiederherstellung._reisen()
    m.api_trip_create({"name": "Eigen", "tours": ["h0", "h1"]})
    assert wiederherstellung._reisen() == n0 + 1
    import sqlite3
    from app import config
    # Die Tabelle liegt in der Datenbank-Datei und damit in jeder Sicherung/Wiederherstellung
    con = sqlite3.connect(str(config.DB_PATH))
    assert con.execute("SELECT name FROM trip_custom").fetchall() == [("Eigen",)]
    con.close()
