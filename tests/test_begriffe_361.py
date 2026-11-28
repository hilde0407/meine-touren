"""3.61.0 – Begriffe und Bedienlogik (docs/LEITFADEN-BEGRIFFE.md): die Wörter, die Tabelle 1 des Leitfadens ersetzt hat, dürfen in den sichtbaren deutschen Texten nicht
wieder auftauchen. Geprüft werden alle String-Literale der Oberfläche (app/static/js/*.js ohne die Übersetzungstabellen 00-i18n*, Kommentare ausgenommen), die Texte der
HTML-Seiten und die Texte des Servers (Strings in app/*.py ohne Docstrings: Meldungen, PDFs, E-Mails, Benachrichtigungen), dazu das Handbuch.

Ausnahmen stehen unten in AUSNAHMEN – jede mit Grund (Dienstnamen, echte andere Bedeutung). Neue Ausnahmen nur mit Begründung; im Zweifel den Text ändern.
Dazu Regeln der Bedienlogik, die sich am Quelltext prüfen lassen: keine Browser-Fenster (prompt/confirm/alert), kein „OK“/„Übernehmen“/„Anwenden“ als Knopf,
„Standard wiederherstellen“ statt „Zurücksetzen“/„Standardwerte“/„Vorgabe wiederherstellen“, Mehrzahl ausgeschrieben statt „Foto(s)“."""
import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "app" / "static" / "js"

# Muster -> Wort laut Leitfaden (Tabelle 1)
VERBOTEN = {
    r"\bTour(en)? aufnehm|\bAufnehmen einer Tour|\bbeim Aufnehmen\b|\bAufnahme läuft\b|\bTracking\b": "aufzeichnen / Aufzeichnung (GPS)",
    r"\bTags\b|\bSchlagworte[n]?\b|\bLabels?\b": "Schlagwort / Schlagwörter",
    r"\bRekord": "Bestwerte",
    r"\bHöhenmeter\b|\bAnstieg\b": "Aufstieg",
    r"Gesamtzeit|Zeit unterwegs|Stunden unterwegs|Zeit in Bewegung|Tage unterwegs": "Dauer / Bewegungszeit / aktive Tage",
    r"\bTage mit Touren?\b": "aktive Tage",
    r"\bDistanz\b": "Strecke",
    r"\bPläne\b|\b[Ii]m Plan\b|[Hh]inter dem Plan|Vor dem Plan|Planungen\b": "geplante Tour / Planung / im Soll",
    r"\bBackups?\b|Datensicherung": "Sicherung",
    r"Seitenlayout": "Ansicht",
    r"Alle Jahre": "Gesamte Zeit",
    r"\(zusammengefasst\)": "Statistik-Gruppe („Name = A + B“)",
    r"\bDashboard\b": "Übersicht",
    r"Favoriten für|optgroup label=\"Favoriten\"": "Favoriten-Sportarten",
    r"\bWorkouts?\b": "Tour (außer als Dienstname)",
    r"Als GPX speichern|GPX-Datei laden|Höhen korrigieren|Höhe aus (der )?Uhr abgleichen|Höhe abgleichen|Höhe\w* \w+ abgleichen": "„Höhe korrigieren“ / exportieren",
    r"\bsynchronisier|\bSync\b": "abgleichen",
    r"Routen laden": "holen (Verwaltung → Touren holen → Komoot „Fehlende Strecken holen“)",
    r"Angemeldet als": "„Verbunden mit …“",
    r"Jahres-Rückblick": "Jahresrückblick",
    r"Gespeichert ✓|✓ Gespeichert|gespeichert ✓|^Gespeichert\.?$|✓ Kopiert|✓ Geändert": "„<Sache> gespeichert“ (ohne ✓, ohne Punkt)",
    r"\bAktivität(en)?\b": "Sportart bzw. Tour (Aktivität nur als Name eines Dienstes)",
    r"Verwaltung → Portale\b|Verwaltung → (Garmin|Suunto|Zepp|Komoot|Update|Sicherung|Protokoll|Standort teilen)\b(?! &)": "Wegangabe „Verwaltung → Reiter → Bereich“",
    r"\w\((s|e|n|en)\)\s": "Mehrzahl ausschreiben (fmtAnzahl)",
    r"\d+ Bilder\b|\bBilder,? \d+ einer Tour|Neuer Tag\b": "Foto / Fotos bzw. Schlagwort (3.71.0)",
    r"aus Meine Touren entfernt": "„gelöscht“ (Löschen = Daten sind weg, Leitfaden 2.2)",
}
# Genaue Knopf- bzw. Literaltexte, die es nicht mehr gibt
VERBOTEN_GANZ = {
    "OK": "Hauptaktion benennen (Leitfaden 2.1)", "Übernehmen": "Hauptaktion benennen", "Anwenden": "Hauptaktion benennen", "Trennen": "„Verbindung trennen“",
    "Zurücksetzen": "„Standard wiederherstellen“", "Standardwerte": "„Standard wiederherstellen“", "Vorgabe wiederherstellen": "„Standard wiederherstellen“",
    "Alle Tags": "„Alle Schlagwörter“", "alle Sportarten": "„Alle Sportarten“", "Rückblicke": "„Jahresrückblicke“",
}

# (Datei, Muster im Text) -> Grund. Muster ist ein regulärer Ausdruck, der den ganzen erlaubten Ausschnitt trifft.
AUSNAHMEN = [
    ("05-verwaltung.js", r"Aktivitäten werden <b>lokal</b>|viele Aktivitäten enthalten|einzelne Aktivität|Aktivität öffnen|Aktivitäten übernommen", "Garmin nennt seine Datensätze „Aktivitäten“ (Dienstname)"),
    ("57-bausteine-statistik.js", r"deine Aktivität|deiner Aktivität", "körperliche Aktivität (WHO-Einordnung) – andere Bedeutung als „Sportart“"),
    ("devices.py", r"Aktivität\w*", "Garmin-/Suunto-Datensätze heißen beim Dienst „Aktivitäten“"),
    ("fitfile.py", r"Aktivität\w*", "FIT-Dateityp „activity“ (Name im Dateiformat)"),
    ("portals.py", r"Aktivitäten|Workout", "Komoot-/Strava-Begriffe („Aktivitäten hochladen“, Strava-Sportart „Workout“)"),
    ("komoot_paket.py", r"Aktivität\w*", "Komoot-Begriff in der Anleitung zum Hochladen"),
    ("sync.py", r"Workout--", "Dateiname im Zepp-Export (intern)"),
    ("zepp.py", r"\bhm\b|x-hm|hm\.health|hm-registration", "Kennungen der Zepp-Schnittstelle"),
    ("wiederherstellung.py", r"Backup", "liest INFO.txt älterer Sicherungen („Meine Touren Backup …“)"),
    ("db.py", r"synchronous", "SQLite-PRAGMA"),
    ("11-benutzer.js", r"Zurücksetzen", "Passwort zurücksetzen (Kontofunktion, kein Standard)"),
    ("35-sicherheit.js", r"Zurücksetzen", "Passwort zurücksetzen (Kontofunktion, kein Standard)"),
    ("security.py", r"[Zz]urücksetzen", "Passwort zurücksetzen (Kontofunktion, kein Standard)"),
    ("portals.py", r"Zurücksetzen auf „privat“", "Sichtbarkeit bei Komoot"),
    ("65-zeitraum.js", r"Zurücksetzen", "Zeitraum-Leiste: setzt den vorübergehend gewählten Zeitraum der Seite zurück (Filter, kein gespeicherter Standard)"),
]
UI_EXT = (".js", ".html")


def _js_strings(src):
    """String-Literale (Template-Teile ohne ${…}) eines JS-Quelltexts, ohne Kommentare und Regex-Literale."""
    out, n = [], len(src)

    def tpl(i):
        buf = []
        while i < n:
            c = src[i]
            if c == "\\":
                buf.append(src[i:i + 2]); i += 2; continue
            if c == "`":
                out.append("".join(buf)); return i + 1
            if c == "$" and src[i + 1:i + 2] == "{":
                out.append("".join(buf)); buf = []
                i = code(i + 2, True); continue
            buf.append(c); i += 1
        return i

    def code(i, inner):
        depth, prev = 0, ""
        while i < n:
            c = src[i]
            if c == "/" and src[i + 1:i + 2] == "/":
                j = src.find("\n", i); i = n if j < 0 else j; continue
            if c == "/" and src[i + 1:i + 2] == "*":
                i = src.find("*/", i) + 2; continue
            if c in "'\"":
                j, buf = i + 1, []
                while j < n and src[j] != c and src[j] != "\n":
                    if src[j] == "\\":
                        buf.append(src[j:j + 2]); j += 2; continue
                    buf.append(src[j]); j += 1
                out.append("".join(buf)); i = j + 1; continue
            if c == "`":
                i = tpl(i + 1); continue
            if c == "/" and prev and prev in "(,=:[!&|?{};+":
                j, cls = i + 1, False
                while j < n and src[j] != "\n":
                    if src[j] == "\\":
                        j += 2; continue
                    if src[j] == "[":
                        cls = True
                    elif src[j] == "]":
                        cls = False
                    elif src[j] == "/" and not cls:
                        break
                    j += 1
                i, prev = j + 1, "x"; continue
            if inner and c == "{":
                depth += 1
            if inner and c == "}":
                if depth == 0:
                    return i + 1
                depth -= 1
            if not c.isspace():
                prev = c
            i += 1
        return i

    code(0, False)
    return out


def _py_strings(src):
    tree, doc = ast.parse(src), set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.body and isinstance(node.body[0], ast.Expr) \
                and isinstance(getattr(node.body[0], "value", None), ast.Constant):
            doc.add(id(node.body[0].value))
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc]


def _html_texts(src):
    src = re.sub(r"<script[\s\S]*?</script>|<style[\s\S]*?</style>|<!--[\s\S]*?-->", "", src)
    return [m.group(1) or m.group(2) for m in re.finditer(r">([^<]+)<|(?:title|placeholder|aria-label|alt)=\"([^\"]*)\"", src) if (m.group(1) or m.group(2) or "").strip()]


def texte():
    for p in sorted(JS.glob("*.js")):
        if not p.name.startswith("00-i18n"):
            for t in _js_strings(p.read_text(encoding="utf-8")):
                yield p.name, t
    for p in sorted((ROOT / "app" / "static").glob("*.html")):
        for t in _html_texts(p.read_text(encoding="utf-8")):
            yield p.name, t
    for p in sorted((ROOT / "app").glob("*.py")):
        for t in _py_strings(p.read_text(encoding="utf-8")):
            yield p.name, t


def _erlaubt(datei, text, treffer):
    for f, muster, _grund in AUSNAHMEN:
        if f == datei and any(m.start() < treffer.end() and treffer.start() < m.end() for m in re.finditer(muster, text)):     # Ausnahme überlappt den Fund
            return True
    return False


def test_keine_entfallenen_begriffe_in_sichtbaren_texten():
    funde = []
    for datei, text in texte():
        for muster, wort in VERBOTEN.items():
            for m in re.finditer(muster, text, re.M):
                if not _erlaubt(datei, text, m):
                    funde.append(f"{datei}: „{m.group(0)}“ → {wort}: {text.strip()[:110]!r}")
    assert not funde, "\n".join(sorted(set(funde))[:60])


def test_keine_alten_knopftexte():
    funde = []
    for datei, text in texte():
        t = text.strip()
        if datei.endswith(".py"):
            continue
        if t in VERBOTEN_GANZ:
            m = re.match(re.escape(t), t)
            if not _erlaubt(datei, t, m):
                funde.append(f"{datei}: „{t}“ → {VERBOTEN_GANZ[t]}")
        for m in re.finditer(r">\s*(OK|Übernehmen|Anwenden|Trennen|Zurücksetzen|Standardwerte)\s*</button>", text):
            if not _erlaubt(datei, text, m):
                funde.append(f"{datei}: Knopf „{m.group(1)}“")
        for m in re.finditer(r"\bok: \"(OK|Übernehmen|Anwenden|Trennen|Zurücksetzen)\"", text):
            funde.append(f"{datei}: ok „{m.group(1)}“")
    for p in sorted(JS.glob("*.js")):
        if p.name.startswith("00-i18n"):
            continue
        for m in re.finditer(r"\bok: \"(OK|Übernehmen|Anwenden|Trennen|Zurücksetzen)\"", p.read_text(encoding="utf-8")):
            funde.append(f"{p.name}: uiConfirm ok „{m.group(1)}“")
    assert not funde, "\n".join(sorted(set(funde)))


def test_keine_browser_fenster():
    """Leitfaden 2.1: nur eigene Dialoge (uiConfirm, uiAlert, uiPrompt, uiModal). Ausnahme: das Lesezeichen für das Zepp-Token läuft auf einer fremden Seite."""
    funde = []
    for p in sorted(JS.glob("*.js")):
        if p.name.startswith("00-i18n"):
            continue
        src = re.sub(r"/\*[\s\S]*?\*/|//[^\n]*", "", p.read_text(encoding="utf-8"))
        for m in re.finditer(r"(?<![\w.$])(prompt|confirm|alert)\(|window\.(prompt|confirm|alert)\(", src):
            zeile = src[src.rfind("\n", 0, m.start()) + 1:src.find("\n", m.start())]
            if p.name == "05-verwaltung.js" and "apptoken" in zeile:
                continue                                                      # Lesezeichen (javascript:) auf user.huami.com – dort gibt es keine eigenen Dialoge
            funde.append(f"{p.name}: {zeile.strip()[:100]}")
    assert not funde, funde


def test_dialog_standard_ist_kein_ok():
    src = (JS / "00-dialog.js").read_text(encoding="utf-8")
    assert 'o.ok = "OK"' not in src and '"Schließen"' in src and "window.uiPrompt" in src


def test_handbuch_ohne_entfallene_begriffe():
    hb = (ROOT / "docs" / "HANDBUCH.md").read_text(encoding="utf-8")
    hb = re.sub(r"`[^`]*`", "", hb)                                                       # Code, Adressen, Schlüssel
    funde = []
    for muster in (r"\bRekord", r"\bHöhenmeter\b", r"\bTags\b", r"\bSchlagworte\b", r"\bBackups?\b", r"\bWorkouts?\b", r"Zeit unterwegs", r"Gesamtzeit", r"Alle Jahre",
                   r"Favoriten für", r"Tour aufnehm", r"Höhen korrigieren", r"Höhe aus Uhr abgleichen", r"GPX-Datei laden", r"Routen laden", r"Seitenlayout"):
        for m in re.finditer(muster, hb):
            zeile = hb[hb.rfind("\n", 0, m.start()) + 1:hb.find("\n", m.start())]
            funde.append(f"{m.group(0)}: {zeile.strip()[:120]}")
    assert not funde, "\n".join(funde[:40])


def test_leitfaden_im_repo_und_verlinkt():
    lf = ROOT / "docs" / "LEITFADEN-BEGRIFFE.md"
    assert lf.exists() and "ein Wort je Sache" in lf.read_text(encoding="utf-8")
    assert "docs/LEITFADEN-BEGRIFFE.md" in (ROOT / "README.md").read_text(encoding="utf-8")


def test_reiter_allgemein_mit_alias():
    src = (JS / "13-start.js").read_text(encoding="utf-8")
    assert '["allgemein", "Allgemein",' in src and 'uebersicht: "allgemein"' in src and 'aktivitaeten: "sportarten"' in src


def test_gemeinsame_sportart_auswahl():
    """Leitfaden 2.6: je Muster EINE Funktion – Filtern (sportFilterHtml/sportFilterOptions) und Zuweisen (sportWahlHtml)."""
    nutzer = {"sportFilterHtml": {"02-uebersicht.js", "06-erweiterungen.js", "53-filter.js", "56-statistik.js"},
              "sportFilterOptions": {"02-uebersicht.js"},
              "sportWahlHtml": {"27-planung.js", "30-aufzeichnen.js", "34-tourmenue.js", "52-bausteine-uebersicht.js"}}
    for fn, dateien in nutzer.items():
        for d in dateien:
            assert fn + "(" in (JS / d).read_text(encoding="utf-8"), (fn, d)
    for d in ("27-planung.js", "34-tourmenue.js"):
        assert "sportOptions(" not in (JS / d).read_text(encoding="utf-8"), d
