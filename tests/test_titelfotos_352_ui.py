"""3.52.0 – Titelfoto je Tour in der Tourenliste (Browser, Chromium), gemessen am Zugriffsprotokoll des Servers: 150+ Touren, die meisten mit Fotos.
Erstes Öffnen: Bildanfragen durch den Sichtbereich begrenzt (nicht proportional zur Zahl der Touren), ein einziger Aufruf für alle Titelfotos;
erneutes Öffnen und Neuladen: keine Bildanfrage. Feste Kacheln (kein Layoutsprung, Platzhalter bis das Bild da ist), Strecke ohne Fotos oder wenn das Bild
fehlt, Schalter je Gerät, 390 px hell/dunkel, vier Sprachen, Suche. Screenshots mit MT_SHOTS=<Ordner>."""
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest

expect = pytest.importorskip("playwright.sync_api").expect

from tests.helpers_ui import T, quiet, settled  # noqa: E402
from tests.test_tourseite_ui import _wait  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
N = 160

SEED = r"""
import sys, os, time, math, shutil, random; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from PIL import Image, ImageDraw
from app import db, config, routes, photos
db.init()
now = int(time.time()); rnd = random.Random(5)
base = config.DATA_DIR / "motive"; base.mkdir(parents=True, exist_ok=True)
for i in range(12):                                   # einfache Landschaftsmotive (Himmel, Berge) – Testbilder in Kameragröße wären unnötig langsam
    w, h = 960, 640; im = Image.new("RGB", (w, h), (90 + i * 10, 150, 220)); d = ImageDraw.Draw(im)
    d.polygon([(0, h), (0, h * .55), (w * .3, h * (.25 + i * .02)), (w * .55, h * .5), (w * .8, h * .3), (w, h * .5), (w, h)], fill=(40, 90 + i * 8, 60))
    d.rectangle([0, h * .8, w, h], fill=(70, 140, 70)); im.save(base / ("m%%02d.jpg" %% i), quality=80)
SP = ["hike", "hike", "touringbicycle", "mtb", "jogging", "skitour"]
batch = []
for k in range(%(n)d):
    tid = "t%%04d" %% k; ts = now - (k * 2 + 1) * 86400
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,'t','komoot')",
               (tid, "Runde Nummer %%d am See" %% k, SP[k %% 6], ts, ts + 9000, 9000 + k * 10, 9000, 300 + k, 300, 47.5, 11.0))
    routes.store(tid, [(47.5 + 0.01 * math.sin(2 * math.pi * i / 59 + k), 11.0 + 0.012 * (1 - math.cos(2 * math.pi * i / 59)), 900, i * 60000) for i in range(60)])
    if k %% 5 == 3:                                   # jede fünfte Tour ohne Fotos (Mischung Foto/Strecke)
        continue
    lib = config.LIB_DIR / tid; lib.mkdir(parents=True, exist_ok=True)
    for j in range(3 + k %% 5):
        p = lib / ("f%%02d.jpg" %% j); shutil.copyfile(base / ("m%%02d.jpg" %% ((k + j) %% 12)), p)
        batch.append((str(p), p.stat().st_mtime, p.stat().st_size, ts + 300 + j * 900, None, None))
photos._store(batch)
photos.assign_all()
"""

LAUNCH = r"""
import sys, os; sys.path.insert(0, %(root)r)
import uvicorn
from app.main import app
uvicorn.run(app, host="127.0.0.1", port=%(port)d, log_level="info", access_log=True)
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("tf352")
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
    yield {"url": url, "log": log}
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)
    fh.close()


def hits(app, pat=r"/pic/(\d+)\?size=(\d+)[^ \"]*"):
    return re.findall(r'"GET ' + pat + r' HTTP', app["log"].read_text(errors="replace"))


VPIC = r"/pic/(\d+)\?size=(\d+)&v=[0-9a-f]+"        # Bilder mit Version (die Liste); die Übersicht lädt daneben eigene Bilder ohne Version


@pytest.fixture(scope="module")
def pw():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


def _ctx(pw, width=1280, scheme="light", lang="de", sw="allow"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale="de-DE", viewport={"width": width, "height": 900 if width > 500 else 844}, color_scheme=scheme, device_scale_factor=1, reduced_motion="reduce",
                        service_workers=sw)          # „block“, wo Antworten abgefangen werden (sonst holt der Service Worker an page.route vorbei)
    ctx.add_init_script("try { localStorage.setItem('lang', %r); %s } catch (e) {}" % (lang, "localStorage.setItem('viewmode', 'mobile');" if width < 500 else ""))
    ctx.browser_ = b
    return ctx


def _page(ctx):
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    return pg


def _list_ready(pg):
    """Liste steht, alle Bilder im Sichtbereich sind geladen."""
    pg.wait_for_selector("#tl a.tr", timeout=T)
    pg.wait_for_function("() => !document.querySelector('.trp[data-cv]') && [...document.querySelectorAll('#tl img.trimg')].filter(i => i.getBoundingClientRect().top < innerHeight).every(i => i.complete && i.naturalWidth > 0)", timeout=T)
    quiet(pg, 3000)


def _shots(pg, name):
    d = os.environ.get("MT_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(Path(d) / name))


def test_bildanfragen_begrenzt_und_beim_zweiten_mal_keine(pw, app):
    ctx = _ctx(pw)
    pg = _page(ctx)
    n0, c0 = len(hits(app, VPIC)), len(hits(app, r"/api/tour-covers"))
    pg.goto(app["url"] + "/#/dash")
    pg.wait_for_function("() => { try { return TOURS.length > 0 && COVERS !== null } catch (e) { return false } }", timeout=T)
    quiet(pg, 3000)
    n1 = len(hits(app, VPIC))
    pg.evaluate("() => { window.__t0 = performance.now(); location.hash = '#/tours'; }")
    pg.wait_for_selector("#tl a.tr", timeout=T)
    build = pg.evaluate("() => performance.now() - window.__t0")
    _list_ready(pg)
    first = hits(app, VPIC)[n1:]
    rows = pg.locator("#tl a.tr").count()
    with_photo = pg.locator("#tl a.tr .trimg").count()
    assert rows == 80 and with_photo == 64                                   # 80 Zeilen, 4 von 5 mit Foto
    assert 0 < len(first) <= 40, first                                       # durch den Sichtbereich begrenzt, nicht 64 (oder 128 bei allen Touren)
    assert {s for _, s in first} == {"300"}                                   # eine Größe (die des Foto-Streifens)
    assert len(hits(app, r"/api/tour-covers")) - c0 == 1                      # ein Aufruf für alle Titelfotos (beim Start, parallel zur Tourenliste)
    srcs = pg.eval_on_selector_all("#tl img.trimg", "l => l.map(i => i.getAttribute('src'))")
    assert all(re.fullmatch(r"/pic/\d+\?size=300&v=[0-9a-f]{12}", s) for s in srcs)
    assert pg.eval_on_selector_all("#tl img.trimg", "l => l.every(i => i.loading === 'lazy' && i.decoding === 'async')")
    pg.mouse.wheel(0, 3000)                                                   # beim Scrollen kommt nach, was in die Nähe des Sichtbereichs rückt
    _list_ready(pg)
    scrolled = hits(app, VPIC)[n1:]
    assert len(first) < len(scrolled) <= 64
    n2 = len(hits(app, VPIC))
    pg.evaluate("() => { location.hash = '#/dash'; }")
    pg.wait_for_function("() => location.hash === '#/dash'")
    quiet(pg, 2000)
    pg.evaluate("() => { location.hash = '#/tours'; }")
    _list_ready(pg)
    assert [h for h in hits(app, VPIC)[n2:] if h[1] == "300"] == []                   # erneut öffnen: keine Bildanfrage
    n3, c3 = len(hits(app, VPIC)), len(hits(app, r"/api/tour-covers"))
    pg.reload()
    _list_ready(pg)
    assert [h for h in hits(app, VPIC)[n3:] if h[1] == "300"] == []                   # neu laden: keine Bildanfrage
    assert len(hits(app, r"/api/tour-covers")) - c3 == 1
    print(f"\n[Messung 3.52.0] {N} Touren, Liste mit 80 Zeilen ({with_photo} mit Foto): erstes Öffnen {len(first)} Bildanfragen, nach Scrollen {len(scrolled)}, "
          f"erneut 0, neu geladen 0; Aufbau der Liste {build:.0f} ms")
    assert not pg.errors, pg.errors
    ctx.browser_.close()


def test_platzhalter_ohne_layoutsprung(pw, app):
    """Kommt die Antwort mit den Titelfotos erst nach dem Zeichnen, stehen Platzhalter fester Größe; danach bleiben alle Zeilen, wo sie waren."""
    ctx = _ctx(pw, sw="block")
    ctx.add_init_script("""window.__cls = 0; try { new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__cls += e.value; }).observe({type: 'layout-shift', buffered: true}); } catch (e) {}""")
    pg = _page(ctx)
    held = []
    pg.route("**/api/tour-covers", lambda r: held.append(r))
    pg.goto(app["url"] + "/#/tours")
    pg.wait_for_selector("#tl a.tr", timeout=T)
    expect(pg.locator("#tl .trp[data-cv]").first).to_be_attached(timeout=T)
    settled(pg)
    pg.wait_for_function("() => document.querySelectorAll('#tl .trp[data-cv]').length > 10", timeout=T)
    before = pg.evaluate("() => [...document.querySelectorAll('#tl a.tr')].slice(0, 12).map(a => { const r = a.getBoundingClientRect(), p = a.querySelector('.trp').getBoundingClientRect(); return [r.top, r.height, p.width, p.height]; })")
    bg = pg.evaluate("() => getComputedStyle(document.querySelector('#tl .trp[data-cv]')).backgroundColor")
    assert bg not in ("rgba(0, 0, 0, 0)", "transparent")
    assert held, "Titelfotos wurden nicht angefragt"
    cls0 = pg.evaluate("() => window.__cls")
    for r in held:
        r.continue_()
    _list_ready(pg)
    after = pg.evaluate("() => [...document.querySelectorAll('#tl a.tr')].slice(0, 12).map(a => { const r = a.getBoundingClientRect(), p = a.querySelector('.trp').getBoundingClientRect(); return [r.top, r.height, p.width, p.height]; })")
    assert before == after and all(b[2:] == [120, 80] for b in after), (before, after)
    assert pg.evaluate("() => window.__cls") - cls0 < 0.01
    assert pg.locator("#tl img.trimg").count() == 64 and pg.locator("#tl .trp.trr svg.mini").count() == 16
    assert not pg.errors, pg.errors
    ctx.browser_.close()


def test_bild_fehlt_strecke_statt_bruchbild(pw, app):
    ctx = _ctx(pw, sw="block")
    pg = _page(ctx)
    pg.route(re.compile(r".*/pic/\d+\?size=300&v=.*"), lambda r: r.fulfill(status=404, body="weg"))
    pg.goto(app["url"] + "/#/tours")
    pg.wait_for_selector("#tl a.tr", timeout=T)
    pg.wait_for_function("() => document.querySelectorAll('#tl .trp.trr svg.mini').length > 16", timeout=T)    # die sichtbaren Bilder fehlen: Strecke in derselben Kachel
    box = pg.evaluate("() => { const p = document.querySelector('#tl .trp.trr').getBoundingClientRect(); return [p.width, p.height]; }")
    assert box == [120, 80]
    assert not pg.errors, pg.errors
    ctx.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_mobil_390(pw, app, scheme):
    ctx = _ctx(pw, 390, scheme)
    pg = _page(ctx)
    pg.goto(app["url"] + "/#/tours")
    _list_ready(pg)
    settled(pg)
    assert pg.evaluate("() => document.documentElement.classList.contains('mob')")
    assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    r = pg.evaluate("""() => [...document.querySelectorAll('#tl a.tr')].slice(0, 10).map(a => {
        const b = a.getBoundingClientRect(), p = a.querySelector('.trp').getBoundingClientRect(), nm = a.querySelector('.nm').getBoundingClientRect(), n = a.querySelector('.n').getBoundingClientRect();
        return {w: p.width, h: p.height, inRow: p.left >= b.left && p.right <= nm.left && nm.right <= b.right + 0.5 && n.right <= b.right + 0.5, rowH: b.height, img: !!a.querySelector('img.trimg')}; })""")
    assert all(x["w"] == 88 and x["h"] == 88 and x["inRow"] for x in r), r
    assert all(x["rowH"] < 150 for x in r), r                                           # dicht genug: höchstens etwa 6 Touren je Bildschirm
    assert any(x["img"] for x in r) and not all(x["img"] for x in r)                    # Mischung Foto/Strecke
    ink = pg.evaluate("() => [getComputedStyle(document.querySelector('#tl .nm')).color, getComputedStyle(document.body).backgroundColor]")
    assert ink[0] != ink[1]
    _shots(pg, f"tourenliste-fotos-390-{scheme}.png")
    pg.mouse.wheel(0, 1800)
    _list_ready(pg)
    _shots(pg, f"tourenliste-fotos-390-{scheme}-weiter.png")
    assert not pg.errors, pg.errors
    ctx.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_desktop_screenshot(pw, app, scheme):
    ctx = _ctx(pw, 1280, scheme)
    pg = _page(ctx)
    pg.goto(app["url"] + "/#/tours")
    _list_ready(pg)
    settled(pg)
    assert pg.evaluate("() => getComputedStyle(document.querySelector('#tl a.tr.trf')).gridTemplateColumns.startsWith('120px')")
    _shots(pg, f"tourenliste-fotos-1280-{scheme}.png")
    assert not pg.errors, pg.errors
    ctx.browser_.close()


def test_schalter_je_geraet_und_suche(pw, app):
    ctx = _ctx(pw, 390)
    pg = _page(ctx)
    pg.goto(app["url"] + "/#/tours")
    _list_ready(pg)
    pg.click("#tmore")
    chk = pg.locator(".uimod input[data-tlf]")
    expect(chk).to_be_checked()
    expect(pg.locator(".uimod .tlfchk")).to_contain_text("Fotos in der Tourenliste")
    chk.uncheck()
    pg.keyboard.press("Escape")
    pg.wait_for_function("() => localStorage.getItem('mt_tlfotos') === '0'")
    quiet(pg, 2000)
    c0 = len(hits(app, r"/api/tour-covers"))
    pg.reload()                                                                               # direkt auf der Liste (die Startseite holt ihre Karten-Fotos auch bei „aus“)
    pg.wait_for_selector("#tl a.tr", timeout=T)
    quiet(pg, 2000)
    assert pg.locator("#tl .trp").count() == 0 and pg.locator("#tl a.tr.trf").count() == 0      # aus: wie bisher (Strecke), keine Titelfotos geladen
    assert pg.locator("#tl a.tr svg.mini").count() == 80
    assert len(hits(app, r"/api/tour-covers")) == c0
    pg.click("#tmore")
    pg.locator(".uimod input[data-tlf]").check()
    pg.wait_for_function("() => localStorage.getItem('mt_tlfotos') === '1' && COVERS && Object.keys(COVERS).length > 0", timeout=T)   # wieder an: Titelfotos geladen
    pg.keyboard.press("Escape")
    pg.evaluate("() => { location.hash = '#/dash'; }")
    quiet(pg, 1500)
    pg.evaluate("() => { location.hash = '#/search?q=Nummer 1'; }")                          # Suche benutzt dieselbe Zeile
    pg.wait_for_selector("main a.tr", timeout=T)
    pg.wait_for_function("() => document.querySelectorAll('main a.tr.trf .trimg').length > 0", timeout=T)
    assert not pg.errors, pg.errors
    ctx.browser_.close()


@pytest.mark.parametrize("lang,label", [("en", "Photos in the tour list"), ("fr", "Photos dans la liste des parcours"), ("es", "Fotos en la lista de rutas")])
def test_sprachen(pw, app, lang, label):
    ctx = _ctx(pw, 390, lang=lang)
    pg = _page(ctx)
    pg.goto(app["url"] + "/#/tours")
    _list_ready(pg)
    pg.click("#tmore")
    expect(pg.locator(".uimod .tlfchk")).to_contain_text(label)
    assert not pg.errors, pg.errors
    ctx.browser_.close()
