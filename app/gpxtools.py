"""TCX/GPX -> sauberes GPX (nur GPS-Punkte). Python-Port von conv.pl."""
import math
import re
from datetime import datetime, timezone
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from . import config

TZ = ZoneInfo(config.TZ_NAME)

# Zepp-Sporttyp -> Komoot-Sportart (3.50.0: Laufen ist eigene Sportart wie im Tagebuch; 3.59.0: 178 ist wieder Schneeschuh)
#   1 Laufen draußen, 8 Laufband -> jogging · 6/7 Gehen, 13, 15, 22 -> hike · 9 Rad · 43/105 Ski alpin · 178 Schneeschuh (-> hike + Schlagwort) · 206 E-Bike
ZEPP_SPORT = {
    1: "jogging", 6: "hike", 7: "hike", 8: "jogging", 9: "touringbicycle", 13: "hike", 15: "hike", 22: "hike",
    43: "skialpin", 105: "skialpin", 178: "snowshoe", 206: "e_touringbicycle",
}
ZEPP_LAUFEN = (1, 8)                       # Zepp-Typen, die bis 3.49.0 als Wandern geführt wurden und jetzt Laufen sind (Umzug: app/sport_umzug.py)
ALIAS = {
    "cycling": "touringbicycle", "running": "jogging", "walking": "hike", "hiking": "hike",
    "type_1": "jogging", "type_6": "hike", "type_7": "hike", "type_8": "jogging", "type_9": "touringbicycle",
    "type_13": "hike", "type_15": "hike", "type_22": "hike", "type_43": "skialpin", "type_105": "skialpin",
    "type_178": "snowshoe", "type_206": "e_touringbicycle",
    # 3.60.0: übliche englische GPX-/TCX-Typen anderer Apps -> Katalog (entfernte Aktivitäten über RUECKFALL)
    "trail_running": "trailrun", "mountain_biking": "mtb", "road_biking": "racebike", "gravel_cycling": "mtb_easy", "e_biking": "e_touringbicycle",
    "alpine_skiing": "skialpin", "backcountry_skiing": "skitour", "cross_country_skiing": "nordic", "snowboarding": "snowboard", "snowshoeing": "snowshoe",
    "kayaking": "kayak", "canoeing": "kayak", "paddling": "kayak", "rafting": "rafting", "boating": "boat", "inline_skating": "skaten",
    "horseback_riding": "horse", "paragliding": "paraglide", "rock_climbing": "climbing", "mountaineering": "mountaineering",
    "stand_up_paddleboarding": "sup", "swimming": "swim", "sailing": "sailing", "ice_skating": "iceskate",
}
# Aktivitäten-Katalog – EINE Tabelle (wie SPORT_TABLE in 01-grundlagen.js; tests/test_katalog_360.py prüft, dass beide gleich sind).
# 3.60.0: die endgültige Auswahl – genau 29 Aktivitäten in 5 Kategorien (in beiden Apps gleich). Vorhandene Schlüssel bleiben (auch Komoot-Kennungen wie
# touringbicycle, e_mtb, mtb_easy = Gravel, skaten = Inline); neu sind bikepacking, rafting und paraglide. Schneeschuh gehört zur Kategorie „Winter“.
# Eine weitere Aktivität = eine Zeile hier und eine in SPORT_TABLE (+ Übersetzung des Namens in 00-i18n-neu.js).
#   (Schlüssel, Name der Sportart, Vorgabename einer Tour, Kategorie)
KATEGORIEN = [("fuss", "Zu Fuß"), ("rad", "Rad"), ("winter", "Winter"), ("wasser", "Wasser"), ("sonst", "Outdoor und Sonstige")]
CATALOG = [
    ("hike", "Wandern", "Wanderung", "fuss"), ("walk", "Spazieren / Gehen", "Spaziergang", "fuss"), ("mountaineering", "Bergsteigen", "Bergtour", "fuss"),
    ("climbing", "Klettern / Klettersteig", "Klettertour", "fuss"), ("nordicwalking", "Nordic Walking", "Nordic Walking", "fuss"),
    ("jogging", "Laufen", "Lauf", "fuss"), ("trailrun", "Trailrunning", "Trailrun", "fuss"),
    ("touringbicycle", "Radtour", "Radtour", "rad"), ("racebike", "Rennrad", "Rennradtour", "rad"), ("mtb", "Mountainbike", "Mountainbike-Tour", "rad"),
    ("mtb_easy", "Gravelbike", "Gravel-Tour", "rad"), ("e_touringbicycle", "E-Bike", "E-Bike-Tour", "rad"), ("e_mtb", "E-Mountainbike", "E-Mountainbike-Tour", "rad"),
    ("bikepacking", "Bikepacking", "Bikepacking-Tour", "rad"),
    ("skialpin", "Ski alpin", "Skifahren", "winter"), ("skitour", "Skitour", "Skitour", "winter"), ("nordic", "Langlauf", "Langlauf", "winter"),
    ("snowboard", "Snowboard", "Snowboard", "winter"), ("snowshoe", "Schneeschuhwandern", "Schneeschuhwanderung", "winter"),
    ("kayak", "Kajak / Kanu", "Paddeltour", "wasser"), ("rowing", "Rudern", "Rudertour", "wasser"), ("dragonboat", "Drachenboot", "Drachenboot", "wasser"),
    ("rafting", "Rafting", "Raftingtour", "wasser"), ("boat", "Bootfahren", "Bootstour", "wasser"),
    ("skateboard", "Skateboard", "Skateboard", "sonst"), ("skaten", "Inlineskaten / Rollschuh", "Inlinetour", "sonst"), ("horse", "Reiten", "Ausritt", "sonst"),
    ("paraglide", "Gleitschirm", "Gleitschirmflug", "sonst"), ("other", "Sonstiges", "Tour", "sonst"),
]
# 3.60.0 Rückfall: Schlüssel, die 3.59.0 im Katalog hatte (oder die eine Quelle meldet) und die nicht mehr angeboten werden -> Aktivität des Katalogs.
# Touren mit einem solchen Schlüssel bleiben, wie sie sind (keine Datenänderung); Anzeige, Filter, Statistik und Ziele behandeln sie wie ihre Rückfall-Aktivität
# (norm, stat_gruppen, 01-grundlagen.js SPORT_ALIAS/sNorm – dieselbe Tabelle). Import (Komoot-Datei, GPX/TCX, FIT, Zepp, Aufzeichnung) und Senden (Strava, Komoot)
# setzen den Rückfall ein. Favoriten und Statistik-Gruppen lassen entfernte Schlüssel beim Laden still weg.
RUECKFALL = {
    "dogwalk": "walk", "orienteering": "jogging", "pilgrimage": "hike", "commute": "touringbicycle", "cyclocross": "racebike", "bmx": "other",
    "splitboard": "skitour", "snowmobile": "other", "sled": "other", "iceskate": "other", "sup": "kayak",
    "sailing": "other", "swim": "other", "snorkel": "other", "diving": "other", "surf": "other", "kitesurf": "other", "wakesurf": "other", "waterski": "other",
    "fishing": "other", "hunting": "other", "archery": "other", "golf": "other", "atv": "other", "motorbike": "other",
}
LABEL = {k: tour for k, _, tour, _ in CATALOG}                  # Vorgabename einer importierten Tour je Sportart (nur der Katalog)
SPORT_NAME = {k: n for k, n, _, _ in CATALOG}                   # Name der Sportart (deutsch)
SPORT_NAME.update({k: SPORT_NAME[v] for k, v in RUECKFALL.items()})   # 3.60.0: ältere Touren mit entferntem Schlüssel zeigen den Namen ihres Rückfalls
# Aktivitäten-Familien (intern, für Tempo-Schätzung, Planung, Steilheit und ältere Ziele „grp:…“) – NICHT die Statistik-Gruppen (app/stat_gruppen.py, je Benutzer)
FAMILIE = {
    "foot": ("hike", "mountaineering", "nordicwalking", "snowshoe", "walk", "climbing"),
    "bike": ("touringbicycle", "e_touringbicycle", "racebike", "mtb", "mtb_easy", "e_mtb", "bikepacking"),
    "ski": ("skitour", "skialpin", "snowboard"),
    "run": ("jogging", "nordic", "trailrun"),
}
# 3.50.0 legte Schneeschuh mit Wandern zusammen (Wandern + Schlagwort). Seit 3.59.0 ist Schneeschuh wieder eine eigene Sportart: nichts wird mehr zusammengelegt.
# Touren, die 3.50.0 umgestellt hat, bleiben Wandern mit Schlagwort, bis du sie unter Prüfen „als Schneeschuh führst“ (app/sport_umzug.py).
# 3.60.0: Die entfernten Aktivitäten (RUECKFALL) werden wie früher zusammengelegte Kennungen umgesetzt (ohne Schlagwort).
MERGE = {k: (v, None) for k, v in RUECKFALL.items()}
SCHNEESCHUH_TAG = "Schneeschuh"
NAME_RAW = {"snowshoe": "Schneeschuhwanderung"}   # Vorgabename einer importierten Tour, deren Quelle Schneeschuh meldet


def roh(sport):
    """3.60.0: alle gespeicherten Schlüssel, die als diese Sportart zählen (sie selbst und die entfernten Schlüssel mit ihr als Rückfall) – für SQL-Filter."""
    s = norm(sport)[0]
    return [s] + [k for k, v in RUECKFALL.items() if v == s]


def norm(sport):
    """Sportart einer Quelle -> (Sportart dieser App, Schlagwort oder None). Zusammengelegte bzw. entfernte Kennungen (MERGE, 3.60.0 RUECKFALL) werden umgesetzt,
    alles andere bleibt (auch fremde Komoot-Kennungen)."""
    s = str(sport or "")
    if s in MERGE:
        return MERGE[s]
    return s, None


def known(sport):
    """Kennt die App diese Sportart (auch als zusammengelegte Kennung)?"""
    return sport in LABEL or sport in MERGE


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


# ---------- 3.58.0: Wegpunkte und Beschreibung nur in Kopien zum Hochladen bzw. im Komoot-Paket (die gespeicherte GPX bleibt unverändert) ----------
_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ud800-\udfff\ufffe\uffff]")
DESC_MAX = 2000          # Zeichen der Notiz in <desc>
WPT_DESC_MAX = 200       # Zeichen einer Pin-Notiz (wie tour_wps)
WPT_NAME_MAX = 60
WPT_MAX = 200


def clean_text(s, n):
    """Text für eine GPX-Datei: ohne Steuerzeichen (Zeilenumbrüche und Tabulator bleiben), Zeilenenden vereinheitlicht, höchstens n Zeichen
    (gekürzt mit „…“), noch NICHT XML-maskiert (das macht der Aufrufer mit escape)."""
    s = _CTRL.sub("", str(s or "")).replace("\r\n", "\n").replace("\r", "\n").strip()
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s if len(s) <= n else s[: max(0, n - 1)].rstrip() + "…"


def _wpt_xml(w):
    f = lambda ts: datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        la, lo = float(w["lat"]), float(w["lng"])
    except (KeyError, TypeError, ValueError):
        return ""
    if not (-90 <= la <= 90 and -180 <= lo <= 180) or (la == 0 and lo == 0):
        return ""
    name = clean_text(w.get("name") or "", WPT_NAME_MAX).replace("\n", " ")
    desc = clean_text(w.get("desc") or "", WPT_DESC_MAX)
    out = f'<wpt lat="{la:.7f}" lon="{lo:.7f}">'
    if w.get("ele") is not None:
        try:
            out += f"<ele>{float(w['ele']):.1f}</ele>"
        except (TypeError, ValueError):
            pass
    if w.get("ts"):
        try:
            out += f"<time>{f(w['ts'])}</time>"
        except (TypeError, ValueError, OverflowError, OSError):
            pass
    if name:
        out += f"<name>{escape(name)}</name>"
    if desc and desc != name:
        out += f"<desc>{escape(desc)}</desc>"
    if w.get("sym"):
        out += f"<sym>{escape(str(w['sym'])[:30])}</sym>"
    return out + "</wpt>"


def with_waypoints(gpx, wpts=(), desc=""):
    """Kopie einer GPX 1.1 mit <wpt> (Liste von dict: lat, lng, ts, name, desc, ele, sym) und der Beschreibung desc in <metadata><desc>
    und <trk><desc>. Vorhandene <wpt> der Vorlage werden ersetzt (sonst doppelt). Reihenfolge nach GPX-1.1-Schema: metadata, wpt, trk."""
    desc = clean_text(desc, DESC_MAX)
    g = re.sub(r"<wpt\b[^>]*/>|<wpt\b.*?</wpt>\s*", "", gpx, flags=re.S)
    if desc:
        d = f"<desc>{escape(desc)}</desc>"
        m = re.search(r"<metadata>(.*?)</metadata>", g, flags=re.S)
        if m and "<desc>" not in m.group(1):
            inner = m.group(1)
            nm = re.match(r"(\s*<name>.*?</name>)", inner, flags=re.S)
            inner = (nm.group(1) + d + inner[nm.end():]) if nm else d + inner
            g = g[:m.start(1)] + inner + g[m.end(1):]
        elif not m:
            g = re.sub(r"(<gpx\b[^>]*>)", lambda x: x.group(1) + f"\n<metadata>{d}</metadata>", g, count=1)
        t = re.search(r"<trk>(\s*<name>.*?</name>)?", g, flags=re.S)
        if t and not re.match(r"\s*<desc>", g[t.end():]):
            g = g[:t.end()] + d + g[t.end():]
    xs = [x for x in (_wpt_xml(w) for w in list(wpts)[:WPT_MAX]) if x]
    if xs:
        block = "\n".join(xs) + "\n"
        m = re.search(r"</metadata>\s*", g)
        if m:
            g = g[:m.end()] + block + g[m.end():]
        else:
            g = re.sub(r"(<gpx\b[^>]*>\s*)", lambda x: x.group(1) + block, g, count=1)
    return g


def convert(text, filename="", default_sport="hike", wpts=None, desc=""):
    """Gibt dict(gpx, name, sport, start_ts, end_ts, dist_m, n, tags) zurück. tags: Schlagworte aus der Sportart (3.50.0: Schneeschuh -> Wandern + „Schneeschuh“).
    3.58.0: mit wpts/desc (nur für Kopien zum Hochladen) enthält die GPX zusätzlich Wegpunkte und Beschreibung; der Import ruft ohne sie auf (unverändert)."""
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
    raw = typ if known(typ) else (default_sport if known(default_sport) else "hike")
    sport, tag = norm(raw)
    start, end = pts[0][3], pts[-1][3]
    name = f"{NAME_RAW.get(raw) or LABEL.get(sport, 'Tour')} {start.astimezone(TZ).strftime('%d.%m.%Y %H:%M')}"
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
    if wpts or desc:
        gpx = with_waypoints(gpx, wpts or (), desc)
    return {"gpx": gpx, "name": name, "sport": sport, "start_ts": int(start.timestamp()),
            "end_ts": int(end.timestamp()), "dist_m": dist, "n": len(pts), "tags": [tag] if tag else []}
