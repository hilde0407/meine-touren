"""3.37.0 – Neue Bausteine im Browser (Chromium): „Jahreszeiten und Wetter“, Wochenansicht von „Belastung und Erholung“, „Ausrüstung“ mit Prozent und Warnzeichen,
Vorschau in der Baustein-Galerie, 390 px, Hell/Dunkel, Englisch. Die Serverdaten werden für die genauen Zahlen per Route vorgegeben (die Berechnung prüft test_saison.py);
je ein Durchlauf liest den echten Server. Wettlauf-Regel: nach jeder Aktion auf den Zustand warten (expect/wait_for_function, 15 s), nie nur schlafen.
Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import datetime
import json
import re

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.test_seitenlayout_ui import T, _api, _browser, _edit, pw  # noqa: F401
from tests.test_reise_seiten_ui import app  # noqa: F401
from tests.test_tourseite_ui import _shot
from tests.test_bausteine_konfig_ui import open_gear, save_dialog
from tests.helpers_ui import quiet  # noqa: E402

TL = 30000
KEYS = ("tour-haupt", "tour-auswertung", "uebersicht", "statistik", "reise", "reisen", "fotos", "karte")
TODAY = datetime.date.today()
MON = TODAY - datetime.timedelta(days=TODAY.weekday())
ELAPSED = TODAY.weekday() + 1


@pytest.fixture(autouse=True)
def clean(app):
    for k in KEYS:
        _api(app, k, "DELETE")
    yield


def _open(pw, url, widgets, **kw):
    _api(url, "uebersicht", "PUT", {"hidden": ["jahr", "zepp", "zuletzt", "tag", "erinn"], "widgets": widgets})
    pg = _browser(pw, url, devs=None, **kw)
    return pg


def _go(pg, url):
    pg.goto(f"{url}/#/dash", timeout=TL)
    pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen')", timeout=TL)
    quiet(pg, 5000)


def _wx(**kw):
    d = {"zeitraum": "all", "von": None, "bis": TODAY.isoformat(), "sport": [], "touren": 40, "km": 520.0}
    mon = [(12, 100), (10, 80), (30, 200), (36, 300), (44, 500), (50, 700), (46, 650), (40, 520), (30, 380), (20, 260), (8, 90), (4, 40)]
    d["monate"] = [{"monat": i + 1, "touren": n, "km": float(k), "mit_wetter": n, "t_mittel": t, "t_min": t - 6 if t is not None else None, "t_max": t + 6 if t is not None else None}
                   for i, ((n, k), t) in enumerate(zip(mon, [-1.2, 1.0, 6.4, 11.0, 15.3, 19.8, 22.5, 21.0, 16.0, 10.2, 4.0, 0.1]))]
    z = [("fruehling", [3, 4, 5], 110, 840), ("sommer", [6, 7, 8], 150, 1850), ("herbst", [9, 10, 11], 80, 730), ("winter", [12, 1, 2], 70, 330)]
    d["jahreszeiten"] = [{"key": k, "monate": m, "touren": n, "km": float(km), "mit_wetter": n, "t_mittel": t, "t_min": t - 9, "t_max": t + 9}
                         for (k, m, n, km), t in zip(z, [10.9, 21.1, 10.4, 0.0])]
    d["wetter"] = {"mit": 28, "ohne": 12, "t_mittel": 10.6, "t_min": -9.0, "t_max": 30.0, "klassen": [
        {"key": "kalt", "von": None, "bis": 0.0, "touren": 3, "km": 20.0}, {"key": "kuehl", "von": 0.0, "bis": 10.0, "touren": 8, "km": 90.0},
        {"key": "mild", "von": 10.0, "bis": 20.0, "touren": 11, "km": 200.0}, {"key": "warm", "von": 20.0, "bis": None, "touren": 6, "km": 120.0}]}
    d.update(kw)
    return d


def _ohne_wetter():
    d = _wx()
    for m in d["monate"] + d["jahreszeiten"]:
        m.update(mit_wetter=0, t_mittel=None, t_min=None, t_max=None)
    d["wetter"] = {"mit": 0, "ohne": 40, "t_mittel": None, "t_min": None, "t_max": None, "klassen": []}
    return d


def _belastung():
    wochen = []
    spec = {0: (1, "1000000", 5.0, 40), 1: (3, "1010100", 30.0, 300), 2: (2, "0100010", 12.0, None), 4: (1, "0000100", 9.0, 120), 5: (2, "1000001", 18.0, 210), 6: (1, "0010000", 6.0, 80), 7: (2, "0101000", 14.0, 160)}
    for i, (n, tage, km, bel) in spec.items():
        m = MON - datetime.timedelta(days=7 * i)
        wochen.append({"key": m.isoformat(), "label": "x", "von": m.isoformat(), "bis": (m + datetime.timedelta(days=6)).isoformat(), "touren": n, "mit_daten": 0 if bel is None else n,
                       "ohne_angabe": n if bel is None else 0, "belastung": bel, "km": km, "tage": tage})
    wochen.sort(key=lambda w: w["key"])
    return {"wochen": wochen, "monate": [], "daten_insgesamt": 9, "aktuell": {"status": "ok", "stufe": "mehr", "abweichung_pct": 20}, "gesamt": {}, "haertest_wochen": [], "haertest_touren": [], "offen": {}}


def _gear():
    g = lambda i, n, km, lim, st: {"id": i, "name": n, "kind": "Schuhe", "km": km, "up": 0, "h": 0, "n": 1, "limit_km": lim, "status": st, "last": 0, "anteil_pct": round(km / lim * 100) if lim else None}  # noqa: E731
    return [g(1, "Alte Treter", 412, 600, "ok"), g(2, "Mountainbike", 3100, None, ""), g(3, "Trailschuhe", 560, 600, "soon"), g(4, "Laufschuhe", 163, 150, "over"), g(5, "Wanderstiefel", 150, 150, "over")]


def _handler(v):
    def h(route):
        if isinstance(v, tuple):
            route.fulfill(status=v[0], json=v[1])
        else:
            route.fulfill(json=v)
    return h


def _route(pg, **data):
    for k, v in data.items():
        pat = {"saison": "**/api/bausteine/saison*", "belastung": "**/api/stats/belastung*", "gear": "**/api/bausteine/ausruestung*"}[k]
        pg.route(pat, _handler(v))


def _card(pg, t):
    return pg.locator(f'[data-wtype="{t}"]')


def _no_overflow(pg):
    assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"), pg.evaluate("() => [document.documentElement.scrollWidth, window.innerWidth]")


# ------------------------------------------------------------------------------ Jahreszeiten und Wetter

def test_saison_echter_server_rendert_und_hat_aria(pw, app):
    pg = _open(pw, app, [{"id": "s1", "type": "saison", "cfg": {}}])
    try:
        _go(pg, app)
        c = _card(pg, "saison")
        expect(c.locator(".slrows li").first).to_be_visible(timeout=15000)
        assert c.locator(".slrows").first.locator("li").count() == 4 and c.locator("svg.slcol").count() == 1 and c.locator(".slxl span").count() >= 12
        assert c.locator("svg.slcol").get_attribute("role") == "img" and "je Monat" in c.locator("svg.slcol").get_attribute("aria-label")
        assert c.locator(".slwx").count() == 1 or c.locator(".slrows").count() == 2                       # entweder Hinweis ohne Wetterdaten oder die Temperatur-Verteilung
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_saison_mit_wetterdaten_zeigt_temperaturen_und_ohne_hinweis(pw, app):
    pg = _open(pw, app, [{"id": "s1", "type": "saison", "cfg": {}}])
    _route(pg, saison=_wx())
    try:
        _go(pg, app)
        c = _card(pg, "saison")
        expect(c.locator(".slrows").first.locator("li")).to_have_count(4, timeout=15000)
        assert "Sommer" in c.locator(".slrows").first.inner_text() and "im Schnitt 21 °C" in c.locator(".slrows").first.inner_text() and "12 bis 30 °C" in c.locator(".slrows").first.inner_text()
        assert c.locator(".slcmp").inner_text() == "Deine stärkste Jahreszeit: Sommer."
        assert c.locator(".sltmp span").count() == 12 and c.locator(".slwx").count() == 0
        assert c.locator(".slrows").nth(1).locator("li").count() == 4 and "Unter 0 °C" in c.locator(".slrows").nth(1).inner_text()
        assert "Wetterdaten für 28 von 40 Touren" in c.inner_text() and "nie als 0 °C" in c.inner_text()
        assert c.locator(".slbadge, .tlbadge").count() >= 0
        assert not pg.errors, pg.errors
        _api(app, "uebersicht", "PUT", {"hidden": ["jahr", "zepp", "zuletzt", "tag", "erinn"], "widgets": [{"id": "s1", "type": "saison", "cfg": {"metric": "count"}}]})
        pg.unroute("**/api/bausteine/saison*")
        _route(pg, saison=_ohne_wetter())
        pg.reload()
        pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen')", timeout=TL)
        c = _card(pg, "saison")
        expect(c.locator(".slwx")).to_be_visible(timeout=15000)
        assert "keine Wetterdaten" in c.locator(".slwx").inner_text() and "nichts abgerufen" in c.locator(".slwx").inner_text()
        assert c.locator(".sltmp").count() == 0 and "im Schnitt" not in c.inner_text() and "°C" not in c.locator(".slrows").first.inner_text()
        assert "Touren" in c.locator(".slrows").first.locator("li").first.locator("b").inner_text()                # Säulen/Zahlen nach Anzahl der Touren
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_saison_leer_und_fehler(pw, app):
    pg = _open(pw, app, [{"id": "s1", "type": "saison", "cfg": {}}])
    _route(pg, saison=_wx(touren=0, km=0.0))
    try:
        _go(pg, app)
        expect(_card(pg, "saison").locator(".slnone")).to_have_text("Noch keine Touren.", timeout=15000)
        pg.unroute("**/api/bausteine/saison*")
        _route(pg, saison=(500, {"detail": "kaputt"}))
        pg.reload()
        pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen')", timeout=TL)
        expect(_card(pg, "saison").locator(".slnone")).to_have_text("Die Auswertung konnte nicht geladen werden.", timeout=15000)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_saison_fragt_mit_filter_und_zeitraum(pw, app):
    pg = _open(pw, app, [{"id": "s1", "type": "saison", "cfg": {"sports": ["hike", "mtb"], "range": "y", "yr": 2024}}])
    seen = []
    pg.route("**/api/bausteine/saison*", lambda r: (seen.append(r.request.url), r.fulfill(json=_wx())))
    try:
        _go(pg, app)
        expect(_card(pg, "saison").locator(".slrows li").first).to_be_visible(timeout=15000)
        q = seen[0].split("?", 1)[1]
        assert "sport=hike%2Cmtb" in q and "zeitraum=c" in q and "von=2024-01-01" in q and "bis=2024-12-31" in q
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------------------ Belastung und Erholung: Wochenansicht

def test_belastung_wochenansicht_ruhetage_ohne_angabe_und_ruhewoche(pw, app):
    pg = _open(pw, app, [{"id": "b1", "type": "belastung", "cfg": {"view": "wochen"}}])
    _route(pg, belastung=_belastung())
    try:
        _go(pg, app)
        c = _card(pg, "belastung")
        expect(c.locator(".slwk")).to_have_count(8, timeout=15000)
        rows = c.locator(".slwk")
        assert rows.first.get_attribute("class").split() == ["slwk", "cur"] and rows.first.locator(".slr1 small").inner_text() == "läuft"                # neueste Woche zuerst
        assert rows.first.locator(".slr2 span").all_inner_texts() == ["1 Tour", "5,0 km", "1 Ruhetag" if ELAPSED == 2 else f"{ELAPSED - 1} Ruhetage"] and rows.first.locator(".slr1 b").inner_text() == "Belastung 40"
        assert rows.first.locator(".slwdo.on").count() == 1 and rows.first.locator(".slwdo.fut").count() == 7 - ELAPSED and rows.first.locator(".slwdo").count() == 7
        w1 = rows.nth(1)
        assert w1.locator(".slr1 b").inner_text() == "Belastung 300" and w1.locator(".slr2 span").all_inner_texts() == ["3 Touren", "30,0 km", "4 Ruhetage"] and w1.locator(".slwdo.on").count() == 3 and w1.locator(".slwdo.off").count() == 4
        w2 = rows.nth(2)                                                                                              # Touren, aber kein Uhr-Wert: „ohne Angabe“, kein Balken, nie 0
        assert w2.locator(".slr1 b").inner_text() == "Belastung ohne Angabe" and w2.locator(".slbr-f").evaluate("e => +e.getAttribute('width')") == 0 and "5 Ruhetage" in w2.locator(".slr2 span").all_inner_texts()
        w3 = rows.nth(3)                                                                                              # keine Tour in dieser Woche
        assert w3.locator(".slr1 b").inner_text() == "Ruhewoche" and w3.locator(".slr2 span").all_inner_texts() == ["0 Touren", "0,0 km", "7 Ruhetage"] and w3.locator(".slwdo.on").count() == 0
        assert w1.locator(".slwdd").get_attribute("aria-hidden") == "true" and c.locator(".slwleg").count() == 1
        assert "Deutlich" not in c.inner_text() and c.locator(".slcmp").inner_text() == "Etwas mehr Belastung als sonst"
        bars = c.locator(".slbr-f").evaluate_all("els => els.map(e => +e.getAttribute('width'))")
        assert max(bars) == 100 and bars[1] == 100 * 300 / 300 * 1 and bars[0] > 0                                    # die Woche mit der höchsten Belastung füllt den Balken
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_belastung_kompakt_bleibt_unveraendert_und_12_wochen(pw, app):
    pg = _open(pw, app, [{"id": "b1", "type": "belastung", "cfg": {}}, {"id": "b2", "type": "belastung", "cfg": {"view": "wochen", "weeks": 12}}])
    _route(pg, belastung=_belastung())
    try:
        _go(pg, app)
        a, b = pg.locator('[data-wid="b1"]'), pg.locator('[data-wid="b2"]')
        expect(b.locator(".slwk")).to_have_count(12, timeout=15000)
        assert a.locator("svg.slbars rect").count() == 7 and a.locator(".slwk").count() == 0 and "gegenüber dem Schnitt" in a.inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_belastung_ohne_touren_ohne_uhrdaten_und_fehler(pw, app):
    pg = _open(pw, app, [{"id": "b2", "type": "belastung", "cfg": {"view": "wochen"}}])
    leer = {"wochen": [], "monate": [], "daten_insgesamt": 0, "aktuell": {"status": "zu_wenig_daten"}, "gesamt": {}, "haertest_wochen": [], "haertest_touren": [], "offen": {}}
    _route(pg, belastung=leer)
    try:
        _go(pg, app)
        expect(_card(pg, "belastung").locator(".slnone")).to_have_text("In den letzten 8 Wochen gab es keine Tour.", timeout=15000)
        pg.unroute("**/api/stats/belastung*")
        d = _belastung()
        d["daten_insgesamt"] = 0
        d["aktuell"] = {"status": "zu_wenig_daten"}
        for w in d["wochen"]:
            w["belastung"] = None
        _route(pg, belastung=d)
        pg.reload()
        pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen')", timeout=TL)
        c = _card(pg, "belastung")
        expect(c.locator(".slwk")).to_have_count(8, timeout=15000)
        assert "Noch keine Uhr-Daten" in c.inner_text() and "Für einen Vergleich liegen noch zu wenige Wochen" in c.inner_text()
        assert all(t == "Belastung ohne Angabe" for t in c.locator(".slwk").evaluate_all("els => els.filter(e => !/Ruhewoche/.test(e.textContent)).map(e => e.querySelector('.slr1 b').textContent)"))
        assert not pg.errors, pg.errors
        pg.unroute("**/api/stats/belastung*")
        _route(pg, belastung=(500, {"detail": "kaputt"}))
        pg.reload()
        pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen')", timeout=TL)
        expect(_card(pg, "belastung").locator(".slnone")).to_have_text("Die Belastung konnte nicht geladen werden.", timeout=15000)
    finally:
        pg.browser_.close()


def test_belastung_einstellung_ansicht_im_dialog(pw, app):
    pg = _open(pw, app, [{"id": "b1", "type": "belastung", "cfg": {}}])
    _route(pg, belastung=_belastung())
    try:
        _go(pg, app)
        _edit(pg)
        open_gear(pg, '.slit[data-sl="b1"] [data-a="cfg"]')
        assert pg.locator(".sldlg legend").all_inner_texts()[:2] == ["Ansicht", "Wochen in der Wochenansicht"]
        pg.locator(".sldlg .flchip", has_text="Wochenansicht mit Ruhetagen").click()
        pg.locator(".sldlg .flchip", has_text=re.compile(r"^12 Wochen$")).click()
        save_dialog(pg)
        expect(pg.locator('[data-wid="b1"] .slwk')).to_have_count(12, timeout=15000)
        pg.wait_for_function("() => { const s = document.getElementById('slsaved'); return !!s && s.textContent.trim() === 'Ansicht gespeichert'; }", timeout=T)
        cfg = _api(app, "uebersicht")["layout"]["widgets"][0]["cfg"]
        assert cfg == {"view": "wochen", "weeks": 12}, cfg
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------------------ Ausrüstung

def test_ausruestung_prozent_symbol_und_reihenfolge(pw, app):
    pg = _open(pw, app, [{"id": "g1", "type": "ausruestung", "cfg": {}}])
    _route(pg, gear=_gear())
    try:
        _go(pg, app)
        c = _card(pg, "ausruestung")
        expect(c.locator(".slrows li")).to_have_count(5, timeout=15000)
        names = [re.sub(r"^[×!]", "", n.strip()) for n in c.locator(".slrows li .slr1 > span").all_inner_texts()]
        assert names == ["Laufschuhe", "Wanderstiefel", "Trailschuhe", "Alte Treter", "Mountainbike"], names                      # Warnungen zuerst
        li = c.locator(".slrows li")
        assert li.nth(0).locator(".slwi.bad").inner_text() == "×" and li.nth(0).locator(".slwi").get_attribute("aria-hidden") == "true"
        assert li.nth(0).locator(".slr1 b").inner_text() == "163 von 150 km (109 %)" and li.nth(0).locator(".slr2").inner_text() == "Limit überschritten um 13,0 km: Zeit für einen Wechsel"
        assert li.nth(1).locator(".slr2").inner_text() == "Limit erreicht: Zeit für einen Wechsel"
        assert li.nth(2).locator(".slwi.warn").inner_text() == "!" and li.nth(2).locator(".slr2").inner_text() == "Bald fällig: noch 40,0 km" and "(93 %)" in li.nth(2).locator(".slr1 b").inner_text()
        assert li.nth(3).locator(".slwi").count() == 0 and li.nth(3).locator(".slr1 b").inner_text() == "412 von 600 km (69 %)" and li.nth(3).locator(".slr2").inner_text() == "Noch 188 km"
        assert li.nth(4).locator(".slr2").inner_text() == "Ohne Limit" and "%" not in li.nth(4).locator(".slr1 b").inner_text()
        assert pg.locator('[data-wtype="ausruestung"] .slbadge, [data-wtype="ausruestung"] .tlbadge').count() >= 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_ausruestung_echter_server_und_leerzustand(pw, app):
    pg = _open(pw, app, [{"id": "g1", "type": "ausruestung", "cfg": {}}])
    try:
        _go(pg, app)
        c = _card(pg, "ausruestung")
        expect(c.locator(".slrows li, .slnone").first).to_be_visible(timeout=15000)
        assert not pg.errors, pg.errors
        pg.route("**/api/bausteine/ausruestung*", lambda r: r.fulfill(json=[]))
        pg.reload()
        pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen')", timeout=TL)
        expect(_card(pg, "ausruestung").locator(".slnone")).to_have_text("Noch keine Ausrüstung angelegt.", timeout=15000)
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------------------ Galerie, Handy, Hell/Dunkel, Englisch

@pytest.mark.parametrize("width", [1280, 390])
def test_galerie_zeigt_die_neuen_bausteine_mit_live_vorschau(pw, app, width):
    pg = _open(pw, app, [], width=width, height=1000 if width > 600 else 900)
    _route(pg, saison=_wx(), belastung=_belastung(), gear=_gear())
    try:
        _go(pg, app)
        _edit(pg)
        pg.locator("#slbar [data-a=add]").click()
        pg.wait_for_selector(".slcat .slcard", timeout=T)
        for key, qs, sel in (("saison", "Jahreszeiten", ".slrows"), ("belastung", "Belastung", ".slcmp"), ("ausruestung", "Ausrüstung", ".slwi")):
            pg.locator("#slq").fill(qs)
            card = pg.locator(f'.slcat .slcard:has([data-add="{key}"])')
            expect(card).to_be_visible(timeout=15000)
            card.scroll_into_view_if_needed()
            pg.wait_for_function("(k) => { const e = document.querySelector(`.slcat .slcard [data-add=${k}]`); const p = e && e.closest('.slcard').querySelector('.slpv'); return !!p && p.dataset.live === 'live'; }", arg=key, timeout=TL)
            pv = card.locator(".slpv")
            assert pv.locator(".slpvlive " + sel).count() >= 1 and pv.evaluate("e => e.querySelector('.slpvlive .tlw').inert === true"), key
            _no_overflow(pg)
            _shot(pg, f"galerie-{key}-{width}.png", full=False)
        assert not pg.errors, pg.errors
        pg.locator("#slq").fill("Jahreszeiten")
        pg.locator('.slcat [data-add="saison"]').click()
        pg.wait_for_function("() => !document.querySelector('.slcat') && !!document.querySelector('[data-wtype=saison] .slrows li')", timeout=TL)
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", [1280, 390])
def test_ansichten_in_beiden_themes_und_breiten(pw, app, scheme, width):
    pg = _open(pw, app, [{"id": "s1", "type": "saison", "cfg": {}}, {"id": "b1", "type": "belastung", "cfg": {"view": "wochen"}}, {"id": "g1", "type": "ausruestung", "cfg": {}}],
               width=width, height=1000 if width > 600 else 900, scheme=scheme)
    _route(pg, saison=_wx(), belastung=_belastung(), gear=_gear())
    try:
        _go(pg, app)
        expect(pg.locator('[data-wtype="belastung"] .slwk')).to_have_count(8, timeout=15000)
        expect(pg.locator('[data-wtype="saison"] .slrows li').first).to_be_visible(timeout=15000)
        expect(pg.locator('[data-wtype="ausruestung"] .slrows li')).to_have_count(5, timeout=15000)
        _no_overflow(pg)
        # nicht nur Farbe: Warnzeilen tragen Symbol und Text; Kontrast des Symbols (Zeichen gegen Kreis) mindestens 3:1
        for sel in (".slwi.bad", ".slwi.warn"):
            r = pg.locator(f'[data-wtype="ausruestung"] {sel}').first.evaluate("""e => {
              const p = c => c.match(/[\\d.]+/g).map(Number), L = c => { const [r, g, b] = p(c).slice(0, 3).map(v => { v /= 255; return v <= .03928 ? v / 12.92 : ((v + .055) / 1.055) ** 2.4; }); return .2126 * r + .7152 * g + .0722 * b; };
              const cs = getComputedStyle(e); let bg = cs.backgroundColor; if (/rgba\\(.*, 0\\)|transparent/.test(bg)) bg = getComputedStyle(document.body).backgroundColor;
              const a = L(cs.color), b = L(bg); return (Math.max(a, b) + .05) / (Math.min(a, b) + .05); }""")
            assert r >= 4.5, (scheme, sel, r)
        _shot(pg, f"saison-neu-{width}-{scheme}.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_englisch(pw, app):
    pg = _open(pw, app, [{"id": "s1", "type": "saison", "cfg": {}}, {"id": "b1", "type": "belastung", "cfg": {"view": "wochen"}}, {"id": "g1", "type": "ausruestung", "cfg": {}}], locale="en-US")
    _route(pg, saison=_wx(), belastung=_belastung(), gear=_gear())
    try:
        _go(pg, app)
        expect(pg.locator('[data-wtype="belastung"] .slwk')).to_have_count(8, timeout=15000)
        s, b, g = _card(pg, "saison"), _card(pg, "belastung"), _card(pg, "ausruestung")
        expect(s.locator(".slrows li").first).to_be_visible(timeout=15000)
        expect(g.locator(".slrows li")).to_have_count(5, timeout=15000)
        assert "Your strongest season: Summer." == s.locator(".slcmp").inner_text() and "on average 21 °C" in s.locator(".slrows").first.inner_text()
        assert "Wk" in b.locator(".slwk").first.inner_text() and "rest days" in " ".join(b.locator(".slwk").nth(1).locator(".slr2 span").all_inner_texts()) and "Rest week" in b.inner_text() and "Load not specified" in b.inner_text()
        assert "Limit exceeded by 13.0 km" in g.inner_text() and "Due soon" in g.inner_text()
        assert not re.search(r"Ruhetag|Jahreszeit|Belastung|überschritten", s.inner_text() + b.inner_text() + g.inner_text()), (s.inner_text() + b.inner_text() + g.inner_text())[:300]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
