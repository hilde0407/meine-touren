"""3.60.1 Statistik-Gruppen (Oberfläche, Chromium): bestehende Gruppe „Wandern“ bleibt, Hinweis „Name wie eine Sportart – bitte umbenennen“ (auch beim Tippen),
Speichern verlangt einen anderen Namen; Beschriftung „<Name> = A + B + …“ mit Tooltip in Statistikfilter, Rekorden, Ziel-Auswahl und Aufteilung; Englisch."""
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
ALT = [{"id": "wan", "name": "Wandern", "sports": ["hike", "mountaineering"]}, {"id": "rad", "name": "Rad fahren", "sports": ["touringbicycle", "racebike", "mtb", "mtb_easy"]}]

SEED = """
import sys, os, time, json; sys.path.insert(0, {root!r}); os.environ['DATA_DIR'] = {data!r}
from app import db
db.init()
now = int(time.time())
for i, (tid, sp, km) in enumerate([("w1", "hike", 10), ("b1", "mountaineering", 8), ("r1", "touringbicycle", 30), ("m1", "mtb", 20), ("k1", "kayak", 4)]):
    ts = now - (20 + i * 2) * 86400
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (tid, "Tour " + tid, sp, ts, ts + 3600, km * 1000, 3600, 100 + i, 100, 48.0, 8.0, "tour_recorded", "local"))
db.put("stat_gruppen", json.dumps({alt!r}))
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    d = tmp_path_factory.mktemp("sg3601")
    data = d / "data"
    out = subprocess.run([sys.executable, "-c", SEED.format(root=str(ROOT), data=str(data), alt=ALT)], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
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


def _gruppen(url):
    return json.loads(urllib.request.urlopen(url + "/api/stats/gruppen", timeout=10).read())["gruppen"]


def _put(url, g):
    rq = urllib.request.Request(url + "/api/stats/gruppen", data=json.dumps({"gruppen": g}).encode(), method="PUT", headers={"content-type": "application/json"})
    urllib.request.urlopen(rq, timeout=10).read()


def _page(pw, url, lang="de", w=1280):
    b = pw.chromium.launch()
    ctx = b.new_context(locale={"de": "de-DE", "en": "en-GB"}[lang], viewport={"width": w, "height": 900}, service_workers="block")
    ctx.add_init_script(f"try {{ localStorage.setItem('lang', '{lang}'); localStorage.removeItem('admtab'); }} catch (e) {{}}")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    return b, pg, errs


def test_bestehende_gruppe_mit_aktivitaetsnamen_hinweis_und_umbenennen(pw, app):
    b, pg, errs = _page(pw, app)
    try:
        pg.goto(app + "/#/admin?tab=sportarten")
        pg.wait_for_selector("#sgp .sgg", timeout=TL)
        quiet(pg, 3000)
        sec = pg.locator("#sgp")
        expect(sec.locator(".sgg")).to_have_count(2)                                         # nicht gelöscht
        assert sec.locator("#sgn0").input_value() == "Wandern"                               # nicht umbenannt
        expect(sec.locator("#sgw0")).to_have_text("Name wie eine Sportart – bitte umbenennen")
        assert sec.locator("#sgw0").is_visible() and sec.locator("#sgw1").is_hidden() and sec.locator("#sgn0").get_attribute("aria-invalid") == "true"
        # Speichern verlangt einen anderen Namen (Fokus ins Feld), nichts wird gespeichert
        sec.locator("#sgsave").click()
        expect(sec.locator("#sgerr")).to_have_text("Gruppe 1: „Wandern“ heißt schon eine Sportart – bitte einen anderen Gruppennamen wählen")
        assert pg.evaluate("() => document.activeElement.id") == "sgn0" and _gruppen(app) == ALT
        # Hinweis beim Tippen: auch andere Schreibweisen und Sprachen
        sec.locator("#sgn1").fill(" mountain BIKE ")
        expect(sec.locator("#sgw1")).to_be_visible()
        sec.locator("#sgn1").fill("Rad fahren")
        expect(sec.locator("#sgw1")).to_be_hidden()
        sec.locator("#sgn0").fill("Wandern & Berg".replace("&", "und"))
        expect(sec.locator("#sgw0")).to_be_hidden()
        assert sec.locator("#sgn0").get_attribute("aria-invalid") is None
        sec.locator("#sgsave").click()
        expect(sec.locator("#sgok")).to_have_text("Gespeichert ✓ – gilt ab sofort in der Statistik.", timeout=TL)
        assert [g["name"] for g in _gruppen(app)] == ["Wandern und Berg", "Rad fahren"] and [g["id"] for g in _gruppen(app)] == ["wan", "rad"]
        assert not errs, errs
    finally:
        b.close()


def test_beschriftung_name_gleich_aktivitaeten(pw, app):
    _put(app, [{"id": "berg", "name": "Bergwandern", "sports": ["hike", "mountaineering"]}, {"id": "rad", "name": "Rad fahren", "sports": ALT[1]["sports"]}])
    b, pg, errs = _page(pw, app)
    try:
        pg.goto(app + "/#/stats")
        chip = pg.locator('#sch [data-s="sgrp:rad"]')
        expect(chip).to_have_text("Rad fahren = Radtour + Rennrad + Mountainbike + …", timeout=TL)
        assert chip.get_attribute("title") == "Rad fahren = Radtour + Rennrad + Mountainbike + Gravelbike"
        expect(pg.locator('#sch [data-s="sgrp:berg"]')).to_have_text("Bergwandern = Wandern + Bergsteigen")
        assert pg.locator('#sch [data-s="sgrp:berg"]').get_attribute("title") == "Bergwandern = Wandern + Bergsteigen"
        expect(pg.locator('[data-st="sportarten"] .rows, #stc-sportarten .rows').first).to_contain_text("Rad fahren = Radtour + Rennrad + Mountainbike + …")
        # Ziel-Auswahl und Zielname
        opt = pg.locator('#gsp option[value="sgrp:rad"]')
        if opt.count():
            assert opt.text_content() == "Rad fahren = Radtour + Rennrad + Mountainbike + …" and opt.get_attribute("title").endswith("+ Gravelbike")
        assert pg.evaluate("() => goalSportName('sgrp:berg')") == "Bergwandern = Wandern + Bergsteigen"
        # Rekorde
        pg.goto(app + "/#/records?s=")
        a = pg.locator('a.chip[href="#/records?s=sgrp%3Arad"]')
        expect(a).to_contain_text("Rad fahren = Radtour + Rennrad + Mountainbike + …", timeout=TL)
        assert a.get_attribute("title") == "Rad fahren = Radtour + Rennrad + Mountainbike + Gravelbike"
        assert not errs, errs
    finally:
        b.close()


def test_englisch(pw, app):
    _put(app, [{"id": "berg", "name": "Bergwandern", "sports": ["hike", "mountaineering"]}])
    b, pg, errs = _page(pw, app, lang="en", w=390)
    try:
        pg.goto(app + "/#/stats")
        expect(pg.locator('#sch [data-s="sgrp:berg"]')).to_have_text("Bergwandern = Hiking + Mountaineering", timeout=TL)
        pg.goto(app + "/#/admin?tab=sportarten")
        pg.wait_for_selector("#sgp .sgg", timeout=TL)
        quiet(pg, 3000)
        pg.locator("#sgn0").fill("Hiking")
        expect(pg.locator("#sgw0")).to_have_text("Same name as a sport – please rename")
        pg.locator("#sgsave").click()
        expect(pg.locator("#sgerr")).to_have_text("Group 1: “Hiking” is already the name of a sport – please choose a different group name", timeout=TL)
        assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert not errs, errs
    finally:
        b.close()
