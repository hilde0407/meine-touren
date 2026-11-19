"""3.48.0 – Rückblick pro Tour „Wie ist es gelaufen?“: GET /api/tours/<id>/rueckblick (app/rueckblick.py). Konstruierte Daten, von Hand gerechnet.
Median-Schwellen 0,80 / 1,25 (planhilfe), mindestens 5 Vergleichstouren, nie Platzhalterwerte; mit verknüpftem Plan bleibt „Plan und Ergebnis“ maßgeblich."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import db, routes  # noqa: E402

T0 = 1750000000
DAY = 86400


def loop(lat0=48.0, lng0=11.0, r=0.01, n=120):
    return [(lat0 + r * math.sin(2 * math.pi * i / (n - 1)), lng0 + r * (1 - math.cos(2 * math.pi * i / (n - 1))), 500 + 20 * math.sin(i / 9), i * 1000) for i in range(n)]


def mk(tid, days, dist=10000, dur=7200, up=300, sport="hike", route=None):
    ts = T0 + days * DAY
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,?,?,'t','komoot')",
               (tid, f"Tour {tid}", sport, ts, ts + (dur or 0), dist, dur, up, up))
    if route is not None:
        routes.store(tid, loop(**route))


def client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def get(tid):
    r = client().get(f"/api/tours/{tid}/rueckblick")
    assert r.status_code == 200, r.text
    return r.json()


def test_zu_wenig_vergleichstouren_und_unbekannt():
    for i in range(4):                                   # nur 4 frühere Touren: unter MIN_N
        mk(f"v{i}", i * 5)
    mk("t", 30)
    d = get("t")
    assert d["status"] == "zu_wenig" and d["eigene"] is None and d["aehnliche"] is None and d["sport_n"] == 4 and d["min_n"] == 5
    assert client().get("/api/tours/nix/rueckblick").status_code == 404


def test_einordnung_median_schwellen_und_zeitfenster():
    # 5 Vergleichstouren (12 Monate davor): 10 km, 2 h, 300 m  -> Median 10 km, 2 h, 300 m, Tempo 5 km/h
    for i in range(5):
        mk(f"v{i}", i * 10)
    mk("alt", -500)                                       # älter als 12 Monate vor „t“: zählt nicht
    mk("spaeter", 200)                                    # nach „t“: zählt nicht
    mk("ski", 20, sport="skitour")                        # andere Sportgruppe: zählt nicht
    mk("t", 100, dist=14000, dur=7200, up=240)            # 14 km = 140 % (länger), 2 h = 100 % (ähnlich), 240 m = 80 % (genau Grenze: ähnlich), Tempo 7 km/h = 140 % (schneller)
    d = get("t")
    assert d["status"] == "ok" and d["sport_n"] == 5 and d["eigene"]["n"] == 5
    k = d["eigene"]["kennzahlen"]
    assert k["strecke"]["einordnung"] == "ueber" and k["strecke"]["verhaeltnis_median_pct"] == 140 and k["strecke"]["median"] == 10.0
    assert k["dauer"]["einordnung"] == "aehnlich" and k["dauer"]["verhaeltnis_median_pct"] == 100
    assert k["auf"]["einordnung"] == "aehnlich" and k["auf"]["verhaeltnis_median_pct"] == 80
    assert k["tempo"]["einordnung"] == "ueber" and abs(k["tempo"]["wert"] - 7.0) < 1e-6 and k["strecke"]["perzentil"] == 100
    assert d["aehnliche"] is None and d["besuch"] is None
    mk("t2", 101, dist=7000, dur=14400, up=100)           # 70 % Strecke, 200 % Dauer, 33 % Aufstieg, Tempo 1,75 km/h (35 %)
    k2 = get("t2")["eigene"]["kennzahlen"]
    assert k2["strecke"]["einordnung"] == "unter" and k2["dauer"]["einordnung"] == "ueber" and k2["auf"]["einordnung"] == "unter" and k2["tempo"]["einordnung"] == "unter"


def test_fehlende_werte_sind_nie_null():
    for i in range(5):
        mk(f"v{i}", i * 10)
    mk("t", 100, dist=14000, dur=None, up=None)            # ohne Dauer und Aufstieg: keine Einordnung dafür, nie 0
    d = get("t")
    k = d["eigene"]["kennzahlen"]
    assert k["dauer"] is None and k["tempo"] is None and k["auf"] is None and k["strecke"]["einordnung"] == "ueber"
    mk("leer", 110, dist=None, dur=None, up=None)
    assert get("leer")["status"] == "zu_wenig"             # nichts einzuordnen: Abschnitt entfällt


def test_aehnliche_touren_und_besuch():
    for i in range(6):                                     # 6 Läufe derselben Strecke (Median 2 h, 10 km)
        mk(f"r{i}", i * 40, route={})
    mk("r6", 300, dur=5400, route={})                       # 7. Besuch, schneller und kürzere Dauer: 1,5 h = 75 % -> kürzer
    d = get("r6")
    assert d["status"] == "ok" and d["besuch"] == {"nr": 7, "von": 7}
    assert d["aehnliche"]["n"] == 6
    assert d["aehnliche"]["kennzahlen"]["dauer"]["einordnung"] == "unter" and d["aehnliche"]["kennzahlen"]["dauer"]["verhaeltnis_median_pct"] == 75
    assert d["aehnliche"]["kennzahlen"]["tempo"]["einordnung"] == "ueber"
    assert get("r0")["besuch"] == {"nr": 1, "von": 7}


def test_mit_verknuepftem_plan_bleibt_plan_und_ergebnis_massgeblich():
    for i in range(6):
        mk(f"v{i}", i * 10)
    mk("t", 100)
    assert get("t")["status"] == "ok"
    db.execute("INSERT INTO plans(name,sport,pts,km,up,down,max_alt,est_h,note,ts,tour_id) VALUES('P','hike','[]',10,300,300,500,2,'',1,'t')")
    assert get("t") == {"status": "hat_plan"}


def test_betrachter_darf_lesen():
    import re
    from app import main
    assert re.match(main.VIEWER_GET, "/api/tours/abc/rueckblick")
