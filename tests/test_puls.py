"""Puls: Zepp-Dekodierung, GPX-Roundtrip, API."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import zepp, tracks, gpxtools, db  # noqa: E402


def _pts(n=40, hr=True):
    s = {"trackid": "1700000000"}
    ll = ";".join(["5000000000,800000000"] + ["100,100"] * (n - 1))
    d = {"longitude_latitude": ll, "time": ";".join(["0"] + ["10"] * (n - 1)), "altitude": ";".join(["10000"] * n),
         "heart_rate": ";".join(("0,100" if i == 0 else "10,1") for i in range(n)) if hr else "", "gait": ""}
    return s, zepp.decode_points(s, d)


def test_decode_has_hr():
    s, pts = _pts()
    assert all(len(p) == 5 for p in pts)
    assert pts[0][4] == 100 and pts[10][4] == 110
    s, pts = _pts(hr=False)
    assert all(p[4] is None for p in pts)


def test_hr_roundtrip_and_api():
    from fastapi.testclient import TestClient
    from app import main
    s, pts = _pts()
    g = zepp.points_to_gpx(s, pts, "hike")
    assert "gpxtpx:hr" in g
    tour, c = tracks.adopt(g, "z.gpx", ident="zt1")
    assert "gpxtpx:hr" in tracks.gpx_file("zt1").read_text()
    r = TestClient(main.app).get("/api/tours/zt1/hr").json()
    assert r["n"] >= 30 and r["max"] >= 130 and 100 <= r["avg"] <= 140 and sum(r["zones"]) > 0
    # Tour ohne Puls
    s, p2 = _pts(hr=False)
    tracks.adopt(zepp.points_to_gpx(s, p2, "hike"), "n.gpx", ident="zt2")
    assert TestClient(main.app).get("/api/tours/zt2/hr").json() == {"n": 0}


def test_merge_hr_backfill():
    s, pts = _pts(hr=False)
    tracks.adopt(zepp.points_to_gpx(s, pts, "hike"), "m.gpx", ident="zt3")
    f = tracks.gpx_file("zt3")
    assert "gpxtpx:hr" not in f.read_text()
    s2, pts2 = _pts()
    txt, n = tracks.merge_hr(f.read_text(), [(p[0], p[4]) for p in pts2 if p[4]])
    assert n >= 30 and "xmlns:gpxtpx" in txt
    f.write_text(txt)
    from fastapi.testclient import TestClient
    from app import main
    assert TestClient(main.app).get("/api/tours/zt3/hr").json()["n"] >= 30
    assert tracks.merge_hr(txt, [(p[0], 99) for p in pts2])[1] == 0         # vorhandener Puls bleibt


def test_backfill_matches_existing_tour_without_gpx(monkeypatch):
    """Eine Komoot-Tour (ohne lokales GPX) bekommt den Puls über das passende Zepp-Training."""
    from fastapi.testclient import TestClient
    from app import main, puls
    s, pts = _pts()
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,status,source) VALUES(?,?,?,?,?,?,?,?,?)",
               ("k99", "Komoot-Tour", "hike", 1700000030, 1700000400, 500.0, 370, "tour_recorded", "komoot"))
    det = {"longitude_latitude": ";".join(["5000000000,800000000"] + ["100,100"] * 39), "time": ";".join(["0"] + ["10"] * 39),
           "altitude": ";".join(["10000"] * 40), "heart_rate": ";".join(("0,100" if i == 0 else "10,1") for i in range(40)), "gait": ""}

    class Api:
        def history(self): return [{"trackid": "1700000000", "dis": "500", "run_time": "390"}]
        def detail(self, sm): return det
    puls.backfill_hr(Api())
    r = TestClient(main.app).get("/api/tours/k99/hr").json()
    assert r["n"] >= 30 and r["max"] > 120
    puls.backfill_hr(Api())                                   # zweiter Lauf: nichts mehr zu tun


def test_tour_list_flags_hr():
    from fastapi.testclient import TestClient
    from app import main
    s, pts = _pts()
    tracks.adopt(zepp.points_to_gpx(s, pts, "hike"), "h.gpx", ident="zt8")
    s2, p2 = _pts(hr=False)
    tracks.adopt(zepp.points_to_gpx(s2, p2, "hike"), "h2.gpx", ident="zt9")
    r = {t["id"]: t["has_hr"] for t in TestClient(main.app).get("/api/tours").json()}
    assert r["zt8"] is True and r["zt9"] is False


def test_hr_survives_trackfix_export_backup():
    import io, zipfile
    from fastapi.testclient import TestClient
    from app import main, trackfix, extras, sync
    c = TestClient(main.app)
    s, pts = _pts()
    tracks.adopt(zepp.points_to_gpx(s, pts, "hike"), "t.gpx", ident="zt20")
    # Spur-Korrektur schreibt das GPX neu – der Puls bleibt
    trackfix.apply("zt20", remove_spikes=True, smooth=True)
    assert "gpxtpx:hr" in tracks.gpx_file("zt20").read_text()
    assert c.get("/api/tours/zt20/hr").json()["n"] >= 30
    # Export enthält Zeit und Puls
    g = c.get("/api/tours/zt20/gpx").text
    assert "<time>" in g and "gpxtpx:hr" in g and "xmlns:gpxtpx" in g
    # Puls-Zusatzdatei (Komoot-Tour) kommt ins Backup und in den Export
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,status,source) VALUES(?,?,?,?,?,?,?,?,?)",
               ("k77", "K", "hike", 1700000000, 1700000400, 500.0, 400, "tour_recorded", "komoot"))
    from app import routes
    routes.store("k77", [(50 + i * 1e-5, 8 + i * 1e-5, 100.0, i * 10000) for i in range(40)])
    import json
    tracks.hr_sidecar("k77").write_text(json.dumps([[i * 10, 100 + i] for i in range(40)]))
    assert "gpxtpx:hr" in c.get("/api/tours/k77/gpx").text
    z = zipfile.ZipFile(io.BytesIO(extras.make_backup()[1]))
    assert "tracks/k77.hr.json" in z.namelist() and "tracks/zt20.gpx" in z.namelist()


def test_viewer_may_read_hr():
    from app import main
    assert main.VIEWER_GET.match("/api/tours/abc/hr") and not main.VIEWER_GET.match("/api/tours/abc/elev-fix")
