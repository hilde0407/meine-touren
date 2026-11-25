"""3.50.0 – Laufen und Schneeschuh in der Oberfläche (Browser, Chromium): Prüfen → „Läufe von der Uhr“ (einzeln und gesammelt, mit Rückfrage), Steilheit und
Sicherheitsnotiz bei Schneeschuh, 390 px hell/dunkel, vier Sprachen. 3.59.0: Schneeschuh ist wieder eine eigene Sportart (in Auswahl, Filter und Statistik).
Screenshots mit TS_SHOTS=<Ordner>."""
import os
import socket
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.test_bausteine_ui import T, _shot  # noqa: F401
from tests.test_bausteine_ui import pw  # noqa: F401  (Fixture)
from tests.test_tourseite_ui import LAUNCH, _wait
from tests.helpers_ui import quiet, settled, set_lang

ROOT = Path(__file__).resolve().parent.parent

SEED = r"""
import sys, os, time, math; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db, config, routes
db.init()
now = int(time.time())
def loop(n=120):
    return [(47.5 + 0.01 * math.sin(2 * math.pi * i / (n - 1)), 11.0 + 0.012 * (1 - math.cos(2 * math.pi * i / (n - 1))), 1200 + 260 * math.sin(i / 9), i * 40000) for i in range(n)]
def tour(tid, days, sport, dist, dur, src="komoot", name=None):
    ts = now - days * 86400
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,'t',?)",
               (tid, name or "Tour " + tid, sport, ts, ts + dur, dist, dur, 300, 300, 47.5, 11.0, src))
    routes.store(tid, loop())
    return ts
tour("h1", 30, "hike", 12000, 14400, name="Hüttenrunde")
tour("h2", 20, "hike", 9000, 10800, name="Seeweg")
tour("s1", 60, "snowshoe", 7000, 12600, name="Schneeschuh am Hörnle")
k1 = tour("k1", 10, "hike", 8000, 2800, name="Abendlauf Isar")
k2 = tour("k2", 5, "hike", 10000, 3400, name="Lauf am Kanal")
tour("r1", 3, "jogging", 6000, 2000, name="Runde im Park")
def wo(tid, start, ztype, kid, status):
    db.execute("INSERT INTO workouts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (tid, start, start + 3000, ztype, "hike", 8000, 3000, None, status, kid, "", now))
wo(9001, k1, 1, "k1", "in_komoot")
wo(9002, k2 + 40, 1, None, "in_komoot")
db.execute("INSERT INTO goals(year,sport,metric,target,period) VALUES(?,?,?,?,?)", (time.localtime().tm_year, "hike", "km", 500, "year"))
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    tmp = tmp_path_factory.mktemp("sp350")
    data = tmp / "data"
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data)}], capture_output=True, text=True, cwd=ROOT, env=env)
    assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / "launch.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    pr = subprocess.Popen([sys.executable, str(script)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    yield {"url": url, "data": data}
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)


def _q(app, sql, args=()):
    c = sqlite3.connect(app["data"] / "komoot_hub.sqlite", timeout=15)
    try:
        r = c.execute(sql, args).fetchall()
        c.commit()
        return r
    finally:
        c.close()


def _reset(app):
    _q(app, "UPDATE tours SET sport='hike' WHERE id IN ('k1','k2')")
    _q(app, "DELETE FROM tour_sport")


def _page(pw, app, route, width=1280, scheme="light"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale="de-DE", viewport={"width": width, "height": 900 if width > 500 else 844}, color_scheme=scheme, device_scale_factor=1, reduced_motion="reduce")
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.browser_ = b
    pg.goto(app["url"] + "/" + route)
    pg.wait_for_function("() => document.querySelectorAll('#main *').length > 3", timeout=T)
    quiet(pg, 4000)
    return pg


def test_schneeschuh_bleibt_beim_start_schneeschuh(app):
    assert _q(app, "SELECT sport FROM tours WHERE id='s1'") == [("snowshoe",)]
    assert _q(app, "SELECT tag FROM tour_tags WHERE id='s1'") == []


def test_pruefen_laeufe_von_der_uhr(pw, app):
    _reset(app)
    pg = _page(pw, app, "#/check")
    box = pg.locator("#zlauf")
    expect(box).to_be_visible(timeout=T)
    expect(box.locator("h2")).to_have_text("Läufe von der Uhr")
    expect(box.locator(".r")).to_have_count(2)
    expect(box).to_contain_text("Komoot-Tour")
    expect(box).to_contain_text("passt über die Startzeit")
    expect(pg.locator("#zlall")).to_have_text("Alle 2 auf Laufen umstellen")
    box.locator('.r[data-id="k1"] [data-zl]').click()
    pg.wait_for_function("() => document.querySelectorAll('#zlauf .r').length === 1", timeout=T)
    assert _q(app, "SELECT sport FROM tours WHERE id='k1'") == [("jogging",)]
    assert _q(app, "SELECT sport FROM tour_sport WHERE id='k1'") == [("jogging",)]
    quiet(pg, 3000)
    pg.click("#zlall")
    dlg = pg.locator(".uidlg .uibox")
    expect(dlg).to_be_visible(timeout=T)
    expect(dlg).to_contain_text("Alle 1 Touren auf „Laufen“ umstellen?")
    dlg.locator("button", has_text="Abbrechen").click()
    expect(dlg).to_have_count(0, timeout=T)
    assert _q(app, "SELECT sport FROM tours WHERE id='k2'") == [("hike",)]
    pg.click("#zlall")
    expect(dlg).to_be_visible(timeout=T)
    dlg.locator("button", has_text="Umstellen").click()
    expect(pg.locator("#zlauf")).to_have_count(0, timeout=T)
    assert _q(app, "SELECT sport FROM tours WHERE id='k2'") == [("jogging",)]
    assert not pg.errors
    pg.browser_.close()


def test_sportart_schneeschuh_in_filter_und_auswahl(pw, app):
    pg = _page(pw, app, "#/stats?s=snowshoe")
    pg.wait_for_selector("#sch", timeout=T)
    on = pg.eval_on_selector_all("#sch .chip.on", "l => l.map(x => x.textContent.trim())")
    assert on == ["Schneeschuhwandern"]
    chips = pg.eval_on_selector_all("#sch .chip", "l => l.map(x => x.dataset.s)")
    assert "snowshoe" in chips and "jogging" in chips
    r = pg.evaluate("""() => ({name: sName('snowshoe'), col: sCol('snowshoe') === sCol('hike'), keys: Object.keys(SPORT), grp: sportGrp('snowshoe'),
        fl: flSport({sport: 'hike'}, {sports: ['snowshoe']}), fl2: flSport({sport: 'jogging'}, {sports: ['snowshoe']}),
        sn: isSnowshoe({sport: 'hike', tags: 'Gipfel|Schneeschuh'}), sn2: isSnowshoe({sport: 'hike', tags: ''}), sn3: isSnowshoe({sport: 'hike', tags: ['Schneeschuh']})})""")
    assert r == {"name": "Schneeschuhwandern", "col": False, "keys": r["keys"], "grp": "foot", "fl": False, "fl2": False, "sn": True, "sn2": False, "sn3": True}
    assert "snowshoe" in r["keys"] and "jogging" in r["keys"] and "kayak" in r["keys"]
    assert not pg.errors
    pg.browser_.close()


def test_schneeschuh_tour_behaelt_steilheit_und_sicherheit(pw, app):
    pg = _page(pw, app, "#/tour/s1")
    expect(pg.locator("#sfigs")).to_contain_text("der Strecke über 30°", timeout=T)
    expect(pg.locator("#safety")).to_have_count(1, timeout=T)
    expect(pg.locator(".tlsubfig .tag, .mt18 .tag").first).to_have_text("Schneeschuhwandern")
    pg.goto(app["url"] + "/#/tour/h1")
    pg.wait_for_function("() => location.hash === '#/tour/h1' && !!document.querySelector('#sfigs')", timeout=T)
    quiet(pg, 3000)
    assert "über 30°" not in pg.inner_text("#sfigs") and pg.locator("#safety").count() == 0
    assert not pg.errors
    pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_pruefen_mobil(pw, app, scheme):
    _reset(app)
    pg = _page(pw, app, "#/check", width=390, scheme=scheme)
    assert pg.evaluate("() => document.documentElement.classList.contains('mob')")
    box = pg.locator("#zlauf")
    expect(box.locator(".r")).to_have_count(2, timeout=T)
    settled(pg)
    assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    bb = pg.locator("#zlall").bounding_box()
    assert bb and bb["x"] >= 0 and bb["x"] + bb["width"] <= 391
    for b in box.locator("[data-zl]").all():
        x = b.bounding_box()
        assert x["x"] + x["width"] <= 391 and x["height"] >= 28
    box.scroll_into_view_if_needed()
    d = os.environ.get("TS_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        box.screenshot(path=str(Path(d) / f"pruefen-laeufe-390-{scheme}.png"))
    pg.goto(app["url"] + "/#/stats")
    pg.wait_for_selector("#sch", timeout=T)
    settled(pg)
    chips = pg.eval_on_selector_all("#sch .chip", "l => l.map(x => x.textContent.trim())")
    assert "Laufen" in chips and "Schneeschuhwandern" in chips                          # 3.59.0: Schneeschuh ist wieder eigene Sportart
    assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    if d:
        pg.locator("#sch").screenshot(path=str(Path(d) / f"statistik-sportarten-390-{scheme}.png"))
    pg.goto(app["url"] + "/#/tour/s1")
    expect(pg.locator("#sfigs")).to_contain_text("über 30°", timeout=T)
    settled(pg)
    if d:
        pg.screenshot(path=str(Path(d) / f"tour-schneeschuh-390-{scheme}.png"))
    assert not pg.errors
    pg.browser_.close()


@pytest.mark.parametrize("lang,titel,knopf", [("en", "Runs from the watch", "Switch all 2 to running"), ("fr", "Courses de la montre", "Passer les 2 en course à pied"),
                                              ("es", "Carreras del reloj", "Cambiar las 2 a correr")])
def test_pruefen_sprachen(pw, app, lang, titel, knopf):
    _reset(app)
    pg = _page(pw, app, "#/check")
    set_lang(pg, lang)
    pg.goto(app["url"] + "/#/check")
    box = pg.locator("#zlauf")
    expect(box.locator("h2")).to_have_text(titel, timeout=T)
    expect(pg.locator("#zlall")).to_have_text(knopf, timeout=T)
    expect(box.locator("[data-zl]").first).not_to_have_text("Auf Laufen umstellen", timeout=T)
    assert "Laufen ist eine eigene Sportart" not in box.inner_text()
    pg.evaluate("() => localStorage.setItem('lang', 'de')")
    assert not pg.errors
    pg.browser_.close()
