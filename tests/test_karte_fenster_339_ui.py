"""3.39.0 Karte: „Touren im Ausschnitt“ (#mbx) öffnet genau ein Fenster über allen Bedienfeldern (Escape schließt, Fokus hinein und zurück, Dialog-Attribute); Hinweistext der Heatmap in vier Sprachen.
Wettlauf-Regel: auf Zustände warten (expect/wait_for_function mit 15 s, press_until_gone), keine festen Pausen. Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import os

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.test_seitenlayout_ui import T, _browser, pw  # noqa: F401
from tests.test_reise_seiten_ui import app  # noqa: F401
from tests.test_foto_karte_ui import clean, _mapok  # noqa: F401
from tests.test_tourseite_ui import _shot
from tests.helpers_ui import press_until_gone, quiet, settled

TL = 30000
FEN = ".uimod.mbxfen"
OBEN = """(sel) => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2, t = document.elementFromPoint(x, y); return !!t && (e === t || e.contains(t)); }"""
UEBER = """() => { const e = document.querySelector('.uimod.mbxfen .uibox h2'); if (!e) return null; const r = e.getBoundingClientRect(); const pts = [[r.left + 4, r.top + r.height / 2], [r.left + r.width / 2, r.top + r.height / 2], [r.left + 4, r.top + 2]];
  return pts.map(([x, y]) => { const t = document.elementFromPoint(x, y); return !!t && !!t.closest('.uimod.mbxfen') && !t.closest('.mapui'); }); }"""
KNOPF_BEDECKT = """() => { const b = document.getElementById('mbx'), r = b.getBoundingClientRect(), t = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return !!t && !!t.closest('.uimod.mbxfen'); }"""


def _karte(pw, url, lang="de", **kw):
    pg = _browser(pw, url, devs=None, locale={"de": "de-DE", "en": "en-GB", "fr": "fr-FR", "es": "es-ES"}[lang], **kw)
    pg.context.add_init_script("try { localStorage.setItem('lang', %r); } catch (e) {}" % lang)
    pg.goto(f"{url}/#/map", timeout=TL)
    pg.wait_for_function("() => !!document.querySelector('#kax #bigmap') && typeof map !== 'undefined' && !!map && !!document.getElementById('mbx') && document.getElementById('bigmap').clientWidth > 300", timeout=TL)
    quiet(pg, 3000, 500)
    return pg


def _oeffnen(pg):
    pg.locator("#mbx").click()
    expect(pg.locator(FEN)).to_have_count(1, timeout=T)


def test_ein_fenster_ueber_allen_bedienfeldern(pw, app, clean):
    pg = _karte(pw, app)
    try:
        _oeffnen(pg)
        win = pg.locator(FEN)
        box = win.locator(".uibox")
        assert box.get_attribute("role") == "dialog" and box.get_attribute("aria-modal") == "true" and box.get_attribute("aria-labelledby")
        expect(pg.locator(FEN + " h2")).to_be_visible(timeout=T)
        # zweiter Aufruf (z. B. per Tastatur oder Skript) ersetzt das Fenster, es entsteht nie ein zweites
        for _ in range(3):
            pg.evaluate("() => document.getElementById('mbx').click()")
            expect(win).to_have_count(1, timeout=T)
        assert pg.locator(".uimod").count() == 1
        # Titelzeile liegt vor allen Bedienfeldern (elementFromPoint), der Knopf dahinter ist nicht mehr erreichbar
        assert pg.evaluate(UEBER) == [True, True, True]
        assert pg.evaluate(KNOPF_BEDECKT) is True
        z = pg.evaluate("() => [+getComputedStyle(document.querySelector('.uimod.mbxfen')).zIndex, +getComputedStyle(document.querySelector('.mapui')).zIndex]")
        assert z[0] > z[1], z
        # Fokus liegt im Fenster
        assert pg.evaluate("() => !!document.activeElement.closest('.uimod.mbxfen')")
        _shot(pg, "karte-ausschnitt-fenster-1280")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_escape_schliesst_und_fokus_kehrt_zum_knopf_zurueck(pw, app, clean):
    pg = _karte(pw, app)
    try:
        _oeffnen(pg)
        press_until_gone(pg, "Escape", FEN)
        assert pg.evaluate("() => document.activeElement && document.activeElement.id") == "mbx"
        # wieder öffnen: Schließen-Knopf, Klick auf den Hintergrund, Tab bleibt im Fenster
        _oeffnen(pg)
        pg.locator("#mbc").click()
        expect(pg.locator(FEN)).to_have_count(0, timeout=T)
        assert pg.evaluate("() => document.activeElement.id") == "mbx"
        _oeffnen(pg)
        for _ in range(6):
            pg.keyboard.press("Tab")
            assert pg.evaluate("() => !!document.activeElement.closest('.uimod.mbxfen')")
        pg.mouse.click(5, 5)                                                          # Hintergrund
        expect(pg.locator(FEN)).to_have_count(0, timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_390_fenster_vor_den_bedienfeldern(pw, app, clean, scheme):
    pg = _karte(pw, app, width=390, height=844, scheme=scheme)
    try:
        _oeffnen(pg)
        assert pg.evaluate(UEBER) == [True, True, True]
        assert pg.evaluate("() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)") == 0
        settled(pg)
        _shot(pg, f"karte-ausschnitt-fenster-390-{scheme}")
        press_until_gone(pg, "Escape", FEN)
    finally:
        pg.browser_.close()


HEAT = {"de": ("Heatmap: zeichnet alle Touren in einer Farbe übereinander", "Heatmap"),
        "en": ("Heatmap: draws all tours on top of each other in one colour", "Heatmap"),
        "fr": ("Carte de chaleur : superpose tous les parcours dans une seule couleur", "Carte de chaleur"),
        "es": ("Mapa de calor: superpone todas las rutas en un solo color", "Mapa de calor")}


@pytest.mark.parametrize("lang", ["de", "en", "fr", "es"])
def test_heatmap_hinweis_erklaert_den_unterschied(pw, app, clean, lang):
    pg = _karte(pw, app, lang=lang)
    try:
        b = pg.locator("#mht")
        titel = b.get_attribute("title")
        assert titel.startswith(HEAT[lang][0]), titel
        assert b.inner_text().strip() == HEAT[lang][1]                                # Knopfname unverändert („Heatmap“ bzw. die vorhandene Übersetzung)
        strecken = {"de": "Strecken", "en": "Tracks", "fr": "Tracés", "es": "Trazados"}[lang]
        assert strecken in titel, titel                                               # nennt den Knopf, der Farbe und Breite der Tracklinien ändert
        if lang == "de":
            assert "Ersetzt die farbigen Tracklinien" in titel and "'Strecken'" in titel
    finally:
        pg.browser_.close()
