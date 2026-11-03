"""GPS-Track korrigieren: Ausreißer (Sprünge) entfernen und schnelle Abschnitte (Seilbahn, Bus, Auto) aus der Wertung nehmen.

* Ausreißer: Punkte, die mit unmöglichem Tempo vom vorigen guten Punkt „wegspringen“ – sie werden aus dem Track gelöscht.
* Schnelle Abschnitte: längere Strecken mit Tempo weit über dem, was zur Sportart passt. Sie bleiben im Track sichtbar, ihre
  Strecke und Zeit werden aber aus Länge und Dauer der Tour herausgerechnet („Fahrt“).
Das Original bleibt erhalten (Wiederherstellen jederzeit möglich)."""
import json
import math
import time

from . import config, db, routes, tracks

WALK = ("hike", "nordicwalking", "snowshoe", "mountaineering")
# (Spitzentempo in km/h für Sprung-Erkennung, Dauertempo in km/h für „schneller Abschnitt“)
LIMITS = {"walk": (22, 9), "run": (35, 20), "bike": (90, 45), "other": (150, 60)}


def kind(sport):
    s = sport or "hike"
    if s in WALK:
        return "walk"
    if s in ("jogging", "nordic"):
        return "run"
    if s in ("touringbicycle", "e_touringbicycle", "racebike", "mtb", "e_mtb"):
        return "bike"
    return "other"


def hav(a, b):
    p = math.pi / 180
    dl = (b[1] - a[1]) * p
    h = math.sin((b[0] - a[0]) * p / 2) ** 2 + math.cos(a[0] * p) * math.cos(b[0] * p) * math.sin(dl / 2) ** 2
    return 12742000 * math.asin(min(1, math.sqrt(h)))


def orig_path(tid):
    return routes.D / f"{tid}.orig-track.json"


def orig_gpx(tid):
    return config.TRACK_DIR / f"{tid}.orig.gpx"


def _load(tid, fixed=False):
    """Punkte [lat,lng,alt,t_ms] – bei lokalen Touren aus der GPX-Datei (volle Auflösung), sonst aus dem Routen-Cache.
    Ist die Tour schon korrigiert, wird vom Original ausgegangen."""
    tid = str(tid)
    if fixed and orig_gpx(tid).exists():
        return [list(p) for p in tracks.points_from_gpx(orig_gpx(tid).read_text(encoding="utf-8"))]
    if fixed and orig_path(tid).exists():
        return json.loads(orig_path(tid).read_text())
    f = tracks.gpx_file(tid)
    if f.exists():
        return [list(p) for p in tracks.points_from_gpx(f.read_text(encoding="utf-8"))]
    return routes.load(tid)


def find_spikes(pts, vmax_kmh, look=12):
    """Indizes von Punkten, die vom letzten guten Punkt mit unmöglichem Tempo wegspringen und innerhalb der nächsten Punkte wieder
    auf die Strecke zurückkehren. Bleibt der neue Ort dauerhaft (Lücke, Fahrt), ist das kein Ausreißer."""
    def jumps(a, b):
        d = hav(pts[a], pts[b])
        t0, t1 = pts[a][3], pts[b][3]
        if t0 is not None and t1 is not None:
            return d > 40 and d / max(1.0, (t1 - t0) / 1000) * 3.6 > vmax_kmh
        return d > 300                                     # ohne Zeit: nur große Sprünge
    bad, last, i, n = [], 0, 1, len(pts)
    while i < n:
        if jumps(last, i):
            k = next((k for k in range(i + 1, min(n, i + look + 1)) if not jumps(last, k) and hav(pts[last], pts[k]) < 0.5 * hav(pts[last], pts[i])), None)
            if k is not None:
                bad.extend(range(i, k))
                i = k
                continue
        last = i
        i += 1
    return bad


def find_fast(pts, vmax_kmh, window_s=90, min_m=300):
    """Zusammenhängende Abschnitte (Indexbereiche), in denen das Tempo über ein Zeitfenster dauerhaft über der Grenze liegt."""
    n = len(pts)
    if n < 3 or pts[0][3] is None or pts[-1][3] is None:
        return []
    flag = [False] * n
    j = 0
    for i in range(n):
        if pts[i][3] is None:
            continue
        while j < n - 1 and (pts[j][3] is None or pts[j][3] - pts[i][3] < window_s * 1000):
            j += 1
        dt = (pts[j][3] - pts[i][3]) / 1000 if pts[j][3] is not None else 0
        if dt >= 10 and j > i:
            d = sum(hav(pts[k], pts[k + 1]) for k in range(i, j))
            if d / dt * 3.6 > vmax_kmh:
                for k in range(i, j + 1):
                    flag[k] = True
    out, i = [], 0
    while i < n:
        if not flag[i]:
            i += 1
            continue
        k = i
        while k + 1 < n and flag[k + 1]:
            k += 1
        i0, i1 = i, k
        def seg_v(x):
            a, b = pts[x], pts[x + 1]
            return hav(a, b) / max(1, (b[3] - a[3]) / 1000) * 3.6 if a[3] is not None and b[3] is not None else 0
        while i0 < i1 and seg_v(i0) <= vmax_kmh:          # Ränder des Zeitfensters auf das tatsächlich schnelle Stück kürzen
            i0 += 1
        while i1 > i0 and seg_v(i1 - 1) <= vmax_kmh:
            i1 -= 1
        dist = sum(hav(pts[x], pts[x + 1]) for x in range(i0, i1))
        secs = ((pts[i1][3] or 0) - (pts[i0][3] or 0)) / 1000
        if dist >= min_m and secs > 0:
            mx = max((hav(pts[x], pts[x + 1]) / max(1, (pts[x + 1][3] - pts[x][3]) / 1000) * 3.6 for x in range(i0, i1)
                      if pts[x][3] is not None and pts[x + 1][3] is not None), default=0)
            out.append({"i0": i0, "i1": i1, "m": round(dist), "s": round(secs), "avg": round(dist / secs * 3.6, 1), "max": round(mx, 1),
                        "t0": pts[i0][3] // 1000})
        i = k + 1
    return out


def _line(pts, i0, i1, n=60):
    seg = pts[i0:i1 + 1]
    step = max(1, len(seg) // n)
    return [[round(p[0], 5), round(p[1], 5)] for p in seg[::step]] + [[round(seg[-1][0], 5), round(seg[-1][1], 5)]]


def analyse(tid):
    tid = str(tid)
    t = db.one("SELECT * FROM tours WHERE id=?", (tid,))
    if not t:
        raise KeyError(tid)
    fx = db.one("SELECT * FROM track_fix WHERE id=?", (tid,))
    pts = _load(tid, fixed=bool(fx))
    if not pts or len(pts) < 5:
        raise RuntimeError("Für diese Tour liegt keine Strecke vor (Verwaltung → „Routen laden“).")
    peak, sustain = LIMITS[kind(t["sport"])]
    has_t = pts[0][3] is not None and pts[-1][3] is not None
    bad = find_spikes(pts, peak)
    badset = set(bad)
    keep = [p for i, p in enumerate(pts) if i not in badset]
    fast = find_fast(keep, sustain) if has_t else []
    for k, f in enumerate(fast):
        f["id"] = k
        f["line"] = _line(keep, f["i0"], f["i1"])
    runs, i = [], 0
    while i < len(bad):                                    # Ausreißer zu Gruppen zusammenfassen
        k = i
        while k + 1 < len(bad) and bad[k + 1] == bad[k] + 1:
            k += 1
        runs.append({"i0": bad[i], "i1": bad[k], "n": k - i + 1, "at": [round(pts[bad[i]][0], 5), round(pts[bad[i]][1], 5)]})
        i = k + 1
    step = max(1, len(pts) // 800)
    return {"id": tid, "sport": t["sport"], "kind": kind(t["sport"]), "has_time": has_t, "n": len(pts),
            "limit_peak": peak, "limit_sustain": sustain, "spikes": runs, "n_spikes": len(bad), "fast": fast,
            "line": [[round(p[0], 5), round(p[1], 5)] for p in pts[::step]],
            "dist_km": round((fx["orig_dist"] if fx else t["dist_m"] or 0) / 1000, 2),
            "now_km": round((t["dist_m"] or 0) / 1000, 2), "fixed": bool(fx),
            "applied": {"spikes": fx["removed"], "excluded": fx["excluded"]} if fx else None}


def apply(tid, remove_spikes=True, exclude=()):
    tid = str(tid)
    t = db.one("SELECT * FROM tours WHERE id=?", (tid,))
    if not t:
        raise KeyError(tid)
    fx = db.one("SELECT * FROM track_fix WHERE id=?", (tid,))
    local = tracks.gpx_file(tid).exists()
    pts = _load(tid, fixed=bool(fx))
    if not pts or len(pts) < 5:
        raise RuntimeError("Für diese Tour liegt keine Strecke vor")
    peak, sustain = LIMITS[kind(t["sport"])]
    bad = set(find_spikes(pts, peak)) if remove_spikes else set()
    keep = [p for i, p in enumerate(pts) if i not in bad]
    fast = find_fast(keep, sustain) if keep[0][3] is not None else []
    exset = {int(x) for x in exclude}
    ex = [f for k, f in enumerate(fast) if k in exset]
    before = sum(hav(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    after = sum(hav(keep[i], keep[i + 1]) for i in range(len(keep) - 1))
    ex_m = sum(sum(hav(keep[x], keep[x + 1]) for x in range(f["i0"], f["i1"])) for f in ex)
    ex_s = sum(f["s"] for f in ex)
    o_dist = fx["orig_dist"] if fx else t["dist_m"]
    o_dur = fx["orig_dur"] if fx else t["dur_s"]
    # Länge: Original-Wert um die entfernten Sprünge und Fahrten verringern (die gespeicherte Länge kann von der Punktesumme abweichen)
    dist = max(0.0, (o_dist or 0) - (before - after) - ex_m)
    dur = max(0.0, (o_dur or 0) - ex_s)
    if not fx:                                            # Original sichern
        if local:
            orig_gpx(tid).write_text(tracks.gpx_file(tid).read_text(encoding="utf-8"), encoding="utf-8")
        else:
            routes.D.mkdir(parents=True, exist_ok=True)
            orig_path(tid).write_text(json.dumps(pts))
    if local:
        tracks.gpx_file(tid).write_text(build_gpx(t, keep), encoding="utf-8")
    routes.store(tid, [tuple(p) for p in keep])
    with db.cur() as c:
        c.execute("INSERT OR REPLACE INTO track_fix(id,orig_dist,orig_dur,dist,dur,removed,excluded,ts) VALUES(?,?,?,?,?,?,?,?)",
                  (tid, o_dist, o_dur, dist, dur, len(bad), len(ex), int(time.time())))
        c.execute("UPDATE tours SET dist_m=?,dur_s=? WHERE id=?", (dist, dur, tid))
    return {"dist_m": dist, "orig_dist": o_dist, "dur_s": dur, "orig_dur": o_dur, "removed": len(bad), "excluded": len(ex)}


def build_gpx(t, pts):
    from datetime import datetime, timezone
    from xml.sax.saxutils import escape
    start = t["start_ts"]
    fmt = lambda ts: datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = []
    for p in pts:
        ele = f"<ele>{p[2]}</ele>" if p[2] is not None else ""
        tm = f"<time>{fmt(int(start + p[3] / 1000))}</time>" if p[3] is not None else ""
        body.append(f'<trkpt lat="{p[0]}" lon="{p[1]}">{ele}{tm}</trkpt>')
    name = escape(t["name"] or str(t["id"]))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Meine Touren" xmlns="http://www.topografix.com/GPX/1/1">\n'
            f"<metadata><name>{name}</name><time>{fmt(start)}</time></metadata>\n"
            f"<trk><name>{name}</name><type>{t['sport'] or 'hike'}</type><trkseg>\n" + "\n".join(body) + "\n</trkseg></trk></gpx>\n")


def restore(tid):
    tid = str(tid)
    fx = db.one("SELECT * FROM track_fix WHERE id=?", (tid,))
    if not fx:
        return False
    pts = None
    if orig_gpx(tid).exists():
        txt = orig_gpx(tid).read_text(encoding="utf-8")
        tracks.gpx_file(tid).write_text(txt, encoding="utf-8")
        pts = [tuple(p) for p in tracks.points_from_gpx(txt)]
        orig_gpx(tid).unlink()
    elif orig_path(tid).exists():
        pts = [tuple(p) for p in json.loads(orig_path(tid).read_text())]
        orig_path(tid).unlink()
    if pts:
        routes.store(tid, pts)
    with db.cur() as c:
        c.execute("UPDATE tours SET dist_m=?,dur_s=? WHERE id=?", (fx["orig_dist"], fx["orig_dur"], tid))
        c.execute("DELETE FROM track_fix WHERE id=?", (tid,))
    return True


def drop(tid):
    """Korrektur verwerfen, ohne Werte zurückzuschreiben (Komoot-Daten werden gerade frisch geladen)."""
    tid = str(tid)
    orig_path(tid).unlink(missing_ok=True)
    db.execute("DELETE FROM track_fix WHERE id=?", (tid,))


def reapply(komoot_tours):
    """Nach dem Neuladen der Tourenliste von Komoot: Korrektur erhalten, solange Komoot die Länge nicht selbst geändert hat."""
    k = {str(t["id"]): t for t in komoot_tours}
    for f in db.query("SELECT * FROM track_fix"):
        t = k.get(f["id"])
        if t is None:
            continue                                      # lokale Tour (nicht von Komoot): bleibt
        if abs((t["dist_m"] or 0) - (f["orig_dist"] or 0)) < 1:
            db.execute("UPDATE tours SET dist_m=?,dur_s=? WHERE id=?", (f["dist"], f["dur"], f["id"]))
        else:
            drop(f["id"])
            for p in (routes.path_full(f["id"]), routes.path_small(f["id"])):
                p.unlink(missing_ok=True)
