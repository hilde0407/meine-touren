import os, sys, time
from pathlib import Path
import pytest

SAMPLE = Path("/tmp/meine_touren_test_photos")
os.environ["DATA_DIR"] = str(Path("/tmp/komoot_hub_test"))
os.environ["PHOTOS_DIR"] = str(SAMPLE)
os.environ["FAKE"] = "1"
sys.path.insert(0, str(Path(__file__).parent.parent))

from app import config, db, gpxtools, sync, photos, stats, zepp, komoot, routes  # noqa


@pytest.fixture(autouse=True)
def fresh():
    import shutil, time
    from app import jobs
    for _ in range(100):                      # Hintergrundjobs vorheriger Tests abwarten
        if not any(v["state"]["running"] for v in list(jobs._S.values())):
            break
        time.sleep(0.05)
    db.close_all()
    from app import auth
    auth.reset()
    shutil.rmtree(config.DATA_DIR, ignore_errors=True)
    db.close_all()                            # evtl. zwischenzeitlich von einem Nachzügler geöffnete Verbindung verwerfen
    db.init()


def gpx(name):
    """Synthetische Zepp-ähnliche GPX-Datei (Rundweg ca. 3 km, 5-s-Takt); Start (Ortszeit) steht im Dateinamen."""
    import math, re
    from datetime import datetime, timedelta, timezone
    m = re.match(r"Workout--(\d{4})-(\d\d)-(\d\d)--(\d\d)-(\d\d)-(\d\d)\.gpx", name)
    t0 = datetime(*[int(x) for x in m.groups()], tzinfo=gpxtools.TZ).astimezone(timezone.utc)
    pts = []
    for i in range(500):
        a = 2 * math.pi * i / 499
        lat = 48.0 + 0.004 * math.sin(a); lon = 8.0 + 0.006 * (1 - math.cos(a))
        ele = 400 + 40 * math.sin(2 * a) + 0.02 * i
        t = (t0 + timedelta(seconds=5 * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pts.append(f'<trkpt lat="{lat:.6f}" lon="{lon:.6f}"><ele>{ele:.1f}</ele><time>{t}</time></trkpt>')
    return ('<?xml version="1.0"?><gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1"><trk><type>hiking</type><trkseg>'
            + "".join(pts) + "</trkseg></trk></gpx>")


def test_convert_zepp_gpx():
    c = gpxtools.convert(gpx("Workout--2021-12-05--16-10-17.gpx"), "x.gpx")
    assert c["sport"] == "hike" and c["n"] > 100 and c["dist_m"] > 500
    assert c["name"].startswith("Wanderung 05.12.2021 ")
    assert "<trkpt" in c["gpx"] and c["start_ts"] < c["end_ts"]


def test_convert_tcx_and_sport_alias():
    tcx = """<TrainingCenterDatabase><Trackpoint><Time>2019-05-01T08:00:00Z</Time><Position><LatitudeDegrees>50.0</LatitudeDegrees><LongitudeDegrees>8.0</LongitudeDegrees></Position><AltitudeMeters>100</AltitudeMeters></Trackpoint>
    <Trackpoint><Time>2019-05-01T08:10:00Z</Time><Position><LatitudeDegrees>50.01</LatitudeDegrees><LongitudeDegrees>8.01</LongitudeDegrees></Position></Trackpoint></TrainingCenterDatabase>"""
    c = gpxtools.convert(tcx, "a.tcx")
    assert c["n"] == 2 and c["name"] == "Wanderung 01.05.2019 10:00"  # lokale Zeit (MESZ)
    g = c["gpx"].replace("<type>hike</type>", "<type>type_206</type>")
    assert gpxtools.convert(g, "b.gpx")["sport"] == "e_touringbicycle"
    with pytest.raises(gpxtools.NoGps):
        gpxtools.convert("<gpx></gpx>", "e.gpx")


def test_duplicate_detection():
    tours = [{"id": "1", "start_ts": 1000000, "dist_m": 5000, "dur_s": 3600}]
    assert sync.is_duplicate(1000200, 9999, 10, tours)            # Start ±5 min
    assert not sync.is_duplicate(1002000, 9999, 10, tours)
    assert sync.is_duplicate(1000000 + 3600, 5030, 3620, tours)   # gleiche Distanz+Dauer, 1 h versetzt
    assert not sync.is_duplicate(1000000 + 3600, 8000, 3620, tours)


def test_komoot_date_parsing():
    assert komoot.parse_date("2026-10-16T12:23:00.000+02:00") == komoot.parse_date("2026-10-16T10:23:00Z")
    assert komoot.parse_date("2026-10-16T12:23:00+0200") == komoot.parse_date("2026-10-16T10:23:00Z")


def test_zepp_decode_roundtrip():
    s = {"trackid": "1700000000"}
    d = {"longitude_latitude": "5000000000,800000000;1000,1000;1000,-500", "time": "0;10;10", "altitude": "10000;10100;10200", "heart_rate": "", "gait": ""}
    pts = zepp.decode_points(s, d)
    assert [p[0] for p in pts] == [1700000000, 1700000010, 1700000020]
    assert abs(pts[0][1] - 50.0) < 1e-6 and abs(pts[1][1] - 50.00001) < 1e-6 and abs(pts[2][2] - 8.00000500) < 1e-5
    assert "<trkpt" in zepp.points_to_gpx(s, pts, "hike")


def test_login_payload_is_encrypted_block():
    from Crypto.Cipher import AES
    assert len(zepp.KEY) == 16 and len(zepp.IV) == 16


class FakeKomoot:
    def __init__(self, tours): self.tours_ = tours; self.uploaded = []
    def login(self): return "1"
    def tours(self): return [dict(t) for t in self.tours_]
    def upload(self, gpx, sport, name):
        self.uploaded.append((sport, name)); return "created", str(900 + len(self.uploaded))


def test_import_pipeline_skips_existing(monkeypatch):
    db.put("upload_pause_s", "0")
    a = gpxtools.convert(gpx("Workout--2021-12-05--16-10-17.gpx"), "a.gpx")
    existing = [{"id": "5", "name": "x", "sport": "hike", "start_ts": a["start_ts"] + 60, "end_ts": a["end_ts"],
                 "dist_m": a["dist_m"], "dur_s": a["end_ts"] - a["start_ts"], "up_m": 0, "down_m": 0, "lat": None, "lng": None, "status": "tour_recorded"}]
    k = FakeKomoot(existing)
    items = [("a", gpx("Workout--2021-12-05--16-10-17.gpx"), "a.gpx"), ("b", gpx("Workout--2023-10-02--12-04-19.gpx"), "b.gpx")]
    monkeypatch.setattr(sync, "_komoot", lambda fresh=False: k)
    res = sync.import_gpx_texts(items, dry_run=True, k=FakeKomoot(existing))
    assert [r[1] for r in res] == ["skipped_dup", "would_upload"]
    res = sync.import_gpx_texts(items, k=k)
    assert [r[1] for r in res] == ["skipped_dup", "uploaded"] and len(k.uploaded) == 1
    assert db.one("SELECT source FROM tours WHERE id=?", (res[1][2],))["source"] == "local"   # lokal gespeichert


def _tour(i, ts, dist=10000, dur=7200, up=300):
    return {"id": str(i), "name": f"T{i}", "sport": "hike", "start_ts": ts, "end_ts": ts + dur, "dist_m": dist, "dur_s": dur,
            "up_m": up, "down_m": up, "lat": 50, "lng": 8, "status": "tour_recorded"}


def test_stats_and_mqtt():
    from datetime import datetime
    now = datetime.now(gpxtools.TZ)
    y = now.year
    ts = lambda yy, mm, dd: int(datetime(yy, mm, dd, 10, tzinfo=gpxtools.TZ).timestamp())
    tours = [_tour(1, ts(y, 1, 5)), _tour(2, ts(y, 1, 9), 5000), _tour(3, ts(y - 1, 6, 1), 20000)]
    db.executemany("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES(:id,:name,:sport,:start_ts,:end_ts,:dist_m,:dur_s,:up_m,:down_m,:lat,:lng,:status)", tours)
    s = stats.compute()
    assert s["touren_gesamt"] == 3 and s["strecke_gesamt"] == 35.0
    assert s["touren_dieses_jahr"] == 2 and s["strecke_dieses_jahr"] == 15.0
    assert s["strecke_letztes_jahr"] == 20.0 and s["aufstieg_dieses_jahr"] == 600 and s["dauer_dieses_jahr"] == 4.0
    assert s["monate_dieses_jahr"][0] == 15.0 and s["letzte_tour"]["km"] == 5.0


def test_photos_import_compress_scan_assign():
    from PIL import Image
    import shutil
    shutil.rmtree(SAMPLE, ignore_errors=True); (SAMPLE / "Tour").mkdir(parents=True)
    for i, hh in enumerate((10, 11, 12)):                       # drei synthetische Fotos mit EXIF-Aufnahmezeit
        ex = Image.Exif(); ex[0x0132] = f"2023:05:01 {hh}:00:00"; ex.get_ifd(0x8769)[0x9003] = f"2023:05:01 {hh}:00:00"
        Image.effect_noise((3000, 2000), 40).convert("RGB").save(SAMPLE / "Tour" / f"p{i}.jpg", exif=ex.tobytes(), quality=90)
    assert photos.import_from() == 3
    files = list(config.LIB_DIR.rglob("*.jpg"))
    assert len(files) == 3 and all(f.stat().st_size < 3_000_000 for f in files)
    with Image.open(files[0]) as im:
        assert max(im.size) <= 2200
    assert photos.import_from() == 0          # inkrementell
    n = photos.scan()
    assert n == 3
    rows = db.query("SELECT * FROM photos ORDER BY taken_ts")
    assert all(r["taken_ts"] > 1.6e9 for r in rows)   # EXIF-Zeit blieb bei der Komprimierung erhalten
    t0 = rows[0]["taken_ts"]
    db.executemany("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES(:id,:name,:sport,:start_ts,:end_ts,:dist_m,:dur_s,:up_m,:down_m,:lat,:lng,:status)",
                   [_tour(7, t0 - 3600, dur=4 * 3600), _tour(8, t0 + 10 * 86400)])
    photos.assign_all()
    assert {r["tour_id"] for r in db.query("SELECT tour_id FROM photos")} == {"7"}
    assert photos.scan() == 0
    p = photos.thumb(rows[0]["id"], 300)
    assert p and p.stat().st_size > 1000
    # manuelle Zuordnung mit Zeitversatz
    ids = [r["id"] for r in rows]
    r = photos.assign_manual([ids[0]], "8", shift=True, minutes_after_start=10, scope="day")
    t8 = db.one("SELECT start_ts FROM tours WHERE id='8'")["start_ts"]
    ph = {x["id"]: x for x in db.query("SELECT * FROM photos")}
    assert ph[ids[0]]["taken_ts"] == t8 + 600 and ph[ids[0]]["manual"] == 1 and ph[ids[0]]["tour_id"] == "8"
    assert ph[ids[1]]["offset_s"] == r["offset_s"]
    photos.scan()                              # Neuscan behält Zeitkorrektur + manuelle Zuordnung
    ph = {x["id"]: x for x in db.query("SELECT * FROM photos")}
    assert ph[ids[0]]["tour_id"] == "8" and ph[ids[0]]["taken_ts"] == t8 + 600
    photos.unassign_manual([ids[0]], reset_time=True)
    ph = {x["id"]: x for x in db.query("SELECT * FROM photos")}
    assert ph[ids[0]]["taken_ts"] == rows[0]["taken_ts"] and ph[ids[0]]["manual"] == 0
    photos.unassign_manual([ids[1]], exclude=True)    # aus Tour entfernt: bleibt auch nach Neuzuordnung ohne Tour
    photos.assign_all(); photos.scan()
    p1 = db.one("SELECT * FROM photos WHERE id=?", (ids[1],))
    assert p1["tour_id"] is None and p1["manual"] == 2


def test_routes_cache_and_overview():
    items = [(50 + i / 1000, 8 + i / 1000, 100 + i, i * 1000) for i in range(300)]
    full = routes.store("42", items)
    assert len(full) <= 1501 and full[0][3] == 0
    assert routes.load("42")[0][:2] == [50.0, 8.0]
    ov = routes.overview()
    assert list(ov) == ["42"] and len(ov["42"]) <= 101


def test_export_marks_existing_and_never_uploads(monkeypatch):
    db.put("zepp_token", "T" * 60)
    a = gpxtools.convert(gpx("Workout--2021-12-05--16-10-17.gpx"), "a.gpx")
    db.executemany("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES(:id,:name,:sport,:start_ts,:end_ts,:dist_m,:dur_s,:up_m,:down_m,:lat,:lng,:status)", [_tour(1, a["start_ts"] + 30)])
    s1 = {"trackid": str(a["start_ts"]), "type": 13, "dis": "5000", "run_time": "3600", "end_time": str(a["end_ts"]), "source": "x"}
    s2 = {"trackid": "1600000000", "type": 9, "dis": "20000", "run_time": "3000", "end_time": "1600003000", "source": "x"}
    d = {"longitude_latitude": "5000000000,800000000;1000,1000", "time": "0;10", "altitude": "10000;10100", "heart_rate": "", "gait": ""}
    class FakeApi:
        def __init__(self, *a): self.host = "h"
        def history(self): return [s1, s2]
        def detail(self, s): return d
    monkeypatch.setattr(zepp, "ZeppApi", FakeApi)
    monkeypatch.setattr(komoot, "Komoot", lambda *a: (_ for _ in ()).throw(AssertionError("Komoot darf nicht aufgerufen werden")))
    sync.export_zepp()
    st = {r["trackid"]: r["status"] for r in db.query("SELECT trackid,status FROM workouts")}
    assert st[a["start_ts"]] == "in_komoot" and st[1600000000] == "local"
    assert any(config.EXPORT_DIR.rglob("*.gpx"))


def test_upload_selected_only_chosen(monkeypatch):
    db.put("upload_pause_s", "0")
    ps = []
    for ts in (1700000000, 1700100000):
        p = config.EXPORT_DIR / f"w{ts}.gpx"; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(gpx("Workout--2021-12-05--16-10-17.gpx").replace("2021-12-05", "2021-12-%02d" % (5 + ts % 7)))
        db.execute("INSERT INTO workouts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (ts, ts, ts + 10, 13, "hike", 1, 1, str(p), "new", None, "", 0))
    fk = FakeKomoot([])
    monkeypatch.setattr(sync, "_komoot", lambda: fk)
    sync.upload_selected([1700000000])
    assert len(fk.uploaded) == 1
    st = {r["trackid"]: r["status"] for r in db.query("SELECT trackid,status FROM workouts")}
    assert st[1700000000] == "in_komoot" and st[1700100000] == "new"


def test_api(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main, "scheduler", lambda: None)
    with TestClient(main.app) as c:
        assert c.get("/api/stats").json()["touren_gesamt"] == 0
        assert c.post("/api/settings", json={"komoot_email": "a@b.de", "komoot_password": "geheim"}).json()["ok"]
        s = c.get("/api/settings").json()
        assert s["komoot_email"] == "a@b.de" and s["komoot_password"] == "***"
        c.post("/api/settings", json={"komoot_password": "***"})
        assert db.get("komoot_password") == "geheim"
        assert c.get("/").status_code == 200 and c.get("/slideshow.html").status_code == 200
        assert c.get("/api/photo-info").json()["count"] == 0
        assert c.get("/api/status").json() == {"tours": 0, "local_tours": 0, "routes": 0, "protected": False, "version": config.VERSION, "zepp": {"state": "", "checked": "", "token_ts": ""}, "inbox": str(config.INBOX_DIR), "app_name": config.APP_NAME, "backup_dir": str(config.BACKUP_ROOT)}
        assert c.get("/api/routes").json() == {}
        assert c.post("/api/jobs/nope").status_code == 404


def test_zepp_token_endpoints(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main, "scheduler", lambda: None)
    monkeypatch.setattr(zepp.ZeppApi, "ping", lambda self: ("https://x", 3))
    with TestClient(main.app) as c:
        assert "Kein gültiges" in c.post("/api/zepp-token", data={"token": "kurz"}).text
        r = c.post("/api/zepp-token", data={"token": "A" * 80})
        assert "geprüft" in r.text and db.get("zepp_token") == "A" * 80
        assert c.post("/api/zepp-token/test").json()["ok"]


def test_browser_upload_keeps_exif_time(monkeypatch):
    import io
    from PIL import Image
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(main, "scheduler", lambda: None)
    buf = io.BytesIO(); Image.new("RGB", (200, 100), "green").save(buf, "JPEG")
    with TestClient(main.app) as c:
        r = c.post("/api/photo-upload", files={"file": ("x.jpg", buf.getvalue(), "image/jpeg")},
                   data={"rel": "2021/03 - Tour/IMG_1.jpg".rsplit(".", 1)[0], "taken": "2021:03:23 16:06:33", "mtime": "1616515593"})
        assert r.json()["ok"]
        assert c.post("/api/photo-upload", files={"file": ("x.jpg", buf.getvalue(), "image/jpeg")}, data={"rel": "../../evil"}).status_code in (200, 400)
        assert "2021/03 - Tour/IMG_1" in c.get("/api/photo-library").json()
        assert not (config.DATA_DIR.parent / "evil.jpg").exists()
    ts, _, _ = photos.read_meta(str(config.LIB_DIR / "2021/03 - Tour/IMG_1.jpg"))
    from datetime import datetime
    assert datetime.fromtimestamp(ts, gpxtools.TZ).strftime("%Y-%m-%d %H:%M:%S") == "2021-03-23 16:06:33"


def test_rename_local_and_komoot(monkeypatch):
    class K(FakeKomoot):
        renamed = []
        def rename(self, tid, name): self.renamed.append((tid, name))
    k = K([_tour(1, 1_700_000_000)])
    monkeypatch.setattr(sync, "_komoot", lambda fresh=False: k)
    sync.refresh_tours(k)
    assert sync.rename_tour("1", "Neu lokal", komoot=False) == (False, "")
    assert db.one("SELECT name FROM tours WHERE id='1'")["name"] == "Neu lokal" and not k.renamed
    sync.refresh_tours(k)  # Komoot-Name unverändert -> lokale Umbenennung bleibt
    assert db.one("SELECT name FROM tours WHERE id='1'")["name"] == "Neu lokal"
    assert sync.rename_tour("1", "Auch Komoot", komoot=True)[0] is True and k.renamed == [("1", "Auch Komoot")]
    k.tours_[0]["name"] = "Auch Komoot"
    sync.refresh_tours(k)
    assert db.one("SELECT name FROM tours WHERE id='1'")["name"] == "Auch Komoot"
    sync.rename_tour("1", "X", komoot=False); sync.refresh_tours(k)
    assert db.one("SELECT name FROM tours WHERE id='1'")["name"] == "X"
    k.tours_[0]["name"] = "Andere Änderung"; sync.refresh_tours(k)
    assert db.one("SELECT name FROM tours WHERE id='1'")["name"] == "Andere Änderung"


def test_sync_single_tour_and_changed_route(monkeypatch):
    class K(FakeKomoot):
        def tour(self, tid): return dict(self.tours_[0])
        def coordinates(self, tid): return [(50.0, 8.0, 100, 0), (50.1, 8.1, 120, 1000)]
    k = K([_tour(1, 1_700_000_000, dist=10000)])
    monkeypatch.setattr(sync, "_komoot", lambda fresh=False: k)
    sync.refresh_tours(k)
    routes.store("1", [(1.0, 1.0, 0, 0), (2.0, 2.0, 0, 1)])
    k.tours_[0].update(dist_m=7000, dur_s=5000)
    sync.refresh_tours(k)                      # geänderte Strecke -> Cache verworfen
    assert routes.load("1") is None
    routes.store("1", [(1.0, 1.0, 0, 0)])
    t = sync.sync_tour("1")
    assert t["dist_m"] == 7000 and routes.load("1")[1][0] == 50.1


def test_extras_backup_notes_goals_gpx(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    import zipfile, io
    from app import extras, main
    db.put("komoot_password", "geheim")
    db.executemany("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES(:id,:name,:sport,:start_ts,:end_ts,:dist_m,:dur_s,:up_m,:down_m,:lat,:lng,:status)", [_tour(31, 1_700_000_000)])
    routes.store("31", [(50.0, 8.0, 100, 0), (50.1, 8.1, 130, 60000)])
    with TestClient(main.app) as c:
        r = c.get("/api/backup"); assert r.status_code == 200
        z = zipfile.ZipFile(io.BytesIO(r.content)); assert "komoot_hub.sqlite" in z.namelist()
        p = tmp_path / "x.sqlite"; p.write_bytes(z.read("komoot_hub.sqlite"))
        import sqlite3; assert sqlite3.connect(p).execute("SELECT v FROM settings WHERE k='komoot_password'").fetchone()[0] in ("", None)
        assert c.post("/api/tours/31/note", json={"note": "Schön & windig"}).status_code == 200
        assert [t for t in c.get("/api/tours").json() if t["id"] == "31"][0]["note"] == "Schön & windig"
        assert c.post("/api/goals", json={"year": 2026, "metric": "km", "target": 500, "sport": "hike"}).status_code == 200
        g = c.get("/api/goals").json(); assert g[0]["target"] == 500
        c.delete(f"/api/goals/{g[0]['id']}"); assert c.get("/api/goals").json() == []
        gx = c.get("/api/tours/31/gpx"); assert gx.status_code == 200 and "<trkpt" in gx.text and "<time>" in gx.text
        assert c.get("/api/records/altitude").json()[0] == {"id": "31", "alt": 130}
    out = extras.make_backup(tmp_path / "bk", keep=2); assert out.exists()


def test_weather_tiles_inbox_zepp(monkeypatch, tmp_path):
    from fastapi.testclient import TestClient
    from app import extras, main
    t = _tour(41, 1_600_000_000, dur=7200)
    db.executemany("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES(:id,:name,:sport,:start_ts,:end_ts,:dist_m,:dur_s,:up_m,:down_m,:lat,:lng,:status)", [t])
    class R:
        status_code = 200; content = b"PNG"
        def json(self):
            from datetime import datetime
            base = datetime.fromtimestamp(t["start_ts"], tz=gpxtools.TZ).replace(minute=0, second=0, microsecond=0)
            ts = [(base.replace(hour=base.hour) ).isoformat(timespec="minutes").replace("+02:00", "").replace("+01:00", "")]
            hrs = [base.replace(hour=h) for h in range(max(0, base.hour - 1), min(23, base.hour + 3))]
            return {"hourly": {"time": [h.strftime("%Y-%m-%dT%H:%M") for h in hrs], "temperature_2m": [10 + i for i in range(len(hrs))],
                               "precipitation": [0.2] * len(hrs), "weather_code": [3] * len(hrs), "wind_speed_10m": [12] * len(hrs)}}
    monkeypatch.setattr(extras.requests, "get", lambda *a, **k: R())
    monkeypatch.setattr(extras, "TILE_DIR", tmp_path / "tiles")
    with TestClient(main.app) as c:
        w = c.get("/api/tours/41/weather").json(); assert w["text"] == "bedeckt" and w["tmax"] >= w["tmin"] and w["precip"] > 0
        assert c.get("/tiles/osm/3/4/2").content == b"PNG" and (tmp_path / "tiles/osm/3/4/2.png").exists()
        assert c.get("/tiles/evil/3/4/2").status_code == 404 and c.get("/tiles/osm/3/9/2").status_code == 404
        monkeypatch.setattr(extras.config, "TILE_FETCH", False)
        rr = c.get("/tiles/topo/3/1/1", follow_redirects=False); assert rr.status_code == 307 and "opentopomap" in rr.headers["location"]
    config.INBOX_DIR.mkdir(parents=True, exist_ok=True)
    assert sync.inbox_newest() == 0
    (config.INBOX_DIR / "x.txt").write_text("a"); assert sync.inbox_newest() > 0
    db.put("zepp_token", "x" * 50)
    monkeypatch.setattr(sync.zepp.ZeppApi, "ping", lambda self: (_ for _ in ()).throw(RuntimeError("abgelaufen")))
    assert sync.check_zepp().startswith("fail:") and db.get("zepp_state").startswith("fail:abgelaufen")


def test_name_suggestions(monkeypatch):
    from app import extras
    names = {"a": "Oberstdorf", "b": "Birgsau"}
    monkeypatch.setattr(extras, "place_name", lambda la, ln: names["a"] if la < 47.5 else names["b"])
    monkeypatch.setattr(extras, "peak_name", lambda la, ln: "Nebelhorn")
    t = {"sport": "hike", "name": "x", "dist_m": 12000, "lat": 47.4, "lng": 10.2}
    pts = [[47.4, 10.2, 800], [47.45, 10.25, 1500], [47.6, 10.3, 900]]
    r = extras.name_suggestions(t, pts)
    assert "Wanderung von Oberstdorf nach Birgsau" in r and "Wanderung Oberstdorf – Nebelhorn" in r


def test_elev_fix(monkeypatch):
    from app import elev, db, routes
    import random
    # künstliches Gelände: Höhe steigt mit der Breite (≈ 0,2 m pro Pixel-Zeile), Tile liefert Terrarium-RGB
    class Px:
        def __getitem__(self, k):
            h = 1000 + k[1] * 0.5 + 32768
            return int(h // 256), int(h % 256), 0
    monkeypatch.setattr(elev, "_tile", lambda x, y: Px())
    pts = [[-21.1 + i * 0.0003, 55.45, 1000 + random.uniform(-80, 80), i * 1000] for i in range(300)]
    h = elev.terrain([(p[0], p[1]) for p in pts][:5], tile=lambda x, y: Px())
    assert all(900 < v < 5000 for v in h)
    up, down = elev.ascent(elev.smooth([1000 + random.uniform(-80, 80) for _ in range(300)]))
    assert up < 1500            # Rauschen darf nicht als tausende Höhenmeter zählen
    up2, _ = elev.ascent([0, 10, 20, 30, 25, 30, 40])
    assert up2 == 45 and elev.suspicious({"dist_m": 10000, "up_m": 2397}) and not elev.suspicious({"dist_m": 10000, "up_m": 600})


def test_geo_fill(monkeypatch):
    from app import extras, db
    monkeypatch.setattr(extras.time, "sleep", lambda s: None)
    db.execute("INSERT OR REPLACE INTO tours(id,name,sport,start_ts,dist_m,lat,lng) VALUES('g1','G','hike',1700000000,1000,47.4,10.2)")
    n = extras.geo_fill(fetch=lambda la, ln: {"country": "Deutschland", "state": "Bayern", "county": "Oberallgäu", "place": "Oberstdorf"})
    assert n >= 1
    r = db.one("SELECT * FROM tour_geo WHERE id='g1'")
    assert r["state"] == "Bayern" and r["place"] == "Oberstdorf"
    assert extras.geo_fill(fetch=lambda la, ln: 1 / 0) == 0      # bereits zugeordnet → keine Anfrage mehr


def test_trail_names():
    from app import extras
    pts = [[50.0 + i * 0.001, 8.0, 300, i] for i in range(60)]
    on = {"tags": {"name": "Wispertrail Hohe Wurzel", "route": "hiking"}, "members": [{"geometry": [{"lat": 50.0 + i * 0.001, "lon": 8.0003} for i in range(60)]}]}
    off = {"tags": {"name": "Fernweg X", "route": "hiking"}, "members": [{"geometry": [{"lat": 50.0 + i * 0.001, "lon": 8.01} for i in range(60)]}]}
    part = {"tags": {"name": "Teilstück", "route": "hiking"}, "members": [{"geometry": [{"lat": 50.0 + i * 0.001, "lon": 8.0} for i in range(10)]}]}
    r = extras.trail_names({"sport": "hike"}, pts, fetch=lambda q: [off, part, on])
    assert r == ["Wispertrail Hohe Wurzel"]


def test_guides():
    from app import extras, db
    gpx = '<gpx xmlns="http://www.topografix.com/GPX/1/1"><metadata><name>Hohe Wurzel</name></metadata><trk><trkseg>' + "".join(f'<trkpt lat="{50 + i * 0.0005}" lon="8.0"></trkpt>' for i in range(80)) + "</trkseg></trk></gpx>"
    title, pts = extras._guide_parse(gpx, "t12.gpx")
    assert title == "Hohe Wurzel" and len(pts) >= 80 // 1
    db.execute("INSERT INTO guide_tours(book,title,pts) VALUES(?,?,?)", ("Rother Taunus", title, __import__("json").dumps(pts)))
    mine = [[50 + i * 0.0005, 8.0004, 300, i] for i in range(80)]
    assert extras.guide_matches(mine) == [("Rother Taunus", "Hohe Wurzel")]
    far = [[51 + i * 0.0005, 9.0, 300, i] for i in range(80)]
    assert extras.guide_matches(far) == []
    part = [[50 + i * 0.0005, 8.0004, 300, i] for i in range(10)]
    assert extras.guide_matches(part) == []              # nur kleiner Teil der Buchtour


def test_check_places_health(monkeypatch):
    from app import more, db, routes, extras
    from fastapi.testclient import TestClient
    from app import main
    monkeypatch.setattr(extras.time, "sleep", lambda s: None); monkeypatch.setattr(more.time, "sleep", lambda s: None)
    with TestClient(main.app) as c:
        for i, (nm, ts, km, up) in enumerate([("Wanderung 01.05.2026 10:00", 1780000000, 10000, 2500), ("Wanderung 01.05.2026 10:05", 1780000300, 10100, 300), ("Hohe Wurzel", 1770000000, 8000, 400)]):
            db.execute("INSERT OR REPLACE INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (f"c{i}", nm, "hike", ts, ts + 3600, km, 3600, up, up, 50.1, 8.0, "x"))
            routes.store(f"c{i}", [(50.1 + j * 0.001, 8.0, 300 + j * 4, j) for j in range(80)])
        r = c.get("/api/check").json()
        assert any(d["a"] == "c0" and d["b"] == "c1" for d in r["duplicates"])
        assert len(r["default_names"]) >= 2 and any(s["id"] == "c0" for s in r["suspicious"])
        def boom(la, ln): raise RuntimeError("Overpass: down")
        assert more.peaks_pending() == 3 and more.peaks_fill(fetch=boom, retry_wait=0) == 0
        assert more.peaks_pending() == 3                      # Fehler: nichts verloren, nichts als erledigt markiert
        assert more.peaks_fill(fetch=lambda la, ln: "Hohe Wurzel") >= 1
        assert more.peaks_pending() == 0 and c.get("/api/places").json()["pending_peaks"] == 0
        from app import memo
        n0 = len(c.get("/api/places").json()["peaks"]); calls = []
        f = memo.cached(lambda: calls.append(1) or len(calls)); f.__name__ = "t"
        assert f() == f() == 1                                  # zweiter Aufruf aus dem Zwischenspeicher
        db.execute("INSERT OR REPLACE INTO tour_peak(id,name,alt,lat,lng) VALUES('zz','Neuer Gipfel',1,1,1)")
        assert f() == 2                                         # Datenänderung -> neu berechnet
        p = c.get("/api/places").json()
        assert p["peaks"][0]["name"] == "Hohe Wurzel" and p["peaks"][0]["n"] >= 1
        assert isinstance(c.get("/api/health").json(), list) and c.get("/api/guides/progress").status_code == 200


def test_auto_backup(tmp_path, monkeypatch):
    from app import extras, config
    monkeypatch.setattr(config, "backup_dirs", lambda uid=None: [tmp_path / "a" / "b"])
    p = extras.auto_backup()
    assert p and extras.newest_backup() is not None
    assert extras.auto_backup() is None        # frisch genug → kein zweites Backup


def test_more2(monkeypatch):
    from app import more2, db, routes, extras, main
    from fastapi.testclient import TestClient
    monkeypatch.setattr(more2.time, "sleep", lambda s: None)
    with TestClient(main.app) as c:
        base = 1700000000
        # 6 Heimat-Touren + 2 Reise-Touren an aufeinanderfolgenden Tagen weit weg
        specs = [(f"h{i}", 50.1, 8.6, base + i * 86400 * 9) for i in range(6)] + [("r1", -21.1, 55.4, base + 100 * 86400), ("r2", -21.2, 55.5, base + 101 * 86400)]
        for tid, la, lo, ts in specs:
            db.execute("INSERT OR REPLACE INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (tid, tid, "hike", ts, ts + 3600, 8000, 3600, 300, 300, la, lo, "x"))
            routes.store(tid, [(la + j * 0.0005, lo, 300 + j, j) for j in range(80)])
        tr = c.get("/api/trips").json()
        assert tr and set(tr[0]["tours"]) == {"r1", "r2"} and tr[0]["photo"] is None
        db.execute("INSERT INTO photos(path,mtime,size,taken_ts,lat,lng,tour_id) VALUES('/x/a.jpg',1,1,?,?,?,?)", (base + 100 * 86400 + 5, -21.1, 55.4, "r1"))
        assert c.get("/api/trips").json()[0]["photo"] is not None
        assert c.post("/api/tours/r1/tags", json={"tags": ["Urlaub", " Réunion "]}).json()["tags"] == ["Urlaub", "Réunion"]
        assert any(t["tag"] == "Urlaub" for t in c.get("/api/tags").json())
        assert [t for t in c.get("/api/tours").json() if t["id"] == "r1"][0]["tags"]
        assert len(c.get("/api/collection/coords?ids=r1,r2").json()) > 100
        ng = c.get("/api/newground").json()
        assert ng["tours"]["h0"]["pct"] > 90 and ng["tours"]["h1"]["pct"] < 10        # gleiche Strecke wiederholt → kein Neuland
        assert c.get("/api/tiles/plan?ids=r1").json()["total"] > 0
        s = c.post("/api/tours/r1/share", json={"photos": False, "trim": True}).json()
        pub = c.get("/api/public/" + s["token"]).json()
        assert pub["name"] == "r1" and len(pub["coords"]) < 80 and c.get("/s/" + s["token"]).status_code == 200
        assert c.delete("/api/share/" + s["token"]).status_code == 200 and c.get("/api/public/" + s["token"]).status_code == 404
        sent = []
        monkeypatch.setattr(more2.requests, "post", lambda u, **k: sent.append((u, k)) or type("R", (), {"status_code": 200})())
        db.put("notify_url", "http://example.test/hook"); db.put("notify_last", "")
        monkeypatch.setattr(more2.more, "api_health", lambda: [{"text": "Testwarnung"}])
        assert more2.notify_check() is True and more2.notify_check() is False and sent


def test_users_isolation_and_sharing():
    from fastapi.testclient import TestClient
    from PIL import Image
    from app import main, db, config, auth, ctx, photos
    lib = config.LIB_DIR
    lib.mkdir(parents=True, exist_ok=True)
    p1 = lib / "a.jpg"; Image.new("RGB", (40, 30), "red").save(p1)
    base = 1700000000
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES('t1','Hohe Wurzel','hike',?,?,8000,3600,300,300,50.1,8.0,'x')", (base, base + 3600))
    photos._store([(str(p1), p1.stat().st_mtime, p1.stat().st_size, base + 600, None, None)]); photos.assign_all()
    db.put("komoot_email", "max@example.org")
    with TestClient(main.app) as c:
        assert c.get("/api/me").json()["needs_setup"] is True
        assert c.post("/api/setup", json={"name": "Max", "password": "kurz"}).status_code == 400
        r = c.post("/api/setup", json={"name": "Max", "password": "geheim1234"}).json()
        assert r["adopted"] and r["uid"] == "max"
        assert (config.DATA_DIR / "users" / "max" / "komoot_hub.sqlite").exists() and not (config.DATA_DIR / "komoot_hub.sqlite").exists()
        assert [t["name"] for t in c.get("/api/tours").json()] == ["Hohe Wurzel"]
        assert c.get("/photo/1?size=200").status_code == 200           # Pfad wurde mit umgezogen
        r = c.get("/pic/1?size=200"); assert r.status_code == 200 and r.headers["cache-control"] == "private, no-cache"
        assert c.get("/pic/1?size=200", headers={"If-None-Match": r.headers["etag"]}).status_code == 304   # Browser fragt nach, statt blind zu vertrauen
        anon = TestClient(main.app)
        assert anon.get("/api/tours").status_code == 401 and anon.get("/photo/1").status_code == 401
        assert anon.get("/").status_code == 200                          # Programmdateien bleiben erreichbar (Anmeldeseite)
        assert c.post("/api/users", json={"name": "Anna", "password": "annas-pass1", "role": "user"}).json()["uid"] == "anna"
        a = TestClient(main.app)
        assert a.post("/api/login", json={"name": "Anna", "password": "falsch"}).status_code == 401
        assert a.post("/api/login", json={"name": "anna", "password": "annas-pass1"}).status_code == 200
        assert a.get("/api/tours").json() == [] and a.get("/photo/1").status_code == 404      # getrennte Daten
        assert a.get("/api/users").status_code == 200 and a.post("/api/users", json={"name": "X", "password": "12345678"}).status_code == 403
        assert a.get("/api/shared/photos").json() == []
        assert a.get("/sphoto/max/1").status_code == 404            # ohne Freigabe kein Zugriff
        assert c.post("/api/grants", json={"grantee": "anna", "scope": "tour", "ref": "t1"}).status_code == 200
        sh = a.get("/api/shared/photos").json()
        assert sh[0]["owner"] == "max" and len(sh[0]["photos"]) == 1
        assert a.get("/sphoto/max/1?size=200").status_code == 200
        # Annas Tour im gleichen Zeitfenster → Fotos von Max werden angeboten und lassen sich übernehmen
        with ctx.as_user("anna"):
            db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES('a1','Annas Tour','hike',?,?,8000,3600,300,300,50.1,8.0,'x')", (base, base + 3600))
        assert len(a.get("/api/shared/for-tour/a1").json()) == 1
        assert a.post("/api/shared/import", json={"owner": "max", "ids": [1]}).json()["imported"] == 1
        assert a.get("/api/shared/for-tour/a1").json() == []
        assert [p["tour_id"] for p in a.get("/api/photos").json()] == ["a1"]
        assert c.get("/api/photos").json() and (config.DATA_DIR / "users" / "anna" / "photos" / "von-max" / "a.jpg").exists()
        g = c.get("/api/grants").json()["mine"][0]; assert c.delete(f"/api/grants/{g['id']}").status_code == 200
        assert a.get("/sphoto/max/1").status_code == 404
        # letzter Administrator kann nicht gelöscht/herabgestuft werden
        assert c.patch("/api/users/max", json={"role": "user"}).status_code == 400 and c.delete("/api/users/max").status_code == 400
        assert c.patch("/api/users/anna", json={"active": False}).status_code == 200 and a.get("/api/tours").status_code == 401


def test_local_tours_and_portals(monkeypatch):
    import json, zipfile
    from fastapi.testclient import TestClient
    from app import main, portals, tracks, extras
    db.put("upload_pause_s", "0")
    # 1) lokal importieren, ohne Portal: Tour + GPX + Strecke liegen lokal vor
    items = [("a", gpx("Workout--2021-12-05--16-10-17.gpx"), "a.gpx")]
    res = sync.import_items(items)
    assert res[0][1] == "imported"
    tid = res[0][2]
    t = db.one("SELECT * FROM tours WHERE id=?", (tid,))
    assert t["source"] == "local" and tracks.gpx_file(tid).exists() and routes.load(tid)
    assert sync.import_items(items)[0][1] == "skipped_dup"
    # 2) Komoot-Aktualisierung lässt lokale Touren stehen und führt eine gleiche Tour bei Komoot nicht doppelt
    twin = {"id": "777", "name": "bei Komoot", "sport": "hike", "start_ts": t["start_ts"] + 20, "end_ts": t["end_ts"], "dist_m": t["dist_m"],
            "dur_s": t["dur_s"], "up_m": 1, "down_m": 1, "lat": 1, "lng": 1, "status": "tour_recorded"}
    other = _tour(888, 1_600_000_000)
    k = FakeKomoot([twin, other])
    sync.refresh_tours(k)
    ids = {r["id"]: r["source"] for r in db.query("SELECT id,source FROM tours")}
    assert ids[tid] == "local" and ids["888"] == "komoot" and "777" not in ids
    assert portals.status_of(tid)["komoot"]["status"] == "linked"
    # 3) GPX-Export (aus gespeicherter Datei) und für Komoot-Touren aus den lokalen Streckenpunkten
    routes.store("888", [(50.0 + i * 1e-4, 8.0, 100 + i, i * 1000) for i in range(30)])
    g = tracks.gpx_for("888"); assert g.count("<trkpt") == 30 and "<time>" in g
    # 4) Strava (Netzwerk simuliert)
    calls = []

    class R:
        def __init__(self, code, js): self.status_code = code; self._j = js; self.text = json.dumps(js)
        def json(self): return self._j
    def post(url, **kw):
        calls.append(url)
        if url.endswith("/oauth/token"):
            return R(200, {"access_token": "AT", "refresh_token": "RT", "expires_at": 9999999999, "athlete": {"firstname": "Max", "lastname": "M"}})
        if url.endswith("/uploads"):
            assert kw["data"]["sport_type"] == "Hike" and kw["headers"]["Authorization"] == "Bearer AT"
            return R(201, {"id": 5, "activity_id": 4711, "error": None})
        return R(200, {})
    monkeypatch.setattr(portals.requests, "post", post)
    monkeypatch.setattr(portals.time, "sleep", lambda s: None)
    db.put("strava_client_id", "1"); db.put("strava_client_secret", "x")
    with TestClient(main.app) as c:
        assert c.get("/api/portals").json()["portals"][1]["connected"] is False
        u = c.get("/api/strava/connect").json()["url"]
        assert "client_id=1" in u and "activity%3Awrite" in u
        r = c.post("/api/strava/code", json={"code": "http://localhost/exchange_token?state=&code=abc&scope=read"}); assert r.json()["athlete"] == "Max M"
        assert c.get("/api/settings").json()["strava_client_secret"] == "***"
        r = c.post(f"/api/tours/{tid}/upload", json={"portals": ["strava"]}).json()
        assert r["strava"]["status"] == "uploaded" and r["strava"]["url"].endswith("/activities/4711")
        r = c.post(f"/api/tours/{tid}/upload", json={"portals": ["strava", "komoot"]}).json()
        assert r["strava"]["status"] == "already"
        r = c.post("/api/tours/888/upload", json={"portals": ["komoot"]}).json()
        assert r["komoot"]["status"] == "already"                 # stammt von Komoot
        assert c.get(f"/api/tours/{tid}/gpx").text.startswith("<?xml")
        assert c.get(f"/api/tours/{tid}/coords").status_code == 200
        # Zepp-Training: nur lokal übernehmen
        p = config.EXPORT_DIR / "w.gpx"; p.parent.mkdir(parents=True, exist_ok=True); p.write_text(gpx("Workout--2023-10-02--12-04-19.gpx"))
        db.execute("INSERT INTO workouts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (1696000000, 1696000000, 1696000100, 13, "hike", 1, 1, str(p), "new", None, "", 0))
        assert c.post("/api/workouts/adopt", json={"trackids": [1696000000]}).json()["tours"] == ["z1696000000"]
        assert db.one("SELECT status FROM workouts WHERE trackid=1696000000")["status"] == "local"
        # Backup enthält die Original-GPX lokaler Touren
        name, data = extras.make_backup()
        import io
        assert any(n.startswith("tracks/") for n in zipfile.ZipFile(io.BytesIO(data)).namelist())
        assert c.delete(f"/api/tours/{tid}").status_code == 200 and not tracks.gpx_file(tid).exists()
        assert c.delete("/api/tours/888").status_code == 400


def test_hoehen_platzhalter(fresh):
    """Platzhalterwerte wie −20 000 m dürfen nicht als Aufstieg gezählt werden (Zepp-Import)."""
    from app import elev, tracks, zepp
    spike = [300.0, 301.0] + [-20000.0] * 4 + [303.0, 304.0, 305.0] + [-200000.0] * 4 + [307.0, 308.0, 309.0, 310.0]
    assert max(elev.clean(spike)) < 400 and min(elev.clean(spike)) > 0
    assert elev.ascent(elev.smooth(spike, 3, 3))[0] > 5000                     # ohne Bereinigung: absurder Aufstieg
    assert elev.ascent(elev.smooth(elev.clean(spike), 3, 3))[0] < 30
    txt = gpx("Workout--2026-05-01--10-00-00.gpx")
    import re as _re
    ele = iter(range(10 ** 6))
    bad = _re.sub(r"<ele>[^<]*</ele>", lambda m: "<ele>-20000.0</ele>" if 100 <= next(ele) < 106 else m.group(0), txt)
    t, c = tracks.adopt(bad, "Workout--2026-05-01--10-00-00.gpx")
    assert t["up_m"] < 200 and "-20000" not in tracks.gpx_file(t["id"]).read_text()
    db.execute("UPDATE tours SET up_m=24000 WHERE id=?", (t["id"],))                  # bereits falsch importierte Tour
    tracks.gpx_file(t["id"]).write_text(bad)
    assert elev.recompute_local() >= 1 and db.one("SELECT up_m FROM tours WHERE id=?", (t["id"],))["up_m"] < 200


def test_zeitzonen_dublette():
    """Dieselbe Aktivität mit um ganze Stunden verschobener Startzeit gilt als Doppelte."""
    from app import sync
    tours = [{"id": "z1", "start_ts": 1729678104, "dist_m": 11100, "dur_s": 5000, "source": "local"}]
    assert sync.is_duplicate(1729681704, 11110, 5010, tours, 300)["id"] == "z1"          # +1 h
    assert sync.is_duplicate(1729681704 + 3600, 11110, 5010, tours, 300)["id"] == "z1"    # +2 h
    assert sync.is_duplicate(1729678104 + 4 * 3600, 11110, 5010, tours, 300) is None      # +4 h: andere Tour
    assert sync.is_duplicate(1729681704, 15000, 5010, tours, 300) is None                 # andere Länge


def test_fotos_ohne_aufnahmezeit_nicht_zugeordnet(fresh, tmp_path):
    """Fotos nur mit Dateidatum (Exportzeit) dürfen nicht automatisch einer Tour zugeordnet werden."""
    from app import photos
    base = 1780000000
    db.execute("INSERT OR REPLACE INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES('u1','T','hike',?,?,1000,3600,10,10,50,8,'x','local')", (base, base + 3600))
    photos._store([("/a.jpg", 1.0, 1, base + 600, None, None, 1), ("/b.jpg", 1.0, 1, base + 700, None, None, 0)])
    photos.assign_all()
    r = {p["path"]: p["tour_id"] for p in db.query("SELECT path,tour_id FROM photos")}
    assert r["/a.jpg"] == "u1" and r["/b.jpg"] is None


def test_reisen_mit_ruhetagen(fresh):
    """Eine Reise darf Tage ohne Tour enthalten (nicht jeden Tag wird gewandert); zu Hause oder weit weg trennt sie."""
    from app import more2
    base = 1780000000 - 1780000000 % 86400 + 43200
    D = 86400
    spec = [(f"h{i}", 50.1, 8.6, base + i * 2 * D) for i in range(-30, 0)]                 # Heimat
    spec += [("r1", -21.1, 55.4, base), ("r2", -21.2, 55.5, base + D), ("r3", -21.0, 55.6, base + 4 * D), ("r4", -21.1, 55.5, base + 5 * D)]   # Reunion mit Ruhetagen
    spec += [("x1", 50.1, 8.6, base + 7 * D)]                                             # zu Hause
    spec += [("a1", 47.0, 12.0, base + 20 * D), ("a2", 47.1, 12.1, base + 21 * D), ("a3", 47.1, 12.1, base + 30 * D), ("a4", 47.1, 12.1, base + 31 * D)]   # 9 Tage Pause
    spec += [("b1", 47.0, 12.0, base + 40 * D), ("b2", 47.1, 12.1, base + 42 * D)]           # 2 Tage Pause -> eine Reise
    for tid, la, lo, ts in spec:
        db.execute("INSERT OR REPLACE INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (tid, tid, "hike", ts, ts + 3600, 8000, 3600, 300, 300, la, lo, "x"))
    got = sorted(sorted(t["tours"]) for t in more2.build_trips())
    assert ["r1", "r2", "r3", "r4"] in got                       # Réunion mit Ruhetagen = eine Reise
    assert ["a1", "a2"] in got and ["a3", "a4"] in got           # mehr als 7 Tage Pause trennt
    assert ["b1", "b2"] in got
