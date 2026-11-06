"""Touren planen: Strecke zeichnen oder laden, Höhenmeter aus dem Geländemodell, gespeicherte Pläne."""
import json
import time

from fastapi import APIRouter, HTTPException

from . import db, elev

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
    vals = (name, str(body.get("sport") or "hike")[:30], json.dumps(pts), num("km"), num("up"), num("down"), num("max_alt"), num("est_h"), str(body.get("note") or "")[:1000], int(time.time()))
    pid = body.get("id")
    if pid and db.one("SELECT 1 FROM plans WHERE id=?", (int(pid),)):
        db.execute("UPDATE plans SET name=?,sport=?,pts=?,km=?,up=?,down=?,max_alt=?,est_h=?,note=?,ts=? WHERE id=?", vals + (int(pid),))
        return {"id": int(pid)}
    return {"id": db.execute("INSERT INTO plans(name,sport,pts,km,up,down,max_alt,est_h,note,ts) VALUES(?,?,?,?,?,?,?,?,?,?)", vals)}


@router.delete("/api/plans/{pid}")
def api_plan_del(pid: int):
    db.execute("DELETE FROM plans WHERE id=?", (pid,))
    return {"ok": True}
