"""Herzfrequenz: Speicherung (Zusatzdatei bzw. GPX), Abgleich mit Zepp und die Schnittstelle für die Pulskarte.

Der Puls einer Tour liegt entweder im lokalen GPX (gpxtpx:hr) oder – bei Touren ohne eigenes GPX, z. B. aus Komoot –
in der Zusatzdatei tracks/<id>.hr.json ([[Sekunden seit Start, bpm], …]). Lesen: tracks.hr_series()."""
import json
import time

from fastapi import APIRouter

from . import config, db, gpxtools, jobs, sync, tracks, zepp
from .jobs import log

router = APIRouter()
hr_sidecar = tracks.hr_sidecar


def _sc_load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


_HR_CACHE = {}


def tours_with_hr():
    """IDs aller Touren mit Pulsdaten (Zusatzdatei oder Puls im lokalen GPX); billig, da nur Dateigrößen/-zeiten geprüft werden."""
    ids = set()
    if not config.TRACK_DIR.exists():
        return ids
    for f in config.TRACK_DIR.iterdir():
        n = f.name
        try:
            st = f.stat()
        except OSError:
            continue
        if n.endswith(".hr.json"):
            if st.st_size >= 40:
                ids.add(n[:-8])
        elif n.endswith(".gpx"):
            c = _HR_CACHE.get(str(f))
            if not c or c[0] != st.st_mtime_ns:
                try:
                    has = "gpxtpx:hr" in f.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    has = False
                c = _HR_CACHE[str(f)] = (st.st_mtime_ns, has)
            if c[1]:
                ids.add(n[:-4])
    return ids


def backfill_hr(api=None):
    """Puls zu Touren nachladen, für die es ein passendes Zepp-Training gibt (gleiche ID z<Nr> oder gleicher Start/gleiche Strecke –
    auch Komoot- oder Datei-Touren). Touren, Notizen und Fotos bleiben unberührt: der Puls kommt in eine Zusatzdatei (und ins lokale GPX)."""
    import json
    api = api or sync._zepp_api()
    config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
    tours = db.query("SELECT id,start_ts,dist_m,dur_s FROM tours")
    byid = {t["id"]: t for t in tours}
    tol = db.get_int("dup_tolerance_s", 300)
    todo = []
    for s in api.history():
        tr = int(s["trackid"])
        t = byid.get(f"z{tr}") or sync.is_duplicate(tr, float(s.get("dis") or 0), int(float(s.get("run_time") or 0)), tours, tol)
        if not t:
            continue
        gf = tracks.gpx_file(t["id"])
        sc = hr_sidecar(t["id"])
        if (sc.exists() and len(_sc_load(sc)) >= 5) or (gf.exists() and "gpxtpx:hr" in gf.read_text(encoding="utf-8", errors="ignore")):
            continue
        todo.append((s, t, gf))
    log(f"Puls abgleichen: {len(todo)} Touren mit passendem Zepp-Training, aber ohne Puls")
    done = 0
    for i, (s, t, gf) in enumerate(todo, 1):
        jobs.progress(f"Puls {i}/{len(todo)}")
        try:
            det = api.detail(s)
            pts = zepp.decode_points(s, det)
            hr = [(p[0], p[4]) for p in pts if p[4]]
            if not hr:
                raw = str(det.get("heart_rate") or "")
                log(f"  {t['id']}: kein Puls erkannt – Zepp-Feld heart_rate: " + (f"{len(raw)} Zeichen, Anfang „{raw[:80]}“" if raw else "leer"))
                hr_sidecar(t["id"]).write_text("[]", encoding="utf-8")            # nicht bei jedem Lauf erneut abfragen
                continue
            hr_sidecar(t["id"]).write_text(json.dumps([[a - int(s["trackid"]), b] for a, b in hr]), encoding="utf-8")
            if gf.exists():
                text, n = tracks.merge_hr(gf.read_text(encoding="utf-8"), hr)
                if n:
                    gf.write_text(text, encoding="utf-8")
            done += 1
            log(f"  {t['id']}: {len(hr)} Pulswerte (Zepp-Daten: {len(str(det.get('heart_rate') or ''))} Zeichen, {len(pts)} Streckenpunkte)")
        except Exception as e:  # noqa
            log(f"  {t['id']}: {e}")
        time.sleep(0.2)
    log(f"Puls abgleichen: {done} Touren ergänzt")


def _series(tour_id):
    """Pulsverlauf einer Tour als [[Sekunden seit Start, bpm, Punktindex], …] und die Zahl der Streckenpunkte."""
    side = hr_sidecar(tour_id)
    sd = _sc_load(side) if side.exists() else []
    if sd:
        return [[int(a), int(b), i] for i, (a, b) in enumerate(sd)], len(sd)
    f = tracks.gpx_file(tour_id)
    if not f.exists():
        return [], 0
    typ, raw = gpxtools._points_gpx_hr(f.read_text(encoding="utf-8", errors="ignore"))
    rows = [(gpxtools.parse_time(t), hr, i) for i, (la, lo, el, t, hr) in enumerate(raw) if hr and not (la == 0 and lo == 0)]
    if len(rows) < 5:
        return [], len(raw)
    t0 = gpxtools.parse_time(raw[0][3])
    return [[int((t - t0).total_seconds()), hr, i] for t, hr, i in rows], len(raw)


def _hr_max():
    try:
        return int(db.get("hr_max") or 0) or 185
    except ValueError:
        return 185


def _zone(bpm, hmax):
    return min(4, max(0, int((bpm / hmax - 0.5) / 0.1)))


@router.get("/api/tours/{tour_id}/hr")
def api_hr(tour_id: str):
    """Pulsverlauf einer Tour mit Durchschnitt, Extremwerten und Zeit in den fünf Pulszonen."""
    pts, total = _series(tour_id)
    if len(pts) < 5:
        return {"n": 0}
    hmax = max(_hr_max(), max(p[1] for p in pts))
    zs = [0] * 5
    for a, b in zip(pts, pts[1:]):
        zs[_zone(a[1], hmax)] += min(b[0] - a[0], 30)
    vals = [p[1] for p in pts]
    return {"n": len(pts), "pts": pts, "avg": round(sum(vals) / len(vals)), "max": max(vals), "min": min(vals), "hrmax": hmax, "zones": zs, "total": total}


_SUM = {}      # Dateipfad -> (Änderungszeit, {bpm: Sekunden}, Durchschnitt, Maximum)


def _hist(tour_id):
    """Sekunden je Pulswert einer Tour (zwischengespeichert, solange sich die Datei nicht ändert)."""
    side = hr_sidecar(tour_id)
    f = side if side.exists() and side.stat().st_size >= 40 else tracks.gpx_file(tour_id)
    if not f.exists():
        return None
    key, mt = str(f), f.stat().st_mtime_ns
    c = _SUM.get(key)
    if not c or c[0] != mt:
        pts, _ = _series(tour_id)
        h = {}
        for a, b in zip(pts, pts[1:]):
            h[a[1]] = h.get(a[1], 0) + min(b[0] - a[0], 30)
        vals = [p[1] for p in pts]
        c = _SUM[key] = (mt, h, round(sum(vals) / len(vals)) if vals else 0, max(vals) if vals else 0)
    return c


@router.get("/api/hr/stats")
def api_hr_stats():
    """Belastung je Tour: Durchschnitts- und Maximalpuls sowie Sekunden in den fünf Pulszonen (einheitlicher Maximalpuls für alle Touren)."""
    rows = []
    for tid in sorted(tours_with_hr()):
        c = _hist(tid)
        if c and c[1]:
            rows.append((tid, c))
    hmax = max([_hr_max()] + [c[3] for _, c in rows])
    out = []
    for tid, (_, h, avg, mx) in rows:
        zs = [0] * 5
        for bpm, sec in h.items():
            zs[_zone(bpm, hmax)] += sec
        out.append({"id": tid, "avg": avg, "max": mx, "zones": zs})
    return {"hrmax": hmax, "tours": out}
