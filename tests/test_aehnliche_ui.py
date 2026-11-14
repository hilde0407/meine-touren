"""3.14.0 – Oberfläche (Browser, Chromium): Abschnitt „Ähnliche Touren im Vergleich“ auf der Tourseite. Alle Daten konstruiert (Rundwege mit gleicher Strecke).
Mit AE_SHOTS=<Ordner> werden Screenshots (Desktop hell/dunkel, 390 px) abgelegt."""
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
from app import db, config, routes
db.init()
config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
mode = %(mode)r
now = int(time.time())
def loop(lat0=48.0, lng0=11.0, r=0.01, n=120):
    return [(lat0 + r * math.sin(2 * math.pi * i / (n - 1)), lng0 + r * (1 - math.cos(2 * math.pi * i / (n - 1))), 500 + 20 * math.sin(i / 9), i * 1000) for i in range(n)]
def tour(tid, ts, name, dist, dur, up, **kw):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,?,?,'t','komoot')", (tid, name, "hike", ts, ts + (dur or 0), dist, dur, up, up))
    routes.store(tid, loop(**kw))
if mode == "full":
    # (Tage zurück, Name, Strecke m, Dauer s, Aufstieg m)
    for i, (days, name, dist, dur, up) in enumerate([(1900, "Gipfelrunde im Frühjahr", 6000, 8100, 330), (1500, "Gipfelrunde", 6100, 7800, 310), (1100, "Gipfelrunde mit sehr langem Namen für die Kürzung auf kleinen Bildschirmen", 5900, 7200, 300),
                                                      (700, "Gipfelrunde", 6000, None, 320), (330, "Gipfelrunde", 6200, 6900, 340), (40, "Gipfelrunde heute", 6000, 6300, 325), (12, "Gipfelrunde", 6000, 7000, 325)]):
        tour("r%%d" %% i, now - days * 86400, name, dist, dur, up)
    db.execute("INSERT INTO devices(id,name,kind,active) VALUES(1,'Amazfit Balance','zepp',1)")
    db.execute("INSERT INTO devices(id,name,kind,active) VALUES(2,'Garmin Forerunner 255','garmin',1)")
    for t, d in (("r0", 2), ("r1", 2), ("r4", 1), ("r5", 1), ("r6", 1)):
        db.execute("INSERT OR REPLACE INTO tour_device(tour_id,device_id) VALUES(?,?)", (t, d))
else:
    tour("e0", now - 5 * 86400, "Einzelrunde", 6000, 7000, 300)
    tour("e1", now - 9 * 86400, "Andere Runde", 6000, 7000, 300, lat0=49.5)
"""

LAUNCH = r"""
import sys, os; sys.path.insert(0, %(root)r)
import uvicorn
from app.main import app
uvicorn.run(app, host="127.0.0.1", port=%(port)d, log_level="warning")
"""


def _wait(url):
    for _ in range(150):
        try:
            urllib.request.urlopen(url + "/api/version", timeout=1)
            return
        except Exception:
            time.sleep(0.2)


def _serve(mode, tmp):
    data = tmp / mode
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data), "mode": mode}], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / f"launch_{mode}.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    pr = subprocess.Popen([sys.executable, str(script)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    return pr, url


@pytest.fixture(scope="module")
def apps(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    d = tmp_path_factory.mktemp("ae")
    procs, urls = [], {}
    for m in ("full", "single"):
        p, u = _serve(m, d)
        procs.append(p); urls[m] = u
    yield urls
    for p in procs:
        p.terminate()
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            p.kill(); p.wait(5)


@pytest.fixture(scope="module")
def pw():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


def _page(pw, url, hash_, wait, width=1280, height=1000, scheme="light", dpr=1, locale="de-DE"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale=locale, viewport={"width": width, "height": height}, color_scheme=scheme, device_scale_factor=dpr)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(url) else r.continue_())
    pg.goto(f"{url}/#/{hash_}")
    if wait:
        pg.wait_for_selector(wait, timeout=15000)
    else:
        pg.wait_for_timeout(2500)
    pg.wait_for_timeout(400)
    pg.browser_ = b
    return pg


def _shot(pg, name, sel="#aehncard"):
    d = os.environ.get("AE_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        pg.locator(sel).scroll_into_view_if_needed()
        pg.locator(sel).screenshot(path=str(Path(d) / name))


def _open(pg):
    if not pg.locator("#aehncard details").evaluate("e => e.open"):
        pg.locator("#aehncard details > summary").click()
    pg.wait_for_selector("#aehncard .aer", timeout=5000)
    pg.wait_for_selector("#aehncard .aesvg", timeout=5000)


CONTRAST = """() => {
  const parse = c => { const m = c.match(/[\\d.]+/g).map(Number); return {r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1}; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const bg = el => { for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c.a > 0.5) return c; } return {r: 255, g: 255, b: 255, a: 1}; };
  const out = {};
  for (const sel of [".aedt", ".aesub", ".aecl", ".aec b", ".aed", ".aed i", ".aetag.cur", ".aetag:not(.cur)", ".aesaid", ".aelegend span"]) {
    const el = document.querySelector("#aehncard " + sel);
    if (!el) continue;
    const f = parse(getComputedStyle(el).color), b = bg(el), l1 = lum(f), l2 = lum(b);
    out[sel] = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }
  const svg = document.querySelector("#aehncard .aesvg text"), card = document.querySelector("#aehncard");
  if (svg) { const f = parse(getComputedStyle(svg).fill), b = bg(card), l1 = lum(f), l2 = lum(b); out["svg text"] = (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05); }
  return out;
}"""


def test_card_collapsed_by_default_with_key_statement_and_state_is_remembered(pw, apps):
    pg = _page(pw, apps["full"], "tour/r5", "#aehncard")
    try:
        d = pg.locator("#aehncard details")
        assert d.count() == 1 and not d.evaluate("e => e.open")
        key = pg.locator("#aehncard summary").inner_text()
        assert "Ähnliche Touren im Vergleich" in key and "6 Wiederholungen" in key
        assert "Bestes Tempo bisher" in key                                              # r5 (6300 s) ist schneller als alle früheren Läufe
        assert pg.locator("#aehncard .aer").first.is_hidden()                              # zugeklappt: Zeilen nicht sichtbar
        pg.locator("#aehncard summary").click()
        pg.wait_for_function("() => localStorage.getItem('mt_trf_aehn') === '1'")
        assert d.evaluate("e => e.open")
        pg.reload(); pg.wait_for_selector("#aehncard"); pg.wait_for_timeout(500)
        assert pg.locator("#aehncard details").evaluate("e => e.open")                  # Zustand bleibt
        pg.wait_for_selector("#aehncard .aesvg")
        pg.locator("#aehncard summary").click()
        pg.wait_for_function("() => localStorage.getItem('mt_trf_aehn') === '0'")
        assert pg.evaluate("localStorage.getItem('mt_trf_aehn')") == "0" and pg.locator("#aehncard summary").evaluate("e => getComputedStyle(e).cursor") == "pointer"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_rows_values_deviation_chart_and_links(pw, apps):
    pg = _page(pw, apps["full"], "tour/r4", "#aehncard", dpr=2)
    try:
        _open(pg)
        assert pg.locator("#aehncard .aer").count() == 7 and pg.locator("#aehncard .aer.cur").count() == 1
        cur = pg.locator("#aehncard .aer.cur")
        assert "Diese Tour" in cur.inner_text() and cur.locator(".aed").count() == 0 and cur.locator("a").count() == 0       # keine Abweichung zu sich selbst, kein Link
        order = pg.locator("#aehncard .aer .aedt").all_inner_texts()
        years = [int(x[-4:]) * 372 + int(x[3:5]) * 31 + int(x[:2]) for x in order]
        assert years == sorted(years, reverse=True)                                       # neueste zuerst
        t = pg.locator("#aehncard").inner_text()
        assert "Von 2 späteren Läufen waren 1 schneller" in pg.locator("#aehncard .aesaid").inner_text()
        r2 = pg.locator("#aehncard .aer", has_text="Gipfelrunde mit sehr langem Namen")
        txt = r2.inner_text()                                                             # 7200 s gegen 6900 s: +5:00 länger; 5,9 km gegen 6,2 km: −0,3 km
        assert "+5:00" in txt and "länger" in txt and "−0,3 km" in txt and "kürzer" in txt and "−9 %" in txt and "langsamer" in txt and "3,0 km/h" in txt
        assert "Garmin Forerunner 255" not in txt and "Amazfit" not in txt                # r2 hat kein Gerät
        assert "Garmin Forerunner 255" in pg.locator("#aehncard .aer", has_text="Gipfelrunde im Frühjahr").inner_text()
        none_row = pg.locator("#aehncard .aer").filter(has=pg.locator("b", has_text="–")).first            # r3 ohne Zeit: „–“ statt 0
        assert none_row.count() == 1 and "0 min" not in none_row.inner_text()
        assert pg.locator("#aehncard .aedot").count() == 6 and pg.locator("#aehncard .aedot.cur").count() == 1        # sechs Läufe mit Tempo, einer ohne
        assert pg.locator("#aehncard .aelegend").is_visible()
        for bad in ("NaN", "undefined", "null", "Infinity"):
            assert bad not in t and bad not in pg.locator("#aehncard svg.aesvg").inner_html(), bad
        href = pg.locator("#aehncard .aer a").first.get_attribute("href")
        assert href.startswith("#/tour/r")
        pg.locator("#aehncard .aer a").first.click()
        pg.wait_for_function("() => location.hash !== '#/tour/r4'")
        pg.wait_for_selector("#aehncard .aer.cur")
        assert pg.locator("#aehncard .aer.cur").count() == 1 and pg.locator("#aehncard .aer.cur a").count() == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_key_statement_faster_than_some(pw, apps):
    pg = _page(pw, apps["full"], "tour/r6", "#aehncard")
    try:
        assert "Schneller als 3 von 5 früheren Läufen" in pg.locator("#aehncard summary").inner_text()
        pg.locator("#aehncard summary").click()
        assert "Schnellster Lauf" in pg.locator("#aehncard .aer", has_text="05.10.2026").inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_key_statement_first_run_and_missing_time_of_current(pw, apps):
    pg = _page(pw, apps["full"], "tour/r0", "#aehncard")
    try:
        assert "Erster Lauf dieser Strecke" in pg.locator("#aehncard summary").inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    pg = _page(pw, apps["full"], "tour/r3", "#aehncard")
    try:
        assert "6 Wiederholungen" in pg.locator("#aehncard summary").inner_text() and "Tempo" not in pg.locator("#aehncard summary").inner_text()
        pg.locator("#aehncard summary").click()
        assert "keinen Tempovergleich" in pg.locator("#aehncard").inner_text() and pg.locator("#aehncard .aedot.cur").count() == 0 and pg.locator("#aehncard .aedot").count() == 6
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_absent_without_repeat(pw, apps):
    pg = _page(pw, apps["single"], "tour/e0", "#profcard")
    try:
        pg.wait_for_timeout(2500)
        assert pg.locator("#aehncard").count() == 0 and "Ähnliche Touren" not in pg.locator("body").inner_text() and not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_english_translation(pw, apps):
    pg = _page(pw, apps["full"], "tour/r4", "#aehncard", locale="en-US")
    try:
        _open(pg)
        t = pg.locator("#aehncard").inner_text()
        for word in ("Similar tours compared", "repeats", "This tour", "longer", "Duration", "Other runs", "Fastest run"):
            assert word in t, word
        assert "Ähnliche" not in t and "Wiederholung" not in t and "länger" not in t and "früheren" not in t
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("loc,word", [("fr-FR", "Parcours similaires comparés"), ("es-ES", "Rutas similares comparadas")])
def test_french_spanish_translation(pw, apps, loc, word):
    pg = _page(pw, apps["full"], "tour/r4", "#aehncard", locale=loc)
    try:
        _open(pg)
        t = pg.locator("#aehncard").inner_text()
        assert word in t and "Ähnliche" not in t and "Wiederholung" not in t and "länger" not in t and "Läufe" not in t and "Diese Tour" not in t
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_contrast_in_light_and_dark(pw, apps, scheme):
    pg = _page(pw, apps["full"], "tour/r4", "#aehncard", scheme=scheme, dpr=2)
    try:
        _open(pg)
        c = pg.evaluate(CONTRAST)
        assert len(c) >= 9, c
        low = {k: round(v, 2) for k, v in c.items() if v < 4.5}
        assert not low, f"{scheme}: Kontrast unter 4,5:1: {low}"
        _shot(pg, f"aehnliche-desktop-{scheme}.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_mobile_390_no_horizontal_scroll(pw, apps, scheme):
    pg = _page(pw, apps["full"], "tour/r4", "#aehncard", width=390, height=844, scheme=scheme, dpr=2)
    try:
        _open(pg)
        pg.wait_for_timeout(300)
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), pg.evaluate("[document.documentElement.scrollWidth, window.innerWidth]")
        over = pg.evaluate("[...document.querySelectorAll('#aehncard .aer, #aehncard .aem, #aehncard summary')].filter(e => e.scrollWidth > e.clientWidth + 1).map(e => e.className)")
        assert not over, over
        r = pg.locator("#aehncard").bounding_box()
        assert r["x"] >= 0 and r["x"] + r["width"] <= 391
        assert pg.evaluate("[...document.querySelectorAll('#aehncard .aec b, #aehncard .aed')].every(e => e.getBoundingClientRect().right <= innerWidth)")
        _shot(pg, f"aehnliche-mobil-{scheme}.png")
        pg.locator("#aehncard summary").click()
        _shot(pg, f"aehnliche-mobil-{scheme}-zu.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
