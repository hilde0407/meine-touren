"""Diagnose „Was liefert meine Uhr?“ – zeigt, welche Felder eine Tour bzw. die Touren eines Geräts wirklich enthalten (nur lesend).

Je Tour gibt es höchstens fünf Quellen; jede nennt ALLE vorhandenen Felder, auch unbekannte und nicht ausgewertete:
* zepp_summary  Trainings-Zusammenfassung aus dem Zepp-Verlauf (zugeordnet wie mydevices.match_summaries / devquality.match_unique)
* zepp_detail   Zepp-Detail: Kanäle/Spalten mit Anzahl, Anteil gefüllt und Wertebereich (Rohwerte, so wie Zepp sie liefert)
* fit           FIT-Originaldatei aus Eingang/Export (falls noch vorhanden): Nachrichten- und Feldnummern, auch unbekannte
* gpx           Messwerte in der gespeicherten GPX-Spur (Erweiterungen je Punkt)
* sidecar       bereits ausgewertete Kanäle der Zusatzdatei tracks/<id>.met.json
Nichts wird gespeichert, verändert oder protokolliert; Zugangsdaten erscheinen nie in der Ausgabe.

Datenschutz: Koordinaten, Zeitstempel, Kennungen und Namen werden nie als Werte ausgegeben. Felder, die danach aussehen (Name oder sehr große Zahlen,
z. B. Halbkreis-/1e-8-Grad-Koordinaten), zeigen nur Anzahl, aber keinen Wertebereich. Textwerte werden nie ausgegeben. Der Sammel-Export enthält zusätzlich
keine Beispielwerte, keine Tournamen und keine Touren-IDs.
"""
import gzip
import io
import re
import time
import zipfile
from datetime import date
from statistics import median

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from . import config, db, devquality, fitfile, metrics, mydevices, tracks

router = APIRouter()

MAX_TOURS = 10                 # höchstens so viele (neueste) Touren je Gerät – und damit höchstens so viele Zepp-Detail-Abrufe
MAX_FIT_FILES = 300            # höchstens so viele FIT-Dateien je Anfrage im Eingang/Export durchsuchen
MAX_FIT_BYTES = 60 * 1024 ** 2 # größere FIT-Dateien (oder Archivmitglieder) werden übersprungen
FIT_SEARCH_S = 25.0            # höchstens so lange nach FIT-Originalen suchen
MAX_GPX_BYTES = 25 * 1024 ** 2
MAX_ROWS = 200_000             # Zeilen je Zepp-Spalte
CAP_VALS = 50_000
NO_VALUE = -2000000            # Zepp-Platzhalter „kein Wert“

SOURCES = [
    ("zepp_summary", "Zepp: Trainings-Zusammenfassung"),
    ("zepp_detail", "Zepp: Detaildaten (Kanäle)"),
    ("fit", "FIT-Originaldatei"),
    ("gpx", "GPX-Spur"),
    ("sidecar", "Messwert-Datei (ausgewertet)"),
]
SRC_LABEL = dict(SOURCES)

# ------------------------------------------------------------------------------------------------ Datenschutz
_SENS = re.compile(r"(?:^|[_.\[ ])(?:lat|lon|lng|latitude|longitude)(?:$|[_.\]\d])|coord|position|location|city|addr|geo|user|token|passw|secret|auth|nick|mail"
                   r"|serial|phone|imei|ssid|(?:^|[_.\[])(?:id|uid|mac|sn)(?:$|[_.\]])|name", re.I)
BIG = 1e7                      # Zahlen ab dieser Größe sind meist Koordinaten (Halbkreise, 1e-7/1e-8 Grad) oder Zeitstempel


def _hide_range(name, lo, hi):
    return bool(_SENS.search(name)) or (lo is not None and (abs(lo) >= BIG or abs(hi) >= BIG))


# ------------------------------------------------------------------------------------------------ Klartext
ZEPP_SUMMARY = {
    "trackid": ("Start des Trainings (Unix-Zeit) – zugleich Kennung", True),
    "source": ("Kennung der Uhr bzw. App, die das Training aufgezeichnet hat", True),
    "type": ("Nummer der Sportart", True),
    "dis": ("Strecke in Metern", True),
    "run_time": ("Dauer in Sekunden", True),
    "end_time": ("Ende des Trainings (Unix-Zeit)", True),
    "calorie": ("Kalorien (kcal)", True),
}
ZEPP_DETAIL = {
    "time": ("Zeitabstände zwischen den Streckenpunkten", True),
    "longitude_latitude": ("GPS-Position (Koordinaten werden hier nie angezeigt)", True),
    "altitude": ("Höhe in Zentimetern", True),
    "heart_rate": ("Puls: Zeitabstand, Pulsänderung", True),
    "gait": ("Schritt-Daten (Schrittlänge, Kadenz) – wird nur übernommen, wenn es zur GPS-Geschwindigkeit passt", True),
    "speed": ("Geschwindigkeit – wird nur übernommen, wenn die Einheit zur GPS-Geschwindigkeit passt", True),
    "cadence": ("Trittfrequenz (Rad)", True),
}
# Nur nach dem Namen geraten: wird mit „vermutlich“ gekennzeichnet
_GUESS = [
    (r"vo2", "VO2max (geschätzte maximale Sauerstoffaufnahme)"),
    (r"recover", "Erholungszeit"),
    (r"(?:^|_)(?:training_?)?load|(?:^|_)tl(?:$|_)", "Trainingsbelastung"),
    (r"training_?effect|(?:^|_)a?te(?:$|_)", "Trainingseffekt"),
    (r"calor|kcal", "Kalorien"),
    (r"stride|step_?len", "Schrittlänge"),
    (r"ground|gct|contact", "Bodenkontaktzeit"),
    (r"vertical|vosc|oscill", "Vertikale Oszillation"),
    (r"resp|breath", "Atemfrequenz"),
    (r"stress", "Belastung/Stress"),
    (r"heart|(?:^|_)hr(?:$|_)", "Puls"),
    (r"pace", "Tempo (Minuten je km)"),
    (r"cadence|freq", "Kadenz/Schrittfrequenz"),
    (r"altitude|ascend|descend|elev", "Höhe bzw. Höhenmeter"),
    (r"speed", "Geschwindigkeit"),
    (r"power|watt", "Leistung"),
    (r"temp", "Temperatur"),
    (r"swim|stroke|swolf", "Schwimmen"),
]


def _guess(name):
    n = name.lower()
    for pat, txt in _GUESS:
        if re.search(pat, n):
            return "vermutlich: " + txt
    return ""


# FIT: Nachricht -> Name
FIT_MSG = {0: "file_id", 2: "device_settings", 3: "user_profile", 7: "zones_target", 8: "hr_zone", 12: "sport", 18: "session", 19: "lap", 20: "record",
           21: "event", 23: "device_info", 26: "workout", 27: "workout_step", 34: "activity", 35: "software", 49: "file_creator", 55: "monitoring",
           78: "hrv", 101: "length", 103: "monitoring_info", 132: "hr", 216: "time_in_zone"}
# (Nachricht, Feld) -> (Name, Klartext, Skalierung, Einheit); nur sicher bekannte Felder
FIT_F = {
    (20, 0): ("position_lat", "GPS-Position (Breite)", 1, ""), (20, 1): ("position_long", "GPS-Position (Länge)", 1, ""),
    (20, 2): ("altitude", "Höhe", 5, "m"), (20, 78): ("enhanced_altitude", "Höhe (genau)", 5, "m"),
    (20, 3): ("heart_rate", "Puls", 1, "bpm"), (20, 4): ("cadence", "Kadenz", 1, "1/min"), (20, 53): ("fractional_cadence", "Kadenz (Bruchteil)", 128, ""),
    (20, 5): ("distance", "Strecke seit Start", 100, "m"), (20, 6): ("speed", "Geschwindigkeit", 1000, "m/s"),
    (20, 73): ("enhanced_speed", "Geschwindigkeit (genau)", 1000, "m/s"), (20, 7): ("power", "Leistung", 1, "W"),
    (20, 13): ("temperature", "Temperatur", 1, "°C"), (20, 39): ("vertical_oscillation", "Vertikale Oszillation", 10, "mm"),
    (20, 41): ("stance_time", "Bodenkontaktzeit", 10, "ms"), (20, 85): ("step_length", "Schrittlänge", 10, "mm"),
    (20, 91): ("absolute_pressure", "Luftdruck", 1, "Pa"), (20, 99): ("respiration_rate", "Atemfrequenz", 1, "1/min"),
    (20, 108): ("enhanced_respiration_rate", "Atemfrequenz (genau)", 100, "1/min"), (20, 253): ("timestamp", "Zeitstempel", 1, ""),
    (18, 2): ("start_time", "Start der Sitzung", 1, ""), (18, 5): ("sport", "Sportart", 1, ""), (18, 6): ("sub_sport", "Unter-Sportart", 1, ""),
    (18, 7): ("total_elapsed_time", "Gesamtzeit", 1000, "s"), (18, 8): ("total_timer_time", "Zeit in Bewegung", 1000, "s"),
    (18, 9): ("total_distance", "Gesamtstrecke", 100, "m"), (18, 11): ("total_calories", "Kalorien", 1, "kcal"),
    (18, 14): ("avg_speed", "Ø Geschwindigkeit", 1000, "m/s"), (18, 15): ("max_speed", "Höchstgeschwindigkeit", 1000, "m/s"),
    (18, 16): ("avg_heart_rate", "Ø Puls", 1, "bpm"), (18, 17): ("max_heart_rate", "Höchster Puls", 1, "bpm"),
    (18, 22): ("total_ascent", "Aufstieg", 1, "m"), (18, 23): ("total_descent", "Abstieg", 1, "m"),
    (18, 24): ("total_training_effect", "Trainingseffekt (aerob)", 10, ""), (18, 137): ("total_anaerobic_training_effect", "Trainingseffekt (anaerob)", 10, ""),
    (0, 1): ("manufacturer", "Hersteller-Nummer", 1, ""), (0, 2): ("product", "Produkt-Nummer", 1, ""), (0, 8): ("product_name", "Produktname", 1, ""),
    (0, 3): ("serial_number", "Seriennummer", 1, ""), (0, 4): ("time_created", "Erstellt am", 1, ""),
    (23, 2): ("manufacturer", "Hersteller-Nummer", 1, ""), (23, 4): ("product", "Produkt-Nummer", 1, ""), (23, 27): ("product_name", "Produktname", 1, ""),
    (23, 3): ("serial_number", "Seriennummer", 1, ""), (12, 0): ("sport", "Sportart", 1, ""), (12, 1): ("sub_sport", "Unter-Sportart", 1, ""),
}
FIT_PRIVATE_MSG = {3, 30, 51}   # user_profile (Gewicht, Größe, Alter …), weight_scale, blood_pressure: nie Werte, nur Anzahl
# von fitfile.py heute ausgewertet (siehe _use/_extra/_summary)
FIT_USED = {(20, f) for f in (0, 1, 2, 3, 4, 6, 7, 13, 39, 41, 53, 73, 78, 85, 91, 99, 108, 253)} | {(18, f) for f in (5, 6, 11, 24, 137)} \
    | {(0, f) for f in (1, 2, 8)} | {(23, f) for f in (0, 2, 4, 27)} | {(12, 0), (12, 1)}
# Offset der Höhe (Meter = roh/5 − 500)
_OFFSET = {(20, 2): 500, (20, 78): 500}


# ------------------------------------------------------------------------------------------------ Kennzahlen
def _r(x):
    return None if x is None else round(float(x), 3)


def _nums(vals):
    v = [x for x in vals if x is not None]
    if not v:
        return None, None, None
    return min(v), median(v), max(v)


def _field(source, name, n, typ, vals=None, share=None, used=False, text="", unit="", sample=None, extra=None, sens=None, private=False):
    """Ein Feld in Einheitsform. n = vorhandene (nicht leere) Werte; Zahlenwerte `vals` liefern Bereich und Beispiel. Bereich und Beispiel entfallen bei
    Koordinaten-/Kennungs-ähnlichen Feldern (hidden)."""
    lo, md, hi = _nums(vals) if vals else (None, None, None)
    sn = name if sens is None else sens                  # Namensprüfung (bei FIT nur am Feldnamen, nicht am Nachrichtennamen)
    hidden = lo is not None and (private or _hide_range(sn, lo, hi))
    if hidden or (lo is None and _SENS.search(sn)):
        lo = md = hi = sample = None
        hidden = True
    f = {"source": source, "name": name, "n": int(n), "type": typ, "min": _r(lo), "median": _r(md), "max": _r(hi), "share": None if share is None else round(share, 3),
         "used": bool(used), "text": text, "unit": unit, "hidden": hidden, "sample": _r(sample) if sample is not None and not hidden else None}
    if extra:
        f.update(extra)
    return f


def _num(s):
    try:
        x = float(s)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


# ------------------------------------------------------------------------------------------------ Zepp
def _zepp_text(table, name):
    t = table.get(name)
    if t:
        return t[0], t[1]
    return _guess(name), False


def _analyze(source, table, name, v, depth=0):
    """Einen Wert aus Zepp-Zusammenfassung/-Detail in Felder umsetzen. Unbekannte Strukturen werden nie verschwiegen (mindestens eine Zeile)."""
    text, used = _zepp_text(table, name)
    if v is None or v == "":
        return [_field(source, name, 0, "leer", used=used, text=text)]
    if isinstance(v, bool):
        return [_field(source, name, 1, "Wahrheitswert", used=used, text=text)]
    if isinstance(v, (int, float)):
        return [_field(source, name, 1, "Zahl", [float(v)], 1.0, used, text, sample=float(v))]
    if isinstance(v, dict):
        out = [_field(source, name, len(v), "Objekt", used=used, text=text)]
        if depth < 1:
            for k, x in v.items():
                out += _analyze(source, table, f"{name}.{k}", x, depth + 1)
        return out
    if isinstance(v, (list, tuple)):
        nums = [float(x) for x in v if isinstance(x, (int, float)) and not isinstance(x, bool)]
        if nums and len(nums) == len(v):
            return [_field(source, name, len(v), "Zahlenliste", nums[:CAP_VALS], 1.0, used, text)]
        return [_field(source, name, len(v), "Liste", used=used, text=text)]
    s = str(v)
    if ";" not in s and "," not in s:
        x = _num(s)
        if x is not None:
            return [_field(source, name, 1, "Zahl", [x], 1.0, used, text, sample=x)]
        return [_field(source, name, 1, "Text", used=used, text=text)]
    rows = [r.split(",") for r in s.split(";") if r != ""][:MAX_ROWS]
    if not rows:
        return [_field(source, name, 0, "leer", used=used, text=text)]
    ncol = max(len(r) for r in rows)
    out = []
    for i in range(ncol):
        vals, txt = [], 0
        for r in rows:
            c = r[i].strip() if i < len(r) else ""
            if c == "":
                continue
            x = _num(c)
            if x is None:
                txt += 1
            elif x != NO_VALUE:
                vals.append(x)
        filled = len(vals) + txt
        nm = name if ncol == 1 else f"{name}[{i}]"
        out.append(_field(source, nm, filled, "Zahl" if vals and len(vals) >= txt else ("Text" if txt else "leer"), vals[:CAP_VALS] or None,
                          filled / len(rows), used, text, "roh" if vals else "", extra={"rows": len(rows)}))
    return out


def _zepp_state_for_error(e):
    msg = str(e)
    for k in ("zepp_token", "zepp_password", "zepp_email"):
        v = db.get(k)
        if v:
            msg = msg.replace(str(v), "…")
    return msg[:200]


class _Zepp:
    """Zepp-Zugang für EINE Anfrage: Verlauf höchstens einmal, Details einzeln und gezählt."""

    def __init__(self):
        self.state, self.msg, self.hist, self.api, self.details = None, "", None, None, 0

    def load(self):
        if self.state is not None:
            return self.state
        from . import sync, zepp
        import requests
        try:
            self.api = sync._zepp_api()
        except RuntimeError as e:
            self.state, self.msg = ("kein_zugang", "") if "fehlen" in str(e) else ("fehler", _zepp_state_for_error(e))
            return self.state
        except Exception as e:  # noqa
            self.state, self.msg = "fehler", _zepp_state_for_error(e)
            return self.state
        try:
            self.hist = self.api.history()
            self.state = "ok"
        except (zepp.ZeppError, requests.RequestException, RuntimeError) as e:
            self.state, self.msg = "fehler", _zepp_state_for_error(e)
        except Exception as e:  # noqa
            self.state, self.msg = "fehler", type(e).__name__
        return self.state

    def match(self, t):
        tol = db.get_int("dup_tolerance_s", 300)
        c = devquality.match_unique(self.hist or [], [t], tol).get(t["id"]) or []
        if not c:
            return None, 0
        c.sort(key=lambda s: abs(int(s["trackid"]) - (t["start_ts"] or 0)))
        return c[0], len(c)

    def detail(self, s):
        self.details += 1
        return self.api.detail(s)


# ------------------------------------------------------------------------------------------------ FIT-Originale
def _fit_members(path, depth=0):
    """FIT-Bytes aus einer Datei (.fit, .gz, .zip – auch verschachtelt, höchstens 2 Ebenen); Fehler werden übersprungen."""
    low = path.name.lower()
    try:
        if low.endswith(".fit"):
            if path.stat().st_size <= MAX_FIT_BYTES:
                yield path.read_bytes()
        elif low.endswith(".gz"):
            with gzip.open(path, "rb") as g:
                raw = g.read(MAX_FIT_BYTES + 1)
            if len(raw) <= MAX_FIT_BYTES and fitfile.is_fit(raw):
                yield raw
        elif low.endswith(".zip"):
            yield from _zip_members(zipfile.ZipFile(path), depth)
    except (OSError, zipfile.BadZipFile, EOFError, ValueError):
        return


def _zip_members(z, depth):
    with z:
        for zi in z.infolist():
            if zi.is_dir() or zi.file_size > MAX_FIT_BYTES:
                continue
            n = zi.filename.lower()
            try:
                if n.endswith(".fit"):
                    yield z.read(zi)
                elif n.endswith(".zip") and depth < 1:
                    yield from _zip_members(zipfile.ZipFile(io.BytesIO(z.read(zi))), depth + 1)
                elif n.endswith(".gz"):
                    raw = gzip.decompress(z.read(zi))
                    if len(raw) <= MAX_FIT_BYTES and fitfile.is_fit(raw):
                        yield raw
            except (OSError, zipfile.BadZipFile, EOFError, ValueError):
                continue


def locate_fits(tours):
    """FIT-Originale im Eingang und Export suchen und den Touren (Start ±Toleranz) zuordnen: {tour_id: scan}, dazu {"scanned", "truncated"}.
    Die Suche ist begrenzt (Dateianzahl, Größe, Zeit) und bricht ab, sobald alle Touren gefunden sind."""
    tol = max(db.get_int("dup_tolerance_s", 300), 300)
    want = {t["id"]: t["start_ts"] for t in tours if t.get("start_ts")}
    found, st = {}, {"scanned": 0, "truncated": False}
    if not want:
        return found, st
    t_end = time.monotonic() + FIT_SEARCH_S
    roots = [p for p in (config.INBOX_DIR, config.EXPORT_DIR) if p and p.exists()]
    for root in roots:
        try:
            files = sorted(f for f in root.rglob("*") if f.is_file() and f.suffix.lower() in (".fit", ".gz", ".zip"))
        except OSError:
            continue
        for f in files:
            for raw in _fit_members(f):
                if not fitfile.is_fit(raw):
                    continue
                if st["scanned"] >= MAX_FIT_FILES or time.monotonic() > t_end:
                    st["truncated"] = True
                    return found, st
                st["scanned"] += 1
                sc = fitfile.scan(raw)
                for tid, s0 in want.items():
                    if tid in found:
                        continue
                    if any(abs(s - s0) <= tol for s in sc["starts"]):
                        found[tid] = sc
                if len(found) == len(want):
                    return found, st
    return found, st


def _fit_fields(sc):
    out = []
    for (g, f), e in sorted(sc["fields"].items()):
        msg = FIT_MSG.get(g, f"nachricht_{g}")
        k = FIT_F.get((g, f))
        name = f"{msg}.{k[0]}" if k else f"{msg}.feld_{f}"
        scale, unit = (k[2], k[3]) if k else (1, "")
        off = _OFFSET.get((g, f), 0)
        vals = [v / scale - off for v in e["vals"]] if e["vals"] else None
        typ = "Zahl" if e["vals"] and len(e["vals"]) >= e["text"] else ("Text" if e["text"] else "leer")
        txt = k[1] if k else f"unbekanntes Feld – wird nicht ausgewertet (Nachricht {g}, Feld {f})"
        out.append(_field("fit", name, e["n"], typ, vals, None, (g, f) in FIT_USED, txt, unit, sample=vals[0] if vals else None,
                          extra={"msg": g, "num": f, "known": bool(k)}, sens=name.split(".", 1)[1], private=g in FIT_PRIVATE_MSG))
        if not k and out[-1]["min"] is not None:
            out[-1]["unit"] = "roh"
    return out


# ------------------------------------------------------------------------------------------------ GPX und Zusatzdatei
def _gpx_fields(tid):
    p = tracks.gpx_file(tid)
    try:
        if not p.is_file() or p.stat().st_size > MAX_GPX_BYTES:
            return None
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    vals, cnt, npts = {}, {}, 0
    for m in re.finditer(r"<trkpt\b[^>]*>(.*?)</trkpt>", text, flags=re.S):
        npts += 1
        seen = set()
        for name, val in metrics._TAG_RE.findall(m.group(1)):
            k = name.lower()
            if k in ("ele", "time", "name", "desc", "sym", "type") or k in seen:
                continue
            seen.add(k)
            cnt[k] = cnt.get(k, 0) + 1
            x = _num(val)
            if x is not None and len(vals.setdefault(k, [])) < CAP_VALS:
                vals[k].append(x)
    out = []
    for k in sorted(cnt):
        used = k in metrics._TAGS or k in ("hr", "heartrate")
        out.append(_field("gpx", k, cnt[k], "Zahl" if vals.get(k) else "Text", vals.get(k), cnt[k] / npts if npts else None, used,
                          "wird aus der Spur gelesen" if used else "unbekannte Erweiterung der Spur – wird nicht ausgewertet",
                          extra={"points": npts}))
    return out, npts


def _sidecar_fields(tid):
    d = metrics.load(tid)
    if not d:
        return None
    out = []
    ts = d.get("t") or []
    for k, ser in (d.get("series") or {}).items():
        if not isinstance(ser, list):
            continue
        v = [float(x) for x in ser if isinstance(x, (int, float)) and not isinstance(x, bool)]
        lab, unit = (metrics.CH[k][0], metrics.CH[k][1]) if k in metrics.CH else (k, "")
        out.append(_field("sidecar", k, len(v), "Messreihe", v, len(v) / len(ser) if ser else None, True, lab, unit, extra={"points": len(ts)}))
    for k, x in (d.get("sum") or {}).items():
        lab = {"kcal": ("Kalorien", "kcal"), "te": ("Trainingseffekt (aerob)", ""), "ate": ("Trainingseffekt (anaerob)", "")}.get(k, (k, ""))
        n = _num(x)
        out.append(_field("sidecar", f"sum.{k}", 1 if n is not None else 0, "Zahl", [n] if n is not None else None, 1.0, True, lab[0], lab[1], sample=n))
    return out


# ------------------------------------------------------------------------------------------------ Bericht je Tour
HINT = {
    "kein_zugang": "Es ist kein Zepp-Zugang eingerichtet (Einstellungen → Zepp). Ohne Zugang können die Zepp-Felder nicht gelesen werden.",
    "fehler": "Zepp ist nicht erreichbar oder die Zugangsdaten stimmen nicht",
    "kein_training": "Zu dieser Tour wurde im Zepp-Verlauf kein passendes Training gefunden (Start, Dauer und Strecke passen zu keinem).",
    "nicht_zutreffend": "Diese Quelle gibt es nur bei Zepp-Uhren.",
    "keine_datei": "Nicht vorhanden.",
    "keine_touren": "Diesem Gerät sind noch keine Touren zugeordnet.",
}


def _src(key, state, fields=None, hint="", **kw):
    return dict({"key": key, "label": SRC_LABEL[key], "state": state, "hint": hint, "fields": fields or []}, **kw)


def _tour_row(tid):
    return db.one("SELECT id,name,start_ts,dist_m,dur_s FROM tours WHERE id=?", (str(tid),))


def _one(t, zc, fits, zepp_ok):
    """Alle Quellen EINER Tour (t: Zeile aus tours). zc: _Zepp; fits: {tour_id: scan}; zepp_ok: Zepp überhaupt sinnvoll (Gerät/Quelle ist Zepp)."""
    src = []
    if not zepp_ok:
        src += [_src("zepp_summary", "nicht_zutreffend", hint=HINT["nicht_zutreffend"]), _src("zepp_detail", "nicht_zutreffend", hint=HINT["nicht_zutreffend"])]
    else:
        st = zc.load()
        if st != "ok":
            h = HINT[st] + (f": {zc.msg}" if st == "fehler" and zc.msg else "")
            src += [_src("zepp_summary", st, hint=h), _src("zepp_detail", st, hint=h)]
        else:
            s, ncand = zc.match(t) if t.get("start_ts") else (None, 0)
            if not s:
                src += [_src("zepp_summary", "kein_training", hint=HINT["kein_training"]), _src("zepp_detail", "kein_training", hint=HINT["kein_training"])]
            else:
                fl = []
                for k, v in s.items():
                    fl += _analyze("zepp_summary", ZEPP_SUMMARY, str(k), v)
                src.append(_src("zepp_summary", "ok", fl, candidates=ncand))
                try:
                    det = zc.detail(s)
                    fd = []
                    for k, v in (det or {}).items():
                        fd += _analyze("zepp_detail", ZEPP_DETAIL, str(k), v)
                    src.append(_src("zepp_detail", "ok", fd))
                except Exception as e:  # noqa
                    src.append(_src("zepp_detail", "fehler", hint=HINT["fehler"] + f": {_zepp_state_for_error(e)}"))
    sc = fits.get(t["id"])
    if sc:
        src.append(_src("fit", "ok", _fit_fields(sc), bad=bool(sc["bad"])))
    else:
        src.append(_src("fit", "keine_datei", hint="Keine FIT-Originaldatei zu dieser Tour gefunden (gesucht wird in Eingang und Export). "
                        "Beim Import wird die FIT-Datei in eine GPX-Spur umgewandelt – ihre Messwerte stehen unter „GPX-Spur“."))
    g = _gpx_fields(t["id"])
    src.append(_src("gpx", "ok", g[0], points=g[1]) if g and g[1] else _src("gpx", "keine_datei", hint="Zu dieser Tour ist keine GPX-Spur gespeichert (zum Beispiel Komoot-Touren ohne Datei)."))
    sf = _sidecar_fields(t["id"])
    src.append(_src("sidecar", "ok", sf) if sf is not None else _src("sidecar", "keine_datei", hint="Noch keine Messwert-Datei (Verwaltung → „Messwerte nachladen“)."))
    return src


def _is_zepp(tid):
    return mydevices.tour_kind(tid) in ("zepp", "")


def report_tour(tid):
    t = _tour_row(tid)
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    fits, st = locate_fits([t])
    src = _one(t, _Zepp(), fits, _is_zepp(t["id"]))
    for s in src:
        s["tours_checked"] = 1 if s["state"] == "ok" else 0
        for f in s["fields"]:
            f["n_tours"] = 1 if f["n"] > 0 else 0
    return {"scope": "tour", "tour": {"id": t["id"], "name": t["name"], "start": mydevices._day(t["start_ts"])}, "sources": src,
            "fit_scanned": st["scanned"], "fit_truncated": st["truncated"]}


def report_device(did):
    d = db.one("SELECT * FROM devices WHERE id=?", (did,))
    if not d:
        raise HTTPException(404, "Gerät nicht gefunden")
    mine = {tid for tid, (dv, _m) in mydevices.assignments().items() if dv and dv["id"] == did}
    rows = [t for t in db.query("SELECT id,name,start_ts,dist_m,dur_s FROM tours ORDER BY start_ts DESC") if t["id"] in mine]
    tours = rows[:MAX_TOURS]
    zepp_ok = d["kind"] == "zepp"
    out = {"scope": "device", "device": {"id": d["id"], "name": d["name"], "kind": d["kind"], "model": d["model"] or "", "zsrc": d.get("zsrc") or ""},
           "tours_total": len(rows), "tours_checked": len(tours), "limit": MAX_TOURS}
    if not tours:
        out["sources"] = [_src(k, "keine_touren", hint=HINT["keine_touren"], tours_checked=0) for k, _l in SOURCES]
        out["fit_scanned"], out["fit_truncated"] = 0, False
        return out
    fits, st = locate_fits(tours)
    zc = _Zepp()
    per = [_one(t, zc, fits, zepp_ok) for t in tours]
    srcs = []
    for key, _lab in SOURCES:
        parts = [p for one in per for p in one if p["key"] == key]
        ok = [p for p in parts if p["state"] == "ok"]
        if not ok:
            states = [p["state"] for p in parts]
            s0 = max(set(states), key=states.count)
            hint = next((p["hint"] for p in parts if p["state"] == s0), "")
            srcs.append(_src(key, s0, hint=hint, tours_checked=0))
            continue
        agg = {}
        for p in ok:
            for f in p["fields"]:
                a = agg.setdefault(f["name"], dict(f, n=0, n_tours=0, _med=[], _lo=[], _hi=[], _sh=[], hidden=False, sample=None))
                a["n"] += f["n"]
                a["n_tours"] += 1 if f["n"] > 0 else 0
                a["hidden"] = a["hidden"] or f["hidden"]
                if f["min"] is not None:
                    a["_lo"].append(f["min"]); a["_hi"].append(f["max"]); a["_med"].append(f["median"])
                if f["share"] is not None:
                    a["_sh"].append(f["share"])
                if f["type"] != "leer":
                    a["type"] = f["type"]
        fl = []
        for a in agg.values():
            lo, hi, md = a.pop("_lo"), a.pop("_hi"), a.pop("_med")
            sh = a.pop("_sh")
            a["min"], a["max"] = (min(lo), max(hi)) if lo and not a["hidden"] else (None, None)
            a["median"] = _r(median(md)) if md and not a["hidden"] else None
            a["share"] = round(sum(sh) / len(sh), 3) if sh else None
            fl.append(a)
        srcs.append(_src(key, "ok", fl, tours_checked=len(ok), bad=any(p.get("bad") for p in ok)))
    out["sources"] = srcs
    out["fit_scanned"], out["fit_truncated"] = st["scanned"], st["truncated"]
    out["zepp_details"] = zc.details
    return out


def export_payload(rep):
    """Datensparsame Fassung für die Weitergabe: nur Feldnamen, Zähler, Anteile und Wertebereiche. Keine Touren-IDs/-Namen, keine Beispielwerte, keine Texte."""
    d = rep["device"]
    keep = ("name", "msg", "num", "known", "n", "n_tours", "type", "min", "median", "max", "share", "used", "unit", "hidden", "text")
    z = d.get("zsrc") or ""
    return {"format": "meine-touren-uhr-felder", "version": 1, "erstellt": date.today().isoformat(),
            "geraet": {"art": d["kind"], "modell": d["model"][:60], "zepp_kennung": z if re.fullmatch(r"[A-Za-z0-9_.\-]{1,60}", z) else ""},
            "touren_gesamt": rep["tours_total"], "touren_geprueft": rep["tours_checked"],
            "quellen": [{"quelle": s["key"], "zustand": s["state"], "touren_mit_daten": s.get("tours_checked", 0),
                         "felder": [{k: f[k] for k in keep if k in f} for f in s["fields"]]} for s in rep["sources"]]}


@router.get("/api/tours/{tour_id}/uhr-felder")
def api_tour_fields(tour_id: str):
    """Alle Felder dieser Tour je Quelle (Zepp-Zusammenfassung, Zepp-Detail, FIT, GPX, Messwert-Datei). Nur lesend."""
    return report_tour(tour_id)


@router.get("/api/devices/{did}/uhr-felder")
def api_device_fields(did: int):
    """Felder über höchstens die 10 neuesten Touren des Geräts: je Feld, in wie vielen dieser Touren es vorkommt. Nur lesend."""
    return report_device(did)


@router.get("/api/devices/{did}/uhr-felder.json")
def api_device_fields_json(did: int, download: int = 0):
    """Dieselbe Auswertung als datensparsame JSON-Datei (download=1 → als Datei speichern)."""
    body = export_payload(report_device(did))
    r = JSONResponse(body)
    if download:
        r.headers["Content-Disposition"] = f'attachment; filename="uhr-felder-{did}.json"'
    return r
