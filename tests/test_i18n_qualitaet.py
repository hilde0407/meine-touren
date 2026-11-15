"""3.24.0 – Qualität der Übersetzungstabelle (00-i18n-neu.js, Versionen 3.10 bis 3.23 und alles davor): alle vier Sprachen vorhanden, nicht leer,
Platzhalter ({}) und Zahlen in allen Sprachen gleich, keine deutschen Reste in Englisch, Französisch und Spanisch (außer Eigennamen und Lehnwörtern aus der Whitelist)."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "00-i18n-neu.js"

# Wörter, die in mehreren Sprachen gleich geschrieben werden oder Eigennamen sind: dürfen auch in en/fr/es vorkommen
WHITELIST = {"komoot", "strava", "zepp", "garmin", "amazfit", "gpx", "fit", "tour", "touren", "pdf", "hdr", "html", "json", "zip", "osm", "wlan", "wi", "fi", "online",
             "offline", "start", "ziel", "meilen", "meine", "alpen", "gps", "api", "id", "km", "min", "app", "name", "status", "text", "mit", "kölsch"}
# unverwechselbar deutsche Wörter (Funktionswörter und häufige Begriffe der Oberfläche)
DE = {"und", "nicht", "oder", "wird", "werden", "wurde", "wurden", "ist", "sind", "für", "über", "mehr", "keine", "kein", "dein", "deine", "deiner", "deinen", "deinem", "bitte",
      "seite", "ansicht", "ansichten", "baustein", "bausteine", "hinweis", "hinweise", "zeigt", "wenn", "dann", "auch", "noch", "nur", "diese", "dieser", "dieses", "diesen",
      "einen", "einer", "eines", "einem", "alle", "aller", "einstellungen", "löschen", "speichern", "abbrechen", "schließen", "öffnen", "anzeigen", "ausblenden", "einblenden",
      "höhenmeter", "strecke", "tage", "woche", "monat", "jahr", "datei", "fehler", "wieder", "gespeichert", "geändert", "hinzufügen", "entfernen", "zurück", "weiter", "oben",
      "unten", "links", "rechts", "alle", "ohne", "sich", "wir", "sie", "ihr", "ihre", "der", "die", "das", "den", "dem", "des", "von", "zum", "zur", "bei", "nach", "aus", "auf",
      "wie", "was", "wer", "wo", "weil", "aber", "sondern", "bis", "seit", "oder", "sowie", "zwischen", "durch", "gegen", "unter", "vor", "als", "kann", "können", "muss", "müssen"}
# Wörter der Liste, die in Englisch, Französisch oder Spanisch regulär vorkommen (kein deutscher Rest)
AMBIG = {"die", "des", "an", "vor", "sie", "sich", "was", "wo", "wie", "bis", "als", "auf", "aus", "den", "dem", "der", "das", "von", "wir", "ihr", "bei", "unter", "muss", "kann", "mehr",
         "oben", "links", "rechts", "alle", "sondern", "weil", "name", "ohne", "tage", "datei", "diese", "dann", "wird", "auch", "nach", "wer", "zum", "zur", "durch", "gegen"}
STRONG = DE - AMBIG


def _rows():
    body = SRC.read_text(encoding="utf8").split("window.I18N_NEU = `", 1)[1].rsplit("`", 1)[0]
    return [r for r in body.split("\n") if r.strip()]


def _cols(r):
    return [c.strip() for c in r.split(" || ")]


def _key(c):
    return c.split(" @@ ")[-1] if " @@ " in c else c


def test_alle_sprachen_vorhanden_und_nicht_leer():
    bad = [r[:70] for r in _rows() if len(_cols(r)) != 4 or not all(_cols(r))]
    assert not bad, bad[:10]


def test_platzhalter_und_zahlen_gleich():
    bad = []
    for r in _rows():
        c = [_key(x) for x in _cols(r)]
        if len(c) != 4:
            continue
        n = c[0].count("{}")
        if any(x.count("{}") != n for x in c[1:]):
            bad.append(("Platzhalter", r[:70]))
        digits = sorted(re.findall(r"\d+", c[0].replace("{}", "")))
        for x in c[1:]:
            if sorted(re.findall(r"\d+", x.replace("{}", ""))) != digits:
                bad.append(("Zahlen", r[:70]))
                break
    assert not bad, bad[:10]


def test_keine_deutschen_reste_in_en_fr_es():
    bad = []
    for r in _rows():
        c = _cols(r)
        if len(c) != 4:
            continue
        for lang, x in zip(("en", "fr", "es"), c[1:]):
            words = {w.lower() for w in re.findall(r"[A-Za-zÄÖÜäöüß]+", x.replace("{}", " "))} - WHITELIST
            hit = words & STRONG
            if lang != "fr" and re.search(r"[äöüß]", x):
                hit |= {w for w in words if re.search(r"[äöüß]", w)}
            if lang == "fr" and re.search(r"[äöß]", x):
                hit |= {w for w in words if re.search(r"[äöß]", w)}
            if hit and x != c[0]:
                bad.append((lang, sorted(hit), r[:60]))
    assert not bad, bad[:15]
