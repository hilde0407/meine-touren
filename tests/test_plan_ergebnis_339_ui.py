"""3.39.0 Tourseite: Karte „Plan und Ergebnis“ (Soll/Ist) – nur mit verknüpftem Plan; Kennzahlen mit Pfeil + Wort, gestrichelte Plan-Linie über der durchgezogenen gelaufenen, Link zum Plan, Verknüpfung lösen,
Katalog, Englisch, 390 px hell/dunkel. Wettlauf-Regel: auf Zustände warten (expect/wait_for_function mit 15 s). Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import json
import math
import urllib.request

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.helpers_ui import T, quiet, settled, toggle_details  # noqa: E402
from tests.test_seitenlayout_ui import _api, _browser, pw  # noqa: E402,F401
from tests.test_reise_seiten_ui import app  # noqa: E402,F401
from tests.test_tourseite_ui import _shot  # noqa: E402

CARD = "#tlw-planist"
KEYS = ("tour-haupt", "tour-auswertung")


def _req(url, path, method="GET", body=None):
    r = urllib.request.Request(url + path, method=method, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=10) as x:
        return json.loads(x.read() or b"{}")


def _loop(lat0, lng0, r=0.01, n=60, k=1.0):
    return [[lat0 + k * r * math.sin(2 * math.pi * i / (n - 1)), lng0 + r * (1 - math.cos(2 * math.pi * i / (n - 1)))] for i in range(n)]


@pytest.fixture(autouse=True)
def clean(app):
    for k in KEYS:
        _api(app, k, "DELETE")
    for p in _req(app, "/api/plans"):
        _req(app, f"/api/plans/{p['id']}", "DELETE")
    yield


def _plan(app, tour, km=8.0, up=150, est_h=2.0, name="Rund um den See"):
    pid = _req(app, "/api/plans", "POST", {"name": name, "sport": "hike", "pts": _loop(48.0, 11.0, k=0.8), "km": km, "up": up, "down": up, "est_h": est_h})["id"]
    if tour:
        _req(app, f"/api/plans/{pid}/tour", "POST", {"tour_id": tour})
    return pid


def _tour(pw, app, tid="h0", **kw):
    pg = _browser(pw, app, devs=None, **kw)
    pg.goto(f"{app}/#/tour/{tid}")
    pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen') && !!document.querySelector('#tl')", timeout=30000)
    quiet(pg, 3000, 500)
    return pg


def test_ohne_verknuepfung_nichts_zu_sehen(pw, app):
    _plan(app, None)                                            # Plan ohne Tour
    pg = _tour(pw, app)
    try:
        if pg.locator(CARD).count():                                    # 3.48.0: ohne Plan höchstens „Wie ist es gelaufen?“ (genug Vergleichstouren), nie Plan und Ergebnis
            expect(pg.locator(CARD + " summary h3")).to_have_text("Wie ist es gelaufen?", timeout=T)
            assert pg.locator(CARD + " .plname, " + CARD + " [data-a=unlink]").count() == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_karte_mit_verknuepfung_zahlen_symbole_linien_und_link(pw, app):
    pid = _plan(app, "h0", km=8.0, up=150, est_h=3.0)           # Tour: 9,0 km, 150 m, 2:30 Std.
    pg = _tour(pw, app)
    try:
        expect(pg.locator(CARD)).to_be_visible(timeout=T)
        c = pg.locator(CARD)
        expect(c.locator("summary h3")).to_have_text("Plan und Ergebnis", timeout=T)
        # 3.55.0: Geplant / Gelaufen als zwei Spalten, je vier Kennzahlen; die Abweichung steht beim gelaufenen Wert
        expect(c.locator(".pe-ist .pek")).to_have_count(4, timeout=T)
        pl = [r.inner_text() for r in c.locator(".pe-plan .pek").all()]
        txt = [r.inner_text() for r in c.locator(".pe-ist .pek").all()]
        assert "Strecke" in pl[0] and "8,0 km" in pl[0] and "länger" not in pl[0] and "Dauer" in pl[3] and "3:00" in pl[3]
        assert "Strecke" in txt[0] and "9,0 km" in txt[0] and "↑" in txt[0] and "+1,0 km" in txt[0] and "länger als geplant" in txt[0]
        assert "Aufstieg" in txt[1] and "=" in txt[1] and "wie geplant" in txt[1]
        assert "Abstieg" in txt[2] and "wie geplant" in txt[2]
        assert "Dauer" in txt[3] and "2:30" in txt[3] and "↓" in txt[3] and "−30 Min." in txt[3] and "kürzer als geplant" in txt[3]
        # Karte mit beiden Linien: Plan gestrichelt, gelaufen durchgezogen; Beschriftung und Legende
        mp = c.locator(".pemap")
        assert "gestrichelt" in mp.get_attribute("aria-label")
        expect(mp.locator("path.pepl")).to_have_count(1, timeout=T)
        assert mp.locator("path.pepl").get_attribute("stroke-dasharray") not in (None, "", "none")
        assert mp.locator("path.peis").get_attribute("stroke-dasharray") in (None, "", "none")
        assert "Geplant (gestrichelt)" in c.locator(".plleg").inner_text() and "Gelaufen (durchgezogen)" in c.locator(".plleg").inner_text()
        # Link zum Plan
        assert c.locator(".plname a").get_attribute("href") == f"#/plan/{pid}" and c.locator(".plact a").get_attribute("href") == f"#/plan/{pid}"
        # einklappbar
        toggle_details(pg, CARD + " details.tls", False)
        expect(c.locator(".pecols")).to_be_hidden(timeout=T)
        toggle_details(pg, CARD + " details.tls", True)
        expect(c.locator(".pecols")).to_be_visible(timeout=T)
        _shot(pg, "tour-plan-ergebnis-1280-hell.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_verknuepfung_loesen(pw, app):
    pid = _plan(app, "h0")
    pg = _tour(pw, app)
    try:
        expect(pg.locator(CARD)).to_be_visible(timeout=T)
        pg.locator(CARD + ' [data-a="unlink"]').click()
        dlg = pg.locator(".uidlg")
        expect(dlg).to_be_visible(timeout=T)
        dlg.get_by_role("button", name="Verknüpfung lösen").click()
        expect(pg.locator(CARD + ' [data-a="unlink"], ' + CARD + " .plname")).to_have_count(0, timeout=T)      # 3.48.0: danach höchstens „Wie ist es gelaufen?“ (ohne Plan)
        assert _req(app, f"/api/plans/{pid}")["tour_id"] is None
        assert _req(app, "/api/tours/h0/plan") == {"status": "kein_plan"}
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_katalog_zeigt_den_baustein_auch_ohne_verknuepfung(pw, app):
    pg = _tour(pw, app, tid="h1")
    try:
        pg.locator("#slopen").click()
        pg.wait_for_selector("#slbar", timeout=T)
        pg.locator("[data-a='add']").first.click()
        card = pg.locator(".slcard", has_text="Plan und Ergebnis")
        expect(card).to_have_count(1, timeout=T)
        expect(card.locator("[data-add='planergebnis']")).to_be_visible(timeout=T)
        assert "Erscheint nur bei Touren" in card.inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_englisch(pw, app):
    _plan(app, "h0", km=8.0, up=150, est_h=3.0)
    pg = _browser(pw, app, devs=None, locale="en-GB")
    pg.context.add_init_script("try { localStorage.setItem('lang', 'en'); } catch (e) {}")
    pg.goto(f"{app}/#/tour/h0")
    try:
        c = pg.locator(CARD)
        expect(c).to_be_visible(timeout=30000)
        expect(c.locator("summary h3")).to_have_text("Plan and result", timeout=T)
        t = c.inner_text()
        for w in ("Distance", "Ascent", "Descent", "Duration", "longer than planned", "as planned", "shorter than planned", "To the plan", "Remove link", "Planned", "Walked"):
            assert w in t, (w, t)
        assert "Planned (dashed)" in t and "Walked (solid)" in t
        for de in ("länger als geplant", "wie geplant", "Dauer", "Zum Plan", "gestrichelt", "Geplant", "Gelaufen"):
            assert de not in t, de
        assert "dashed" in c.locator(".pemap").get_attribute("aria-label")
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width,height", [(390, 844), (1280, 900)])
def test_responsiv_ohne_ueberlauf_und_screenshots(pw, app, scheme, width, height):
    _plan(app, "h0", km=8.0, up=150, est_h=3.0)
    pg = _tour(pw, app, width=width, height=height, scheme=scheme)
    try:
        c = pg.locator(CARD)
        expect(c).to_be_visible(timeout=T)
        c.scroll_into_view_if_needed()
        settled(pg)
        assert pg.evaluate("() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)") == 0
        box = c.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= width + 1
        for sel in (".plact .btn", ".plact a"):
            assert pg.locator(CARD + " " + sel).first.bounding_box()["height"] >= 44 - 1
        # Kontrast der Differenzzeile und Legende
        ratio = pg.evaluate("""() => { const p = c => { const n = c.match(/[\\d.]+/g).map(Number); return c.startsWith('color(') ? [n[0] * 255, n[1] * 255, n[2] * 255, n[3] ?? 1] : n; }, L = a => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(a[0]) + .7152 * f(a[1]) + .0722 * f(a[2]); };
          const bg = el => { for (let e = el; e; e = e.parentElement) { const c = p(getComputedStyle(e).backgroundColor); if ((c[3] ?? 1) > .5) return c; } return [255, 255, 255]; };
          return ['#tlw-planist .pe-ist .pld small', '#tlw-planist .plleg span', '#tlw-planist .pefig dt', '#tlw-planist .pedt'].map(s => { const e = document.querySelector(s); const a = L(p(getComputedStyle(e).color)), b = L(bg(e)); return (Math.max(a, b) + .05) / (Math.min(a, b) + .05); }); }""")
        assert min(ratio) >= 4.5, ratio
        _shot(pg, f"tour-plan-ergebnis-{width}-{scheme}.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
