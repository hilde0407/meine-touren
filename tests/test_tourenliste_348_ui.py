"""3.48.0 – Tourenliste am Handy (Browser, Chromium): 390 px ruhige Karte je Tour (feste Miniatur, Titel höchstens zwei Zeilen, Kennzahlen linksbündig zur Titelspalte, keine Überläufe, auch mit
130 % Zoom), kompakte Filter (nur Suche, Sportart, Sortierung; Jahr, Jahreszeit, Bewertung, Region, Tags hinter „Filter“ mit Zähler und Zurücksetzen), Filter wirken, Englisch;
Desktop (1280) unverändert. Screenshots mit TS_SHOTS=<Ordner>."""
import pytest
from playwright.sync_api import expect

from tests.test_bausteine_ui import T, _browser, _shot  # noqa: F401
from tests.test_bausteine_ui import app, pw  # noqa: F401  (Fixtures)

EXTRA_IDS = ("fy", "fz", "fb", "fr", "ft")


def _liste(pw, app, **kw):
    pg = _browser(pw, app, **kw)
    pg.goto(f"{app}/#/tours")
    pg.evaluate("() => { try { sessionStorage.removeItem('tf'); } catch (e) {} }")
    pg.reload()
    pg.wait_for_selector("#tl a.tr", timeout=T)
    pg.wait_for_function("() => document.fonts.status === 'loaded'", timeout=T)
    return pg


def _anzahl(pg):
    return int(pg.evaluate("() => (document.querySelector('#cnt').textContent.match(/^(\\d+)/) || [0, -1])[1]"))


def test_desktop_unveraendert(pw, app):
    pg = _liste(pw, app, width=1280, height=900)
    try:
        for i in ("q", "fy", "fs", "fz", "fb", "fr", "fg", "ft", "so"):
            expect(pg.locator("#" + i)).to_be_visible(timeout=T)
        expect(pg.locator("#fmore")).to_be_hidden()
        order = pg.evaluate("() => [...document.querySelectorAll('#flt select, #flt input')].map(e => e.id)")
        assert order == ["q", "fy", "fs", "fz", "fb", "fr", "fg", "ft", "so"], order                    # gleiche Reihenfolge wie bisher, dazu (3.64.0) „Gebiet“ hinter „Region“
        r = pg.evaluate("""() => { const t = document.querySelector('.tr'), n = t.querySelector('.n').getBoundingClientRect(), m = t.querySelector('.nm').getBoundingClientRect();
          return {nRight: n.left > m.left + 200, fs: parseFloat(getComputedStyle(t.querySelector('.nm')).fontSize), nfs: parseFloat(getComputedStyle(t.querySelector('.n span')).fontSize)}; }""")
        assert r["nRight"] and r["fs"] == 22 and r["nfs"] == 24, r                                    # Kennzahlen rechts, Schriftgrößen wie bisher
        _shot(pg, "tourenliste-1280-light.png", full=False)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_mobile_filter_hinter_knopf_zaehler_zuruecksetzen(pw, app):
    pg = _liste(pw, app, width=390, height=844, dpr=2)
    try:
        for i in ("q", "fs", "so", "fmore"):
            expect(pg.locator("#" + i)).to_be_visible(timeout=T)
        for i in EXTRA_IDS:
            expect(pg.locator("#" + i)).to_be_hidden()
        assert pg.evaluate("() => document.querySelector('#flt').getBoundingClientRect().height") < 200                # Filter nehmen nicht den ersten Bildschirm
        total = _anzahl(pg)
        assert total > 3
        expect(pg.locator("#fcnt")).to_be_hidden()
        pg.locator("#fmore").click()
        for i in EXTRA_IDS:
            expect(pg.locator("#" + i)).to_be_visible(timeout=T)
        assert pg.get_attribute("#fmore", "aria-expanded") == "true"
        sel = pg.evaluate("() => [...document.querySelectorAll('#flt select')].filter(s => s.getBoundingClientRect().width > 0).map(s => [s.id, Math.round(s.getBoundingClientRect().height), s.scrollWidth <= s.clientWidth + 1])")
        assert all(h >= 40 for _, h, _ in sel), sel
        pg.select_option("#fz", "winter")
        pg.wait_for_function("() => !document.querySelector('#fcnt').hidden && document.querySelector('#fcnt').textContent === '1'", timeout=T)
        pg.select_option("#fb", "4")
        pg.wait_for_function("() => document.querySelector('#fcnt').textContent === '2'", timeout=T)
        assert _anzahl(pg) <= total
        expect(pg.locator("#fclear")).to_be_visible()
        pg.locator("#fclear").click()
        pg.wait_for_function("() => document.querySelector('#fcnt').hidden && document.querySelector('#fz').value === '' && document.querySelector('#fb').value === ''", timeout=T)
        assert _anzahl(pg) == total
        expect(pg.locator("#fclear")).to_be_hidden()
        # Filter wirken: Sportart und Suche (sichtbare Filter), Jahr hinter dem Knopf
        sport = pg.evaluate("() => [...document.querySelectorAll('#fs option')].map(o => o.value).filter(Boolean)[0]")
        pg.select_option("#fs", sport)
        pg.wait_for_function("(n) => +document.querySelector('#cnt').textContent.split(' ')[0] < n", arg=total, timeout=T) if sport != "hike" else None
        pg.select_option("#fs", "")
        y = pg.evaluate("() => [...document.querySelectorAll('#fy option')].map(o => o.value).filter(v => v !== '0')[0]")
        pg.select_option("#fy", y)
        pg.wait_for_function("() => document.querySelector('#fcnt').textContent === '1'", timeout=T)
        assert pg.evaluate("(y) => [...document.querySelectorAll('#tl .tr')].length > 0 && document.querySelector('#cnt').textContent.length > 0", y)
        pg.locator("#fclear").click()
        pg.fill("#q", "zzzzzz")
        expect(pg.locator("#tl .empty")).to_be_visible(timeout=T)
        pg.fill("#q", "")
        pg.wait_for_selector("#tl a.tr", timeout=T)
        # gemerkter Filter: nach dem Neuladen ist der Bereich offen und der Zähler stimmt (nie unsichtbar aktiv)
        pg.locator("#fmore").click() if pg.get_attribute("#fmore", "aria-expanded") != "true" else None
        pg.select_option("#fz", "sommer")
        pg.wait_for_function("() => document.querySelector('#fcnt').textContent === '1'", timeout=T)
        pg.reload()
        pg.wait_for_selector("#tl a.tr, #tl .empty", timeout=T)
        expect(pg.locator("#fz")).to_be_visible(timeout=T)
        assert pg.inner_text("#fcnt") == "1"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme,zoom", [("light", 1), ("dark", 1), ("light", 1.3)])
def test_mobile_karten_ruhig_ohne_ueberlauf(pw, app, scheme, zoom):
    pg = _liste(pw, app, width=390, height=844, dpr=2, scheme=scheme)
    try:
        if zoom != 1:
            pg.evaluate("(z) => { document.body.style.zoom = z; }", zoom)                                  # wie größere Systemschrift: weniger Platz je Zeile
        pg.wait_for_function("() => document.querySelectorAll('#tl a.tr').length >= 3", timeout=T)
        r = pg.evaluate("""() => {
          const W = innerWidth, out = {over: document.documentElement.scrollWidth - W, rows: []};
          document.querySelectorAll('#tl a.tr').forEach(t => {
            const b = t.getBoundingClientRect(), nm = t.querySelector('.nm').getBoundingClientRect(), n = t.querySelector('.n').getBoundingClientRect(), svg = (t.querySelector('.trp') || t.querySelector('svg.mini')).getBoundingClientRect();   // 3.52.0: Kachel (Foto oder Strecke)
            const s = t.querySelector('.s').getBoundingClientRect();
            out.rows.push({h: Math.round(b.height), left: Math.abs(n.left - nm.left), svgW: Math.round(svg.width / (+document.body.style.zoom || 1)), trf: t.classList.contains('trf'), cut: t.scrollWidth > t.clientWidth + 1, right: Math.max(nm.right, n.right, s.right) <= b.right + 1,
              nfs: parseFloat(getComputedStyle(t.querySelector('.n span')).fontSize), nmfs: parseFloat(getComputedStyle(t.querySelector('.nm')).fontSize), nmH: Math.round(nm.height / (+document.body.style.zoom || 1)),
              nOverlap: n.top < s.bottom - 1 && n.left < s.right && n.right > s.left, sep: getComputedStyle(t.querySelector('.n')).borderTopWidth});
          });
          return out; }""")
        assert r["over"] <= 0, r
        assert len(r["rows"]) >= 3
        for x in r["rows"]:
            assert x["h"] >= 44 and x["left"] <= 1.5 and x["svgW"] <= (88 if x["trf"] else 70) and not x["cut"] and x["right"] and not x["nOverlap"], x
            assert x["nfs"] <= 16 and x["nmfs"] <= 20 and x["nmH"] <= 2 * 24, x                               # kleinere, einheitliche Schrift; Titel höchstens zwei Zeilen
        assert len({x["nfs"] for x in r["rows"]}) == 1
        if zoom == 1:
            _shot(pg, f"tourenliste-390-{scheme}.png", full=False)
            pg.locator("#fmore").click()
            _shot(pg, f"tourenliste-390-{scheme}-filter.png", full=False)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_englisch(pw, app):
    pg = _liste(pw, app, width=390, height=844, locale="en-US")
    try:
        pg.evaluate("() => localStorage.setItem('lang', 'en')")
        pg.reload()
        pg.wait_for_selector("#tl a.tr", timeout=T)
        assert pg.inner_text("#fmore").strip() == "Filter"
        pg.locator("#fmore").click()
        pg.select_option("#fz", "winter")
        pg.wait_for_function("() => document.querySelector('#fcnt').textContent === '1'", timeout=T)
        assert pg.get_attribute("#fmore", "aria-label") == "Filter (1 active)"
        assert pg.inner_text("#fclear").strip() == "Reset filter"
        pg.evaluate("() => localStorage.setItem('lang', 'de')")
    finally:
        pg.browser_.close()
