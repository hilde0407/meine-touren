"""3.18.0 – Daten für die Bausteine: GET /api/bausteine/<name> (app/bausteine_daten.py).
Alle Daten sind konstruiert (gerade Strecke mit bekannten Zeiten und Höhen), Leerfälle, Zwischenspeicher, Betrachter, Benutzertrennung, Versionshinweise."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import bausteine_daten as bd, db, routes  # noqa: E402

T0 = 1782032400            # 2026-06-21 09:00 UTC = 11:00 Ortszeit (Sommer)
M = 111195.0               # Meter je Breitengrad


def line(speed1=2.0, speed2=1.0, pause=300, time=True, alt=True, n=320):
    """Gerade Strecke nach Norden, alle 10 m ein Punkt: erste 1600 m mit 10 % Steigung und 2 m/s, dann eine Pause, dann 1600 m eben mit 1 m/s."""
    pts, t = [], 0.0
    for i in range(n + 1):
        d = i * 10.0
        if i:
            t += 10.0 / (speed1 if d <= 1600 else speed2)
        a = 500 + 0.1 * d if d <= 1600 else 660.0
        pts.append((52.0 + d / M, 13.0, a if alt else None, int(t * 1000) if time else None))
        if i == 160:                                             # Pause am Wendepunkt: gleicher Ort, 300 s später
            t += pause
            pts.append((52.0 + d / M, 13.0, a if alt else None, int(t * 1000) if time else None))
    return pts


def mk(tid, route=None, ts=T0, dur=3000, dist=3200, lat=52.52, lng=13.405, name=None):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,'t','komoot')",
               (tid, name or tid, "hike", ts, ts + dur, dist, dur, 160, 0, lat, lng))
    if route:
        routes.store(tid, route)


def client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def get(c, name, **q):
    r = c.get(f"/api/bausteine/{name}", params=q)
    assert r.status_code == 200, r.text
    return r.json()


def test_splits_steigung_bewegung_gipfel_profil():
    mk("a", line())
    with client() as c:
        s = get(c, "splits", tour="a")
        assert s["status"] == "ok" and s["schritt_m"] == 1000
        v = s["splits"]
        assert [x["km"] for x in v] == [1.0, 2.0, 3.0, 3.2] and v[-1]["teil"] is True and not v[0].get("teil")
        assert abs(v[0]["dauer_s"] - 500) < 2 and abs(v[0]["kmh"] - 7.2) < 0.1            # 1 km mit 2 m/s
        assert abs(v[1]["dauer_s"] - 700) < 3                                            # 600 m mit 2 m/s + 400 m mit 1 m/s, die Pause zählt nicht
        assert abs(v[2]["dauer_s"] - 1000) < 3 and abs(v[3]["dauer_s"] - 200) < 3
        assert abs(v[0]["hm"] - 100) < 2 and abs(v[2]["hm"]) < 2
        st = get(c, "steigung", tour="a")
        assert st["status"] == "ok" and set(st["anteile"]) == set(bd.NAMEN)
        assert abs(sum(st["anteile"].values()) - 1) < 0.01
        assert abs(st["anteile"]["auf"] - 0.5) < 0.06 and abs(st["anteile"]["eben"] - 0.5) < 0.06
        b = get(c, "bewegung", tour="a")
        assert b["gesamt_s"] == 2700 and b["pause_s"] == 300 and b["bewegung_s"] == 2400
        assert [x[0] for x in b["abschnitte"]] == ["b", "p", "b"] and b["abschnitte"][1][1:] == [800, 1100]
        g = get(c, "gipfel", tour="a", ab=600)
        assert g["hoch_m"] == 660 and g["tief_m"] == 500 and g["nach_s"] == 800 and abs(g["bei_m"] - 1600) < 15
        assert g["ab_m"] == 600 and abs(g["ueber_anteil"] - 0.6875) < 0.05
        assert "ueber_anteil" not in get(c, "gipfel", tour="a")
        assert get(c, "gipfel", tour="a", ab=900)["ueber_anteil"] == 0
        p = get(c, "profil", tour="a")
        assert p["status"] == "ok" and 2 <= len(p["h"]) <= bd.MAX_PROFIL and len(p["d"]) == len(p["h"]) and p["d"][0] == 0 and abs(p["d"][-1] - 3200) < 20
        assert abs(max(p["h"]) - 660) < 3


def test_long_tour_uses_larger_steps():
    n = 5000                                                     # 50 km
    pts = [(52.0 + i * 10.0 / M, 13.0, 300.0, i * 5000) for i in range(n + 1)]
    mk("lang", pts, dist=50000)
    with client() as c:
        s = get(c, "splits", tour="lang")
        assert s["schritt_m"] == 2000 and len(s["splits"]) == 25 and abs(s["splits"][0]["kmh"] - 7.2) < 0.1


def test_empty_cases_and_errors():
    mk("ohne", None)
    mk("zeit", line(time=False))
    mk("hoehe", line(alt=False))
    mk("kurz", [(52.0 + i * 10.0 / M, 13.0, 300.0, i * 5000) for i in range(20)], dist=190)
    with client() as c:
        assert get(c, "splits", tour="ohne")["status"] == "keine_strecke" and get(c, "gipfel", tour="ohne")["status"] == "keine_strecke"
        assert get(c, "splits", tour="zeit")["status"] == "keine_zeit" and get(c, "bewegung", tour="zeit")["status"] == "keine_zeit"
        assert get(c, "profil", tour="zeit")["status"] == "ok" and get(c, "steigung", tour="zeit")["status"] == "ok"
        assert get(c, "profil", tour="hoehe")["status"] == "keine_hoehe" and get(c, "gipfel", tour="hoehe")["status"] == "keine_hoehe"
        assert get(c, "splits", tour="hoehe")["status"] == "ok"
        assert get(c, "splits", tour="kurz")["status"] == "zu_kurz"
        assert c.get("/api/bausteine/splits", params={"tour": "gibtsnicht"}).status_code == 404
        assert c.get("/api/bausteine/splits").status_code == 400
        assert c.get("/api/bausteine/unbekannt").status_code == 404
        assert get(c, "ausruestung") == [] and get(c, "geplant") == []


def test_cache_is_used_and_invalidated(monkeypatch):
    mk("c", line())
    with client() as c:
        get(c, "splits", tour="c")
        f = bd._cache_path("c")
        assert f.exists()
        monkeypatch.setattr(bd, "analyse", lambda pts: (_ for _ in ()).throw(AssertionError("sollte aus dem Zwischenspeicher kommen")))
        assert get(c, "profil", tour="c")["status"] == "ok"
        routes.store("c", line(speed1=4.0))                     # Quelldatei ändert sich: neu rechnen
        monkeypatch.undo()
        assert get(c, "splits", tour="c")["splits"][0]["kmh"] > 12


def test_tageslicht():
    mk("t", line(), dur=7200)                                    # 11:00 bis 13:00 Ortszeit
    mk("nacht", line(), ts=T0 + 13 * 3600, dur=3600, name="nacht")   # 22:00 bis 23:00 Ortszeit
    mk("polar", line(), lat=78.2, lng=15.6, name="polar")
    mk("ohnepos", line(), lat=None, lng=None, name="ohnepos")
    with client() as c:
        d = get(c, "tageslicht", tour="t")
        assert d["status"] == "ok" and d["datum"] == "2026-06-21"
        assert 4 * 60 + 35 <= d["aufgang_min"] <= 4 * 60 + 55 and 21 * 60 + 22 <= d["untergang_min"] <= 21 * 60 + 45        # Berlin, Sommersonnenwende
        assert d["daemm_von_min"] < d["aufgang_min"] < d["untergang_min"] < d["daemm_bis_min"]
        assert d["start_min"] == 660 and d["ende_min"] == 780 and d["hell_min"] == 120 and d["dunkel_min"] == 0
        assert 1000 <= d["tag_min"] <= 1020
        n = get(c, "tageslicht", tour="nacht")
        assert n["hell_min"] == 0 and n["dunkel_min"] == 60
        assert get(c, "tageslicht", tour="polar")["status"] == "polar"
        assert get(c, "tageslicht", tour="ohnepos")["status"] == "keine_position"


def test_sun_known_values():
    from datetime import date
    # München, 21.12.: Aufgang etwa 08:00, Untergang etwa 16:24 (Ortszeit MEZ = UTC+1)
    a, b = bd._sonne(date(2026, 12, 21), 48.137, 11.575, 90.833)
    assert 7 * 60 + 52 <= (a.hour * 60 + a.minute + 60) <= 8 * 60 + 8 and 16 * 60 + 15 <= (b.hour * 60 + b.minute + 60) <= 16 * 60 + 32


def test_gear_and_plans():
    mk("g1", line())
    db.execute("INSERT INTO gear(name,kind,sports,since,until,limit_km,note) VALUES('Wanderschuhe','Schuhe','hike','','',3,'')")
    db.execute("INSERT INTO gear(name,kind,sports,since,until,limit_km,note) VALUES('Alte Schuhe','Schuhe','hike','','2020-01-01',0,'')")
    db.execute("INSERT INTO plans(name,sport,pts,km,up,down,max_alt,est_h,note,ts) VALUES('Rund um den See','hike','[]',12.5,300,300,700,4.2,'',100)")
    db.execute("INSERT INTO plans(name,sport,pts,km,up,down,max_alt,est_h,note,ts) VALUES('Gipfelweg','hike','[[1,2]]',8,900,900,2100,5,'',200)")
    with client() as c:
        g = get(c, "ausruestung")
        assert [x["name"] for x in g] == ["Wanderschuhe"] and g[0]["limit_km"] == 3 and g[0]["status"] in ("soon", "over", "ok") and g[0]["km"] > 0
        p = get(c, "geplant")
        assert [x["name"] for x in p] == ["Gipfelweg", "Rund um den See"] and "pts" not in p[0] and p[0]["km"] == 8


def test_viewer_reads_users_are_separated_and_anonymous_is_refused():
    from fastapi.testclient import TestClient
    from app import main
    mk("a", line())
    with TestClient(main.app) as c:
        assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200
        assert get(c, "splits", tour="a")["status"] == "ok"
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        c.post("/api/users", json={"name": "Eva", "email": "eva@example.com", "password": "evas-pass123", "role": "user"})
        assert TestClient(main.app).get("/api/bausteine/splits?tour=a").status_code in (401, 403)
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        for n in ("splits", "steigung", "bewegung", "gipfel", "profil", "tageslicht"):
            assert v.get(f"/api/bausteine/{n}?tour=a").json()["status"] == "ok", n               # Betrachter darf lesen
        assert v.get("/api/bausteine/ausruestung").status_code == 200 and v.get("/api/bausteine/geplant").status_code == 200
        assert v.post("/api/bausteine/splits", json={}).status_code in (403, 405)                  # …aber nicht schreiben
        e = TestClient(main.app)
        assert e.post("/api/login", json={"name": "eva", "password": "evas-pass123"}).status_code == 200
        assert e.get("/api/bausteine/splits?tour=a").status_code == 404                             # eigene, leere Datenbank
        assert e.get("/api/bausteine/ausruestung").json() == []
    assert main.VIEWER_GET.match("/api/bausteine/splits") and not main.VIEWER_GET.match("/api/bausteine/splits/x") and not main.VIEWER_GET.match("/api/bausteine/Splits")


def test_version_notes_and_script_order():
    from app import config as cfg
    root = Path(__file__).resolve().parent.parent
    assert cfg.VERSION.startswith("3.68.0 · Meine Touren")
    notes = (root / "docs" / "versionen" / "3.18.0.md").read_text(encoding="utf-8")
    assert "Mehr Bausteine" in notes and "/api/bausteine/" in notes
    for name in ("Kilometer-Splits", "Jahresziel", "Kalender-Heatmap", "Tageslicht", "Wiederentdecken"):
        assert name in notes
