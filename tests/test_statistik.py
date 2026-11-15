"""3.22.0 – Statistikseite, Backend: Layout-Schlüssel „statistik“ (Validierung, Ansichten, Export-Prüfung, Betrachter, Benutzertrennung),
Filterparameter von GET /api/bausteine/jahr (zeitraum=c) und GET /api/bausteine/statistik, Version und Versionshinweise."""
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import bausteine_daten as bd, db  # noqa: E402
from app.gpxtools import TZ  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HEUTE = date(2026, 11, 15)


def client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def mk(tid, d, sport="hike", km=10, dur=3600, up=100, name=None):
    ts = int(datetime(d.year, d.month, d.day, 9, 0, tzinfo=TZ).timestamp())
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,?,?,'t','komoot')",
               (tid, name or tid, sport, ts, ts + dur, km * 1000, dur, up, up))


def seed():
    mk("a", date(2026, 3, 2), "hike", 12, 4 * 3600, 400)                 # Montag
    mk("b", date(2026, 3, 7), "touringbicycle", 40, 7200, 300)           # Samstag
    mk("c", date(2026, 9, 20), "hike", 28, 8 * 3600, 900)                # Sonntag
    mk("d", date(2025, 5, 4), "hike", 5, 3600, 50)                       # Sonntag, genau 5 km: Klasse 5–10
    mk("e", date(2025, 11, 1), "jogging", 60, 3 * 3600, 20)              # sehr schnell, aber nicht mehr als 50 km Laufen: Klasse über 50


# ------------------------------------------------------------------  Layout-Schlüssel „statistik“
def test_layout_key_statistik_saves_validates_and_is_separate():
    with client() as c:
        assert c.get("/api/layout/statistik").json()["layout"] is None
        doc = {"order": ["kpi", "heat"], "hidden": ["ziele"], "closed": ["tag"], "w": {"kmverlauf": "voll", "sportarten": "drittel"},
               "widgets": [{"id": "w1", "type": "sttop", "cfg": {"wert": "tempo", "n": 8, "eigen": True, "sports": ["hike"], "range": "12m"}},
                           {"id": "w2", "type": "stmonate", "cfg": {}}, {"id": "w3", "type": "heatmap", "cfg": {"sports": ["hike"]}}], "cfg": {"jahr": {"range": "all"}}}
        r = c.put("/api/layout/statistik", json=doc)
        assert r.status_code == 200, r.text
        got = c.get("/api/layout/statistik").json()
        assert got["layout"]["order"] == ["kpi", "heat"] and got["layout"]["w"]["sportarten"] == "drittel" and got["layout"]["widgets"][0]["cfg"]["eigen"] is True
        assert got["container"]["views"][0]["id"] == "standard"
        assert c.get("/api/layout/uebersicht").json()["layout"] is None and c.get("/api/layout/tour-haupt").json()["layout"] is None
        bad = [{"w": {"kpi": "riesig"}}, {"widgets": [{"id": "w1", "type": "sttop", "cfg": {"eigen": "ja"}}]}, {"widgets": [{"id": "w1", "type": "splits", "cfg": {}}]},
               {"widgets": [{"id": "w1", "type": "kennzahlen", "cfg": {}}]}, {"widgets": [{"id": "w1", "type": "sttop", "cfg": {"range": "c"}}]}, {"evil": 1}, {"order": ["a b"]}]
        for b in bad:
            assert c.put("/api/layout/statistik", json=b).status_code == 400, b
        # die Statistik-Bausteine gehören nur auf die Statistikseite, Bausteine der Übersicht dürfen dorthin
        for k in ("uebersicht", "tour-haupt", "tour-auswertung"):
            assert c.put(f"/api/layout/{k}", json={"widgets": [{"id": "w1", "type": "sttop", "cfg": {}}]}).status_code == 400, k
        assert c.put("/api/layout/tour-haupt", json={"widgets": [{"id": "w1", "type": "rekorde", "cfg": {}}]}).status_code == 200
        assert c.get("/api/layout/statistik").json()["layout"]["order"] == ["kpi", "heat"]      # nichts davon wurde überschrieben
        assert c.delete("/api/layout/statistik").status_code == 200 and c.get("/api/layout/statistik").json()["layout"] is None


def test_views_container_and_export_check_for_statistik():
    with client() as c:
        box = {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1}}, {"id": "v1", "name": "Training", "layout": {"order": ["tp"], "widgets": [{"id": "t-sttop", "type": "sttop", "cfg": {"wert": "tempo"}}]}}],
               "active": "v1", "rules": {}}
        assert c.put("/api/layout/statistik", json=box).status_code == 200
        assert c.get("/api/layout/statistik").json()["container"]["active"] == "v1"
        assert c.put("/api/layout/statistik", json=dict(box, rules={"hike": "v1"})).status_code == 400            # Regeln nach Sportart nur auf Tourseiten
        lay = box["views"][1]["layout"]
        doc = {"format": "meine-touren-ansicht", "format_version": 1, "app_version": "3.22.0", "page": "statistik", "name": "Training", "exported": "2026-11-15T10:00:00Z", "layouts": {"statistik": lay}}
        r = c.post("/api/layout/check", json=doc).json()
        assert r["ok"] is True and r["page"] == "statistik" and r["stats"]["statistik"]["types"] == ["sttop"], r
        wrong = dict(doc, page="uebersicht", layouts={"uebersicht": lay})
        assert c.post("/api/layout/check", json=wrong).json()["ok"] is False                                      # Statistik-Baustein in der Übersicht
        assert c.post("/api/layout/check", json=dict(doc, page="gibtsnicht")).json()["ok"] is False


def test_viewer_reads_default_cannot_write_and_users_are_separated():
    from fastapi.testclient import TestClient
    from app import main
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        assert c.put("/api/layout/statistik", json={"order": ["heat", "kpi"]}).status_code == 200
        assert c.post("/api/users", json={"name": "Anna", "email": "anna@example.com", "password": "annas-pass12", "role": "user"}).status_code == 200
        assert c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"}).status_code == 200
        a = TestClient(main.app)
        assert a.post("/api/login", json={"name": "anna", "password": "annas-pass12"}).status_code == 200
        assert a.get("/api/layout/statistik").json()["layout"] is None                       # Benutzertrennung
        assert a.put("/api/layout/statistik", json={"order": ["kpi"]}).status_code == 200
        assert c.get("/api/layout/statistik").json()["layout"]["order"] == ["heat", "kpi"]
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        g = v.get("/api/layout/statistik").json()
        assert g["layout"] is None and g["default"] is True
        assert v.put("/api/layout/statistik", json={"order": ["kpi"]}).status_code == 403 and v.delete("/api/layout/statistik").status_code == 403
        assert v.get("/api/bausteine/statistik").status_code == 200                           # Betrachter dürfen die Auswertung lesen
        assert TestClient(main.app).get("/api/bausteine/statistik").status_code == 401


# ------------------------------------------------------------------  Filterparameter der Endpunkte
def test_statistik_endpoint_filters_sport_and_period():
    seed()
    s = bd.statistik_auswertung(zeitraum_="all", heute=HEUTE)
    assert s["touren"] == 5 and s["km"] == 145 and s["hm"] == 1670 and s["von"] is None
    assert [m["monat"] for m in s["monate"]][:2] == ["2025-05", "2025-06"] and s["monate"][-1]["monat"] == "2026-11" and len(s["monate"]) == 19
    assert next(m for m in s["monate"] if m["monat"] == "2026-03")["touren"] == 2
    h = bd.statistik_auswertung(sport="hike", zeitraum_="all", heute=HEUTE)
    assert h["touren"] == 3 and h["km"] == 45 and h["sport"] == ["hike"]
    mix = bd.statistik_auswertung(sport="hike,touringbicycle", zeitraum_="y", jahr=2026, heute=HEUTE)
    assert mix["touren"] == 3 and mix["von"] == "2026-01-01" and mix["bis"] == "2026-12-31" and len(mix["monate"]) == 12
    y = bd.statistik_auswertung(zeitraum_="12m", heute=HEUTE)                                  # 2025-12-01 bis heute: nur 2026
    assert y["touren"] == 3 and y["von"] == "2025-12-01"
    d = bd.statistik_auswertung(zeitraum_="90d", heute=HEUTE)
    assert d["touren"] == 1 and d["von"] == "2026-08-18" and d["km"] == 28
    c = bd.statistik_auswertung(zeitraum_="c", von_="2026-03-01", bis_="2026-03-31", heute=HEUTE)
    assert c["touren"] == 2 and c["km"] == 52 and [m["monat"] for m in c["monate"]] == ["2026-03"]
    # Wochentage (Mo = 0), Längenklassen (unter 5, 5–10, 10–15, 15–20, 20–30, 30–50, über 50)
    assert s["wochentage"]["touren"] == [1, 0, 0, 0, 0, 2, 2] and s["wochentage"]["km"][6] == 33
    assert s["laengen"]["anzahl"] == [0, 1, 1, 0, 1, 1, 1] and s["laengen"]["grenzen"] == [5, 10, 15, 20, 30, 50]


def test_statistik_endpoint_top_and_validation():
    seed()
    top = bd.statistik_auswertung(wert="km", n=2, heute=HEUTE)["top"]
    assert [t["id"] for t in top] == ["e", "b"] and top[0]["km"] == 60 and top[0]["kmh"] == 20
    assert [t["id"] for t in bd.statistik_auswertung(wert="hm", n=1, heute=HEUTE)["top"]] == ["c"]
    assert bd.statistik_auswertung(wert="dauer", n=1, heute=HEUTE)["top"][0]["id"] == "c"
    assert [t["id"] for t in bd.statistik_auswertung(wert="tempo", n=3, heute=HEUTE)["top"]] == ["e", "b", "d"]          # e 20, b 20 (Gleichstand), d 5 km/h, c 3,5 km/h
    with client() as c:
        g = lambda **q: c.get("/api/bausteine/statistik", params=q)
        assert g(zeitraum="all").status_code == 200 and g(sport="hike", zeitraum="y", jahr=2026).json()["touren"] >= 0
        for q in ({"zeitraum": "x"}, {"sport": "a b"}, {"sport": ",".join("s%d" % i for i in range(21))}, {"jahr": 1800}, {"zeitraum": "c"}, {"zeitraum": "c", "von": "2026-02-01", "bis": "2026-01-01"},
                  {"zeitraum": "c", "von": "kaputt", "bis": "2026-01-01"}, {"wert": "alles"}, {"n": 0}, {"n": 21}):
            assert g(**q).status_code in (400, 422), q
        j = c.get("/api/bausteine/jahr", params={"zeitraum": "c", "von": "2026-03-01", "bis": "2026-03-31", "sport": "hike"}).json()
        assert j["touren"] == 1 and j["km"] == 12 and j["von"] == "2026-03-01" and j["vorher"] is None and j["reihe_km"] == [12]
        assert c.get("/api/bausteine/jahr", params={"zeitraum": "c"}).status_code == 400
        assert c.get("/api/bausteine/jahr", params={"zeitraum": "year", "vergleich": 1}).status_code == 200        # bisheriges Verhalten bleibt


def test_view_filter_field_is_validated_stored_per_view_and_in_exports():
    with client() as c:
        ok = {"sports": ["hike", "mtb"], "range": "c", "from": "2026-01-01", "to": "2026-03-31"}
        for key in ("statistik", "uebersicht", "tour-haupt"):
            r = c.put(f"/api/layout/{key}", json={"filter": ok, "order": []})
            assert r.status_code == 200, (key, r.text)
            assert c.get(f"/api/layout/{key}").json()["layout"]["filter"] == ok
        assert c.put("/api/layout/statistik", json={"filter": {"range": "y", "yr": 2025}}).status_code == 200
        assert c.get("/api/layout/statistik").json()["layout"]["filter"] == {"range": "y", "yr": 2025}
        bad = [{"range": "c"}, {"range": "c", "from": "2026-05-01", "to": "2026-01-01"}, {"range": "c", "from": "x", "to": "y"}, {"range": "y"}, {"range": "all", "yr": 2025},
               {"range": "all", "from": "2026-01-01", "to": "2026-02-01"}, {"range": "forever"}, {"sports": ["a b"]}, {"sports": "hike"}, {"range": "all", "extra": 1}, "all", []]
        for b in bad:
            assert c.put("/api/layout/statistik", json={"filter": b}).status_code == 400, b
        assert c.get("/api/layout/statistik").json()["layout"]["filter"] == {"range": "y", "yr": 2025}      # Fehlversuche ändern nichts
        # Der Filter gehört zur Ansicht: je Ansicht ein eigener, im Behälter gespeichert
        box = {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1, "filter": {"range": "12m"}}}, {"id": "v1", "name": "Laufen", "layout": {"v": 1, "filter": {"range": "all", "sports": ["jogging"]}}}], "active": "standard"}
        assert c.put("/api/layout/statistik", json=box).status_code == 200
        got = c.get("/api/layout/statistik").json()["container"]["views"]
        assert got[0]["layout"]["filter"] == {"range": "12m"} and got[1]["layout"]["filter"]["sports"] == ["jogging"]
        doc = {"format": "meine-touren-ansicht", "format_version": 1, "app_version": "3.22.0", "page": "statistik", "name": "Laufen", "exported": "2026-11-15T10:00:00Z", "layouts": {"statistik": box["views"][1]["layout"]}}
        assert c.post("/api/layout/check", json=doc).json()["ok"] is True
        doc["layouts"]["statistik"] = {"v": 1, "filter": {"range": "nie"}}
        assert c.post("/api/layout/check", json=doc).json()["ok"] is False


def test_version_and_notes():
    from app import config
    assert config.VERSION.startswith("3.26.0 · Meine Touren")
    notes = (ROOT / "docs" / "versionen" / "3.22.0.md").read_text(encoding="utf-8")
    assert "Statistik" in notes and "globale" in notes.lower() and "Bewusst nicht enthalten" in notes
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("js/55-vorlagen.js") < html.index("js/56-statistik.js") < html.index("js/57-bausteine-statistik.js") < html.index("js/39-sw.js")
    assert 'const V = "mt-v104"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
