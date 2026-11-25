"""3.61.2 Handy-Übersicht bei großer Systemschrift (Browser, Chromium, 390 px): „Seite anpassen“, „Ansichten“ und der Zepp-Knopf werden nie abgeschnitten (kein Ellipsis, scrollWidth <= clientWidth),
die Knöpfe dürfen unterschiedlich breit sein oder umbrechen (Tippfläche >= 44 px), die gelben Kennzahl-Kacheln („13,1 km“) brechen Wert und Einheit nicht in zwei Zeilen um und laufen nicht über.
Die Systemschrift (Android-Textgröße) wird nachgebaut: jede berechnete Schriftgröße der Seite wird mit dem Faktor multipliziert (wie WebView-textZoom; html{font-size:150%} allein trifft nur rem/em).
Dieselben Knöpfe auf der Karte (.kaopen) und der Tourseite sowie die Kopfknöpfe der Hauptseiten werden bei 150 % geprüft. Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import os

import pytest

from tests.test_zepp_uebersicht_ui import Fake, _page, _ready, _shot, app, clean, pw, T  # noqa: F401
from tests.test_tourseite_ui import _settled

expect = pytest.importorskip("playwright.sync_api").expect

ZOOM_JS = """(f) => {
  const els = [...document.querySelectorAll('body *')], sz = els.map(e => parseFloat(getComputedStyle(e).fontSize));
  els.forEach((e, i) => e.style.setProperty('font-size', (sz[i] * f) + 'px', 'important'));
}"""

# abgeschnittene Texte: Elemente mit verstecktem Überlauf (oder Ellipsis), deren Inhalt breiter ist als sie selbst, nur sichtbare
CUT_JS = """() => {
  const out = [];
  for (const e of document.querySelectorAll('body *')) {
    const cs = getComputedStyle(e), r = e.getBoundingClientRect();
    if (!r.width || !r.height || cs.visibility === 'hidden' || cs.display === 'none' || e.closest('[hidden]')) continue;
    if (r.width <= 2 || r.height <= 2) continue;                                      // verborgene Texte (sr-only)
    if (e.closest('.leaflet-container, svg, canvas, select')) continue;
    const hid = cs.overflowX !== 'visible' && cs.overflowX !== 'auto' && cs.overflowX !== 'scroll';
    if ((hid || cs.textOverflow === 'ellipsis') && e.scrollWidth > e.clientWidth + 1 && (e.textContent || '').trim())
      out.push((e.id ? '#' + e.id : e.tagName.toLowerCase() + '.' + String(e.className).split(' ').join('.')) + ' ' + e.scrollWidth + '>' + e.clientWidth + ' "' + e.textContent.trim().slice(0, 30) + '"');
  }
  return out;
}"""
OVER = "() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)"
BTNS = """() => [...document.querySelectorAll('#slzepp, #slopen, #slviews')].filter(e => e.offsetParent !== null).map(e => {
  const r = e.getBoundingClientRect(), t = e.querySelector('.slbt') || e;
  return {id: e.id, x: r.x, y: r.y, w: r.width, h: r.height, right: r.right, cut: t.offsetWidth > 2 && t.scrollWidth > t.clientWidth + 1, txt: e.innerText.trim()};
})"""
SIGNS = """() => [...document.querySelectorAll('.hli .sign, .hero .sign')].filter(e => e.offsetParent !== null).map(e => {
  const sv = e.querySelector('.sv'), r = e.getBoundingClientRect(), u = e.querySelector('.su');
  return {txt: sv.textContent, lines: Math.round(sv.getBoundingClientRect().height / (parseFloat(getComputedStyle(sv).fontSize) * 1.3)) || 1, over: sv.scrollWidth > e.clientWidth + 1 || sv.getBoundingClientRect().right > r.right + 1, unit: !!u, h: r.height};
})"""


def _zoom(pg, f):
    if f != 1:
        pg.evaluate(ZOOM_JS, f)


@pytest.mark.parametrize("f", [1, 1.3, 1.5])
def test_uebersicht_knoepfe_und_kacheln_bei_grosser_schrift(pw, app, clean, f):
    fake = Fake()
    pg = _page(pw, app, fake, width=390, height=844, dpr=2)
    try:
        _ready(pg)
        expect(pg.locator("#slzepp")).to_be_visible(timeout=T)
        expect(pg.locator(".hli .sign").first).to_be_visible(timeout=T)
        _settled(pg)
        _zoom(pg, f)
        _settled(pg)
        _shot(pg, f"uebersicht-390-{int(f * 100)}.png", full=False)
        d = os.environ.get("TS_SHOTS")
        if d:
            pg.locator(".hli").first.screenshot(path=os.path.join(d, f"kacheln-390-{int(f * 100)}.png"))
        b = pg.evaluate(BTNS)
        assert {x["id"] for x in b} == {"slzepp", "slopen", "slviews"}, b
        for x in b:
            assert not x["cut"], x                                                      # Text nie abgeschnitten
            assert x["h"] >= 43.5 and x["right"] <= 390.5 and x["x"] >= -0.5, x          # Tippfläche, im Bild
        z = [x for x in b if x["id"] == "slzepp"][0]
        assert all(x["y"] >= z["y"] + z["h"] - 1 for x in b if x["id"] != "slzepp"), b   # Zepp-Knopf allein in der ersten Zeile
        assert pg.evaluate(OVER) == 0
        s = pg.evaluate(SIGNS)
        assert len(s) == 3 and all(x["unit"] for x in s), s
        assert all(x["lines"] == 1 and not x["over"] for x in s), s                      # Wert samt Einheit in einer Zeile, kein Überlauf
        assert pg.evaluate(CUT_JS) == [] or all("sign" not in c and "slbt" not in c for c in pg.evaluate(CUT_JS)), pg.evaluate(CUT_JS)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_uebersicht_ohne_zepp_knoepfe_bei_150(pw, app, clean):
    fake = Fake(conf=False)
    pg = _page(pw, app, fake, width=390, height=844, dpr=2)
    try:
        pg.wait_for_selector("#slopen", timeout=30000)
        _settled(pg)
        _zoom(pg, 1.5)
        _settled(pg)
        _shot(pg, "uebersicht-ohne-zepp-390-150.png", full=False)
        b = pg.evaluate(BTNS)
        assert {x["id"] for x in b} >= {"slopen", "slviews"}, b
        assert all(not x["cut"] and x["h"] >= 43.5 and x["right"] <= 390.5 for x in b), b
        assert pg.evaluate(OVER) == 0
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("route", ["#/map", "#/tour/t3", "#/tours", "#/stats", "#/dash"])
def test_kopfknoepfe_der_hauptseiten_bei_150_nicht_abgeschnitten(pw, app, clean, route):
    fake = Fake()
    pg = _page(pw, app, fake, width=390, height=844, dpr=2)
    try:
        _ready(pg)
        pg.goto(f"{app}/{route}")
        pg.wait_for_function("() => !!document.querySelector('.kaopen, #tl a.tr, .hero, #stx, #slopen')", timeout=30000)
        _settled(pg)
        _zoom(pg, 1.5)
        _settled(pg)
        _shot(pg, f"seite-{route.strip('#/').replace('/', '-')}-390-150.png", full=False)
        cut = pg.evaluate(CUT_JS)
        kopf = [c for c in cut if any(k in c for k in ("slbt", "slopen", "slviews", "slzepp", "kaopen", "mfb", "chip", "btn", "sign"))]
        assert kopf == [], kopf
        assert pg.evaluate(OVER) == 0
        for x in pg.evaluate(BTNS):
            assert not x["cut"] and x["h"] >= (39.5 if route == "#/map" else 43.5), x                # Kartenleiste: 40-px-Symbolknöpfe (Höhe der Leiste ist fest, siehe test_werkzeugzeile_ui.py)
    finally:
        pg.browser_.close()
