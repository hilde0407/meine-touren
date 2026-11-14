"""3.10.0 – Oberfläche „Genauigkeit“ in der Gerätekarte (Browser, Chromium): Aufbau, leerer Zustand, Diagramm, Liste auffälliger Touren,
Korrekturvorschlag mit Bestätigung (Netz gemockt), Auswertung starten, Handybreite, Kontrast. Die Kennzahlen im Datenbestand sind konstruiert."""
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
import sys, os, json, random, time; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db, config, metrics
db.init()
rnd = random.Random(7)
now = int(time.time())
config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
D = {}
for name, model, since, until in (("Amazfit Balance 2", "Balance 2", "2025-01-01", ""), ("Amazfit GTR 4", "GTR 4", "2022-01-01", "2024-12-31"),
                                  ("Amazfit Pace", "Pace", "2016-01-01", "2019-12-31"), ("Garmin Forerunner 255", "Forerunner 255", "", "")):
    kind = "garmin" if name.startswith("Garmin") else "zepp"
    D[name] = db.execute("INSERT INTO devices(name,kind,model,since,until,active,note,zsrc) VALUES(?,?,?,?,?,1,'','')", (name, kind, model, since, until))
def tour(tid, day, name, sport="hike"):
    import datetime
    ts = int(datetime.datetime.strptime(day, "%%Y-%%m-%%d").replace(hour=9).timestamp())
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,10000,7200,500,500,'t','komoot')", (tid, name, sport, ts, ts + 7200))
    db.execute("INSERT OR REPLACE INTO tour_source(tour_id,src,name) VALUES(?,'zepp','')", (tid,))
def row(tid, dev, day, ratio, f, jumps, hrbad, pl=1):
    dem = rnd.uniform(150, 900)
    db.execute("INSERT INTO device_quality(tour_id,device_id,berechnet_am,day,sport,zepp_n,dist_tour_m,dist_dev_m,dist_ratio,dist_plausible,h_src,h_state,up_dev,down_dev,up_dem,down_dem,gps_src,gps_n,gps_jumps,gps_gap_pct,gps_med_dt,gps_pts_km,gps_dec,hr_n,hr_bad_pct) "
               "VALUES(?,?,?,?,'hike',1,10000,?,?,?,'zepp','ok',?,?,?,?,'zepp',400,?,?,NULL,NULL,0,?,?)",
               (tid, dev, now - 3600, day, 10000 * ratio, ratio, pl, dem * (1 + f), dem * (1 + f), dem, dem, jumps, rnd.choice([0.0, 0.5, 2.0, 30.0]) if jumps else 1.0, 300 if hrbad is not None else None, hrbad))
for i in range(40):
    day = "2025-%%02d-%%02d" %% (1 + i %% 11, 1 + i %% 27)
    tid = "k%%d" %% i
    tour(tid, day, "Rundweg Nr. %%d" %% i)
    r = rnd.gauss(0.95, 0.035) if i not in (3, 17) else 3.1
    row(tid, D["Amazfit Balance 2"], day, r, rnd.gauss(0.28, 0.12), rnd.choice([0] * 6 + [1, 2, 4]), rnd.choice([0.0] * 14 + [14.0]), 1 if 0.5 <= r <= 2 else 0)
    if i < 25:
        metrics.store(tid, {"v": 1, "src": "zepp", "device": "x", "t0": 0, "t": [0, 1, 2, 3, 4, 5, 6], "series": {"speed": [1.0] * 7, "cad": [150.0] * 7, **({"temp": [4.0] * 7} if i < 12 else {})}})
    if i < 30:
        (config.TRACK_DIR / ("%%s.hr.json" %% tid)).write_text(json.dumps([[s * 5, 120 + s %% 9] for s in range(120)]))
for i in range(30):
    day = "2023-%%02d-%%02d" %% (1 + i %% 11, 1 + i %% 27)
    tid = "g%%d" %% i
    tour(tid, day, "Gipfelrunde Nr. %%d" %% i)
    row(tid, D["Amazfit GTR 4"], day, rnd.gauss(1.01, 0.012), rnd.gauss(0.04, 0.05), rnd.choice([0] * 40 + [1]), 0.0)
    metrics.store(tid, {"v": 1, "src": "zepp", "device": "x", "t0": 0, "t": [0, 1, 2, 3, 4, 5, 6], "series": {"speed": [1.0] * 7, "cad": [150.0] * 7, "pow": [200.0] * 7}})
for i in range(3):
    day = "2018-05-%%02d" %% (1 + i)
    tid = "p%%d" %% i
    tour(tid, day, "Alte Runde %%d" %% i)
    row(tid, D["Amazfit Pace"], day, 1.02, 0.05, 0, None)
db.execute("INSERT INTO device_quality(tour_id,device_id) SELECT 'nirgends', 1 WHERE 0")
"""


def _seed(data):
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data)}], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr


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
    d = tmp_path_factory.mktemp("gq")
    _seed(d / "data")
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
    pg.errors, pg.posts = [], []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: pg.errors.append("CSP: " + m.text) if "Content Security Policy" in m.text else None)
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(app_url) else r.continue_())
    pg.on("request", lambda r: pg.posts.append((r.method, r.url)) if r.method != "GET" else None)
    pg.goto(app_url + "/#/admin?tab=quellen")
    pg.wait_for_selector("#devsec .dvcard", timeout=10000)
    pg.wait_for_timeout(300)
    pg.browser_ = b
    return pg


def _card(pg, name):
    return pg.locator("#devsec .dvcard", has_text=name)


def test_card_shows_channels_and_collapsed_section_with_verdict(pw, app_url):
    pg = _page(pw, app_url)
    try:
        c = _card(pg, "Balance 2")
        assert "Das liefert diese Uhr:" in c.inner_text()
        chips = [x.strip() for x in c.locator(".dvch").all_inner_texts()]
        assert chips == ["Puls", "Tempo", "Kadenz", "Temperatur"]                           # Temperatur bei 12 von 40 = 30 %; Leistung nirgends
        g4 = [x.strip() for x in _card(pg, "GTR 4").locator(".dvch").all_inner_texts()]
        assert g4 == ["Tempo", "Kadenz", "Leistung"]                                          # Puls: keine Pulsdaten
        assert c.locator("details.dvq").get_attribute("open") is None                          # eingeklappt
        assert "Auffällige Abweichungen" in c.locator("details.dvq > summary").inner_text() or "Einschränkungen" in c.locator("details.dvq > summary").inner_text()
        assert "noch nicht ausgewertet" in _card(pg, "Forerunner").locator("details.dvq > summary").inner_text()
        assert not pg.errors, pg.errors
        assert not pg.posts
    finally:
        pg.browser_.close()


def test_open_section_kpis_chart_list_and_suggestion_dialog(pw, app_url):
    pg = _page(pw, app_url)
    try:
        c = _card(pg, "Balance 2")
        c.locator("details.dvq > summary").click()
        pg.wait_for_selector("details.dvq[open] .dvbadul", timeout=8000)
        assert not pg.locator(".dvbox").count()                # Klick im Abschnitt öffnet nicht das Bearbeiten
        tiles = c.locator(".dvk")
        assert tiles.count() == 4 and [x.strip() for x in c.locator(".dvkl").all_inner_texts()] == ["Strecke", "Höhe", "GPS-Spur", "Puls"]
        txt = c.inner_text()
        assert "kürzer als die Komoot-Strecke" in txt and "1 unplausibel" not in txt and "2 unplausibel" in txt
        assert c.locator("svg.dvdots").count() == 2 and c.locator("svg.dvdots").first.get_attribute("role") == "img"
        assert c.locator("svg.dvdots").first.locator("circle").count() == 38                    # 40 Touren minus 2 unplausible
        assert "Wie wird bewertet?" in txt and "Zuletzt ausgewertet am" in txt
        n = c.locator(".dvbadul li").count()
        assert n >= 3
        first = c.locator(".dvbadul li").first
        assert first.locator("a").get_attribute("href").startswith("#/tour/")
        # Korrektur vorschlagen: Dialog, nichts passiert ohne Bestätigung
        li = c.locator(".dvbadul li", has=pg.locator("text=Aufstieg")).first
        li.locator("button").click()
        pg.wait_for_selector(".dvsug")
        assert "Höhe aus Geländemodell neu berechnen" in pg.inner_text(".dvsug") and "Es passiert nichts, bevor du es bestätigst" in pg.inner_text(".dvbox")
        # Bestätigung ist jetzt der gemeinsame Dialog (kein Browser-confirm): Abbrechen ändert nichts
        pg.locator(".dvsug button", has_text="Ausführen").first.click()
        pg.wait_for_selector(".uidlg [role=dialog], .uidlg [role=alertdialog]")
        dlg = pg.locator(".uidlg .uibox")
        assert dlg.get_attribute("aria-modal") == "true" and "Höhe aus Geländemodell neu berechnen?" in dlg.inner_text()
        pg.locator(".uidlg .uifoot button", has_text="Abbrechen").click()
        pg.wait_for_timeout(300)
        assert not pg.locator(".uidlg").count() and not pg.posts                               # abgebrochen: kein Aufruf
        # bestätigen (Antwort nachgebaut) und rückgängig machen
        calls = []

        def fake(route):
            calls.append(route.request.url.rsplit("/", 1)[-1])
            route.fulfill(status=200, content_type="application/json", body='{"up_m":420,"down_m":415,"orig_up":610,"orig_down":600,"ok":true}')
        pg.route("**/api/tours/*/elev-fix", fake)
        pg.route("**/api/tours/*/elev-restore", fake)
        pg.locator(".dvsug button", has_text="Ausführen").first.click()
        pg.wait_for_selector(".uidlg")
        pg.locator(".uidlg .uifoot button", has_text="Ausführen").click()                      # bestätigen
        pg.wait_for_selector("#dvsundo", timeout=5000)
        assert calls == ["elev-fix"] and "Aufstieg 420 m" in pg.inner_text(".dvsres") and "vorher 610 m" in pg.inner_text(".dvsres")
        pg.click("#dvsundo")
        pg.wait_for_selector(".dvsres:has-text('Zurückgenommen')", timeout=5000)
        assert calls == ["elev-fix", "elev-restore"]
        assert not [e for e in pg.errors if "CSP" in e or "TypeError" in e], pg.errors
    finally:
        pg.browser_.close()


def test_empty_and_too_few_tours_states(pw, app_url):
    pg = _page(pw, app_url)
    try:
        e = _card(pg, "Forerunner")
        e.locator("details.dvq > summary").click()
        t = e.inner_text()
        assert "Noch nicht ausgewertet." in t and "verändert keine Tour" in t and e.locator(".dvqrun").count() == 1
        p = _card(pg, "Amazfit Pace")
        p.locator("details.dvq > summary").click()
        pg.wait_for_selector("details.dvq[open] .dvk")
        assert "Noch keine Einschätzung" in p.inner_text() and "mindestens 5 verglichene Touren" in p.inner_text()
        assert p.locator(".dvks.none").count() >= 1
    finally:
        pg.browser_.close()


def _contrast_js():
    return """() => {
      const parse = s => { const m = s.match(/[\\d.]+/g).map(Number); if (s.startsWith('color(')) return m.slice(m[0] === 0 && s.includes('srgb') ? 0 : 0, 3).map(v => v * 255); return m.slice(0, 3); };
      const lin = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
      const L = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
      const bg = el => { for (let e = el; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor; const a = c.match(/[\\d.]+/g); if (c !== 'rgba(0, 0, 0, 0)' && !(a.length === 4 && +a[3] === 0)) return parse(c); } return [255, 255, 255]; };
      const out = [];
      for (const sel of ['.dvqs.ok', '.dvqs.warn', '.dvqs.bad', '.dvqs.none', '.dvks.ok', '.dvks.warn', '.dvks.bad', '.dvks.none', '.dvqv b', '.dvc.fl.warn', '.dvc.fl.bad', '.dvkl', '.dvkn', '.dvgive', '.dvch', '.dvbt .mut', '.dvqwhen', '.dvh', '.dvtip', '.dvfig figcaption']) {
        document.querySelectorAll(sel).forEach((el, i) => { if (i > 1) return; const f = parse(getComputedStyle(el).color), b = bg(el); const l1 = L(f), l2 = L(b); out.push([sel, (Math.max(l1, l2) + .05) / (Math.min(l1, l2) + .05)]); });
      }
      return out;
    }"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_contrast_at_least_4_5(pw, app_url, scheme):
    pg = _page(pw, app_url, scheme=scheme)
    try:
        for n in ("Balance 2", "Pace"):
            _card(pg, n).locator("details.dvq > summary").click()
        pg.wait_for_selector(".dvbadul")
        res = pg.evaluate(_contrast_js())
        assert len(res) > 15
        bad = [(s, round(c, 2)) for s, c in res if c < 4.5]
        assert not bad, bad
    finally:
        pg.browser_.close()


def test_mobile_390_no_overflow_and_touch_targets(pw, app_url):
    pg = _page(pw, app_url, width=390, height=844, dpr=2)
    try:
        c = _card(pg, "Balance 2")
        c.locator("details.dvq > summary").click()
        pg.wait_for_selector(".dvbadul")
        assert pg.evaluate("document.documentElement.scrollWidth") <= 391
        over = pg.evaluate("[...document.querySelectorAll('#devsec .dvq *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('svg')).map(e => e.className || e.tagName).slice(0, 5)")
        assert not over, over
        h = c.locator("details.dvq > summary").bounding_box()["height"]
        assert h >= 44
        assert min(b.bounding_box()["height"] for b in c.locator(".dvbadul .btn").all()[:3]) >= 36
    finally:
        pg.browser_.close()


# Muss zuletzt laufen: ersetzt die konstruierten Zeilen durch echt berechnete (ohne Zepp-Zugang und GPX bleibt nur der Puls).
def test_run_job_and_progress(pw, app_url):
    pg = _page(pw, app_url)
    try:
        pg.locator("#dvqall").click()
        pg.wait_for_timeout(500)
        for _ in range(120):                                   # Panel wird nach dem Ende neu gezeichnet: Knopf wieder frei
            if pg.locator("#dvqall").count() and pg.locator("#dvqall").is_enabled() and pg.locator("#devsec .dvqprog:not(:empty)").count() == 0:
                break
            pg.wait_for_timeout(500)
        import json
        log = json.loads(urllib.request.urlopen(app_url + "/api/jobs").read())
        assert any("Genauigkeit fertig" in x for x in log["log"]) and log["ok"] is True
        assert ("POST", app_url + "/api/jobs/dev-quality") in pg.posts
        assert not pg.errors, pg.errors
        q = {d["name"]: d for d in json.loads(urllib.request.urlopen(app_url + "/api/devices/quality").read())["devices"]}
        assert q["Amazfit Balance 2"]["n_eval"] == 40 and q["Amazfit Balance 2"]["dist"]["n"] == 0     # Zeilen ersetzt: ohne Zepp-Zugang und ohne eigene GPX bleibt nur der Puls
        assert q["Amazfit Balance 2"]["hr"]["n"] == 30
    finally:
        pg.browser_.close()
