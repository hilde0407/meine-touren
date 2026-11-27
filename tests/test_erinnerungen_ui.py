"""3.32.0 – Erinnerungen-Kachel (Browser, Chromium): Standard unverändert, Einstellungs-Dialog mit Vorschau (Auswahl, Darstellung, Größe, Anzeige), Wirkung je Auswahlart und Darstellung,
Breiten, Einzelbild-Show (Automatik, Pause, „weniger Bewegung“), weitere Kacheln, Standard wiederherstellen, Link zur Diashow, 390 px hell und dunkel ohne Überlauf, Englisch.
Wettlauf-Regel: nach jeder Aktion auf den Zustand warten (wait_for_function mit Pfeilfunktion / expect, 15 s), nie nur schlafen. Mit TS_SHOTS=<Ordner> entstehen Screenshots."""
import json
import os
import re
import socket
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.test_bausteine_ui import T, TEXTCONTRAST, _api, _edit, _reset, _shot  # noqa: F401
from tests.test_bausteine_ui import pw  # noqa: F401  (Fixture)
from tests.test_bausteine_konfig_ui import click_gear, save_dialog
from tests.test_tourseite_ui import LAUNCH, SEED, _wait

ROOT = Path(__file__).resolve().parent.parent

EXTRA = r"""
import sys, os, time, random; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from datetime import date, datetime
from app import db
from app.gpxtools import TZ
db.init()
today = date.today()
def back(y):
    try:
        return today.replace(year=today.year - y)
    except ValueError:
        return today.replace(year=today.year - y, day=28)
def tour(tid, name, sport, d, h=9):
    ts = int(datetime(d.year, d.month, d.day, h, 0, tzinfo=TZ).timestamp())
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,9000,7000,200,200,50.7,7.2,'t','komoot')", (tid, name, sport, ts, ts + 7000))
    return ts
from datetime import timedelta
t_h0 = tour("h0", "Heute vor einem Jahr", "hike", back(1))
t_h1 = tour("h1", "Heute vor zwei Jahren", "mtb", back(2))
t_b1 = tour("b1", "Radrunde am See", "mtb", today - timedelta(days=9))
t_b2 = tour("b2", "Morgenlauf", "jogging", today - timedelta(days=30))
from PIL import Image, ImageDraw
pd = %(photos)r
os.makedirs(pd, exist_ok=True)
cols = [("#2f6f5f", "#e8c46a"), ("#3b6f9f", "#f2e6c8"), ("#7a5f3f", "#9fc2a8"), ("#4a7a4a", "#c8dce8"), ("#6a4f8f", "#f0d0a0"), ("#8f4f4f", "#d0e0c0")]
shapes = [(900, 600), (900, 600), (600, 900), (1200, 400), (900, 600), (900, 600)]
plan = [("r3", 40 * 86400, 4, True), ("h0", None, 3, False), ("h1", None, 2, True), ("b1", None, 4, True), ("b2", None, 2, False), ("r1", 200 * 86400, 1, False)]
base = {"h0": t_h0, "h1": t_h1, "b1": t_b1, "b2": t_b2}
n = 0
for tid, back_s, k, rated in plan:
    ts = base.get(tid) or (int(time.time()) - back_s)
    for i in range(k):
        w, h = shapes[n %% len(shapes)]
        c1, c2 = cols[n %% len(cols)]
        im = Image.new("RGB", (w, h), c1)
        dr = ImageDraw.Draw(im)
        dr.polygon([(0, h), (w * .28, h * .43), (w * .53, h * .8), (w * .78, h * .33), (w, h)], fill=c2)
        dr.ellipse((w * .75, h * .1, w * .86, h * .27), fill="#fff3b0")
        f = os.path.join(pd, "e%%d.jpg" %% n)
        im.save(f, "JPEG", quality=85)
        db.execute("INSERT INTO photos(path,mtime,size,taken_ts,tour_id,dated,rating,sharp,manual) VALUES(?,?,?,?,?,1,?,12.0,0)", (f, 1.0, 1000, ts + 600 * (i + 1), tid, 5 if (rated and i == 0) else 0))
        n += 1
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("erin")
    data = tmp / "data"
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    for code in (SEED % {"root": str(ROOT), "data": str(data)}, EXTRA % {"root": str(ROOT), "data": str(data), "photos": str(tmp / "pics")}):
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, env=env)
        assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / "launch.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    pr = subprocess.Popen([sys.executable, str(script)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    yield url
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)


def photos(url, **q):
    with urllib.request.urlopen(url + "/api/photos?" + urllib.parse.urlencode(q), timeout=15) as r:
        return json.loads(r.read())


def browser(pw, url, width=1280, height=1000, scheme="light", dpr=1, lang="de", reduce=True, wait=True, touch=False):
    b = pw.chromium.launch()
    ctx = b.new_context(locale="en-US" if lang == "en" else "de-DE", viewport={"width": width, "height": height}, color_scheme=scheme, device_scale_factor=dpr,
                        reduced_motion="reduce" if reduce else "no-preference", has_touch=touch, is_mobile=touch)
    ctx.add_init_script("try { localStorage.setItem('lang', %r); } catch (e) {}" % lang)
    pg = ctx.new_page()
    pg.errors, pg.reqs = [], []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("request", lambda r: pg.reqs.append(r.url))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(url) else r.continue_())
    pg.browser_ = b
    pg.goto(f"{url}/#/dash")
    pg.wait_for_selector("main.home #hlast", timeout=T)
    pg.wait_for_function("() => !!document.querySelector('#slopen')", timeout=T)
    if wait:
        ready(pg)
    return pg


READY = "() => { const s = document.querySelector('main.home [id=hmemsec]'); return !!s && !s.hidden && s.querySelectorAll('.erb img').length > 0; }"


def ready(pg, n=None, sel="#hmemsec"):
    pg.wait_for_function("([sel, n]) => { const s = document.querySelector(sel); return !!s && !s.hidden && s.querySelectorAll('.erb img').length > 0 && (n === null || s.querySelectorAll('.erb img').length === n); }", arg=[sel, n], timeout=T)


def put(url, cfg=None, w=None, widgets=None, extra=None):
    lay = {"v": 1, **(extra or {})}
    if cfg is not None:
        lay["cfg"] = {"erinn": cfg}
    if w:
        lay["w"] = {**lay.get("w", {}), "erinn": w}
    if widgets:
        lay["widgets"] = widgets
    _api(url, "uebersicht", "PUT", {"layout": lay})


def show(pw, url, cfg=None, w=None, extra=None, **kw):
    put(url, cfg, w, extra=extra)
    return browser(pw, url, **kw)


def close(pg):
    assert not pg.errors, pg.errors
    pg.browser_.close()


NIMG = "() => document.querySelectorAll('#hmemsec .erb img').length"
COLS = "() => new Set([...document.querySelectorAll('#hmemsec .erg img')].map(i => Math.round(i.getBoundingClientRect().left))).size"
OVER = "() => ({page: document.documentElement.scrollWidth - window.innerWidth, tile: [...document.querySelectorAll('#hmemsec, #hmemsec .erb, #hmemsec .erg')].filter(e => e.scrollWidth > e.clientWidth + 1).map(e => e.className)})"
ASPECT = "() => { const r = document.querySelector('#hmemsec .erg img').getBoundingClientRect(); return r.width / r.height; }"


# ------------------------------------------------------------------  Standard bleibt Standard  ------------------------------------------------------------------

def test_default_is_the_old_tile(pw, app):
    _reset(app)
    pg = browser(pw, app)
    reqs = [u for u in pg.reqs if "/api/photos?random" in u]
    assert reqs and reqs[0].endswith("/api/photos?random=true&limit=6"), reqs                    # dieselbe Abfrage wie bisher
    assert pg.evaluate(NIMG) == 6
    assert pg.locator("#hmemsec h2").inner_text() == "Erinnerungen"
    a = pg.locator("#hmemsec a.hmore")
    assert a.inner_text() == "Zufalls-Diashow" and a.get_attribute("href") == "slideshow.html?random=1" and a.get_attribute("target") == "_blank"
    assert pg.locator("#hmemsec .ernew, #hmemsec figcaption, #hmemsec .flk").count() == 0 and pg.locator("main.home .slit").count() == 0
    assert pg.evaluate("() => document.querySelector('#hmemsec').classList.contains('slcell')") and pg.locator("#hmemsec.w-halb").count() == 1
    assert pg.evaluate(OVER) == {"page": 0, "tile": []}
    pg.locator("#hmemsec .erg img").first.click()                                                  # Lightbox wie bisher
    pg.wait_for_function("() => document.querySelector('#lb').classList.contains('on')", timeout=T)
    close(pg)


# ------------------------------------------------------------------  Dialog: speichern und wirken  ------------------------------------------------------------------

GEAR = '.slit[data-sl="erinn"] [data-a="cfg"]'
DOC = "() => JSON.stringify(((SL.docs.uebersicht || {}).cfg || {}).erinn || null)"


def radio(pg, name, value):
    pg.locator(f'.sldlg input[name="{name}"][value="{value}"]').check()


def open_dialog(pg):
    _edit(pg)
    click_gear(pg, GEAR)
    pg.wait_for_selector('.sldlg [role="dialog"] form.erform', timeout=T)
    expect(pg.locator(".sldlg .erpvb img").first).to_be_visible(timeout=15000)


def test_dialog_modes_save_and_take_effect(pw, app):
    _reset(app)
    pg = browser(pw, app)
    open_dialog(pg)
    assert pg.locator(".sldlg .slbox > h2").inner_text() == "Einstellungen: Erinnerungen"
    assert pg.locator(".sldlg .erpvb .hsh h2").inner_text() == "Erinnerungen"                       # Vorschau zeigt die Kachel
    # Vorschau folgt dem Formular: 3 Fotos als Streifen
    radio(pg, "er-n", 3)
    radio(pg, "er-view", "strip")
    pg.wait_for_function("() => document.querySelectorAll('.sldlg .erpvb .ers img').length === 3", timeout=T)
    radio(pg, "er-view", "grid")
    radio(pg, "er-n", 12)
    pg.wait_for_function("() => document.querySelectorAll('.sldlg .erpvb .erg img').length === 12", timeout=T)
    pg.get_by_role("button", name="Abbrechen", exact=True).click()                                 # Abbrechen speichert nichts
    pg.wait_for_function("() => !document.querySelector('.sldlg')", timeout=T)
    assert pg.evaluate(DOC) == "null" and pg.evaluate(NIMG) == 6
    # Beste Fotos, 3 Stück: genau die bewerteten (je Tour das erste Foto)
    click_gear(pg, GEAR)
    pg.wait_for_selector('.sldlg form.erform', timeout=T)
    radio(pg, "er-mode", "best")
    radio(pg, "er-n", 3)
    save_dialog(pg)
    pg.wait_for_function("() => (SL.docs.uebersicht.cfg.erinn || {}).mode === 'best'", timeout=T)
    ready(pg, 3)
    ids = pg.evaluate("() => [...document.querySelectorAll('#hmemsec .erg img')].map(i => +/pic\\/(\\d+)/.exec(i.src)[1])")
    best = [p["id"] for p in photos(app, best="true", limit=3)]
    assert sorted(ids) == sorted(best) and len(set(ids)) == 3
    assert json.loads(pg.evaluate(DOC)) == {"mode": "best", "n": 3}                                 # nur Abweichungen vom Standard
    assert pg.locator("#hmemsec .flk").inner_text() == "Beste Fotos" and pg.locator("#hmemsec a.hmore").inner_text() == "Diashow starten"
    assert any("best=true" in u and "limit=3" in u for u in pg.reqs)
    # An diesem Tag in früheren Jahren, nur Wandern: 3 Fotos der Tour „Heute vor einem Jahr“
    click_gear(pg, GEAR)
    pg.wait_for_selector('.sldlg form.erform', timeout=T)
    radio(pg, "er-mode", "day")
    radio(pg, "er-n", 6)
    pg.locator(".sldlg .erdt2 summary").click()
    pg.locator(".sldlg .flsp .flchip", has_text=re.compile(r"^Wandern$")).click()
    pg.wait_for_function("() => document.querySelectorAll('.sldlg .erpvb .erg img').length === 3", timeout=T)
    save_dialog(pg)
    ready(pg, 3)
    assert pg.evaluate("() => [...new Set([...document.querySelectorAll('#hmemsec img')].map(i => i.alt))]") == ["Heute vor einem Jahr"]
    assert any("day=" in u and "before=" in u and "sport=hike" in u for u in pg.reqs)
    assert pg.locator("#hmemsec a.hmore").get_attribute("href").startswith("slideshow.html?day=") and "sport=hike" in pg.locator("#hmemsec a.hmore").get_attribute("href")
    # Neueste: die jüngsten Fotos zuerst
    click_gear(pg, GEAR)
    pg.wait_for_selector('.sldlg form.erform', timeout=T)
    radio(pg, "er-mode", "recent")
    pg.locator(".sldlg .erreset").click()                                          # Standardwerte im Formular, noch nichts gespeichert
    pg.wait_for_function("() => document.querySelector('.sldlg input[name=er-mode]:checked').value === 'random' && document.querySelector('.sldlg input[name=er-n]:checked').value === '6'", timeout=T)
    radio(pg, "er-mode", "recent")
    radio(pg, "er-n", 9)
    save_dialog(pg)
    ready(pg, 9)
    ts = pg.evaluate("() => [...document.querySelectorAll('#hmemsec img')].map(i => +/pic\\/(\\d+)/.exec(i.src)[1])")
    assert ts == [p["id"] for p in photos(app, recent=1, limit=9)]
    # Aktivität und Zeitraum: Joggen, letzte 90 Tage: nur die 2 Fotos des Morgenlaufs
    click_gear(pg, GEAR)
    pg.wait_for_selector('.sldlg form.erform', timeout=T)
    pg.locator(".sldlg .erdt2").evaluate("e => (e.open = true)")
    pg.locator(".sldlg .flsp .flchip", has_text=re.compile(r"^Laufen|Joggen")).first.click()
    pg.locator('.sldlg select[name="f1"]').select_option("90d")
    pg.wait_for_function("() => document.querySelectorAll('.sldlg .erpvb .erg img').length === 2", timeout=T)
    save_dialog(pg)
    ready(pg, 2)
    cfg = json.loads(pg.evaluate(DOC))
    assert cfg["sports"] == ["jogging"] and cfg["range"] == "90d" and cfg["mode"] == "recent"
    assert pg.evaluate("() => [...new Set([...document.querySelectorAll('#hmemsec img')].map(i => i.alt))]") == ["Morgenlauf"]
    assert any("date_from=" in u and "sport=jogging" in u for u in pg.reqs)
    assert "range" in pg.locator("#hmemsec a.hmore").get_attribute("href") or "from=" in pg.locator("#hmemsec a.hmore").get_attribute("href")
    close(pg)


def test_settings_persist_after_reload_and_reset_restores_default(pw, app):
    _reset(app)
    cfg = {"mode": "recent", "n": 9, "view": "grid", "ratio": "43", "size": "l", "caption": True, "shuffle": True, "title": "Meine Bilder"}
    pg = show(pw, app, cfg)
    assert pg.locator("#hmemsec h2").inner_text() == "Meine Bilder"
    pg.reload()
    pg.wait_for_selector("main.home #hlast", timeout=T)
    ready(pg, 9)
    assert pg.locator("#hmemsec figcaption").count() == 9 and pg.locator("#hmemsec .ernew").count() == 1
    _edit(pg)
    pg.locator("#slbar [data-a=more]").click() if pg.locator("#slbar [data-a=reset]").is_hidden() else None
    pg.locator("#slbar [data-a=reset]").click()
    pg.get_by_role("button", name="Standard wiederherstellen").last.click()
    pg.wait_for_function("() => !SL.docs.uebersicht || !(SL.docs.uebersicht.cfg || {}).erinn", timeout=T)
    ready(pg, 6)
    assert pg.locator("#hmemsec h2").inner_text() == "Erinnerungen" and pg.locator("#hmemsec figcaption, #hmemsec .ernew").count() == 0
    pg.wait_for_function(SAVED, timeout=T)
    assert _api(app, "uebersicht").get("layout") in (None, {}), _api(app, "uebersicht")
    close(pg)


SAVED = "() => { const s = document.getElementById('slsaved'); return !!s && s.textContent.trim() === 'Ansicht gespeichert'; }"


# ------------------------------------------------------------------  Darstellung, Seitenverhältnis, Größe  ------------------------------------------------------------------

def test_grid_ratio_size_and_caption(pw, app):
    for ratio, exp in (("sq", 1.0), ("43", 4 / 3), ("169", 16 / 9)):
        pg = show(pw, app, {"ratio": ratio, "n": 6}, w="voll")
        a = pg.evaluate(ASPECT)
        assert abs(a - exp) < 0.03, (ratio, a)
        close(pg)
    widths = {}
    for size in ("s", "m", "l"):
        pg = show(pw, app, {"size": size, "n": 9, "caption": True}, w="zweidrittel")
        widths[size] = pg.evaluate("() => document.querySelector('#hmemsec .erg img').getBoundingClientRect().width")
        if size == "s":
            cap = pg.locator("#hmemsec figcaption").first
            assert cap.locator("b").inner_text() and re.fullmatch(r"\d\d\.\d\d\.\d{4}", cap.locator("span").inner_text())          # Tourname und Datum
            assert pg.evaluate("() => document.querySelectorAll('#hmemsec figcaption').length") == 9
        close(pg)
    assert widths["s"] < widths["m"] < widths["l"], widths                                               # größere Bilder = breitere Kacheln, weniger Spalten
    pg = show(pw, app, {"ratio": "orig", "n": 12, "size": "m"}, w="voll")                                # Originalformat: unterschiedliche Höhen, nichts abgeschnitten
    ready(pg, 12)
    pg.wait_for_function("() => [...document.querySelectorAll('#hmemsec .erg img')].every(i => i.complete && i.naturalWidth > 0)", timeout=T)
    hs = pg.evaluate("() => [...new Set([...document.querySelectorAll('#hmemsec .erg img')].map(i => Math.round(i.getBoundingClientRect().height)))].length")
    assert hs >= 3
    assert pg.evaluate("() => [...document.querySelectorAll('#hmemsec .erg img')].every(i => Math.abs(i.getBoundingClientRect().width / i.getBoundingClientRect().height - i.naturalWidth / i.naturalHeight) < 0.05)")
    assert pg.evaluate(OVER) == {"page": 0, "tile": []}
    close(pg)


ROWMATES = {"voll": {}, "zweidrittel": {"wp1": "drittel"}, "halb": {"wp1": "halb"}, "drittel": {"wp1": "drittel", "wp2": "drittel"}}
SHARE = {"voll": (0.94, 1.01), "zweidrittel": (0.6, 0.7), "halb": (0.44, 0.52), "drittel": (0.28, 0.36)}


def test_columns_follow_the_width_of_the_tile(pw, app):
    """Breite über das Raster: Kachel neben Nachbarn gleicher Zeile (sonst füllt das Raster den Rest auf), Spalten der Fotos nach der echten Breite."""
    cols = {}
    for w in ("voll", "zweidrittel", "halb", "drittel"):
        extra = {"hidden": ["tag"], "order": ["aufmacher", "jahr", "zepp", "zuletzt", "erinn", "wp1", "wp2"], "widgets": [{"id": "wp1", "type": "periode"}, {"id": "wp2", "type": "serie"}],
                 "w": {"wp2": "drittel", **ROWMATES[w]}}
        pg = show(pw, app, {"n": 12, "size": "m"}, w=w, extra=extra)
        assert pg.locator(f"#hmemsec.w-{w}").count() == 1
        cols[w] = pg.evaluate(COLS)
        tile = pg.evaluate("() => document.querySelector('#hmemsec').getBoundingClientRect().width / document.querySelector('main.home').getBoundingClientRect().width")
        assert SHARE[w][0] < tile < SHARE[w][1], (w, tile)
        assert pg.evaluate(OVER) == {"page": 0, "tile": []}
        n = pg.evaluate(NIMG)
        rows = pg.evaluate("() => new Set([...document.querySelectorAll('#hmemsec .erg img')].map(i => Math.round(i.getBoundingClientRect().top))).size")
        assert rows * cols[w] >= n and (rows - 1) * cols[w] < n                                          # keine leeren Zeilen, höchstens ein Rest in der letzten
        close(pg)
    assert cols["voll"] > cols["zweidrittel"] >= cols["halb"] > cols["drittel"] >= 2, cols


def test_strip_scrolls_sideways(pw, app):
    pg = show(pw, app, {"view": "strip", "n": 12, "size": "l", "caption": True}, w="halb")
    s = pg.locator("#hmemsec .ers")
    assert pg.evaluate("() => { const e = document.querySelector('#hmemsec .ers'); return e.scrollWidth > e.clientWidth + 50 && getComputedStyle(e).overflowX === 'auto'; }")
    assert s.get_attribute("tabindex") == "0" and s.get_attribute("role") == "region"
    h = pg.evaluate("() => [...new Set([...document.querySelectorAll('#hmemsec .ers img')].map(i => Math.round(i.getBoundingClientRect().height)))]")
    assert h == [240]
    s.evaluate("e => (e.scrollLeft = 400)")
    assert s.evaluate("e => e.scrollLeft") > 300
    assert pg.evaluate(OVER)["page"] == 0
    close(pg)


# ------------------------------------------------------------------  Einzelbild-Show  ------------------------------------------------------------------

CUR = "() => document.querySelector('#hmemsec .erpc').textContent.trim()"


def test_show_buttons_keys_height_and_lightbox(pw, app):
    pg = show(pw, app, {"view": "show", "n": 6, "height": "k", "caption": True}, w="voll")
    assert pg.evaluate("() => document.querySelectorAll('#hmemsec .erpv img.on').length") == 1 and pg.evaluate(CUR) == "1 / 6"
    assert pg.evaluate("() => document.querySelector('#hmemsec .erpv').getBoundingClientRect().height") == 180
    assert pg.locator("#hmemsec .erpcap b").inner_text()
    pg.locator("#hmemsec .ernext").click()
    pg.wait_for_function("() => document.querySelector('#hmemsec .erpc').textContent.trim() === '2 / 6'", timeout=T)
    pg.locator("#hmemsec .erprev").click()
    pg.locator("#hmemsec .erprev").click()
    pg.wait_for_function("() => document.querySelector('#hmemsec .erpc').textContent.trim() === '6 / 6'", timeout=T)            # läuft rund
    pg.locator("#hmemsec .erpv").focus()
    pg.keyboard.press("ArrowRight")
    pg.wait_for_function("() => document.querySelector('#hmemsec .erpc').textContent.trim() === '1 / 6'", timeout=T)
    assert pg.evaluate("() => document.querySelector('#hmemsec .erpv img.on').getAttribute('aria-hidden')") == "false"
    for h, px in (("n", 280), ("h", 420)):
        put(app, {"view": "show", "n": 6, "height": h}, w="voll")
        pg.reload()
        pg.wait_for_selector("main.home #hlast", timeout=T)
        ready(pg)
        pg.wait_for_function("(px) => document.querySelector('#hmemsec .erpv').getBoundingClientRect().height === px", arg=px, timeout=T)
    pg.keyboard.press("Tab")
    pg.locator("#hmemsec .erpv").click()
    pg.wait_for_function("() => document.querySelector('#lb').classList.contains('on')", timeout=T)
    close(pg)


def test_show_advances_by_itself_pauses_on_hover_and_respects_reduced_motion(pw, app):
    put(app, {"view": "show", "n": 6, "tempo": 3}, w="voll")
    pg = browser(pw, app, reduce=False)                                                          # „weniger Bewegung“ aus: Automatik an
    assert pg.evaluate(CUR) == "1 / 6" and pg.locator("#hmemsec .erpp").get_attribute("aria-pressed") == "false"
    pg.wait_for_function("() => document.querySelector('#hmemsec .erpc').textContent.trim() !== '1 / 6'", timeout=T)       # blättert selbst (3 s)
    pg.locator("#hmemsec .erpv").hover()                                                         # Maus darüber: Pause
    now = pg.evaluate(CUR)
    pg.wait_for_timeout(3800)
    assert pg.evaluate(CUR) == now, "blättert trotz Maus auf dem Bild"
    pg.mouse.move(2, 2)                                                                          # Maus weg: geht weiter
    pg.wait_for_function("(c) => document.querySelector('#hmemsec .erpc').textContent.trim() !== c", arg=now, timeout=T)
    pg.locator("#hmemsec .erpp").click()                                                         # eigener Anhalten-Knopf
    pg.mouse.move(2, 2)
    assert pg.locator("#hmemsec .erpp").get_attribute("aria-pressed") == "true" and pg.locator("#hmemsec .erpp").get_attribute("aria-label") == "Abspielen"
    now = pg.evaluate(CUR)
    pg.wait_for_timeout(3800)
    assert pg.evaluate(CUR) == now, "blättert trotz Pause"
    close(pg)
    pg = browser(pw, app, reduce=True)                                                           # „weniger Bewegung“ an: keine Automatik, kein Überblenden
    assert pg.locator("#hmemsec .erpp").get_attribute("aria-pressed") == "true" and pg.locator("#hmemsec .erpp").get_attribute("aria-label") == "Abspielen"
    assert pg.evaluate("() => getComputedStyle(document.querySelector('#hmemsec .erpv img')).transitionDuration") in ("0s", "")
    pg.wait_for_timeout(3800)
    assert pg.evaluate(CUR) == "1 / 6"
    pg.locator("#hmemsec .erpp").click()                                                         # auf Wunsch lässt sie sich starten
    pg.wait_for_function("() => document.querySelector('#hmemsec .erpc').textContent.trim() !== '1 / 6'", timeout=T)
    close(pg)


def test_show_pauses_on_touch_and_swipes(pw, app):
    put(app, {"view": "show", "n": 6, "tempo": 3}, w="voll")
    pg = browser(pw, app, width=390, height=844, reduce=False, touch=True)
    box = pg.locator("#hmemsec .erpv").bounding_box()
    y = box["y"] + box["height"] / 2
    pg.evaluate("window.scrollTo(0, 0)")
    pg.locator("#hmemsec .erpv").scroll_into_view_if_needed()
    box = pg.locator("#hmemsec .erpv").bounding_box()
    y = box["y"] + box["height"] / 2
    for dx, exp in ((-1, "2 / 6"), (1, "1 / 6")):                                                # Wischen nach links = nächstes Foto
        pg.evaluate("""([x0, y, x1]) => { const el = document.querySelector('#hmemsec .erpv'); const ev = (t, x) => el.dispatchEvent(new PointerEvent(t, {bubbles: true, pointerType: 'touch', clientX: x, clientY: y, isPrimary: true}));
                       ev('pointerdown', x0); ev('pointerup', x1); }""", [box["x"] + box["width"] / 2, y, box["x"] + box["width"] / 2 + 120 * dx])
        pg.wait_for_function("(e) => document.querySelector('#hmemsec .erpc').textContent.trim() === e", arg=exp, timeout=T)
    pg.evaluate("() => document.querySelector('#hmemsec .erpv').dispatchEvent(new PointerEvent('pointerdown', {bubbles: true, pointerType: 'touch', clientX: 50, clientY: 50, isPrimary: true}))")   # Berührung hält die Automatik an
    now = pg.evaluate(CUR)
    pg.wait_for_timeout(3800)
    assert pg.evaluate(CUR) == now
    close(pg)


# ------------------------------------------------------------------  weitere Kacheln, Diashow-Link  ------------------------------------------------------------------

def test_second_tile_from_the_catalog_and_independent_settings(pw, app):
    _reset(app)
    put(app, {"mode": "best", "n": 3})
    pg = browser(pw, app)
    ready(pg, 3)
    _edit(pg)
    pg.locator("#slbar [data-a=add]").click()
    pg.wait_for_selector(".slcat .slcard", timeout=T)
    card = pg.locator('.slcard:has([data-add="erinn"])')
    assert card.count() == 1 and card.locator("h3").inner_text() == "Erinnerungen" and "Weitere" not in card.inner_text() and card.locator('[data-add="erinn"]').inner_text() == "Hinzufügen"
    card.locator('[data-add="erinn"]').click()
    pg.wait_for_function("() => !!document.querySelector('main.home [data-wtype=erinn]')", timeout=T)
    wid = pg.evaluate("() => document.querySelector('main.home [data-wtype=erinn]').dataset.wid")
    ready(pg, 6, f"#tlw-{wid}")                                                                  # neue Kachel: Standard (6 zufällige), die erste bleibt bei 3 besten
    assert pg.locator("#hmemsec .erb img").count() == 3
    click_gear(pg, f'.slit[data-sl="{wid}"] [data-a="cfg"]')
    pg.wait_for_selector('.sldlg form.erform', timeout=T)
    radio(pg, "er-view", "show")
    radio(pg, "er-height", "k")
    save_dialog(pg)
    pg.wait_for_function("(w) => document.querySelectorAll('#tlw-' + w + ' .erpv img').length === 6", arg=wid, timeout=T)
    assert pg.locator("#hmemsec .erb img").count() == 3
    pg.locator("#slbar [data-a=done]").click()
    pg.wait_for_function("() => SL.dirty.size === 0 && SL.busy.size === 0 && !SL.edit", timeout=T)
    doc = _api(app, "uebersicht")["layout"]
    assert doc["cfg"]["erinn"] == {"mode": "best", "n": 3} and doc["widgets"][0]["type"] == "erinn" and doc["widgets"][0]["cfg"] == {"view": "show", "height": "k"}
    _reset(app)
    close(pg)


def test_slideshow_understands_the_link_parameters(pw, app):
    b = pw.chromium.launch()
    for q, want in (("day=%s&before=%d&sport=hike", ["day=", "before=", "sport=hike"]), ("best=60", ["best=true", "limit=60"]), ("recent=1&from=2020-01-01&to=2030-01-01", ["recent=true", "date_from=2020-01-01", "date_to=2030-01-01"])):
        from datetime import date
        q = q % (date.today().strftime("%m-%d"), date.today().year, ) if "%" in q else q
        pg = b.new_page()
        reqs = []
        pg.on("request", lambda r: reqs.append(r.url))
        pg.goto(f"{app}/slideshow.html?{q}")
        pg.wait_for_function("() => document.getElementById('cap') && document.getElementById('cap').textContent.trim().length > 0", timeout=T)
        api = [u for u in reqs if "/api/photos?" in u]
        assert api and all(w in api[0] for w in want), (q, api)
        if "from=" in q or "day=" in q:
            assert pg.evaluate("() => getComputedStyle(document.getElementById('bshr')).display") == "none"               # gefilterte Diashow: kein Teilen
        pg.close()
    b.close()


# ------------------------------------------------------------------  Handy 390 px, hell und dunkel, Englisch  ------------------------------------------------------------------

@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_mobile_390_no_overflow_touch_targets_contrast_and_shots(pw, app, scheme):
    shots = [("grid", {"n": 6}), ("strip", {"view": "strip", "n": 9, "caption": True}), ("show", {"view": "show", "n": 6, "caption": True, "shuffle": True}), ("orig", {"ratio": "orig", "n": 6, "caption": True, "shuffle": True})]
    for name, cfg in shots:
        pg = show(pw, app, dict(cfg, shuffle=True) if name in ("grid", "strip") else cfg, width=390, height=900, scheme=scheme, dpr=2)
        ready(pg)
        pg.locator("#hmemsec").scroll_into_view_if_needed()                                       # Bilder laden erst in der Nähe des Fensters (loading=lazy), im Streifen auch seitlich
        pg.evaluate("() => document.querySelectorAll('#hmemsec .erb img').forEach(i => { i.loading = 'eager'; })")
        pg.wait_for_function("() => [...document.querySelectorAll('#hmemsec .erb img')].filter(i => i.getAttribute('src')).every(i => i.complete)", timeout=T)
        assert pg.evaluate(OVER) == {"page": 0, "tile": []}, name
        if name in ("grid", "orig"):
            assert pg.evaluate(COLS) == 2, name                                                  # Handy: zwei Spalten
        r = pg.evaluate("() => [...document.querySelectorAll('#hmemsec .ernew, #hmemsec .erdia, #hmemsec .erbtn')].filter(e => !e.hidden).map(e => [e.className, Math.round(e.getBoundingClientRect().width), Math.round(e.getBoundingClientRect().height)])")
        assert r and all(w >= 44 and h >= 44 for _, w, h in r), r
        c = pg.evaluate(TEXTCONTRAST, "#hmemsec, #hmemsec *")
        assert c["n"] >= 3 and not c["low"], (name, scheme, c["low"])
        pg.locator("#hmemsec").scroll_into_view_if_needed()
        if os.environ.get("TS_SHOTS"):
            Path(os.environ["TS_SHOTS"]).mkdir(parents=True, exist_ok=True)
            pg.locator("#hmemsec").screenshot(path=str(Path(os.environ["TS_SHOTS"]) / f"erinnerungen-{name}-390-{scheme}.png"))
        close(pg)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_desktop_widths_and_shots(pw, app, scheme):
    out = os.environ.get("TS_SHOTS")
    for name, cfg, w in (("raster-halb", {"n": 6, "caption": True, "shuffle": True}, "halb"), ("raster-voll-4zu3", {"n": 12, "ratio": "43", "size": "s", "caption": True}, "voll"),
                         ("streifen-voll", {"view": "strip", "n": 12, "size": "m", "caption": True}, "voll"), ("show-halb", {"view": "show", "n": 6, "caption": True, "mode": "best"}, "halb"),
                         ("original-zweidrittel", {"ratio": "orig", "n": 9, "size": "m", "caption": True, "mode": "recent"}, "zweidrittel"), ("raster-drittel", {"n": 3, "size": "l"}, "drittel")):
        pg = show(pw, app, cfg, w=w, scheme=scheme)
        pg.wait_for_function("() => [...document.querySelectorAll('#hmemsec .erb img')].filter(i => i.getAttribute('src')).every(i => i.complete)", timeout=T)
        assert pg.evaluate(OVER) == {"page": 0, "tile": []}, name
        c = pg.evaluate(TEXTCONTRAST, "#hmemsec, #hmemsec *")
        assert not c["low"], (name, scheme, c["low"])
        if out:
            Path(out).mkdir(parents=True, exist_ok=True)
            pg.locator("#hmemsec").screenshot(path=str(Path(out) / f"erinnerungen-{name}-1280-{scheme}.png"))
        close(pg)
    pg = show(pw, app, {"mode": "best", "n": 9, "view": "strip", "caption": True, "shuffle": True}, w="halb", scheme=scheme, height=1400)
    open_dialog(pg)
    if out:
        pg.screenshot(path=str(Path(out) / f"erinnerungen-dialog-1280-{scheme}.png"))
    c = pg.evaluate(TEXTCONTRAST, ".sldlg, .sldlg *")
    assert not c["low"], (scheme, c["low"])
    close(pg)
    _reset(app)


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_dialog_390_fits_and_is_touchable(pw, app, scheme):
    _reset(app)
    pg = browser(pw, app, width=390, height=844, scheme=scheme, dpr=2)
    open_dialog(pg)
    assert pg.evaluate("() => ({page: document.documentElement.scrollWidth - window.innerWidth, box: (b => b.scrollWidth - b.clientWidth)(document.querySelector('.sldlg .slbox'))})") == {"page": 0, "box": 0}
    assert pg.evaluate("() => [...document.querySelectorAll('.sldlg .flchip, .sldlg summary, .sldlg .uifoot .btn')].filter(e => e.offsetParent).every(e => e.getBoundingClientRect().height >= 40 && e.getBoundingClientRect().right <= window.innerWidth)")
    radio(pg, "er-view", "show")                                                                  # Felder der Darstellung wechseln mit
    assert pg.evaluate("() => [...document.querySelectorAll('.sldlg [data-for]')].filter(e => !e.hidden).map(e => e.querySelector('legend') ? e.querySelector('legend').textContent : 'hinweis')") == ["hinweis", "Höhe der Show", "Tempo (Sekunden je Foto)"]
    radio(pg, "er-view", "grid")
    assert pg.evaluate("() => [...document.querySelectorAll('.sldlg [data-for]')].filter(e => !e.hidden).map(e => e.querySelector('legend').textContent)") == ["Größe der Fotos"]
    if os.environ.get("TS_SHOTS"):
        Path(os.environ["TS_SHOTS"]).mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(Path(os.environ["TS_SHOTS"]) / f"erinnerungen-dialog-390-{scheme}.png"))
    close(pg)


def test_english_texts(pw, app):
    put(app, {"mode": "best", "n": 3, "view": "show", "caption": True, "shuffle": True})
    pg = browser(pw, app, lang="en")
    assert pg.locator("#hmemsec h2").inner_text() == "Memories" and pg.locator("#hmemsec .flk").inner_text() == "Best photos"
    assert pg.locator("#hmemsec .erdia").inner_text() == "Start slideshow" and pg.locator("#hmemsec .ernew").inner_text() == "Shuffle again"
    pg.wait_for_function("() => document.querySelector('#hmemsec .erpv').getAttribute('aria-label') === 'Photo 1 of 3'", timeout=T)
    assert pg.locator("#hmemsec .erprev").get_attribute("aria-label") == "Previous photo"
    _edit(pg)
    click_gear(pg, GEAR)
    pg.wait_for_selector('.sldlg form.erform', timeout=T)
    expect(pg.locator(".sldlg .slbox > h2")).to_have_text("Settings: Memories", timeout=15000)
    txt = pg.locator(".sldlg form").inner_text()
    for w in ("Which photos", "Single-photo show", "Original format", "Caption (tour name and date)", "Start slideshow"):
        assert w in txt, w
    assert not re.search(r"\b(Auswahl|Darstellung|Größe|Zufällige|Seitenverhältnis)\b", txt), txt
    _reset(app)
    close(pg)


def test_neu_mischen_aendert_reihenfolge_und_zeichnet_neu(pw, app):
    """3.62.2: „Neu mischen“ (nicht Zufällig) mischt die Reihenfolge sichtbar anders, in Raster und Einzelbild-Show, und zeichnet die Anzeige neu; Zufällig zieht neu."""
    srcs = "() => [...document.querySelectorAll('#hmemsec .erf img')].map(i => i.getAttribute('src'))"
    for view, mode in (("grid", "recent"), ("grid", "random")):
        pg = show(pw, app, {"mode": mode, "n": 6, "view": view, "shuffle": True})
        ready(pg, 6)
        cur = pg.evaluate(srcs)
        for _ in range(3):
            pg.evaluate("() => { document.querySelector('#hmemsec .erb').firstElementChild._alt = 1; }")
            pg.click("#hmemsec .ernew")
            pg.wait_for_function("() => { const c = document.querySelector('#hmemsec .erb').firstElementChild; return !!c && !c._alt; }", timeout=T)
            ready(pg, None)
            new = pg.evaluate(srcs)
            assert new != cur, (mode, cur)
            if mode == "recent":
                assert sorted(new) == sorted(cur)
            cur = new
        close(pg)
    put(app)
