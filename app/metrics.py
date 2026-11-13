"""Messwerte der Aufzeichnungsgeräte (Geschwindigkeit, Kadenz, Leistung, Temperatur, Atmung, Schrittlänge, Bodenkontakt …).

Je Tour gibt es eine Zusatzdatei tracks/<id>.met.json:
  {"v": 1, "src": "zepp|garmin|suunto|polar|phone|other", "device": "Anzeigename des Geräts laut Datei", "t0": <Start, Unix-s>,
   "t": [Sekunden seit Start …], "series": {"speed": [km/h oder null …], "cad": […], …}, "stat": {"cad": {"avg":…, "max":…, "min":…}},
   "sum": {"kcal":…, "te":…, "ate":…}}
Die Reihen sind auf höchstens 600 Stützstellen verdichtet und enthalten nur Kanäle, die das Gerät wirklich geliefert hat.
Was nicht gemessen wurde, fehlt – es wird nie etwas erfunden. Nur die Geschwindigkeit wird für Touren ohne Geräte-Kanal aus GPS und Zeit
berechnet und dann als „abgeleitet“ gekennzeichnet. Die Zusatzdatei ersetzt nie eine vorhandene mit Messreihen (außer ausdrücklich mit force).
"""
import json
import math
import re
import time
from statistics import median

from fastapi import APIRouter, HTTPException

from . import config, db, gpxtools, tracks
from .jobs import log

router = APIRouter()
MAXPTS = 600
FOOT = {"hike", "jogging", "mountaineering", "nordicwalking", "snowshoe"}

# Kanal -> (Beschriftung, Einheit, Nachkommastellen, kleinster gültiger Wert, größter gültiger Wert)
CH = {
    "speed": ("Geschwindigkeit", "km/h", 1, 0.0, 120.0),
    "cad": ("Kadenz", "1/min", 0, 0.5, 280.0),
    "pow": ("Leistung", "W", 0, 0.0, 3000.0),
    "temp": ("Temperatur", "°C", 1, -50.0, 60.0),
    "resp": ("Atemfrequenz", "1/min", 1, 3.0, 90.0),
    "stride": ("Schrittlänge", "m", 2, 0.2, 3.0),
    "gct": ("Bodenkontaktzeit", "ms", 0, 80.0, 1000.0),
    "vosc": ("Vertikale Oszillation", "mm", 1, 10.0, 200.0),
    "press": ("Luftdruck", "hPa", 0, 300.0, 1100.0),
}
ORDER = ["speed", "pace", "cad", "stride", "pow", "temp", "resp", "gct", "vosc", "press"]
SRC_LABEL = {"zepp": "Amazfit/Zepp", "garmin": "Garmin", "suunto": "Suunto", "polar": "Polar", "phone": "Handy", "other": "Anderes Gerät"}


def sidecar(tid):
    return config.TRACK_DIR / f"{tid}.met.json"


def label_for(key, sport):
    """(Beschriftung, Einheit) – die Kadenz heißt je nach Sportart Schrittfrequenz (spm) oder Trittfrequenz (U/min)."""
    if key == "cad":
        return ("Schrittfrequenz", "Schritte/min") if sport in FOOT else ("Trittfrequenz", "U/min")
    if key == "pace":
        return "Tempo (Pace)", "min/km"
    return CH[key][0], CH[key][1]


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def _ok(key, v):
    """Wert prüfen: Platzhalter (z. B. -20000), Unsinn und – wo 0 „nicht gemessen“ heißt – Nullen werden verworfen."""
    x = _num(v)
    if x is None:
        return None
    lo, hi = CH[key][3], CH[key][4]
    return x if lo <= x <= hi else None


# ---------------------------------------------------------------------------- Lesen aus GPX/TCX
_TAGS = {
    "cad": "cad", "cadence": "cad", "runcadence": "cad", "atemp": "temp", "temp": "temp", "temperature": "temp",
    "power": "pow", "watts": "pow", "speed": "speed", "resp": "resp", "respiration": "resp", "respirationrate": "resp",
    "gct": "gct", "groundcontacttime": "gct", "vosc": "vosc", "verticaloscillation": "vosc", "vo": "vosc",
    "stride": "stride", "steplength": "stride", "stridelength": "stride", "press": "press", "pressure": "press",
}
_TAG_RE = re.compile(r"<(?:[A-Za-z0-9_]+:)?([A-Za-z0-9_]+)(?:\s[^>]*)?>\s*([^<>\s][^<>]*?)\s*</")


def _channels(inner):
    out = {}
    for name, val in _TAG_RE.findall(inner):
        key = _TAGS.get(name.lower())
        if not key or key in out:
            continue
        x = _num(val)
        if x is None:
            continue
        if key == "speed":
            x *= 3.6                                  # GPX/TCX: m/s
        elif key == "stride" and x > 20:
            x /= 1000.0                               # Millimeter
        v = _ok(key, x)
        if v is not None:
            out[key] = v
    return out


def _ts(t):
    try:
        return gpxtools.parse_time(t).timestamp()
    except (ValueError, TypeError):
        return None


def kind_from_creator(creator):
    c = (creator or "").lower()
    for words, k in ((("garmin",), "garmin"), (("suunto",), "suunto"), (("polar",), "polar"), (("zepp", "amazfit", "huami", "mi fit"), "zepp"),
                     (("meine touren (android)",), "phone")):
        if any(w in c for w in words):
            return k
    return "other" if c else ""


def parse(text, filename=""):
    """GPX/TCX-Text -> dict(samples=[(unix_s, {kanal: wert})], src, device, sum). Defensiv: unlesbare Teile werden übersprungen."""
    samples = []
    low = filename.lower()
    is_tcx = low.endswith(".tcx") or ("<TrainingCenterDatabase" in text[:3000] and "<gpx" not in text[:3000])
    src = dev = ""
    sm = {}
    if is_tcx:
        m = re.search(r"<Creator\b[^>]*>.*?<Name>([^<]*)</Name>", text, flags=re.S)
        dev = (m.group(1).strip() if m else "")
        src = kind_from_creator(dev)
        for m in re.finditer(r"<Trackpoint>(.*?)</Trackpoint>", text, flags=re.S):
            b = m.group(1)
            t = re.search(r"<Time>([^<]*)</Time>", b)
            ts = _ts(t.group(1)) if t else None
            ch = _channels(b)
            if ts is not None and ch:
                samples.append((ts, ch))
    else:
        head = text[:4000]
        m = re.search(r"<gpx\b[^>]*\bcreator\s*=\s*[\"']([^\"']*)[\"']", head)
        creator = m.group(1) if m else ""
        m = re.search(r'<mt:device\s+src="([a-z]*)"[^>]*>([^<]*)</mt:device>', head)
        if m:
            src, dev = m.group(1), m.group(2).strip()
        else:
            src = "" if creator.lower().startswith("meine touren") and "android" not in creator.lower() else kind_from_creator(creator)
            dev = creator if src and src != "phone" else ""
            if src == "phone":
                dev = "Handy"
        m = re.search(r"<mt:sum\s+([^>]*)/>", head)
        if m:
            for k, v in re.findall(r'(\w+)="([^"]*)"', m.group(1)):
                x = _num(v)
                if k in ("kcal", "te", "ate") and x is not None:
                    sm[k] = x
        for m in re.finditer(r"<trkpt\b[^>]*>(.*?)</trkpt>", text, flags=re.S):
            inner = m.group(1)
            if "<" not in inner.replace("<ele>", "").replace("<time>", ""):
                continue
            t = re.search(r"<time>([^<]*)</time>", inner)
            ts = _ts(t.group(1)) if t else None
            ch = _channels(inner)
            if ts is not None and ch:
                samples.append((ts, ch))
    return {"samples": samples, "src": src, "device": dev, "sum": sm}


# ---------------------------------------------------------------------------- Zepp-Cloud
def _rows(raw):
    """Zepp-Spalte „Zeitabstand,Wert,…;…“ (leerer Zeitabstand = 1 s) -> [(Sekunden seit Start, [Werte als int/None])]."""
    out, t = [], 0
    for r in filter(None, (raw or "").split(";") if isinstance(raw, str) else []):
        c = r.split(",")
        try:
            t += int(c[0]) if c[0] != "" else 1
            out.append((t, [int(x) if x not in ("", None) else None for x in c[1:]]))
        except ValueError:
            continue
    return out


def _gps_speed(pts):
    """Mittleres Tempo (m/s) aus den Streckenpunkten (Median) – dient nur zur Plausibilitätsprüfung der Zepp-Spalten."""
    v = []
    for a, b in zip(pts, pts[1:]):
        dt = b[0] - a[0]
        if dt <= 0:
            continue
        d = math.hypot((b[2] - a[2]) * 111320 * math.cos(math.radians(a[1])), (b[1] - a[1]) * 110540)
        v.append(d / dt)
    v = [x for x in v if x > 0.3]
    return median(v) if v else None


def zepp_samples(summary, detail, pts):
    """Messwerte aus dem Zepp-Detail (nur Spalten, die zur GPS-Geschwindigkeit passen) -> (samples, summary-dict).
    Aufbau der Spalten ist nicht dokumentiert: jede Spalte wird auf Plausibilität geprüft, sonst verworfen."""
    t0 = int(summary["trackid"])
    ref = _gps_speed(pts) if pts else None
    ch = {}                                            # kanal -> [(ts, wert)]
    # Geschwindigkeit: Spalte „speed“, Einheit (m/s, dm/s, cm/s, mm/s) nur übernehmen, wenn sie zum GPS-Tempo passt
    rows = _rows(detail.get("speed"))
    vals = [(t, r[0]) for t, r in rows if r and r[0] is not None and r[0] > 0]
    if vals and ref:
        med = median(v for _, v in vals)
        for scale in (1.0, 0.1, 0.01, 0.001):
            if 0.6 <= med * scale / ref <= 1.6:
                ch["speed"] = [(t0 + t, v * scale * 3.6) for t, v in vals]
                break
    # Kadenz/Schrittlänge aus „gait“ (Spalten vorher unbekannt): Paar (Schrittlänge cm, Kadenz), das zur GPS-Geschwindigkeit passt
    g = _rows(detail.get("gait"))
    if g and ref:
        ncol = min(len(r) for _, r in g)
        cols = [[(t, r[i]) for t, r in g if r[i] is not None and r[i] > 0] for i in range(ncol)]
        meds = [median(v for _, v in c) if len(c) >= 5 else None for c in cols]
        best = None
        for i, mi in enumerate(meds):
            for j, mj in enumerate(meds):
                if i == j or mi is None or mj is None:
                    continue
                if 20 <= mi <= 250 and 40 <= mj <= 260:                 # Schrittlänge in cm, Schritte/min
                    err = abs(mi / 100.0 * mj / 60.0 - ref) / ref
                    if err <= 0.25 and (best is None or err < best[0]):
                        best = (err, i, j)
        if best:
            _, i, j = best
            ch["stride"] = [(t0 + t, v / 100.0) for t, v in cols[i]]
            ch["cad"] = [(t0 + t, float(v)) for t, v in cols[j]]
    for key in ("cadence",):                           # Rad: eigene Spalte „cadence“ (Umdrehungen/min)
        rows = _rows(detail.get(key))
        vals = [(t, r[0]) for t, r in rows if r and r[0] is not None and 0 < r[0] <= 250]
        if len(vals) >= 5 and "cad" not in ch:
            ch["cad"] = [(t0 + t, float(v)) for t, v in vals]
    merged = {}
    for k, lst in ch.items():
        for ts, v in lst:
            x = _ok(k, v)
            if x is not None:
                merged.setdefault(ts, {})[k] = x
    sm = {}
    kc = _num(summary.get("calorie"))
    if kc and 1 <= kc <= 30000:
        sm["kcal"] = int(kc)
    return sorted(merged.items()), sm


# ---------------------------------------------------------------------------- Verdichten und Speichern
def _stat(vals, key):
    v = [x for x in vals if x is not None]
    if not v:
        return None
    d = CH[key][2]
    st = {"avg": round(sum(v) / len(v), d + 1), "max": round(max(v), d + 1), "min": round(min(v), d + 1)}
    if key == "speed":
        mv = [x for x in v if x >= 1.0]                  # „in Bewegung“: ab 1 km/h
        if mv:
            st["avg_mov"] = round(sum(mv) / len(mv), 2)
    return st


def build(samples, t0, src, device="", summary=None):
    """samples: [(unix_s, {kanal: wert})] -> Zusatzdatei-Inhalt (dict). Kanäle ohne brauchbare Werte entfallen."""
    samples = sorted(samples, key=lambda s: s[0])
    raw = {}
    for ts, ch in samples:
        for k, v in ch.items():
            if k in CH:
                x = _ok(k, v)
                if x is not None:
                    raw.setdefault(k, []).append((ts - t0, x))
    for k in list(raw):                                  # zu wenig oder nur Nullen = nicht wirklich gemessen
        vals = [v for _, v in raw[k]]
        if len(vals) < 5 or (k in ("speed", "pow") and max(vals) <= 0):
            del raw[k]
    out = {"v": 1, "src": src or "other", "device": (device or "")[:80], "t0": int(t0), "t": [], "series": {}}
    if summary:
        out["sum"] = {k: v for k, v in summary.items() if k in ("kcal", "te", "ate") and _num(v) is not None}
    if not raw:
        return out
    offs = sorted({int(round(o)) for lst in raw.values() for o, _ in lst})
    dur = max(offs[-1], 1)
    n = min(MAXPTS, len(offs))
    w = dur / n
    out["stat"] = {k: _stat([v for _, v in lst], k) for k, lst in raw.items()}
    buckets = {}
    for k, lst in raw.items():
        for o, v in lst:
            b = min(n - 1, int(max(o, 0) // w)) if w else 0
            e = buckets.setdefault(b, {"o": [], "v": {}})
            e["o"].append(o)
            e["v"].setdefault(k, []).append(v)
    keys = sorted(buckets)
    out["t"] = [int(round(sum(buckets[b]["o"]) / len(buckets[b]["o"]))) for b in keys]
    for k in raw:
        d = CH[k][2] + 1
        out["series"][k] = [round(sum(buckets[b]["v"][k]) / len(buckets[b]["v"][k]), d) if k in buckets[b]["v"] else None for b in keys]
    return out


def load(tid):
    try:
        d = json.loads(sidecar(tid).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return d if isinstance(d, dict) else None


def has_series(d):
    return bool(d and d.get("series"))


def store(tid, data, force=False):
    """Zusatzdatei schreiben. Eine vorhandene Datei mit Messreihen bleibt unberührt (außer force). Gibt True zurück, wenn geschrieben wurde."""
    old = load(tid)
    if old and has_series(old) and not force:
        return False
    if old and not has_series(data) and not force and old.get("src") and old.get("src") != "other":
        return False                                     # nur-Kopfdaten ersetzen keine bekannten Kopfdaten
    config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
    p = sidecar(tid)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    tmp.replace(p)
    try:
        db.execute("INSERT OR REPLACE INTO tour_source(tour_id,src,name) VALUES(?,?,?)", (str(tid), data.get("src") or "", data.get("device") or ""))
    except Exception:  # noqa
        pass
    return True


def store_from_text(tid, text, filename="", t0=None, src=None, sport=None, force=False):
    """Aus GPX/TCX-Text (z. B. aus FIT umgewandelt) die Messwerte lesen und speichern. Gibt den Inhalt zurück (oder None bei Fehlern)."""
    try:
        r = parse(text, filename)
        if t0 is None:
            row = db.one("SELECT start_ts FROM tours WHERE id=?", (str(tid),))
            t0 = (row or {}).get("start_ts") if row else None
        if t0 is None and r["samples"]:
            t0 = int(r["samples"][0][0])
        if t0 is None:
            return None
        s = src or r["src"] or "other"
        data = build(r["samples"], t0, s, r["device"] or ("Handy" if s == "phone" else ""), r["sum"])
        store(tid, data, force)
        return data
    except Exception as e:  # noqa
        log(f"Messwerte {tid}: {e}")
        return None


def adopt_staged(tid, gpx_path):
    """Zepp-Export: die beim Abruf neben die GPX-Datei gelegte Messwert-Datei zur lokalen Tour übernehmen."""
    try:
        from pathlib import Path
        sp = Path(gpx_path).with_suffix(".met.json")
        if sp.exists():
            d = json.loads(sp.read_text(encoding="utf-8"))
            if isinstance(d, dict):
                row = db.one("SELECT start_ts FROM tours WHERE id=?", (str(tid),))
                if row and row["start_ts"] and d.get("t0") is not None and d.get("t"):
                    sh = int(d["t0"]) - int(row["start_ts"])           # Zeiten beziehen sich auf den Beginn der Tour (erster GPS-Punkt)
                    if sh:
                        d["t"] = [x + sh for x in d["t"]]
                        d["t0"] = int(row["start_ts"])
                store(tid, d)
    except Exception as e:  # noqa
        log(f"Messwerte {tid}: {e}")


def forget(tid):
    sidecar(tid).unlink(missing_ok=True)
    try:
        db.execute("DELETE FROM tour_source WHERE tour_id=?", (str(tid),))
        db.execute("DELETE FROM tour_device WHERE tour_id=?", (str(tid),))
    except Exception:  # noqa
        pass


def tours_with_metrics():
    ids = set()
    if config.TRACK_DIR.exists():
        for f in config.TRACK_DIR.glob("*.met.json"):
            try:
                if f.stat().st_size >= 40:
                    ids.add(f.name[:-9])
            except OSError:
                pass
    return ids


# ---------------------------------------------------------------------------- abgeleitet (GPS und Zeit)
def _hav(a, b):
    return math.hypot((b[1] - a[1]) * 111320 * math.cos(math.radians(a[0])), (b[0] - a[0]) * 110540)


def derived_speed(tid):
    """Geschwindigkeit aus Streckenpunkten und Zeit: (t, werte km/h, stat) oder None. Mindestens 15 s und 8 m Abstand je Messung."""
    pts = None
    try:
        from . import routes
        r = routes.load(tid)
        if r and len(r) > 5 and all(len(p) > 3 and p[3] is not None for p in r[:5]):
            pts = [(p[0], p[1], p[3] / 1000.0) for p in r]
    except Exception:  # noqa
        pts = None
    if not pts:
        f = tracks.gpx_file(tid)
        if f.exists():
            typ, raw = gpxtools._points_gpx_hr(f.read_text(encoding="utf-8", errors="ignore"))
            tt = [(la, lo, _ts(t)) for la, lo, el, t, hr in raw if not (la == 0 and lo == 0)]
            tt = [p for p in tt if p[2] is not None]
            if tt:
                pts = [(a, b, c - tt[0][2]) for a, b, c in tt]
    if not pts or len(pts) < 6:
        return None
    t, v = [], []
    i = 0
    while i < len(pts) - 1:
        j = i + 1
        while j < len(pts) - 1 and pts[j][2] - pts[i][2] < 15:
            j += 1
        dt = pts[j][2] - pts[i][2]
        if dt >= 5:
            d = sum(_hav(pts[k], pts[k + 1]) for k in range(i, j))
            sp = d / dt * 3.6
            if 0 <= sp <= 120:
                t.append((pts[i][2] + pts[j][2]) / 2)
                v.append(sp)
        i = j
    if len(v) < 5:
        return None
    return t, v


def _condense(t, v, n=MAXPTS):
    if len(t) <= n:
        return [int(round(x)) for x in t], v
    w = (t[-1] - t[0] or 1) / n
    b = {}
    for x, y in zip(t, v):
        b.setdefault(min(n - 1, int((x - t[0]) // w)), []).append((x, y))
    ks = sorted(b)
    return [int(round(sum(p[0] for p in b[k]) / len(b[k]))) for k in ks], [sum(p[1] for p in b[k]) / len(b[k]) for k in ks]


def _pace(speed):
    """min/km aus km/h; zu langsam (unter 2 km/h) = keine Angabe."""
    return [round(60.0 / s, 2) if s is not None and s >= 2.0 else None for s in speed]


def _chan(key, sport, series, stat, derived=False):
    lab, unit = label_for(key, sport)
    d = CH[key][2] if key in CH else 1
    return {"label": lab, "unit": unit, "dec": d, "series": series, "derived": derived, "inv": key == "pace", **(stat or {})}


def compute(tid):
    """Antwort von /api/tours/<id>/metrics (ohne Gerätezuordnung)."""
    t = db.one("SELECT sport, start_ts FROM tours WHERE id=?", (str(tid),))
    if not t:
        return None
    sport = t["sport"] or ""
    d = load(tid) or {}
    ser, tt = dict(d.get("series") or {}), list(d.get("t") or [])
    stat = d.get("stat") or {}
    chans = {}
    for k in ORDER:
        if k in ser and k in CH and len(ser[k]) == len(tt):
            chans[k] = _chan(k, sport, ser[k], stat.get(k))
    out = {"n": 0, "src": d.get("src") or "", "source": d.get("device") or "", "t": tt, "channels": chans, "sum": d.get("sum") or {}, "sport": sport}
    if "speed" not in chans:
        r = derived_speed(str(tid))
        if r:
            tx, vx = _condense(*r)
            c = _chan("speed", sport, [round(x, 2) for x in vx], _stat(vx, "speed"), True)
            if not tt:
                out["t"] = tt = tx
            elif tx != tt:
                c["t"] = tx                              # eigene Zeitachse (Geräte-Kanäle haben eine andere)
            chans["speed"] = c
    if "speed" in chans and sport in FOOT:
        sp = chans["speed"]
        ps = _pace(sp["series"])
        vv = [p for p in ps if p is not None]
        if len(vv) >= 5:
            c = _chan("pace", sport, ps, {"avg": round(60.0 / sp["avg_mov"], 2) if sp.get("avg_mov") else round(sum(vv) / len(vv), 2), "max": min(vv), "min": max(vv)}, True)
            if "t" in sp:
                c["t"] = sp["t"]
            chans["pace"] = c
    if sport in FOOT and "cad" in chans and "speed" in chans and "stride" not in chans and "t" not in chans["speed"]:
        cs, ss = chans["cad"]["series"], chans["speed"]["series"]
        sr = [round(s / 3.6 * 60.0 / c, 2) if s and c and c >= 40 and s >= 1.0 and 0.2 <= s / 3.6 * 60.0 / c <= 3.0 else None for s, c in zip(ss, cs)]
        vv = [x for x in sr if x is not None]
        if len(vv) >= 5:
            chans["stride"] = _chan("stride", sport, sr, {"avg": round(sum(vv) / len(vv), 2), "max": max(vv), "min": min(vv)}, True)
    out["channels"] = {k: chans[k] for k in ORDER if k in chans}
    out["n"] = len(out["t"])
    return out


@router.get("/api/tours/{tour_id}/metrics")
def api_metrics(tour_id: str):
    from . import mydevices
    m = compute(tour_id)
    if m is None:
        raise HTTPException(404, "Tour nicht gefunden")
    m["device"] = mydevices.device_of(tour_id)
    return m


# ---------------------------------------------------------------------------- Nachladen für den Bestand
def backfill(api=None):
    """Messwerte für vorhandene Touren nachladen: (1) Zepp-Cloud (passendes Training), (2) Original-Dateien im Eingang/Export.
    Idempotent; Touren mit vorhandenen Messreihen und fremde Zusatzdateien werden nicht angefasst."""
    from . import sync
    tours = db.query("SELECT id,start_ts,dist_m,dur_s,sport FROM tours WHERE start_ts IS NOT NULL")
    byid = {t["id"]: t for t in tours}
    tol = db.get_int("dup_tolerance_s", 300)
    n_z = n_f = 0
    try:
        if api is None and (db.get("zepp_token") or (db.get("zepp_email") and db.get("zepp_password"))):
            api = sync._zepp_api()
    except Exception as e:  # noqa
        log(f"Messwerte: Zepp nicht erreichbar ({e})")
        api = None
    if api is not None:
        from . import zepp
        todo = []
        for s in api.history():
            tr = int(s["trackid"])
            t = byid.get(f"z{tr}") or sync.is_duplicate(tr, float(s.get("dis") or 0), int(float(s.get("run_time") or 0)), tours, tol)
            if not t:
                continue
            o = load(t["id"])
            if o and (has_series(o) or o.get("checked") or o.get("src") in ("garmin", "suunto", "polar", "phone")):
                continue
            todo.append((s, t))
        log(f"Messwerte: {len(todo)} Touren mit passendem Zepp-Training ohne Messwerte")
        for i, (s, t) in enumerate(todo, 1):
            from . import jobs
            jobs.progress(f"Messwerte Zepp {i}/{len(todo)}")
            try:
                det = api.detail(s)
                pts = zepp.decode_points(s, det)
                samples, sm = zepp_samples(s, det, pts)
                d = build(samples, int(t["start_ts"]), "zepp", "Amazfit/Zepp", sm)
                d["checked"] = 1
                if store(t["id"], d, force=bool(o_meta_only(t["id"]))):
                    if has_series(d):
                        n_z += 1
                        log(f"  {t['id']}: {', '.join(d['series'])}")
            except Exception as e:  # noqa
                log(f"  {t['id']}: {e}")
            time.sleep(0.2)
    n_f = backfill_files(tours, tol)
    log(f"Messwerte: {n_z} Touren aus Zepp, {n_f} aus Dateien ergänzt")


def o_meta_only(tid):
    d = load(tid)
    return bool(d) and not has_series(d)


def backfill_files(tours, tol):
    """Original-Dateien (FIT/GPX/TCX, auch in ZIP) aus Eingang und Export lesen und zu passenden Touren ohne Messreihen zuordnen."""
    from . import fitfile, sync
    n = 0
    roots = [p for p in (config.INBOX_DIR, config.EXPORT_DIR) if p and p.exists()]
    todo = {t["id"] for t in tours if not has_series(load(t["id"]))}
    seen = 0
    for root in roots:
        for f in sorted(root.rglob("*")):
            if not f.is_file() or f.suffix.lower() not in (".fit", ".gpx", ".tcx", ".zip", ".gz") or f.stat().st_size > 200 * 1024 * 1024:
                continue
            if not todo:
                return n
            try:
                for name, text, kind in fitfile.iter_expand(str(f)):
                    if kind not in ("fit", "gpx") or not text:
                        continue
                    seen += 1
                    r = parse(text, name)
                    if not r["samples"]:
                        continue
                    c = gpxtools.convert(text, name, db.get("default_sport") or "hike")
                    cand = [t for t in tours if t["id"] in todo]
                    t = sync.is_duplicate(c["start_ts"], c["dist_m"], c["end_ts"] - c["start_ts"], cand, tol)
                    if not t:
                        continue
                    d = build(r["samples"], t["start_ts"], r["src"] or "other", r["device"], r["sum"])
                    if has_series(d) and store(t["id"], d, force=o_meta_only(t["id"])):
                        todo.discard(t["id"])
                        n += 1
                        log(f"  {t['id']}: {', '.join(d['series'])} (aus {name})")
            except Exception as e:  # noqa
                log(f"  {f.name}: {e}")
    return n
