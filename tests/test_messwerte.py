"""Messwerte der Aufzeichnungsgeräte (FIT/GPX/TCX/Zepp), Zusatzdatei, API, Backup – und „Meine Geräte“.
Alle Daten sind synthetisch bzw. nachgebaut (keine echten Geräte); die Spaltenformate der Zepp-Cloud sind aus dem Code abgeleitet."""
import io
import json
import struct
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import db, fitfile, metrics, mydevices, tracks, zepp  # noqa: E402

FIT_EPOCH = 631065600
T0 = 1750000000


def _deg(d):
    return int(d * 2 ** 31 / 180)


def make_fit(t0=T0, n=60, sport=1, manu=1, pname=b"Forerunner 255", channels=True, sub=0):
    """FIT mit file_id, Messwerten je Punkt (Puls, Kadenz, Tempo, Leistung, Temperatur, Atmung, Bodenkontakt, vert. Oszillation, Schrittlänge) und Session."""
    e = "<"
    body = b""
    fid = [(1, 2, 0x84), (2, 2, 0x84), (8, 16, 0x07)]
    body += bytes([0x40, 0, 0]) + struct.pack(e + "H", 0) + bytes([len(fid)]) + b"".join(bytes(f) for f in fid)
    body += bytes([0]) + struct.pack(e + "HH", manu, 3990) + pname.ljust(16, b"\0")
    f = [(253, 4, 0x86), (0, 4, 0x85), (1, 4, 0x85), (2, 2, 0x84), (3, 1, 0x02)]
    if channels:
        f += [(4, 1, 0x02), (6, 2, 0x84), (7, 2, 0x84), (13, 1, 0x01), (99, 1, 0x02), (41, 2, 0x84), (39, 2, 0x84), (85, 2, 0x84)]
    body += bytes([0x41, 0, 0]) + struct.pack(e + "H", 20) + bytes([len(f)]) + b"".join(bytes(x) for x in f)
    ts0 = t0 - FIT_EPOCH
    for i in range(n):
        row = struct.pack(e + "IiiHB", ts0 + i * 5, _deg(47.5 + i * 0.0003), _deg(12.9 + i * 0.0004), int((1200 + i * 2) * 5 + 2500), 120 + i % 30)
        if channels:
            temp = 0x7F if i % 10 == 0 else (-2 & 0xFF if i % 2 else 3)          # 0x7F = ungültig
            row += struct.pack(e + "BHHBBHHH", 80 + i % 8, 2500 + i * 10, 150 + i % 5, temp, 16, 2700 + i, 1050, 12000)
        body += bytes([1]) + row
    body += bytes([0x42, 0, 0]) + struct.pack(e + "H", 18) + bytes([4, 5, 1, 0, 6, 1, 0, 11, 2, 0x84, 24, 1, 2]) + bytes([2]) + bytes([sport, sub]) + struct.pack(e + "H", 612) + bytes([34])
    head = struct.pack("<BBHI4s", 14, 0x20, 2100, len(body), b".FIT") + b"\x00\x00"
    return head + body + b"\x00\x00"


def test_fit_channels_into_gpx_and_sidecar():
    gpx, sp = fitfile.to_gpx(make_fit(), "lauf")
    assert sp == "jogging" and "<gpxtpx:cad>" in gpx and "<mt:power>" in gpx and 'src="garmin"' in gpx
    t, c = tracks.adopt(gpx, "lauf.gpx", ident="m1")
    d = metrics.load("m1")
    assert d["src"] == "garmin" and d["device"] == "Forerunner 255" and d["t0"] == c["start_ts"]
    s = d["series"]
    assert {"speed", "cad", "pow", "temp", "resp", "gct", "vosc", "stride", "press"} - set(s) == {"press"}   # Luftdruck nicht geliefert -> fehlt
    assert len(d["t"]) <= 600 and all(len(v) == len(d["t"]) for v in s.values())
    assert 150 <= d["stat"]["cad"]["avg"] <= 180                       # Laufen: Schritte beider Beine (2 x Schläge je Bein)
    assert abs(d["stat"]["speed"]["avg"] - 2.7 * 3.6) < 2.5            # m/s -> km/h
    assert -2.1 <= d["stat"]["temp"]["min"] and d["stat"]["temp"]["max"] <= 3.1   # ungültige Temperatur (0x7F) wurde verworfen
    assert d["sum"]["kcal"] == 612 and abs(d["sum"]["te"] - 3.4) < 0.01
    assert d["stat"]["stride"]["avg"] == 1.2 and 270 <= d["stat"]["gct"]["avg"] <= 330 and d["stat"]["vosc"]["avg"] == 105


def test_fit_without_channels_has_only_header():
    gpx, _ = fitfile.to_gpx(make_fit(channels=False, manu=123, pname=b""))
    assert "mt:power" not in gpx and 'src="polar"' in gpx
    tracks.adopt(gpx, "p.gpx", ident="m2")
    d = metrics.load("m2")
    assert d["src"] == "polar" and d["device"] == "Polar" and d["series"] == {}
    from fastapi.testclient import TestClient
    from app import main
    r = TestClient(main.app).get("/api/tours/m2/metrics").json()
    assert "pow" not in r["channels"] and "cad" not in r["channels"]    # was das Gerät nicht liefert, erscheint nicht


def test_gpx_extensions_and_placeholders():
    pts = ""
    for i in range(30):
        cad = 0 if i < 5 else 85            # 0 = nicht gemessen
        pw = "-20000" if i == 3 else 150 + i
        pts += (f'<trkpt lat="{47.5 + i * 0.0003}" lon="12.9"><ele>1000</ele><time>2025-06-15T08:{i // 2:02d}:{(i % 2) * 30:02d}Z</time>'
                f'<extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>130</gpxtpx:hr><gpxtpx:cad>{cad}</gpxtpx:cad><gpxtpx:atemp>0</gpxtpx:atemp></gpxtpx:TrackPointExtension>'
                f'<power>{pw}</power></extensions></trkpt>\n')
    g = ('<?xml version="1.0"?><gpx version="1.1" creator="Garmin Edge 530" xmlns="http://www.topografix.com/GPX/1/1" '
         'xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1"><trk><type>cycling</type><trkseg>' + pts + '</trkseg></trk></gpx>')
    tracks.adopt(g, "r.gpx", ident="m3")
    d = metrics.load("m3")
    assert d["src"] == "garmin" and d["device"] == "Garmin Edge 530"
    assert d["stat"]["temp"]["avg"] == 0.0                              # 0 °C ist ein echter Wert
    assert d["stat"]["cad"]["min"] == 85                                # Kadenz 0 verworfen
    assert d["stat"]["pow"]["min"] >= 150                               # Platzhalter -20000 verworfen
    assert "speed" not in d["series"]


def test_tcx_channels():
    tp = "".join(f'<Trackpoint><Time>2025-06-15T08:{i // 2:02d}:{(i % 2) * 30:02d}Z</Time><Position><LatitudeDegrees>47.5{i:03d}</LatitudeDegrees><LongitudeDegrees>12.9</LongitudeDegrees></Position>'
                 f'<HeartRateBpm><Value>120</Value></HeartRateBpm><Cadence>{70 + i % 5}</Cadence><Extensions><TPX><Speed>6.5</Speed><Watts>{200 + i}</Watts></TPX></Extensions></Trackpoint>' for i in range(30))
    x = f'<TrainingCenterDatabase><Activities><Activity Sport="Biking"><Creator><Name>Polar Vantage V2</Name></Creator><Lap><Track>{tp}</Track></Lap></Activity></Activities></TrainingCenterDatabase>'
    r = metrics.parse(x, "a.tcx")
    assert r["src"] == "polar" and r["device"] == "Polar Vantage V2" and len(r["samples"]) == 30
    d = metrics.build(r["samples"], int(r["samples"][0][0]), "polar", r["device"])
    assert set(d["series"]) == {"cad", "speed", "pow"} and abs(d["stat"]["speed"]["avg"] - 23.4) < 0.1


def test_condense_to_600():
    smp = [(T0 + i, {"speed": 5 + (i % 7), "temp": 4.5}) for i in range(5000)]
    d = metrics.build(smp, T0, "garmin")
    assert 100 < len(d["t"]) <= 600 and len(d["series"]["speed"]) == len(d["t"]) and d["t"] == sorted(d["t"])
    assert metrics.build([(T0, {"speed": 5})], T0, "garmin")["series"] == {}      # zu wenig Werte


def test_sidecar_never_overwritten():
    smp = [(T0 + i * 5, {"pow": 100 + i}) for i in range(20)]
    d = metrics.build(smp, T0, "garmin", "Fenix")
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,status,source) VALUES('x1','X','hike',?,?,1000,100,'t','local')", (T0, T0 + 100))
    assert metrics.store("x1", d) is True
    d2 = metrics.build([(T0 + i * 5, {"pow": 7}) for i in range(20)], T0, "polar", "Anderes")
    assert metrics.store("x1", d2) is False and metrics.load("x1")["device"] == "Fenix"
    assert metrics.store("x1", d2, force=True) is True


def _zepp_detail(n=60, speed_unit=10, gait=True):
    """Zepp-Detail wie in test_puls: 10 s Takt, ca. 14 m je Schritt der Koordinaten (ca. 1,4 m/s)."""
    ll = ";".join(["5000000000,800000000"] + ["0,128"] * (n - 1))        # 128 E-8 Grad = ca. 14 m Ost je 10 s (bei 50° Breite: 0,0000128° = 0,9 m ...)
    return {"longitude_latitude": ll, "time": ";".join(["0"] + ["10"] * (n - 1)), "altitude": ";".join(["10000"] * n),
            "heart_rate": "", "gait": "", "speed": ";".join(["0"] + [f"10,{14 * speed_unit // 10}"] * (n - 1))}


def test_zepp_samples_plausibility_gate():
    s = {"trackid": str(T0), "calorie": "351"}
    # Strecke: 0,0002° Breite je 10 s = 22 m / 10 s = 2,2 m/s
    n = 60
    ll = ";".join(["5000000000,800000000"] + ["20000,0"] * (n - 1))
    det = {"longitude_latitude": ll, "time": ";".join(["0"] + ["10"] * (n - 1)), "altitude": ";".join(["10000"] * n), "heart_rate": "", "gait": ""}
    pts = zepp.decode_points(s, det)
    det["speed"] = ";".join(["0"] + ["10,22"] * (n - 1))               # 22 in 0,1 m/s = 2,2 m/s: passt
    smp, sm = metrics.zepp_samples(s, det, pts)
    assert sm == {"kcal": 351} and smp and abs(smp[5][1]["speed"] - 2.2 * 3.6) < 0.3
    det["speed"] = ";".join(["0"] + ["10,9000"] * (n - 1))             # unplausibel: wird verworfen
    assert metrics.zepp_samples(s, det, pts)[0] == []
    det["speed"] = ""
    det["gait"] = ";".join(["0,0,0"] + ["10,95,140"] * (n - 1))        # Schrittlänge 95 cm x 140 Schritte/min = 2,2 m/s: passt
    smp, _ = metrics.zepp_samples(s, det, pts)
    assert smp and abs(smp[5][1]["stride"] - 0.95) < 0.01 and smp[5][1]["cad"] == 140
    det["gait"] = ";".join(["0,0,0"] + ["10,95,40"] * (n - 1))         # passt nicht zur GPS-Geschwindigkeit
    assert metrics.zepp_samples(s, det, pts)[0] == []
    det["gait"] = "kaputt;;;1,x"
    assert metrics.zepp_samples(s, det, pts)[0] == []                   # defensiv: kein Fehler


def test_zepp_backfill_and_idempotent():
    s = {"trackid": str(T0)}
    n = 60
    ll = ";".join(["5000000000,800000000"] + ["20000,0"] * (n - 1))
    det = {"longitude_latitude": ll, "time": ";".join(["0"] + ["10"] * (n - 1)), "altitude": ";".join(["10000"] * n), "heart_rate": "",
           "gait": ";".join(["0,0,0"] + ["10,95,140"] * (n - 1))}
    pts = zepp.decode_points(s, det)
    tracks.adopt(zepp.points_to_gpx(s, pts, "hike"), "z.gpx", ident=f"z{T0}", src="zepp")
    assert metrics.load(f"z{T0}")["series"] == {}                       # nur Kopfdaten (Quelle zepp)
    calls = []

    class Api:
        def history(self): return [{"trackid": str(T0), "dis": "1300", "run_time": "590", "calorie": "100"}]
        def detail(self, sm): calls.append(1); return det
    metrics.backfill(Api())
    d = metrics.load(f"z{T0}")
    assert d["src"] == "zepp" and "cad" in d["series"] and d["sum"]["kcal"] == 100
    metrics.backfill(Api())
    assert len(calls) == 1                                              # zweiter Lauf: nichts zu tun


def test_backfill_from_original_files(tmp_path):
    from app import config
    gpx, _ = fitfile.to_gpx(make_fit(channels=False), "a")             # Tour wurde ohne Messwerte gespeichert (Altbestand)
    tracks.adopt(gpx, "a.gpx", ident="old1")
    (config.INBOX_DIR).mkdir(parents=True, exist_ok=True)
    (config.INBOX_DIR / "original.fit").write_bytes(make_fit(channels=True))
    assert not metrics.has_series(metrics.load("old1"))
    metrics.backfill()
    assert "cad" in metrics.load("old1")["series"]
    first = (config.TRACK_DIR / "old1.met.json").read_bytes()
    metrics.backfill()
    assert (config.TRACK_DIR / "old1.met.json").read_bytes() == first


def test_api_metrics_derived_speed_and_pace():
    from fastapi.testclient import TestClient
    from app import main
    pts = "".join(f'<trkpt lat="{47.5 + i * 0.0002}" lon="12.9"><ele>1000</ele><time>2025-06-15T08:{i // 6:02d}:{(i % 6) * 10:02d}Z</time></trkpt>' for i in range(60))
    g = f'<gpx version="1.1" creator="Strava" xmlns="http://www.topografix.com/GPX/1/1"><trk><type>hiking</type><trkseg>{pts}</trkseg></trk></gpx>'
    tracks.adopt(g, "s.gpx", ident="m5")
    r = TestClient(main.app).get("/api/tours/m5/metrics").json()
    sp = r["channels"]["speed"]
    assert sp["derived"] is True and 6 < sp["avg"] < 9 and r["src"] == "other"           # 22 m / 10 s = 7,9 km/h
    assert r["channels"]["pace"]["derived"] is True and 6 < r["channels"]["pace"]["avg"] < 10
    assert set(r["channels"]) == {"speed", "pace"}
    assert TestClient(main.app).get("/api/tours/gibtsnicht/metrics").status_code == 404


def test_api_metrics_device_channels_not_derived():
    from fastapi.testclient import TestClient
    from app import main
    tracks.adopt(fitfile.to_gpx(make_fit(), "l")[0], "l.gpx", ident="m6")
    r = TestClient(main.app).get("/api/tours/m6/metrics").json()
    assert r["source"] == "Forerunner 255" and r["src"] == "garmin"
    assert r["channels"]["speed"]["derived"] is False and r["channels"]["cad"]["label"] in ("Schrittfrequenz", "Trittfrequenz")
    assert r["channels"]["cad"]["label"] == "Schrittfrequenz" and r["sum"]["kcal"] == 612
    assert r["channels"]["stride"]["derived"] is False


def test_backup_and_umzug_contain_met_json(tmp_path):
    from app import extras, umzug, config
    tracks.adopt(fitfile.to_gpx(make_fit(), "l")[0], "l.gpx", ident="m7")
    z = zipfile.ZipFile(io.BytesIO(extras.make_backup()[1]))
    assert "tracks/m7.met.json" in z.namelist()
    out = umzug.make(config.DATA_DIR, tmp_path / "out", "t")
    names = zipfile.ZipFile(out).namelist()
    assert any(n.endswith("tracks/m7.met.json") for n in names)


def test_delete_local_removes_sidecar():
    t, _ = tracks.adopt(fitfile.to_gpx(make_fit(), "l")[0], "l.gpx", ident="m8")
    assert metrics.sidecar("m8").exists()
    tracks.delete_local("m8")
    assert not metrics.sidecar("m8").exists() and not db.one("SELECT 1 FROM tour_source WHERE tour_id='m8'")


# ------------------------------------------------------------------------------------------------ Meine Geräte
def _tour(tid, ts, src):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,status,source) VALUES(?,?,?,?,?,1000,100,'t','local')", (tid, tid, "hike", ts, ts + 100))
    db.execute("INSERT OR REPLACE INTO tour_source(tour_id,src,name) VALUES(?,?,?)", (tid, src, ""))


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def test_devices_auto_assignment_by_date_two_watches():
    c = _client()
    old = c.post("/api/devices", json={"name": "Amazfit alt", "kind": "zepp", "until": "2025-03-31"}).json()["id"]
    new = c.post("/api/devices", json={"name": "Amazfit Balance 2", "kind": "zepp", "since": "2025-04-01"}).json()["id"]
    _tour("a1", 1735689600, "zepp")      # 2025-01-01
    _tour("a2", 1750000000, "zepp")      # 2025-06-15
    _tour("a3", 1750000000, "garmin")
    assert mydevices.device_of("a1")["name"] == "Amazfit alt" and mydevices.device_of("a2")["name"] == "Amazfit Balance 2"
    assert mydevices.device_of("a3") is None                                   # keine Garmin-Uhr angelegt
    devs = {d["id"]: d for d in c.get("/api/devices").json()["devices"]}       # GET /api/devices liefert zusätzlich die Geräteliste
    assert devs[old]["n"] == 1 and devs[new]["n"] == 1
    assert {t["id"]: t["dev"] for t in c.get("/api/tours").json()}["a2"] == "Amazfit Balance 2"


def test_devices_manual_wins_and_auto_again():
    c = _client()
    a = c.post("/api/devices", json={"name": "A", "kind": "zepp", "until": "2025-03-31"}).json()["id"]
    b = c.post("/api/devices", json={"name": "B", "kind": "zepp", "since": "2025-04-01"}).json()["id"]
    _tour("b1", 1750000000, "zepp")
    assert mydevices.device_of("b1")["id"] == b
    r = c.post("/api/tours/b1/device", json={"device_id": a}).json()
    assert r["device"]["id"] == a and r["device"]["manual"] is True
    assert mydevices.device_of("b1")["id"] == a
    assert c.post("/api/tours/b1/device", json={"auto": True}).json()["device"]["id"] == b
    assert c.post("/api/tours/nix/device", json={"device_id": a}).status_code == 404
    assert c.post("/api/tours/b1/device", json={"device_id": 999}).status_code == 404
    # Sammelaktion
    _tour("b2", 1735689600, "garmin"); _tour("b3", 1750000000, "garmin")
    n = c.post("/api/devices/assign-range", json={"device_id": a, "from": "2025-01-01", "to": "2025-02-01"}).json()["n"]
    assert n == 1 and mydevices.device_of("b2")["id"] == a and mydevices.device_of("b3") is None


def test_devices_delete_refused_with_tours_then_move():
    c = _client()
    a = c.post("/api/devices", json={"name": "Alt", "kind": "zepp"}).json()["id"]
    b = c.post("/api/devices", json={"name": "Neu", "kind": "other"}).json()["id"]
    _tour("c1", T0, "zepp")
    r = c.delete(f"/api/devices/{a}")
    assert r.status_code == 409 and "umhängen" in r.json()["detail"]
    assert c.delete(f"/api/devices/{a}?move_to={a}").status_code == 400
    assert c.delete(f"/api/devices/{a}?move_to={b}").json()["moved"] == 1
    assert mydevices.device_of("c1")["id"] == b                                 # Tour behält ein Gerät
    assert c.delete(f"/api/devices/{b}").status_code == 409
    assert c.delete(f"/api/devices/{b}?move_to=0").status_code == 409
    c.post("/api/tours/c1/device", json={"auto": True})
    assert c.delete(f"/api/devices/{b}").status_code == 200


def test_devices_empty_delete_and_validation():
    c = _client()
    d = c.post("/api/devices", json={"name": "Leer", "kind": "phone"}).json()["id"]
    assert c.delete(f"/api/devices/{d}").json()["ok"] is True
    assert c.post("/api/devices", json={"name": " ", "kind": "zepp"}).status_code == 400
    assert c.post("/api/devices", json={"name": "x", "kind": "toaster"}).status_code == 400
    assert c.post("/api/devices", json={"name": "x", "kind": "zepp", "since": "01.02.2025"}).status_code == 400
    assert c.post("/api/devices", json={"name": "x", "kind": "zepp", "since": "2025-05-01", "until": "2025-04-01"}).status_code == 400
    assert c.patch("/api/devices/999", json={"name": "y"}).status_code == 404


def test_devices_rename_shows_in_tour_api_and_deactivate_keeps_name():
    c = _client()
    d = c.post("/api/devices", json={"name": "Uhr 1", "kind": "zepp"}).json()["id"]
    tracks.adopt(zepp.points_to_gpx({"trackid": str(T0)}, zepp.decode_points({"trackid": str(T0)}, {"longitude_latitude": ";".join(["5000000000,800000000"] + ["20000,0"] * 29),
                 "time": ";".join(["0"] + ["10"] * 29), "altitude": ";".join(["10000"] * 30), "heart_rate": "", "gait": ""}), "hike"), "z.gpx", ident=f"z{T0}", src="zepp")
    tid = f"z{T0}"
    assert c.get(f"/api/tours/{tid}/metrics").json()["device"]["name"] == "Uhr 1"
    assert c.patch(f"/api/devices/{d}", json={"name": "Amazfit Balance 2", "model": "Balance 2"}).json()["ok"]
    r = c.get(f"/api/tours/{tid}/metrics").json()["device"]
    assert r["name"] == "Amazfit Balance 2" and r["active"] is True
    c.patch(f"/api/devices/{d}", json={"active": False})
    r = c.get(f"/api/tours/{tid}/metrics").json()["device"]
    assert r["name"] == "Amazfit Balance 2" and r["active"] is False              # Touren behalten den Namen
    assert c.patch(f"/api/devices/{d}", json={"until": "2020-01-01", "since": "2021-01-01"}).status_code == 400


def test_device_suggestions_create_nothing():
    c = _client()
    _tour("s1", T0, "zepp"); _tour("s2", T0 + 5, "zepp"); _tour("s3", T0 + 9, "polar")
    r = c.get("/api/devices/suggestions").json()
    assert {x["kind"]: x["n"] for x in r} == {"zepp": 2, "polar": 1}
    assert c.get("/api/my-devices").json()["devices"] == []
    c.post("/api/devices", json={"name": "Z", "kind": "zepp"})
    assert [x["kind"] for x in c.get("/api/devices/suggestions").json()] == ["polar"]


def test_devices_in_backup_database(tmp_path):
    """Die Tabellen devices/tour_device/tour_source liegen in der Datenbank und damit in Sicherung und Umzugspaket."""
    import sqlite3
    from app import extras
    c = _client()
    d = c.post("/api/devices", json={"name": "Sicherungstest", "kind": "garmin"}).json()["id"]
    _tour("d1", T0, "garmin")
    c.post("/api/tours/d1/device", json={"device_id": d})
    z = zipfile.ZipFile(io.BytesIO(extras.make_backup()[1]))
    (tmp_path / "b.sqlite").write_bytes(z.read("komoot_hub.sqlite"))
    con = sqlite3.connect(tmp_path / "b.sqlite")
    assert con.execute("SELECT name FROM devices").fetchone()[0] == "Sicherungstest"
    assert con.execute("SELECT device_id FROM tour_device WHERE tour_id='d1'").fetchone()[0] == d
    assert con.execute("SELECT src FROM tour_source WHERE tour_id='d1'").fetchone()[0] == "garmin"
