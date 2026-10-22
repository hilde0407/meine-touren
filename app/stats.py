"""Kennzahlen wie im Home-Assistant-Komoot-Dashboard."""
from datetime import datetime

from . import db
from .gpxtools import TZ

SPORT_DE = {
    "hike": "Wandern", "touringbicycle": "Radtour", "e_touringbicycle": "E-Bike", "racebike": "Rennrad",
    "mtb": "MTB", "jogging": "Laufen", "skialpin": "Skifahren", "snowshoe": "Schneeschuh",
    "mountaineering": "Bergtour", "nordic": "Langlauf", "nordicwalking": "Nordic Walking", "skitour": "Skitour",
}


def local(ts):
    return datetime.fromtimestamp(ts, tz=TZ)


def compute(now=None):
    now = now or datetime.now(TZ)
    tours = [t for t in db.query("SELECT * FROM tours WHERE start_ts IS NOT NULL ORDER BY start_ts DESC")]
    y, m = now.year, now.month
    tot = {"count": len(tours), "km": sum(t["dist_m"] for t in tours) / 1000}
    this_year = [t for t in tours if local(t["start_ts"]).year == y]
    last_year = [t for t in tours if local(t["start_ts"]).year == y - 1]
    this_month = [t for t in this_year if local(t["start_ts"]).month == m]
    last = tours[0] if tours else None
    per_month = [0.0] * 12
    for t in this_year:
        per_month[local(t["start_ts"]).month - 1] += t["dist_m"] / 1000
    years = {}
    for t in tours:
        yy = local(t["start_ts"]).year
        a = years.setdefault(yy, {"year": yy, "count": 0, "km": 0.0, "up": 0.0, "hours": 0.0})
        a["count"] += 1; a["km"] += t["dist_m"] / 1000; a["up"] += t["up_m"] or 0; a["hours"] += (t["dur_s"] or 0) / 3600
    by_sport = {}
    for t in this_year:
        by_sport[t["sport"]] = by_sport.get(t["sport"], 0) + t["dist_m"] / 1000
    r = lambda v, n=1: round(v, n)
    return {
        "touren_gesamt": tot["count"], "strecke_gesamt": r(tot["km"]),
        "touren_dieses_jahr": len(this_year), "strecke_dieses_jahr": r(sum(t["dist_m"] for t in this_year) / 1000),
        "aufstieg_dieses_jahr": int(sum(t["up_m"] or 0 for t in this_year)),
        "dauer_dieses_jahr": r(sum(t["dur_s"] or 0 for t in this_year) / 3600, 2),
        "strecke_letztes_jahr": r(sum(t["dist_m"] for t in last_year) / 1000),
        "touren_diesen_monat": len(this_month), "strecke_diesen_monat": r(sum(t["dist_m"] for t in this_month) / 1000),
        "letzte_tour": {
            "id": last["id"], "name": last["name"], "sport": last["sport"],
            "sport_de": SPORT_DE.get(last["sport"], last["sport"]),
            "datum": local(last["start_ts"]).isoformat(), "km": r(last["dist_m"] / 1000, 2),
            "aufstieg": int(last["up_m"] or 0), "dauer_h": r((last["dur_s"] or 0) / 3600, 2),
        } if last else None,
        "monate_dieses_jahr": [r(v) for v in per_month],
        "jahre": sorted(years.values(), key=lambda a: a["year"], reverse=True),
        "sportarten_dieses_jahr": {k: r(v) for k, v in by_sport.items()},
    }
