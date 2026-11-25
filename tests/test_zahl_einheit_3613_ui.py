"""3.61.3 Zahl und Einheit bleiben zusammen, Gruppenname reicht (Browser, Chromium, 1440 px und 390 px mit 150 % Systemschrift):
Jahresrückblick (#/recap/<Jahr>) und Baustein „Sportarten“ der Statistik zeigen rechts „756 km, 68 %“ in EINER Zeile (Wertzelle: ein einziges Rechteck, nicht höher als 1,6 Zeilen, kein Überlauf),
auch wenn links die Beschriftung einer Statistik-Gruppe steht („Wandern (gesamt)“, Zusammensetzung nur im Tooltip). In der Anzeige steht kein „ = “ und kein „ + “.
Die Gruppen werden wie in Verwaltung → Sportarten über die Schnittstelle /api/stats/gruppen angelegt. Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from tests.helpers_ui import free_port, quiet

ROOT = Path(__file__).resolve().parent.parent
pw_api = pytest.importorskip("playwright.sync_api")
expect = pw_api.expect
TL = 20000
GRP = [{"id": "wg", "name": "Wandern (gesamt)", "sports": ["hike", "mountaineering", "snowshoe"]},
       {"id": "rad", "name": "Rad (alle zusammen)", "sports": ["touringbicycle", "racebike", "mtb", "mtb_easy"]}]
SEED = """
import sys, os, time; sys.path.insert(0, {root!r}); os.environ['DATA_DIR'] = {data!r}
from app import db
db.init()
now = int(time.time())
for i, (tid, sp, km) in enumerate([("w1", "hike", 560), ("b1", "mountaineering", 150), ("s1", "snowshoe", 46), ("r1", "touringbicycle", 30), ("m1", "mtb", 20), ("k1", "kayak", 16), ("j1", "jogging", 5)]):
    ts = now - (2 + i) * 86400
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (tid, "Tour " + tid, sp, ts, ts + 3600, km * 1000, 3600, 100 + i, 100, 48.0, 8.0, "tour_recorded", "local"))
"""
ZOOM_JS = """(f) => {
  const els = [...document.querySelectorAll('body *')], sz = els.map(e => parseFloat(getComputedStyle(e).fontSize));
  els.forEach((e, i) => e.style.setProperty('font-size', (sz[i] * f) + 'px', 'important'));
}"""
# je Zeile: Wertzelle in einer Zeile, Beschriftung links ohne „ = “/„ + “, kein Überlauf der Zeile
ROWS_JS = """() => [...new Set([...document.querySelectorAll('.panel')].filter(p => (p.querySelector('h2') || {}).textContent === 'Sportarten').concat([...document.querySelectorAll('[data-st=sportarten], #stc-sportarten')]).flatMap(p => [...p.querySelectorAll('.rows .r')]))].map(r => {
  const v = r.lastElementChild, l = r.firstElementChild, cs = getComputedStyle(v), lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.3;
  return {txt: l.textContent.trim(), val: v.textContent, rects: v.getClientRects().length, h: v.getBoundingClientRect().height, lh,
          over: r.scrollWidth > r.clientWidth + 1 || v.getBoundingClientRect().right > r.getBoundingClientRect().right + 1, nowrap: cs.whiteSpace};
})"""
OVER = "() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)"


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    d = tmp_path_factory.mktemp("ze3613")
    data = d / "data"
    out = subprocess.run([sys.executable, "-c", SEED.format(root=str(ROOT), data=str(data))], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr
    port = free_port()
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(d / "p"), BACKUP_DIR=str(d / "bak"), MT_NO_SCHEDULER="1")
    pr = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(150):
        try:
            urllib.request.urlopen(url + "/api/version", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    rq = urllib.request.Request(url + "/api/stats/gruppen", data=json.dumps({"gruppen": GRP}).encode(), method="PUT", headers={"content-type": "application/json"})
    urllib.request.urlopen(rq, timeout=10).read()
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


def _shot(pg, name):
    d = os.environ.get("TS_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(Path(d) / name), full_page=True, timeout=60000)


def _pruefe(rows, schmal):
    assert len(rows) >= 3, rows
    gr = [r for r in rows if r["txt"] in ("Wandern (gesamt)", "Rad (alle zusammen)")]
    assert len(gr) == 2, rows                                                    # Gruppenname reicht, die Gruppen kommen vor
    for r in rows:
        assert " = " not in r["txt"] and " + " not in r["txt"], r                # Zusammensetzung nur im Tooltip
        assert r["rects"] == 1 and r["h"] <= 1.6 * r["lh"] and not r["over"] and r["nowrap"] == "nowrap", r      # „756 km, 68 %“ in einer Zeile
        assert " %" in r["val"] and " %" not in r["val"].replace(" %", "") and " km" in r["val"], r["val"]


@pytest.mark.parametrize("width,f", [(1440, 1), (390, 1.5)])
def test_rueckblick_und_sportarten_baustein_zahl_und_einheit_in_einer_zeile(pw, app, width, f):
    b = pw.chromium.launch()
    ctx = b.new_context(locale="de-DE", viewport={"width": width, "height": 900}, service_workers="block", device_scale_factor=1)
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    try:
        jahr = time.localtime().tm_year
        pg.goto(f"{app}/#/recap/{jahr}")
        pg.wait_for_function("() => [...document.querySelectorAll('.panel h2')].some(h => h.textContent === 'Sportarten')", timeout=TL)
        quiet(pg, 2000)
        if f != 1:
            pg.evaluate(ZOOM_JS, f)
            quiet(pg, 500)
        _shot(pg, f"rueckblick-{width}.png")
        _pruefe(pg.evaluate(ROWS_JS), width < 700)
        assert pg.evaluate(OVER) == 0
        assert pg.locator(".panel:has(h2:text-is('Sportarten')) .rows .r > span[title*=' = ']").count() == 2          # Zusammensetzung im Tooltip
        pg.goto(f"{app}/#/stats")
        pg.wait_for_selector("[data-st=sportarten] .rows .r", timeout=TL)
        quiet(pg, 2000)
        if f != 1:
            pg.evaluate(ZOOM_JS, f)
            quiet(pg, 500)
        _shot(pg, f"sportarten-baustein-{width}.png")
        _pruefe(pg.evaluate(ROWS_JS), width < 700)
        assert pg.evaluate(OVER) == 0
        assert not errs, errs
    finally:
        b.close()


def test_chip_zeigt_nur_den_namen_mit_tooltip_und_aria_label(pw, app):
    b = pw.chromium.launch()
    pg = b.new_context(locale="de-DE", viewport={"width": 1280, "height": 900}, service_workers="block").new_page()
    try:
        pg.goto(f"{app}/#/stats")
        chip = pg.locator('#sch [data-s="sgrp:wg"]')
        expect(chip).to_have_text("Wandern (gesamt)", timeout=TL)
        assert chip.get_attribute("title") == "Wandern (gesamt) = Wandern + Bergsteigen + Schneeschuhwandern" and chip.get_attribute("aria-label") == chip.get_attribute("title")
    finally:
        b.close()
