"""Wanderführer (z. B. Rother): Tourtitel aus eigenen GPX-Downloads erkennen.

Ein Buch liegt als ZIP mit GPX-Dateien vor. Daraus merkt sich die App Name, Länge und
Streckenverlauf jeder Buchtour und erkennt später, welche eigene Tour dazu passt.
"""
import re
import json
import zipfile
from xml.etree import ElementTree as ET

from fastapi import APIRouter, HTTPException, Request

from . import db

router = APIRouter()


def _hav(a, b):
    from . import extras
    return extras._hav(a, b)


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


def guide_stats(text, pts):
    """Länge (km) aus den Punkten, Aufstieg (m) aus den Höhenangaben der GPX-Datei (None, falls keine vorhanden)."""
    import math
    km = 0.0
    for a, b in zip(pts, pts[1:]):
        dy = (b[0] - a[0]) * 111.2
        dx = (b[1] - a[1]) * 111.2 * math.cos(math.radians((a[0] + b[0]) / 2))
        km += (dx * dx + dy * dy) ** 0.5
    up = None
    try:
        els = []
        for el in ET.fromstring(text).iter():
            if el.tag.split("}")[-1] in ("trkpt", "rtept"):
                for ch in el:
                    if ch.tag.split("}")[-1] == "ele" and ch.text:
                        els.append(float(ch.text))
        if len(els) >= 3:
            sm = [sum(els[max(0, i - 2):i + 3]) / len(els[max(0, i - 2):i + 3]) for i in range(len(els))]
            up, ref = 0.0, sm[0]
            for v in sm[1:]:                       # Schwelle 3 m gegen Rauschen
                if v - ref >= 3:
                    up += v - ref; ref = v
                elif ref - v >= 3:
                    ref = v
    except Exception:  # noqa
        up = None
    return round(km, 2), (round(up) if up is not None else None)


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
            km, up = guide_stats(it.get("gpx", ""), pts)
            db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES(?,?,?,?,?)", (book, title[:200], json.dumps([[round(a, 5), round(b, 5)] for a, b in pts]), km, up))
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
