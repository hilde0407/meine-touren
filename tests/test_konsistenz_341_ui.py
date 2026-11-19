"""3.41.0 – Browser (Chromium): A7 Tourname bleibt in allen Sprachen unübersetzt, H1 Auswahlleiste der Fotos lesbar und weg nach Seitenwechsel, C3 Benutzermenü schließt mit Esc und beim Seitenwechsel."""
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from tests.helpers_ui import T, free_port, quiet, wait_http

expect = pytest.importorskip("playwright.sync_api").expect
ROOT = Path(__file__).resolve().parent.parent

SEED = r"""
import sys, os, time; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db
db.init()
now = int(time.time())
for i, n in enumerate(["Solo ohne Uhr", "Gipfelrunde Aufstieg", "Zeit und Strecke"]):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,?,?,'t','komoot')", ("t%%d" %% i, n, "hike", now - (i + 2) * 86400, now - (i + 2) * 86400 + 6000, 5000, 6000, 200, 200))
"""
NAMEN = ["Solo ohne Uhr", "Gipfelrunde Aufstieg", "Zeit und Strecke"]


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("k341")
    data = tmp / "data"
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data)}], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr
    port = free_port()
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    pr = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    wait_http(url + "/api/version")
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


def _page(pw, url, lang, w=1280, hash_="#/tours"):
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": w, "height": 900}, reduced_motion="reduce")
    ctx.add_init_script("try { localStorage.setItem('lang', %r); } catch (e) {}" % lang)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(url) else r.continue_())
    pg.browser_ = b
    pg.goto(url + "/" + hash_)
    return pg


@pytest.mark.parametrize("lang", ["de", "en", "fr", "es"])
def test_a7_tourname_bleibt_unuebersetzt(pw, app, lang):
    pg = _page(pw, app, lang)
    try:
        pg.wait_for_function("(n) => n.every(x => document.body.innerText.includes(x))", arg=NAMEN, timeout=T)
        quiet(pg, 3000)
        text = pg.evaluate("() => document.querySelector('#main').innerText")
        for n in NAMEN:
            assert n in text, (lang, n)
        # Tourseite: Überschrift ebenfalls unverändert
        pg.goto(app + "/#/tour/t0")
        pg.wait_for_function("() => document.querySelector('#main h1, #main h2')?.innerText.includes('Solo ohne Uhr')", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


FOTOS = """() => {
  document.querySelector('#main').innerHTML = '<div id="pg"><div class="sec"><span class="sp">x</span></div><img data-i="0" src="data:image/gif;base64,R0lGODlhAQABAAAAACw="></div>';
  photoSelect([{id: 1, taken_ts: 1700000000}], 2023);
  return !!document.querySelector('#pg .sec .sp + button');
}"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_h1_auswahlleiste_lesbar_und_weg_nach_seitenwechsel(pw, app, scheme):
    pg = _page(pw, app, "de")
    pg.emulate_media(color_scheme=scheme)
    try:
        pg.wait_for_function("() => typeof photoSelect === 'function' && !!document.querySelector('#main')", timeout=T)
        quiet(pg, 2000)
        assert pg.evaluate(FOTOS)
        pg.click("#pg .sec .sp + button")
        pg.click("#pg img[data-i]")
        expect(pg.locator(".seltb")).to_be_visible(timeout=T)
        farben = pg.evaluate("""() => [...document.querySelectorAll('.seltb .btn')].map(b => { const c = getComputedStyle(b), t = getComputedStyle(document.querySelector('.seltb')); return [c.color, c.backgroundColor === 'rgba(0, 0, 0, 0)' ? t.backgroundColor : c.backgroundColor, b.textContent.trim()]; })""")
        assert len(farben) >= 3
        for farbe, grund, text in farben:
            assert farbe != grund, (scheme, text, farbe, grund)
        pg.evaluate("() => { location.hash = '#/stats'; }")
        pg.wait_for_function("() => !document.querySelector('.seltb')", timeout=T)
        assert pg.evaluate("() => !document.body.classList.contains('selmode')")
    finally:
        pg.browser_.close()


def test_c3_benutzermenue_schliesst_mit_esc_und_seitenwechsel(pw, app):
    pg = _page(pw, app, "de")
    try:
        pg.wait_for_function("() => !!document.querySelector('#umenu')", timeout=T)
        quiet(pg, 2000)
        pg.click("#umenu")
        expect(pg.locator(".umpop")).to_be_visible(timeout=T)
        pg.keyboard.press("Escape")
        expect(pg.locator(".umpop")).to_have_count(0, timeout=T)
        pg.click("#umenu")
        expect(pg.locator(".umpop")).to_be_visible(timeout=T)
        pg.evaluate("() => { location.hash = '#/stats'; }")
        expect(pg.locator(".umpop")).to_have_count(0, timeout=T)
        # erneutes Öffnen funktioniert
        pg.click("#umenu")
        expect(pg.locator(".umpop")).to_be_visible(timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_e1_streckenfarbe_panel_im_sichtfeld(pw, app):
    pg = _page(pw, app, "de", hash_="#/tour/t0")
    try:
        pg.wait_for_function("() => document.querySelector('#main h1, #main h2')?.innerText.includes('Solo ohne Uhr')", timeout=T)
        quiet(pg, 3000)
        sicht = pg.evaluate("() => [...document.querySelectorAll('.tpanel')].every(p => { const r = p.getBoundingClientRect(); return r.width === 0 || (r.left >= -1 && r.right <= innerWidth + 1); })")
        assert sicht
    finally:
        pg.browser_.close()
