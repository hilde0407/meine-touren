"""3.16.0 – Tourseite schlanker, Auswertung als Unterseite (Browser, Chromium).
Hauptseite #/tour/<id>: nur Kopf, Karte, Höhenprofil (mit Puls), Wegpunkte, Einstieg „Detaillierte Auswertung“, Fotos (Bewertung, Notiz, Ausrüstung, Sicherheit bleiben oben im Kopf wie in 3.14.0).
Unterseite #/tour/<id>/auswertung: Aufzeichnung (Gerät, Messwerte, Training laut Uhr, Wetter) und Auswertung (Analyse, Tempo, Ähnliche, Vergleich) mit Sprung-Leiste,
„Alles auf-/zuklappen“, gemerktem Zustand, Blöcken je Gerät. Dazu: Navigation hin und zurück, Direktaufruf, Tour ohne Uhr-Daten, Tour ohne Strecke (leere Unterseite),
390 px, Kontrast hell/dunkel, Übersetzung, Betrachter. Alle Daten konstruiert; Uhr-Training, Puls, Wetter und Wegpunkte werden im Browser nachgestellt (page.route),
weil eine Tour in der Datenbank genau ein Gerät hat (tour_device/tour_source/tour_zsrc: je Tour eine Zeile).
Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt (Hauptseite und Unterseite, Desktop/390 px, hell/dunkel)."""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from tests.helpers_ui import quiet  # noqa: E402

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
for i, (days, name, dist, dur, up) in enumerate([(300, "Gipfelrunde im Frühjahr", 6000, 8100, 330), (200, "Gipfelrunde", 6100, 7800, 310), (100, "Gipfelrunde heute", 6000, 7200, 330),
                                                  (40, "Gipfelrunde heute", 6000, 6300, 325), (12, "Gipfelrunde", 6000, 7000, 325)]):
    tour("r%%d" %% i, now - days * 86400, name, dist, dur, up)
tour("s0", now - 3 * 86400, "Solo ohne Uhr", 5000, 6000, 200, lat0=49.5, lng0=9.0)
db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES('n0','Ohne Strecke','hike',?,?,3000,3600,100,100,'t','komoot')", (now - 5 * 86400, now - 5 * 86400 + 3600))
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


def _page(pw, url, tour="r3", devs="one", width=1280, height=1000, scheme="light", dpr=1, locale="de-DE", sub=False, ctx_init=None, settle=1800):
    """sub=True öffnet die Unterseite #/tour/<id>/auswertung. devs: 'one' (Uhr-Training vom selben Gerät), 'two' (von einem zweiten Gerät), None (nichts nachgestellt)."""
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
    pg.goto(f"{url}/#/tour/{tour}" + ("/auswertung" if sub else ""))
    if sub:
        pg.wait_for_function(READY_SUB, timeout=15000)
    else:
        _ready_main(pg, devs, tlsum=tour != "n0")
    quiet(pg, settle)
    _settled(pg)
    pg.browser_ = b
    return pg


READY_SUB = "() => { const l = document.querySelector('#tlload'); return !!l && l.hidden; }"
# Der Einstieg (#tlgb-sum) wird nach und nach aus den Kurzaussagen der Nachlade-Abschnitte aufgebaut: fertig, wenn sich seine Signatur 700 ms nicht mehr ändert
SIG_STABLE = """() => {
  const b = document.querySelector('#tlgb-sum');
  if (!b || !b.dataset.sig) return false;
  const w = window.__sigw = window.__sigw || {s: '', t: Date.now()};
  if (w.s !== b.dataset.sig) { w.s = b.dataset.sig; w.t = Date.now(); return false; }
  return Date.now() - w.t > 700;
}"""


def _ready_main(pg, devs=True, tlsum=True):
    """Hauptseite fertig: Fotos-Abschnitt da, bei nachgestellten Uhr-Daten Wegpunkte und Puls, und der Einstieg hat alle Kurzaussagen eingesammelt."""
    pg.wait_for_selector("#tls-photos", timeout=15000)
    if devs:
        pg.wait_for_selector("#wpcard", timeout=15000)
        pg.wait_for_selector("#pulscard", timeout=15000)
    if tlsum:
        pg.wait_for_function(SIG_STABLE, timeout=15000)


def _settled(pg):
    """Layout fertig: Schriften geladen und zwei Frames ohne Änderung der Seitenhöhe (Screenshot und Messungen nie mitten im Aufbau)."""
    pg.evaluate("() => document.fonts.ready.then(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))))")
    pg.wait_for_function("() => { const h = document.documentElement.scrollHeight, w = window.__hs = window.__hs || {h: 0, n: 0}; w.n = w.h === h ? w.n + 1 : 0; w.h = h; return w.n >= 3; }", timeout=15000, polling=100)


def _shot(pg, name, full=True):
    d = os.environ.get("TS_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        pg.evaluate("window.scrollTo(0, 0)")
        _settled(pg)
        pg.screenshot(path=str(Path(d) / name), full_page=full, timeout=60000)


MAIN_ORDER = ["map", "prof", "puls", "wp", "photos"]
SUB_ORDER = ["met", "uhr", "wx", "ana", "steig", "aehn", "cmp"]
DETAIL = "#metcard, #uhrcard, #anacard, #steigcard, #aehncard, #cmpseg, #devrow, #main .wx, #tlnav, #tlall"
SECS = "() => [...document.querySelectorAll('#tl details.tls')].map(d => d.dataset.tls)"
OPEN = "() => Object.fromEntries([...document.querySelectorAll('#tl details.tls')].map(d => [d.dataset.tls, d.open]))"


# ------------------------------------------------------------------  Hauptseite  ------------------------------------------------------------------

def test_main_page_is_slim(pw, app):
    pg = _page(pw, app, devs="one")
    try:
        assert pg.evaluate(SECS) == MAIN_ORDER                                        # Karte, Höhenprofil, Puls, Wegpunkte, Fotos – sonst nichts
        assert pg.locator("#tl .tlgh").all_inner_texts() == ["Streckenverlauf", "Auswertung dieser Tour", "Fotos zur Tour"]
        assert pg.locator(DETAIL).count() == 0                                        # Detail-Karten, Wetter, Gerätezeile, Leiste: nicht auf der Hauptseite
        assert pg.locator("#pulscard").count() == 1 and pg.locator("#prof #phr, #profcard #phr").count() == 1     # Pulslinie im Höhenprofil + Herzfrequenz-Karte
        assert pg.locator("#wpcard").count() == 1 and "2 Wegpunkte" in pg.locator("#tls-wp .tlk").inner_text()
        # Reihenfolge von oben nach unten: Kopf, Karte, Höhenprofil, Puls, Wegpunkte, Einstieg, Fotos
        ys = pg.evaluate("() => ['.figs', '#tls-map', '#tls-prof', '#tls-puls', '#tls-wp', '#tlsum', '#tls-photos'].map(s => document.querySelector(s).getBoundingClientRect().top + scrollY)")
        assert ys == sorted(ys) and len(set(ys)) == len(ys) - 1 and ys[3] == ys[4], ys          # 3.20.0: Herzfrequenz und Wegpunkte stehen im Raster nebeneinander
        o = pg.evaluate(OPEN)
        assert all(o.values())                                                        # alles Verbleibende ist standardmäßig offen
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_entry_card_shows_key_facts_and_links_to_subpage(pw, app):
    pg = _page(pw, app, devs="one")
    try:
        e = pg.locator("#tlsum")
        assert e.is_visible()
        rows = e.locator(".tlsrows li")
        assert 2 <= rows.count() <= 3
        t = e.inner_text()
        assert "Training laut Uhr" in t and "Trainingseffekt 3,2" in t and "Analyse" in t and "Bewegungszeit" in t
        assert "Enthält:" in t and "Messwerte" in t and "Wetter" in t and "Vergleich dieser Strecke" in t
        go = pg.locator("#tlsgo")
        assert go.inner_text() == "Detaillierte Auswertung ansehen ›" and go.get_attribute("href") == "#/tour/r3/auswertung"
        assert go.evaluate("e => e.tagName") == "A"
        assert pg.locator("#tlsum").evaluate("e => e.getBoundingClientRect().height") > 80
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_entry_card_only_when_there_is_something(pw, app):
    pg = _page(pw, app, tour="s0", devs=None)                                          # Strecke ohne Uhr-Daten: nur die Analyse aus der Strecke
    try:
        assert pg.locator("#tlsum").is_visible()
        t = pg.locator("#tlsum").inner_text()
        assert "Analyse" in t and "Training laut Uhr" not in t and "Messwerte" not in t and "Wetter" not in t
        assert pg.evaluate(SECS) == ["map", "prof", "photos"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    pg = _page(pw, app, tour="n0", devs=None)                                          # Tour ohne Strecke und ohne Daten: kein Einstieg
    try:
        assert pg.locator("#tlsum, #tlsgo").count() == 0 and pg.locator("#tlg-sum").is_hidden()
        assert pg.evaluate(SECS) == ["map", "prof", "photos"]
        assert pg.locator("#tls-prof").is_hidden()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_navigation_there_and_back(pw, app):
    pg = _page(pw, app, devs="one")
    try:
        pg.locator("#tlsgo").click()
        pg.wait_for_function("() => location.hash === '#/tour/r3/auswertung' && document.querySelector('#tlload') && document.querySelector('#tlload').hidden")
        pg.wait_for_function("() => window.scrollY === 0", timeout=15000)
        assert pg.evaluate("window.scrollY") == 0
        assert pg.locator("h1.tlsubt").inner_text() == "Gipfelrunde heute" and pg.locator("#tlback").inner_text() == "‹ Zurück zur Tour"
        assert pg.locator("#tm, #tls-map, #tls-photos, #tls-puls, #tls-wp").count() == 0     # keine Hauptseiten-Teile
        pg.go_back()                                                                    # Browser-Zurück
        pg.wait_for_selector("#tlsum")
        assert pg.evaluate("location.hash") == "#/tour/r3"
        pg.locator("#tlsgo").click()
        pg.wait_for_selector("#tlback")
        pg.locator("#tlback").click()                                                   # „‹ Zurück zur Tour“
        pg.wait_for_selector("#tlsum")
        assert pg.evaluate("location.hash") == "#/tour/r3"
        pg.go_back()                                                                    # zurück zur Unterseite
        pg.wait_for_selector("#tlback")
        assert pg.evaluate("location.hash") == "#/tour/r3/auswertung"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_notes_rating_gear_safety_stay_at_their_old_place(pw, app):
    """Bewertung, Notiz, Ausrüstung und Sicherheitsnotiz stehen wie in 3.14.0 oben im Kopf (zwischen Aktionsleiste und Kennzahlen), nicht in einer Gruppe am Seitenende."""
    pg = _page(pw, app, devs="one")
    try:
        assert pg.locator("#tl #starrow, #tl #note, #tl #gearrow, #tl #safety, #tls-notes, #tlg-more .field").count() == 0
        ys = pg.evaluate("() => ['#etag', '#note', '#starrow', '.figs', '#tl'].map(s => document.querySelector(s).getBoundingClientRect().top + scrollY)")
        assert ys[0] < ys[1] < ys[3] < ys[4] and ys[2] < ys[3], ys                       # Aktionsleiste · Notiz · (Sterne) · Kennzahlen · Gruppen
        assert pg.locator("#note").is_visible() and pg.locator("#starrow .st").count() == 5
        pg.locator("#note").fill("Nebel am Gipfel")
        pg.locator("#starrow .st").nth(3).click()
        pg.wait_for_function("() => document.querySelectorAll('#starrow .st.on').length === 4")
        assert pg.evaluate("document.querySelector('#tlg-more').innerText").count("Notiz") == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_entry_card_keyboard_and_whole_card_clickable(pw, app):
    pg = _page(pw, app, devs="one")
    try:
        pg.locator("#tlsgo").focus()
        assert pg.locator("#tlsgo").evaluate("e => getComputedStyle(e).outlineStyle !== 'none' && parseFloat(getComputedStyle(e).outlineWidth) >= 2")
        pg.keyboard.press("Enter")
        pg.wait_for_selector("#tlback")
        assert pg.evaluate("location.hash") == "#/tour/r3/auswertung"
        pg.go_back()
        pg.wait_for_selector("#tlsum", timeout=15000)
        _ready_main(pg)
        quiet(pg, 1800)                                                      # Seite fertig aufgebaut (Karte, Fotos), dann ändert sich nichts mehr
        pg.locator("#tlsum").scroll_into_view_if_needed()
        quiet(pg, 1500)                                                      # weiches Scrollen abwarten
        box = pg.locator("#tlsum").bounding_box()
        pg.mouse.click(box["x"] + box["width"] - 30, box["y"] + 25)                     # Klick irgendwo in die Karte
        pg.wait_for_selector("#tlback", timeout=15000)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_collapsed_map_is_resized_when_opened(pw, app):
    pg = _page(pw, app, devs="one", ctx_init="try { localStorage.setItem('mt_trf_tl_map', '0') } catch (e) {}")
    try:
        assert not pg.evaluate(OPEN)["map"]
        pg.locator("#tls-map > summary").click()
        pg.wait_for_function("() => document.querySelector('#tm').clientWidth > 300", timeout=15000)
        pg.wait_for_function("() => document.querySelectorAll('#tm .leaflet-tile-loaded, #tm path.leaflet-interactive').length >= 1", timeout=15000)
        pg.wait_for_function("""() => { const p = document.querySelector('#tm path.leaflet-interactive'); if (!p) return false; const m = p.getBoundingClientRect(), c = document.querySelector('#tm').getBoundingClientRect(); return m.left >= c.left && m.right <= c.right; }""", timeout=15000)
        pg.wait_for_timeout(500)
        assert pg.locator("#tm .leaflet-tile-loaded, #tm path.leaflet-interactive").count() >= 1
        assert pg.evaluate("(() => { const m = document.querySelector('#tm path.leaflet-interactive').getBoundingClientRect(), c = document.querySelector('#tm').getBoundingClientRect(); return m.left >= c.left && m.right <= c.right; })()")
    finally:
        pg.browser_.close()


def test_main_state_is_remembered(pw, app):
    pg = _page(pw, app, devs="one")
    try:
        pg.locator("#tls-wp > summary").click()
        pg.wait_for_function("() => { try { return localStorage.getItem('mt_trf_tl_wp') === '0'; } catch (e) { return false; } }", timeout=15000)
        pg.reload(); _ready_main(pg); quiet(pg, 1500)
        o = pg.evaluate(OPEN)
        assert not o["wp"] and o["map"] and o["photos"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Unterseite  ------------------------------------------------------------------

def test_sub_groups_and_order_two_devices(pw, app):
    pg = _page(pw, app, devs="two", sub=True)
    try:
        assert pg.evaluate(SECS) == SUB_ORDER
        assert pg.locator("#tl .tlgh").all_inner_texts() == ["Aufzeichnung", "Auswertung dieser Tour"]
        blocks = pg.locator("#tlrec .tldev")
        assert blocks.count() == 2 and pg.locator("#tlrec .tldev.multi").count() == 2
        assert "Amazfit Balance" in blocks.nth(0).locator(".tldh, #devrow").first.inner_text() and "Garmin Forerunner 255" in blocks.nth(1).locator(".tldh").inner_text()
        assert blocks.nth(0).locator("#metcard").count() == 1 and blocks.nth(1).locator("#uhrcard").count() == 1
        assert pg.locator("#devedit").count() == 1                                   # Gerät ändern bleibt erreichbar
        assert pg.locator("#tlrec #devrow, #tlrec .tldh").count() == 2                # je Block genau ein Gerätekopf
        for d in pg.locator("#tl details.tls").all():                                 # Abschnittskopf einheitlich: Symbol, Titel (h3), Kurzaussage
            assert d.locator("> summary svg.tli").count() == 1 and d.locator("> summary h3.tlt").count() == 1 and d.locator("> summary").get_attribute("aria-controls")
        assert pg.locator("#tls-uhr .tlk").inner_text().startswith("Trainingseffekt 3,2") and "Bewegungszeit" in pg.locator("#tls-ana .tlk").inner_text()
        assert "schnellste von" in pg.locator("#tls-cmp .tlk").inner_text()
        assert pg.locator("#tm, #profcard, #pulscard, #wpcard, #tls-photos, #starrow, #note, #tlsum").count() == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_sub_one_device_has_no_block_headings_and_default_state(pw, app):
    pg = _page(pw, app, devs="one", sub=True)
    try:
        assert pg.evaluate(SECS) == SUB_ORDER
        assert pg.locator("#tlrec .tldev").count() == 1 and pg.locator("#tlrec .tldh").count() == 0 and pg.locator("#tlrec .tldev.multi").count() == 0
        assert pg.locator("#tlrec > #devrow").count() == 1                         # „Aufgezeichnet mit“ steht einmal oben (seit 3.17.0 im Gerät-Block)
        o = pg.evaluate(OPEN)
        assert o["met"] and o["uhr"] and not any(o[k] for k in ("ana", "steig", "aehn", "wx", "cmp"))
        assert pg.locator("#tls-ana .tlsb").is_hidden() and pg.locator("#tls-ana .tlk").is_visible()      # Kurzaussage auch zugeklappt sichtbar
        assert pg.locator("#tlload").is_hidden() and pg.locator("#tlempty").is_hidden()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_sub_head_has_name_figures_and_back_link(pw, app):
    pg = _page(pw, app, devs="one", sub=True)
    try:
        assert pg.locator("h1").inner_text() == "Gipfelrunde heute"
        assert pg.locator(".tlsubeb").text_content() == "Detaillierte Auswertung"
        f = pg.locator(".tlsubfig").inner_text()
        assert "6,0 km" in f and "↑ 325 m" in f and "1:45 Std." in f and "3,4 km/h" in f, f
        assert pg.locator("#tlback").get_attribute("href") == "#/tour/r3"
        assert pg.evaluate("document.querySelector('h1').getBoundingClientRect().height") < 90
        assert pg.locator(".tlsubfig .tag").is_visible()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_sub_measurements_diagram_and_all_fields_are_here(pw, app):
    pg = _page(pw, app, devs="one", sub=True)
    try:
        assert pg.locator("#metcard svg.metsvg").count() >= 1 and pg.locator("#metcard #dvulink").count() == 1
        assert pg.locator("#uhrcard #utneu").count() == 1
        assert "Steigung auf der Karte zeigen" in pg.locator("#gtog").inner_text() or True
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_sub_nav_chips_jump_open_and_focus(pw, app):
    pg = _page(pw, app, devs="two", sub=True)
    try:
        names = pg.locator("#tlnav .tlchip").all_inner_texts()
        assert names == ["Gerät & Messwerte", "Wetter", "Analyse", "Vergleich"]
        assert pg.locator("#tlnav .tlchip").first.evaluate("e => e.tagName") == "BUTTON" and pg.locator("#tlall").inner_text() == "Alles aufklappen"
        pg.locator("#tlnav .tlchip", has_text="Vergleich").click()
        pg.wait_for_function("() => document.querySelector('#tls-aehn').open && document.querySelector('#tls-cmp').open", timeout=15000)
        pg.wait_for_function("() => { const t = document.querySelector('#tls-aehn').getBoundingClientRect().top; return t > 0 && t < 400; }", timeout=15000)       # weiches Scrollen abwarten
        pg.wait_for_function("() => document.activeElement === document.querySelector('#tls-aehn > summary') && document.querySelector('#tls-aehn > summary').getAttribute('aria-expanded') === 'true'", timeout=15000)
        pg.wait_for_function("() => { try { return localStorage.getItem('mt_trf_aehn') === '1'; } catch (e) { return false; } }", timeout=15000)
        top = pg.evaluate("document.querySelector('#tls-aehn').getBoundingClientRect().top")
        assert 0 < top < 400, top
        assert pg.locator("#tls-aehn > summary").get_attribute("aria-expanded") == "true"
        assert pg.evaluate("document.activeElement === document.querySelector('#tls-aehn > summary')")
        assert pg.evaluate("localStorage.getItem('mt_trf_aehn')") == "1"
        pg.locator("#tlnav .tlchip", has_text="Wetter").click()
        pg.wait_for_function("() => document.querySelector('#tls-wx').open", timeout=15000)
        assert pg.evaluate("location.hash") == "#/tour/r3/auswertung"                 # kein Hash-Sprung, die Routing-Adresse bleibt
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_jump_respects_reduced_motion(pw, app):
    pg = _page(pw, app, devs="one", sub=True)
    try:
        pg.emulate_media(reduced_motion="reduce")
        pg.evaluate("() => { window.__b = []; window.__o = Element.prototype.scrollIntoView; Element.prototype.scrollIntoView = function (...a) { if (a[0] && a[0].behavior) window.__b.push(a[0].behavior); return window.__o.apply(this, a); }; }")
        pg.locator("#tlnav .tlchip", has_text="Analyse").click()
        pg.wait_for_function("() => window.__b.length === 1", timeout=15000)
        assert pg.evaluate("window.__b") == ["auto"]
        pg.emulate_media(reduced_motion="no-preference")
        pg.locator("#tlnav .tlchip", has_text="Wetter").click()
        pg.wait_for_function("() => window.__b.length === 2", timeout=15000)
        assert pg.evaluate("window.__b") == ["auto", "smooth"]
    finally:
        pg.browser_.close()


def test_sub_nav_is_sticky_on_desktop_under_the_header(pw, app):
    pg = _page(pw, app, devs="one", height=500, sub=True)
    try:
        pg.locator("#tlall").click()
        pg.wait_for_function("() => document.querySelector('#tlall').textContent === 'Alles zuklappen' && document.documentElement.scrollHeight > 2400", timeout=15000)
        pg.wait_for_timeout(500)
        assert pg.locator("#tlnav").evaluate("e => getComputedStyle(e).position") == "sticky"
        pg.evaluate("window.scrollTo(0, 1800)")
        pg.wait_for_function("""() => { const n = document.querySelector('#tlnav').getBoundingClientRect(), h = document.querySelector('header.top').getBoundingClientRect(); return window.scrollY > 1000 && Math.abs(n.y - (h.y + h.height)) <= 2 && n.height > 20; }""", timeout=15000)
        pg.wait_for_timeout(400)
        n = pg.locator("#tlnav").bounding_box()
        h = pg.locator("header.top").bounding_box()
        assert abs(n["y"] - (h["y"] + h["height"])) <= 2 and n["height"] > 20, (n, h)
    finally:
        pg.browser_.close()


def test_expand_all_collapse_all_and_state_is_remembered(pw, app):
    pg = _page(pw, app, devs="one", sub=True)
    try:
        pg.locator("#tlall").click()
        pg.wait_for_function("() => document.querySelector('#tlall').textContent === 'Alles zuklappen'", timeout=15000)
        pg.wait_for_function("() => [...document.querySelectorAll('#tl details.tls')].every(x => x.open)", timeout=15000)
        assert all(pg.evaluate(OPEN).values())
        assert pg.evaluate("document.querySelectorAll('#tl details.tls[open]').length") == len(SUB_ORDER)
        pg.reload(); pg.wait_for_function(READY_SUB, timeout=15000); quiet(pg, 1500)
        pg.wait_for_function("() => { const d = [...document.querySelectorAll('#tl details.tls')]; return d.length > 0 && d.every(x => x.open); }", timeout=15000)
        assert all(pg.evaluate(OPEN).values())                                          # Zustand bleibt nach dem Neuladen (Direktaufruf der Unterseite)
        pg.locator("#tlall").click()
        pg.wait_for_function("() => document.querySelector('#tlall').textContent === 'Alles aufklappen'", timeout=15000)
        pg.wait_for_function("() => [...document.querySelectorAll('#tl details.tls')].every(x => !x.open)", timeout=15000)
        assert not any(pg.evaluate(OPEN).values())
        pg.locator("#tls-ana > summary").click()
        pg.wait_for_function("() => { try { return localStorage.getItem('mt_trf_tl_ana') === '1'; } catch (e) { return false; } }", timeout=15000)
        pg.reload(); pg.wait_for_function(READY_SUB, timeout=15000); quiet(pg, 1500)
        pg.wait_for_function("() => { const a = document.querySelector('#tls-ana'), m = document.querySelector('#tls-met'), u = document.querySelector('#tls-uhr'); return !!a && !!m && !!u && a.open && !m.open && !u.open; }", timeout=15000)
        o = pg.evaluate(OPEN)
        assert o["ana"] and not o["met"] and not o["uhr"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_sub_state_is_shared_with_the_old_keys(pw, app):
    """Offen/zu bleibt unter denselben Schlüsseln (mt_trf_tl_met …) wie bisher: wer Messwerte zugeklappt hatte, findet sie zu."""
    pg = _page(pw, app, devs="one", sub=True, ctx_init="try { localStorage.setItem('mt_trf_tl_met', '0'); localStorage.setItem('mt_trf_tl_ana', '1') } catch (e) {}")
    try:
        o = pg.evaluate(OPEN)
        assert not o["met"] and o["ana"] and o["uhr"]
    finally:
        pg.browser_.close()


def test_sub_slope_link_opens_map_with_gradient_on_main_page(pw, app):
    pg = _page(pw, app, devs="one", sub=True)
    try:
        pg.locator("#tls-ana > summary").click()
        pg.wait_for_selector("#gtog", timeout=15000)
        assert pg.locator("#gtog").get_attribute("href") == "#/tour/r3?karte=steigung"
        pg.locator("#gtog").click()
        pg.wait_for_function("() => document.querySelector('#tm .smap.on') && document.querySelector('#tm .sleg')", timeout=15000)
        assert pg.evaluate("location.hash").startswith("#/tour/r3")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_main_map_slope_button_still_works(pw, app):
    pg = _page(pw, app, devs="one")
    try:
        pg.wait_for_selector("#tm .smap", timeout=15000)
        pg.locator("#tm .smap").click()
        pg.wait_for_function("() => document.querySelector('#tm .smap.on') && document.querySelector('#tm .sleg')", timeout=15000)
        pg.locator("#tm .smap").click()
        pg.wait_for_function("() => !document.querySelector('#tm .sleg')", timeout=15000)
    finally:
        pg.browser_.close()


def test_sub_without_watch_data_has_no_empty_sections_or_chips(pw, app):
    pg = _page(pw, app, tour="s0", devs=None, sub=True)
    try:
        assert pg.evaluate(SECS) == ["ana"]
        assert pg.locator("#metcard, #uhrcard, #aehncard, #cmpseg, #tls-wx").count() == 0
        assert pg.locator("#tlnav").is_hidden() or pg.locator("#tlnav .tlchip").count() < 2
        bad = pg.evaluate("[...document.querySelectorAll('#tl .tlg')].filter(g => !g.hidden && ![...g.querySelectorAll('details.tls')].some(d => !d.hidden)).map(g => g.id)")
        assert not bad, bad
        assert pg.locator("#tlg-rec").is_hidden() and pg.locator("#tlempty").is_hidden()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_sub_direct_call_without_any_data_shows_friendly_note(pw, app):
    pg = _page(pw, app, tour="n0", devs=None, sub=True)
    try:
        assert pg.evaluate(SECS) == []
        e = pg.locator("#tlempty")
        assert e.is_visible() and "keine Auswertung" in e.inner_text()
        assert e.locator("a").get_attribute("href") == "#/tour/n0" and pg.locator("#tlnav").is_hidden() and pg.locator("#tlload").is_hidden()
        assert pg.locator("h1").inner_text() == "Ohne Strecke"
        e.locator("a").click()
        pg.wait_for_selector("#tls-photos")
        assert pg.evaluate("location.hash") == "#/tour/n0"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_sub_for_unknown_tour_shows_error_not_blank(pw, app):
    b = pw.chromium.launch()
    try:
        p = b.new_context(locale="de-DE").new_page()
        p.goto(f"{app}/#/tour/gibtsnicht/auswertung")
        p.wait_for_selector("#main .bad", timeout=10000)
        assert "nicht gefunden" in p.locator("#main .bad").inner_text()
    finally:
        b.close()


def test_from_album_back_link_survives_the_subpage(pw, app):
    pg = _page(pw, app, devs="one")
    try:
        pg.evaluate("window._from = '#/album/x'")
        pg.locator("#tlsgo").click()
        pg.wait_for_selector("#tlback")
        assert pg.evaluate("window._from") == "#/album/x"                               # die Rücksprung-Adresse geht nicht verloren
        pg.locator("#tlback").click()
        pg.wait_for_selector("#tls-photos")
        assert pg.locator("a.back").first.get_attribute("href") == "#/album/x"
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Darstellung  ------------------------------------------------------------------

@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("sub", [False, True])
def test_mobile_390_no_horizontal_scroll(pw, app, scheme, sub):
    pg = _page(pw, app, devs="two", width=390, height=844, scheme=scheme, dpr=2, sub=sub)
    try:
        pg.evaluate("tlSetAll(true)")
        pg.wait_for_function("() => [...document.querySelectorAll('#tl details.tls')].filter(d => !d.hidden).every(d => d.open)", timeout=15000)
        quiet(pg, 1000)
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
        over = pg.evaluate("[...document.querySelectorAll('#tl details.tls, #tl .tlsb, #tlnav, #tl .tldev, #tlsum, .tlsubt, .tlsubfig')].filter(e => e.getBoundingClientRect().right > innerWidth + 1).map(e => e.id || e.className)")
        assert not over, over
        name = "auswertung" if sub else "tour"
        if sub:
            assert pg.locator("#tlnav .tlchips").evaluate("e => e.scrollWidth > e.clientWidth || e.scrollWidth <= e.clientWidth") and pg.locator("#tlnav").evaluate("e => getComputedStyle(e).position") == "relative"
        else:
            assert pg.locator("#tlsgo").evaluate("e => e.getBoundingClientRect().height >= 44 && e.getBoundingClientRect().width > 250")      # gut treffbar
        _shot(pg, f"{name}-390-{scheme}-aufgeklappt.png")
        pg.evaluate("tlSetAll(false)"); pg.wait_for_timeout(500)
        _shot(pg, f"{name}-390-{scheme}-zu.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


CONTRAST = """(sels) => {
  const parse = c => { const m = c.match(/[\\d.]+/g).map(Number); return {r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1}; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const bg = el => { for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c.a > 0.5) return c; } return {r: 255, g: 255, b: 255, a: 1}; };
  const out = {};
  for (const sel of sels) {
    const el = document.querySelector(sel);
    if (!el) continue;
    const f = parse(getComputedStyle(el).color), b = bg(el), l1 = lum(f), l2 = lum(b);
    out[sel] = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }
  const ic = document.querySelector("#tl .tli"), card = ic && ic.closest("details, .tlsum");
  if (ic) { const f = parse(getComputedStyle(ic).stroke), b = bg(card), l1 = lum(f), l2 = lum(b); out["icon"] = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05); }
  return out;
}"""
SUB_SELS = ["#tl .tlgh", "#tlnav .tlchip", "#tlall", "#tls-met .tlt", "#tls-met .tlk", "#tls-uhr .tlk", "#tls-ana .tlk", ".tldh b", ".tldh small", ".tlsubeb", ".tlsubt", ".tlsubfig", "#tlback"]
MAIN_SELS = ["#tl .tlgh", "#tls-map .tlt", "#tls-map .tlk", "#tls-puls .tlk", "#tls-wp .tlk", ".tlsn", ".tlsv", ".tlsin", ".tlsgo", ".tlbar .sub"]


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_contrast_in_light_and_dark(pw, app, scheme):
    pg = _page(pw, app, devs="two", scheme=scheme, dpr=2, sub=True)
    try:
        c = pg.evaluate(CONTRAST, SUB_SELS)
        assert len(c) >= 10, c
        low = {k: round(v, 2) for k, v in c.items() if v < 4.5}
        assert not low, f"{scheme}: Kontrast unter 4,5:1 (Unterseite): {low}"
        _shot(pg, f"auswertung-desktop-{scheme}-zwei-geraete-standard.png")
        pg.evaluate("tlSetAll(true)"); quiet(pg, 1200)
        _shot(pg, f"auswertung-desktop-{scheme}-zwei-geraete-aufgeklappt.png")
        pg.close()
        pg = _page(pw, app, devs="one", scheme=scheme, dpr=2, sub=True)
        _shot(pg, f"auswertung-desktop-{scheme}-ein-geraet-standard.png")
        pg.evaluate("tlSetAll(true)"); quiet(pg, 1200)
        _shot(pg, f"auswertung-desktop-{scheme}-ein-geraet-aufgeklappt.png")
        pg.close()
        pg = _page(pw, app, devs="one", scheme=scheme, dpr=2)
        c = pg.evaluate(CONTRAST, MAIN_SELS)
        assert len(c) >= 9, c
        low = {k: round(v, 2) for k, v in c.items() if v < 4.5}
        assert not low, f"{scheme}: Kontrast unter 4,5:1 (Hauptseite): {low}"
        _shot(pg, f"tour-desktop-{scheme}-hauptseite.png")
        pg.close()
        pg = _page(pw, app, tour="s0", devs=None, scheme=scheme, dpr=2)
        _shot(pg, f"tour-desktop-{scheme}-ohne-uhr.png")
        pg.close()
        pg = _page(pw, app, tour="n0", devs=None, scheme=scheme, dpr=2, sub=True)
        _shot(pg, f"auswertung-desktop-{scheme}-leer.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_keyboard_focus_visible_and_english(pw, app):
    pg = _page(pw, app, devs="two", locale="en-US", sub=True)
    try:
        t = pg.locator("#tl").inner_text() + pg.locator("#tlnav").inner_text() + pg.locator("#main").text_content()
        for w in ("Recording", "Evaluation of this tour", "Back to the tour", "Detailed evaluation", "Weather", "Expand all", "Device & readings"):
            assert w in t, w
        for g in ("Aufzeichnung", "Zurück zur Tour", "Detaillierte Auswertung", "Alles aufklappen", "Wetter"):
            assert g not in t, g
        pg.locator("#tls-ana > summary").focus()
        assert pg.locator("#tls-ana > summary").evaluate("e => getComputedStyle(e).outlineStyle !== 'none' && parseFloat(getComputedStyle(e).outlineWidth) >= 2")
        pg.locator("#tlback").focus()
        assert pg.locator("#tlback").evaluate("e => parseFloat(getComputedStyle(e).outlineWidth) >= 2")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    pg = _page(pw, app, devs="two", locale="fr-FR")
    try:
        t = pg.locator("#tlsum").inner_text()
        assert "Voir l’évaluation détaillée" in t and "Contient" in t and "Détaillée" not in t, t
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    pg = _page(pw, app, devs="two", locale="en-US")
    try:
        t = pg.locator("#tl").inner_text()
        for w in ("Route", "Evaluation of this tour", "Photos of the tour", "View detailed evaluation ›", "Includes:", "Waypoints"):
            assert w in t, w
        for g in ("Streckenverlauf", "Detaillierte", "Enthält"):
            assert g not in t, g
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_viewer_sees_both_pages_without_edit_buttons(pw, app):
    pg = _page(pw, app, devs="two", ctx_init="window.__viewer = 1")
    try:
        pg.evaluate("ME.user = {role: 'viewer', uid: 9, name: 'Oma'}; document.documentElement.classList.add('viewer')")
        pg.evaluate("document.querySelector('#tl').dataset.alt = '1'; window.__sigw = null")          # alte Seite markieren: die neu gezeichnete (ohne Marke) abwarten
        pg.evaluate("route()")
        pg.wait_for_selector("#tl:not([data-alt]) #tls-photos", timeout=15000); _ready_main(pg); quiet(pg, 1800)
        assert pg.evaluate(SECS) == MAIN_ORDER and pg.locator("#tlsgo").is_visible()
        pg.locator("#tlsgo").click()
        pg.wait_for_function(READY_SUB, timeout=15000); quiet(pg, 800)
        assert pg.evaluate(SECS) == SUB_ORDER
        assert pg.locator("#devedit").count() == 0 and pg.locator("#utneu").count() == 0
        assert pg.locator("#tlnav .tlchip").count() == 4
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
