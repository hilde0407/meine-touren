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
LIMITS = {"walk": (22, 12), "run": (35, 22), "bike": (90, 50), "other": (150, 60)}


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


def find_fast(pts, vmax_kmh, window_s=120, min_m=400):
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


def smooth_len(pts, half_s=25):
    """Länge des Tracks, nachdem die Positionen über ±half_s Sekunden (ohne Zeit: ±3 Punkte) gemittelt wurden."""
    n = len(pts)
    timed = all(p[3] is not None for p in pts)
    out, lo, hi = [], 0, 0
    for i in range(n):
        if timed:
            while pts[lo][3] < pts[i][3] - half_s * 1000:
                lo += 1
            while hi + 1 < n and pts[hi + 1][3] <= pts[i][3] + half_s * 1000:
                hi += 1
        else:
            lo, hi = max(0, i - 3), min(n - 1, i + 3)
        seg = pts[lo:hi + 1]
        out.append((sum(p[0] for p in seg) / len(seg), sum(p[1] for p in seg) / len(seg)))
    return sum(hav(out[i], out[i + 1]) for i in range(n - 1))


def jitter_m(pts):
    raw = sum(hav(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    return max(0.0, raw - smooth_len(pts)), raw


def timing(pts, sport):
    """Prüft die Zeitstempel: Sind sie nur gleichmäßig über die Strecke verteilt (konstantes Tempo in jedem 10-Minuten-Block),
    wurden sie nicht aufgezeichnet (z. B. geplante Route). Liefert auch eine Wanderzeit-Schätzung (SAC: 4,2 km/h, 400 m/h hoch, 800 m/h runter)."""
    from . import elev
    if pts[0][3] is None or pts[-1][3] is None:
        return {"uniform": False, "est_s": None}
    blk = {}
    for i in range(len(pts) - 1):
        b = pts[i][3] // 600000
        x = blk.setdefault(b, [0.0, 0.0])
        x[0] += hav(pts[i], pts[i + 1]); x[1] += max(0, (pts[i + 1][3] - pts[i][3]) / 1000)
    v = [d / s * 3.6 for d, s in blk.values() if s > 60 and d > 100]
    uniform = False
    if len(v) >= 5:
        m = sum(v) / len(v)
        uniform = m > 0 and (sum((x - m) ** 2 for x in v) / len(v)) ** 0.5 / m < 0.03
    est = None
    alts = [p[2] for p in pts if p[2] is not None]
    if kind(sport) == "walk" and len(alts) > 5:
        up, down = elev.ascent(elev.smooth(alts, 3, 3))
        dist = sum(hav(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
        h, vv = dist / 4200, up / 400 + down / 800
        est = int(3600 * (max(h, vv) + min(h, vv) / 2))
    return {"uniform": uniform, "est_s": est}


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
    tm = timing(pts, t["sport"])
    fast = find_fast(keep, sustain) if has_t and not tm["uniform"] else []      # bei erfundenen Zeitstempeln lässt sich Tempo nicht beurteilen
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
    jit, raw = jitter_m(keep)
    dur_now = (t["dur_s"] or 0)
    from .gpxtools import TZ
    from datetime import datetime
    st = datetime.fromtimestamp(t["start_ts"] or 0, TZ).replace(hour=0, minute=0, second=0, microsecond=0)
    d0 = int(st.timestamp())
    ph = db.one("SELECT COUNT(*) n, MIN(taken_ts) a, MAX(taken_ts) b FROM photos WHERE COALESCE(dated,1)=1 AND taken_ts IS NOT NULL AND "
                "(tour_id=? OR (taken_ts>=? AND taken_ts<?))", (tid, d0, d0 + 86400))
    photos_info = {"n": ph["n"], "first": ph["a"], "last": ph["b"]} if ph and ph["n"] >= 2 and ph["b"] - ph["a"] >= 600 else None
    at, an = anchor_times(pts, _photo_rows(t))
    anchors = {"n": an, "start": int(at[0]), "end": int(at[-1]), "dur_s": int(at[-1] - at[0])} if at else None
    return {"anchors": anchors, "photos": photos_info, "start_ts": t["start_ts"], "timing": tm, "jitter_m": round(jit), "raw_m": round(raw), "spike_m": round(sum(hav(pts[i], pts[i + 1]) for i in range(len(pts) - 1)) - raw),
            "dur_s": round(fx["orig_dur"] if fx else dur_now),"id": tid, "sport": t["sport"], "kind": kind(t["sport"]), "has_time": has_t, "n": len(pts),
            "limit_peak": peak, "limit_sustain": sustain, "spikes": runs, "n_spikes": len(bad), "fast": fast,
            "line": [[round(p[0], 5), round(p[1], 5)] for p in pts[::step]],
            "dist_km": round((fx["orig_dist"] if fx else t["dist_m"] or 0) / 1000, 2),
            "now_km": round((t["dist_m"] or 0) / 1000, 2), "fixed": bool(fx),
            "applied": {"spikes": fx["removed"], "excluded": fx["excluded"]} if fx else None}


def _photo_rows(t):
    from .gpxtools import TZ
    from datetime import datetime
    d0 = int(datetime.fromtimestamp(t["start_ts"] or 0, TZ).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
    return db.query("SELECT taken_ts, lat, lng FROM photos WHERE lat IS NOT NULL AND lng IS NOT NULL AND taken_ts IS NOT NULL AND COALESCE(dated,1)=1 "
                    "AND (tour_id=? OR (taken_ts>=? AND taken_ts<?))", (t["id"], d0, d0 + 86400))


def anchor_times(pts, rows, max_m=150):
    """Zeit jedes Trackpunkts aus Fotos mit Aufnahmeort: Ein Foto, das auf dem Track liegt, verrät, wann man dort war.
    Zwischen den Fotos wird entlang der Strecke linear interpoliert, davor und danach mit dem Tempo des nächsten Abschnitts.
    Gibt (Zeiten absolut in s, Anzahl Anker) oder (None, 0) zurück."""
    n = len(pts)
    cum = [0.0]
    for i in range(n - 1):
        cum.append(cum[-1] + hav(pts[i], pts[i + 1]))
    cand = {}
    for r in rows:
        best, bi = None, None
        for i in range(0, n, max(1, n // 4000)):
            d = hav((r["lat"], r["lng"]), pts[i])
            if best is None or d < best:
                best, bi = d, i
        if best is not None and best <= max_m:
            cand.setdefault(bi, []).append(r["taken_ts"])
    items = sorted((cum[i], min(v)) for i, v in cand.items())
    # nur zeitlich zur Strecke passende Anker behalten (längste wachsende Folge)
    best_seq = []
    seqs = []
    for k, it in enumerate(items):
        seqs.append(max((seqs[j] for j in range(k) if items[j][1] < it[1] and items[j][0] < it[0]), key=len, default=[]) + [it])
        if len(seqs[-1]) > len(best_seq):
            best_seq = seqs[-1]
    if len(best_seq) < 3 or best_seq[-1][1] - best_seq[0][1] < 600:
        return None, len(best_seq)
    A = best_seq
    pace = lambda a, b: min(3.0, max(0.3, (b[1] - a[1]) / max(1.0, b[0] - a[0])))
    p0, p1 = pace(A[0], A[1]), pace(A[-2], A[-1])
    out, k = [], 0
    for c in cum:
        if c <= A[0][0]:
            out.append(A[0][1] - (A[0][0] - c) * p0)
        elif c >= A[-1][0]:
            out.append(A[-1][1] + (c - A[-1][0]) * p1)
        else:
            while A[k + 1][0] < c:
                k += 1
            f = (c - A[k][0]) / max(1e-6, A[k + 1][0] - A[k][0])
            out.append(A[k][1] + f * (A[k + 1][1] - A[k][1]))
    return out, len(A)


def diagnose(tid):
    """Kurze Ursachenliste für eine auffällige Tour (leer = Track unauffällig, dann liegt es wohl an der Sportart)."""
    try:
        t = db.one("SELECT * FROM tours WHERE id=?", (str(tid),))
        pts = _load(tid, fixed=bool(db.one("SELECT 1 x FROM track_fix WHERE id=?", (str(tid),)))) if t else None
        if not t or not pts or len(pts) < 5:
            return None
        peak, sustain = LIMITS[kind(t["sport"])]
        out = []
        tm = timing(pts, t["sport"])
        if tm["uniform"]:
            out.append("Zeitangaben nicht aufgezeichnet (überall gleiches Tempo) – Dauer korrigieren")
        bad = find_spikes(pts, peak)
        if bad:
            out.append(f"{len(bad)} GPS-Ausreißer")
        if pts[0][3] is not None and not tm["uniform"]:
            keep = [p for i, p in enumerate(pts) if i not in set(bad)]
            fast = find_fast(keep, sustain)
            if fast:
                out.append(f"{len(fast)} Abschnitt{'e' if len(fast) > 1 else ''} mit Fahrt-Tempo (Seilbahn, Bus, Auto?)")
        jit, raw = jitter_m(pts)
        if jit >= 300 and jit >= raw * 0.05:
            out.append(f"GPS-Zittern (Strecke ca. {jit / 1000:.1f} km zu lang)".replace(".", ","))
        return out
    except Exception:  # noqa
        return None


def apply(tid, remove_spikes=True, exclude=(), smooth=False, set_dur_s=None, set_start_ts=None, use_anchors=False):
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
    new_dur = None
    if use_anchors:                                       # Zeit der Trackpunkte aus Fotos mit Aufnahmeort
        at, an = anchor_times(pts, _photo_rows(t))
        if not at:
            raise RuntimeError("Zu wenige Fotos auf dem Track, um die Zeit daraus abzuleiten")
        t0 = at[0]
        pts = [[p[0], p[1], p[2], int((a - t0) * 1000)] for p, a in zip(pts, at)]
        set_start_ts, set_dur_s = int(t0), int(at[-1] - t0)
    if set_dur_s:                                         # Zeitstempel auf die angegebene Dauer strecken (bei nicht aufgezeichneten Zeiten)
        new_dur = int(set_dur_s)
        if not 60 <= new_dur <= 14 * 86400:
            raise ValueError("Unplausible Dauer")
        if pts[-1][3] is None or pts[-1][3] <= 0:
            raise RuntimeError("Der Track hat keine Zeitstempel")
        f = new_dur * 1000 / pts[-1][3]
        pts = [[p[0], p[1], p[2], None if p[3] is None else int(p[3] * f)] for p in pts]
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
    jit = jitter_m(keep)[0] if smooth else 0.0
    dist = max(0.0, (o_dist or 0) - (before - after) - ex_m - jit)
    dur = max(0.0, ((new_dur if new_dur else (o_dur or 0)) - ex_s))
    if not fx:                                            # Original sichern
        if local:
            orig_gpx(tid).write_text(tracks.gpx_file(tid).read_text(encoding="utf-8"), encoding="utf-8")
        else:
            routes.D.mkdir(parents=True, exist_ok=True)
            orig_path(tid).write_text(json.dumps(pts))
    if set_start_ts:
        t = dict(t); t["start_ts"] = int(set_start_ts)
    if local:
        tracks.gpx_file(tid).write_text(build_gpx(t, keep), encoding="utf-8")
    routes.store(tid, [tuple(p) for p in keep])
    cur_t = db.one("SELECT start_ts, end_ts FROM tours WHERE id=?", (tid,))
    o_end = fx["orig_end"] if fx and fx["orig_end"] else cur_t["end_ts"]
    o_start = fx["orig_start"] if fx and fx["orig_start"] else cur_t["start_ts"]
    with db.cur() as c:
        c.execute("INSERT OR REPLACE INTO track_fix(id,orig_dist,orig_dur,dist,dur,removed,excluded,ts,orig_end,orig_start) VALUES(?,?,?,?,?,?,?,?,?,?)",
                  (tid, o_dist, o_dur, dist, dur, len(bad), len(ex), int(time.time()), o_end, o_start))
        c.execute("UPDATE tours SET dist_m=?,dur_s=? WHERE id=?", (dist, dur, tid))
        if set_start_ts:
            c.execute("UPDATE tours SET start_ts=? WHERE id=?", (int(set_start_ts), tid))
        if new_dur:
            c.execute("UPDATE tours SET end_ts=? WHERE id=?", ((t["start_ts"] or 0) + new_dur, tid))
    if new_dur or set_start_ts:
        try:
            from . import photos
            photos.assign_all()
        except Exception:  # noqa
            pass
    return {"dist_m": dist, "orig_dist": o_dist, "dur_s": dur, "orig_dur": o_dur, "removed": len(bad), "excluded": len(ex), "jitter_m": jit}


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
        if fx["orig_end"]:
            c.execute("UPDATE tours SET end_ts=? WHERE id=?", (fx["orig_end"], tid))
        if fx["orig_start"]:
            c.execute("UPDATE tours SET start_ts=? WHERE id=?", (fx["orig_start"], tid))
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
