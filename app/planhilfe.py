"""Planung ausbauen (3.47.0): Notizen und Quellen am Plan, Entscheidungshilfe „Passt die Tour zu mir?“.

Reine Funktionen (kein Netz, nie ein Abruf der gespeicherten Links):

* Links: `pruefe_links` – nur http/https, Länge und Anzahl begrenzt, keine Zugangsdaten in der Adresse, Art aus fester Liste.
* Form: `form` – Strecke, Aufstieg und Dauer des Plans gegen die eigenen Touren derselben Sportgruppe der letzten 12 Monate.
  Einordnung über das Verhältnis zum Median (unter 80 % „kürzer/weniger“, über 125 % „länger/mehr“, dazwischen „ähnlich“), dazu das Perzentil
  (Anteil der eigenen Touren darunter, Gleiche zählen halb) und das Verhältnis zur längsten/höchsten Tour. Unter MIN_N Vergleichstouren: „zu wenig“, nie Platzhalter.
* Tageslicht: `tageslicht` – Sonnenauf-/-untergang am Startpunkt (dieselbe NOAA-Näherung wie der Baustein „Tageslicht“, etwa 2 Minuten genau),
  geschätzte Rückkehr = Start + Dauer + Puffer. Uhrzeiten in der Zeitzone der App (TZ), gerechnet mit absoluten Zeitpunkten (richtig auch an Tagen mit Zeitumstellung).

Orientierung, keine Sicherheitsgarantie: Dämmerung und Reserve sind Rechenwerte, keine Aussage über Wetter, Lawinenlage oder Gelände.
"""
import json
import math
import re
import time
from datetime import date, datetime, timedelta, timezone
from statistics import median
from urllib.parse import urlsplit

from . import bausteine_daten, belastung, config, db, plan_check
from .gpxtools import TZ

MIN_N = 5                       # Vergleichstouren, darunter „zu wenig“
MONATE = 12
UNTER, UEBER = 0.80, 1.25       # Verhältnis zum Median: darunter „kürzer“, darüber „länger“
DEUTLICH_UEBER_MAX = 1.20       # über 120 % der längsten/höchsten eigenen Tour: Hinweis
ETWA_MAX = 0.95                 # ab 95 % „etwa so lang/hoch wie deine längste/höchste“
RESERVE_OK_MIN = 60             # ab 60 Minuten Reserve vor Sonnenuntergang „Reserve“, darunter „knapp“
PUFFER_STANDARD = 20            # Prozent der geschätzten Dauer
START_STANDARD = "09:00"

LINK_ARTEN = ("fuehrer", "karte", "wetter", "huette", "sonstiges")
QUELLEN = ("eigen", "komoot", "outdooractive", "fuehrer", "sonstiges")
MAX_LINKS, MAX_URL, MAX_TITEL, MAX_QTEXT, MAX_NOTIZ = 20, 500, 120, 200, 4000

_DATUM = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_ZEIT = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


# ------------------------------------------------------------------------------------------------ Notizen und Quellen
def pruefe_url(u):
    """Gültige http(s)-Adresse (bereinigt) oder ValueError. Kein javascript:, data:, file: …; keine Leerzeichen/Steuerzeichen; keine Zugangsdaten in der Adresse."""
    if not isinstance(u, str):
        raise ValueError("Adresse fehlt")
    u = u.strip()
    if not u:
        raise ValueError("Adresse fehlt")
    if len(u) > MAX_URL:
        raise ValueError(f"Adresse zu lang (höchstens {MAX_URL} Zeichen)")
    if re.search(r"[\s\x00-\x1f\x7f]", u):
        raise ValueError("Adresse enthält Leerzeichen oder Steuerzeichen")
    try:
        p = urlsplit(u)
        host = p.hostname
    except ValueError:
        raise ValueError("Adresse ungültig")
    if p.scheme.lower() not in ("http", "https"):
        raise ValueError("Nur Adressen mit http:// oder https:// sind erlaubt")
    if not host or p.username is not None or p.password is not None:
        raise ValueError("Adresse ungültig (Server fehlt oder Zugangsdaten in der Adresse)")
    return u


def pruefe_links(raw):
    """Liste {titel, url, art} prüfen: höchstens MAX_LINKS, Titel höchstens MAX_TITEL (leer = Servername), Art aus LINK_ARTEN (leer = sonstiges). ValueError mit verständlicher Meldung."""
    if raw in (None, ""):
        return []
    if not isinstance(raw, list):
        raise ValueError("Links: Liste erwartet")
    if len(raw) > MAX_LINKS:
        raise ValueError(f"Höchstens {MAX_LINKS} Links je Plan")
    out = []
    for i, x in enumerate(raw, 1):
        if not isinstance(x, dict):
            raise ValueError(f"Link {i}: ungültig")
        try:
            url = pruefe_url(x.get("url"))
        except ValueError as e:
            raise ValueError(f"Link {i}: {e}")
        titel = x.get("titel")
        titel = "" if titel is None else titel
        if not isinstance(titel, str):
            raise ValueError(f"Link {i}: Titel muss Text sein")
        titel = " ".join(titel.split())
        if len(titel) > MAX_TITEL:
            raise ValueError(f"Link {i}: Titel zu lang (höchstens {MAX_TITEL} Zeichen)")
        art = x.get("art") or "sonstiges"
        if art not in LINK_ARTEN:
            raise ValueError(f"Link {i}: Art unbekannt")
        out.append({"titel": titel or (urlsplit(url).hostname or url), "url": url, "art": art})
    return out


def lade_links(raw):
    """Gespeicherte Links lesen; ungültige Einträge (etwa aus einer manipulierten Datenbank) werden still ausgelassen."""
    try:
        lst = json.loads(raw) if raw else []
    except (TypeError, ValueError):
        return []
    out = []
    for x in lst if isinstance(lst, list) else []:
        try:
            out += pruefe_links([x])
        except ValueError:
            continue
    return out[:MAX_LINKS]


def pruefe_quelle(art, text):
    """(art, text) der Herkunft: art None = nicht angegeben; Freitext höchstens MAX_QTEXT Zeichen."""
    art = None if art in (None, "") else art
    if art is not None and art not in QUELLEN:
        raise ValueError("Herkunft unbekannt")
    if text is not None and not isinstance(text, str):
        raise ValueError("Herkunft: Text erwartet")
    text = " ".join((text or "").split())
    if len(text) > MAX_QTEXT:
        raise ValueError(f"Herkunft: Text zu lang (höchstens {MAX_QTEXT} Zeichen)")
    return art, text or None


def pruefe_notiz(t):
    if t is None:
        return ""
    if not isinstance(t, str):
        raise ValueError("Notiz: Text erwartet")
    if len(t) > MAX_NOTIZ:
        raise ValueError(f"Notiz zu lang (höchstens {MAX_NOTIZ} Zeichen)")
    return t


def pruefe_datum(v):
    """YYYY-MM-DD (echtes Datum 2000–2100) oder None bei leer."""
    if v in (None, ""):
        return None
    if not isinstance(v, str) or not _DATUM.match(v):
        raise ValueError("Datum: Format JJJJ-MM-TT erwartet")
    try:
        d = date.fromisoformat(v)
    except ValueError:
        raise ValueError("Datum ungültig")
    if not 2000 <= d.year <= 2100:
        raise ValueError("Datum außerhalb 2000–2100")
    return v


def pruefe_start(v):
    """HH:MM (24 Stunden) oder None bei leer."""
    if v in (None, ""):
        return None
    if not isinstance(v, str) or not _ZEIT.match(v):
        raise ValueError("Startzeit: Format HH:MM erwartet")
    return v


def pruefe_puffer(v):
    """Ganze Prozent 0–100 oder None bei leer."""
    if v in (None, ""):
        return None
    if isinstance(v, bool):
        raise ValueError("Puffer: Zahl erwartet")
    try:
        x = float(v)
    except (TypeError, ValueError):
        raise ValueError("Puffer: Zahl erwartet")
    if not math.isfinite(x) or x < 0 or x > 100 or x != int(x):
        raise ValueError("Puffer: ganze Prozent von 0 bis 100")
    return int(x)


# ------------------------------------------------------------------------------------------------ Form
def _grp(sport):
    return plan_check._grp(sport)


def _metrik(wert, vals):
    """Einordnung eines Planwertes gegen eigene Werte (mindestens MIN_N); None bei fehlendem Planwert oder zu wenig Vergleichswerten."""
    if wert is None or wert < 0 or len(vals) < MIN_N:
        return None
    med, mx = median(vals), max(vals)
    ver = round(wert / med, 3) if med > 0 else None
    if med > 0:
        ein = "unter" if wert / med < UNTER else "ueber" if wert / med > UEBER else "aehnlich"
    else:
        ein = "aehnlich" if wert <= 0 else "ueber"
    perz = round(100.0 * (sum(1 for v in vals if v < wert) + 0.5 * sum(1 for v in vals if v == wert)) / len(vals))
    f = wert / mx if mx > 0 else (1.0 if wert <= 0 else math.inf)
    stufe = "deutlich_ueber" if f > DEUTLICH_UEBER_MAX else "ueber" if f > 1.0 else "etwa" if f >= ETWA_MAX else "unter"
    return {"wert": wert, "median": med, "max": mx, "n": len(vals), "verhaeltnis_median_pct": None if ver is None else round(ver * 100),
            "einordnung": ein, "perzentil": perz, "vs_max_pct": None if math.isinf(f) else round(f * 100), "max_stufe": stufe}


def form(km, up, est_h, sport, tours, now_ts):
    """Plan-Werte gegen die Touren derselben Sportgruppe der letzten 12 Monate. tours: [{sport,start_ts,dist_m,dur_s,up_m}].
    Rückgabe {"status": "zu_wenig"|"ok", "n", "min_n", "monate", "km", "up", "dauer", "deutlich_ueber": [...]}; Teilwerte sind None, wenn der Planwert fehlt oder weniger als MIN_N Vergleichswerte vorliegen."""
    lo = now_ts - MONATE * 30.4375 * 86400
    g = _grp(sport)
    rows = [t for t in tours if t.get("start_ts") and lo <= t["start_ts"] <= now_ts + 86400 and (t.get("dist_m") or 0) > 0
            and ((_grp(t["sport"]) == g) if g else t["sport"] == sport)]
    out = {"status": "zu_wenig", "n": len(rows), "min_n": MIN_N, "monate": MONATE, "km": None, "up": None, "dauer": None, "deutlich_ueber": []}
    if len(rows) < MIN_N:
        return out
    out["status"] = "ok"
    out["km"] = _metrik(km if km and km > 0 else None, [t["dist_m"] / 1000.0 for t in rows])
    out["up"] = _metrik(up, [t["up_m"] for t in rows if t.get("up_m") is not None])
    out["dauer"] = _metrik(est_h if est_h and est_h > 0 else None, [t["dur_s"] / 3600.0 for t in rows if (t.get("dur_s") or 0) > 0])
    out["deutlich_ueber"] = [k for k in ("km", "up", "dauer") if out[k] and out[k]["max_stufe"] == "deutlich_ueber"]
    return out


def belastungskontext(now=None):
    """Belastung der letzten 4 Wochen gegen die 12 Wochen davor (nur wenn belastung.py dafür genug Uhr-Werte hat), sonst None."""
    try:
        now = now or datetime.now(TZ)
        rows = db.query("SELECT id,start_ts FROM tours WHERE start_ts IS NOT NULL")
        for t in rows:
            t["v"] = belastung._load_value(t["id"])
            t["ts"] = t["start_ts"]
        a = belastung.aktuell(rows, now)
    except Exception:  # noqa – eine Zusatzangabe darf die Hilfe nie verhindern
        return None
    if a.get("status") != "ok" or a.get("stufe") is None:
        return None
    return {"stufe": a["stufe"], "abweichung_pct": a["abweichung_pct"], "aktuell_schnitt": a["aktuell_schnitt"], "basis_schnitt": a["basis_schnitt"]}


# ------------------------------------------------------------------------------------------------ Tageslicht
def _wall(dt):
    d = dt.astimezone(TZ)
    return d.hour * 60 + d.minute


def tageslicht(lat, lng, datum, start, dauer_h, puffer_pct, heute):
    """Sonnenaufgang/-untergang am Startpunkt und geschätzte Rückkehr.
    datum: 'YYYY-MM-DD' oder None (= heute); start: 'HH:MM' oder None (= 09:00); dauer_h: geschätzte Dauer; puffer_pct: None = 20 %; heute: date (in TZ).
    Uhrzeiten sind Minuten seit Mitternacht (Ortszeit TZ); `rueckkehr_tag_plus` > 0, wenn die Rückkehr nach Mitternacht liegt.
    status: ok | polar_tag | polar_nacht | keine_position | keine_dauer; ampel (bei ok): reserve (>= 60 min) | knapp (0–59 min) | nach_untergang."""
    if lat is None or lng is None or not (-90 <= lat <= 90 and -180 <= lng <= 180) or (lat == 0 and lng == 0):
        return {"status": "keine_position"}
    day = date.fromisoformat(datum) if datum else heute
    st = start or START_STANDARD
    pf = PUFFER_STANDARD if puffer_pct is None else puffer_pct
    base = {"datum": day.isoformat(), "datum_gewaehlt": bool(datum), "start": st, "start_gewaehlt": bool(start), "puffer_pct": pf, "puffer_gewaehlt": puffer_pct is not None, "zeitzone": config.TZ_NAME}
    if not dauer_h or dauer_h <= 0:
        return {**base, "status": "keine_dauer"}
    hh, mm = int(st[:2]), int(st[3:])
    start_dt = datetime(day.year, day.month, day.day, hh, mm, tzinfo=TZ).astimezone(timezone.utc)      # ab hier absolute Zeitpunkte (UTC): Dauer addieren und vergleichen, ohne dass die Zeitumstellung die Rechnung verfälscht
    dauer_min = dauer_h * 60.0
    puffer_min = dauer_min * pf / 100.0
    ret_dt = start_dt + timedelta(minutes=dauer_min + puffer_min)
    out = {**base, "start_min": hh * 60 + mm, "dauer_min": round(dauer_min), "puffer_min": round(puffer_min), "rueckkehr_min": _wall(ret_dt),
           "rueckkehr_tag_plus": (ret_dt.astimezone(TZ).date() - day).days}
    sun, civ = bausteine_daten._sonne(day, lat, lng, 90.833), bausteine_daten._sonne(day, lat, lng, 96.0)
    if not sun:
        out["status"] = "polar_" + (bausteine_daten.polar_art(day, lat) or "nacht")
        return out
    out.update(status="ok", aufgang_min=_wall(sun[0]), untergang_min=_wall(sun[1]), daemm_bis_min=_wall(civ[1]) if civ else None)
    reserve = math.floor((sun[1] - ret_dt).total_seconds() / 60.0)      # ganze Minuten abgerundet: 59,9 Minuten sind noch „knapp“
    out["reserve_min"] = reserve
    out["ampel"] = "reserve" if reserve >= RESERVE_OK_MIN else "knapp" if reserve >= 0 else "nach_untergang"
    out["start_vor_aufgang"] = start_dt < sun[0]
    out["start_nach_untergang"] = start_dt >= sun[1]
    return out


# ------------------------------------------------------------------------------------------------ Zusammenstellung
def _start_punkt(pts_json):
    try:
        p = json.loads(pts_json)[0]
        return float(p[0]), float(p[1])
    except (TypeError, ValueError, IndexError, KeyError):
        return None, None


_K = object()                                            # „nicht angegeben“ (None heißt: leer = Standard)


def hilfe(plan, datum=_K, start=_K, puffer=_K, now_ts=None, tours=None):
    """Entscheidungshilfe für einen Plan (Zeile aus `plans`). datum/start/puffer überschreiben für diesen Aufruf die gespeicherten Werte (nichts wird gespeichert).
    Der Plan ist nur lesend betroffen; Links werden nie abgerufen."""
    now_ts = time.time() if now_ts is None else now_ts
    heute = datetime.fromtimestamp(now_ts, tz=TZ).date()
    if tours is None:
        tours = db.query("SELECT sport,start_ts,dist_m,dur_s,up_m FROM tours WHERE start_ts>=? AND dist_m IS NOT NULL AND dist_m>0", (now_ts - (MONATE * 30.4375 + 2) * 86400,))
    km, up, est = plan.get("km"), plan.get("up"), plan.get("est_h")
    dauer = est
    dauer_quelle = "plan" if est else None
    if not dauer and km and km > 0:                          # ohne gespeicherte Gesamtzeit: reine Gehzeit aus dem Steigungstempo (nur Wandern/Laufen), ausdrücklich so benannt
        g = plan_check._gehzeit(plan.get("sport") or "hike", km, up, plan.get("down"))
        if g:
            dauer, dauer_quelle = g["sekunden"] / 3600.0, "gehzeit"
    lat, lng = _start_punkt(plan.get("pts") or "[]")
    f = form(km, up, est, plan.get("sport") or "hike", tours, now_ts)
    f["belastung"] = belastungskontext(datetime.fromtimestamp(now_ts, tz=TZ)) if f["status"] == "ok" else None
    links = lade_links(plan.get("links"))
    return {"plan": {"id": plan.get("id"), "name": plan.get("name") or "", "sport": plan.get("sport"), "km": km, "up": up, "est_h": est},
            "form": f,
            "tageslicht": {**tageslicht(lat, lng, plan.get("plan_datum") if datum is _K else datum, plan.get("plan_start") if start is _K else start,
                                        dauer, plan.get("puffer_pct") if puffer is _K else puffer, heute), "dauer_quelle": dauer_quelle},
            "wetter_links": [x for x in links if x["art"] == "wetter"]}
