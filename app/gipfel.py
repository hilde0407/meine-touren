"""Gipfel zu den Touren bestimmen.

Für Touren mit genug Aufstieg wird der höchste Punkt der Strecke gesucht und bei
OpenStreetMap nach dem Namen des Gipfels gefragt – schonend, mit Pause zwischen den
Anfragen, und Fehler lassen die Tour einfach offen für den nächsten Durchlauf.
"""
import time

from fastapi import APIRouter

from . import db, extras, jobs, memo, routes

HIKE = ("hike", "mountaineering", "skitour", "snowshoe", "nordicwalking", "skialpin")   # Sportarten, bei denen ein Gipfel Sinn ergibt

router = APIRouter()


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
