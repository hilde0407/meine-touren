"""3.46.0 – Aufräumen im Code: ein Formatierer je Wert (auch Dateigrößen), keine festen Sprachkürzel, ein Dialog-Baustein, Wörterbuch ohne Altlasten."""
import re
from pathlib import Path

import pytest

ST = Path(__file__).resolve().parent.parent / "app" / "static"
JS = ST / "js"
QUELLEN = [f for f in sorted(JS.glob("*.js")) if "i18n" not in f.name]


def _text(f):
    return f.read_text(encoding="utf-8")


def _ohne_kommentare(s):
    return re.sub(r"/\*.*?\*/", "", s, flags=re.S)


def test_keine_alten_format_helfer():
    alt = re.compile(r"\b(fmtHM|fmtH|slDur|homeDur|dateL|dateS|rsDt|rsMb)\b")
    schlecht = {f.name: alt.findall(_text(f)) for f in QUELLEN}
    assert not {k: v for k, v in schlecht.items() if v}, schlecht


def test_kein_festes_de_DE_ausser_format_und_uebersetzung():
    schlecht = []
    for f in QUELLEN:
        if f.name == "01-format.js":
            continue
        t = _ohne_kommentare(_text(f))
        if "de-DE" in t or re.search(r"\.toLocale(Date|Time)?String\(", t):
            schlecht.append(f.name)
    assert not schlecht, f"direkte toLocale…-Aufrufe oder \"de-DE\" außerhalb von 01-format.js: {schlecht}"


def test_oeffentliche_seiten_laden_format():
    for h in ("rueckblick", "show", "share", "slideshow"):
        html = _text(ST / f"{h}.html")
        assert "/js/01-format.js" in html and html.index("00-i18n.js") < html.index("01-format.js"), h


def test_keine_alten_modal_reste():
    for f in QUELLEN:
        t = _ohne_kommentare(_text(f))
        assert not re.search(r"(^|[^A-Za-z0-9_.])modal\(", t), f.name
        assert not re.search(r"\bconst modal\b|class=\"(modal|mbox)\b", t), f.name
    css = _ohne_kommentare(_text(ST / "style.css"))
    assert not re.search(r"\.(modal|mbox)\b", css)


def test_dialog_helfer_nutzen_uimodal():
    rs = _text(JS / "68-wiederherstellen.js")
    assert "uiModal(" in rs and 'document.createElement("div")' not in rs.split("async function rsInit")[0].split("function rsDialog")[1]
    sl = _text(JS / "49-seitenlayout.js")
    teil = sl.split("function slModal(")[1].split("\n}\n")[0]
    assert "uiModal(" in teil and "createElement" not in teil


def test_wortschatz_altlasten_weg():
    neu = _text(JS / "00-i18n-neu.js")
    for k in ("m aufwärts || ", "{} m aufwärts || ", "Tempo (Pace) || "):
        assert not any(l.startswith(k) for l in neu.split("\n")), k
    assert "Average pace" not in neu and "Tempo im Schnitt|Average pace" not in _text(JS / "00-i18n.js")
    # Englisch nennt die Verwaltung überall „Admin“ (wie das Menü)
    for l in neu.split("\n"):
        p = l.split(" || ")
        if len(p) >= 4 and "Verwaltung" in p[0]:
            assert "Administration" not in p[1], l


@pytest.fixture(scope="module")
def pg():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page()
        page.set_content("<html><body></body></html>")
        page.evaluate("(c) => { window.__f = new Function(c + '; return {fmtGroesse, fmtDatum};')(); }", _text(JS / "01-format.js"))
        yield page
        b.close()


def call(pg, lang, fn, *args):
    return pg.evaluate("([l, fn, a]) => { window.LANG = l; return window.__f[fn](...a); }", [lang, fn, list(args)])


@pytest.mark.parametrize("lang,n,exp", [
    ("de", 12345678, "12,3 MB"), ("en", 12345678, "12.3 MB"), ("fr", 12345678, "12,3 Mo"), ("es", 12345678, "12,3 MB"),
    ("de", 1500000000, "1,5 GB"), ("en", 1500000000, "1.5 GB"), ("fr", 1500000000, "1,5 Go"), ("es", 1500000000, "1,5 GB"),
    ("de", 50000, "50 kB"), ("fr", 50000, "50 ko"), ("de", 0, "1 kB"), ("de", None, "1 kB"),
])
def test_groesse_vier_sprachen(pg, lang, n, exp):
    assert call(pg, lang, "fmtGroesse", n) == exp


@pytest.mark.parametrize("lang,exp", [
    ("de", "Mittwoch, 18. November 2026"), ("en", "Wednesday, 18 November 2026"),
    ("fr", "mercredi, 18 novembre 2026"), ("es", "miércoles, 18 de noviembre de 2026"),
])
def test_datum_mit_wochentag(pg, lang, exp):
    assert call(pg, lang, "fmtDatum", "2026-11-18", {"wochentag": True}) == exp
