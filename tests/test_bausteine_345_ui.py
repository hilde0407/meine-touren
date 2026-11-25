"""3.45.0 „Weniger Bausteine, klarere Namen“ (Browser, Chromium): alte Baustein-Kennungen laden weiter (Server-Antwort mit alten Typen, umgezogene gespeicherte Ansicht, alter
Ansichtscode per Link), Vorlagen ohne alte Typen, Baustein „Ziele“ (Balken, Ring, Nur Warnung; Pflege als Abschnitt der Statistik), Baustein „Bestwerte“ (Anzahl 1/3/…), Katalognamen
eindeutig und gleich dem Titel, Gruppe „Allgemein (nicht zu dieser Tour)“ im Katalog der Tourseite, Felder nur zur passenden Darstellung, 390 px ohne Überlauf, hell/dunkel.
Wettlauf-Regel: auf Zustände warten (expect/wait_for_function mit 15 s). Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt. Nur erfundene Testdaten."""
import base64
import json
import os
import urllib.request
from datetime import date

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.helpers_ui import press_until_gone, quiet, settled  # noqa: E402
from tests.test_seitenlayout_ui import T, _api, _browser, _edit, pw  # noqa: E402,F401
from tests.test_statistik_ui import TL, app  # noqa: E402,F401
from tests.test_tourseite_ui import _shot  # noqa: E402

KEYS = ("tour-haupt", "tour-auswertung", "uebersicht", "statistik")
YEAR = date.today().year
DOY = (date.today() - date(YEAR, 1, 1)).days + 1
ALT = [
    {"id": "w1", "type": "jahresziel", "cfg": {"metric": "km", "goal": 1200}},
    {"id": "w2", "type": "jahresziele", "cfg": {}},
    {"id": "w3", "type": "hnziel", "cfg": {"schwelle": 10}},
    {"id": "w4", "type": "hnwoche", "cfg": {"einheit": "touren", "ziel": 3}},
    {"id": "w5", "type": "rekorde", "cfg": {}},
    {"id": "w7", "type": "hinweise", "cfg": {"woche_ziel": 40}},
]
NEU = {"w1": "ziele", "w2": "ziele", "w3": "ziele", "w4": "ziele", "w5": "bestwerte", "w7": "hinweise"}


def _req(url, path, method="GET", body=None):
    r = urllib.request.Request(url + path, method=method, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=10) as x:
        return json.loads(x.read() or b"{}")


def _no_goals(url):
    for g in _req(url, "/api/goals"):
        _req(url, f"/api/goals/{g['id']}", "DELETE")


@pytest.fixture(autouse=True)
def clean(app):
    for k in KEYS:
        _api(app, k, "DELETE")
    _no_goals(app)
    yield
    _no_goals(app)


def _open(pw, app, route="#/dash", sel="#slopen", **kw):
    pg = _browser(pw, app, devs=None, **kw)
    pg.goto(f"{app}/{route}", timeout=TL)
    pg.wait_for_selector(sel, state="attached", timeout=TL)
    return pg


def _code(layouts, page="uebersicht", name="Alte Ansicht"):
    d = {"format": "meine-touren-ansicht", "format_version": 1, "app_version": "3.44.0", "page": page, "name": name, "layouts": layouts}
    return "MTA1." + base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")


def _catalog(pg):
    pg.locator("#slbar [data-a=add]").click()
    pg.wait_for_selector(".slcat .slcard", timeout=T)


# ------------------------------------------------------------------------------------------------ Umzug alter Kennungen
def test_alte_kennungen_aus_server_oder_zwischenspeicher_werden_abgebildet(pw, app):
    """Die Oberfläche bildet alte Typen selbst ab (SL_ALIAS), etwa aus einem Zwischenspeicher oder einer älteren Server-Antwort: keine Lücke, kein Fehler."""
    old = {"widgets": ALT + [{"id": "w6", "type": "sttop", "cfg": {"wert": "km", "n": 3}}], "order": ["w5", "w1"]}
    box = {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": old}], "active": "standard", "rules": {}}
    pg = _browser(pw, app, devs=None)
    try:
        def fake(k):
            return lambda r: r.fulfill(json={"key": k, "layout": old, "container": box, "ts": 1}) if r.request.method == "GET" else r.continue_()
        for k in ("uebersicht", "statistik"):
            pg.route(f"**/api/layout/{k}", fake(k))
        pg.goto(f"{app}/#/dash", timeout=TL)
        for i, t in NEU.items():
            pg.wait_for_selector(f"#tlw-{i}[data-wtype={t}]", state="attached", timeout=T)
        assert pg.evaluate("() => SL.docs.uebersicht.widgets.map(w => w.type)") == ["ziele", "ziele", "ziele", "ziele", "bestwerte", "hinweise", "bestwerte"]
        assert pg.evaluate("() => JSON.stringify(SL.docs.uebersicht.widgets[0].cfg)") == '{"view":"ring","zeit":"jahr"}'
        assert pg.evaluate("() => SL.docs.uebersicht.widgets[6].cfg.n") == 3
        expect(pg.locator("#tlw-w5 .utile").first).to_be_visible(timeout=T)
        pg.goto(f"{app}/#/stats", timeout=TL)
        pg.wait_for_selector("#tlw-w6[data-wtype=bestwerte] ol li", state="attached", timeout=T)
        expect(pg.locator("#tlw-w6 ol li")).to_have_count(3, timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_gespeicherte_alte_ansicht_zieht_um_und_behaelt_das_ziel(pw, app):
    _api(app, "uebersicht", "PUT", {"widgets": ALT})
    assert [w["type"] for w in _api(app, "uebersicht")["layout"]["widgets"]] == [NEU[w["id"]] for w in ALT]
    assert sorted((g["period"], g["metric"], g["target"]) for g in _req(app, "/api/goals")) == [("week", "count", 3.0), ("week", "km", 40.0), ("year", "km", 1200.0)]
    pg = _open(pw, app)
    try:
        expect(pg.locator("#tlw-w1 .slgoal")).to_have_count(1, timeout=T)                         # Ring wie früher, mit dem übernommenen Ziel
        expect(pg.locator("#tlw-w1 .slcmp")).to_contain_text("von 1.200 km", timeout=T)
        expect(pg.locator("#tlw-w2 .goal")).to_have_count(1, timeout=T)                           # „Ziele“: nur Jahresziele (wie bisher)
        expect(pg.locator("#tlw-w4 .goal.zlw")).to_have_count(2, timeout=T)                       # ehemaliges „Wochenziel“: die Wochenziele
        expect(pg.locator("#tlw-w4 .tlt")).to_have_text("Ziele dieser Woche", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_alter_ansichtscode_per_link_wird_importiert(pw, app):
    code = _code({"uebersicht": {"widgets": [ALT[0], ALT[4]]}}, name="Aus 3.44")
    pg = _open(pw, app)
    try:
        quiet(pg, 3000)
        pg.goto(f"{app}/#/layoutcode/{code}")
        pg.wait_for_selector("#slimpres .slimpok", timeout=T)
        expect(pg.locator("#slimpres")).to_contain_text("1.200 km im Jahr", timeout=T)
        expect(pg.locator("#slimpres")).to_contain_text("nicht übernommen", timeout=T)
        assert "nicht bekannt" not in pg.locator("#slimpres").inner_text()
        pg.get_by_role("button", name="Als neue Ansicht importieren", exact=True).click()
        pg.wait_for_function("() => slViewName('uebersicht', SL.view.uebersicht) === 'Aus 3.44'", timeout=T)
        assert pg.evaluate("() => SL.docs.uebersicht.widgets.map(w => w.type)") == ["ziele", "bestwerte"]
        press_until_gone(pg, "Escape", ".sldlg")
        pg.wait_for_selector("#tlw-w5[data-wtype=bestwerte]", state="attached", timeout=T)
        assert _req(app, "/api/goals") == []                                                       # fremdes Ziel wird nicht angelegt
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_vorlagen_nutzen_nur_vorhandene_bausteine(pw, app):
    pg = _open(pw, app)
    try:
        bad = pg.evaluate("""() => SL_TPL.flatMap(t => t.items.filter(([r]) => r.startsWith('w:') && !window.SL_WT[r.slice(2)]).map(([r]) => t.id + ':' + r))""")
        assert bad == []
        kompakt = pg.evaluate("() => SL_TPL.find(t => t.id === 'ue-kompakt').items.map(i => i[0])")
        assert kompakt == ["jahr", "w:periode", "w:letzte", "w:bestwerte"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------------------------------------ Ziele
def test_ziele_darstellungen_balken_ring_warnung(pw, app):
    _req(app, "/api/goals", "POST", {"year": YEAR, "metric": "km", "target": 99999})
    _req(app, "/api/goals", "POST", {"year": YEAR, "metric": "count", "sport": "hike", "target": 2})
    _req(app, "/api/goals", "POST", {"period": "week", "metric": "count", "target": 2})
    _api(app, "uebersicht", "PUT", {"widgets": [{"id": "zb", "type": "ziele", "cfg": {}}, {"id": "zr", "type": "ziele", "cfg": {"view": "ring", "zeit": "jahr"}},
                                                {"id": "zw", "type": "ziele", "cfg": {"view": "warnung", "zeit": "jahr", "schwelle": 10}},
                                                {"id": "zh", "type": "ziele", "cfg": {"view": "balken", "sports": ["jogging"]}}]})
    pg = _open(pw, app)
    try:
        expect(pg.locator("#tlw-zb .goal")).to_have_count(3, timeout=T)                           # zwei Jahresziele und ein Wochenziel
        expect(pg.locator("#tlw-zb .goal.zlw")).to_have_count(1, timeout=T)
        expect(pg.locator("#tlw-zr .slgoal")).to_have_count(2, timeout=T)
        expect(pg.locator("#tlw-zh .goal")).to_have_count(2, timeout=T)                           # Sportart: das Ziel ohne Sportart betrifft alle, „Wandern“ nicht
        if DOY >= 14:                                                                              # Prognose erst ab dem 14. Tag des Jahres
            pg.wait_for_function("() => document.querySelector('#tlw-zw').dataset.hn === 'an'", timeout=T)
            expect(pg.locator("#tlw-zw .hnbox")).to_contain_text("Prognose", timeout=T)
        assert pg.locator("#tlw-zb a[href='#/stats']").count() == 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_ziele_werden_in_der_statistik_gepflegt(pw, app):
    pg = _open(pw, app, route="#/stats", sel="#tlw-ziele")
    try:
        expect(pg.locator("#tlw-ziele .slnone")).to_contain_text(f"Noch kein Ziel für {YEAR}", timeout=T)
        pg.locator("#tlw-ziele .zladd > summary").click()
        pg.select_option("#gper", "week")
        pg.select_option("#gm", "count")
        pg.fill("#gt", "3")
        pg.locator("#gadd").click()
        expect(pg.locator("#tlw-ziele .goal.zlw")).to_have_count(1, timeout=T)
        expect(pg.locator("#tlw-ziele .goal.zlw .gh b")).to_have_text("Touren pro Woche", timeout=T)
        assert [(g["period"], g["year"], g["target"]) for g in _req(app, "/api/goals")] == [("week", 0, 3.0)]
        pg.locator("#tlw-ziele .zladd > summary").click()
        pg.fill("#gt", "500")
        pg.locator("#gadd").click()
        expect(pg.locator("#tlw-ziele .goal")).to_have_count(2, timeout=T)
        pg.locator("#tlw-ziele .goal.zlw .gx").click()
        pg.get_by_role("button", name="Löschen", exact=True).click()                             # Rückfrage über uiConfirm
        expect(pg.locator("#tlw-ziele .goal")).to_have_count(1, timeout=T)
        assert [(g["period"], g["target"]) for g in _req(app, "/api/goals")] == [("year", 500.0)]
        # das Jahr folgt dem Filter der Seite
        pg.goto(f"{app}/#/stats?y={YEAR - 1}")
        expect(pg.locator("#tlw-ziele .tlt")).to_have_text(f"Ziele {YEAR - 1}", timeout=T)
        expect(pg.locator("#tlw-ziele .slnone")).to_contain_text(f"Noch kein Ziel für {YEAR - 1}", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_einstellungen_zeigen_felder_nur_zur_darstellung(pw, app):
    _api(app, "uebersicht", "PUT", {"widgets": [{"id": "zb", "type": "ziele", "cfg": {}}]})
    pg = _open(pw, app)
    try:
        pg.wait_for_selector("#tlw-zb", state="attached", timeout=T)
        _edit(pg)
        pg.locator('.slit[data-sl="zb"] [data-a=cfg]').click()
        pg.wait_for_selector(".slform", timeout=T)
        sch = pg.locator(".slform [data-show]").filter(has_text="Prozent")
        expect(sch).to_be_hidden(timeout=T)
        pg.locator(".slform label.flchip", has_text="Nur Warnung").click()
        expect(sch).to_be_visible(timeout=T)
        pg.locator(".slform button[type=submit]").click()
        pg.wait_for_function("() => SL.docs.uebersicht.widgets[0].cfg.view === 'warnung' && SL.docs.uebersicht.widgets[0].cfg.schwelle === 10", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------------------------------------ Bestwerte
def test_bestwerte_anzahl_und_abschnitt_der_statistik(pw, app):
    _api(app, "statistik", "PUT", {"widgets": [{"id": "b1", "type": "bestwerte", "cfg": {"eigen": True}}, {"id": "b3", "type": "bestwerte", "cfg": {"n": 3, "werte": ["km", "monat"], "eigen": True}}]})
    pg = _open(pw, app, route="#/stats", sel="#tlw-bestwerte")
    try:
        expect(pg.locator("#tlw-bestwerte .tlt")).to_have_text("Bestwerte", timeout=T)
        expect(pg.locator("#tlw-bestwerte .utile")).to_have_count(5, timeout=T)                 # Abschnitt „Bestwerte“: Strecke, Aufstieg, Dauer, Tempo, Monat
        expect(pg.locator("#tlw-b1 a.utile.slrec")).to_have_count(4, timeout=T)
        expect(pg.locator("#tlw-b3 ol")).to_have_count(2, timeout=T)
        expect(pg.locator("#tlw-b3 ol").first.locator("li")).to_have_count(3, timeout=T)
        assert pg.locator("#tlw-b3 .bwh").all_inner_texts() == ["Nach Strecke", "Stärkste Monate"]
        assert pg.locator("#tlw-b3 .flk").inner_text().startswith("Top 3")
        best = pg.evaluate("() => Math.max(...TOURS.map(t => t.km))")
        expect(pg.locator("#tlw-b3 ol").first.locator("li b").first).to_have_text(pg.evaluate(f"() => fmtKm({best})"), timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------------------------------------ Namen und Katalog
NAMES = """() => {
  const out = {dup: [], title: [], sec: [], old: []}, fams = ['uebersicht', 'statistik', 'tour', 'reise', 'reisen', 'fotos', 'karte'];
  for (const fam of fams) {
    const L = Object.entries(SL_WT).filter(([, T]) => slFits(T, fam)), seen = {};
    for (const [k, T] of L) {
      const n = T.name;
      if (seen[n]) out.dup.push(fam + ':' + n); seen[n] = 1;
      const t = T.title(T.defaults || {});
      if (t !== n && !t.startsWith(n) && !(T.name === 'Diese Woche / dieser Monat') && !T.neu && !/^Strecke je Tag|Reisen je Jahr/.test(n)) out.title.push(k + ': ' + n + ' / ' + t);
      if ((SL_REG[fam] || []).some(r => r.title === n && r.build !== k)) out.sec.push(fam + ':' + n);
      if (/-Kachel|-Mini|-Streifen|-Tafel|Mini-|-Knopf|-Zeitleiste/.test(n)) out.old.push(n);
    }
  }
  return out;
}"""


def test_katalognamen_eindeutig_gleich_titel_nie_wie_ein_abschnitt(pw, app):
    pg = _open(pw, app)
    try:
        pg.wait_for_function("() => typeof SL_WT === 'object' && !!SL_WT.ziele && !!SL_WT.bestwerte", timeout=T)
        r = pg.evaluate(NAMES)
        assert r == {"dup": [], "title": [], "sec": [], "old": []}, r
        for t in ("jahresziel", "jahresziele", "hnziel", "hnwoche", "rekorde", "sttop"):
            assert pg.evaluate(f"() => !SL_WT['{t}']"), t
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("width,scheme", [(1280, "light"), (390, "dark")])
def test_katalog_der_uebersicht_und_der_statistik(pw, app, width, scheme):
    sfx = f"{width}-{'hell' if scheme == 'light' else 'dunkel'}"
    pg = _open(pw, app, width=width, height=900, scheme=scheme)
    try:
        _edit(pg)
        _catalog(pg)
        names = pg.locator(".slcard .slci h3").all_inner_texts()
        assert names.count("Ziele") == 1 and names.count("Bestwerte") == 1
        for n in ("Jahresziel", "Jahresziel in Gefahr", "Wochenziel", "Rekorde", "Top-Touren"):
            assert n not in names, n
        assert len(names) == 33
        _shot(pg, f"uebersicht-katalog-{sfx}.png", full=False)
        press_until_gone(pg, "Escape", ".slcat")
        pg.goto(f"{app}/#/stats")
        pg.wait_for_selector("#tlw-ziele", state="attached", timeout=TL)
        quiet(pg, 3000)
        _edit(pg)
        _catalog(pg)
        names = pg.locator(".slcard .slci h3").all_inner_texts()
        assert names.count("Ziele") == 1 and names.count("Bestwerte") == 1 and "Top-Touren" not in names
        assert len(names) == 31                                                                    # vorher 34: „Ziele“ und „Bestwerte“ statt Jahresziel, Ziele, Jahresziel in Gefahr, Rekorde, Top-Touren
        pg.fill("#slq", "Ziele")
        pg.wait_for_function("() => document.querySelectorAll('.slcard:not([hidden])').length >= 1", timeout=T)
        assert pg.evaluate("() => document.querySelector('.slcat').scrollWidth <= document.querySelector('.slcat').clientWidth + 1")
        _shot(pg, f"statistik-katalog-{sfx}.png", full=False)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("width,scheme", [(1280, "light"), (390, "dark")])
def test_tourseite_allgemeine_bausteine_in_zugeklappter_gruppe(pw, app, width, scheme):
    pg = _open(pw, app, route="#/tour/t0", sel="#slopen", width=width, height=900, scheme=scheme)
    try:
        quiet(pg, 3000)
        _edit(pg)
        _catalog(pg)
        g = pg.locator("details.slallg")
        expect(g).to_have_count(1, timeout=T)
        assert g.evaluate("e => e.open") is False
        expect(g.locator("summary")).to_have_text("Allgemein (nicht zu dieser Tour)", timeout=T)
        inside = g.locator(".slcard .slci h3").evaluate_all("es => es.map(e => e.textContent)")          # zugeklappt: Text über textContent
        assert "Ziele" in inside and "Dein Jahr" in inside and "Kennzahlen" not in inside
        outside = pg.locator(".slcat section.slsec .slcard .slci h3").all_inner_texts()
        assert "Kennzahlen" in outside and "Ziele" not in outside and "Dein Jahr" not in outside
        assert pg.evaluate("() => [...document.querySelectorAll('.slcat section.slsec .slcard')].every(c => c.dataset.cat !== 'allg')")
        pg.locator(".slchip", has_text="Allgemein").click()
        pg.wait_for_function("() => document.querySelector('details.slallg').open", timeout=T)
        pg.locator(".slchip", has_text="Alle").first.click()
        pg.evaluate("() => { document.querySelector('details.slallg').open = false; }")
        pg.fill("#slq", "Bestwerte")
        pg.wait_for_function("() => document.querySelector('details.slallg').open && document.querySelectorAll('.slcard:not([hidden])').length === 1", timeout=T)
        pg.fill("#slq", "")
        pg.evaluate("() => { document.querySelector('details.slallg').open = true; }")
        pg.locator("details.slallg").scroll_into_view_if_needed()
        _shot(pg, f"tour-katalog-{width}-{'hell' if scheme == 'light' else 'dunkel'}.png", full=False)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("width,scheme", [(1280, "light"), (1280, "dark"), (390, "light"), (390, "dark")])
def test_neue_bausteine_responsiv_hell_dunkel(pw, app, width, scheme):
    _req(app, "/api/goals", "POST", {"year": YEAR, "metric": "km", "target": 400})
    _req(app, "/api/goals", "POST", {"period": "week", "metric": "count", "target": 2})
    _api(app, "uebersicht", "PUT", {"widgets": [{"id": "zb", "type": "ziele", "cfg": {}}, {"id": "zr", "type": "ziele", "cfg": {"view": "ring"}},
                                                {"id": "b1", "type": "bestwerte", "cfg": {}}, {"id": "b5", "type": "bestwerte", "cfg": {"n": 5, "werte": ["km", "tempo"]}}]})
    pg = _open(pw, app, width=width, height=900, scheme=scheme, dpr=2 if width < 500 else 1)
    try:
        for s in ("#tlw-zb .goal", "#tlw-zr .slgoal", "#tlw-b1 .utile", "#tlw-b5 ol li"):
            pg.wait_for_selector(s, timeout=T)
        settled(pg)
        assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"), "horizontaler Überlauf"
        for s in ("#tlw-zb", "#tlw-zr", "#tlw-b1", "#tlw-b5"):
            assert pg.evaluate(f"() => {{ const e = document.querySelector('{s}'); return e.scrollWidth <= e.clientWidth + 1; }}"), s
        pg.locator("#tlw-zr").scroll_into_view_if_needed()
        _shot(pg, f"bausteine-{width}-{'hell' if scheme == 'light' else 'dunkel'}.png")
        if width < 500:
            pg.goto(f"{app}/#/stats")
            pg.wait_for_selector("#tlw-ziele .zladd", timeout=TL)
            settled(pg)
            assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
            pg.locator("#tlw-ziele .zladd > summary").click()
            box = pg.locator("#gt").bounding_box()
            assert box and box["x"] >= 0 and box["x"] + box["width"] <= width + 1
            if os.environ.get("TS_SHOTS"):
                pg.locator("#tlw-ziele").screenshot(path=os.path.join(os.environ["TS_SHOTS"], f"statistik-ziele-{width}-{'hell' if scheme == 'light' else 'dunkel'}.png"))
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
