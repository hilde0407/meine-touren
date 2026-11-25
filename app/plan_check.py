"""Machbarkeits-Check und Verknüpfung geplanter Touren mit gelaufenen Touren (3.38.0).

Check: vergleicht eine geplante Strecke (km, Aufstieg, Abstieg, Sportart) mit den eigenen Touren der letzten 12 Monate derselben Sportgruppe.
Drei Stufen (gewohnt / etwas mehr / deutlich mehr) und ehrliche Meldung bei zu wenig Touren (< MIN_TOUREN). Fehlende Werte („ohne Angabe“) zählen nie als 0.

Zeit: Die Planseite zeigt die Dauer inkl. Pausen (eigene Regression a·km + b·Hm über die Archiv-Touren, im Browser). Dieser Check liefert zusätzlich
die reine Gehzeit ohne Pausen aus dem Steigungstempo (steigung.py, nur Wandern/Laufen). Beide Zahlen sind in der Oberfläche ausdrücklich so beschriftet.

Verknüpfung: Vorschlag, welche gelaufene Tour einen Plan überdeckt (>= 80 % der Planpunkte liegen höchstens 100 m neben der gelaufenen Strecke);
nur Touren mit ±25 % der Planlänge und gleicher Sportgruppe werden geprüft. Es wird nie automatisch verknüpft.
"""
import json
import math
import time
from datetime import datetime
from statistics import median

from . import config, db, memo, routes, steigung
from .gpxtools import TZ
from .hinweise import SPORT_GRP

MONATE = 12
MIN_TOUREN = 6                  # darunter: keine persönliche Einschätzung
TOL = 1.05                      # bis 5 % über dem bisherigen Höchstwert zählt noch als gewohnt (Rundungsrauschen)
ETWAS_KM, ETWAS_UP = 1.20, 1.30   # bis hierhin „etwas mehr“, darüber „deutlich mehr“
AEHNLICH = 0.25                 # „ähnlich lang“: ±25 % der Länge
STATUS = ("geplant", "gegangen", "verworfen")
COVER_MIN = 0.80
COVER_R = 100.0                 # m

_PROF = {"t": 0.0, "v": None}


def _grp(sport):
    for k, v in SPORT_GRP.items():
        if sport in v:
            return k
    return None


def _num(v, name, lo, hi, optional=True):
    if v is None or v == "":
        if optional:
            return None
        raise ValueError(f"{name} fehlt")
    if isinstance(v, bool):
        raise ValueError(f"{name}: Zahl erwartet")
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError(f"{name}: Zahl erwartet")
    if not math.isfinite(x) or x < lo or x > hi:
        raise ValueError(f"{name}: Wert außerhalb des gültigen Bereichs")
    return x


def _tour(r):
    return {"id": r["id"], "name": r["name"] or "", "datum": datetime.fromtimestamp(r["start_ts"], tz=TZ).date().isoformat(),
            "km": round((r["dist_m"] or 0) / 1000.0, 1), "up": round(r["up_m"]) if r["up_m"] is not None else None}


def _gehzeit(grp_sport, km, up, down):
    """Reine Gehzeit (s, ohne Pausen) nach Steigungstempo; None, wenn Aufstieg/Abstieg fehlen oder die Sportart nicht abgedeckt ist."""
    g = "wandern" if grp_sport in steigung.SPORTS["wandern"] else "laufen" if grp_sport in steigung.SPORTS["laufen"] else None
    if g is None or up is None or down is None:
        return None
    now = time.monotonic()
    if _PROF["v"] is None or now - _PROF["t"] > 60 or _PROF["v"][0] != g or _PROF["v"][3] != str(config.DB_PATH):
        prof, quelle, e = steigung.profile_for(g)
        _PROF.update(t=now, v=(g, prof, quelle, str(config.DB_PATH)))
    _, prof, quelle, _p = _PROF["v"]
    try:
        sec = steigung.estimate_duration(km * 1000.0, up, down, prof)
    except ValueError:
        return None
    return {"sekunden": round(sec), "quelle": quelle}


_MAXALT = {}


def _hoechster(tid):
    """Höchster Punkt der gespeicherten Strecke (Platzhalterwerte außerhalb −500 … 9000 m zählen nicht); None, wenn es keine Höhen gibt."""
    try:
        f = routes.path_full(tid)
        st = f.stat()
    except OSError:
        return None
    key = (str(f), st.st_mtime_ns)
    if key not in _MAXALT:
        try:
            al = [p[2] for p in json.loads(f.read_text()) if len(p) > 2 and p[2] is not None and -500 <= p[2] <= 9000]
        except (OSError, ValueError, TypeError):
            al = []
        if len(_MAXALT) > 5000:
            _MAXALT.clear()
        _MAXALT[key] = max(al) if al else None
    return _MAXALT[key]


def check(body):
    """Eingabe: km, up, down (optional), sport, max_alt (optional). ValueError bei ungültigen Zahlen."""
    km = _num(body.get("km"), "km", 0.0, 2000.0, optional=False)
    if km <= 0:
        raise ValueError("km: Die Strecke muss länger als 0 sein")
    up = _num(body.get("up"), "Aufstieg", 0.0, 100000.0)
    down = _num(body.get("down"), "Abstieg", 0.0, 100000.0)
    max_alt = _num(body.get("max_alt"), "Höchster Punkt", -500.0, 9000.0)
    sport = str(body.get("sport") or "hike")[:40]
    grp = _grp(sport)
    lo = time.time() - MONATE * 30.4375 * 86400
    rows = db.query("SELECT id,name,sport,start_ts,dist_m,dur_s,up_m FROM tours WHERE start_ts>=? AND dist_m IS NOT NULL AND dist_m>0", (lo,))
    rows = [r for r in rows if (_grp(r["sport"]) == grp if grp else r["sport"] == sport)]
    out = {"ok": True, "n": len(rows), "min_n": MIN_TOUREN, "monate": MONATE, "sport": sport,
           "diese": {"km": round(km, 1), "up": round(up) if up is not None else None, "down": round(down) if down is not None else None, "max_alt": round(max_alt) if max_alt is not None else None},
           "stufe": "zu_wenig", "gruende": [], "laengste": None, "hoechster_aufstieg": None, "laenger": None, "aehnlich": None, "gehzeit": None, "hoechster_punkt": None}
    out["gehzeit"] = _gehzeit(sport, km, up, down)
    if len(rows) < MIN_TOUREN:
        return out
    lg = max(rows, key=lambda r: r["dist_m"])
    out["laengste"] = _tour(lg)
    mit_up = [r for r in rows if r["up_m"] is not None]
    if mit_up:
        out["hoechster_aufstieg"] = _tour(max(mit_up, key=lambda r: r["up_m"]))
    out["laenger"] = sum(1 for r in rows if r["dist_m"] / 1000.0 > km)
    gr = []
    max_km = lg["dist_m"] / 1000.0
    f_km = km / max_km
    stufe = "gewohnt"
    if f_km > TOL:
        gr.append("km")
        stufe = "deutlich_mehr" if f_km > ETWAS_KM else "etwas_mehr"
    if up is not None and mit_up:
        max_up = max(r["up_m"] for r in mit_up)
        if max_up > 0:
            f_up = up / max_up
        else:
            f_up = 1.0 if up == 0 else math.inf
        if f_up > TOL:
            gr.append("up")
            s2 = "deutlich_mehr" if f_up > ETWAS_UP else "etwas_mehr"
            if stufe == "gewohnt" or s2 == "deutlich_mehr":
                stufe = s2
    out["stufe"], out["gruende"] = stufe, gr
    ae = [r for r in rows if abs(r["dist_m"] / 1000.0 - km) <= AEHNLICH * km]
    if ae:
        d = [r["dur_s"] for r in ae if r["dur_s"]]
        u = [r["up_m"] for r in ae if r["up_m"] is not None]
        out["aehnlich"] = {"n": len(ae), "dauer_h": round(median(d) / 3600.0, 2) if d else None, "up": round(median(u)) if u else None, "n_dauer": len(d), "n_up": len(u)}
    if max_alt is not None:                                  # nur Information, beeinflusst die Stufe nicht
        hs = [h for h in (_hoechster(r["id"]) for r in rows) if h is not None]
        if hs and len(hs) * 2 >= len(rows):                  # nur, wenn mindestens die Hälfte der Touren Höhen hat (sonst wäre der Vergleich eine Scheinzahl)
            out["hoechster_punkt"] = {"eigen": round(max(hs)), "n": len(hs)}
    return out


# ---------------------------------------------------------------------------------------------- Verknüpfung
def _line(tid, n=500):
    p = routes.load(tid)
    if not p or len(p) < 5:
        return None
    step = max(1, len(p) // n)
    return [(q[0], q[1]) for q in p[::step]] + [(p[-1][0], p[-1][1])]


def _bbox_ok(samp, line):
    la = [p[0] for p in line]; lo = [p[1] for p in line]
    return not (min(la) - 0.02 > max(s[0] for s in samp) or max(la) + 0.02 < min(s[0] for s in samp)
                or min(lo) - 0.03 > max(s[1] for s in samp) or max(lo) + 0.03 < min(s[1] for s in samp))


def coverage_of(plan_pts, tid):
    """Anteil der (ausgedünnten) Planpunkte, die höchstens COVER_R m neben der gelaufenen Strecke liegen."""
    from .wanderfuehrer import _covered
    line = _line(tid)
    if not line or len(plan_pts) < 2:
        return 0.0
    n = min(60, len(plan_pts))
    samp = [(plan_pts[int(i * (len(plan_pts) - 1) / max(1, n - 1))][0], plan_pts[int(i * (len(plan_pts) - 1) / max(1, n - 1))][1]) for i in range(n)]
    if not _bbox_ok(samp, line):
        return 0.0
    return _covered(samp, line, COVER_R)


def vorschlag_fuer(plan, belegt=()):
    """Beste gelaufene Tour für den Plan (dict) oder None. Prüft nur Touren mit ±25 % der Planlänge und gleicher Sportgruppe."""
    km = plan["km"]
    if not km or km <= 0:
        return None
    try:
        pts = json.loads(plan["pts"])
    except (TypeError, ValueError):
        return None
    grp = _grp(plan["sport"])
    best = None
    for t in db.query("SELECT id,name,sport,start_ts,dist_m,dur_s,up_m FROM tours WHERE dist_m IS NOT NULL AND start_ts IS NOT NULL AND dist_m BETWEEN ? AND ?", (km * 1000 * (1 - AEHNLICH), km * 1000 * (1 + AEHNLICH))):
        if t["id"] in belegt or (_grp(t["sport"]) != grp if grp else t["sport"] != plan["sport"]):
            continue
        c = coverage_of(pts, t["id"])
        if c >= COVER_MIN and (best is None or c > best[0]):
            best = (c, t)
    if not best:
        return None
    return {"tour_id": best[1]["id"], "name": best[1]["name"] or "", "datum": datetime.fromtimestamp(best[1]["start_ts"], tz=TZ).date().isoformat(), "ueberdeckung": round(best[0], 2)}


@memo.cached
def vorschlaege():
    """{plan_id: Vorschlag} für alle noch unverknüpften, nicht verworfenen Pläne (höchstens die 40 neuesten)."""
    belegt = {r["tour_id"] for r in db.query("SELECT tour_id FROM plans WHERE tour_id IS NOT NULL")}
    out = {}
    for p in db.query("SELECT id,sport,km,pts FROM plans WHERE tour_id IS NULL AND status='geplant' ORDER BY ts DESC LIMIT 40"):
        v = vorschlag_fuer(p, belegt)
        if v:
            out[str(p["id"])] = v
    return out
