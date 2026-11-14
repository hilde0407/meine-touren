"""3.11.0 – Oberfläche „Training laut Uhr“ (Browser, Chromium): Abschnitt erscheint nur mit Daten, Kacheln, Pulszonen, Kilometer-Splits, Wetter, Quelle, Hinweise,
Neu laden, offline aus der Zusatzdatei, Handybreite (390 px), Kontrast hell/dunkel, Übersetzung. Zepp ist nachgebaut (konstruierte Werte in den echten Bereichen).
Mit UHR_SHOTS=<Ordner> werden Screenshots abgelegt."""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
T0 = 1750000000
ZA, ZL, ZN = f"z{T0 + 10}", f"z{T0 + 86400 + 10}", f"z{T0 + 2 * 86400 + 10}"


class UiApi:
    """Nachgebautes Zepp: erster Verlauf mit 312 kcal, jeder spätere mit 999 kcal; Splits je Training."""
    n = 0

    def __init__(self, st):
        self.st = st

    def history(self):
        UiApi.n += 1
        from tests.test_uhrtraining import summary
        kc = "312" if UiApi.n == 1 else "999"
        a = summary(self.st[0], calorie=kc)
        b = summary(self.st[1], dis="12400", run_time="9000", total_step="19800", heart_range="1500,100;2400,118;3000,135;1500,150;450,160;150,168", calorie=kc)
        return [a, b]

    def detail(self, s):
        from tests.test_uhrtraining import kilo
        if int(s["trackid"]) == self.st[0]:
            return {"kilo_pace": kilo()}
        rows = [f"{i},{700 + (i * 37) % 120},0,0,{110 + i * 2},0,0,300,0,{54 + i % 3},0,0,0,40" for i in range(12)]
        rows.append("12,285,0,0,150,0,0,300,0,56,0,0,0,40")            # Teilkilometer: 400 m in 285 s
        return {"kilo_pace": ";".join(rows)}


SEED = r"""
import sys, os; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db, config, metrics
from tests.test_uhrdiag import _gpx
db.init()
db.execute("INSERT INTO devices(name,kind,model,since,until,active,note,zsrc) VALUES('Amazfit Cheetah Pro','zepp','Cheetah Pro','','',1,'','')")
db.execute("INSERT INTO devices(name,kind,model,since,until,active,note,zsrc) VALUES('Garmin Forerunner 255','garmin','Forerunner 255','','',1,'','')")
def tour(tid, ts, kind, name, dist, dur):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,'hike',?,?,?,?,100,100,'t','komoot')", (tid, name, ts, ts + dur, dist, dur))
    db.execute("INSERT OR REPLACE INTO tour_source(tour_id,src,name) VALUES(?,?,'')", (tid, kind))
config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
tour(%(za)r, %(t0)d + 10, "zepp", "Rundweg Eins", 5400, 3600)
tour(%(zl)r, %(t0)d + 86400 + 10, "zepp", "Lange Runde", 12400, 9000)
tour(%(zn)r, %(t0)d + 2 * 86400 + 10, "zepp", "Ohne Zepp-Training", 5000, 3000)
tour("g1", %(t0)d + 100 * 86400, "garmin", "Garmin-Runde", 5000, 3000)
for t in (%(za)r, %(zl)r, %(zn)r, "g1"):
    _gpx(t)
metrics.store(%(za)r, {"v": 1, "src": "zepp", "device": "Amazfit/Zepp", "t0": %(t0)d + 10, "t": [0, 1, 2, 3, 4, 5, 6], "series": {"speed": [3.0] * 7, "cad": [150.0] * 7}, "sum": {"kcal": 512}})
"""

LAUNCH = r"""
import sys, os; sys.path.insert(0, %(root)r)
from app import sync
from tests.test_uhrtraining_ui import UiApi
if %(nozepp)r:
    def nope():
        raise RuntimeError("Zepp-Zugangsdaten fehlen (Einstellungen)")
    sync._zepp_api = nope
else:
    sync._zepp_api = lambda: UiApi((%(t0)d + 10, %(t0)d + 86400 + 10))
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


def _serve(data, tmp, nozepp):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / f"launch{int(nozepp)}.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port, "nozepp": nozepp, "t0": T0})
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    pr = subprocess.Popen([sys.executable, str(script)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    return pr, url


@pytest.fixture(scope="module")
def apps(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    d = tmp_path_factory.mktemp("uhrtr")
    data = d / "data"
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data), "t0": T0, "za": ZA, "zl": ZL, "zn": ZN}], capture_output=True, text=True, cwd=ROOT,
                         env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr
    p1, u1 = _serve(data, d, False)
    for t in (ZA, ZL):                                                   # beide Touren einmal laden: Zusatzdateien entstehen (für den Offline-Test)
        urllib.request.urlopen(f"{u1}/api/tours/{t}/uhr-training", timeout=20).read()
    p2, u2 = _serve(data, d, True)
    yield {"zepp": u1, "nozepp": u2}
    for p in (p1, p2):
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


def _page(pw, url, tid, width=1280, height=1000, scheme="light", dpr=1, locale="de-DE", wait="#uhrcard"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale=locale, viewport={"width": width, "height": height}, color_scheme=scheme, device_scale_factor=dpr)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(url) else r.continue_())
    pg.goto(f"{url}/#/tour/{tid}")
    if wait:
        pg.wait_for_selector(wait, timeout=10000)
    else:
        pg.wait_for_selector("#profcard", timeout=10000)
        pg.wait_for_timeout(1500)
    pg.wait_for_timeout(300)
    pg.browser_ = b
    return pg


def _shot(pg, name, sel="#uhrcard"):
    d = os.environ.get("UHR_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        pg.locator(sel).scroll_into_view_if_needed()
        pg.locator(sel).screenshot(path=str(Path(d) / name))


def test_section_content_and_order(pw, apps):
    pg = _page(pw, apps["zepp"], ZA)
    try:
        c = pg.locator("#uhrcard")
        t = c.inner_text()
        assert t.startswith("Training laut Uhr") and "Amazfit Cheetah Pro" in t and "Quelle:" in t
        tiles = {x.locator("span").first.inner_text(): x.locator("b").inner_text() for x in c.locator(".utile").all()}
        assert tiles["Trainingseffekt (aerob)"] == "3,2" and tiles["Trainingseffekt (anaerob)"] == "1,4" and tiles["Trainingsbelastung"] == "96"
        assert tiles["Anstrengung (deine Angabe)"] == "5" and tiles["Kalorien"] == "312" and tiles["Pausenzeit"] == "4 min"
        assert tiles["Puls Ø"] == "118" and tiles["Puls höchster"] == "152" and tiles["Schrittfrequenz Ø"] == "112"
        assert "310" in t and "m Aufstieg" in t and "m höchster Punkt" in t and "Höhenmeter laut Uhr" in t
        assert c.locator(".br6 span").count() == 6 and "Pulszonen laut Uhr" in t and "bis 168 bpm" in t
        assert c.locator(".utc").count() == 6 and c.locator(".utc.part").count() == 1 and "Tempo je Kilometer" in t
        assert "10:50" in c.locator(".utv").first.inner_text() and "0,4 km" in t and "Puls (bpm)" in t and "Schritte/min" in t
        assert "21" in t and "°C Temperatur" in t and "74" in t and "% Luftfeuchte" in t and "Wetter laut Uhr" in t
        assert "nicht mit Garmin vergleichbar" in t and "Von Zepp neu laden" in t
        for bad in ("-1", "-274", "-361", "2004831", "avg_pace", "NaN", "undefined", "null"):
            assert bad not in t, bad
        assert "title" in c.locator(".utc").first.evaluate("e => Object.keys(e.attributes).map(a => e.attributes[a].name).join()") and "Kilometer 1: 10:50 min/km, Puls 112 bpm, 112 Schritte/min" == c.locator(".utc").first.get_attribute("title")
        ids = pg.evaluate("[...document.querySelectorAll('#profcard, #pulscard, #metcard, #uhrcard')].map(e => e.id)")
        assert ids.index("metcard") < ids.index("uhrcard") < ids.index("pulscard")        # 3.15.0: Messwerte, Training laut Uhr, Puls (je Gerät ein Block)
        assert not pg.errors, pg.errors
        _shot(pg, "uhrtraining-desktop.png")
    finally:
        pg.browser_.close()


def test_section_absent_without_data(pw, apps):
    for tid in (ZN, "g1"):
        pg = _page(pw, apps["zepp"], tid, wait=None)
        try:
            assert pg.locator("#uhrcard").count() == 0 and pg.locator(".utiles").count() == 0 and "Training laut Uhr" not in pg.locator("body").inner_text()
            assert not pg.errors, pg.errors
        finally:
            pg.browser_.close()


def test_offline_from_sidecar_and_reload_error_keeps_values(pw, apps):
    pg = _page(pw, apps["nozepp"], ZA)
    try:
        assert pg.locator(".utile", has_text="Kalorien").locator("b").inner_text() == "312" and pg.locator(".utc").count() == 6          # ohne Zepp-Zugang aus der Zusatzdatei
        pg.click("#utneu")
        pg.wait_for_selector("#utmsg:not(:empty)", timeout=10000)
        assert "kein Zepp-Zugang" in pg.locator("#utmsg").inner_text() and pg.locator(".utile", has_text="Kalorien").locator("b").inner_text() == "312"
        assert pg.locator("#utneu").is_enabled() and not pg.errors, pg.errors
        _shot(pg, "uhrtraining-ohne-zugang.png", "#utneu")
    finally:
        pg.browser_.close()


def test_reload_button_updates_values(pw, apps):
    pg = _page(pw, apps["zepp"], ZL)
    try:
        k = pg.locator(".utile", has_text="Kalorien").locator("b")
        assert k.inner_text() in ("312", "999")
        pg.click("#utneu")
        pg.wait_for_selector("#utmsg:has-text('Neu von Zepp geladen')", timeout=10000)
        assert k.inner_text() == "999" and pg.locator(".utc").count() == 13 and pg.locator("#utneu").inner_text() == "Von Zepp neu laden"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_mobile_390_no_horizontal_page_scroll(pw, apps):
    for tid, n in ((ZA, 6), (ZL, 13)):
        pg = _page(pw, apps["nozepp"], tid, width=390, height=844, dpr=2)
        try:
            assert pg.locator(".utc").count() == n
            assert pg.evaluate("document.documentElement.scrollWidth") <= 391
            over = pg.evaluate("[...document.querySelectorAll('#uhrcard *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('.utsp')).map(e => e.className || e.tagName).slice(0, 5)")
            assert not over, over
            assert pg.evaluate("document.querySelector('#uhrcard').getBoundingClientRect().right") <= 391
            if n == 13:
                assert pg.evaluate("(() => { const s = document.querySelector('.utsp'); return s.scrollWidth > s.clientWidth; })()")          # lange Tour: nur der Diagramm-Kasten scrollt
            _shot(pg, f"uhrtraining-390-{tid[-4:]}.png")
        finally:
            pg.browser_.close()


def _contrast_js():
    return """() => {
      const parse = s => { const m = s.match(/[\\d.]+/g).map(Number); return m.slice(0, 3); };
      const lin = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
      const L = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
      const bg = el => { for (let e = el; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor; const a = c.match(/[\\d.]+/g); if (c !== 'rgba(0, 0, 0, 0)' && !(a.length === 4 && +a[3] === 0)) return parse(c); } return [255, 255, 255]; };
      const cr = (f, b) => { const l1 = L(f), l2 = L(b); return (Math.max(l1, l2) + .05) / (Math.min(l1, l2) + .05); };
      const out = [];
      for (const sel of ['#uhrcard h3', '.uth', '.utsrc', '.utile b', '.utile span', '.utile small', '.utv', '.utk', '.utp', '.utl', '.utnotes li', '.hrleg', '#utneu', '#utmsg']) {
        document.querySelectorAll('#uhrcard ' + sel).forEach((el, i) => { if (i > 3 || !el.innerText.trim()) return; out.push([sel, cr(parse(getComputedStyle(el).color), bg(el))]); });
      }
      const bar = document.querySelector('#uhrcard .utc i');
      out.push(['Balken (Grafik)', cr(parse(getComputedStyle(bar).backgroundColor), bg(bar.parentElement))]);
      return out;
    }"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_contrast_light_and_dark(pw, apps, scheme):
    pg = _page(pw, apps["nozepp"], ZA, scheme=scheme, dpr=2)
    try:
        res = pg.evaluate(_contrast_js())
        sels = {s for s, _c in res}
        assert {".utile b", ".utile span", ".utv", ".utk", ".utl", ".utnotes li", "#utneu", ".uth"} <= sels
        bad = [(s, round(c, 2)) for s, c in res if c < (3.0 if s.startswith('Balken') else 4.5)]          # Text 4,5:1, Grafik (Balken) 3:1
        assert not bad and 'Balken (Grafik)' in sels, bad
        _shot(pg, f"uhrtraining-{scheme}.png")
    finally:
        pg.browser_.close()


def test_translated_in_english(pw, apps):
    pg = _page(pw, apps["nozepp"], ZA, locale="en-US")
    try:
        pg.wait_for_selector("#uhrcard h3:has-text('Training according')", timeout=5000)
        t = pg.locator("#uhrcard").inner_text()
        for x in ("Training effect (aerobic)", "Heart rate zones according to the watch", "Pace per kilometre", "Weather according to the watch", "Reload from Zepp", "m ascent", "Zepp scale"):
            assert x in t, x
        assert pg.locator(".utc").first.get_attribute("title").startswith("Kilometre 1: 10:50 min/km, heart rate 112 bpm, 112 steps/min")
    finally:
        pg.browser_.close()
