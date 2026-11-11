"""„Wie oft bin ich diese Strecke schon gegangen?“

Vergleicht die Strecken aller Touren miteinander und fasst zusammen, welche Touren
weitgehend denselben Weg nehmen. Das Ergebnis wird zwischengespeichert und beim Laden
der Seite im Hintergrund schon vorgerechnet.
"""
import json
import threading

from fastapi import APIRouter

from . import config, ctx, db, memo, routes

router = APIRouter()


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
    old = _WARM.get(uid)
    if old is not None and old.is_alive():           # läuft für diesen Benutzer schon: nicht bei jedem Seitenaufruf einen weiteren Faden starten
        return
    _WARM[uid] = th = threading.Thread(target=run, daemon=True)
    th.start()


_WARM = {}


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
