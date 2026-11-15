"""3.20.0 – Raster und seitenübergreifende Bausteine (Browser, Chromium).
Breite je Abschnitt (Umschalter im Bearbeitungsmodus), Raster nebeneinander ab 900 px, zwei Spalten auf dem Tablet, eine Spalte bis 640 px (390 px ohne seitliches Scrollen),
Tab-Reihenfolge = DOM-Reihenfolge, Ziehen und Tastatur in Leserichtung, Karte nach Breitenänderung, „Dein Jahr“ auf der Tourseite, tour-bezogene Bausteine nicht in der Übersicht, Kontrast.
Wettlauf-Regel wie in test_seitenlayout_ui.py: nach jeder Aktion auf den Zustand warten (wait_for_function/expect mit 15 s), nie nur schlafen.
Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt (Chromium, dpr 2)."""
import pytest

from tests.test_seitenlayout_ui import (T, _api, _browser, _dash, _edit, _grip, _saved, _server, _tour, app, clean, pw)      # noqa: F401  (Fixtures werden hier gebraucht)
from tests.test_tourseite_ui import CONTRAST, _shot

W = {"jahr": "wj1", "serie": "ws1"}
HAUPT = {"widgets": [{"id": "wk1", "type": "kennzahlen", "cfg": {}}, {"id": "wt1", "type": "tempo", "cfg": {}}, {"id": "wj1", "type": "jahr", "cfg": {}}, {"id": "ws1", "type": "serie", "cfg": {}},
                     {"id": "wm1", "type": "meilensteine", "cfg": {}}, {"id": "wn1", "type": "notiz", "cfg": {"text": "Rast am Bach, Rückweg über den Grat."}}]}
UEBER = {"widgets": [{"id": "wp1", "type": "periode", "cfg": {}}, {"id": "wv1", "type": "jahresvergleich", "cfg": {}}, {"id": "wl1", "type": "letzte", "cfg": {}}, {"id": "wh1", "type": "heatmap", "cfg": {}},
                     {"id": "ws1", "type": "serie", "cfg": {}}, {"id": "wm1", "type": "meilensteine", "cfg": {}}, {"id": "wz1", "type": "jahresziel", "cfg": {}}, {"id": "wa1", "type": "auffaellig", "cfg": {}},
                     {"id": "wr1", "type": "rekorde", "cfg": {}}, {"id": "wd1", "type": "wochentage", "cfg": {}}, {"id": "wo1", "type": "sportarten", "cfg": {}}]}


def _settle(pg, n):
    """Warten, bis n Bausteine ihren Inhalt haben (kein „Wird geladen …“ mehr)."""
    pg.wait_for_function("([n]) => document.querySelectorAll('.tlw[data-wid], .tlw[id^=tlw-]').length >= n && ![...document.querySelectorAll('.slwb .slnone')].some(e => e.textContent.includes('Wird geladen'))", arg=[n], timeout=T)
    pg.wait_for_timeout(600)


@pytest.mark.skipif(not __import__("os").environ.get("TS_SHOTS"), reason="nur mit TS_SHOTS")
@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_screenshots(pw, app, scheme):
    _api(app, "tour-haupt", "PUT", HAUPT)
    _api(app, "uebersicht", "PUT", UEBER)
    for width, tag in ((1280, "1280"), (820, "tablet"), (390, "390")):
        pg = _tour(pw, app, width=width, scheme=scheme, dpr=2)
        try:
            _settle(pg, 6)
            _shot(pg, f"tour-{tag}-{scheme}.png")
            _edit(pg)
            pg.wait_for_timeout(500)
            _shot(pg, f"tour-{tag}-{scheme}-edit.png")
        finally:
            pg.browser_.close()
        pg = _dash(pw, app, width=width, scheme=scheme, dpr=2)
        try:
            _settle(pg, 8)
            _shot(pg, f"dash-{tag}-{scheme}.png")
            _edit(pg)
            pg.wait_for_timeout(500)
            _shot(pg, f"dash-{tag}-{scheme}-edit.png")
        finally:
            pg.browser_.close()


# ------------------------------------------------------------------  Tests  ------------------------------------------------------------------

BOX = """(sels) => Object.fromEntries(sels.map(s => { const e = document.querySelector(s); if (!e) return [s, null]; const r = e.getBoundingClientRect(); return [s, {x: r.x, y: r.y, w: r.width, h: r.height}]; }))"""
NOSCROLL = "() => document.documentElement.scrollWidth <= window.innerWidth + 1"
DOMORDER = "() => [...document.querySelectorAll('#tl .tlgb > *')].filter(e => getComputedStyle(e).display !== 'none').map(e => e.dataset.tls || e.dataset.sl || e.id)"


def _boxes(pg, *sels):
    return pg.evaluate(BOX, list(sels))


def test_default_tour_page_puts_small_sections_side_by_side_at_1280(pw, app):
    pg = _tour(pw, app)
    try:
        b = _boxes(pg, "#tls-map", "#tls-prof", "#tls-puls", "#tls-wp")
        assert abs(b["#tls-map"]["w"] - b["#tls-prof"]["w"]) < 2 and b["#tls-map"]["w"] > 1000          # Karte und Höhenprofil: ganze Breite
        assert b["#tls-puls"]["y"] == b["#tls-wp"]["y"] and b["#tls-puls"]["x"] < b["#tls-wp"]["x"]       # Herzfrequenz und Wegpunkte nebeneinander
        assert abs(b["#tls-puls"]["w"] - b["#tls-wp"]["w"]) < 2 and b["#tls-puls"]["w"] < b["#tls-map"]["w"] * 0.55
        assert abs(b["#tls-puls"]["h"] - b["#tls-wp"]["h"]) < 2                                         # gleiche Höhe in der Zeile
        assert [h.strip() for h in pg.locator("#tl .tlgh").all_inner_texts()] == ["Streckenverlauf", "Auswertung dieser Tour", "Fotos zur Tour"]
        assert pg.evaluate(NOSCROLL) and not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_width_switch_changes_layout_and_is_saved_and_reload_keeps_it(pw, app):
    pg = _tour(pw, app)
    try:
        _edit(pg)
        sw = pg.locator('.slit[data-sl="puls"] .slw')
        assert sw.count() == 4 and pg.locator('.slit[data-sl="puls"] .slw[aria-pressed="true"]').get_attribute("data-w") == "halb"
        assert pg.locator('.slit[data-sl="sum"] .slw').count() == 0                                   # der Einstieg bleibt ganz breit
        pg.locator('.slit[data-sl="puls"] .slw[data-w="voll"]').click()
        pg.wait_for_function("() => document.querySelector('.slit[data-sl=\"puls\"]').classList.contains('w-voll')", timeout=T)
        pg.wait_for_function("() => document.querySelector('.slit[data-sl=\"puls\"] .slw[data-w=\"voll\"]').getAttribute('aria-pressed') === 'true'", timeout=T)
        assert pg.evaluate("() => document.activeElement && document.activeElement.dataset.w") == "voll"       # Fokus bleibt auf dem Umschalter
        _saved(pg)
        assert _server(app, "tour-haupt")["w"] == {"puls": "voll"}
        b = _boxes(pg, '.slit[data-sl="puls"]', '.slit[data-sl="wp"]')
        assert b['.slit[data-sl="wp"]']["y"] > b['.slit[data-sl="puls"]']["y"] + 50                    # jetzt untereinander
        pg.locator('.slit[data-sl="puls"] .slw[data-w="halb"]').click()                                # zurück auf den Standard: nichts mehr gespeichert
        pg.wait_for_function("() => document.querySelector('.slit[data-sl=\"puls\"]').classList.contains('w-halb')", timeout=T)
        pg.wait_for_function("() => { const s = document.getElementById('slsaved'); return !!s && s.textContent.trim() === 'Gespeichert'; }", timeout=T)
        assert "w" not in _server(app, "tour-haupt")
        pg.locator('.slit[data-sl="wp"] .slw[data-w="drittel"]').click()
        pg.wait_for_function("() => document.querySelector('.slit[data-sl=\"wp\"]').dataset.cw === 'drittel'", timeout=T)
        _saved(pg)
        pg.reload()
        pg.wait_for_function("() => !!document.querySelector('#wpcard') && !!document.querySelector('#slopen')", timeout=T)
        pg.wait_for_function("() => document.querySelector('#wpcard').classList.contains('w-drittel')", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_row_rest_is_filled_so_there_is_no_gap(pw, app):
    _api(app, "tour-haupt", "PUT", {"w": {"wp": "drittel"}})
    pg = _tour(pw, app)
    try:
        pg.wait_for_function("() => document.querySelector('#wpcard').classList.contains('w-drittel')", timeout=T)
        pg.wait_for_function("() => document.querySelector('#wpcard').classList.contains('fd-6') && document.querySelector('#pulscard').classList.contains('w-halb')", timeout=T)
        b = _boxes(pg, "#tls-puls", "#tls-wp", "#tls-map")
        assert abs(b["#tls-puls"]["w"] + b["#tls-wp"]["w"] + 16 - b["#tls-map"]["w"]) < 3           # halb + (drittel, aufgefüllt auf halb) = ganze Zeile
    finally:
        pg.browser_.close()
    _api(app, "tour-haupt", "PUT", {"w": {"puls": "zweidrittel", "wp": "zweidrittel"}})
    pg = _tour(pw, app)
    try:
        pg.wait_for_function("() => ['#pulscard', '#wpcard'].every(s => document.querySelector(s).classList.contains('fd-12'))", timeout=T)      # je allein in der Zeile: ganze Breite
        b = _boxes(pg, "#tls-wp", "#tls-map")
        assert abs(b["#tls-wp"]["w"] - b["#tls-map"]["w"]) < 2
    finally:
        pg.browser_.close()


def test_tablet_has_two_columns_and_390_one_without_horizontal_scroll(pw, app):
    _api(app, "tour-haupt", "PUT", HAUPT)
    pg = _tour(pw, app, width=820)
    try:
        _settle(pg, 6)
        b = _boxes(pg, "#tls-puls", "#tls-wp", "#tlw-wk1", "#tlw-wt1")
        assert b["#tls-puls"]["y"] == b["#tls-wp"]["y"] and b["#tlw-wk1"]["y"] == b["#tlw-wt1"]["y"]
        assert pg.evaluate(NOSCROLL)
    finally:
        pg.browser_.close()
    pg = _tour(pw, app, width=390)
    try:
        _settle(pg, 6)
        b = _boxes(pg, "#tls-puls", "#tls-wp", "#tlw-wk1", "#tlw-wt1", "#tlw-wj1")
        assert b["#tls-wp"]["y"] > b["#tls-puls"]["y"] and b["#tlw-wt1"]["y"] > b["#tlw-wk1"]["y"]
        assert abs(b["#tls-puls"]["x"] - b["#tls-wp"]["x"]) < 1 and b["#tlw-wj1"]["w"] > 330
        assert pg.evaluate(NOSCROLL)
        _edit(pg)
        pg.wait_for_function("() => document.querySelectorAll('.slw').length > 8", timeout=T)
        assert pg.evaluate(NOSCROLL) and not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_overview_grid_default_and_390(pw, app):
    pg = _dash(pw, app)
    try:
        b = _boxes(pg, "#hlast", "#hyear", "#hrecent", "#htag")
        assert b["#hlast"]["w"] > 1000 and b["#hyear"]["w"] > 1000 and b["#hrecent"]["w"] > 1000
        assert pg.evaluate(NOSCROLL)
    finally:
        pg.browser_.close()
    _api(app, "uebersicht", "PUT", UEBER)
    pg = _dash(pw, app)
    try:
        _settle(pg, 8)
        b = _boxes(pg, "#tlw-wp1", "#tlw-wv1", "#tlw-wh1")
        assert b["#tlw-wp1"]["y"] == b["#tlw-wv1"]["y"] and b["#tlw-wp1"]["x"] < b["#tlw-wv1"]["x"]       # zwei halbe nebeneinander
        assert b["#tlw-wh1"]["w"] > 1000                                                                   # Heatmap ganz breit
        assert pg.evaluate(NOSCROLL) and not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    pg = _dash(pw, app, width=390)
    try:
        _settle(pg, 8)
        b = _boxes(pg, "#tlw-wp1", "#tlw-wv1")
        assert b["#tlw-wv1"]["y"] > b["#tlw-wp1"]["y"] and pg.evaluate(NOSCROLL)
        _edit(pg)
        assert pg.evaluate(NOSCROLL)
    finally:
        pg.browser_.close()


def test_tab_order_is_dom_order_and_keyboard_moves_in_reading_direction(pw, app):
    _api(app, "tour-haupt", "PUT", HAUPT)
    pg = _tour(pw, app)
    try:
        _settle(pg, 6)
        assert pg.evaluate("() => !document.querySelector('style, link[rel=stylesheet]') || ![...document.styleSheets].some(s => { try { return [...s.cssRules].some(r => /grid-auto-flow:\\s*[^;]*dense|order:\\s*\\d/.test(r.cssText) && /tlgb|slcell|main\\.home/.test(r.cssText)); } catch (e) { return false; } })")
        _edit(pg)
        order = pg.evaluate(DOMORDER)
        assert order.index("puls") < order.index("wp") < order.index("wk1") < order.index("wt1")
        # Tab von Griff zu Griff folgt dem DOM (die Griffe stehen in Dokumentreihenfolge)
        grips = pg.evaluate("() => [...document.querySelectorAll('#tl .slit')].map(w => w.dataset.sl)")
        assert grips.index("puls") < grips.index("wp")
        _grip(pg, "puls").focus()
        pg.keyboard.press("ArrowRight")                                                                    # nach hinten: hinter Wegpunkte
        pg.wait_for_function("() => { const o = [...document.querySelectorAll('#tl .slit')].map(w => w.dataset.sl); return o.indexOf('wp') < o.indexOf('puls'); }", timeout=T)
        _saved(pg)
        assert pg.evaluate("() => document.activeElement.classList.contains('slgrip') && document.activeElement.closest('.slit').dataset.sl") == "puls"
        pg.keyboard.press("ArrowLeft")
        pg.wait_for_function("() => { const o = [...document.querySelectorAll('#tl .slit')].map(w => w.dataset.sl); return o.indexOf('puls') < o.indexOf('wp'); }", timeout=T)
        # Tab-Reihenfolge der Schalter innerhalb der Leiste: Griff, Breite (4), Hoch, Runter …
        pg.locator('.slit[data-sl="wp"] .slgrip').focus()
        seq = []
        for _ in range(7):
            pg.keyboard.press("Tab")
            seq.append(pg.evaluate("() => { const a = document.activeElement; return a.dataset.w || a.dataset.a || ''; }"))
        assert seq[:6] == ["voll", "zweidrittel", "halb", "drittel", "up", "down"], seq
    finally:
        pg.browser_.close()


def test_drag_in_two_dimensions_moves_to_the_right_place(pw, app):
    pg = _tour(pw, app, height=3800)
    try:
        _edit(pg)
        g = _boxes(pg, '.slit[data-sl="puls"] .slgrip', '.slit[data-sl="wp"]')
        gx, gy = g['.slit[data-sl="puls"] .slgrip']["x"] + 20, g['.slit[data-sl="puls"] .slgrip']["y"] + 20
        w = g['.slit[data-sl="wp"]']
        pg.mouse.move(gx, gy)
        pg.mouse.down()
        pg.mouse.move(gx + 60, gy + 10, steps=4)
        pg.mouse.move(w["x"] + w["w"] - 30, w["y"] + 120, steps=6)                                         # rechte Hälfte der Wegpunkte: dahinter einfügen
        pg.wait_for_function("() => !!document.querySelector('.sl-lift')", timeout=T)
        pg.mouse.up()
        pg.wait_for_function("() => { const o = [...document.querySelectorAll('#tl .slit')].map(w => w.dataset.sl); return o.indexOf('wp') < o.indexOf('puls'); }", timeout=T)
        _saved(pg)
        order = _server(app, "tour-haupt")["order"]
        assert order.index("wp") < order.index("puls")
    finally:
        pg.browser_.close()


def test_map_gets_the_new_size_after_a_width_change(pw, app):
    pg = _tour(pw, app)
    try:
        pg.wait_for_function("() => typeof map !== 'undefined' && !!map && !!document.querySelector('#tls-map .leaflet-container')", timeout=T)
        size = "() => ({m: map.getSize().x, c: document.querySelector('#tls-map .leaflet-container').clientWidth})"
        s = pg.evaluate(size)
        assert abs(s["m"] - s["c"]) <= 1 and s["c"] > 900
        _edit(pg)
        pg.locator('.slit[data-sl="prof"] .slw[data-w="halb"]').click()
        pg.locator('.slit[data-sl="map"] .slw[data-w="halb"]').click()                                       # Karte und Höhenprofil nebeneinander
        pg.wait_for_function("() => { const c = document.querySelector('#tls-map .leaflet-container'); return c.clientWidth < 600 && c.clientWidth > 400 && Math.abs(map.getSize().x - c.clientWidth) <= 1; }", timeout=T)
        pg.locator('.slit[data-sl="map"] .slw[data-w="voll"]').click()
        pg.wait_for_function("() => { const c = document.querySelector('#tls-map .leaflet-container'); return c.clientWidth > 900 && Math.abs(map.getSize().x - c.clientWidth) <= 1; }", timeout=T)
        assert pg.locator("#tls-map .leaflet-tile-pane, #tls-map .leaflet-overlay-pane").count() >= 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_dein_jahr_can_be_added_on_the_tour_page_and_tour_widgets_not_on_the_overview(pw, app):
    pg = _tour(pw, app)
    try:
        _edit(pg)
        pg.locator('#slbar [data-a="add"]').click()
        pg.wait_for_selector(".slcard", timeout=T)
        names = pg.locator(".slcard h3").all_inner_texts()
        assert "Dein Jahr" in names and "Kennzahlen-Kachel" in names and "Heute vor X Jahren" in names
        assert "Auffällige Touren" not in names                                                              # nur Übersicht
        pg.locator('.slcard:has(h3:text-is("Dein Jahr")) [data-add]').click()
        pg.wait_for_function("() => !!document.querySelector('.tlw[data-wtype=\"jahr\"], section.hyear.tlw')", timeout=T)
        pg.wait_for_function("() => { const e = document.querySelector('section.hyear.tlw'); return !!e && !!e.querySelector('.hyn b'); }", timeout=T)
        _saved(pg)
        lay = _server(app, "tour-haupt")
        assert [w["type"] for w in lay["widgets"]] == ["jahr"]
        assert pg.evaluate("() => !!document.querySelector('#tlgb-bst section.hyear')")                   # in der Gruppe „Bausteine“
        pg.reload()
        pg.wait_for_selector("section.hyear.tlw .hyn b", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    pg = _dash(pw, app)
    try:
        _edit(pg)
        pg.locator('#slbar [data-a="add"]').click()
        pg.wait_for_selector(".slcard", timeout=T)
        names = pg.locator(".slcard h3").all_inner_texts()
        assert "Dein Jahr" in names and "Auffällige Touren" in names
        assert "Kennzahlen-Kachel" not in names and "Eigene Notiz" not in names and "Puls-Zonen" not in names
    finally:
        pg.browser_.close()


def test_overview_widget_on_the_sub_page_and_a_widget_from_a_newer_page_is_ignored(pw, app):
    _api(app, "tour-haupt", "PUT", {"widgets": [{"id": "wj1", "type": "jahr", "cfg": {}}, {"id": "wx1", "type": "auffaellig", "cfg": {}}], "page": {"wj1": "auswertung", "wx1": "auswertung"}})
    pg = _tour(pw, app, sub=True)
    try:
        pg.wait_for_selector("#tl section.hyear.tlw .hyn b", timeout=T)
        assert pg.locator("#tlw-wx1").count() == 0                                                         # „Auffällige Touren“ darf nur in die Übersicht: ignoriert
    finally:
        pg.browser_.close()


def test_viewer_sees_the_default_grid(pw, app):
    _api(app, "tour-haupt", "PUT", {"w": {"puls": "voll"}})
    pg = _tour(pw, app)
    try:
        pg.wait_for_function("() => document.querySelector('#pulscard').classList.contains('w-voll')", timeout=T)
        pg.evaluate("ME.user = {role: 'viewer', uid: 9, name: 'Oma'}; document.documentElement.classList.add('viewer')")       # wie in test_seitenlayout_ui: Betrachter bekommen den Standard
        pg.evaluate("document.querySelector('#tl').dataset.alt = '1'; window.__sigw = null")
        pg.evaluate("route()")
        pg.wait_for_selector("#tl:not([data-alt]) #tls-photos", timeout=T)
        pg.wait_for_function("() => { const e = document.querySelector('#pulscard'); return !!e && e.classList.contains('w-halb'); }", timeout=T)
        assert pg.locator("#slopen").count() == 0
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_contrast_of_the_width_switch(pw, app, scheme):
    pg = _tour(pw, app, scheme=scheme)
    try:
        _edit(pg)
        c = pg.evaluate(CONTRAST, ['.slit[data-sl="puls"] .slw:not([aria-pressed="true"])', '.slit[data-sl="puls"] .slw[aria-pressed="true"]', ".slit .slnm", ".slit .slb"])
        low = {k: round(v, 2) for k, v in c.items() if v < 4.5}
        assert len(c) >= 4 and not low, (scheme, c)
        icon = pg.evaluate("() => { const r = document.querySelector('.slit[data-sl=\"puls\"] .slw[aria-pressed=\"true\"] .wf'); return getComputedStyle(r).fill + '|' + getComputedStyle(r.closest('.slw')).backgroundColor; }")
        f, b = icon.split("|")
        assert f != b                                                                                      # Füllung hebt sich vom Grund ab
    finally:
        pg.browser_.close()
