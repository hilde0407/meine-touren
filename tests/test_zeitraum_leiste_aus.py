"""3.37.2 – Leiste „Zeitraum der Seite“ standardmäßig ausgeblendet (Server: Feld zrbar; Oberfläche: Chromium, Desktop und 390 px).
Standard unsichtbar und ohne Wirkung; Schalter „Zeitraum der Seite anzeigen“ (Seite anpassen) bleibt nach Neuladen und in der Ansicht; ?z=… blendet ein; ein gespeicherter Zeitraum erzwingt die Leiste;
Rückgängig/Wiederholen; Erklärung („Was ist das?“, „Hilfe“) mit aria-expanded; Hilfstext „Gerade gilt: …“ in den Baustein-Einstellungen.
Wettlauf-Regel: auf den Zustand warten (wait_for_function mit Pfeilfunktionen, expect mit 15 s), nie nur schlafen. Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import datetime
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
expect = pytest.importorskip("playwright.sync_api").expect

from tests.test_core import fresh  # noqa: F401,E402
from tests.test_seitenlayout_ui import T, _api, _browser, _edit, _saved, pw  # noqa: F401,E402
from tests.test_reise_seiten_ui import app, _done, _saved_doc  # noqa: F401,E402
from tests.test_tourseite_ui import _shot  # noqa: E402
from tests.helpers_ui import quiet  # noqa: E402

TL = 30000
CY = datetime.date.today().year
KEYS = ("tour-haupt", "tour-auswertung", "uebersicht", "statistik", "reise", "reisen", "fotos", "karte")


# ------------------------------------------------------------------  Server  ------------------------------------------------------------------

def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _export(layout, page="uebersicht"):
    return {"format": "meine-touren-ansicht", "format_version": 1, "page": page, "name": "Mit Zeitraum", "layouts": {page: layout}}


def test_server_zrbar_validation_and_backward_compatibility():
    with _client() as c:
        old = {"order": ["tag", "jahr"], "hidden": ["zuletzt"]}
        r = c.put("/api/layout/uebersicht", json=old)
        assert r.status_code == 200 and "zrbar" not in r.json()["layout"]                      # alte Layouts ohne Feld bleiben gültig
        r = c.put("/api/layout/uebersicht", json=dict(old, zrbar=True))
        assert r.status_code == 200 and r.json()["layout"]["zrbar"] is True
        assert c.get("/api/layout/uebersicht").json()["layout"]["zrbar"] is True
        r = c.put("/api/layout/uebersicht", json=dict(old, zrbar=False))                        # nur die Abweichung vom Standard (aus) wird gespeichert
        assert r.status_code == 200 and "zrbar" not in r.json()["layout"]
        for bad in ("ja", 1, 0, None, [], {}, "true"):
            assert c.put("/api/layout/uebersicht", json={"zrbar": bad}).status_code in (400, 422), bad
        assert c.put("/api/layout/statistik", json={"zrbar": True}).status_code == 400          # die Leiste gibt es nur auf der Übersicht
        assert c.put("/api/layout/tour-haupt", json={"zrbar": True}).status_code == 400


def test_server_zrbar_in_views_export_and_code():
    import base64
    import json
    with _client() as c:
        box = {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1}}, {"id": "v1", "name": "Mit Zeitraum", "layout": {"zrbar": True}}], "active": "v1"}
        r = c.put("/api/layout/uebersicht", json=box)
        assert r.status_code == 200, r.text
        got = c.get("/api/layout/uebersicht").json()["container"]
        assert [v["layout"].get("zrbar") for v in got["views"]] == [None, True]
        doc = _export({"zrbar": True, "order": ["tag"]})
        r = c.post("/api/layout/check", json=doc).json()
        assert r["ok"] and r["layouts"]["uebersicht"]["zrbar"] is True and r["stats"]["uebersicht"]["zrbar"] is True, r
        code = "MTA1." + base64.urlsafe_b64encode(json.dumps(doc).encode()).decode().rstrip("=")
        r = c.post("/api/layout/code", json={"code": code}).json()
        assert r["ok"] and r["layouts"]["uebersicht"]["zrbar"] is True, r
        bad = c.post("/api/layout/check", json=_export({"zrbar": "ja"})).json()
        assert not bad["ok"] and bad["errors"]
        bad = c.post("/api/layout/check", json=_export({"zrbar": True}, page="statistik")).json()
        assert not bad["ok"]


# ------------------------------------------------------------------  Oberfläche  ------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_ui(request):
    if "app" in request.fixturenames:
        url = request.getfixturevalue("app")
        for k in KEYS:
            _api(url, k, "DELETE")
    yield


def _dash(pw, url, hash_="#/dash", width=1280, height=1000, scheme="light", dpr=1, mobile=False):
    pg = _browser(pw, url, devs=None, width=width, height=height, scheme=scheme, dpr=dpr)
    if mobile:                                                                                         # Handy: Klasse html.mob (Breite bis 760 px)
        pg.set_viewport_size({"width": width, "height": height})
    pg.goto(f"{url}/{hash_}", timeout=TL)
    pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen') && !!document.querySelector('#hlast') && !!window.ZR_READY", timeout=TL)
    try:
        quiet(pg, 5000)
    except Exception:
        pass
    return pg


def _put(url, **lay):
    _api(url, "uebersicht", "PUT", lay)


def test_default_hidden_and_blocks_not_filtered(pw, app):
    pg = _dash(pw, app)
    try:
        assert pg.locator("#zrbar").count() == 0 and pg.locator("#zrchip").count() == 0
        assert pg.evaluate("() => ZR.F.uebersicht") is None and pg.evaluate("() => zrOn('uebersicht')") is False
        assert pg.locator("#zrbar, .zrbar").count() == 0
        assert pg.evaluate("() => document.querySelectorAll('[data-pageperiod], .zrpage').length") == 0      # kein Baustein trägt einen Seitenzeitraum
        assert not pg.errors, pg.errors
        # Bearbeitungsmodus: Schalter vorhanden, aus, 44 px hoch
        _edit(pg)
        sw = pg.locator("#slzrin")
        expect(sw).to_be_visible(timeout=T)
        assert not sw.is_checked() and not sw.is_disabled()
        assert pg.locator("#slzr").bounding_box()["height"] >= 44 and pg.locator("#slzrhb").bounding_box()["height"] >= 44
        assert "Zeitraum der Seite anzeigen" in pg.locator("#slzr").inner_text()
        assert pg.locator("#zrbar").count() == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_switch_shows_bar_persists_and_belongs_to_the_view(pw, app):
    pg = _dash(pw, app)
    try:
        _edit(pg)
        pg.locator("#slzrin").check()
        expect(pg.locator("#zrbar")).to_be_visible(timeout=T)
        _saved(pg)
        doc = _saved_doc(pg, "uebersicht", want=lambda d: d and d.get("zrbar") is True)
        assert doc["zrbar"] is True
        _done(pg)
        pg.reload()
        pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#hlast')", timeout=TL)
        expect(pg.locator("#zrbar")).to_be_visible(timeout=T)
        assert pg.evaluate("() => ZR.F.uebersicht") is None                                               # sichtbar, aber „Je Baustein“ ohne Wirkung
        assert "eigenen Zeitraum" in pg.locator("#zrbar .zrl").inner_text()
        # wieder aus
        _edit(pg)
        pg.locator("#slzrin").uncheck()
        expect(pg.locator("#zrbar")).to_have_count(0, timeout=T)
        _saved(pg)
        doc = _saved_doc(pg, "uebersicht", want=lambda d: d is None or "zrbar" not in d)
        assert not doc or "zrbar" not in doc
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    # je Ansicht: Standard ohne Leiste, zweite Ansicht mit Leiste
    box = {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1}}, {"id": "v1", "name": "Mit Zeitraum", "layout": {"v": 1, "zrbar": True}}], "active": "standard"}
    _api(app, "uebersicht", "PUT", box)
    pg = _dash(pw, app)
    try:
        assert pg.locator("#zrbar").count() == 0
        pg.evaluate("() => slSwitch('uebersicht', 'v1')")                                                  # Ansichtswechsel blendet die Leiste ein
        expect(pg.locator("#zrbar")).to_be_visible(timeout=T)
        pg.evaluate("() => slSwitch('uebersicht', 'standard')")
        expect(pg.locator("#zrbar")).to_have_count(0, timeout=T)
    finally:
        pg.browser_.close()
    _api(app, "uebersicht", "PUT", dict(box, active="v1"))
    pg = _dash(pw, app)
    try:
        expect(pg.locator("#zrbar")).to_be_visible(timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_url_parameter_shows_bar_for_the_session(pw, app):
    pg = _dash(pw, app, f"#/dash?z={CY - 1}")
    try:
        expect(pg.locator("#zrbar")).to_be_visible(timeout=T)
        assert pg.evaluate("() => ZR.F.uebersicht.yr") == CY - 1
        assert pg.locator('#zrbar [data-zr="prev"]').get_attribute("aria-pressed") == "true"
        # Zurücksetzen: die Leiste bleibt in dieser Sitzung stehen, nach dem Neuladen ist sie wieder weg
        pg.locator("#zrbar .zrreset").click()
        pg.wait_for_function("() => location.hash === '#/dash' && !ZR.F.uebersicht", timeout=T)
        expect(pg.locator("#zrbar")).to_be_visible(timeout=T)
        pg.reload()
        pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#hlast') && !!window.ZR_READY", timeout=TL)
        expect(pg.locator("#zrbar")).to_have_count(0, timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_stored_period_forces_the_bar(pw, app):
    # zuletzt gewählt (Nutzereinstellung im Browser)
    pg = _dash(pw, app)
    try:
        key = pg.evaluate("() => zrLsKey('uebersicht')")
        pg.evaluate("([k, v]) => localStorage.setItem(k, v)", [key, '{"range":"12m"}'])
        pg.reload()
        pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#hlast') && !!window.ZR_READY", timeout=TL)
        expect(pg.locator("#zrbar")).to_be_visible(timeout=T)
        assert pg.evaluate("() => ZR.F.uebersicht.kind") == "12m"
        # der Schalter steht dann an und ist gesperrt
        _edit(pg)
        sw = pg.locator("#slzrin")
        assert sw.is_checked() and sw.is_disabled()
        expect(pg.locator("#slzrnote")).to_be_visible(timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    # in der Ansicht gespeichert
    _put(app, filter={"range": "y", "yr": CY - 1})
    pg = _dash(pw, app)
    try:
        expect(pg.locator("#zrbar")).to_be_visible(timeout=T)
        assert pg.evaluate("() => ZR.F.uebersicht.yr") == CY - 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_undo_redo_include_the_switch(pw, app):
    pg = _dash(pw, app)
    try:
        _edit(pg)
        pg.locator("#slzrin").check()
        expect(pg.locator("#zrbar")).to_be_visible(timeout=T)
        pg.locator('#slbar [data-a="undo"]').click()
        expect(pg.locator("#zrbar")).to_have_count(0, timeout=T)
        assert not pg.locator("#slzrin").is_checked()
        pg.locator('#slbar [data-a="redo"]').click()
        expect(pg.locator("#zrbar")).to_be_visible(timeout=T)
        assert pg.locator("#slzrin").is_checked()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_help_in_edit_mode_and_in_the_bar(pw, app):
    _put(app, zrbar=True)
    pg = _dash(pw, app)
    try:
        # Bearbeitungsmodus: „Was ist das?“ klappt auf und zu, open-Zustand explizit gesetzt
        _edit(pg)
        hb, hp = pg.locator("#slzrhb"), pg.locator("#slzrhelp")
        if hb.get_attribute("aria-expanded") == "true":
            hb.click()
        expect(hb).to_have_attribute("aria-expanded", "false", timeout=T)
        expect(hp).to_be_hidden(timeout=T)
        hb.click()
        expect(hb).to_have_attribute("aria-expanded", "true", timeout=T)
        expect(hp).to_be_visible(timeout=T)
        t = hp.inner_text()
        for w in ("für alle Bausteine", "Zeitraum der Seite verwenden", "Heute vor X Jahren", "?z="):
            assert w in t, t
        assert hp.locator("li").count() == 4
        hb.click()
        expect(hp).to_be_hidden(timeout=T)
        _done(pg)
        # Leiste: Knopf „Hilfe“
        info = pg.locator("#zrbar .zrinfo")
        expect(info).to_be_visible(timeout=T)
        assert info.get_attribute("aria-controls") == "zrhelp" and info.bounding_box()["height"] >= 44
        if info.get_attribute("aria-expanded") == "true":
            info.click()
        expect(pg.locator('#zrbar [data-zr="help"]')).to_have_attribute("aria-expanded", "false", timeout=T)
        expect(pg.locator("#zrhelp")).to_be_hidden(timeout=T)
        pg.locator('#zrbar [data-zr="help"]').click()
        expect(pg.locator('#zrbar [data-zr="help"]')).to_have_attribute("aria-expanded", "true", timeout=T)
        expect(pg.locator("#zrhelp")).to_be_visible(timeout=T)
        assert "für alle Bausteine" in pg.locator("#zrhelp").inner_text() and pg.locator("#zrhelp li").count() == 4
        assert pg.evaluate("() => document.activeElement.dataset.zr") == "help"
        pg.locator('#zrbar [data-zr="help"]').click()
        expect(pg.locator("#zrhelp")).to_be_hidden(timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_block_settings_say_which_period_applies(pw, app):
    _put(app, zrbar=True)
    pg = _dash(pw, app, f"#/dash?z={CY - 1}")
    try:
        _edit(pg)
        pg.locator('.slit[data-sl="jahr"] [data-a="cfg"]').click()
        now = pg.locator("[data-zrnow]")
        expect(now).to_be_visible(timeout=T)
        expect(now).to_contain_text(f"Gerade gilt: {CY - 1} von der Seite", timeout=T)
        pg.locator("input[data-zr][data-global]").uncheck()
        expect(now).to_have_text("Dieser Baustein nutzt seinen eigenen Zeitraum", timeout=T)
        pg.locator("input[data-zr][data-global]").check()
        expect(now).to_contain_text("Gerade gilt:", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_mobile_390_default_switch_and_chip(pw, app, scheme):
    pg = _dash(pw, app, width=390, height=844, scheme=scheme, dpr=2, mobile=True)
    try:
        assert pg.evaluate("() => document.documentElement.classList.contains('mob')")
        assert pg.locator("#zrbar").count() == 0 and pg.locator("#zrchip").count() == 0
        assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth")
        _shot(pg, f"zr-390-standard-{scheme}.png")
        _edit(pg)
        sw = pg.locator("#slzrin")
        expect(sw).to_be_visible(timeout=T)
        box = pg.locator("#slzr").bounding_box()
        assert box["height"] >= 44 and box["x"] >= 0 and box["x"] + box["width"] <= 390 + 1, box
        assert sw.bounding_box()["width"] >= 24 and pg.locator("#slzrhb").bounding_box()["height"] >= 44
        assert pg.evaluate("() => document.getElementById('slzrin').getBoundingClientRect().top < innerHeight")
        _shot(pg, f"zr-390-schalter-{scheme}.png")
        pg.locator("#slzrhb").click()
        expect(pg.locator("#slzrhelp")).to_be_visible(timeout=T)
        assert pg.locator("#slzr").bounding_box()["x"] + pg.locator("#slzr").bounding_box()["width"] <= 391
        _shot(pg, f"zr-390-hilfe-{scheme}.png")
        pg.locator("#slzrhb").click()
        sw.check()
        _saved(pg)
        _done(pg)
        expect(pg.locator("#zrchip")).to_be_visible(timeout=T)                                           # Handy: Chip in der Werkzeugzeile
        assert pg.locator("#zrchip").bounding_box()["height"] >= 40
        pg.locator("#zrchip").click()
        expect(pg.locator("#zrchip")).to_have_attribute("aria-expanded", "true", timeout=T)
        info = pg.locator('#zrbody [data-zr="help"]')
        expect(info).to_be_visible(timeout=T)
        assert info.bounding_box()["height"] >= 44
        info.click()
        expect(info).to_have_attribute("aria-expanded", "true", timeout=T)
        expect(pg.locator("#zrhelp")).to_be_visible(timeout=T)
        _shot(pg, f"zr-390-mit-leiste-{scheme}.png")
        assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
