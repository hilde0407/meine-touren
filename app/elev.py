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
