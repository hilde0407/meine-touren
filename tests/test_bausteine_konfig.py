"""3.19.0 – Konfigurierbare Bausteine, Backend: Layout-Validierung der Konfiguration (app/layout.py) und GET /api/bausteine/jahr (app/bausteine_daten.py).
Alle Daten sind konstruiert; erwartet wird von Hand gerechnet (nicht mit derselben Funktion)."""
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import bausteine_daten as bd, db  # noqa: E402
from app.gpxtools import TZ  # noqa: E402

HEUTE = date(2026, 6, 15)
# (id, Sportart, Datum, Strecke m, Aufstieg m, Dauer s)
DATA = [
    ("a", "hike", "2026-02-10", 10000, 300, 7200), ("b", "hike", "2026-05-20", 20000, 800, 10800), ("c", "mtb", "2026-05-21", 40000, 500, 7200),
    ("d", "hike", "2026-06-20", 5000, 100, 3600),                                                    # nach „heute“: zählt nirgends
    ("e", "hike", "2025-03-01", 8000, 200, 3600), ("f", "hike", "2025-09-01", 30000, 900, 9000), ("g", "mtb", "2025-04-01", 50000, 400, 10000),
    ("h", "hike", "2024-07-01", 12000, 300, 4000),
]


def seed():
    for tid, sp, d, dist, up, dur in DATA:
        ts = int(datetime.fromisoformat(d + "T12:00:00").replace(tzinfo=TZ).timestamp())
        db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,'t','komoot')",
                   (tid, tid, sp, ts, ts + dur, dist, dur, up, up, 50.0, 7.0))
    db.execute("INSERT INTO tours(id,name,sport,start_ts,dist_m,dur_s,up_m,status,source) VALUES('ohnezeit','x','hike',NULL,9999,10,1,'t','komoot')")      # ohne Startzeit: wird nie gezählt


def run(**kw):
    kw.setdefault("heute", HEUTE)
    return bd.jahr_auswertung(**kw)


def client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def test_jahr_year_with_and_without_sport_filter():
    seed()
    r = run()
    assert (r["touren"], r["km"], r["hm"]) == (3, 70, 1600) and abs(r["stunden"] - 25200 / 3600) < 1e-3 and r["sport"] == [] and r["von"] == "2026-01-01" and r["bis"] == "2026-06-15"
    assert r["reihe_km"][1] == 10 and r["reihe_km"][4] == 60 and sum(r["reihe_km"]) == 70 and len(r["reihe_km"]) == 12
    h = run(sport="hike")
    assert (h["touren"], h["km"], h["hm"]) == (2, 30, 1100) and abs(h["stunden"] - 5) < 1e-3 and h["reihe_km"][1] == 10 and h["reihe_km"][4] == 20 and h["vorher"] is None
    both = run(sport="hike,mtb")
    assert both["touren"] == 3 and both["sport"] == ["hike", "mtb"]
    assert run(sport="skitour")["touren"] == 0 and run(sport="skitour")["km"] == 0


def test_jahr_comparison_periods():
    seed()
    v = run(sport="hike", vergleich=True)["vorher"]
    assert v["von"] == "2025-01-01" and v["bis"] == "2025-06-15" and (v["touren"], v["km"]) == (1, 8)                        # Vorjahr bis zum selben Tag: nur „e“
    assert run(vergleich=True)["vorher"]["km"] == 58                                                                          # e (8) und g (50), nicht f
    y = run(zeitraum_="y", jahr=2025, sport="hike", vergleich=True)
    assert (y["touren"], y["km"], y["von"], y["bis"]) == (2, 38, "2025-01-01", "2025-12-31") and (y["vorher"]["touren"], y["vorher"]["km"]) == (1, 12)   # ganzes Vorjahr 2024: „h“
    a = run(zeitraum_="all", sport="hike", vergleich=True)
    assert (a["touren"], a["km"]) == (5, 80) and a["vorher"] is None and a["jahre"] == [2024, 2025, 2026] and a["reihe_km"] == [12, 38, 30]
    m = run(zeitraum_="12m", vergleich=True)
    assert m["von"] == "2025-07-01" and (m["touren"], m["km"]) == (4, 100) and len(m["reihe_km"]) == 12                          # f, a, b, c
    assert m["reihe_km"][2] == 30 and m["reihe_km"][7] == 10 and m["reihe_km"][10] == 60
    assert m["vorher"]["von"] == "2024-07-01" and m["vorher"]["bis"] == "2025-06-30" and m["vorher"]["km"] == 70              # h (12), e (8), g (50)
    n = run(zeitraum_="90d", vergleich=True)
    assert n["von"] == "2026-03-18" and (n["touren"], n["km"]) == (2, 60) and len(n["reihe_km"]) == 13 and n["reihe_km"][9] == 60
    assert n["vorher"]["von"] == "2025-12-18" and n["vorher"]["bis"] == "2026-03-17" and n["vorher"]["km"] == 10             # nur „a“ (10.02.)


def test_jahr_endpoint_validation_defaults_and_viewer_and_users():
    from fastapi.testclient import TestClient
    from app import main
    seed()
    with TestClient(main.app) as c:
        assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200
        seed()                                                                                                                  # Max hat eigene Touren (eigene Datenbank)
        r = c.get("/api/bausteine/jahr", params={"zeitraum": "all", "sport": "hike,mtb"})
        assert r.status_code == 200 and r.json()["touren"] >= 6 and r.json()["zeitraum"] == "all"
        assert c.get("/api/bausteine/jahr").json()["zeitraum"] == "year"
        for q in ({"zeitraum": "foo"}, {"sport": "a b"}, {"sport": "<x>"}, {"sport": ",".join("s%d" % i for i in range(21))}, {"zeitraum": "y", "jahr": 1800}, {"jahr": 3000}, {"jahr": "abc"}):
            assert c.get("/api/bausteine/jahr", params=q).status_code in (400, 422), q
        assert c.get("/api/bausteine/jahr", params={"sport": "hike,,mtb"}).json()["sport"] == ["hike", "mtb"]                    # leere Teile entfallen
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        c.post("/api/users", json={"name": "Eva", "email": "eva@example.com", "password": "evas-pass123", "role": "user"})
        assert TestClient(main.app).get("/api/bausteine/jahr").status_code in (401, 403)
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert v.get("/api/bausteine/jahr", params={"zeitraum": "all"}).status_code == 200                                      # Betrachter darf lesen …
        assert v.post("/api/bausteine/jahr", json={}).status_code in (403, 405)                                                 # … nicht schreiben
        e = TestClient(main.app)
        assert e.post("/api/login", json={"name": "eva", "password": "evas-pass123"}).status_code == 200
        r = e.get("/api/bausteine/jahr", params={"zeitraum": "all"}).json()
        assert r["touren"] == 0 and r["km"] == 0                                                                                # Benutzertrennung: Evas Datenbank ist leer
    assert main.VIEWER_GET.match("/api/bausteine/jahr")


GOOD = [
    {"widgets": [{"id": "w1", "type": "jahr", "cfg": {"sports": ["hike", "mtb"], "range": "y", "yr": 2025, "metrics": ["km", "count"], "compare": False, "title": "  Mein Wandern  "}}]},
    {"cfg": {"jahr": {"sports": ["hike"], "range": "12m"}}},
    {"widgets": [{"id": "w2", "type": "letzte", "cfg": {"n": 8, "sports": []}}, {"id": "w3", "type": "meilensteine", "cfg": {"basis": "all"}}]},
    {"widgets": [{"id": "w4", "type": "zukunft", "cfg": {"neu": "ok", "liste": ["a"], "zahl": 3}}]},                    # unbekannte Schlüssel einer neueren Version bleiben erlaubt
]
BAD = [
    {"widgets": [{"id": "w1", "type": "jahr", "cfg": {"sports": "hike"}}]}, {"widgets": [{"id": "w1", "type": "jahr", "cfg": {"sports": ["a b"]}}]},
    {"widgets": [{"id": "w1", "type": "jahr", "cfg": {"sports": ["x"] * 21}}]}, {"widgets": [{"id": "w1", "type": "jahr", "cfg": {"sports": [1]}}]},
    {"widgets": [{"id": "w1", "type": "jahr", "cfg": {"range": "decade"}}]}, {"widgets": [{"id": "w1", "type": "jahr", "cfg": {"range": 5}}]},
    {"widgets": [{"id": "w1", "type": "jahr", "cfg": {"yr": 1900}}]}, {"widgets": [{"id": "w1", "type": "jahr", "cfg": {"yr": "2025"}}]}, {"widgets": [{"id": "w1", "type": "jahr", "cfg": {"yr": True}}]},
    {"widgets": [{"id": "w1", "type": "jahr", "cfg": {"metrics": []}}]}, {"widgets": [{"id": "w1", "type": "jahr", "cfg": {"metrics": ["km", "speed"]}}]},
    {"widgets": [{"id": "w1", "type": "jahr", "cfg": {"compare": "ja"}}]}, {"widgets": [{"id": "w1", "type": "jahr", "cfg": {"title": "x" * 61}}]},
    {"widgets": [{"id": "w1", "type": "jahr", "cfg": {"title": 5}}]}, {"widgets": [{"id": "w1", "type": "letzte", "cfg": {"n": 11}}]}, {"widgets": [{"id": "w1", "type": "letzte", "cfg": {"n": 0}}]},
    {"widgets": [{"id": "w1", "type": "meilensteine", "cfg": {"basis": "dieses"}}]},
    {"cfg": []}, {"cfg": {"a b": {}}}, {"cfg": {"jahr": {"range": "x"}}}, {"cfg": {"jahr": []}}, {"cfg": {"k%d" % i: {} for i in range(11)}},
]


def test_layout_cfg_validation():
    with client() as c:
        for g in GOOD:
            r = c.put("/api/layout/uebersicht", json=g)
            assert r.status_code == 200, (g, r.text)
        r = c.put("/api/layout/uebersicht", json=GOOD[0]).json()["layout"]["widgets"][0]["cfg"]
        assert r["title"] == "Mein Wandern" and r["sports"] == ["hike", "mtb"] and r["compare"] is False                          # Titel bereinigt, Werte unverändert
        assert c.put("/api/layout/uebersicht", json={"widgets": [{"id": "w", "type": "jahr", "cfg": {"sports": ["hike", "hike"]}}]}).json()["layout"]["widgets"][0]["cfg"]["sports"] == ["hike"]
        c.put("/api/layout/uebersicht", json=GOOD[1])
        assert c.get("/api/layout/uebersicht").json()["layout"]["cfg"] == {"jahr": {"sports": ["hike"], "range": "12m"}}
        for b in BAD:
            assert c.put("/api/layout/uebersicht", json=b).status_code == 400, str(b)[:100]
        assert c.get("/api/layout/uebersicht").json()["layout"]["cfg"]["jahr"]["range"] == "12m"                                 # fehlgeschlagene Schreibversuche ändern nichts
        big = {"widgets": [{"id": "w%d" % i, "type": "jahr", "cfg": {"sports": ["sport_%02d_%s" % (j, "x" * 20) for j in range(20)], "title": "t" * 60}} for i in range(40)]}
        assert c.put("/api/layout/uebersicht", json=big).status_code == 400                                                      # Größenlimit gilt weiter


def test_layout_cfg_viewer_and_users():
    from fastapi.testclient import TestClient
    from app import main
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        assert c.put("/api/layout/uebersicht", json=GOOD[1]).status_code == 200
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        c.post("/api/users", json={"name": "Eva", "email": "eva@example.com", "password": "evas-pass123", "role": "user"})
        v = TestClient(main.app)
        v.post("/api/login", json={"name": "oma", "password": "omas-pass12"})
        assert v.get("/api/layout/uebersicht").json()["layout"] is None and v.put("/api/layout/uebersicht", json=GOOD[1]).status_code == 403
        e = TestClient(main.app)
        e.post("/api/login", json={"name": "eva", "password": "evas-pass123"})
        assert e.get("/api/layout/uebersicht").json()["layout"] is None                                                           # Evas Konfiguration ist getrennt
        assert e.put("/api/layout/uebersicht", json={"cfg": {"jahr": {"sports": ["mtb"]}}}).status_code == 200
        assert c.get("/api/layout/uebersicht").json()["layout"]["cfg"]["jahr"]["sports"] == ["hike"]


def test_version_and_notes_and_script_order():
    from app import config as cfg
    root = Path(__file__).resolve().parent.parent
    assert cfg.VERSION.startswith("3.42.0 · Meine Touren")
    notes = (root / "docs" / "versionen" / "3.19.0.md").read_text(encoding="utf-8")
    assert "Konfigurierbare Bausteine" in notes and "/api/bausteine/jahr" in notes and "53-filter.js" in notes
    html = (root / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("js/52-bausteine-uebersicht.js") < html.index("js/53-filter.js") < html.index("js/39-sw.js")
    assert 'const V = "mt-v124"' in (root / "app" / "static" / "sw.js").read_text(encoding="utf-8")
