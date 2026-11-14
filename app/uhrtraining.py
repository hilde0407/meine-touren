"""„Training laut Uhr“: die Werte, die eine Zepp-Uhr (Amazfit Cheetah Pro, Balance …) zu einem Training wirklich geliefert hat.

Quelle: Trainingszusammenfassung aus dem Zepp-Verlauf (api.history()) und – einmal je Tour – die Kilometer-Splits (`kilo_pace`) aus dem Zepp-Detail.
Zuordnung Tour ↔ Training wie überall (devquality.match_unique = mydevices.match_summaries). Das Ergebnis liegt je Tour dauerhaft in
tracks/<id>.uhr.json (nur ausgewählte Felder, keine Koordinaten/Kennungen): Der Abschnitt funktioniert danach ohne Zepp-Zugang, und Seitenaufrufe
belasten Zepp nicht. Der Verlauf wird höchstens alle 10 Minuten neu geladen (Zwischenspeicher im Speicher).
Der Job „Uhr-Daten aller Touren laden“ (load_all, 3.12.0) schreibt dieselben Zusatzdateien für alle zugeordneten Zepp-Touren aus EINEM Verlauf – ohne Detail-Abrufe.
Solche Dateien tragen "detail": false und "detail_offen": true; die Kilometerwerte werden beim ersten Öffnen der Tour nachgeholt (danach "detail_offen": false,
auch wenn das Detail fehlschlug – „Von Zepp neu laden“ versucht es erneut). Ein erneutes Laden überschreibt nie schon vorhandene Kilometerwerte mit „nichts“.

Grundsatz: Es wird nur gezeigt, was die Uhr geliefert hat UND plausibel ist. Platzhalter (-1, -274, -361, -2 004 831 …) und Unsinn erscheinen nie.
Deutungen, die nicht belegt sind (Skalen und Spalten), sind unten als ANNAHME gekennzeichnet und werden mit Gegenproben abgesichert:

* te / anaerobic_te      ANNAHME: ganze Zahl in Zehnteln (26 = 2,6). Keine ganze Zahl oder außerhalb 1..60 → nicht angezeigt.
* exercise_load, rpe     unverändert angezeigt (Skala laut Zepp, nicht mit Garmin vergleichbar).
* avg_pace               wird NIE angezeigt (Einheit unbekannt; die Werte 0,95–2,1 sind als min/km unmöglich).
* avg_slope              wird nicht angezeigt (Einheit unbekannt). pauseTimeWithMillis wird nicht ausgewertet (Einheit unbekannt); nur pause_time (Sekunden).
* heart_range            ANNAHME: sechs Paare „Sekunden in der Zone, obere Pulsgrenze“. Nur angezeigt, wenn die Summe der Zonenzeiten zur Dauer (run_time)
                         passt (±15 %) und die Grenzen aufsteigen (40..250).
* weatherInfo            ANNAHME: [1] = Temperatur in °C, [5] = Luftfeuchte in %. Nur angezeigt, wenn plausibel (−30..50 bzw. 1..100; 0 = Platzhalter).
* kilo_pace              ANNAHME: je Zeile [0] = Kilometer-Nr. (0-basiert), [1] = Sekunden für diesen Kilometer, [4] = Puls, [9] = Schrittzyklen oder Schritte/min.
                         Splits nur, wenn Summe der Zeiten und Strecke zur Tour passen; Teilkilometer am Ende nur, wenn Zeit und Reststrecke dazu passen.
                         Puls nur, wenn [4] in 40..220 liegt. Schrittfrequenz nur, wenn [9] (oder 2×[9]) zur mittleren Schrittfrequenz der Zusammenfassung passt.
"""
import json
import math
import re
import threading
import time
from statistics import median

from fastapi import APIRouter, HTTPException, Request

from . import config, ctx, db, devquality, mydevices, sync

router = APIRouter()

TTL = 600                       # Verlauf höchstens so lange (Sekunden) im Speicher behalten
ERR_TTL = 120                   # nach einem Zepp-Fehler so lange nicht erneut anfragen
PLACEHOLDER = {-1.0, -274.0, -361.0, -2000000.0, -2004831.0}
KEEP = ("trackid", "type", "dis", "run_time", "end_time", "te", "anaerobic_te", "exercise_load", "rpe", "calorie", "total_step", "pause_time",
        "avg_heart_rate", "max_heart_rate", "min_heart_rate", "avg_frequency", "altitude_ascend", "altitude_descend", "max_altitude", "min_altitude",
        "heart_range", "weatherInfo")                                   # nur diese Felder landen in der Zusatzdatei (kein source, keine Koordinaten)
MAX_RAW = 200_000

_LOCK = threading.Lock()
_HIST = {}                      # Benutzer -> {"ts", "hist", "api"}
_ERR = {}                       # Benutzer -> (ts, Zustand, Meldung)

MSG = {
    "kein_zugang": "Es ist kein Zepp-Zugang eingerichtet (Einstellungen → Zepp). Gespeicherte Werte bleiben sichtbar.",
    "fehler": "Zepp ist gerade nicht erreichbar oder die Zugangsdaten stimmen nicht. Gespeicherte Werte bleiben sichtbar.",
    "kein_training": "Zu dieser Tour wurde im Zepp-Verlauf kein passendes Training gefunden.",
    "mehrdeutig": "Zu dieser Tour passen mehrere Zepp-Trainings – es wird nichts angezeigt, um nichts zu verwechseln.",
    "nicht_zepp": "Diese Tour stammt nicht von einer Zepp-Uhr.",
    "nicht_geladen": "Noch nicht von Zepp geladen.",
}


HINT = {
    "te": "Trainingseffekt: Skala laut Zepp (Rohwert in Zehnteln gelesen, 26 = 2,6) – nicht mit Garmin vergleichbar.",
    "last": "Belastung und Anstrengung: Skalen laut Zepp, nicht mit Garmin oder Suunto vergleichbar.",
    "zonen": "Pulszonen: Zeiten und Obergrenzen laut Uhr, so gedeutet – die Summe der Zonenzeiten passt zur Dauer.",
    "splits": "Kilometerwerte: Kilometer-Nr., Zeit und Puls je Kilometer laut Uhr; die Spalten sind von Zepp nicht dokumentiert und wurden gegen Dauer und Strecke geprüft.",
    "hoehe": "Höhenmeter laut Uhr können von den Höhenmetern der Tour abweichen (andere Messung und Glättung).",
    "wetter": "Wetter laut Uhr (Temperatur und Luftfeuchte); die Deutung der Felder ist nicht von Zepp dokumentiert.",
    "detail": "Die Kilometerwerte konnten nicht geladen werden – „Von Zepp neu laden“ versucht es erneut.",
    "detail_offen": "Die Kilometerwerte werden beim ersten Öffnen der Tour von Zepp geladen.",
}


def reset_cache():
    with _LOCK:
        _HIST.clear()
        _ERR.clear()


def sidecar(tid):
    return config.TRACK_DIR / f"{tid}.uhr.json"


def load(tid):
    try:
        d = json.loads(sidecar(tid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) and isinstance(d.get("summary"), dict) else None


def store(tid, data):
    config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
    p = sidecar(tid)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)


def forget(tid):
    sidecar(tid).unlink(missing_ok=True)


# ------------------------------------------------------------------------------------------------ Zahlen prüfen
def _f(v):
    """Zahl oder None (kein Wahrheitswert, nicht NaN/unendlich, kein Platzhalter)."""
    if isinstance(v, bool) or v is None:
        return None
    try:
        x = float(str(v).strip()) if isinstance(v, str) else float(v)
    except (TypeError, ValueError):
        return None
    return None if (not math.isfinite(x) or x in PLACEHOLDER) else x


def _rng(v, lo, hi):
    x = _f(v)
    return x if x is not None and lo <= x <= hi else None


def _rows(raw):
    """Zepp-Tabelle „a,b,c;a,b,c“ (Text) oder Liste von Listen -> [[Zahl oder None …] …]. Unlesbares ergibt eine leere Liste."""
    out = []
    try:
        if isinstance(raw, str):
            if len(raw) > MAX_RAW:
                return []
            for r in filter(None, raw.split(";")):
                out.append([_f(c) if c.strip() != "" else None for c in r.split(",")])
        elif isinstance(raw, (list, tuple)):
            for r in raw:
                if isinstance(r, (list, tuple)):
                    out.append([_f(c) for c in r])
                elif isinstance(r, str) and "," in r:
                    out.append([_f(c) if c.strip() != "" else None for c in r.split(",")])
                else:
                    return []
    except (TypeError, ValueError):
        return []
    return out[:2000]


def _list(raw):
    """weatherInfo: Liste, JSON-Text oder „a,b,c“ -> Liste von Rohwerten."""
    if isinstance(raw, (list, tuple)):
        return list(raw)
    if isinstance(raw, str):
        s = raw.strip()
        if s.startswith("["):
            try:
                v = json.loads(s)
                return v if isinstance(v, list) else []
            except ValueError:
                return []
        return [c for c in re.split(r"[;,]", s)]
    return []


# ------------------------------------------------------------------------------------------------ Auswertung
def kennzahlen(s):
    """Werte der Zusammenfassung -> {schlüssel: {"wert", …}}; nur Plausibles."""
    w = {}
    te = _f(s.get("te"))
    if te is not None and te == int(te) and 1 <= te <= 60:
        w["te"] = {"wert": round(te / 10, 1)}
    ate = _f(s.get("anaerobic_te"))
    if ate is not None and ate == int(ate) and 1 <= ate <= 60:
        w["ate"] = {"wert": round(ate / 10, 1)}
    x = _rng(s.get("exercise_load"), 1, 2000)
    if x is not None:
        w["last"] = {"wert": round(x)}
    x = _rng(s.get("rpe"), 1, 10)
    if x is not None:
        w["rpe"] = {"wert": round(x, 1) if x != int(x) else int(x)}
    x = _rng(s.get("calorie"), 1, 30000)
    if x is not None:
        w["kcal"] = {"wert": round(x)}
    x = _rng(s.get("total_step"), 1, 300000)
    if x is not None:
        w["schritte"] = {"wert": round(x)}
    x = _rng(s.get("pause_time"), 1, 86400)          # -1 = keine Angabe; 0 wird nicht gezeigt
    if x is not None:
        w["pause_s"] = {"wert": round(x)}
    avg, mx, mn = (_rng(s.get(k), 30, 240) for k in ("avg_heart_rate", "max_heart_rate", "min_heart_rate"))
    if avg is not None and mx is not None and avg > mx:
        mx = mn = None
    if mn is not None and (avg is not None and mn > avg or mx is not None and mn > mx):
        mn = None
    for k, v in (("puls_avg", avg), ("puls_max", mx), ("puls_min", mn)):
        if v is not None:
            w[k] = {"wert": round(v)}
    x = _rng(s.get("avg_frequency"), 30, 260)
    if x is not None:
        w["frequenz"] = {"wert": round(x)}
    up, down = _rng(s.get("altitude_ascend"), 0, 15000), _rng(s.get("altitude_descend"), 0, 15000)
    if up == 0 and down == 0:
        up = down = None                              # beides 0 = vermutlich Platzhalter
    if up is not None:
        w["aufstieg"] = {"wert": round(up)}
    if down is not None:
        w["abstieg"] = {"wert": round(down)}
    hi, lo = _rng(s.get("max_altitude"), -500, 9000), _rng(s.get("min_altitude"), -500, 9000)
    if hi is not None and lo is not None and (hi < lo or hi == lo == 0):
        hi = lo = None
    if hi is not None:
        w["hoehe_max"] = {"wert": round(hi)}
    if lo is not None:
        w["hoehe_min"] = {"wert": round(lo)}
    return w


def pulszonen(s):
    """Sechs Paare (Sekunden in der Zone, obere Grenze) – nur, wenn die Summe zur Dauer passt. Sonst None."""
    run = _rng(s.get("run_time"), 60, 7 * 86400)
    rows = _rows(s.get("heart_range"))
    if run is None or not 3 <= len(rows) <= 8 or any(len(r) < 2 or r[0] is None or r[1] is None for r in rows):
        return None
    secs, lims = [r[0] for r in rows], [r[1] for r in rows]
    if any(x < 0 for x in secs) or any(not 40 <= x <= 250 for x in lims) or any(b <= a for a, b in zip(lims, lims[1:])):
        return None
    tot = sum(secs)
    if tot <= 0 or not 0.85 * run <= tot <= 1.15 * run:
        return None
    return [{"zone": i + 1, "sekunden": round(a), "bis_bpm": round(b), "anteil": round(a / tot, 4)} for i, (a, b) in enumerate(zip(secs, lims))]


def wetter(s):
    """Temperatur (°C) und Luftfeuchte (%) laut Uhr – nur plausible Werte. Sonst None."""
    w = _list(s.get("weatherInfo"))
    t = _f(w[1]) if len(w) > 1 else None
    h = _f(w[5]) if len(w) > 5 else None
    t = t if t is not None and t != 0 and -30 <= t <= 50 else None          # 0 = Platzhalter
    h = h if h is not None and 1 <= h <= 100 else None
    out = {}
    if t is not None:
        out["temp_c"] = round(t, 1) if t != int(t) else int(t)
    if h is not None:
        out["feuchte_pct"] = round(h)
    return out or None


def splits(s, kilo_pace, freq=None):
    """Kilometer-Splits -> Liste {"km", "sek", "min_km", "puls", "schritte", "strecke_m"} oder None, wenn es nicht zur Tour passt."""
    dis, run = _rng(s.get("dis"), 100, 1_000_000), _rng(s.get("run_time"), 60, 7 * 86400)
    rows = _rows(kilo_pace)
    if dis is None or run is None or not rows:
        return None
    nfull = int(dis // 1000)
    if nfull < 1:
        return None
    idx = [r[0] if r else None for r in rows]
    if any(i is None or i != int(i) for i in idx) or [int(i) for i in idx] != list(range(len(rows))) or len(rows) > nfull + 1:
        return None                                   # Nummern lückenlos ab 0, höchstens ein Teilstück am Ende
    full = rows[:nfull]
    tim = [r[1] if len(r) > 1 else None for r in full]
    if not full or any(t is None or not 120 <= t <= 3600 for t in tim):
        return None
    expect = run * len(full) * 1000.0 / dis
    if sum(tim) > 1.15 * run or not 0.6 * expect <= sum(tim) <= 1.4 * expect:
        return None
    out = [{"km": i + 1, "sek": round(t), "min_km": round(t / 60, 2), "puls": None, "schritte": None, "strecke_m": 1000, "_r": r} for i, (t, r) in enumerate(zip(tim, full))]
    if len(rows) == nfull + 1 and len(full) == nfull:                 # Teilstück: nur, wenn Zeit und Reststrecke zusammenpassen
        r = rows[nfull]
        rem = dis - nfull * 1000.0
        t = r[1] if len(r) > 1 else None
        if t is not None and rem >= 100 and t > 0:
            pace = t / (rem / 1000.0)
            med = median(tim)
            if 0.6 * med <= pace <= 1.6 * med and 0.9 * run <= sum(tim) + t <= 1.1 * run:
                out.append({"km": nfull + 1, "sek": round(t), "min_km": round(pace / 60, 2), "puls": None, "schritte": None, "strecke_m": round(rem), "_r": r})
    if len(out) < 2:
        return None
    ok = [o for o in out if len(o["_r"]) > 4 and o["_r"][4] is not None and 40 <= o["_r"][4] <= 220]
    if len(ok) >= 0.6 * len(out):
        for o in ok:
            o["puls"] = round(o["_r"][4])
    cad = [o["_r"][9] for o in out if len(o["_r"]) > 9 and o["_r"][9] is not None and o["_r"][9] > 0]
    if freq and len(cad) >= 0.6 * len(out):
        m = median(cad)
        fac = min((1, 2), key=lambda f: abs(m * f - freq))
        if abs(m * fac - freq) <= 0.25 * freq:
            for o in out:
                c = o["_r"][9] if len(o["_r"]) > 9 else None
                if c is not None and c > 0 and 40 <= c * fac <= 260:
                    o["schritte"] = round(c * fac)
    for o in out:
        o.pop("_r")
    return out


# ------------------------------------------------------------------------------------------------ Ermüdungsverlauf
# Alle Schwellen sind WILLKÜRLICH gewählt (Erfahrungswerte, nicht belegt) – sie ordnen nur in Worten ein, die Zahlen selbst stehen daneben.
ERM_MIN_KM = 6              # unter 6 vollen Kilometern ist der Unterschied der Hälften zu zufällig: keine Wertung
ERM_TEMPO = (3, 8, 15)      # Tempoverlust in %: <3 gleichmäßig, 3–8 leicht, 8–15 spürbar, ab 15 deutlich langsamer
ERM_PULS = 5                # Pulsänderung (bpm), ab der „Puls stieg/sank“ gesagt wird
ERM_HOEHE_M, ERM_HOEHE_X = 40, 2.0      # Hälften „stark verschieden“ in den Höhenmetern: Unterschied mindestens 40 m UND mindestens doppelt so viel


def _hoehe_verschieden(h):
    """True, wenn Auf- oder Abstieg der beiden Hälften stark verschieden sind (dann ist ein Tempovergleich unfair)."""
    for k in ("auf", "ab"):
        a, b = h["erste"][k], h["zweite"][k]
        if abs(a - b) >= ERM_HOEHE_M and max(a, b) >= ERM_HOEHE_X * max(min(a, b), 10):
            return True
    return False


def ermuedung(sp, hoehen=None):
    """Tempo und Puls der ersten gegen die zweite Hälfte (nach Strecke geteilt) aus den Kilometer-Splits.
    Nur volle Kilometer zählen (Teilstück am Ende entfällt); bei ungerader Zahl bleibt der mittlere Kilometer außen vor.
    Unter ERM_MIN_KM vollen Kilometern: None. hoehen = {"erste": {"auf","ab"}, "zweite": {…}} (m) oder None (unbekannt).
    Unterscheiden sich die Hälften stark in den Höhenmetern, gibt es nur einen Hinweis und keine Wertung.
    -> {"status": "ok"|"nur_hinweis", "km": Anzahl voller Kilometer, "tempo_pct": +langsamer/−schneller, "puls_diff": bpm oder None, "stufe", "puls", "hoehen_geprueft", "hoehen"}"""
    full = [s for s in (sp or []) if s.get("strecke_m") == 1000 and s.get("sek")]
    n = len(full)
    if n < ERM_MIN_KM:
        return None
    k = n // 2
    a, b = full[:k], full[n - k:]
    base = {"km": n, "k": k, "hoehen_geprueft": hoehen is not None, "hoehen": hoehen}
    if hoehen is not None and _hoehe_verschieden(hoehen):
        return {**base, "status": "nur_hinweis", "tempo_pct": None, "puls_diff": None, "stufe": None, "puls": None}
    ta, tb = sum(x["sek"] for x in a) / k, sum(x["sek"] for x in b) / k
    pct = round((tb / ta - 1) * 100)
    pa, pb = [x["puls"] for x in a if x.get("puls") is not None], [x["puls"] for x in b if x.get("puls") is not None]
    diff = round(sum(pb) / len(pb) - sum(pa) / len(pa)) if len(pa) >= 0.6 * k and len(pb) >= 0.6 * k else None
    lo, mid, hi = ERM_TEMPO
    stufe = ("deutlich_langsamer" if pct >= hi else "spuerbar_langsamer" if pct >= mid else "leicht_langsamer" if pct >= lo else
             "schneller" if pct <= -lo else "gleichmaessig")
    puls = None if diff is None else "steigt" if diff >= ERM_PULS else "sinkt" if diff <= -ERM_PULS else "gleich"
    return {**base, "status": "ok", "tempo_pct": pct, "puls_diff": diff, "stufe": stufe, "puls": puls}


def ermuedung_fuer(tid, s, sp):
    """ermuedung() für eine Tour; die Höhenmeter je Hälfte kommen aus der Strecke (fehlt sie oder hat sie keine Höhe, bleibt hoehen None)."""
    if not sp:
        return None
    full = [x for x in sp if x.get("strecke_m") == 1000]
    if len(full) < ERM_MIN_KM:
        return None
    h = None
    try:
        from . import steigung
        h = steigung.hoehen_je_haelfte(tid, len(full) // 2, _rng(s.get("dis"), 100, 1_000_000))
    except Exception:  # noqa
        h = None
    return ermuedung(sp, h)


# ------------------------------------------------------------------------------------------------ Zepp
def _state_msg(e):
    """Zustand und Meldung aus einer Ausnahme – ohne den Text der Ausnahme (könnte Zugangsdaten enthalten)."""
    if isinstance(e, RuntimeError) and "fehlen" in str(e):
        return "kein_zugang"
    return "fehler"


def _history(force=False):
    """(Zustand, Verlauf, API) – Verlauf höchstens alle TTL Sekunden neu; Fehler werden ERR_TTL Sekunden gemerkt."""
    u = ctx.uid() or ""
    now = time.monotonic()
    with _LOCK:
        c = _HIST.get(u)
        if c and not force and now - c["ts"] < TTL:
            return "ok", c["hist"], c["api"]
        e = _ERR.get(u)
        if e and not force and now - e[0] < ERR_TTL:
            return e[1], None, None
    try:
        api = sync._zepp_api()
        hist = api.history()
    except Exception as ex:  # noqa
        st = _state_msg(ex)
        with _LOCK:
            _HIST.pop(u, None)
            _ERR[u] = (now, st, MSG[st])
        return st, None, None
    with _LOCK:
        _ERR.pop(u, None)
        _HIST[u] = {"ts": now, "hist": hist, "api": api}
    return "ok", hist, api


def _choose(c, tid):
    """Aus den zugeordneten Trainings einer Tour das eindeutige wählen: (Training oder None, Zustand)."""
    if not c:
        return None, "kein_training"
    exact = [s for s in c if tid == f"z{s.get('trackid')}"]
    if len(exact) == 1:
        return exact[0], "ok"
    return (c[0], "ok") if len(c) == 1 else (None, "mehrdeutig")


def _pick(hist, t):
    tol = db.get_int("dup_tolerance_s", 300)
    return _choose(devquality.match_unique(hist or [], [t], tol).get(t["id"]) or [], t["id"])


def _tour(tid):
    return db.one("SELECT id,name,start_ts,dist_m,dur_s FROM tours WHERE id=?", (str(tid),))


def _device(tid):
    try:
        d = mydevices.device_of(tid)
    except Exception:  # noqa
        d = None
    return d


def eligible(tid):
    d = _device(tid)
    if d:
        return d["kind"] == "zepp"
    return mydevices.tour_kind(tid) == "zepp"


def fetch(tid, t):
    """Vom Zepp-Verlauf (und Detail) laden und als Zusatzdatei speichern. -> (Daten oder None, Zustand)."""
    st, hist, api = _history()
    if st != "ok":
        return None, st
    s, st = _pick(hist, t)
    if not s:
        return None, st
    old = load(tid)
    data = {"v": 1, "geladen": int(time.time()), "summary": {k: s[k] for k in KEEP if k in s}, "detail": False, "detail_offen": False, "kilo_pace": None}
    try:
        det = api.detail(s) or {}
        kp = det.get("kilo_pace")
        data["kilo_pace"] = kp if isinstance(kp, (str, list)) and len(json.dumps(kp)) <= MAX_RAW else None
        data["detail"] = True
    except Exception:  # noqa
        if old and old.get("detail"):                 # Detail schlug jetzt fehl, war aber schon da: die vorhandenen Kilometerwerte bleiben
            data["kilo_pace"], data["detail"] = old.get("kilo_pace"), True
        # sonst: Zusammenfassung bleibt nutzbar; „Von Zepp neu laden“ versucht das Detail erneut
    store(tid, data)
    return data, "ok"


def aufbereiten(tid, data):
    s = data["summary"]
    w = kennzahlen(s)
    freq = (w.get("frequenz") or {}).get("wert")
    z, sp, we = pulszonen(s), splits(s, data.get("kilo_pace"), freq), wetter(s)
    hin = []
    if "te" in w or "ate" in w:
        hin.append(HINT["te"])
    if "last" in w or "rpe" in w:
        hin.append(HINT["last"])
    if z:
        hin.append(HINT["zonen"])
    if sp:
        hin.append(HINT["splits"])
    if "aufstieg" in w or "abstieg" in w:
        hin.append(HINT["hoehe"])
    if we:
        hin.append(HINT["wetter"])
    if not data.get("detail"):
        hin.append(HINT["detail_offen"] if data.get("detail_offen") else HINT["detail"])
    d = _device(tid)
    return {"werte": w, "pulszonen": z, "splits": sp, "wetter": we, "hinweise": hin, "ermuedung": ermuedung_fuer(tid, s, sp),
            "device": {"id": d["id"], "name": d["name"], "kind": d["kind"], "model": d["model"], "photo": d.get("photo") or 0} if d else {"id": None, "name": "Amazfit/Zepp", "kind": "zepp", "model": ""}}


def antwort(tid, data, status, meldung=""):
    base = {"quelle": "zepp", "status": status, "meldung": meldung or MSG.get(status, ""), "device": None, "geladen": None, "werte": {}, "pulszonen": None, "splits": None,
            "wetter": None, "hinweise": [], "ermuedung": None}
    if data:
        base.update(aufbereiten(tid, data))
        base["geladen"] = data.get("geladen")
        if status == "ok" and not base["werte"] and not base["pulszonen"] and not base["splits"] and not base["wetter"]:
            base["status"] = "leer"                   # Training gefunden, aber die Uhr hat nichts Brauchbares geliefert
            base["meldung"] = "Die Uhr hat zu diesem Training keine auswertbaren Werte geliefert."
    return base


# ------------------------------------------------------------------------------------------------ Job: alle Touren
def load_all(api=None, dry=False, max_new=None):
    """Job „Uhr-Daten aller Touren laden“: den Zepp-Verlauf EINMAL laden und für alle zugeordneten Zepp-Touren, die noch keine Zusatzdatei haben, die Zusammenfassung
    speichern (mit store(), wie beim Öffnen einer Tour) – ohne Detail-Abrufe. Vorhandene Zusatzdateien bleiben unberührt (idempotent, auch solche mit Kilometerwerten).
    Obergrenze je Lauf: Einstellung uhr_alle_max (Standard 1000, 1–5000). Zugangsdaten und Fehlertexte aus Zepp werden nicht protokolliert."""
    from .jobs import log, progress
    cap = max(1, min(5000, db.get_int("uhr_alle_max", 1000))) if max_new is None else max_new
    if api is None:
        st, hist, _a = _history(force=True)
        if st != "ok":
            log("Uhr-Daten: " + MSG[st])
            return {"status": st, "neu": 0}
    else:
        hist = api.history()
    tours = db.query("SELECT id,name,start_ts,dist_m,dur_s FROM tours WHERE start_ts IS NOT NULL ORDER BY start_ts DESC")
    asg = mydevices.assignments()
    zt = []
    for t in tours:
        d = (asg.get(t["id"]) or (None, False))[0]
        if (d["kind"] if d else mydevices.tour_kind(t["id"])) == "zepp":
            zt.append(t)
    have = sum(1 for t in zt if load(t["id"]))
    todo = [t for t in zt if not load(t["id"])]
    log(f"Uhr-Daten: {len(hist or [])} Trainings im Zepp-Verlauf, {len(zt)} Touren mit Zepp-Uhr, {have} schon gespeichert, {len(todo)} offen")
    cand = devquality.match_unique(hist or [], todo, db.get_int("dup_tolerance_s", 300))
    neu = unklar = ohne = 0
    stopped = False
    for i, t in enumerate(todo, 1):
        if i % 25 == 0:
            progress(f"Uhr-Daten {i}/{len(todo)}")
        s, st = _choose(cand.get(t["id"]) or [], t["id"])
        if not s:
            if st == "mehrdeutig":
                unklar += 1
            else:
                ohne += 1
            continue
        if neu >= cap:
            stopped = True
            break
        if not dry:
            store(t["id"], {"v": 1, "geladen": int(time.time()), "summary": {k: s[k] for k in KEEP if k in s}, "detail": False, "detail_offen": True, "kilo_pace": None})
        neu += 1
    log(f"Uhr-Daten: {neu} Touren {'würden' if dry else 'wurden'} gespeichert, {ohne} ohne passendes Training, {unklar} mehrdeutig (nichts gespeichert)"
        + (f" – Obergrenze von {cap} je Lauf erreicht, den Job erneut starten" if stopped else ""))
    log("Kilometerwerte (Splits) kommen weiterhin beim ersten Öffnen der Tour.")
    return {"status": "ok", "neu": neu, "ohne_training": ohne, "mehrdeutig": unklar, "schon_da": have, "obergrenze": stopped}


@router.get("/api/tours/{tour_id}/uhr-training")
def api_get(tour_id: str, request: Request):
    """Training laut Uhr. Gespeicherte Werte kommen aus der Zusatzdatei; nur wenn es noch keine gibt, wird (einmal) bei Zepp nachgefragt.
    Betrachter lesen nur gespeicherte Werte."""
    t = _tour(tour_id)
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    if not eligible(t["id"]):
        return antwort(t["id"], None, "nicht_zepp")
    d = load(t["id"])
    u = getattr(request.state, "user", None)
    viewer = bool(u and u.get("role") == "viewer")
    if d and d.get("detail_offen") and not viewer and t["start_ts"]:     # vom Job gespeichert: Kilometerwerte jetzt (einmal) nachholen
        d2, _st = fetch(t["id"], t)
        d = d2 or d
    if d:
        return antwort(t["id"], d, "ok")
    if viewer:
        return antwort(t["id"], None, "nicht_geladen")
    if not t["start_ts"]:
        return antwort(t["id"], None, "kein_training")
    d, st = fetch(t["id"], t)
    return antwort(t["id"], d, st)


@router.post("/api/tours/{tour_id}/uhr-training/neu")
def api_reload(tour_id: str):
    """Von Zepp neu laden (Verlauf frisch, Detail erneut). Bei einem Fehler bleiben die bisherigen Werte erhalten."""
    t = _tour(tour_id)
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    if not eligible(t["id"]):
        return antwort(t["id"], None, "nicht_zepp")
    old = load(t["id"])
    st, hist, api = _history(force=True)
    if st != "ok":
        return antwort(t["id"], old, st)
    s, st = _pick(hist, t) if t["start_ts"] else (None, "kein_training")
    if not s:
        return antwort(t["id"], old, st)
    d, st = fetch(t["id"], t)
    return antwort(t["id"], d or old, st)
