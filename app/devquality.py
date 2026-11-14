"""Genauigkeit der Uhren: Messgrößen je Tour (nur lesend), Aggregation je Gerät, Einschätzung in Worten, Korrekturvorschläge.

Nichts hier verändert Touren, Strecken oder Höhen. Der Job „Genauigkeit der Uhren auswerten“ schreibt ausschließlich in die Tabelle
`device_quality` (eine Zeile je Tour, wird bei jedem Lauf ersetzt = wiederholbar). Korrekturen sind nur Vorschläge: die Oberfläche
ruft nach Bestätigung die vorhandenen Endpunkte auf (Höhe aus Geländemodell, Höhe aus Zepp-Uhr, Track bereinigen); alle Wiederherstellen-Wege bleiben.

Messgrößen je Tour
* STRECKE   Zepp-`dis` / Tourstrecke (bei korrigiertem Track: die ursprüngliche Strecke). Nur Touren, die genau EINEM Zepp-Training
            zugeordnet sind; Touren mit der Kennung z<Nr> entfallen (ihre Strecke IST die der Uhr). Verhältnis außerhalb 0,5–2 = „unplausibel“
            (meist falsch zugeordnet) und wird getrennt gezählt, nicht gemittelt.
* HÖHE      Auf-/Abstieg der Uhr (Höhen der Uhr, gleiche Glättung wie elev.zepp_fix) gegen den Auf-/Abstieg aus dem Geländemodell (gleiche
            Berechnung wie elev.fix) – beide auf denselben, auf höchstens 1500 Stück ausgedünnten Punkten.
            Geländemodell nur aus dem Kachel-Zwischenspeicher; höchstens `quality_tile_max` (Standard 60) NEUE Kacheln je Lauf.
* GPS       Sprünge (Tempo über der Sportart-Grenze), Anteil Pausen/Lücken, Punktabstand – aus dem Track, den die Uhr selbst aufgezeichnet hat
            (lokale Touren: gespeicherte GPX; Komoot-Touren: der Komoot-Track stammt NICHT von der Uhr, daher dort aus dem Zepp-Detail).
* PULS      Anteil unplausibler Messwerte (außerhalb 30–220 bpm) und konstanter Strecken (Sensor-Aussetzer).
Zepp-Details werden je Lauf höchstens `quality_detail_max` (Standard 120) abgerufen, reihum über die Geräte; der Rest folgt im nächsten Lauf.
"""
import json
import time
from math import hypot, cos, radians
from statistics import median

from fastapi import APIRouter, HTTPException

from . import config, db, elev, jobs, metrics, mydevices, puls, routes, trackfix
from .jobs import log

router = APIRouter()

# ------------------------------------------------------------------------------------------------ Schwellen (willkürlich, aber begründet)
MIN_N = 5                       # unter 5 verglichenen Touren sagt ein Median nichts: keine Einschätzung
RATIO_MIN, RATIO_MAX = 0.5, 2.0 # Strecken-Verhältnis außerhalb = unplausibel (falsche Zuordnung, Teilaufzeichnung)
# Strecke: mittlere Abweichung. Uhren-GPS liegt typischerweise bei 1–3 % Abweichung; die Referenz (Komoot) hat selbst Rauschen.
DIST_GOOD, DIST_OK = 3.0, 8.0   # ≤3 % gut, 3–8 % mäßig, >8 % auffällig
SPREAD_PP = 10.0                # Interquartilsabstand über 10 Prozentpunkten: „schwankt von Tour zu Tour“
# Höhe: mittlere Abweichung des Aufstiegs vom Geländemodell. Das Modell (Kachelstufe 12, 25–40 m je Pixel) glättet Gelände und unterschätzt
# Aufstiege etwas; Barometer und GPS-Höhe streuen von Tour zu Tour deutlich – darum großzügiger als bei der Strecke.
H_GOOD, H_OK = 10.0, 25.0       # ≤10 % gut, 10–25 % mäßig, >25 % auffällig
H_MIN_UP = 50.0                 # Prozentwerte nur bei mindestens 50 m Aufstieg im Modell (darunter ist Prozent sinnlos)
H_FLAG_PCT, H_FLAG_M = 25.0, 30.0   # einzelne Tour auffällig: >25 % UND mindestens 30 m Unterschied
# GPS: Anteil der Touren mit mindestens einem Sprung.
G_GOOD, G_OK = 5.0, 15.0        # ≤5 % gut, 5–15 % mäßig, >15 % auffällig
GPS_FLAG_JUMPS, GPS_FLAG_GAP = 3, 25.0   # einzelne Tour: mindestens 3 Sprünge bzw. über 25 % Lücken/Pausen
JUMP_MS = {"walk": 12.0, "run": 12.0, "bike": 25.0, "other": 35.0}   # m/s: zu Fuß 43 km/h, Rad 90 km/h, sonst (Ski …) 126 km/h
JUMP_MIN_M = 25.0               # ein Sprung ist mindestens 25 m weit (kurze Intervalle mit Zeitrauschen zählen nicht)
GAP_MIN_S, GAP_FACTOR = 60.0, 6.0   # Lücke: Abstand über 60 s und über dem Sechsfachen des üblichen Punktabstands
# Puls: Anteil der Touren mit mehr als 5 % unplausiblen Werten.
HR_LO, HR_HI = 30, 220
HR_FLAT_S, HR_FLAT_N = 120, 6   # gleicher Wert über 120 s und mindestens 6 Messungen = Sensor-Aussetzer
HR_TOUR_BAD = 5.0               # eine Tour gilt als „mit Aussetzern“ ab 5 %
HR_GOOD, HR_OK = 10.0, 25.0     # Anteil solcher Touren: ≤10 % gut, 10–25 % mäßig, >25 % auffällig
HR_FLAG_PCT = 10.0              # einzelne Tour auffällig ab 10 %
CHANNEL_SHARE = 20.0            # „Das liefert diese Uhr“: Kanal bei mindestens 20 % der Touren des Geräts
MAXPTS = 1500                   # wie routes.store

LEVEL_ORDER = {"gut": 0, "mäßig": 1, "auffällig": 2}


class NoDem(RuntimeError):
    """Geländemodell für diese Tour nicht verfügbar (Kachel fehlt im Zwischenspeicher und das Kontingent ist aufgebraucht)."""


# ------------------------------------------------------------------------------------------------ kleine Hilfen
def percentile(vals, q):
    """q in 0..100, lineare Interpolation; None bei leerer Liste."""
    v = sorted(vals)
    if not v:
        return None
    k = (len(v) - 1) * q / 100.0
    a = int(k)
    b = min(a + 1, len(v) - 1)
    return v[a] + (v[b] - v[a]) * (k - a)


def _r(x, d=1):
    return None if x is None else round(x, d)


def dist_ratio(dev_m, tour_m):
    """(Verhältnis Uhr/Tour, plausibel?) – None, wenn eine der Strecken fehlt."""
    if not dev_m or not tour_m or dev_m <= 0 or tour_m <= 0:
        return None, None
    r = dev_m / tour_m
    return r, RATIO_MIN <= r <= RATIO_MAX


def _hav(a, b):
    return hypot((b[1] - a[1]) * 111320 * cos(radians(a[0])), (b[0] - a[0]) * 110540)


def gps_quality(pts, sport):
    """Sprünge, Lücken, Punktabstand eines Tracks [[lat,lng,alt,t_ms]…]. None bei zu wenigen Punkten.
    Ohne Zeitstempel bleiben Sprünge/Lücken leer (es lässt sich kein Tempo beurteilen)."""
    n = len(pts)
    if n < 5:
        return None
    dist = sum(_hav(pts[i], pts[i + 1]) for i in range(n - 1))
    out = {"gps_n": n, "gps_jumps": None, "gps_gap_pct": None, "gps_med_dt": None, "gps_pts_km": _r(n / (dist / 1000), 1) if dist > 50 else None}
    if any(p[3] is None for p in pts):
        return out
    vmax = JUMP_MS[trackfix.kind(sport)]
    dts, jumps, prev = [], 0, False
    for a, b in zip(pts, pts[1:]):
        dt = (b[3] - a[3]) / 1000.0
        if dt <= 0:
            continue
        dts.append(dt)
        d = _hav(a, b)
        j = d >= JUMP_MIN_M and d / dt > vmax
        if j and not prev:                       # Hin- und Rücksprung eines Ausreißers = ein Ereignis
            jumps += 1
        prev = j
    total = (pts[-1][3] - pts[0][3]) / 1000.0
    if not dts or total <= 0:
        return out
    med = median(dts)
    lim = max(GAP_MIN_S, GAP_FACTOR * med)
    out.update(gps_jumps=jumps, gps_gap_pct=_r(100.0 * sum(x for x in dts if x > lim) / total, 1), gps_med_dt=_r(med, 1))
    return out


def hr_quality(rows):
    """rows: [[Sekunden, bpm, …]] -> (Anzahl, Prozent unplausibel) oder None bei weniger als 20 Messwerten."""
    n = len(rows)
    if n < 20:
        return None
    bad = [not (HR_LO <= r[1] <= HR_HI) for r in rows]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and rows[j + 1][1] == rows[i][1]:
            j += 1
        if j - i + 1 >= HR_FLAT_N and rows[j][0] - rows[i][0] >= HR_FLAT_S:
            for k in range(i, j + 1):
                bad[k] = True
        i = j + 1
    return n, _r(100.0 * sum(bad) / n, 1)


# ------------------------------------------------------------------------------------------------ Höhe
def _tile_factory(budget):
    """Kachelfunktion für elev.terrain: erst Zwischenspeicher, neue Kacheln nur im Rahmen des Kontingents; sonst NoDem."""
    cache = {}

    def tile(x, y):
        k = (x, y)
        if k in cache:
            return cache[k]
        if not (elev.DIR / str(elev.Z) / str(x) / f"{y}.png").exists():
            if budget["tiles"] <= 0:
                raise NoDem("Kachel nicht im Zwischenspeicher")
            budget["tiles"] -= 1
        try:
            px = elev._tile(x, y)
        except Exception as e:  # noqa
            raise NoDem(str(e))
        if len(cache) >= 40:
            cache.clear()
        cache[k] = px
        return px
    return tile


def height_metrics(pts, budget):
    """(Zustand, dict) – Zustand 'ok', 'no_pts', 'no_alt' oder 'no_dem'. dict: up_dev, down_dev, up_dem, down_dem.
    Geräte-Höhe wie elev._zepp_apply (bereinigen, Glättung 3/3), Gelände wie elev.fix (Glättung 5/5), beide auf denselben Punkten."""
    pts = routes._decimate(list(pts), MAXPTS) if pts else []
    if len(pts) < 20:
        return "no_pts", {}
    alts = [p[2] for p in pts]
    good = [a for a in alts if a is not None and -500.0 <= a <= 9000.0]
    if len(good) < 0.8 * len(pts) or max(good) - min(good) < 0.01:
        return "no_alt", {}                                 # keine (echten) Höhenwerte der Uhr
    up, down = elev.ascent(elev.smooth(elev.clean(alts), 3, 3))
    try:
        dem = elev.smooth(elev.terrain([(p[0], p[1]) for p in pts], tile=_tile_factory(budget)))
    except NoDem:
        return "no_dem", {}
    dup, ddown = elev.ascent(dem)
    return "ok", {"up_dev": _r(up), "down_dev": _r(down), "up_dem": _r(dup), "down_dem": _r(ddown)}


# ------------------------------------------------------------------------------------------------ Tabelle
COLS = ("tour_id", "device_id", "berechnet_am", "day", "sport", "zepp_n", "dist_tour_m", "dist_dev_m", "dist_ratio", "dist_plausible",
        "h_src", "h_state", "up_dev", "down_dev", "up_dem", "down_dem",
        "gps_src", "gps_n", "gps_jumps", "gps_gap_pct", "gps_med_dt", "gps_pts_km", "gps_dec", "hr_n", "hr_bad_pct")


def ensure_table():
    db.execute("CREATE TABLE IF NOT EXISTS device_quality (tour_id TEXT PRIMARY KEY, device_id INTEGER, berechnet_am INTEGER, day TEXT, sport TEXT, zepp_n INTEGER, "
               "dist_tour_m REAL, dist_dev_m REAL, dist_ratio REAL, dist_plausible INTEGER, h_src TEXT, h_state TEXT, up_dev REAL, down_dev REAL, up_dem REAL, down_dem REAL, "
               "gps_src TEXT, gps_n INTEGER, gps_jumps INTEGER, gps_gap_pct REAL, gps_med_dt REAL, gps_pts_km REAL, gps_dec INTEGER, hr_n INTEGER, hr_bad_pct REAL)")
    db.execute("CREATE INDEX IF NOT EXISTS device_quality_dev ON device_quality(device_id)")


def _zepp_points(s, det):
    """Zepp-Detail -> Punkte [lat, lng, alt, t_ms seit Start] (nur mit GPS)."""
    from . import zepp
    p = zepp.decode_points(s, det)
    if not p:
        return []
    t0 = p[0][0]
    return [[q[1], q[2], q[3], (q[0] - t0) * 1000] for q in p]


def match_unique(summaries, tours, tol):
    """{tour_id: [Zepp-Training …]} – dieselbe Zuordnung wie mydevices.match_summaries (z<Nr>, gleicher Start/Strecke, Überlappung)."""
    from . import sync
    byid = {t["id"]: t for t in tours}
    out = {}
    for s in summaries:
        if not isinstance(s, dict):
            continue
        try:
            tr, dis, rt = int(s["trackid"]), float(s.get("dis") or 0), int(float(s.get("run_time") or 0))
            t = byid.get(f"z{tr}") or sync.is_duplicate(tr, dis, rt, tours, tol) or mydevices._overlap(tr, dis, rt, tours)
        except (KeyError, TypeError, ValueError):
            continue
        if t:
            out.setdefault(t["id"], []).append(s)
    return out


def _own_points(t, fixed):
    """Track, den das Gerät selbst aufgezeichnet hat (nur lokale Touren), sonst None. -> (Punkte, ausgedünnt?)"""
    if t.get("source") != "local":
        return None, False
    pts = trackfix._load(t["id"], fixed=fixed)
    if not pts:
        return None, False
    from . import tracks
    return pts, not tracks.gpx_file(t["id"]).exists() and len(pts) >= 0.95 * MAXPTS


def _cfg(key, default, lo, hi):
    return max(lo, min(hi, db.get_int(key, default)))


def run(api=None, detail_max=None, tile_max=None):
    """Job: Messgrößen für alle Touren mit zugeordnetem Gerät berechnen und in device_quality speichern. Rückgabe: Zähler."""
    from . import sync
    ensure_table()
    now = int(time.time())
    budget = {"tiles": tile_max if tile_max is not None else _cfg("quality_tile_max", 60, 0, 600)}
    dmax = detail_max if detail_max is not None else _cfg("quality_detail_max", 120, 0, 600)
    asg = mydevices.assignments()
    devs = {d["id"]: d for d in db.query("SELECT * FROM devices")}
    tours = [t for t in db.query("SELECT id,name,sport,start_ts,dist_m,dur_s,source FROM tours WHERE start_ts IS NOT NULL")
             if asg.get(t["id"]) and asg[t["id"]][0]]
    fixes = {r["id"]: r["orig_dist"] for r in db.query("SELECT id, orig_dist FROM track_fix")}
    prior = {r["tour_id"]: r for r in db.query("SELECT * FROM device_quality")}
    log(f"Genauigkeit: {len(tours)} Touren mit Gerät, {len(devs)} Geräte")
    # Zepp-Verlauf einmal laden – nur wenn es eine Zepp-Uhr mit Touren gibt
    summ, by_tour = [], {}
    ztours = [t for t in tours if asg[t["id"]][0]["kind"] == "zepp"]
    if ztours:
        try:
            if api is None and (db.get("zepp_token") or (db.get("zepp_email") and db.get("zepp_password"))):
                api = sync._zepp_api()
            if api is not None:
                jobs.progress("Zepp-Verlauf wird gelesen …")
                summ = api.history()
                by_tour = match_unique(summ, ztours, db.get_int("dup_tolerance_s", 300))
                log(f"Genauigkeit: Zepp-Verlauf mit {len(summ)} Trainings gelesen, {len(by_tour)} Touren zugeordnet")
            else:
                log("Genauigkeit: Kein Zepp-Zugang eingerichtet – Strecke und Höhe der Zepp-Uhren (bei Komoot-Touren) bleiben leer")
        except Exception as e:  # noqa
            api = None
            log(f"Genauigkeit: Zepp nicht erreichbar ({type(e).__name__}) – nur lokale Messgrößen")
    rows, need = {}, []
    for i, t in enumerate(tours, 1):
        if i % 25 == 0:
            jobs.progress(f"Genauigkeit {i}/{len(tours)}")
        tid, dev = t["id"], asg[t["id"]][0]
        r = dict.fromkeys(COLS)
        r.update(tour_id=tid, device_id=dev["id"], berechnet_am=now, day=mydevices._day(t["start_ts"]), sport=t["sport"], zepp_n=0)
        cands = by_tour.get(tid, []) if dev["kind"] == "zepp" else []
        r["zepp_n"] = len(cands)
        tour_m = fixes.get(tid) or t["dist_m"]
        if len(cands) == 1 and tid != f"z{int(cands[0]['trackid'])}":
            r["dist_tour_m"] = _r(tour_m, 0)
            r["dist_dev_m"] = _r(float(cands[0].get("dis") or 0), 0) or None
            ratio, ok = dist_ratio(r["dist_dev_m"], tour_m)
            r["dist_ratio"], r["dist_plausible"] = (round(ratio, 4) if ratio else None), (None if ok is None else int(ok))
        pts, dec = _own_points(t, tid in fixes)
        if pts:
            r["h_src"], r["gps_src"] = "track", "track"
            try:
                r["h_state"], h = height_metrics(pts, budget)
            except Exception as e:  # noqa
                r["h_state"], h = "no_pts", {}
                log(f"  {tid}: Höhe nicht auswertbar ({type(e).__name__})")
            r.update(h)
            g = gps_quality(pts, t["sport"])
            if g:
                r.update(g)
                r["gps_dec"] = int(dec)
        elif len(cands) == 1 and api is not None:
            p = prior.get(tid)
            if p and p["h_src"] == "zepp" and p["h_state"] in ("ok", "no_alt", "no_pts"):
                for c in COLS[10:23]:                    # schon früher aus dem Zepp-Detail berechnet: nicht erneut abrufen
                    r[c] = p[c]
            else:
                r["h_src"], r["h_state"] = "zepp", "pending"
                need.append((dev["id"], t["start_ts"], t, cands[0]))
        try:                                             # Puls (lokal gespeichert): auch bei Komoot-Touren aus der Zusatzdatei
            hr = hr_quality(puls._series(tid)[0])
            if hr:
                r["hr_n"], r["hr_bad_pct"] = hr
        except Exception:  # noqa
            pass
        rows[tid] = r
    # Zepp-Details: reihum über die Geräte (jeweils die neuesten zuerst), höchstens dmax
    by_dev = {}
    for d, st, t, s in sorted(need, key=lambda x: -x[1]):
        by_dev.setdefault(d, []).append((t, s))
    order = []
    while any(by_dev.values()):
        for d in list(by_dev):
            if by_dev[d]:
                order.append(by_dev[d].pop(0))
    todo, rest = order[:dmax], len(order) - min(len(order), dmax)
    if need:
        log(f"Genauigkeit: {len(need)} Komoot-/Datei-Touren brauchen das Zepp-Detail, {len(todo)} davon in diesem Lauf")
    for i, (t, s) in enumerate(todo, 1):
        jobs.progress(f"Zepp-Details {i}/{len(todo)}")
        r = rows[t["id"]]
        try:
            pts = _zepp_points(s, api.detail(s))
            if not pts:
                r["h_state"] = "no_pts"
            else:
                r["h_state"], h = height_metrics(pts, budget)
                r.update(h)
                g = gps_quality(pts, t["sport"])
                if g:
                    g.update(gps_med_dt=None, gps_pts_km=None)        # Punkte aus dem Zepp-Detail sind aus mehreren Reihen zusammengesetzt: Dichte nicht beurteilen
                    r.update(g)
                    r["gps_src"], r["gps_dec"] = "zepp", 0
        except Exception as e:  # noqa
            r["h_state"] = "pending"
            log(f"  {t['id']}: Zepp-Detail nicht lesbar ({type(e).__name__})")
        time.sleep(0.2)
    if rest:
        log(f"Genauigkeit: {rest} weitere Touren folgen beim nächsten Lauf (Obergrenze {dmax} Zepp-Abrufe je Lauf)")
    nodem = sum(1 for r in rows.values() if r["h_state"] == "no_dem")
    if nodem:
        log(f"Genauigkeit: Für {nodem} Touren fehlen Geländekacheln (Obergrenze {_cfg('quality_tile_max', 60, 0, 600) if tile_max is None else tile_max} neue Kacheln je Lauf) – beim nächsten Lauf geht es weiter")
    with db.cur() as c:
        c.execute("DELETE FROM device_quality WHERE tour_id NOT IN (SELECT id FROM tours)")
        c.executemany(f"INSERT OR REPLACE INTO device_quality({','.join(COLS)}) VALUES({','.join('?' * len(COLS))})", [tuple(r[k] for k in COLS) for r in rows.values()])
    res = {"tours": len(rows), "zepp_matched": sum(1 for r in rows.values() if r["zepp_n"] == 1), "zepp_ambiguous": sum(1 for r in rows.values() if r["zepp_n"] > 1),
           "dist": sum(1 for r in rows.values() if r["dist_plausible"] == 1), "dist_implausible": sum(1 for r in rows.values() if r["dist_plausible"] == 0),
           "height": sum(1 for r in rows.values() if r["h_state"] == "ok"), "gps": sum(1 for r in rows.values() if r["gps_n"]), "hr": sum(1 for r in rows.values() if r["hr_n"]),
           "pending": sum(1 for r in rows.values() if r["h_state"] in ("pending", "no_dem"))}
    log(f"Genauigkeit fertig: {res['tours']} Touren, Strecke {res['dist']} (+{res['dist_implausible']} unplausibel), Höhe {res['height']}, GPS {res['gps']}, Puls {res['hr']}"
        + (f", {res['zepp_ambiguous']} mit mehreren Zepp-Trainings übersprungen" if res["zepp_ambiguous"] else "")
        + (f", {res['pending']} noch offen" if res["pending"] else ""))
    return res


# ------------------------------------------------------------------------------------------------ Einschätzung
def _lvl(v, good, ok):
    return "gut" if v <= good else "mäßig" if v <= ok else "auffällig"


def _de(x, d=1):
    return f"{x:.{d}f}".replace(".", ",")


def _stat(vals):
    return {"n": len(vals), "median": _r(median(vals), 2) if vals else None, "p25": _r(percentile(vals, 25), 2), "p75": _r(percentile(vals, 75), 2)}


def assess_dist(rows, ref):
    """Strecke: Abweichung der Uhr von der Tourstrecke. ref = 'komoot' oder 'tour' (Wortwahl)."""
    ok = [r for r in rows if r["dist_plausible"] == 1 and r["dist_ratio"]]
    n_bad = sum(1 for r in rows if r["dist_plausible"] == 0)
    pcts = [(r["dist_ratio"] - 1) * 100 for r in ok]
    out = {"n": len(ok), "n_implausible": n_bad, "level": None, "text": None, "points": [round(p, 1) for p in pcts[:400]]}
    if not pcts:
        return out
    s = _stat(pcts)
    out.update(s)
    if len(pcts) < MIN_N:
        return out
    med = s["median"]
    out["level"] = _lvl(abs(med), DIST_GOOD, DIST_OK)
    if out["level"] == "gut":
        out["text"] = f"Die Strecke passt zur {'Komoot-Strecke' if ref == 'komoot' else 'gespeicherten Strecke'} (im Mittel {_de(abs(med))} % Abweichung)."
    else:
        out["text"] = f"Die Uhr misst im Mittel {_de(abs(med))} % {'kürzer' if med < 0 else 'länger'} als die {'Komoot-Strecke' if ref == 'komoot' else 'gespeicherte Strecke'}."
    if s["p75"] - s["p25"] > SPREAD_PP:
        out["spread"] = f"Die Abweichung schwankt von Tour zu Tour stark ({_de(s['p25'], 0)} bis {_de(s['p75'], 0)} %)."
    return out


def assess_height(rows):
    ok = [r for r in rows if r["h_state"] == "ok" and r["up_dem"] is not None and r["up_dev"] is not None]
    up = [(r["up_dev"] - r["up_dem"]) / r["up_dem"] * 100 for r in ok if r["up_dem"] >= H_MIN_UP]
    dn = [(r["down_dev"] - r["down_dem"]) / r["down_dem"] * 100 for r in ok if (r["down_dem"] or 0) >= H_MIN_UP]
    out = {"n": len(ok), "n_pct": len(up), "level": None, "text": None, "points": [round(p, 1) for p in up[:400]],
           "up_err_m": _stat([r["up_dev"] - r["up_dem"] for r in ok]), "down_err_m": _stat([r["down_dev"] - r["down_dem"] for r in ok]), "up_err_pct": _stat(up), "down_err_pct": _stat(dn)}
    if len(up) < MIN_N:
        return out
    med, mad = median(up), median(abs(x) for x in up)
    out["level"] = _lvl(mad, H_GOOD, H_OK)                 # Streuung entscheidet (typisches |Fehler|), das Vorzeichen steht im Text
    if out["level"] == "gut":
        out["text"] = f"Auf- und Abstieg passen zum Geländemodell (im Mittel {_de(mad)} % Abweichung)."
    else:
        out["text"] = f"Der Aufstieg liegt im Mittel {_de(abs(med))} % {'niedriger' if med < 0 else 'höher'} als im Geländemodell (typische Abweichung {_de(mad, 0)} %)."
    return out


def assess_gps(rows):
    g = [r for r in rows if r["gps_jumps"] is not None]
    out = {"n": len(g), "level": None, "text": None}
    if not g:
        return out
    gaps = [r["gps_gap_pct"] for r in g if r["gps_gap_pct"] is not None]
    dts = [r["gps_med_dt"] for r in g if r["gps_src"] == "track" and not r["gps_dec"] and r["gps_med_dt"]]
    share = 100.0 * sum(1 for r in g if r["gps_jumps"] > 0) / len(g)
    out.update(jump_tours_pct=_r(share, 1), median_jumps=_r(median(r["gps_jumps"] for r in g), 1), median_gap_pct=_r(median(gaps), 1) if gaps else None,
               median_dt_s=_r(median(dts), 1) if dts else None, n_dt=len(dts))
    if len(g) < MIN_N:
        return out
    out["level"] = _lvl(share, G_GOOD, G_OK)
    out["text"] = (f"Die GPS-Spur ist sauber (nur bei {_de(share, 0)} % der Touren Sprünge)." if out["level"] == "gut"
                   else f"Bei {_de(share, 0)} % der Touren springt die GPS-Spur (unmögliches Tempo).")
    return out


def assess_hr(rows):
    h = [r for r in rows if r["hr_n"]]
    out = {"n": len(h), "level": None, "text": None}
    if not h:
        return out
    share = 100.0 * sum(1 for r in h if r["hr_bad_pct"] > HR_TOUR_BAD) / len(h)
    out.update(bad_tours_pct=_r(share, 1), median_bad_pct=_r(median(r["hr_bad_pct"] for r in h), 1))
    if len(h) < MIN_N:
        return out
    out["level"] = _lvl(share, HR_GOOD, HR_OK)
    out["text"] = (f"Der Puls ist plausibel (nur bei {_de(share, 0)} % der Touren Aussetzer)." if out["level"] == "gut"
                   else f"Bei {_de(share, 0)} % der Touren hat der Puls Aussetzer oder unmögliche Werte.")
    return out


def verdict(parts):
    """Gesamteinschätzung: schlechteste bewertete Messgröße. parts: {name: assess-dict}."""
    rated = {k: v for k, v in parts.items() if v.get("level")}
    if not rated:
        return {"level": None, "label": "Noch keine Einschätzung", "findings": [f"Für eine Einschätzung braucht jede Messgröße mindestens {MIN_N} verglichene Touren."]}
    worst = max((v["level"] for v in rated.values()), key=LEVEL_ORDER.get)
    find = [v["text"] for k, v in rated.items() if v["level"] != "gut" and v.get("text")]
    for v in rated.values():
        if v.get("spread"):
            find.append(v["spread"])
    if worst == "gut":
        return {"level": "gut", "label": "Zuverlässig", "findings": [v["text"] for v in rated.values() if v.get("text")]}
    return {"level": worst, "label": "Mit Einschränkungen zuverlässig" if worst == "mäßig" else "Auffällige Abweichungen", "findings": find}


# ------------------------------------------------------------------------------------------------ Kanäle („Das liefert diese Uhr“)
CH_LABEL = {"hr": "Puls", "speed": "Tempo", "cad": "Kadenz", "pow": "Leistung", "temp": "Temperatur", "resp": "Atmung", "stride": "Schrittlänge",
            "gct": "Bodenkontaktzeit", "vosc": "Vertikale Oszillation", "press": "Luftdruck", "kcal": "Kalorien", "te": "Trainingseffekt"}
CH_ORDER = ["hr", "speed", "cad", "stride", "pow", "temp", "resp", "gct", "vosc", "press", "kcal", "te"]
_SC = {}


def _sidecar_keys(tid):
    """Kanäle einer Tour aus der .met.json (mit Zwischenspeicher nach Änderungszeit)."""
    p = metrics.sidecar(tid)
    try:
        st = p.stat()
    except OSError:
        return ()
    c = _SC.get(str(p))
    if c and c[0] == (st.st_mtime_ns, st.st_size):
        return c[1]
    d = metrics.load(tid) or {}
    keys = tuple(k for k, v in (d.get("series") or {}).items() if isinstance(v, list) and any(x is not None for x in v)) + tuple(k for k in (d.get("sum") or {}) if k in CH_LABEL)
    _SC[str(p)] = ((st.st_mtime_ns, st.st_size), keys)
    return keys


def channels(tids):
    """[{key,label,n,share}] – Kanäle, die bei mindestens CHANNEL_SHARE % der Touren vorkommen."""
    if not tids:
        return []
    cnt = {}
    hr = puls.tours_with_hr()
    for tid in tids:
        ks = set(_sidecar_keys(tid))
        if tid in hr:
            ks.add("hr")
        for k in ks:
            cnt[k] = cnt.get(k, 0) + 1
    out = [{"key": k, "label": CH_LABEL[k], "n": cnt[k], "share": _r(100.0 * cnt[k] / len(tids), 0)} for k in CH_ORDER if k in cnt and 100.0 * cnt[k] / len(tids) >= CHANNEL_SHARE]
    return out


# ------------------------------------------------------------------------------------------------ Vorschläge
def tour_flags(r):
    """Auffälligkeiten einer Tour (Liste von {kind, value, …}); leer = unauffällig. Reihenfolge = Schwere."""
    f = []
    if r["dist_plausible"] == 0:
        f.append({"kind": "dist_implausible", "ratio": _r(r["dist_ratio"], 2), "dev_m": r["dist_dev_m"], "tour_m": r["dist_tour_m"]})
    elif r["dist_plausible"] == 1 and abs(r["dist_ratio"] - 1) * 100 > DIST_OK:
        f.append({"kind": "dist", "pct": _r((r["dist_ratio"] - 1) * 100, 1), "dev_m": r["dist_dev_m"], "tour_m": r["dist_tour_m"]})
    if r["h_state"] == "ok" and r["up_dem"] is not None and r["up_dem"] >= H_MIN_UP:
        e = r["up_dev"] - r["up_dem"]
        if abs(e) / r["up_dem"] * 100 > H_FLAG_PCT and abs(e) >= H_FLAG_M:
            f.append({"kind": "height", "pct": _r(e / r["up_dem"] * 100, 1), "err_m": _r(e, 0), "up_dev": r["up_dev"], "up_dem": r["up_dem"]})
    if (r["gps_jumps"] or 0) >= GPS_FLAG_JUMPS:
        f.append({"kind": "gps_jumps", "n": r["gps_jumps"]})
    if (r["gps_gap_pct"] or 0) > GPS_FLAG_GAP:
        f.append({"kind": "gps_gaps", "pct": r["gps_gap_pct"]})
    if (r["hr_bad_pct"] or 0) > HR_FLAG_PCT:
        f.append({"kind": "hr", "pct": r["hr_bad_pct"]})
    return f


def _suggestions(tid, flags, dev_kind, fix):
    """Vorhandene Aktionen, die zu den Auffälligkeiten passen. Nur Beschreibungen – ausgeführt wird erst nach Bestätigung in der Oberfläche."""
    out = []
    kinds = {x["kind"] for x in flags}
    if "height" in kinds:
        out.append({"action": "elev-dem", "label": "Höhe aus Geländemodell neu berechnen", "method": "POST", "url": f"/api/tours/{tid}/elev-fix", "undo": f"/api/tours/{tid}/elev-restore"})
        if dev_kind == "zepp":
            out.append({"action": "elev-zepp", "label": "Höhe aus Uhr (Zepp) abgleichen", "method": "POST", "url": f"/api/tours/{tid}/elev-zepp", "undo": f"/api/tours/{tid}/elev-restore"})
    if kinds & {"gps_jumps", "gps_gaps"}:
        out.append({"action": "trackfix", "label": "GPS-Track bereinigen …", "tour": tid})
    if "dist" in kinds or "dist_implausible" in kinds:
        out.append({"action": "info", "label": "Nur ein Hinweis: die Strecke wird nicht verändert."})
    if fix:
        out.append({"action": "elev-restore", "label": "Höhenkorrektur zurücknehmen", "method": "POST", "url": f"/api/tours/{tid}/elev-restore"})
    return out


def _current_rows():
    """Zeilen der Tabelle, je Tour dem AKTUELL zugeordneten Gerät (nach Umhängen zählt das neue Gerät). {device_id: [row…]} und {tour_id: tour}."""
    ensure_table()
    asg = mydevices.assignments()
    tours = {t["id"]: t for t in db.query("SELECT id,name,start_ts,source FROM tours")}
    per = {}
    for r in db.query("SELECT * FROM device_quality"):
        a = asg.get(r["tour_id"])
        if a and a[0] and r["tour_id"] in tours:
            r["device_id"] = a[0]["id"]
            per.setdefault(a[0]["id"], []).append(r)
    return per, tours, asg


def payload():
    per, tours, asg = _current_rows()
    devs = db.query("SELECT * FROM devices ORDER BY active DESC, kind, COALESCE(NULLIF(since,''),'0000'), name")
    mine = {}
    for tid, (d, _m) in asg.items():
        if d:
            mine.setdefault(d["id"], []).append(tid)
    out = []
    last = 0
    for d in devs:
        rows = per.get(d["id"], [])
        last = max([last] + [r["berechnet_am"] or 0 for r in rows])
        dr = [r for r in rows if r["dist_plausible"] is not None]
        komoot = sum(1 for r in dr if tours[r["tour_id"]]["source"] == "komoot")
        ref = "komoot" if komoot and komoot * 2 >= len(dr) else "tour"      # Wortwahl: Referenz ist meist die Komoot-Strecke
        parts = {"dist": assess_dist(rows, ref), "height": assess_height(rows), "gps": assess_gps(rows), "hr": assess_hr(rows)}
        days = sorted(r["day"] for r in rows if r["day"])
        flagged = sum(1 for r in rows if tour_flags(r))
        tips = []
        if parts["height"]["level"] in ("mäßig", "auffällig"):
            tips.append({"kind": "height", "text": "Bei einzelnen Touren lässt sich die Höhe aus dem Geländemodell neu berechnen oder mit der Uhr abgleichen (Liste „Auffällige Touren“). Jede Änderung ist wiederherstellbar."})
        if parts["gps"]["level"] in ("mäßig", "auffällig"):
            tips.append({"kind": "gps", "text": "Bei Touren mit GPS-Sprüngen hilft „GPS-Track bereinigen“. Das Original bleibt erhalten."})
        if parts["dist"]["level"] in ("mäßig", "auffällig") and parts["dist"].get("median") is not None:
            m = parts["dist"]["median"]
            who = "die Komoot-Strecke" if ref == "komoot" else "die gespeicherte Strecke"
            tips.append({"kind": "dist", "text": f"Die Uhr misst im Mittel {_de(abs(m))} % {'kürzer' if m < 0 else 'länger'} als {who}. Für Vergleiche der Strecken bitte beachten – die Strecke wird nicht geändert."})
        out.append({"id": d["id"], "name": d["name"], "kind": d["kind"], "model": d["model"] or "", "active": bool(d["active"]),
                    "n_tours": len(mine.get(d["id"], [])), "n_eval": len(rows), "flagged": flagged,
                    "period": {"from": days[0], "to": days[-1]} if days else None,
                    **{k: v for k, v in parts.items()}, "verdict": verdict(parts), "tips": tips, "ref": ref,
                    "channels": channels(mine.get(d["id"], []))})
    zepp_ok = bool(db.get("zepp_token") or (db.get("zepp_email") and db.get("zepp_password")))
    return {"devices": out, "computed_at": last or None, "zepp_configured": zepp_ok, "min_n": MIN_N,
            "thresholds": {"dist": [DIST_GOOD, DIST_OK], "height": [H_GOOD, H_OK], "gps": [G_GOOD, G_OK], "hr": [HR_GOOD, HR_OK]}}


@router.get("/api/devices/quality")
def api_quality():
    return payload()


@router.get("/api/devices/{did}/quality/tours")
def api_quality_tours(did: int, limit: int = 100):
    d = db.one("SELECT * FROM devices WHERE id=?", (did,))
    if not d:
        raise HTTPException(404, "Gerät nicht gefunden")
    per, tours, _asg = _current_rows()
    fx = {r["id"]: r["src"] for r in db.query("SELECT id, src FROM elev_fix")}
    names = {r["id"]: r["name"] for r in db.query("SELECT id,name FROM tours")}
    out = []
    for r in per.get(did, []):
        fl = tour_flags(r)
        if not fl:
            continue
        tid = r["tour_id"]
        order = {"dist_implausible": 0, "gps_jumps": 1, "height": 2, "dist": 3, "gps_gaps": 4, "hr": 5}
        out.append({"id": tid, "name": names.get(tid) or tid, "day": r["day"], "flags": fl, "fixed": ("zepp" if fx[tid] == "zepp" else "dem") if tid in fx else None,
                    "suggest": _suggestions(tid, fl, d["kind"], tid in fx), "_o": min(order[x["kind"]] for x in fl), "_n": len(fl)})
    out.sort(key=lambda x: x["day"] or "", reverse=True)               # neueste zuerst, danach stabil nach Schwere
    out.sort(key=lambda x: (-x["_n"], x["_o"]))
    for x in out:
        x.pop("_o"); x.pop("_n")
    return {"device": {"id": d["id"], "name": d["name"]}, "total": len(out), "tours": out[:max(1, min(limit, 500))]}
