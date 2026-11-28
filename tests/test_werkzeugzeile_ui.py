"""3.37.1 – Werkzeugzeile auf dem Handy (390 px, Chromium mit isMobile/hasTouch, Klasse html.mob) und Kartenseite ohne Höhensprung.
Übersicht: EINE schlanke Zeile (Seite anpassen, Ansichten als Menü, Zeitraum als Chip mit aufklappender Auswahl, standardmäßig zu) statt dreier hoher Zeilen; Tastatur und Sprachausgabe (aria-expanded,
aria-controls, Escape), hell und dunkel. Andere Seiten mit Seitenanpassung: einzeilig. Desktop unverändert. Karte: Chips und Knöpfe haben direkt nach dem Laden und nach Netzwerk-Ruhe dieselbe Höhe.
Wettlauf-Regel: auf den Zustand warten (wait_for_function mit Pfeilfunktionen, expect mit 15 s), nie nur schlafen. Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import datetime
import os
import time  # noqa: F401

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.test_seitenlayout_ui import T, _api, _zr_on, pw  # noqa: F401,E402
from tests.test_reise_seiten_ui import app  # noqa: F401,E402
from tests.test_tourseite_ui import _shot  # noqa: E402
from tests.helpers_ui import quiet  # noqa: E402

TL = 30000
KEYS = ("tour-haupt", "tour-auswertung", "uebersicht", "statistik", "reise", "reisen", "fotos", "karte")
CY = datetime.date.today().year


@pytest.fixture(autouse=True)
def clean(app):
    for k in KEYS:
        _api(app, k, "DELETE")
    yield


def _mob(pw, url, hash_, scheme="light", width=390, height=844, mobile=True, init=None, zr=True):
    """3.37.2: Die Leiste „Zeitraum der Seite“ ist standardmäßig aus; diese Tests schalten sie über das Layout (Feld zrbar) ein (zr=False: Standard).
    Handy-Kontext wie in der Android-App (390 x 844, dpr 2, Touch); fremde Hosts (Kartenkacheln) werden abgewiesen."""
    if zr:
        _zr_on(url)
    b = pw.chromium.launch()
    ctx = b.new_context(locale="de-DE", viewport={"width": width, "height": height}, device_scale_factor=2, is_mobile=mobile, has_touch=mobile, color_scheme=scheme, reduced_motion="reduce")
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/*", lambda r: r.continue_() if r.request.url.startswith(url) else r.abort())
    if init:
        pg.add_init_script(init)
    pg.browser_ = b
    pg.goto(f"{url}/{hash_}", timeout=TL)
    return pg


def _idle(pg):
    """Netzwerk-Ruhe abwarten; läuft im Hintergrund eine Abfrage im Takt (Nachladen von Strecken), reicht nach 10 s der Zustand der Seite."""
    try:
        quiet(pg, 5000)
    except Exception:
        pass


def _dash(pw, url, **kw):
    pg = _mob(pw, url, "#/dash", **kw)
    pg.wait_for_selector("main.home #hlast", timeout=TL)
    pg.wait_for_selector("#zrchip", timeout=T)
    _idle(pg)
    return pg


ZWEITE = """() => { const f = SL.fam; slViewAdd(f, 'Zweite', slLayoutsOf(f, SL.view[f])); slApply(); }"""     # 3.71.1: mit nur einer Ansicht öffnet „Ansichten“ gleich den Dialog (3.71.0, N-06); das Menü braucht eine zweite


def _zweite_ansicht(pg):
    pg.evaluate(ZWEITE)
    pg.wait_for_function("() => !!document.getElementById('slview')", timeout=T)


ROW = """() => { const w = document.getElementById('slopenw'), r = w.getBoundingClientRect(), z = document.getElementById('zrbar'), zr = z.getBoundingClientRect();
  const btn = [...w.querySelectorAll('button')].filter(b => b.offsetParent !== null).map(b => [b.id, Math.round(b.getBoundingClientRect().height), Math.round(b.getBoundingClientRect().width)]);
  return {h: Math.round(r.height), zr: Math.round(zr.height), zrShown: getComputedStyle(z).display !== 'none', btn, mob: document.documentElement.classList.contains('mob'), over: document.documentElement.scrollWidth - innerWidth,
          chipRight: document.getElementById('zrchip').getBoundingClientRect().right}; }"""


# ------------------------------------------------------------------  Übersicht  ------------------------------------------------------------------

@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_uebersicht_eine_schlanke_zeile(pw, app, scheme):
    pg = _dash(pw, app, scheme=scheme)
    try:
        m = pg.evaluate(ROW)
        assert m["mob"] and m["over"] <= 1, m
        assert m["h"] <= 96, m                                                    # vorher 96 (Knopfzeile mit Touren-Knopf) + Leiste „Zeitraum der Seite“ mit 300 px = rund 440 px
        assert not m["zrShown"] and m["zr"] == 0, m                              # Auswahl standardmäßig zu: die Leiste nimmt keinen Platz
        assert {b[0] for b in m["btn"]} >= {"slopen", "slviews", "zrchip"}, m
        assert all(40 <= b[1] <= 48 and b[2] >= 40 for b in m["btn"]), m          # Touch-Ziele 40 bis 48 px
        assert m["chipRight"] <= 390 - 8, m
        chip = pg.locator("#zrchip")
        expect(chip).to_have_attribute("aria-expanded", "false", timeout=T)
        assert chip.get_attribute("aria-controls") == "zrbody"
        assert chip.inner_text().replace("\n", " ").startswith("Zeitraum:") and pg.locator("#zrbody").count() == 1 and not pg.locator("#zrbody").is_visible()
        # Namen für Sprachausgabe: Symbolknöpfe tragen den Text weiter
        assert pg.evaluate("() => document.getElementById('slopen').textContent.trim()") == "Seite anpassen"
        assert pg.evaluate("() => document.getElementById('slviews').textContent.trim()") == "Ansichten"
        assert pg.evaluate("() => document.querySelector('#slopenw .slvw') === null || getComputedStyle(document.querySelector('#slopenw .slvw')).display === 'none'")
        _shot(pg, f"werkzeugzeile-uebersicht-zu-{scheme}.png", full=False)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_zeitraum_chip_klappt_auf_waehlt_und_klappt_zu(pw, app, scheme):
    pg = _dash(pw, app, scheme=scheme)
    try:
        chip, body = pg.locator("#zrchip"), pg.locator("#zrbody")
        chip.click()
        expect(chip).to_have_attribute("aria-expanded", "true", timeout=T)
        expect(body).to_be_visible(timeout=T)
        assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
        assert pg.evaluate("() => [...document.querySelectorAll('#zrbody [data-zr]')].filter(b => b.offsetParent !== null).every(b => b.getBoundingClientRect().height >= 32)")
        _shot(pg, f"werkzeugzeile-uebersicht-zeitraum-auf-{scheme}.png", full=False)
        pg.locator('#zrbody [data-zr="prev"]').click()
        pg.wait_for_function("(y) => location.hash === '#/dash?z=' + y && document.getElementById('zrchip').textContent.includes(String(y))", arg=CY - 1, timeout=T)
        expect(chip).to_have_attribute("aria-expanded", "false", timeout=T)
        expect(body).to_be_hidden(timeout=T)
        assert pg.evaluate("() => document.activeElement.id") == "zrchip"                # Fokus zurück auf den Chip
        assert pg.evaluate(ROW)["h"] <= 96
        _shot(pg, f"werkzeugzeile-uebersicht-gewaehlt-{scheme}.png", full=False)
        # Escape schließt, Fokus bleibt am Chip; Von–bis: die Auswahl bleibt offen, bis „Übernehmen“
        chip.click()
        expect(body).to_be_visible(timeout=T)
        pg.locator('#zrbody [data-zr="c"]').click()
        expect(pg.locator("#zrvon")).to_be_visible(timeout=T)
        pg.keyboard.press("Escape")
        expect(chip).to_have_attribute("aria-expanded", "false", timeout=T)
        assert pg.evaluate("() => document.activeElement.id") == "zrchip"
        chip.click()
        pg.locator("#zrvon [name=von]").fill(f"{CY - 1}-03-01")
        pg.locator("#zrvon [name=bis]").fill(f"{CY - 1}-04-30")
        pg.locator("#zrvon button[type=submit]").click()
        pg.wait_for_function("(y) => location.hash === '#/dash?z=c&von=' + y + '-03-01&bis=' + y + '-04-30'", arg=CY - 1, timeout=T)
        expect(chip).to_have_attribute("aria-expanded", "false", timeout=T)
        assert "–" in chip.inner_text()
        # Zurücksetzen steht in der Auswahl
        chip.click()
        pg.locator('#zrbody [data-zr="reset"]').click()
        pg.wait_for_function("() => location.hash === '#/dash' && document.getElementById('zrchip').textContent.includes('Je Baustein')", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_zeitraum_chip_per_tastatur_und_englisch(pw, app):
    pg = _dash(pw, app)
    try:
        pg.locator("#zrchip").focus()
        pg.keyboard.press("Enter")
        expect(pg.locator("#zrchip")).to_have_attribute("aria-expanded", "true", timeout=T)
        pg.keyboard.press("Tab")                                                        # nächstes Element ist die Auswahl (Reihenfolge im Dokument)
        assert pg.evaluate("() => !!document.activeElement.closest('#zrbar')")
        pg.keyboard.press("Escape")
        expect(pg.locator("#zrchip")).to_have_attribute("aria-expanded", "false", timeout=T)
        pg.evaluate("() => localStorage.setItem('lang', 'en')")
        pg.goto(f"{app}/#/dash?z={CY - 1}")
        pg.reload()
        pg.wait_for_selector("#zrchip", timeout=TL)
        pg.wait_for_function("() => /Period:/.test(document.getElementById('zrchip').textContent)", timeout=T)
        assert pg.locator("#slopen").inner_text().strip() == "Customize page"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_ansichten_menue(pw, app, scheme):
    pg = _dash(pw, app, scheme=scheme)
    try:
        _zweite_ansicht(pg)
        btn = pg.locator("#slviews")
        assert btn.get_attribute("aria-haspopup") == "menu" and btn.get_attribute("aria-expanded") == "false"
        btn.click()
        menu = pg.locator("#slvmenu")
        expect(menu).to_be_visible(timeout=T)
        assert menu.get_attribute("role") == "menu" and btn.get_attribute("aria-expanded") == "true" and btn.get_attribute("aria-controls") == "slvmenu"
        assert pg.evaluate("() => [...document.querySelectorAll('#slvmenu button')].every(b => b.getBoundingClientRect().height >= 44)")
        assert pg.evaluate("() => { const r = document.getElementById('slvmenu').getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth && r.bottom <= innerHeight; }")
        _shot(pg, f"werkzeugzeile-ansichten-menue-{scheme}.png", full=False)
        pg.keyboard.press("Escape")
        expect(menu).to_have_count(0, timeout=T)
        assert pg.evaluate("() => document.activeElement.id") == "slviews" and btn.get_attribute("aria-expanded") == "false"
        # Ungespeicherte Änderung des Zeitraums: Punkt am Knopf und „Ansicht speichern …“ im Menü
        pg.locator("#zrchip").click()
        pg.locator('#zrbody [data-zr="12m"]').click()
        pg.wait_for_function("() => document.getElementById('slviews').classList.contains('slvd')", timeout=T)
        assert pg.evaluate("() => getComputedStyle(document.querySelector('#slviews .slvdot')).display") == "block"
        btn.click()
        save = pg.locator('#slvmenu [data-m="save"]')
        expect(save).to_be_visible(timeout=T)
        assert save.inner_text() == "Ansicht speichern …"
        _shot(pg, f"werkzeugzeile-ansichten-menue-geaendert-{scheme}.png", full=False)
        save.click()
        pg.wait_for_selector('.slmenu [data-m="here"]', timeout=T)                      # derselbe Dialog wie auf dem Desktop
        pg.locator(".slmenu [data-m=drop]").click()
        pg.wait_for_function("() => !document.getElementById('slviews').classList.contains('slvd')", timeout=T)
        # Verwalten …: der bekannte Dialog; Fokus danach wieder am Knopf
        btn.click()
        pg.locator('#slvmenu [data-m="manage"]').click()
        pg.wait_for_selector(".slvws .slvr", timeout=T)
        pg.locator(".slvws [data-close]").click()
        pg.wait_for_function("() => !document.querySelector('.slvws')", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_ansichten_menue_wechselt_die_ansicht(pw, app):
    pg = _dash(pw, app)
    try:
        pg.evaluate("() => { slViewAdd('uebersicht', 'Zweite', slLayoutsOf('uebersicht', SL.view.uebersicht)); slApply(); }")
        pg.wait_for_function("() => !!document.getElementById('slview')", timeout=T)
        first = pg.evaluate("() => SL.view.uebersicht")
        pg.locator("#slviews").click()
        items = pg.locator('#slvmenu [role="menuitemradio"]')
        expect(items).to_have_count(2, timeout=T)
        assert [x.get_attribute("aria-checked") for x in items.all()].count("true") == 1
        pg.locator('#slvmenu [role="menuitemradio"][aria-checked="false"]').click()
        pg.wait_for_function("(f) => SL.view.uebersicht !== f && !document.getElementById('slvmenu')", arg=first, timeout=T)
        assert pg.evaluate("() => document.activeElement.id") == "slviews"
        pg.wait_for_selector("#zrchip", timeout=T)
        assert pg.evaluate(ROW)["h"] <= 96
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  andere Seiten, Desktop  ------------------------------------------------------------------

@pytest.mark.parametrize("seite", ["#/stats", "#/photos", "#/trips"])
def test_andere_seiten_einzeilig(pw, app, seite):
    pg = _mob(pw, app, seite)
    try:
        pg.wait_for_selector("#slopen", timeout=TL)
        _idle(pg)
        _zweite_ansicht(pg)
        m = pg.evaluate("() => { const w = document.getElementById('slopenw'); return {h: Math.round(w.getBoundingClientRect().height), n: [...w.querySelectorAll('button')].filter(b => b.offsetParent !== null).length, "
                        "small: [...w.querySelectorAll('button')].filter(b => b.offsetParent !== null && (b.getBoundingClientRect().height < 40 || b.getBoundingClientRect().width < 40)).length, over: document.documentElement.scrollWidth - innerWidth, "
                        "sel: !!document.querySelector('#slopenw .slvw') && getComputedStyle(document.querySelector('#slopenw .slvw')).display !== 'none'}; }")
        assert m["h"] <= 48 and m["n"] == 2 and not m["small"] and m["over"] <= 1 and not m["sel"], m
        assert pg.locator("#zrchip").count() == 0                                     # nur die Übersicht hat den Zeitraum der Seite
        pg.locator("#slviews").click()
        expect(pg.locator("#slvmenu")).to_be_visible(timeout=T)
        pg.keyboard.press("Escape")
        pg.locator("#slopen").click()
        pg.wait_for_selector("#slbar", timeout=T)                                      # Bearbeitungsmodus startet wie bisher
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_desktop_unveraendert(pw, app):
    pg = _mob(pw, app, "#/dash", width=1280, height=900, mobile=False)
    try:
        pg.wait_for_selector("main.home #hlast", timeout=TL)
        pg.wait_for_selector("#zrbar .zrtog", timeout=T)
        assert pg.evaluate("() => !document.documentElement.classList.contains('mob')")
        assert pg.locator("#zrchip").count() == 0
        assert pg.locator("#zrbar .zrtog").get_attribute("aria-expanded") == "true" and pg.locator("#zrbody").is_visible()
        assert pg.locator("#slopen").inner_text().strip() == "Seite anpassen" and pg.locator("#slviews").inner_text().strip() == "Ansichten"
        assert pg.evaluate("() => getComputedStyle(document.querySelector('#slviews .sli')).display") == "none"
        assert pg.evaluate("() => getComputedStyle(document.querySelector('#slviews .slvdot')).display") == "none"
        assert pg.evaluate("() => document.getElementById('slviews').getAttribute('aria-haspopup')") == "dialog"
        pg.locator("#slviews").click()
        pg.wait_for_selector(".slvws .slvr", timeout=T)                              # Dialog, kein Menü
        assert pg.locator("#slvmenu").count() == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Karte  ------------------------------------------------------------------

# Zeichnet ab Seitenstart in jedem Einzelbild die Höhe der Bedienfelder (Reihe, Kästen, Chips, Knöpfe, Auswahl): erste, kleinste, größte und letzte Höhe je Element
SAMPLER = """() => { window.__ka = {}; const t0 = performance.now();
  const tick = () => { const u = document.querySelector('.mapui');
    if (u) { const els = [u, ...u.querySelectorAll('.chip, .btn, select, .box')], seen = {};
      els.forEach(e => { const r = e.getBoundingClientRect(); if (!r.height) return; const base = (e.id || (e.className || e.tagName).toString().replace(/\\s+/g, '.')), n = seen[base] = (seen[base] || 0) + 1, k = base + '#' + n;
        const o = window.__ka[k] || (window.__ka[k] = {first: Math.round(r.height * 10) / 10, min: r.height, max: r.height, at: Math.round(performance.now() - t0)}); o.min = Math.min(o.min, r.height); o.max = Math.max(o.max, r.height); o.last = r.height; }); }
    requestAnimationFrame(tick); };
  tick(); }"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_karte_chips_ohne_hoehensprung(pw, app, scheme):
    """Ursache bis 3.37.0: „Seite anpassen / Ansichten“ (#slopenw) wird erst NACH dem Aufbau in die Reihe der Bedienfelder gesetzt (kaAfter) und zog als zweizeiliger Kasten die ganze Reihe von 54 auf 110 px hoch."""
    pg = _mob(pw, app, "#/map", scheme=scheme, init="(" + SAMPLER + ")()")
    try:
        pg.wait_for_selector(".mapui .chip", state="attached", timeout=TL)
        pg.wait_for_function("() => !!document.querySelector('#kax #bigmap') && typeof map !== 'undefined' && !!map && !!document.querySelector('.mapui #slopen') && document.getElementById('bigmap').clientWidth > 300", timeout=TL)
        _idle(pg)
        quiet(pg, 1500)                                                      # nach Netzwerk-Ruhe noch 1,5 s: späte Skripte und Stile haben gegriffen
        rec = pg.evaluate("() => window.__ka")
        assert len(rec) >= 6, rec                                                 # 3.43.0: am Handy sind nur Standort, „Filter & Ebenen“ und „Seite anpassen“ sichtbar
        jumps = {k: v for k, v in rec.items() if v["max"] - v["min"] > 1 or abs(v["last"] - v["first"]) > 1}
        assert not jumps, jumps                                                       # Höhe direkt nach dem Laden (erstes Bild) = nach 1,5 s Ruhe, auch zwischendurch nie anders (Toleranz 1 px)
        chips = {k: v for k, v in rec.items() if (k.startswith("chip") and not k.startswith("chip.kapt")) or k.startswith(("mloc", "mfb"))}
        assert chips and all(v["max"] <= 44 and v["min"] == v["max"] == v["first"] for v in chips.values()), chips            # Mobilgröße der Chips: 3.71.0 (M-07) mindestens 44 px; geprüft wird weiter, dass sie nicht springen (gleiche Höhe von Anfang an)
        assert rec["mapui#1"]["last"] <= 60, rec["mapui#1"]                            # die Reihe der Bedienfelder bleibt eine schlanke Zeile
        bt = pg.evaluate("() => [...document.querySelectorAll('.kaopen .btn')].filter(b => b.offsetParent !== null).map(b => Math.round(b.getBoundingClientRect().height))")
        assert bt and all(40 <= h <= 44 for h in bt), bt
        assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
        _shot(pg, f"werkzeugzeile-karte-{scheme}.png", full=False)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_karte_ansichten_menue_nicht_abgeschnitten(pw, app):
    pg = _mob(pw, app, "#/map")
    try:
        pg.wait_for_selector(".mapui #slviews", state="attached", timeout=TL)
        _idle(pg)
        _zweite_ansicht(pg)
        pg.evaluate("() => { document.querySelector('.mapui').scrollLeft = 9999; }")
        pg.locator("#slviews").click()
        expect(pg.locator("#slvmenu")).to_be_visible(timeout=T)
        assert pg.evaluate("() => { const r = document.getElementById('slvmenu').getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth && r.height > 40; }")
        pg.keyboard.press("Escape")
        expect(pg.locator("#slvmenu")).to_have_count(0, timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
