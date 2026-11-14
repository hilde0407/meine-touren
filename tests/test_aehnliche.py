"""3.14.0 – „Ähnliche Touren im Vergleich“: GET /api/tours/<id>/aehnliche (app/aehnliche.py).
Alle Daten sind konstruiert: Rundwege mit identischer Strecke (die Wiederholungserkennung aus app/wiederholungen.py entscheidet, was zusammengehört)."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import aehnliche, db, routes  # noqa: E402

T0 = 1700000000            # 2023-11-14
DAY = 86400


def loop(lat0=48.0, lng0=11.0, r=0.01, n=120):
    return [(lat0 + r * math.sin(2 * math.pi * i / (n - 1)), lng0 + r * (1 - math.cos(2 * math.pi * i / (n - 1))), 500 + 20 * math.sin(i / 9), i * 1000) for i in range(n)]


def mk(tid, days, dur=7200, dist=6000, up=300, route=True, name=None, **kw):
    ts = T0 + days * DAY
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,?,?,'t','komoot')",
               (tid, name or f"Runde {tid}", "hike", ts, ts + (dur or 0), dist, dur, up, up))
    if route:
        routes.store(tid, loop(**kw))


def client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def get(c, tid):
    r = c.get(f"/api/tours/{tid}/aehnliche")
    assert r.status_code == 200, r.text
    return r.json()


def row(d, tid):
    return next(r for r in d["touren"] if r["id"] == tid)


def test_no_repeat_and_unknown_tour():
    mk("a", 0)
    mk("b", 10, lat0=49.5)                                    # anderer Ort: keine Wiederholung
    c = client()
    assert get(c, "a") == {"status": "keine_wiederholung"} and get(c, "b") == {"status": "keine_wiederholung"}
    assert c.get("/api/tours/gibtsnicht/aehnliche").status_code == 404


def test_tour_without_route_is_no_repeat_and_not_an_error():
    mk("a", 0, route=False)
    mk("b", 5, route=False)
    assert get(client(), "a") == {"status": "keine_wiederholung"}


def test_rows_values_deviation_and_sorting():
    mk("t1", 0, dur=7200, dist=6000, up=300)                    # 3,00 km/h
    mk("t2", 400, dur=6000, dist=6000, up=320)                  # 3,60 km/h
    mk("t3", 800, dur=7800, dist=6300, up=280)                  # 2,908 km/h  <- geöffnet
    mk("x", 100, lat0=50.0)                                    # andere Strecke: nicht dabei
    d = get(client(), "t3")
    assert d["status"] == "ok" and d["anzahl"] == 3 and [r["id"] for r in d["touren"]] == ["t1", "t2", "t3"]
    cur = row(d, "t3")
    assert cur["aktuell"] is True and "abweichung" not in cur and cur["tempo_kmh"] == round(6300 / 7800 * 3.6, 2) == 2.91
    assert cur["datum"] == "2026-01-22"                                                      # Ortszeit-Datum der Tour (T0 + 800 Tage)
    r2 = row(d, "t2")
    assert r2["aktuell"] is False and r2["dauer_s"] == 6000 and r2["strecke_m"] == 6000 and r2["auf_m"] == 320 and r2["tempo_kmh"] == 3.6
    assert r2["abweichung"] == {"dauer_s": -1800, "strecke_m": -300, "auf_m": 40, "tempo_pct": round((3.6 / 2.91 - 1) * 100, 1)}
    assert row(d, "t1")["abweichung"]["dauer_s"] == -600
    assert d["bestes_id"] == "t2" and d["mit_tempo"] == 3
    # von der anderen Seite gesehen: dieselbe Gruppe, andere Abweichungen
    d1 = get(client(), "t1")
    assert [r["id"] for r in d1["touren"]] == ["t1", "t2", "t3"] and row(d1, "t3")["abweichung"]["dauer_s"] == 600


def test_summary_statements():
    c = client()
    for i, dur in enumerate((7000, 6500, 7500, 6000)):         # vier frühere Läufe, Tempo 3,09 / 3,32 / 2,88 / 3,6
        mk(f"f{i}", i * 30, dur=dur)
    mk("now", 200, dur=6800)                                    # 3,18 km/h: schneller als f0 (7000) und f2, langsamer als f1 und f3
    a = get(c, "now")["aussage"]
    assert a == {"art": "schneller_als", "frueher": 4, "schneller_als": 2, "spaeter": 0, "spaeter_schneller": 0}
    mk("best", 300, dur=5000)                                   # schneller als alle früheren
    assert get(c, "best")["aussage"]["art"] == "bestes_bisher" and get(c, "best")["aussage"]["schneller_als"] == 5
    mk("slow", 400, dur=9000)
    a = get(c, "slow")["aussage"]
    assert a["art"] == "langsamer_als_alle" and a["schneller_als"] == 0 and a["frueher"] == 6
    d = get(c, "f0")                                            # ältester Lauf: es gibt nur spätere
    assert d["aussage"]["art"] == "erster" and d["aussage"]["frueher"] == 0 and d["aussage"]["spaeter"] == 6
    assert d["aussage"]["spaeter_schneller"] == 4               # f1 (6500), f3 (6000), now (6800) und best (5000) sind schneller als f0 (7000); slow (9000) nicht


def test_equal_pace_is_not_faster():
    mk("a", 0, dur=7200)
    mk("b", 10, dur=7200)
    a = get(client(), "b")["aussage"]
    assert a["art"] == "langsamer_als_alle" and a["schneller_als"] == 0                          # gleich schnell zählt nicht als schneller
    assert get(client(), "b")["touren"][0]["abweichung"]["tempo_pct"] == 0.0


def test_missing_time_or_distance_never_zero():
    mk("a", 0, dur=7200)
    mk("b", 50, dur=None)                                        # keine Zeit
    mk("c", 100, dur=30)                                         # Platzhalter-Zeit unter einer Minute
    mk("cur", 150, dur=6000)
    d = get(client(), "cur")
    b, cc = row(d, "b"), row(d, "c")
    assert b["dauer_s"] is None and b["tempo_kmh"] is None and b["abweichung"]["dauer_s"] is None and b["abweichung"]["tempo_pct"] is None
    assert cc["dauer_s"] is None and cc["tempo_kmh"] is None
    assert row(d, "a")["tempo_kmh"] == 3.0 and d["mit_tempo"] == 2                                # nur a und cur zählen
    assert d["aussage"]["frueher"] == 1 and d["bestes_id"] == "cur"
    for r in d["touren"]:
        assert r["tempo_kmh"] != 0 and r["dauer_s"] != 0


def test_current_tour_without_time_gets_list_but_no_verdict():
    mk("a", 0, dur=7200)
    mk("b", 50, dur=6000)
    mk("cur", 100, dur=None)
    d = get(client(), "cur")
    assert d["status"] == "ok" and d["anzahl"] == 3 and d["aussage"] is None
    cur = row(d, "cur")
    assert cur["tempo_kmh"] is None and cur["dauer_s"] is None
    assert row(d, "a")["abweichung"] == {"dauer_s": None, "strecke_m": 0, "auf_m": 0, "tempo_pct": None}
    assert d["bestes_id"] == "b"


def test_hidden_tour_is_no_repeat_and_missing_values():
    mk("a", 0)
    mk("b", 20)
    mk("h", 40)
    db.execute("INSERT INTO tour_hidden(id,js,ts) VALUES('h','{}',0)")
    d = get(client(), "a")
    assert [r["id"] for r in d["touren"]] == ["a", "b"]
    assert get(client(), "h") == {"status": "keine_wiederholung"}
    db.execute("UPDATE tours SET up_m=NULL WHERE id='b'")
    d = get(client(), "a")
    assert row(d, "b")["auf_m"] is None and row(d, "b")["abweichung"]["auf_m"] is None


def test_device_per_row():
    mk("a", 0)
    mk("b", 400)
    c = client()
    dev = c.post("/api/devices", json={"name": "Amazfit Balance", "kind": "zepp"}).json()["id"]
    db.execute("INSERT OR REPLACE INTO tour_device(tour_id, device_id) VALUES('a', ?)", (dev,))
    d = get(c, "b")
    assert row(d, "a")["geraet"] == "Amazfit Balance" and row(d, "b")["geraet"] is None


def test_helpers_numbers():
    assert aehnliche._num(None) is None and aehnliche._num("x") is None and aehnliche._num(float("nan")) is None and aehnliche._num("12.5") == 12.5


def test_other_user_gets_404_viewer_and_anonymous():
    from fastapi.testclient import TestClient
    from app import main
    mk("a", 0)
    mk("b", 30)
    with TestClient(main.app) as c:
        assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200
        assert get(c, "a")["anzahl"] == 2
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        c.post("/api/users", json={"name": "Eva", "email": "eva@example.com", "password": "evas-pass123", "role": "user"})
        assert TestClient(main.app).get("/api/tours/a/aehnliche").status_code in (401, 403)
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert v.get("/api/tours/a/aehnliche").json()["status"] == "ok"                   # Betrachter darf lesen
        e = TestClient(main.app)
        assert e.post("/api/login", json={"name": "eva", "password": "evas-pass123"}).status_code == 200
        assert e.get("/api/tours/a/aehnliche").status_code == 404                           # eigene (leere) Datenbank: fremde Tour unbekannt
        assert e.get("/api/tours/b/aehnliche").status_code == 404


def test_version_notes_script_and_regex():
    from app import config as cfg, main
    root = Path(__file__).resolve().parent.parent
    assert cfg.VERSION.startswith("3.14.0 · Meine Touren")
    notes = (root / "docs" / "versionen" / "3.14.0.md").read_text(encoding="utf-8")
    assert "Ähnliche Touren im Vergleich" in notes and "/api/tours/<id>/aehnliche" in notes
    html = (root / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("js/46-belastung.js") < html.index("js/47-aehnliche.js") < html.index("js/39-sw.js")
    assert main.VIEWER_GET.match("/api/tours/abc/aehnliche") and not main.VIEWER_GET.match("/api/tours/abc/aehnliche/x")
