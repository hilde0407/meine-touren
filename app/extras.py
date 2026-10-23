"""Zusatzfunktionen: Backup, Notizen, Ziele, GPX-Export, Rekorde."""
import io
import re
import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
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
                for g in sorted(config.TRACK_DIR.glob("*.gpx")):
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
    return Response(tour_gpx(t, pts), media_type="application/gpx+xml", headers={"Content-Disposition": f'attachment; filename="{fn}.gpx"'})


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
                tmp = f.with_suffix(".tmp"); tmp.write_bytes(r.content); tmp.replace(f)
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
           "hourly": "temperature_2m,precipitation,weather_code,wind_speed_10m"}
    if not old:
        prm.pop("start_date"); prm.pop("end_date"); prm["past_days"] = 7; prm["forecast_days"] = 1
    r = requests.get(url, params=prm, headers=UA, timeout=20)
    if r.status_code != 200:
        raise RuntimeError(f"Wetterdienst: HTTP {r.status_code}")
    h = r.json().get("hourly") or {}
    rows = []
    for i, tm in enumerate(h.get("time", [])):
        ts = int(datetime.fromisoformat(tm).replace(tzinfo=TZ).timestamp())
        if t["start_ts"] - 3600 < ts < (t["end_ts"] or t["start_ts"]) + 1800:
            rows.append({"ts": ts, "t": h["temperature_2m"][i], "p": h["precipitation"][i], "c": h["weather_code"][i], "w": h["wind_speed_10m"][i]})
    if not rows:
        raise RuntimeError("Keine Wetterdaten für diesen Zeitraum")
    temps = [r["t"] for r in rows if r["t"] is not None]
    code = max((r["c"] for r in rows if r["c"] is not None), default=0)
    return {"tmin": min(temps), "tmax": max(temps), "precip": round(sum(r["p"] or 0 for r in rows), 1), "wind": max((r["w"] or 0) for r in rows),
            "code": code, "text": WMO.get(code, "–"), "hours": len(rows)}


@router.get("/api/tours/{tour_id}/weather")
def api_weather(tour_id: str):
    t = db.one("SELECT * FROM tours WHERE id=?", (tour_id,))
    if not t or t["lat"] is None:
        raise HTTPException(404, "Tour oder Startpunkt unbekannt")
    c = db.one("SELECT js,ts FROM weather WHERE id=?", (tour_id,))
    if c and (time.time() - c["ts"] < 86400 * 30 or (time.time() - t["start_ts"]) > 10 * 86400):
        return json.loads(c["js"])
    try:
        w = fetch_weather(t)
    except Exception as e:  # noqa
        raise HTTPException(502, str(e))
    db.execute("INSERT OR REPLACE INTO weather(id,js,ts) VALUES(?,?,?)", (tour_id, json.dumps(w), int(time.time())))
    return w


# ---------- Selbsttest ----------
@router.post("/api/selftest")
def api_selftest():
    from . import sync as _sync
    res = []

    def chk(name, fn):
        try:
            d = fn(); res.append({"name": name, "ok": True, "detail": d or ""})
        except Exception as e:  # noqa
            res.append({"name": name, "ok": False, "detail": str(e)[:200]})

    chk("Datenbank schreibbar", lambda: (db.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('selftest','1')") and "") or "ok")

    def disk():
        u = shutil.disk_usage(config.DATA_DIR); free = u.free / 1e9
        if free < 1:
            raise RuntimeError(f"nur noch {free:.1f} GB frei")
        return f"{free:.1f} GB frei"
    chk("Speicherplatz", disk)
    kc = {}

    def kl():
        kc["k"] = _sync._komoot(True); return f"angemeldet als {kc['k'].user_id}"
    chk("Komoot-Anmeldung", kl)
    if "k" in kc:
        def tl():
            n = len(kc["k"].tours()); return f"{n} Touren bei Komoot"
        chk("Komoot-Tourenliste", tl)

        def co():
            t = db.one("SELECT id,name FROM tours ORDER BY start_ts DESC LIMIT 1")
            if not t:
                raise RuntimeError("keine Tour geladen")
            p = kc["k"].coordinates(t["id"])
            if not p:
                raise RuntimeError("keine Streckenpunkte")
            return f"{len(p)} Punkte für „{t['name']}“"
        chk("Komoot-Strecke abrufen", co)
    if db.get("zepp_token"):
        def zp():
            st = _sync.check_zepp()
            if st != "ok":
                raise RuntimeError(st.replace("fail:", ""))
            return "Token gültig"
        chk("Zepp-Token", zp)
    chk("Kartenkacheln (Internet)", lambda: (requests.get(TILE_UP["osm"].format(z=1, x=0, y=0), headers=UA, timeout=8).raise_for_status() or "erreichbar"))
    chk("Wetterdienst (Internet)", lambda: (requests.get("https://api.open-meteo.com/v1/forecast?latitude=50&longitude=8&hourly=temperature_2m&forecast_days=1", headers=UA, timeout=8).raise_for_status() or "erreichbar"))
    chk("Höhendaten für 3D (Internet)", lambda: (requests.get("https://s3.amazonaws.com/elevation-tiles-prod/terrarium/0/0/0.png", headers=UA, timeout=8).raise_for_status() or "erreichbar"))

    def bk():
        d = config.backup_dirs(ctx.uid())[0]; fs = sorted(list(d.glob("meine-touren-*.zip")) + list(d.glob("komoot-hub-*.zip")), key=lambda f: f.stat().st_mtime) if d.exists() else []
        if not fs:
            raise RuntimeError("noch kein automatisches Backup vorhanden (läuft nachts um 03:40)")
        age = (time.time() - fs[-1].stat().st_mtime) / 3600
        return f"{len(fs)} Backups, letztes vor {age:.0f} Std."
    chk("Automatisches Backup", bk)
    chk("Fotobibliothek", lambda: f"{db.one('SELECT COUNT(*) n FROM photos')['n']} Fotos, Eingang: {config.INBOX_DIR}")
    return res


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
    guides = safe(guide_matches, pts) if part in ("all", "guides") else []
    if part == "guides":
        return [x for b, ti in (guides or []) for x in ((f"{ti} ({b})", ti) if b else (ti,)) if x != t["name"]]
    trails = (safe(trail_names, t, pts) or []) if part in ("all", "trails") else []   # zuerst: Overpass läuft, während Nominatim wartet
    a = safe(place_name, start[0], start[1])
    loop = _hav(start, end) < max(500, 0.15 * (t["dist_m"] or 0))
    b = None if loop or part != "all" and part != "places" else safe(place_name, end[0], end[1])
    f = safe(place_name, far[0], far[1]) if (part in ("all", "places") and loop and _hav(start, far) > 2500) else None
    pk = None
    if part in ("all", "peak") and hi is not None and start[2] is not None and hi[2] - start[2] >= 150 and t["sport"] in ("hike", "mountaineering", "skitour", "snowshoe", "nordicwalking", "skialpin"):
        pk = safe(peak_name, hi[0], hi[1])
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


# ---------- Wanderführer (z. B. Rother): Tourtitel aus eigenen GPX-Downloads ----------
from xml.etree import ElementTree as ET
from fastapi import Request


def _guide_parse(text, fallback):
    root = ET.fromstring(text)
    loc = lambda el: el.tag.split("}")[-1]
    pts, names = [], []
    for el in root.iter():
        n = loc(el)
        if n == "trkpt" or n == "rtept":
            try:
                pts.append((float(el.get("lat")), float(el.get("lon"))))
            except (TypeError, ValueError):
                pass
        elif n == "name" and (el.text or "").strip():
            names.append(el.text.strip())
    if len(pts) < 3:
        raise ValueError("keine Streckenpunkte")
    step = max(1, len(pts) // 400)
    title = next((x for x in names if not re.fullmatch(r"[\w\- ]*\.gpx", x, re.I)), None) or re.sub(r"\.gpx$", "", fallback, flags=re.I)
    return title, pts[::step] + ([pts[-1]] if step > 1 else [])


def _seg_dist(p, a, b):
    k = 111000.0
    cx = 0.65  # cos(~50°)
    px, py, ax, ay, bx, by = p[1] * k * cx, p[0] * k, a[1] * k * cx, a[0] * k, b[1] * k * cx, b[0] * k
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    u = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return ((px - ax - u * dx) ** 2 + (py - ay - u * dy) ** 2) ** 0.5


def _covered(samples, line, r):
    hit = 0
    for p in samples:
        for i in range(len(line) - 1):
            a = line[i]
            if abs(a[0] - p[0]) > 0.01 or abs(a[1] - p[1]) > 0.015:
                continue
            if _seg_dist(p, a, line[i + 1]) <= r:
                hit += 1; break
    return hit / max(1, len(samples))


def guide_matches(pts):
    gs = db.query("SELECT id,book,title,pts FROM guide_tours")
    if not gs or len(pts) < 5:
        return []
    n = min(40, len(pts))
    samp = [(pts[int(i * (len(pts) - 1) / max(1, n - 1))][0], pts[int(i * (len(pts) - 1) / max(1, n - 1))][1]) for i in range(n)]
    out = []
    for g in gs:
        line = json.loads(g["pts"])
        la, lo = [p[0] for p in line], [p[1] for p in line]
        if min(la) - 0.02 > max(s[0] for s in samp) or max(la) + 0.02 < min(s[0] for s in samp) or min(lo) - 0.03 > max(s[1] for s in samp) or max(lo) + 0.03 < min(s[1] for s in samp):
            continue
        c1 = _covered(samp, line, 80)                       # Anteil meiner Tour auf der Buchtour
        if c1 < 0.6:
            continue
        step = max(1, len(line) // 40)
        c2 = _covered(line[::step], [(p[0], p[1]) for p in pts], 120)   # Anteil der Buchtour, den ich gegangen bin
        if c2 >= 0.5:
            out.append((c1 * c2, g["book"], g["title"]))
    out.sort(reverse=True)
    return [(b, t) for _, b, t in out[:2]]


@router.get("/api/guides")
def api_guides():
    return db.query("SELECT id,book,title FROM guide_tours ORDER BY book,title")


@router.post("/api/guides")
async def api_guides_add(request: Request):
    data = await request.json()
    book = (data.get("book") or "").strip()[:80]
    ok, bad = 0, []
    for it in data.get("items") or []:
        try:
            title, pts = _guide_parse(it.get("gpx", ""), it.get("name", "Tour"))
            db.execute("INSERT INTO guide_tours(book,title,pts) VALUES(?,?,?)", (book, title[:200], json.dumps([[round(a, 5), round(b, 5)] for a, b in pts])))
            ok += 1
        except Exception as ex:  # noqa
            bad.append(f"{it.get('name', '?')}: {ex}")
    return {"added": ok, "failed": bad}


@router.delete("/api/guides/{gid}")
def api_guides_del(gid: str):
    if gid.startswith("book:"):
        db.execute("DELETE FROM guide_tours WHERE book=?", (gid[5:],))
    else:
        db.execute("DELETE FROM guide_tours WHERE id=?", (int(gid),))
    return {"ok": True}


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
