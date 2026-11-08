"""Wegpunkte mit Notiz (in der Android-App unterwegs gesetzt) und die Erzählung zu einer Tour."""
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from . import db

router = APIRouter()


def ensure():
    db.execute("CREATE TABLE IF NOT EXISTS tour_wps (id INTEGER PRIMARY KEY AUTOINCREMENT, tour_id TEXT, ts INTEGER, lat REAL, lng REAL, note TEXT)")
    db.execute("CREATE INDEX IF NOT EXISTS tour_wps_t ON tour_wps(tour_id)")


def _ts(s):
    try:
        return int(datetime.fromisoformat(s.strip().replace("Z", "+00:00")).astimezone(timezone.utc).timestamp())
    except Exception:  # noqa
        return 0


def from_gpx(gpx):
    """<wpt>-Einträge einer GPX-Datei als Liste (ts, lat, lng, note)."""
    out = []
    if "<wpt" not in gpx:
        return out
    try:
        root = ET.fromstring(gpx.encode("utf-8") if isinstance(gpx, str) else gpx)
    except ET.ParseError:
        return out
    for w in root.iter():
        if not w.tag.endswith("wpt"):
            continue
        try:
            la, lo = float(w.get("lat")), float(w.get("lon"))
        except (TypeError, ValueError):
            continue
        if not (-90 <= la <= 90 and -180 <= lo <= 180):
            continue
        name, t = "", 0
        for c in w:
            if c.tag.endswith("name"):
                name = (c.text or "").strip()
            elif c.tag.endswith("time"):
                t = _ts(c.text or "")
        out.append((t, la, lo, name[:200]))
    return out[:200]


def save(tour_id, wps):
    ensure()
    db.execute("DELETE FROM tour_wps WHERE tour_id=?", (tour_id,))
    for t, la, lo, n in wps:
        db.execute("INSERT INTO tour_wps(tour_id,ts,lat,lng,note) VALUES(?,?,?,?,?)", (tour_id, t, la, lo, n))


@router.get("/api/tours/{tour_id}/wps")
def api_wps(tour_id: str):
    ensure()
    return db.query("SELECT id,ts,lat,lng,note FROM tour_wps WHERE tour_id=? ORDER BY ts,id", (tour_id,))


@router.put("/api/tours/{tour_id}/wps/{wid}")
async def api_wps_put(tour_id: str, wid: int, request: Request):
    ensure()
    try:
        d = await request.json()
    except Exception:  # noqa
        raise HTTPException(400, "Ungültige Daten")
    note = re.sub(r"\s+", " ", str(d.get("note") or "")).strip()[:200]
    if not db.one("SELECT 1 FROM tour_wps WHERE id=? AND tour_id=?", (wid, tour_id)):
        raise HTTPException(404, "Wegpunkt nicht gefunden")
    db.execute("UPDATE tour_wps SET note=? WHERE id=?", (note, wid))
    return {"ok": True}


@router.delete("/api/tours/{tour_id}/wps/{wid}")
def api_wps_del(tour_id: str, wid: int):
    ensure()
    db.execute("DELETE FROM tour_wps WHERE id=? AND tour_id=?", (wid, tour_id))
    return {"ok": True}
