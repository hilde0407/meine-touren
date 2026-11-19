"""3.38.1 Baustein „Geplante Touren“ (Oberfläche, Chromium): nur offene Pläne, Einstellung „Gegangene Pläne auch zeigen“, Soll/Ist, Leer-Zustand, Englisch, 390 px.
Synchronisation nur über wait_for_function (Pfeilfunktionen) und expect(..., timeout=15000); keine festen Pausen. Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from tests.helpers_ui import quiet  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
pw_api = pytest.importorskip("playwright.sync_api")
expect = pw_api.expect
TL = 15000
TZN = "Europe/Berlin"
LAUF_TS = 1760000000                                         # Tag der gelaufenen Tour (feste Zahl, damit das erwartete Datum nicht von „heute“ abhängt)

SEED = """
import sys, os; sys.path.insert(0, {root!r}); os.environ['DATA_DIR'] = {data!r}
import time
from app import db
db.init()
db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES('lauf','Seerunde gelaufen','hike',?,?,11000,6120,320,320,48.0,8.0,'tour_recorded','komoot')", ({lauf}, {lauf} + 6200))
def plan(name, ts, status, tour, est):
    db.execute("INSERT INTO plans(name,sport,pts,km,up,down,max_alt,est_h,note,ts,status,tour_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (name, 'hike', '[]', 12.5, 300, 300, 700, est, '', ts, status, tour))
plan('Gipfelweg', 400, 'geplant', None, 4.5)
plan('Rund um den See', 300, 'geplant', None, 3.0)
plan('Seerunde', 200, 'gegangen', 'lauf', 2.0)
plan('Alter Verworfener', 100, 'verworfen', None, 1.0)
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    d = tmp_path_factory.mktemp("gp3381")
    data = d / "data"
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(d / "p"), BACKUP_DIR=str(d / "b"), MT_NO_SCHEDULER="1")
    out = subprocess.run([sys.executable, "-c", SEED.format(root=str(ROOT), data=str(data), lauf=LAUF_TS)], capture_output=True, text=True, cwd=ROOT, env=env)
    assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    pr = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
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


def _layout(url, cfg=None, method="PUT"):
    body = None if method == "DELETE" else {"widgets": [{"id": "wg1", "type": "geplant", "cfg": cfg or {}}]}
    r = urllib.request.Request(f"{url}/api/layout/uebersicht", method=method, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=20) as x:
        return json.loads(x.read() or b"{}")


def _browser(pw, url, width=1280, height=1000, lang="de", scheme="light"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale="en-GB" if lang == "en" else "de-DE", timezone_id=TZN, viewport={"width": width, "height": height}, color_scheme=scheme, reduced_motion="reduce")
    ctx.add_init_script("try { localStorage.setItem('lang', %r); } catch (e) {}" % lang)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(url) else r.continue_())
    pg.browser_ = b
    return pg


def _dash(pw, url, **kw):
    pg = _browser(pw, url, **kw)
    pg.goto(f"{url}/#/dash")
    pg.wait_for_selector('[data-wtype="geplant"] .tlsb', timeout=TL)
    pg.wait_for_function("() => { const b = document.querySelector('[data-wtype=\"geplant\"] .tlsb'); return !!b && !/Wird geladen|Loading/.test(b.textContent) && !!b.querySelector('.sllist, .slnone'); }", timeout=TL)
    return pg


def _shot(pg, name):
    d = os.environ.get("TS_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        try:
            quiet(pg, 5000)
        except Exception:
            pass
        pg.locator('[data-wtype="geplant"]').scroll_into_view_if_needed()
        pg.screenshot(path=str(Path(d) / name), full_page=False, timeout=60000)


def _gone_date(lang="de"):
    d = datetime.fromtimestamp(LAUF_TS, ZoneInfo(TZN))
    return d.strftime("%d/%m/%Y") if lang == "en" else d.strftime("%d.%m.%Y")


def _names(pg):
    return pg.locator('[data-wtype="geplant"] .sllist li').evaluate_all("els => els.map(e => e.firstElementChild.textContent.trim())")


def test_standard_zeigt_nur_offene(pw, app):
    _layout(app, {})
    pg = _dash(pw, app)
    try:
        assert _names(pg) == ["Gipfelweg", "Rund um den See"]
        txt = pg.locator('[data-wtype="geplant"]').inner_text()
        assert "Seerunde" not in txt and "Alter Verworfener" not in txt and "gegangen" not in txt
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_altes_layout_ohne_feld_wie_standard(pw, app):
    _layout(app, {"title": "Meine Pläne"})
    pg = _dash(pw, app)
    try:
        assert _names(pg) == ["Gipfelweg", "Rund um den See"]
    finally:
        pg.browser_.close()


def test_gegangene_mit_datum_und_differenz_verworfene_nie(pw, app):
    _layout(app, {"gegangen": True})
    pg = _dash(pw, app)
    try:
        assert _names(pg) == ["Gipfelweg", "Rund um den See", "Seerunde"]                    # offene zuerst
        li = pg.locator('[data-wtype="geplant"] .sllist li.slgone')
        expect(li).to_have_count(1, timeout=TL)
        t = li.inner_text()
        assert f"gegangen am {_gone_date()}" in t, t
        assert "geplant 2:00 Std." in t and "gelaufen 1:42 Std." in t and "(−18 Min.)" in t, t
        assert "Alter Verworfener" not in pg.locator('[data-wtype="geplant"]').inner_text()
        assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_einstellung_im_dialog_speichern_und_wieder_ausschalten(pw, app):
    _layout(app, {})
    pg = _dash(pw, app)
    try:
        pg.locator("#slopen").click()
        pg.wait_for_selector('.slit[data-sl="wg1"]', timeout=TL)
        gear = '.slit[data-sl="wg1"] [data-a="cfg"]'
        if not pg.locator(gear).is_visible():
            pg.locator('.slit[data-sl="wg1"] [data-a="more"]').click()
            pg.wait_for_function("(s) => { const e = document.querySelector(s); return !!e && e.offsetParent !== null; }", arg=gear, timeout=TL)
        pg.locator(gear).click()
        pg.wait_for_selector('.sldlg [role="dialog"] form', timeout=TL)
        box = pg.locator('.sldlg input[type=checkbox]')
        expect(box).to_have_count(1, timeout=TL)
        assert pg.locator(".sldlg label.slck").inner_text() == "Gegangene Pläne auch zeigen" and not box.is_checked()      # Standard: aus
        box.check()
        pg.get_by_role("button", name="Speichern", exact=True).click()
        pg.wait_for_function("() => !document.querySelector('.sldlg')", timeout=TL)
        pg.wait_for_function("() => document.querySelectorAll('[data-wtype=\"geplant\"] .sllist li').length === 3", timeout=TL)
        pg.wait_for_function("() => { const s = document.getElementById('slsaved'); return !!s && s.textContent.trim() === 'Gespeichert'; }", timeout=TL)
        with urllib.request.urlopen(f"{app}/api/layout/uebersicht", timeout=10) as r:
            assert json.loads(r.read())["layout"]["widgets"][0]["cfg"] == {"gegangen": True}
        # wieder ausschalten: Standard wird nicht gespeichert
        if not pg.locator(gear).is_visible():
            pg.locator('.slit[data-sl="wg1"] [data-a="more"]').click()
            pg.wait_for_function("(s) => { const e = document.querySelector(s); return !!e && e.offsetParent !== null; }", arg=gear, timeout=TL)
        pg.locator(gear).click()
        pg.wait_for_selector('.sldlg [role="dialog"] form', timeout=TL)
        box = pg.locator('.sldlg input[type=checkbox]')
        assert box.is_checked()
        box.uncheck()
        pg.get_by_role("button", name="Speichern", exact=True).click()
        pg.wait_for_function("() => !document.querySelector('.sldlg')", timeout=TL)
        pg.wait_for_function("() => document.querySelectorAll('[data-wtype=\"geplant\"] .sllist li').length === 2", timeout=TL)
        pg.wait_for_function("() => { const s = document.getElementById('slsaved'); return !!s && s.textContent.trim() === 'Gespeichert'; }", timeout=TL)
        with urllib.request.urlopen(f"{app}/api/layout/uebersicht", timeout=10) as r:
            assert json.loads(r.read())["layout"]["widgets"][0]["cfg"] == {}
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_leer_zustand_freundlich(pw, app):
    _layout(app, {})
    pg = _browser(pw, app)
    try:
        pg.route("**/api/bausteine/geplant*", lambda r: r.fulfill(json=[]))
        pg.goto(f"{app}/#/dash")
        loc = pg.locator('[data-wtype="geplant"] .slnone')
        expect(loc).to_have_text("Keine offenen Pläne.", timeout=TL)
        assert pg.locator('[data-wtype="geplant"] a[href="#/plan"]').count() == 1
    finally:
        pg.browser_.close()


def test_englisch(pw, app):
    _layout(app, {"gegangen": True})
    pg = _dash(pw, app, lang="en")
    try:
        li = pg.locator('[data-wtype="geplant"] .sllist li.slgone')
        expect(li).to_have_count(1, timeout=TL)
        t = li.inner_text()
        assert f"walked on {_gone_date('en')}" in t and "planned 2:00 h" in t and "walked 1:42 h" in t, t
        assert "gegangen" not in t and "gelaufen" not in t and "geplant" not in t
        pg.route("**/api/bausteine/geplant*", lambda r: r.fulfill(json=[]))
        pg.reload()
        expect(pg.locator('[data-wtype="geplant"] .slnone')).to_have_text("No open plans.", timeout=TL)
    finally:
        pg.browser_.close()


def test_handy_390_ohne_seitliches_scrollen_und_screenshot(pw, app):
    _layout(app, {"gegangen": True})
    pg = _dash(pw, app, width=390, height=900)
    try:
        expect(pg.locator('[data-wtype="geplant"] .sllist li')).to_have_count(3, timeout=TL)
        try:
            quiet(pg, 5000)
        except Exception:
            pass
        assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert pg.evaluate("() => { const w = document.querySelector('[data-wtype=\"geplant\"]'); const r = w.getBoundingClientRect(); return r.left >= 0 && r.right <= window.innerWidth + 1; }")
        _shot(pg, "uebersicht-geplante-touren-390.png")
        _layout(app, method="DELETE")
    finally:
        pg.browser_.close()
