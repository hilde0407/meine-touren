"""Eigene Kennzahl (3.28.0): ein Baustein, den der Benutzer ohne Programmieren selbst zusammenstellt (Dialog „Eigene Kennzahl“).

Die Definition ist nur eine Auswahl aus festen Listen (Messgröße, Rechenart, Filter, optional eine Formel A ÷ B aus zwei solchen Auswahlen) – es gibt keinen Freitext-Ausdruck,
kein eval und kein SQL vom Benutzer; Schlagwörter gehen ausschließlich als gebundener Parameter in die Abfrage. Sie steht als Baustein vom Typ „eigenkz“ im Layout-Dokument
(app/layout.py; deshalb gelten Ansichten, Vorlagen, Export und „Standard wiederherstellen“ ohne Sonderweg). Der Server prüft die Definition beim Speichern (clean_cfg) und beim Auswerten
(POST /api/bausteine/eigen) mit denselben Regeln.

Konfiguration (cfg), alle Felder streng geprüft, unbekannte Schlüssel sind ein Fehler:
  title   Name, 1–60 Zeichen (ohne Steuer- und Spitzklammern)       symbol  Emoji/Zeichen, höchstens 8 Zeichen (optional)
  mess    touren | km | hm | abstieg | dauer | gehzeit | puls | pulsmax | tempo | steigung | hmkm
  agg     sum | avg | max | min | count | record | monat   (nicht jede Messgröße erlaubt jede Rechenart, siehe MESS)
  durch   {mess, agg}   optional: Formel A ÷ B (A = mess/agg, B = durch); op: div (A ÷ B, Standard) | pct (A in Prozent von B)
  sports  [Sportart]   range year | y | 12m | 90d | all | c   yr (bei y)   from, to (bei c, JJJJ-MM-TT)   tag (Schlagwort)   minkm (Mindeststrecke 0–1000)
  vgl     true = Vergleich mit dem Zeitraum davor (±%)           ziel  Zielwert (> 0, höchstens 10 000 000) → Fortschrittsbalken
  vglart  davor (Standard) | jahr (gleicher Zeitraum ein Jahr früher) | monat (Zeitraum einen Monat früher); nur zusammen mit vgl   (3.35.0)
  plan    true = Ziel mit linearem Soll vergleichen („im Plan?“; nur zusammen mit ziel; gilt bei laufendem/bestimmtem Jahr und eigenem Bereich, Summe/Anzahl ohne Formel)   (3.35.0)
  spark   saeulen (Standard, wie vor 3.35.0) | linie (Sparkline) | aus   (3.35.0)       touren  true = Antippen öffnet die zugehörigen Touren (3.35.0; nur Anzeige, der Server rechnet nichts anderes)
Messgrößen: gehzeit = Bewegungszeit ohne Pausen (3.29.0, aus dem Zwischenspeicher cache/tempo/<id>.json von app/steigung.py: Touren ab 2 km mit Höhe und Zeit), puls = Durchschnittspuls einer Tour und
pulsmax = Höchstpuls einer Tour (3.29.0, aus der Pulsdatei <id>.hr.json bzw. dem GPX, Zwischenspeicher in app/puls.py; nur Touren mit Pulsdaten; Summe ergibt hier keinen Sinn, deshalb nur
avg/max/min/count/record). Die Gehzeit wird bei noch nicht berechneten Touren höchstens GEHZEIT_BUDGET_S Sekunden je Aufruf nachgerechnet, der Rest steht in der Antwort als „offen“.
Messgrößen: tempo = Strecke ÷ Dauer je Tour (km/h), steigung = Aufstieg ÷ Strecke (%), hmkm = Aufstieg je km. Bei diesen „Verhältnissen“ ist avg gewichtet (Summe ÷ Summe),
max/min/record zählen nur Touren mit sinnvoller Länge (Tempo: ab 3 km und 30 Min., sonst ab 1 km); Touren ohne die nötigen Angaben zählen nicht.
Antwort: {wert, einheit: {z, n}, n (Touren im Zeitraum), offen (nur wenn > 0: Touren, deren Gehzeit noch nicht berechnet ist), von, bis, vorher: {wert, pct, von, bis}|None, reihe: {art, werte}, rekord: {id, name, datum, wert}|None, ziel: {ziel, pct, (soll, soll_pct, plan: voraus|im_plan|zurueck)}|None}.
3.35.0: vorher enthält zusätzlich art, diff (absolute Differenz) und dir (auf | ab | gleich, unter ±0,5 % gleich); reihe.art ist woche (Zeitraum bis 98 Tage, höchstens 15 Werte), monat (bis 36 Monate) oder jahr (höchstens 12), bei spark = aus entfällt reihe.
"""
import calendar
import json
import re
import time
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

from . import bausteine_daten as bd
from . import db, gpxtools, puls, steigung
from .gpxtools import TZ

router = APIRouter()
TYPE = "eigenkz"
MAX_PRO_NUTZER = 24                      # eigene Bausteine je Benutzer (über alle Seiten und Ansichten)
MAX_TITLE = 60
MAX_SYMBOL = 8
MAX_TAG = 40
MAX_ZIEL = 10_000_000
GEHZEIT_BUDGET_S = 5.0                   # so lange rechnet ein Aufruf höchstens an Touren, deren Gehzeit noch nicht im Zwischenspeicher steht
RANGES = ("year", "y", "12m", "90d", "all", "c")
KEYS = {"title", "symbol", "mess", "agg", "durch", "op", "sports", "range", "yr", "from", "to", "tag", "minkm", "vgl", "ziel", "eigen", "vglart", "plan", "spark", "touren"}
OPS = ("div", "pct")
VGLARTEN = ("davor", "jahr", "monat")
SPARKS = ("saeulen", "linie", "aus")
# Messgröße: Einheit, ob es ein Verhältnis ist (Summe ÷ Summe), erlaubte Rechenarten, Mindestlänge/-dauer für max/min/record
MESS = {
    "touren": {"unit": "touren", "ratio": False, "aggs": ("sum", "count", "monat")},
    "km": {"unit": "km", "ratio": False, "aggs": ("sum", "avg", "max", "min", "count", "record", "monat")},
    "hm": {"unit": "m", "ratio": False, "aggs": ("sum", "avg", "max", "min", "count", "record", "monat")},
    "abstieg": {"unit": "m", "ratio": False, "aggs": ("sum", "avg", "max", "min", "count", "record", "monat")},
    "dauer": {"unit": "h", "ratio": False, "aggs": ("sum", "avg", "max", "min", "count", "record", "monat")},
    "gehzeit": {"unit": "h", "ratio": False, "aggs": ("sum", "avg", "max", "min", "count", "record", "monat")},
    "puls": {"unit": "bpm", "ratio": False, "aggs": ("avg", "max", "min", "count", "record")},
    "pulsmax": {"unit": "bpm", "ratio": False, "aggs": ("avg", "max", "min", "count", "record")},
    "tempo": {"unit": "kmh", "ratio": True, "aggs": ("avg", "max", "min", "count", "record"), "min_km": 3.0, "min_h": 0.5},
    "steigung": {"unit": "pct", "ratio": True, "aggs": ("avg", "max", "min", "count", "record"), "min_km": 1.0, "min_h": 0.0},
    "hmkm": {"unit": "m_km", "ratio": True, "aggs": ("avg", "max", "min", "count", "record"), "min_km": 1.0, "min_h": 0.0},
}
AGGS = ("sum", "avg", "max", "min", "count", "record", "monat")
FORMEL_AGGS = ("sum", "avg", "max", "min", "count")          # in einer Formel: weder Bestwert (hat eine Tour dabei) noch „pro Monat“
SPORT_RE = re.compile(r"^[A-Za-z0-9_]{1,40}$")
BAD_TEXT = re.compile(r"[\x00-\x1f\x7f<>]")


def _bad(msg):
    return HTTPException(400, msg)


def _text(x, name, lo, hi):
    if not isinstance(x, str) or BAD_TEXT.search(x) or not lo <= len(x.strip()) <= hi:
        raise _bad(f"„{name}“ muss {lo} bis {hi} Zeichen lang sein (ohne Steuer- und Spitzklammern)" if lo else f"„{name}“ darf höchstens {hi} Zeichen lang sein (ohne Steuer- und Spitzklammern)")
    return " ".join(x.split())


def _zahl(x, name, lo, hi, offen=False):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or x != x or (x <= lo if offen else x < lo) or x > hi:
        raise _bad(f"Ungültiger Wert für „{name}“")
    return x


def _datum(x, name):
    try:
        d = date.fromisoformat(x) if isinstance(x, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", x) else None
    except ValueError:
        d = None
    if not d or not 1970 <= d.year <= 2100:
        raise _bad(f"Ungültiges Datum für „{name}“ (JJJJ-MM-TT)")
    return d


def _operand(x, name, aggs):
    if not isinstance(x, dict) or set(x) - {"mess", "agg"}:
        raise _bad(f"Ungültige Angabe „{name}“")
    m, a = x.get("mess"), x.get("agg")
    if m not in MESS:
        raise _bad(f"Unbekannte Messgröße in „{name}“")
    if a not in aggs or a not in MESS[m]["aggs"]:
        raise _bad(f"Diese Rechenart gibt es für diese Messgröße nicht („{name}“)")
    return {"mess": m, "agg": a}


def clean_cfg(v):
    """Prüft die Definition einer eigenen Kennzahl; gibt die bereinigte Fassung zurück (HTTPException 400 bei Fehlern)."""
    if not isinstance(v, dict) or set(v) - KEYS:
        raise _bad("Ungültige Einstellung einer eigenen Kennzahl")
    out = {"title": _text(v.get("title"), "Name", 1, MAX_TITLE)}
    if v.get("symbol") not in (None, ""):
        out["symbol"] = _text(v["symbol"], "Symbol", 1, MAX_SYMBOL)
    out.update(_operand({"mess": v.get("mess"), "agg": v.get("agg")}, "Messgröße", AGGS))
    if "durch" in v:
        out["durch"] = _operand(v["durch"], "durch", FORMEL_AGGS)
        if out["agg"] not in FORMEL_AGGS:
            raise _bad("In einer Formel sind Bestwert und „pro Monat“ nicht möglich")
        op = v.get("op", "div")
        if op not in OPS:
            raise _bad("Unbekannte Rechenart der Formel")
        out["op"] = op
    elif "op" in v:
        raise _bad("„op“ gehört nur zu einer Formel")
    if "sports" in v:
        s = v["sports"]
        from .stat_gruppen import FILTER_RE                                # 3.59.0: auch eine Statistik-Gruppe „sgrp:<id>“
        if not isinstance(s, list) or len(s) > 20 or not all(isinstance(i, str) and FILTER_RE.match(i) for i in s):
            raise _bad("Ungültige Sportart")
        if s:
            out["sports"] = list(dict.fromkeys(s))
    r = v.get("range", "year")
    if r not in RANGES:
        raise _bad("Unbekannter Zeitraum")
    out["range"] = r
    if r == "y":
        yr = v.get("yr")
        if isinstance(yr, bool) or not isinstance(yr, int) or not 1970 <= yr <= 2100:
            raise _bad("Ungültiges Jahr")
        out["yr"] = yr
    elif "yr" in v:
        raise _bad("„yr“ gehört nur zu einem bestimmten Jahr")
    if r == "c":
        a, b = _datum(v.get("from"), "von"), _datum(v.get("to"), "bis")
        if a > b:
            raise _bad("„von“ darf nicht nach „bis“ liegen")
        out["from"], out["to"] = a.isoformat(), b.isoformat()
    elif "from" in v or "to" in v:
        raise _bad("„from“ und „to“ gehören nur zu einem eigenen Bereich")
    if v.get("tag") not in (None, ""):
        out["tag"] = _text(v["tag"], "Schlagwort", 1, MAX_TAG)
    if v.get("minkm") not in (None, 0):
        out["minkm"] = _zahl(v["minkm"], "Mindeststrecke", 0, 1000)
    if "vgl" in v:
        if not isinstance(v["vgl"], bool):
            raise _bad("Ungültiger Wert für „vgl“")
        if v["vgl"]:
            out["vgl"] = True
    if "vglart" in v:                                      # 3.35.0
        if v["vglart"] not in VGLARTEN:
            raise _bad("Unbekannte Art des Vergleichs")
        if not out.get("vgl"):
            raise _bad("„vglart“ gehört nur zu einem Vergleich")
        if v["vglart"] != "davor":
            out["vglart"] = v["vglart"]
    if v.get("ziel") not in (None, 0):
        out["ziel"] = _zahl(v["ziel"], "Ziel", 0, MAX_ZIEL, offen=True)
    if "plan" in v:
        if not isinstance(v["plan"], bool):
            raise _bad("Ungültiger Wert für „plan“")
        if v["plan"]:
            if "ziel" not in out:
                raise _bad("„plan“ gehört nur zu einem Ziel")
            out["plan"] = True
    if "spark" in v:
        if v["spark"] not in SPARKS:
            raise _bad("Unbekannte Darstellung des Verlaufs")
        if v["spark"] != "saeulen":
            out["spark"] = v["spark"]
    if "touren" in v:
        if not isinstance(v["touren"], bool):
            raise _bad("Ungültiger Wert für „touren“")
        if v["touren"]:
            out["touren"] = True
    if "eigen" in v:                                       # 3.34.0: true = eigener Zeitraum (der Zeitraum der Seite gilt hier nicht)
        if not isinstance(v["eigen"], bool):
            raise _bad("Ungültiger Wert für „eigen“")
        if v["eigen"]:
            out["eigen"] = True
    return out


def zaehle(doc):
    """Eigene Bausteine in einem Layout-Dokument (altes Format oder Behälter mit Ansichten) als Menge {(Kennung, Definition)}; gleiche Kopien in mehreren Ansichten zählen einmal."""
    if not isinstance(doc, dict):
        return set()
    lays = [x.get("layout") for x in doc["views"] if isinstance(x, dict)] if isinstance(doc.get("views"), list) else [doc]
    out = set()
    for lay in lays:
        for w in (lay or {}).get("widgets", []) if isinstance(lay, dict) else []:
            if isinstance(w, dict) and w.get("type") == TYPE:
                out.add((w.get("id"), json.dumps(w.get("cfg"), sort_keys=True)))
    return out


# ------------------------------------------------------------------------------------------------ Rechnen
def _rows(cfg):
    sql = "SELECT t.id,t.name,t.sport,t.start_ts,t.dist_m,t.dur_s,t.up_m,t.down_m FROM tours t WHERE t.start_ts IS NOT NULL"
    par = []
    if cfg.get("tag"):
        sql += " AND EXISTS (SELECT 1 FROM tour_tags x WHERE x.id=t.id AND x.tag=? COLLATE NOCASE)"
        par.append(cfg["tag"])
    from . import stat_gruppen
    sports, minkm, rows = stat_gruppen.plain(cfg.get("sports") or []), cfg.get("minkm") or 0, []      # 3.59.0: Gruppen aufgelöst; gelöschte Gruppe = alle
    for r in db.query(sql, tuple(par)):
        r["sport"] = gpxtools.norm(r["sport"])[0]                      # 3.60.0: entfernte Aktivitäten zählen als ihre Rückfall-Aktivität
        if sports and r["sport"] not in {gpxtools.norm(x)[0] for x in sports}:
            continue
        if minkm and (r["dist_m"] or 0) < minkm * 1000:
            continue
        r["d"] = datetime.fromtimestamp(r["start_ts"], tz=TZ).date()
        rows.append(r)
    return rows


def _num(r, mess):
    """Wert der Messgröße einer Tour oder None, wenn die Angabe fehlt. Verhältnisse: (Zähler, Nenner, Faktor) mit eigenem Aufruf _ratio."""
    if mess == "touren":
        return 1.0
    if mess == "km":
        return None if r["dist_m"] is None else r["dist_m"] / 1000
    if mess == "hm":
        return r["up_m"]
    if mess == "abstieg":
        return r["down_m"]
    if mess == "dauer":
        return r["dur_s"] / 3600 if (r["dur_s"] or 0) > 0 else None
    if mess == "gehzeit":
        return r.get("_gz")                                                 # von _prep gesetzt (None = keine Angabe oder noch nicht berechnet)
    if mess == "puls":
        return r.get("_pa")
    if mess == "pulsmax":
        return r.get("_pm")
    return None


def _prep(cfg, rows):
    """Holt Gehzeit und Puls nur für die Touren, die die Auswertung braucht, und nur wenn die Kennzahl sie verwendet (alles aus Zwischenspeichern, nie alle Tracks bei jedem Aufruf)."""
    used = {cfg["mess"], (cfg.get("durch") or {}).get("mess")}
    if used & {"puls", "pulsmax"}:
        ids = puls.tours_with_hr()
        for r in rows:
            c = puls._hist(r["id"]) if r["id"] in ids else None
            if c and c[1] and c[3]:                                       # c = (Änderungszeit, Sekunden je Pulswert, Durchschnitt, Maximum)
                r["_pa"], r["_pm"] = float(c[2]), float(c[3])
    if "gehzeit" in used:
        end = time.monotonic() + GEHZEIT_BUDGET_S
        for r in rows:
            t = steigung.tempo_of(r["id"], allow_compute=time.monotonic() < end)
            if t is None:
                r["_off"] = True
            elif t.get("status") == "ok" and (t.get("zeit_s") or 0) > 0:
                r["_gz"] = t["zeit_s"] / 3600


def _ratio(r, mess):
    """(Zähler, Nenner, Faktor) einer Tour für ein Verhältnis oder None."""
    km, h, up = (r["dist_m"] or 0) / 1000, (r["dur_s"] or 0) / 3600, r["up_m"]
    if mess == "tempo":
        return (km, h, 1.0) if km > 0 and h > 0 else None
    if mess == "steigung":
        return (up, km, 0.1) if up is not None and km > 0 else None           # Aufstieg ÷ (km·1000) · 100 = (hm ÷ km) / 10
    if mess == "hmkm":
        return (up, km, 1.0) if up is not None and km > 0 else None
    return None


def _monate_zahl(von, bis):
    return max(1, (bis.year - von.year) * 12 + bis.month - von.month + 1)


def _pick(pairs, agg):
    """Kleinster (min) oder größter Wert; bei Gleichstand die früheste Tour."""
    sign = 1 if agg == "min" else -1
    return min(pairs, key=lambda x: (sign * x[1], x[0]["start_ts"], x[0]["id"]))


def _einzel(rows, mess, agg, monate):
    """(Wert oder None, Tour oder None) einer Messgröße mit Rechenart über `rows`."""
    M = MESS[mess]
    if M["ratio"]:
        pr = [(r, _ratio(r, mess)) for r in rows]
        pr = [(r, p) for r, p in pr if p]
        if agg == "count":
            return float(len(pr)), None
        if agg == "avg":
            den = sum(p[1] for _r, p in pr)
            return (sum(p[0] for _r, p in pr) / den * pr[0][1][2] if pr and den > 0 else None), None
        good = [(r, p[0] / p[1] * p[2]) for r, p in pr if (r["dist_m"] or 0) / 1000 >= M["min_km"] and (r["dur_s"] or 0) / 3600 >= M["min_h"]]
        if not good:
            return None, None
        pick = _pick(good, agg)
        return pick[1], pick[0] if agg == "record" else None
    vs = [(r, _num(r, mess)) for r in rows]
    vs = [(r, v) for r, v in vs if v is not None]
    if agg == "count":
        return float(len(vs)), None
    if agg == "sum":
        return float(sum(v for _r, v in vs)), None
    if agg == "monat":
        return float(sum(v for _r, v in vs)) / monate, None
    if not vs:
        return None, None
    if agg == "avg":
        return sum(v for _r, v in vs) / len(vs), None
    pick = _pick(vs, agg)
    return pick[1], pick[0] if agg == "record" else None


def _wert(rows, cfg, monate):
    """(Wert, Tour) der ganzen Kennzahl; mit Formel A ÷ B bzw. A in % von B."""
    a, tour = _einzel(rows, cfg["mess"], cfg["agg"], monate)
    if "durch" not in cfg:
        return a, tour
    b, _ = _einzel(rows, cfg["durch"]["mess"], cfg["durch"]["agg"], monate)
    if a is None or not b:
        return None, None
    return (a / b * 100 if cfg.get("op") == "pct" else a / b), None


def einheit(cfg):
    """{z, n}: Einheit als Zähler und Nenner (Codes: touren, km, m, h, kmh, pct, m_km, monat); beide None = reine Zahl."""
    def one(mess, agg):
        return "touren" if agg == "count" else MESS[mess]["unit"]
    z = one(cfg["mess"], cfg["agg"])
    if "durch" not in cfg:
        return {"z": z, "n": "monat" if cfg["agg"] == "monat" else None}
    if cfg.get("op") == "pct":
        return {"z": "pct", "n": None}
    n = one(cfg["durch"]["mess"], cfg["durch"]["agg"])
    return {"z": None, "n": None} if z == n else {"z": z, "n": n}


def _zeitraum(cfg, heute):
    r = cfg.get("range", "year")
    if r == "c":
        a, b = date.fromisoformat(cfg["from"]), date.fromisoformat(cfg["to"])
        n = (b - a).days + 1
        return a, b, (a - timedelta(days=n), a - timedelta(days=1))
    von, bis, vor = bd.zeitraum(r, cfg.get("yr") or heute.year, heute)
    return von, bis, vor


def _runde(x):
    return None if x is None else round(x, 4)


WOCHEN_TAGE = 98                         # bis zu dieser Länge des Zeitraums zeigt der Verlauf Wochen (höchstens 15 Werte)


def _reihe(rows, cfg, von, bis):
    """Verlauf für das Mini-Diagramm: je Woche (Zeitraum bis 98 Tage), je Monat (bis 36 Monate), sonst je Jahr (höchstens die letzten 12). Immer begrenzt und deterministisch."""
    first = von or (min(r["d"] for r in rows) if rows else bis)
    n_mon = _monate_zahl(first, bis)
    if cfg["agg"] != "monat" and (bis - first).days + 1 <= WOCHEN_TAGE:
        mo = first - timedelta(days=first.weekday())
        keys = [mo + timedelta(days=7 * i) for i in range((bis - mo).days // 7 + 1)]
        kf = lambda d: d - timedelta(days=d.weekday())  # noqa: E731
        art, mon = "woche", lambda k: 1
    elif n_mon <= 36:
        keys, kf = [], lambda d: (d.year, d.month)  # noqa: E731
        y, m = first.year, first.month
        while (y, m) <= (bis.year, bis.month):
            keys.append((y, m))
            y, m = (y + 1, 1) if m == 12 else (y, m + 1)
        art, mon = "monat", lambda k: 1
    else:
        keys, kf = list(range(first.year, bis.year + 1))[-12:], lambda d: d.year  # noqa: E731
        art, mon = "jahr", lambda k: _monate_zahl(max(first, date(k, 1, 1)), min(bis, date(k, 12, 31)))
    gr = {k: [] for k in keys}
    for r in rows:
        k = kf(r["d"])
        if k in gr:
            gr[k].append(r)
    werte = [_runde(_wert(gr[k], cfg, mon(k))[0]) if gr[k] or cfg["agg"] in ("sum", "count", "monat") else None for k in keys]
    labels = [k.isoformat() if art == "woche" else f"{k[0]:04d}-{k[1]:02d}" if art == "monat" else str(k) for k in keys]
    return {"art": art, "labels": labels, "werte": werte}


def _versch(d, jahre=0, monate=0):
    """Datum um Jahre und Monate früher (Monatsende wird angepasst, 29.02. -> 28.02.)."""
    y, m = divmod(d.year * 12 + d.month - 1 - jahre * 12 - monate, 12)
    return date(y, m + 1, min(d.day, calendar.monthrange(y, m + 1)[1]))


def _soll_anteil(cfg, heute):
    """Anteil des Zielzeitraums, der bis heute vergangen ist (0 < x <= 1), oder None, wenn ein lineares Soll nicht sinnvoll ist (laufende Fenster, gesamte Zeit, Formeln, Höchst-/Mittelwerte)."""
    if cfg.get("durch") or cfg["agg"] not in ("sum", "count"):
        return None
    r = cfg.get("range", "year")
    if r == "year" or (r == "y" and cfg.get("yr") == heute.year):
        a, b = date(heute.year, 1, 1), date(heute.year, 12, 31)
    elif r == "y":
        return 1.0 if cfg["yr"] < heute.year else None
    elif r == "c":
        a, b = date.fromisoformat(cfg["from"]), date.fromisoformat(cfg["to"])
    else:
        return None
    if heute < a:
        return None
    return min(1.0, ((heute - a).days + 1) / ((b - a).days + 1))


def auswerten(cfg, heute=None):
    """Auswertung einer geprüften Definition (clean_cfg) für den angemeldeten Benutzer (seine Datenbank)."""
    heute = heute or datetime.now(TZ).date()
    cfg = clean_cfg(cfg)
    von, bis, vor = _zeitraum(cfg, heute)
    art = cfg.get("vglart", "davor")
    if cfg.get("vgl") and von and art != "davor":                                  # 3.35.0: gleicher Zeitraum ein Jahr bzw. einen Monat früher
        vor = (_versch(von, jahre=1 if art == "jahr" else 0, monate=1 if art == "monat" else 0), _versch(bis, jahre=1 if art == "jahr" else 0, monate=1 if art == "monat" else 0))
    rows = _rows(cfg)
    inn = [r for r in rows if (not von or r["d"] >= von) and r["d"] <= bis]
    vr = [r for r in rows if vor and vor[0] <= r["d"] <= vor[1]] if cfg.get("vgl") else []
    _prep(cfg, inn + vr)
    first = von or (min((r["d"] for r in inn), default=bis))
    wert, tour = _wert(inn, cfg, _monate_zahl(first, bis))
    out = {"wert": _runde(wert), "einheit": einheit(cfg), "n": len(inn), "von": von.isoformat() if von else None, "bis": bis.isoformat(),
           "vorher": None, "reihe": None if cfg.get("spark") == "aus" else _reihe(inn, cfg, von, bis), "rekord": None, "ziel": None}
    if tour is not None:
        out["rekord"] = {"id": tour["id"], "name": tour["name"] or "", "datum": tour["d"].isoformat(), "wert": _runde(wert)}
    off = sum(1 for r in inn if r.get("_off"))
    if off:
        out["offen"] = off
    if cfg.get("vgl") and vor:
        w2, _ = _wert(vr, cfg, _monate_zahl(vor[0], vor[1]))
        pct = round((wert - w2) / w2 * 100, 1) if wert is not None and w2 else None
        diff = _runde(wert - w2) if wert is not None and w2 is not None else None
        ref = pct if pct is not None else diff
        out["vorher"] = {"wert": _runde(w2), "pct": pct, "von": vor[0].isoformat(), "bis": vor[1].isoformat(), "n": len(vr), "art": art, "diff": diff,
                         "dir": None if ref is None else "gleich" if (abs(pct) < 0.5 if pct is not None else diff == 0) else "auf" if ref > 0 else "ab"}
    if cfg.get("ziel"):
        out["ziel"] = {"ziel": cfg["ziel"], "pct": round(wert / cfg["ziel"] * 100, 1) if wert is not None else 0.0}
        fr = _soll_anteil(cfg, heute) if cfg.get("plan") else None
        if fr:
            soll, w = cfg["ziel"] * fr, wert or 0.0
            out["ziel"].update({"soll": _runde(soll), "soll_pct": round(fr * 100, 1), "plan": "voraus" if w > soll * 1.05 else "im_plan" if w >= soll * 0.95 else "zurueck"})
    return out


MAX_BODY = 4000


@router.post("/api/bausteine/eigen")
async def api_eigen(request: Request):
    """Wertet die Definition einer eigenen Kennzahl aus (nur lesend; Betrachter dürfen das nicht, weil sie keine eigenen Bausteine haben und die Sperre für POST allgemein gilt)."""
    raw = await request.body()
    if len(raw) > MAX_BODY:
        raise HTTPException(413, "Die Einstellung ist zu groß")
    try:
        body = json.loads(raw or b"null")
    except ValueError:
        raise HTTPException(400, "Kein gültiges JSON")
    if isinstance(body, dict) and set(body) == {"cfg"}:
        body = body["cfg"]
    return await run_in_threadpool(auswerten, body)               # die Gehzeit kann einige Sekunden rechnen: nicht den Server blockieren
