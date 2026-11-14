"""Tempo nach Steigung: wie schnell gehst/läufst du bergauf, eben und bergab – und daraus eine Zeitschätzung.

Je Tour wird aus der Strecke (Punkte mit Höhe und Zeit; lokale GPX in voller Auflösung, sonst der Routen-Zwischenspeicher) berechnet:

* Die Höhe wird auf einem 10-m-Raster entlang der Strecke über ~50 m geglättet (gleitender Mittelwert), dann in 50-m-Abschnitte zerlegt.
* Steigung je Abschnitt = Höhenunterschied / 50 m.  Klassen: bergauf > +5 %, bergab < −5 %, dazwischen eben.
* Pausen werden aus der Zeit genommen: Zwischen zwei Messpunkten mit Tempo < 0,3 km/h zählt die Zeit nicht (es zählt die reine Bewegungszeit).
* Je Klasse: Strecke, Zeit, Tempo (km/h); bergauf zusätzlich die vertikale Aufstiegsgeschwindigkeit (m/h).
* Klassen mit weniger als 300 m oder 2 min Bewegungszeit, Touren unter 2 km und Touren ohne Höhe/Zeit liefern KEINEN Wert (nie 0 als Platzhalter).

Das Ergebnis je Tour liegt als Zwischenspeicher in cache/tempo/<id>.json und gilt nur, solange die Quelldatei (GPX bzw. Routen-Zwischenspeicher)
unverändert ist (Änderungszeit + Größe): Wird der Track oder die Höhe korrigiert, wird neu gerechnet. Der Zwischenspeicher baut sich von selbst neu auf
und steht deshalb nicht in der Sicherung (er ist im Umzugspaket als Teil des Datenordners enthalten).

Zeitschätzung: estimate_duration() – Naismith-ähnlich: Zeit = Strecke / Tempo eben + Aufstieg × Mehrzeit je Höhenmeter + Abstieg × Mehrzeit je Höhenmeter.
Die Mehrzeiten werden aus deinen Touren abgeleitet (Median über alle Touren); ohne eigene Werte gelten Naismith-Werte (5 km/h, 1 h je 600 m Aufstieg).
"""
import json
import math
import time
from bisect import bisect_right
from datetime import datetime
from statistics import median

from fastapi import APIRouter, HTTPException

from . import config, db, routes, tracks, trackfix
from .gpxtools import TZ

router = APIRouter()

ALGO = 1                                  # Version der Rechenvorschrift: bei Änderung werden alle Zwischenwerte ungültig
STEP = 10.0                               # Raster entlang der Strecke (m)
SMOOTH_STEPS = 5                          # Glättungsfenster: 5 × 10 m = 50 m
SEG_STEPS = 5                             # Abschnitt: 50 m
SEG_M = STEP * SEG_STEPS
PAUSE_KMH = 0.3                           # unterhalb dieses Tempos zwischen zwei Punkten gilt die Zeit als Pause
SLOPE = 0.05                              # ±5 % trennt bergauf/eben/bergab
MIN_TOUR_M = 2000                         # kürzere Touren werden nicht ausgewertet
MIN_CLASS_M, MIN_CLASS_S = 300.0, 120.0   # kleinste Klasse, die gezeigt wird
MIN_CLIMB_M = 30.0                        # für die Mehrzeit je Höhenmeter mindestens so viele Höhenmeter in der Klasse
MIN_COVER = 0.8                           # Anteil der Punkte mit Höhe und Zeit, ab dem eine Tour auswertbar ist
MIN_TOURS = 3                             # so viele Touren braucht ein eigener Wert für die Zeitschätzung
SPORTS = {"wandern": ("hike", "nordicwalking"), "laufen": ("jogging",)}
SPORT_DE = {"wandern": "Wandern", "laufen": "Laufen"}
# Standard ohne eigene Werte: Naismith (5 km/h, 1 h je 600 m Aufstieg = 6 s/m, Abstieg ohne Zuschlag)
DEFAULT_PROFILE = {"eben_kmh": 5.0, "e_up": 6.0, "e_down": 0.0}
LIMITS = {"eben_kmh": (1.0, 15.0), "e_up": (0.0, 15.0), "e_down": (0.0, 10.0)}
BUDGET_S = 6.0                            # so lange rechnet ein Statistik-Aufruf höchstens an noch nicht berechneten Touren


# ------------------------------------------------------------------------------------------------ Rechnen
def _alt(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) and -500.0 <= x <= 9000.0 else None       # Platzhalter (z. B. −2 004 831) fallen heraus


def _axis(pts):
    """Punkte [lat, lng, alt, t_ms] -> (Strecke, Höhe, Bewegungszeit) je Punkt mit Höhe und Zeit; oder (None, Grund)."""
    dist, prev, kept, total = 0.0, None, [], 0
    for p in pts or []:
        try:
            la, lo = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError):
            continue
        if not (math.isfinite(la) and math.isfinite(lo)):
            continue
        total += 1
        if prev is not None:
            dist += trackfix.hav(prev, (la, lo))
        prev = (la, lo)
        a = _alt(p[2]) if len(p) > 2 else None
        t = p[3] if len(p) > 3 else None
        if a is None or t is None or isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t):
            continue
        kept.append((dist, a, t / 1000.0))
    if total < 10 or dist < MIN_TOUR_M:
        return None, "zu_kurz"
    if len(kept) < max(10, MIN_COVER * total):
        return None, "keine_hoehe"
    d, h, mt, m = [], [], [], 0.0
    last = None
    for dd, a, t in kept:
        if last is None:
            d.append(dd); h.append(a); mt.append(0.0)
        else:
            dt = t - last[2]
            if dt <= 0:
                continue                                       # Zeit läuft nicht vorwärts: Punkt auslassen
            if (dd - last[0]) / dt * 3.6 >= PAUSE_KMH:
                m += dt                                        # Pause (Tempo unter 0,3 km/h): Zeit zählt nicht
            d.append(dd); h.append(a); mt.append(m)
        last = (dd, a, t)
    if len(d) < 10 or d[-1] < MIN_TOUR_M:
        return None, "zu_kurz"
    return (d, h, mt), "ok"


def _interp(xs, ys, x):
    i = bisect_right(xs, x)
    if i <= 0:
        return ys[0]
    if i >= len(xs):
        return ys[-1]
    x0, x1 = xs[i - 1], xs[i]
    return ys[i] if x1 == x0 else ys[i - 1] + (ys[i] - ys[i - 1]) * (x - x0) / (x1 - x0)


def _grid(axis):
    """Höhe (geglättet) und Bewegungszeit auf dem 10-m-Raster."""
    d, h, mt = axis
    n = int(d[-1] // STEP) + 1
    alt = [_interp(d, h, i * STEP) for i in range(n)]
    tim = [_interp(d, mt, i * STEP) for i in range(n)]
    w = SMOOTH_STEPS // 2
    sm = []
    for i in range(n):
        a, b = max(0, i - w), min(n, i + w + 1)
        sm.append(sum(alt[a:b]) / (b - a))
    return sm, tim


def _klasse(c):
    if c["dist_m"] < MIN_CLASS_M or c["zeit_s"] < MIN_CLASS_S:
        return None
    return {"dist_m": round(c["dist_m"]), "zeit_s": round(c["zeit_s"]), "hm": round(c["hm"], 1), "kmh": round(c["dist_m"] / c["zeit_s"] * 3.6, 2)}


def compute(pts):
    """Tempo je Steigungsklasse aus Streckenpunkten. -> {"status": "ok", …} oder {"status": "zu_kurz"|"keine_hoehe"|"zu_wenig"}."""
    axis, why = _axis(pts)
    if axis is None:
        return {"status": why}
    alt, tim = _grid(axis)
    cl = {k: {"dist_m": 0.0, "zeit_s": 0.0, "hm": 0.0} for k in ("auf", "eben", "ab")}
    up = down = 0.0
    for s in range(0, len(alt) - SEG_STEPS, SEG_STEPS):
        dh = alt[s + SEG_STEPS] - alt[s]
        dt = tim[s + SEG_STEPS] - tim[s]
        if dt <= 0:
            continue
        k = "auf" if dh / SEG_M > SLOPE else "ab" if dh / SEG_M < -SLOPE else "eben"
        c = cl[k]
        c["dist_m"] += SEG_M; c["zeit_s"] += dt; c["hm"] += abs(dh) if k != "eben" else 0.0
        up += max(dh, 0.0); down += max(-dh, 0.0)
    out = {k: _klasse(c) for k, c in cl.items()}
    if not any(out.values()):
        return {"status": "zu_wenig"}
    res = {"status": "ok", "klassen": out, "vert_mh": None, "e_up": None, "e_down": None,
           "dist_m": round(sum(c["dist_m"] for c in cl.values())), "zeit_s": round(sum(c["zeit_s"] for c in cl.values())),
           "up_m": round(up), "down_m": round(down)}
    a = out["auf"]
    if a:
        res["vert_mh"] = round(a["hm"] / a["zeit_s"] * 3600, 0)
    e = out["eben"]
    if e:
        v = e["kmh"] / 3.6
        for k, key in (("auf", "e_up"), ("ab", "e_down")):
            c = out[k]
            if c and c["hm"] >= MIN_CLIMB_M:
                res[key] = round((c["zeit_s"] - c["dist_m"] / v) / c["hm"], 3)          # Mehr-/Minderzeit je Höhenmeter gegenüber ebenem Gehen
    return res


# ------------------------------------------------------------------------------------------------ Zwischenspeicher
def _source(tid):
    f = tracks.gpx_file(tid)
    if f.exists():
        return f
    r = routes.path_full(tid)
    return r if r.exists() else None


def _sig(src):
    s = src.stat()
    return [src.suffix, s.st_mtime_ns, s.st_size]


def cache_path(tid):
    return config.CACHE_DIR / "tempo" / f"{tid}.json"


def _points(tid):
    try:
        return trackfix._load(tid)
    except Exception:  # noqa
        return None


def tempo_of(tid, allow_compute=True):
    """Ergebnis für eine Tour (aus dem Zwischenspeicher, sonst berechnet). None = noch nicht berechnet und Rechnen nicht erlaubt;
    {"status": "keine_strecke"} = es gibt keine Strecke."""
    tid = str(tid)
    src = _source(tid)
    if src is None:
        return {"status": "keine_strecke"}
    sig = _sig(src)
    cp = cache_path(tid)
    try:
        c = json.loads(cp.read_text(encoding="utf-8"))
        if c.get("algo") == ALGO and c.get("sig") == sig and isinstance(c.get("res"), dict):
            return c["res"]
    except (OSError, ValueError):
        pass
    if not allow_compute:
        return None
    res = compute(_points(tid))
    try:
        cp.parent.mkdir(parents=True, exist_ok=True)
        tmp = cp.with_name(cp.name + ".tmp")
        tmp.write_text(json.dumps({"algo": ALGO, "sig": sig, "res": res}, separators=(",", ":")), encoding="utf-8")
        tmp.replace(cp)
    except OSError:
        pass
    return res


def hoehen_je_haelfte(tid, k, dis):
    """Auf- und Abstieg (m, geglättet) der ersten und der zweiten Hälfte einer Tour mit k + k vollen Kilometern (Mittelstück bei ungerader Zahl
    ausgelassen). dis = Länge laut Uhr (m); die Aufteilung erfolgt anteilig an der Streckenlänge. -> {"erste": {"auf","ab"}, "zweite": {…}} oder None."""
    axis, _w = _axis(_points(str(tid)))
    if axis is None or not dis or dis <= 0 or k < 1:
        return None
    alt, _tim = _grid(axis)
    total = len(alt) - 1
    if total < SEG_STEPS * 4:
        return None
    n_all = total * STEP

    def part(a_m, b_m):
        a, b = int(round(a_m / dis * n_all / STEP)), int(round(b_m / dis * n_all / STEP))
        a, b = max(0, min(total, a)), max(0, min(total, b))
        up = down = 0.0
        for i in range(a, b - SEG_STEPS + 1, SEG_STEPS):
            dh = alt[i + SEG_STEPS] - alt[i]
            up += max(dh, 0.0); down += max(-dh, 0.0)
        return {"auf": round(up), "ab": round(down)}
    n = int(dis // 1000)
    return {"erste": part(0, k * 1000.0), "zweite": part((n - k) * 1000.0, n * 1000.0)}


# ------------------------------------------------------------------------------------------------ Zeitschätzung
def _profile(profile):
    """Gültige Werte aus profile übernehmen (Rest = Standard); Grenzen einhalten."""
    out = dict(DEFAULT_PROFILE)
    for k, (lo, hi) in LIMITS.items():
        try:
            x = float((profile or {}).get(k))
        except (TypeError, ValueError):
            continue
        if math.isfinite(x):
            out[k] = min(hi, max(lo, x))
    return out


def estimate_duration(dist_m, up_m, down_m, profile=None):
    """Geschätzte reine Gehzeit (Sekunden, ohne Pausen) – Naismith-ähnlich auf Basis der eigenen Werte:
       Zeit = Strecke / Tempo eben + Aufstieg × e_up + Abstieg × e_down  (e_* = Mehrzeit je Höhenmeter in s/m).
    profile: {"eben_kmh", "e_up", "e_down"}; fehlende/ungültige Einträge nehmen den Naismith-Standard, Werte werden auf sinnvolle Grenzen gekappt.
    Nie fallend in Strecke, Aufstieg und Abstieg. Ungültige Eingaben (negativ, keine Zahl, absurd groß) -> ValueError."""
    vals = []
    for x, lim in ((dist_m, 2_000_000), (up_m, 100_000), (down_m, 100_000)):
        try:
            v = float(x)
        except (TypeError, ValueError):
            raise ValueError("Zahl erwartet")
        if not math.isfinite(v) or v < 0 or v > lim:
            raise ValueError("Wert außerhalb des gültigen Bereichs")
        vals.append(v)
    p = _profile(profile)
    return vals[0] / (p["eben_kmh"] / 3.6) + vals[1] * p["e_up"] + vals[2] * p["e_down"]


# ------------------------------------------------------------------------------------------------ Statistik
def _med(vals):
    v = [x for x in vals if x is not None]
    return (round(median(v), 2), len(v)) if v else (None, 0)


def stats(jahr=None, budget_s=BUDGET_S):
    """Median über alle Touren je Sportgruppe. Rechnet höchstens budget_s Sekunden an noch nicht berechneten Touren; der Rest steht in "offen"."""
    t_end = time.monotonic() + budget_s
    rows = db.query("SELECT id,sport,start_ts,dist_m FROM tours WHERE start_ts IS NOT NULL AND dist_m>=? ORDER BY start_ts DESC", (MIN_TOUR_M,))
    per = {g: [] for g in SPORTS}
    offen = 0
    for t in rows:
        g = next((k for k, v in SPORTS.items() if t["sport"] in v), None)
        if g is None:
            continue
        if jahr and datetime.fromtimestamp(t["start_ts"], tz=TZ).year != jahr:
            continue
        r = tempo_of(t["id"], allow_compute=time.monotonic() < t_end)
        if r is None:
            offen += 1
        elif r.get("status") == "ok":
            per[g].append(r)
    out = {}
    for g, lst in per.items():
        e = {"touren": len(lst)}
        for k, key in (("auf", "auf_kmh"), ("eben", "eben_kmh"), ("ab", "ab_kmh")):
            e[key], e["n_" + key] = _med([(r["klassen"][k] or {}).get("kmh") for r in lst])
        e["vert_mh"], e["n_vert_mh"] = _med([r["vert_mh"] for r in lst])
        e["e_up"], e["n_e_up"] = _med([r["e_up"] for r in lst])
        e["e_down"], e["n_e_down"] = _med([r["e_down"] for r in lst])
        out[g] = e
    return {"gruppen": out, "offen": offen}


def profile_for(gruppe, jahr=None):
    """(Profil, Quelle) für estimate_duration: eigene Mediane (mindestens MIN_TOURS Touren je Wert), sonst Naismith. Quelle: eigene | teilweise | standard."""
    e = stats(jahr)["gruppen"].get(gruppe) or {}
    prof, own = {}, 0
    for k in ("eben_kmh", "e_up", "e_down"):
        if e.get(k) is not None and e.get("n_" + k, 0) >= MIN_TOURS:
            prof[k] = e[k]; own += 1
    return _profile(prof), ("eigene" if own == 3 else "teilweise" if own else "standard"), e


@router.get("/api/tours/{tour_id}/tempo")
def api_tour_tempo(tour_id: str):
    t = db.one("SELECT id,sport,dist_m FROM tours WHERE id=?", (str(tour_id),))
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    r = tempo_of(t["id"])
    return r if r.get("status") == "ok" else {"status": r.get("status") or "keine_daten"}


@router.get("/api/stats/tempo")
def api_stats_tempo(jahr: int = 0):
    if jahr and not 1990 <= jahr <= 2100:
        raise HTTPException(400, "Ungültiges Jahr")
    r = stats(jahr or None)
    years = sorted({datetime.fromtimestamp(x["start_ts"], tz=TZ).year for x in db.query("SELECT start_ts FROM tours WHERE start_ts IS NOT NULL")}, reverse=True)
    return {**r, "jahre": years, "jahr": jahr or None, "min_touren": MIN_TOURS}


@router.get("/api/stats/gehzeit")
def api_gehzeit(km: float, auf: float = 0, ab: float = 0, sport: str = "wandern", jahr: int = 0):
    """Rechner: Strecke (km), Aufstieg und Abstieg (m) -> geschätzte reine Gehzeit mit deinen Werten (oder Naismith, wenn noch zu wenig Daten)."""
    if sport not in SPORTS:
        raise HTTPException(400, "Sportart: wandern oder laufen")
    try:
        prof, quelle, e = profile_for(sport, jahr or None)
        sec = estimate_duration(km * 1000.0, auf, ab, prof)
    except ValueError:
        raise HTTPException(400, "Bitte Zahlen im gültigen Bereich eingeben (Strecke bis 2000 km, Auf-/Abstieg bis 100 000 m)")
    return {"sekunden": round(sec), "quelle": quelle, "profil": prof, "touren": e.get("touren", 0), "sport": sport}
