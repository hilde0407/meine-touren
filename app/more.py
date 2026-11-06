"""Prüfen/Aufräumen, Orte & Gipfel, Wanderführer-Fortschritt, Gesundheitscheck."""
import json
import threading
import re
import shutil
import os
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
            from . import trackfix
            out.append({"diag": trackfix.diagnose(t["id"]), "id": t["id"], "name": t["name"], "sport": t["sport"], "start_ts": t["start_ts"], "km": round(d / 1000, 2),
                        "kmh": round(v, 1), "why": why, "suggest": sug, "local": t.get("source") == "local",
                        "on_komoot": t.get("source") != "local" or bool(db.one("SELECT 1 x FROM tour_uploads WHERE tour_id=? AND portal='komoot' AND remote_id!=''", (t["id"],)))})
    return out


@router.post("/api/tours/{tour_id}/sport")
def api_set_sport(tour_id: str, body: dict):
    sp = str(body.get("sport") or "")
    if sp not in SPORT_OK:
        raise HTTPException(400, "Unbekannte Sportart")
    if not db.one("SELECT 1 x FROM tours WHERE id=?", (tour_id,)):
        raise HTTPException(404, "Tour nicht gefunden")
    msg = ""
    if body.get("komoot"):                # auch bei Komoot ändern (Komoot-Tour selbst bzw. hochgeladene Kopie einer lokalen Tour)
        from . import portals, sync
        t = db.one("SELECT source FROM tours WHERE id=?", (tour_id,))
        kid = tour_id if t["source"] != "local" else (portals.status_of(tour_id).get("komoot") or {}).get("remote_id")
        if kid:
            try:
                sync._komoot().set_sport(kid, sp); msg = "auch bei Komoot geändert"
            except Exception as e:  # noqa
                raise HTTPException(502, str(e))
        else:
            msg = "bei Komoot nicht vorhanden – nur hier geändert"
    db.execute("INSERT OR REPLACE INTO tour_sport(id,sport) VALUES(?,?)", (tour_id, sp))
    db.execute("UPDATE tours SET sport=? WHERE id=?", (sp, tour_id))
    return {"ok": True, "komoot": msg}


def _fixerr(tour_id, e):
    if isinstance(e, KeyError):
        if db.one("SELECT 1 x FROM tour_hidden WHERE id=?", (tour_id,)):
            raise HTTPException(409, "Die Tour ist ausgeblendet – bitte zuerst unter Prüfen wieder einblenden.")
        raise HTTPException(404, "Tour nicht gefunden")
    raise HTTPException(422, str(e))


@router.get("/api/tours/{tour_id}/trackfix")
def api_trackfix(tour_id: str):
    """Auffälligkeiten im GPS-Track: Ausreißer und zu schnelle Abschnitte."""
    from . import trackfix
    try:
        return trackfix.analyse(tour_id)
    except Exception as e:  # noqa
        _fixerr(tour_id, e)


@router.post("/api/tours/{tour_id}/trackfix")
def api_trackfix_apply(tour_id: str, body: dict):
    from . import trackfix
    try:
        return trackfix.apply(tour_id, bool(body.get("spikes", True)), body.get("exclude") or [], bool(body.get("smooth", False)), body.get("dur_s"), body.get("start_ts"), bool(body.get("anchors")))
    except Exception as e:  # noqa
        _fixerr(tour_id, e)


@router.post("/api/tours/{tour_id}/trackfix-restore")
def api_trackfix_restore(tour_id: str):
    from . import trackfix
    return {"ok": trackfix.restore(tour_id)}


@router.post("/api/series/rename")
def api_series_rename(body: dict):
    """Mehrtagestour benennen: items = [{id, n}], name = Reihenname, word = „Tag“/„Etappe“ … → „Name – Tag N“ für jede Tour."""
    name = re.sub(r"\s+", " ", str(body.get("name") or "")).strip()
    word = re.sub(r"\s+", " ", str(body.get("word") or "Tag")).strip()[:20] or "Tag"
    items = body.get("items") or []
    if not name or len(name) > 120 or not items or len(items) > 60:
        raise HTTPException(400, "Name und mindestens eine Tour nötig")
    done = 0
    for it in items:
        tid, n = str(it.get("id")), int(it.get("n") or 0)
        if n < 1 or not db.one("SELECT 1 x FROM tours WHERE id=?", (tid,)):
            continue
        new = f"{name} – {word} {n}"
        old = db.one("SELECT name FROM tours WHERE id=?", (tid,))["name"]
        db.execute("UPDATE tours SET name=? WHERE id=?", (new, tid))
        db.execute("INSERT OR REPLACE INTO tour_names(id,name,orig) VALUES(?,?,COALESCE((SELECT orig FROM tour_names WHERE id=?),?))", (tid, new, tid, old))
        done += 1
    return {"ok": True, "renamed": done}


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


def delete_tour(tid, on_komoot=False):
    """Tour löschen. on_komoot: auch die zugehörige Komoot-Tour endgültig löschen (die Tour selbst bzw. die hochgeladene Kopie).
    Eine Komoot-Tour, die nur hier gelöscht wird, wird gemerkt, damit sie beim nächsten Abgleich nicht wiederkommt."""
    from . import photos, portals, sync, tracks
    t = db.one("SELECT * FROM tours WHERE id=?", (tid,))
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    local = t.get("source") == "local"
    up = portals.status_of(tid).get("komoot") or {}
    kid = (up.get("remote_id") if local else tid) or ""
    msg = ""
    if on_komoot and kid:
        gone = sync._komoot().delete(kid)
        msg = "bei Komoot gelöscht" if gone else "bei Komoot nicht (mehr) vorhanden"
    if local:
        tracks.delete_local(tid)
    else:
        if not (on_komoot and kid):           # nur hier gelöscht: beim nächsten Abgleich nicht wieder anlegen
            db.execute("INSERT OR REPLACE INTO tour_hidden(id,js,ts) VALUES(?,?,?)", (tid, json.dumps({**t, "deleted": 1}), int(time.time())))
        for tb in ("tours", "tour_tags", "tour_notes", "tour_geo", "tour_peak", "tour_names", "elev_fix", "weather", "tour_sport", "tour_rating", "tour_safety"):
            db.execute(f"DELETE FROM {tb} WHERE id=?", (tid,))
        db.execute("DELETE FROM tour_gear WHERE tour_id=?", (tid,))
        db.execute("DELETE FROM tour_uploads WHERE tour_id=?", (tid,))
        db.execute("UPDATE photos SET tour_id=NULL WHERE tour_id=? AND COALESCE(manual,0)=0", (tid,))
        for p in (routes.path_full(tid), routes.path_small(tid)):
            p.unlink(missing_ok=True)
    photos.assign_all()
    return {"ok": True, "komoot": msg}


@router.post("/api/tours/{tour_id}/delete")
def api_delete_tour(tour_id: str, body: dict):
    try:
        return delete_tour(tour_id, bool(body.get("komoot")))
    except HTTPException:
        raise
    except Exception as e:  # noqa
        raise HTTPException(502, str(e))


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
        "hidden": [{"id": r["id"], **{k: v for k, v in json.loads(r["js"]).items() if k in ("name", "sport", "start_ts", "dist_m")}} for r in db.query("SELECT id,js FROM tour_hidden ORDER BY ts DESC") if not json.loads(r["js"]).get("deleted")],
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


# ---------- Wie oft bin ich diese Strecke gegangen? ----------
def _pline(pts):
    step = max(1, len(pts) // 250)
    line = [(p[0], p[1]) for p in pts[::step]]
    if line[-1] != (pts[-1][0], pts[-1][1]):
        line.append((pts[-1][0], pts[-1][1]))
    return line


def _cover(samp, line, r_m, cos):
    """Anteil der Stützpunkte `samp`, die höchstens r_m Meter von der Linie `line` entfernt liegen."""
    k = 111000.0
    hit = 0
    for p in samp:
        px, py = p[1] * k * cos, p[0] * k
        best = 1e18
        for a, b in zip(line, line[1:]):
            if abs(a[0] - p[0]) > 0.02 and abs(b[0] - p[0]) > 0.02:
                continue
            ax, ay, bx, by = a[1] * k * cos, a[0] * k, b[1] * k * cos, b[0] * k
            dx, dy = bx - ax, by - ay
            L = dx * dx + dy * dy
            u = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
            d = ((px - ax - u * dx) ** 2 + (py - ay - u * dy) ** 2) ** 0.5
            if d < best:
                best = d
                if d <= r_m:
                    break
        if best <= r_m:
            hit += 1
    return hit / max(1, len(samp))


def _repeats_sig():
    r = db.one("SELECT COUNT(*) n, COALESCE(SUM(dist_m),0) d, COALESCE(MAX(start_ts),0) m FROM tours") or {}
    h = db.one("SELECT COUNT(*) n FROM tour_hidden") or {}
    try:
        cd = (config.CACHE_DIR / "coords").stat().st_mtime_ns
    except OSError:
        cd = None
    return (r.get("n"), r.get("d"), r.get("m"), h.get("n"), cd)


def warm_repeats():
    """Wiederholungs-Auswertung im Hintergrund vorberechnen, damit die Übersicht nicht darauf warten muss."""
    from . import ctx
    uid = ctx.uid()

    def run():
        try:
            with ctx.as_user(uid):
                api_repeats()
        except Exception:  # noqa
            pass
    threading.Thread(target=run, daemon=True).start()


@router.get("/api/repeats")
@memo.cached(sig=_repeats_sig)
def api_repeats():
    """Touren, die dieselbe Strecke mehrfach gegangen wurden: {tour_id: {"n": Anzahl, "with": [{"id","start_ts"}, …]}} (nur n >= 2)."""
    import math
    hidden = {r["id"] for r in db.query("SELECT id FROM tour_hidden")}
    items = []
    for t in db.query("SELECT id,start_ts,dist_m FROM tours ORDER BY start_ts"):
        if t["id"] in hidden or (t["dist_m"] or 0) < 1000:
            continue
        pts = routes.load(t["id"])
        if not pts or len(pts) < 5:
            continue
        line = _pline(pts)
        la, lo = [p[0] for p in line], [p[1] for p in line]
        n = min(50, len(line))
        samp = [line[int(i * (len(line) - 1) / max(1, n - 1))] for i in range(n)]
        items.append({"id": t["id"], "ts": t["start_ts"], "km": (t["dist_m"] or 0) / 1000, "line": line, "samp": samp,
                      "bb": (min(la), max(la), min(lo), max(lo)), "cos": math.cos(math.radians(sum(la) / len(la)))})
    out = {}
    srt = sorted(items, key=lambda x: x["bb"][0])           # Sweep nach Südkante: spätere Touren beginnen weiter nördlich
    for i, a in enumerate(srt):
        for b in srt[i + 1:]:
            if b["bb"][0] > a["bb"][1] + 0.003:
                break
            if a["bb"][3] + 0.004 < b["bb"][2] or b["bb"][3] + 0.004 < a["bb"][2]:
                continue
            if not 0.8 <= a["km"] / max(b["km"], 1e-6) <= 1.25:
                continue
            if _cover(a["samp"][:: max(1, len(a["samp"]) // 5)], b["line"], 60, a["cos"]) < 0.6:     # schneller Vortest mit wenigen Punkten
                continue
            if _cover(a["samp"], b["line"], 60, a["cos"]) >= 0.85 and _cover(b["samp"], a["line"], 60, a["cos"]) >= 0.85:
                out.setdefault(a["id"], []).append(b)
                out.setdefault(b["id"], []).append(a)
    ts = {x["id"]: x["ts"] for x in items}
    res = {}
    for tid, others in out.items():
        res[tid] = {"n": len(others) + 1, "with": sorted([{"id": o["id"], "start_ts": o["ts"]} for o in others], key=lambda x: x["start_ts"]), "start_ts": ts[tid]}
    return res


# ---------- Unbenutzte Fotos (keiner Tour zugeordnet) aufräumen ----------
def _unused_where(years):
    w, a = "tour_id IS NULL", []
    ys = [int(y) for y in (years or [])]
    if ys:
        w += " AND CAST(strftime('%Y', taken_ts, 'unixepoch') AS INT) IN (" + ",".join("?" * len(ys)) + ")"
        a += ys
    return w, tuple(a)


@router.get("/api/photos-unused")
def api_photos_unused():
    rows = db.query("SELECT CAST(strftime('%Y', taken_ts, 'unixepoch') AS INT) y, COUNT(*) n, COALESCE(SUM(size),0) b FROM photos WHERE tour_id IS NULL GROUP BY y ORDER BY y DESC")
    sample = [r["id"] for r in db.query("SELECT id FROM photos WHERE tour_id IS NULL ORDER BY RANDOM() LIMIT 12")]
    return {"count": sum(r["n"] for r in rows), "bytes": sum(r["b"] for r in rows), "years": rows, "sample": sample}


@router.post("/api/photos-unused/delete")
def api_photos_unused_delete(body: dict):
    """Löscht Fotos ohne Tour (nur die Kopien der Bibliothek, nie Originale). `years` leer = alle Jahre.
    Die Auswahl wird erst jetzt neu bestimmt: inzwischen zugeordnete Fotos bleiben erhalten."""
    from . import photos
    years = body.get("years") or []
    if not years and not body.get("all"):
        raise HTTPException(400, "Bitte Jahre wählen oder „alle“ bestätigen")
    w, a = _unused_where(years)
    ids = [r["id"] for r in db.query(f"SELECT id FROM photos WHERE {w}", a)]
    return {"ok": True, "deleted": photos.delete_photos(ids) if ids else 0}


# ---------- Titelfoto je Tour ----------
@router.get("/api/tour-covers")
def api_tour_covers():
    """Pro Tour ein Foto aus der Mitte der Aufnahmen: {tour_id: {"id": Foto-ID, "n": Anzahl Fotos}}"""
    by = {}
    for r in db.query("SELECT id,tour_id FROM photos WHERE tour_id IS NOT NULL AND COALESCE(manual,0)!=2 ORDER BY tour_id,taken_ts"):
        by.setdefault(r["tour_id"], []).append(r["id"])
    return {t: {"id": ids[len(ids) // 2], "n": len(ids)} for t, ids in by.items()}


# ---------- Beste Fotos ----------
@router.get("/api/tours/{tour_id}/best-photos")
def api_best_photos(tour_id: str, n: int = 10):
    from . import photos
    best, total = photos.best_of_tour(tour_id, max(1, min(n, 60)))
    return {"photos": best, "total": total, "rated": sum(1 for p in best if (p.get("rating") or 0) > 0)}


# ---------- Wunschliste ----------
@router.get("/api/wishlist")
def api_wishlist():
    done = {}
    for b in api_guides_progress():
        for x in b["tours"]:
            done[x["id"]] = x
    rows = db.query("SELECT g.id,g.book,g.title,g.km,g.up,g.pts,w.ts AS wish, w.season FROM guide_tours g LEFT JOIN wishlist w ON w.gid=g.id ORDER BY g.book,g.title")
    out = []
    for r in rows:
        km = r["km"]
        if km is None:
            pts = json.loads(r["pts"])
            km = extras.guide_stats("<x/>", pts)[0]
            db.execute("UPDATE guide_tours SET km=? WHERE id=?", (km, r["id"]))
        d = done.get(r["id"]) or {}
        out.append({"id": r["id"], "book": r["book"] or "", "title": r["title"], "km": km, "up": r["up"], "wish": 1 if r["wish"] else 0, "season": r["season"] or "", "tour": d.get("tour"), "ts": d.get("ts")})
    return out


@router.post("/api/wishlist")
def api_wishlist_set(body: dict):
    gid = int(body.get("id"))
    if not db.one("SELECT 1 FROM guide_tours WHERE id=?", (gid,)):
        raise HTTPException(404, "Tour nicht gefunden")
    if "season" in body and db.one("SELECT 1 FROM wishlist WHERE gid=?", (gid,)):      # nur die Jahreszeit ändern
        sea = body.get("season") if body.get("season") in ("sommer", "winter") else ""
        db.execute("UPDATE wishlist SET season=? WHERE gid=?", (sea, gid))
    elif body.get("on", True):
        sea = body.get("season") if body.get("season") in ("sommer", "winter") else ""
        db.execute("INSERT OR REPLACE INTO wishlist(gid,ts,season) VALUES(?,?,?)", (gid, int(time.time()), sea))
    else:
        db.execute("DELETE FROM wishlist WHERE gid=?", (gid,))
    return {"ok": True}


# ---------- Gesundheitscheck (ohne Netzwerk) ----------
@router.get("/api/health")
def api_health():
    w = []
    if os.environ.get("MT_DEMO") == "1":
        w.append({"level": "info", "text": "Demo-Modus: Alle Touren und Fotos hier sind Beispieldaten."})
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
        w.append({"level": "warn", "text": "Es gibt noch kein Backup – das erste wird automatisch angelegt (nachts), oder jetzt sofort:", "action": "backup"})
    elif time.time() - nb.stat().st_mtime > 2 * 86400:
        w.append({"level": "warn", "text": "Das letzte Backup ist älter als 2 Tage.", "action": "backup"})
    try:
        free = shutil.disk_usage(config.DATA_DIR).free
        if free < 1_000_000_000:
            w.append({"level": "warn", "text": f"Nur noch {free // 1_000_000} MB Speicherplatz frei."})
    except OSError:
        pass
    return w


# ---------- Tagebuch: Bewertung · Sicherheitsnotiz ----------
@router.post("/api/tours/{tour_id}/rating")
def api_rating(tour_id: str, body: dict):
    if not db.one("SELECT 1 x FROM tours WHERE id=?", (tour_id,)):
        raise HTTPException(404, "Tour nicht gefunden")
    try:
        n = int(body.get("stars") or 0)
    except (TypeError, ValueError):
        raise HTTPException(400, "Ungültige Bewertung")
    if not 0 <= n <= 5:
        raise HTTPException(400, "Bewertung von 1 bis 5 Sternen")
    if n:
        db.execute("INSERT OR REPLACE INTO tour_rating(id,stars) VALUES(?,?)", (tour_id, n))
    else:
        db.execute("DELETE FROM tour_rating WHERE id=?", (tour_id,))
    return {"ok": True}


SAFETY_GEAR = ("lvs", "sonde", "schaufel", "helm", "airbag", "erste-hilfe", "biwaksack", "stirnlampe")


@router.get("/api/tours/{tour_id}/safety")
def api_safety_get(tour_id: str):
    r = db.one("SELECT level,grp,gear,note FROM tour_safety WHERE id=?", (tour_id,))
    if not r:
        return {"level": None, "grp": "", "gear": [], "note": "", "set": False}
    return {"level": r["level"], "grp": r["grp"] or "", "gear": [g for g in (r["gear"] or "").split(",") if g], "note": r["note"] or "", "set": True}


@router.post("/api/tours/{tour_id}/safety")
def api_safety_set(tour_id: str, body: dict):
    if not db.one("SELECT 1 x FROM tours WHERE id=?", (tour_id,)):
        raise HTTPException(404, "Tour nicht gefunden")
    lv = body.get("level")
    lv = int(lv) if lv not in (None, "", 0, "0") else None
    if lv is not None and not 1 <= lv <= 5:
        raise HTTPException(400, "Lawinenwarnstufe von 1 bis 5")
    gear = ",".join(g for g in (body.get("gear") or []) if g in SAFETY_GEAR)
    grp, note = str(body.get("grp") or "").strip()[:200], str(body.get("note") or "").strip()[:1000]
    if lv is None and not (gear or grp or note):
        db.execute("DELETE FROM tour_safety WHERE id=?", (tour_id,))
    else:
        db.execute("INSERT OR REPLACE INTO tour_safety(id,level,grp,gear,note) VALUES(?,?,?,?,?)", (tour_id, lv, grp, gear, note))
    return {"ok": True}
