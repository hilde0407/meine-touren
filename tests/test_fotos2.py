"""Zuordnung nach Aufnahmeort, GPS-Zeitabgleich und Importplan (Version 1.2)."""
import math, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.test_core import fresh  # noqa: F401
from app import db, photos, routes  # noqa

T0 = 1_700_000_000 - 8 * 3600      # Mittag (Ortszeit), damit nichts über Mitternacht läuft


def _tour(tid, start, dur, lat0, lon0):
    """Tour mit geradem Weg nach Osten; Strecke wird mit relativer Zeit gespeichert."""
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (tid, f"Tour {tid}", "hike", start, start + dur, 5000, dur, 10, 10, lat0, lon0, "tour_recorded", "local"))
    n = 120
    routes.store(tid, [(lat0, lon0 + 0.0009 * i, 500, int(dur * 1000 * i / (n - 1))) for i in range(n)])


def _photo(i, ts, lat=None, lon=None, dated=1):
    db.execute("INSERT INTO photos(path,taken_ts,lat,lng,dated) VALUES(?,?,?,?,?)", (f"/x/f{i}.jpg", ts, lat, lon, dated))


def _tid(i):
    return db.one("SELECT tour_id FROM photos WHERE path=?", (f"/x/f{i}.jpg",))["tour_id"]


def test_overlapping_tours_decided_by_photo_location():
    _tour("A", T0, 7200, 48.0, 8.0)                 # läuft von 8.000 nach etwa 8.107
    _tour("B", T0 + 1800, 7200, 49.0, 9.0)          # gleichzeitig, 100 km entfernt
    _photo(1, T0 + 3600, 48.0, 8.05)                # im Zeitfenster beider, aber an Strecke A
    _photo(2, T0 + 3600, 49.0, 9.05)                # an Strecke B
    _photo(3, T0 + 3600)                            # ohne Ort: Zeit allein (beide passen) -> eine von beiden, kein Fehler
    photos.assign_all(force=True)
    assert _tid(1) == "A" and _tid(2) == "B" and _tid(3) in ("A", "B")


def test_photo_far_from_track_is_not_assigned():
    _tour("A", T0, 3600, 48.0, 8.0)
    _photo(1, T0 + 600, 48.0, 8.02)
    _photo(2, T0 + 600, 52.0, 13.0)                 # gleiche Zeit, aber Hunderte km weg
    photos.assign_all(force=True)
    assert _tid(1) == "A" and _tid(2) is None


def test_time_is_decisive_without_gps_and_inside_beats_margin():
    _tour("A", T0, 3600, 48.0, 8.0)
    _tour("B", T0 + 3600 + 600, 3600, 48.0, 8.0)    # beginnt 10 Min. nach A
    _photo(1, T0 + 3600 + 300)                      # 5 Min. nach Ende A (Toleranz), 5 Min. vor Start B (Toleranz) -> Gleichstand, kein Absturz
    _photo(2, T0 + 3600 + 900)                      # klar innerhalb B
    photos.assign_all(force=True)
    assert _tid(2) == "B" and _tid(1) in ("A", "B")


def test_gps_offset_finds_wrong_camera_clock():
    _tour("A", T0, 3600, 48.0, 8.0)
    for i in range(8):                              # Fotos entlang der Strecke, Kamera 2 h 7 min zu spät
        frac = (i + 1) / 10
        _photo(i, int(T0 + 3600 * frac + 2 * 3600 + 7 * 60), 48.0, 8.0 + 0.0009 * 119 * frac)
    r = photos.suggest_offset("A")
    assert r["ok"] and abs(r["delta_s"] + 2 * 3600 + 7 * 60) <= 120 and not r["aligned"]
    out = photos.apply_offset("A", r["delta_s"], r["ids"])
    assert out["shifted"] >= 8
    r2 = photos.suggest_offset("A")
    assert r2["ok"] and r2["aligned"]
    assert db.one("SELECT COUNT(*) n FROM photos WHERE tour_id='A'")["n"] == 8


def test_gps_offset_reports_when_not_enough_photos():
    _tour("A", T0, 3600, 48.0, 8.0)
    _photo(1, T0 + 100, 48.0, 8.01)
    assert not photos.suggest_offset("A")["ok"]


def test_plan_offers_gps_shift_and_only_tour():
    _tour("A", T0, 3600, 48.0, 8.0)
    from datetime import datetime
    items = []
    for i in range(6):
        ts = T0 + int(3600 * (i + 1) / 8) + 5 * 3600 + 13 * 60          # Kamera 5 h 13 min vor
        t = datetime.fromtimestamp(ts, photos.TZ).strftime("%Y:%m:%d %H:%M:%S")
        items.append({"k": i, "t": t, "lat": 48.0, "lng": 8.0 + 0.0009 * 119 * (i + 1) / 8})
    days = photos.plan(items)
    opts = [o for d in days for o in d["options"] if o.get("by_gps")]
    assert opts and abs(opts[0]["shift_s"] + 5 * 3600 + 13 * 60) <= 120 and opts[0]["matched"] == 6
    only = photos.plan(items, "A")
    assert only[0]["status"] == "ask" and only[0]["options"][0]["tour"] == "A" and only[0]["options"][0]["by_gps"]


def test_plan_ok_when_most_photos_match_one_tour():
    _tour("A", T0, 3600, 48.0, 8.0)
    from datetime import datetime
    f = lambda ts: datetime.fromtimestamp(ts, photos.TZ).strftime("%Y:%m:%d %H:%M:%S")
    items = [{"k": i, "t": f(T0 + 300 * (i + 1))} for i in range(4)] + [{"k": 9, "t": f(T0 + 3600 + 5000)}]   # 4 von 5 passen
    d = photos.plan(items)
    assert len(d) == 1 and d[0]["status"] == "ok" and d[0]["matched"] == 4


# ---------- Browser: Fotos zu einer Tour hinzufügen, Kamerauhr falsch ----------
import os, socket, subprocess, time, urllib.request, json, io  # noqa: E402
import pytest  # noqa: E402

ROOT = Path(__file__).parent.parent


@pytest.fixture(scope="module")
def tour_server(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    d = tmp_path_factory.mktemp("f2")
    code = f"""
import sys, os; sys.path.insert(0, {str(ROOT)!r}); os.environ['DATA_DIR'] = {str(d / 'data')!r}
from app import db, tracks, gpxtools
from datetime import datetime, timedelta, timezone
db.init()
t0 = datetime(2025, 6, 14, 9, 0, 0, tzinfo=gpxtools.TZ).astimezone(timezone.utc)
pts = ''.join('<trkpt lat="48.000000" lon="%.6f"><ele>500</ele><time>%s</time></trkpt>' % (8 + 0.0009 * i, (t0 + timedelta(seconds=30 * i)).strftime('%Y-%m-%dT%H:%M:%SZ')) for i in range(120))
tracks.adopt('<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><type>hiking</type><trkseg>' + pts + '</trkseg></trk></gpx>', 'w.gpx', name='Kameratest')
print(db.query('SELECT id,start_ts FROM tours')[0]['id'])
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(d / "data")))
    assert out.returncode == 0, out.stderr
    tid = out.stdout.strip().splitlines()[-1]
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    env = dict(os.environ, DATA_DIR=str(d / "data"), PHOTOS_DIR=str(d / "p"), BACKUP_DIR=str(d / "b"), MT_NO_SCHEDULER="1")
    pr = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=1); break
        except Exception:
            time.sleep(0.2)
    yield f"http://127.0.0.1:{port}", tid, d
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)


def test_browser_add_photos_to_tour_with_wrong_camera_clock(tour_server):
    from playwright.sync_api import sync_playwright
    from PIL import Image
    import random
    base, tid, d = tour_server
    from datetime import datetime, timedelta
    src = d / "fotos"; src.mkdir()
    true_start = datetime(2025, 6, 14, 9, 0, 0)
    truth = []
    for i in range(6):
        frac = (i + 1) / 8
        t_true = true_start + timedelta(seconds=int(3570 * frac))
        t_cam = t_true + timedelta(hours=3, minutes=7)                       # Kamera 3 h 7 min vor
        random.seed(i)
        im = Image.new("RGB", (64, 48)); im.putdata([(random.randint(0, 255),) * 3 for _ in range(64 * 48)])
        b = io.BytesIO(); im.save(b, "JPEG")
        data = photos.with_exif_time(b.getvalue(), t_cam.strftime("%Y:%m:%d %H:%M:%S"), 48.0, 8.0 + 0.0009 * 119 * frac)
        (src / f"k{i}.jpg").write_bytes(data)
        truth.append(t_true)
    with sync_playwright() as pw:
        br = pw.chromium.launch(); pg = br.new_page(viewport={"width": 1200, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(f"{base}/#/tour/{tid}"); pg.wait_for_selector("#padd", timeout=15000)
        pg.click("#padd")
        pg.set_input_files("#pfil", [str(p) for p in sorted(src.glob("*.jpg"))])
        pg.wait_for_selector("#pigo:not([disabled])", timeout=20000)
        txt = pg.inner_text("#pib")
        assert "(per GPS)" in txt and "−3 Std. 7 Min." in txt
        if os.environ.get("MT_SHOT"):
            pg.screenshot(path=os.environ["MT_SHOT"])
        pg.click("#pigo")
        pg.wait_for_function("document.querySelector('#pib') && document.querySelector('#pib').textContent.includes('✓')", timeout=90000)
        ph = json.load(urllib.request.urlopen(f"{base}/api/photos?tour_id={tid}&limit=50"))
        assert len(ph) == 6
        got = sorted(p["taken_ts"] for p in ph)
        want = sorted(int(t.replace(tzinfo=photos.TZ).timestamp()) for t in truth)
        assert all(abs(a - b) <= 120 for a, b in zip(got, want))
        r = json.load(urllib.request.urlopen(f"{base}/api/photo-offset?tour_id={tid}"))
        assert r["ok"] and r["aligned"]
        assert not errs
        br.close()


# ---------- Zeitzonen-Versatz der Kamera und erneuter Import gelöschter Fotos ----------
def _jpeg(seed):
    from PIL import Image
    import random
    random.seed(seed)
    im = Image.new("RGB", (64, 48)); im.putdata([(random.randint(0, 255),) * 3 for _ in range(64 * 48)])
    b = io.BytesIO(); im.save(b, "JPEG")
    return b.getvalue()


def test_offset_time_original_is_kept_and_used(tmp_path):
    from PIL import Image
    data = photos.with_exif_time(_jpeg(1), "2026:10:29 12:17:17", None, None, "+00:00")
    p = tmp_path / "a.jpg"; p.write_bytes(data)
    ts, _, _ = photos.read_meta(p)
    assert ts == int(__import__("datetime").datetime(2026, 10, 29, 12, 17, 17, tzinfo=__import__("datetime").timezone.utc).timestamp())
    with Image.open(p) as im:
        assert im.getexif().get_ifd(0x8769).get(0x9011) == "+00:00"
    # nur OffsetTimeOriginal (ohne OffsetTime) wird ebenfalls erkannt
    ex = Image.Exif(); ex.get_ifd(0x8769)[0x9003] = "2026:10:29 12:00:00"; ex.get_ifd(0x8769)[0x9011] = "+01:00"
    q = tmp_path / "b.jpg"; Image.new("RGB", (8, 8)).save(q, "JPEG", exif=ex.tobytes())
    assert photos.read_meta(q)[0] == int(__import__("datetime").datetime(2026, 10, 29, 11, 0, 0, tzinfo=__import__("datetime").timezone.utc).timestamp())


def test_plan_uses_camera_offset():
    t = int(__import__("datetime").datetime(2026, 10, 29, 12, 10, 0, tzinfo=__import__("datetime").timezone.utc).timestamp())
    _tour("G", t, 2 * 3600 + 600, 28.1, -17.1)                 # 12:10-14:20 UTC (La Gomera)
    items = [{"k": i, "t": "2026:10:29 %02d:%02d:00" % divmod(740 + i * 20, 60), "o": "+00:00"} for i in range(5)]
    d = photos.plan(items)
    assert len(d) == 1 and d[0]["status"] == "ok" and d[0]["matched"] == 5       # ohne Offset (Berlin) lägen alle 1 h zu früh
    no_off = photos.plan([{k: v for k, v in it.items() if k != "o"} for it in items])
    assert no_off[0]["matched"] < 5


def test_upload_with_offset_and_reimport_of_deleted(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main, "scheduler", lambda: None)
    with TestClient(main.app) as c:
        db.put("photo_only_tracked", "0")
        for i in range(2):
            r = c.post("/api/photo-upload", files={"file": ("x.jpg", _jpeg(10 + i), "image/jpeg")},
                       data={"rel": f"gom/f{i}", "taken": "2026:10:29 12:17:17", "offset": "+00:00", "mtime": "0"})
            assert r.status_code == 200
        photos.scan()
        rows = db.query("SELECT id,taken_ts FROM photos WHERE path LIKE '%gom_f%' ORDER BY id")
        utc = int(__import__("datetime").datetime(2026, 10, 29, 12, 17, 17, tzinfo=__import__("datetime").timezone.utc).timestamp())
        assert len(rows) == 2 and all(r["taken_ts"] == utc for r in rows)
        c.post("/api/photo-delete", json={"ids": [rows[0]["id"]]})
        lib = c.get("/api/photo-library?split=1").json()
        assert "gom/f0" in lib["deleted"] and "gom/f0" not in lib["have"]
        r = c.post("/api/photo-upload", files={"file": ("x.jpg", _jpeg(10), "image/jpeg")}, data={"rel": "gom/f0", "taken": "2026:10:29 12:17:17", "offset": "+00:00", "mtime": "0"})
        assert r.status_code == 200 and not r.json().get("skipped")
        lib = c.get("/api/photo-library?split=1").json()
        assert "gom/f0" in lib["have"] and "gom/f0" not in lib["deleted"]


def test_upload_shift_keeps_offset_zone(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main, "scheduler", lambda: None)
    with TestClient(main.app) as c:
        db.put("photo_only_tracked", "0")
        c.post("/api/photo-upload", files={"file": ("x.jpg", _jpeg(20), "image/jpeg")},
               data={"rel": "gom/s0", "taken": "2026:10:29 12:00:00", "offset": "+00:00", "shift_s": "3600", "mtime": "0"})
        photos.scan()
        r = db.one("SELECT taken_ts FROM photos WHERE path LIKE '%gom_s0%'")
        utc = int(__import__("datetime").datetime(2026, 10, 29, 13, 0, 0, tzinfo=__import__("datetime").timezone.utc).timestamp())
        assert r["taken_ts"] == utc
