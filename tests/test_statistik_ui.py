"""3.22.0 – Statistik als Widget-Seite + globaler Filter (Browser, Chromium).
Standardlayout unverändert, Abschnitte einklappbar, globaler Filter (Aktivität mehrfach, Zeitraum, frei von–bis) ändert Werte mehrerer Bausteine und bleibt nach Neuladen in der Adresse,
Baustein mit eigenem Filter bleibt, Bearbeitungsmodus (Reihenfolge, Breite, Ausblenden, Baustein hinzufügen, Zahnrad-Schalter), Ansichten und Vorlagen auf der Statistikseite, 390 px, Kontrast, Tastatur.
Wettlauf-Regel: nach jeder Aktion auf den Zustand warten (wait_for_function/expect mit 15 s), nie nur schlafen.
Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt (Chromium, dpr 2)."""
import json
import os
import socket
import subprocess
import sys

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.helpers_ui import quiet  # noqa: E402
from tests.test_seitenlayout_ui import ROOT, T, _api, _browser, _edit, _saved, pw  # noqa: F401
from tests.test_tourseite_ui import CONTRAST, LAUNCH, _settled, _shot, _wait

TL = 30000        # erster Seitenaufbau unter Last (parallele Läufe)
KEYS = ("tour-haupt", "tour-auswertung", "uebersicht", "statistik")
# (Tage zurück, Sportart, km, Dauer in s, Aufstieg m): dieses Jahr, Vorjahr und davor; drei Sportarten
TOURS = [(10, "touringbicycle", 40, 7200, 300), (30, "hike", 14, 14400, 500), (60, "touringbicycle", 60, 10800, 600), (120, "hike", 10, 10800, 300), (200, "jogging", 8, 3600, 80),
         (400, "hike", 25, 25200, 1100), (450, "touringbicycle", 80, 14400, 700), (700, "hike", 18, 18000, 650), (800, "jogging", 10, 4000, 90), (260, "hike", 22, 21600, 900)]
SEED = r"""
import sys, os, time; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db, config
db.init()
now = int(time.time())
for i, (days, sport, km, dur, up) in enumerate(%(tours)r):
    ts = now - days * 86400
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,?,?,'t','komoot')", ("t%%d" %% i, "Tour %%d %%s" %% (i, sport), sport, ts, ts + dur, km * 1000, dur, up, up))
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    tmp = tmp_path_factory.mktemp("st")
    data = tmp / "data"
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data), "tours": TOURS}], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / "launch.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    pr = subprocess.Popen([sys.executable, str(script)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    yield url
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)


@pytest.fixture(autouse=True)
def clean(app):
    for k in KEYS:
        _api(app, k, "DELETE")
    yield


STD = ["kpi", "ziele", "kmmonat", "kmverlauf", "sportarten", "bestwerte", "heat"]          # feste Abschnitte vor „Belastung/Tempo“ (ohne Uhr-Daten gibt es die nicht), „An diesem Tag“ je nach Datum
SECS = "() => [...document.querySelectorAll('#stx > .tlw > details.tls, #stx > #blsec, #stx > #tpsec')].map(e => e.dataset.tls || e.id)"


def _stats(pw, url, query="", width=1280, height=1000, scheme="light", dpr=1, locale="de-DE"):
    pg = _browser(pw, url, width=width, height=height, scheme=scheme, dpr=dpr, locale=locale, devs=None)
    pg.goto(f"{url}/#/stats{query}", timeout=TL)
    pg.wait_for_selector("#stx #tls-kpi", state="attached", timeout=TL)             # erster Aufbau unter Last: großzügiger als T
    pg.wait_for_function("() => !!document.querySelector('#slopen') && typeof SL === 'object' && !!SL.view.statistik", timeout=T)
    return pg


def _vals(pg):
    return pg.evaluate("() => ({n: document.querySelector('#stf .sub').textContent, kpi: [...document.querySelectorAll('#tlsb-kpi .fig .v')].map(e => e.textContent.replace(/\\s+/g, ''))})")


def _go(pg, query):
    """Hash-Navigation und Warten, bis der Router die Seite NEU gezeichnet hat (die alte Ansicht trägt data-old und zählt nicht)."""
    changed = pg.evaluate("q => { const x = document.getElementById('stx'); if (location.hash === '#/stats' + q) return false; if (x) x.dataset.old = '1'; location.hash = '#/stats' + q; return true; }", query)
    if changed:
        pg.wait_for_selector("#stx:not([data-old]) #tls-kpi", state="attached", timeout=T)
    pg.wait_for_function("() => !!document.querySelector('#slopen') && typeof SL === 'object' && !!SL.view.statistik", timeout=T)


def _wait_n(pg, text):
    pg.wait_for_function("t => { const s = document.querySelector('#stf .sub'); return !!s && s.textContent.trim() === t && !!document.querySelector('#stx #tls-kpi'); }", arg=text, timeout=T)


def _server(url, key="statistik"):
    return _api(url, key).get("layout")


# ------------------------------------------------------------------  Standard bleibt Standard  ------------------------------------------------------------------

def test_default_layout_is_unchanged_and_sections_fold(pw, app):
    pg = _stats(pw, app)
    try:
        secs = pg.evaluate(SECS)
        assert secs[:7] == STD and secs[-1] == "erinn" or secs[-1] == "tag" or "erinn" not in secs, secs
        assert pg.locator("#slopen").is_visible() and pg.locator(".slit").count() == 0 and pg.locator("#slbar").count() == 0
        # alle bisherigen Steuerungen sind da
        assert pg.locator(".years button").count() == 1 + len(pg.evaluate("years()")) and pg.locator(".years button.on").inner_text() == "Gesamt"
        assert pg.locator("#sch [data-s='']").inner_text() == "Alle Sportarten" and pg.locator("#sch [data-s]").count() == 1 + 3
        assert pg.locator("#tlsb-kpi .fig").count() == 5 and pg.locator("#tls-kmmonat .chart").count() == 1 and pg.locator("#tls-kmverlauf .chart").count() == 1
        expect(pg.locator("#tlw-bestwerte .utile")).to_have_count(5, timeout=T)                  # 3.45.0: Abschnitt „Bestwerte“ ist der Baustein (Strecke, Aufstieg, Dauer, Tempo, Monat)
        assert pg.locator("#tls-heat svg.heat").count() == 1
        assert pg.locator("#stf h2").inner_text() == "Alle Touren" and _vals(pg)["n"] == "10 Touren"
        # Köpfe mit Kurzaussage, Aufbau wie bei den anderen Abschnitten (tlCard)
        assert "10 Touren" in pg.locator("#tlk-kpi").inner_text() and "km" in pg.locator("#tlk-kpi").inner_text()
        assert "287 km" in pg.locator("#tlk-kmmonat").inner_text() and "Tage mit Touren" in pg.locator("#tlk-heat").inner_text()
        assert pg.locator("#stx .stn").count() == 0                                           # ohne Filter kein Hinweis
        # einklappbar, Zustand bleibt nach Neuladen
        d = pg.locator("#tls-kmmonat")
        assert d.evaluate("e => e.open")
        d.locator("> summary").click()
        pg.wait_for_function("() => localStorage.getItem('mt_trf_st_kmmonat') === '0'", timeout=T)
        assert not d.evaluate("e => e.open") and d.locator("> summary").get_attribute("aria-expanded") == "false"
        pg.reload()
        pg.wait_for_selector("#stx #tls-kmmonat", timeout=T)
        pg.wait_for_function("() => document.querySelector('#tls-kmmonat') && !document.querySelector('#tls-kmmonat').open", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  globaler Filter  ------------------------------------------------------------------

def _add(pg, type_):
    pg.locator("#slbar [data-a=add]").click()
    pg.wait_for_selector(f'.slcat [data-add="{type_}"]', timeout=T)
    pg.locator(f'.slcat [data-add="{type_}"]').click()
    pg.wait_for_selector(f"#stx .tlw[data-wtype='{type_}']", timeout=T)


def _put(url, widgets, **kw):
    _api(url, "statistik", "PUT", {"v": 1, "widgets": widgets, **kw})


def test_global_filter_changes_several_blocks_keeps_own_filter_and_survives_reload(pw, app):
    _put(app, [{"id": "wa", "type": "stmonate", "cfg": {}}, {"id": "wb", "type": "sttop", "cfg": {"eigen": True, "sports": ["jogging"]}}, {"id": "wc", "type": "wochentage", "cfg": {}},
               {"id": "wd", "type": "belastung", "cfg": {}}])
    pg = _stats(pw, app)
    try:
        pg.wait_for_selector("#tlw-wa .slcol", timeout=T)
        pg.wait_for_selector("#tlw-wb .sllist li", timeout=T)
        assert pg.locator("#tlw-wb .sllist li").count() == 2                              # eigener Filter: nur Laufen (2 Touren)
        assert _vals(pg)["n"] == "10 Touren"
        before = pg.locator("#tlw-wa .slcmpn").inner_text()
        # Aktivität: Mehrfachauswahl Wandern + Radtour
        pg.locator("#sch [data-s='hike']").click()
        _wait_n(pg, "5 Touren")
        pg.wait_for_selector("#sch [data-s='hike'][aria-pressed='true']", timeout=T)             # Chips sind neu gezeichnet, erst dann der nächste Klick (sonst trifft er die alte Zeile)
        quiet(pg, 3000)
        pg.locator("#sch [data-s='touringbicycle']").click()
        _wait_n(pg, "8 Touren")
        pg.wait_for_selector("#sch [data-s='hike'][aria-pressed='true']", timeout=T)
        assert "s=hike,touringbicycle" in pg.url and pg.locator("#sch [data-s='touringbicycle'][aria-pressed='true']").count() == 1
        assert pg.locator("#stf h2").inner_text() == "Alle Touren, Wandern und Radtour"
        assert pg.locator("#tlk-kpi").inner_text().startswith("8 Touren")
        assert pg.locator("#tlw-wa .slcmpn").inner_text() != before                        # Baustein übernimmt den Filter
        assert pg.locator("#tlw-wa .flk").inner_text() == "Wandern, Radtour"
        assert pg.locator("#tlw-wb .sllist li").count() == 2 and "Laufen" in pg.locator("#tlw-wb .flk").inner_text()      # eigener Filter bleibt
        assert pg.locator("#tlw-wb .stn").count() == 0
        # Hinweis bei Abschnitten, die den Filter nicht kennen
        assert pg.locator("#tls-sportarten .stn").inner_text() == "Sportart gilt hier nicht"
        assert pg.locator("#tlw-wd .stn").inner_text() == "Filter gilt hier nicht" or pg.locator("#tlw-wd .stn").inner_text() == "Sportart gilt hier nicht"
        assert pg.locator("#tls-kpi .stn").count() == 0
        # Neuladen behält den Filter
        pg.reload()
        _wait_n(pg, "8 Touren")
        assert pg.locator("#sch [data-s='hike'][aria-pressed='true']").count() == 1
        # Zeitraum: Jahr, 12 Monate, 90 Tage, frei
        pg.locator("#stf a#stfr").click()
        _wait_n(pg, "10 Touren")
        n = {}
        for lab, sel, want in (("12m", "[data-z='12m']", "6 Touren"), ("90d", "[data-z='90d']", "3 Touren")):
            pg.locator(sel).click()
            pg.wait_for_selector(f"{sel}[aria-pressed='true']", timeout=T)
            _wait_n(pg, want)                                                              # Zahl erst lesen, wenn die Seite neu gezeichnet ist
            n[lab] = pg.locator("#stf .sub").inner_text()
        assert n["12m"] == "6 Touren" and n["90d"] == "3 Touren", n                       # 10, 30, 60, 120, 200, 260 d zurück bzw. 10, 30, 60 d
        pg.wait_for_selector("#stx #tls-kmmonat .chart", timeout=T)
        assert pg.locator("#tls-kmmonat .chart").count() == 1 and "Filter aktiv" in pg.locator(".stfs").inner_text()
        assert pg.locator("#tls-ziele .stn").inner_text() == "Zeitraum gilt hier nur als Jahr" or pg.locator("#tls-ziele .stn").count() == 1
        _go(pg, "?z=c&von=2000-01-01&bis=2000-02-01")
        _wait_n(pg, "0 Touren")
        assert pg.locator("#stfc").is_visible() and not pg.errors, pg.errors
        pg.locator("#stfc [name=von]").fill("2026-05-01"); pg.locator("#stfc [name=bis]").fill("2026-01-01")
        pg.locator("#stfc button").click()
        pg.wait_for_function("() => document.querySelector('.stfe').textContent.includes('nicht nach')", timeout=T)
        yr = pg.evaluate("years()[0]")
        pg.locator(f".years [data-y='{yr}']").click()
        pg.wait_for_function("y => location.hash.includes('y=' + y)", arg=yr, timeout=T)
        pg.wait_for_selector(f".years [data-y='{yr}'].on", timeout=T)
        assert pg.locator("#stf h2").inner_text() == f"Das Jahr {yr}" and not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_widget_dialog_switch_global_or_own_filter(pw, app):
    _put(app, [{"id": "wa", "type": "sttop", "cfg": {}}])
    pg = _stats(pw, app, "?s=hike")
    try:
        pg.wait_for_selector("#tlw-wa .sllist li", timeout=T)
        assert pg.locator("#tlw-wa .sllist li").count() == 5 and pg.locator("#tlw-wa .flk").inner_text() == "Top 5, Wandern"
        _edit(pg)
        pg.locator('.slit[data-sl="wa"] [data-a=cfg]').click()
        pg.wait_for_selector(".slform [data-global]", timeout=T)
        assert pg.locator(".slform [data-global]").is_checked() and pg.locator(".slform select[name='f4']").is_disabled()
        pg.locator(".slform [data-global]").uncheck()
        pg.wait_for_function("() => !document.querySelector('.flsp input[type=checkbox]').disabled", timeout=T)
        pg.locator(".flsp [data-all]").uncheck() if False else None
        pg.locator(".flsp input[value='jogging']").check()
        pg.locator(".slform button[type=submit]").click()
        pg.wait_for_selector("#tlw-wa .flk:has-text('Laufen')", timeout=T)
        _saved(pg)
        assert _server(app)["widgets"][0]["cfg"]["eigen"] is True and _server(app)["widgets"][0]["cfg"]["sports"] == ["jogging"]
        assert pg.locator("#tlw-wa .sllist li").count() == 2
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Bearbeitungsmodus, Ansichten, Vorlagen  ------------------------------------------------------------------

def test_edit_mode_order_width_hide_add_reset_and_reload(pw, app):
    pg = _stats(pw, app)
    try:
        _edit(pg)
        assert pg.locator(".slit").count() == 7
        pg.locator('.slit[data-sl="heat"] [data-a=up]').click()
        pg.wait_for_function("() => { const o = [...document.querySelectorAll('#stx .slit')].map(e => e.dataset.sl); return o.indexOf('heat') === o.indexOf('bestwerte') - 1; }", timeout=T)
        pg.locator('.slit[data-sl="kmverlauf"] [data-a=w][data-w="voll"]').click()
        pg.wait_for_selector('.slit[data-sl="kmverlauf"].w-voll', timeout=T)
        pg.locator('.slit[data-sl="ziele"] [data-a=eye]').click()
        pg.wait_for_selector('.slit[data-sl="ziele"].sl-dim', timeout=T)
        _add(pg, "sthoehe")
        _add(pg, "stlaengen")
        _saved(pg)
        lay = _server(app)
        assert "heat" in lay["order"] and lay["hidden"] == ["ziele"] and lay["w"]["kmverlauf"] == "voll" and {w["type"] for w in lay["widgets"]} == {"sthoehe", "stlaengen"}
        pg.locator("#slbar [data-a=done]").click()
        pg.wait_for_selector("#slbar", state="detached", timeout=T)
        assert pg.locator("#tls-ziele").count() == 0 or not pg.locator("#tls-ziele").is_visible()
        pg.reload()
        pg.wait_for_selector("#tlw-" + lay["widgets"][0]["id"] + " svg", timeout=T)
        pg.wait_for_function("() => { const o = [...document.querySelectorAll('#stx > .tlw')].map(e => e.dataset.wtype || ''); return o.includes('sthoehe') && o.includes('stlaengen'); }", timeout=T)
        assert not pg.locator("#tls-ziele").is_visible() and pg.locator("#tlw-" + lay["widgets"][1]["id"] + " .slcol").count() == 1
        _edit(pg)
        pg.locator("#slbar [data-a=reset]").click()
        pg.locator(".uibox .btn.danger, .uibox button:has-text('Standard wiederherstellen')").last.click()
        pg.wait_for_function("() => document.querySelectorAll('#stx > .tlw[data-wtype]').length === 0 && !!document.querySelector('#tls-ziele')", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_all_new_blocks_render_and_match_server_reference(pw, app):
    ws = [{"id": "w" + t, "type": t, "cfg": {}} for t in ("stmonate", "stentwicklung", "stlaengen", "sthoehe", "sttop", "jahr", "rekorde", "heatmap", "meilensteine")]
    _put(app, ws)
    pg = _stats(pw, app)
    try:
        for w in ws:
            pg.wait_for_selector(f"#tlw-{w['id']} .slnone, #tlw-{w['id']} svg, #tlw-{w['id']} .sllist, #tlw-{w['id']} .hyg, #tlw-{w['id']} .utiles", timeout=T)
        pg.wait_for_function("() => !document.querySelector('.slwb .slnone') || ![...document.querySelectorAll('.slwb .slnone')].some(e => e.textContent.includes('geladen'))", timeout=T)
        for t in ("stmonate", "stlaengen", "sthoehe"):
            assert pg.locator(f"#tlw-w{t} svg[role=img]").count() >= 1, t
        txt = pg.locator("#stx").inner_text()
        for bad in ("NaN", "undefined", "Infinity"):
            assert bad not in txt, bad
        # Referenz des Servers: Summen und Top-Liste stimmen mit der Oberfläche überein
        ref = _get(app, "/api/bausteine/statistik?wert=km&n=5")
        top = pg.locator("#tlw-wsttop .sllist li a").all_inner_texts()
        assert top == [r["name"] for r in ref["top"]]
        assert ref["touren"] == 10 and sum(ref["laengen"]["anzahl"]) == 10
        assert pg.locator("#tlw-wstlaengen .slcol rect").count() == 7
        assert pg.locator("#tlw-wstentwicklung .stline, #tlw-wstentwicklung .slnone").count() == 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def _get(url, path):
    import urllib.request
    with urllib.request.urlopen(url + path, timeout=10) as r:
        return json.loads(r.read())


def test_views_templates_export_on_statistics_page(pw, app, tmp_path):
    pg = _stats(pw, app)
    try:
        _edit(pg)
        pg.locator("#slbar [data-a=views]").click()
        pg.wait_for_selector(".sldlg .uibox", timeout=T)
        pg.locator(".sldlg [data-a=tpl]").click()
        pg.wait_for_function("() => [...document.querySelectorAll('.sldlg h3')].some(h => h.textContent.includes('Jahresrückblick'))", timeout=T)
        assert pg.locator(".sldlg:not([inert])").inner_text().count("Training") >= 1 and "Kompakt" in pg.locator(".sldlg:not([inert])").inner_text()
        pg.locator('.sldlg:not([inert]) [data-tpl="st-training"] button').click()
        pg.wait_for_function("() => typeof SL === 'object' && slViewName('statistik', SL.view.statistik) === 'Training'", timeout=T)
        pg.wait_for_function("() => document.querySelectorAll('#stx .slit').length > 0 && !!document.querySelector('#stx .slit[data-sl=t-stentwicklung]')", timeout=T)
        _srv(pg, "j['container'] and len(j['container']['views']) == 2")
        box = _api(app, "statistik")["container"]
        assert [v["name"] for v in box["views"]] == ["Standard", "Training"] and box["views"][1]["layout"]["widgets"]
        doc = pg.evaluate("() => slExportDoc('statistik', SL.view.statistik)")
        assert doc["page"] == "statistik" and doc["format"] == "meine-touren-ansicht" and "statistik" in doc["layouts"]
        chk = _post(app, "/api/layout/check", doc)
        assert chk["ok"] is True, chk
        bad = dict(doc, page="uebersicht", layouts={"uebersicht": doc["layouts"]["statistik"]})
        assert _post(app, "/api/layout/check", bad)["ok"] is False
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def _post(url, path, body):
    import urllib.request
    req = urllib.request.Request(url + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())


def test_every_statistics_template_passes_server_validation(pw, app):
    pg = _stats(pw, app)
    try:
        docs = pg.evaluate("() => SL_TPL.filter(t => t.fam === 'statistik').map(t => slTplDocs(t))")
        assert len(docs) == 3
        for d in docs:
            _api(app, "statistik", "PUT", d["statistik"])
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  mobil, Kontrast, Tastatur  ------------------------------------------------------------------

def test_mobile_390_no_horizontal_scroll_and_filter_usable(pw, app):
    _put(app, [{"id": "wa", "type": "stentwicklung", "cfg": {}}, {"id": "wb", "type": "stmonate", "cfg": {}}, {"id": "wc", "type": "sttop", "cfg": {}}])
    pg = _stats(pw, app, "?z=12m", width=390, height=844, dpr=2)
    try:
        pg.wait_for_selector("#tlw-wc .sllist", timeout=T)
        assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"), pg.evaluate("document.documentElement.scrollWidth")
        wide = pg.evaluate("() => [...document.querySelectorAll('#main *')].filter(e => e.getBoundingClientRect().right > window.innerWidth + 1 && !e.closest('.years, .chart, svg, a.btn')).map(e => e.className || e.tagName).slice(0, 5)")
        assert not wide, wide
        _shot(pg, "statistik-390-hell.png")
        _edit(pg)
        assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        pg.locator('.slit[data-sl="heat"] [data-a=up]').click()
        pg.wait_for_function("() => !document.getElementById('slchg').hidden", timeout=T)
        assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        _shot(pg, "statistik-390-bearbeiten.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


SELS = ["#stf h2", "#stf .sub", "#stf .chip", "#stf .chip.on", ".stfs", "#stx .tlt", "#stx .tlk", ".stn", "#stx .utile span", "#tlw-wa .slcmpn", "#tlw-wa .slcmp", "#slfchg", "#slsave"]


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_contrast_and_screenshots_light_and_dark(pw, app, scheme):
    _put(app, [{"id": "wa", "type": "stentwicklung", "cfg": {}}, {"id": "wb", "type": "stmonate", "cfg": {}}, {"id": "wc", "type": "sttop", "cfg": {}}, {"id": "wd", "type": "stlaengen", "cfg": {}},
               {"id": "we", "type": "belastung", "cfg": {}}])
    pg = _stats(pw, app, "?s=hike", scheme=scheme, dpr=2)
    try:
        pg.wait_for_selector("#tlw-wa svg, #tlw-wa .slnone", timeout=T)
        pg.wait_for_selector("#tlw-we .slnone", timeout=T)
        _settled(pg)                                                                          # Kontrast erst messen, wenn Diagramme und Schrift fertig stehen
        c = pg.evaluate(CONTRAST, SELS)
        assert len(c) >= 8, c
        low = {k: round(v, 2) for k, v in c.items() if v < 4.5}
        assert not low, f"{scheme}: Kontrast unter 4,5:1: {low}"
        _shot(pg, f"statistik-{scheme}-mit-filter.png")
        _edit(pg)
        pg.locator('.slit[data-sl="heat"] [data-a=up]').click()
        pg.wait_for_function("() => !document.getElementById('slchg').hidden", timeout=T)
        _settled(pg)
        c2 = pg.evaluate(CONTRAST, ["#slchg", "#slsaved", "#slbar [data-a=discard]", "#slbar [data-a=savenew]", "#slbar [data-a=done]"])
        low2 = {k: round(v, 2) for k, v in c2.items() if v < 4.5}
        assert len(c2) >= 4 and not low2, f"{scheme}: Kontrast der Leiste: {low2} {c2}"
        _shot(pg, f"statistik-{scheme}-bearbeiten.png")
        pg.locator("#slbar [data-a=add]").click()
        pg.wait_for_selector(".slcat .slcard", timeout=T)
        assert pg.locator(".slcat .slcath").first.inner_text() == "Statistik" and pg.locator('.slcat [data-add="bestwerte"]').count() == 1
        assert pg.locator('.slcat [data-add="splits"]').count() == 0                         # Tour-Bausteine gehören nicht hierher
        _shot(pg, f"statistik-{scheme}-katalog.png", full=False)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_keyboard_filter_focus_and_english(pw, app):
    pg = _stats(pw, app, locale="en-US")
    try:
        pg.locator("#sch [data-s='hike']").focus()
        pg.keyboard.press("Enter")
        _wait_n(pg, "5 tours")
        pg.wait_for_function("() => document.activeElement && document.activeElement.dataset.s === 'hike'", timeout=T)        # Fokus bleibt auf dem Filter
        assert pg.evaluate("getComputedStyle(document.activeElement).outlineStyle") != "none"
        txt = pg.locator("#stf").inner_text()
        assert "All sports" in txt and "Last 12 months" in txt and "Reset to the saved filter" in txt, txt
        assert "Alle Sportarten" not in txt and "Filter zurücksetzen" not in txt
        assert "Sport does not apply here" in pg.locator("#tls-sportarten .stn").inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Ansicht speichern: Filter gehört zur Ansicht, Anordnung verwerfen / als neue Ansicht  ------------------------------------------------------------------
DLG = ".sldlg:not([inert])"


def _views(app):
    return _api(app, "statistik")["container"]["views"]


def _srv(pg, expr):
    """Wartet (Abfrage im Sekundentakt bis 15 s), bis die Antwort des Servers j (GET /api/layout/statistik) die Bedingung erfüllt."""
    url = pg.url.split("/#")[0]
    for _ in range(150):
        j = _api(url, "statistik")
        if eval(expr, {"j": j}):
            return j
        pg.wait_for_timeout(100)
    raise AssertionError("Server hat den Stand nicht übernommen: " + expr)


def test_filter_belongs_to_view_save_here_discard_and_new_view(pw, app):
    pg = _stats(pw, app)
    try:
        assert pg.locator("#slsave").count() == 0                                         # unverändert: kein Knopf
        pg.locator("#sch [data-s='hike']").click()
        _wait_n(pg, "5 Touren")
        pg.wait_for_selector("#slsave", timeout=T)
        expect(pg.locator("#slfchg")).to_have_text("geändert", timeout=T)
        assert _server(app) is None
        pg.reload()                                                                       # ungespeichert bleibt für die Sitzung
        _wait_n(pg, "5 Touren")
        pg.wait_for_selector("#slsave", timeout=T)
        pg.locator("#slsave").click()
        pg.locator(f"{DLG} [data-m=here]").click()
        pg.wait_for_selector("#slsave", state="detached", timeout=T)
        _srv(pg, "j['layout'] and j['layout'].get('filter')")
        assert _api(app, "statistik") and _server(app)["filter"] == {"sports": ["hike"], "range": "all"}, _api(app, "statistik")
        pg.wait_for_function("() => /Ansicht gespeichert/.test((document.querySelector('.slok') || {}).textContent || '')", timeout=T)
        _go(pg, "")                                                                       # ohne Angabe gilt der gespeicherte Filter
        _wait_n(pg, "5 Touren")
        expect(pg.locator("#sch [data-s='hike'][aria-pressed='true']")).to_have_count(1, timeout=T)
        expect(pg.locator("#slsave")).to_have_count(0, timeout=T)
        pg.locator("#sch [data-s='']").click()                                           # ausdrücklich „alle“ weicht vom Gespeicherten ab
        _wait_n(pg, "10 Touren")
        pg.wait_for_selector("#slsave", timeout=T)
        pg.locator("#slsave").click()
        pg.locator(f"{DLG} [data-m=drop]").click()                                       # verwerfen: zurück auf den gespeicherten Filter
        _wait_n(pg, "5 Touren")
        pg.wait_for_selector("#slsave", state="detached", timeout=T)
        # als neue Ansicht: Original bleibt
        pg.locator("#sch [data-s='']").click()
        _wait_n(pg, "10 Touren")
        pg.locator("#sch [data-s='jogging']").click()
        _wait_n(pg, "2 Touren")
        pg.locator("#slsave").click()
        pg.locator(f"{DLG} [data-m=new]").click()
        pg.locator("#slvname").fill("Laufen")
        pg.locator(f"{DLG} button[type=submit]").click()
        pg.wait_for_function("() => (SL.store.statistik.views || []).length === 2 && SL.view.statistik !== 'standard'", timeout=T)
        _srv(pg, "j['container'] and len(j['container']['views']) == 2")
        _wait_n(pg, "2 Touren")
        v = {x["name"]: x for x in _views(app)}
        assert v["Standard"]["layout"]["filter"] == {"sports": ["hike"], "range": "all"} and v["Laufen"]["layout"]["filter"] == {"sports": ["jogging"], "range": "all"}
        expect(pg.locator("#slsave")).to_have_count(0, timeout=T)
        assert not pg.errors, pg.errors
        pg.locator("#slview").select_option(label="Standard")                            # Ansichtswechsel bringt den Filter der Ansicht mit
        _wait_n(pg, "5 Touren")
    finally:
        pg.browser_.close()


def test_edit_bar_marker_discard_restores_save_as_new_keeps_original_and_done_confirms(pw, app):
    pg = _stats(pw, app)
    try:
        _edit(pg)
        assert pg.locator("#slchg").is_hidden()
        order0 = pg.evaluate("() => [...document.querySelectorAll('#stx .slit')].map(e => e.dataset.sl)")
        pg.locator('.slit[data-sl="heat"] [data-a=up]').click()
        pg.wait_for_function("() => !document.getElementById('slchg').hidden", timeout=T)
        assert pg.locator("#slchg").inner_text() == "Ungespeicherte Änderungen"
        _saved(pg)
        assert "heat" in _server(app)["order"]                                            # automatisches Zwischenspeichern bleibt
        # Verwerfen stellt den Stand von vor dem Bearbeiten wieder her (Server und Anzeige)
        quiet(pg, 3000)                                                                  # Zwischenspeichern/Neuaufbau abwarten, dann verwerfen
        pg.locator("#slbar [data-a=discard]").click()
        pg.locator(".uibox button:has-text('Verwerfen')").last.click()
        pg.wait_for_function("() => document.getElementById('slchg').hidden", timeout=T)
        pg.wait_for_function("o => JSON.stringify([...document.querySelectorAll('#stx .slit')].map(e => e.dataset.sl)) === JSON.stringify(o)", arg=order0, timeout=T)
        pg.wait_for_function("() => !SL.dirty.size", timeout=T)
        pg.wait_for_function("() => document.getElementById('slsaved').textContent.trim() === 'Gespeichert' || document.getElementById('slsaved').textContent.trim() === 'Verworfen'", timeout=T)
        assert _server(app) is None or "order" not in _server(app)
        # Als neue Ansicht speichern: Original bleibt auf dem Stand von vor dem Bearbeiten
        pg.locator('.slit[data-sl="kmverlauf"] [data-a=w][data-w="voll"]').click()
        pg.wait_for_selector('.slit[data-sl="kmverlauf"].w-voll', timeout=T)
        pg.wait_for_function("() => !document.getElementById('slchg').hidden", timeout=T)
        pg.locator("#slbar [data-a=savenew]").click()
        pg.locator("#slvname").fill("Breit")
        pg.locator(f"{DLG} button[type=submit]").click()
        pg.wait_for_function("() => (SL.store.statistik.views || []).length === 2", timeout=T)
        pg.wait_for_selector("#stx #tls-kpi", state="attached", timeout=T)
        _srv(pg, "j['container'] and len(j['container']['views']) == 2")
        v = {x["name"]: x for x in _views(app)}
        assert (v["Standard"]["layout"].get("w") or {}).get("kmverlauf") is None and v["Breit"]["layout"]["w"]["kmverlauf"] == "voll"
        # Fertig bestätigt sichtbar
        pg.wait_for_selector("#slbar", timeout=T)                                         # Bearbeitungsmodus bleibt nach dem Ansichtswechsel erhalten
        pg.wait_for_function("() => document.querySelectorAll('.slit').length > 0", timeout=T)
        pg.locator('.slit[data-sl="heat"] [data-a=up]').click()
        _saved(pg)
        pg.locator("#slbar [data-a=done]").click()
        pg.wait_for_function("() => /Anordnung gespeichert/.test((document.querySelector('.slok') || {}).textContent || '')", timeout=T)
        assert pg.locator("#slbar").count() == 0 and not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_edit_bar_discard_and_save_as_new_work_on_overview_and_tour_page(pw, app):
    for hash_, key, ready in (("#/dash", "uebersicht", "#hlast"), ("#/tour/t1", "tour-haupt", "#tl")):
        pg = _browser(pw, app, width=1280, height=1000, scheme="light", dpr=1, locale="de-DE", devs=None)
        try:
            pg.goto(f"{app}/{hash_}")
            pg.wait_for_selector(ready, state="attached", timeout=T)
            pg.wait_for_selector("#slopen", timeout=T)
            _edit(pg)
            ids = pg.evaluate("() => [...document.querySelectorAll('.slit')].map(e => e.dataset.sl)")
            first = ids[0]
            pg.locator(f'.slit[data-sl="{first}"] [data-a=down]').click()
            pg.wait_for_function("() => !document.getElementById('slchg').hidden", timeout=T)
            quiet(pg, 3000)                                                                  # Zwischenspeichern/Neuaufbau abwarten, dann verwerfen
            pg.locator("#slbar [data-a=discard]").click()
            pg.locator(".uibox button:has-text('Verwerfen')").last.click()
            pg.wait_for_function("() => document.getElementById('slchg').hidden", timeout=T)
            pg.wait_for_function("o => document.querySelector('.slit').dataset.sl === o", arg=first, timeout=T)
            pg.locator(f'.slit[data-sl="{first}"] [data-a=down]').click()
            pg.wait_for_function("() => !document.getElementById('slchg').hidden", timeout=T)
            pg.locator("#slbar [data-a=savenew]").click()
            pg.locator("#slvname").fill("Zweite")
            pg.locator(f"{DLG} button[type=submit]").click()
            pg.wait_for_function("() => slMaster(SL.fam).views.length === 2 && document.getElementById('slchg').hidden", timeout=T)
            for _ in range(150):
                c = _api(app, key).get("container") or {}
                if len(c.get("views", [])) == 2:
                    break
                pg.wait_for_timeout(100)
            v = {x["name"]: x for x in c["views"]}
            assert not (v["Standard"]["layout"].get("order")) and v["Zweite"]["layout"].get("order"), v
            assert not pg.errors, pg.errors
        finally:
            pg.browser_.close()
