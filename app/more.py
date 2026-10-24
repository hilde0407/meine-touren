"""Prüfen/Aufräumen, Orte & Gipfel, Wanderführer-Fortschritt, Gesundheitscheck."""
import json
import re
import shutil
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from . import config, db, elev, extras, jobs, memo, routes

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
                out.append({"a": a["id"], "b": b["id"], "a_local": a.get("source") == "local", "b_local": b.get("source") == "local"})
    return out


WALK = ("hike", "nordicwalking", "snowshoe", "mountaineering")
SPORT_OK = {"hike", "touringbicycle", "e_touringbicycle", "racebike", "mtb", "e_mtb", "jogging", "skialpin", "snowshoe", "mountaineering",
            "nordic", "nordicwalking", "skitour", "other"}


def implausible(tours):
    """Fehlaufzeichnungen (fast keine Strecke/Dauer) und Tempo, das nicht zur Sportart passt (z. B. „Wandern“ mit 20 km/h)."""
    out = []
    for t in tours:
        d, s = t["dist_m"] or 0, t["dur_s"] or 0
        v = d / s * 3.6 if s else 0
        why, sug = None, None
        if d < 300 or (s and s < 180):
            why = f"Fehlaufzeichnung? nur {d:.0f} m" + (f" in {s // 60:.0f} min" if s else "")
        elif t["sport"] in WALK and v > 8:
            why, sug = f"{v:.1f} km/h – zu schnell für {t['sport'] == 'hike' and 'Wandern' or 'diese Sportart'}", "touringbicycle"
        elif t["sport"] == "jogging" and v > 22:
            why, sug = f"{v:.1f} km/h – zu schnell zum Laufen", "touringbicycle"
        elif t["sport"] in ("touringbicycle", "racebike", "mtb") and 0 < v < 4 and d > 2000:
            why, sug = f"{v:.1f} km/h – sehr langsam für Rad", "hike"
        if why:
            why = re.sub(r"(\d)\.(\d)", r"\1,\2", why)
            out.append({"id": t["id"], "name": t["name"], "sport": t["sport"], "start_ts": t["start_ts"], "km": round(d / 1000, 2),
                        "kmh": round(v, 1), "why": why, "suggest": sug, "local": t.get("source") == "local"})
    return out


@router.post("/api/tours/{tour_id}/sport")
def api_set_sport(tour_id: str, body: dict):
    sp = str(body.get("sport") or "")
    if sp not in SPORT_OK:
        raise HTTPException(400, "Unbekannte Sportart")
    if not db.one("SELECT 1 x FROM tours WHERE id=?", (tour_id,)):
        raise HTTPException(404, "Tour nicht gefunden")
    db.execute("INSERT OR REPLACE INTO tour_sport(id,sport) VALUES(?,?)", (tour_id, sp))
    db.execute("UPDATE tours SET sport=? WHERE id=?", (sp, tour_id))
    return {"ok": True}


@router.post("/api/tours/{tour_id}/hide")
def api_hide(tour_id: str, body: dict):
    """Tour aus allen Ansichten und Statistiken ausblenden (Daten bleiben erhalten) bzw. wieder einblenden."""
    if body.get("hide", True):
        t = db.one("SELECT * FROM tours WHERE id=?", (tour_id,))
        if not t:
            raise HTTPException(404, "Tour nicht gefunden")
        db.execute("INSERT OR REPLACE INTO tour_hidden(id,js,ts) VALUES(?,?,?)", (tour_id, json.dumps(t), int(time.time())))
        db.execute("DELETE FROM tours WHERE id=?", (tour_id,))
        db.execute("UPDATE photos SET tour_id=NULL WHERE tour_id=? AND COALESCE(manual,0)=0", (tour_id,))
    else:
        r = db.one("SELECT js FROM tour_hidden WHERE id=?", (tour_id,))
        if not r:
            raise HTTPException(404, "Nicht ausgeblendet")
        t = json.loads(r["js"])
        cols = [c for c in t if c in {x["name"] for x in db.query("PRAGMA table_info(tours)")}]
        db.execute(f"INSERT OR REPLACE INTO tours({','.join(cols)}) VALUES({','.join('?' * len(cols))})", tuple(t[c] for c in cols))
        db.execute("DELETE FROM tour_hidden WHERE id=?", (tour_id,))
    from . import photos
    photos.assign_all()
    return {"ok": True}


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
        "implausible": implausible(tours),
        "hidden": [{"id": r["id"], **{k: v for k, v in json.loads(r["js"]).items() if k in ("name", "sport", "start_ts", "dist_m")}} for r in db.query("SELECT id,js FROM tour_hidden ORDER BY ts DESC")],
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
    """Gipfel bestimmen. Jedes Ergebnis wird sofort gespeichert; ein erneuter Start macht dort weiter, wo der letzte aufgehört hat."""
    fetch = fetch or extras.peak_name
    ok = n = fails = skipped = 0
    now = int(time.time())
    todo = []
    for t in _peak_candidates():
        if t["sport"] not in HIKE or (t["up_m"] or 0) < 150:      # kommt nie infrage: ohne Netzwerk als erledigt vermerken
            db.execute("INSERT OR REPLACE INTO tour_peak(id,name,alt,lat,lng) VALUES(?,?,?,?,?)", (t["id"], "", None, None, None)); continue
        if not routes.path_full(t["id"]).exists():                 # Strecke fehlt noch: später (nach „Strecken lokal sichern“) erneut
            skipped += 1; continue
        todo.append(t)
    failed = {r["k"][9:]: r["ts"] for r in db.query("SELECT k,ts FROM geocache WHERE k LIKE 'peakfail:%'")}
    fresh = lambda t: now - failed.get(t["id"], 0) < 6 * 3600     # vor Kurzem gescheitert: erst die übrigen Touren, dann diese
    todo = [t for t in todo if not fresh(t)] + [t for t in todo if fresh(t)]
    total = len(todo) if not limit else min(limit, len(todo))
    jobs.log(f"Gipfel: {total} Touren zu bearbeiten (jedes Ergebnis wird sofort gespeichert)")
    for t in todo:
        if limit and n >= limit:
            break
        pts = routes.load(t["id"])
        alts = [p for p in (pts or []) if len(p) > 2 and p[2] is not None]
        if len(alts) < 5:
            db.execute("INSERT OR REPLACE INTO tour_peak(id,name,alt,lat,lng) VALUES(?,?,?,?,?)", (t["id"], "", None, None, None)); continue
        hi = max(alts, key=lambda p: p[2]); n += 1
        jobs.progress(f"Gipfel {n} von {total} · {ok} bestimmt")
        name, err, t0 = None, None, time.monotonic()
        for attempt in range(2):                                   # Overpass begrenzt Anfragen: kurz warten und erneut versuchen
            try:
                name = fetch(hi[0], hi[1]); err = None; break
            except Exception as e:  # noqa
                err = e
                if attempt < 1:
                    time.sleep(retry_wait)
        if err is not None:
            fails += 1
            db.execute("INSERT OR REPLACE INTO geocache(k,name,ts) VALUES(?,?,?)", (f"peakfail:{t['id']}", "", int(time.time())))
            if fails == 1 or fails % 5 == 0:
                jobs.log(f"  Gipfel: {err}")
            if fails >= 5:
                jobs.log("  Gipfel: Overpass antwortet nicht – Abbruch, bereits Bestimmtes bleibt gespeichert. Später einfach erneut starten."); break
            continue
        fails = 0
        db.execute("DELETE FROM geocache WHERE k=?", (f"peakfail:{t['id']}",))
        db.execute("INSERT OR REPLACE INTO tour_peak(id,name,alt,lat,lng) VALUES(?,?,?,?,?)", (t["id"], name or "", hi[2], hi[0], hi[1]))
        ok += 1
        if time.monotonic() - t0 > 0.05:                           # nur nach echten Abfragen pausieren (Zwischenspeicher-Treffer sofort)
            time.sleep(1.0)
    jobs.log(f"Gipfel: {ok} bestimmt" + (f", {skipped} Touren ohne lokale Strecke übersprungen" if skipped else "") + f", noch offen: {peaks_pending()}")
    return ok


@router.get("/api/places")
@memo.cached
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
@memo.cached
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
