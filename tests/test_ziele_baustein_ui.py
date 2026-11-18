"""3.29.0 – Baustein „Ziele“ in der Übersicht (Browser, Chromium): gleiche Daten wie „Ziele“ der Statistik (GET /api/goals), Fortschrittsbalken je Ziel, einklappbar, Leerzustand mit Link,
Jahr wählbar, 390 px ohne Überlauf, Kontrast hell und dunkel. Wettlauf-Regel: auf den Zustand warten, nie nur schlafen. Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import json
import urllib.request
from datetime import date

import pytest

from tests.test_statistik_ui import _api, _browser, _shot, app, clean, pw, T  # noqa: F401
from tests.helpers_ui import toggle_details
from tests.test_tourseite_ui import CONTRAST, _settled

expect = pytest.importorskip("playwright.sync_api").expect
YEAR = date.today().year


def _goal(url, **g):
    req = urllib.request.Request(f"{url}/api/goals", method="POST", data=json.dumps(g).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read() or b"{}")


@pytest.fixture
def goals(app):
    for g in json.loads(urllib.request.urlopen(f"{app}/api/goals", timeout=10).read()):
        urllib.request.urlopen(urllib.request.Request(f"{app}/api/goals/{g['id']}", method="DELETE"), timeout=10)
    yield app
    for g in json.loads(urllib.request.urlopen(f"{app}/api/goals", timeout=10).read()):
        urllib.request.urlopen(urllib.request.Request(f"{app}/api/goals/{g['id']}", method="DELETE"), timeout=10)


def _dash_page(pw, url, width=1280, scheme="light", dpr=1):
    _api(url, "uebersicht", "PUT", {"v": 1, "widgets": [{"id": "wz", "type": "jahresziele", "cfg": {}}]})
    pg = _browser(pw, url, width=width, height=900, scheme=scheme, dpr=dpr, devs=None)
    pg.goto(f"{url}/#/dash")
    pg.wait_for_selector("#tlw-wz", state="attached", timeout=30000)
    return pg


def test_zeigt_die_ziele_des_jahres_mit_balken_und_klappt_ein(pw, goals):
    _goal(goals, year=YEAR, metric="count", sport="", target=10)
    _goal(goals, year=YEAR, metric="km", sport="hike", target=100)
    _goal(goals, year=YEAR - 1, metric="km", sport="", target=500)
    pg = _dash_page(pw, goals)
    try:
        expect(pg.locator("#tlw-wz .goal")).to_have_count(2, timeout=T)
        assert pg.locator("#tlw-wz summary").inner_text().startswith(f"Ziele {YEAR}")
        assert pg.locator("#tlw-wz .goal svg.slbr").count() == 2
        vals = pg.evaluate("async () => (await api('/api/goals')).filter(g => g.year === new Date().getFullYear()).map(g => Math.round(Math.min(100, goalVal(g, TOURS) / g.target * 100)) + ' %')")
        for i, v in enumerate(vals):
            expect(pg.locator("#tlw-wz .goal .gs").nth(i)).to_contain_text(v, timeout=T)
        assert pg.locator("#tlw-wz a[href='#/stats']").count() >= 1
        # einklappbar
        assert pg.locator("#tlw-wz details").first.evaluate("e => e.open")
        toggle_details(pg, "#tlw-wz details", False)
        toggle_details(pg, "#tlw-wz details", True)
        # Jahr „letztes Jahr“ über die Einstellung
        _api(goals, "uebersicht", "PUT", {"v": 1, "widgets": [{"id": "wz", "type": "jahresziele", "cfg": {"year": "last"}}]})
        pg.reload()
        pg.wait_for_selector("#tlw-wz details", state="attached", timeout=T)
        pg.evaluate("() => { const d = document.querySelector('#tlw-wz details'); if (d) d.open = true; }")
        pg.wait_for_selector("#tlw-wz .goal", timeout=T)
        assert pg.locator("#tlw-wz summary").inner_text().startswith(f"Ziele {YEAR - 1}") and pg.locator("#tlw-wz .goal").count() == 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_leer_zustand(pw, goals):
    pg = _dash_page(pw, goals)
    try:
        expect(pg.locator("#tlw-wz .slnone")).to_contain_text(f"Noch kein Ziel für {YEAR}", timeout=T)
        assert pg.locator("#tlw-wz a[href='#/stats']").count() == 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("width,scheme", [(1280, "light"), (390, "light"), (390, "dark")])
def test_390_ohne_ueberlauf_und_kontrast(pw, goals, width, scheme):
    _goal(goals, year=YEAR, metric="count", sport="", target=3)               # übertroffen: „Ziel erreicht“
    _goal(goals, year=YEAR, metric="km", sport="hike", target=1000)
    pg = _dash_page(pw, goals, width=width, scheme=scheme, dpr=2 if width == 390 else 1)
    try:
        expect(pg.locator("#tlw-wz .goal")).to_have_count(2, timeout=T)
        _settled(pg)
        assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
        assert pg.evaluate("() => { const w = document.getElementById('tlw-wz'); return w.scrollWidth <= w.clientWidth + 1; }")
        c = pg.evaluate(CONTRAST, ["#tlw-wz .goal .gh b", "#tlw-wz .goal .gh span", "#tlw-wz .goal .gs", "#tlw-wz .tlk"])
        low = {k: round(v, 2) for k, v in c.items() if v < 4.5}
        assert len(c) >= 3 and not low, f"{scheme}: Kontrast unter 4,5:1: {low}"
        _shot(pg, f"ziele-baustein-{width}-{scheme}.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
