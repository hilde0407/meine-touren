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
