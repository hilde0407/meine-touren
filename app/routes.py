"""Streckenpunkte aller Touren (von Komoot) zwischenspeichern."""
import json
import time

from . import config, db, jobs
from .jobs import log

def _D():
    return config.CACHE_DIR / "coords"


def __getattr__(name):
    if name == "D":
        return _D()
    raise AttributeError(name)


def _decimate(pts, n):
    if len(pts) <= n:
        return pts
    step = len(pts) / n
    out = [pts[int(i * step)] for i in range(n)]
    out.append(pts[-1])
    return out


def path_full(tid):
    return _D() / f"{tid}.json"


def path_small(tid):
    return _D() / f"{tid}.s.json"


def store(tid, items):
    """items: [(lat, lng, alt, t_ms)]"""
    _D().mkdir(parents=True, exist_ok=True)
    full = [[round(a, 5), round(b, 5), round(c, 1) if c is not None else None, t] for a, b, c, t in _decimate(list(items), 1500)]
    small = [[round(p[0], 4), round(p[1], 4)] for p in _decimate(full, 100)]
    path_full(tid).write_text(json.dumps(full))
    path_small(tid).write_text(json.dumps(small))
    return full


def load(tid):
    f = path_full(tid)
    return json.loads(f.read_text()) if f.exists() else None


def fetch_missing(k, pause=0.3, limit=None):
    tours = db.query("SELECT id FROM tours ORDER BY start_ts DESC")
    todo = [t["id"] for t in tours if not path_full(t["id"]).exists()]
    if limit:
        todo = todo[:limit]
    log(f"Routen: {len(todo)} von {len(tours)} Touren noch nicht geladen")
    ok = fail = 0
    for i, tid in enumerate(todo, 1):
        jobs.progress(f"Routen {i}/{len(todo)}")
        try:
            items = k.coordinates(tid)
            if items:
                store(tid, items); ok += 1
            else:
                fail += 1
        except Exception as e:  # noqa
            fail += 1
            if fail <= 3:
                log(f"  Route {tid}: {e}")
        time.sleep(pause)
    log(f"Routen: {ok} geladen, {fail} ohne Daten/Fehler")
    return ok


_OV = {}


def overview_bytes():
    """Die Übersichtslinien als fertiges JSON samt ETag. Wird nur neu gelesen, wenn sich Dateien geändert haben."""
    import hashlib
    import os
    d = _D()
    n, mx = 0, 0
    if d.exists():
        with os.scandir(d) as it:
            for e in it:
                if e.name.endswith(".s.json"):
                    n += 1
                    mx = max(mx, e.stat().st_mtime_ns)
    sig = (n, mx)
    hit = _OV.get(str(d))
    if hit and hit[0] == sig:
        return hit[1], hit[2]
    body = json.dumps(overview(), separators=(",", ":")).encode()
    etag = '"' + hashlib.sha1(body).hexdigest()[:16] + '"'
    _OV[str(d)] = (sig, body, etag)
    return body, etag


def overview():
    """{id: [[lat,lng],...]} aller zwischengespeicherten Touren."""
    out = {}
    if _D().exists():
        for f in _D().glob("*.s.json"):
            try:
                pts = [q for q in json.loads(f.read_text()) if isinstance(q, list) and len(q) >= 2 and q[0] is not None and q[1] is not None]
            except (ValueError, TypeError):
                continue
            if pts:
                out[f.name[:-7]] = pts
    return out
