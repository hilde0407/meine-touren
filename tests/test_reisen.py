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
    assert more2.api_trips() == []                                # Standard: 2 Tage sind noch keine Reise (mindestens 4)
    db.put("trip_min_days", "2")
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


def test_day_trips_excluded_and_hide(monkeypatch):
    """Ein Tag (auch mit mehreren Aufzeichnungen) ist keine Reise; Reisen lassen sich ausblenden und wiederherstellen."""
    from app import db, more2
    from app.gpxtools import TZ
    ts = lambda d, h=10: int(datetime.fromisoformat(f"{d}T{h:02d}:00:00").replace(tzinfo=TZ).timestamp())
    def add(i, d, h, lat, lng):
        db.execute("INSERT INTO tours(id,name,sport,start_ts,dist_m,up_m,dur_s,lat,lng) VALUES(?,?,?,?,?,?,?,?,?)", (i, i, "hike", ts(d, h), 10000, 300, 3600, lat, lng))
    for k in range(6):                                            # Zuhause (Münchner Raum), damit „weit weg“ erkannt wird
        add(f"h{k}", f"2026-03-{k + 1:02d}", 10, 48.1, 11.5)
    add("a1", "2026-06-10", 9, 28.0, -16.5); add("a2", "2026-06-10", 15, 28.0, -16.5)   # Tagesausflug mit zwei Aufzeichnungen
    add("b1", "2026-07-01", 9, 28.0, -16.5); add("b2", "2026-07-02", 9, 28.0, -16.5)    # echte Reise (2 Tage)
    monkeypatch.setattr(more2, "cover_photo", lambda ids: None)
    assert more2.api_trips() == []                                # Standard: 2 Tage sind noch keine Reise (mindestens 4)
    db.put("trip_min_days", "2")
    ids = [t["id"] for t in more2.build_trips()]
    assert "b1" in ids and "a1" not in ids
    more2.api_trip_hide("b1", {"hide": True})
    assert more2.api_trips() == [] and [t["id"] for t in more2.api_trips(hidden=1)] == ["b1"]
    more2.api_trip_hide("b1", {"hide": False})
    assert [t["id"] for t in more2.api_trips()] == ["b1"]
