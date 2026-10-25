"""Tests für Garmin-/Suunto-Import, FIT-Dateien und Datei-Import (ohne echte Konten: Antworten sind nachgebaut)."""
import io, json, struct, sys, time, types, zipfile
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.test_core import fresh  # noqa: F401
from app import db, devices, fitfile, jobs  # noqa

FIT_EPOCH = 631065600
HERE = Path(__file__).parent


def _deg(d):
    return int(d * 2 ** 31 / 180)


def make_fit(t0, lat0=47.5, lon0=12.9, n=40, sport=17, sub=0, big=False, compressed=False, dev=False, nogps=False):
    """Kleiner FIT-Schreiber nur für Tests (Definition + Datensätze, optional Big-Endian/komprimierte Zeit/Entwicklerfelder)."""
    e = ">" if big else "<"
    body = b""
    # Definition record (global 20): timestamp, lat, lon, altitude
    fields = [(253, 4, 0x86), (0, 4, 0x85), (1, 4, 0x85), (2, 2, 0x84)]
    hdr = 0x40 | (0x20 if dev else 0) | 0
    body += bytes([hdr, 0, 1 if big else 0]) + struct.pack(e + "H", 20) + bytes([len(fields)]) + b"".join(bytes(f) for f in fields)
    if dev:
        body += bytes([1, 1, 2, 0])                     # ein Entwicklerfeld: Nr 1, 2 Byte, Gerät 0
    ts0 = t0 - FIT_EPOCH
    for i in range(n):
        la, lo = (0x7FFFFFFF, 0x7FFFFFFF) if nogps else (_deg(lat0 + i * 0.0003), _deg(lon0 + i * 0.0004))
        body += bytes([0]) + struct.pack(e + "IiiH", ts0 + i * 5, la, lo, int((1200 + i * 2) * 5 + 2500))
        if dev:
            body += b"\x01\x02"
    if compressed:                                      # Definition ohne Zeitstempel + komprimierte Köpfe
        f2 = [(0, 4, 0x85), (1, 4, 0x85)]
        body += bytes([0x41, 0, 1 if big else 0]) + struct.pack(e + "H", 20) + bytes([2]) + b"".join(bytes(f) for f in f2)
        last = ts0 + (n - 1) * 5
        for k in range(1, 6):
            off = (last + k * 2) & 0x1F
            body += bytes([0x80 | (1 << 5) | off]) + struct.pack(e + "ii", _deg(lat0 + (n + k) * 0.0003), _deg(lon0 + (n + k) * 0.0004))
    # Session (global 18): sport, sub_sport
    body += bytes([0x42, 0, 1 if big else 0]) + struct.pack(e + "H", 18) + bytes([2, 5, 1, 0, 6, 1, 0]) + bytes([2, sport, sub])
    head = struct.pack("<BBHI4s", 14, 0x20, 2100, len(body), b".FIT") + b"\x00\x00"
    return head + body + b"\x00\x00"


T0 = 1750000000


def test_fit_decoder_matches_reference_file():
    d = (HERE / "beispiel_wanderung.fit").read_bytes()
    gpx, sp = fitfile.to_gpx(d, "x")
    assert sp == "hike" and gpx.count("<trkpt") == 60
    assert 'lat="47.5000000" lon="12.9000000"' in gpx


@pytest.mark.parametrize("kw", [{}, {"big": True}, {"dev": True}, {"compressed": True}, {"big": True, "dev": True, "compressed": True}])
def test_fit_variants(kw):
    gpx, sp = fitfile.to_gpx(make_fit(T0, **kw))
    n = gpx.count("<trkpt")
    assert n == (45 if kw.get("compressed") else 40)
    assert sp == "hike"
    assert "<ele>1200.0</ele>" in gpx


def test_fit_sports_and_no_gps():
    assert fitfile.to_gpx(make_fit(T0, sport=2, sub=8))[1] == "mtb"
    assert fitfile.to_gpx(make_fit(T0, sport=13, sub=37))[1] == "skitour"
    assert fitfile.to_gpx(make_fit(T0, sport=2, sub=28))[1] == "e_touringbicycle"
    with pytest.raises(ValueError):
        fitfile.to_gpx(make_fit(T0, nogps=True))
    assert [k for _, _, k in fitfile.expand("a.fit", make_fit(T0, nogps=True))] == ["nogps"]
    assert [k for _, _, k in fitfile.expand("a.fit", b"kein fit")] == ["bad"]


def test_zip_nested_like_garmin_export(tmp_path):
    inner = io.BytesIO()
    with zipfile.ZipFile(inner, "w") as z:
        z.writestr("1.fit", make_fit(T0)); z.writestr("2.fit", make_fit(T0 + 86400, nogps=True)); z.writestr("x.json", "{}")
    outer = tmp_path / "export.zip"
    with zipfile.ZipFile(outer, "w") as z:
        z.writestr("DI_CONNECT/DI-Connect-Fitness-Uploaded-Files/UploadedFiles_0-_Part1.zip", inner.getvalue())
        z.writestr("DI_CONNECT/summarizedActivities.json", "[]")
    kinds = sorted(k for _, _, k in fitfile.iter_expand(str(outer)))
    assert kinds == ["fit", "nogps"]


def test_import_paths_creates_local_tours_and_is_idempotent(tmp_path):
    z = tmp_path / "e.zip"
    with zipfile.ZipFile(z, "w") as zz:
        for i in range(3):
            zz.writestr(f"{i}.fit", make_fit(T0 + i * 86400, lat0=47.5 + i * 0.1))
        zz.writestr("leer.fit", make_fit(T0, nogps=True))
    t = devices.import_paths([z])
    assert t["imported"] == 3 and t["nogps"] == 1
    rows = db.query("SELECT * FROM tours WHERE source='local'")
    assert len(rows) == 3 and all(r["dist_m"] > 500 for r in rows)
    t2 = devices.import_paths([z])
    assert t2["imported"] == 0                                  # nichts doppelt
    assert len(db.query("SELECT id FROM tours")) == 3


def test_import_paths_dry_run_changes_nothing(tmp_path):
    f = tmp_path / "a.fit"; f.write_bytes(make_fit(T0))
    t = devices.import_paths([f], dry_run=True)
    assert t["imported"] == 1 and not db.query("SELECT id FROM tours")


def test_inbox_folder_import(tmp_path):
    from app import config
    root = config.INBOX_DIR / "touren"; root.mkdir(parents=True, exist_ok=True)
    (root / "a.fit").write_bytes(make_fit(T0))
    assert devices.import_inbox_activities() == 1
    assert not (root / "a.fit").exists() and (root / "erledigt" / "a.fit").exists()


# ----------------------------------------------------------------- Garmin (nachgebaut)
class FakeGarmin:
    class ActivityDownloadFormat:
        ORIGINAL, GPX = "orig", "gpx"

    def __init__(self, acts):
        self.acts, self.calls = acts, 0
        self.client = types.SimpleNamespace(dumps=lambda: json.dumps({"di_token": "t2"}))

    def get_activities(self, start, limit):
        self.calls += 1
        return self.acts[start:start + limit]

    def download_activity(self, aid, dl_fmt):
        a = next(x for x in self.acts if x["activityId"] == aid)
        if dl_fmt == "orig":
            b = io.BytesIO()
            with zipfile.ZipFile(b, "w") as z:
                z.writestr(f"{aid}_ACTIVITY.fit", a["_fit"])
            return b.getvalue()
        return b"<gpx></gpx>"


def _acts(n, base=T0):
    out = []
    for i in range(n):
        ts = base - i * 86400
        out.append({"activityId": 9000 + i, "activityName": f"Wanderung {i}" if i % 2 else "Garmin Wandern",
                    "startTimeGMT": time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(ts)), "activityType": {"typeKey": "mountain_biking" if i == 0 else "hiking"},
                    "hasPolyline": i != 3, "_fit": make_fit(ts, lat0=47.0 + i * 0.05)})
    return out


def test_garmin_sync_imports_names_sports_and_remembers(monkeypatch):
    db.put("garmin_tokens", json.dumps({"di_token": "t"}))
    fake = FakeGarmin(_acts(6))
    monkeypatch.setattr(devices, "_garmin_client", lambda: fake)
    monkeypatch.setattr(devices.time, "sleep", lambda s: None)
    r = devices.garmin_sync()
    assert r["imported"] == 5                                   # Nr. 3 hat keine Polyline (drinnen)
    t = db.one("SELECT * FROM tours WHERE name='Wanderung 1'")
    assert t and t["sport"] == "hike" and t["source"] == "local"
    assert db.one("SELECT sport FROM tours ORDER BY start_ts DESC LIMIT 1")["sport"] == "mtb"
    assert db.one("SELECT COUNT(*) n FROM ext_imports WHERE src='garmin'")["n"] == 6
    assert json.loads(db.get("garmin_tokens")) == {"di_token": "t2"}      # erneuerte Token gespeichert
    n = len(db.query("SELECT id FROM tours"))
    r2 = devices.garmin_sync()
    assert r2["imported"] == 0 and len(db.query("SELECT id FROM tours")) == n


def test_garmin_since_filter(monkeypatch):
    db.put("garmin_tokens", json.dumps({"di_token": "t"}))
    db.put("garmin_since", time.strftime("%Y-%m-%d", time.gmtime(T0 - 2 * 86400 + 3600)))
    monkeypatch.setattr(devices, "_garmin_client", lambda: FakeGarmin(_acts(6)))
    monkeypatch.setattr(devices.time, "sleep", lambda s: None)
    assert devices.garmin_sync()["imported"] == 3          # ab Datum einschließlich des ganzen Tages: 13., 14., 15. Juni


def test_garmin_login_with_mfa(monkeypatch):
    class G:
        def __init__(self, email=None, password=None, return_on_mfa=False):
            self.client = types.SimpleNamespace(dumps=lambda: json.dumps({"di_token": "neu"}))
        def login(self, tok=None): return "needs_mfa", {"state": 1}
        def resume_login(self, state, code):
            assert code == "123456" and state == {"state": 1}
    monkeypatch.setitem(sys.modules, "garminconnect", types.SimpleNamespace(Garmin=G))
    assert devices.garmin_login("a@b.de", "pw") == {"mfa": True}
    with pytest.raises(devices.DeviceError):
        devices.garmin_mfa("000")  # falscher Code löst im Fake einen AssertionError aus -> als DeviceError gemeldet
    assert not devices.garmin_connected()
    devices.garmin_login("a@b.de", "pw")
    assert devices.garmin_mfa(" 123456 ") == {"ok": True}
    assert devices.garmin_connected() and db.get("garmin_email") == "a@b.de"
    assert "pw" not in (db.get("garmin_tokens") or "")          # Passwort wird nie gespeichert


def test_garmin_missing_package_gives_hint(monkeypatch):
    monkeypatch.setitem(sys.modules, "garminconnect", None)
    ok, why = devices.garmin_available()
    assert not ok and "Dateiweg" in why


def test_garmin_error_messages():
    assert "bremst" in devices._garmin_err(Exception("429 Too Many Requests"))
    assert "abgelehnt" in devices._garmin_err(Exception("401 Unauthorized"))


# ----------------------------------------------------------------- Suunto (nachgebaut)
class Resp:
    def __init__(self, code=200, js=None, content=b""):
        self.status_code, self._js, self.content = code, js, content
    def json(self): return self._js


def test_suunto_oauth_and_sync(monkeypatch):
    db.put("suunto_client_id", "cid"); db.put("suunto_client_secret", "sec"); db.put("suunto_key", "key")
    seen = {}
    def post(url, data=None, auth=None, timeout=0):
        seen["post"] = (url, data, auth)
        return Resp(200, {"access_token": "A", "refresh_token": "R", "expires_in": 86400})
    monkeypatch.setattr(devices.requests, "post", post)
    devices.suunto_exchange("CODE", "https://x/api/suunto/callback")
    assert seen["post"][0].endswith("/oauth/token") and seen["post"][2] == ("cid", "sec") and seen["post"][1]["code"] == "CODE"
    assert devices.suunto_connected() and "enc1:" in db.one("SELECT v FROM settings WHERE k='suunto_tokens'")["v"]
    ws = [{"workoutKey": f"W{i}", "startTime": (T0 - i * 86400) * 1000, "activityId": 11 if i else 2} for i in range(3)]
    fits = {f"W{i}": make_fit(T0 - i * 86400, lat0=46.0 + i * 0.05) for i in range(3)}
    hdrs = []
    def get(url, params=None, headers=None, timeout=0):
        hdrs.append(headers)
        if url.endswith("/v2/workouts"):
            return Resp(200, {"payload": ws if not params["offset"] else []})
        return Resp(200, content=fits[url.rsplit("/", 1)[-1]])
    monkeypatch.setattr(devices.requests, "get", get)
    monkeypatch.setattr(devices.time, "sleep", lambda s: None)
    r = devices.suunto_sync()
    assert r["imported"] == 3
    assert hdrs[0]["Ocp-Apim-Subscription-Key"] == "key" and hdrs[0]["Authorization"] == "Bearer A"
    assert db.one("SELECT COUNT(*) n FROM tours WHERE sport='hike'")["n"] == 2
    assert devices.suunto_sync()["imported"] == 0


def test_suunto_refresh_expired_token(monkeypatch):
    db.put("suunto_client_id", "cid"); db.put("suunto_client_secret", "sec"); db.put("suunto_key", "key")
    db.put("suunto_tokens", json.dumps({"access_token": "alt", "refresh_token": "R", "expires_at": 1}))
    got = {}
    monkeypatch.setattr(devices.requests, "post", lambda url, data=None, auth=None, timeout=0: got.update(d=data) or Resp(200, {"access_token": "NEU", "expires_in": 100}))
    assert devices._su_access() == "NEU" and got["d"]["grant_type"] == "refresh_token"
    assert devices.suunto_tokens()["refresh_token"] == "R"        # alter Refresh-Token bleibt, falls kein neuer kommt


def test_suunto_forbidden_message(monkeypatch):
    db.put("suunto_tokens", json.dumps({"access_token": "a", "expires_at": 9999999999}))
    monkeypatch.setattr(devices.requests, "get", lambda *a, **k: Resp(403))
    with pytest.raises(devices.DeviceError) as e:
        devices._su_get("/v2/workouts")
    assert "Subscription-Key" in str(e.value)
