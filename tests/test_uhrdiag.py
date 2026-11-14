"""3.10.1 – Diagnose „Was liefert meine Uhr?“: Felderliste je Tour und je Gerät, Aggregation, Obergrenze der Zepp-Abrufe, Rechte, Datenschutz des Exports.
Alle Daten sind konstruiert (Zepp-Zusammenfassung/-Detail, FIT-Datei, GPX, Zusatzdatei) – echte Zepp-Antworten gibt es hier nicht. Die Zepp-Felder
`te`, `recovery_time`, `neues_feld`, `new_channel` usw. sind ERFUNDEN, um zu prüfen, dass unbekannte Felder nie verschwiegen werden."""
import io
import json
import struct
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from tests.test_messwerte import _client  # noqa: E402
from app import config, db, fitfile, metrics, sync, tracks, uhrdiag  # noqa: E402

T0 = 1750000000
TOKEN = "SUPER-GEHEIMES-TOKEN-4711"
FIT_EPOCH = 631065600


# ---------------------------------------------------------------- Bausteine
def _deg(d):
    return int(d * 2 ** 31 / 180)


def make_fit(t0=T0, n=40, unknown=True, serial=123456789):
    """FIT mit file_id (inkl. Seriennummer), record (Puls, Strecke, Höhe, Schrittlänge, UNBEKANNTES Feld 226 und 227) und session (Kalorien, Trainingseffekt, UNBEKANNTE Felder 200 und 168)."""
    e = "<"
    body = b""
    fid = [(1, 2, 0x84), (2, 2, 0x84), (3, 4, 0x8C)]
    body += bytes([0x40, 0, 0]) + struct.pack(e + "H", 0) + bytes([len(fid)]) + b"".join(bytes(f) for f in fid)
    body += bytes([0]) + struct.pack(e + "HHI", 1, 3990, serial)
    f = [(253, 4, 0x86), (0, 4, 0x85), (1, 4, 0x85), (3, 1, 0x02), (5, 4, 0x86), (85, 2, 0x84)] + ([(226, 2, 0x84), (227, 1, 0x02)] if unknown else [])
    body += bytes([0x41, 0, 0]) + struct.pack(e + "H", 20) + bytes([len(f)]) + b"".join(bytes(x) for x in f)
    ts0 = t0 - FIT_EPOCH
    for i in range(n):
        row = struct.pack(e + "IiiBIH", ts0 + i * 5, _deg(47.5 + i * 0.0003), _deg(12.9 + i * 0.0004), 120 + i % 30, i * 1000, 10500 + i)
        if unknown:
            row += struct.pack(e + "HB", 300 + i, 7)
        body += bytes([1]) + row
    s = [(2, 4, 0x86), (11, 2, 0x84), (24, 1, 0x02)] + ([(200, 2, 0x84), (168, 2, 0x84)] if unknown else [])
    body += bytes([0x42, 0, 0]) + struct.pack(e + "H", 18) + bytes([len(s)]) + b"".join(bytes(x) for x in s)
    body += bytes([2]) + struct.pack(e + "IHB", ts0, 612, 34) + (struct.pack(e + "HH", 55, 1234) if unknown else b"")
    head = struct.pack("<BBHI4s", 14, 0x20, 2100, len(body), b".FIT") + b"\x00\x00"
    return head + body + b"\x00\x00"


def _tour(tid, ts, kind="zepp", dist=10000, dur=3000, name=None):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,100,100,'t','komoot')",
               (tid, name or f"Geheimer Tourname {tid}", "hike", ts, ts + dur, dist, dur))
    db.execute("INSERT OR REPLACE INTO tour_source(tour_id,src,name) VALUES(?,?,'')", (tid, kind))


def _summary(start, **kw):
    s = {"trackid": str(start), "source": "run.46.huami.com", "type": "6", "dis": "10000", "run_time": "3000", "end_time": str(start + 3000), "calorie": "512",
         "te": "3.4", "recovery_time": "36", "neues_feld": "7", "objekt": {"a": 1, "b": "x"}, "city": "Berlin", "lat_start": "48.1234", "device_serial": "ABC123", "leer": ""}
    s.update(kw)
    return s


def _detail(extra=True):
    d = {"time": "0;10;10;10", "longitude_latitude": "4812340000,812340000;1000,1000;1000,1000;1000,1000", "altitude": "80000;80100;80250;80300",
         "heart_rate": ",80;,1;,2;,-1", "gait": "", "speed": ""}
    if extra:
        d.update({"new_channel": "1,5;1,6;1,;1,8", "stress": "", "vo2max_curve": "10,-2000000;10,41"})
    return d


class Api:
    def __init__(self, hist, extra=True, fail_detail=False):
        self.hist, self.extra, self.details, self.fail_detail = hist, extra, 0, fail_detail

    def history(self):
        return self.hist

    def detail(self, s):
        self.details += 1
        if self.fail_detail:
            raise RuntimeError("Detail kaputt")
        return _detail(self.extra)


def _use_api(monkeypatch, api):
    monkeypatch.setattr(sync, "_zepp_api", lambda: api)
    return api


def _dev(c, **kw):
    return c.post("/api/devices", json=dict({"name": "Meine Balance 2", "kind": "zepp", "model": "Balance 2"}, **kw)).json()["id"]


def _by(src, name):
    return next(f for f in src["fields"] if f["name"] == name)


def _src(rep, key):
    return next(s for s in rep["sources"] if s["key"] == key)


def _gpx(tid, with_ext=True):
    config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
    pts = "".join(f'<trkpt lat="{47.5 + i * 0.0003:.6f}" lon="12.9"><ele>1200</ele><time>2025-06-15T14:{i // 60:02d}:{i % 60:02d}Z</time>'
                  + (f"<extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>{120 + i}</gpxtpx:hr><gpxtpx:mystery>{i * 3}</gpxtpx:mystery></gpxtpx:TrackPointExtension></extensions>" if with_ext else "")
                  + "</trkpt>" for i in range(30))
    tracks.gpx_file(tid).write_text('<?xml version="1.0"?><gpx version="1.1" creator="t" xmlns="http://www.topografix.com/GPX/1/1" xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">'
                                    f"<trk><trkseg>{pts}</trkseg></trk></gpx>", encoding="utf-8")


def _world(monkeypatch, n=1, extra=True):
    """n Zepp-Touren eines Geräts (neueste zuerst bei den hohen Nummern), Zepp-Verlauf mit passenden Trainings."""
    c = _client()
    did = _dev(c)
    hist, tids = [], []
    for i in range(n):
        st = T0 + i * 86400
        tid = f"z{st + 10}"
        _tour(tid, st + 10, "zepp")
        hist.append(_summary(st + 10))
        tids.append(tid)
    return c, did, tids, _use_api(monkeypatch, Api(hist, extra))


# ---------------------------------------------------------------- FIT-Scan
def test_fit_scan_lists_known_and_unknown_fields_with_counts():
    sc = fitfile.scan(make_fit(n=40))
    f = sc["fields"]
    assert f[(20, 3)]["n"] == 40 and min(f[(20, 3)]["vals"]) == 120
    assert f[(20, 226)]["n"] == 40 and f[(20, 226)]["vals"][0] == 300 and f[(20, 227)]["vals"][0] == 7           # unbekannte Felder werden erreicht
    assert f[(18, 200)]["vals"] == [55] and f[(18, 168)]["vals"] == [1234] and f[(18, 11)]["vals"] == [612]
    assert f[(0, 3)]["vals"] == [123456789]
    assert not sc["bad"] and T0 in sc["starts"]
    # normales Lesen ist unverändert
    gpx, _sp = fitfile.to_gpx(make_fit(n=40))
    assert gpx.count("<trkpt") == 40


def test_fit_scan_of_damaged_file_keeps_what_was_read():
    raw = make_fit(n=40)
    sc = fitfile.scan(raw[:len(raw) // 2 + 3])
    assert sc["fields"][(20, 3)]["n"] > 5                                         # Teil gelesen
    assert fitfile.scan(b"das ist keine FIT-Datei")["bad"] is True


# ---------------------------------------------------------------- Felderliste je Tour
def test_tour_fields_all_sources_and_unknown_never_hidden(monkeypatch):
    c, did, tids, api = _world(monkeypatch)
    tid = tids[0]
    config.INBOX_DIR.mkdir(parents=True, exist_ok=True)
    (config.INBOX_DIR / "a.fit").write_bytes(make_fit(t0=T0 + 10))
    _gpx(tid)
    metrics.store(tid, {"v": 1, "src": "zepp", "device": "x", "t0": 0, "t": [0, 1, 2, 3, 4, 5, 6], "series": {"speed": [1.0, 2.0, None, 3.0, 3.0, 3.0, 3.0], "cad": [150.0] * 7}, "sum": {"kcal": 512, "te": 3.4}})
    r = c.get(f"/api/tours/{tid}/uhr-felder")
    assert r.status_code == 200
    rep = r.json()
    assert [s["key"] for s in rep["sources"]] == ["zepp_summary", "zepp_detail", "fit", "gpx", "sidecar"]
    assert all(s["state"] == "ok" and s["tours_checked"] == 1 for s in rep["sources"])
    # (a) Zusammenfassung
    zs = _src(rep, "zepp_summary")
    assert {f["name"] for f in zs["fields"]} >= {"trackid", "source", "type", "dis", "run_time", "end_time", "calorie", "te", "recovery_time", "neues_feld", "objekt", "objekt.a", "objekt.b", "city", "lat_start", "device_serial", "leer"}
    assert _by(zs, "calorie")["used"] is True and _by(zs, "calorie")["min"] == 512 and "Kalorien" in _by(zs, "calorie")["text"]
    assert _by(zs, "recovery_time")["used"] is False and _by(zs, "recovery_time")["text"].startswith("vermutlich: Erholungszeit")
    assert _by(zs, "te")["text"].startswith("vermutlich: Trainingseffekt") and _by(zs, "neues_feld")["used"] is False and _by(zs, "neues_feld")["text"] == ""
    assert _by(zs, "leer")["n"] == 0 and _by(zs, "leer")["type"] == "leer" and _by(zs, "objekt")["type"] == "Objekt"
    for k in ("city", "lat_start", "device_serial", "trackid", "end_time"):                       # Koordinaten/Kennungen/Zeitstempel: kein Wert
        f = _by(zs, k)
        assert f["hidden"] and f["min"] is None and f["max"] is None and f["sample"] is None, k
    # (b) Detail
    zd = _src(rep, "zepp_detail")
    names = {f["name"] for f in zd["fields"]}
    assert {"time", "longitude_latitude[0]", "longitude_latitude[1]", "altitude", "heart_rate[0]", "heart_rate[1]", "gait", "speed", "new_channel[0]", "new_channel[1]", "stress", "vo2max_curve[1]"} <= names
    hr = _by(zd, "heart_rate[1]")
    assert hr["used"] and (hr["min"], hr["median"], hr["max"]) == (-1, 1.5, 80) and hr["share"] == 1.0 and hr["n"] == 4
    assert _by(zd, "heart_rate[0]")["share"] == 0.0 and _by(zd, "heart_rate[0]")["type"] == "leer"      # leerer Zeitabstand = 1 s
    nc = _by(zd, "new_channel[1]")
    assert nc["used"] is False and (nc["min"], nc["max"]) == (5, 8) and nc["n"] == 3 and nc["share"] == 0.75       # 3 von 4 Zeilen gefüllt
    v = _by(zd, "vo2max_curve[1]")
    assert v["n"] == 1 and v["share"] == 0.5 and v["min"] == v["max"] == 41                       # Platzhalter -2000000 zählt nicht
    assert v["text"].startswith("vermutlich: VO2max")
    assert _by(zd, "stress")["n"] == 0
    for f in zd["fields"]:
        if f["name"].startswith("longitude_latitude"):
            assert f["hidden"] and f["min"] is None and f["median"] is None and f["max"] is None
    assert _by(zd, "altitude")["max"] == 80300 and _by(zd, "altitude")["used"]
    # (c) FIT: bekannte und unbekannte Felder mit Nummer
    fit = _src(rep, "fit")
    assert rep["fit_scanned"] == 1
    hrf = _by(fit, "record.heart_rate")
    assert hrf["used"] and hrf["n"] == 40 and hrf["unit"] == "bpm" and (hrf["min"], hrf["max"]) == (120, 149) and (hrf["msg"], hrf["num"]) == (20, 3)
    st = _by(fit, "record.step_length")
    assert st["used"] and st["unit"] == "mm" and 1049 < st["min"] < 1051 and "Schrittlänge" in st["text"]
    kc = _by(fit, "session.total_calories")
    assert kc["used"] and kc["min"] == 612 and _by(fit, "session.total_training_effect")["max"] == 3.4
    u = _by(fit, "record.feld_226")
    assert not u["used"] and u["known"] is False and u["n"] == 40 and u["min"] == 300 and u["max"] == 339 and (u["msg"], u["num"]) == (20, 226) and "unbekannt" in u["text"]
    assert _by(fit, "session.feld_200")["min"] == 55 and _by(fit, "session.feld_168")["min"] == 1234
    assert _by(fit, "record.distance")["used"] is False                                            # wird heute nicht ausgewertet
    pos = _by(fit, "record.position_lat")
    assert pos["used"] and pos["hidden"] and pos["min"] is None                                    # Koordinaten nie ausgegeben
    ser = _by(fit, "file_id.serial_number")
    assert ser["hidden"] and ser["min"] is None
    man = _by(fit, "file_id.manufacturer")
    assert not man["hidden"] and man["min"] == 1 and man["used"]                                 # Herstellernummer ist unbedenklich und wird gezeigt
    # (d) GPX und Zusatzdatei
    g = _src(rep, "gpx")
    assert _by(g, "hr")["used"] and _by(g, "hr")["n"] == 30 and _by(g, "mystery")["used"] is False and _by(g, "mystery")["max"] == 87
    sc = _src(rep, "sidecar")
    assert _by(sc, "speed")["n"] == 6 and _by(sc, "speed")["share"] == round(6 / 7, 3) and _by(sc, "speed")["used"]
    assert _by(sc, "sum.te")["min"] == 3.4 and _by(sc, "cad")["unit"] == "1/min"
    # nirgends Koordinaten oder Zugangsdaten
    txt = json.dumps(rep)
    for bad in ("48.1234", "4812340000", "Berlin", "ABC123", "123456789", "47.5", TOKEN):
        assert bad not in txt, bad
    assert api.details == 1


def test_tour_unknown_404_and_read_only(monkeypatch):
    c, did, tids, api = _world(monkeypatch)
    assert c.get("/api/tours/gibtsnicht/uhr-felder").status_code == 404
    _gpx(tids[0])
    metrics.store(tids[0], {"v": 1, "src": "zepp", "device": "x", "t0": 0, "t": [0], "series": {"speed": [1.0] * 6}})
    before = ([dict(r) for r in db.query("SELECT * FROM tours")], [dict(r) for r in db.query("SELECT * FROM tour_source")], [dict(r) for r in db.query("SELECT * FROM tour_zsrc")],
              [dict(r) for r in db.query("SELECT * FROM devices")], [dict(r) for r in db.query("SELECT * FROM tour_device")],
              {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in config.TRACK_DIR.iterdir()})
    assert c.get(f"/api/tours/{tids[0]}/uhr-felder").status_code == 200
    assert c.get(f"/api/devices/{did}/uhr-felder").status_code == 200
    assert c.get(f"/api/devices/{did}/uhr-felder.json?download=1").status_code == 200
    after = ([dict(r) for r in db.query("SELECT * FROM tours")], [dict(r) for r in db.query("SELECT * FROM tour_source")], [dict(r) for r in db.query("SELECT * FROM tour_zsrc")],
             [dict(r) for r in db.query("SELECT * FROM devices")], [dict(r) for r in db.query("SELECT * FROM tour_device")],
             {p.name: (p.stat().st_mtime_ns, p.read_bytes()) for p in config.TRACK_DIR.iterdir()})
    assert before == after                                                                         # nichts verändert, nichts gespeichert
    assert c.post(f"/api/tours/{tids[0]}/uhr-felder").status_code in (404, 405)
    assert c.get("/api/devices/9999/uhr-felder").status_code == 404


def test_states_without_zepp_access_without_training_and_on_error(monkeypatch):
    c = _client()
    did = _dev(c)
    _tour("a1", T0, "zepp")
    _gpx("a1")

    def nope():
        raise RuntimeError("Zepp-Zugangsdaten fehlen (Einstellungen)")
    monkeypatch.setattr(sync, "_zepp_api", nope)
    rep = c.get("/api/tours/a1/uhr-felder").json()
    assert _src(rep, "zepp_summary")["state"] == "kein_zugang" and "Zepp-Zugang" in _src(rep, "zepp_summary")["hint"]
    assert _src(rep, "gpx")["state"] == "ok" and _src(rep, "fit")["state"] == "keine_datei" and _src(rep, "sidecar")["state"] == "keine_datei"   # Rest geht weiter
    # Verlauf ohne passendes Training
    _use_api(monkeypatch, Api([_summary(T0 + 40 * 86400)]))
    assert _src(c.get("/api/tours/a1/uhr-felder").json(), "zepp_detail")["state"] == "kein_training"
    # Fehler: Token darf nirgends erscheinen
    db.put("zepp_token", TOKEN)

    class Boom(Api):
        def history(self):
            raise sync.zepp.ZeppError(f"HTTP 401 mit {TOKEN}")
    _use_api(monkeypatch, Boom([]))
    rep = c.get("/api/tours/a1/uhr-felder").json()
    assert _src(rep, "zepp_summary")["state"] == "fehler" and TOKEN not in json.dumps(rep)
    d = c.get(f"/api/devices/{did}/uhr-felder").json()
    assert _src(d, "zepp_summary")["state"] == "fehler" and TOKEN not in json.dumps(d)
    # Detail-Fehler: Zusammenfassung bleibt
    _use_api(monkeypatch, Api([_summary(T0)], fail_detail=True))
    rep = c.get("/api/tours/a1/uhr-felder").json()
    assert _src(rep, "zepp_summary")["state"] == "ok" and _src(rep, "zepp_detail")["state"] == "fehler"


def test_garmin_tour_does_not_call_zepp(monkeypatch):
    c = _client()
    api = _use_api(monkeypatch, Api([_summary(T0)]))
    _tour("g1", T0, "garmin")
    d = c.post("/api/devices", json={"name": "Forerunner", "kind": "garmin"}).json()["id"]
    config.INBOX_DIR.mkdir(parents=True, exist_ok=True)
    (config.INBOX_DIR / "g.fit").write_bytes(make_fit(t0=T0))
    rep = c.get("/api/tours/g1/uhr-felder").json()
    assert _src(rep, "zepp_summary")["state"] == "nicht_zutreffend" and _src(rep, "fit")["state"] == "ok"
    dev = c.get(f"/api/devices/{d}/uhr-felder").json()
    assert _src(dev, "zepp_detail")["state"] == "nicht_zutreffend" and _src(dev, "fit")["tours_checked"] == 1
    assert api.details == 0                                                                        # Zepp wurde nie gefragt


# ---------------------------------------------------------------- Aggregation je Gerät
def test_device_aggregation_counts_tours_per_field(monkeypatch):
    c = _client()
    did = _dev(c)
    hist = []
    for i in range(4):
        st = T0 + i * 86400
        _tour(f"z{st + 10}", st + 10, "zepp")
        hist.append(_summary(st + 10, **({} if i != 1 else {"neues_feld": ""}), **({"nur_einmal": "5"} if i == 3 else {})))
    api = _use_api(monkeypatch, Api(hist, extra=False))
    rep = c.get(f"/api/devices/{did}/uhr-felder").json()
    assert rep["tours_total"] == 4 and rep["tours_checked"] == 4 and rep["limit"] == 10
    zs = _src(rep, "zepp_summary")
    assert zs["tours_checked"] == 4
    assert _by(zs, "calorie")["n_tours"] == 4 and _by(zs, "neues_feld")["n_tours"] == 3          # eine Tour liefert es leer
    assert _by(zs, "nur_einmal")["n_tours"] == 1                                                   # nicht überall vorhanden
    assert _by(zs, "calorie")["sample"] is None and _by(zs, "calorie")["min"] == 512
    zd = _src(rep, "zepp_detail")
    assert zd["tours_checked"] == 4 and _by(zd, "heart_rate[1]")["n_tours"] == 4 and "new_channel[1]" not in {f["name"] for f in zd["fields"]}
    assert _src(rep, "fit")["state"] == "keine_datei" and _src(rep, "fit")["tours_checked"] == 0
    assert api.details == 4


def test_device_limit_is_ten_newest_tours_and_ten_detail_calls(monkeypatch):
    c, did, tids, api = _world(monkeypatch, n=15)
    rep = c.get(f"/api/devices/{did}/uhr-felder").json()
    assert rep["tours_total"] == 15 and rep["tours_checked"] == 10 and api.details == 10 and rep["zepp_details"] == 10
    assert _src(rep, "zepp_detail")["tours_checked"] == 10
    # die neuesten 10: Details wurden für die letzten 10 Trainings abgerufen (kein Abruf für die 5 ältesten)
    got = []
    orig = api.detail
    api.detail = lambda s: (got.append(int(s["trackid"])), orig(s))[1]
    c.get(f"/api/devices/{did}/uhr-felder")
    assert sorted(got) == sorted(T0 + i * 86400 + 10 for i in range(5, 15))
    assert uhrdiag.MAX_TOURS == 10


def test_device_without_tours_explains(monkeypatch):
    c = _client()
    did = _dev(c)
    rep = c.get(f"/api/devices/{did}/uhr-felder").json()
    assert rep["tours_total"] == 0 and all(s["state"] == "keine_touren" and "noch keine Touren" in s["hint"] for s in rep["sources"])


# ---------------------------------------------------------------- FIT-Suche: Archive und Obergrenze
def test_fit_found_in_zip_and_search_is_capped(monkeypatch):
    c, did, tids, api = _world(monkeypatch)
    config.INBOX_DIR.mkdir(parents=True, exist_ok=True)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for i in range(5):
            z.writestr(f"x{i}.fit", make_fit(t0=T0 + 5000 + i * 4000))
        z.writestr("y.fit", make_fit(t0=T0 + 10))
    (config.INBOX_DIR / "export.zip").write_bytes(buf.getvalue())
    rep = c.get(f"/api/tours/{tids[0]}/uhr-felder").json()
    assert _src(rep, "fit")["state"] == "ok" and rep["fit_scanned"] == 6 and not rep["fit_truncated"]
    monkeypatch.setattr(uhrdiag, "MAX_FIT_FILES", 3)
    rep = c.get(f"/api/tours/{tids[0]}/uhr-felder").json()
    assert rep["fit_truncated"] is True and rep["fit_scanned"] == 3 and _src(rep, "fit")["state"] == "keine_datei"
    assert "keine FIT-Originaldatei" in _src(rep, "fit")["hint"].replace("Keine", "keine")


# ---------------------------------------------------------------- Rechte
def test_viewer_may_read_everything_but_nothing_else(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    _use_api(monkeypatch, Api([_summary(T0 + 10)]))
    _tour(f"z{T0 + 10}", T0 + 10)                                             # Altbestand: gehört nach der Einrichtung dem ersten Benutzer
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        did = _dev(c)
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        for u in (f"/api/devices/{did}/uhr-felder", f"/api/devices/{did}/uhr-felder.json", f"/api/devices/{did}/uhr-felder.json?download=1", f"/api/tours/z{T0 + 10}/uhr-felder"):
            assert v.get(u).status_code == 200, u
        assert v.post(f"/api/devices/{did}/uhr-felder").status_code in (403, 405) and v.delete(f"/api/devices/{did}/uhr-felder").status_code == 403
        assert TestClient(main.app).get(f"/api/devices/{did}/uhr-felder").status_code in (401, 403)           # ohne Anmeldung nicht
        assert TestClient(main.app).get(f"/api/devices/{did}/uhr-felder.json").status_code in (401, 403)


# ---------------------------------------------------------------- Export
def test_export_json_is_privacy_safe_and_downloadable(monkeypatch):
    c, did, tids, api = _world(monkeypatch, n=3)
    db.put("zepp_token", TOKEN)
    db.put("zepp_email", "geheim@example.com")
    config.INBOX_DIR.mkdir(parents=True, exist_ok=True)
    (config.INBOX_DIR / "a.fit").write_bytes(make_fit(t0=T0 + 10))
    for t in tids:
        _gpx(t)
        metrics.store(t, {"v": 1, "src": "zepp", "device": "Mein Geheimname", "t0": 0, "t": [0], "series": {"speed": [1.0] * 6}, "sum": {"kcal": 5}})
    r = c.get(f"/api/devices/{did}/uhr-felder.json?download=1")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"] and f"uhr-felder-{did}.json" in r.headers["content-disposition"]
    assert "content-disposition" not in c.get(f"/api/devices/{did}/uhr-felder.json").headers
    body = r.json()
    assert body["format"] == "meine-touren-uhr-felder" and body["geraet"] == {"art": "zepp", "modell": "Balance 2", "zepp_kennung": ""}
    assert body["touren_gesamt"] == 3 and body["touren_geprueft"] == 3 and [q["quelle"] for q in body["quellen"]] == ["zepp_summary", "zepp_detail", "fit", "gpx", "sidecar"]
    txt = r.text
    for bad in ("Geheimer Tourname", "Mein Geheimname", "Meine Balance 2", "Berlin", "ABC123", "48.1234", "4812340000", "123456789", TOKEN, "geheim@example.com", "z17", "47.5", "12.9", "sample",
                '"id"', "tour_id", "komoot"):
        assert bad not in txt, bad
    z = {f["name"]: f for q in body["quellen"] if q["quelle"] == "zepp_summary" for f in q["felder"]}
    assert z["calorie"]["n_tours"] == 3 and z["calorie"]["min"] == 512 and z["lat_start"]["hidden"] and z["lat_start"]["min"] is None
    fit = {f["name"]: f for q in body["quellen"] if q["quelle"] == "fit" for f in q["felder"]}
    assert fit["record.feld_226"]["min"] == 300 and fit["record.position_lat"]["min"] is None and fit["file_id.serial_number"]["min"] is None
    assert next(q for q in body["quellen"] if q["quelle"] == "fit")["touren_mit_daten"] == 1
    # Kennung nur, wenn sie wie eine Gerätekennung aussieht
    c.patch(f"/api/devices/{did}", json={"zsrc": "run.46.huami.com"})
    assert c.get(f"/api/devices/{did}/uhr-felder.json").json()["geraet"]["zepp_kennung"] == "run.46.huami.com"
    c.patch(f"/api/devices/{did}", json={"zsrc": "Max Mustermann <x@y.de>"})
    assert c.get(f"/api/devices/{did}/uhr-felder.json").json()["geraet"]["zepp_kennung"] == ""


def test_fit_private_messages_show_count_only():
    """user_profile (Nachricht 3: Gewicht, Größe …) liefert nie Werte, auch nicht bei unbekannten Feldern."""
    sc = {"fields": {(3, 1): {"n": 1, "vals": [72], "text": 0}, (3, 4): {"n": 1, "vals": [180], "text": 0}, (20, 3): {"n": 2, "vals": [100, 110], "text": 0}}, "starts": [], "bad": False}
    f = {x["name"]: x for x in uhrdiag._fit_fields(sc)}
    assert f["user_profile.feld_1"]["hidden"] and f["user_profile.feld_1"]["min"] is None and f["user_profile.feld_1"]["n"] == 1
    assert f["user_profile.feld_4"]["max"] is None and f["record.heart_rate"]["max"] == 110


def test_privacy_rule_for_names_and_big_numbers():
    h = uhrdiag._hide_range
    assert h("longitude_latitude[0]", 1, 2) and h("start_lat", 1, 2) and h("position_long", 1, 2) and h("device_serial", 1, 2) and h("user_id", 1, 2)
    assert h("x", 5.7e8, 5.8e8) and h("trackid", 1.7e9, 1.7e9)                                    # Halbkreise bzw. Unix-Zeit
    assert not h("calorie", 500, 900) and not h("relative_effort", 1, 2) and not h("dis", 3000, 25000) and not h("heart_rate[1]", 40, 190)
