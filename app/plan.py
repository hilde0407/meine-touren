"""Touren planen: Strecke zeichnen oder laden, Aufstieg aus dem Geländemodell, gespeicherte Pläne."""
import json
import re
import threading
import time

import requests

from fastapi import APIRouter, Depends, HTTPException, Request

from . import db, elev, config, gpxtools, routes, planhilfe

def _gate(request: Request):
    """Ist die Tourplanung ausgeschaltet, antwortet die ganze Planungs-Schnittstelle mit 403 (außer dem Verbindungstest der Einstellungen)."""
    if request.url.path != "/api/plan/test" and not enabled():
        raise HTTPException(403, "Die Tourplanung ist in den Einstellungen ausgeschaltet")


router = APIRouter(dependencies=[Depends(_gate)])
tour_router = APIRouter()                      # 3.39.0: nur lesend, ohne _gate (auch ein bestehendes Ergebnis bleibt sichtbar, wenn „Tour planen“ ausgeschaltet wird)
MAXPTS = 3000
MAXLINE = 400                                  # längste Linie in der Soll/Ist-Karte der Tourseite


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


def enabled():
    return (db.get("plan_enabled") or "1") != "0"


def _brouter_url():
    own = (db.get("brouter_url") or "").strip().rstrip("/")
    mode = db.get("plan_mode") or ""
    if mode == "public" or not own:
        return BROUTER
    return own


@router.post("/api/plan/test")
def api_plan_test(body: dict):
    """Prüft, ob unter der Adresse ein BRouter antwortet (leer = aktuell eingestellte Adresse)."""
    url = (body.get("url") or "").strip().rstrip("/")
    if url and not url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "Die Adresse muss mit http:// oder https:// beginnen")
    url = url or _brouter_url()
    try:
        r = requests.get(url, params={"lonlats": "8.4037,49.0069|8.4137,49.0119", "profile": "trekking", "alternativeidx": 0, "format": "geojson"}, headers=UA, timeout=12)
    except Exception as e:
        return {"ok": False, "msg": f"Keine Verbindung zu {url}: {str(e)[:120]}"}
    txt = (r.text or "")[:300]
    if r.status_code == 200 and '"features"' in txt + r.text[:2000]:
        return {"ok": True, "msg": "BRouter antwortet, Routen werden berechnet ✓"}
    if "datafile" in txt and "not found" in txt:
        m = re.search(r"datafile (\S+)", txt)
        return {"ok": True, "warn": True, "msg": f"BRouter läuft, aber die Karten-Kachel {m.group(1) if m else ''} fehlt noch (bei Test-Punkten in Karlsruhe). Für andere Regionen ist das normal; nötige Kacheln mit install-brouter.sh nachladen."}
    return {"ok": False, "msg": f"Unerwartete Antwort ({r.status_code}): {txt[:150]}"}


@router.post("/api/plan/route")
def api_plan_route(body: dict):
    """Verbindet zwei Punkte über bekannte Wege (OpenStreetMap, BRouter). alt = 0 … 3: Alternativrouten."""
    if not enabled():
        raise HTTPException(403, "Die Tourplanung ist in den Einstellungen ausgeschaltet")
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


@router.post("/api/plan/check")
def api_plan_check(body: dict):
    """Machbarkeits-Check: geplante Strecke gegen die eigenen Touren der letzten 12 Monate (nur lesend)."""
    from . import plan_check
    try:
        return plan_check.check(body)
    except ValueError as e:
        raise HTTPException(400, str(e))


def _plan_row(r):
    """Listenzeile eines Plans; die verknüpfte Tour (falls es sie noch gibt) mit Soll/Ist-Werten."""
    t = None
    if r.get("tour_id"):
        x = db.one("SELECT id,name,start_ts,dist_m,dur_s,up_m FROM tours WHERE id=?", (r["tour_id"],))
        if x:
            t = {"id": x["id"], "name": x["name"] or "", "start_ts": x["start_ts"], "km": round((x["dist_m"] or 0) / 1000.0, 2) if x["dist_m"] else None,
                 "h": round(x["dur_s"] / 3600.0, 3) if x["dur_s"] else None, "up": round(x["up_m"]) if x["up_m"] is not None else None}
    r["tour"] = t
    if r.get("tour_id") and not t:
        r["tour_id"] = None                                   # Tour wurde gelöscht: Verknüpfung gilt nicht mehr
    return r


@router.get("/api/plans")
def api_plans():
    out = []
    for r in db.query("SELECT id,name,sport,km,up,down,max_alt,est_h,note,ts,tour_id,status,links,quelle FROM plans ORDER BY ts DESC"):
        r["n_links"] = len(planhilfe.lade_links(r.pop("links", None)))          # nur die Anzahl; die Links selbst liefert GET /api/plans/{id}
        r["has_note"] = bool((r.get("note") or "").strip())
        out.append(_plan_row(r))
    return out


@router.get("/api/plans/vorschlaege")
def api_plan_vorschlaege():
    """Gelaufene Touren, die einen noch offenen Plan zu mindestens 80 % überdecken (nur Vorschläge, nichts wird verknüpft)."""
    from . import plan_check
    return plan_check.vorschlaege()


def _plan_or_404(pid):
    if not db.one("SELECT 1 FROM plans WHERE id=?", (pid,)):
        raise HTTPException(404, "Plan nicht gefunden")


@router.post("/api/plans/{pid}/tour")
def api_plan_link(pid: int, body: dict):
    """Plan mit einer gelaufenen Tour verknüpfen (tour_id) oder lösen (tour_id leer/null). Verknüpfen setzt den Status auf „gegangen“, Lösen auf „geplant“."""
    _plan_or_404(pid)
    tid = body.get("tour_id")
    if tid in (None, ""):
        db.execute("UPDATE plans SET tour_id=NULL, status=CASE WHEN status='gegangen' THEN 'geplant' ELSE status END WHERE id=?", (pid,))
        return {"ok": True, "tour_id": None, "status": db.one("SELECT status FROM plans WHERE id=?", (pid,))["status"]}
    if not isinstance(tid, (str, int)) or isinstance(tid, bool) or len(str(tid)) > 64:
        raise HTTPException(400, "Ungültige Tour")
    tid = str(tid)
    if not db.one("SELECT 1 FROM tours WHERE id=?", (tid,)):
        raise HTTPException(404, "Tour nicht gefunden")
    db.execute("UPDATE plans SET tour_id=?, status='gegangen' WHERE id=?", (tid, pid))
    return {"ok": True, "tour_id": tid, "status": "gegangen"}


@router.post("/api/plans/{pid}/status")
def api_plan_status(pid: int, body: dict):
    """Status setzen: geplant | gegangen | verworfen. Ein anderer Status als „gegangen“ löst eine bestehende Verknüpfung mit einer Tour."""
    from .plan_check import STATUS
    _plan_or_404(pid)
    st = body.get("status")
    if st not in STATUS:
        raise HTTPException(400, "Status muss geplant, gegangen oder verworfen sein")
    if st == "gegangen":
        db.execute("UPDATE plans SET status=? WHERE id=?", (st, pid))
    else:
        db.execute("UPDATE plans SET status=?, tour_id=NULL WHERE id=?", (st, pid))
    return {"ok": True, "status": st}


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
    r["links"] = planhilfe.lade_links(r.get("links"))
    r["puffer_standard"] = planhilfe.PUFFER_STANDARD
    return r


@router.get("/api/plans/{pid}/hilfe")
def api_plan_hilfe(pid: int, datum: str = None, start: str = None, puffer: str = None):
    """Entscheidungshilfe „Passt die Tour zu mir?“: Form gegen die eigenen Touren, Tageslicht am Startpunkt, Quellen vom Typ Wetter/Lawinenbericht.
    datum/start/puffer (auch leer = Standard) überschreiben nur für diese Antwort die gespeicherten Werte. Nur lesend; gespeicherte Links werden nie abgerufen."""
    r = db.one("SELECT * FROM plans WHERE id=?", (pid,))
    if not r:
        raise HTTPException(404, "Plan nicht gefunden")
    kw = {}
    try:
        if datum is not None:
            kw["datum"] = planhilfe.pruefe_datum(datum)
        if start is not None:
            kw["start"] = planhilfe.pruefe_start(start)
        if puffer is not None:
            kw["puffer"] = planhilfe.pruefe_puffer(puffer)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return planhilfe.hilfe(r, **kw)


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
    pid = body.get("id")
    old = db.one("SELECT 1 FROM plans WHERE id=?", (int(pid),)) if pid else None
    try:
        note = planhilfe.pruefe_notiz(body.get("note"))
        qa, qt = planhilfe.pruefe_quelle(body.get("quelle"), body.get("quelle_text"))
        extra = (json.dumps(planhilfe.pruefe_links(body.get("links")), ensure_ascii=False), qa, qt, planhilfe.pruefe_datum(body.get("plan_datum")),
                 planhilfe.pruefe_start(body.get("plan_start")), planhilfe.pruefe_puffer(body.get("puffer_pct")))
    except ValueError as e:
        raise HTTPException(400, str(e))
    vals = (name, gpxtools.norm(str(body.get("sport") or "hike")[:30])[0], json.dumps(pts), num("km"), num("up"), num("down"), num("max_alt"), num("est_h"), note, int(time.time()), wps) + extra
    if old:
        cols = ["name", "sport", "pts", "km", "up", "down", "max_alt", "est_h", "note", "ts", "wps"]
        for k, c in (("links", ["links"]), ("quelle", ["quelle"]), ("quelle_text", ["quelle_text"]), ("plan_datum", ["plan_datum"]), ("plan_start", ["plan_start"]), ("puffer_pct", ["puffer_pct"])):
            cols += c if k in body else []                    # ein Aufruf ohne diese Felder (ältere Programme) lässt Links, Herkunft und Termin unverändert
        vv = list(vals[:11]) + [v for k, v in zip(("links", "quelle", "quelle_text", "plan_datum", "plan_start", "puffer_pct"), extra) if k in body]
        db.execute("UPDATE plans SET " + ",".join(f"{c}=?" for c in cols) + " WHERE id=?", tuple(vv) + (int(pid),))
        return {"id": int(pid)}
    return {"id": db.execute("INSERT INTO plans(name,sport,pts,km,up,down,max_alt,est_h,note,ts,wps,links,quelle,quelle_text,plan_datum,plan_start,puffer_pct) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", vals)}


@router.delete("/api/plans/{pid}")
def api_plan_del(pid: int):
    db.execute("DELETE FROM plans WHERE id=?", (pid,))
    return {"ok": True}


# ---------- 3.39.0 Soll/Ist an der Tourseite ----------
def simplify(pts, n=MAXLINE):
    """Linie auf höchstens `n` Punkte verkürzen (Douglas-Peucker in Prioritätsreihenfolge: die jeweils auffälligsten Punkte bleiben; Anfang und Ende immer).
    Rechnet in einer flachen Näherung (Längengrad mit cos(Breite) gestreckt); sehr lange Linien werden vorher gleichmäßig auf 4000 Punkte gedünnt."""
    import heapq
    import math
    pts = [[float(p[0]), float(p[1])] for p in pts or []]
    if len(pts) > 4000:
        step = len(pts) / 4000.0
        pts = [pts[int(i * step)] for i in range(4000)] + [pts[-1]]
    if len(pts) <= n:
        return [[round(a, 5), round(b, 5)] for a, b in pts]
    k = math.cos(math.radians(sum(p[0] for p in pts) / len(pts)))
    xy = [(p[1] * k, p[0]) for p in pts]

    def far(i, j):
        (x1, y1), (x2, y2) = xy[i], xy[j]
        dx, dy = x2 - x1, y2 - y1
        d2 = dx * dx + dy * dy
        best, at = -1.0, None
        for m in range(i + 1, j):
            x0, y0 = xy[m]
            if d2 == 0:
                dist = math.hypot(x0 - x1, y0 - y1)
            else:
                t = max(0.0, min(1.0, ((x0 - x1) * dx + (y0 - y1) * dy) / d2))
                dist = math.hypot(x0 - (x1 + t * dx), y0 - (y1 + t * dy))
            if dist > best:
                best, at = dist, m
        return best, at

    keep = {0, len(pts) - 1}
    heap = []
    if len(pts) > 2:
        d, m = far(0, len(pts) - 1)
        heap.append((-d, m, 0, len(pts) - 1))
    while heap and len(keep) < n:
        _, m, i, j = heapq.heappop(heap)
        keep.add(m)
        for a, b in ((i, m), (m, j)):
            if b - a > 1:
                d, mm = far(a, b)
                heapq.heappush(heap, (-d, mm, a, b))
    return [[round(pts[i][0], 5), round(pts[i][1], 5)] for i in sorted(keep)]


@tour_router.get("/api/tours/{tour_id}/plan")
def api_tour_plan(tour_id: str):
    """Verknüpfte Planung einer gelaufenen Tour (Soll/Ist): Kopf des Plans, Kennzahlen mit Differenzen und beide Linien auf höchstens 400 Punkte verkürzt.
    Ohne Verknüpfung {"status": "kein_plan"}; fehlende Werte sind null (nie 0). Nur lesend, gehört dem angemeldeten Benutzer (Betrachter dürfen lesen); Freigabelinks liefern nichts davon."""
    t = db.one("SELECT id,name,start_ts,dist_m,dur_s,up_m FROM tours WHERE id=?", (tour_id,))
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    p = db.one("SELECT id,name,sport,km,up,down,est_h,ts,pts FROM plans WHERE tour_id=? ORDER BY ts DESC LIMIT 1", (tour_id,))
    if not p:
        return {"status": "kein_plan"}
    ist = {"km": round(t["dist_m"] / 1000.0, 2) if t["dist_m"] else None, "up": round(t["up_m"]) if t["up_m"] is not None else None, "h": round(t["dur_s"] / 3600.0, 3) if t["dur_s"] else None}
    soll = {"km": p["km"] if p["km"] else None, "up": round(p["up"]) if p["up"] is not None else None, "h": p["est_h"] if p["est_h"] else None}

    def diff(k, nd):
        return round(ist[k] - soll[k], nd) if ist[k] is not None and soll[k] is not None else None
    try:
        plan_line = simplify(json.loads(p["pts"]))
    except (TypeError, ValueError):
        plan_line = []
    track = routes.load(tour_id)
    return {"status": "ok", "plan": {"id": p["id"], "name": p["name"] or "", "sport": p["sport"], "ts": p["ts"]}, "soll": soll, "ist": ist,
            "diff": {"km": diff("km", 2), "up": diff("up", 0), "h": diff("h", 3)}, "plan_linie": plan_line, "tour_linie": simplify(track) if track else []}
