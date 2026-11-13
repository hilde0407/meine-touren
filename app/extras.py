"""Zusatzfunktionen: Backup, Notizen, Ziele, GPX-Export, Rekorde."""
import io
import re
import json
import shutil
import sqlite3
import tempfile
import uuid
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Response

from . import config, ctx, db, routes
from .gpxtools import TZ

router = APIRouter()


# ---------- Backup ----------
def make_backup(dest_dir=None, strip_secrets=False, keep=14):
    """Konsistente Kopie der Datenbank als ZIP. Gibt Pfad (dest_dir) oder Bytes zurück."""
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td) / "komoot_hub.sqlite"
        src = sqlite3.connect(str(config.DB_PATH))
        dst = sqlite3.connect(str(tmp))
        with dst:
            src.backup(dst)
        src.close()
        if strip_secrets:
            for k in config.SECRET_KEYS:
                dst.execute("UPDATE settings SET v='' WHERE k=?", (k,))
            dst.commit()
        dst.close()
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(tmp, "komoot_hub.sqlite")
            u = ctx.uid()
            if u:
                z.writestr("UID.txt", u)
            if config.SYSTEM_DB.exists() and not strip_secrets:
                st = Path(td) / "system.sqlite"
                a = sqlite3.connect(str(config.SYSTEM_DB)); b = sqlite3.connect(str(st))
                with b:
                    a.backup(b)
                a.close(); b.close()
                z.write(st, "system.sqlite")
            if not strip_secrets and config.TRACK_DIR.exists():       # lokale Touren: Original-GPX gehören zum Datenbestand
                for g in sorted(list(config.TRACK_DIR.glob("*.gpx")) + list(config.TRACK_DIR.glob("*.hr.json"))):
                    z.write(g, f"tracks/{g.name}")
            z.writestr("INFO.txt", f"Meine Touren Backup {datetime.now(TZ).isoformat()}\nWiederherstellen: deploy/restore.sh <datei.zip>\n")
    name = f"meine-touren-{datetime.now(TZ):%Y-%m-%d_%H%M}.zip"
    if dest_dir is None:
        return name, buf.getvalue()
    d = Path(dest_dir); d.mkdir(parents=True, exist_ok=True)
    p = d / name; p.write_bytes(buf.getvalue()); p.chmod(0o600)
    for old in sorted(list(d.glob("meine-touren-*.zip")) + list(d.glob("komoot-hub-*.zip")), key=lambda f: f.stat().st_mtime)[:-keep]:
        old.unlink()
    return p


@router.post("/api/backup/now")
def api_backup_now():
    """Sofort eine Sicherung in den Sicherungsordner schreiben (für den Hinweis „noch kein Backup“)."""
    p = auto_backup(max_age_s=0)
    if not p:
        raise HTTPException(500, "Die Sicherung konnte nicht geschrieben werden: " + (db.get("backup_err") or "unbekannter Fehler"))
    return {"ok": True, "name": Path(str(p)).name}


@router.get("/api/backup")
def api_backup():
    name, data = make_backup(strip_secrets=True)
    return Response(data, media_type="application/zip", headers={"Content-Disposition": f'attachment; filename="{name}"'})


# ---------- Notizen ----------
@router.post("/api/tours/{tour_id}/note")
def api_note(tour_id: str, body: dict):
    note = (body.get("note") or "").strip()[:5000]
    if not db.one("SELECT 1 x FROM tours WHERE id=?", (tour_id,)):
        raise HTTPException(404, "Tour nicht gefunden")
    if note:
        db.execute("INSERT OR REPLACE INTO tour_notes(id,note) VALUES(?,?)", (tour_id, note))
    else:
        db.execute("DELETE FROM tour_notes WHERE id=?", (tour_id,))
    return {"ok": True}


# ---------- Ziele ----------
METRICS = {"km", "up", "count", "hours"}


@router.get("/api/goals")
def api_goals():
    return db.query("SELECT * FROM goals ORDER BY year DESC, id")


@router.post("/api/goals")
def api_goal_add(body: dict):
    try:
        year, target = int(body["year"]), float(body["target"])
    except (KeyError, ValueError, TypeError):
        raise HTTPException(400, "Jahr und Zielwert angeben")
    metric = body.get("metric", "km")
    if metric not in METRICS or target <= 0:
        raise HTTPException(400, "Ungültiges Ziel")
    db.execute("INSERT INTO goals(year,sport,metric,target) VALUES(?,?,?,?)", (year, body.get("sport") or "", metric, target))
    return {"ok": True}


@router.delete("/api/goals/{gid}")
def api_goal_del(gid: int):
    db.execute("DELETE FROM goals WHERE id=?", (gid,))
    return {"ok": True}


# ---------- GPX-Export ----------
def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def tour_gpx(t, pts):
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<gpx version="1.1" creator="Meine Touren" xmlns="http://www.topografix.com/GPX/1/1">',
           f'<metadata><name>{_esc(t["name"])}</name></metadata>',
           f'<trk><name>{_esc(t["name"])}</name><trkseg>']
    for p in pts:
        ele = f"<ele>{p[2]}</ele>" if len(p) > 2 and p[2] is not None else ""
        tm = ""
        if len(p) > 3 and p[3] is not None and t["start_ts"]:
            tm = "<time>" + datetime.fromtimestamp(t["start_ts"] + p[3] / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") + "</time>"
        out.append(f'<trkpt lat="{p[0]}" lon="{p[1]}">{ele}{tm}</trkpt>')
    out.append("</trkseg></trk></gpx>")
    return "\n".join(out)


@router.get("/api/tours/{tour_id}/gpx")
def api_gpx(tour_id: str):
    t = db.one("SELECT * FROM tours WHERE id=?", (tour_id,))
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    pts = routes.load(tour_id)
    if not pts:
        raise HTTPException(404, "Strecke noch nicht geladen (Tour mit Komoot abgleichen)")
    fn = "".join(c if c.isalnum() or c in " -_" else "_" for c in t["name"]).strip() or tour_id
    from . import tracks
    text = tour_gpx(t, pts)
    hr = tracks.hr_series(tour_id)
    if hr:
        text = tracks.merge_hr(text, hr)[0]
    return Response(text, media_type="application/gpx+xml", headers={"Content-Disposition": f'attachment; filename="{fn}.gpx"'})


# ---------- Rekorde: höchste Punkte aus den gespeicherten Strecken ----------
_alt_cache = {}


@router.get("/api/records/altitude")
def api_altitude(limit: int = 10):
    res = []
    if routes.D.exists():
        for f in routes.D.glob("*.json"):
            if f.name.endswith(".s.json"):
                continue
            key = (f.name, f.stat().st_mtime)
            if key not in _alt_cache:
                try:
                    alts = [p[2] for p in json.loads(f.read_text()) if len(p) > 2 and p[2] is not None]
                except (ValueError, TypeError):
                    alts = []
                _alt_cache[key] = max(alts) if alts else None
            if _alt_cache[key] is not None:
                res.append({"id": f.stem, "alt": _alt_cache[key]})
    res.sort(key=lambda r: -r["alt"])
    return res[:limit]


# ---------- Kartenkacheln: Cache-Proxy (nur auf Abruf, kein Massen-Download) ----------
import os
import time

import requests
from fastapi.responses import FileResponse, RedirectResponse

TILE_UP = {
    "osm": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
    "topo": "https://tile.opentopomap.org/{z}/{x}/{y}.png",
    "sat": "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
}
TILE_TTL = 14 * 86400
TILE_DIR = config.TILE_CACHE
UA = {"User-Agent": "MeineTouren/1.0 (privates Selbsthosting; https://github.com/hilde0407/meine-touren)"}


@router.get("/tiles/{style}/{z}/{x}/{y}")
def api_tile(style: str, z: int, x: int, y: int):
    if style not in TILE_UP or not (0 <= z <= 19) or x < 0 or y < 0 or x >= 2 ** z or y >= 2 ** z:
        raise HTTPException(404)
    f = TILE_DIR / style / str(z) / str(x) / f"{y}.png"
    fresh = f.exists() and time.time() - f.stat().st_mtime < TILE_TTL
    if not fresh and config.TILE_FETCH:
        try:
            r = requests.get(TILE_UP[style].format(z=z, x=x, y=y), headers=UA, timeout=8)
            if r.status_code == 200 and r.content:
                f.parent.mkdir(parents=True, exist_ok=True)
                # eindeutiger Temp-Name: zwei gleichzeitige Abrufe derselben Kachel dürfen sich nicht die Datei wegnehmen
                tmp = f.with_name(f"{f.stem}.{uuid.uuid4().hex}.tmp")
                try:
                    tmp.write_bytes(r.content); tmp.replace(f)
                except OSError:
                    if not f.exists():                # Windows verweigert das Ersetzen, wenn ein anderer Abruf gerade dieselbe Kachel schreibt – dann gewinnt dieser
                        raise
                finally:
                    tmp.unlink(missing_ok=True)       # nach Erfolg schon weg, bei Fehler keine Reste
                fresh = True
        except requests.RequestException:
            pass
    if not f.exists():   # Server kommt nicht ins Internet: Browser direkt zum Kartenanbieter weiterleiten
        return RedirectResponse(TILE_UP[style].format(z=z, x=x, y=y), status_code=307)
    ct = "image/jpeg" if style == "sat" else "image/png"
    return FileResponse(f, media_type=ct, headers={"Cache-Control": "public, max-age=86400"})


def prune_tiles(max_bytes=1_500_000_000):
    if not TILE_DIR.exists():
        return 0
    files = [(p.stat().st_mtime, p.stat().st_size, p) for p in TILE_DIR.rglob("*.png") if p.is_file()]
    total, removed = sum(s for _, s, _ in files), 0
    for _, s, p in sorted(files, key=lambda t: t[0]):
        if total <= max_bytes:
            break
        p.unlink(missing_ok=True); total -= s; removed += 1
    return removed


# ---------- Wetter am Tourtag (Open-Meteo, kostenlos, ohne Schlüssel) ----------
WMO = {0: "klar", 1: "überwiegend klar", 2: "teils bewölkt", 3: "bedeckt", 45: "Nebel", 48: "Reifnebel", 51: "leichter Nieselregen", 53: "Nieselregen",
       55: "starker Nieselregen", 56: "gefrierender Nieselregen", 57: "gefrierender Nieselregen", 61: "leichter Regen", 63: "Regen", 65: "starker Regen",
       66: "gefrierender Regen", 67: "gefrierender Regen", 71: "leichter Schneefall", 73: "Schneefall", 75: "starker Schneefall", 77: "Schneegriesel",
       80: "leichte Schauer", 81: "Schauer", 82: "heftige Schauer", 85: "Schneeschauer", 86: "starke Schneeschauer", 95: "Gewitter", 96: "Gewitter mit Hagel", 99: "Gewitter mit Hagel"}


def fetch_weather(t):
    day = datetime.fromtimestamp(t["start_ts"], tz=TZ).date()
    end_day = datetime.fromtimestamp(t["end_ts"] or t["start_ts"], tz=TZ).date()
    old = (datetime.now(TZ).date() - day).days > 6
    url = "https://archive-api.open-meteo.com/v1/archive" if old else "https://api.open-meteo.com/v1/forecast"
    prm = {"latitude": t["lat"], "longitude": t["lng"], "start_date": day.isoformat(), "end_date": end_day.isoformat(), "timezone": "Europe/Berlin",
           "hourly": "temperature_2m,precipitation,weather_code,wind_speed_10m,snowfall,snow_depth"}
    prm["start_date"] = (day - timedelta(days=3)).isoformat()      # drei Tage davor: Neuschnee vor der Tour
    if not old:
        prm.pop("start_date"); prm.pop("end_date"); prm["past_days"] = 7; prm["forecast_days"] = 1
    r = requests.get(url, params=prm, headers=UA, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"Wetterdienst: HTTP {r.status_code}")
    h = r.json().get("hourly") or {}
    rows, snow72, depth = [], 0.0, []
    sf, sd = h.get("snowfall") or [], h.get("snow_depth") or []
    for i, tm in enumerate(h.get("time", [])):
        ts = int(datetime.fromisoformat(tm).replace(tzinfo=TZ).timestamp())
        if t["start_ts"] - 72 * 3600 < ts <= t["start_ts"]:
            snow72 += (sf[i] if i < len(sf) else None) or 0
        if t["start_ts"] - 3600 < ts < (t["end_ts"] or t["start_ts"]) + 1800:
            rows.append({"ts": ts, "t": h["temperature_2m"][i], "p": h["precipitation"][i], "c": h["weather_code"][i], "w": h["wind_speed_10m"][i],
                         "s": (sf[i] if i < len(sf) else None) or 0})
            if i < len(sd) and sd[i] is not None:
                depth.append(sd[i] * 100)                   # Meter -> cm
    if not rows:
        raise RuntimeError("Keine Wetterdaten für diesen Zeitraum")
    temps = [r["t"] for r in rows if r["t"] is not None]
    code = max((r["c"] for r in rows if r["c"] is not None), default=0)
    return {"tmin": min(temps), "tmax": max(temps), "precip": round(sum(r["p"] or 0 for r in rows), 1), "wind": max((r["w"] or 0) for r in rows),
            "code": code, "text": WMO.get(code, "–"), "hours": len(rows),
            "snowfall": round(sum(r["s"] for r in rows), 1), "snow72": round(snow72, 1), "snow_depth": round(max(depth)) if depth else None}


@router.get("/api/tours/{tour_id}/weather")
def api_weather(tour_id: str):
    t = db.one("SELECT * FROM tours WHERE id=?", (tour_id,))
    if not t or t["lat"] is None:
        raise HTTPException(404, "Tour oder Startpunkt unbekannt")
    c = db.one("SELECT js,ts FROM weather WHERE id=?", (tour_id,))
    old = json.loads(c["js"]) if c else None
    if old and "snow72" in old and (time.time() - c["ts"] < 86400 * 30 or (time.time() - t["start_ts"]) > 10 * 86400):
        return old
    try:
        w = fetch_weather(t)
    except Exception as e:  # noqa
        if old:                                   # ältere Daten ohne Schneeangaben sind besser als nichts
            return old
        raise HTTPException(502, str(e))
    db.execute("INSERT OR REPLACE INTO weather(id,js,ts) VALUES(?,?,?)", (tour_id, json.dumps(w), int(time.time())))
    return w


# ---------- Namensvorschläge aus Kartendaten (Nominatim + Overpass, beide OpenStreetMap) ----------
SPORT_NAME = {"hike": "Wanderung", "touringbicycle": "Radtour", "e_touringbicycle": "E-Bike-Tour", "racebike": "Rennradtour", "mtb": "MTB-Tour",
              "jogging": "Lauf", "skialpin": "Skifahren", "skitour": "Skitour", "nordic": "Langlauf", "snowshoe": "Schneeschuhwanderung",
              "mountaineering": "Bergtour", "nordicwalking": "Nordic Walking"}
_last_geo = [0.0]
import threading
_geo_lock = threading.Lock()
OVERPASS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]


def overpass(q, timeout=12):
    last = None
    for u in OVERPASS:                      # zweiter Server als Rückfall, kurze Wartezeit statt minutenlangem Hängen
        try:
            r = requests.post(u, data={"data": q}, headers=UA, timeout=timeout)
            if r.status_code == 200:
                return r.json().get("elements") or []
            last = f"HTTP {r.status_code}"
        except requests.RequestException as ex:
            last = type(ex).__name__
    raise RuntimeError(f"Overpass: {last}")


def _hav(a, b):
    from math import asin, cos, radians, sin, sqrt
    la, lb = radians(a[0]), radians(b[0]); dl, dn = lb - la, radians(b[1] - a[1])
    return 2 * 6371000 * asin(sqrt(sin(dl / 2) ** 2 + cos(la) * cos(lb) * sin(dn / 2) ** 2))


def place_name(lat, lng):
    """Ortsname (Dorf/Stadt/Ortsteil) zu einer Koordinate; Ergebnisse werden zwischengespeichert."""
    key = f"{lat:.3f},{lng:.3f}"
    with _geo_lock:                                  # Nominatim: höchstens 1 Anfrage pro Sekunde, auch bei parallelen Aufrufen
        c = db.one("SELECT name FROM geocache WHERE k=?", (key,))
        if c:
            return c["name"] or None
        wait = 1.1 - (time.time() - _last_geo[0])
        if wait > 0:
            time.sleep(wait)
        _last_geo[0] = time.time()
        r = requests.get("https://nominatim.openstreetmap.org/reverse", headers=UA, timeout=8,
                         params={"format": "jsonv2", "lat": lat, "lon": lng, "zoom": 14, "accept-language": "de", "addressdetails": 1})
        if r.status_code != 200:
            raise RuntimeError(f"Ortssuche: HTTP {r.status_code}")
        a = r.json().get("address") or {}
        name = next((a[k] for k in ("hamlet", "village", "suburb", "town", "city_district", "city", "municipality", "county") if a.get(k)), None)
        db.execute("INSERT OR REPLACE INTO geocache(k,name,ts) VALUES(?,?,?)", (key, name or "", int(time.time())))
        return name


_ov_down = [0.0]          # Zeitpunkt, bis zu dem Overpass als nicht erreichbar gilt (spart minutenlange Wartezeiten)


def nominatim_peaks(lat, lng, r=350):
    """Ausweichweg ohne Overpass: Gipfel in der Nähe über die Nominatim-Suche (höchstens 1 Anfrage pro Sekunde)."""
    dl, dn = 0.0065, 0.0095
    with _geo_lock:
        wait = 1.1 - (time.time() - _last_geo[0])
        if wait > 0:
            time.sleep(wait)
        _last_geo[0] = time.time()
        resp = requests.get("https://nominatim.openstreetmap.org/search", headers=UA, timeout=10, params={
            "q": "peak", "viewbox": f"{lng - dn},{lat + dl},{lng + dn},{lat - dl}", "bounded": 1, "format": "jsonv2", "limit": 10, "accept-language": "de"})
    if resp.status_code != 200:
        raise RuntimeError(f"Nominatim: HTTP {resp.status_code}")
    out = []
    for e in resp.json():
        if e.get("category") == "natural" and e.get("type") == "peak" and e.get("name"):
            out.append({"lat": float(e["lat"]), "lon": float(e["lon"]), "tags": {"name": e["name"]}})
    return out


def peak_name(lat, lng):
    key = f"peak:{lat:.3f},{lng:.3f}"
    c = db.one("SELECT name FROM geocache WHERE k=?", (key,))
    if c:
        return c["name"] or None
    q = f'[out:json][timeout:10];(node(around:350,{lat},{lng})["natural"~"peak|saddle"]["name"];node(around:350,{lat},{lng})["tourism"="alpine_hut"]["name"];);out;'
    els = None
    if time.time() > _ov_down[0]:
        try:
            els = overpass(q, 10)
        except RuntimeError:
            _ov_down[0] = time.time() + 600          # 10 Minuten lang nicht erneut versuchen
    if els is None:
        els = [e for e in nominatim_peaks(lat, lng) if _hav((lat, lng), (e["lat"], e["lon"])) <= 350]
    els.sort(key=lambda x: _hav((lat, lng), (x["lat"], x["lon"])))
    name = (els[0].get("tags") or {}).get("name") if els else None
    db.execute("INSERT OR REPLACE INTO geocache(k,name,ts) VALUES(?,?,?)", (key, name or "", int(time.time())))
    return name


TRAIL_BRANDS = re.compile(r"wisper|traumschleife|traumpfad|hiwwel|saar-?hunsr|rheinsteig|rheingau|soonwald|nahe|taunus|lahn|westerwald|premiumweg|steig|trail|schleife", re.I)
ROUTE_TYPES = {"bike": "bicycle|mtb", "walk": "hiking|foot|running"}
BIKE_SPORTS = {"touringbicycle", "e_touringbicycle", "racebike", "mtb"}


def _near(p, nodes, r):
    # grobe Vorauswahl über Gradabstand, dann exakt
    dl, dn = r / 111000.0, r / 75000.0
    return any(abs(p[0] - a) < dl and abs(p[1] - b) < dn and _hav(p, (a, b)) <= r for a, b in nodes)


def trail_names(t, pts, fetch=None):
    """Benannte Wander-/Radrouten (Wispertrails, Traumschleifen, Hiwweltouren …), denen die Tour folgt (OpenStreetMap-Routenrelationen)."""
    import hashlib
    if len(pts) < 5:
        return []
    n = min(40, max(8, len(pts) // 8))
    samp = [(pts[int(i * (len(pts) - 1) / (n - 1))][0], pts[int(i * (len(pts) - 1) / (n - 1))][1]) for i in range(n)]
    kind = ROUTE_TYPES["bike" if t["sport"] in BIKE_SPORTS else "walk"]
    key = "trail:" + hashlib.md5((kind + ",".join(f"{a:.4f},{b:.4f}" for a, b in samp)).encode()).hexdigest()
    c = db.one("SELECT name FROM geocache WHERE k=?", (key,))
    if c:
        return json.loads(c["name"] or "[]")
    poly = ",".join(f"{a:.5f},{b:.5f}" for a, b in samp)
    q = f'[out:json][timeout:12];rel(around:30,{poly})["route"~"^({kind})$"]["name"];out tags geom;'
    if fetch:
        els = fetch(q)
    else:
        els = overpass(q, 14)
    found = []
    for el in els:
        tags = el.get("tags") or {}
        nodes = [(g["lat"], g["lon"]) for m in el.get("members", []) if m.get("geometry") for g in m["geometry"]]
        if not nodes:
            continue
        cov = sum(1 for p in samp if _near(p, nodes, 60)) / len(samp)
        if cov < 0.6:
            continue
        name = tags["name"].strip()
        found.append((bool(TRAIL_BRANDS.search(name) or TRAIL_BRANDS.search(tags.get("network:name", "") + tags.get("operator", ""))), cov, name, tags.get("ref")))
    found.sort(key=lambda x: (not x[0], -x[1]))
    names = []
    for _, _, nm, ref in found:
        if nm not in names:
            names.append(nm)
    names = names[:3]
    db.execute("INSERT OR REPLACE INTO geocache(k,name,ts) VALUES(?,?,?)", (key, json.dumps(names, ensure_ascii=False), int(time.time())))
    return names


def name_suggestions(t, pts, part="all"):
    sp = SPORT_NAME.get(t["sport"], "Tour")
    if not pts:
        pts = [[t["lat"], t["lng"], None]] if t["lat"] is not None else []
    if not pts:
        raise RuntimeError("Keine Kartendaten vorhanden")
    start, end = pts[0], pts[-1]
    far = max(pts, key=lambda p: _hav(start, p))
    hi = max((p for p in pts if len(p) > 2 and p[2] is not None), key=lambda p: p[2], default=None)
    errs, out = [], []

    def safe(fn, *a):
        try:
            return fn(*a)
        except Exception as e:  # noqa
            errs.append(str(e)); return None
    loop = _hav(start, end) < max(500, 0.15 * (t["dist_m"] or 0))
    want_peak = part in ("all", "peak") and hi is not None and start[2] is not None and hi[2] - start[2] >= 150 and t["sport"] in ("hike", "mountaineering", "skitour", "snowshoe", "nordicwalking", "skialpin")

    def do_guides():
        from .wanderfuehrer import guide_matches
        return safe(guide_matches, pts) if part in ("all", "guides") else []

    def do_trails():
        return (safe(trail_names, t, pts) or []) if part in ("all", "trails") else []

    def do_places():
        a_ = safe(place_name, start[0], start[1])
        b_ = None if loop or part != "all" and part != "places" else safe(place_name, end[0], end[1])
        f_ = safe(place_name, far[0], far[1]) if (part in ("all", "places") and loop and _hav(start, far) > 2500) else None
        return a_, b_, f_

    def do_peak():
        return safe(peak_name, hi[0], hi[1]) if want_peak else None

    if part == "all":      # wie in den Tourdetails: Overpass (Wege, Gipfel, Wanderführer) und Nominatim (Orte) laufen gleichzeitig statt nacheinander
        import contextvars
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(4) as ex:
            fs = [ex.submit(contextvars.copy_context().run, fn) for fn in (do_guides, do_trails, do_places, do_peak)]
            guides, trails, (a, b, f), pk = [x.result() for x in fs]
    else:
        guides = do_guides()
        if part == "guides":
            return [x for bk, ti in (guides or []) for x in ((f"{ti} ({bk})", ti) if bk else (ti,)) if x != t["name"]]
        trails = do_trails()
        a, b, f = do_places()
        pk = do_peak()
    for tn in trails:
        out.append(tn)
        if a and a.lower() not in tn.lower():
            out.append(f"{tn} bei {a}")
    if not loop and a and b and a != b:
        out.append(f"{sp} von {a} nach {b}")
    if pk:
        out.append(f"{sp} zum {pk}" if not a else f"{sp} {a} – {pk}")
    if a and part in ("all", "places"):
        out.append(f"{sp} bei {a}")
    if f and f != a and a:
        out.append(f"{sp} {a} – {f}")
    if loop and a and part in ("all", "places"):
        out.append(f"Runde um {a}" if t["sport"] in ("hike", "jogging", "nordicwalking") else f"{sp}-Runde {a}")
    out = [x for b, ti in (guides or []) for x in ((ti, f"{ti} ({b})") if b else (ti,))] + out
    seen, res = set(), []
    for s in out:
        if s not in seen and s != t["name"]:
            seen.add(s); res.append(s)
    if not res and errs:
        raise RuntimeError(errs[0])
    return res[:5]


@router.get("/api/tours/{tour_id}/name-suggestions")
def api_name_suggestions(tour_id: str, part: str = "all"):
    t = db.one("SELECT * FROM tours WHERE id=?", (tour_id,))
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    try:
        return {"suggestions": name_suggestions(t, routes.load(tour_id) or [], part)}
    except Exception as e:  # noqa
        raise HTTPException(502, str(e))


# ---------- Höhenkorrektur ----------
@router.post("/api/tours/{tour_id}/elev-fix")
def api_elev_fix(tour_id: str):
    from . import elev
    try:
        return elev.fix(tour_id)
    except KeyError:
        raise HTTPException(404, "Tour nicht gefunden")
    except Exception as e:  # noqa
        raise HTTPException(502, str(e))


@router.post("/api/tours/{tour_id}/elev-zepp")
def api_elev_zepp(tour_id: str):
    """Höhe aus der barometrischen Uhr-Höhe (Zepp) übernehmen; Wiederherstellen läuft über elev-restore."""
    from . import elev
    try:
        return elev.zepp_fix(tour_id)
    except KeyError:
        raise HTTPException(404, "Tour nicht gefunden")
    except elev.ZeppFixError as e:
        raise HTTPException(422, str(e))
    except Exception as e:  # noqa
        raise HTTPException(502, str(e))


@router.post("/api/tours/{tour_id}/elev-restore")
def api_elev_restore(tour_id: str):
    from . import elev
    return {"ok": elev.restore(tour_id)}


# ---------- Regionen der Touren (Land, Bundesland, Landkreis, Ort) ----------
def region_of(lat, lng):
    r = requests.get("https://nominatim.openstreetmap.org/reverse", headers=UA, timeout=10,
                     params={"format": "jsonv2", "lat": lat, "lon": lng, "zoom": 12, "accept-language": "de", "addressdetails": 1})
    if r.status_code != 200:
        raise RuntimeError(f"Ortssuche: HTTP {r.status_code}")
    a = r.json().get("address") or {}
    place = next((a[k] for k in ("village", "town", "city", "municipality", "suburb", "hamlet") if a.get(k)), None)
    return {"country": a.get("country"), "state": a.get("state") or a.get("region") or a.get("province"),
            "county": a.get("county") or a.get("state_district"), "place": place}


def geo_fill(dry=False, limit=None, fetch=None):
    """Tourstartpunkte einer Region zuordnen (1 Anfrage/s, nur für Touren ohne Eintrag)."""
    from . import jobs
    fetch = fetch or region_of
    todo = db.query("SELECT id,lat,lng FROM tours WHERE lat IS NOT NULL AND lng IS NOT NULL AND id NOT IN (SELECT id FROM tour_geo) ORDER BY start_ts DESC")
    if limit:
        todo = todo[:limit]
    jobs.log(f"Regionen: {len(todo)} Touren ohne Region")
    ok = 0
    for i, t in enumerate(todo, 1):
        jobs.progress(f"Regionen {i}/{len(todo)}")
        try:
            g = fetch(t["lat"], t["lng"])
        except Exception as e:  # noqa
            jobs.log(f"  Regionen: {e} – Abbruch, nächster Versuch später"); break
        db.execute("INSERT OR REPLACE INTO tour_geo(id,country,state,county,place,ts) VALUES(?,?,?,?,?,?)",
                   (t["id"], g.get("country"), g.get("state"), g.get("county"), g.get("place"), int(time.time())))
        ok += 1
        time.sleep(1.1)
    jobs.log(f"Regionen: {ok} zugeordnet")
    return ok


def newest_backup():
    fs = [p for d in config.backup_dirs(ctx.uid()) if d.exists() for p in d.glob("*.zip")]
    return max(fs, key=lambda p: p.stat().st_mtime) if fs else None


def backup_on_update():
    """Beim ersten Start einer neuen Programmversion sofort eine Sicherung anlegen (Rückweg bei Problemen)."""
    if db.get("last_version") == config.VERSION:
        return None
    nb = newest_backup()
    p = None
    if db.one("SELECT 1 x FROM tours LIMIT 1") and not (nb and time.time() - nb.stat().st_mtime < 600):
        p = auto_backup(max_age_s=0)
    db.put("last_version", config.VERSION)
    return p


def auto_backup(max_age_s=23 * 3600):
    """Sicherung selbst erstellen, falls die letzte älter ist (unabhängig vom Cron-Eintrag)."""
    nb = newest_backup()
    if nb and time.time() - nb.stat().st_mtime < max_age_s:
        return None
    err = None
    for d in config.backup_dirs(ctx.uid()):
        try:
            d.mkdir(parents=True, exist_ok=True)
            p = make_backup(str(d), keep=14)
            db.put("backup_err", "")
            return p
        except Exception as e:  # noqa
            err = f"{d}: {e}"
    db.put("backup_err", err or "unbekannt")
    return None


# ---------- Wanderführer: ausgelagert nach wanderfuehrer.py, hier nur noch die gewohnten Namen ----------
def __getattr__(name):
    """Ausgelagerte Funktionen bleiben unter ihrem gewohnten Namen erreichbar."""
    if name in ("_guide_parse", "guide_stats", "guide_matches", "_seg_dist", "_covered", "GUIDE_DIR"):
        from . import wanderfuehrer
        return getattr(wanderfuehrer, name)
    if name == "api_selftest":
        from . import selbsttest
        return selbsttest.api_selftest
    raise AttributeError(name)
