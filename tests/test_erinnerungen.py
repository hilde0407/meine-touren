"""3.32.0 – Erinnerungen-Kachel, Server: Filter von GET /api/photos (Aktivität, Zeitraum, Kalendertag, beste Fotos), Whitelist-Prüfung, Layout-Konfiguration (streng geprüft),
Betrachter dürfen lesen, nichts Fremdes (Dateipfade) in der Antwort, Version und Hinweise."""
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _ts(d, h=10):
    from app.gpxtools import TZ
    return int(datetime(d.year, d.month, d.day, h, 0, tzinfo=TZ).timestamp())


def _years_back(n):
    t = date.today()
    try:
        return t.replace(year=t.year - n)
    except ValueError:                              # 29. Februar
        return t.replace(year=t.year - n, day=28)


def _seed():
    """Fünf Touren (zwei an einem Kalendertag wie heute in früheren Jahren) mit 13 Fotos; Bewertung und Schärfe stehen schon, damit nichts nachgerechnet werden muss."""
    from app import db
    db.init()
    tours = [("h0", "Heute vor einem Jahr", "hike", _years_back(1)), ("h1", "Heute vor zwei Jahren", "mtb", _years_back(2)), ("a0", "Rad am See", "mtb", date.today() - timedelta(days=9)),
             ("a1", "Wanderung alt", "hike", date.today() - timedelta(days=200)), ("a2", "Joggen", "jogging", date.today() - timedelta(days=30))]
    for tid, name, sp, d in tours:
        ts = _ts(d, 9)
        db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,5000,3600,100,100,'t','komoot')", (tid, name, sp, ts, ts + 3600))
    n = 0
    plan = {"h0": 3, "h1": 2, "a0": 4, "a1": 2, "a2": 2}
    for tid, k in plan.items():
        base = db.one("SELECT start_ts FROM tours WHERE id=?", (tid,))["start_ts"]
        for i in range(k):
            n += 1
            db.execute("INSERT INTO photos(path,mtime,size,taken_ts,tour_id,dated,rating,sharp,manual) VALUES(?,?,?,?,?,1,?,?,0)",
                       (f"/nirgends/geheim/p{n}.jpg", 1.0, 1000, base + 600 * (i + 1), tid, 5 if n in (1, 4, 6) else 0, 10.0))
    db.execute("INSERT INTO photos(path,mtime,size,taken_ts,tour_id,dated,rating,sharp,manual) VALUES('/nirgends/geheim/abgelehnt.jpg',1.0,1000,?, 'a0',1,5,10.0,2)", (_ts(date.today() - timedelta(days=9), 12),))
    return n


def _get(c, **q):
    from urllib.parse import urlencode
    return c.get("/api/photos?" + urlencode(q))


def test_default_call_is_unchanged_and_never_leaks_paths():
    _seed()
    with _client() as c:
        r = c.get("/api/photos?random=true&limit=6")
        assert r.status_code == 200 and len(r.json()) == 6
        for p in r.json():
            assert set(p) == {"id", "taken_ts", "tour_id", "lat", "lng", "manual", "offset_s", "tour_name"}
        assert len(c.get("/api/photos").json()) == 14
        assert "geheim" not in c.get("/api/photos?limit=100").text


def test_filter_by_activity():
    _seed()
    with _client() as c:
        mtb = _get(c, sport="mtb", limit=100).json()
        assert {p["tour_id"] for p in mtb} == {"h1", "a0"} and len(mtb) == 2 + 4 + 1             # inklusive des abgelehnten Fotos (der bisherige Aufruf filtert nichts weg)
        both = _get(c, sport="mtb,jogging", limit=100).json()
        assert {p["tour_id"] for p in both} == {"h1", "a0", "a2"}
        assert _get(c, sport="ski", limit=100).json() == []


def test_filter_by_period():
    _seed()
    with _client() as c:
        a = (date.today() - timedelta(days=40)).isoformat()
        got = _get(c, date_from=a, limit=100).json()
        assert {p["tour_id"] for p in got} == {"a0", "a2"}
        got = _get(c, date_from=a, date_to=(date.today() - timedelta(days=20)).isoformat(), limit=100).json()
        assert {p["tour_id"] for p in got} == {"a2"}
        assert {p["tour_id"] for p in _get(c, date_from=date.today().isoformat(), date_to=date.today().isoformat(), limit=100).json()} == set()
        assert len(_get(c, date_to=date.today().isoformat(), limit=100).json()) == 14


def test_same_calendar_day_in_earlier_years():
    _seed()
    md = date.today().strftime("%m-%d")
    with _client() as c:
        got = _get(c, day=md, before=date.today().year, limit=100).json()
        assert {p["tour_id"] for p in got} == {"h0", "h1"} and len(got) == 5
        assert {p["tour_id"] for p in _get(c, day=md, before=date.today().year - 1, limit=100).json()} == {"h1"}          # nur Jahre vor „before“
        assert {p["tour_id"] for p in _get(c, day=md, sport="hike", before=date.today().year, limit=100).json()} == {"h0"}
        assert {p["tour_id"] for p in _get(c, day=md, limit=100).json()} == {"h0", "h1"}
        other = (date.today() + timedelta(days=100)).strftime("%m-%d")
        assert _get(c, day=other, before=date.today().year, limit=100).json() == []


def test_best_photos_prefer_rated_ones_and_never_the_rejected():
    _seed()
    with _client() as c:
        got = _get(c, best="true", limit=3).json()
        assert len(got) == 3 and {p["id"] for p in got} == {1, 4, 6}
        assert all("path" not in p and "rating" not in p and "sharp" not in p for p in got)
        everyone = _get(c, best="true", limit=100).json()
        assert all(p["manual"] != 2 for p in everyone) and len(everyone) == 13               # das abgelehnte Foto fehlt
        assert {p["tour_id"] for p in _get(c, best="true", sport="jogging", limit=5).json()} == {"a2"}
        assert _get(c, best="true", day=(date.today() + timedelta(days=100)).strftime("%m-%d"), before=date.today().year).json() == []


def test_parameters_are_validated():
    _seed()
    with _client() as c:
        bad = [{"sport": "x') OR 1=1 --"}, {"sport": "a b"}, {"sport": ",".join("s%d" % i for i in range(21))}, {"sport": "ä"}, {"sport": "x" * 41},
               {"date_from": "2026-13-01"}, {"date_from": "26-01-01"}, {"date_to": "heute"}, {"date_from": "2026-05-02", "date_to": "2026-05-01"}, {"date_from": "1900-01-01"},
               {"day": "13-01"}, {"day": "02-30"}, {"day": "1-1"}, {"day": "'; DROP"}, {"day": "11-16", "before": 1800}, {"day": "11-16", "before": 3000}, {"before": 2026}]
        for q in bad:
            r = _get(c, **q)
            assert r.status_code == 400, (q, r.status_code)
        assert _get(c, day="02-29", before=2030).status_code == 200                           # Schalttag ist erlaubt
        assert _get(c, limit=-5).status_code == 200 and len(_get(c, limit=-5).json()) == 1     # kein „unbegrenzt“ mehr durch ein negatives Limit
        assert len(_get(c, limit=0).json()) == 1
        assert c.get("/api/photos?best=maybe").status_code == 422


def test_viewer_may_read_but_not_change():
    _seed()
    with _client() as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        assert c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"}).status_code == 200
        v = _client()
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        r = v.get("/api/photos?best=true&limit=3&sport=mtb")
        assert r.status_code == 200 and all("path" not in p for p in r.json())
        assert v.get("/api/photos?sport=%27%3B").status_code == 400
        assert v.get("/api/layout/uebersicht").json()["default"] is True                      # Betrachter bekommen immer den Standard (keine Einstellung der Kachel des Besitzers)
        assert v.put("/api/layout/uebersicht", json={"cfg": {"erinn": {"mode": "best"}}}).status_code == 403
        assert c.put("/api/layout/uebersicht", json={"cfg": {"erinn": {"mode": "best"}}}).status_code == 200


GOOD = {"mode": "day", "n": 12, "view": "show", "ratio": "169", "size": "l", "height": "h", "tempo": 8, "caption": True, "shuffle": True, "link": False,
        "sports": ["hike", "mtb"], "range": "y", "yr": 2024, "title": "Meine Erinnerungen"}


def test_layout_cfg_of_the_default_block_and_of_added_tiles_is_checked_strictly():
    with _client() as c:
        assert c.put("/api/layout/uebersicht", json={"cfg": {"erinn": GOOD}}).status_code == 200
        assert c.get("/api/layout/uebersicht").json()["layout"]["cfg"]["erinn"] == GOOD
        assert c.put("/api/layout/uebersicht", json={"cfg": {"erinn": {}}}).status_code == 200
        assert c.put("/api/layout/uebersicht", json={"widgets": [{"id": "wer1", "type": "erinn", "cfg": GOOD}, {"id": "wer2", "type": "erinn", "cfg": {"mode": "recent", "n": 3}}]}).status_code == 200
        assert [w["id"] for w in c.get("/api/layout/uebersicht").json()["layout"]["widgets"]] == ["wer1", "wer2"]
        assert c.put("/api/layout/uebersicht", json={"w": {"erinn": "drittel"}}).status_code == 200                       # Breite wie bei allen Bausteinen
        bad = [{"mode": "alle"}, {"mode": 1}, {"n": 5}, {"n": 12.5}, {"n": True}, {"n": "6"}, {"view": "film"}, {"ratio": "21:9"}, {"size": "xl"}, {"height": "x"}, {"tempo": 1}, {"tempo": 5.5},
               {"caption": "ja"}, {"shuffle": 1}, {"link": None}, {"sports": ["a b"]}, {"range": "forever"}, {"range": "y"}, {"yr": 2024}, {"yr": 1800, "range": "y"}, {"title": "x" * 61},
               {"frei": "erfunden"}, {"onclick": "alert(1)"}, {"title": 5}]
        for b in bad:
            assert c.put("/api/layout/uebersicht", json={"cfg": {"erinn": b}}).status_code == 400, b
            assert c.put("/api/layout/uebersicht", json={"widgets": [{"id": "wer1", "type": "erinn", "cfg": b}]}).status_code == 400, b
        assert c.put("/api/layout/uebersicht", json={"cfg": {"erinn": "mode"}}).status_code == 400
        assert c.put("/api/layout/statistik", json={"widgets": [{"id": "wer1", "type": "erinn", "cfg": {"n": 9}}]}).status_code == 200      # Typ ist allgemein erlaubt (die Oberfläche bietet ihn nur auf der Übersicht an)
        assert c.get("/api/layout/uebersicht").json()["layout"]["w"] == {"erinn": "drittel"}


def test_saved_layouts_without_cfg_stay_valid_and_the_registry_key_is_unchanged():
    js = (ROOT / "app" / "static" / "js" / "49-seitenlayout.js").read_text(encoding="utf-8")
    assert '{id: "erinn", w: "halb", title: "Erinnerungen", page: "uebersicht", group: "cols", plain: true, build: "erinn"}' in js
    with _client() as c:
        old = {"v": 1, "order": ["zuletzt", "jahr", "aufmacher", "tag", "erinn"], "hidden": ["erinn"], "w": {"erinn": "voll"}}
        assert c.put("/api/layout/uebersicht", json=old).status_code == 200
        assert c.get("/api/layout/uebersicht").json()["layout"] == old


def test_version_notes_service_worker_and_script_registration():
    from app import config
    assert config.VERSION.startswith("3.37.2 · Meine Touren")
    notes = (ROOT / "docs" / "versionen" / "3.32.0.md").read_text(encoding="utf-8")
    assert "Erinnerungen" in notes and "Diashow" in notes and "Datenschutz" in notes
    assert 'const V = "mt-v118"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    assert 'SL_APPV = "3.37.2"' in (ROOT / "app" / "static" / "js" / "54-ansichten.js").read_text(encoding="utf-8")
    assert "js/60-bausteine-erinnerungen.js" in (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    show = (ROOT / "app" / "static" / "js" / "seite-slideshow.js").read_text(encoding="utf-8")
    for k in ("sport", "date_from", "date_to", "day", "before", "recent", "best"):                # die Parameter, die der Link der Kachel setzt, versteht die Diashow
        assert f'"{k}"' in show, k
