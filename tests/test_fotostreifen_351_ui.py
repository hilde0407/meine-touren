"""3.51.0 – Foto-Streifen der Tourseite (Browser, Chromium): sofort ein fester Streifen mit den besten 12 Fotos, das volle Raster erst auf Wunsch (seitenweise zu 60),
gemessen an den Bildanfragen, die beim Server ankommen (Zugriffsprotokoll): beim ersten Öffnen nur die Streifenbilder, beim erneuten Öffnen keine.
Vollbild, Auswahlmodus, Diashow-Knopf und Fotos auf der Karte bleiben; keine Layoutsprünge; 390 px hell/dunkel; vier Sprachen. Screenshots mit MT_SHOTS=<Ordner>."""
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
N = 84

SEED = r"""
import sys, os, time, math; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from PIL import Image
from app import db, config, routes, photos
db.init()
now = int(time.time())
def loop(n=200):
    return [(47.5 + 0.01 * math.sin(2 * math.pi * i / (n - 1)), 11.0 + 0.012 * (1 - math.cos(2 * math.pi * i / (n - 1))), 1200 + 260 * math.sin(i / 9), i * 60000) for i in range(n)]
def tour(tid, days, name, n):
    from datetime import datetime
    from app.gpxtools import TZ
    d = datetime.fromtimestamp(now - days * 86400, TZ)
    ts = int(d.replace(hour=9, minute=0, second=0, microsecond=0).timestamp())     # 3.52.0: Start 9 Uhr – die Fotos (bis 3 Std.) bleiben am selben Tag, unabhängig von der Uhrzeit des Testlaufs
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,'t','komoot')",
               (tid, name, "hike", ts, ts + 12000, 12000, 12000, 500, 500, 47.5, 11.0))
    routes.store(tid, loop())
    lib = config.LIB_DIR / tid
    lib.mkdir(parents=True, exist_ok=True)
    batch = []
    for i in range(n):
        p = lib / ("f%%03d.jpg" %% i)
        Image.new("RGB", (640, 427), ((i * 37) %% 255, (i * 91) %% 255, 140)).save(p, quality=70)
        batch.append((str(p), p.stat().st_mtime, p.stat().st_size, ts + 120 + i * 130, None, None))
    photos._store(batch)
tour("f1", 3, "Fotorunde am See", %(n)d)
tour("f2", 6, "Kurze Runde", 5)
photos.assign_all()
db.execute("UPDATE photos SET rating=0, sharp=10")
"""

LAUNCH = r"""
import sys, os; sys.path.insert(0, %(root)r)
import uvicorn
from app.main import app
uvicorn.run(app, host="127.0.0.1", port=%(port)d, log_level="info", access_log=True)
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("fs351")
    data = tmp / "data"
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1", MT_NO_WARM="1")
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data), "n": N}], capture_output=True, text=True, cwd=ROOT, env=env)
    assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / "launch.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    log = tmp / "access.log"
    fh = open(log, "w")
    pr = subprocess.Popen([sys.executable, "-u", str(script)], cwd=ROOT, env=dict(env, MT_NO_WARM="0"), stdout=fh, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    yield {"url": url, "log": log}
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)
    fh.close()


def pic_hits(app):
    """Bildanfragen, die beim Server angekommen sind (auch 304-Nachfragen zählen): [(id, size)]"""
    return [(int(m.group(1)), int(m.group(2))) for m in re.finditer(r'"GET /pic/(\d+)\?size=(\d+)[^ "]* HTTP', app["log"].read_text(errors="replace"))]


@pytest.fixture(scope="module")
def pw():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


def _ctx(pw, width=1280, scheme="light", lang="de"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale="de-DE", viewport={"width": width, "height": 900 if width > 500 else 844}, color_scheme=scheme, device_scale_factor=1, reduced_motion="reduce")
    ctx.add_init_script("try { localStorage.setItem('lang', %r); } catch (e) {}" % lang)
    ctx.browser_ = b
    return ctx


def _open(ctx, app, tid="f1"):
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.goto(app["url"] + "/#/tour/" + tid)
    pg.wait_for_selector("#tls-photos", timeout=T)
    expect(pg.locator("#phs img")).to_have_count(12 if tid == "f1" else 5, timeout=T)
    return pg


def _strip_loaded(pg):
    pg.locator("#phs").scroll_into_view_if_needed()
    try:
        pg.wait_for_function("() => [...document.querySelectorAll('#phs img')].every(i => i.complete && i.naturalWidth > 0)", timeout=T)
    except Exception:
        print(pg.evaluate("() => [...document.querySelectorAll('#phs img')].map(i => [i.complete, i.naturalWidth, Math.round(i.getBoundingClientRect().left), Math.round(i.getBoundingClientRect().top)])"))
        raise
    quiet(pg, 3000)


@pytest.mark.kern                     # Stichprobe im schnellen Kern (tests/README.md)
def test_streifen_erst_und_zweitaufruf(pw, app):
    """Messung: Bildanfragen des Fotoabschnitts beim ersten Öffnen ≤ 12 (vorher bis zu 84/400), beim erneuten Öffnen 0."""
    ctx = _ctx(pw)
    n0 = len(pic_hits(app))
    pg = _open(ctx, app)
    _strip_loaded(pg)
    first = pic_hits(app)[n0:]
    sec = [h for h in first if h[1] != 120]                             # 120 = Fotos auf der Karte (Perlenkette), eigene Zählung
    assert len(sec) <= 12 and {s for _, s in sec} == {300}, first        # nur die Streifenbilder (300 px), kein Raster
    assert pg.locator("#th .th").count() == 0 and pg.locator("#th").is_hidden()
    srcs = pg.eval_on_selector_all("#phs img", "l => l.map(i => i.getAttribute('src'))")
    assert all(re.search(r"size=300&v=[0-9a-f]{12}$", s) for s in srcs)
    assert pg.evaluate("() => document.querySelector('#ss').href.includes('slideshow.html?tour=f1')") and pg.locator("#ss").is_visible()
    assert pg.locator("#tm .pm").count() > 0                             # Fotos auf der Karte
    n1 = len(pic_hits(app))
    pg.close()
    pg = _open(ctx, app)                                                # erneut öffnen (neue Seite, gleicher Browser)
    _strip_loaded(pg)
    again = pic_hits(app)[n1:]
    assert again == [], again                                           # kein Bild fragt beim Server nach – auch die Kartenfotos nicht
    pg.reload()
    expect(pg.locator("#phs img")).to_have_count(12, timeout=T)
    _strip_loaded(pg)
    assert pic_hits(app)[n1:] == []
    print(f"\n[Messung 3.51.0] erstes Öffnen: {len(sec)} Bildanfragen Fotoabschnitt, {len(first) - len(sec)} Kartenfotos; erneut: {len(again)}")
    assert not pg.errors, pg.errors
    ctx.browser_.close()


def test_raster_seitenweise_und_bedienung(pw, app):
    ctx = _ctx(pw)
    pg = _open(ctx, app)
    _strip_loaded(pg)
    btn = pg.locator("#phall")
    expect(btn).to_have_text(f"Alle {N} Fotos")
    assert btn.get_attribute("aria-expanded") == "false"
    btn.click()
    expect(pg.locator("#th .th")).to_have_count(60, timeout=T)           # erster Block
    assert pg.locator("#phs").is_hidden() and btn.get_attribute("aria-expanded") == "true"
    expect(btn).to_have_text("Weniger zeigen")
    pg.locator("#phpg").scroll_into_view_if_needed()                    # Nachladen beim Herunterscrollen (oder „Mehr anzeigen“)
    expect(pg.locator("#th .th")).to_have_count(N, timeout=T)
    expect(pg.locator("#phpg")).to_be_hidden()
    assert pg.evaluate("() => [...document.querySelectorAll('#th img')].map(i => +i.dataset.i).join()") == ",".join(map(str, range(N)))
    # Vollbild aus dem Raster und aus dem Streifen, mit Blättern durch alle Fotos
    pg.locator("#th img[data-i='70']").scroll_into_view_if_needed()
    pg.locator("#th img[data-i='70']").click()
    expect(pg.locator("#lb")).to_have_class(re.compile(r"\bon\b"))
    expect(pg.locator("#lbc")).to_contain_text(f"71/{N}")
    assert re.search(r"size=2000&v=[0-9a-f]{12}$", pg.get_attribute("#lbi", "src"))
    pg.keyboard.press("Escape")
    btn.click()
    expect(pg.locator("#phs")).to_be_visible()
    first = pg.locator("#phs img").first
    i0 = int(first.get_attribute("data-i"))
    first.click()
    expect(pg.locator("#lbc")).to_contain_text(f"{i0 + 1}/{N}")
    pg.keyboard.press("ArrowRight")
    expect(pg.locator("#lbc")).to_contain_text(f"{i0 + 2}/{N}")
    pg.keyboard.press("Escape")
    # Auswahlmodus öffnet das Raster; Auswahl gilt auch für nachgeladene Fotos
    pg.click("button:has-text('Fotos bearbeiten')")
    expect(pg.locator("#th")).to_be_visible()
    expect(pg.locator(".seltb")).to_be_visible()
    pg.locator("#th img[data-i='0']").click(force=True)                # erstes Foto: dieses und alle späteren des Tages
    expect(pg.locator(".seltb b")).to_have_text(str(N))
    pg.click("[data-a=off]")
    expect(pg.locator(".seltb")).to_be_hidden()
    assert not pg.errors, pg.errors
    ctx.browser_.close()


def test_wenige_fotos_ohne_raster_knopf(pw, app):
    ctx = _ctx(pw)
    pg = _open(ctx, app, "f2")
    expect(pg.locator("#phm")).to_be_hidden()
    expect(pg.locator("#pc")).to_have_text("5 Fotos")
    pg.click("button:has-text('Fotos bearbeiten')")                      # Auswahl: Raster mit allen 5
    expect(pg.locator(".thumbs img[data-i]")).to_have_count(5, timeout=T)
    pg.click("[data-a=off]")
    assert not pg.errors, pg.errors
    ctx.browser_.close()


def test_beste_fotos_knopf_bleibt(pw, app):
    ctx = _ctx(pw)
    pg = _open(ctx, app)
    pg.click("#pbest")
    expect(pg.locator("#pc")).to_contain_text("beste von", timeout=T)
    expect(pg.locator("#th .th")).to_have_count(10)
    assert pg.locator("#phs").is_hidden() and pg.locator("#phm").is_hidden()
    assert pg.locator("#ss").get_attribute("href").endswith("best=10")
    assert not pg.errors, pg.errors
    ctx.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_mobil_ohne_layoutsprung(pw, app, scheme):
    ctx = _ctx(pw, 390, scheme)
    ctx.add_init_script("""window.__cls = 0; try { new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput && e.sources && e.sources.some(s => s.node && s.node.closest && s.node.closest('#tls-photos'))) window.__cls += e.value; }).observe({type: 'layout-shift', buffered: true}); } catch (e) {}""")
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.goto(app["url"] + "/#/tour/f1")
    pg.wait_for_selector("#phs", timeout=T)
    h0 = pg.evaluate("() => document.querySelector('#phs').getBoundingClientRect().height")       # Gerüst vor der Fotoliste
    expect(pg.locator("#phs img")).to_have_count(12, timeout=T)
    _strip_loaded(pg)
    settled(pg)
    assert pg.evaluate("() => document.documentElement.classList.contains('mob')")
    h1 = pg.evaluate("() => document.querySelector('#phs').getBoundingClientRect().height")
    assert h0 == h1 == 110, (h0, h1)
    boxes = pg.evaluate("() => [...document.querySelectorAll('#phs img')].map(i => [i.getBoundingClientRect().width, i.getBoundingClientRect().height])")
    assert all(b == [96, 96] for b in boxes), boxes
    assert pg.evaluate("() => window.__cls") < 0.01
    assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")       # Streifen scrollt in sich, nicht die Seite
    assert pg.evaluate("() => { const s = document.querySelector('#phs'); return s.scrollWidth > s.clientWidth && getComputedStyle(s).scrollSnapType.startsWith('x'); }")
    bg = pg.evaluate("() => getComputedStyle(document.querySelector('#phs .phi')).backgroundColor")
    assert bg not in ("rgba(0, 0, 0, 0)", "transparent")                 # Platzhalterfarbe
    d = os.environ.get("MT_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        pg.locator("#tls-photos").screenshot(path=str(Path(d) / f"tour-fotostreifen-390-{scheme}.png"))
    pg.click("#phall")
    expect(pg.locator("#th .th")).to_have_count(60, timeout=T)
    pg.locator("#tls-photos").scroll_into_view_if_needed()
    settled(pg)
    assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    if d:
        pg.screenshot(path=str(Path(d) / f"tour-fotoraster-390-{scheme}.png"))
    # einklappbar wie bisher
    pg.locator("#tls-photos > summary").click()
    expect(pg.locator("#tls-photos")).not_to_have_attribute("open", "")
    assert not pg.errors, pg.errors
    ctx.browser_.close()


@pytest.mark.parametrize("lang,alle,weniger", [("en", f"All {N} photos", "Show less"), ("fr", f"Les {N} photos", "Afficher moins"), ("es", f"Las {N} fotos", "Mostrar menos")])
def test_sprachen(pw, app, lang, alle, weniger):
    ctx = _ctx(pw, lang=lang)
    pg = _open(ctx, app)
    expect(pg.locator("#phall")).to_have_text(alle, timeout=T)
    pg.click("#phall")
    expect(pg.locator("#phall")).to_have_text(weniger, timeout=T)
    assert not pg.errors, pg.errors
    ctx.browser_.close()
