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


# ---------- Kommentare zu Fotos (in der Erzählung) ----------
def _author(request):
    u = getattr(request.state, "user", None)
    return (u or {}).get("name") or ""


@router.get("/api/tours/{tour_id}/comments")
def api_tour_comments(tour_id: str):
    """Alle Kommentare zu den Fotos einer Tour: {Foto-ID: [{id, ts, author, text}, …]}."""
    out = {}
    for r in db.query("SELECT c.id,c.photo_id,c.ts,c.author,c.text FROM photo_comments c JOIN photos p ON p.id=c.photo_id WHERE p.tour_id=? ORDER BY c.ts,c.id", (tour_id,)):
        out.setdefault(str(r["photo_id"]), []).append({"id": r["id"], "ts": r["ts"], "author": r["author"], "text": r["text"]})
    return out


@router.get("/api/photos/{pid}/comments")
def api_photo_comments(pid: int):
    return db.query("SELECT id,ts,author,text FROM photo_comments WHERE photo_id=? ORDER BY ts,id", (pid,))


@router.post("/api/photos/{pid}/comments")
async def api_photo_comment_add(pid: int, request: Request):
    import time
    try:
        d = await request.json()
    except Exception:  # noqa
        raise HTTPException(400, "Ungültige Daten")
    text = str(d.get("text") or "").strip()[:1000]
    if not text:
        raise HTTPException(400, "Bitte einen Kommentar eingeben")
    if not db.one("SELECT 1 FROM photos WHERE id=?", (pid,)):
        raise HTTPException(404, "Tour oder Foto nicht gefunden")
    n = db.one("SELECT COUNT(*) n FROM photo_comments WHERE photo_id=?", (pid,))["n"]
    if n >= 200:
        raise HTTPException(400, "Zu viele Daten auf einmal")
    ts = int(time.time())
    db.execute("INSERT INTO photo_comments(photo_id,ts,author,text) VALUES(?,?,?,?)", (pid, ts, _author(request), text))
    row = db.one("SELECT id,ts,author,text FROM photo_comments WHERE photo_id=? ORDER BY id DESC LIMIT 1", (pid,))
    return row


@router.delete("/api/comments/{cid}")
def api_comment_del(cid: int):
    db.execute("DELETE FROM photo_comments WHERE id=?", (cid,))
    return {"ok": True}


@router.get("/api/place")
def api_place(lat: float, lng: float):
    """Ortsname zu einer Koordinate (für die Erzählung); bei Fehlern/ohne Internet einfach leer."""
    from . import extras
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise HTTPException(400, "Ungültige Daten")
    try:
        return {"name": extras.place_name(lat, lng)}
    except Exception:  # noqa
        return {"name": None}


@router.get("/api/geo/search")
def api_geo_search(q: str):
    """Ortssuche (OpenStreetMap/Nominatim) für den Heimatort: bis zu 5 Treffer mit Name und Koordinaten."""
    import time as _t
    import requests
    from . import extras
    q = " ".join(q.split())[:120]
    if len(q) < 2:
        raise HTTPException(400, "Bitte einen Ort eingeben")
    with extras._geo_lock:
        wait = 1.1 - (_t.time() - extras._last_geo[0])
        if wait > 0:
            _t.sleep(wait)
        extras._last_geo[0] = _t.time()
        try:
            r = requests.get("https://nominatim.openstreetmap.org/search", headers=extras.UA, timeout=10,
                             params={"q": q, "format": "jsonv2", "limit": 5, "accept-language": "de", "addressdetails": 0})
        except Exception as e:  # noqa
            raise HTTPException(502, f"Ortssuche nicht erreichbar: {e}")
    if r.status_code != 200:
        raise HTTPException(502, f"Ortssuche: HTTP {r.status_code}")
    return [{"name": e.get("display_name", ""), "lat": float(e["lat"]), "lng": float(e["lon"])} for e in r.json()]
