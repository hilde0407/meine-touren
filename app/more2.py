"""Tags/Alben, Reisen, Sammlungen, Offline-Kacheln, Wetter- und Neuland-Auswertung, Teilen, Benachrichtigung."""
import hashlib
from pathlib import Path
import json
import secrets
import statistics
import threading
import time
from datetime import datetime
from math import cos, floor, radians

import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from . import auth, config, ctx, db, extras, jobs, memo, more, photos, routes
from .gpxtools import TZ

router = APIRouter()


def _ids(s):
    return [x for x in (s or "").split(",") if x][:400]


# ---------- Tags / Alben ----------
def cover_photo(tour_ids):
    """Titelfoto für eine Sammlung: das mittlere Foto (nach Aufnahmezeit) aus den zugehörigen Touren."""
    if not tour_ids:
        return None
    ph = db.query("SELECT id FROM photos WHERE tour_id IN (%s) ORDER BY taken_ts, id" % ",".join("?" * len(tour_ids)), tuple(tour_ids))
    return ph[len(ph) // 2]["id"] if ph else None


@router.get("/api/tags")
def api_tags():
    rows = db.query("SELECT x.tag AS tag, COUNT(*) AS n, ROUND(SUM(t.dist_m)/1000.0,0) AS km FROM tour_tags x JOIN tours t ON t.id=x.id GROUP BY x.tag ORDER BY n DESC, tag")
    for r in rows:
        r["photo"] = cover_photo([x["id"] for x in db.query("SELECT id FROM tour_tags WHERE tag=?", (r["tag"],))])
    return rows


@router.post("/api/tours/{tour_id}/tags")
async def api_set_tags(tour_id: str, request: Request):
    tags = []
    for x in (await request.json()).get("tags") or []:
        x = str(x).replace("|", " ").strip()[:40]
        if x and x not in tags:
            tags.append(x)
    with db.cur() as c:
        c.execute("DELETE FROM tour_tags WHERE id=?", (tour_id,))
        c.executemany("INSERT OR IGNORE INTO tour_tags(id,tag) VALUES(?,?)", [(tour_id, x) for x in tags[:20]])
    return {"tags": tags}


# ---------- Reisen ----------
def build_trips():
    tours = db.query("SELECT t.*, g.state AS g_state, g.country AS g_country, g.place AS g_place FROM tours t LEFT JOIN tour_geo g ON g.id=t.id "
                     "WHERE t.start_ts IS NOT NULL AND t.lat IS NOT NULL ORDER BY t.start_ts")
    if len(tours) < 3:
        return []
    hl, hn = statistics.median(t["lat"] for t in tours), statistics.median(t["lng"] for t in tours)
    away = [t for t in tours if extras._hav((hl, hn), (t["lat"], t["lng"])) > 60000]
    groups, cur = [], []
    day = lambda t: datetime.fromtimestamp(t["start_ts"], tz=TZ).date()
    for t in away:
        if cur and (day(t) - day(cur[-1])).days > 1:
            groups.append(cur); cur = []
        cur.append(t)
    if cur:
        groups.append(cur)
    out = []
    for g in groups:
        days = {day(t) for t in g}
        if len(g) < 2 and len(days) < 2:
            continue
        regs = [t["g_state"] or t["g_country"] or t["g_place"] for t in g if t["g_state"] or t["g_country"] or t["g_place"]]
        reg = max(set(regs), key=regs.count) if regs else "Reise"
        d0, d1 = min(days), max(days)
        out.append({"id": g[0]["id"], "region": reg, "country": next((t["g_country"] for t in g if t["g_country"]), None), "start": d0.isoformat(), "end": d1.isoformat(),
                    "days": (d1 - d0).days + 1, "tours": [t["id"] for t in g], "km": round(sum(t["dist_m"] or 0 for t in g) / 1000, 1),
                    "up_m": round(sum(t["up_m"] or 0 for t in g)), "h": round(sum(t["dur_s"] or 0 for t in g) / 3600, 1)})
    return sorted(out, key=lambda x: x["start"], reverse=True)


@router.get("/api/trips")
def api_trips():
    out = build_trips()
    for t in out:
        t["photo"] = cover_photo(t["tours"])
    return out


@router.get("/api/collection/coords")
def api_collection_coords(ids: str):
    ts = db.query("SELECT id FROM tours WHERE id IN (%s) ORDER BY start_ts" % ",".join("?" * len(_ids(ids))), tuple(_ids(ids))) if _ids(ids) else []
    pts = []
    for t in ts:
        pts += [p for p in (routes.load(t["id"]) or []) if p and p[0] is not None and p[1] is not None]
    step = max(1, len(pts) // 3000)
    return pts[::step]


# ---------- Offline-Kacheln für eine Sammlung (bewusst klein gehalten: Nutzungsbedingungen der Kartenserver) ----------
def plan_tiles(ids, zs=(11, 12, 13, 14), cap=1500):
    from math import log, pi, tan
    tiles = set()
    for tid in ids:
        for p in routes.load(tid) or []:
            if p[0] is None:
                continue
            for z in zs:
                n = 2 ** z
                x = int((p[1] + 180) / 360 * n); y = int((1 - log(tan(radians(p[0])) + 1 / cos(radians(p[0]))) / pi) / 2 * n)
                tiles.add((z, x, y))
    return sorted(tiles, key=lambda t: (t[0], t[1], t[2]))[:cap] if len(tiles) <= cap else sorted(tiles, key=lambda t: (-abs(t[0] - 12), t[0]))[:cap]


def prefetch(ids):
    todo = [t for t in plan_tiles(ids) if not (extras.TILE_DIR / "osm" / str(t[0]) / str(t[1]) / f"{t[2]}.png").exists()]
    jobs.log(f"Offline-Karte: {len(todo)} Kacheln")
    ok = 0
    for i, (z, x, y) in enumerate(todo, 1):
        jobs.progress(f"Kacheln {i}/{len(todo)}")
        try:
            r = requests.get(extras.TILE_UP["osm"].format(z=z, x=x, y=y), headers=extras.UA, timeout=10)
            if r.status_code != 200:
                raise RuntimeError(f"HTTP {r.status_code}")
            f = extras.TILE_DIR / "osm" / str(z) / str(x) / f"{y}.png"
            f.parent.mkdir(parents=True, exist_ok=True); f.write_bytes(r.content); ok += 1
        except Exception as e:  # noqa
            jobs.log(f"  Kacheln: {e} – Abbruch"); break
        time.sleep(1.0)
    jobs.log(f"Offline-Karte: {ok} Kacheln gespeichert")


@router.get("/api/tiles/plan")
def api_tiles_plan(ids: str):
    ids = _ids(ids)
    total = len(plan_tiles(ids)); todo = len([t for t in plan_tiles(ids) if not (extras.TILE_DIR / "osm" / str(t[0]) / str(t[1]) / f"{t[2]}.png").exists()])
    return {"total": total, "missing": todo}


@router.post("/api/tiles/prefetch")
async def api_tiles_prefetch(request: Request):
    ids = _ids(",".join((await request.json()).get("ids") or []))
    if not jobs.start("Offline-Karte laden", prefetch, ids):
        raise HTTPException(409, "Es läuft bereits ein Job")
    return {"started": True}


# ---------- Wetter-Auswertung ----------
@router.get("/api/weather/stats")
def api_weather_stats():
    rows = db.query("SELECT w.id, w.js, t.start_ts, t.sport, t.name FROM weather w JOIN tours t ON t.id=w.id")
    out = []
    for r in rows:
        try:
            w = json.loads(r["js"])
            out.append({"id": r["id"], "name": r["name"], "start_ts": r["start_ts"], "sport": r["sport"], "tmin": w["tmin"], "tmax": w["tmax"], "precip": w["precip"], "wind": w["wind"], "code": w["code"], "text": w["text"]})
        except Exception:  # noqa
            pass
    return {"rows": out, "missing": db.one("SELECT COUNT(*) n FROM tours WHERE lat IS NOT NULL AND id NOT IN (SELECT id FROM weather)")["n"]}


def weather_fill(limit=None):
    todo = db.query("SELECT * FROM tours WHERE lat IS NOT NULL AND start_ts IS NOT NULL AND id NOT IN (SELECT id FROM weather) ORDER BY start_ts DESC")
    if limit:
        todo = todo[:limit]
    ok = 0
    for i, t in enumerate(todo, 1):
        jobs.progress(f"Wetter {i}/{len(todo)}")
        try:
            w = extras.fetch_weather(t)
        except Exception as e:  # noqa
            jobs.log(f"  Wetter: {e}"); 
            if "HTTP 429" in str(e):
                break
            continue
        db.execute("INSERT OR REPLACE INTO weather(id,js,ts) VALUES(?,?,?)", (t["id"], json.dumps(w), int(time.time())))
        ok += 1
        time.sleep(0.4)
    jobs.log(f"Wetter: {ok} geladen")
    return ok


# ---------- Neuland: welcher Anteil der Strecke war neu? ----------
_NG = {"key": None, "val": None}


def newground():
    tours = db.query("SELECT id,start_ts,dist_m FROM tours WHERE start_ts IS NOT NULL ORDER BY start_ts")
    files = sum(1 for _ in routes.D.glob("*.json")) if routes.D.exists() else 0
    key = (len(tours), files, tours[-1]["id"] if tours else None)
    if _NG["key"] == key:
        return _NG["val"]
    seen, res = set(), {}
    for t in tours:
        pts = [p for p in (routes.load(t["id"]) or []) if p and p[0] is not None]
        if len(pts) < 3:
            continue
        mine, total, new = set(), 0.0, 0.0
        for a, b in zip(pts, pts[1:]):
            d = extras._hav((a[0], a[1]), (b[0], b[1]))
            if d <= 0:
                continue
            n = max(1, int(d / 30)); seg = d / n
            for i in range(n):
                la, lo = a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n
                cy, cx = floor(la / 0.0004), floor(lo / (0.0004 / max(0.2, cos(radians(la)))))
                total += seg
                if not any((cy + dy, cx + dx) in seen for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                    new += seg
                mine.add((cy, cx))
        seen |= mine
        if total > 0:
            res[t["id"]] = {"new_km": round(new / 1000, 2), "km": round(total / 1000, 2), "pct": round(100 * new / total)}
    years = {}
    for t in tours:
        r = res.get(t["id"])
        if r:
            y = str(datetime.fromtimestamp(t["start_ts"], tz=TZ).year)
            d = years.setdefault(y, {"new_km": 0, "km": 0}); d["new_km"] += r["new_km"]; d["km"] += r["km"]
    val = {"tours": res, "years": {y: {"new_km": round(v["new_km"], 1), "km": round(v["km"], 1)} for y, v in sorted(years.items())}}
    _NG["key"], _NG["val"] = key, val
    return val


@router.get("/api/newground")
@memo.cached
def api_newground():
    return newground()


# ---------- Teilen ----------
def _trim(pts, meters=300):
    if len(pts) < 10:
        return pts
    s, e = pts[0], pts[-1]
    out = [p for p in pts if extras._hav((s[0], s[1]), (p[0], p[1])) > meters and extras._hav((e[0], e[1]), (p[0], p[1])) > meters]
    return out if len(out) > 5 else pts[len(pts) // 4: -len(pts) // 4]


@router.post("/api/tours/{tour_id}/share")
async def api_share(tour_id: str, request: Request):
    if not db.one("SELECT 1 FROM tours WHERE id=?", (tour_id,)):
        raise HTTPException(404)
    d = await request.json()
    token = secrets.token_urlsafe(12)
    db.execute("INSERT INTO shares(token,tour_id,photos,trim,ts) VALUES(?,?,?,?,?)", (token, tour_id, 1 if d.get("photos") else 0, 0 if d.get("trim") is False else 1, int(time.time())))
    auth.q("INSERT OR REPLACE INTO share_index(token,uid) VALUES(?,?)", (token, ctx.uid() or ""))
    return {"token": token, "url": f"/s/{token}"}


@router.get("/api/tours/{tour_id}/shares")
def api_shares(tour_id: str):
    return db.query("SELECT token,photos,trim,ts FROM shares WHERE tour_id=? ORDER BY ts DESC", (tour_id,))


@router.delete("/api/share/{token}")
def api_share_del(token: str):
    db.execute("DELETE FROM shares WHERE token=?", (token,))
    auth.q("DELETE FROM share_index WHERE token=? AND uid=?", (token, ctx.uid() or ""))
    return {"ok": True}


def _share(token):
    from . import auth
    idx = auth.q1("SELECT uid FROM share_index WHERE token=?", (token,))
    if idx:
        ctx._uid.set(idx["uid"] or None)          # ab hier arbeitet die Anfrage mit den Daten des Besitzers
    elif auth.users_exist():
        raise HTTPException(404, "Link nicht (mehr) gültig")
    s = db.one("SELECT * FROM shares WHERE token=?", (token,))
    if not s:
        raise HTTPException(404, "Link nicht (mehr) gültig")
    return s


@router.get("/s/{token}")
def share_page(token: str):
    _share(token)
    return FileResponse(Path(__file__).parent / "static" / "share.html", media_type="text/html", headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@router.get("/api/public/{token}")
def api_public(token: str):
    s = _share(token)
    t = db.one("SELECT * FROM tours WHERE id=?", (s["tour_id"],))
    pts = [p for p in (routes.load(t["id"]) or []) if p and p[0] is not None]
    if s["trim"]:
        pts = _trim(pts)
    ph = db.query("SELECT id,taken_ts FROM photos WHERE tour_id=? AND manual!=2 ORDER BY taken_ts LIMIT 60", (t["id"],)) if s["photos"] else []
    return {"name": t["name"], "sport": t["sport"], "date": datetime.fromtimestamp(t["start_ts"], tz=TZ).isoformat(), "km": round((t["dist_m"] or 0) / 1000, 1),
            "up_m": round(t["up_m"] or 0), "down_m": round(t["down_m"] or 0), "h": round((t["dur_s"] or 0) / 3600, 1),
            "coords": [[round(p[0], 5), round(p[1], 5), p[2]] for p in pts[::max(1, len(pts) // 800)]], "photos": [p["id"] for p in ph]}


@router.get("/pub/{token}/photo/{pid}")
def public_photo(token: str, pid: int, size: int = 1400):
    s = _share(token)
    if not s["photos"] or not db.one("SELECT 1 FROM photos WHERE id=? AND tour_id=? AND manual!=2", (pid, s["tour_id"])):
        raise HTTPException(404)
    p = photos.thumb(pid, max(120, min(size, 2000)))
    if not p:
        raise HTTPException(404)
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


PUBLIC_PREFIXES = ("/s/", "/api/public/", "/pub/", "/vendor/", "/tiles/")


# ---------- Benachrichtigung (freier Webhook, standardmäßig aus) ----------
def notify_send(text, title="Meine Touren"):
    url = (db.get("notify_url") or "").strip()
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("Keine gültige Webhook-Adresse eingetragen")
    r = requests.post(url, data=text.encode("utf-8"), headers={"Title": title, "Content-Type": "text/plain; charset=utf-8"}, timeout=10)
    if r.status_code >= 300:
        raise RuntimeError(f"Webhook: HTTP {r.status_code}")


def notify_check():
    if not (db.get("notify_url") or "").strip():
        return False
    w = [x["text"] for x in more.api_health()]
    h = hashlib.md5("|".join(w).encode()).hexdigest() if w else ""
    if h == (db.get("notify_last") or ""):
        return False
    notify_send("\n".join(w) if w else "Alles wieder in Ordnung.")
    db.put("notify_last", h)
    return True


@router.post("/api/notify/test")
def api_notify_test():
    try:
        notify_send("Testnachricht von Meine Touren")
        return {"ok": True}
    except Exception as e:  # noqa
        raise HTTPException(502, str(e))
