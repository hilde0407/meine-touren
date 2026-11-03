"""GPS-Track korrigieren: Ausreißer entfernen, schnelle Abschnitte herausrechnen, Original wiederherstellen."""
import math, sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.test_core import fresh  # noqa: F401
from app import db, tracks, trackfix, routes  # noqa


def _gpx(spike=True, ride=True):
    t0 = datetime(2026, 7, 5, 6, 0, tzinfo=timezone.utc)
    pts = []
    lat, lon = 46.5, 10.0
    for i in range(600):
        lon += 0.00004 if not (ride and 300 <= i < 330) else 0.0012     # 4 km/h zu Fuß; Fahrt: ~100 km/h
        la = lat + (0.05 if spike and i in (100, 101) else 0)            # Sprung 5,5 km
        t = (t0 + timedelta(seconds=10 * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pts.append(f'<trkpt lat="{la:.6f}" lon="{lon:.6f}"><ele>{1500 + i}</ele><time>{t}</time></trkpt>')
    return '<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><type>hiking</type><trkseg>' + "".join(pts) + "</trkseg></trk></gpx>"


def test_analyse_apply_restore():
    t, _ = tracks.adopt(_gpx(), "alp.gpx", name="Alpen Tag 6")
    tid = t["id"]
    a = trackfix.analyse(tid)
    assert a["n_spikes"] == 2 and len(a["spikes"]) == 1
    assert len(a["fast"]) == 1 and a["fast"][0]["avg"] > 25 and 295 <= a["fast"][0]["i0"] <= 305
    d0 = db.one("SELECT dist_m,dur_s FROM tours WHERE id=?", (tid,))
    r = trackfix.apply(tid, True, [0])
    d1 = db.one("SELECT dist_m,dur_s FROM tours WHERE id=?", (tid,))
    assert d1["dist_m"] < d0["dist_m"] * 0.5            # Sprünge und Fahrt zählen nicht mehr
    assert d1["dur_s"] < d0["dur_s"]
    assert trackfix.analyse(tid)["fixed"] is True
    assert len(tracks.points_from_gpx(tracks.gpx_file(tid).read_text(encoding="utf-8"))) == 598
    assert trackfix.restore(tid)
    d2 = db.one("SELECT dist_m,dur_s FROM tours WHERE id=?", (tid,))
    assert abs(d2["dist_m"] - d0["dist_m"]) < 1 and d2["dur_s"] == d0["dur_s"]
    assert len(tracks.points_from_gpx(tracks.gpx_file(tid).read_text(encoding="utf-8"))) == 600


def test_clean_track_has_no_findings():
    t, _ = tracks.adopt(_gpx(False, False), "ok.gpx", name="Ruhig")
    a = trackfix.analyse(t["id"])
    assert a["n_spikes"] == 0 and a["fast"] == []


def test_api_hidden_tour_message():
    from fastapi.testclient import TestClient
    import app.more as more
    t, _ = tracks.adopt(_gpx(), "alp2.gpx", name="Versteckt")
    more.api_hide(t["id"], {"hide": True})
    try:
        more.api_trackfix(t["id"])
        assert False
    except Exception as e:
        assert getattr(e, "status_code", 0) == 409


def test_gps_jitter_is_reported_and_removed():
    import random
    random.seed(3)
    t0 = datetime(2026, 7, 6, 6, 0, tzinfo=timezone.utc)
    pts = []
    for i in range(500):
        t = (t0 + timedelta(seconds=5 * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pts.append(f'<trkpt lat="{46.5 + random.uniform(-0.00015, 0.00015):.6f}" lon="{10.0 + 0.00003 * i + random.uniform(-0.00015, 0.00015):.6f}"><ele>1500</ele><time>{t}</time></trkpt>')
    g = '<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><type>hiking</type><trkseg>' + "".join(pts) + "</trkseg></trk></gpx>"
    t, _ = tracks.adopt(g, "zit.gpx", name="Zittern")
    a = trackfix.analyse(t["id"])
    assert a["jitter_m"] > 0.5 * a["raw_m"]                     # fast die ganze „Strecke“ ist Rauschen
    d0 = db.one("SELECT dist_m FROM tours WHERE id=?", (t["id"],))["dist_m"]
    trackfix.apply(t["id"], True, [], True)
    assert db.one("SELECT dist_m FROM tours WHERE id=?", (t["id"],))["dist_m"] < d0 * 0.5
    assert len(a["fast"]) == 0 or all(f["m"] > 400 for f in a["fast"])


def test_uniform_timestamps_detected_and_duration_set():
    """Gleichmäßig verteilte (nicht aufgezeichnete) Zeitstempel: kein falscher „schneller Abschnitt“, Dauer lässt sich korrigieren."""
    t0 = datetime(2026, 7, 6, 5, 0, tzinfo=timezone.utc)
    pts = []
    for i in range(1000):                                   # 10 km/h exakt, 20 m Auf- und Abstieg je Kilometer
        t = (t0 + timedelta(seconds=3.6 * 0.1 * 36 * i / 36 * 10)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pts.append(f'<trkpt lat="{46.5:.6f}" lon="{10.0 + 0.0000144 * i * 10:.6f}"><ele>{1500 + 400 * math.sin(i / 80):.1f}</ele><time>{t}</time></trkpt>')
    g = '<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><type>hiking</type><trkseg>' + "".join(pts) + "</trkseg></trk></gpx>"
    t, _ = tracks.adopt(g, "plan.gpx", name="Geplant")
    tid = t["id"]
    a = trackfix.analyse(tid)
    assert a["timing"]["uniform"] and a["timing"]["est_s"] > a["dur_s"]
    assert a["fast"] == []
    r = trackfix.apply(tid, True, [], False, 6 * 3600)
    row = db.one("SELECT dur_s,end_ts,start_ts FROM tours WHERE id=?", (tid,))
    assert row["dur_s"] == 6 * 3600 and row["end_ts"] - row["start_ts"] == 6 * 3600
    pts2 = routes.load(tid)
    assert abs(pts2[-1][3] - 6 * 3600 * 1000) < 2000
    assert trackfix.restore(tid)
    row = db.one("SELECT dur_s,end_ts,start_ts FROM tours WHERE id=?", (tid,))
    assert row["dur_s"] != 6 * 3600 and row["end_ts"] - row["start_ts"] != 6 * 3600


def test_photos_offer_duration_and_start():
    t0 = datetime(2026, 7, 6, 5, 0, tzinfo=timezone.utc)
    pts = []
    for i in range(300):
        tt = (t0 + timedelta(seconds=12 * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pts.append(f'<trkpt lat="46.5" lon="{10.0 + 0.00014 * i:.6f}"><ele>1500</ele><time>{tt}</time></trkpt>')
    g = '<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><type>hiking</type><trkseg>' + "".join(pts) + "</trkseg></trk></gpx>"
    t, _ = tracks.adopt(g, "ph.gpx", name="Mit Fotos")
    st = db.one("SELECT start_ts FROM tours WHERE id=?", (t["id"],))["start_ts"]
    for j, off in enumerate((600, 7200, 30000)):
        db.execute("INSERT INTO photos(path,taken_ts,dated) VALUES(?,?,1)", (f"/x/e{j}.jpg", st + off))
    a = trackfix.analyse(t["id"])
    assert a["photos"] and a["photos"]["last"] - a["photos"]["first"] == 29400
    trackfix.apply(t["id"], True, [], False, 29400, a["photos"]["first"])
    row = db.one("SELECT start_ts,end_ts,dur_s FROM tours WHERE id=?", (t["id"],))
    assert row["start_ts"] == st + 600 and row["end_ts"] == st + 600 + 29400
    assert trackfix.restore(t["id"])
    assert db.one("SELECT start_ts FROM tours WHERE id=?", (t["id"],))["start_ts"] == st


def test_diagnose_in_implausible_list():
    from app import more
    t, _ = tracks.adopt(_gpx(), "d.gpx", name="Diag")
    d = trackfix.diagnose(t["id"])
    assert any("Ausreißer" in x for x in d) and any("Fahrt" in x for x in d)
    t2, _ = tracks.adopt(_gpx(False, False), "d2.gpx", name="Ruhig2")
    assert not any("Ausreißer" in x or "Fahrt" in x for x in trackfix.diagnose(t2["id"]))
    rows = more.implausible([dict(db.one("SELECT * FROM tours WHERE id=?", (t["id"],)))])
    assert rows == [] or "diag" in rows[0]


def test_photo_gps_anchors_set_track_time():
    t0 = datetime(2026, 7, 6, 5, 0, tzinfo=timezone.utc)
    pts = []
    for i in range(500):
        tt = (t0 + timedelta(seconds=4 * i)).strftime("%Y-%m-%dT%H:%M:%SZ")      # Track: nur 2000 s (erfundene Zeit)
        pts.append(f'<trkpt lat="46.5" lon="{10.0 + 0.0001 * i:.6f}"><ele>1500</ele><time>{tt}</time></trkpt>')
    g = '<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><type>hiking</type><trkseg>' + "".join(pts) + "</trkseg></trk></gpx>"
    t, _ = tracks.adopt(g, "anker.gpx", name="Anker")
    tid = t["id"]
    st = db.one("SELECT start_ts FROM tours WHERE id=?", (tid,))["start_ts"]
    # echte Zeiten: 1 h Pause in der Mitte -> Fotos bei 10 %, 40 %, 60 % (nach der Pause), 90 % der Strecke
    real = {50: 3600, 200: 5 * 3600, 300: 9 * 3600, 450: 11 * 3600}
    for i, (idx, off) in enumerate(real.items()):
        db.execute("INSERT INTO photos(path,taken_ts,lat,lng,dated,tour_id) VALUES(?,?,?,?,1,?)", (f"/x/a{i}.jpg", st + off, 46.5, 10.0 + 0.0001 * idx, tid))
    a = trackfix.analyse(tid)
    assert a["anchors"] and a["anchors"]["n"] == 4 and a["anchors"]["dur_s"] > 9 * 3600
    trackfix.apply(tid, True, [], False, None, None, True)
    row = db.one("SELECT start_ts,end_ts,dur_s FROM tours WHERE id=?", (tid,))
    assert row["dur_s"] > 9 * 3600 and row["start_ts"] < st + 3600
    pts2 = routes.load(tid)
    k = min(range(len(pts2)), key=lambda i: abs(pts2[i][1] - (10.0 + 0.0001 * 300)))
    assert abs(row["start_ts"] + pts2[k][3] / 1000 - (st + 9 * 3600)) < 300      # Foto-Position ↔ Fotozeit


def test_selftest_has_new_local_checks():
    from app import extras
    res = {r["name"]: r for r in extras.api_selftest()}
    for n in ("Datenbank-Integrität", "Schreibrechte der Ordner", "Foto-Dateien erreichbar", "HEIC-Unterstützung", "Auffällige Touren", "Update-Weg"):
        assert n in res, n
    assert res["Datenbank-Integrität"]["ok"] and res["Schreibrechte der Ordner"]["ok"], res
