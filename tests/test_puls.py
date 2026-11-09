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
         "heart_rate": ";".join(f"{10 if i else 0},{100 + i}" for i in range(n)) if hr else "", "gait": ""}
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
