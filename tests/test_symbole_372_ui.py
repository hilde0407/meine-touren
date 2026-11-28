"""3.72.0 (N-05) – Ein Symbolsystem: keine Emoji und keine Zeichen wie ✓ ⚠ ✕ ℹ ❤ in der Oberfläche, nur Liniensymbole (svg.ic, currentColor).
Ausgenommen bleiben die Pfeile → ↑ ↓ in Wegangaben und Messwerten und die Sterne ★ ☆ der Bewertung (Textzeichen, keine Emoji). Texte von Nutzern werden nie verändert."""
import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.helpers_ui import settled  # noqa: E402
from tests.test_audit_371_ui import app, _page  # noqa: F401, E402
from tests.test_seitenlayout_ui import T, pw, _browser  # noqa: F401, E402

SCAN = """() => { const out = [], w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) { const n = w.currentNode, t = n.nodeValue, m = t.match(/[\\u2190\\u2194-\\u21ff\\u2300-\\u23ff\\u2460-\\u2604\\u2607-\\u27bf\\u2900-\\u297f\\u2b00-\\u2bff\\u{1F000}-\\u{1FAFF}\\u25a0-\\u25ff]/u);
    if (!m) continue; const e = n.parentElement; if (!e || e.closest('script,style,option,svg,[translate=no]') || (e.offsetParent === null && getComputedStyle(e).position !== 'fixed')) continue;
    out.push(m[0] + ' | ' + e.tagName.toLowerCase() + '.' + String(e.className).slice(0, 25) + ' | ' + t.trim().slice(0, 40)); }
  return out; }"""


@pytest.mark.parametrize("seite", ["dash", "tours", "trips", "stats", "admin", "tour/h0", "tour/h0/auswertung", "story/h0", "recap/2026"])
def test_keine_emoji_in_der_oberflaeche(pw, app, seite):
    pg = _page(pw, app, seite, 1280, "light")
    try:
        pg.wait_for_timeout(600)
        rest = pg.evaluate(SCAN)
        assert rest == [], rest
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_verwaltung_reiter_sportarten_und_handy_menue_liniensymbole(pw, app):
    pg = _page(pw, app, "admin", 1280, "light", "#atabs")
    try:
        pg.locator('#atabs button[data-t="sportarten"]').first.click()
        pg.wait_for_selector(".katic svg.ic", timeout=T)
        assert pg.evaluate("() => document.querySelectorAll('.katic svg.ic').length") >= 29            # je Sportart des Katalogs ein Liniensymbol
        assert pg.evaluate("() => [...document.querySelectorAll('.katic')].every(e => !e.textContent.trim())")
        # Benutzermenü, Info, Karte: Liniensymbole statt 👥, ℹ️, ⌖
        assert pg.evaluate("() => !!document.querySelector('.av svg.ic')")
        pg.goto(app + "/#/map")
        pg.wait_for_selector("#mloc svg.ic", timeout=T)
        assert pg.evaluate("() => { const s = document.querySelector('#mloc svg.ic'); return s.getAttribute('stroke') === 'currentColor' && s.getAttribute('viewBox') === '0 0 24 24'; }")
    finally:
        pg.browser_.close()


def test_nutzertexte_bleiben_unveraendert(pw, app):
    pg = _page(pw, app, "tours", 1280, "light", "#q")
    try:
        pg.evaluate("""() => { const d = document.createElement('div'); d.id = 'nt'; d.innerHTML = '<span>🥾 Wanderung</span><button>🥾 Knopf</button>'; document.body.appendChild(d); }""")
        pg.wait_for_function("() => !!document.querySelector('#nt button svg.ic')", timeout=T)
        assert pg.evaluate("() => document.querySelector('#nt span').textContent") == "🥾 Wanderung"        # Text eines Nutzers (kein Knopf, kein aria-hidden): unverändert
    finally:
        pg.browser_.close()
