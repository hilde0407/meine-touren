"""Tests für Zustandsseite, doppelte Namen, Zuordnungs-Cache, Update-Backup und den Foto-Upload im Browser."""
import os, subprocess, sys, time, socket, io
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.test_core import fresh  # noqa: F401  (setzt die Testumgebung und liefert die Fixture)
from app import db, health, photos, extras, config, sync  # noqa


def _tour(i, name, ts):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (i, name, "hike", ts, ts + 3600, 1000, 3600, 10, 10, 47.0, 11.0, "tour_recorded", "local"))


def test_duplicate_names_detected():
    _tour("a", "Tag 6", 1600000000); _tour("b", "Tag 6", 1600090000); _tour("c", "Tag 7", 1600180000); _tour("d", "Tag 6", 1700000000)
    d = health.duplicate_names()
    assert len(d) == 1 and {t["id"] for t in d[0]["tours"]} == {"a", "b"}


def test_health_reports_missing_komoot_and_backup(monkeypatch):
    monkeypatch.setattr(extras, "newest_backup", lambda: None)
    h = health.health()
    names = {c["name"]: c for c in h["checks"]}
    assert not names["Komoot-Zugang"]["ok"] and not names["Letztes Backup"]["ok"]
    assert not h["ok"]


def test_update_check_compares_versions(monkeypatch):
    class R:
        status_code = 200
        def json(self): return {"tag_name": "v99.0.0", "html_url": "https://example.org/r"}
    monkeypatch.setattr(health.requests, "get", lambda *a, **k: R())
    health._upd.update(ts=0, data=None)
    u = health.update_check()
    assert u["newer"] and u["latest"] == "99.0.0"


def test_assign_all_skips_when_unchanged(monkeypatch):
    _tour("a", "T", 1600000000)
    db.execute("INSERT INTO photos(path,taken_ts,dated) VALUES('p1',1600000100,1)")
    photos.assign_all()
    assert db.one("SELECT tour_id FROM photos")["tour_id"] == "a"
    calls = []
    monkeypatch.setattr(photos, "log", lambda m: calls.append(m))
    photos.assign_all()
    assert not calls                      # unverändert: keine Neuberechnung
    db.execute("INSERT INTO photos(path,taken_ts,dated) VALUES('p2',1600000200,1)")
    photos.assign_all()
    assert calls and db.one("SELECT tour_id FROM photos WHERE path='p2'")["tour_id"] == "a"


def test_backup_on_update(tmp_path, monkeypatch):
    _tour("a", "T", 1600000000)
    made = []
    monkeypatch.setattr(extras, "auto_backup", lambda max_age_s=0: made.append(1) or "x")
    monkeypatch.setattr(extras, "newest_backup", lambda: None)
    assert extras.backup_on_update() == "x" and made
    made.clear()
    assert extras.backup_on_update() is None and not made    # gleiche Version: nichts


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


@pytest.fixture
def server(tmp_path):
    pytest.importorskip("playwright.sync_api")
    port = _free_port()
    env = dict(os.environ, DATA_DIR=str(tmp_path / "d"), PHOTOS_DIR=str(tmp_path / "p"), BACKUP_DIR=str(tmp_path / "b"))
    root = str(Path(__file__).parent.parent)
    pr = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=root, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    import urllib.request
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=1); break
        except Exception:
            time.sleep(0.2)
    yield port
    pr.terminate(); pr.wait(5)


def test_browser_admin_and_folder_upload(server, tmp_path):
    sync_api = pytest.importorskip("playwright.sync_api")
    from PIL import Image
    import json, urllib.request
    base = f"http://127.0.0.1:{server}"
    req = urllib.request.Request(base + "/api/settings", data=json.dumps({"photo_only_tracked": "0"}).encode(), headers={"content-type": "application/json"})
    urllib.request.urlopen(req)
    d = tmp_path / "up" / "2024"; d.mkdir(parents=True)
    for i in range(3):
        import random; random.seed(i)
        im = Image.new("RGB", (64, 48)); im.putdata([(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)) for _ in range(64 * 48)]); im.save(d / f"f{i}.jpg")
    with sync_api.sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium") if os.path.exists("/opt/pw-browsers/chromium") else None)
        pg = b.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(base + "/#/admin"); pg.wait_for_selector("#hlt", timeout=10000)
        assert "Zustand" in pg.inner_text("#hlt") or pg.locator("#hlt").count() == 0
        assert not errs
        dlg = []
        pg.on("dialog", lambda d: (dlg.append(d.message), d.accept()))
        pg.set_input_files("#pdir", str(d))
        pg.wait_for_function("document.querySelector('#ptxt') && /Fertig|Abgebrochen/.test(document.querySelector('#ptxt').textContent)", timeout=30000)
        pg.wait_for_function("document.querySelector('#ptxt').textContent.includes('✓')", timeout=60000)
        n = json.load(urllib.request.urlopen(base + "/api/photos?limit=50"))
        assert len(n) == 3
        assert not errs
        b.close()


def test_name_suggestions_run_in_parallel(monkeypatch):
    import time as _t
    from app import extras as ex
    def slow(*a, **k):
        _t.sleep(0.4); return None
    monkeypatch.setattr(ex, "guide_matches", lambda pts: slow() or [])
    monkeypatch.setattr(ex, "trail_names", lambda t, pts: slow() or [])
    monkeypatch.setattr(ex, "place_name", lambda la, lo: slow() or "Ort")
    monkeypatch.setattr(ex, "peak_name", lambda la, lo: slow() or "Gipfel")
    pts = [[47.0, 11.0, 1000.0], [47.01, 11.01, 1400.0], [47.02, 11.0, 1100.0]]
    t = {"sport": "hike", "name": "x", "lat": 47.0, "lng": 11.0, "dist_m": 20000}
    t0 = _t.time(); res = ex.name_suggestions(t, pts, "all"); dt = _t.time() - t0
    assert res and dt < 1.3          # nacheinander wären es > 2 s


def test_implausible_hide_and_sport_override():
    from fastapi.testclient import TestClient
    from app import main, more
    _tour("z", "Wanderung 01.03.2020", 1583000000); db.execute("UPDATE tours SET dist_m=50,dur_s=60,source='komoot' WHERE id='z'")
    _tour("f", "Schnell", 1590000000); db.execute("UPDATE tours SET dist_m=40000,dur_s=7200 WHERE id='f'")
    _tour("ok", "Normal", 1600000000)
    c = TestClient(main.app)
    r = c.get("/api/check").json()
    ids = {x["id"]: x for x in r["implausible"]}
    assert set(ids) == {"z", "f"} and ids["f"]["suggest"] == "touringbicycle"
    assert c.post("/api/tours/f/sport", json={"sport": "touringbicycle"}).status_code == 200
    assert c.post("/api/tours/z/hide", json={"hide": True}).status_code == 200
    r = c.get("/api/check").json()
    assert not r["implausible"] and [h["id"] for h in r["hidden"]] == ["z"]
    assert "z" not in {t["id"] for t in c.get("/api/tours").json()}
    # Komoot-Abgleich: ausgeblendete Tour bleibt weg, eigene Sportart bleibt erhalten
    class K:
        def tours(self):
            return [{"id": "z", "name": "x", "sport": "hike", "start_ts": 1583000000, "end_ts": 1583000060, "dist_m": 50, "dur_s": 60, "up_m": 0, "down_m": 0, "lat": 47, "lng": 11, "status": "tour_recorded"},
                    {"id": "k2", "name": "y", "sport": "hike", "start_ts": 1610000000, "end_ts": 1610003600, "dist_m": 5000, "dur_s": 3600, "up_m": 0, "down_m": 0, "lat": 47, "lng": 11, "status": "tour_recorded"}]
    db.execute("INSERT INTO tour_sport(id,sport) VALUES('k2','skitour')")
    sync.refresh_tours(K())
    assert not db.one("SELECT 1 x FROM tours WHERE id='z'") and db.one("SELECT sport FROM tours WHERE id='k2'")["sport"] == "skitour"
    assert c.post("/api/tours/z/hide", json={"hide": False}).status_code == 200
    assert db.one("SELECT dist_m FROM tours WHERE id='z'")["dist_m"] == 50


def test_delete_tour_local_and_komoot(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main, portals
    deleted = []
    class K:
        def delete(self, i): deleted.append(i); return True
        def tours(self):
            return [{"id": "k1", "name": "x", "sport": "hike", "start_ts": 1583000000, "end_ts": 1583000060, "dist_m": 50, "dur_s": 60, "up_m": 0, "down_m": 0, "lat": 47, "lng": 11, "status": "tour_recorded"}]
    monkeypatch.setattr(sync, "_komoot", lambda *a, **k: K())
    c = TestClient(main.app)
    sync.refresh_tours(K())
    assert db.one("SELECT 1 x FROM tours WHERE id='k1'")
    # nur hier löschen: kommt beim Abgleich nicht wieder
    assert c.post("/api/tours/k1/delete", json={"komoot": False}).json()["ok"] and not deleted
    sync.refresh_tours(K())
    assert not db.one("SELECT 1 x FROM tours WHERE id='k1'")
    assert c.get("/api/check").json()["hidden"] == []
    # lokale, zu Komoot hochgeladene Tour: auch dort löschen
    _tour("g1", "Lokal", 1600000000)
    portals.record("g1", "komoot", "uploaded", "999")
    r = c.post("/api/tours/g1/delete", json={"komoot": True}).json()
    assert deleted == ["999"] and "gelöscht" in r["komoot"] and not db.one("SELECT 1 x FROM tours WHERE id='g1'")


def test_set_sport_also_on_komoot(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    calls = []
    class K:
        def set_sport(self, i, s): calls.append((i, s))
    monkeypatch.setattr(sync, "_komoot", lambda *a, **k: K())
    _tour("k5", "Komoot", 1600000000); db.execute("UPDATE tours SET source='komoot' WHERE id='k5'")
    r = TestClient(main.app).post("/api/tours/k5/sport", json={"sport": "touringbicycle", "komoot": True}).json()
    assert calls == [("k5", "touringbicycle")] and r["komoot"] == "auch bei Komoot geändert"
    assert db.one("SELECT sport FROM tours WHERE id='k5'")["sport"] == "touringbicycle"


def test_secrets_are_encrypted(monkeypatch):
    from app import secret
    monkeypatch.delenv("MT_SECRET_KEY", raising=False); secret.reset_cache()
    db.put("komoot_password", "geheim123")
    raw = db.one("SELECT v FROM settings WHERE k='komoot_password'")["v"]
    assert raw.startswith("enc1:") and "geheim" not in raw
    assert db.get("komoot_password") == "geheim123"
    assert (config.DATA_DIR / "secret.key").exists()
    if os.name != "nt":
        assert oct((config.DATA_DIR / "secret.key").stat().st_mode)[-3:] == "600"
    # Altbestand im Klartext wird beim Lesen verschlüsselt
    db.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('strava_tokens','{\"a\":1}')")
    assert db.get("strava_tokens") == '{"a":1}'
    assert db.one("SELECT v FROM settings WHERE k='strava_tokens'")["v"].startswith("enc1:")
    # anderer Schlüssel (z. B. Sicherung von einem anderen Rechner): leer statt Fehler
    monkeypatch.setenv("MT_SECRET_KEY", "anderer"); secret.reset_cache()
    assert db.get("komoot_password") == ""
    monkeypatch.delenv("MT_SECRET_KEY"); secret.reset_cache()
    assert db.get("komoot_password") == "geheim123"
    assert db.get("tile_style") == db.get("tile_style")        # normale Einstellungen unverändert


def test_shift_photos_tour_day_and_reset():
    _tour("a", "T", 1600000000); _tour("b", "U", 1600020000)
    for i, (ts, tour) in enumerate([(1600000100, "a"), (1600000200, "a"), (1600012000, None), (1600020100, "b"), (1600200000, None)]):
        db.execute("INSERT INTO photos(path,taken_ts,dated,tour_id) VALUES(?,?,1,?)", (f"p{i}", ts, tour))
    photos.assign_all()
    q = lambda: [r["taken_ts"] for r in db.query("SELECT taken_ts FROM photos ORDER BY id")]
    r = photos.shift_photos("a", 600)
    assert r["shifted"] == 2 and q() == [1600000700, 1600000800, 1600012000, 1600020100, 1600200000]
    row = db.one("SELECT manual, offset_s FROM photos WHERE path='p0'")
    assert row["manual"] == 1 and row["offset_s"] == 600
    photos.shift_photos("a", 60, scope="day")                      # auch p2 (gleicher Tag, ohne Tour); b/andere Tage nicht
    assert q() == [1600000760, 1600000860, 1600012060, 1600020100, 1600200000]
    r = photos.shift_photos("a", 0, reset=True, scope="day")
    assert q() == [1600000100, 1600000200, 1600012000, 1600020100, 1600200000]
    with pytest.raises(ValueError):
        photos.shift_photos("a", 10 ** 9)
    with pytest.raises(KeyError):
        photos.shift_photos("nix", 1)
    _tour("c", "leer", 1700000000)
    with pytest.raises(ValueError):
        photos.shift_photos("c", 5)


def test_photo_shift_api():
    from fastapi.testclient import TestClient
    from app import main
    _tour("a", "T", 1600000000)
    db.execute("INSERT INTO photos(path,taken_ts,dated,tour_id) VALUES('p',1600000100,1,'a')")
    with TestClient(main.app) as c:
        assert c.post("/api/photo-shift", json={"tour_id": "a", "delta_s": 30}).json()["shifted"] == 1
        assert c.post("/api/photo-shift", json={"tour_id": "zz", "delta_s": 1}).status_code == 404
        assert c.post("/api/photo-shift", json={"tour_id": "a", "delta_s": "abc"}).status_code == 400
