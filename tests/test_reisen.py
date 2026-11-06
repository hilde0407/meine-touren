"""Reisen: Name und Zeitraum ändern."""
import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401


def test_trip_edit(monkeypatch):
    from app import db, more2
    from app.gpxtools import TZ
    import pytest
    from fastapi import HTTPException
    ts = lambda d: int(datetime.fromisoformat(d + "T10:00:00").replace(tzinfo=TZ).timestamp())
    for i, d in enumerate(["2026-05-01", "2026-05-02", "2026-05-03", "2026-05-04"]):
        db.execute("INSERT INTO tours(id,name,sport,start_ts,dist_m,up_m,dur_s,lat,lng) VALUES(?,?,?,?,?,?,?,?,?)", (f"t{i}", f"T{i}", "hike", ts(d), 10000, 500, 3600, 28.0, -16.5))
    auto = {"id": "t0", "region": "Teneriffa", "country": "Spanien", "start": "2026-05-01", "end": "2026-05-02", "days": 2, "tours": ["t0", "t1"], "km": 20.0, "up_m": 1000, "h": 2.0}
    monkeypatch.setattr(more2, "build_trips", lambda: [dict(auto)])
    monkeypatch.setattr(more2, "cover_photo", lambda ids: None)
    assert more2.api_trips()[0]["region"] == "Teneriffa"
    more2.api_trip_edit("t0", {"name": "Kanaren 2026", "start": "2026-05-01", "end": "2026-05-04"})
    t = more2.api_trips()[0]
    assert t["region"] == "Kanaren 2026" and t["end"] == "2026-05-04" and t["tours"] == ["t0", "t1", "t2", "t3"] and t["km"] == 40.0 and t["days"] == 4 and t["edited"]
    assert t["auto_region"] == "Teneriffa"
    more2.api_trip_edit("t0", {"name": "Nur Name"})
    t = more2.api_trips()[0]
    assert t["region"] == "Nur Name" and t["end"] == "2026-05-02" and len(t["tours"]) == 2
    with pytest.raises(HTTPException):
        more2.api_trip_edit("t0", {"start": "2026-05-05", "end": "2026-05-01"})
    with pytest.raises(HTTPException):
        more2.api_trip_edit("t0", {"start": "kaputt"})
    with pytest.raises(HTTPException):
        more2.api_trip_edit("nix", {"name": "x"})
    more2.api_trip_edit("t0", {})
    assert not more2.api_trips()[0].get("edited") and more2.api_trips()[0]["region"] == "Teneriffa"
