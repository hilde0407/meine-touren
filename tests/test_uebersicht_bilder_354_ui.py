"""3.54.0 – Bilder der Übersicht mit Zwischenspeicher (Browser, Chromium), gemessen am Zugriffsprotokoll des Servers: 130 Touren, die meisten mit Fotos,
einige „an diesem Tag“ in früheren Jahren; auf der Übersicht stehen Kopfbereich, „Zuletzt unterwegs“, „An diesem Tag“, „Erinnerungen“ (zufällig und „beste“),
„Zuletzt aufgenommene Fotos“ und „Wiederentdecken“.
Erstes Öffnen: alle Bildadressen tragen eine Version (&v=…), loading=lazy/decoding=async, feste Platzhalter; erneutes Öffnen und Neuladen: keine Bildanfrage.
Screenshots mit MT_SHOTS=<Ordner>."""
import os
import re
import socket
import subprocess
import sys
import urllib.request
import json
from pathlib import Path

import pytest

expect = pytest.importorskip("playwright.sync_api").expect

from tests.helpers_ui import T, quiet, settled  # noqa: E402
from tests.test_tourseite_ui import _wait  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
N = 130

SEED = r"""
import sys, os, time, math, shutil, random; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from PIL import Image, ImageDraw
from app import db, config, routes, photos
db.init()
now = int(time.time())
base = config.DATA_DIR / "motive"; base.mkdir(parents=True, exist_ok=True)
for i in range(12):
    w, h = 960, 640; im = Image.new("RGB", (w, h), (90 + i * 10, 150, 220)); d = ImageDraw.Draw(im)
    d.polygon([(0, h), (0, h * .55), (w * .3, h * (.25 + i * .02)), (w * .55, h * .5), (w * .8, h * .3), (w, h * .5), (w, h)], fill=(40, 90 + i * 8, 60))
    d.rectangle([0, h * .8, w, h], fill=(70, 140, 70)); im.save(base / ("m%%02d.jpg" %% i), quality=80)
SP = ["hike", "hike", "touringbicycle", "mtb", "jogging", "skitour"]
batch = []
def tour(k, ts, name, nph):
    tid = "t%%04d" %% k
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,'t','komoot')",
               (tid, name, SP[k %% 6], ts, ts + 9000, 9000 + k * 10, 9000, 300 + k, 300, 47.5, 11.0))
    routes.store(tid, [(47.5 + 0.01 * math.sin(2 * math.pi * i / 59 + k), 11.0 + 0.012 * (1 - math.cos(2 * math.pi * i / 59)), 900, i * 60000) for i in range(60)])
    if not nph:
        return
    lib = config.LIB_DIR / tid; lib.mkdir(parents=True, exist_ok=True)
    for j in range(nph):
        p = lib / ("f%%02d.jpg" %% j); shutil.copyfile(base / ("m%%02d.jpg" %% ((k + j) %% 12)), p)
        batch.append((str(p), p.stat().st_mtime, p.stat().st_size, ts + 300 + j * 900, None, None))
for k in range(%(n)d):
    tour(k, now - (k * 2 + 1) * 86400 - 3600, "Runde Nummer %%d am See" %% k, 0 if k %% 5 == 3 else 3 + k %% 5)
for y in range(1, 4):                                  # „An diesem Tag“: heute vor 1–3 Jahren (Mittag, damit das Datum auch nahe Mitternacht stimmt)
    d = time.localtime(now); ts = int(time.mktime((d.tm_year - y, d.tm_mon, d.tm_mday if (d.tm_mon, d.tm_mday) != (2, 29) else 28, 12, 0, 0, 0, 0, -1)))
    tour(900 + y, ts, "Jahrestag-Runde %%d" %% y, 4)
photos._store(batch)
photos.assign_all()
"""

LAUNCH = r"""
import sys, os; sys.path.insert(0, %(root)r)
import uvicorn
from app.main import app
uvicorn.run(app, host="127.0.0.1", port=%(port)d, log_level="info", access_log=True)
"""

LAYOUT = {"widgets": [{"id": "wbest", "type": "erinn", "cfg": {"mode": "best"}}, {"id": "wneu", "type": "neuefotos", "cfg": {}},
                      {"id": "wwied", "type": "wiederentdecken", "cfg": {}}]}


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("ub354")
    data = tmp / "data"
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1", MT_NO_WARM="1")
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data), "n": N}], capture_output=True, text=True, cwd=ROOT, env=env)
    assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / "launch.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    log = tmp / "access.log"
    fh = open(log, "w")
    pr = subprocess.Popen([sys.executable, "-u", str(script)], cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    req = urllib.request.Request(f"{url}/api/layout/uebersicht", method="PUT", data=json.dumps(LAYOUT).encode(), headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()
    yield {"url": url, "log": log}
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)
    fh.close()


def hits(app, pat=r"/pic/\d+\?[^ \"]*"):
    return re.findall(r'"GET (' + pat + r') HTTP', app["log"].read_text(errors="replace"))


@pytest.fixture(scope="module")
def pw():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


def _ctx(pw, width=1280, scheme="light", lang="de", sw="allow"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale="de-DE", viewport={"width": width, "height": 900 if width > 500 else 844}, color_scheme=scheme, device_scale_factor=1, reduced_motion="reduce",
                        service_workers=sw)
    ctx.add_init_script("try { localStorage.setItem('lang', %r); %s } catch (e) {}" % (lang, "localStorage.setItem('viewmode', 'mobile');" if width < 500 else ""))
    ctx.browser_ = b
    return ctx


def _page(ctx):
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    return pg


DASH_IMGS = "main.home img"


def _dash_ready(pg, scroll=True):
    """Übersicht steht; alle Bausteine gezeichnet; alle Bilder (auch die außerhalb des Sichtbereichs, nach Scrollen bis zum Ende) geladen."""
    pg.wait_for_selector("main.home #hlast .hli h1", timeout=T)
    pg.wait_for_selector("main.home .erf img, main.home .erg img", timeout=T)
    pg.wait_for_selector("main.home .slrd", timeout=T)
    quiet(pg, 4000, 400)
    if scroll:
        for _ in range(12):
            pg.mouse.wheel(0, 700)
            quiet(pg, 800, 150)
    try:
        pg.wait_for_function("() => [...document.querySelectorAll('main.home img')].filter(i => { const r = i.getBoundingClientRect(); return i.getClientRects().length && (i.loading !== 'lazy' || (r.top < innerHeight * 2 && r.left < innerWidth && r.right > 0)); }).every(i => i.complete)", timeout=T)
    except Exception:
        print(pg.evaluate("() => [...document.querySelectorAll('main.home img')].filter(i => !i.complete).map(i => [i.getAttribute('src'), i.loading, i.getBoundingClientRect().top, i.className])"))
        raise
    quiet(pg, 3000, 400)


def _shots(pg, name):
    d = os.environ.get("MT_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(Path(d) / name), full_page=True)


def _prime_best(app):
    """„Beste Fotos“ rechnet fehlende Bewertung/Schärfe beim Aufruf nach (begrenzt) und wechselt dann die Auswahl; erst messen, wenn die Auswahl feststeht."""
    last = None
    for _ in range(30):
        with urllib.request.urlopen(app["url"] + "/api/photos?best=true&limit=6", timeout=30) as r:
            ids = [p["id"] for p in json.loads(r.read())]
        if ids == last:
            return
        last = ids


VPIC = r"/pic/\d+\?size=\d+&v=[0-9a-f]{12}"


def test_messung_erneut_keine_bildanfrage(pw, app):
    _prime_best(app)
    ctx = _ctx(pw)
    pg = _page(ctx)
    n0 = len(hits(app))
    pg.goto(app["url"] + "/#/dash")
    _dash_ready(pg)
    first = hits(app)[n0:]
    srcs = pg.eval_on_selector_all(DASH_IMGS, "l => l.map(i => i.getAttribute('src')).filter(Boolean)")
    assert len(srcs) >= 25 and all(re.fullmatch(VPIC, x) for x in srcs), srcs                     # jede Bildadresse der Übersicht mit Version
    assert first and all(re.fullmatch(VPIC, h) for h in first), first
    sizes = {int(re.search(r"size=(\d+)", h).group(1)) for h in first}
    assert sizes <= {300, 400, 500, 1200}, sizes                                                   # nur vorab erzeugte Größen (1200: Kopfbild, photos.warm_home)
    lazy = pg.eval_on_selector_all("main.home img:not(.hlp)", "l => l.every(i => i.loading === 'lazy' && i.decoding === 'async')")
    assert lazy
    pg.evaluate("() => { location.hash = '#/tours'; }")
    pg.wait_for_selector("#tl a.tr", timeout=T)
    quiet(pg, 2000)
    n2 = len(hits(app))
    pg.evaluate("() => { location.hash = '#/dash'; }")
    _dash_ready(pg)
    again = hits(app)[n2:]
    assert pg.eval_on_selector_all(DASH_IMGS, "l => l.map(i => i.getAttribute('src')).filter(Boolean)") == srcs      # dieselben Bilder (auch die Zufallsauswahl)
    n3 = len(hits(app))
    pg.reload()
    _dash_ready(pg)
    reload_ = hits(app)[n3:]
    print(f"\n[Messung 3.54.0] Übersicht, {N} Touren (Kopfbereich, Zuletzt unterwegs, An diesem Tag, Erinnerungen zufällig + beste, Zuletzt aufgenommene Fotos, Wiederentdecken): "
          f"erstes Öffnen {len(first)} Bildanfragen ({len(srcs)} Bilder), erneut {len(again)}, neu geladen {len(reload_)}")
    assert again == [] and reload_ == [], (again, reload_)
    assert not pg.errors, pg.errors
    ctx.browser_.close()


def test_neu_mischen_und_andere_tour(pw, app):
    """„Neu mischen“ zieht neue Zufallsfotos (und merkt sie), „Andere Tour“ würfelt neu; danach bleibt die neue Auswahl beim erneuten Öffnen."""
    req = urllib.request.Request(f"{app['url']}/api/layout/uebersicht", method="PUT", headers={"Content-Type": "application/json"},
                                 data=json.dumps({**LAYOUT, "cfg": {"erinn": {"shuffle": True}}}).encode())
    urllib.request.urlopen(req, timeout=10).read()
    try:
        ctx = _ctx(pw)
        pg = _page(ctx)
        pg.goto(app["url"] + "/#/dash")
        _dash_ready(pg, scroll=False)
        ids = lambda: pg.eval_on_selector_all("#hmemsec .erf img", "l => l.map(i => i.getAttribute('src'))")
        a = ids()
        assert len(a) == 6
        pg.click("#hmemsec .ernew")
        pg.wait_for_function("(a) => { const l = [...document.querySelectorAll('#hmemsec .erf img')].map(i => i.getAttribute('src')); return l.length === 6 && l.join() !== a.join(); }", arg=a, timeout=T)
        b = ids()
        w0 = pg.inner_text("main.home .slrdn")
        for _ in range(8):
            pg.click("main.home .slrd [data-other]")
            pg.wait_for_function("(w) => document.querySelector('main.home .slrdn') && document.querySelector('main.home .slrdn').textContent !== w", arg=w0, timeout=T)
            if pg.locator("main.home .slrd img").count():
                break
            w0 = pg.inner_text("main.home .slrdn")
        w1 = pg.inner_text("main.home .slrdn")
        pg.evaluate("() => { location.hash = '#/tours'; }")
        pg.wait_for_selector("#tl a.tr", timeout=T)
        pg.evaluate("() => { location.hash = '#/dash'; }")
        _dash_ready(pg, scroll=False)
        assert ids() == b and pg.inner_text("main.home .slrdn") == w1
        src = pg.get_attribute("main.home .slrd img", "src")
        assert re.fullmatch(r"/pic/\d+\?size=300&v=[0-9a-f]{12}", src), src                  # Titelfoto der Tour wie in der Tourenliste
        assert pg.evaluate("() => { const r = document.querySelector('main.home .slrd img').getBoundingClientRect(); return [r.width, r.height]; }") == [112, 112]
        assert not pg.errors, pg.errors
        ctx.browser_.close()
    finally:
        req = urllib.request.Request(f"{app['url']}/api/layout/uebersicht", method="PUT", data=json.dumps(LAYOUT).encode(), headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10).read()


def test_platzhalter_ohne_layoutsprung(pw, app):
    """Solange die Bilder unterwegs sind, haben alle Kästchen ihre endgültige Größe und eine Platzhalterfarbe; danach steht alles, wo es war."""
    ctx = _ctx(pw, sw="block")
    pg = _page(ctx)
    held = []
    pg.route(re.compile(r".*/pic/\d+\?.*"), lambda r: held.append(r))
    pg.goto(app["url"] + "/#/dash")
    pg.wait_for_selector("main.home .erf img", timeout=T)
    pg.wait_for_selector("main.home .slrd img", timeout=T)
    pg.wait_for_selector("main.home .hlt img", timeout=T)
    settled(pg)
    box = "() => [...document.querySelectorAll('main.home .hlm, main.home .hlt img, main.home .hcm, main.home .erf img, main.home .slfotos img, main.home .slrd img, main.home .trp')].filter(e => e.getClientRects().length).map(e => { const r = e.getBoundingClientRect(); return [Math.round(r.left), Math.round(r.top + scrollY), Math.round(r.width), Math.round(r.height)]; })"
    before = pg.evaluate(box)
    assert len(before) > 25 and all(b[2] > 0 and b[3] > 0 for b in before), before
    bg = pg.evaluate("() => ['.erf img', '.slfotos img', '.slrd img', '.hlt img'].map(s => getComputedStyle(document.querySelector('main.home ' + s)).backgroundColor)")
    assert all(x not in ("rgba(0, 0, 0, 0)", "transparent") for x in bg), bg
    pg.unroute(re.compile(r".*/pic/\d+\?.*"))
    for r in held:
        try:
            r.continue_()
        except Exception:
            pass
    pg.evaluate("() => { document.querySelectorAll('main.home img[loading=lazy]').forEach(i => { i.loading = 'eager'; }); }")
    pg.wait_for_function("() => [...document.querySelectorAll('main.home img')].filter(i => i.getClientRects().length).every(i => i.complete)", timeout=T)
    settled(pg)
    assert pg.evaluate(box) == before
    assert not pg.errors, pg.errors
    ctx.browser_.close()


@pytest.mark.parametrize("width,scheme", [(390, "light"), (390, "dark"), (1280, "light"), (1280, "dark")])
def test_ansicht(pw, app, width, scheme):
    ctx = _ctx(pw, width, scheme)
    pg = _page(ctx)
    pg.goto(app["url"] + "/#/dash")
    _dash_ready(pg)
    pg.evaluate("() => { document.querySelectorAll('main.home img[loading=lazy]').forEach(i => { i.loading = 'eager'; }); window.scrollTo(0, 0); }")
    pg.wait_for_function("() => [...document.querySelectorAll('main.home img')].filter(i => i.getClientRects().length).every(i => i.complete && i.naturalWidth > 0)", timeout=T)
    settled(pg)
    assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    if width < 500:
        assert pg.evaluate("() => document.documentElement.classList.contains('mob')")
    _shots(pg, f"uebersicht-{width}-{scheme}.png")
    assert not pg.errors, pg.errors
    ctx.browser_.close()
