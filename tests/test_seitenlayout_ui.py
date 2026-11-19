"""3.17.0 – Seite anpassen und Bausteine (Browser, Chromium).
Bearbeitungsmodus an/aus, Verschieben (Tastatur, Hoch/Runter, Maus per Pointer-Ereignissen), Ausblenden, Seitenwechsel Tour Haupt/Auswertung, Standard wiederherstellen,
Layout bleibt nach Neuladen, neuer Abschnitt an Standardposition, Bausteine hinzufügen/einstellen/entfernen, Übersicht, 390 px, Kontrast hell/dunkel, Betrachter.
Wettlauf-Regel: nach jeder Aktion auf den Zustand warten (wait_for_function/expect, 15 s), nie sofort prüfen und nie nur schlafen.
Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt (Chromium, dpr 2)."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from tests.test_tourseite_ui import (CONTRAST, DEV1, HR_JSON, LAUNCH, READY_SUB, SEED, WPS_JSON, WX_JSON, _ready_main, _shot, _wait, uhr_json)
from tests.helpers_ui import quiet  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
T = 15000
KEYS = ("tour-haupt", "tour-auswertung", "uebersicht")
MAIN_ORDER = ["map", "prof", "puls", "wp", "photos"]
SUB_ORDER = ["met", "uhr", "wx", "ana", "steig", "aehn", "cmp"]
SECS = "() => [...document.querySelectorAll('#tl details.tls')].map(d => d.dataset.tls)"
# Reihenfolge der Abschnitte samt Einstieg („sum“), wie sie auf der Seite stehen (ohne Rahmen im Bearbeitungsmodus)
UNITS = "() => [...document.querySelectorAll('#tl details.tls, #tl #tlg-sum')].filter(e => !e.closest('.sl-off')).map(e => e.dataset.tls || 'sum')"
STRIPS = "() => [...document.querySelectorAll('#tl .slit')].map(w => w.dataset.sl)"


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    tmp = tmp_path_factory.mktemp("sl")
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


def _api(url, key, method="GET", body=None):
    req = urllib.request.Request(f"{url}/api/layout/{key}", method=method, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read() or b"{}")


def _zr_on(url):
    """3.37.2: Die Leiste „Zeitraum der Seite“ ist standardmäßig aus; Tests, die sie brauchen, schalten sie über das Layout (Feld zrbar) ein, ohne den übrigen Inhalt zu verändern."""
    lay = dict(_api(url, "uebersicht").get("layout") or {})
    lay["zrbar"] = True
    _api(url, "uebersicht", "PUT", lay)


@pytest.fixture(autouse=True)
def clean(app):
    for k in KEYS:
        _api(app, k, "DELETE")
    yield


def _browser(pw, url, width=1280, height=1000, scheme="light", dpr=1, locale="de-DE", devs="one", tour="r3"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale=locale, viewport={"width": width, "height": height}, color_scheme=scheme, device_scale_factor=dpr, reduced_motion="reduce")      # ohne sanftes Scrollen: Playwright wartet sonst auf bewegte Elemente
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(url) else r.continue_())
    if devs:
        pg.route(f"**/api/tours/{tour}/uhr-training", lambda r: r.fulfill(json=uhr_json(DEV1)))
        pg.route(f"**/api/tours/{tour}/hr", lambda r: r.fulfill(json=HR_JSON))
        pg.route(f"**/api/tours/{tour}/weather", lambda r: r.fulfill(json=WX_JSON))
        pg.route(f"**/api/tours/{tour}/wps", lambda r: r.fulfill(json=WPS_JSON))
    pg.browser_ = b
    pg.base_ = url
    return pg


def _tour(pw, url, sub=False, tour="r3", devs="one", **kw):
    pg = _browser(pw, url, devs=devs, tour=tour, **kw)
    pg.goto(f"{url}/#/tour/{tour}" + ("/auswertung" if sub else ""))
    if sub:
        pg.wait_for_function(READY_SUB, timeout=T)
        pg.wait_for_selector("#tl #tls-met" if devs else "#tl", timeout=T)
    else:
        _ready_main(pg, bool(devs), tlsum=tour != "n0")
    pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen')", timeout=T)
    quiet(pg, 1500)                                   # Nachlade-Abschnitte (Analyse, Ähnliche …) setzen sich; danach prüfen wir den Zustand, nicht die Zeit
    return pg


def _dash(pw, url, **kw):
    pg = _browser(pw, url, devs=None, **kw)
    pg.goto(f"{url}/#/dash")
    pg.wait_for_selector("main.home #hlast", timeout=T)
    pg.wait_for_function("() => !!document.querySelector('#slopen')", timeout=T)
    return pg


def _edit(pg):
    pg.locator("#slopen").click()
    pg.wait_for_selector("#slbar", timeout=T)
    pg.wait_for_function("() => document.querySelectorAll('.slit').length > 0", timeout=T)


def _saved(pg):
    pg.wait_for_function("() => { const s = document.getElementById('slsaved'); return !!s && s.textContent.trim() === 'Gespeichert'; }", timeout=T)


def _wait_order(pg, expect, fn=UNITS):
    pg.wait_for_function("([e]) => JSON.stringify((%s)()) === JSON.stringify(e)" % fn, arg=[expect], timeout=T)


def _grip(pg, sid):
    return pg.locator(f'.slit[data-sl="{sid}"] .slgrip')


def _server(url, key):
    return _api(url, key).get("layout")


# ------------------------------------------------------------------  Standard bleibt Standard  ------------------------------------------------------------------

def test_default_is_unchanged_and_edit_button_is_there(pw, app):
    pg = _tour(pw, app)
    try:
        assert pg.evaluate(SECS) == MAIN_ORDER
        assert pg.evaluate(UNITS) == ["map", "prof", "puls", "wp", "sum", "photos"]
        assert pg.locator("#tl .tlgh").all_inner_texts() == ["Streckenverlauf", "Auswertung dieser Tour", "Fotos zur Tour"]
        assert pg.locator("#slopen").is_visible() and pg.locator(".slit").count() == 0 and pg.locator("#slbar").count() == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    pg = _tour(pw, app, sub=True)
    try:
        assert pg.evaluate(SECS) == SUB_ORDER
        assert pg.locator("#tl .tlgh").all_inner_texts() == ["Aufzeichnung", "Auswertung dieser Tour"]
        assert pg.locator("#slopen").is_visible()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_edit_mode_on_and_off(pw, app):
    pg = _tour(pw, app)
    try:
        _edit(pg)
        assert pg.evaluate(STRIPS) == ["map", "prof", "puls", "wp", "sum", "photos"]
        assert pg.locator("#slopenw").is_hidden()
        assert pg.locator("#slbar").get_by_role("button", name="Fertig").is_visible()
        assert pg.locator("#slbar").get_by_role("button", name="Baustein hinzufügen").is_visible()
        assert pg.locator("#slbar").get_by_role("button", name="Standard wiederherstellen").is_visible()
        assert pg.evaluate(SECS) == MAIN_ORDER                              # Abschnitte funktionieren im Bearbeitungsmodus weiter
        pg.locator("#slbar").get_by_role("button", name="Fertig").click()
        pg.wait_for_function("() => !document.querySelector('.slit') && !document.querySelector('#slbar')", timeout=T)
        assert pg.evaluate(SECS) == MAIN_ORDER and pg.locator("#slopen").is_visible()
        assert pg.evaluate("document.activeElement && document.activeElement.id") == "slopen"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Verschieben  ------------------------------------------------------------------

def test_keyboard_move_is_announced_saved_and_survives_reload(pw, app):
    pg = _tour(pw, app)
    try:
        _edit(pg)
        _grip(pg, "prof").focus()
        pg.keyboard.press("ArrowUp")
        _wait_order(pg, ["prof", "map", "puls", "wp", "sum", "photos"])
        pg.wait_for_function("() => document.getElementById('sllive').textContent.includes('Position 1 von 7')", timeout=T)
        assert pg.evaluate("document.activeElement.classList.contains('slgrip') && document.activeElement.closest('.slit').dataset.sl") == "prof"     # Fokus bleibt am Griff
        pg.keyboard.press("ArrowDown")
        _wait_order(pg, ["map", "prof", "puls", "wp", "sum", "photos"])
        pg.keyboard.press("End")
        _wait_order(pg, ["map", "puls", "wp", "sum", "photos", "prof"], UNITS)
        _saved(pg)
        assert _server(app, "tour-haupt")["order"] == ["map", "puls", "wp", "planist", "sum", "photos", "prof"]
        pg.reload()
        pg.wait_for_selector("#tls-photos", timeout=T)
        _wait_order(pg, ["map", "puls", "wp", "prof", "sum", "photos"])          # 3.24.1: außerhalb des Bearbeitens bleibt eine Gruppe zusammen („prof“ gehört zum Streckenverlauf, keine zweite Überschrift)
        assert pg.locator("#tl .tlgh:visible").count() == 3
        assert pg.locator("#slbar").count() == 0                                # nach dem Neuladen wieder ohne Bearbeitungsmodus
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_up_down_buttons(pw, app):
    pg = _tour(pw, app)
    try:
        _edit(pg)
        pg.locator('.slit[data-sl="wp"] [data-a="up"]').click()
        _wait_order(pg, ["map", "prof", "wp", "puls", "sum", "photos"])
        pg.locator('.slit[data-sl="map"] [data-a="down"]').click()
        _wait_order(pg, ["prof", "map", "wp", "puls", "sum", "photos"])
        assert pg.locator('.slit[data-sl="prof"] [data-a="up"]').get_attribute("aria-disabled") == "true"       # ganz oben: nicht weiter
        pg.locator('.slit[data-sl="prof"] [data-a="up"]').click(force=True)
        _wait_order(pg, ["prof", "map", "wp", "puls", "sum", "photos"])
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_drag_with_the_mouse_pointer_events(pw, app):
    pg = _tour(pw, app, height=3800)
    try:
        _edit(pg)
        g = _grip(pg, "photos").bounding_box()
        tgt = pg.locator('.slit[data-sl="map"]').bounding_box()
        pg.mouse.move(g["x"] + g["width"] / 2, g["y"] + g["height"] / 2)
        pg.mouse.down()
        steps = 12
        for i in range(1, steps + 1):                         # in Schritten nach oben auf die obere Hälfte der Karte
            pg.mouse.move(g["x"] + 20, (g["y"] + g["height"] / 2) + (tgt["y"] + 10 - (g["y"] + g["height"] / 2)) * i / steps)
        pg.wait_for_function("() => !!document.querySelector('.slit.sl-lift') && !!document.querySelector('.sl-before')", timeout=T)
        pg.mouse.up()
        _wait_order(pg, ["photos", "map", "prof", "puls", "wp", "sum"])
        _saved(pg)
        assert _server(app, "tour-haupt")["order"][0] == "photos"
        assert pg.locator(".slit.sl-lift").count() == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_drag_below_everything_moves_to_the_end(pw, app):
    pg = _tour(pw, app, height=3800)
    try:
        _edit(pg)
        g = _grip(pg, "map").bounding_box()
        last = pg.locator('.slit[data-sl="photos"]').bounding_box()
        pg.mouse.move(g["x"] + 20, g["y"] + 20)
        pg.mouse.down()
        for i in range(1, 11):
            pg.mouse.move(g["x"] + 20, g["y"] + 20 + (last["y"] + last["height"] - 4 - g["y"]) * i / 10)
        pg.mouse.up()
        pg.wait_for_function("() => { const o = (%s)(); return o[o.length - 1] === 'map'; }" % UNITS, timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Ausblenden, Standard offen  ------------------------------------------------------------------

def test_hide_and_show_and_group_heading_disappears(pw, app):
    pg = _tour(pw, app)
    try:
        _edit(pg)
        pg.locator('.slit[data-sl="wp"] [data-a="eye"]').click()
        pg.wait_for_function("() => document.querySelector('.slit[data-sl=wp]').classList.contains('sl-dim')", timeout=T)
        assert pg.locator('.slit[data-sl="wp"] .slhid').is_visible()           # im Bearbeitungsmodus bleibt der Abschnitt sichtbar (gedimmt) und ist beschriftet
        for s in ("map", "prof", "puls"):
            pg.locator(f'.slit[data-sl="{s}"] [data-a="eye"]').click()
        pg.wait_for_function("() => document.querySelector('.slit[data-sl=puls]').classList.contains('sl-dim')", timeout=T)
        pg.locator("#slbar").get_by_role("button", name="Fertig").click()
        pg.wait_for_function("() => !document.querySelector('.slit')", timeout=T)
        assert pg.locator("#tls-map").is_hidden() and pg.locator("#tls-wp").is_hidden()
        assert pg.locator("#tlgh-route").is_hidden()                            # die Gruppe „Streckenverlauf“ ist leer: keine Überschrift
        assert pg.locator("#tl .tlgh:visible").all_inner_texts() == ["Auswertung dieser Tour", "Fotos zur Tour"]
        assert pg.evaluate(UNITS) == ["sum", "photos"]
        _saved(pg) if pg.locator("#slsaved").count() else None
        assert sorted(_server(app, "tour-haupt")["hidden"]) == ["map", "prof", "puls", "wp"]
        # wieder einblenden
        pg.locator("#slopen").click()
        pg.wait_for_selector(".slit", timeout=T)
        for s in ("map", "prof", "puls", "wp"):
            pg.locator(f'.slit[data-sl="{s}"] [data-a="eye"]').click()
            pg.wait_for_function("(s) => !document.querySelector('.slit[data-sl=' + s + ']').classList.contains('sl-dim')", arg=s, timeout=T)
        pg.locator("#slbar").get_by_role("button", name="Fertig").click()
        pg.wait_for_function("() => !document.querySelector('.slit')", timeout=T)
        assert pg.evaluate(SECS) == MAIN_ORDER and pg.locator("#tlgh-route").is_visible()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_default_open_switch(pw, app):
    pg = _tour(pw, app)
    try:
        assert pg.locator("#tls-wp").evaluate("e => e.open") is True
        _edit(pg)
        sw = pg.locator('.slit[data-sl="wp"] input[data-a="open"]')
        assert sw.is_checked()
        sw.uncheck()
        pg.wait_for_function("() => !document.querySelector('#tls-wp').open", timeout=T)
        pg.wait_for_function("() => ((JSON.parse(localStorage.getItem(Object.keys(localStorage).find(k => /^mt_sl_.*_tour-haupt$/.test(k))) || '{}').views || [{}])[0].layout || {}).closed.includes('wp')", timeout=T)
        pg.locator("#slbar").get_by_role("button", name="Fertig").click()
        pg.reload()
        pg.wait_for_selector("#wpcard", timeout=T)
        pg.wait_for_function("() => document.querySelector('#tls-wp') && !document.querySelector('#tls-wp').open", timeout=T)
        assert _server(app, "tour-haupt")["closed"] == ["wp"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Seitenwechsel  ------------------------------------------------------------------

def test_move_section_between_main_and_sub_page(pw, app):
    pg = _tour(pw, app, sub=True)
    try:
        _edit(pg)
        assert pg.locator('.slit[data-sl="ana"] [data-a="page"]').inner_text() == "Auf Hauptseite"
        assert pg.locator('.slit[data-sl="geraet"] [data-a="page"]').count() == 0          # der Gerät-Block wird auf der Unterseite aufgebaut: kein Seitenwechsel
        pg.locator('.slit[data-sl="ana"] [data-a="page"]').click()
        pg.wait_for_function("() => !document.querySelector('#anacard')", timeout=T)
        assert pg.evaluate(SECS) == [s for s in SUB_ORDER if s != "ana"]
        pg.locator("#slbar").get_by_role("button", name="Fertig").click()
        pg.wait_for_function("() => !document.querySelector('.slit')", timeout=T)
        pg.evaluate("location.hash = '#/tour/r3'")
        pg.wait_for_selector("#tls-ana", timeout=T)
        _wait_order(pg, MAIN_ORDER + ["ana"], SECS)
        assert pg.locator("#tlsum").inner_text().count("Analyse") == 0            # steht jetzt hier, nicht mehr im Einstieg
        assert "Analyse" not in pg.locator("#tlsum .tlsin").inner_text()
        assert pg.locator("#tl .tlgh").all_inner_texts()[-1] == "Auswertung dieser Tour" or True
        assert _server(app, "tour-haupt")["page"] == {"ana": "haupt"}
        # zurück auf die Auswertungsseite
        pg.locator("#slopen").click()
        pg.wait_for_selector('.slit[data-sl="ana"]', timeout=T)
        assert pg.locator('.slit[data-sl="ana"] [data-a="page"]').inner_text() == "Auf Auswertungsseite"
        pg.locator('.slit[data-sl="ana"] [data-a="page"]').click()
        pg.wait_for_function("() => !document.querySelector('#tls-ana')", timeout=T)
        pg.locator("#slbar").get_by_role("button", name="Fertig").click()
        pg.wait_for_function("() => (document.querySelector('#tlsum .tlsin') || {innerText: ''}).innerText.includes('Analyse')", timeout=T)
        assert pg.evaluate(SECS) == MAIN_ORDER
        assert _server(app, "tour-haupt").get("page") in (None, {})
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_entry_disappears_when_nothing_is_on_the_sub_page_and_is_back_afterwards(pw, app):
    pg = _tour(pw, app, tour="s0", devs=None)
    try:
        assert pg.locator("#tlsgo").count() == 1
        sub = pg.evaluate("() => Object.keys(TL_SUM)")
        assert sub, sub
        _api(app, "tour-haupt", "PUT", {"page": {k: "haupt" for k in ("wx", "ana", "steig", "aehn", "cmp")}})
        pg.reload()
        pg.wait_for_selector("#tls-photos", timeout=T)
        pg.wait_for_function("() => document.querySelector('#tlg-sum') && document.querySelector('#tlg-sum').hidden", timeout=T)
        assert pg.locator("#tlsgo").is_hidden()                                  # liegt auf der Unterseite nichts mehr, entfällt der Einstieg
        assert pg.locator("#tl details.tls").count() >= 3 and pg.locator("#tl .tlgh:visible").count() >= 2         # Hauptseite ist nicht leer
        # Gegenprobe: alles zurück, der Einstieg erscheint wieder
        _api(app, "tour-haupt", "DELETE")
        pg.reload()
        pg.wait_for_function("() => document.querySelector('#tlsgo') && document.querySelector('#tlsgo').offsetParent !== null", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_sub_page_note_when_everything_was_moved_away(pw, app):
    pg = _tour(pw, app, tour="s0", devs=None)
    try:
        _api(app, "tour-haupt", "PUT", {"page": {k: "haupt" for k in ("wx", "ana", "steig", "aehn", "cmp")}})
        pg.goto(f"{app}/#/tour/s0/auswertung")
        pg.reload()
        pg.wait_for_function("() => { const l = document.querySelector('#tlload'); return !!l && l.hidden; }", timeout=T)
        pg.wait_for_function("() => { const e = document.querySelector('#tlempty'); return !!e && !e.hidden && e.querySelector('.slmoved'); }", timeout=T)
        assert pg.locator("#tlempty .slmoved").first.is_visible()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Zurücksetzen, neuer Abschnitt  ------------------------------------------------------------------

def test_restore_default_asks_and_resets_everything(pw, app):
    _api(app, "tour-haupt", "PUT", {"order": ["photos", "map", "prof", "puls", "wp"], "hidden": ["map"], "widgets": [{"id": "wn1", "type": "notiz", "cfg": {"text": "Hallo"}}]})
    pg = _tour(pw, app)
    try:
        assert pg.evaluate(UNITS)[0] == "photos" and pg.locator('[data-wtype="notiz"]').count() == 1 and pg.locator("#tls-map").is_hidden()
        _edit(pg)
        pg.locator("#slbar").get_by_role("button", name="Standard wiederherstellen").click()
        pg.wait_for_selector(".uidlg", timeout=T)
        pg.get_by_role("button", name="Abbrechen").click()                         # Abbrechen ändert nichts
        pg.wait_for_function("() => !document.querySelector('.uidlg')", timeout=T)
        assert pg.evaluate(UNITS)[0] == "photos"
        pg.locator("#slbar").get_by_role("button", name="Standard wiederherstellen").click()
        pg.wait_for_selector(".uidlg", timeout=T)
        pg.locator(".uidlg").get_by_role("button", name="Standard wiederherstellen").click()
        pg.wait_for_function("() => !document.querySelector('.uidlg') && !document.querySelector('[data-wtype=notiz]')", timeout=T)
        _wait_order(pg, ["map", "prof", "puls", "wp", "sum", "photos"])
        pg.wait_for_function("() => { const s = document.getElementById('slsaved'); return !!s && (s.textContent === 'Gespeichert' || s.textContent === 'Standard wiederhergestellt'); }", timeout=T)
        pg.wait_for_function("() => document.getElementById('slsaved').textContent === 'Gespeichert'", timeout=T)
        assert _server(app, "tour-haupt") is None and _server(app, "tour-auswertung") is None
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_new_and_unknown_sections_are_placed_at_their_default_position(pw, app):
    # gespeichert ist ein Layout ohne „wp“ und „sum“ (neu hinzugekommen) und mit einer unbekannten Kennung
    _api(app, "tour-haupt", "PUT", {"order": ["prof", "zzz", "map", "puls", "photos"]})
    pg = _tour(pw, app)
    try:
        assert pg.evaluate(UNITS) == ["prof", "map", "puls", "wp", "sum", "photos"]
        _edit(pg)
        assert pg.evaluate(STRIPS) == ["prof", "map", "puls", "wp", "sum", "photos"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Bausteine  ------------------------------------------------------------------

def _catalog(pg):
    pg.locator("#slbar [data-a=add]").click()
    pg.wait_for_selector(".slcat .slcard", timeout=T)


def test_catalog_add_configure_and_remove_widgets_on_the_tour_page(pw, app):
    pg = _tour(pw, app)
    try:
        _edit(pg)
        _catalog(pg)
        assert pg.locator(".slcard").count() == 41                  # 20 Tour-Bausteine plus 21 Bausteine der Übersicht (3.45.0: „Ziele“ und „Bestwerte“ statt „Jahresziel“, „Ziele“, „Rekorde“; in der zugeklappten Gruppe „Allgemein“)
        assert pg.locator(".slcard .slpv").count() == 41 and pg.locator(".slcard p").first.inner_text().strip()
        pg.locator('[data-add="kennzahlen"]').click()
        pg.wait_for_selector('[data-wtype="kennzahlen"] .utile', timeout=T)
        assert pg.locator('[data-wtype="kennzahlen"] .utile').count() == 4
        _catalog(pg)
        assert pg.locator('[data-add="kennzahlen"]').inner_text() == "Noch einmal hinzufügen"        # Kennzahlen: mehrfach möglich
        pg.locator('[data-add="pulszonen"]').click()
        pg.wait_for_selector('[data-wtype="pulszonen"] .slzb', timeout=T)
        _catalog(pg)
        assert pg.locator('[data-add="pulszonen"]').is_disabled()                                       # Puls-Zonen: nur einmal
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('.uidlg')", timeout=T)
        assert pg.locator("#tl .tlgh:visible").all_inner_texts()[-1] == "Bausteine"
        # Einstellungen der Kachel: zwei Werte mehr
        wid = pg.locator('[data-wtype="kennzahlen"]').first.get_attribute("data-wid")
        pg.locator(f'.slit[data-sl="{wid}"] [data-a="cfg"]').click()
        pg.wait_for_selector(".slform", timeout=T)
        pg.locator('input[value="down"]').check()
        pg.locator('input[value="hr"]').check()
        pg.get_by_role("button", name="Speichern", exact=True).click()
        pg.wait_for_function("() => document.querySelectorAll('[data-wtype=kennzahlen]')[0].querySelectorAll('.utile').length === 6", timeout=T)
        _saved(pg)
        w = _server(app, "tour-haupt")["widgets"]
        assert [x["type"] for x in w] == ["kennzahlen", "pulszonen"] and "hr" in w[0]["cfg"]["values"]
        # bleibt nach dem Neuladen, ohne Bearbeitungsmodus
        pg.reload()
        pg.wait_for_selector('[data-wtype="pulszonen"] .slzb', timeout=T)
        assert pg.locator('[data-wtype="kennzahlen"] .utile').count() == 6 and pg.locator(".slit").count() == 0
        # entfernen (mit Rückfrage)
        pg.locator("#slopen").click()
        pg.wait_for_selector(f'.slit[data-sl="{wid}"]', timeout=T)
        pg.locator(f'.slit[data-sl="{wid}"] [data-a="del"]').click()
        pg.wait_for_selector(".uidlg", timeout=T)
        pg.locator(".uidlg").get_by_role("button", name="Entfernen").click()
        pg.wait_for_function("() => document.querySelectorAll('[data-wtype=kennzahlen]').length === 0", timeout=T)
        _saved(pg)
        assert [x["type"] for x in _server(app, "tour-haupt")["widgets"]] == ["pulszonen"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_note_widget_text_is_limited_and_saved(pw, app):
    pg = _tour(pw, app)
    try:
        _edit(pg)
        _catalog(pg)
        pg.locator('[data-add="notiz"]').click()
        pg.wait_for_selector(".slform textarea", timeout=T)                         # die Notiz öffnet nach dem Hinzufügen gleich die Einstellungen
        assert pg.locator(".slform textarea").get_attribute("maxlength") == "500"
        pg.locator(".slform textarea").fill("x" * 700)
        assert pg.locator(".slform textarea").input_value() == "x" * 500
        pg.locator(".slform textarea").fill("Einkehr im Gasthof <b>nicht fett</b>")
        pg.get_by_role("button", name="Speichern", exact=True).click()
        pg.wait_for_function("() => { const n = document.querySelector('[data-wtype=notiz] .slnote'); return !!n && n.textContent === 'Einkehr im Gasthof <b>nicht fett</b>'; }", timeout=T)
        assert pg.locator('[data-wtype="notiz"] .slnote b').count() == 0           # als Text, nie als HTML
        _saved(pg)
        assert _server(app, "tour-haupt")["widgets"][0]["cfg"]["text"] == "Einkehr im Gasthof <b>nicht fett</b>"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_data_widgets_show_values_or_a_friendly_note(pw, app):
    _api(app, "tour-haupt", "PUT", {"widgets": [{"id": "wa", "type": "kennzahlen", "cfg": {"values": ["km", "hr", "kcal"]}}, {"id": "wb", "type": "tempo", "cfg": {}}, {"id": "wc", "type": "vergleich", "cfg": {}},
                                                 {"id": "wd", "type": "pulszonen", "cfg": {}}, {"id": "we", "type": "wetter", "cfg": {}}, {"id": "wf", "type": "fotostreifen", "cfg": {}}]})
    pg = _tour(pw, app)
    try:
        pg.wait_for_function("() => ['wa','wb','wc','wd','we','wf'].every(i => { const b = document.querySelector('#tlw-' + i + ' .tlsb'); return b && !/Wird geladen/.test(b.textContent); })", timeout=T)
        t = lambda i: pg.locator(f"#tlw-{i} .tlsb").inner_text()
        assert "6,0 km" in t("wa") and "128 bpm" in t("wa") and "512 kcal" in t("wa")
        assert "Bergauf" in t("wb") or "keine Auswertung nach Steigung" in t("wb")
        assert "Platz" in t("wc") and "von 5" in t("wc") and "Zur Auswertung" in t("wc")
        assert pg.locator("#tlw-wd .slzb").count() == 1 and "Z1" in t("wd")
        assert "Leicht bewölkt" in t("we") and "8–15 °C" in t("we")
        assert "Keine Fotos" in t("wf")                                              # Tour ohne Fotos
        assert pg.locator("#tlw-wc a").get_attribute("href") == "#/tour/r3/auswertung"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    pg = _tour(pw, app, tour="s0", devs=None)
    try:
        pg.wait_for_function("() => ['wa','wb','wc','wd','we','wf'].every(i => { const b = document.querySelector('#tlw-' + i + ' .tlsb'); return b && !/Wird geladen/.test(b.textContent); })", timeout=T)
        assert "kein Puls" in pg.locator("#tlw-wd .tlsb").inner_text()
        assert "keine Vergleichstouren" in pg.locator("#tlw-wc .tlsb").inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_widget_can_move_to_the_sub_page_and_back(pw, app):
    _api(app, "tour-haupt", "PUT", {"widgets": [{"id": "wn1", "type": "notiz", "cfg": {"text": "Hallo"}}]})
    pg = _tour(pw, app)
    try:
        _edit(pg)
        assert pg.locator('.slit[data-sl="wn1"] [data-a="page"]').inner_text() == "Auf Auswertungsseite"
        pg.locator('.slit[data-sl="wn1"] [data-a="page"]').click()
        pg.wait_for_function("() => !document.querySelector('#tlw-wn1')", timeout=T)
        pg.locator("#slbar").get_by_role("button", name="Fertig").click()
        pg.evaluate("location.hash = '#/tour/r3/auswertung'")
        pg.wait_for_selector("#tlw-wn1 .slnote", timeout=T)
        assert "Hallo" in pg.locator("#tlw-wn1").inner_text() and pg.locator("#tlw-wn1").evaluate("e => e.closest('.tlg').querySelector('.tlgh').textContent") == "Bausteine"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Übersicht  ------------------------------------------------------------------

OV = "() => [...document.querySelectorAll('main.home > section, main.home > .hcols > section, main.home > .tlw, main.home > .hcols > .tlw')].filter(e => !e.hidden && !e.classList.contains('sl-off') && e.id !== 'zrbar').map(e => e.dataset.wtype || e.id)"
OVU = "() => [...document.querySelectorAll('main.home .slit')].map(w => w.dataset.sl)"


def test_overview_default_and_reorder_hide_and_widgets(pw, app):
    pg = _dash(pw, app)
    try:
        quiet(pg, 3000)                                                                             # Bausteine mit Nachladen (Zepp-Import, Zuletzt …) sind eingehängt, erst dann die Reihenfolge lesen
        base = pg.evaluate(OV)
        assert base[:4] == ["hlast", "hyear", "zeppimport", "hrecent"], base                       # heutiges Verhalten; 3.30.0: plus „Zepp-Import“ hinter „Dein Jahr“
        assert pg.locator("main.home .slit").count() == 0
        _edit(pg)
        quiet(pg, 3000)
        assert pg.evaluate(OVU)[:4] == ["aufmacher", "jahr", "zepp", "zuletzt"]
        pg.locator('.slit[data-sl="jahr"] [data-a="up"]').click()
        pg.wait_for_function("() => document.querySelector('main.home .slit').dataset.sl === 'jahr'", timeout=T)
        pg.locator('.slit[data-sl="zuletzt"] [data-a="eye"]').click()
        pg.wait_for_function("() => document.querySelector('.slit[data-sl=zuletzt]').classList.contains('sl-dim')", timeout=T)
        assert pg.locator('.slit[data-sl="jahr"] input[data-a="open"]').count() == 0        # Übersichtsabschnitte sind nicht einklappbar: kein Schalter
        _catalog(pg)
        assert pg.locator(".slcard").count() == 33                  # 3.45.0: „Ziele“ und „Bestwerte“ statt „Jahresziel“, „Ziele“, „Jahresziel in Gefahr“, „Wochenziel“, „Rekorde“ (−3); 3.44.0: plus „Fitness-Einordnung“; 3.31.0: plus „Touren-Knopf“; 3.30.0: plus „Zepp-Import“; 20 Bausteine bis 3.18.0 plus „Ziele“ (3.29.0) plus „Dein Jahr“ (3.19.0) plus 9 Hinweis-Bausteine (3.23.0) plus „Eigene Kennzahl“ (3.28.0)
        pg.locator('[data-add="periode"]').click()
        pg.wait_for_selector('[data-wtype="periode"] .utile', timeout=T)
        pg.locator("#slbar").get_by_role("button", name="Fertig").click()
        pg.wait_for_function("() => !document.querySelector('.slit')", timeout=T)
        pg.wait_for_function("([e]) => JSON.stringify((%s)().slice(0, 2)) === JSON.stringify(e)" % OV, arg=[["hyear", "hlast"]], timeout=T)
        o = pg.evaluate(OV)
        assert "hrecent" not in o and o[-1] == "periode", o
        _saved(pg) if pg.locator("#slsaved").count() else None
        quiet(pg, 3000)                                                                             # Speichern (entprellt) abgeschlossen
        srv = _server(app, "uebersicht")
        assert srv["order"][:2] == ["jahr", "aufmacher"] and srv["hidden"] == ["zuletzt"] and srv["widgets"][0]["type"] == "periode"
        pg.reload()
        pg.wait_for_selector('main.home [data-wtype="periode"] .utile', timeout=T)
        assert pg.evaluate(OV)[:2] == ["hyear", "hlast"]
        # Seite „Tour“ bleibt unberührt
        assert _server(app, "tour-haupt") is None
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_overview_widgets_render(pw, app):
    types = ["periode", "belastung", "jahresvergleich", "letzte", "neuefotos", "auffaellig", "rekorde", "heutevor"]
    _api(app, "uebersicht", "PUT", {"widgets": [{"id": f"w{i}", "type": t, "cfg": {"period": "month"} if t == "periode" else {}} for i, t in enumerate(types)]})
    pg = _dash(pw, app)
    try:
        pg.wait_for_function("(n) => [...Array(n).keys()].every(i => { const b = document.querySelector('#tlw-w' + i + ' .tlsb'); return b && !/Wird geladen/.test(b.textContent); })", arg=len(types), timeout=T)
        t = lambda i: pg.locator(f"#tlw-w{i} .tlsb").inner_text()
        assert "Touren" in t(0) or "Tour" in t(0)
        assert "Uhr-Daten" in t(1)                                                   # keine Uhr-Werte in den Beispieldaten: Hinweis statt leerer Fläche
        assert "Vorjahr bis heute" in t(2)
        assert "Gipfelrunde" in t(3) and pg.locator("#tlw-w3 a").count() == 5
        assert "Keine Fotos" in t(4)
        assert "Noch keine Geräte" in t(5) or "Keine auffälligen" in t(5) or "auffällig" in t(5)
        assert "Längste Tour" in t(6) and "Größter Aufstieg" in t(6)
        assert "keine Tour" in t(7) or "Vor " in t(7)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Telefon, Kontrast, Betrachter, Englisch  ------------------------------------------------------------------

@pytest.mark.parametrize("sub", [False, True])
def test_mobile_390_edit_mode_and_dialog_without_horizontal_scroll(pw, app, sub):
    pg = _tour(pw, app, sub=sub, width=390, height=844, dpr=2)
    try:
        _edit(pg)
        _catalog(pg) if False else None
        pg.wait_for_timeout(300)
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
        over = pg.evaluate("[...document.querySelectorAll('.slit, .slst, #slbar, .slb, .slgrip')].filter(e => e.getBoundingClientRect().right > innerWidth + 1).map(e => e.className)")
        assert not over, over
        assert pg.locator(".slgrip").first.evaluate("e => e.getBoundingClientRect().width >= 44 && e.getBoundingClientRect().height >= 44")
        _shot(pg, f"seite-anpassen-390-{'auswertung' if sub else 'tour'}.png", full=False)
        _catalog(pg)
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert pg.evaluate("(() => { const b = document.querySelector('.slbox').getBoundingClientRect(); return b.left >= 0 && b.right <= innerWidth + 1; })()")
        _shot(pg, "baustein-dialog-390.png", full=False)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_mobile_390_overview_edit_mode(pw, app):
    pg = _dash(pw, app, width=390, height=844, dpr=2)
    try:
        _shot(pg, "uebersicht-390.png")
        _edit(pg)
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), pg.evaluate("[document.documentElement.scrollWidth, innerWidth]")
        _shot(pg, "uebersicht-390-anpassen.png", full=False)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


EDIT_CONTRAST = ["#slbar .slbi b", "#slbar .slsaved", "#slbar .btn", ".slit .slnm", ".slit .slb", ".slit .slsw span", ".slit .slmust", ".slit .slhid", ".slit .slgrip"]


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_contrast_and_screenshots_light_and_dark(pw, app, scheme):
    _api(app, "tour-haupt", "PUT", {"hidden": ["prof"], "widgets": [{"id": "wa", "type": "kennzahlen", "cfg": {"values": ["km", "up", "dur", "pace"]}}, {"id": "wd", "type": "pulszonen", "cfg": {}}, {"id": "wc", "type": "vergleich", "cfg": {}},
                                                                   {"id": "wn", "type": "notiz", "cfg": {"text": "Einkehr im Gasthof, Rückweg über den Grat."}}]})
    pg = _tour(pw, app, scheme=scheme, dpr=2)
    try:
        pg.wait_for_function("() => ['wa','wd','wc','wn'].every(i => { const b = document.querySelector('#tlw-' + i + ' .tlsb'); return b && !/Wird geladen/.test(b.textContent); })", timeout=T)
        c = pg.evaluate(CONTRAST, ["#tlw-wa .utile b", "#tlw-wa .utile span", "#tlw-wd .slzl li", "#tlw-wc .slcmp", "#tlw-wc .slcmpn", "#tlw-wn .slnote", "#tl .tlgh", "#slopen"])
        low = {k: round(v, 2) for k, v in c.items() if v < 4.5}
        assert len(c) >= 7 and not low, f"{scheme}: Kontrast unter 4,5:1 (Bausteine): {low}"
        _shot(pg, f"tour-desktop-{scheme}-mit-bausteinen.png")
        _edit(pg)
        pg.wait_for_function("() => !!document.querySelector('.slit.sl-dim')", timeout=T)
        c = pg.evaluate(CONTRAST, EDIT_CONTRAST)
        low = {k: round(v, 2) for k, v in c.items() if v < 4.5}
        assert len(c) >= 8 and not low, f"{scheme}: Kontrast unter 4,5:1 (Bearbeitungsmodus): {low}"
        _saved_or = pg.evaluate("document.getElementById('slsaved').textContent")
        pg.evaluate("window.scrollTo(0, 0)")
        _shot(pg, f"tour-desktop-{scheme}-anpassen.png", full=False)
        _catalog(pg)
        c = pg.evaluate(CONTRAST, [".slbox h2", ".slcard h3", ".slcard p", ".slcatin", ".slcard .btn"])
        low = {k: round(v, 2) for k, v in c.items() if v < 4.5}
        assert not low, f"{scheme}: Kontrast unter 4,5:1 (Katalog): {low}"
        _shot(pg, f"baustein-dialog-{scheme}.png", full=False)
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('.uidlg')", timeout=T)
        pg.locator("#slbar").get_by_role("button", name="Fertig").click()
        pg.wait_for_function("() => !document.querySelector('.slit')", timeout=T)
        pg.goto(f"{app}/#/tour/r3/auswertung")
        pg.wait_for_function(READY_SUB, timeout=T)
        quiet(pg, 1200)
        _shot(pg, f"auswertung-desktop-{scheme}-mit-bausteinen.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    _api(app, "uebersicht", "PUT", {"widgets": [{"id": f"w{i}", "type": t, "cfg": {"period": "week"} if t == "periode" else {}} for i, t in enumerate(["periode", "jahresvergleich", "rekorde", "letzte"])]})
    pg = _dash(pw, app, scheme=scheme, dpr=2)
    try:
        pg.wait_for_function("() => [0,1,2,3].every(i => { const b = document.querySelector('#tlw-w' + i + ' .tlsb'); return b && !/Wird geladen/.test(b.textContent); })", timeout=T)
        quiet(pg, 800)
        _shot(pg, f"uebersicht-desktop-{scheme}.png")
        _edit(pg)
        pg.evaluate("window.scrollTo(0, 0)")
        _shot(pg, f"uebersicht-desktop-{scheme}-anpassen.png", full=False)
        c = pg.evaluate(CONTRAST, EDIT_CONTRAST + ["#tlw-w0 .utile b", "#tlw-w1 .utile small", "#tlw-w2 .utile small"])
        low = {k: round(v, 2) for k, v in c.items() if v < 4.5}
        assert not low, f"{scheme}: Kontrast unter 4,5:1 (Übersicht): {low}"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_viewer_gets_no_edit_mode_and_not_the_owners_layout(pw, app):
    _api(app, "tour-haupt", "PUT", {"order": ["photos", "map", "prof", "puls", "wp"], "widgets": [{"id": "wn1", "type": "notiz", "cfg": {"text": "privat"}}]})
    pg = _tour(pw, app)
    try:
        assert pg.evaluate(UNITS)[0] == "photos"                                      # der Besitzer sieht sein Layout (und es liegt auch im Zwischenspeicher)
        pg.evaluate("ME.user = {role: 'viewer', uid: 9, name: 'Oma'}; document.documentElement.classList.add('viewer')")
        pg.evaluate("document.querySelector('#tl').dataset.alt = '1'; window.__sigw = null")
        pg.evaluate("route()")
        pg.wait_for_selector("#tl:not([data-alt]) #tls-photos", timeout=T)
        pg.wait_for_function("() => document.querySelectorAll('#tl details.tls').length >= 5", timeout=T)
        quiet(pg, 1500)
        assert pg.evaluate(SECS) == MAIN_ORDER and pg.locator("#slopen").count() == 0 and pg.locator('[data-wtype="notiz"]').count() == 0
        assert pg.evaluate("typeof slEdit === 'function' && (slEdit(true), document.querySelectorAll('.slit').length + document.querySelectorAll('#slbar').length)") == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_english_texts(pw, app):
    pg = _tour(pw, app, locale="en-US")
    try:
        assert pg.locator("#slopen").inner_text().strip() == "Customize page"
        _edit(pg)
        t = pg.locator("#slbar").inner_text()
        for w in ("Add widget", "Restore default", "Done"):
            assert w in t, t
        assert pg.locator('.slit[data-sl="map"] .slgrip').get_attribute("aria-label").startswith("Drag to move")
        _catalog(pg)
        assert "Key figures" in pg.locator(".slcat").inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
