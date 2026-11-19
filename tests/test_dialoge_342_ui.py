"""3.42.0 Ein Dialog, ein Schalter, ein Knopf: alle früheren .modal-Fenster laufen über uiModal() (Esc, Fokusfalle, Fokus zurück, Klick daneben),
„Abbrechen“ steht links und der Hauptknopf rechts, jede An/Aus-Einstellung ist derselbe Schalter und „an“ ist gelb, „Seite anpassen“ steht überall oben rechts.
Wettlauf-Regel: auf Zustände warten (expect/wait_for_function mit 15 s, press_until_gone), keine festen Pausen. Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import re
from pathlib import Path

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.test_seitenlayout_ui import T, _browser, pw  # noqa: F401
from tests.test_reise_seiten_ui import app  # noqa: F401
from tests.test_foto_karte_ui import clean  # noqa: F401
from tests.test_tourseite_ui import _shot
from tests.helpers_ui import press_until_gone, quiet, settled

TL = 30000
JS = [f for f in sorted((Path(__file__).resolve().parent.parent / "app" / "static" / "js").glob("*.js")) if "i18n" not in f.name]
GELB = "rgb(242, 194, 48)"
POS = """(sel) => { const b = document.querySelector(sel); const r = b.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }"""


def _tour(pw, url, **kw):
    pg = _browser(pw, url, devs=None, **kw)
    pg.goto(f"{url}/#/tour/r3", timeout=TL)
    pg.wait_for_function("() => !!document.querySelector('#ren') && !!document.querySelector('#etag')", timeout=TL)
    quiet(pg, 3000, 500)
    return pg


# ---------- Quelltext-Regeln ----------

def test_keine_alten_modal_fenster_mehr():
    for f in JS:
        t = f.read_text(encoding="utf-8")
        assert 'className = "modal' not in t and 'class="modal' not in t and 'class="mbox' not in t, f"{f.name}: altes .modal/.mbox-Fenster"


def test_abbrechen_steht_links_vom_hauptknopf():
    """In allen Fußzeilen (uifoot/dvfoot/Dialogzeilen) kommt der Hauptknopf (btn ohne ghost/alt) nie vor „Abbrechen“/„Schließen“ derselben Zeile."""
    pat = re.compile(r'<button[^>]*class="btn"[^>]*>[^<]*</button><button[^>]*class="btn (?:ghost|alt)[^"]*"[^>]*>(?:Abbrechen|Schließen)</button>')
    for f in JS:
        bad = pat.findall(f.read_text(encoding="utf-8"))
        assert not bad, f"{f.name}: Hauptknopf vor Abbrechen/Schließen: {bad[:1]}"


# ---------- Verhalten im Browser ----------

def test_umbenennen_esc_fokusfalle_und_fokus_zurueck(pw, app, clean):
    pg = _tour(pw, app)
    try:
        pg.locator("#ren").focus()
        pg.locator("#ren").click()
        expect(pg.locator(".uimod")).to_have_count(1, timeout=T)
        box = pg.locator(".uimod .uibox")
        assert box.get_attribute("role") == "dialog" and box.get_attribute("aria-modal") == "true" and box.get_attribute("aria-labelledby")
        assert pg.evaluate("() => document.querySelector('.uimod .uibox > h2') !== null")             # Titel ist immer eine H2, auch bei früheren H3
        assert pg.evaluate("() => !!document.activeElement.closest('.uimod')")                      # Fokus im Fenster
        assert pg.evaluate("() => document.querySelector('#main').closest('[inert]') !== null || document.querySelector('#main').inert || !!document.querySelector('#main').closest('[inert]')")
        # Fokusfalle: viele Tabs, der Fokus verlässt das Fenster nie (vorwärts wie rückwärts)
        for _ in range(12):
            pg.keyboard.press("Tab")
            assert pg.evaluate("() => !!document.activeElement.closest('.uimod')")
        for _ in range(5):
            pg.keyboard.press("Shift+Tab")
            assert pg.evaluate("() => !!document.activeElement.closest('.uimod')")
        press_until_gone(pg, "Escape", ".uimod")
        assert pg.evaluate("() => document.activeElement && document.activeElement.id") == "ren"      # Fokus zurück an den Auslöser
        assert pg.evaluate("() => !document.querySelector('[inert]')")                               # Hintergrund wieder bedienbar
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_klick_daneben_und_abbrechen_schliessen(pw, app, clean):
    pg = _tour(pw, app)
    try:
        pg.locator("#etag").click()
        expect(pg.locator(".uimod")).to_have_count(1, timeout=T)
        pg.locator("#tgx").click()
        expect(pg.locator(".uimod")).to_have_count(0, timeout=T)
        pg.locator("#etag").click()
        expect(pg.locator(".uimod")).to_have_count(1, timeout=T)
        pg.mouse.click(4, 4)                                                                          # auf den Hintergrund
        expect(pg.locator(".uimod")).to_have_count(0, timeout=T)
        pg.locator("#ren").click()
        expect(pg.locator(".uimod")).to_have_count(1, timeout=T)
        pg.evaluate("() => location.hash = '#/tours'")                                                # Seitenwechsel räumt das Fenster weg und gibt den Hintergrund frei
        expect(pg.locator(".uimod")).to_have_count(0, timeout=T)
        assert pg.evaluate("() => !document.querySelector('[inert]')")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_hauptknopf_rechts_abbrechen_links(pw, app, clean):
    pg = _tour(pw, app)
    try:
        for opener, cancel, ok in (("#ren", "#rcx", "#rok"), ("#etag", "#tgx", "#tgs")):
            pg.locator(opener).click()
            expect(pg.locator(".uimod")).to_have_count(1, timeout=T)
            a, b = pg.evaluate(POS, cancel), pg.evaluate(POS, ok)
            assert a[2] <= b[0] + 1 and abs(a[1] - b[1]) < 6, (opener, a, b)                         # Abbrechen links, gleiche Zeile
            press_until_gone(pg, "Escape", ".uimod")
        # Neue Dialoge (uiConfirm) haben dieselbe Reihenfolge
        pg.evaluate("() => { window.__r = uiConfirm({title: 'Test', text: 'x', ok: 'Ja'}); }")
        expect(pg.locator(".uidlg .uifoot .btn")).to_have_count(2, timeout=T)
        assert pg.evaluate("() => [...document.querySelectorAll('.uidlg .uifoot .btn')].map(b => b.textContent)") == ["Abbrechen", "Ja"]
        press_until_gone(pg, "Escape", ".uidlg")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_handy_dialog_scrollt_und_bleibt_im_bild(pw, app, clean):
    pg = _tour(pw, app, width=390, height=700)
    try:
        pg.evaluate("() => document.querySelector('#ren').click()")
        expect(pg.locator(".uimod")).to_have_count(1, timeout=T)
        r = pg.evaluate("() => { const b = document.querySelector('.uimod .uibox').getBoundingClientRect(); return [b.left, b.right, b.top, b.bottom, innerWidth, innerHeight]; }")
        assert r[0] >= 0 and r[1] <= r[4] + 1 and r[2] >= 0 and r[3] <= r[5] + 1, r
        assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
        _shot(pg, "dialog-umbenennen-390")
        press_until_gone(pg, "Escape", ".uimod")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_schalter_an_ist_gelb_und_eine_form(pw, app, clean, scheme):
    pg = _browser(pw, app, devs=None, scheme=scheme)
    try:
        pg.goto(f"{app}/#/admin", timeout=TL)
        pg.wait_for_function("() => !!document.querySelector('[data-k=auto_sync]') && !!document.querySelector('#pon')", timeout=TL)
        quiet(pg, 3000, 500)
        info = pg.evaluate("""() => ['auto_sync', 'update_check', 'notify_events', 'plan_enabled'].map(k => { const e = document.querySelector('[data-k=' + k + ']'); if (!e) return [k, null];
          const s = getComputedStyle(e), r = e.getBoundingClientRect(); return [k, e.tagName + ':' + e.type, s.appearance, Math.round(r.width), Math.round(r.height)]; })""")
        for k, typ, app_, w, h in info:
            assert typ == "INPUT:checkbox", (k, typ)                                              # kein Auswahlfeld „an/aus“, „ja/nein“ mehr
            assert app_ == "none" and w >= 40 and h >= 24, (k, app_, w, h)                       # eine Schalterform
        for k in ("auto_sync", "plan_enabled"):
            for want in (True, False):
                pg.evaluate("([k, v]) => { const e = document.querySelector('[data-k=' + k + ']'); e.checked = v; }", [k, want])
                bg = pg.evaluate("(k) => getComputedStyle(document.querySelector('[data-k=' + k + ']')).backgroundColor", k)
                assert (bg == GELB) == want, (scheme, k, want, bg)                                 # an = gelb, aus = nicht gelb
        pg.locator("[data-k=auto_sync]").scroll_into_view_if_needed()
        _shot(pg, f"schalter-{scheme}-1280")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_schalter_wirkt_beim_speichern(pw, app, clean):
    pg = _browser(pw, app, devs=None)
    try:
        pg.goto(f"{app}/#/admin", timeout=TL)
        pg.wait_for_function("() => !!document.querySelector('[data-k=auto_sync]') && !!document.querySelector('#pon')", timeout=TL)
        quiet(pg, 3000, 500)
        pg.locator("[data-k=auto_sync]").check()
        pg.locator("#pon").uncheck()
        expect(pg.locator("#pbox")).to_be_hidden(timeout=T)
        pg.locator("#save").click()
        pg.wait_for_function("() => document.querySelector('#ok') && document.querySelector('#ok').textContent.length > 0", timeout=TL)
        pg.reload()
        pg.wait_for_function("() => !!document.querySelector('[data-k=auto_sync]') && !!document.querySelector('#pon')", timeout=TL)
        quiet(pg, 3000, 500)
        assert pg.locator("[data-k=auto_sync]").is_checked() and not pg.locator("#pon").is_checked()
        pg.locator("#pon").check()
        pg.locator("[data-k=auto_sync]").uncheck()
        pg.locator("#save").click()
        pg.wait_for_function("() => document.querySelector('#ok') && document.querySelector('#ok').textContent.length > 0", timeout=TL)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("hash_,sel", [("#/tour/r3", "#slopenw"), ("#/stats", "#slopenw"), ("#/trips", "#slopenw")])
def test_seite_anpassen_sitzt_oben_rechts(pw, app, clean, hash_, sel):
    pg = _browser(pw, app, devs=None)
    try:
        pg.goto(f"{app}/{hash_}", timeout=TL)
        pg.wait_for_function("() => !!document.querySelector('#slopen')", timeout=TL)
        quiet(pg, 3000, 500)
        r = pg.evaluate("""() => { const w = document.querySelector('#slopenw'), m = document.querySelector('#main'), a = w.getBoundingClientRect(), b = m.getBoundingClientRect(), v = document.querySelector('#slviews').getBoundingClientRect();
          return {first: m.firstElementChild === w, top: a.top - b.top, right: b.right - v.right}; }""")
        assert r["first"] and r["top"] < 60 and r["right"] < 60, r                                  # erste Zeile der Seite, rechtsbündig
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
