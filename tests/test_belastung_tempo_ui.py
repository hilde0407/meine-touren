"""3.12.0 – Oberfläche (Browser, Chromium): Statistik-Abschnitte „Belastung und Erholung“ und „Dein typisches Tempo“ (mit Rechner), Tourseite (Ermüdungsverlauf in
„Training laut Uhr“, „Tempo nach Steigung“). Alle Daten konstruiert. Mit BT_SHOTS=<Ordner> werden Screenshots abgelegt."""
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
import sys, os, time; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db, config, routes, uhrtraining as ut
from tests.test_belastung_tempo import track, STD
db.init()
config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
mode = %(mode)r
now = int(time.time())
def tour(tid, ts, kind, name, dist, dur, sport="hike"):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,100,100,'t','komoot')", (tid, name, sport, ts, ts + dur, dist, dur))
    db.execute("INSERT OR REPLACE INTO tour_source(tour_id,src,name) VALUES(?,?,'')", (tid, kind))
if mode == "full":
    for i in range(30):
        ts = now - (7 * i + 2) * 86400
        z = i %% 5 != 4
        tid = ("z%%d" %% ts) if z else "g%%d" %% i
        tour(tid, ts, "zepp" if z else "garmin", "Runde %%d" %% i if i else "Hauptrunde", 5000, 4000)
        if z:
            load = (150 if i < 4 else 70) + (i * 37) %% 60
            ut.store(tid, {"v": 1, "geladen": 1, "summary": {"trackid": str(ts), "dis": "5000", "run_time": "4000", "exercise_load": str(load), "te": "32"}, "detail": True, "kilo_pace": None})
        if i == 0:
            continue
        routes.store(tid, [tuple(p) for p in track([(2000, 0, 5 + (i %% 3) * .2), (1000, .10, 3 + (i %% 4) * .1), (1000, 0, 5), (1000, -.10, 6)])])
    # jüngste Tour: 8 km, zweite Hälfte langsamer, Puls steigt (Ermüdung) – flache Strecke
    tid = "z%%d" %% (now - 2 * 86400)
    db.execute("UPDATE tours SET dist_m=8000, dur_s=5200, end_ts=start_ts+5200 WHERE id=?", (tid,))
    open(os.path.join(%(data)r, "fat.txt"), "w").write(tid)
    kp = ";".join("%%d,%%d,0,0,%%d,0,0,300,0,56,0,0,0,40" %% (i, 600 if i < 4 else 700, 120 if i < 4 else 135) for i in range(8))
    ut.store(tid, {"v": 1, "geladen": 1, "summary": {"trackid": tid[1:], "dis": "8000", "run_time": "5200", "exercise_load": "175", "te": "32", "avg_heart_rate": "128", "avg_frequency": "112"}, "detail": True, "kilo_pace": kp})
    routes.store(tid, [tuple(p) for p in track([(1500, 0, 5), (1000, .10, 5), (1500, 0, 5)] * 2)])
elif mode == "pending":
    for i in range(3):
        tour("z%%d" %% (now - (i + 1) * 86400), now - (i + 1) * 86400, "zepp", "Offene Runde %%d" %% i, 5000, 3600)
else:
    for i in range(3):
        tour("g%%d" %% i, now - (i + 1) * 86400, "garmin", "Ohne Daten %%d" %% i, 5000, 3600)
"""

LAUNCH = r"""
import sys, os; sys.path.insert(0, %(root)r)
from app import sync
def nope():
    raise RuntimeError("Zepp-Zugangsdaten fehlen (Einstellungen)")
sync._zepp_api = nope
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
    d = tmp_path_factory.mktemp("bt")
    procs, urls = [], {}
    for m in ("full", "pending", "empty"):
        p, u = _serve(m, d)
        procs.append(p); urls[m] = u
    urls["fat"] = (d / "full" / "fat.txt").read_text()
    urls["g"] = "g4"
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


def _shot(pg, name, sel):
    d = os.environ.get("BT_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        pg.locator(sel).scroll_into_view_if_needed()
        pg.locator(sel).screenshot(path=str(Path(d) / name))


def _open_tempo(pg):
    pg.wait_for_selector("#tpsec", timeout=15000)
    if not pg.locator("#tpsec details.trsec").evaluate("e => e.open"):
        pg.locator("#tpsec details.trsec > summary").click()
    pg.wait_for_selector("#tpbody .utile", timeout=15000)


def test_stats_sections_content_keyboard_and_fold_state(pw, apps):
    pg = _page(pw, apps["full"], "stats", "#blsec")
    try:
        pg.wait_for_selector("#blsec .blbar", timeout=15000)
        t = pg.locator("#blsec").inner_text()
        assert "Belastung und Erholung" in t and "Aktuell im Vergleich" in t and "Touren mit Uhr-Daten" in t and "Belastung im Zeitraum" in t
        assert "Mehr Belastung als sonst" in t or "mehr Belastung als sonst" in t or "Belastung als sonst" in t
        assert pg.locator("#blsec .blbar, #blsec .blpart").count() >= 10 and pg.locator("#blsec .blnone").count() >= 1          # Touren ohne Uhr-Daten: gestrichelt, kein Balken
        assert "Die härtesten Wochen" in t and "Die härtesten Touren" in t and "Hauptrunde" in t or "Runde" in t
        for bad in ("NaN", "undefined", "null", "-1"):
            assert bad not in t, bad
        # Tastatur: Balken per Pfeil, Tooltip in Klartext
        g = pg.locator("#blsec .blg[tabindex='0']")
        g.focus()
        pg.wait_for_selector("#bltip:not([hidden])")
        tip = pg.locator("#bltip").inner_text()
        assert "Belastung" in tip and "Touren mit Uhr-Daten" in tip
        first = pg.evaluate("document.activeElement.dataset.i")
        pg.keyboard.press("ArrowLeft")
        assert pg.evaluate("document.activeElement.dataset.i") != first and pg.evaluate("document.activeElement.getAttribute('tabindex')") == "0"
        assert "Belastung" in pg.locator("#blsec .blg:focus").get_attribute("aria-label")
        pg.keyboard.press("Escape")
        assert pg.locator("#bltip").is_hidden()
        # Wochen/Monate umschalten
        pg.locator("#blsec [data-m='m']").click()
        pg.wait_for_selector("#blsec .blsvg[aria-label*='Monat']")
        assert pg.locator("#blsec [data-m='m']").get_attribute("aria-pressed") == "true"
        pg.locator("#blsec [data-m='w']").click()
        # Einklappen merken
        sm = pg.locator("#blsec details.trsec > summary")
        assert pg.locator("#blsec details.trsec").evaluate("e => e.open")
        sm.click()
        assert not pg.locator("#blsec details.trsec").evaluate("e => e.open") and pg.evaluate("localStorage.getItem('mt_trf_bl_sec')") == "0"
        pg.reload(); pg.wait_for_selector("#blsec"); pg.wait_for_timeout(500)
        assert not pg.locator("#blsec details.trsec").evaluate("e => e.open")
        assert pg.locator("#blsec details.trsec > summary").evaluate("e => getComputedStyle(e).cursor") == "pointer"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_stats_tempo_section_and_calculator(pw, apps):
    pg = _page(pw, apps["full"], "stats", "#tpsec")
    try:
        pg.wait_for_selector("#tpkey:not(:empty)", timeout=15000)
        key = pg.locator("#tpkey").inner_text()
        assert "Bergauf" in key and "km/h" in key
        _open_tempo(pg)
        tiles = {x.locator("span").first.inner_text(): x.locator("b").inner_text() for x in pg.locator("#tpbody .utile").all()}
        assert {"Bergauf", "Eben", "Bergab", "Aufstieg pro Stunde"} <= set(tiles) and "km/h" in tiles["Eben"] and "m/h" in tiles["Aufstieg pro Stunde"]
        assert "Median über" in pg.locator("#tpbody").inner_text()
        pg.locator("#tpkm").fill("10"); pg.locator("#tpup").fill("600"); pg.locator("#tpdown").fill("600")
        pg.locator("#tpform button").click()
        pg.wait_for_selector("#tpres .tpbig")
        r = pg.locator("#tpres").inner_text()
        assert "Geschätzte Gehzeit" in r and "h" in r and "Reine Gehzeit ohne Pausen" in r and "Grundlage" in r
        pg.locator("#tpkm").fill("abc"); pg.locator("#tpform button").click()
        assert "als Zahlen" in pg.locator("#tpres").inner_text()
        pg.locator("#tpsec [data-s='laufen']").click()
        pg.wait_for_selector("#tpbody p.mut")                                          # keine Läufe: ehrliche Meldung statt Nullen
        assert "Keine Touren mit Höhendaten" in pg.locator("#tpbody").inner_text() and "0,0" not in pg.locator("#tpbody").inner_text()
        _shot(pg, "stat-tempo-desktop.png", "#tpsec")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_stats_sections_absent_without_data(pw, apps):
    pg = _page(pw, apps["empty"], "stats", None)
    try:
        assert pg.locator("#blsec").count() == 0 and pg.locator("#tpsec").count() == 0 and pg.locator("#main .inner").count() == 1
        assert "Belastung und Erholung" not in pg.locator("body").inner_text() and not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_stats_pending_zepp_tours_show_hint_and_job_button(pw, apps):
    pg = _page(pw, apps["pending"], "stats", "#blsec")
    try:
        pg.wait_for_selector("#bljob:not([hidden])", timeout=15000)
        t = pg.locator("#blsec").inner_text()
        assert "Für 3 Zepp-Touren liegen noch keine Uhr-Werte vor." in t and "Uhr-Daten aller Touren laden" in t
        assert pg.locator("#blsec .blbar, #blsec .blpart").count() == 0                  # nichts als 0 gezeichnet
        pg.locator("#blsec details[data-trf='bl_hint'] summary").click()
        assert "beim ersten Öffnen einer Tour gespeichert" in pg.locator("#blsec").inner_text()
        assert pg.locator("#tpsec").count() == 0
        _shot(pg, "stat-belastung-offen.png", "#blsec")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_tour_page_fatigue_and_slope_sections(pw, apps):
    pg = _page(pw, apps["full"], f"tour/{apps['fat']}", "#uhrcard")
    try:
        pg.wait_for_selector("#steigcard", timeout=15000)
        f = pg.locator("#uhrcard details[data-trf='uhr_erm']")
        assert f.count() == 1 and not f.evaluate("e => e.open")                            # Detailtiefe zugeklappt, Kernaussage in der Zeile
        sm = f.locator("summary").inner_text()
        assert "Zweite Hälfte" in sm and "Tempo 17 % langsamer" in sm and "Puls +15 bpm" in sm
        f.locator("summary").click()
        assert "Deutlich langsamer in der zweiten Hälfte" in f.inner_text() and "Verglichen werden die ersten 4 und die letzten 4" in f.inner_text()
        assert pg.evaluate("localStorage.getItem('mt_trf_uhr_erm')") == "1"
        s = pg.locator("#steigcard details")
        assert not s.evaluate("e => e.open") and "Bergauf" in s.locator("summary").inner_text() and "km/h" in s.locator("summary").inner_text()
        s.locator("summary").click()
        assert pg.locator("#steigcard .utile").count() >= 2 and "Nur Bewegungszeit" in pg.locator("#steigcard").inner_text()
        ids = pg.evaluate("[...document.querySelectorAll('#profcard, #pulscard, #metcard, #uhrcard, #steigcard')].map(e => e.id)")
        assert ids.index("steigcard") == len(ids) - 1 and ids.index("uhrcard") < ids.index("steigcard")
        assert not pg.errors, pg.errors
        _shot(pg, "tour-desktop-uhr.png", "#uhrcard")
        _shot(pg, "tour-desktop-steig.png", "#steigcard")
    finally:
        pg.browser_.close()


def test_tour_page_without_track_has_no_slope_card_and_fold_state_survives_reload(pw, apps):
    pg = _page(pw, apps["full"], "tour/" + apps["g"], None)
    try:
        assert pg.locator("#steigcard").count() == 1                                        # g1 hat eine Strecke
    finally:
        pg.browser_.close()
    pg = _page(pw, apps["empty"], "tour/g0", None)
    try:
        assert pg.locator("#steigcard").count() == 0 and pg.locator("#uhrcard").count() == 0 and not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_mobile_390_no_horizontal_scroll(pw, apps):
    pg = _page(pw, apps["full"], "stats", "#blsec .blbar", width=390, height=844, dpr=2)
    try:
        pg.locator("#tpsec details.trsec > summary").click()
        pg.wait_for_selector("#tpbody .utile", timeout=15000)
        pg.locator("#blsec details[data-trf='bl_tab'] summary").click()
        pg.locator("#blsec details[data-trf='bl_note'] summary").click()
        pg.locator("#tpkm").fill("12,5"); pg.locator("#tpform button").click(); pg.wait_for_selector("#tpres .tpbig")
        assert pg.evaluate("document.documentElement.scrollWidth") <= 391
        over = pg.evaluate("[...document.querySelectorAll('#blsec *, #tpsec *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('.blscroll') && !e.closest('.tblw')).map(e => e.className || e.tagName).slice(0, 5)")
        assert not over, over
        _shot(pg, "stat-belastung-390.png", "#blsec")
        _shot(pg, "stat-tempo-390.png", "#tpsec")
    finally:
        pg.browser_.close()
    pg = _page(pw, apps["full"], f"tour/{apps['fat']}", "#steigcard", width=390, height=844, dpr=2)
    try:
        pg.locator("#uhrcard details[data-trf='uhr_erm'] summary").click()
        pg.locator("#steigcard summary").click()
        assert pg.evaluate("document.documentElement.scrollWidth") <= 391
        over = pg.evaluate("[...document.querySelectorAll('#steigcard *, #uhrcard *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('.utsp')).map(e => e.className || e.tagName).slice(0, 5)")
        assert not over, over
        _shot(pg, "tour-390-uhr.png", "#uhrcard")
        _shot(pg, "tour-390-steig.png", "#steigcard")
    finally:
        pg.browser_.close()


CONTRAST = """() => {
  const parse = s => s.match(/[\\d.]+/g).map(Number).slice(0, 3);
  const lin = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  const L = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
  const bg = el => { for (let e = el; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor; const a = c.match(/[\\d.]+/g); if (c !== 'rgba(0, 0, 0, 0)' && !(a.length === 4 && +a[3] === 0)) return parse(c); } return [255, 255, 255]; };
  const cr = (f, b) => { const l1 = L(f), l2 = L(b); return (Math.max(l1, l2) + .05) / (Math.min(l1, l2) + .05); };
  const out = [];
  for (const sel of SELS) document.querySelectorAll(sel).forEach((el, i) => { if (i > 2 || !el.textContent.trim()) return; out.push([sel, cr(parse(getComputedStyle(el).color), bg(el))]); });
  for (const [sel, prop] of GRAPH) { const el = document.querySelector(sel); if (el) { const cs = getComputedStyle(el); out.push(['Grafik ' + sel, cr(parse(cs[prop]), bg(el.closest('.panel') || document.body))]); } }
  return out;
}"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_contrast_stats_and_tour(pw, apps, scheme):
    pg = _page(pw, apps["full"], "stats", "#blsec .blbar", scheme=scheme, dpr=2)
    try:
        pg.locator("#tpsec details.trsec > summary").click()
        pg.wait_for_selector("#tpbody .utile", timeout=15000)
        pg.locator("#blsec details[data-trf='bl_tab'] summary").click()
        pg.locator("#blsec details[data-trf='bl_note'] summary").click()
        pg.locator("#tpkm").fill("12,5"); pg.locator("#tpform button").click(); pg.wait_for_selector("#tpres .tpbig")
        sels = ["#blsec .gt", "#blsec .gs", "#blkey", "#tpkey", "#blsec .blnow b", "#blsec .blnowd", "#blsec .utile b", "#blsec .utile span", "#blsec .utile small", "#blsec .uth", "#blsec .bllegend span",
                "#blsec .blsvg text", "#blsec .trft", "#blsec th", "#blsec td", "#blsec .blsel span", "#blsec .hrnote", "#tpsec .utile b", "#tpsec .utile span", "#tpsec .tpform label", "#tpres .tpbig", "#tpres .hrnote", "#tpsec .hrnote"]
        js = CONTRAST.replace("SELS", repr(sels)).replace("GRAPH", repr([["#blsec .blbar", "fill"], ["#blsec .blnone", "stroke"], ["#blsec .blgrid", "stroke"]]))
        res = pg.evaluate(js)
        names = {s for s, _c in res}
        assert {"#blsec .gt", "#blsec .blnow b", "#blsec .utile b", "#tpres .tpbig", "Grafik #blsec .blbar", "Grafik #blsec .blnone"} <= names
        bad = [(s, round(c, 2)) for s, c in res if c < (3.0 if s.startswith("Grafik") and "blgrid" not in s else 1.0 if "blgrid" in s else 4.5)]    # Text 4,5:1, Balken/Rahmen 3:1; Gitternetz absichtlich zurückhaltend
        assert not bad, bad
        _shot(pg, f"stat-belastung-{scheme}.png", "#blsec")
        _shot(pg, f"stat-tempo-{scheme}.png", "#tpsec")
    finally:
        pg.browser_.close()
    pg = _page(pw, apps["full"], f"tour/{apps['fat']}", "#steigcard", scheme=scheme, dpr=2)
    try:
        pg.locator("#uhrcard details[data-trf='uhr_erm'] summary").click()
        pg.locator("#steigcard summary").click()
        sels = ["#uhrcard .trft", "#uhrcard .trfk", "#uhrcard .utfat", "#steigcard .trft", "#steigcard .trfk", "#steigcard .utile b", "#steigcard .utile span", "#steigcard .utile small", "#steigcard .hrnote"]
        res = pg.evaluate(CONTRAST.replace("SELS", repr(sels)).replace("GRAPH", "[]"))
        assert {"#uhrcard .trfk", "#steigcard .utile small"} <= {s for s, _c in res}
        bad = [(s, round(c, 2)) for s, c in res if c < 4.5]
        assert not bad, bad
        _shot(pg, f"tour-{scheme}-uhr.png", "#uhrcard")
        _shot(pg, f"tour-{scheme}-steig.png", "#steigcard")
    finally:
        pg.browser_.close()


def test_english_translation(pw, apps):
    pg = _page(pw, apps["full"], "stats", "#blsec .blbar", locale="en-GB")
    try:
        pg.evaluate("localStorage.setItem('lang','en')"); pg.reload(); pg.wait_for_selector("#blsec .blbar", timeout=15000); pg.wait_for_timeout(800)
        t = pg.locator("#blsec").inner_text()
        assert "Load and recovery" in t and "Current compared with usual" in t and "Belastung" not in t.replace("Belastung", "", 0) or "Load" in t
        assert "Die härtesten" not in t and "Touren mit" not in t
    finally:
        pg.browser_.close()
