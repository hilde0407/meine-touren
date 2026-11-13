"""Fehlerhafte GPS-Höhen mit einem Geländemodell (AWS Terrain Tiles / Terrarium) korrigieren."""
import io
import json
import time
from math import floor, log, pi, radians, tan

import requests

from . import config, db, routes

Z = 12
UP = "https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{z}/{x}/{y}.png"
DIR = config.TILE_CACHE / "dem"
UA = {"User-Agent": "MeineTouren/1.0 (privates Selbsthosting; https://github.com/hilde0407/meine-touren)"}


def orig_path(tid):
    return routes.D / f"{tid}.orig.json"


def _tile(x, y):
    from PIL import Image
    f = DIR / str(Z) / str(x) / f"{y}.png"
    if not f.exists():
        r = requests.get(UP.format(z=Z, x=x, y=y), headers=UA, timeout=15)
        if r.status_code != 200:
            raise RuntimeError(f"Geländedaten: HTTP {r.status_code}")
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(r.content)
    return Image.open(f).convert("RGB").load()


def _px(lat, lng):
    n = 2 ** Z
    fx = (lng + 180) / 360 * n
    fy = (1 - log(tan(radians(lat)) + 1 / __import__("math").cos(radians(lat))) / pi) / 2 * n
    return fx, fy


def terrain(points, tile=_tile):
    """Geländehöhe (m) für [(lat,lng)] per bilinearer Interpolation."""
    tiles, out = {}, []
    for lat, lng in points:
        fx, fy = _px(lat, lng)
        gx, gy = fx * 256 - 0.5, fy * 256 - 0.5
        x0, y0 = floor(gx), floor(gy)
        wx, wy = gx - x0, gy - y0

        def h(ix, iy):
            tx, ty = ix // 256, iy // 256
            if (tx, ty) not in tiles:
                tiles[(tx, ty)] = tile(tx, ty)
            r, g, b = tiles[(tx, ty)][ix % 256, iy % 256]
            return r * 256 + g + b / 256 - 32768
        out.append(h(x0, y0) * (1 - wx) * (1 - wy) + h(x0 + 1, y0) * wx * (1 - wy) + h(x0, y0 + 1) * (1 - wx) * wy + h(x0 + 1, y0 + 1) * wx * wy)
    return out


def smooth(v, med=5, avg=5):
    n = len(v)
    m = [sorted(v[max(0, i - med // 2): i + med // 2 + 1])[len(v[max(0, i - med // 2): i + med // 2 + 1]) // 2] for i in range(n)]
    return [sum(m[max(0, i - avg // 2): i + avg // 2 + 1]) / len(m[max(0, i - avg // 2): i + avg // 2 + 1]) for i in range(n)]


def clean(v, lo=-500.0, hi=9000.0):
    """Unmögliche Höhenwerte (z. B. Platzhalter „keine Höhe“ wie −20 000 m) durch den nächsten gültigen Nachbarn ersetzen."""
    ok = [x is not None and lo <= x <= hi for x in v]
    if not any(ok):
        return [None] * len(v) if all(x is None for x in v) else [0.0] * len(v)
    out, last = list(v), None
    for i, x in enumerate(v):
        if ok[i]:
            last = x
        elif last is not None:
            out[i] = last
    nxt = None
    for i in range(len(v) - 1, -1, -1):
        if ok[i]:
            nxt = v[i]
        elif out[i] is None or not (lo <= out[i] <= hi):
            out[i] = nxt
    return out


def clean_gpx(text):
    """Alle <ele>-Werte einer GPX-Datei bereinigen. Gibt (Text, Anzahl ersetzter Werte) zurück."""
    import re
    vals = re.findall(r"<ele>([^<]*)</ele>", text)
    if not vals:
        return text, 0
    nums = []
    for x in vals:
        try:
            nums.append(float(x))
        except ValueError:
            nums.append(None)
    fixed = clean(nums)
    n = sum(1 for a, b in zip(nums, fixed) if a != b)
    if not n:
        return text, 0
    it = iter(fixed)
    return re.sub(r"<ele>[^<]*</ele>", lambda m: "<ele>%s</ele>" % (round(next(it), 2)), text), n


def recompute_local():
    """Auf-/Abstieg lokaler Touren (GPX/Zepp) mit bereinigten Höhen neu berechnen. Durch das Geländemodell korrigierte Touren bleiben unberührt."""
    from . import jobs, tracks
    fixed = {r["id"] for r in db.query("SELECT id FROM elev_fix")}
    n = ch = 0
    for t in db.query("SELECT id,up_m,down_m FROM tours WHERE source='local'"):
        if t["id"] in fixed:
            continue
        f = tracks.gpx_file(t["id"])
        if not f.exists():
            continue
        text, bad = clean_gpx(f.read_text(encoding="utf-8"))
        items = tracks.points_from_gpx(text)
        alts = [p[2] for p in items if p[2] is not None]
        if len(alts) < 6:
            continue
        up, down = ascent(smooth(clean(alts), 3, 3))
        n += 1
        if bad or abs(up - (t["up_m"] or 0)) >= 1 or abs(down - (t["down_m"] or 0)) >= 1:
            if bad:
                f.write_text(text, encoding="utf-8"); routes.store(t["id"], items)
            db.execute("UPDATE tours SET up_m=?,down_m=? WHERE id=?", (up, down, t["id"])); ch += 1
            if ch <= 5:
                jobs.log(f"  {t['id']}: Aufstieg {round(t['up_m'] or 0)} m → {round(up)} m")
    jobs.log(f"Höhenmeter: {n} lokale Touren geprüft, {ch} korrigiert")
    return ch


def ascent(v, hyst=4.0):
    """Auf-/Abstieg mit Schwelle (kleine Schwankungen zählen nicht)."""
    up = down = 0.0
    ref = v[0]
    for h in v[1:]:
        if h - ref >= hyst:
            up += h - ref; ref = h
        elif ref - h >= hyst:
            down += ref - h; ref = h
    return up, down


def suspicious(t):
    km = (t["dist_m"] or 0) / 1000
    return km > 0.5 and (t["up_m"] or 0) > 120 * km and (t["up_m"] or 0) > 400


def fix(tid):
    tid = str(tid)
    t = db.one("SELECT * FROM tours WHERE id=?", (tid,))
    if not t:
        raise KeyError(tid)
    cur = db.one("SELECT * FROM elev_fix WHERE id=?", (tid,))
    pts = (json.loads(orig_path(tid).read_text()) if cur and orig_path(tid).exists() else None) or routes.load(tid)
    if not pts or len(pts) < 5:
        raise RuntimeError("Keine Streckenpunkte vorhanden")
    dem = smooth(terrain([(p[0], p[1]) for p in pts]))
    up, down = ascent(dem)
    if not cur:
        orig_path(tid).write_text(json.dumps(pts))
    new = [[p[0], p[1], round(h, 1), p[3]] for p, h in zip(pts, dem)]
    routes.D.mkdir(parents=True, exist_ok=True)
    routes.path_full(tid).write_text(json.dumps(new))
    o_up, o_down = (cur["orig_up"], cur["orig_down"]) if cur else (t["up_m"], t["down_m"])
    with db.cur() as c:
        c.execute("INSERT OR REPLACE INTO elev_fix(id,orig_up,orig_down,up_m,down_m,ts) VALUES(?,?,?,?,?,?)", (tid, o_up, o_down, up, down, int(time.time())))
        c.execute("UPDATE tours SET up_m=?,down_m=? WHERE id=?", (up, down, tid))
    return {"up_m": up, "down_m": down, "orig_up": o_up, "orig_down": o_down}


def restore(tid):
    tid = str(tid)
    cur = db.one("SELECT * FROM elev_fix WHERE id=?", (tid,))
    if not cur:
        return False
    if orig_path(tid).exists():
        routes.path_full(tid).write_text(orig_path(tid).read_text())
        orig_path(tid).unlink()
    with db.cur() as c:
        c.execute("UPDATE tours SET up_m=?,down_m=? WHERE id=?", (cur["orig_up"], cur["orig_down"], tid))
        c.execute("DELETE FROM elev_fix WHERE id=?", (tid,))
    return True


class ZeppFixError(RuntimeError):
    """Fachlicher Fehler beim Zepp-Abgleich (Meldung ist für die Oberfläche gedacht)."""


def align_zepp(items, zpts, t0=None):
    """Höhen einer Tour mit der barometrischen Uhr-Höhe abgleichen. -> neue Höhenliste (je Tourpunkt) oder None, wenn Zepp nicht taugt.

    items: [(lat, lng, alt, t_ms)] – t_ms ist die Zeit seit Tourstart (Komoot/GPX-Konvention), t0 der Unix-Start der Tour (s),
    damit Tour- und Zepp-Zeit (Unix-Sekunden) vergleichbar werden. Ohne t0 oder ohne Zeiten wird die Tour gleichmäßig über den Zepp-Zeitraum gelegt.
    zpts: [(unix_ts, alt_m)].
    Das Barometer driftet absolut, ist aber im Verlauf genau; Komoot-/GPS-Höhen sind absolut brauchbar, im Verlauf aber ungenau.
    Darum: Verlauf von Zepp, Niveau der Originalhöhen (Median der Differenz, robust gegen Ausreißer)."""
    from bisect import bisect_left
    from statistics import median
    z = sorted((float(t), float(h)) for t, h in zpts if h is not None and -500.0 <= h <= 9000.0)   # Platzhalter („keine Höhe“) fallen hier raus
    if len(z) < 6 or not items or max(h for _, h in z) - min(h for _, h in z) < 0.01:             # konstante Höhe = keine echten Messwerte
        return None
    zt = [t for t, _ in z]
    n = len(items)
    if t0 is not None and all(p[3] is not None for p in items):
        ts = [t0 + p[3] / 1000.0 for p in items]
    else:
        ts = [zt[0] + (zt[-1] - zt[0]) * i / max(1, n - 1) for i in range(n)]
    tol = 30.0
    zv = []
    for t in ts:
        if t < zt[0] - tol or t > zt[-1] + tol:
            zv.append(None)
            continue
        j = bisect_left(zt, t)
        if j <= 0:
            zv.append(z[0][1])
        elif j >= len(z):
            zv.append(z[-1][1])
        else:
            (ta, ha), (tb, hb) = z[j - 1], z[j]
            zv.append(ha if tb == ta else ha + (hb - ha) * (t - ta) / (tb - ta))
    if sum(v is not None for v in zv) < 0.8 * n:
        return None
    diffs = [v - p[2] for v, p in zip(zv, items) if v is not None and p[2] is not None and -500.0 <= p[2] <= 9000.0]
    off = median(diffs) if diffs else 0.0                 # ohne Originalhöhen bleibt Zepp unverändert
    return [round(v - off, 1) if v is not None else p[2] for v, p in zip(zv, items)]


def _zepp_match(api, t, tol):
    """Zepp-Training zu einer Tour: gleiche ID z<Nr>, sonst gleicher Start/gleiche Strecke wie bei puls.backfill_hr."""
    from . import sync
    hist = api.history()
    if str(t["id"]).startswith("z"):
        for s in hist:
            if f"z{int(s['trackid'])}" == str(t["id"]):
                return s
    for s in hist:
        if sync.is_duplicate(int(s["trackid"]), float(s.get("dis") or 0), int(float(s.get("run_time") or 0)), [t], tol):
            return s
    return None


def _zepp_apply(t, s, api):
    """Detail des Trainings laden, abgleichen und speichern. Gleiche Sicherung wie fix(): Original einmalig in <id>.orig.json, elev_fix hält die alten Werte."""
    from . import sync, zepp
    tid = str(t["id"])
    cur = db.one("SELECT * FROM elev_fix WHERE id=?", (tid,))
    # Bei bereits korrigierter Tour bleibt das ursprüngliche Original die Basis (wie fix()), sonst würde das Korrigierte zum „Original“.
    pts = (json.loads(orig_path(tid).read_text()) if cur and orig_path(tid).exists() else None) or routes.load(tid)
    if not pts or len(pts) < 5:
        raise ZeppFixError("Keine Streckenpunkte vorhanden")
    zp = [(p[0], p[3]) for p in zepp.decode_points(s, api.detail(s))]
    # Tourzeit ist relativ zum Tourstart; Zepp-Zeit absolut. Startet die Tour (Zeitzone/Sommerzeit) um ganze Stunden versetzt zum Training,
    # wird die Tour auf den Trainingsstart gelegt (wie is_duplicate den Versatz toleriert).
    tr = int(s["trackid"])
    t0 = t["start_ts"] if t["start_ts"] else tr
    d = tr - t0
    tol = db.get_int("dup_tolerance_s", 300)
    if abs(d) > tol:
        h = round(d / 3600)
        t0 += h * 3600 if h and abs(d - h * 3600) <= tol else 0
    if str(tid) == f"z{tr}":
        t0 = tr
    alts = align_zepp(pts, zp, t0)
    if alts is None:
        raise ZeppFixError("Zepp-Training hat keine brauchbaren Höhendaten")
    up, down = ascent(smooth(clean([a for a in alts if a is not None]), 3, 3))     # wie recompute_local für lokale Touren
    if not cur:
        orig_path(tid).write_text(json.dumps(pts))
    new = [[p[0], p[1], a, p[3]] for p, a in zip(pts, alts)]
    routes.D.mkdir(parents=True, exist_ok=True)
    routes.path_full(tid).write_text(json.dumps(new))
    o_up, o_down = (cur["orig_up"], cur["orig_down"]) if cur else (t["up_m"], t["down_m"])
    with db.cur() as c:
        c.execute("INSERT OR REPLACE INTO elev_fix(id,orig_up,orig_down,up_m,down_m,ts,src) VALUES(?,?,?,?,?,?,?)", (tid, o_up, o_down, up, down, int(time.time()), "zepp"))
        c.execute("UPDATE tours SET up_m=?,down_m=? WHERE id=?", (up, down, tid))
    return {"up": up, "down": down, "up_m": up, "down_m": down, "orig_up": o_up, "orig_down": o_down}


def zepp_fix(tid, api=None):
    """Höhe EINER Tour aus der Zepp-Uhr (Barometer) übernehmen. Rückgabe {up, down, orig_up, orig_down}; Original bleibt über restore() wiederherstellbar."""
    from . import sync
    tid = str(tid)
    t = db.one("SELECT * FROM tours WHERE id=?", (tid,))
    if not t:
        raise KeyError(tid)
    if api is None:
        try:
            api = sync._zepp_api()
        except RuntimeError as e:
            if "Zugangsdaten fehlen" in str(e):
                raise ZeppFixError("Kein Zepp-Zugang eingerichtet (Einstellungen)")
            raise ZeppFixError(f"Zepp-Anmeldung fehlgeschlagen: {e}")
    s = _zepp_match(api, t, db.get_int("dup_tolerance_s", 300))
    if not s:
        raise ZeppFixError("Kein passendes Zepp-Training gefunden")
    return _zepp_apply(t, s, api)


def zepp_fix_all(api=None):
    """Job: Höhe aller Touren mit passendem Zepp-Training abgleichen. Bereits korrigierte/abgeglichene Touren bleiben unberührt
    (einzeln jederzeit erneut möglich); z<Nr>-Touren haben die Uhr-Höhe ohnehin schon."""
    from . import jobs, sync
    api = api or sync._zepp_api()
    tours = db.query("SELECT * FROM tours")
    byid = {t["id"]: t for t in tours}
    fixed = {r["id"] for r in db.query("SELECT id FROM elev_fix")}
    tol = db.get_int("dup_tolerance_s", 300)
    todo, seen = [], set()
    for s in api.history():
        tr = int(s["trackid"])
        t = byid.get(f"z{tr}") or sync.is_duplicate(tr, float(s.get("dis") or 0), int(float(s.get("run_time") or 0)), tours, tol)
        if not t or t["id"] in fixed or t["id"] in seen or str(t["id"]).startswith("z"):
            continue
        seen.add(t["id"])
        todo.append((s, t))
    jobs.log(f"Höhe abgleichen: {len(todo)} Touren mit passendem Zepp-Training")
    done = 0
    for i, (s, t) in enumerate(todo, 1):
        jobs.progress(f"Höhe {i}/{len(todo)}")
        try:
            r = _zepp_apply(t, s, api)
            done += 1
            jobs.log(f"  {t['id']}: Aufstieg {round(r['orig_up'] or 0)} m → {round(r['up'])} m")
        except Exception as e:  # noqa
            jobs.log(f"  {t['id']}: {e}")
        time.sleep(0.2)
    jobs.log(f"Höhe abgleichen: {done} Touren abgeglichen")
    return done


def drop(tid):
    """Korrektur verwerfen, ohne Werte zurückzuschreiben (Komoot-Daten werden gerade frisch geladen)."""
    tid = str(tid)
    orig_path(tid).unlink(missing_ok=True)
    db.execute("DELETE FROM elev_fix WHERE id=?", (tid,))


def reapply(komoot_tours):
    """Nach dem Neuladen der Tourenliste: Korrekturen erhalten, solange Komoot die Werte nicht selbst geändert hat."""
    k = {str(t["id"]): t for t in komoot_tours}
    for f in db.query("SELECT * FROM elev_fix"):
        t = k.get(f["id"])
        if t is not None and abs((t["up_m"] or 0) - (f["orig_up"] or 0)) < 1:
            db.execute("UPDATE tours SET up_m=?,down_m=? WHERE id=?", (f["up_m"], f["down_m"], f["id"]))
        else:
            drop(f["id"])
            for p in (routes.path_full(f["id"]), routes.path_small(f["id"])):
                p.unlink(missing_ok=True)
