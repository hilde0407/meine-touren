"""Ausrüstung (Rad, Schuhe, Ski …) mit Kilometer-/Höhenmeter-Summen und Verschleiß-Hinweis."""
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException

from . import db

router = APIRouter()
KINDS = ("Rad", "Schuhe", "Ski", "Schneeschuhe", "Sonstiges")


def _day(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d") if ts else ""


def _sports(g):
    return [s for s in (g["sports"] or "").split(",") if s]


def _matches(g, t):
    """Standard-Zuordnung: Sportart passt und Datum liegt im Nutzungszeitraum."""
    if t["sport"] not in _sports(g):
        return False
    d = _day(t["start_ts"])
    return (not g["since"] or d >= g["since"]) and (not g["until"] or d <= g["until"])


def _assignments(gears, tours):
    """{tour_id: [gear_id]} – ausdrückliche Wahl hat Vorrang, sonst die Standard-Regel."""
    explicit = {}
    for r in db.query("SELECT tour_id, gear_id FROM tour_gear"):
        explicit.setdefault(r["tour_id"], []).append(r["gear_id"])
    out = {}
    for t in tours:
        if t["id"] in explicit:
            out[t["id"]] = [g for g in explicit[t["id"]] if g]
        else:
            out[t["id"]] = [g["id"] for g in gears if _matches(g, t)]
    return out


@router.get("/api/gear")
def api_gear():
    gears = db.query("SELECT * FROM gear ORDER BY (until IS NOT NULL AND until!=''), kind, name")
    tours = db.query("SELECT id, sport, start_ts, dist_m, up_m, dur_s FROM tours")
    by = {t["id"]: t for t in tours}
    asg = _assignments(gears, tours)
    tot = {g["id"]: {"km": 0.0, "up": 0.0, "h": 0.0, "n": 0, "last": 0} for g in gears}
    for tid, ids in asg.items():
        t = by[tid]
        for gid in ids:
            if gid in tot:
                s = tot[gid]
                s["km"] += (t["dist_m"] or 0) / 1000
                s["up"] += t["up_m"] or 0
                s["h"] += (t["dur_s"] or 0) / 3600
                s["n"] += 1
                s["last"] = max(s["last"], t["start_ts"] or 0)
    out = []
    for g in gears:
        s = tot[g["id"]]
        lim = g["limit_km"] or 0
        st = "" if not lim else "over" if s["km"] >= lim else "soon" if s["km"] >= 0.9 * lim else "ok"
        out.append({"id": g["id"], "name": g["name"], "kind": g["kind"], "sports": _sports(g), "since": g["since"] or "", "until": g["until"] or "",
                    "limit_km": lim or None, "note": g["note"] or "", "km": round(s["km"], 1), "up": round(s["up"]), "h": round(s["h"], 1),
                    "n": s["n"], "last": s["last"], "status": st})
    return out


@router.post("/api/gear")
def api_gear_save(body: dict):
    name = str(body.get("name") or "").strip()[:80]
    if not name:
        raise HTTPException(400, "Bitte einen Namen eingeben")
    kind = body.get("kind") if body.get("kind") in KINDS else "Sonstiges"
    sports = ",".join(s for s in (body.get("sports") or []) if isinstance(s, str) and s.replace("_", "").isalnum())
    try:
        lim = float(body.get("limit_km") or 0) or None
    except (TypeError, ValueError):
        raise HTTPException(400, "Kilometer-Grenze ist keine Zahl")
    since, until = str(body.get("since") or "")[:10], str(body.get("until") or "")[:10]
    vals = (name, kind, sports, since, until, lim, str(body.get("note") or "")[:300])
    gid = body.get("id")
    if gid:
        if not db.one("SELECT 1 FROM gear WHERE id=?", (int(gid),)):
            raise HTTPException(404, "Ausrüstung nicht gefunden")
        db.execute("UPDATE gear SET name=?,kind=?,sports=?,since=?,until=?,limit_km=?,note=? WHERE id=?", vals + (int(gid),))
        return {"id": int(gid)}
    return {"id": db.execute("INSERT INTO gear(name,kind,sports,since,until,limit_km,note) VALUES(?,?,?,?,?,?,?)", vals)}


@router.delete("/api/gear/{gid}")
def api_gear_delete(gid: int):
    db.execute("DELETE FROM tour_gear WHERE gear_id=?", (gid,))
    db.execute("DELETE FROM gear WHERE id=?", (gid,))
    return {"ok": True}


@router.get("/api/tours/{tour_id}/gear")
def api_tour_gear(tour_id: str):
    t = db.one("SELECT id, sport, start_ts FROM tours WHERE id=?", (tour_id,))
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    gears = db.query("SELECT * FROM gear ORDER BY kind, name")
    explicit = [r["gear_id"] for r in db.query("SELECT gear_id FROM tour_gear WHERE tour_id=?", (tour_id,))]
    ids = [g for g in explicit if g] if explicit else [g["id"] for g in gears if _matches(g, t)]
    return {"ids": ids, "auto": not explicit, "all": [{"id": g["id"], "name": g["name"], "kind": g["kind"]} for g in gears]}


@router.post("/api/tours/{tour_id}/gear")
def api_tour_gear_set(tour_id: str, body: dict):
    if not db.one("SELECT 1 FROM tours WHERE id=?", (tour_id,)):
        raise HTTPException(404, "Tour nicht gefunden")
    db.execute("DELETE FROM tour_gear WHERE tour_id=?", (tour_id,))
    if body.get("auto"):
        return {"ok": True}
    ids = [int(i) for i in body.get("ids") or [] if db.one("SELECT 1 FROM gear WHERE id=?", (int(i),))]
    for gid in ids or [0]:                         # 0 = ausdrücklich „keine Ausrüstung“
        db.execute("INSERT OR IGNORE INTO tour_gear(tour_id,gear_id) VALUES(?,?)", (tour_id, gid))
    return {"ok": True}
