"""3.16.1 – „Als geprüft markieren“ in der Genauigkeitsliste und im Dialog „GPS-Track korrigieren“ (Browser, Chromium).
Nach jedem Klick wird auf den Zustand gewartet (nie sofort geprüft): langsame CI-Läufe hatten sonst Wettlauf-Fehler."""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHOTS = os.environ.get("MT_SHOTS", "")

SEED = r"""
import sys, os, time, datetime; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db
db.init()
now = int(time.time())
dev = db.execute("INSERT INTO devices(name,kind,model,since,until,active,note,zsrc) VALUES('Amazfit Balance 2','zepp','Balance 2','2025-01-01','',1,'','')")
def tour(tid, day, name, gaps, jumps=0, ratio=1.0):
    ts = int(datetime.datetime.strptime(day, "%%Y-%%m-%%d").replace(hour=9).timestamp())
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,'hike',?,?,10000,7200,500,500,'t','komoot')", (tid, name, ts, ts + 7200))
    db.execute("INSERT OR REPLACE INTO tour_source(tour_id,src,name) VALUES(?,'zepp','')", (tid,))
    db.execute("INSERT INTO device_quality(tour_id,device_id,berechnet_am,day,sport,zepp_n,dist_tour_m,dist_dev_m,dist_ratio,dist_plausible,h_src,h_state,up_dev,down_dev,up_dem,down_dem,gps_src,gps_n,gps_jumps,gps_gap_pct,hr_n,hr_bad_pct) "
               "VALUES(?,?,?,?,'hike',1,10000,?,?,1,'zepp','ok',500,500,500,500,'zepp',400,?,?,300,0)", (tid, dev, now - 3600, day, 10000 * ratio, ratio, jumps, gaps))
tour("g1", "2025-06-01", "Betriebsausflug Rast", 28.0)
tour("g2", "2025-06-02", "Rundweg mit Sprung", 30.0, jumps=3)
tour("g3", "2025-06-03", "Strecke zu kurz", 1.0, ratio=0.85)
for i in range(6):
    tour("ok%%d" %% i, "2025-05-%%02d" %% (1 + i), "Unauffällig %%d" %% i, 1.0)
"""

FAKE_TF = ('{"line":[[47.0,11.0],[47.01,11.01]],"fast":[],"spikes":[],"n_spikes":0,"spike_m":0,"jitter_m":0,"raw_m":5000,"dist_km":5,"dur_s":7200,"now_km":5,'
           '"limit_sustain":12,"fixed":false,"applied":null,"photos":null,"anchors":null,"has_time":true,"timing":{"uniform":false,"est_s":null}}')


def _wait(url):
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/api/version", timeout=1)
            return
        except Exception:
            time.sleep(0.2)


@pytest.fixture(scope="module")
def app_url(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    d = tmp_path_factory.mktemp("ack")
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(d / "data")}], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(d / "data")))
    assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    env = dict(os.environ, DATA_DIR=str(d / "data"), PHOTOS_DIR=str(d / "p"), BACKUP_DIR=str(d / "b"), MT_NO_SCHEDULER="1")
    pr = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
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


def _page(pw, app_url, width=1280, height=1000, scheme="light", dpr=1):
    b = pw.chromium.launch()
    ctx = b.new_context(locale="de-DE", viewport={"width": width, "height": height}, color_scheme=scheme, device_scale_factor=dpr)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(app_url) else r.continue_())
    pg.goto(app_url + "/#/admin?tab=quellen")
    pg.wait_for_selector("#devsec .dvcard", timeout=15000)
    pg.browser_ = b
    return pg


def _open(pg):
    from playwright.sync_api import expect
    if not pg.evaluate("() => document.querySelector('#devsec .dvcard details.dvq').open"):       # nach dem Neuladen steht der Zustand im Browser
        pg.locator("#devsec .dvcard details.dvq > summary").click()
    expect(pg.locator(".dvbadl > .dvbadul li").first).to_be_visible(timeout=15000)


def _api(app_url, path, method="GET"):
    import json
    req = urllib.request.Request(app_url + path, method=method)
    try:
        return json.loads(urllib.request.urlopen(req).read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"status": e.code}


def _shot(pg, name):
    if SHOTS:
        Path(SHOTS).mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(Path(SHOTS) / name), full_page=False)


def test_list_buttons_depend_on_kind_ack_and_undo(pw, app_url):
    from playwright.sync_api import expect
    pg = _page(pw, app_url)
    try:
        _open(pg)
        lis = pg.locator(".dvbadl > .dvbadul li")
        expect(lis).to_have_count(3, timeout=15000)
        gap = lis.filter(has_text="Betriebsausflug Rast")
        assert "Pausen und Aufzeichnungslücken sind bei Touren normal und lassen sich nicht reparieren" in gap.inner_text()
        assert gap.get_by_role("button", name="Korrektur vorschlagen").count() == 0                 # nichts zu reparieren
        other = lis.filter(has_text="Rundweg mit Sprung")
        assert other.get_by_role("button", name="Korrektur vorschlagen").count() == 1 and other.get_by_role("button", name="Als geprüft markieren").count() == 1
        assert pg.locator(".dvack").count() == 0
        pg.wait_for_function("() => document.querySelector('#devsec .dvbadul li button') !== null", timeout=15000)
        gap.scroll_into_view_if_needed()
        _shot(pg, "liste_nur_luecken_hell.png")
        gap.get_by_role("button", name="Als geprüft markieren").click()
        expect(pg.locator(".dvbadl > .dvbadul li")).to_have_count(2, timeout=15000)
        expect(pg.locator(".dvack > summary")).to_have_text("Als geprüft markiert (1)", timeout=15000)
        expect(pg.locator("details.dvsec[data-sec=auff] > summary .dvqs")).to_have_text("2", timeout=15000)       # Zähler stimmt mit der Liste überein
        pg.locator(".dvack > summary").click()
        expect(pg.locator(".dvack li", has_text="Betriebsausflug Rast")).to_be_visible(timeout=15000)
        pg.locator(".dvack li button", has_text="Zurücknehmen").click()
        expect(pg.locator(".dvbadl > .dvbadul li")).to_have_count(3, timeout=15000)
        expect(pg.locator(".dvack")).to_have_count(0, timeout=15000)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_failed_ack_shows_dialog(pw, app_url):
    from playwright.sync_api import expect
    pg = _page(pw, app_url)
    try:
        _open(pg)
        pg.route("**/api/tours/*/quality-ack", lambda r: r.fulfill(status=409, content_type="application/json", body='{"detail":"Diese Tour hat keine offenen Auffälligkeiten"}'))
        pg.locator(".dvbadul li", has_text="Rundweg mit Sprung").get_by_role("button", name="Als geprüft markieren").click()
        expect(pg.locator(".uidlg .uibox")).to_contain_text("keine offenen Auffälligkeiten", timeout=15000)
        pg.locator(".uidlg .uifoot button").first.click()
        expect(pg.locator(".uidlg")).to_have_count(0, timeout=15000)
    finally:
        pg.browser_.close()


def test_trackfix_dialog_offers_ack_when_nothing_found(pw, app_url):
    from playwright.sync_api import expect
    pg = _page(pw, app_url)
    try:
        pg.route("**/api/tours/g1/trackfix", lambda r: r.fulfill(status=200, content_type="application/json", body=FAKE_TF))
        pg.route("**/api/tours/ok0/trackfix", lambda r: r.fulfill(status=200, content_type="application/json", body=FAKE_TF))
        # unauffällige Tour: kein Angebot
        pg.evaluate("() => { trackFixDialog('ok0', () => {}); }")
        expect(pg.locator(".mbox")).to_contain_text("nichts Auffälliges gefunden", timeout=15000)
        pg.wait_for_timeout(600)                                                                    # Angebot dürfte erst nach der Flag-Abfrage erscheinen
        assert pg.locator("#tfack1").count() == 0
        pg.locator("#tfno").click()
        expect(pg.locator(".mbox")).to_have_count(0, timeout=15000)
        # Tour mit offener Lücken-Auffälligkeit
        pg.evaluate("() => { window.__done = 0; trackFixDialog('g1', () => { window.__done++; }); }")
        expect(pg.locator("#tfack")).to_contain_text("Diese Tour steht noch in der Liste „Auffällige Touren“. Als geprüft markieren?", timeout=15000)
        _shot(pg, "trackfix_hell.png")
        pg.locator("#tfack1").click()
        expect(pg.locator(".mbox")).to_have_count(0, timeout=15000)
        pg.wait_for_function("() => window.__done === 1", timeout=15000)
        assert _api(app_url, "/api/tours/g1/quality-flags") == {"flags": [], "acked": True}
        _api(app_url, "/api/tours/g1/quality-ack", "DELETE")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_contrast_and_mobile_layout(pw, app_url, scheme):
    from playwright.sync_api import expect
    pg = _page(pw, app_url, width=390, height=900, scheme=scheme, dpr=2)
    try:
        _open(pg)
        _api(app_url, "/api/tours/g1/quality-ack", "POST")
        pg.reload()
        pg.wait_for_selector("#devsec .dvcard", timeout=15000)
        _open(pg)
        expect(pg.locator(".dvack > summary")).to_be_visible(timeout=15000)
        pg.locator(".dvack > summary").click()
        expect(pg.locator(".dvack li button")).to_be_visible(timeout=15000)
        assert pg.evaluate("document.documentElement.scrollWidth") <= 391
        res = pg.evaluate("""() => {
          const parse = s => { const m = s.match(/[\\d.]+/g).map(Number); return s.startsWith('color(') ? m.slice(0, 3).map(v => v * 255) : m.slice(0, 3); };
          const lin = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
          const L = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
          const bg = el => { for (let e = el; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor; const a = c.match(/[\\d.]+/g); if (c !== 'rgba(0, 0, 0, 0)' && !(a.length === 4 && +a[3] === 0)) return parse(c); } return [255, 255, 255]; };
          return ['.dvack > summary', '.dvack .dvbt .mut', '.dvnote', '.dvack .btn', '.dvbadul .btn.alt', '.dvbadul .btn.ghost'].map(sel => { const el = document.querySelector(sel); if (!el) return [sel, 99]; const l1 = L(parse(getComputedStyle(el).color)), l2 = L(bg(el)); return [sel, (Math.max(l1, l2) + .05) / (Math.min(l1, l2) + .05)]; });
        }""")
        bad = [(s, round(c, 2)) for s, c in res if c < 4.5]
        assert not bad, bad
        _shot(pg, f"liste_{scheme}_390.png")
        assert not pg.errors, pg.errors
    finally:
        _api(app_url, "/api/tours/g1/quality-ack", "DELETE")
        pg.browser_.close()
