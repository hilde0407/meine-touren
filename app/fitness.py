"""Fitness-Einordnung (3.44.0): ordnet die Aktivität der letzten 12 Wochen in Relation zum Alter ein. ORIENTIERUNG, KEINE MEDIZINISCHE AUSSAGE.

Endpunkte (je Benutzer, die Datenbank gehört dem angemeldeten Benutzer):
  GET    /api/fitness               Einordnung (siehe berechne); ohne Geburtsjahr nur {"status": "kein_geburtsjahr"}
  PUT    /api/fitness/geburtsjahr   {"jahr": JJJJ} setzt/ändert das Geburtsjahr (Alter 10 bis 110, sonst 400)
  DELETE /api/fitness/geburtsjahr   entfernt es wieder
Das Geburtsjahr (nur das Jahr) liegt in der Tabelle `settings` des Benutzers unter „birth_year“ – bewusst NICHT in config.DEFAULTS: es erscheint nie in GET /api/settings,
nie in Freigabelinks, Exporten oder Ansichten und nie im Konto eines anderen Benutzers. Betrachter (Rolle „viewer“) dürfen weder lesen noch schreiben
(/api/fitness steht nicht in main.VIEWER_GET; die Oberfläche zeigt ihnen einen Hinweis). Es wird nur lokal gerechnet, kein Aufruf nach außen.

Grundlage: die letzten 12 Wochen (84 Tage bis einschließlich heute, in 12 Blöcken zu je 7 Tagen); zum Vergleich die 12 Wochen davor. Drei Teilwerte, jeder 0 bis 100,
jeder nur, wenn die Daten da sind (sonst {"wert": None, "status": "keine_daten"} – nie 0 als Platzhalter):

1. Umfang       durchschnittliche Dauer je Woche (Minuten, Summe der Tourdauer / 12) gegen die WHO-Empfehlung für Erwachsene von 150 bis 300 Minuten Bewegung mit mittlerer Intensität
                je Woche (WHO-Leitlinien zu körperlicher Aktivität und sitzendem Verhalten, 2020; gilt auch ab 65 Jahren in gleicher Menge). Linear: 0 min = 0, 150 min = 70, 300 min und mehr = 100.
2. Regelmäßigkeit  100 × (0,7 × Anteil der Wochen mit mindestens einer Tour + 0,3 × Gleichmäßigkeit); Gleichmäßigkeit = 1 − Variationskoeffizient der Touren je Woche (auf 0 bis 1 begrenzt).
3. Intensität   altersbezogen, mit Puls (mindestens 10 Minuten Pulsdaten in den 12 Wochen): Anteil der Pulszeit im Bereich 60 bis 90 % der geschätzten Maximalpuls
                HFmax = 208 − 0,7 × Alter (Tanaka, Monahan und Seals 2001); Alter = laufendes Jahr − Geburtsjahr (auf das Jahr genau, daher ±1 Jahr). Ein eingestellter „Maximalpuls“ der
                Pulszonen wird hier bewusst NICHT verwendet (die Einordnung soll vom Alter abhängen und nachvollziehbar bleiben); der mittlere Puls (in % HFmax) wird zusätzlich genannt.
                Ohne Pulsdaten als Ersatz: Aufstieg je Stunde (Summe Aufstieg / Summe Dauer, nur Touren mit Dauer und Aufstieg) gegen einen alterskorrigierten Richtwert:
                REF_AUFSTIEG_H = 400 m/h bei Alter 30 und jünger, je Jahr darüber 1 % weniger (Faktor k = 1 − 0,01 × (Alter − 30), nicht unter 0,5); Teilwert = 100 × (Aufstieg/h) / (k × 400), höchstens 100.
                DIE RICHTWERTE SIND GROBE NÄHERUNGEN (der Rückgang der Leistungsfähigkeit liegt im Mittel bei rund 10 % je Jahrzehnt; Gelände und Sportart beeinflussen den Wert stark), keine
                Normwerte. Das Tempo wird bewusst nicht herangezogen (Gelände und Sportart verfälschen es zu stark). Fehlt beides (kein Puls, kein Aufstieg), fehlt der Teilwert.
Eine VO2max wird nicht geschätzt (die Uhr-Daten der App enthalten keine plausible VO2max).

Gesamt: Mittel der vorhandenen Teilwerte, mindestens zwei nötig (sonst Status „zu_wenig“). Einordnung: ab 80 „sehr_aktiv“, ab 60 „gut“, ab 40 „solide“, darunter „ausbaufaehig“.
Trend: Gesamtwert der letzten 12 Wochen gegen den der 12 Wochen davor (mit demselben Alter): ab +5 Punkten „up“, ab −5 „down“, sonst „flat“; ohne auswertbaren Vorzeitraum None.
Die Schwellen (Einordnung, ±5, 0,7/0,3, 400 m/h, 1 % je Jahr) sind frei gewählte Anhaltswerte und stehen hier offen, damit sie sich nachvollziehen und ändern lassen.
"""
import math
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request

from . import db, puls
from .gpxtools import TZ

router = APIRouter()

WEEKS = 12
ALTER_MIN, ALTER_MAX = 10, 110
WHO_MIN, WHO_MAX = 150.0, 300.0           # Minuten je Woche
PULS_MIN_S = 600                          # mindestens so viele Sekunden Pulsdaten in den 12 Wochen
ZONE_LO, ZONE_HI = 0.60, 0.90             # Anteil der HFmax
REF_AUFSTIEG_H = 400.0                    # m Aufstieg je Stunde für volle Punkte bei Alter <= 30
REF_ALTER = 30
K_MIN = 0.5
MIN_TEILE = 2
TREND_SCHWELLE = 5
KLASSEN = ((80, "sehr_aktiv"), (60, "gut"), (40, "solide"), (0, "ausbaufaehig"))
BPM_MIN, BPM_MAX = 30, 240
KEY = "birth_year"


# ------------------------------------------------------------------------------------------------ reine Funktionen
def alter(geburtsjahr, heute):
    return heute.year - int(geburtsjahr)


def hfmax(a):
    """Geschätzte maximale Herzfrequenz nach Tanaka (2001): 208 − 0,7 × Alter."""
    return 208.0 - 0.7 * a


def pruefe_jahr(jahr, heute):
    """Geburtsjahr prüfen (ganze Zahl, Alter 10 bis 110) -> int oder ValueError."""
    if isinstance(jahr, bool) or not isinstance(jahr, (int, str)):
        raise ValueError("Bitte ein Geburtsjahr angeben (vier Ziffern).")
    try:
        j = int(str(jahr).strip())
    except ValueError:
        raise ValueError("Bitte ein Geburtsjahr angeben (vier Ziffern).")
    if not (heute.year - ALTER_MAX <= j <= heute.year - ALTER_MIN):
        raise ValueError(f"Das Geburtsjahr muss zwischen {heute.year - ALTER_MAX} und {heute.year - ALTER_MIN} liegen.")
    return j


def teilwert_umfang(min_woche):
    """Minuten je Woche -> 0..100 (0 = 0, 150 = 70, 300 und mehr = 100); None bleibt None."""
    if min_woche is None or not math.isfinite(min_woche) or min_woche < 0:
        return None
    if min_woche <= WHO_MIN:
        return round(70 * min_woche / WHO_MIN)
    return round(min(100.0, 70 + 30 * (min_woche - WHO_MIN) / (WHO_MAX - WHO_MIN)))


def teilwert_regel(touren_je_woche):
    """Touren je Woche (Liste mit WEEKS Zahlen) -> 0..100; ohne Touren None."""
    n = len(touren_je_woche)
    if not n or sum(touren_je_woche) <= 0:
        return None
    anteil = sum(1 for x in touren_je_woche if x > 0) / n
    mw = sum(touren_je_woche) / n
    sd = math.sqrt(sum((x - mw) ** 2 for x in touren_je_woche) / n)
    gleich = 1 - min(1.0, sd / mw)
    return round(100 * (0.7 * anteil + 0.3 * gleich))


def teilwert_puls(hist, a):
    """hist = {bpm: Sekunden} (alle Touren des Zeitraums) -> {"wert", "mittel_bpm", "mittel_pct", "zone_pct", "hfmax", "sekunden"} oder None (zu wenig Pulsdaten)."""
    h = {int(b): float(s) for b, s in (hist or {}).items() if BPM_MIN <= int(b) <= BPM_MAX and s > 0}
    tot = sum(h.values())
    if tot < PULS_MIN_S:
        return None
    hm = hfmax(a)
    zone = sum(s for b, s in h.items() if ZONE_LO * hm <= b <= ZONE_HI * hm)
    mean = sum(b * s for b, s in h.items()) / tot
    return {"wert": round(100 * zone / tot), "mittel_bpm": round(mean), "mittel_pct": round(100 * mean / hm), "zone_pct": round(100 * zone / tot), "hfmax": round(hm), "sekunden": round(tot)}


def faktor_alter(a):
    return max(K_MIN, 1 - 0.01 * max(0, a - REF_ALTER))


def teilwert_aufstieg(up_m, dauer_s, a):
    """Aufstieg je Stunde gegen den alterskorrigierten Richtwert -> {"wert", "m_h", "ref_m_h"} oder None (kein Aufstieg / zu wenig Zeit)."""
    if not up_m or up_m <= 0 or not dauer_s or dauer_s < 3600:
        return None
    mh = up_m / (dauer_s / 3600)
    ref = faktor_alter(a) * REF_AUFSTIEG_H
    return {"wert": round(min(100.0, 100 * mh / ref)), "m_h": round(mh), "ref_m_h": round(ref)}


def klasse(gesamt):
    for ab, name in KLASSEN:
        if gesamt >= ab:
            return name
    return KLASSEN[-1][1]


def _fenster(touren, von, bis):
    return [t for t in touren if von <= t["tag"] <= bis]


def _teile(touren, bis, a):
    """Teilwerte für die 84 Tage bis einschließlich `bis`. touren: [{"tag": date, "dauer_s", "up_m", "hist"}]."""
    von = bis - timedelta(days=WEEKS * 7 - 1)
    ts = _fenster(touren, von, bis)
    out = {"touren": len(ts), "umfang": None, "regel": None, "intensitaet": None}
    if not ts:
        return out
    je_woche = [0] * WEEKS
    for t in ts:
        je_woche[min(WEEKS - 1, (bis - t["tag"]).days // 7)] += 1
    mit_dauer = [t for t in ts if (t.get("dauer_s") or 0) > 0]
    if mit_dauer:
        mw = sum(t["dauer_s"] for t in mit_dauer) / 60 / WEEKS
        out["umfang"] = {"wert": teilwert_umfang(mw), "min_woche": round(mw, 1), "who_min": int(WHO_MIN), "who_max": int(WHO_MAX), "ohne_dauer": len(ts) - len(mit_dauer)}
    out["regel"] = {"wert": teilwert_regel(je_woche), "wochen_aktiv": sum(1 for x in je_woche if x > 0), "wochen": WEEKS, "touren": len(ts)}
    hist = {}
    for t in ts:
        for b, s in (t.get("hist") or {}).items():
            hist[b] = hist.get(b, 0) + s
    p = teilwert_puls(hist, a)
    if p:
        out["intensitaet"] = {**p, "quelle": "puls"}
    else:
        m = [t for t in mit_dauer if (t.get("up_m") or 0) > 0]
        u = teilwert_aufstieg(sum(t["up_m"] for t in m), sum(t["dauer_s"] for t in m), a)
        if u:
            out["intensitaet"] = {**u, "quelle": "aufstieg"}
    return out


def _gesamt(teile):
    w = [teile[k]["wert"] for k in ("umfang", "regel", "intensitaet") if teile.get(k) and teile[k].get("wert") is not None]
    return round(sum(w) / len(w)) if len(w) >= MIN_TEILE else None


def _teil_oder_leer(x):
    return x if x else {"wert": None, "status": "keine_daten"}


def berechne(touren, geburtsjahr, heute):
    """Einordnung aus Touren (siehe _teile) und Geburtsjahr; `heute` ein date. Ohne Geburtsjahr: nur {"status": "kein_geburtsjahr"} (nie Platzhalterwerte)."""
    if geburtsjahr is None:
        return {"status": "kein_geburtsjahr"}
    a = alter(geburtsjahr, heute)
    base = {"geburtsjahr": int(geburtsjahr), "alter": a, "wochen": WEEKS, "von": (heute - timedelta(days=WEEKS * 7 - 1)).isoformat(), "bis": heute.isoformat()}
    if not touren:
        return {**base, "status": "keine_touren"}
    jetzt = _teile(touren, heute, a)
    if not jetzt["touren"]:
        return {**base, "status": "keine_aktuellen"}
    out = {**base, "touren": jetzt["touren"], "umfang": _teil_oder_leer(jetzt["umfang"]), "regel": _teil_oder_leer(jetzt["regel"]), "intensitaet": _teil_oder_leer(jetzt["intensitaet"])}
    g = _gesamt(jetzt)
    if g is None:
        return {**out, "status": "zu_wenig"}
    vor = _gesamt(_teile(touren, heute - timedelta(days=WEEKS * 7), a))
    trend = None if vor is None else ("up" if g - vor >= TREND_SCHWELLE else "down" if vor - g >= TREND_SCHWELLE else "flat")
    return {**out, "status": "ok", "gesamt": g, "einordnung": klasse(g), "trend": trend, "vorher": vor}


# ------------------------------------------------------------------------------------------------ Daten und Endpunkte
def _touren(heute):
    """Touren der letzten 24 Wochen mit Dauer, Aufstieg und – falls vorhanden – dem Pulsverlauf (Sekunden je bpm)."""
    ab = heute - timedelta(days=2 * WEEKS * 7 + 1)
    ab_ts = int(datetime(ab.year, ab.month, ab.day, tzinfo=TZ).timestamp())
    hr = puls.tours_with_hr()
    out = []
    for r in db.query("SELECT id,start_ts,dur_s,up_m FROM tours WHERE start_ts IS NOT NULL AND start_ts>=?", (ab_ts,)):
        c = puls._hist(r["id"]) if r["id"] in hr else None
        out.append({"tag": datetime.fromtimestamp(r["start_ts"], tz=TZ).date(), "dauer_s": r["dur_s"], "up_m": r["up_m"], "hist": c[1] if c else None})
    return out


def _geburtsjahr():
    v = db.get(KEY)
    try:
        return int(v) if v else None
    except ValueError:
        return None


@router.get("/api/fitness")
def api_fitness():
    j = _geburtsjahr()
    heute = datetime.now(TZ).date()
    if j is None:
        return {"status": "kein_geburtsjahr"}
    if db.one("SELECT 1 x FROM tours WHERE start_ts IS NOT NULL LIMIT 1") is None:
        return berechne([], j, heute)
    return berechne(_touren(heute), j, heute)


@router.put("/api/fitness/geburtsjahr")
async def api_set_geburtsjahr(request: Request):
    try:
        d = await request.json()
    except ValueError:
        raise HTTPException(400, "Ungültige Anfrage")
    if not isinstance(d, dict):
        raise HTTPException(400, "Ungültige Anfrage")
    try:
        j = pruefe_jahr(d.get("jahr"), datetime.now(TZ).date())
    except ValueError as e:
        raise HTTPException(400, str(e))
    db.put(KEY, str(j))
    return {"ok": True}


@router.delete("/api/fitness/geburtsjahr")
def api_del_geburtsjahr():
    db.execute("DELETE FROM settings WHERE k=?", (KEY,))
    return {"ok": True}
