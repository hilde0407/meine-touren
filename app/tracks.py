"""Lokale Strecken: Hauptquelle für Karte und Tourdetail. Eigene Touren (aus Zepp-Export, GPX/TCX-Dateien) werden
als GPX im Benutzerordner abgelegt (tracks/<id>.gpx); jede Tour hat zusätzlich die Anzeige-Strecke (routes)."""
import re
import time
from datetime import datetime, timezone
from xml.sax.saxutils import escape

from . import config, db, elev, gpxtools, routes
from .gpxtools import TZ


def gpx_file(tid):
    return config.TRACK_DIR / f"{tid}.gpx"


def points_from_gpx(text):
    """[(lat, lng, alt, t_ms_seit_start)] aus GPX-Text."""
    typ, raw = gpxtools._points_gpx(text)
    pts = [(la, lo, el, gpxtools.parse_time(t)) for la, lo, el, t in raw if not (la == 0 and lo == 0)]
    if not pts:
        return []
    t0 = pts[0][3]
    out = []
    for la, lo, el, t in pts:
        try:
            alt = float(el) if el not in ("", None) else None
        except ValueError:
            alt = None
        out.append((la, lo, alt, int((t - t0).total_seconds() * 1000) if t and t0 else None))
    return out


def gpx_for(tid):
    """GPX-Text einer Tour: Originaldatei, sonst aus den lokal gespeicherten Streckenpunkten aufgebaut."""
    tid = str(tid)
    f = gpx_file(tid)
    if f.exists():
        return f.read_text(encoding="utf-8")
    t = db.one("SELECT * FROM tours WHERE id=?", (tid,))
    pts = routes.load(tid)
    if not t or not pts or len(pts) < 2:
        raise RuntimeError("Für diese Tour liegt keine Strecke lokal vor (zuerst „Routen laden“ bzw. mit Komoot abgleichen)")
    start = t["start_ts"] or int(time.time())
    end = t["end_ts"] or start
    n = len(pts)
    fmt = lambda ts: datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = []
    for i, p in enumerate(pts):
        ms = p[3] if len(p) > 3 and p[3] is not None else None
        ts = start + (ms / 1000 if ms is not None else (end - start) * i / max(1, n - 1))
        ele = f"<ele>{p[2]}</ele>" if p[2] is not None else ""
        body.append(f'<trkpt lat="{p[0]}" lon="{p[1]}">{ele}<time>{fmt(int(ts))}</time></trkpt>')
    name = escape(t["name"] or tid)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Meine Touren" xmlns="http://www.topografix.com/GPX/1/1">\n'
            f"<metadata><name>{name}</name><time>{fmt(start)}</time></metadata>\n"
            f"<trk><name>{name}</name><type>{t['sport'] or 'hike'}</type><trkseg>\n" + "\n".join(body) + "\n</trkseg></trk></gpx>\n")


def adopt(text, filename="", prefix="g", ident=None, name=None, sport=None, tours=None):
    """GPX/TCX als lokale Tour anlegen. Gibt die Tour (dict) zurück."""
    c = gpxtools.convert(text, filename, db.get("default_sport") or "hike")
    c["gpx"] = elev.clean_gpx(c["gpx"])[0]
    tid = str(ident or f"{prefix}{c['start_ts']}")
    items = points_from_gpx(c["gpx"])
    alts = [p[2] for p in items if p[2] is not None]
    up = down = 0.0
    if len(alts) > 5:
        up, down = elev.ascent(elev.smooth(alts, 3, 3))
    config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
    gpx_file(tid).write_text(c["gpx"], encoding="utf-8")
    routes.store(tid, items)
    nm = name or c["name"]
    db.execute("INSERT OR REPLACE INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) "
               "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (tid, nm, sport or c["sport"], c["start_ts"], c["end_ts"], c["dist_m"], c["end_ts"] - c["start_ts"], up, down,
                items[0][0], items[0][1], "tour_recorded", "local"))
    return db.one("SELECT * FROM tours WHERE id=?", (tid,)), c


def delete_local(tid):
    t = db.one("SELECT source FROM tours WHERE id=?", (str(tid),))
    if not t or t["source"] != "local":
        raise ValueError("Nur lokale Touren können hier gelöscht werden")
    for tb in ("tours", "tour_tags", "tour_notes", "tour_geo", "tour_peak", "tour_names", "elev_fix", "tour_uploads", "weather"):
        col = "tour_id" if tb == "tour_uploads" else "id"
        db.execute(f"DELETE FROM {tb} WHERE {col}=?", (str(tid),))
    db.execute("UPDATE photos SET tour_id=NULL WHERE tour_id=? AND COALESCE(manual,0)=0", (str(tid),))
    for p in (gpx_file(tid), routes.path_full(tid), routes.path_small(tid)):
        p.unlink(missing_ok=True)
