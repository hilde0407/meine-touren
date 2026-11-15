"""Daten für die Bausteine der Seite „Seite anpassen“ (3.18.0): leichte Auswertungen, die es sonst nirgends gibt.

GET /api/bausteine/<name> (nur lesend, je Benutzer – die Datenbank und der Zwischenspeicher gehören dem angemeldeten Benutzer; Betrachter dürfen lesen):

  Tour (Parameter ?tour=<id>), alle aus EINER Auswertung der Streckenpunkte (Punkte mit Höhe und Zeit, lokale GPX in voller Auflösung, sonst Routen-Zwischenspeicher):
    splits      Zeit und Tempo je Kilometer (bei langen Touren je 2, 5 oder 10 km), nur Bewegungszeit
    steigung    Anteil der Strecke je Steigungsklasse (sieben Klassen von „steil bergab“ bis „steil bergauf“)
    bewegung    Bewegung und Pause als Zeitstreifen (Pause = Tempo unter 0,3 km/h zwischen zwei Punkten)
    gipfel      höchster Punkt (Höhe, Zeitpunkt, Streckenmeter) und Anteil der Strecke über einer Höhe (?ab=<m>)
    profil      kompaktes Höhenprofil (höchstens 120 Punkte)
    tageslicht  Sonnenaufgang/-untergang und Dämmerung am Tag der Tour (rechnerisch aus Datum und Startposition, ohne externe Quelle) und das Zeitfenster der Tour
  Ohne Parameter:
    ausruestung Ausrüstung mit Kilometerstand und Limit (wie /api/gear, aber auch für Betrachter lesbar)
    geplant     geplante Touren (ohne Streckenpunkte)

Fehlt etwas, kommt {"status": "<grund>"} (nie 0 als Platzhalter): keine_strecke, keine_zeit, keine_hoehe, zu_kurz, keine_position, polar.
Der Zwischenspeicher cache/bausteine/<id>.json gilt nur, solange die Quelldatei unverändert ist (Änderungszeit + Größe) und die Rechenvorschrift (ALGO) gleich bleibt;
er baut sich von selbst neu auf und braucht keine Sicherung.
"""
import json
import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException

from . import config, db, gear, steigung, trackfix
from .gpxtools import TZ

router = APIRouter()

ALGO = 1
PAUSE_KMH = 0.3                      # wie in steigung.py
MIN_M = 500.0                        # kürzere Strecken werden nicht ausgewertet
MAX_PROFIL = 120
# Steigungsklassen in Prozent (untere Grenze, Beschriftung): sieben Klassen, von steil bergab bis steil bergauf
KLASSEN = [(-1e9, "steil_ab"), (-15.0, "ab"), (-5.0, "leicht_ab"), (-2.0, "eben"), (2.0, "leicht_auf"), (5.0, "auf"), (15.0, "steil_auf")]
NAMEN = ("steil_ab", "ab", "leicht_ab", "eben", "leicht_auf", "auf", "steil_auf")


# ------------------------------------------------------------------------------------------------ Rechnen
def _pts(pts):
    """Punkte [lat, lng, alt, t_ms] -> Liste (Strecke m, Höhe oder None, Zeit s oder None); Punkte mit ungültiger Position entfallen."""
    out, prev, dist = [], None, 0.0
    for p in pts or []:
        try:
            la, lo = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError):
            continue
        if not (math.isfinite(la) and math.isfinite(lo)) or (la == 0 and lo == 0):
            continue
        if prev is not None:
            dist += trackfix.hav(prev, (la, lo))
        prev = (la, lo)
        a = steigung._alt(p[2]) if len(p) > 2 else None
        t = p[3] if len(p) > 3 else None
        t = t / 1000.0 if isinstance(t, (int, float)) and not isinstance(t, bool) and math.isfinite(t) else None
        out.append((dist, a, t))
    return out


def _lerp(x, x0, x1, y0, y1):
    return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def _moving(rows):
    """Bewegungszeit je Punkt (s) und die Pausen [(von_s, bis_s)] in Gesamtzeit; nur mit Zeitstempeln. None, wenn die Zeit fehlt oder nicht vorwärts läuft."""
    ts = [r for r in rows if r[2] is not None]
    if len(ts) < max(10, 0.8 * len(rows)):
        return None
    pauses, m, last = [], 0.0, None
    keep = []
    for d, a, t in ts:
        if last is not None:
            dt = t - last[2]
            if dt <= 0:
                continue                                     # Zeit läuft nicht vorwärts: Punkt auslassen
            if (d - last[0]) / dt * 3.6 >= PAUSE_KMH:
                m += dt
            else:
                if pauses and abs(pauses[-1][1] - last[2]) < 1e-6:
                    pauses[-1][1] = t
                else:
                    pauses.append([last[2], t])
        keep.append((d, a, t, m))
        last = (d, a, t)
    return keep, pauses


def _split_len(dist_m):
    return 1000 if dist_m <= 30000 else 2000 if dist_m <= 60000 else 5000 if dist_m <= 150000 else 10000


def _splits(keep, dist_m):
    step = _split_len(dist_m)
    ds = [k[0] for k in keep]
    out, nxt, j, prev_m, prev_up_h = [], step, 0, 0.0, None

    def at(x):
        nonlocal j
        while j < len(ds) - 2 and ds[j + 1] < x:
            j += 1
        k0, k1 = keep[j], keep[j + 1]
        m = _lerp(x, k0[0], k1[0], k0[3], k1[3])
        a = _lerp(x, k0[0], k1[0], k0[1], k1[1]) if k0[1] is not None and k1[1] is not None else None
        return m, a

    m0, a0 = 0.0, keep[0][1]
    while nxt <= dist_m + 1e-6:
        m1, a1 = at(nxt)
        if m1 - m0 > 0:
            out.append({"km": round(nxt / 1000.0, 3), "dauer_s": round(m1 - m0, 1), "kmh": round(step / (m1 - m0) * 3.6, 2),
                        "hm": round(a1 - a0, 1) if a0 is not None and a1 is not None else None})
        m0, a0 = m1, a1
        nxt += step
    rest = dist_m - (nxt - step)
    if rest >= step * 0.1:                                   # letzter, angebrochener Abschnitt
        m1, a1 = keep[-1][3], keep[-1][1]
        if m1 - m0 > 0:
            out.append({"km": round(dist_m / 1000.0, 3), "dauer_s": round(m1 - m0, 1), "kmh": round(rest / (m1 - m0) * 3.6, 2),
                        "hm": round(a1 - a0, 1) if a0 is not None and a1 is not None else None, "teil": True})
    return {"schritt_m": step, "splits": out}


def _grid(rows):
    """Höhe auf einem 10-m-Raster entlang der Strecke (über 50 m geglättet). Braucht Höhen an mindestens 80 % der Punkte."""
    h = [(d, a) for d, a, _t in rows if a is not None]
    if len(h) < max(10, 0.8 * len(rows)):
        return None
    ds, hs = [x[0] for x in h], [x[1] for x in h]
    n = int(ds[-1] // 10) + 1
    alt, j = [], 0
    for i in range(n):
        x = i * 10.0
        while j < len(ds) - 2 and ds[j + 1] < x:
            j += 1
        alt.append(_lerp(x, ds[j], ds[j + 1], hs[j], hs[j + 1]) if len(ds) > 1 else hs[0])
    sm = []
    for i in range(n):
        a, b = max(0, i - 2), min(n, i + 3)
        sm.append(sum(alt[a:b]) / (b - a))
    return sm


def _klasse_von(pct):
    k = 0
    for i, (lo, _n) in enumerate(KLASSEN):
        if pct >= lo:
            k = i
    return NAMEN[k]


def _steigung(alt):
    seg = {n: 0.0 for n in NAMEN}
    for s in range(0, len(alt) - 5, 5):
        seg[_klasse_von((alt[s + 5] - alt[s]) / 50.0 * 100)] += 50.0
    tot = sum(seg.values())
    if tot < MIN_M:
        return None
    return {"dist_m": round(tot), "anteile": {n: round(seg[n] / tot, 4) for n in NAMEN}}


def _profil(alt, dist_m):
    n = len(alt)
    k = min(MAX_PROFIL, n)
    idx = sorted({round(i * (n - 1) / (k - 1)) for i in range(k)}) if k > 1 else [0]
    return {"dist_m": round(dist_m), "d": [round(i * 10.0) for i in idx], "h": [round(alt[i], 1) for i in idx]}


def _gipfel(alt, rows, dist_m):
    """Höchster Punkt aus den Rohpunkten (nicht geglättet, aber nur gültige Höhen)."""
    hi = None
    for d, a, t in rows:                                      # erster Punkt mit der größten Höhe
        if a is not None and (hi is None or a > hi[0]):
            hi = (a, d, t)
    lo = min((a for _d, a, _t in rows if a is not None), default=None)
    t0 = next((t for _d, _a, t in rows if t is not None), None)
    return {"hoch_m": round(hi[0]), "tief_m": round(lo), "bei_m": round(hi[1]), "nach_s": round(hi[2] - t0) if hi[2] is not None and t0 is not None else None,
            "bei_anteil": round(hi[1] / dist_m, 3) if dist_m else None}


def _bewegung(keep, pauses):
    t0, t1 = keep[0][2], keep[-1][2]
    total = t1 - t0
    pa = sum(b - a for a, b in pauses)
    segs, cur = [], t0
    for a, b in pauses:
        if b - a < max(15.0, total / 400):                   # Mini-Pausen (Ampel, Ruckler) nicht einzeln zeigen
            continue
        if a > cur:
            segs.append(["b", round(cur - t0), round(a - t0)])
        segs.append(["p", round(a - t0), round(b - t0)])
        cur = b
    if t1 > cur:
        segs.append(["b", round(cur - t0), round(t1 - t0)])
    return {"gesamt_s": round(total), "bewegung_s": round(total - pa), "pause_s": round(pa), "abschnitte": segs}


def analyse(pts):
    """Alle Auswertungen einer Strecke -> {"status": "ok"|…, "splits": {…}|None, …}."""
    rows = _pts(pts)
    if len(rows) < 10 or rows[-1][0] < MIN_M:
        return {"status": "zu_kurz"}
    res = {"status": "ok", "dist_m": round(rows[-1][0])}
    mv = _moving(rows)
    if mv:
        keep, pauses = mv
        res["splits"] = _splits(keep, keep[-1][0]) if keep[-1][0] >= MIN_M else None
        res["bewegung"] = _bewegung(keep, pauses) if keep[-1][2] - keep[0][2] >= 60 else None
    else:
        res["splits"] = res["bewegung"] = None
    alt = _grid(rows)
    if alt and len(alt) > 6:
        res["steigung"] = _steigung(alt)
        res["profil"] = _profil(alt, rows[-1][0])
        res["gipfel"] = _gipfel(alt, rows, rows[-1][0])
    else:
        res["steigung"] = res["profil"] = res["gipfel"] = None
    return res


# ------------------------------------------------------------------------------------------------ Tageslicht
def _sonne(day, lat, lng, zenit):
    """(Aufgang, Untergang) als UTC-Zeitpunkt für das Datum `day` (NOAA-Näherung, auf etwa 2 Minuten genau); None bei Polartag/-nacht."""
    n = day.timetuple().tm_yday
    g = 2 * math.pi / 365 * (n - 1)
    eqt = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g) - 0.040849 * math.sin(2 * g))
    dec = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g) + 0.000907 * math.sin(2 * g)
           - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    la = math.radians(lat)
    c = (math.cos(math.radians(zenit)) - math.sin(la) * math.sin(dec)) / (math.cos(la) * math.cos(dec))
    if c >= 1 or c <= -1:
        return None
    ha = math.degrees(math.acos(c))
    base = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    return base + timedelta(minutes=720 - 4 * (lng + ha) - eqt), base + timedelta(minutes=720 - 4 * (lng - ha) - eqt)


def tageslicht(start_ts, end_ts, lat, lng):
    if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180) or (lat == 0 and lng == 0):
        return {"status": "keine_position"}
    start = datetime.fromtimestamp(start_ts, tz=TZ)
    day = start.date()
    sun, civ = _sonne(day, lat, lng, 90.833), _sonne(day, lat, lng, 96.0)
    if not sun:
        return {"status": "polar"}
    mid = datetime(day.year, day.month, day.day, tzinfo=TZ)
    mn = lambda d: round((d.astimezone(TZ) - mid).total_seconds() / 60.0, 1)  # noqa: E731
    end = end_ts if end_ts and end_ts > start_ts else None
    out = {"status": "ok", "datum": day.isoformat(), "aufgang_min": mn(sun[0]), "untergang_min": mn(sun[1]),
           "daemm_von_min": mn(civ[0]) if civ else None, "daemm_bis_min": mn(civ[1]) if civ else None,
           "tag_min": round((sun[1] - sun[0]).total_seconds() / 60.0), "start_min": mn(datetime.fromtimestamp(start_ts, tz=timezone.utc)),
           "ende_min": mn(datetime.fromtimestamp(end, tz=timezone.utc)) if end else None}
    if end:
        a, b = max(start_ts, sun[0].timestamp()), min(end, sun[1].timestamp())
        out["hell_min"] = round(max(0.0, b - a) / 60.0)
        out["dunkel_min"] = round((end - start_ts) / 60.0) - out["hell_min"]
    return out


# ------------------------------------------------------------------------------------------------ Zwischenspeicher, Endpunkte
def _cache_path(tid):
    return config.CACHE_DIR / "bausteine" / f"{tid}.json"


def tour_analyse(tid):
    tid = str(tid)
    src = steigung._source(tid)
    if src is None:
        return {"status": "keine_strecke"}
    sig = steigung._sig(src)
    cp = _cache_path(tid)
    try:
        c = json.loads(cp.read_text(encoding="utf-8"))
        if c.get("algo") == ALGO and c.get("sig") == sig and isinstance(c.get("res"), dict):
            return c["res"]
    except (OSError, ValueError):
        pass
    res = analyse(steigung._points(tid))
    try:
        cp.parent.mkdir(parents=True, exist_ok=True)
        tmp = cp.with_name(cp.name + ".tmp")
        tmp.write_text(json.dumps({"algo": ALGO, "sig": sig, "res": res}, separators=(",", ":")), encoding="utf-8")
        tmp.replace(cp)
    except OSError:
        pass
    return res


def _tour(tour):
    if not tour:
        raise HTTPException(400, "Parameter „tour“ fehlt")
    t = db.one("SELECT id,start_ts,end_ts,dur_s,lat,lng FROM tours WHERE id=?", (str(tour),))
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    return t


def _teil(tour, key, nodata):
    t = _tour(tour)
    r = tour_analyse(t["id"])
    if r.get("status") != "ok":
        return {"status": r.get("status") or "keine_daten"}
    if not r.get(key):
        return {"status": nodata}
    return {"status": "ok", **r[key]}


@router.get("/api/bausteine/splits")
def api_splits(tour: str = ""):
    return _teil(tour, "splits", "keine_zeit")


@router.get("/api/bausteine/steigung")
def api_steigung(tour: str = ""):
    return _teil(tour, "steigung", "keine_hoehe")


@router.get("/api/bausteine/bewegung")
def api_bewegung(tour: str = ""):
    return _teil(tour, "bewegung", "keine_zeit")


@router.get("/api/bausteine/profil")
def api_profil(tour: str = ""):
    return _teil(tour, "profil", "keine_hoehe")


@router.get("/api/bausteine/gipfel")
def api_gipfel(tour: str = "", ab: float = 0):
    t = _tour(tour)
    r = tour_analyse(t["id"])
    if r.get("status") != "ok":
        return {"status": r.get("status") or "keine_daten"}
    g, p = r.get("gipfel"), r.get("profil")
    if not g or not p:
        return {"status": "keine_hoehe"}
    out = {"status": "ok", **g}
    if ab > 0 and len(p["h"]) > 1:                             # Anteil der Strecke über „ab“ Metern, aus dem Profil (lineare Zwischenwerte)
        d, h, ueber = p["d"], p["h"], 0.0
        for i in range(len(h) - 1):
            a, b, w = h[i], h[i + 1], d[i + 1] - d[i]
            if a >= ab and b >= ab:
                ueber += w
            elif (a >= ab) != (b >= ab) and a != b:
                f = (ab - a) / (b - a)
                ueber += w * ((1 - f) if a >= ab else f)
        out["ab_m"] = ab
        out["ueber_anteil"] = round(ueber / max(1.0, d[-1] - d[0]), 3)
    return out


@router.get("/api/bausteine/tageslicht")
def api_tageslicht(tour: str = ""):
    t = _tour(tour)
    if t.get("start_ts") is None:
        return {"status": "keine_zeit"}
    end = t.get("end_ts") or (t["start_ts"] + t["dur_s"] if t.get("dur_s") else None)
    return tageslicht(t["start_ts"], end, t.get("lat"), t.get("lng"))


@router.get("/api/bausteine/ausruestung")
def api_ausruestung():
    out = []
    for g in gear.api_gear():
        if g.get("until"):
            continue                                           # ausgemusterte Ausrüstung nicht zeigen
        out.append({k: g[k] for k in ("id", "name", "kind", "km", "up", "h", "n", "limit_km", "status", "last")})
    return out


@router.get("/api/bausteine/geplant")
def api_geplant():
    rows = db.query("SELECT id,name,sport,km,up,est_h,ts FROM plans ORDER BY ts DESC LIMIT 20")
    return [{"id": r["id"], "name": r["name"] or "", "sport": r["sport"], "km": r["km"], "up": r["up"], "est_h": r["est_h"], "ts": r["ts"]} for r in rows]
