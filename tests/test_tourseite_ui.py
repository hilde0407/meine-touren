"""3.15.0 – Neue Tourseite (Browser, Chromium): Gruppen und Reihenfolge, Abschnitts-Leiste mit Sprung-Chips, „Alles auf-/zuklappen“, gemerkter Zustand, Blöcke je Gerät,
Tour ohne Uhr-Daten (keine leeren Abschnitte), 390 px, Kontrast hell/dunkel, Übersetzung, Betrachter. Alle Daten konstruiert; Uhr-Training, Puls, Wetter und Wegpunkte
werden im Browser nachgestellt (page.route), weil eine Tour in der Datenbank genau ein Gerät hat (tour_device/tour_source/tour_zsrc: je Tour eine Zeile).
Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt (Desktop/390 px, hell/dunkel, ein und zwei Geräte, Standard und alles aufgeklappt)."""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

SEED = r"""
import sys, os, time, math; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db, config, routes, metrics
db.init()
config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
now = int(time.time())
def loop(lat0=48.0, lng0=11.0, r=0.01, n=120):
    return [(lat0 + r * math.sin(2 * math.pi * i / (n - 1)), lng0 + r * (1 - math.cos(2 * math.pi * i / (n - 1))), 500 + 60 * math.sin(i / 14), i * 40000) for i in range(n)]
def tour(tid, ts, name, dist, dur, up, **kw):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,?,?,'t','komoot')", (tid, name, "hike", ts, ts + (dur or 0), dist, dur, up, up))
    routes.store(tid, loop(**kw))
for i, (days, name, dist, dur, up) in enumerate([(300, "Gipfelrunde im Frühjahr", 6000, 8100, 330), (200, "Gipfelrunde", 6100, 7800, 310), (100, "Gipfelrunde im Herbst", 6000, 7200, 330),
                                                  (40, "Gipfelrunde heute", 6000, 6300, 325), (12, "Gipfelrunde", 6000, 7000, 325)]):
    tour("r%%d" %% i, now - days * 86400, name, dist, dur, up)
tour("s0", now - 3 * 86400, "Solo ohne Uhr", 5000, 6000, 200, lat0=49.5, lng0=9.0)
routes.store("s0", [(a, b, c, None) for a, b, c, _ in loop(lat0=49.5, lng0=9.0)])       # Strecke ohne Zeitstempel: auch keine aus GPS berechneten Messwerte
db.execute("INSERT INTO devices(id,name,kind,model,active) VALUES(1,'Amazfit Balance','zepp','Balance',1)")
db.execute("INSERT INTO devices(id,name,kind,model,active) VALUES(2,'Garmin Forerunner 255','garmin','Forerunner 255',1)")
db.execute("INSERT OR REPLACE INTO tour_device(tour_id,device_id) VALUES('r3',1)")
n = 60
metrics.store("r3", {"v": 1, "src": "zepp", "device": "Amazfit Balance", "t0": now - 40 * 86400, "t": [i * 100 for i in range(n)],
                     "series": {"speed": [3.5 + 0.5 * math.sin(i / 7) for i in range(n)], "cad": [110 + 10 * math.sin(i / 5) for i in range(n)]}, "sum": {"kcal": 512}})
"""

LAUNCH = r"""
import sys, os; sys.path.insert(0, %(root)r)
import uvicorn
from app.main import app
uvicorn.run(app, host="127.0.0.1", port=%(port)d, log_level="warning")
"""

DEV1 = {"id": 1, "name": "Amazfit Balance", "kind": "zepp", "model": "Balance", "active": True}
DEV2 = {"id": 2, "name": "Garmin Forerunner 255", "kind": "garmin", "model": "Forerunner 255", "active": True}


def uhr_json(dev):
    return {"status": "ok", "device": dev, "geladen": 1750000000, "werte": {"te": {"wert": 3.2}, "last": {"wert": 118}, "kcal": {"wert": 512}, "puls_avg": {"wert": 128}},
            "pulszonen": [], "splits": [], "ermuedung": None, "wetter": {"temp_c": 14, "feuchte_pct": 60}, "hinweise": []}


HR_JSON = {"n": 60, "pts": [[i * 100, 110 + int(20 * (1 + __import__("math").sin(i / 6))), i] for i in range(60)], "avg": 128, "max": 151, "min": 110, "hrmax": 185, "zones": [600, 3000, 2000, 400, 0], "total": 60}
WX_JSON = {"code": 2, "text": "Leicht bewölkt", "tmin": 8, "tmax": 15, "precip": 0.4, "wind": 18, "snow_depth": None, "snow72": 0, "snowfall": 0}
WPS_JSON = [{"id": 1, "lat": 48.0, "lng": 11.0, "ts": 1750000100, "note": "Rast am Bach"}, {"id": 2, "lat": 48.005, "lng": 11.01, "ts": 1750003100, "note": "Gipfel"}]


def _wait(url):
    for _ in range(150):
        try:
            urllib.request.urlopen(url + "/api/version", timeout=1)
            return
        except Exception:
            time.sleep(0.2)


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    tmp = tmp_path_factory.mktemp("ts")
    data = tmp / "data"
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data)}], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
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


@pytest.fixture(scope="module")
def pw():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


def _page(pw, url, tour="r3", devs="one", width=1280, height=1000, scheme="light", dpr=1, locale="de-DE", wait="#tls-notes", ctx_init=None):
    """devs: 'one' (Uhr-Training vom selben Gerät), 'two' (Uhr-Training von einem zweiten Gerät), None (nichts nachgestellt)."""
    b = pw.chromium.launch()
    ctx = b.new_context(locale=locale, viewport={"width": width, "height": height}, color_scheme=scheme, device_scale_factor=dpr)
    if ctx_init:
        ctx.add_init_script(ctx_init)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(url) else r.continue_())
    if devs:
        pg.route(f"**/api/tours/{tour}/uhr-training", lambda r: r.fulfill(json=uhr_json(DEV1 if devs == "one" else DEV2)))
        pg.route(f"**/api/tours/{tour}/hr", lambda r: r.fulfill(json=HR_JSON))
        pg.route(f"**/api/tours/{tour}/weather", lambda r: r.fulfill(json=WX_JSON))
        pg.route(f"**/api/tours/{tour}/wps", lambda r: r.fulfill(json=WPS_JSON))
    pg.goto(f"{url}/#/tour/{tour}")
    pg.wait_for_selector(wait, timeout=15000)
    pg.wait_for_timeout(1800)
    pg.browser_ = b
    return pg


def _shot(pg, name, full=True):
    d = os.environ.get("TS_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        pg.evaluate("window.scrollTo(0, 0)")
        pg.screenshot(path=str(Path(d) / name), full_page=full)


FULL_ORDER = ["map", "prof", "wp", "met", "puls", "uhr", "wx", "ana", "steig", "aehn", "cmp", "photos", "notes"]
SECS = "() => [...document.querySelectorAll('#tl details.tls')].map(d => d.dataset.tls)"
OPEN = "() => Object.fromEntries([...document.querySelectorAll('#tl details.tls')].map(d => [d.dataset.tls, d.open]))"


def test_groups_and_order_two_devices(pw, app):
    pg = _page(pw, app, devs="two")
    try:
        assert pg.evaluate(SECS) == FULL_ORDER
        assert pg.locator("#tl .tlgh").all_inner_texts() == ["Streckenverlauf", "Aufzeichnung", "Auswertung dieser Tour", "Fotos & Notizen"]
        blocks = pg.locator("#tlrec .tldev")
        assert blocks.count() == 2 and pg.locator("#tlrec .tldev.multi").count() == 2
        assert "Amazfit Balance" in blocks.nth(0).locator(".tldh, #devrow").first.inner_text() and "Garmin Forerunner 255" in blocks.nth(1).locator(".tldh").inner_text()
        assert pg.locator("#tlrec .tldev").nth(0).locator("#metcard, #pulscard").count() == 2 and blocks.nth(1).locator("#uhrcard").count() == 1
        assert pg.locator("#devedit").count() == 1                                   # Gerät ändern bleibt erreichbar
        assert pg.locator("#tlrec .tldev").nth(0).locator("#devrow, .tldh").count() == 1 and pg.locator("#tlrec .tldh, #tlrec #devrow").count() == 2     # je Block genau ein Gerätekopf
        # Abschnittskopf einheitlich: Symbol, Titel (h3), Kurzaussage; alle Daten weiter vorhanden
        for d in pg.locator("#tl details.tls").all():
            assert d.locator("> summary svg.tli").count() == 1 and d.locator("> summary h3.tlt").count() == 1 and d.locator("> summary").get_attribute("aria-controls")
        assert pg.locator("#tls-uhr .tlk").inner_text().startswith("Trainingseffekt 3,2") and "Ø 128" in pg.locator("#tls-puls .tlk").inner_text()
        assert "2 Wegpunkte" in pg.locator("#tls-wp .tlk").inner_text() and "Bewegungszeit" in pg.locator("#tls-ana .tlk").inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_one_device_has_no_block_headings_and_default_state(pw, app):
    pg = _page(pw, app, devs="one")
    try:
        assert pg.evaluate(SECS) == ["map", "prof", "wp", "met", "uhr", "puls", "wx", "ana", "steig", "aehn", "cmp", "photos", "notes"]
        assert pg.locator("#tlrec .tldev").count() == 1 and pg.locator("#tlrec .tldh").count() == 0 and pg.locator("#tlrec .tldev.multi").count() == 0
        assert pg.locator("#tlgb-rec > #devrow").count() == 1                         # „Aufgezeichnet mit“ steht einmal oben
        o = pg.evaluate(OPEN)
        assert all(o[k] for k in ("map", "prof", "met", "photos", "notes")) and not any(o[k] for k in ("ana", "steig", "aehn", "wx", "cmp"))
        assert pg.locator("#tls-ana .tlsb").is_hidden() and pg.locator("#tls-ana .tlk").is_visible()      # Kurzaussage auch zugeklappt sichtbar
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_nav_chips_jump_open_and_focus(pw, app):
    pg = _page(pw, app, devs="two")
    try:
        names = pg.locator("#tlnav .tlchip").all_inner_texts()
        assert names == ["Karte", "Höhe", "Wegpunkte", "Gerät & Messwerte", "Wetter", "Analyse", "Vergleich", "Fotos", "Notizen"]
        assert pg.locator("#tlnav .tlchip").first.evaluate("e => e.tagName") == "BUTTON" and pg.locator("#tlall").inner_text() == "Alles aufklappen"
        pg.locator("#tlnav .tlchip", has_text="Vergleich").click()
        pg.wait_for_function("() => document.querySelector('#tls-aehn').open && document.querySelector('#tls-cmp').open")
        pg.wait_for_timeout(1200)
        top = pg.evaluate("document.querySelector('#tls-aehn').getBoundingClientRect().top")
        assert 0 < top < 400, top
        assert pg.locator("#tls-aehn > summary").get_attribute("aria-expanded") == "true"
        assert pg.evaluate("document.activeElement === document.querySelector('#tls-aehn > summary')")
        assert pg.evaluate("localStorage.getItem('mt_trf_aehn')") == "1"
        pg.locator("#tlnav .tlchip", has_text="Wetter").click()
        pg.wait_for_function("() => document.querySelector('#tls-wx').open")
        assert pg.evaluate("location.hash") == "#/tour/r3"                           # kein Hash-Sprung, die Routing-Adresse bleibt
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_jump_respects_reduced_motion(pw, app):
    pg = _page(pw, app, devs="one")
    try:
        pg.emulate_media(reduced_motion="reduce")
        pg.evaluate("() => { window.__b = []; window.__o = Element.prototype.scrollIntoView; Element.prototype.scrollIntoView = function (...a) { if (a[0] && a[0].behavior) window.__b.push(a[0].behavior); return window.__o.apply(this, a); }; }")
        pg.locator("#tlnav .tlchip", has_text="Fotos").click()
        assert pg.evaluate("window.__b") == ["auto"]
        pg.emulate_media(reduced_motion="no-preference")
        pg.locator("#tlnav .tlchip", has_text="Karte").click()
        assert pg.evaluate("window.__b") == ["auto", "smooth"]
    finally:
        pg.browser_.close()


def test_nav_is_sticky_on_desktop_under_the_header(pw, app):
    pg = _page(pw, app, devs="one")
    try:
        assert pg.locator("#tlnav").evaluate("e => getComputedStyle(e).position") == "sticky"
        pg.evaluate("window.scrollTo(0, 2500)")
        pg.wait_for_timeout(400)
        n = pg.locator("#tlnav").bounding_box()
        h = pg.locator("header.top").bounding_box()
        assert abs(n["y"] - (h["y"] + h["height"])) <= 2 and n["height"] > 20, (n, h)
    finally:
        pg.browser_.close()


def test_expand_all_collapse_all_and_state_is_remembered(pw, app):
    pg = _page(pw, app, devs="one")
    try:
        pg.locator("#tlall").click()
        pg.wait_for_function("() => document.querySelector('#tlall').textContent === 'Alles zuklappen'")
        assert all(pg.evaluate(OPEN).values())
        assert pg.evaluate("document.querySelectorAll('#tl details.tls[open]').length") == len(FULL_ORDER)
        pg.reload(); pg.wait_for_selector("#tls-notes"); pg.wait_for_timeout(1500)
        assert all(pg.evaluate(OPEN).values())                                          # Zustand bleibt nach dem Neuladen
        pg.locator("#tlall").click()
        pg.wait_for_function("() => document.querySelector('#tlall').textContent === 'Alles aufklappen'")
        assert not any(pg.evaluate(OPEN).values())
        pg.locator("#tls-ana > summary").click()                                       # einzeln wieder öffnen; Leiste meldet „nicht alles zu“ erst bei allen offen
        pg.wait_for_function("() => localStorage.getItem('mt_trf_tl_ana') === '1'")
        pg.reload(); pg.wait_for_selector("#tls-notes"); pg.wait_for_timeout(1500)
        o = pg.evaluate(OPEN)
        assert o["ana"] and not o["map"] and not o["met"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_collapsed_map_is_resized_when_opened(pw, app):
    pg = _page(pw, app, devs="one", ctx_init="try { localStorage.setItem('mt_trf_tl_map', '0') } catch (e) {}")
    try:
        assert not pg.evaluate(OPEN)["map"]
        pg.locator("#tls-map > summary").click()
        pg.wait_for_function("() => document.querySelector('#tm').clientWidth > 300")
        pg.wait_for_timeout(500)
        assert pg.locator("#tm .leaflet-tile-loaded, #tm path.leaflet-interactive").count() >= 1
        assert pg.evaluate("(() => { const m = document.querySelector('#tm path.leaflet-interactive').getBoundingClientRect(), c = document.querySelector('#tm').getBoundingClientRect(); return m.left >= c.left && m.right <= c.right; })()")
    finally:
        pg.browser_.close()


def test_tour_without_watch_data_has_no_empty_sections_or_chips(pw, app):
    pg = _page(pw, app, tour="s0", devs=None, wait="#tls-photos")
    try:
        ids = pg.evaluate(SECS)
        assert ids[:2] == ["map", "prof"] and ids[-2:] == ["photos", "notes"]
        for gone in ("met", "uhr", "puls", "wx", "wp", "aehn", "cmp"):
            assert gone not in ids, gone
        assert pg.locator("#metcard, #uhrcard, #pulscard, #aehncard, #wpcard").count() == 0
        chips = pg.locator("#tlnav .tlchip").all_inner_texts()
        assert "Gerät & Messwerte" not in chips and "Vergleich" not in chips and "Wetter" not in chips and "Karte" in chips and "Fotos" in chips
        # keine Gruppe ohne sichtbaren Abschnitt, kein Abschnitt ohne Inhalt
        bad = pg.evaluate("[...document.querySelectorAll('#tl .tlg')].filter(g => !g.hidden && ![...g.querySelectorAll('details.tls')].some(d => !d.hidden)).map(g => g.id)")
        assert not bad, bad
        assert pg.locator("#tlg-rec").is_hidden()
        assert pg.evaluate("[...document.querySelectorAll('#tl details.tls:not([hidden])')].every(d => d.querySelector('.tlsb').textContent.trim() !== '' || d.querySelector('.tlsb *'))")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_mobile_390_no_horizontal_scroll(pw, app, scheme):
    pg = _page(pw, app, devs="two", width=390, height=844, scheme=scheme, dpr=2)
    try:
        pg.evaluate("tlSetAll(true)")
        pg.wait_for_timeout(1000)
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
        over = pg.evaluate("[...document.querySelectorAll('#tl details.tls, #tl .tlsb, #tlnav, #tl .tldev')].filter(e => e.getBoundingClientRect().right > innerWidth + 1).map(e => e.id || e.className)")
        assert not over, over
        assert pg.locator("#tlnav .tlchips").evaluate("e => e.scrollWidth > e.clientWidth && getComputedStyle(e).overflowX === 'auto'")      # Chips scrollen waagerecht
        assert pg.locator("#tlnav").evaluate("e => getComputedStyle(e).position") == "relative"
        _shot(pg, f"tour-390-{scheme}-zwei-geraete-aufgeklappt.png")
        pg.evaluate("tlSetAll(false)"); pg.wait_for_timeout(500)
        _shot(pg, f"tour-390-{scheme}-zwei-geraete-zu.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


CONTRAST = """() => {
  const parse = c => { const m = c.match(/[\\d.]+/g).map(Number); return {r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1}; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const bg = el => { for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c.a > 0.5) return c; } return {r: 255, g: 255, b: 255, a: 1}; };
  const out = {};
  for (const sel of [".tlgh", ".tlchip", ".tlall", "#tls-map .tlt", "#tls-map .tlk", "#tls-uhr .tlk", "#tls-ana .tlk", ".tldh b", ".tldh small", ".tlbar .sub"]) {
    const el = document.querySelector("#tl " + sel) || document.querySelector("#tlnav " + sel) || document.querySelector(sel);
    if (!el) continue;
    const f = parse(getComputedStyle(el).color), b = bg(el), l1 = lum(f), l2 = lum(b);
    out[sel] = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }
  const ic = document.querySelector("#tl .tli"), card = document.querySelector("#tls-map");
  if (ic) { const f = parse(getComputedStyle(ic).stroke), b = bg(card), l1 = lum(f), l2 = lum(b); out["icon"] = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05); }
  return out;
}"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_contrast_in_light_and_dark(pw, app, scheme):
    pg = _page(pw, app, devs="two", scheme=scheme, dpr=2)
    try:
        c = pg.evaluate(CONTRAST)
        assert len(c) >= 10, c
        low = {k: round(v, 2) for k, v in c.items() if v < 4.5}
        assert not low, f"{scheme}: Kontrast unter 4,5:1: {low}"
        _shot(pg, f"tour-desktop-{scheme}-zwei-geraete-standard.png")
        pg.evaluate("tlSetAll(true)"); pg.wait_for_timeout(1200)
        _shot(pg, f"tour-desktop-{scheme}-zwei-geraete-aufgeklappt.png")
        pg.close()
        pg = _page(pw, app, devs="one", scheme=scheme, dpr=2)
        _shot(pg, f"tour-desktop-{scheme}-ein-geraet-standard.png")
        pg.evaluate("tlSetAll(true)"); pg.wait_for_timeout(1200)
        _shot(pg, f"tour-desktop-{scheme}-ein-geraet-aufgeklappt.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_keyboard_focus_visible_and_english(pw, app):
    pg = _page(pw, app, devs="two", locale="en-US")
    try:
        t = pg.locator("#tl").inner_text() + pg.locator("#tlnav").inner_text()
        for w in ("Route", "Recording", "Evaluation of this tour", "Photos & notes", "Weather", "Waypoints", "Expand all", "Device & readings", "Notes & gear"):
            assert w in t, w
        for g in ("Streckenverlauf", "Aufzeichnung", "Wegpunkte", "Alles aufklappen", "Notizen"):
            assert g not in t, g
        pg.locator("#tls-ana > summary").focus()
        assert pg.locator("#tls-ana > summary").evaluate("e => getComputedStyle(e).outlineStyle !== 'none' && parseFloat(getComputedStyle(e).outlineWidth) >= 2")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_viewer_sees_all_sections_without_edit_buttons(pw, app):
    pg = _page(pw, app, devs="two", ctx_init="window.__viewer = 1")
    try:
        pg.evaluate("ME.user = {role: 'viewer', uid: 9, name: 'Oma'}; document.documentElement.classList.add('viewer')")
        pg.evaluate("route()")
        pg.wait_for_selector("#tls-notes"); pg.wait_for_timeout(1800)
        assert pg.evaluate(SECS) == FULL_ORDER
        assert pg.locator("#devedit").count() == 0 and pg.locator("#utneu").count() == 0
        assert pg.locator("#tlnav .tlchip").count() == 9
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
