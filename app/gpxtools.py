"""TCX/GPX -> sauberes GPX (nur GPS-Punkte). Python-Port von conv.pl."""
import math
import re
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from . import config

TZ = ZoneInfo(config.TZ_NAME)

# Zepp-Sporttyp -> Komoot-Sportart
ZEPP_SPORT = {
    1: "hike", 6: "hike", 7: "hike", 9: "touringbicycle", 13: "hike", 22: "hike",
    43: "skialpin", 105: "skialpin", 178: "snowshoe", 206: "e_touringbicycle",
}
ALIAS = {
    "cycling": "touringbicycle", "running": "hike", "walking": "hike", "hiking": "hike",
    "type_1": "hike", "type_6": "hike", "type_7": "hike", "type_9": "touringbicycle",
    "type_13": "hike", "type_22": "hike", "type_43": "skialpin", "type_105": "skialpin",
    "type_178": "snowshoe", "type_206": "e_touringbicycle",
}
LABEL = {
    "hike": "Wanderung", "mountaineering": "Bergtour", "jogging": "Lauf",
    "touringbicycle": "Radtour", "e_touringbicycle": "E-Bike-Tour", "racebike": "Rennradtour",
    "mtb": "MTB-Tour", "skialpin": "Skifahren", "skitour": "Skitour",
    "snowshoe": "Schneeschuhwandern", "nordic": "Langlauf", "nordicwalking": "Nordic Walking",
}


class NoGps(Exception):
    pass


def parse_time(t):
    t = re.sub(r"\.\d+", "", t.strip())
    if not re.search(r"(Z|[+-]\d\d:?\d\d)$", t):
        t += "Z"
    t = t.replace("Z", "+00:00")
    return datetime.fromisoformat(t).astimezone(timezone.utc)


def _points_gpx(text):
    typ, pts = _points_gpx_hr(text)
    return typ, [p[:4] for p in pts]


def _hr_ok(v):
    try:
        v = int(float(v))
    except (TypeError, ValueError):
        return None
    return v if 30 <= v <= 240 else None


def _points_gpx_hr(text):
    """Wie _points_gpx, aber mit Puls als fünftem Wert (None, wenn nicht vorhanden)."""
    head = re.sub(r"<trkpt\b.*", "", text, flags=re.S)
    m = re.search(r"<type>([^<]*)</type>", head)
    typ = m.group(1) if m else ""
    pts = []
    for m in re.finditer(r"<trkpt\b([^>]*)>(.*?)</trkpt>", text, flags=re.S):
        attr, inner = m.group(1), m.group(2)
        lat = re.search(r"lat\s*=\s*[\"']([^\"']+)[\"']", attr)
        lon = re.search(r"lon\s*=\s*[\"']([^\"']+)[\"']", attr)
        ele = re.search(r"<ele>([^<]*)</ele>", inner)
        t = re.search(r"<time>([^<]*)</time>", inner)
        if lat and lon and t:
            hr = re.search(r"<(?:\w+:)?hr>\s*([^<\s]*)\s*</(?:\w+:)?hr>", inner)
            pts.append((float(lat.group(1)), float(lon.group(1)), ele.group(1) if ele else "", t.group(1), _hr_ok(hr.group(1)) if hr else None))
    return typ, pts


def _points_tcx(text):
    pts = []
    for m in re.finditer(r"<Trackpoint>(.*?)</Trackpoint>", text, flags=re.S):
        b = m.group(1)
        g = lambda tag: (re.search(rf"<{tag}>([^<]*)<", b) or [None, ""])[1]
        lat, lon, ele, t = g("LatitudeDegrees"), g("LongitudeDegrees"), g("AltitudeMeters"), g("Time")
        hr = re.search(r"<HeartRateBpm[^>]*>\s*<Value>([^<]*)<", b)
        if lat and lon and t:
            pts.append((float(lat), float(lon), ele, t, _hr_ok(hr.group(1)) if hr else None))
    return "", pts


def convert(text, filename="", default_sport="hike"):
    """Gibt dict(gpx, name, sport, start_ts, end_ts, dist_m, n) zurück."""
    if filename.lower().endswith(".gpx") or "<gpx" in text[:2000]:
        typ, raw = _points_gpx_hr(text)
    else:
        typ, raw = _points_tcx(text)
    pts = [(la, lo, el, parse_time(t), hr) for la, lo, el, t, hr in raw if not (la == 0 and lo == 0)]
    if not pts:
        raise NoGps("Keine GPS-Punkte")
    dist = 0.0
    for a, b in zip(pts, pts[1:]):
        dx = (b[1] - a[1]) * 111320 * math.cos(math.radians(b[0]))
        dy = (b[0] - a[0]) * 110540
        dist += math.hypot(dx, dy)
    typ = ALIAS.get(typ, typ)
    sport = typ if typ in LABEL else (default_sport if default_sport in LABEL else "hike")
    start, end = pts[0][3], pts[-1][3]
    name = f"{LABEL.get(sport, 'Tour')} {start.astimezone(TZ).strftime('%d.%m.%Y %H:%M')}"
    f = lambda d: d.strftime("%Y-%m-%dT%H:%M:%SZ")
    body = "".join(
        f'<trkpt lat="{la}" lon="{lo}">' + (f"<ele>{el}</ele>" if el != "" else "") + f"<time>{f(t)}</time>"
        + (f"<extensions><gpxtpx:TrackPointExtension><gpxtpx:hr>{hr}</gpxtpx:hr></gpxtpx:TrackPointExtension></extensions>" if hr else "") + "</trkpt>\n"
        for la, lo, el, t, hr in pts
    )
    gpx = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="Meine Touren" xmlns="http://www.topografix.com/GPX/1/1" '
        'xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1">\n'
        f"<metadata><name>{escape(name)}</name><time>{f(start)}</time></metadata>\n"
        f"<trk><name>{escape(name)}</name><type>{sport}</type><trkseg>\n{body}</trkseg></trk></gpx>\n"
    )
    return {"gpx": gpx, "name": name, "sport": sport, "start_ts": int(start.timestamp()),
            "end_ts": int(end.timestamp()), "dist_m": dist, "n": len(pts)}
