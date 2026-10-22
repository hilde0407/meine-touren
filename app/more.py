"""Prüfen/Aufräumen, Orte & Gipfel, Wanderführer-Fortschritt, Gesundheitscheck."""
import json
import re
import shutil
import time
from pathlib import Path

from fastapi import APIRouter

from . import config, db, elev, extras, jobs, routes

router = APIRouter()
DEFAULT_NAME = re.compile(r"\d{2}\.\d{2}\.\d{4}")
HIKE = ("hike", "mountaineering", "skitour", "snowshoe", "nordicwalking", "skialpin")


def _hav(a, b):
    return extras._hav(a, b)


def duplicates(tours):
    ts = sorted([t for t in tours if t["start_ts"]], key=lambda t: t["start_ts"])
    out = []
    for i, a in enumerate(ts):
        for b in ts[i + 1:]:
            if b["start_ts"] - a["start_ts"] > 6 * 3600:
                break
            da, db_ = a["dist_m"] or 0, b["dist_m"] or 0
            if not da or not db_ or abs(da - db_) / max(da, db_) > 0.15:
                continue
            near = a["lat"] is not None and b["lat"] is not None and _hav((a["lat"], a["lng"]), (b["lat"], b["lng"])) < 400
            if near or abs(b["start_ts"] - a["start_ts"]) < 900:
                out.append({"a": a["id"], "b": b["id"]})
    return out


@router.get("/api/check")
def api_check():
    tours = db.query("SELECT t.*, (SELECT COUNT(*) FROM photos p WHERE p.tour_id=t.id) AS photos, "
                     "(SELECT 1 FROM tour_geo g WHERE g.id=t.id) AS has_geo, (SELECT 1 FROM elev_fix e WHERE e.id=t.id) AS fixed FROM tours t ORDER BY start_ts DESC")
    brief = lambda t: {"id": t["id"], "name": t["name"], "sport": t["sport"], "start_ts": t["start_ts"], "km": round((t["dist_m"] or 0) / 1000, 1), "up_m": t["up_m"]}
    return {
        "total": len(tours),
        "duplicates": duplicates(tours),
        "default_names": [brief(t) for t in tours if DEFAULT_NAME.search(t["name"] or "")],
        "suspicious": [brief(t) for t in tours if not t["fixed"] and elev.suspicious(t)],
        "gaps": {"no_route": sum(1 for t in tours if not routes.path_full(t["id"]).exists()),
                 "no_region": sum(1 for t in tours if not t["has_geo"] and t["lat"] is not None),
                 "no_photos": sum(1 for t in tours if not t["photos"]),
                 "no_distance": sum(1 for t in tours if not t["dist_m"])},
    }


# ---------- Gipfel ----------
def _peak_candidates():
    """Touren, für die ein Gipfel infrage kommt (Wandersportart, mind. 150 m Aufstieg) und die noch nicht bestimmt sind."""
    return db.query(f"SELECT id,sport,up_m FROM tours WHERE id NOT IN (SELECT id FROM tour_peak) ORDER BY start_ts DESC")


def peaks_pending():
    """Anzahl wirklich bearbeitbarer Touren: Strecke liegt lokal vor und die Tour kommt infrage."""
    n = 0
    for t in _peak_candidates():
        if t["sport"] in HIKE and (t["up_m"] or 0) >= 150 and routes.path_full(t["id"]).exists():
            n += 1
    return n


def peaks_fill(limit=None, fetch=None, retry_wait=8):
    fetch = fetch or extras.peak_name
    ok = n = fails = skipped = 0
    for t in _peak_candidates():
        if limit and n >= limit:
            break
        if t["sport"] not in HIKE or (t["up_m"] or 0) < 150:      # kommt nie infrage: ohne Netzwerk als erledigt vermerken
            db.execute("INSERT OR REPLACE INTO tour_peak(id,name,alt,lat,lng) VALUES(?,?,?,?,?)", (t["id"], "", None, None, None)); continue
        pts = routes.load(t["id"])
        alts = [p for p in (pts or []) if len(p) > 2 and p[2] is not None]
        if len(alts) < 5:                                          # Strecke fehlt noch: später (nach „Strecken lokal sichern“) erneut
            skipped += 1; continue
        hi = max(alts, key=lambda p: p[2]); n += 1
        jobs.progress(f"Gipfel {n}")
        name, err = None, None
        for attempt in range(3):                                   # Overpass begrenzt Anfragen: kurz warten und erneut versuchen
            try:
                name = fetch(hi[0], hi[1]); err = None; break
            except Exception as e:  # noqa
                err = e
                if attempt < 2:
                    time.sleep(retry_wait * (attempt + 1))
        if err is not None:
            fails += 1
            if fails == 1 or fails % 5 == 0:
                jobs.log(f"  Gipfel: {err}")
            if fails >= 8:
                jobs.log("  Gipfel: zu viele Fehler in Folge – Abbruch, später erneut versuchen"); break
            continue
        fails = 0
        db.execute("INSERT OR REPLACE INTO tour_peak(id,name,alt,lat,lng) VALUES(?,?,?,?,?)", (t["id"], name or "", hi[2], hi[0], hi[1]))
        ok += 1
        time.sleep(1.0)
    jobs.log(f"Gipfel: {ok} bestimmt" + (f", {skipped} Touren ohne lokale Strecke übersprungen" if skipped else "") + f", noch offen: {peaks_pending()}")
    return ok


@router.get("/api/places")
def api_places():
    starts = db.query("SELECT g.place AS place, g.state AS state, COUNT(*) AS n, ROUND(SUM(t.dist_m)/1000.0,0) AS km FROM tour_geo g JOIN tours t ON t.id=g.id "
                      "WHERE g.place IS NOT NULL AND g.place!='' GROUP BY g.place, g.state ORDER BY n DESC, km DESC LIMIT 25")
    rows = db.query("SELECT p.name, p.alt, t.id, t.start_ts FROM tour_peak p JOIN tours t ON t.id=p.id WHERE p.name!='' ORDER BY t.start_ts DESC")
    peaks = {}
    for r in rows:
        d = peaks.setdefault(r["name"], {"name": r["name"], "alt": r["alt"], "n": 0, "tours": []})
        d["n"] += 1; d["tours"].append(r["id"]); d["alt"] = max(d["alt"] or 0, r["alt"] or 0)
    pending = peaks_pending()
    return {"starts": starts, "peaks": sorted(peaks.values(), key=lambda p: (-p["n"], -(p["alt"] or 0)))[:40], "pending_peaks": pending}


# ---------- Wanderführer-Fortschritt ----------
@router.get("/api/guides/progress")
def api_guides_progress():
    gs = db.query("SELECT id,book,title,pts FROM guide_tours ORDER BY book,title")
    if not gs:
        return []
    mine = []
    for t in db.query("SELECT id,start_ts FROM tours ORDER BY start_ts DESC"):
        p = routes.load(t["id"])
        if p and len(p) > 5:
            mine.append((t["id"], t["start_ts"], p))
    books = {}
    for g in gs:
        line = json.loads(g["pts"]); step = max(1, len(line) // 40)
        la, lo = [p[0] for p in line], [p[1] for p in line]
        done = None
        for tid, ts, p in mine:
            if min(la) - 0.02 > max(x[0] for x in p[::10]) or max(la) + 0.02 < min(x[0] for x in p[::10]) or min(lo) - 0.03 > max(x[1] for x in p[::10]) or max(lo) + 0.03 < min(x[1] for x in p[::10]):
                continue
            n = min(40, len(p)); samp = [(p[int(i * (len(p) - 1) / max(1, n - 1))][0], p[int(i * (len(p) - 1) / max(1, n - 1))][1]) for i in range(n)]
            if extras._covered(line[::step], [(x[0], x[1]) for x in p], 120) >= 0.7 and extras._covered(samp, line, 80) >= 0.4:
                done = (tid, ts); break
        books.setdefault(g["book"] or "(ohne Buch)", []).append({"id": g["id"], "title": g["title"], "tour": done[0] if done else None, "ts": done[1] if done else None})
    return [{"book": b, "total": len(v), "done": sum(1 for x in v if x["tour"]), "tours": v} for b, v in books.items()]


# ---------- Gesundheitscheck (ohne Netzwerk) ----------
@router.get("/api/health")
def api_health():
    w = []
    if not (db.get("komoot_email") and db.get("komoot_password")) and not db.one("SELECT 1 x FROM tours LIMIT 1"):
        w.append({"level": "warn", "text": "Noch keine Touren: Komoot-Zugang eintragen oder GPX-Dateien bzw. Zepp-Trainings importieren (Verwaltung)."})
    z = db.get("zepp_state") or ""
    if z.startswith("fail"):
        w.append({"level": "warn", "text": "Zepp-Token ist abgelaufen oder ungültig (Verwaltung → Zepp)."})
    st = jobs.get_state()
    if st.get("ok") is False and st.get("finished") and time.time() - st["finished"] < 3 * 86400:
        w.append({"level": "warn", "text": f"Letzter Job „{st.get('running') or 'unbekannt'}“ ist fehlgeschlagen (Verwaltung → Protokoll)."})
    nb = extras.newest_backup()
    err = db.get("backup_err")
    if err:
        w.append({"level": "warn", "text": f"Backup kann nicht geschrieben werden: {err}"})
    elif nb is None:
        w.append({"level": "warn", "text": "Es gibt noch kein Backup – das erste wird in den nächsten Minuten automatisch angelegt."})
    elif time.time() - nb.stat().st_mtime > 2 * 86400:
        w.append({"level": "warn", "text": "Das letzte Backup ist älter als 2 Tage."})
    try:
        free = shutil.disk_usage(config.DATA_DIR).free
        if free < 1_000_000_000:
            w.append({"level": "warn", "text": f"Nur noch {free // 1_000_000} MB Speicherplatz frei."})
    except OSError:
        pass
    return w
