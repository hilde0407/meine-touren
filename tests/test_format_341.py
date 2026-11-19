"""3.41.0 – zentrale Formatierer (app/static/js/01-format.js): Dauer, Strecke, Aufstieg, Tempo, Zahl, Datum, Uhrzeit, Zeitraum je Sprache."""
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "01-format.js"
NAMES = "fmtZahl, fmtDauer, fmtDauerTeile, fmtDauerHtml, fmtKm, fmtHm, fmtAuf, fmtAb, fmtTempo, fmtPace, fmtDatum, fmtDatumKurz, fmtUhrzeit, fmtMonat, fmtTagKurz, fmtZeitraum"


@pytest.fixture(scope="module")
def pg():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.set_content("<html><body></body></html>")
        page.evaluate("(c) => { window.__f = new Function(c + '; return {%s};')(); }" % NAMES, SRC.read_text(encoding="utf-8"))
        yield page
        b.close()


def call(pg, lang, fn, *args):
    return pg.evaluate("([l, fn, a]) => { window.LANG = l; return window.__f[fn](...a); }", [lang, fn, list(args)])


@pytest.mark.parametrize("lang,s,exp", [
    ("de", 6900, "1:55 Std."), ("en", 6900, "1:55 h"), ("fr", 6900, "1:55 h"), ("es", 6900, "1:55 h"),
    ("de", 2700, "45 Min."), ("en", 2700, "45 min"), ("de", 0, "0 Min."), ("de", 3599.6, "1:00 Std."),
    ("de", 10799, "3:00 Std."), ("de", 8760, "2:26 Std."), ("de", None, "0 Min."),
])
def test_dauer_einzeltour(pg, lang, s, exp):
    assert call(pg, lang, "fmtDauer", s) == exp


@pytest.mark.parametrize("lang,s,exp", [
    ("de", 24 * 3600, "24 Std."), ("de", 388 * 3600 + 1500, "388 Std."), ("de", 23 * 3600 + 3000, "23:50 Std."),
    ("en", 1400 * 3600, "1,400 h"), ("fr", 1400 * 3600, "1 400 h"),
])
def test_dauer_summe(pg, lang, s, exp):
    assert call(pg, lang, "fmtDauer", s, {"summe": True}) == exp


def test_dauer_optionen(pg):
    assert call(pg, "de", "fmtDauer", 6900, {"einheit": False}) == "1:55"
    assert call(pg, "de", "fmtDauer", 2700, {"hmm": True, "einheit": False}) == "0:45"
    assert call(pg, "en", "fmtDauerHtml", 6900) == '1:55<span class="u">h</span>'


@pytest.mark.parametrize("lang,km,o,exp", [
    ("de", 24.83, {}, "24,8 km"), ("en", 24.83, {}, "24.8 km"), ("fr", 24.83, {}, "24,8 km"), ("es", 24.83, {}, "24,8 km"),
    ("de", 1950.4, {"summe": True}, "1.950 km"), ("de", 15.66, {"summe": True}, "15,7 km"), ("de", 123.0, {"summe": True}, "123 km"),
    ("de", 123.0, {}, "123,0 km"), ("de", 24.83, {"einheit": False}, "24,8"), ("de", 24.83, {"d": 2}, "24,83 km"), ("en", 1950.4, {"summe": True}, "1,950 km"),
])
def test_strecke(pg, lang, km, o, exp):
    assert call(pg, lang, "fmtKm", km, o) == exp


def test_hoehe_tempo_pace(pg):
    assert call(pg, "de", "fmtHm", 300.4) == "300 m"
    assert call(pg, "de", "fmtAuf", 420) == "↑ 420 m"
    assert call(pg, "en", "fmtAb", 1234) == "↓ 1,234 m"
    assert call(pg, "de", "fmtTempo", 4.84) == "4,8 km/h"
    assert call(pg, "en", "fmtTempo", 4.84) == "4.8 km/h"
    assert call(pg, "de", "fmtPace", 12.5) == "12:30 min/km"
    assert call(pg, "de", "fmtZahl", 29.6) == "29,6"
    assert call(pg, "en", "fmtZahl", 29.6) == "29.6"
    assert call(pg, "de", "fmtZahl", 1234.5, 0) in ("1.235", "1.234")


@pytest.mark.parametrize("lang,lang_exp,kurz_exp,zeit_exp", [
    ("de", "18. November 2026", "18.11.2026", "03:43 Uhr"),
    ("en", "18 November 2026", "18/11/2026", "03:43"),
    ("fr", "18 novembre 2026", "18/11/2026", "03:43"),
    ("es", "18 de noviembre de 2026", "18/11/2026", "03:43"),
])
def test_datum(pg, lang, lang_exp, kurz_exp, zeit_exp):
    iso = "2026-11-18T03:43:00"
    assert call(pg, lang, "fmtDatum", iso) == lang_exp
    assert call(pg, lang, "fmtDatumKurz", iso) == kurz_exp
    assert call(pg, lang, "fmtUhrzeit", iso) == zeit_exp
    assert call(pg, lang, "fmtDatum", iso, {"zeit": True}) == f"{lang_exp}, {zeit_exp}"
    assert call(pg, lang, "fmtDatumKurz", iso, {"zeit": True}) == f"{kurz_exp}, {zeit_exp}"
    assert call(pg, lang, "fmtDatum", "2026-11-18") == lang_exp                      # ohne Uhrzeit
    assert call(pg, lang, "fmtUhrzeit", "2026-11-18") == ""


def test_datum_sekunden_und_ungueltig(pg):
    assert call(pg, "de", "fmtDatumKurz", 0) != ""                                    # Sekunden seit 1970 (je nach Zeitzone 1970)
    assert call(pg, "de", "fmtDatumKurz", "kaputt") == ""
    assert call(pg, "fr", "fmtDatum", "2026-11-01") == "1er novembre 2026"


def test_monat_zeitraum(pg):
    assert call(pg, "de", "fmtMonat", "2026-11-18") == "November 2026"
    assert call(pg, "de", "fmtMonat", "2026-11-18", {"kurz": True}) == "Nov. 2026"
    assert call(pg, "de", "fmtTagKurz", "2026-11-18") == "18. Nov."
    assert call(pg, "de", "fmtZeitraum", "2026-10-10", "2026-10-28") == "10.–28. Oktober 2026"
    assert call(pg, "en", "fmtZeitraum", "2026-10-10", "2026-10-28") == "10–28 October 2026"
    assert call(pg, "de", "fmtZeitraum", "2026-10-30", "2026-11-02") == "30. Oktober – 2. November 2026"
    assert call(pg, "de", "fmtZeitraum", "2025-12-30", "2026-01-02") == "30. Dezember 2025 – 2. Januar 2026"
    assert call(pg, "de", "fmtZeitraum", "2026-10-10", "2026-10-10") == "10. Oktober 2026"
    assert call(pg, "es", "fmtZeitraum", "2026-10-10", "2026-10-28") == "10–28 de octubre de 2026"


def test_keine_alten_helfer_mehr():
    """Die Einzel-Helfer sind weg; neue Stellen müssen die zentralen Formatierer nehmen."""
    import re
    js = SRC.parent
    alt = re.compile(r"\b(fmtHM|fmtH|homeDur|dateL|dateS|timeS)\(")
    bad = {}
    for f in sorted(js.glob("*.js")):
        if f.name.startswith("00-i18n") or f.name.startswith("seite-"):
            continue
        n = len(alt.findall(f.read_text(encoding="utf-8")))
        if n:
            bad[f.name] = n
    assert not bad, bad


def test_kein_toLocale_mit_festem_de_in_der_app():
    """Zahlen und Datum laufen über 01-format.js; ein hartes „de-DE“ in der App-Oberfläche ist ein Rückfall (Sortierschlüssel ausgenommen)."""
    import re
    js = SRC.parent
    bad = {}
    for f in sorted(js.glob("*.js")):
        if f.name.startswith("00-i18n") or f.name.startswith("seite-") or f.name == "01-format.js":
            continue
        t = f.read_text(encoding="utf-8")
        n = len(re.findall(r"toLocale(?:Date|Time)?String\(\"de-DE\"", t))
        if n:
            bad[f.name] = n
    assert not bad, bad
