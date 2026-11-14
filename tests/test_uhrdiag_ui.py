"""3.10.1 – Oberfläche „Was liefert diese Uhr?“ (Browser, Chromium): Gerätekarte, Dialog, Filter, Datei speichern, leerer Zustand, Fehlerfall ohne Zepp-Zugang,
Tourseite mit „Alle Felder dieser Tour“, Handybreite, Kontrast. Der Zepp-Zugang ist nachgebaut (konstruierte Zusammenfassung/Details, erfundene Feldnamen);
echte Zepp-Antworten gibt es hier nicht. Mit UHR_SHOTS=<Ordner> werden Screenshots abgelegt."""
import json
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

SEED = r"""
import sys, os; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db, config, metrics, tracks
from tests.test_uhrdiag import make_fit, _gpx
db.init()
db.execute("INSERT INTO devices(name,kind,model,since,until,active,note,zsrc) VALUES('Amazfit Balance 2','zepp','Balance 2','2025-01-01','',1,'','run.46.huami.com')")
db.execute("INSERT INTO devices(name,kind,model,since,until,active,note,zsrc) VALUES('Amazfit Pace','zepp','Pace','2016-01-01','2019-12-31',1,'','')")
db.execute("INSERT INTO devices(name,kind,model,since,until,active,note,zsrc) VALUES('Garmin Forerunner 255','garmin','Forerunner 255','','',1,'','')")
def tour(tid, ts, kind, name):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,'hike',?,?,10000,3000,100,100,'t','komoot')", (tid, name, ts, ts + 3000))
    db.execute("INSERT OR REPLACE INTO tour_source(tour_id,src,name) VALUES(?,?,'')", (tid, kind))
config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
config.INBOX_DIR.mkdir(parents=True, exist_ok=True)
for i in range(12):
    st = %(t0)d + i * 86400 + 10
    tid = "z%%d" %% st
    tour(tid, st, "zepp", "Rundweg Nr. %%d" %% i)
    metrics.store(tid, {"v": 1, "src": "zepp", "device": "Amazfit/Zepp", "t0": st, "t": [0, 1, 2, 3, 4, 5, 6], "series": {"speed": [3.0] * 7, "cad": [150.0] * 7}, "sum": {"kcal": 512}})
    if i %% 2 == 0:
        _gpx(tid)
(config.INBOX_DIR / "uhr.fit").write_bytes(make_fit(t0=%(t0)d + 11 * 86400 + 10))
tour("g1", %(t0)d + 100 * 86400, "garmin", "Garmin-Runde")
"""

LAUNCH = r"""
import sys, os; sys.path.insert(0, %(root)r)
from app import sync
from tests.test_uhrdiag import Api, _summary
if %(nozepp)r:
    def nope():
        raise RuntimeError("Zepp-Zugangsdaten fehlen (Einstellungen)")
    sync._zepp_api = nope
else:
    hist = [_summary(%(t0)d + i * 86400 + 10) for i in range(12)]
    sync._zepp_api = lambda: Api(hist)
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
    d = tmp_path_factory.mktemp("uhr")
    data = d / "data"
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data), "t0": T0}], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr
    p1, u1 = _serve(data, d, False)
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


def _page(pw, url, width=1280, height=1000, scheme="light", dpr=1, path="#/admin?tab=quellen", wait="#devsec .dvcard", locale="de-DE"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale=locale, viewport={"width": width, "height": height}, color_scheme=scheme, device_scale_factor=dpr, accept_downloads=True)
    pg = ctx.new_page()
    pg.errors, pg.posts = [], []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: pg.errors.append("CSP: " + m.text) if "Content Security Policy" in m.text else None)
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(url) else r.continue_())
    pg.on("request", lambda r: pg.posts.append((r.method, r.url)) if r.method != "GET" else None)
    pg.goto(url + "/" + path)
    pg.wait_for_selector(wait, timeout=10000)
    pg.wait_for_timeout(300)
    pg.browser_ = b
    return pg


def _card(pg, name):
    return pg.locator("#devsec .dvcard", has_text=name)


def _open(pg, name):
    b = _card(pg, name).locator(".dvuhr")
    b.scroll_into_view_if_needed()
    b.evaluate("e => e.click()")                         # feste Kopf-/Speicherleiste kann den Knopf je nach Scrollstand verdecken
    pg.wait_for_selector("#dvubody .dvusrc, #dvubody .bad", timeout=15000)
    pg.wait_for_timeout(200)


def _shot(pg, name):
    d = os.environ.get("UHR_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(Path(d) / name))


def _row(pg, name):
    return pg.locator("#dvubody tbody tr", has=pg.locator(f"code:text-is('{name}')")).first


def test_device_dialog_shows_fields_per_source_with_counts(pw, apps):
    pg = _page(pw, apps["zepp"])
    try:
        assert "Was liefert diese Uhr?" in _card(pg, "Balance 2").inner_text()
        _open(pg, "Balance 2")
        box = pg.locator(".dvubox")
        assert "Gelesen werden die 10 neuesten Touren" in box.inner_text() and "von 12" in box.inner_text()
        heads = [x.split("\n")[0] for x in pg.locator("#dvubody .dvusrc h3").all_inner_texts()]
        assert heads == ["Zepp: Trainings-Zusammenfassung", "Zepp: Detaildaten (Kanäle)", "FIT-Originaldatei", "GPX-Spur", "Messwert-Datei (ausgewertet)"]
        assert "10 von 10 Touren" in pg.locator("#dvubody .dvusrc h3").first.inner_text()
        assert "1 von 10 Touren" in pg.locator("#dvubody .dvusrc h3").nth(2).inner_text()          # FIT nur bei einer Tour
        assert "5 von 10 Touren" in pg.locator("#dvubody .dvusrc h3").nth(3).inner_text()          # GPX bei jeder zweiten
        cal = _row(pg, "calorie")
        assert "10 von 10" in cal.inner_text() and cal.locator(".dvuy").count() == 1 and "512" in cal.inner_text()
        nf_ = _row(pg, "neues_feld")
        assert "10 von 10" in nf_.inner_text() and nf_.locator(".dvun.has").count() == 1 and "nein" in nf_.inner_text()
        assert "vermutlich: Erholungszeit" in _row(pg, "recovery_time").inner_text()
        u = _row(pg, "record.feld_226")
        assert "1 von 1" in u.inner_text() and "unbekanntes Feld" in u.inner_text() and "300 bis 339" in u.inner_text()
        assert "nicht angezeigt" in _row(pg, "lat_start").inner_text() and "48.1234" not in box.inner_text()
        assert _row(pg, "stress").locator("td").nth(0).inner_text().startswith("0 von 10")
        assert "10 Zepp-Details" not in box.inner_text() and not pg.posts and not pg.errors, pg.errors
        _shot(pg, "geraet-dialog-desktop.png")
        # Filter: nur nicht ausgewertete Felder mit Daten
        pg.check("#dvuonly")
        assert _row(pg, "calorie").count() == 0 and _row(pg, "neues_feld").count() == 1 and _row(pg, "stress").count() == 0
        pg.uncheck("#dvuonly")
        assert _row(pg, "calorie").count() == 1
        pg.click("#dvuclose")
        assert pg.locator(".dvubox").count() == 0 and not pg.locator(".dvbox").count()           # kein Bearbeiten-Dialog geöffnet
    finally:
        pg.browser_.close()


def test_menu_entry_and_save_as_file(pw, apps):
    pg = _page(pw, apps["zepp"])
    try:
        _card(pg, "Balance 2").locator(".dvmore").click()
        assert "Was liefert diese Uhr?" in pg.locator(".dvmenu").inner_text()
        pg.locator(".dvmenu button", has_text="Was liefert diese Uhr?").click()
        pg.wait_for_selector("#dvubody .dvusrc", timeout=15000)
        with pg.expect_download() as dl:
            pg.click("#dvudl")
        d = dl.value
        assert d.suggested_filename.startswith("uhr-felder-") and d.suggested_filename.endswith(".json")
        body = json.loads(Path(d.path()).read_text(encoding="utf-8"))
        assert body["format"] == "meine-touren-uhr-felder" and body["touren_geprueft"] == 10
        txt = json.dumps(body)
        for bad in ("Rundweg", "Berlin", "48.1234", "ABC123", "Garmin-Runde"):
            assert bad not in txt, bad
    finally:
        pg.browser_.close()


def test_empty_state_device_without_tours_and_without_zepp_access(pw, apps):
    pg = _page(pw, apps["zepp"])
    try:
        _open(pg, "Amazfit Pace")
        t = pg.locator("#dvubody").inner_text()
        assert "liegen noch keine Felder vor" in t and "noch keine Touren zugeordnet" in t
        assert pg.locator("#dvubody table").count() == 0 and not pg.locator("#dvudl").is_visible()       # nichts zu speichern
        assert t.count("noch keine Touren zugeordnet") == 1                                              # Erklärung nicht je Quelle wiederholt
        _shot(pg, "geraet-leer.png")
    finally:
        pg.browser_.close()
    pg = _page(pw, apps["nozepp"])
    try:
        _open(pg, "Balance 2")
        t = pg.locator("#dvubody").inner_text()
        assert "kein Zepp-Zugang" in t and "Einstellungen → Zepp" in t
        assert "Messwert-Datei" in t and pg.locator("#dvubody tbody tr").count() > 0              # Rest funktioniert trotzdem
        assert _row(pg, "speed").locator(".dvuy").count() == 1
        _shot(pg, "geraet-ohne-zepp.png")
    finally:
        pg.browser_.close()


def test_garmin_device_has_no_zepp_part(pw, apps):
    pg = _page(pw, apps["zepp"])
    try:
        _open(pg, "Forerunner")
        t = pg.locator("#dvubody").inner_text()
        assert "nicht zutreffend" in t and "nur bei Zepp-Uhren" in t
    finally:
        pg.browser_.close()


def test_tour_page_link_opens_tour_dialog(pw, apps):
    tid = f"z{T0 + 10}"
    pg = _page(pw, apps["zepp"], path=f"#/tour/{tid}", wait="#metcard")
    try:
        assert pg.locator("#dvulink").inner_text() == "Alle Felder dieser Tour"
        pg.click("#dvulink")
        pg.wait_for_selector("#dvubody .dvusrc", timeout=15000)
        pg.wait_for_timeout(200)
        t = pg.locator(".dvubox").inner_text()
        assert "Alle Felder dieser Tour" in t and "Rundweg Nr. 0" in t and "nichts gespeichert oder verändert" in t
        assert "vorhanden" in _row(pg, "calorie").inner_text() and _row(pg, "calorie").locator(".dvuy").count() == 1
        assert pg.locator("#dvudl").count() == 0                                                  # Export nur beim Gerät
        assert "FIT-Originaldatei" in t and "nicht vorhanden" in t
        _shot(pg, "tour-dialog-desktop.png")
        assert not [x for x in pg.posts if "/api/settings" not in x[1]] and not pg.errors, (pg.posts, pg.errors)       # die Seite merkt sich selbst die Ansicht; die Diagnose schreibt nichts
    finally:
        pg.browser_.close()


def _contrast_js():
    return """() => {
      const parse = s => { const m = s.match(/[\\d.]+/g).map(Number); return s.startsWith('color(') ? m.slice(0, 3).map(v => v * 255) : m.slice(0, 3); };
      const lin = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
      const L = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
      const bg = el => { for (let e = el; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor; const a = c.match(/[\\d.]+/g); if (c !== 'rgba(0, 0, 0, 0)' && !(a.length === 4 && +a[3] === 0)) return parse(c); } return [255, 255, 255]; };
      const out = [];
      for (const sel of ['.dvuy', '.dvun', '.dvun.has', '.dvut thead th', '.dvut code', '.dvut small', '.dvut td', '.dvuh', '.dvusrc h3', '.dvqs.ok', '.dvqs.none', '.dvuhr', '.dvuchk', '.dvuempty']) {
        document.querySelectorAll(sel).forEach((el, i) => { if (i > 2) return; const f = parse(getComputedStyle(el).color), b = bg(el); const l1 = L(f), l2 = L(b); out.push([sel, (Math.max(l1, l2) + .05) / (Math.min(l1, l2) + .05)]); });
      }
      return out;
    }"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_contrast_at_least_4_5_in_card_and_dialog(pw, apps, scheme):
    pg = _page(pw, apps["zepp"], scheme=scheme)
    try:
        _open(pg, "Balance 2")
        res = pg.evaluate(_contrast_js())
        sels = {s for s, _c in res}
        assert {".dvuy", ".dvun.has", ".dvut code", ".dvut small", ".dvuhr"} <= sels
        bad = [(s, round(c, 2)) for s, c in res if c < 4.5]
        assert not bad, bad
        _shot(pg, f"geraet-dialog-{scheme}.png")
    finally:
        pg.browser_.close()


def test_mobile_390_no_horizontal_scroll(pw, apps):
    pg = _page(pw, apps["zepp"], width=390, height=844, dpr=2)
    try:
        _card(pg, "Balance 2").scroll_into_view_if_needed()
        _shot(pg, "geraet-karte-390.png")
        assert pg.evaluate("document.documentElement.scrollWidth") <= 391
        _open(pg, "Balance 2")
        box = pg.locator(".dvubox")
        assert pg.evaluate("document.documentElement.scrollWidth") <= 391
        assert pg.evaluate("(() => { const b = document.querySelector('.dvubox'); return b.scrollWidth <= b.clientWidth + 1; })()")
        over = pg.evaluate("[...document.querySelectorAll('.dvubox *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('svg')).map(e => e.className || e.tagName).slice(0, 5)")
        assert not over, over
        assert "Wird ausgewertet" in box.inner_text() and "Bereich" in box.inner_text()           # Beschriftungen der gestapelten Zeilen
        assert pg.locator("#dvuclose").bounding_box()["height"] >= 32 and pg.locator("#dvudl").bounding_box()["width"] <= 390
        _shot(pg, "geraet-dialog-390.png")
        pg.evaluate("document.querySelector('.dvubox').scrollTo(0, 700)")
        pg.wait_for_timeout(150)
        _shot(pg, "geraet-dialog-390-mitte.png")
        pg.evaluate("document.querySelector('.dvubox').scrollTo(0, 99999)")
        pg.wait_for_timeout(150)
        _shot(pg, "geraet-dialog-390-ende.png")
        pg.click("#dvuclose")
    finally:
        pg.browser_.close()
    tid = f"z{T0 + 10}"
    pg = _page(pw, apps["zepp"], width=390, height=844, dpr=2, path=f"#/tour/{tid}", wait="#metcard")
    try:
        assert pg.evaluate("document.documentElement.scrollWidth") <= 391
        pg.locator("#dvulink").scroll_into_view_if_needed()
        _shot(pg, "tour-messwerte-390.png")
        pg.click("#dvulink")
        pg.wait_for_selector("#dvubody .dvusrc", timeout=15000)
        assert pg.evaluate("document.documentElement.scrollWidth") <= 391
        _shot(pg, "tour-dialog-390.png")
    finally:
        pg.browser_.close()


def test_dialog_is_translated_in_four_languages(pw, apps):
    """Die Zeilen in 00-i18n-neu.js greifen: Überschrift, Tabellenkopf, Quellen, Zustände und Klartext erscheinen übersetzt."""
    want = {"en-US": ["What does this watch deliver?", "Zepp: workout summary", "Evaluated", "Calories (kcal)", "probably: Training effect", "unknown field – not evaluated"],
            "fr-FR": ["Que fournit cette montre ?", "Zepp : résumé de l’entraînement", "Exploité", "Calories (kcal)", "probablement : Effet d’entraînement", "champ inconnu – non exploité"],
            "es-ES": ["¿Qué datos entrega este reloj?", "Zepp: resumen del entrenamiento", "Se evalúa", "Calorías (kcal)", "probablemente: Efecto del entrenamiento", "campo desconocido: no se evalúa"]}
    for loc, texts in want.items():
        pg = _page(pw, apps["zepp"], locale=loc)
        try:
            b = _card(pg, "Balance 2").locator(".dvuhr")
            b.evaluate("e => e.click()")
            pg.wait_for_selector("#dvubody .dvusrc", timeout=15000)
            pg.wait_for_timeout(300)
            t = pg.locator(".dvubox").inner_text()
            for x in texts:
                assert x in t, (loc, x)
            assert "Wird ausgewertet" not in t and "Nur Felder" not in t, loc
        finally:
            pg.browser_.close()
