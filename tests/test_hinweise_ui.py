"""3.23.0 – Hinweis-Bausteine (Browser, Chromium): unsichtbar ohne Anlass (kein Platz im Raster), sichtbar mit Anlass (Stufe als Symbol + Wort, Warnung als role=alert), gestrichelter Platzhalter im
Bearbeitungsmodus, „Ausblenden“ (Zeitstempel im Layout, überlebt Neuladen, Ablauf), Sammel-Baustein, Zahnrad, Katalog (Kategorie „Hinweise“), Vorlage „Mit Hinweisen“, Statistikseite, Englisch,
390 px, Kontrast hell/dunkel, Fokus, reduzierte Bewegung.
Daten: 25 Touren (die 25. gestern: längste und schnellste Tour), Jahresziel 100.000 km (in Gefahr), r3 ist in der Genauigkeitsliste auffällig, frische Sicherung (Sicherung/Pause/Woche/Erholung ruhig).
Wettlauf-Regel wie in den anderen Browser-Tests: nach jeder Aktion auf den Zustand warten (wait_for_function, 15 s), nie nur schlafen.
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

from tests.test_bausteine_ui import T, TEXTCONTRAST, _api, _catalog, _dash, _edit, _reset, _shot  # noqa: F401
from tests.test_bausteine_ui import pw  # noqa: F401  (Fixture)
from tests.test_tourseite_ui import LAUNCH, SEED, _wait

ROOT = Path(__file__).resolve().parent.parent

MORE = r"""
import sys, os, time, zipfile; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db, config
db.init()
now = int(time.time())
def add(tid, days, dist, dur, up, name):
    ts = now - int(days * 86400)
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,'hike',?,?,?,?,?,?,48.0,11.0,'t','komoot')",
               (tid, name, ts, ts + dur, dist, dur, up, up))
for i in range(17):                                                   # 7 vorhandene + 17 alte = 24, die 25. kommt gestern
    add("o%%d" %% i, 400 + 9 * i, 5000, 7200, 200, "Alte Runde %%d" %% i)
add("z25", 1, 20000, 3600, 800, "Rekordrunde")
db.execute("INSERT INTO goals(year,sport,metric,target) VALUES(?,?,?,?)", (time.localtime().tm_year, "", "km", 100000))
db.execute("INSERT INTO device_quality(tour_id,device_id,berechnet_am,day,sport,zepp_n,dist_tour_m,dist_dev_m,dist_ratio,dist_plausible,h_src,h_state,up_dev,down_dev,up_dem,down_dem,gps_src,gps_n,gps_jumps,gps_gap_pct,gps_med_dt,gps_pts_km,gps_dec,hr_n,hr_bad_pct) "
           "VALUES('r3',1,?,'2026-01-01','hike',1,6000,6000,1.0,1,'zepp','ok',330,330,330,330,'zepp',400,9,1.0,NULL,NULL,0,NULL,NULL)", (now - 3600,))
d = config.DATA_DIR / "backups"
d.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(d / "meine-touren-test.zip", "w") as z:
    z.writestr("x.txt", "x")
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    tmp = tmp_path_factory.mktemp("hn")
    data = tmp / "data"
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    for code in (SEED % {"root": str(ROOT), "data": str(data)}, MORE % {"root": str(ROOT), "data": str(data)}):
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, env=env)
        assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / "launch.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    pr = subprocess.Popen([sys.executable, str(script)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    yield url
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)


def _put(app, widgets, key="uebersicht"):
    _api(app, key, "PUT", {"widgets": [{"id": i, "type": t, "cfg": c} for i, t, c in widgets]})


def _state(pg, wid):
    return pg.evaluate("(w) => { const c = document.getElementById('tlw-' + w); return c ? c.dataset.hn || '' : '-'; }", wid)


def _wait_state(pg, wid, st):
    pg.wait_for_function("([w, s]) => { const c = document.getElementById('tlw-' + w); return !!c && c.dataset.hn === s; }", arg=[wid, st], timeout=T)


def _server_cfg(app, wid):
    lay = _api(app, "uebersicht")["layout"] or {}
    if "views" in lay:                                                  # Behälter mit Ansichten (sobald die Oberfläche gespeichert hat)
        lay = next(v["layout"] for v in lay["views"] if v["id"] == lay["active"])
    for w in lay.get("widgets", []):
        if w["id"] == wid:
            return w.get("cfg", {})


def _wait_server(pg, app, wid, fn):
    """Auf das gespeicherte Layout warten. Nicht mit time.sleep: Die Anfragen der Seite laufen über die Route-Funktion von Playwright und brauchen dessen Ereignisschleife (pg.wait_for_timeout)."""
    end = time.time() + 15
    while time.time() < end:
        c = _server_cfg(app, wid)
        if fn(c):
            return c
        pg.wait_for_timeout(200)
    raise AssertionError(f"Server-Layout nicht wie erwartet: {_server_cfg(app, wid)}")


# color-mix() liefert im Browser „color(srgb …)“: erst über ein Canvas in RGB umrechnen (der Hilfstest aus test_bausteine_ui versteht nur rgb())
_NORM = """const cv = document.createElement('canvas'); cv.width = cv.height = 1; const cx = cv.getContext('2d', {willReadFrequently: true});
  const rgb = c => { cx.clearRect(0, 0, 1, 1); cx.fillStyle = '#000'; cx.fillStyle = c; cx.fillRect(0, 0, 1, 1); const d = cx.getImageData(0, 0, 1, 1).data; return {r: d[0], g: d[1], b: d[2], a: d[3] / 255}; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const ratio = (x, y) => { const a = lum(x), b = lum(y); return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05); };
  const bg = el => { for (let e = el; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor); if (c.a > 0.5) return c; } return {r: 255, g: 255, b: 255, a: 1}; };"""
HN_CONTRAST = "(sel) => {" + _NORM + """
  const low = {}; let n = 0;
  document.querySelectorAll(sel).forEach(el => {
    if (![...el.childNodes].some(x => x.nodeType === 3 && x.textContent.trim()) || el.closest('svg') || !el.offsetParent) return;
    const r = ratio(rgb(getComputedStyle(el).color), bg(el));
    n++;
    if (r < 4.5) low[(el.closest('[data-wtype]') || el).dataset.wtype + ' ' + el.tagName + '.' + el.className + ' "' + el.textContent.trim().slice(0, 20) + '"'] = Math.round(r * 100) / 100;
  });
  return {n, low};
}"""
HN_ICON = "() => {" + _NORM + """
  return [...document.querySelectorAll('.hnbox')].map(b => ratio(rgb(getComputedStyle(b.querySelector('svg')).stroke), bg(b)));
}"""


# ------------------------------------------------------------------  unsichtbar / sichtbar  ------------------------------------------------------------------

def test_quiet_hints_are_invisible_and_take_no_space(pw, app):
    _reset(app)
    _put(app, [("hp", "hnpause", {}), ("hs", "hnsicherung", {}), ("he", "hnerholung", {})])          # 3.45.0: das Wochenziel ist jetzt Teil des Bausteins „Ziele“
    pg = _dash(pw, app)
    try:
        for w in ("hp", "hs", "he"):
            _wait_state(pg, w, "aus")
        r = pg.evaluate("() => ['hp','hs','he'].map(w => { const c = document.getElementById('tlw-' + w); return [getComputedStyle(c).display, c.getBoundingClientRect().height]; })")
        assert all(x == ["none", 0] for x in r), r
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_active_hints_show_text_severity_and_roles(pw, app):
    _reset(app)
    _put(app, [("hz", "hnziel", {}), ("hm", "hnmeilenstein", {}), ("hr", "hnrekord", {}), ("ha", "hnauffaellig", {})])
    pg = _dash(pw, app, dpr=2)
    try:
        for w in ("hz", "hm", "hr", "ha"):
            _wait_state(pg, w, "an")
        z = pg.locator("#tlw-hz .hnbox")
        assert z.get_attribute("role") == "alert" and z.get_attribute("class").endswith("hn-warnung")
        assert pg.locator("#tlw-hz .hnlbl").inner_text().lower().startswith("warnung")
        assert "100.000" in pg.locator("#tlw-hz").inner_text()
        assert "25. Tour erreicht" in pg.locator("#tlw-hm").inner_text()
        assert pg.locator("#tlw-hr .hnbox").get_attribute("role") == "status" and "Längste Tour" in pg.locator("#tlw-hr").inner_text() and "Rekordrunde" in pg.locator("#tlw-hr").inner_text()
        assert pg.locator("#tlw-ha .hnlbl").inner_text().lower().startswith("hinweis") and "1 Tour ist auffällig und noch nicht geprüft." in pg.locator("#tlw-ha").inner_text()
        # Stufe nie nur Farbe: Symbol (SVG, dekorativ) und Wort in jedem Hinweis
        assert pg.evaluate("() => [...document.querySelectorAll('.hnbox')].every(b => b.querySelector('svg.hnsi[aria-hidden=true]') && /^(Info|Hinweis|Warnung)/.test(b.querySelector('.hnlbl').textContent.trim()))")
        assert pg.locator("#tlw-ha .hnact a").inner_text().startswith("In der Verwaltung")
        _shot(pg, "hinweise-uebersicht-hell.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_placeholder_in_edit_mode_only(pw, app):
    _reset(app)
    _put(app, [("hp", "hnpause", {})])
    pg = _dash(pw, app)
    try:
        _wait_state(pg, "hp", "aus")
        assert not pg.locator("#tlw-hp").is_visible()
        _edit(pg)
        pg.wait_for_selector("#tlw-hp", state="visible", timeout=T)
        assert "Wird nur angezeigt, wenn seit mindestens 14 Tagen keine Tour mehr gemacht wurde." in pg.locator("#tlw-hp").inner_text()
        assert "Gerade ist nichts los" in pg.locator("#tlw-hp").inner_text()
        assert pg.evaluate("() => getComputedStyle(document.querySelector('#tlw-hp > details.tls')).borderTopStyle") == "dashed"
        _shot(pg, "hinweise-platzhalter-bearbeiten.png", full=False)
        pg.locator("#slbar").get_by_role("button", name="Fertig").click()
        pg.wait_for_function("() => !document.getElementById('tlw-hp') || getComputedStyle(document.getElementById('tlw-hp')).display === 'none'", timeout=T)
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Ausblenden  ------------------------------------------------------------------

def test_snooze_hides_persists_and_expires(pw, app):
    _reset(app)
    _put(app, [("ha", "hnauffaellig", {})])
    pg = _dash(pw, app)
    try:
        _wait_state(pg, "ha", "an")
        btn = pg.locator("#tlw-ha .hnsn")
        assert btn.inner_text() == "Für 7 Tage ausblenden" and "ausblenden" in btn.get_attribute("aria-label")
        btn.click()
        _wait_state(pg, "ha", "aus")
        c = _wait_server(pg, app, "ha", lambda c: c and c.get("snoozes"))
        art, ts = c["snoozes"][0].split(":")
        assert art == "auffaellig" and abs(int(ts) - (time.time() + 7 * 86400)) < 120
        pg.reload()
        pg.wait_for_selector("main.home #hlast", timeout=T)
        _wait_state(pg, "ha", "aus")
        # abgelaufen: sichtbar, ohne dass etwas gelöscht werden muss
        _api(app, "uebersicht", "PUT", {"widgets": [{"id": "ha", "type": "hnauffaellig", "cfg": {"snoozes": [f"auffaellig:{int(time.time()) - 5}"]}}]})
        pg.reload()
        pg.wait_for_selector("main.home #hlast", timeout=T)
        _wait_state(pg, "ha", "an")
        # im Bearbeitungsmodus: „Wieder anzeigen“
        _api(app, "uebersicht", "PUT", {"widgets": [{"id": "ha", "type": "hnauffaellig", "cfg": {"snoozes": [f"auffaellig:{int(time.time()) + 86400}"]}}]})
        pg.reload()
        pg.wait_for_selector("main.home #hlast", timeout=T)
        _wait_state(pg, "ha", "aus")
        _edit(pg)
        pg.wait_for_selector("#tlw-ha .hnun", timeout=T)
        assert "Ausgeblendet bis" in pg.locator("#tlw-ha").inner_text()
        pg.locator("#tlw-ha .hnun").click()
        _wait_state(pg, "ha", "an")
        _wait_server(pg, app, "ha", lambda c: c is not None and not c.get("snoozes"))
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_collective_widget_list_snooze_focus_and_gear(pw, app):
    _reset(app)
    _put(app, [("hs", "hinweise", {})])
    pg = _dash(pw, app, dpr=2)
    try:
        _wait_state(pg, "hs", "an")
        names = pg.locator("#tlw-hs .hnti").all_inner_texts()
        assert names == ["Jahresziel in Gefahr", "Meilenstein erreicht", "Neue Auffälligkeiten", "Neuer Bestwert"], names
        assert pg.locator("#tlw-hs .hnbox").count() == 4 and pg.locator("#tlw-hs .hnbox[role=alert]").count() == 1
        _shot(pg, "hinweise-sammel-hell.png")
        pg.locator("#tlw-hs .hnsn").first.click()
        pg.wait_for_function("() => document.querySelectorAll('#tlw-hs .hnbox').length === 3", timeout=T)
        assert pg.evaluate("() => document.activeElement.classList.contains('hnsn')"), "Fokus muss auf dem nächsten Knopf bleiben"
        # Auswahl der Arten im Zahnrad: nur noch die Rekord-Tour
        _edit(pg)
        pg.locator('.slit[data-sl="hs"] [data-a="cfg"]').click()
        pg.wait_for_selector(".slform", timeout=T)
        for lbl in ("Jahresziel in Gefahr", "Meilenstein erreicht", "Neue Auffälligkeiten"):
            pg.locator(".slform label", has_text=lbl).locator("input").uncheck()
        pg.get_by_role("button", name="Speichern", exact=True).click()
        pg.wait_for_function("() => document.querySelectorAll('#tlw-hs .hnbox').length === 1", timeout=T)
        _wait_server(pg, app, "hs", lambda c: c and c.get("arten") == ["pause", "rekord", "erholung", "sicherung"])
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_collective_all_snoozed_becomes_invisible(pw, app):
    _reset(app)
    ts = int(time.time()) + 86400
    _put(app, [("hs", "hinweise", {"snoozes": [f"{a}:{ts}" for a in ("ziel", "meilenstein", "auffaellig", "rekord")]})])
    pg = _dash(pw, app)
    try:
        _wait_state(pg, "hs", "aus")
        assert not pg.locator("#tlw-hs").is_visible()
    finally:
        pg.browser_.close()


def test_gear_on_pause_threshold_validation_and_snooze_option(pw, app):
    _reset(app)
    _put(app, [("hp", "hnpause", {})])
    pg = _dash(pw, app)
    try:
        _wait_state(pg, "hp", "aus")
        _edit(pg)
        pg.locator('.slit[data-sl="hp"] [data-a="cfg"]').click()
        pg.wait_for_selector(".slform input[type=number]", timeout=T)
        pg.locator(".slform input[type=number]").fill("0")                                  # ungültig: Fehlermeldung, nichts gespeichert
        pg.get_by_role("button", name="Speichern", exact=True).click()
        pg.wait_for_function("() => document.querySelector('.slerr').textContent.length > 5", timeout=T)
        pg.locator(".slform input[type=number]").fill("1")
        pg.locator(".slform label", has_text="Nicht anbieten").locator("input").check()
        pg.get_by_role("button", name="Speichern", exact=True).click()
        _wait_state(pg, "hp", "an")
        assert "Seit 1 Tag keine Tour." in pg.locator("#tlw-hp").inner_text() and pg.locator("#tlw-hp .hnsn").count() == 0
        c = _wait_server(pg, app, "hp", lambda c: c and c.get("tage") == 1)
        assert c["ausblenden"] == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_acknowledging_a_tour_removes_the_hint(pw, app):
    _reset(app)
    _put(app, [("ha", "hnauffaellig", {})])
    pg = _dash(pw, app)
    try:
        _wait_state(pg, "ha", "an")
        for m in ("POST", "DELETE"):
            req = urllib.request.Request(f"{app}/api/tours/r3/quality-ack", method=m)
            urllib.request.urlopen(req, timeout=10).read()
            pg.reload()
            pg.wait_for_selector("main.home #hlast", timeout=T)
            _wait_state(pg, "ha", "aus" if m == "POST" else "an")                          # trotz 30-s-Zwischenspeicher: der Datenstand ist Teil des Schlüssels
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Katalog, Vorlage, Statistik  ------------------------------------------------------------------

def test_catalog_category_and_page_rules(pw, app):
    _reset(app)
    pg = _dash(pw, app)
    try:
        _edit(pg)
        _catalog(pg)
        pg.locator(".slchip", has_text="Hinweise").click()
        pg.wait_for_function("() => document.querySelectorAll('.slcard:not([hidden])').length === 7", timeout=T)          # 3.45.0: ohne „Jahresziel in Gefahr“ und „Wochenziel“ (jetzt Baustein „Ziele“)
        assert pg.locator(".slcath:visible").all_inner_texts() == ["Hinweise"]
        assert pg.evaluate("() => [...document.querySelectorAll('.slcard:not([hidden])')].every(c => c.querySelector('.slpv').innerHTML.trim() && c.querySelector('p').textContent.trim() && c.querySelector('[data-add]'))")
        assert pg.locator('[data-add="hinweise"]').count() == 1
        _shot(pg, "hinweise-katalog.png", full=False)
    finally:
        pg.browser_.close()
    _reset(app)
    pg = _browser_tour(pw, app)
    try:
        _edit(pg)
        _catalog(pg)
        assert pg.locator(".slchip", has_text="Hinweise").count() == 0 or pg.locator(".slcard:visible [data-add^=hn], .slcard:visible [data-add=hinweise]").count() == 0
    finally:
        pg.browser_.close()


def _browser_tour(pw, app):
    from tests.test_bausteine_ui import _tour
    return _tour(pw, app)


def test_template_mit_hinweisen_and_statistik_page(pw, app):
    _reset(app)
    pg = _dash(pw, app)
    try:
        _edit(pg)
        pg.locator("#slbar [data-a=views]").click()
        pg.wait_for_selector(".slvws .slvr", timeout=T)
        pg.locator(".slvws").get_by_role("button", name="Aus Vorlage …", exact=True).click()
        pg.wait_for_selector(".slvt .slcard", timeout=T)
        assert "Mit Hinweisen" in pg.locator(".slvt .slcard h3").all_inner_texts()
        pg.get_by_role("button", name="Mit Hinweisen: Als neue Ansicht übernehmen", exact=True).click()
        pg.wait_for_function("() => !!document.querySelector('[data-wtype=hinweise]')", timeout=T)
        pg.wait_for_function("() => document.querySelector('[data-wtype=hinweise]').dataset.hn === 'an'", timeout=T)
    finally:
        pg.browser_.close()
    _reset(app)
    _put(app, [("hr", "hnrekord", {}), ("hz", "hnziel", {})], key="statistik")
    pg = _browser_stats(pw, app)
    try:
        _wait_state(pg, "hr", "an")
        assert pg.locator("#tlw-hr .stnote, #tlw-hr .stglob").count() == 0               # Hinweise kennen den globalen Filter nicht
        assert not pg.errors, pg.errors
        _shot(pg, "hinweise-statistik.png")
    finally:
        pg.browser_.close()
    _api(app, "statistik", "DELETE")


def _browser_stats(pw, app):
    from tests.test_bausteine_ui import _browser
    pg = _browser(pw, app)
    pg.goto(f"{app}/#/stats")
    pg.wait_for_function("() => !!document.querySelector('#slopen')", timeout=T)
    return pg


# ------------------------------------------------------------------  Aussehen  ------------------------------------------------------------------

@pytest.mark.parametrize("scheme,width", [("light", 390), ("dark", 390), ("dark", 1280)])
def test_look_390px_contrast_focus_and_motion(pw, app, scheme, width):
    _reset(app)
    _put(app, [("hs", "hinweise", {}), ("hz", "hnziel", {}), ("ha", "hnauffaellig", {})])
    pg = _dash(pw, app, scheme=scheme, width=width, height=900 if width > 500 else 844, dpr=2)
    try:
        for w in ("hs", "hz", "ha"):
            _wait_state(pg, w, "an")
        assert pg.evaluate("() => document.documentElement.scrollWidth - window.innerWidth") <= 0
        r = pg.evaluate(HN_CONTRAST, "[data-wtype^=hn] .tlsb *, [data-wtype=hinweise] .tlsb *")
        assert r["n"] > 20 and not r["low"], f"{scheme} {width}: Kontrast unter 4,5:1 {r['low']}"
        # Symbol gegen Hintergrund mindestens 3:1 (Strich der SVG-Form)
        ic = pg.evaluate(HN_ICON)
        assert ic and min(ic) >= 3, ic
        if width < 500:
            sz = pg.evaluate("() => [...document.querySelectorAll('.hnsn')].map(b => Math.round(b.getBoundingClientRect().height))")
            assert sz and min(sz) >= 40, sz
        pg.locator(".hnsn").first.focus()
        assert pg.evaluate("() => getComputedStyle(document.activeElement).outlineStyle") != "none"
        assert pg.evaluate("() => [...document.querySelectorAll('.hnbox')].every(b => getComputedStyle(b).animationName === 'none')")       # reduzierte Bewegung
        _shot(pg, f"hinweise-{width}-{scheme}.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_english_texts(pw, app):
    _reset(app)
    _put(app, [("hs", "hinweise", {}), ("hp", "hnpause", {})])
    pg = _dash(pw, app, locale="en-US")
    try:
        _wait_state(pg, "hs", "an")
        txt = pg.locator("#tlw-hs").inner_text()
        assert "Annual goal at risk" in txt or "goal" in txt.lower()
        left = pg.evaluate("""() => [...document.querySelectorAll('#tlw-hs *')].filter(e => e.children.length === 0 && /[äöüß]|\\b(Touren|Hinweis|Warnung|ausblenden|Tage)\\b/.test(e.textContent)).map(e => e.textContent.trim().slice(0, 40))""")
        assert not [x for x in left if x not in ("Rekordrunde",)], left
        _edit(pg)
        pg.wait_for_selector("#tlw-hp", state="visible", timeout=T)
        assert "Only shown if" in pg.locator("#tlw-hp").inner_text()
    finally:
        pg.browser_.close()
