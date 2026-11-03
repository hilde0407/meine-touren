"""Wie oft wurde dieselbe Strecke gegangen?"""
import math, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401


def _loop(day, lat0=28.12, lng0=-17.29, r=0.01, jitter=0.0, n=300):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / (n - 1)
        pts.append(f'<trkpt lat="{lat0 + r * math.sin(a) + jitter:.6f}" lon="{lng0 + r * (1 - math.cos(a)):.6f}"><ele>{1000 + 50 * math.sin(a):.0f}</ele><time>2026-{day}T08:{i * 12 // 3600 % 60:02d}:{i * 12 // 60 % 60:02d}:{i * 12 % 60:02d}Z</time></trkpt>')
    return f'<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><trkseg>{"".join(pts)}</trkseg></trk></gpx>'


def test_repeats_counts_same_route_only():
    from app import tracks, more
    for i, (day, kw) in enumerate((("03-01", {}), ("05-10", {"jitter": 0.0002}), ("08-02", {}), ("09-09", {"r": 0.02}), ("10-01", {"lat0": 29.5}))):
        tracks.adopt(_loop(day, **kw), f"r{i}.gpx", name=f"T{i}", ident=f"r{i}")
    rep = more.api_repeats()
    assert rep["r0"]["n"] == 3 and rep["r1"]["n"] == 3 and rep["r2"]["n"] == 3
    assert [x["id"] for x in rep["r2"]["with"]] == ["r0", "r1"]
    assert "r3" not in rep and "r4" not in rep                  # andere Größe bzw. anderer Ort: keine Wiederholung
