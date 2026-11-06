"""Touren planen: Strecke zeichnen oder laden, Höhenmeter aus dem Geländemodell, gespeicherte Pläne."""
import json
import threading
import time

import requests

from fastapi import APIRouter, HTTPException

from . import db, elev, config

router = APIRouter()
MAXPTS = 3000


def _pts(raw):
    out = []
    for p in raw or []:
        try:
            la, lo = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError):
            continue
        if -90 <= la <= 90 and -180 <= lo <= 180:
            out.append([round(la, 6), round(lo, 6)])
    return out


@router.post("/api/plan/elevation")
def api_plan_elevation(body: dict):
    """Geländehöhen für die Punkte einer geplanten Strecke (AWS Terrain Tiles) samt Auf- und Abstieg."""
    pts = _pts(body.get("points"))
    if len(pts) < 2:
        raise HTTPException(400, "Mindestens zwei Punkte nötig")
    if len(pts) > 2500:
        raise HTTPException(400, "Zu viele Punkte")
    try:
        ele = elev.smooth(elev.terrain([(p[0], p[1]) for p in pts]), 5, 3)
    except Exception as e:  # noqa
        raise HTTPException(502, f"Geländemodell nicht erreichbar: {e}")
    up, down = elev.ascent(ele, 4.0)
    return {"ele": [round(h, 1) for h in ele], "up": round(up), "down": round(down), "max": round(max(ele)), "min": round(min(ele))}


PROFILES = ("hiking-mountain", "trekking", "fastbike", "mtb", "gravel", "shortest")
BROUTER = "https://brouter.de/brouter"
UA = {"User-Agent": "MeineTouren/1.0 (privates Selbsthosting; https://github.com/hilde0407/meine-touren)"}
_RC, _RL = {}, threading.Lock()


def _brouter_url():
    return (db.get("brouter_url") or "").strip().rstrip("/") or BROUTER


@router.post("/api/plan/route")
def api_plan_route(body: dict):
    """Verbindet zwei Punkte über bekannte Wege (OpenStreetMap, BRouter). alt = 0 … 3: Alternativrouten."""
    a, b = _pts([body.get("a")]), _pts([body.get("b")])
    if not a or not b:
        raise HTTPException(400, "Start und Ziel angeben")
    prof = body.get("profile") if body.get("profile") in PROFILES else "hiking-mountain"
    try:
        alt = max(0, min(3, int(body.get("alt") or 0)))
    except (TypeError, ValueError):
        alt = 0
    key = (tuple(a[0]), tuple(b[0]), prof, alt, _brouter_url())
    with _RL:
        if key in _RC:
            return _RC[key]
    try:
        r = requests.get(_brouter_url(), params={"lonlats": f"{a[0][1]},{a[0][0]}|{b[0][1]},{b[0][0]}", "profile": prof, "alternativeidx": alt, "format": "geojson"}, headers=UA, timeout=25)
    except requests.RequestException as e:
        raise HTTPException(502, f"Routing-Dienst nicht erreichbar: {e.__class__.__name__}")
    if r.status_code != 200:
        raise HTTPException(502, (r.text or f"HTTP {r.status_code}")[:160].strip())
    try:
        f = r.json()["features"][0]
        co = f["geometry"]["coordinates"]
        pr = f.get("properties") or {}
        pts = [[round(c[1], 6), round(c[0], 6), round(c[2], 1) if len(c) > 2 and c[2] is not None else None] for c in co]
        out = {"pts": pts, "km": round(float(pr.get("track-length") or 0) / 1000, 3), "up": round(float(pr.get("filtered ascend") or 0)), "time_s": int(float(pr.get("total-time") or 0)), "alt": alt}
    except (ValueError, KeyError, IndexError, TypeError):
        raise HTTPException(502, "Unerwartete Antwort des Routing-Dienstes")
    if len(pts) < 2:
        raise HTTPException(502, "Keine Route gefunden")
    with _RL:
        if len(_RC) > 800:
            _RC.clear()
        _RC[key] = out
    return out


@router.get("/api/plan/guide/{gid}")
def api_plan_guide(gid: int):
    g = db.one("SELECT id,book,title,pts FROM guide_tours WHERE id=?", (gid,))
    if not g:
        raise HTTPException(404, "Wanderführer-Tour nicht gefunden")
    return {"id": g["id"], "title": g["title"], "book": g["book"] or "", "pts": _pts(json.loads(g["pts"]))}


@router.get("/api/plans")
def api_plans():
    return db.query("SELECT id,name,sport,km,up,down,max_alt,est_h,note,ts FROM plans ORDER BY ts DESC")


@router.get("/api/plans/{pid}")
def api_plan_get(pid: int):
    r = db.one("SELECT * FROM plans WHERE id=?", (pid,))
    if not r:
        raise HTTPException(404, "Plan nicht gefunden")
    r["pts"] = json.loads(r["pts"])
    try:
        r["wps"] = json.loads(r["wps"]) if r.get("wps") else None
    except ValueError:
        r["wps"] = None
    return r


@router.post("/api/plans")
def api_plan_save(body: dict):
    pts = _pts(body.get("pts"))
    if len(pts) < 2:
        raise HTTPException(400, "Der Plan braucht mindestens zwei Punkte")
    if len(pts) > MAXPTS:
        step = len(pts) / MAXPTS
        pts = [pts[int(i * step)] for i in range(MAXPTS)] + [pts[-1]]
    name = str(body.get("name") or "").strip()[:120] or "Neue Planung"

    def num(k):
        try:
            return float(body[k]) if body.get(k) is not None else None
        except (TypeError, ValueError):
            return None
    wps = body.get("wps")
    wps = json.dumps(wps)[:60000] if isinstance(wps, dict) else None
    vals = (name, str(body.get("sport") or "hike")[:30], json.dumps(pts), num("km"), num("up"), num("down"), num("max_alt"), num("est_h"), str(body.get("note") or "")[:1000], int(time.time()), wps)
    pid = body.get("id")
    if pid and db.one("SELECT 1 FROM plans WHERE id=?", (int(pid),)):
        db.execute("UPDATE plans SET name=?,sport=?,pts=?,km=?,up=?,down=?,max_alt=?,est_h=?,note=?,ts=?,wps=? WHERE id=?", vals + (int(pid),))
        return {"id": int(pid)}
    return {"id": db.execute("INSERT INTO plans(name,sport,pts,km,up,down,max_alt,est_h,note,ts,wps) VALUES(?,?,?,?,?,?,?,?,?,?,?)", vals)}


@router.delete("/api/plans/{pid}")
def api_plan_del(pid: int):
    db.execute("DELETE FROM plans WHERE id=?", (pid,))
    return {"ok": True}
