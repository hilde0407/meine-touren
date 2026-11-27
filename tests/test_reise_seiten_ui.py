"""3.33.0 – Reisen als anpassbare Seiten (Browser, Chromium): Reise-Detailseite (#/trip/<id>, Schlüssel „reise“) und Reisen-Übersicht (#/trips, Schlüssel „reisen“).
Standardoptik unverändert (gleiche Abschnitte in gleicher Reihenfolge, alte Kennungen und Aktionen bleiben), Verschieben / Ausblenden / Breite / Einklappen und Persistenz nach dem Neuladen,
die Karte zeichnet nach Verschieben, Einklappen und Ausblenden korrekt (Leaflet-Größe und Ausschnitt), die neuen Bausteine mit Testdaten, Ansichten, Vorlagen, Export und Import, Standard wiederherstellen,
Betrachter, 390 px hell und dunkel ohne seitliches Scrollen, Übersetzung.
Wettlauf-Regel: nach jeder Aktion auf den Zustand warten (wait_for_function mit Pfeilfunktionen, expect mit 15 s), nie nur schlafen.
Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt (Chromium, dpr 2)."""
import json
import os
import re
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.test_seitenlayout_ui import ROOT, T, _api, _browser, _edit, _saved, pw  # noqa: F401
from tests.test_bausteine_konfig_ui import click_gear, save_dialog  # noqa: E402
from tests.test_bausteine_ui import TEXTCONTRAST  # noqa: E402
from tests.test_tourseite_ui import CONTRAST, LAUNCH, _settled, _shot, _wait

TL = 30000
KEYS = ("tour-haupt", "tour-auswertung", "uebersicht", "statistik", "reise", "reisen")
# Reisen: (Name, Land, Breite, Länge, Tage zurück bis zum ersten Tag, Tage, Zahl der Fotos); Heimat ist 48,11
TRIPS = [("La Gomera", "Spanien", 28.1, -17.2, 40, 6, 6), ("Südtirol", "Italien", 46.6, 11.3, 100, 5, 0), ("Gran Canaria", "Spanien", 28.0, -15.6, 400, 5, 2)]
SEED = r"""
import sys, os, time, math; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db, config, routes
from PIL import Image
db.init()
config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
pics = os.path.join(%(data)r, "pics"); os.makedirs(pics, exist_ok=True)
db.put("home_lat", "48.0"); db.put("home_lng", "11.0")
now = int(time.time()); day = 86400; base = now // day * day + 9 * 3600
def loop(lat0, lng0, r=0.01, n=120):
    return [(lat0 + r * math.sin(2 * math.pi * i / (n - 1)), lng0 + r * (1 - math.cos(2 * math.pi * i / (n - 1))), 500 + 60 * math.sin(i / 14), i * 40000) for i in range(n)]
def tour(tid, ts, name, dist, dur, up, down, lat, lng, country=None, state=None, sport="hike"):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,'t','komoot')", (tid, name, sport, ts, ts + dur, dist, dur, up, down, lat, lng))
    if country:
        db.execute("INSERT INTO tour_geo(id,country,state,county,place,ts) VALUES(?,?,?,?,?,0)", (tid, country, state, state, state))
    routes.store(tid, loop(lat, lng))
for i in range(6):
    tour("h%%d" %% i, base - (20 + i * 31) * day, "Heimrunde %%d" %% i, 9000, 9000, 150, 150, 48.0 + i * 0.001, 11.0)
for tid, tag in (("h0", "Schwarzwald"), ("h1", "Schwarzwald"), ("h2", "Hüttenwanderung"), ("r1_0_0", "Gipfel")):
    db.execute("INSERT INTO tour_tags(id,tag) VALUES(?,?)", (tid, tag))
for k, (name, country, lat, lng, back, days, nph) in enumerate(%(trips)r):
    for d in range(days):
        for j in range(2 if d == 1 else 1):
            tid = "r%%d_%%d_%%d" %% (k, d, j)
            tour(tid, base - (back - d) * day + j * 7200, "%%s Tag %%d%%s" %% (name, d + 1, " (Nachmittag)" if j else ""), 8000 + d * 2500 + j * 1000, 9000 + d * 600, 200 + d * 120, 180 + d * 100, lat, lng + d * 0.04, country, name, "touringbicycle" if d == 2 else "hike")
    for p in range(nph):
        path = os.path.join(pics, "t%%d_%%d.jpg" %% (k, p))
        Image.new("RGB", (640, 480), (40 + 30 * p, 120, 160 - 20 * p)).save(path, "JPEG")
        db.execute("INSERT INTO photos(path,taken_ts,dated,tour_id) VALUES(?,?,1,?)", (path, base - (back - p %% days) * day + 1800, "r%%d_%%d_0" %% (k, p %% days)))
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("rs")
    data = tmp / "data"
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data), "trips": TRIPS}], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
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


def _trips(url):
    with urllib.request.urlopen(url + "/api/trips", timeout=10) as r:
        return {t["region"].split(" – ")[0]: t for t in json.loads(r.read())}


def _tid(url, name="La Gomera"):
    return _trips(url)[name]["id"]


# Reihenfolge der Abschnitte der Reise-Seite wie auf der Seite (ohne Rahmen im Bearbeitungsmodus)
UNITS = "() => [...document.querySelectorAll('#trx #rs-kopf, #trx details.tls')].filter(e => !e.closest('.sl-off')).map(e => e.dataset.tls || 'kopf')"
ALL_UNITS = "() => [...document.querySelectorAll('#trx #rs-kopf, #trx details.tls')].map(e => e.dataset.tls || 'kopf')"
STD = ["kopf", "kennzahlen", "stat", "flug", "karte", "fotos", "touren"]
RUNITS = "() => [...document.querySelectorAll('#rsx details.tls')].filter(e => !e.closest('.sl-off')).map(e => e.dataset.tls)"
RSTD = ["serien", "reisen", "alben"]
MAPOK = """() => {
  const c = document.getElementById('cm');
  if (!c || typeof map === 'undefined' || !map || map.getContainer() !== c || !c.clientWidth) return false;
  const s = map.getSize(), b = map.getBounds();
  return Math.abs(s.x - c.clientWidth) <= 1 && Math.abs(s.y - c.clientHeight) <= 1 && b.contains([28.1, -17.2]) && b.contains([28.11, -17.0]) && map.getZoom() >= 8;
}"""


def _trip(pw, url, name="La Gomera", **kw):
    pg = _browser(pw, url, devs=None, **kw)
    pg.goto(f"{url}/#/trip/{_tid(url, name)}", timeout=TL)
    pg.wait_for_selector("#trx #tls-touren", state="attached", timeout=TL)
    pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen') && typeof map !== 'undefined' && !!map && !!map._cvFit && !!document.querySelector('#trpdf') && !!document.querySelector('#trsnd')", timeout=TL)
    return pg


def _trips_page(pw, url, **kw):
    pg = _browser(pw, url, devs=None, **kw)
    pg.goto(f"{url}/#/trips", timeout=TL)
    pg.wait_for_selector("#rsx #tls-reisen", state="attached", timeout=TL)
    pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen') && document.querySelectorAll('#rsx .otd').length > 0", timeout=TL)
    return pg


def _order(pg, expect_, fn=UNITS):
    pg.wait_for_function("([e]) => JSON.stringify((%s)()) === JSON.stringify(e)" % fn, arg=[expect_], timeout=T)


def _server(url, key):
    return _api(url, key).get("layout")


# ------------------------------------------------------------------  Reise-Detailseite: Standard bleibt Standard  ------------------------------------------------------------------

def test_trip_default_is_unchanged(pw, app):
    """Gleiche Abschnitte in gleicher Reihenfolge, alle Kennungen und Aktionen der alten Seite sind da, die Karte ist richtig eingerahmt."""
    pg = _trip(pw, app)
    try:
        assert pg.evaluate(UNITS) == STD and pg.evaluate(ALL_UNITS) == STD
        for sel in ("#tredit", "#trpdf", "#trsnd", "#trhide", "#coff", "#cofm", "#cm", "#main h1", "#main .figs .fig", ".cstat", "#main .tl .trow, #main .tl a, #main .tl .row"):
            assert pg.locator(sel).count() >= 1, sel
        assert pg.locator("#main h1").inner_text().strip() == "La Gomera, Spanien"
        assert [f.inner_text().split("\n")[-1] for f in pg.locator("#main .figs .fig").all()] == ["Touren", "Strecke", "Aufstieg", "Abstieg", "Unterwegs", "Tage"]
        assert pg.locator("#main .figs .fig .v").first.inner_text().strip() == "7"
        assert "Statistik nach Sportart" in pg.locator("#tls-stat summary").text_content()
        assert pg.locator("#trx details.tls[open]").count() == 6                                  # alle Karten standardmäßig offen
        assert pg.locator("#trx .slcell.w-voll").count() == 7
        # Reihenfolge der Aktionen im Kopf wie bisher: PDF, Senden, Bearbeiten, Keine Reise
        assert pg.evaluate("() => [...document.querySelectorAll('#rs-kopf .row > .btn')].map(b => b.id).filter(Boolean)") == ["trpdf", "trsnd", "tredit", "trhide"]
        pg.wait_for_function(MAPOK, timeout=T)
        assert pg.locator("#slopen").count() == 1 and pg.locator("#slviews").count() == 1 and pg.locator(".slit").count() == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_trip_actions_still_work(pw, app):
    """Bearbeiten-Dialog, Senden und Reisebericht (PDF-Seite) funktionieren unverändert."""
    pg = _trip(pw, app)
    try:
        pg.locator("#tredit").click()
        expect(pg.locator("#tn")).to_have_value("La Gomera", timeout=15000)
        pg.locator("#tno").click()
        expect(pg.locator("#tn")).to_have_count(0, timeout=15000)
        assert pg.locator("#trpdf").get_attribute("href").startswith("#/tripsheet/")
        pg.locator("#trpdf").click()
        pg.wait_for_selector("#tm", timeout=T)
        pg.wait_for_function("() => /Tag für Tag/.test(document.querySelector('#main').textContent) && /Statistik nach Sportart/.test(document.querySelector('#main').textContent)", timeout=T)
        assert pg.locator("#pdfdl").count() == 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Bearbeiten: Verschieben, Ausblenden, Breite, Einklappen, Persistenz  ------------------------------------------------------------------

def _done(pg):
    pg.locator("#slbar").get_by_role("button", name="Fertig").click()
    pg.wait_for_function("() => !document.querySelector('.slit') && !document.getElementById('slbar')", timeout=T)


def _saved_doc(pg, key="reise", want=None):
    """Gespeichertes Dokument vom Server; mit want (Funktion Dokument → Wahrheitswert) wird gewartet, bis der Server den erwarteten Stand hat (Speichern ist verzögert)."""
    for _ in range(60):
        d = pg.evaluate("(k) => fetch('/api/layout/' + k).then(r => r.json()).then(j => j.layout)", key)
        if want is None or (d is not None and want(d)) or (d is None and want(None)):
            return d
        pg.wait_for_timeout(250)
    st = pg.evaluate("(k) => [SL.dirty.size, SL.busy.size, JSON.stringify(SL.store[k]), JSON.stringify(SL.docs[k]), document.getElementById('slsaved') && document.getElementById('slsaved').textContent, SL.docs[k] === slStore(k).views[0].layout, JSON.stringify(SL.view), SL.fam, JSON.stringify(SL.rev), location.hash]", key)
    raise AssertionError("Server hat den erwarteten Stand nicht erreicht: " + json.dumps(d)[:400] + " Seite: " + json.dumps(st)[:600])


def test_trip_edit_move_hide_width_open_and_persistence(pw, app):
    pg = _trip(pw, app)
    try:
        _edit(pg)
        assert pg.locator(".slit").count() == 7
        assert pg.locator('.slit[data-sl="kopf"] [data-a="eye"]').count() == 0 and pg.locator('.slit[data-sl="kopf"] .slmust').is_visible()       # der Kopf bleibt immer sichtbar
        assert pg.locator('.slit[data-sl="kopf"] [data-a="w"]').count() == 0                                                                    # und hat nur eine Breite
        # Hoch/Runter
        pg.locator('.slit[data-sl="touren"] [data-a="up"]').click()
        _order(pg, ["kopf", "kennzahlen", "stat", "flug", "karte", "touren", "fotos"], ALL_UNITS)
        pg.locator('.slit[data-sl="kennzahlen"] [data-a="down"]').click()
        _order(pg, ["kopf", "stat", "kennzahlen", "flug", "karte", "touren", "fotos"], ALL_UNITS)
        # Ausblenden: im Bearbeitungsmodus gedimmt und beschriftet
        pg.locator('.slit[data-sl="flug"] [data-a="eye"]').click()
        pg.wait_for_function("() => document.querySelector('.slit[data-sl=flug]').classList.contains('sl-dim')", timeout=T)
        assert pg.locator('.slit[data-sl="flug"] .slhid').is_visible()
        # Breite: Karte und Touren nebeneinander
        pg.locator('.slit[data-sl="karte"] [data-a="w"][data-w="halb"]').click()
        pg.locator('.slit[data-sl="touren"] [data-a="w"][data-w="halb"]').click()
        pg.wait_for_function("() => { const a = document.querySelector('.slit[data-sl=karte]'), b = document.querySelector('.slit[data-sl=touren]'); return a.dataset.cw === 'halb' && b.dataset.cw === 'halb' && Math.abs(a.getBoundingClientRect().top - b.getBoundingClientRect().top) < 2 && b.getBoundingClientRect().left > a.getBoundingClientRect().left + 200; }", timeout=T)
        # Standardmäßig zu: Fotos
        sw = pg.locator('.slit[data-sl="fotos"] input[data-a="open"]')
        assert sw.is_checked()
        sw.uncheck()
        pg.wait_for_function("() => !document.querySelector('#tls-fotos').open", timeout=T)
        _saved(pg)
        _done(pg)
        # ohne Rahmen: ausgeblendet ist weg, Reihenfolge, Breiten, Zustand
        assert pg.evaluate(UNITS) == ["kopf", "stat", "kennzahlen", "karte", "touren", "fotos"] and pg.locator("#tls-flug").is_hidden()
        assert pg.locator("#rsc-karte").evaluate("e => e.classList.contains('w-halb')") and pg.locator("#tls-fotos").evaluate("e => !e.open")
        doc = _saved_doc(pg, want=lambda d: d.get("closed") == ["fotos"] and d.get("w") == {"karte": "halb", "touren": "halb"} and d.get("hidden") == ["flug"])
        assert "order" in doc, doc
        assert doc["order"] == ["kopf", "stat", "kennzahlen", "flug", "karte", "touren", "fotos"] and doc["hidden"] == ["flug"] and doc["w"] == {"karte": "halb", "touren": "halb"} and doc["closed"] == ["fotos"]
        # nach dem Neuladen derselbe Stand (Server und Zwischenspeicher)
        pg.reload()
        pg.wait_for_selector("#trx #tls-touren", state="attached", timeout=TL)
        pg.wait_for_function("() => typeof map !== 'undefined' && !!map && !!map._cvFit", timeout=TL)
        _order(pg, ["kopf", "stat", "kennzahlen", "karte", "touren", "fotos"])
        assert pg.locator("#tls-flug").is_hidden() and pg.locator("#tls-fotos").evaluate("e => !e.open") and pg.locator("#rsc-touren").evaluate("e => e.classList.contains('w-halb')")
        pg.wait_for_function(MAPOK, timeout=T)
        # das Layout gilt für alle Reisen
        other = _tid(app, "Südtirol")
        pg.goto(f"{app}/#/trip/{other}")
        pg.wait_for_function("(t) => !!document.querySelector('#trx') && document.querySelector('#trx').dataset.trip === t && typeof map !== 'undefined' && !!map && !!map._cvFit", arg=other, timeout=TL)
        _order(pg, ["kopf", "stat", "kennzahlen", "karte", "touren", "fotos"])
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_trip_keyboard_move_and_drag_with_the_pointer(pw, app):
    pg = _trip(pw, app, height=3800)
    try:
        _edit(pg)
        g = pg.locator('.slit[data-sl="fotos"] .slgrip')
        g.focus()
        pg.keyboard.press("ArrowUp")
        _order(pg, ["kopf", "kennzahlen", "stat", "flug", "fotos", "karte", "touren"], ALL_UNITS)
        pg.keyboard.press("Home")
        _order(pg, ["fotos", "kopf", "kennzahlen", "stat", "flug", "karte", "touren"], ALL_UNITS)
        # ziehen: Touren vor Kennzahlen
        b = pg.locator('.slit[data-sl="touren"] .slgrip').bounding_box()
        t = pg.locator('.slit[data-sl="kennzahlen"]').bounding_box()
        x0, y0 = b["x"] + b["width"] / 2, b["y"] + b["height"] / 2
        pg.mouse.move(x0, y0)
        pg.mouse.down()
        for i in range(1, 13):                                                           # in Schritten nach oben auf die obere Hälfte von „Kennzahlen“
            pg.mouse.move(x0 + 20, y0 + (t["y"] + 10 - y0) * i / 12)
        pg.wait_for_function("() => !!document.querySelector('.slit.sl-lift') && !!document.querySelector('.sl-before')", timeout=T)
        pg.mouse.up()
        _order(pg, ["fotos", "kopf", "touren", "kennzahlen", "stat", "flug", "karte"], ALL_UNITS)
        _saved(pg)
        assert _saved_doc(pg, want=lambda d: d.get("order", [""])[0:3] == ["fotos", "kopf", "touren"])["order"] == ["fotos", "kopf", "touren", "kennzahlen", "stat", "flug", "karte"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Karte nach Verschieben, Einklappen, Ausblenden, Breite  ------------------------------------------------------------------

def test_trip_map_is_drawn_correctly_after_move_width_collapse_and_hide(pw, app):
    pg = _trip(pw, app)
    try:
        pg.wait_for_function(MAPOK, timeout=T)
        _edit(pg)
        pg.wait_for_function(MAPOK, timeout=T)                                           # Rahmen im Bearbeitungsmodus ändern die Breite
        pg.locator('.slit[data-sl="karte"] [data-a="up"]').click()
        _order(pg, ["kopf", "kennzahlen", "stat", "karte", "flug", "fotos", "touren"], ALL_UNITS)
        pg.wait_for_function(MAPOK, timeout=T)
        pg.locator('.slit[data-sl="karte"] [data-a="w"][data-w="halb"]').click()
        pg.locator('.slit[data-sl="flug"] [data-a="w"][data-w="halb"]').click()           # ein Zeilenrest wird aufgefüllt: erst mit Nachbarn bleibt die Karte schmal
        pg.wait_for_function("() => document.getElementById('cm').clientWidth < 700", timeout=T)
        pg.wait_for_function(MAPOK, timeout=T)                                           # schmaler: Ausschnitt neu eingerahmt
        pg.locator('.slit[data-sl="karte"] [data-a="w"][data-w="voll"]').click()
        pg.wait_for_function("() => document.getElementById('cm').clientWidth > 900", timeout=T)
        pg.wait_for_function(MAPOK, timeout=T)
        # ausblenden und wieder einblenden
        pg.locator('.slit[data-sl="karte"] [data-a="eye"]').click()
        pg.locator('.slit[data-sl="karte"] [data-a="eye"]').click()
        pg.wait_for_function("() => !document.querySelector('.slit[data-sl=karte]').classList.contains('sl-dim')", timeout=T)
        pg.wait_for_function(MAPOK, timeout=T)
        _done(pg)
        pg.wait_for_function(MAPOK, timeout=T)
        # zuklappen und wieder aufklappen
        pg.locator("#tls-karte > summary").click()
        pg.wait_for_function("() => !document.querySelector('#tls-karte').open", timeout=T)
        pg.locator("#tls-karte > summary").click()
        pg.wait_for_function("() => document.querySelector('#tls-karte').open", timeout=T)
        pg.wait_for_function(MAPOK, timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_trip_map_in_a_hidden_card_is_fitted_when_it_shows(pw, app):
    """Ausgeblendet = kein Platz (Größe 0): die Karte wird erst eingerahmt, wenn sie sichtbar ist (Bearbeitungsmodus zeigt sie gedimmt)."""
    _api(app, "reise", "PUT", {"hidden": ["karte"]})
    pg = _trip(pw, app)
    try:
        assert pg.locator("#tls-karte").is_hidden() and pg.evaluate("() => document.getElementById('cm').clientWidth") == 0
        assert pg.evaluate("() => map._cvStale === true")
        _edit(pg)
        pg.wait_for_function(MAPOK, timeout=T)
        assert pg.evaluate("() => map._cvStale === false")
        # eine selbst bewegte Karte bleibt beim Ändern der Größe stehen
        pg.evaluate("() => { map.setView([28.1, -17.19], 14, {animate: false}); map._cvUser = true; }")
        pg.locator('.slit[data-sl="karte"] [data-a="w"][data-w="halb"]').click()
        pg.locator('.slit[data-sl="flug"] [data-a="w"][data-w="halb"]').click()
        pg.wait_for_function("() => document.getElementById('cm').clientWidth < 700 && Math.abs(map.getSize().x - document.getElementById('cm').clientWidth) <= 1", timeout=T)
        assert pg.evaluate("() => map.getZoom()") == 14
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_trip_map_in_a_card_that_starts_closed_draws_inside_its_frame_when_opened(pw, app):
    _api(app, "reise", "PUT", {"closed": ["karte"]})
    pg = _trip(pw, app)
    try:
        assert pg.locator("#tls-karte").evaluate("e => !e.open")
        pg.locator("#tls-karte > summary").click()
        pg.wait_for_function("() => document.querySelector('#tls-karte').open", timeout=T)
        pg.wait_for_function(MAPOK, timeout=T)
        pg.wait_for_function("""() => { const p = document.querySelector('#cm path.leaflet-interactive'); if (!p) return false; const m = p.getBoundingClientRect(), c = document.querySelector('#cm').getBoundingClientRect(); return m.left >= c.left && m.right <= c.right && m.top >= c.top && m.bottom <= c.bottom; }""", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Neue Bausteine mit Testdaten  ------------------------------------------------------------------

def _wid(pg, typ):
    return pg.evaluate("(t) => document.querySelector('#trx [data-wtype=' + t + '], #rsx [data-wtype=' + t + ']').dataset.wid", typ)


def test_new_trip_blocks_show_the_data_of_the_trip(pw, app):
    _api(app, "reise", "PUT", {"widgets": [{"id": "wk1", "type": "rkennzahl", "cfg": {}}, {"id": "wt1", "type": "rkmtag", "cfg": {}}, {"id": "wd1", "type": "rdiashow", "cfg": {"mode": "random", "view": "grid", "n": 12}}]})
    pg = _trip(pw, app)
    try:
        pg.wait_for_selector("#tlw-wk1 .utile", timeout=TL)
        tiles = pg.evaluate("() => [...document.querySelectorAll('#tlw-wk1 .utile')].map(t => [t.querySelector('b').textContent.trim(), t.querySelector('span').textContent.trim()])")
        assert tiles == [["6", "Reisetage"], ["7", "Touren"], ["97,0 km", "Strecke"], ["3.320 m", "Aufstieg"], ["20:10 Std.", "Unterwegs"], ["1", "Länder"]], tiles
        assert pg.locator("#tlw-wk1 .utile small").first.inner_text() == "Spanien"
        # Strecke je Tag: sechs Säulen, die stärkste (Tag 2: 22 km) hervorgehoben
        pg.wait_for_selector("#tlw-wt1 svg.slcol rect", timeout=T)
        assert pg.locator("#tlw-wt1 svg.slcol rect").count() == 6 and pg.locator("#tlw-wt1 svg.slcol rect.hl").count() == 1
        assert pg.evaluate("() => [...document.querySelectorAll('#tlw-wt1 svg.slcol rect')].findIndex(r => r.classList.contains('hl'))") == 1
        assert "22,0 km" in pg.locator("#tlw-wt1 svg.slcol").get_attribute("aria-label") and "Stärkster Tag" in pg.locator("#tlw-wt1").inner_text()
        # Reise-Diashow: nur die sechs Fotos dieser Reise (die der anderen Reisen kommen nicht vor)
        pg.wait_for_function("() => document.querySelectorAll('#tlw-wd1 .erb img').length === 6", timeout=T)
        href = pg.locator("#tlw-wd1 a.erdia").get_attribute("href")
        assert "from=" in href and "to=" in href, href
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_trip_slideshow_is_limited_to_the_photos_of_the_trip(pw, app):
    _api(app, "reise", "PUT", {"widgets": [{"id": "wd1", "type": "rdiashow", "cfg": {"mode": "recent", "view": "grid", "n": 12}}]})
    # Südtirol hat keine Fotos: ein Hinweis statt der Fotos der anderen Reisen; Gran Canaria (vor 400 Tagen) zeigt genau seine zwei
    pg = _trip(pw, app, "Südtirol")
    try:
        pg.wait_for_function("() => /keine Fotos/.test(document.querySelector('#tlw-wd1').textContent) && document.querySelectorAll('#tlw-wd1 .erb img').length === 0", timeout=T)
        pg.goto(f"{app}/#/trip/{_tid(app, 'Gran Canaria')}")
        pg.wait_for_function("(t) => document.querySelector('#trx') && document.querySelector('#trx').dataset.trip === t && document.querySelectorAll('#tlw-wd1 .erb img').length === 2", arg=_tid(app, "Gran Canaria"), timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    t = _trips(app)["La Gomera"]
    with urllib.request.urlopen(f"{app}/api/photos?date_from={t['start']}&date_to={t['end']}&limit=50", timeout=10) as r:
        assert len(json.loads(r.read())) == 6


def test_trip_blocks_can_be_added_from_the_catalog_and_only_fit_here(pw, app):
    pg = _trip(pw, app)
    try:
        _edit(pg)
        pg.locator("#slbar [data-a=add]").click()
        pg.wait_for_selector(".slcat .slcard", timeout=T)
        names = pg.locator(".slcat .slcard h3").all_inner_texts()
        assert {"Reise-Kennzahlen", "Strecke je Tag", "Fotos"} <= set(names) and "Reisen-Kennzahlen" not in names and "Reisen je Jahr" not in names, names
        assert pg.locator('.slcard:has([data-add="rkmtag"]) [data-add="rkmtag"]').inner_text() == "Hinzufügen"
        pg.locator('[data-add="rkmtag"]').click()
        pg.wait_for_function("() => !!document.querySelector('#trx [data-wtype=rkmtag] svg.slcol')", timeout=T)
        wid = _wid(pg, "rkmtag")
        _done(pg)
        doc = _saved_doc(pg, want=lambda d: d and any(w["type"] == "rkmtag" for w in d.get("widgets", [])))
        assert [w["type"] for w in doc["widgets"]] == ["rkmtag"] and doc["widgets"][0]["id"] == wid
        pg.reload()
        pg.wait_for_selector("#trx svg.slcol rect", timeout=TL)
        assert pg.locator("#trx svg.slcol rect").count() == 6
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    pg = _trips_page(pw, app)
    try:
        _edit(pg)
        pg.locator("#slbar [data-a=add]").click()
        pg.wait_for_selector(".slcat .slcard", timeout=T)
        names = pg.locator(".slcat .slcard h3").all_inner_texts()
        assert {"Reisen-Kennzahlen", "Reisen je Jahr"} <= set(names) and "Reise-Kennzahlen" not in names and "Strecke je Tag" not in names and "Fotos" not in names, names
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def _chip(pg, label):
    return pg.locator(".sldlg .flchip").filter(has_text=re.compile(r"^%s$" % re.escape(label)))


def test_trip_block_settings_dialogs(pw, app):
    _api(app, "reise", "PUT", {"widgets": [{"id": "wk1", "type": "rkennzahl", "cfg": {}}, {"id": "wt1", "type": "rkmtag", "cfg": {}}, {"id": "wd1", "type": "rdiashow", "cfg": {}}]})
    pg = _trip(pw, app)
    try:
        _edit(pg)
        pg.wait_for_selector("#tlw-wk1 .utile", timeout=TL)
        click_gear(pg, '.slit[data-sl="wk1"] [data-a="cfg"]')
        pg.wait_for_selector(".sldlg form", timeout=T)
        _chip(pg, "Strecke").click()
        _chip(pg, "Länder").click()
        save_dialog(pg)
        pg.wait_for_function("() => document.querySelectorAll('#tlw-wk1 .utile').length === 4", timeout=T)
        pg.wait_for_selector("#tlw-wt1 svg.slcol", timeout=TL)
        click_gear(pg, '.slit[data-sl="wt1"] [data-a="cfg"]')
        pg.wait_for_selector(".sldlg form", timeout=T)
        _chip(pg, "Aufstieg").click()
        save_dialog(pg)
        pg.wait_for_function("() => /Aufstieg je Tag/.test(document.querySelector('.slit[data-sl=wt1]').textContent)", timeout=T)
        # Reise-Diashow: kein Filter und kein „An diesem Tag“ im Dialog
        click_gear(pg, '.slit[data-sl="wd1"] [data-a="cfg"]')
        pg.wait_for_selector(".sldlg form.erform", timeout=T)
        assert pg.locator('.sldlg [name="f1"]').count() == 0 and pg.locator('.sldlg input[value="day"]').count() == 0 and "Fotos aus dem Zeitraum der Reise" in pg.locator(".sldlg").inner_text()
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('.sldlg')", timeout=T)
        _done(pg)
        doc = _saved_doc(pg, want=lambda d: d and any(w["id"] == "wk1" and w.get("cfg", {}).get("values") for w in d.get("widgets", [])))
        cfg = {w["id"]: w.get("cfg", {}) for w in doc["widgets"]}
        assert cfg["wk1"]["values"] == ["tage", "touren", "up", "down", "h"] or cfg["wk1"]["values"] == ["tage", "touren", "up", "h"], cfg
        assert "km" not in cfg["wk1"]["values"] and "laender" not in cfg["wk1"]["values"] and cfg["wt1"] == {"metric": "up"}, cfg
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Reisen-Übersicht  ------------------------------------------------------------------

def test_overview_default_is_unchanged(pw, app):
    pg = _trips_page(pw, app)
    try:
        assert pg.evaluate(RUNITS) == RSTD and pg.locator("#rsx details.tls[open]").count() == 3
        for sel in ("#tr", "#sbbtn", "#rnc-serien .otd", "#rnc-reisen #tr a", "#rnc-alben"):
            assert pg.locator(sel).count() >= 1, sel
        assert pg.locator("#tr a").count() >= 3 and pg.locator("#rnc-serien .otd").count() >= 2                                     # die Reisen und die Mehrtagestouren der Testdaten
        assert "erkannt an Namen wie" in pg.locator("#rnc-serien").inner_text()
        assert pg.locator("#slopen").count() == 1 and pg.locator(".slit").count() == 0
        pg.locator("#tr a").first.click()
        pg.wait_for_selector("#trx #tls-touren", state="attached", timeout=TL)                                                       # die Liste führt weiter zur Reise
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_overview_edit_move_hide_and_persistence(pw, app):
    pg = _trips_page(pw, app)
    try:
        _edit(pg)
        assert pg.locator(".slit").count() == 3 + (1 if pg.locator('.slit[data-sl="entfernt"]').count() else 0)
        pg.locator('.slit[data-sl="alben"] [data-a="up"]').click()
        _order(pg, ["serien", "alben", "reisen"], "() => [...document.querySelectorAll('#rsx details.tls')].map(e => e.dataset.tls)")
        pg.locator('.slit[data-sl="serien"] [data-a="eye"]').click()
        pg.wait_for_function("() => document.querySelector('.slit[data-sl=serien]').classList.contains('sl-dim')", timeout=T)
        pg.locator('.slit[data-sl="reisen"] [data-a="w"][data-w="zweidrittel"]').click()
        pg.locator('.slit[data-sl="alben"] [data-a="w"][data-w="drittel"]').click()
        pg.wait_for_function("() => { const a = document.querySelector('.slit[data-sl=reisen]'), b = document.querySelector('.slit[data-sl=alben]'); return Math.abs(a.getBoundingClientRect().top - b.getBoundingClientRect().top) < 2 && a.getBoundingClientRect().width > b.getBoundingClientRect().width * 1.7; }", timeout=T)
        _done(pg)
        doc = _saved_doc(pg, "reisen", want=lambda d: d and d.get("hidden") == ["serien"])
        assert doc["order"][:3] == ["serien", "alben", "reisen"] or doc["order"][:3] == ["alben", "serien", "reisen"], doc
        assert doc["w"] == {"reisen": "zweidrittel", "alben": "drittel"}, doc
        pg.reload()
        pg.wait_for_selector("#rsx #tls-reisen", state="attached", timeout=TL)
        pg.wait_for_function("() => document.querySelectorAll('#rsx .otd, #rsx #tr a').length > 0", timeout=TL)
        pg.wait_for_function("() => JSON.stringify([...document.querySelectorAll('#rsx details.tls')].filter(e => !e.closest('.sl-off')).map(e => e.dataset.tls)) === JSON.stringify(['alben', 'reisen'])", timeout=TL)
        assert pg.locator("#tls-serien").is_hidden() and pg.locator("#tr a").count() >= 3
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_overview_removed_trips_card_starts_closed_and_restores(pw, app):
    hid = [{"id": "x1", "region": "Entfernte Fahrt", "start": "2026-01-01", "end": "2026-01-05", "tours": ["a", "b"]}]
    pg = _browser(pw, app, devs=None)
    pg.route("**/api/trips?hidden=1", lambda r: r.fulfill(json=hid))
    try:
        pg.goto(f"{app}/#/trips", timeout=TL)
        pg.wait_for_selector("#rsx #tls-entfernt", state="attached", timeout=TL)
        assert pg.evaluate(RUNITS) == RSTD + ["entfernt"] and pg.locator("#tls-entfernt").evaluate("e => !e.open")
        assert "1 Reise" in pg.locator("#tls-entfernt summary").inner_text() and pg.locator('#tls-entfernt [data-rt="x1"]').count() == 1
        pg.locator("#tls-entfernt > summary").click()
        expect(pg.locator('#tls-entfernt [data-rt="x1"]')).to_be_visible(timeout=15000)
        assert "Entfernte Fahrt" in pg.locator("#tls-entfernt").inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_overview_blocks_show_the_data_of_all_trips(pw, app):
    _api(app, "reisen", "PUT", {"widgets": [{"id": "wn1", "type": "rnzahlen", "cfg": {}}, {"id": "wj1", "type": "rnjahre", "cfg": {"metric": "count"}}]})
    pg = _trips_page(pw, app)
    try:
        pg.wait_for_selector("#tlw-wn1 .utile", timeout=TL)
        tiles = pg.evaluate("() => [...document.querySelectorAll('#tlw-wn1 .utile')].map(t => [t.querySelector('b').textContent.trim(), t.querySelector('span').textContent.trim()])")
        assert tiles[0] == ["3", "Reisen"] and tiles[1] == ["16", "Reisetage"] and tiles[-1][1] == "Länder" and tiles[-1][0] == "2", tiles
        pg.wait_for_selector("#tlw-wj1 svg.slcol rect", timeout=TL)
        assert pg.locator("#tlw-wj1 svg.slcol rect").count() >= 1 and "Reisen je Jahr" in pg.locator("#tlw-wj1").evaluate("e => e.querySelector('summary').textContent")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Ansichten, Vorlagen, Export, Standard wiederherstellen  ------------------------------------------------------------------

def _cont_wait(pg, url, key, pred):
    """Wartet (ohne Schlafen des Python-Prozesses) auf den Stand der Ansichten beim Server."""
    c = None
    for _ in range(60):
        c = _api(url, key).get("container")
        if c and pred(c):
            return c
        pg.wait_for_timeout(250)
    raise AssertionError("Server hat den erwarteten Stand nicht erreicht: " + json.dumps(c)[:300])


def _open_views(pg):
    pg.locator("#slbar [data-a=views]").click()
    pg.wait_for_selector(".slvws .slvr", timeout=T)


def test_views_templates_and_reset_on_the_trip_page(pw, app):
    pg = _trip(pw, app)
    try:
        _edit(pg)
        _open_views(pg)
        pg.locator(".slvws").get_by_role("button", name="Aus Vorlage …", exact=True).click()
        pg.wait_for_selector(".slvt .slcard", timeout=T)
        assert pg.locator(".slvt .slcard h3").all_inner_texts() == ["Kompakt", "Fotoreise", "Tag für Tag"]
        pg.get_by_role("button", name="Kompakt: Als neue Ansicht übernehmen", exact=True).click()
        pg.wait_for_function("() => !document.querySelector('.slvt')", timeout=T)
        pg.wait_for_function("() => slViewName('reise', SL.view.reise) === 'Kompakt'", timeout=T)
        pg.wait_for_function("() => !!document.querySelector('#trx [data-wtype=rkmtag] svg.slcol rect')", timeout=TL)
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('.uidlg') && !document.querySelector('.slvws')", timeout=T)
        pg.wait_for_function(MAPOK, timeout=TL)                                                                                          # die Karte stimmt auch nach dem Wechsel der Ansicht
        c = _cont_wait(pg, app, "reise", lambda c: len(c["views"]) == 2)
        assert [v["name"] for v in c["views"]] == ["Standard", "Kompakt"]
        assert set(c["views"][1]["layout"]["hidden"]) >= {"stat", "flug", "fotos"}
        # Standard wiederherstellen setzt die aktive Ansicht zurück (Reihenfolge, Breiten, Ausgeblendetes, Bausteine), die Seite sieht wieder aus wie zu Beginn
        pg.locator("#slbar [data-a=more]").click() if pg.locator("#slbar [data-a=reset]").is_hidden() else None
        pg.locator("#slbar [data-a=reset]").click()
        pg.get_by_role("button", name="Standard wiederherstellen").last.click()
        pg.wait_for_function("() => !document.querySelector('[data-wtype]:not(#tlw-fotos)')", timeout=T)
        _order(pg, STD, ALL_UNITS)
        c = _cont_wait(pg, app, "reise", lambda c: len(c["views"]) == 2 and c["views"][1]["layout"] in ({"v": 1}, {}))
        assert [v["name"] for v in c["views"]] == ["Standard", "Kompakt"]
        pg.wait_for_function(MAPOK, timeout=TL)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_views_on_the_overview_are_kept_apart_from_the_trip_page(pw, app):
    _api(app, "reisen", "PUT", {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1}}, {"id": "v1", "name": "Nur Reisen", "layout": {"order": ["reisen"], "hidden": ["serien", "alben"]}}], "active": "v1"})
    pg = _trips_page(pw, app)
    try:
        assert pg.evaluate(RUNITS) == ["reisen"]
        assert pg.locator("#slview").count() == 1
    finally:
        pg.browser_.close()
    assert _api(app, "reise").get("layout") is None and _api(app, "reise").get("container") is None


@pytest.mark.parametrize("page,key,widget", [("trip", "reise", {"id": "w1", "type": "rkmtag", "cfg": {"metric": "h"}}), ("trips", "reisen", {"id": "w1", "type": "rnjahre", "cfg": {"metric": "km"}})])
def test_export_and_import_of_a_view(pw, app, tmp_path, page, key, widget):
    lay = {"v": 1, "order": ["w1"], "widgets": [widget], "hidden": ["stat"] if key == "reise" else ["alben"]}
    _api(app, key, "PUT", {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1}}, {"id": "vt", "name": "Mein Reiselayout", "layout": lay}], "active": "standard"})
    pg = _trip(pw, app) if page == "trip" else _trips_page(pw, app)
    try:
        _edit(pg)
        _open_views(pg)
        with pg.expect_download(timeout=T) as dl:
            pg.locator(".slvws").get_by_role("button", name="Exportieren: Mein Reiselayout", exact=True).click()
        d = dl.value
        assert d.suggested_filename == f"ansicht-{key}-mein-reiselayout.json"
        doc = json.loads(open(d.path(), encoding="utf-8").read())
        assert doc["format"] == "meine-touren-ansicht" and doc["page"] == key and doc["app_version"] == "3.62.1" and list(doc["layouts"]) == [key] and doc["layouts"][key]["widgets"][0]["type"] == widget["type"]
        f = tmp_path / "gut.json"
        f.write_text(json.dumps(doc), encoding="utf-8")
        pg.locator(".slvws").get_by_role("button", name="Importieren …", exact=True).click()
        pg.wait_for_selector("#slimpin", state="attached", timeout=T)
        pg.set_input_files("#slimpin", str(f))
        pg.wait_for_selector(".slimpok", timeout=T)
        assert "Mein Reiselayout" in pg.locator(".slimpres").inner_text() and "1 Baustein" in pg.locator(".slimpres").inner_text()
        pg.locator(".slimpres [data-a=new]").click()
        pg.wait_for_function("() => !document.querySelector('.slimp')", timeout=T)
        pg.wait_for_function("(k) => slViewName(k, SL.view[k]) === 'Mein Reiselayout 2'", arg=key, timeout=T)
        c = _cont_wait(pg, app, key, lambda c: len(c["views"]) == 3)
        assert c["views"][2]["layout"]["widgets"][0]["type"] == widget["type"]
        # eine Datei der anderen Seite wird abgelehnt
        other = {**doc, "page": "reisen" if key == "reise" else "reise"}
        g = tmp_path / "falsch.json"
        g.write_text(json.dumps(other), encoding="utf-8")
        pg.locator(".slvws").get_by_role("button", name="Importieren …", exact=True).click()
        pg.wait_for_selector("#slimpin", state="attached", timeout=T)
        pg.set_input_files("#slimpin", str(g))
        pg.wait_for_selector(".slimperr, .slimpres .bad, .slimpres", timeout=T)
        assert pg.locator(".slimpok").count() == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Betrachter  ------------------------------------------------------------------

def test_viewer_gets_the_default_and_no_edit_mode(pw, app):
    _api(app, "reise", "PUT", {"order": ["touren", "kopf", "kennzahlen", "stat", "flug", "karte", "fotos"], "widgets": [{"id": "wn1", "type": "rkmtag", "cfg": {}}]})
    _api(app, "reisen", "PUT", {"order": ["alben", "reisen", "serien"]})
    pg = _trip(pw, app)
    try:
        assert pg.evaluate(UNITS)[0] == "touren"                                                                                          # der Besitzer sieht sein Layout
        pg.evaluate("ME.user = {role: 'viewer', uid: 9, name: 'Oma'}; document.documentElement.classList.add('viewer')")
        pg.evaluate("route()")
        pg.wait_for_function("() => !!document.querySelector('#trx #tls-touren') && document.querySelector('#trx').dataset.trip && !!document.querySelector('#trpdf')", timeout=TL)
        pg.wait_for_function("() => JSON.stringify([...document.querySelectorAll('#trx #rs-kopf, #trx details.tls')].map(e => e.dataset.tls || 'kopf')) === JSON.stringify(%s)" % json.dumps(STD), timeout=TL)
        assert pg.locator("#slopen").count() == 0 and pg.locator('[data-wtype="rkmtag"]').count() == 0
        assert pg.evaluate("typeof slEdit === 'function' && (slEdit(true), document.querySelectorAll('.slit').length + document.querySelectorAll('#slbar').length)") == 0
        pg.goto(f"{app}/#/trips")
        pg.wait_for_selector("#rsx #tls-reisen", state="attached", timeout=TL)
        pg.wait_for_function("() => JSON.stringify([...document.querySelectorAll('#rsx details.tls')].map(e => e.dataset.tls)) === JSON.stringify(['serien', 'reisen', 'alben'])", timeout=TL)
        assert pg.locator("#slopen").count() == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    assert _api(app, "reise")["layout"]["order"][0] == "touren"                                                                          # nichts wurde überschrieben


# ------------------------------------------------------------------  390 px, hell und dunkel, Kontrast, Englisch, Bilder  ------------------------------------------------------------------

OVER = "() => ({page: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth), cards: [...document.querySelectorAll('#trx > *, #rsx > *')].filter(e => e.getBoundingClientRect().right > document.documentElement.clientWidth + 1).map(e => e.id || e.dataset.tls || e.className)})"
FULL = [{"id": "wk1", "type": "rkennzahl", "cfg": {}}, {"id": "wt1", "type": "rkmtag", "cfg": {}}, {"id": "wd1", "type": "rdiashow", "cfg": {"mode": "random", "view": "grid", "n": 6}}]
FULLN = [{"id": "wn1", "type": "rnzahlen", "cfg": {}}, {"id": "wj1", "type": "rnjahre", "cfg": {}}]


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_mobile_390_trip_page_without_overflow_and_with_contrast(pw, app, scheme):
    for name, doc in (("standard", None), ("angepasst", {"order": ["kopf", "wt1", "wk1", "karte", "kennzahlen", "touren", "stat", "flug", "fotos", "wd1"], "widgets": FULL, "w": {"wk1": "halb", "wt1": "halb", "karte": "halb"}, "closed": ["stat"]})):
        if doc:
            _api(app, "reise", "PUT", doc)
        pg = _trip(pw, app, width=390, height=900, scheme=scheme, dpr=2)
        try:
            if doc:
                pg.wait_for_function("() => document.querySelectorAll('#tlw-wd1 .erb img').length === 6 && !!document.querySelector('#tlw-wt1 svg.slcol rect')", timeout=TL)
            pg.wait_for_function(MAPOK, timeout=TL)
            assert pg.evaluate(OVER) == {"page": 0, "cards": []}, (name, pg.evaluate(OVER))
            c = pg.evaluate(TEXTCONTRAST, "#trx, #trx *")
            assert c["n"] >= 10 and not c["low"], (name, scheme, c["low"][:5])
            _shot(pg, f"reise-{name}-390-{scheme}.png")
            if doc:
                _edit(pg)
                assert pg.evaluate(OVER)["page"] == 0, "Bearbeitungsmodus"
                _shot(pg, f"reise-{name}-bearbeiten-390-{scheme}.png")
        finally:
            pg.browser_.close()
        _api(app, "reise", "DELETE")


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_mobile_390_overview_without_overflow_and_with_contrast(pw, app, scheme):
    for name, doc in (("standard", None), ("angepasst", {"order": ["wn1", "alben", "reisen", "wj1", "serien"], "widgets": FULLN, "w": {"wn1": "halb", "wj1": "halb"}, "closed": ["alben"]})):
        if doc:
            _api(app, "reisen", "PUT", doc)
        pg = _trips_page(pw, app, width=390, height=900, scheme=scheme, dpr=2)
        try:
            if doc:
                pg.wait_for_function("() => !!document.querySelector('#tlw-wn1 .utile') && !!document.querySelector('#tlw-wj1 svg.slcol rect')", timeout=TL)
            assert pg.evaluate(OVER) == {"page": 0, "cards": []}, (name, pg.evaluate(OVER))
            c = pg.evaluate(TEXTCONTRAST, "#rsx, #rsx *")
            assert c["n"] >= 6 and not c["low"], (name, scheme, c["low"][:5])
            _shot(pg, f"reisen-{name}-390-{scheme}.png")
            if doc:
                _edit(pg)
                assert pg.evaluate(OVER)["page"] == 0
                _shot(pg, f"reisen-{name}-bearbeiten-390-{scheme}.png")
        finally:
            pg.browser_.close()
        _api(app, "reisen", "DELETE")


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_desktop_1280_shots(pw, app, scheme):
    for name, doc in (("standard", None), ("angepasst", {"order": ["kopf", "wk1", "wt1", "karte", "touren", "kennzahlen", "stat", "flug", "fotos", "wd1"], "widgets": FULL, "w": {"wk1": "drittel", "wt1": "zweidrittel", "karte": "halb", "touren": "halb"}})):
        if doc:
            _api(app, "reise", "PUT", doc)
        pg = _trip(pw, app, height=1000, scheme=scheme, dpr=1)
        try:
            if doc:
                pg.wait_for_function("() => document.querySelectorAll('#tlw-wd1 .erb img').length === 6 && !!document.querySelector('#tlw-wt1 svg.slcol rect')", timeout=TL)
            pg.wait_for_function(MAPOK, timeout=TL)
            assert pg.evaluate(OVER)["page"] == 0
            _shot(pg, f"reise-{name}-1280-{scheme}.png")
            _edit(pg)
            _shot(pg, f"reise-{name}-bearbeiten-1280-{scheme}.png")
        finally:
            pg.browser_.close()
        _api(app, "reise", "DELETE")
    for name, doc in (("standard", None), ("angepasst", {"order": ["wn1", "wj1", "reisen", "serien", "alben"], "widgets": FULLN, "w": {"wn1": "halb", "wj1": "halb"}})):
        if doc:
            _api(app, "reisen", "PUT", doc)
        pg = _trips_page(pw, app, height=1000, scheme=scheme)
        try:
            if doc:
                pg.wait_for_function("() => !!document.querySelector('#tlw-wn1 .utile') && !!document.querySelector('#tlw-wj1 svg.slcol rect')", timeout=TL)
            _shot(pg, f"reisen-{name}-1280-{scheme}.png")
            _edit(pg)
            _shot(pg, f"reisen-{name}-bearbeiten-1280-{scheme}.png")
        finally:
            pg.browser_.close()
        _api(app, "reisen", "DELETE")


def test_english_texts(pw, app):
    _api(app, "reise", "PUT", {"widgets": FULL[:2]})
    pg = _trip(pw, app, locale="en-US")
    try:
        pg.wait_for_function("() => !!document.querySelector('#tlw-wk1 .utile') && !!document.querySelector('#tlw-wt1 svg.slcol rect')", timeout=TL)
        txt = pg.locator("#trx").inner_text()
        for de in ("Reisetage", "Strecke je Tag", "Stärkster Tag", "Reise-Kennzahlen", "Statistik nach Sportart", "an 6 Tagen"):
            assert de not in txt, de
        assert "Trip days" in txt and "Strongest day" in txt and "Trip key figures" in txt and "Distance per day" in txt, txt[:600]
        pg.wait_for_function("() => /Strongest day: Oct/.test(document.querySelector('#tlw-wt1').textContent) || /Strongest day/.test(document.querySelector('#tlw-wt1').textContent)", timeout=T)
        _edit(pg)
        pg.locator("#slbar [data-a=add]").click()
        pg.wait_for_selector(".slcat .slcard", timeout=T)
        names = pg.locator(".slcat .slcard h3").all_inner_texts()
        assert "Photos" in names and "Trip key figures" in names, names
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    pg = _trips_page(pw, app, locale="en-US")
    try:
        assert "Removed trips" not in pg.locator("#rsx").inner_text() and "Tags & albums" in pg.locator("#rsx").inner_text() and "Mehrtagestouren" not in pg.locator("#rsx").inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_trips_albums_card_has_the_albums(pw, app):
    """3.34.0: „Alben und Tags“ steht in der eigenen Karte (nicht gequetscht unter den Reisen), die Karte „Reisen“ enthält nur die Reisen und keine zweite Überschrift."""
    pg = _trips_page(pw, app)
    try:
        expect(pg.locator("#rnc-alben .tlsb a.otd")).to_have_count(3, timeout=15000)
        assert pg.locator("#rnc-reisen #rnalb").count() == 0 and pg.locator("#rnc-reisen .sec").count() == 0, pg.locator("#rnc-reisen").inner_html()[:300]
        assert pg.locator("#rnc-reisen #tr a.otd").count() == 3
        assert pg.locator("#rnc-alben .tlsb h2").count() == 0
        assert not pg.errors
    finally:
        pg.browser_.close()
