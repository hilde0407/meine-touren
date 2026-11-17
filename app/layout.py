"""Seite anpassen (3.17.0): gespeicherte Anordnung der Abschnitte und Bausteine je Seite.

Schlüssel: „tour-haupt“ (Tourseite), „tour-auswertung“ (Unterseite Auswertung), „uebersicht“ (Übersicht), „statistik“ (Statistik, 3.22.0),
„reise“ (Reise-Detailseite #/trip/<id>, 3.33.0), „reisen“ (Reisen-Übersicht #/trips, 3.33.0), „fotos“ (Fotos-Seite #/photos, 3.34.0) und „karte“ (Gesamtkarte #/map, 3.34.0).
Das Layout einer Seite gilt für alle Reisen gleich (je Benutzer, nicht je Reise).
Jeder Benutzer hat eine eigene Datenbank (app/ctx.py); die Tabelle `user_layout` ist daher je Benutzer getrennt, eine Spalte „user“ ist nicht nötig.
Dokument (JSON-Objekt, alle Felder optional):
  order    [id]            Reihenfolge der Abschnitte dieser Seite
  hidden   [id]            ausgeblendete Abschnitte
  closed   [id] / open [id] Abschnitte, die standardmäßig zu bzw. (abweichend vom Standard) offen sind
  page     {id: "haupt"|"auswertung"}  Abschnitte, die auf der anderen Seite der Tour liegen
  widgets  [{id, type, cfg}]  hinzugefügte Bausteine mit ihrer Konfiguration
  cfg      {id: {…}}       Konfiguration der Standard-Bausteine, die nicht als „widgets“ gespeichert sind (3.19.0: der Baustein „Dein Jahr“ der Übersicht, Kennung „jahr“)
  kopf     {holen: false}  Kopfzeile der Übersicht (3.31.0): „holen“ = false schaltet den Schnell-Knopf „Touren holen“ ab (Standard: an, dann steht nichts im Dokument)
  w        {id: Breite}    Breite im Raster (3.20.0): "voll" | "zweidrittel" | "halb" | "drittel"; gespeichert werden nur Abweichungen vom Standard des Abschnitts (den kennt die Oberfläche)
Seiteneignung (3.20.0): Bausteine der Übersicht dürfen auch auf der Tourseite stehen (Dokument „tour-haupt“); tour-bezogene Bausteine (TOUR_ONLY) nur auf Tourseiten,
die Dokumente „uebersicht“ und „statistik“ lehnen sie ab. 3.22.0: Bausteine der Statistik (STATISTIK_ONLY) stehen nur im Dokument „statistik“; die Bausteine der Übersicht dürfen auch dort stehen.
Unbekannte Typen (neuere Version) bleiben überall erlaubt.
Erinnerungen (3.32.0, Typ „erinn“, als Standard-Abschnitt der Übersicht unter cfg.erinn und als hinzugefügter Baustein): streng geprüfte Konfiguration, andere Felder sind nicht erlaubt:
  mode random|best|day|recent (Auswahl der Fotos)   n 3|6|9|12 (Anzahl)   view grid|strip|show (Darstellung)   ratio sq|43|169|orig (Seitenverhältnis)   size s|m|l (Größe der Bilder)
  height k|n|h (Höhe der Einzelbild-Show)   tempo 3|5|8|12 (Sekunden je Bild)   caption / shuffle / link  Ja-Nein (Bildunterschrift, Knopf „Neu mischen“, Link „Diashow starten“)
  sports, range, yr, title wie üblich. Gespeichert werden nur Abweichungen vom Standard (ohne cfg: 6 zufällige Fotos als Raster, mit Link zur Diashow).
Hinweis-Bausteine (3.23.0, „Alarm-Bausteine“: erscheinen nur, wenn etwas los ist; Typen hnziel, hnmeilenstein, hnauffaellig, hnpause, hnrekord, hnwoche, hnerholung, hnsicherung und die Sammel-Variante „hinweise“):
nur in „uebersicht“ und „statistik“ (hnauffaellig, hnpause, hnwoche, hnsicherung nur in „uebersicht“). Ihre Konfiguration wird streng geprüft, andere Felder sind nicht erlaubt:
  schwelle 1–90 (Prozent)   tage 1–365   min 1–1000   ziel / woche_ziel 0–100000   einheit / woche_einheit km|touren   stufe mehr|deutlich_mehr   ausblenden 0–90 (Tage, 0 = Knopf aus)
  arten [ziel, meilenstein, auffaellig, pause, rekord, woche, erholung, sicherung] (Sammel-Baustein)   sports, title wie üblich
  snoozes ["Art:Zeitstempel", …]  bis wann (Sekunden seit 1970, höchstens ein Jahr im Voraus) der Hinweis dieser Art ausgeblendet ist – je Instanz im Layout-Dokument gespeichert.
Statistik (3.22.0): Die Standard-Abschnitte der Statistikseite kennt nur die Oberfläche (order/hidden/closed/open/w gelten wie auf der Übersicht). Der globale Filter der Seite (Aktivität, Zeitraum)
steht in der Adresse der Seite, nicht im Layout. In der Konfiguration eines Bausteins heißt „eigen“ = true: der Baustein behält seinen eigenen Filter (sports, range, yr) statt des globalen.
Gemeinsame Filterfelder in der Konfiguration (3.19.0, streng geprüft; unbekannte Schlüssel einer neueren Version bleiben erlaubt, wenn sie einfache Werte haben):
  sports   [Sportart]      leer = alle Aktivitäten      range  year | y | 12m | 90d | all      yr  Jahr (bei range = y)
  metrics  [count|km|up|h] angezeigte Kennzahlen         compare  Vorjahresvergleich an/aus    title  eigener Titel (höchstens 60 Zeichen)
  n        1…10 (Anzahl Einträge)                        basis  sport | all | year (Vergleichsbasis der Tourseite)
Der Server speichert nur, was er prüfen kann (erlaubte Felder, Kennungen, Größe); welche Abschnitte es gibt, weiß die Oberfläche.
Ansichten (3.21.0): Ein Dokument je Seitenschlüssel kann statt des Layouts auch ein Behälter mit mehreren benannten Ansichten sein:
  {v: 2, views: [{id, name, layout: {…Layout-Dokument…}}], active: id, rules: {Sportart: id}}   (1 bis 12 Ansichten; „active“ = Standardansicht, „rules“ nur auf Tourseiten)
  Das alte Format (ein Layout-Dokument) bleibt gültig und wird beim Lesen als eine Ansicht „Standard“ (Kennung „standard“) geliefert (GET: Feld „container“; Feld „layout“ bleibt, wie gespeichert).
  Tourseite: Hauptseite und Auswertung sind zwei Schlüssel; die Ansichten (Kennungen, Namen, active, rules) werden von der Oberfläche in beiden Dokumenten gleich geführt,
  der Inhalt (layout) steht je Schlüssel für sich. Maßgeblich für Namen, Standardansicht und Regeln ist „tour-haupt“.
  POST /api/layout/check prüft eine Export-Datei (Ansicht als JSON) mit denselben Regeln wie beim Speichern und liefert das bereinigte Ergebnis oder klare Fehler.
Reisen (3.33.0): Bausteine der Reise-Detailseite (REISE_TYPEN: rkennzahl, rdiashow, rkmtag) stehen nur im Dokument „reise“, die der Reisen-Übersicht (REISEN_TYPEN: rnzahlen, rnjahre) nur in „reisen“.
Alle Bausteine anderer Seiten, die dort bekannt sind (Tour-, Statistik-, Hinweis-Bausteine, eigene Kennzahl, Erinnerungen), werden dort abgelehnt; unbekannte Typen (neuere Version) bleiben erlaubt.
Ihre Konfiguration wird streng geprüft (REISE_CFG: nur diese Felder, feste Auswahllisten). „rdiashow“ nimmt die Felder der Erinnerungen (mode, n, view, ratio, size, height, tempo, caption, shuffle, link, title), aber keine Filter:
den Zeitraum der Reise setzt die Oberfläche. Regeln nach Sportart (rules) gibt es nur auf der Tourseite.
Fotos und Karte (3.34.0): Bausteine der Fotos-Seite (FOTO_TYPEN: fkennzahl, fjahre) stehen nur im Dokument „fotos“, die der Karte (KARTE_TYPEN: kzahlen, kliste, klegende) nur in „karte“; alle Bausteine anderer
Seiten, die dort bekannt sind, werden abgelehnt (unbekannte Typen bleiben erlaubt). Konfiguration streng geprüft (nur feste Auswahllisten, plus Titel). Die Bedienfelder auf der Karte (Standort, Jahr, Aktivitäten,
Strecken-Stil, Heatmap und Fotos, Touren im Ausschnitt) sind Standard-Abschnitte der Seite (order/hidden/closed/open wie sonst). Betrachter und Regeln wie bei den anderen Seiten.
Zeitraum der Seite (3.34.0): der Zeitraum steht wie auf der Statistik im Feld „filter“ des Dokuments (range year|y|12m|90d|all|c, yr, from, to), jetzt auch im Dokument „uebersicht“ (ohne sports); ein Baustein behält seinen
eigenen Zeitraum mit „eigen“ = true (auch die Eigene Kennzahl, Feld „eigen“).
Betrachter dürfen lesen, bekommen aber immer den Standard (das Layout des Besitzers wird nicht übernommen) und dürfen nichts schreiben.
"""
import json
import re
import time

from fastapi import APIRouter, HTTPException, Request

from . import db, kennzahl

router = APIRouter()

KEYS = ("tour-haupt", "tour-auswertung", "uebersicht", "statistik", "reise", "reisen", "fotos", "karte")
NEUE_SEITEN = ("uebersicht", "statistik", "reise", "reisen", "fotos", "karte")                 # Seiten mit genau einem Dokument (ohne Regeln nach Sportart)
FIELDS = {"v", "order", "hidden", "closed", "open", "page", "widgets", "cfg", "w", "filter", "kopf"}
WIDTHS = ("voll", "zweidrittel", "halb", "drittel")
# Bausteine, die eine Tour brauchen (Typkennungen wie in static/js/50-bausteine.js und 51-bausteine-tour.js, fam "tour"): nicht in der Übersicht
TOUR_ONLY = frozenset(("kennzahlen", "tempo", "vergleich", "pulszonen", "wetter", "fotostreifen", "notiz", "splits", "steigung", "bewegung", "durchschnitt", "jahresrang",
                       "tageslicht", "gipfel", "vergleiche", "stimmung", "fotohighlights", "miniprofil", "steckbrief"))
# 3.22.0: Bausteine, die nur auf der Statistikseite stehen (Typkennungen wie in static/js/57-bausteine-statistik.js)
STATISTIK_ONLY = frozenset(("stmonate", "stentwicklung", "stlaengen", "sthoehe", "sttop"))
# 3.23.0: Hinweis-Bausteine (Typkennungen wie in static/js/58-bausteine-hinweise.js): nur auf Übersicht und Statistik, einige nur auf der Übersicht
HINWEIS_TYPEN = frozenset(("hnziel", "hnmeilenstein", "hnauffaellig", "hnpause", "hnrekord", "hnwoche", "hnerholung", "hnsicherung", "hinweise"))
HINWEIS_NUR_UEBERSICHT = frozenset(("hnauffaellig", "hnpause", "hnwoche", "hnsicherung"))
# 3.33.0: Bausteine der Reisen-Seiten (Typkennungen wie in static/js/61-bausteine-reise.js)
REISE_TYPEN = frozenset(("rkennzahl", "rdiashow", "rkmtag"))
REISEN_TYPEN = frozenset(("rnzahlen", "rnjahre"))
REISE_VALUES = {"rkennzahl": ("tage", "touren", "km", "up", "down", "h", "laender"), "rnzahlen": ("reisen", "tage", "km", "up", "laender"),
                "fkennzahl": ("fotos", "zugeordnet", "touren", "jahre", "orte"), "kzahlen": ("touren", "km", "up", "h")}
REISE_ENUM = {"rkmtag": {"metric": ("km", "up", "h", "count")}, "rnjahre": {"metric": ("km", "count", "days")},
              "kzahlen": {"basis": ("filter", "ausschnitt")}, "kliste": {"sort": ("date", "km", "up")}, "klegende": {"metric": ("count", "km")}}
REISE_NUM = {"fjahre": {"n": (5, 8, 12)}, "kliste": {"n": (5, 10, 20)}}
# 3.34.0: Bausteine der Fotos-Seite und der Karte (Typkennungen wie in static/js/63-fotoseiten.js und 64-kartenseite.js)
FOTO_TYPEN = frozenset(("fkennzahl", "fjahre"))
KARTE_TYPEN = frozenset(("kzahlen", "kliste", "klegende"))
SEITEN_TYPEN = {"reise": REISE_TYPEN, "reisen": REISEN_TYPEN, "fotos": FOTO_TYPEN, "karte": KARTE_TYPEN}          # Seitenschlüssel -> Bausteine, die nur dort stehen dürfen
ALLE_SEITEN_TYPEN = REISE_TYPEN | REISEN_TYPEN | FOTO_TYPEN | KARTE_TYPEN
HINWEIS_ARTEN = ("ziel", "meilenstein", "auffaellig", "pause", "rekord", "woche", "erholung", "sicherung")
SNOOZE_RE = re.compile(r"^([a-z]{3,12}):(\d{1,11})$")
MAX_SNOOZE_S = 366 * 86400                  # „Ausblenden“ höchstens ein Jahr im Voraus
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
MAX_IDS = 120
MAX_WIDGETS = 40
MAX_TEXT = 600                    # längster Text in der Konfiguration eines Bausteins (die Oberfläche begrenzt eigene Notizen auf 500)
MAX_BYTES = 24000
MAX_SPORTS = 20
SPORT_RE = re.compile(r"^[A-Za-z0-9_]{1,40}$")
RANGES = ("year", "y", "12m", "90d", "all")
METRICS = ("count", "km", "up", "h")
BASES = ("sport", "all", "year")
MAX_TITLE = 60
MAX_VIEWS = 12
MAX_NAME = 40
MAX_RULES = 40
MAX_TOTAL = 150000                # Gesamtgröße eines Behälters mit allen Ansichten
STD_ID = "standard"
STD_NAME = "Standard"
EXPORT_FORMAT = "meine-touren-ansicht"


def _ids(v, name):
    if not isinstance(v, list) or len(v) > MAX_IDS:
        raise HTTPException(400, f"„{name}“ muss eine Liste mit höchstens {MAX_IDS} Einträgen sein")
    out = []
    for x in v:
        if not isinstance(x, str) or not ID_RE.match(x):
            raise HTTPException(400, f"Ungültige Kennung in „{name}“")
        if x not in out:
            out.append(x)
    return out


KNOWN = ("sports", "range", "yr", "metrics", "compare", "title", "n", "basis", "eigen")


def _known(k, x):
    """Strenge Prüfung der gemeinsamen Filterfelder (3.19.0); gibt den bereinigten Wert zurück."""
    bad = HTTPException(400, f"Ungültiger Wert für „{k}“ in der Konfiguration")
    if k == "sports":
        if not isinstance(x, list) or len(x) > MAX_SPORTS or not all(isinstance(i, str) and SPORT_RE.match(i) for i in x):
            raise bad
        return list(dict.fromkeys(x))
    if k == "range":
        if x not in RANGES:
            raise bad
        return x
    if k == "yr":
        if isinstance(x, bool) or not isinstance(x, int) or not 1970 <= x <= 2100:
            raise bad
        return x
    if k == "metrics":
        if not isinstance(x, list) or not x or not all(i in METRICS for i in x):
            raise bad
        return list(dict.fromkeys(x))
    if k in ("compare", "eigen"):
        if not isinstance(x, bool):
            raise bad
        return x
    if k == "title":
        if not isinstance(x, str) or len(x) > MAX_TITLE:
            raise bad
        return x.strip()
    if k == "n":
        if isinstance(x, bool) or not isinstance(x, int) or not 1 <= x <= 10:
            raise bad
        return x
    if k == "basis":
        if x not in BASES:
            raise bad
        return x
    return None


FILTER_RANGES = RANGES + ("c",)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _filter(v):
    """Gespeicherter Filter einer Ansicht (3.22.0): {sports, range, yr, from, to}; „range“ y braucht yr, c braucht from und to (von <= bis)."""
    bad = HTTPException(400, "Ungültiger Filter der Ansicht")
    if not isinstance(v, dict) or set(v) - {"sports", "range", "yr", "from", "to"}:
        raise bad
    out = {}
    if "sports" in v:
        out["sports"] = _known("sports", v["sports"])
    r = v.get("range", "all")
    if r not in FILTER_RANGES:
        raise bad
    out["range"] = r
    if r == "y":
        out["yr"] = _known("yr", v.get("yr"))
    elif "yr" in v:
        raise bad
    if r == "c":
        a, b = v.get("from"), v.get("to")
        if not all(isinstance(x, str) and DATE_RE.match(x) for x in (a, b)) or a > b:
            raise bad
        out["from"], out["to"] = a, b
    elif "from" in v or "to" in v:
        raise bad
    return out


def _num(x, lo, hi, ganz, name):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or x != x or not lo <= x <= hi or (ganz and x != int(x)):
        raise HTTPException(400, f"Ungültiger Wert für „{name}“ in der Konfiguration")
    return int(x) if ganz else x


def _hinweis_cfg(k, x):
    """Strenge Prüfung der Felder der Hinweis-Bausteine (3.23.0); Rückgabe: bereinigter Wert."""
    bad = HTTPException(400, f"Ungültiger Wert für „{k}“ in der Konfiguration")
    if k == "schwelle":
        return _num(x, 1, 90, False, k)
    if k == "tage":
        return _num(x, 1, 365, True, k)
    if k == "min":
        return _num(x, 1, 1000, True, k)
    if k in ("ziel", "woche_ziel"):
        return _num(x, 0, 100000, False, k)
    if k == "ausblenden":
        return _num(x, 0, 90, True, k)
    if k in ("einheit", "woche_einheit"):
        if x not in ("km", "touren"):
            raise bad
        return x
    if k == "stufe":
        if x not in ("mehr", "deutlich_mehr"):
            raise bad
        return x
    if k == "arten":
        if not isinstance(x, list) or not x or not all(i in HINWEIS_ARTEN for i in x):
            raise bad
        return [a for a in HINWEIS_ARTEN if a in x]
    if k == "snoozes":                                  # ["art:Zeitstempel", …]: bis wann der Hinweis dieser Art ausgeblendet ist (Sekunden seit 1970)
        if not isinstance(x, list) or len(x) > len(HINWEIS_ARTEN):
            raise bad
        out, seen = [], set()
        for i in x:
            m = SNOOZE_RE.match(i) if isinstance(i, str) else None
            if not m or m.group(1) not in HINWEIS_ARTEN or m.group(1) in seen or int(m.group(2)) > time.time() + MAX_SNOOZE_S:
                raise bad
            seen.add(m.group(1))
            out.append(i)
        return out
    return None


ERINN_TYPE = "erinn"
ERINN_ENUM = {"mode": ("random", "best", "day", "recent"), "view": ("grid", "strip", "show"), "ratio": ("sq", "43", "169", "orig"), "size": ("s", "m", "l"), "height": ("k", "n", "h")}
ERINN_NUM = {"n": (3, 6, 9, 12), "tempo": (3, 5, 8, 12)}
ERINN_BOOL = ("caption", "shuffle", "link")


def _erinn_cfg(v):
    """Streng geprüfte Konfiguration der Kachel „Erinnerungen“ (3.32.0): feste Auswahllisten, keine fremden Felder."""
    if not isinstance(v, dict) or len(v) > 20:
        raise HTTPException(400, "Ungültige Konfiguration eines Bausteins")
    out = {}
    for k, x in v.items():
        bad = HTTPException(400, f"Ungültiger Wert für „{k}“ in der Konfiguration")
        if k in ("sports", "range", "yr", "title"):
            out[k] = _known(k, x)
        elif k in ERINN_ENUM:
            if not isinstance(x, str) or x not in ERINN_ENUM[k]:
                raise bad
            out[k] = x
        elif k in ERINN_NUM:
            if isinstance(x, bool) or not isinstance(x, int) or x not in ERINN_NUM[k]:
                raise bad
            out[k] = x
        elif k in ERINN_BOOL:
            if not isinstance(x, bool):
                raise bad
            out[k] = x
        else:
            raise HTTPException(400, f"Unbekannte Einstellung „{k}“ für diesen Baustein")
    if out.get("range") == "y" and "yr" not in out:
        raise HTTPException(400, "Ungültiger Wert für „range“ in der Konfiguration")
    if "yr" in out and out.get("range") != "y":
        raise HTTPException(400, "Ungültiger Wert für „yr“ in der Konfiguration")
    return out


def _reise_cfg(typ, v):
    """Streng geprüfte Konfiguration der Bausteine der Reisen-Seiten (3.33.0): feste Auswahllisten, nur Titel zusätzlich, keine fremden Felder."""
    if not isinstance(v, dict) or len(v) > 20:
        raise HTTPException(400, "Ungültige Konfiguration eines Bausteins")
    if typ == "rdiashow":
        if set(v) & {"sports", "range", "yr"}:
            raise HTTPException(400, "Die Reise-Diashow zeigt immer die Fotos der Reise (kein Filter nach Aktivität oder Zeitraum)")
        out = _erinn_cfg(v)
        if out.get("mode") == "day":
            raise HTTPException(400, "„An diesem Tag“ gibt es bei der Reise-Diashow nicht (es sind immer die Fotos der Reise)")
        return out
    out = {}
    for k, x in v.items():
        bad = HTTPException(400, f"Ungültiger Wert für „{k}“ in der Konfiguration")
        if k == "title":
            out[k] = _known(k, x)
        elif k == "values" and typ in REISE_VALUES:
            if not isinstance(x, list) or not x or not all(i in REISE_VALUES[typ] for i in x):
                raise bad
            out[k] = [a for a in REISE_VALUES[typ] if a in x]
        elif k in REISE_ENUM.get(typ, {}):
            if not isinstance(x, str) or x not in REISE_ENUM[typ][k]:
                raise bad
            out[k] = x
        elif k in REISE_NUM.get(typ, {}):
            if isinstance(x, bool) or not isinstance(x, int) or x not in REISE_NUM[typ][k]:
                raise bad
            out[k] = x
        else:
            raise HTTPException(400, f"Unbekannte Einstellung „{k}“ für diesen Baustein")
    return out


HINWEIS_KEYS = ("schwelle", "tage", "min", "ziel", "ausblenden", "einheit", "stufe", "arten", "snoozes", "woche_ziel", "woche_einheit")


def _cfg(v, typ=None):
    if typ == ERINN_TYPE:
        return _erinn_cfg(v)
    if typ in ALLE_SEITEN_TYPEN:                          # 3.33.0 / 3.34.0: Bausteine der Reisen-, Fotos- und Karten-Seite (feste Auswahllisten)
        return _reise_cfg(typ, v)
    if typ == kennzahl.TYPE:                              # 3.28.0: eigene Kennzahl – nur Auswahlen aus festen Listen, streng geprüft (app/kennzahl.py)
        return kennzahl.clean_cfg(v)
    if not isinstance(v, dict) or len(v) > 20:
        raise HTTPException(400, "Ungültige Konfiguration eines Bausteins")
    out = {}
    hn = typ in HINWEIS_TYPEN
    for k, x in v.items():
        if not isinstance(k, str) or not ID_RE.match(k):
            raise HTTPException(400, "Ungültiger Schlüssel in der Konfiguration")
        if hn:                                           # Hinweis-Bausteine: nur diese Felder (plus Aktivität und Titel), jedes streng geprüft
            if k in HINWEIS_KEYS:
                out[k] = _hinweis_cfg(k, x)
            elif k in ("sports", "title"):
                out[k] = _known(k, x)
            else:
                raise HTTPException(400, f"Unbekannte Einstellung „{k}“ für diesen Baustein")
            continue
        if k in KNOWN:
            out[k] = _known(k, x)
            continue
        if isinstance(x, str):
            if len(x) > MAX_TEXT:
                raise HTTPException(400, "Text zu lang")
            out[k] = x
        elif isinstance(x, (bool, int, float)) or x is None:
            out[k] = x
        elif isinstance(x, list) and len(x) <= 20 and all(isinstance(i, str) and len(i) <= 40 for i in x):
            out[k] = x
        else:
            raise HTTPException(400, "Ungültiger Wert in der Konfiguration")
    return out


def clean(doc, key=None):
    """Prüft ein Layout-Dokument und gibt die bereinigte Fassung zurück (HTTPException 400 bei Fehlern)."""
    if not isinstance(doc, dict):
        raise HTTPException(400, "Das Layout muss ein JSON-Objekt sein")
    extra = set(doc) - FIELDS
    if extra:
        raise HTTPException(400, "Unbekannte Felder: " + ", ".join(sorted(map(str, extra))))
    out = {"v": 1}
    for k in ("order", "hidden", "closed", "open"):
        if k in doc:
            out[k] = _ids(doc[k], k)
    if "page" in doc:
        p = doc["page"]
        if not isinstance(p, dict) or len(p) > MAX_IDS:
            raise HTTPException(400, "„page“ muss ein Objekt sein")
        for k, x in p.items():
            if not ID_RE.match(str(k)) or x not in ("haupt", "auswertung"):
                raise HTTPException(400, "Ungültige Seite in „page“")
        out["page"] = dict(p)
    if "w" in doc:
        b = doc["w"]
        if not isinstance(b, dict) or len(b) > MAX_IDS or not all(isinstance(k, str) and ID_RE.match(k) for k in b):
            raise HTTPException(400, "„w“ muss ein Objekt mit Kennungen sein")
        if any(x not in WIDTHS for x in b.values()):
            raise HTTPException(400, "Ungültige Breite in „w“ (erlaubt: " + ", ".join(WIDTHS) + ")")
        out["w"] = dict(b)
    if "widgets" in doc:
        w = doc["widgets"]
        if not isinstance(w, list) or len(w) > MAX_WIDGETS:
            raise HTTPException(400, f"Höchstens {MAX_WIDGETS} Bausteine je Seite")
        seen, ws = set(), []
        for x in w:
            if not isinstance(x, dict) or set(x) - {"id", "type", "cfg"}:
                raise HTTPException(400, "Ungültiger Baustein")
            if not isinstance(x.get("id"), str) or not ID_RE.match(x["id"]) or not isinstance(x.get("type"), str) or not ID_RE.match(x["type"]):
                raise HTTPException(400, "Ungültige Kennung eines Bausteins")
            if x["id"] in seen:
                raise HTTPException(400, "Doppelte Kennung eines Bausteins")
            if key in SEITEN_TYPEN:                          # 3.33.0 / 3.34.0: auf Reisen-, Fotos- und Karten-Seiten nur deren eigene Bausteine (bekannte fremde werden abgelehnt, unbekannte bleiben erlaubt)
                fremd = TOUR_ONLY | STATISTIK_ONLY | HINWEIS_TYPEN | {kennzahl.TYPE, ERINN_TYPE} | (ALLE_SEITEN_TYPEN - SEITEN_TYPEN[key])
                if x["type"] in fremd:
                    raise HTTPException(400, "Dieser Baustein gehört nicht auf diese Seite")
            elif x["type"] in ALLE_SEITEN_TYPEN:
                raise HTTPException(400, "Dieser Baustein gehört zu einer anderen Seite (Reisen, Fotos oder Karte) und kann nur dort stehen")
            if key in ("uebersicht", "statistik") and x["type"] in TOUR_ONLY:
                raise HTTPException(400, "Dieser Baustein gehört zu einer Tour und kann nicht in der Übersicht oder Statistik stehen")
            if key not in (None, "statistik") and x["type"] in STATISTIK_ONLY:
                raise HTTPException(400, "Dieser Baustein gehört zur Statistik und kann nur dort stehen")
            if x["type"] in HINWEIS_TYPEN and key in ("tour-haupt", "tour-auswertung"):
                raise HTTPException(400, "Hinweis-Bausteine gibt es nur auf der Übersicht und der Statistik")
            if x["type"] in HINWEIS_NUR_UEBERSICHT and key == "statistik":
                raise HTTPException(400, "Dieser Hinweis-Baustein gibt es nur auf der Übersicht")
            if x["type"] == kennzahl.TYPE and key in ("tour-haupt", "tour-auswertung"):
                raise HTTPException(400, "Eigene Kennzahlen gibt es nur auf der Übersicht und der Statistik")
            seen.add(x["id"])
            ws.append({"id": x["id"], "type": x["type"], "cfg": _cfg(x.get("cfg") or {}, x["type"])})
        out["widgets"] = ws
    if "filter" in doc:
        out["filter"] = _filter(doc["filter"])
    if "kopf" in doc:
        k = doc["kopf"]
        if not isinstance(k, dict) or set(k) - {"holen"} or not all(isinstance(x, bool) for x in k.values()):
            raise HTTPException(400, "„kopf“ darf nur {\"holen\": true|false} enthalten")
        if k.get("holen") is False:                         # nur die Abweichung vom Standard (an) wird gespeichert
            out["kopf"] = {"holen": False}
    if "cfg" in doc:
        c = doc["cfg"]
        if not isinstance(c, dict) or len(c) > 10 or not all(isinstance(k, str) and ID_RE.match(k) for k in c):
            raise HTTPException(400, "„cfg“ muss ein Objekt mit höchstens 10 Einträgen sein")
        out["cfg"] = {k: _cfg(x, ERINN_TYPE if k == ERINN_TYPE else None) for k, x in c.items()}
    if len(json.dumps(out, ensure_ascii=False)) > MAX_BYTES:
        raise HTTPException(400, "Das Layout ist zu groß")
    return out


def _name(x):
    if not isinstance(x, str) or re.search(r"[\x00-\x1f\x7f<>]", x) or not 1 <= len(x.strip()) <= MAX_NAME:
        raise HTTPException(400, f"Der Name einer Ansicht muss 1 bis {MAX_NAME} Zeichen lang sein (ohne Steuer- und Spitzklammern)")
    return " ".join(x.split())


def clean_container(doc, key=None):
    """Prüft einen Behälter mit Ansichten und gibt die bereinigte Fassung zurück."""
    extra = set(doc) - {"v", "views", "active", "rules"}
    if extra:
        raise HTTPException(400, "Unbekannte Felder: " + ", ".join(sorted(map(str, extra))))
    vs = doc.get("views")
    if not isinstance(vs, list) or not 1 <= len(vs) <= MAX_VIEWS:
        raise HTTPException(400, f"Eine Seite hat 1 bis {MAX_VIEWS} Ansichten")
    views, ids = [], set()
    for x in vs:
        if not isinstance(x, dict) or set(x) - {"id", "name", "layout"}:
            raise HTTPException(400, "Ungültige Ansicht")
        i = x.get("id")
        if not isinstance(i, str) or not ID_RE.match(i):
            raise HTTPException(400, "Ungültige Kennung einer Ansicht")
        if i in ids:
            raise HTTPException(400, "Doppelte Kennung einer Ansicht")
        ids.add(i)
        views.append({"id": i, "name": _name(x.get("name")), "layout": clean(x.get("layout") if x.get("layout") is not None else {}, key)})
    act = doc.get("active", views[0]["id"])
    if act not in ids:
        raise HTTPException(400, "Die Standardansicht („active“) gibt es nicht")
    out = {"v": 2, "views": views, "active": act}
    if "rules" in doc:
        r = doc["rules"]
        if not isinstance(r, dict) or len(r) > MAX_RULES:
            raise HTTPException(400, "„rules“ muss ein Objekt mit höchstens %d Regeln sein" % MAX_RULES)
        if r and key in NEUE_SEITEN:
            raise HTTPException(400, "Regeln nach Sportart gibt es nur auf der Tourseite")
        for k, x in r.items():
            if not isinstance(k, str) or not SPORT_RE.match(k):
                raise HTTPException(400, "Ungültige Sportart in „rules“")
            if x not in ids:
                raise HTTPException(400, "Eine Regel verweist auf eine Ansicht, die es nicht gibt")
        out["rules"] = dict(r)
    if len(json.dumps(out, ensure_ascii=False)) > MAX_TOTAL:
        raise HTTPException(400, "Die Ansichten sind zusammen zu groß")
    return out


def clean_any(doc, key=None):
    """Altes Format (ein Layout-Dokument) oder Behälter mit Ansichten."""
    if isinstance(doc, dict) and "views" in doc:
        return clean_container(doc, key)
    return clean(doc, key)


def normalize(stored):
    """Gespeichertes Dokument (altes oder neues Format) als Behälter; None, wenn nichts gespeichert ist."""
    if not isinstance(stored, dict):
        return None
    if isinstance(stored.get("views"), list):
        return stored
    return {"v": 2, "views": [{"id": STD_ID, "name": STD_NAME, "layout": stored}], "active": STD_ID, "rules": {}}


def _stats(lay):
    return {"order": len(lay.get("order", [])), "hidden": len(lay.get("hidden", [])), "widgets": len(lay.get("widgets", [])), "types": sorted({w["type"] for w in lay.get("widgets", [])})}


def check_export(doc):
    """Prüft die Export-Datei einer Ansicht. Rückgabe: {ok, errors, ignored, name, page, layouts, stats}; Fehler machen die Datei unbrauchbar, Unbekanntes auf oberster Ebene wird ignoriert."""
    errors, ignored, layouts = [], [], {}
    res = {"ok": False, "errors": errors, "ignored": ignored, "name": "", "page": "", "layouts": layouts, "stats": {}}
    if not isinstance(doc, dict):
        errors.append("Die Datei enthält kein JSON-Objekt.")
        return res
    if doc.get("format") != EXPORT_FORMAT:
        errors.append("Das ist keine Datei mit einer exportierten Ansicht aus „Meine Touren“.")
        return res
    fv = doc.get("format_version")
    if isinstance(fv, bool) or not isinstance(fv, int) or fv < 1:
        errors.append("Die Formatversion der Datei fehlt oder ist ungültig.")
        return res
    if fv > 1:
        errors.append(f"Die Datei stammt aus einer neueren Version von „Meine Touren“ (Format {fv}) und kann hier nicht gelesen werden.")
        return res
    page = doc.get("page")
    if page not in ("tour",) + NEUE_SEITEN:
        errors.append("Die Datei nennt keine gültige Seite (erlaubt: tour, uebersicht, statistik, reise, reisen, fotos, karte).")
        return res
    res["page"] = page
    try:
        res["name"] = _name(doc.get("name"))
    except HTTPException as e:
        errors.append(e.detail)
    keys = ("tour-haupt", "tour-auswertung") if page == "tour" else (page,)
    lays = doc.get("layouts")
    if not isinstance(lays, dict):
        errors.append("Die Datei enthält keine Layouts.")
        return res
    for k in lays:
        if k not in keys:
            ignored.append(f"Unbekannter Eintrag „{str(k)[:40]}“ in den Layouts wird ignoriert.")
    for k in keys:
        try:
            layouts[k] = clean(lays.get(k) if lays.get(k) is not None else {}, k)
            res["stats"][k] = _stats(layouts[k])
        except HTTPException as e:
            errors.append(f"{k}: {e.detail}")
    for k in set(doc) - {"format", "format_version", "app_version", "page", "name", "exported", "layouts"}:
        ignored.append(f"Unbekanntes Feld „{str(k)[:40]}“ wird ignoriert.")
    res["ok"] = not errors
    if errors:
        res["layouts"] = {}
    return res


def _key(k):
    if k not in KEYS:
        raise HTTPException(404, "Unbekannte Seite")
    return k


def _viewer(request: Request):
    u = getattr(request.state, "user", None)
    return bool(u and u.get("role") == "viewer")


@router.get("/api/layout/{page_key}")
def get_layout(page_key: str, request: Request):
    _key(page_key)
    if _viewer(request):
        return {"key": page_key, "layout": None, "container": None, "ts": None, "default": True}
    r = db.one("SELECT json,ts FROM user_layout WHERE page_key=?", (page_key,))
    if not r:
        return {"key": page_key, "layout": None, "container": None, "ts": None}
    try:
        lay = json.loads(r["json"])
    except ValueError:
        lay = None
    return {"key": page_key, "layout": lay, "container": normalize(lay), "ts": r["ts"]}


@router.put("/api/layout/{page_key}")
async def put_layout(page_key: str, request: Request):
    _key(page_key)
    if _viewer(request):
        raise HTTPException(403, "Dieser Zugang darf nur ansehen")
    raw = await request.body()
    try:
        body = json.loads(raw or b"null")
    except ValueError:
        if len(raw) > MAX_BYTES * 2:
            raise HTTPException(413, "Das Layout ist zu groß")
        raise HTTPException(400, "Kein gültiges JSON")
    if isinstance(body, dict) and isinstance(body.get("layout"), dict) and set(body) <= {"layout", "key", "ts"}:
        body = body["layout"]                          # {"layout": {...}} wird wie das Dokument selbst angenommen
    if len(raw) > (MAX_TOTAL + 20000 if isinstance(body, dict) and "views" in body else MAX_BYTES * 2):
        raise HTTPException(413, "Das Layout ist zu groß")
    lay = clean_any(body, page_key)
    mine = kennzahl.zaehle(lay)
    if mine:                                           # 3.28.0: höchstens so viele eigene Kennzahlen je Benutzer (über alle Seiten und Ansichten, ohne die Seite, die gerade ersetzt wird)
        for k in KEYS:
            if k != page_key:
                r = db.one("SELECT json FROM user_layout WHERE page_key=?", (k,))
                try:
                    mine |= kennzahl.zaehle(json.loads(r["json"])) if r else set()
                except ValueError:
                    pass
        if len(mine) > kennzahl.MAX_PRO_NUTZER:
            raise HTTPException(400, f"Höchstens {kennzahl.MAX_PRO_NUTZER} eigene Kennzahlen sind möglich")
    ts = int(time.time())
    db.execute("INSERT INTO user_layout(page_key,json,ts) VALUES(?,?,?) ON CONFLICT(page_key) DO UPDATE SET json=excluded.json, ts=excluded.ts",
               (page_key, json.dumps(lay, ensure_ascii=False, separators=(",", ":")), ts))
    return {"ok": True, "key": page_key, "layout": lay, "ts": ts}


@router.post("/api/layout/check")
async def post_check(request: Request):
    if _viewer(request):
        raise HTTPException(403, "Dieser Zugang darf nur ansehen")
    raw = await request.body()
    if len(raw) > 2 * MAX_BYTES * 2 + 2000:
        r = check_export(None)
        r["errors"] = ["Die Datei ist zu groß für eine Ansicht."]
        return r
    try:
        doc = json.loads(raw or b"null")
    except ValueError:
        r = check_export(None)
        r["errors"] = ["Die Datei ist kein gültiges JSON."]
        return r
    return check_export(doc)


@router.delete("/api/layout/{page_key}")
def delete_layout(page_key: str, request: Request):
    _key(page_key)
    if _viewer(request):
        raise HTTPException(403, "Dieser Zugang darf nur ansehen")
    db.execute("DELETE FROM user_layout WHERE page_key=?", (page_key,))
    return {"ok": True, "key": page_key}
