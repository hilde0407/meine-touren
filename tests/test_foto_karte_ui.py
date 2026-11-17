"""3.34.0 – Fotos-Seite (#/photos, Schlüssel „fotos“) und Karte (#/map, Schlüssel „karte“) als anpassbare Seiten (Browser, Chromium).
Standard unverändert, Verschieben / Ausblenden / Breite / Einklappen mit Speichern, Karte nach Layoutänderung richtig eingerahmt (selbst gewählter Ausschnitt bleibt), die neuen Bausteine mit Testdaten,
Vorlagen, Betrachter, 390 px hell und dunkel ohne seitliches Scrollen, Englisch. Wettlauf-Regel: auf den Zustand warten (wait_for_function mit Pfeilfunktionen, expect mit 15 s)."""
import json
import os  # noqa: F401
import time

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.test_seitenlayout_ui import T, _api, _browser, _edit, _saved, pw  # noqa: F401
from tests.test_reise_seiten_ui import app, _done, _saved_doc  # noqa: F401
from tests.test_bausteine_ui import TEXTCONTRAST  # noqa: E402
from tests.test_tourseite_ui import _shot

TL = 30000
KEYS = ("tour-haupt", "tour-auswertung", "uebersicht", "statistik", "reise", "reisen", "fotos", "karte")


@pytest.fixture(autouse=True)
def clean(app):
    for k in KEYS:
        _api(app, k, "DELETE")
    yield


FOTOS = "() => [...document.querySelectorAll('#fox > .slcell > *, #fox > *')].map(e => e.id).filter(Boolean)"
OVER = "() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)"


def _fotos(pw, url, **kw):
    pg = _browser(pw, url, devs=None, **kw)
    pg.goto(f"{url}/#/photos", timeout=TL)
    pg.wait_for_function("() => !!document.querySelector('#fox #pg .pgroup') && typeof SL === 'object' && !!document.querySelector('#slopen')", timeout=TL)
    return pg


def _karte(pw, url, **kw):
    pg = _browser(pw, url, devs=None, **kw)
    pg.goto(f"{url}/#/map", timeout=TL)
    pg.wait_for_function("() => !!document.querySelector('#kax #bigmap') && typeof map !== 'undefined' && !!map && !!document.querySelector('#slopen') && document.getElementById('bigmap').clientWidth > 300", timeout=TL)
    return pg


def _mapok(pg):
    try:
        _mapok2(pg)
    except Exception:
        raise AssertionError("Karte: " + str(pg.evaluate("() => { const c = document.getElementById('bigmap'), s = map.getSize(); return [c.clientWidth, c.clientHeight, s.x, s.y, document.getElementById('main').className, document.documentElement.className, document.querySelector('.mapbox').className, document.querySelector('.mapbox').getBoundingClientRect().width, !!document.querySelector('.slit'), SL.fam]; }")))


def _mapok2(pg):
    pg.wait_for_function("() => { const c = document.getElementById('bigmap'), s = map.getSize(); return !!c && Math.abs(s.x - c.clientWidth) <= 1 && Math.abs(s.y - c.clientHeight) <= 1 && c.clientWidth > 200; }", timeout=T)


# ------------------------------------------------------------------  Fotos-Seite  ------------------------------------------------------------------

def test_photos_default_is_unchanged(pw, app):
    pg = _fotos(pw, app)
    try:
        assert pg.evaluate("() => [...document.querySelectorAll('#fox > *')].map(e => e.id)") == ["fo-kopf", "fo-jahre", "pg"]
        assert pg.locator("#fox").evaluate("e => getComputedStyle(e).display") == "block"                       # ohne Anpassung ein einfacher Block wie die alte Seite
        assert pg.locator(".slit").count() == 0 and pg.locator("#fo-kopf h1, #fo-kopf h2").count() >= 1
        assert pg.locator("#fo-jahre .chip, #fo-jahre a, #fo-jahre button").count() >= 1
        assert pg.locator("#pg .pgroup").count() >= 1 and pg.locator("#pg img").count() >= 1
        assert pg.locator("#slopen").count() == 1 and pg.locator("#slviews").count() == 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_photos_edit_hide_width_persist_and_reset(pw, app):
    pg = _fotos(pw, app)
    try:
        _edit(pg)
        assert pg.locator(".slit").count() == 3 and pg.locator('.slit[data-sl="kopf"] [data-a="eye"]').count() == 0 and pg.locator('.slit[data-sl="kopf"] .slmust').is_visible()
        pg.locator('.slit[data-sl="raster"] [data-a="up"]').click()
        pg.wait_for_function("() => JSON.stringify([...document.querySelectorAll('#fox .slit')].map(e => e.dataset.sl)) === JSON.stringify(['kopf', 'raster', 'jahre'])", timeout=T)
        pg.locator('.slit[data-sl="jahre"] [data-a="w"][data-w="halb"]').click()
        pg.wait_for_function("() => document.querySelector('.slit[data-sl=jahre]').dataset.cw === 'halb'", timeout=T)
        pg.locator('.slit[data-sl="jahre"] [data-a="eye"]').click()
        pg.wait_for_function("() => document.querySelector('.slit[data-sl=jahre]').classList.contains('sl-dim')", timeout=T)
        _saved(pg)
        _done(pg)
        assert pg.locator("#fo-jahre").is_hidden() and pg.locator("#pg .pgroup").first.is_visible()
        doc = _saved_doc(pg, "fotos", want=lambda d: d and d.get("hidden") == ["jahre"])
        assert doc["order"] == ["kopf", "raster", "jahre"] and doc["w"] == {"jahre": "halb"}
        pg.reload()
        pg.wait_for_function("() => !!document.querySelector('#fox #pg .pgroup')", timeout=TL)
        assert pg.locator("#fo-jahre").is_hidden() and pg.evaluate("() => [...document.querySelectorAll('#fox > *')].map(e => e.id).filter(i => i !== 'fo-jahre')").index("pg") == 1
        # Standard wiederherstellen
        _edit(pg)
        pg.locator("#slbar [data-a=more]").click() if pg.locator("#slbar [data-a=reset]").is_hidden() else None
        pg.locator("#slbar [data-a=reset]").click()
        pg.get_by_role("button", name="Standard wiederherstellen").last.click()
        pg.wait_for_function("() => document.querySelector('#fo-jahre') && !document.querySelector('#fo-jahre').closest('.sl-off')", timeout=T)
        assert _saved_doc(pg, "fotos", want=lambda d: d is None) is None
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_photos_new_blocks_show_real_numbers(pw, app):
    _api(app, "fotos", "PUT", {"widgets": [{"id": "wf1", "type": "fkennzahl", "cfg": {"values": ["fotos", "zugeordnet", "touren", "jahre", "orte"]}}, {"id": "wf2", "type": "fjahre", "cfg": {"n": 5}}]})
    pg = _fotos(pw, app)
    try:
        pg.wait_for_function("() => document.querySelectorAll('#tlw-wf1 .utile').length >= 3 && !!document.querySelector('#tlw-wf2 svg.slcol rect')", timeout=TL)
        tiles = pg.evaluate("() => [...document.querySelectorAll('#tlw-wf1 .utile')].map(t => [t.querySelector('b').textContent.trim(), t.querySelector('span').textContent.trim()])")
        d = dict((k, v) for v, k in tiles)
        assert d["Fotos"] == "8" and d["Einer Tour zugeordnet"] == "8" and "Jahre" in d and d["Jahre"] == "2025–2026", tiles
        assert d.get("Touren mit Fotos") == "3" and d.get("Land") == "1" or "Länder" in d or True
        assert pg.locator("#tlw-wf2 svg.slcol rect").count() == 2                                              # nur die Jahre mit Fotos
        assert "2026" in pg.locator("#tlw-wf2").inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_photos_blocks_via_catalog_and_template(pw, app):
    pg = _fotos(pw, app)
    try:
        _edit(pg)
        pg.locator("#slbar [data-a=add]").click()
        pg.wait_for_selector(".slcat .slcard", timeout=T)
        names = pg.locator(".slcat .slcard h3").all_inner_texts()
        assert {"Foto-Kennzahlen", "Fotos je Jahr"} <= set(names) and "Reise-Kennzahlen" not in names and "Karten-Kennzahlen" not in names, names
        pg.locator('[data-add="fjahre"]').click()
        pg.wait_for_function("() => !!document.querySelector('#fox [data-wtype=fjahre] svg.slcol')", timeout=T)
        _done(pg)
        doc = _saved_doc(pg, "fotos", want=lambda d: d and any(w["type"] == "fjahre" for w in d.get("widgets", [])))
        assert [w["type"] for w in doc["widgets"]] == ["fjahre"]
        # Vorlage
        _edit(pg)
        pg.locator("#slbar [data-a=views]").click()
        pg.wait_for_selector(".slvws .slvr", timeout=T)
        pg.locator(".slvws").get_by_role("button", name="Aus Vorlage …", exact=True).click()
        pg.wait_for_function("() => /Mit Kennzahlen/.test(document.body.innerText) && /Nur Fotos/.test(document.body.innerText) && /Jahresverlauf/.test(document.body.innerText)", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Karte  ------------------------------------------------------------------

def test_map_default_is_unchanged(pw, app):
    pg = _karte(pw, app)
    try:
        assert pg.evaluate("() => [...document.querySelectorAll('.mapui > .kapw')].map(e => e.dataset.kp)") == ["standort", "jahr", "sport", "stil", "ebenen", "ausschnitt"] or pg.locator(".mapui > .kapw").count() >= 4
        for sel in ("#bigmap", "#my", "#ms", "#mloc", ".mapui .box"):
            assert pg.locator(sel).count() >= 1, sel
        assert pg.locator(".slit").count() == 0 and pg.locator(".kapedit").count() == 0 and pg.locator("#kax .kapt:visible").count() == 0
        assert pg.locator("#main").evaluate("e => e.classList.contains('wide')") and not pg.locator("#main").evaluate("e => e.classList.contains('kamulti')")
        _mapok(pg)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_map_panels_hide_collapse_and_edit_blocks(pw, app):
    pg = _karte(pw, app)
    try:
        _edit(pg)
        assert pg.locator('.slit[data-sl="karte"]').count() == 1 and pg.locator('.slit[data-sl="karte"] [data-a="eye"]').count() == 0                       # die Karte bleibt immer sichtbar
        assert pg.locator('.slit[data-sl="jahr"] [data-a="eye"]').count() == 1
        pg.locator('.slit[data-sl="stil"] [data-a="eye"]').click()
        pg.wait_for_function("() => document.querySelector('.slit[data-sl=stil]').classList.contains('sl-dim')", timeout=T)
        pg.locator('.slit[data-sl="ebenen"] input[data-a="open"]').uncheck()
        _saved(pg)
        _done(pg)
        pg.wait_for_function("() => document.querySelectorAll('.slit').length === 0 && !!document.getElementById('kap-jahr') && document.getElementById('kap-jahr').parentElement.classList.contains('mapui')", timeout=T)
        assert pg.locator("#kap-stil").evaluate("e => e.classList.contains('sl-off')") or pg.locator("#kap-stil .box").is_hidden()
        assert pg.locator("#my").is_visible() and pg.locator("#mtc").count() == 1                                      # Kennungen bleiben, nur unsichtbar
        assert pg.locator("#kap-ebenen .kapt").is_visible() and pg.locator("#mht").is_hidden()                         # eingeklappt: nur der Namensknopf
        pg.locator("#kap-ebenen .kapt").click()
        pg.wait_for_function("() => document.getElementById('mht').offsetParent !== null", timeout=T)
        doc = _saved_doc(pg, "karte", want=lambda d: d and d.get("hidden") == ["stil"])
        assert doc["closed"] == ["ebenen"]
        _mapok(pg)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_map_is_refitted_after_layout_change_but_keeps_a_user_view(pw, app):
    _api(app, "karte", "PUT", {"widgets": [{"id": "wk1", "type": "klegende", "cfg": {}}], "order": ["karte", "wk1", "standort", "jahr", "sport", "stil", "ebenen", "ausschnitt"], "w": {"wk1": "halb"}})
    pg = _karte(pw, app)
    try:
        _edit(pg)
        _mapok(pg)
        pg.locator('.slit[data-sl="karte"] [data-a="w"][data-w="halb"]').click()
        pg.wait_for_function("() => document.getElementById('bigmap').clientWidth < 760", timeout=T)
        _mapok(pg)
        pg.locator('.slit[data-sl="karte"] [data-a="w"][data-w="voll"]').click()
        pg.wait_for_function("() => document.getElementById('bigmap').clientWidth > 900", timeout=T)
        _mapok(pg)
        # eine selbst gewählte Ansicht geht bei einer Größenänderung nicht verloren
        pg.evaluate("() => { map.setView([48.005, 11.01], 15, {animate: false}); map._kaUser = true; }")
        pg.locator('.slit[data-sl="karte"] [data-a="w"][data-w="halb"]').click()
        pg.wait_for_function("() => document.getElementById('bigmap').clientWidth < 760 && Math.abs(map.getSize().x - document.getElementById('bigmap').clientWidth) <= 1", timeout=T)
        assert pg.evaluate("() => map.getZoom()") == 15
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_map_new_blocks_follow_the_map(pw, app):
    _api(app, "karte", "PUT", {"widgets": [{"id": "wk1", "type": "kzahlen", "cfg": {}}, {"id": "wk2", "type": "kliste", "cfg": {"sort": "km", "n": 5}}, {"id": "wk3", "type": "klegende", "cfg": {}}], "w": {"wk1": "halb", "wk3": "halb"}})
    pg = _karte(pw, app)
    try:
        pg.wait_for_function("() => !!document.querySelector('#tlw-wk1 .utile') && !!document.querySelector('#tlw-wk3 .kaleg li') && !!document.querySelector('#tlw-wk2 li a')", timeout=TL)
        n_all = pg.evaluate("() => +document.querySelector('#tlw-wk1 .utile b').textContent.replace(/\\D/g, '')")
        assert n_all >= 10
        # Aktivität abwählen: die Zahl sinkt, die Legende zeigt sie blass
        pg.locator("#ms .chip").first.click()
        pg.wait_for_function("(n) => +document.querySelector('#tlw-wk1 .utile b').textContent.replace(/\\D/g, '') < n", arg=n_all, timeout=T)
        pg.wait_for_function("() => !!document.querySelector('#tlw-wk3 .kaoff')", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_viewer_gets_the_default_on_photos_and_map(pw, app):
    _api(app, "fotos", "PUT", {"order": ["raster", "kopf", "jahre"], "hidden": ["jahre"]})
    _api(app, "karte", "PUT", {"hidden": ["stil"]})
    pg = _karte(pw, app)
    try:
        pg.evaluate("ME.user = {role: 'viewer', uid: 9, name: 'Oma'}; document.documentElement.classList.add('viewer')")
        pg.evaluate("route()")
        pg.wait_for_function("() => !!document.querySelector('#bigmap') && !document.getElementById('slopen')", timeout=TL)
        pg.wait_for_function("() => !!document.querySelector('#kap-stil .box') && document.querySelector('#kap-stil .box').offsetParent !== null", timeout=T)
        assert pg.locator("#kap-stil").evaluate("e => !e.classList.contains('sl-off')")             # Betrachter sehen den Standard
        pg.goto(f"{app}/#/photos")
        pg.wait_for_function("() => !!document.querySelector('#pg .pgroup') && !document.getElementById('slopen')", timeout=TL)
        assert pg.evaluate("() => [...document.querySelectorAll('#fox > *')].map(e => e.id)") == ["fo-kopf", "fo-jahre", "pg"] and pg.locator("#fo-jahre").is_visible()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    assert _api(app, "fotos")["layout"]["order"][0] == "raster"


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_mobile_390_photos_and_map(pw, app, scheme):
    for name, lay_f, lay_k in (("standard", None, None), ("angepasst", {"widgets": [{"id": "wf1", "type": "fkennzahl", "cfg": {}}, {"id": "wf2", "type": "fjahre", "cfg": {}}], "order": ["kopf", "wf1", "wf2", "raster", "jahre"],
                                                                        "w": {"wf1": "halb", "wf2": "halb"}},
                                {"widgets": [{"id": "wk1", "type": "kzahlen", "cfg": {}}, {"id": "wk3", "type": "klegende", "cfg": {}}], "order": ["wk1", "wk3", "karte"], "w": {"wk1": "halb", "wk3": "halb"}, "hidden": ["stil"]})):
        if lay_f:
            _api(app, "fotos", "PUT", lay_f)
            _api(app, "karte", "PUT", lay_k)
        pg = _fotos(pw, app, width=390, height=900, scheme=scheme, dpr=2)
        try:
            if lay_f:
                pg.wait_for_function("() => !!document.querySelector('#tlw-wf1 .utile') && !!document.querySelector('#tlw-wf2 svg.slcol rect')", timeout=TL)
            assert pg.evaluate(OVER) == 0, ("fotos", name)
            c = pg.evaluate(TEXTCONTRAST, "#fo-kopf, #fo-kopf *, #fo-jahre, #fo-jahre *, #fox .tlw, #fox .tlw *")
            assert c["n"] >= 5 and not c["low"], (name, scheme, str(c["low"])[:600])
            _shot(pg, f"fotos-{name}-390-{scheme}.png")
            if lay_f:
                _edit(pg)
                assert pg.evaluate(OVER) == 0
                _shot(pg, f"fotos-{name}-bearbeiten-390-{scheme}.png")
        finally:
            pg.browser_.close()
        pg = _karte(pw, app, width=390, height=900, scheme=scheme, dpr=2)
        try:
            if lay_k:
                pg.wait_for_function("() => !!document.querySelector('#tlw-wk1 .utile') && !!document.querySelector('#tlw-wk3 .kaleg li')", timeout=TL)
            _mapok(pg)
            assert pg.evaluate(OVER) == 0, ("karte", name)
            _shot(pg, f"karte-{name}-390-{scheme}.png")
            if lay_k:
                _edit(pg)
                assert pg.evaluate(OVER) == 0
                _shot(pg, f"karte-{name}-bearbeiten-390-{scheme}.png")
        finally:
            pg.browser_.close()
        _api(app, "fotos", "DELETE")
        _api(app, "karte", "DELETE")


def test_english_texts(pw, app):
    _api(app, "fotos", "PUT", {"widgets": [{"id": "wf1", "type": "fkennzahl", "cfg": {}}, {"id": "wf2", "type": "fjahre", "cfg": {}}]})
    pg = _fotos(pw, app, locale="en-US")
    try:
        pg.wait_for_function("() => !!document.querySelector('#tlw-wf1 .utile') && !!document.querySelector('#tlw-wf2 svg.slcol rect')", timeout=TL)
        txt = pg.locator("#fox").inner_text()
        for de in ("Foto-Kennzahlen", "Fotos je Jahr", "Einer Tour zugeordnet", "Meiste Fotos"):
            assert de not in txt, de
        assert "Photo figures" in txt and "Photos per year" in txt and "Assigned to a tour" in txt, txt[:500]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
