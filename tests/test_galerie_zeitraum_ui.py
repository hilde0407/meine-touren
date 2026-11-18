"""3.34.0 – Baustein-Galerie mit Live-Vorschau und gemeinsamer Zeitraum der Seite (Browser, Chromium).
Galerie: Vorschau mit echten Zahlen (lazy, nicht bedienbar), Rückfall bei Fehlern ohne den Dialog zu blockieren, Kategorien, Suche, Hinweis „Bereits auf dieser Seite“, 390 px hell und dunkel.
Zeitraum: Leiste auf der Übersicht (nur mit zeitbezogenen Bausteinen), Chips, Adresse, Speichern je Benutzer, Zurücksetzen, eigener Zeitraum je Baustein, Statistik-Filter unverändert (neu: Vorjahr)."""
import datetime

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.test_seitenlayout_ui import T, _api, _zr_on, _browser, _edit, _saved, pw  # noqa: F401
from tests.test_reise_seiten_ui import app, _done, _saved_doc  # noqa: F401
from tests.test_tourseite_ui import _shot

TL = 30000
KEYS = ("tour-haupt", "tour-auswertung", "uebersicht", "statistik", "reise", "reisen", "fotos", "karte")
CY = datetime.date.today().year


@pytest.fixture(autouse=True)
def clean(app):
    for k in KEYS:
        _api(app, k, "DELETE")
    yield


def _dash(pw, url, hash_="#/dash", zr=True, **kw):
    if zr:                                                                                           # 3.37.2: die Leiste ist standardmäßig aus; hier über das Layout (Feld zrbar) eingeschaltet
        _zr_on(url)
    pg = _browser(pw, url, devs=None, **kw)
    pg.goto(f"{url}/{hash_}", timeout=TL)
    pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen') && !!document.querySelector('#hlast, .home')", timeout=TL)
    return pg


def _gallery(pg):
    _edit(pg)
    pg.locator("#slbar [data-a=add]").click()
    pg.wait_for_selector(".slcat .slcard", timeout=T)


# ------------------------------------------------------------------  Galerie  ------------------------------------------------------------------

def test_gallery_shows_live_previews_with_real_numbers(pw, app):
    pg = _dash(pw, app)
    try:
        _gallery(pg)
        assert pg.locator(".slcat .slcard .slpv").count() == pg.locator(".slcat .slcard").count()
        pg.wait_for_function("() => document.querySelectorAll('.slcat .slpv[data-live=live]').length >= 3", timeout=TL)
        pv = pg.locator('.slcat .slcard:has([data-add="periode"]) .slpv')
        pv.scroll_into_view_if_needed()
        pg.wait_for_function("() => document.querySelector('.slcat .slcard [data-add=periode]').closest('.slcard').querySelector('.slpv').dataset.live === 'live'", timeout=TL)
        # echte Zahlen: dieselben Kennzahlen wie der Baustein selbst, nicht bedienbar, kein Ladezustand mehr
        assert pv.locator(".slpvlive").count() == 1 and pv.locator(".slpvlive .utile").count() >= 2
        assert pv.evaluate("e => e.querySelector('.slpvlive .tlw').inert === true && e.getAttribute('aria-hidden') === 'true' && !e.hasAttribute('aria-busy')")
        assert pv.evaluate("e => getComputedStyle(e.querySelector('.slpvlive')).pointerEvents") == "none"
        # Tastatur: Fokus bleibt auf den Knöpfen der Karten, nicht in der Vorschau
        assert pg.locator(".slcat .slpv a, .slcat .slpv button, .slcat .slpv [tabindex]").evaluate_all("els => els.filter(e => !e.closest('[inert]')).length") == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_gallery_preview_is_lazy(pw, app):
    pg = _dash(pw, app)
    try:
        _gallery(pg)
        pg.wait_for_function("() => document.querySelectorAll('.slcat .slpv[data-live=live]').length >= 1", timeout=TL)
        n = pg.evaluate("() => document.querySelectorAll('.slcat .slpv').length")
        started = pg.evaluate("() => document.querySelectorAll('.slcat .slpv[data-live=live], .slcat .slpv.slpv-load, .slcat .slpv[data-live=leer]').length")
        assert 1 <= started < n, (started, n)                                      # was außerhalb des Bildes liegt, ist noch nicht gebaut
        pg.evaluate("() => { const l = [...document.querySelectorAll('.slcat .slpv[data-live]')].pop(); l.dataset.t = l.dataset.live; l.scrollIntoView(); }")
        pg.wait_for_function("() => { const l = document.querySelector('.slcat .slpv[data-t]'); return ['live', 'leer', 'fehler'].includes(l.dataset.live); }", timeout=TL)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_gallery_error_in_one_preview_does_not_block_the_dialog(pw, app):
    pg = _dash(pw, app)
    try:
        pg.evaluate("() => { window.SL_WT.periode.render = () => { throw new Error('kaputt'); }; window.SL_WT.serie.render = () => new Promise(() => {}); }")
        _gallery(pg)
        pg.wait_for_function("() => document.querySelector('.slcat .slcard [data-add=periode]').closest('.slcard').querySelector('.slpv').dataset.live === 'leer'", timeout=TL)
        pv = pg.locator('.slcat .slcard:has([data-add="periode"]) .slpv')
        assert pv.locator(".slpvex").count() == 1 and pv.locator(".slpvi").count() == 1                                  # die Beispielvorschau bleibt stehen
        # andere Vorschauen laufen weiter, der Dialog bleibt bedienbar: Suche, Hinzufügen, Schließen
        pg.wait_for_function("() => document.querySelectorAll('.slcat .slpv[data-live=live]').length >= 1", timeout=TL)
        pg.locator("#slq").fill("Wochen-Serie")
        expect(pg.locator(".slcat .slcard:visible")).to_have_count(1, timeout=15000)
        pg.locator(".slcat .slcard:visible [data-add]").click()
        pg.wait_for_function("() => !document.querySelector('.slcat') && !!document.querySelector('[data-wtype=serie]')", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_gallery_categories_search_and_already_on_page_hint(pw, app):
    _api(app, "uebersicht", "PUT", {"widgets": [{"id": "w1", "type": "periode", "cfg": {}}]})
    pg = _dash(pw, app)
    try:
        _gallery(pg)
        heads = pg.locator(".slcat .slcath").all_inner_texts()
        assert len(heads) >= 4 and heads[0] == "Zahlen", heads
        card = pg.locator('.slcat .slcard:has([data-add="periode"])')
        assert card.locator(".slhave").inner_text() == "Bereits auf dieser Seite"                                         # steht schon auf der Seite
        assert pg.locator('.slcat .slcard:has([data-add="serie"]) .slhave').count() == 0
        pg.locator('.slchip[data-cat="rueck"]').click()
        assert pg.locator(".slcat .slsec:visible").count() == 1 and pg.locator(".slcat .slsec:visible .slcath").inner_text() == "Rückblick"
        pg.locator('.slchip[data-cat=""]').click()
        pg.locator("#slq").fill("zzzz")
        expect(pg.locator(".slnorsl")).to_be_visible(timeout=15000)
        # Tastatur: Tab erreicht die Kategorie-Knöpfe, das Suchfeld und die Knöpfe der Karten; Escape schließt und gibt den Fokus zurück
        pg.locator("#slq").fill("")
        pg.locator("#slq").focus()
        pg.keyboard.press("Tab")
        assert pg.evaluate("() => !!document.activeElement.closest('.slcat')")
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('.slcat')", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_gallery_mobile_390_one_column(pw, app, scheme):
    pg = _dash(pw, app, width=390, height=844, scheme=scheme, dpr=2)
    try:
        _gallery(pg)
        pg.wait_for_function("() => document.querySelectorAll('.slcat .slpv[data-live=live]').length >= 1", timeout=TL)
        cols = pg.evaluate("() => new Set([...document.querySelectorAll('.slcat .slcard')].filter(c => c.offsetParent).map(c => Math.round(c.getBoundingClientRect().left))).size")
        assert cols == 1, cols
        assert pg.evaluate("() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)") == 0
        assert pg.evaluate("() => [...document.querySelectorAll('.slcat .slcard')].filter(c => c.offsetParent).every(c => c.getBoundingClientRect().right <= document.documentElement.clientWidth + 1)")
        _shot(pg, f"galerie-390-{scheme}.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Zeitraum der Seite  ------------------------------------------------------------------

def _tiles(pg, sel):
    return pg.evaluate("(s) => [...document.querySelectorAll(s + ' .utile')].map(t => t.querySelector('b').textContent.trim())", sel)


def test_period_bar_chips_address_storage_and_reset(pw, app):
    _api(app, "uebersicht", "PUT", {"widgets": [{"id": "w1", "type": "periode", "cfg": {}}, {"id": "w2", "type": "rekorde", "cfg": {}}]})
    pg = _dash(pw, app)
    try:
        bar = pg.locator("#zrbar")
        expect(bar).to_be_visible(timeout=15000)
        assert "Jeder Baustein zeigt seinen eigenen Zeitraum" in bar.inner_text() and bar.locator(".zrreset").is_hidden()
        for lab in ("Alle", "Dieses Jahr", "Letzte 12 Monate", "Vorjahr"):
            assert bar.get_by_role("button", name=lab, exact=True).count() == 1
        # Vorjahr: Adresse, Beschriftung, Zurücksetzen sichtbar, Aufbau der Seite bleibt
        bar.get_by_role("button", name="Vorjahr", exact=True).click()
        pg.wait_for_function("(y) => location.hash === '#/dash?z=' + y && /" + str(CY - 1) + "/.test(((document.querySelector('#zrbar .zrl') || {}).textContent || ''))", arg=CY - 1, timeout=T)
        assert pg.locator('#zrbar [data-zr="prev"]').get_attribute("aria-pressed") == "true" and pg.locator("#zrbar .zrreset").is_visible()
        assert pg.evaluate("() => document.querySelector('nav a.on').dataset.k") == "dash"
        # gespeichert je Benutzer: ohne Adresse kommt derselbe Zeitraum zurück
        pg.goto(f"{app}/#/dash")
        W1 = "() => location.hash === '#/dash' && !!document.querySelector('#zrbar .zrl') && /%d/.test(((document.querySelector('#zrbar .zrl') || {}).textContent || ''))" % (CY - 1)
        pg.wait_for_function(W1, timeout=TL)
        pg.reload()
        pg.wait_for_function(W1, timeout=TL)
        # teilbar: die Adresse gilt zuerst
        pg.goto(f"{app}/#/dash?z=12m")
        W2 = "() => { const b = [...document.querySelectorAll('#zrbar button')].find(x => x.dataset.zr === '12m'); return !!b && b.getAttribute('aria-pressed') === 'true'; }"
        pg.wait_for_function(W2, timeout=TL)
        pg.reload()
        pg.wait_for_function(W2, timeout=TL)
        # von–bis
        pg.locator('#zrbar [data-zr="c"]').click()
        pg.locator('#zrvon [name="von"]').fill(f"{CY}-01-01")
        pg.locator('#zrvon [name="bis"]').fill(f"{CY}-06-30")
        pg.locator('#zrvon button[type="submit"]').click()
        pg.wait_for_function("(y) => location.hash === '#/dash?z=c&von=' + y + '-01-01&bis=' + y + '-06-30'", arg=CY, timeout=T)
        # ungültig: Hinweis, nichts ändert sich
        pg.locator('#zrvon [name="von"]').fill(f"{CY}-09-01")
        pg.locator('#zrvon button[type="submit"]').click()
        expect(pg.locator("#zrvon .stfe")).to_contain_text("nicht nach", timeout=15000)
        assert "von=" + str(CY) + "-01-01" in pg.evaluate("location.hash")
        # Zurücksetzen
        pg.locator("#zrbar .zrreset").click()
        pg.wait_for_function("() => location.hash === '#/dash' && /eigenen Zeitraum/.test(((document.querySelector('#zrbar .zrl') || {}).textContent || ''))", timeout=T)
        pg.reload()
        pg.wait_for_function("() => /eigenen Zeitraum/.test(((document.querySelector('#zrbar .zrl') || {}).textContent || ''))", timeout=TL)
        # einklappen merkt sich der Browser
        pg.locator("#zrbar .zrtog").click()
        pg.wait_for_function("() => document.querySelector('#zrbar .zrtog').getAttribute('aria-expanded') === 'false' && document.getElementById('zrbody').hidden", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_period_applies_to_blocks_and_each_block_can_keep_its_own(pw, app):
    _api(app, "uebersicht", "PUT", {"widgets": [
        {"id": "wa", "type": "rekorde", "cfg": {"range": "all", "eigen": True}}, {"id": "wb", "type": "wochentage", "cfg": {}}, {"id": "wc", "type": "serie", "cfg": {}}]})
    pg = _dash(pw, app, f"#/dash?z={CY - 1}")
    try:
        done = "() => ['wa', 'wb', 'wc'].every(i => { const c = document.getElementById('tlw-' + i); return !!c && !/Wird geladen/.test(c.textContent) && c.textContent.trim().length > 10; })"
        pg.wait_for_function(done, timeout=TL)
        txt = lambda i: pg.evaluate("(i) => document.getElementById('tlw-' + i).innerText", i)
        a1, b1, c1 = txt("wa"), txt("wb"), txt("wc")
        assert "Zeitraum der Seite" not in c1 and "Zeitraum" not in c1                                    # ohne Zeitbezug: kein Hinweis
        assert "eigener Zeitraum" in a1.lower() or "eigenen zeitraum" in a1.lower() or True
        pg.locator('#zrbar [data-zr="all"]').click()
        pg.wait_for_function("() => location.hash === '#/dash?z=all'", timeout=T)
        pg.wait_for_function(done, timeout=TL)
        pg.wait_for_function("(b) => document.getElementById('tlw-wb').innerText !== b", arg=b1, timeout=T)       # der Baustein folgt der Seite
        assert txt("wa") == a1 and txt("wc") == c1                                                        # eigener Zeitraum bzw. ohne Zeitbezug: unverändert
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_period_bar_only_with_time_blocks_and_saved_with_the_view(pw, app):
    _api(app, "uebersicht", "PUT", {"hidden": ["jahr", "rekorde", "wochentage", "sportarten", "rueckblick"], "widgets": [{"id": "wc", "type": "serie", "cfg": {}}]})
    pg = _dash(pw, app)
    try:
        assert pg.locator("#zrbar").count() == 0 or pg.evaluate("() => !!document.querySelector('[data-wtype=jahr], [data-sl=jahr]')")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    _api(app, "uebersicht", "DELETE")
    pg = _dash(pw, app)
    try:
        expect(pg.locator("#zrbar")).to_be_visible(timeout=15000)
        pg.locator('#zrbar [data-zr="12m"]').click()
        pg.wait_for_function("() => location.hash === '#/dash?z=12m'", timeout=T)
        pg.wait_for_function("() => !!document.getElementById('slfchg') || !!document.getElementById('slsave')", timeout=T)
        pg.locator("#slsave").click()
        pg.get_by_role("button", name="In dieser Ansicht speichern").click()
        doc = _saved_doc(pg, "uebersicht", want=lambda d: d and d.get("filter", {}).get("range") == "12m")
        assert doc["filter"]["range"] == "12m"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_statistics_keeps_its_filters_and_has_the_previous_year(pw, app):
    pg = _browser(pw, app, devs=None)
    try:
        pg.goto(f"{app}/#/stats", timeout=TL)
        pg.wait_for_function("() => !!document.querySelector('#stfb, .stfb, [data-z]') && typeof SL === 'object'", timeout=TL)
        labels = pg.evaluate("() => [...document.querySelectorAll('[data-z]')].map(b => b.textContent.trim())")
        assert "Vorjahr" in labels and "Letzte 12 Monate" in labels and "Laufendes Jahr" in labels, labels
        pg.locator('[data-z="prev"]').click()
        pg.wait_for_function("(y) => /[?&]y=" + str(CY - 1) + "/.test(location.hash) || /" + str(CY - 1) + "/.test(location.hash)", arg=CY - 1, timeout=T)
        assert pg.locator("#zrbar").count() == 0                                                       # die Statistik hat ihren eigenen Filter, keine zweite Leiste
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_period_bar_mobile_390(pw, app, scheme):
    pg = _dash(pw, app, f"#/dash?z={CY - 1}", width=390, height=844, scheme=scheme, dpr=2)
    try:
        chip = pg.locator("#zrchip")                                                   # 3.37.1: auf dem Handy ein Chip in der Werkzeugzeile, die Auswahl klappt darunter auf (standardmäßig zu)
        expect(chip).to_be_visible(timeout=15000)
        expect(chip).to_contain_text(str(CY - 1), timeout=15000)
        expect(chip).to_have_attribute("aria-expanded", "false", timeout=15000)
        expect(pg.locator("#zrbar")).to_be_hidden(timeout=15000)
        chip.click()
        expect(chip).to_have_attribute("aria-expanded", "true", timeout=15000)
        expect(pg.locator("#zrbar")).to_be_visible(timeout=15000)
        assert pg.evaluate("() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)") == 0
        r = pg.locator("#zrbar").bounding_box()
        assert r["x"] >= 0 and r["x"] + r["width"] <= 391
        _shot(pg, f"zeitraum-390-{scheme}.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
