"""3.60.1 Karte und Auswahl der Sportarten (Chromium): #/map zeigt die Sportarten mit Touren nach Kategorien in Katalog-Reihenfolge, die Statistik-Gruppen als Chips
(ein Klick schaltet alle Mitglieder), eigene Farbe je Sportart (Chip-Punkt = Strecke = Legende), dieselbe Reihenfolge in Statistik, Rekorden und Baustein-Filter."""
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
TL = 15000
RAD = {"id": "rad", "name": "Rad fahren", "sports": ["touringbicycle", "mtb", "e_touringbicycle"]}

SEED = """
import sys, os, time, json; sys.path.insert(0, {root!r}); os.environ['DATA_DIR'] = {data!r}
from app import db
db.init()
now = int(time.time())
# Reihenfolge der Einfügung absichtlich anders als der Katalog (und Anzahl je Sportart verschieden)
spec = [("kayak", 1), ("mtb", 4), ("hike", 3), ("e_touringbicycle", 2), ("skialpin", 1), ("touringbicycle", 5), ("snowshoe", 1), ("golf", 1)]
i = 0
for sp, n in spec:
    for j in range(n):
        i += 1
        ts = now - (10 + i) * 86400
        lat, lng = 47.5 + i * 0.01, 11.0 + i * 0.01
        db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (f"t{{i}}", f"Tour {{i}}", sp, ts, ts + 3600, 5000 + i * 100, 3600, 100, 100, lat, lng, "tour_recorded", "local"))
db.put("stat_gruppen", json.dumps([{rad!r}]))
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    d = tmp_path_factory.mktemp("ka3601")
    data = d / "data"
    out = subprocess.run([sys.executable, "-c", SEED.format(root=str(ROOT), data=str(data), rad=RAD)], capture_output=True, text=True, cwd=ROOT,
                         env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr
    port = free_port()
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(d / "p"), BACKUP_DIR=str(d / "bak"), MT_NO_SCHEDULER="1")
    pr = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(150):
        try:
            urllib.request.urlopen(url + "/api/version", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
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


ORDER = ["hike", "touringbicycle", "mtb", "e_touringbicycle", "skialpin", "snowshoe", "kayak", "other"]       # Katalog-Reihenfolge der vorhandenen Sportarten


def _page(pw, url, lang="de"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale={"de": "de-DE", "en": "en-GB"}[lang], viewport={"width": 1280, "height": 900}, service_workers="block")
    ctx.add_init_script(f"try {{ localStorage.setItem('lang', '{lang}'); }} catch (e) {{}}")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(url) else r.continue_())
    return b, pg, errs


def test_karte_kategorien_gruppen_und_farben(pw, app):
    b, pg, errs = _page(pw, app)
    try:
        pg.goto(app + "/#/map")
        pg.wait_for_selector("#ms .chip[data-s]", timeout=TL)
        quiet(pg, 3000)
        assert pg.eval_on_selector_all("#ms .mscl", "l => l.map(x => x.textContent)") == ["Statistik-Gruppen", "Zu Fuß", "Rad", "Winter", "Wasser", "Outdoor und Sonstige"]   # 3.61.0: Gruppen zuerst (Leitfaden 2.6)
        assert pg.eval_on_selector_all("#ms .chip[data-s]", "l => l.map(x => x.dataset.s)") == ORDER                # nur vorhandene, Katalog-Reihenfolge, „golf“ als Sonstiges
        g = pg.locator('#ms .chip[data-g="sgrp:rad"]')
        assert g.inner_text().strip() == "Rad fahren = Radtour + Mountainbike + E-Bike" and g.get_attribute("title") == "Rad fahren = Radtour + Mountainbike + E-Bike"
        # Farben: drei Rad-Sportarten deutlich verschieden; Chip-Punkt = sCol = Strecke
        cols = pg.evaluate("""() => Object.fromEntries([...document.querySelectorAll('#ms .chip[data-s] i')].map(i => [i.parentElement.dataset.s, getComputedStyle(i).backgroundColor]))""")
        assert len({cols["touringbicycle"], cols["mtb"], cols["e_touringbicycle"]}) == 3 and len(set(cols.values())) == len(ORDER)
        same = pg.evaluate("""() => { const t = TOURS.find(x => x.sport === 'mtb'), d = document.createElement('i'); d.style.background = trackStyle(t).color; document.body.appendChild(d);
            const c = getComputedStyle(d).backgroundColor; d.remove(); return c; }""")
        assert same == cols["mtb"]
        # Gruppe aus: alle Mitglieder aus, Zahl der Touren sinkt; ein Mitglied wieder an: Gruppe bleibt aus; Gruppe an: alle an
        n0 = pg.evaluate("() => TOURS.length")
        g.click()
        expect(g).to_have_attribute("aria-pressed", "false")
        assert sorted(pg.evaluate("() => [...mapOff()]")) == ["e_touringbicycle", "mtb", "touringbicycle"]
        for s in RAD["sports"]:
            expect(pg.locator(f'#ms .chip[data-s="{s}"]')).to_have_attribute("aria-pressed", "false")
        pg.locator('#ms .chip[data-s="mtb"]').click()
        expect(pg.locator('#ms .chip[data-s="mtb"]')).to_have_attribute("aria-pressed", "true")
        expect(g).to_have_attribute("aria-pressed", "false")
        g.click()
        expect(g).to_have_attribute("aria-pressed", "true")
        assert pg.evaluate("() => mapOff().size") == 0 and n0 == 18
        # dieselbe Auswahl in Statistik, Rekorden und Baustein-Filter
        auswahl = pg.evaluate("() => sportOrder(TOURS.map(t => t.sport))")
        assert auswahl == ["sgrp:rad"] + ORDER
        flf = pg.evaluate("""() => { const d = document.createElement('div'); d.innerHTML = flField({kind: 'sports'}, {sports: []}, 0);
            return [[...d.querySelectorAll('.flcat')].map(x => x.textContent), [...d.querySelectorAll('input[value]')].map(x => x.value)]; }""")
        assert flf[0] == ["Statistik-Gruppen", "Zu Fuß", "Rad", "Winter", "Wasser", "Outdoor und Sonstige"] and flf[1] == auswahl
        pg.goto(app + "/#/stats")
        pg.wait_for_selector("#sch [data-s]", timeout=TL)
        quiet(pg, 2000)
        assert [s for s in pg.eval_on_selector_all("#sch [data-s]", "l => l.map(x => x.dataset.s)") if s] == auswahl
        pg.goto(app + "/#/records?s=")
        pg.wait_for_selector('a.chip[href^="#/records?s="]', timeout=TL)
        quiet(pg, 2000)
        hrefs = pg.eval_on_selector_all('a.chip[href^="#/records?s="]', "l => l.map(x => decodeURIComponent(x.getAttribute('href').split('s=')[1]))")
        assert [h for h in hrefs if h] == auswahl
        assert not errs, errs
    finally:
        b.close()


def test_karte_englisch(pw, app):
    b, pg, errs = _page(pw, app, "en")
    try:
        pg.goto(app + "/#/map")
        pg.wait_for_selector("#ms .chip[data-s]", timeout=TL)
        quiet(pg, 3000)
        assert pg.eval_on_selector_all("#ms .mscl", "l => l.map(x => x.textContent)")[:3] == ["Statistics groups", "On foot", "Bike"]
        assert pg.locator('#ms .chip[data-g="sgrp:rad"]').inner_text().strip() == "Rad fahren = Bike ride + Mountain bike + E-bike"
        assert not errs, errs
    finally:
        b.close()
