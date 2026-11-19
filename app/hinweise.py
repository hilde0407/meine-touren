"""Hinweis-Bausteine (3.23.0): „Alarm-Bausteine“, die nur erscheinen, wenn etwas los ist.

GET /api/bausteine/hinweise  – alle Hinweise in EINEM Aufruf (nur lesend, je Benutzer: die Datenbank, die Ziele, die Sicherungen und der Zwischenspeicher gehören dem
angemeldeten Benutzer; Betrachter dürfen lesen). Gerechnet wird nur aus vorhandenen Daten (Touren, Ziele, Geräte-Qualität, Belastung laut Uhr, Sicherungsordner).
Die Oberfläche (58-bausteine-hinweise.js) baut aus den Zahlen die Texte (vier Sprachen) – hier stehen nur Art, Schweregrad und Werte.

Parameter (alle optional; ungültige Werte: 400):
  arten                 kommagetrennt: ziel, meilenstein, auffaellig, pause, rekord, woche, erholung, sicherung (Standard: alle)
  sport                 kommagetrennt, Sportarten (leer = alle); gilt für ziel (welche Ziele), meilenstein, pause, rekord und woche
  ziel_schwelle         1–90 (Prozent, Standard 10): Prognose liegt um MEHR als so viel unter dem Ziel
  meilenstein_tage      1–365 (Standard 7)         auffaellig_min  1–1000 (Standard 1)
  pause_tage            1–365 (Standard 14)        rekord_tage     1–365 (Standard 7)
  woche_ziel            0–100000 (0 = kein Ziel)   woche_einheit   km | touren (Standard km)
  erholung_stufe        mehr | deutlich_mehr (Standard deutlich_mehr)
  sicherung_tage        1–365 (Standard 7)
Antwort: {"stand", "heute", "hinweise": [{"art", "stufe": "info"|"hinweis"|"warnung", "daten": {…}}], "geprueft": [Arten]} – NUR aktive Hinweise stehen in „hinweise“
(nichts los = leere Liste). Die Reihenfolge ist fest (wie oben). „tage“ in Fenstern („letzte N Tage“) zählt heute mit: heute und die N Tage davor.

Regeln im Einzelnen:
  ziel        Ziele (Tabelle „goals“, wie „Ziele“ der Statistik) des laufenden Jahres. Prognose zum Jahresende = Stand ÷ Anteil des vergangenen Jahres, erst ab dem 14. Tag des Jahres
              (wie der Baustein „Jahresziel“). Aktiv, wenn das Ziel noch nicht erreicht ist und die Prognose um mehr als die Schwelle darunter liegt. Mit „sport“ zählen nur Ziele,
              die mindestens eine dieser Sportarten betreffen (ein Ziel ohne Sportart betrifft alle). Warnung ab der doppelten Schwelle, sonst Hinweis.
  meilenstein Rundmarken der Summe über alle Touren (nach Sportart): Kilometer 100, 250, 500, 1000 und danach alle 1000; Aufstieg alle 10 000; Touren 25, 50 und alle 100.
              Aktiv, wenn eine Marke von einer Tour der letzten N Tage überschritten wurde (je Art die höchste). Info.
  auffaellig  Touren in der Genauigkeitsliste der Geräte, noch nicht als geprüft markiert (devquality, „flagged“). Aktiv ab der Mindestanzahl. Hinweis.
  pause       Tage seit der letzten Tour (nach Sportart) mindestens so groß wie die Schwelle. Info; ab der doppelten Schwelle Hinweis.
  rekord      Längste Tour, größter Aufstieg, schnellstes Tempo (mindestens 3 km und 30 Minuten) aller Zeiten (nach Sportart, ab 5 Touren; bei Gleichstand gilt die frühere),
              die in den letzten N Tagen gefahren wurde. Info.
  woche       Fortschritt der laufenden Woche (Montag bis Sonntag) gegen die Wochenziele (3.45.0: Ziele mit period = week, Statistik → Ziele; „woche_ziel“ als Parameter hat
              Vorrang). Mit „sport“ zählen nur Ziele, die eine dieser Sportarten betreffen; ein Ziel zählt die Touren seiner Sportart. Nur mit gesetztem Ziel. „daten“ = das erste
              Ziel, „daten.ziele“ = alle. Alle erreicht = Info; offen = Info, am Samstag und Sonntag Hinweis („in Gefahr“ für die Darstellung „Nur Warnung“ des Bausteins „Ziele“).
  erholung    „Aktuell im Vergleich“ der Belastung (belastung.aktuell: 4 Wochen gegen die 12 davor) mindestens so hoch wie die Stufe UND mindestens eine Tour mit Uhr-Wert in den
              letzten 7 Tagen. Nur mit Uhr-Daten. deutlich_mehr = Warnung, mehr = Hinweis.
  sicherung   Letzte Sicherung (extras.newest_backup) älter als N Tage, oder noch keine (nur, wenn es schon Touren gibt), oder die letzte Sicherung ist fehlgeschlagen. Hinweis;
              Warnung bei Fehler, ohne Sicherung oder ab dem Dreifachen der Schwelle.
Zwischenspeicher: 30 s je Benutzer und Parameter, ungültig, sobald sich Touren, Ziele oder „als geprüft markiert“ ändern.
"""
import re
import time
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException

from . import belastung, ctx, db, devquality, extras
from .gpxtools import TZ

router = APIRouter()

ARTEN = ("ziel", "meilenstein", "auffaellig", "pause", "rekord", "woche", "erholung", "sicherung")
STUFEN = ("info", "hinweis", "warnung")
SPORT_RE = re.compile(r"^[A-Za-z0-9_]{1,40}$")
MIN_TAGE_ZIEL = 14                       # Prognose erst ab dem 14. Tag des Jahres (wie der Baustein „Jahresziel“)
MIN_REKORD = 5                           # Rekorde erst ab so vielen Touren
TEMPO_MIN_M, TEMPO_MIN_S = 3000, 1800    # Tempo-Rekord: mindestens 3 km und 30 Minuten (wie „Rekorde“ der Oberfläche)
CACHE_S = 30
SPORT_GRP = {"bike": ("touringbicycle", "e_touringbicycle", "racebike", "mtb"), "ski": ("skitour", "skialpin"),
             "foot": ("hike", "mountaineering", "nordicwalking", "snowshoe"), "run": ("jogging", "nordic")}
GOAL_GRP = {"grp:bike": "bike", "grp:ski": "ski", "grp:foot": "foot", "grp:run": "run"}      # wie GOAL_GRP in 06-erweiterungen.js
DEFAULTS = {"ziel_schwelle": 10, "meilenstein_tage": 7, "auffaellig_min": 1, "pause_tage": 14, "rekord_tage": 7, "woche_ziel": 0, "woche_einheit": "km",
            "erholung_stufe": "deutlich_mehr", "sicherung_tage": 7}


# ------------------------------------------------------------------------------------------------ Prüfung der Parameter
def _zahl(name, v, lo, hi, ganz=True):
    if v in (None, ""):
        return DEFAULTS[name]
    try:
        x = float(str(v).replace(",", "."))
    except ValueError:
        raise HTTPException(400, f"„{name}“ muss eine Zahl sein")
    if x != x or x in (float("inf"), float("-inf")) or not lo <= x <= hi:
        raise HTTPException(400, f"„{name}“ muss zwischen {lo} und {hi} liegen")
    if ganz:
        if x != int(x):
            raise HTTPException(400, f"„{name}“ muss eine ganze Zahl sein")
        return int(x)
    return x


def check(arten="", sport="", ziel_schwelle=None, meilenstein_tage=None, auffaellig_min=None, pause_tage=None, rekord_tage=None, woche_ziel=None, woche_einheit="",
          erholung_stufe="", sicherung_tage=None):
    """Prüft die Parameter und gibt sie bereinigt als Wörterbuch zurück (HTTPException 400 bei Fehlern)."""
    ar = [x for x in (arten or "").split(",") if x != ""]
    if any(x not in ARTEN for x in ar):
        raise HTTPException(400, "Unbekannte Hinweisart (erlaubt: " + ", ".join(ARTEN) + ")")
    sp = [x for x in (sport or "").split(",") if x != ""]
    if len(sp) > 20 or not all(SPORT_RE.match(x) for x in sp):
        raise HTTPException(400, "Ungültige Sportart")
    if woche_einheit not in ("", "km", "touren"):
        raise HTTPException(400, "„woche_einheit“ muss km oder touren sein")
    if erholung_stufe not in ("", "mehr", "deutlich_mehr"):
        raise HTTPException(400, "„erholung_stufe“ muss mehr oder deutlich_mehr sein")
    return {"arten": [a for a in ARTEN if a in ar] if ar else list(ARTEN), "sport": list(dict.fromkeys(sp)),
            "ziel_schwelle": _zahl("ziel_schwelle", ziel_schwelle, 1, 90, ganz=False), "meilenstein_tage": _zahl("meilenstein_tage", meilenstein_tage, 1, 365),
            "auffaellig_min": _zahl("auffaellig_min", auffaellig_min, 1, 1000), "pause_tage": _zahl("pause_tage", pause_tage, 1, 365),
            "rekord_tage": _zahl("rekord_tage", rekord_tage, 1, 365), "woche_ziel": _zahl("woche_ziel", woche_ziel, 0, 100000, ganz=False),
            "woche_einheit": woche_einheit or DEFAULTS["woche_einheit"], "erholung_stufe": erholung_stufe or DEFAULTS["erholung_stufe"],
            "sicherung_tage": _zahl("sicherung_tage", sicherung_tage, 1, 365)}


# ------------------------------------------------------------------------------------------------ Daten
def _touren(sport):
    """Touren mit Startzeit, älteste zuerst: [{id, name, sport, d (Datum in Ortszeit), start_ts, km, hm, s}]."""
    out = []
    for r in db.query("SELECT id,name,sport,start_ts,dist_m,dur_s,up_m FROM tours WHERE start_ts IS NOT NULL ORDER BY start_ts, id"):
        if sport and r["sport"] not in sport:
            continue
        out.append({"id": r["id"], "name": r["name"] or "", "sport": r["sport"], "d": datetime.fromtimestamp(r["start_ts"], tz=TZ).date(), "start_ts": r["start_ts"],
                    "km": (r["dist_m"] or 0) / 1000.0, "hm": r["up_m"] or 0.0, "s": r["dur_s"] or 0.0})
    return out


def _ziel_sportarten(s):
    """Sportarten, die ein Ziel betrifft: None = alle."""
    if not s:
        return None
    return set(SPORT_GRP[GOAL_GRP[s]]) if s in GOAL_GRP else {s}


def _ziel_wert(g, rows):
    m = g["metric"]
    sp = _ziel_sportarten(g["sport"])
    return sum((r["km"] if m == "km" else r["hm"] if m == "up" else r["s"] / 3600.0 if m == "hours" else 1)
               for r in rows if r["d"].year == g["year"] and (sp is None or r["sport"] in sp))


# ------------------------------------------------------------------------------------------------ die Hinweise
def _ziel(p, heute, rows_all):
    jahr = heute.year
    ylen = 366 if (jahr % 4 == 0 and jahr % 100 != 0) or jahr % 400 == 0 else 365
    doy = (heute - date(jahr, 1, 1)).days + 1
    if doy < MIN_TAGE_ZIEL:
        return None
    gefahr = []
    for g in db.query("SELECT id,year,sport,metric,target FROM goals WHERE year=? AND COALESCE(period,'year')='year' ORDER BY id", (jahr,)):
        if not g["target"] or g["target"] <= 0 or g["metric"] not in ("km", "up", "count", "hours"):
            continue
        sp = _ziel_sportarten(g["sport"])
        if p["sport"] and sp is not None and not sp & set(p["sport"]):
            continue
        ist = _ziel_wert(g, rows_all)
        prog = ist / (doy / ylen)
        if ist >= g["target"] or prog >= g["target"] * (1 - p["ziel_schwelle"] / 100.0):
            continue
        gefahr.append({"id": g["id"], "metrik": g["metric"], "sport": g["sport"] or "", "ziel": g["target"], "ist": round(ist, 2), "prognose": round(prog, 2),
                       "abweichung_pct": round((1 - prog / g["target"]) * 100, 1)})
    if not gefahr:
        return None
    gefahr.sort(key=lambda x: (-x["abweichung_pct"], x["id"]))
    stufe = "warnung" if gefahr[0]["abweichung_pct"] >= 2 * p["ziel_schwelle"] else "hinweis"
    return stufe, {"ziele": gefahr, "schwelle": p["ziel_schwelle"]}


def _marken(typ, a, b):
    """Rundmarken, die beim Anstieg von a auf b (a < Marke <= b) überschritten werden."""
    if typ == "km":
        fest, schritt = (100, 250, 500), 1000
    elif typ == "hm":
        fest, schritt = (), 10000
    else:
        fest, schritt = (25, 50), 100
    out = [m for m in fest if a < m <= b]
    k = int(a // schritt) + 1
    while k * schritt <= b:
        out.append(k * schritt)
        k += 1
    return sorted(set(out))


def _meilenstein(p, heute, rows):
    cum = {"km": 0.0, "hm": 0.0, "touren": 0.0}
    best = {}
    for r in rows:
        add = {"km": r["km"], "hm": r["hm"], "touren": 1}
        for typ in cum:
            a, b = cum[typ], cum[typ] + add[typ]
            cum[typ] = b
            if (heute - r["d"]).days > p["meilenstein_tage"] or r["d"] > heute:
                continue
            ms = _marken(typ, a, b)
            if ms:
                best[typ] = {"typ": typ, "wert": ms[-1], "datum": r["d"].isoformat(), "tour": r["id"], "name": r["name"]}
    if not best:
        return None
    return "info", {"marken": sorted(best.values(), key=lambda x: (x["datum"], x["typ"]), reverse=True), "tage": p["meilenstein_tage"]}


def _auffaellig(p, heute, rows):
    n = sum(d.get("flagged", 0) or 0 for d in devquality.payload()["devices"])
    if n < p["auffaellig_min"]:
        return None
    return "hinweis", {"anzahl": n, "min": p["auffaellig_min"]}


def _pause(p, heute, rows):
    if not rows:
        return None
    last = max(rows, key=lambda r: (r["d"], r["start_ts"]))
    tage = (heute - last["d"]).days
    if tage < p["pause_tage"]:
        return None
    return ("hinweis" if tage >= 2 * p["pause_tage"] else "info"), {"tage": tage, "letzte": last["d"].isoformat(), "tour": last["id"], "name": last["name"], "schwelle": p["pause_tage"]}


def _rekord(p, heute, rows):
    if len(rows) < MIN_REKORD:
        return None
    best = {}
    for typ, f, ok in (("km", lambda r: r["km"], lambda r: r["km"] > 0), ("hm", lambda r: r["hm"], lambda r: r["hm"] > 0),
                       ("tempo", lambda r: r["km"] / (r["s"] / 3600.0), lambda r: r["km"] * 1000 >= TEMPO_MIN_M and r["s"] >= TEMPO_MIN_S)):
        top = None
        for r in rows:                                          # älteste zuerst: bei Gleichstand bleibt die frühere
            if ok(r) and (top is None or f(r) > f(top)):
                top = r
        if top and 0 <= (heute - top["d"]).days <= p["rekord_tage"]:
            best[typ] = {"metrik": typ, "wert": round(f(top), 3), "tour": top["id"], "name": top["name"], "datum": top["d"].isoformat()}
    if not best:
        return None
    return "info", {"rekorde": [best[k] for k in ("km", "hm", "tempo") if k in best], "tage": p["rekord_tage"]}


EINHEIT = {"km": "km", "count": "touren", "up": "up", "hours": "hours"}          # Messgröße eines Wochenziels → „einheit“ der Antwort


def _woche_eins(ziel, einheit, inn, heute, mo):
    ist = sum(r["km"] if einheit == "km" else r["hm"] if einheit == "up" else r["s"] / 3600.0 if einheit == "hours" else 1 for r in inn)
    tage_rest = 6 - heute.weekday()
    erreicht = ist >= ziel
    return {"einheit": einheit, "ziel": ziel, "ist": round(float(ist), 2), "rest": round(max(0.0, ziel - ist), 2), "erreicht": erreicht, "tage_rest": tage_rest,
            "von": mo.isoformat(), "bis": (mo + timedelta(days=6)).isoformat()}


def _woche(p, heute, rows, alle=None):
    """3.45.0: Wochenziele stehen in den Zielen (period = week); „woche_ziel“ als Parameter gilt weiter (ältere Aufrufe) und hat Vorrang."""
    mo = heute - timedelta(days=heute.weekday())
    if p["woche_ziel"] and p["woche_ziel"] > 0:
        inn = [r for r in rows if mo <= r["d"] <= heute]
        ziele = [_woche_eins(p["woche_ziel"], p["woche_einheit"], inn, heute, mo)]
    else:
        ziele = []
        for g in db.query("SELECT id,sport,metric,target FROM goals WHERE period='week' ORDER BY id"):
            if not g["target"] or g["target"] <= 0 or g["metric"] not in EINHEIT:
                continue
            sp = _ziel_sportarten(g["sport"])
            if p["sport"] and sp is not None and not sp & set(p["sport"]):
                continue
            inn = [r for r in (alle if alle is not None else rows) if mo <= r["d"] <= heute and (sp is None or r["sport"] in sp)]
            z = _woche_eins(g["target"], EINHEIT[g["metric"]], inn, heute, mo)
            z.update({"id": g["id"], "sport": g["sport"] or "", "metrik": g["metric"]})
            ziele.append(z)
    if not ziele:
        return None
    d = dict(ziele[0])
    if not (p["woche_ziel"] and p["woche_ziel"] > 0):
        d["ziele"] = ziele                                              # Ziele der Statistik: alle; mit Parameter (älterer Aufruf) wie bisher genau eines ohne Liste
    stufe = "info" if all(z["erreicht"] for z in ziele) or d["tage_rest"] > 1 else "hinweis"
    return stufe, d


def _erholung(p, heute, _rows):
    now = datetime.now(TZ) if heute is None else datetime.combine(heute, datetime.max.time().replace(microsecond=0), tzinfo=TZ)
    allrows = db.query("SELECT id,start_ts FROM tours WHERE start_ts IS NOT NULL ORDER BY start_ts")
    for t in allrows:
        t["v"] = belastung._load_value(t["id"])
        t["ts"] = t["start_ts"]
    if not any(t["v"] is not None for t in allrows):
        return None                                              # keine Uhr-Daten: kein Hinweis
    a = belastung.aktuell(allrows, now)
    if a.get("status") != "ok":
        return None
    erlaubt = ("deutlich_mehr",) if p["erholung_stufe"] == "deutlich_mehr" else ("mehr", "deutlich_mehr")
    if a["stufe"] not in erlaubt:
        return None
    lo = now.timestamp() - 7 * 86400
    if not any(t["v"] is not None and lo < t["ts"] <= now.timestamp() for t in allrows):
        return None                                              # in den letzten 7 Tagen keine Tour mit Uhr-Wert: Erholung hat schon stattgefunden
    return ("warnung" if a["stufe"] == "deutlich_mehr" else "hinweis"), {"stufe": a["stufe"], "abweichung_pct": a["abweichung_pct"], "aktuell_schnitt": a["aktuell_schnitt"], "basis_schnitt": a["basis_schnitt"]}


def _sicherung(p, heute, _rows):
    if not db.one("SELECT 1 x FROM tours LIMIT 1"):
        return None                                              # nichts zu sichern
    nb = extras.newest_backup()
    err = (db.get("backup_err") or "").strip()
    if nb is None:
        return "warnung", {"alter_tage": None, "datum": None, "fehler": bool(err), "schwelle": p["sicherung_tage"]}
    mt = datetime.fromtimestamp(nb.stat().st_mtime, tz=TZ)
    ref = datetime.now(TZ) if heute is None else datetime.combine(heute, datetime.max.time().replace(microsecond=0), tzinfo=TZ)
    alter = max(0, (ref - mt).days)
    if alter < p["sicherung_tage"] and not err:
        return None
    return ("warnung" if err or alter >= 3 * p["sicherung_tage"] else "hinweis"), {"alter_tage": alter, "datum": mt.date().isoformat(), "fehler": bool(err), "schwelle": p["sicherung_tage"]}


_REGELN = {"meilenstein": _meilenstein, "auffaellig": _auffaellig, "pause": _pause, "rekord": _rekord, "woche": _woche, "erholung": _erholung, "sicherung": _sicherung}


def auswertung(p, heute=None):
    """p = Ergebnis von check(). heute = Datum (Tests); ohne Angabe das heutige in Ortszeit."""
    h = heute or datetime.now(TZ).date()
    arten = p["arten"]
    alle = _touren([]) if any(a in arten for a in ("ziel", "meilenstein", "pause", "rekord", "woche")) else []
    rows = [r for r in alle if not p["sport"] or r["sport"] in p["sport"]]
    out = []
    for a in ARTEN:
        if a not in arten:
            continue
        if a == "ziel":
            r = _ziel(p, h, alle)                                         # ein Ziel zählt alle seine Touren, auch wenn die Sportart nur auswählt, welche Ziele gelten
        elif a == "woche":
            r = _woche(p, h, rows, alle)
        elif a in ("erholung", "sicherung"):
            r = _REGELN[a](p, heute, rows)
        else:
            r = _REGELN[a](p, h, rows)
        if r:
            out.append({"art": a, "stufe": r[0], "daten": r[1]})
    return {"stand": datetime.now(TZ).isoformat(timespec="seconds"), "heute": h.isoformat(), "hinweise": out, "geprueft": arten}


# ------------------------------------------------------------------------------------------------ Zwischenspeicher und Endpunkt
_CACHE = {}


def _stand():
    t = db.one("SELECT COUNT(*) n, MAX(start_ts) m, COALESCE(SUM(dist_m),0) d, COALESCE(SUM(up_m),0) u, COALESCE(SUM(dur_s),0) s FROM tours")
    g = db.one("SELECT COUNT(*) n, COALESCE(SUM(target),0) s, MAX(id) m FROM goals")
    q = db.one("SELECT COUNT(*) n, MAX(ts) m FROM quality_ack")
    try:
        nb = extras.newest_backup()
        b = (str(nb), nb.stat().st_mtime) if nb else None
    except Exception:
        b = None
    try:
        dq = tuple((d.get("flagged", 0) or 0) for d in devquality.payload()["devices"])
    except Exception:
        dq = ()
    return (tuple(t.values()), tuple(g.values()), tuple(q.values()), b, (db.get("backup_err") or ""), dq)


@router.get("/api/bausteine/hinweise")
def api_hinweise(arten: str = "", sport: str = "", ziel_schwelle: str = "", meilenstein_tage: str = "", auffaellig_min: str = "", pause_tage: str = "", rekord_tage: str = "",
                 woche_ziel: str = "", woche_einheit: str = "", erholung_stufe: str = "", sicherung_tage: str = ""):
    p = check(arten, sport, ziel_schwelle, meilenstein_tage, auffaellig_min, pause_tage, rekord_tage, woche_ziel, woche_einheit, erholung_stufe, sicherung_tage)
    key = (ctx.uid(), repr(sorted(p.items())), _stand())
    c = _CACHE.get(key)
    if c and time.time() - c[0] < CACHE_S:
        return c[1]
    r = auswertung(p)
    if len(_CACHE) > 200:
        _CACHE.clear()
    _CACHE[key] = (time.time(), r)
    return r
