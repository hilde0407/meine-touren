"""3.24.1 – Späte Karten werden an ihre Layout-Position einsortiert (Browser, Chromium).
Herzfrequenz, Wegpunkte, Uhr-Daten und Wetter treffen hier absichtlich erst nach Fotos und Einstieg ein (fetch verzögert).
Erwartung: Reihenfolge im DOM = Reihenfolge im Layout, jede Gruppen-Überschrift genau einmal und vor ihrem ersten Mitglied.
Wettlauf-Regel: auf den Zustand warten (wait_for_function, 15 s), nie nur schlafen."""
import pytest

from tests.test_seitenlayout_ui import _api, _browser, app, clean, pw  # noqa: F401  (Fixtures)
from tests.test_tourseite_ui import READY_SUB

T = 15000
DELAY = """(() => {
  const f = window.fetch.bind(window), d = %d;
  window.fetch = (u, o) => { const s = String(u && u.url || u); return /\\/(hr|wps|weather|uhr-training|metrics|steigung|aehnliche)(\\?|$)/.test(s) ? new Promise(r => setTimeout(r, d)).then(() => f(u, o)) : f(u, o); };
})()"""
# Reihenfolge aller Karten und Gruppen-Überschriften im DOM
FLOW = """() => [...document.querySelectorAll('#tl h2.tlgh, #tl details.tls, #tl #tlg-sum')].filter(e => !e.closest('.sl-off')).map(e => e.matches('h2') ? 'h:' + e.id : (e.dataset.tls || 'sum'))"""
GROUPS_OK = """() => { const h = [...document.querySelectorAll('#tl h2.tlgh')].filter(e => !e.closest('[hidden]')).map(e => e.id.replace(/-\\d+$/, '')); return h.length === new Set(h).size; }"""


@pytest.fixture(autouse=True)
def clean_all(app):
    for k in ("tour-haupt", "tour-auswertung", "uebersicht", "statistik"):
        _api(app, k, "DELETE")
    yield
    for k in ("tour-haupt", "tour-auswertung", "uebersicht", "statistik"):
        _api(app, k, "DELETE")


def _delayed(pw, url, path, ms=1500, tour="r3"):
    pg = _browser(pw, url, devs="one", tour=tour)
    pg.add_init_script(DELAY % ms)
    pg.goto(f"{url}/#/tour/{tour}{path}")
    return pg


def test_main_late_puls_and_wps_stay_in_route_group(pw, app):
    pg = _delayed(pw, app, "")
    pg.wait_for_selector("#tls-photos", timeout=T)
    first = pg.evaluate(FLOW)
    assert "puls" not in first, first                                       # Voraussetzung: Puls ist wirklich später da als die Fotos
    pg.wait_for_selector("#pulscard", timeout=T)
    pg.wait_for_selector("#wpcard", timeout=T)
    pg.wait_for_function("() => { const o = (%s)(); return o.includes('puls') && o.includes('wp'); }" % FLOW, timeout=T)
    pg.wait_for_function("() => (%s)()" % GROUPS_OK, timeout=T)
    pg.wait_for_timeout(1200)                                               # weitere Nachlader (Wetter, Ähnliche …) abwarten, dann Zustand prüfen
    order = pg.evaluate(FLOW)
    assert order[:5] == ["h:tlgh-route", "map", "prof", "puls", "wp"], order
    assert order.index("wp") < order.index("sum") < order.index("photos") or order.index("wp") < order.index("photos"), order
    assert pg.evaluate(GROUPS_OK) and pg.locator("#tl h2.tlgh#tlgh-route-2").count() == 0, order
    assert pg.evaluate("() => document.querySelector('#pulscard').closest('#tlgb-route') !== null")
    assert not pg.errors
    pg.browser_.close()


def test_sub_late_cards_in_registry_order(pw, app):
    pg = _delayed(pw, app, "/auswertung")
    pg.wait_for_function(READY_SUB, timeout=T)
    pg.wait_for_selector("#tl #tls-met", timeout=T)
    pg.wait_for_timeout(2500)
    order = pg.evaluate(FLOW)
    ids = [x for x in order if not x.startswith("h:")]
    ref = ["met", "uhr", "wx", "ana", "steig", "aehn", "cmp"]
    assert ids == [x for x in ref if x in ids] or ids == [x for x in ["geraet"] + ref if x in ids], order
    assert pg.evaluate(GROUPS_OK), order
    assert not pg.errors
    pg.browser_.close()


@pytest.mark.parametrize("order", [["map", "prof", "photos", "sum", "puls", "wp"], ["wp", "photos", "map", "puls", "prof", "sum"], ["map", "prof", "sum", "photos"]])
def test_main_old_saved_order_never_duplicates_group_heading(pw, app, order):
    """Eine ältere gespeicherte Reihenfolge, die Puls und Wegpunkte hinter Fotos und Einstieg stellt, ergab eine zweite Überschrift „Streckenverlauf“ (tlgh-route-2)."""
    _api(app, "tour-haupt", "PUT", {"layout": {"v": 1, "order": order}})
    pg = _delayed(pw, app, "")
    pg.wait_for_selector("#tls-photos", timeout=T)
    pg.wait_for_selector("#pulscard", timeout=T)
    pg.wait_for_selector("#wpcard", timeout=T)
    pg.wait_for_function("() => { const o = (%s)(); return o.includes('puls') && o.includes('wp') && o.includes('photos'); }" % FLOW, timeout=T)
    pg.wait_for_function("() => (%s)()" % GROUPS_OK, timeout=T)
    pg.wait_for_timeout(1200)
    order_dom = pg.evaluate(FLOW)
    heads = [x for x in order_dom if x.startswith("h:")]
    assert len(heads) == len(set(heads)) and not any(h.endswith("-2") for h in heads), order_dom
    i = order_dom.index("h:tlgh-route")
    assert set(order_dom[i + 1:i + 5]) == {"map", "prof", "puls", "wp"}, order_dom          # die Gruppe steht geschlossen hinter ihrer Überschrift
    assert pg.evaluate("() => ['map','prof','puls','wp'].every(k => document.querySelector('#tls-' + k).closest('#tlg-route'))")
    assert not pg.errors
    pg.browser_.close()


def test_dash_late_blocks_keep_layout_order(pw, app):
    _api(app, "uebersicht", "PUT", {"layout": {"v": 1, "order": ["zuletzt", "jahr", "aufmacher", "tag", "erinn"]}})
    pg = _browser(pw, app, devs=None)
    pg.add_init_script(DELAY % 1200)
    pg.goto(f"{app}/#/dash")
    pg.wait_for_selector("main.home #hlast", timeout=T)
    pg.wait_for_function("() => !!document.querySelector('#slopen')", timeout=T)
    pg.wait_for_timeout(2500)
    ids = pg.evaluate("() => [...document.querySelectorAll('main.home > section, main.home > .hcols > section')].filter(e => !e.hidden).map(e => e.id)")
    ref = ["hrecent", "hyear", "hlast", "htag", "hmemsec"]
    assert ids == [x for x in ref if x in ids] and "hrecent" in ids, ids
    assert pg.locator("main.home .hcols").count() <= 1
    assert not pg.errors
    pg.browser_.close()


def test_stats_late_blocks_keep_layout_order(pw, app):
    _api(app, "statistik", "PUT", {"layout": {"v": 1, "order": ["kpi", "ziele", "heat", "sportarten", "bestwerte", "kmmonat", "kmverlauf", "bl", "tp", "tag", "erinn"]}})
    pg = _browser(pw, app, devs=None)
    pg.add_init_script(DELAY % 1200)
    pg.goto(f"{app}/#/stats")
    pg.wait_for_selector("#stx", timeout=T)
    pg.wait_for_selector("#stc-kpi", timeout=T)
    pg.wait_for_timeout(3000)
    ids = pg.evaluate("() => [...document.querySelectorAll('#stx [id^=stc-], #stx #blsec, #stx #tpsec')].map(e => e.id)")
    ref = ["stc-kpi", "stc-ziele", "stc-heat", "stc-sportarten", "stc-bestwerte", "stc-kmmonat", "stc-kmverlauf", "blsec", "tpsec", "stc-tag", "stc-erinn"]
    assert ids == [x for x in ref if x in ids] and len(ids) >= 4, ids
    assert not pg.errors
    pg.browser_.close()
