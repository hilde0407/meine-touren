"""Bewertung, Sicherheitsnotiz, Schneeangaben im Wetter."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401
from tests.test_wiederholung import _loop


def _tour():
    from app import tracks
    tracks.adopt(_loop("03-01"), "t.gpx", name="T", ident="t1")


def test_rating_and_safety():
    from app import more, main
    import pytest
    from fastapi import HTTPException
    _tour()
    more.api_rating("t1", {"stars": 4})
    assert [t for t in main.api_tours() if t["id"] == "t1"][0]["stars"] == 4
    more.api_rating("t1", {"stars": 0})
    assert [t for t in main.api_tours() if t["id"] == "t1"][0]["stars"] is None
    with pytest.raises(HTTPException):
        more.api_rating("t1", {"stars": 9})
    assert more.api_safety_get("t1")["set"] is False
    more.api_safety_set("t1", {"level": 3, "grp": "zu dritt", "gear": ["lvs", "sonde", "quatsch"], "note": "Triebschnee"})
    s = more.api_safety_get("t1")
    assert s["level"] == 3 and s["gear"] == ["lvs", "sonde"] and s["note"] == "Triebschnee"
    with pytest.raises(HTTPException):
        more.api_safety_set("t1", {"level": 7})
    more.api_safety_set("t1", {})
    assert more.api_safety_get("t1")["set"] is False


def test_weather_snow(monkeypatch):
    from app import extras, db
    import time
    _tour()
    t = db.one("SELECT * FROM tours WHERE id='t1'")
    t["start_ts"], t["end_ts"] = 1_700_000_000, 1_700_007_200
    times = [time.strftime("%Y-%m-%dT%H:00", time.gmtime(1_700_000_000 - 3600 * 80 + 3600 * i)) for i in range(100)]
    n = len(times)

    class R:
        status_code = 200
        def json(self):
            return {"hourly": {"time": times, "temperature_2m": [-5] * n, "precipitation": [0.1] * n, "weather_code": [73] * n, "wind_speed_10m": [12] * n,
                               "snowfall": [0.5] * n, "snow_depth": [0.4] * n}}
    monkeypatch.setattr(extras.requests, "get", lambda *a, **k: R())
    monkeypatch.setattr(extras, "TZ", __import__("datetime").timezone.utc)
    w = extras.fetch_weather(t)
    assert w["snow_depth"] == 40 and w["snow72"] > 0 and w["snowfall"] > 0 and w["tmin"] == -5
