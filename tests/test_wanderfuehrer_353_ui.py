"""3.53.0 – Wanderführer übersichtlich (Browser, Chromium): 5 Bücher × 80 Touren (synthetisch), Fantasie-Titelbilder (Pillow, keine Verlagscover).
Eingeklappte Karten mit Ring (Werte), Titelbild oder Platzhalter, Liste erst beim Aufklappen und in Blöcken zu 60, Zustand je Buch gemerkt, Filter
Alle/Offen/Gewandert (Adresse), Suche über Bücher und Touren, Reihenfolge, Titelbild wählen/entfernen, Karte der offenen Touren nur auf Wunsch,
390 px hell/dunkel, Desktop, Englisch/Französisch/Spanisch. Screenshots mit MT_SHOTS=<Ordner>."""
import os
import re
import socket
import subprocess
import sys
from pathlib import Path

import pytest

expect = pytest.importorskip("playwright.sync_api").expect

from tests.helpers_ui import T, eager_images, quiet, settled  # noqa: E402
from tests.test_tourseite_ui import _wait  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

SEED = r"""
import sys, os, time, json, io; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from PIL import Image, ImageDraw
from app import db, routes, wanderfuehrer
db.init()
now = int(time.time())
ORTE = ["Moosbach", "Felsheim", "Eulenkopf", "Birkental", "Hirschgrund", "Wolkenstein", "Kieselberg", "Lindenau", "Tannhorn", "Sonnhalde"]
BOOKS = [("Rother Fantasiegebirge Nord", 30, (34, 92, 140)), ("Rother Zauberwald", 12, (40, 110, 70)), ("Rother Insel Nirgendwo", 0, None),
         ("Rother Hochland Süd", 5, (150, 70, 40)), ("Rother Seenplatte Ost", 2, None)]
k = 0
for b, (book, done, col) in enumerate(BOOKS):
    lat0 = 45.0; lon0 = 8.0 + 1.5 * b
    for i in range(80):
        name = "%%d Rundweg bei %%s" %% (i + 1, ORTE[(i + b) %% 10])
        if b == 2 and i == 6:
            name = "7 Uferweg am Zwergensee"
        pts = [[round(lat0 + i * 0.04 + j * 0.0005, 5), round(lon0 + j * 0.0004, 5)] for j in range(60)]
        db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES(?,?,?,?,?)", (book, name, json.dumps(pts), round(4 + (i * 7) %% 15 + 0.3 * b, 1), 150 + (i * 37) %% 900))
        if i < done:
            tid = "m%%03d" %% k; ts = now - (k + 1) * 86400; k += 1
            db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,'t','komoot')",
                       (tid, "Meine Tour %%d" %% k, "hike", ts, ts + 9000, 9000, 9000, 300, 300, lat0, lon0))
            routes.store(tid, [(lat0 + i * 0.04 + j * 0.0005, lon0 + j * 0.0004 + 0.0002, 500, j * 60000) for j in range(60)])
    if col:                                   # Fantasie-Titelbild: Farbfläche, Berge, Titelband (kein Verlagscover)
        w, h = 600, 860; im = Image.new("RGB", (w, h), col); d = ImageDraw.Draw(im)
        d.polygon([(0, h), (0, h * .62), (w * .35, h * .35), (w * .6, h * .55), (w * .85, h * .4), (w, h * .6), (w, h)], fill=(240, 240, 235))
        d.rectangle([0, 40, w, 170], fill=(242, 194, 48)); d.rectangle([40, 80, w - 40, 130], fill=(30, 30, 30))
        buf = io.BytesIO(); im.save(buf, "PNG")
        data = wanderfuehrer._cover_jpeg(buf.getvalue())
        import hashlib
        db.execute("INSERT INTO guide_cover(book,img,v,ts) VALUES(?,?,?,?)", (book, data, hashlib.sha1(data).hexdigest()[:12], now))
"""

LAUNCH = r"""
import sys, os; sys.path.insert(0, %(root)r)
import uvicorn
from app.main import app
uvicorn.run(app, host="127.0.0.1", port=%(port)d, log_level="info", access_log=True)
"""

B1, B2, B3, B4, B5 = "Rother Fantasiegebirge Nord", "Rother Zauberwald", "Rother Insel Nirgendwo", "Rother Hochland Süd", "Rother Seenplatte Ost"


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("wf353")
    data = tmp / "data"
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1", MT_NO_WARM="1")
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data)}], capture_output=True, text=True, cwd=ROOT, env=env)
    assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / "launch.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    log = tmp / "access.log"
    fh = open(log, "w")
    pr = subprocess.Popen([sys.executable, "-u", str(script)], cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    yield {"url": url, "log": log, "tmp": tmp}
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)
    fh.close()


@pytest.fixture(scope="module")
def pw():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


def _ctx(pw, width=1280, scheme="light", lang="de"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale="de-DE", viewport={"width": width, "height": 900 if width > 500 else 844}, color_scheme=scheme, device_scale_factor=1, reduced_motion="reduce",
                        service_workers="block")
    ctx.add_init_script("try { if (!sessionStorage.getItem('__init')) { sessionStorage.setItem('__init', '1'); Object.keys(localStorage).filter(k => k.startsWith('mt_gf_')).forEach(k => localStorage.removeItem(k)); } localStorage.setItem('lang', %r); %s } catch (e) {}"
                        % (lang, "localStorage.setItem('viewmode', 'mobile');" if width < 500 else ""))
    ctx.browser_ = b
    return ctx


def _page(ctx):
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    return pg


def _open(pg, app, hash_="#/places"):
    pg.goto(app["url"] + "/" + hash_)
    pg.wait_for_selector("#gfl details.gfb", timeout=T)
    quiet(pg, 3000)


def _card(pg, book):
    return pg.locator("details.gfb", has=pg.locator(".gfname", has_text=book))


def _shots(pg, name, el=None):
    d = os.environ.get("MT_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        eager_images(pg)
        settled(pg)
        if el is not None:
            el.evaluate("e => { e.scrollIntoView({block: 'start'}); window.scrollBy(0, -70); }")
            settled(pg)
        pg.screenshot(path=str(Path(d) / name))


@pytest.mark.kern                     # Stichprobe im schnellen Kern (tests/README.md)
def test_eingeklappt_ring_titelbild_und_aufbauzeit(pw, app):
    ctx = _ctx(pw)
    pg = _page(ctx)
    pg.goto(app["url"] + "/#/dash")
    pg.wait_for_function("() => { try { return TOURS.length > 0 } catch (e) { return false } }", timeout=T)
    quiet(pg, 2000)
    times = []
    for _ in range(5):
        pg.evaluate("() => { location.hash = '#/dash'; }")
        pg.wait_for_function("() => location.hash === '#/dash' && !document.querySelector('#gfl')")
        quiet(pg, 2000)
        pg.evaluate("() => { window.__t0 = performance.now(); location.hash = '#/places'; }")
        pg.wait_for_function("() => document.querySelectorAll('#gfl details.gfb').length === 5", timeout=T)
        times.append(pg.evaluate("() => performance.now() - window.__t0"))
    quiet(pg, 3000)
    cards = pg.locator("#gfl details.gfb")
    assert cards.count() == 5
    assert pg.evaluate("() => [...document.querySelectorAll('#gfl details.gfb')].every(d => !d.open)")             # Standard: eingeklappt
    assert pg.locator("#gfl .gfrows .r").count() == 0                                                             # Liste entsteht erst beim Aufklappen
    rows_dom = pg.evaluate("() => document.querySelectorAll('#gfl *').length")
    assert rows_dom < 400                                                                                         # nicht hunderte Zeilen im DOM
    c1 = _card(pg, B1)
    expect(c1.locator(".gfn")).to_have_text("30 von 80 gewandert")
    expect(c1.locator(".gfz")).to_have_text("offen: 50")
    assert c1.locator("circle.gfr1").get_attribute("stroke-dasharray") == "37.50 100"
    expect(c1.locator("svg.gfring text")).to_have_text("37 %")
    assert c1.locator("svg.gfring").get_attribute("aria-label") == "Anteil gewandert: 37 %"
    assert c1.locator("svg.gfring").get_attribute("role") == "img"
    c3 = _card(pg, B3)
    assert c3.locator("circle.gfr1").count() == 0 and c3.locator("svg.gfring text").text_content() == "0 %"
    expect(_card(pg, B2).locator("svg.gfring text")).to_have_text("15 %")
    assert pg.locator("#gfl .gfc img").count() == 3 and pg.locator("#gfl .gfc svg.gfico").count() == 2         # Titelbild oder Buch-Symbol
    srcs = pg.eval_on_selector_all("#gfl .gfc img", "l => l.map(i => i.getAttribute('src'))")
    assert all(re.fullmatch(r"/api/guides/cover\?book=[^&]+&v=[0-9a-f]{12}", s) for s in srcs)
    eager_images(pg)
    assert pg.evaluate("() => [...document.querySelectorAll('#gfl .gfc img')].every(i => i.naturalWidth > 0)")
    expect(pg.locator("#plb .sec", has_text="Wanderführer-Fortschritt").locator(".sub")).to_have_text("5 Bücher · 49 von 400 gewandert")
    times.sort()
    print(f"\n[Messung 3.53.0] Seite Orte & Ausrüstung mit 5 Büchern × 80 Touren: Karten stehen nach {times[2]:.0f} ms (Median aus 5, min {times[0]:.0f}, max {times[-1]:.0f}), "
          f"{rows_dom} Elemente im Wanderführer-Abschnitt")
    assert not pg.errors, pg.errors
    ctx.browser_.close()


def test_aufklappen_bloecke_und_gemerkt(pw, app):
    ctx = _ctx(pw)
    pg = _page(ctx)
    _open(pg, app)
    c1 = _card(pg, B1)
    c1.locator("summary").click()
    expect(c1.locator(".gfrows .r")).to_have_count(60, timeout=T)                                              # erster Block
    titles = c1.locator(".gfrows .r span[translate=no]").all_inner_texts()
    assert titles[:3] == ["1 Rundweg bei Moosbach", "2 Rundweg bei Felsheim", "3 Rundweg bei Eulenkopf"] and titles[9].startswith("10 ")   # Buchreihenfolge (2 vor 10)
    expect(c1.locator(".gfmore")).to_contain_text("60 von 80")
    assert c1.locator(".gfrows .r.done").count() == 30 and c1.locator(".gfrows .r.done a").first.get_attribute("href").startswith("#/tour/m")
    c1.locator(".gfmoreb").click()
    expect(c1.locator(".gfrows .r")).to_have_count(80, timeout=T)
    expect(c1.locator(".gfmore")).to_have_count(0)
    pg.wait_for_function("(k) => localStorage.getItem('mt_gf_o_' + k) === '1'", arg=B1)
    pg.reload()
    pg.wait_for_selector("#gfl details.gfb", timeout=T)
    expect(_card(pg, B1)).to_have_attribute("open", "")                                                        # gemerkt je Buch
    assert pg.evaluate("() => [...document.querySelectorAll('#gfl details.gfb')].filter(d => d.open).length") == 1
    _card(pg, B1).locator("summary").click()
    pg.wait_for_function("(k) => localStorage.getItem('mt_gf_o_' + k) === '0'", arg=B1)
    assert not pg.errors, pg.errors
    ctx.browser_.close()


def test_filter_offen_gewandert_und_adresse(pw, app):
    ctx = _ctx(pw)
    pg = _page(ctx)
    _open(pg, app)
    _card(pg, B1).locator("summary").click()
    pg.click("[data-gff=offen]")
    pg.wait_for_function("() => location.hash === '#/places?wf=offen'")
    c1 = _card(pg, B1)
    expect(c1.locator(".gfrows .r")).to_have_count(50, timeout=T)
    assert c1.locator(".gfrows .r.done").count() == 0
    expect(c1.locator(".gfz")).to_have_text("offen: 50")
    expect(pg.locator("[data-gff=offen]")).to_have_attribute("aria-pressed", "true")
    pg.click("[data-gff=gewandert]")
    pg.wait_for_function("() => location.hash === '#/places?wf=gewandert'")
    expect(c1.locator(".gfrows .r.done")).to_have_count(30, timeout=T)
    expect(c1.locator(".gfrows .r")).to_have_count(30)
    expect(c1.locator(".gfz")).to_have_text("gewandert: 30")
    expect(_card(pg, B3).locator(".gfz")).to_have_text("gewandert: 0")
    _card(pg, B3).locator("summary").click()
    expect(_card(pg, B3).locator(".gfbody")).to_contain_text("Aus diesem Buch ist noch keine Tour gewandert.")
    pg.select_option("#gfo", "zuletzt")
    pg.wait_for_function("() => location.hash === '#/places?wf=gewandert&wo=zuletzt'")
    dates = c1.locator(".gfrows .r a").all_inner_texts()
    assert dates[0] != dates[-1]
    pg.goto(app["url"] + "/#/places?wf=offen&wo=laenge")                                                       # Adresse stellt den Zustand her
    pg.reload()
    pg.wait_for_selector("#gfl details.gfb", timeout=T)
    expect(pg.locator("[data-gff=offen]")).to_have_class(re.compile(r"\bon\b"))
    assert pg.locator("#gfo").input_value() == "laenge"
    c1 = _card(pg, B1)
    if not c1.evaluate("d => d.open"):
        c1.locator("summary").click()
    expect(c1.locator(".gfrows .r")).to_have_count(50, timeout=T)
    km = [float(re.match(r"([\d,]+) km", t).group(1).replace(",", ".")) for t in c1.locator(".gfrows .r small").all_inner_texts()]
    assert km == sorted(km)                                                                                     # nach Länge
    pg.click("[data-gff='']")
    pg.select_option("#gfo", "")
    pg.wait_for_function("() => location.hash === '#/places'")
    assert not pg.errors, pg.errors
    ctx.browser_.close()


def test_suche_ueber_buecher_und_touren(pw, app):
    ctx = _ctx(pw)
    pg = _page(ctx)
    _open(pg, app)
    pg.fill("#gfq", "zwergensee")
    pg.wait_for_function("() => document.querySelectorAll('#gfl details.gfb').length === 1", timeout=T)
    c3 = _card(pg, B3)
    expect(c3).to_have_attribute("open", "")                                                                   # Treffer nur über eine Tour: klappt auf
    expect(c3.locator(".gfrows .r")).to_have_count(1)
    expect(c3.locator(".gfrows .r")).to_contain_text("7 Uferweg am Zwergensee")
    expect(c3.locator(".gfz")).to_have_text("1 Treffer")
    pg.wait_for_function("() => location.hash === '#/places?wq=zwergensee'")
    assert pg.evaluate("(k) => localStorage.getItem('mt_gf_o_' + k)", B3) is None                               # aufgeklappt von der Suche: nicht gemerkt
    pg.fill("#gfq", "Zauberwald")
    pg.wait_for_function("() => document.querySelectorAll('#gfl details.gfb').length === 1 && document.querySelector('#gfl .gfname').textContent === 'Rother Zauberwald'", timeout=T)
    assert not _card(pg, B2).evaluate("d => d.open")                                                           # Buchname passt: bleibt wie gemerkt
    expect(_card(pg, B2).locator(".gfz")).to_have_text("offen: 68")
    pg.fill("#gfq", "Moosbach")
    pg.wait_for_function("() => document.querySelectorAll('#gfl details.gfb[open]').length >= 4", timeout=T)
    n = _card(pg, B1).locator(".gfrows .r").count()
    assert n == 8 and _card(pg, B1).locator(".gfz").inner_text() == "8 Treffer"
    pg.fill("#gfq", "xyzxyz")
    expect(pg.locator("#gfl")).to_contain_text("Kein Buch und keine Tour passt zu „xyzxyz“.")
    pg.fill("#gfq", "")
    pg.wait_for_function("() => document.querySelectorAll('#gfl details.gfb').length === 5 && location.hash === '#/places'", timeout=T)
    assert not pg.errors, pg.errors
    ctx.browser_.close()


def test_titelbild_waehlen_und_entfernen(pw, app):
    from PIL import Image
    f = app["tmp"] / "fantasie.png"
    im = Image.new("RGB", (1200, 1700), (120, 60, 160))
    im.paste((250, 220, 90), (0, 100, 1200, 300))
    im.save(f)
    ctx = _ctx(pw)
    ctx.add_init_script("window.__fd = []; const a = FormData.prototype.append; FormData.prototype.append = function (k, v) { if (v instanceof Blob) window.__fd.push(v.size); return a.apply(this, arguments); };")
    pg = _page(ctx)
    _open(pg, app)
    c5 = _card(pg, B5)
    assert c5.locator(".gfc svg.gfico").count() == 1
    c5.locator("summary").click()
    expect(c5.locator(".gfcov")).to_be_visible()
    expect(c5.locator(".gfcovx")).to_have_count(0)
    with pg.expect_file_chooser() as fc:
        c5.locator(".gfcov").click()
    with pg.expect_request(lambda r: r.method == "POST" and "/api/guides/cover" in r.url) as rq:
        fc.value.set_files(str(f))
    sent = pg.evaluate("() => window.__fd")
    assert len(sent) == 1 and sent[0] < 80_000 and f.stat().st_size > sent[0]                                   # im Browser verkleinert
    expect(c5.locator(".gfc img")).to_have_count(1, timeout=T)
    src = c5.locator(".gfc img").get_attribute("src")
    assert re.search(r"&v=[0-9a-f]{12}$", src)
    pg.wait_for_function("() => { const i = document.querySelector('#gfl details.gfb[open] .gfc img'); return i && i.complete && i.naturalWidth > 0 && i.naturalWidth <= 480 && i.naturalHeight > i.naturalWidth; }", timeout=T)
    c5.locator(".gfcovx").click()
    pg.locator(".uidlg .uibox button", has_text="Entfernen").click()
    expect(c5.locator(".gfc svg.gfico")).to_have_count(1, timeout=T)
    expect(c5.locator(".gfcovx")).to_have_count(0)
    assert not pg.errors, pg.errors
    ctx.browser_.close()


def test_karte_der_offenen_touren_nur_auf_wunsch(pw, app):
    ctx = _ctx(pw)
    pg = _page(ctx)
    _open(pg, app)
    assert pg.locator("#gfl .leaflet-container").count() == 0
    c4 = _card(pg, B4)
    c4.locator("summary").click()
    assert pg.locator("#gfl .leaflet-container").count() == 0                                                 # Aufklappen baut keine Karte
    c4.locator(".gfmapb").click()
    expect(c4.locator(".gfmap.leaflet-container")).to_be_visible(timeout=T)
    expect(c4.locator(".gfmap path.leaflet-interactive")).to_have_count(75, timeout=T)                         # 80 − 5 gewanderte: Startpunkte
    assert c4.locator(".gfmapb").get_attribute("aria-expanded") == "true"
    c4.locator(".gfmapb").click()
    expect(c4.locator(".gfmap")).to_be_hidden()
    assert pg.locator("#gfl .leaflet-container").count() == 0
    assert not pg.errors, pg.errors
    ctx.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_mobil_390(pw, app, scheme):
    ctx = _ctx(pw, 390, scheme)
    pg = _page(ctx)
    _open(pg, app)
    assert pg.evaluate("() => document.documentElement.classList.contains('mob')")
    pg.locator("#plb .sec", has_text="Wanderführer-Fortschritt").scroll_into_view_if_needed()
    settled(pg)
    assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    m = pg.evaluate("""() => { const d = document.querySelector('#gfl details.gfb'), s = d.getBoundingClientRect(), c = d.querySelector('.gfc').getBoundingClientRect(),
        r = d.querySelector('.gfring').getBoundingClientRect(), main = document.querySelector('#gfl').getBoundingClientRect(),
        chips = [...document.querySelectorAll('[data-gff]')].map(x => x.getBoundingClientRect().height), q = document.querySelector('#gfq').getBoundingClientRect().height,
        o = document.querySelector('#gfo').getBoundingClientRect().height;
        return {sw: s.width, mw: main.width, sh: d.querySelector('summary').getBoundingClientRect().height, cw: c.width, ch: c.height, rw: r.width, chips, q, o,
          ink: getComputedStyle(d.querySelector('.gfn')).color, bg: getComputedStyle(d).backgroundColor, ringInk: getComputedStyle(d.querySelector('.gfrt')).fill, fs: parseFloat(getComputedStyle(d.querySelector('.gfn')).fontSize)}; }""")
    assert abs(m["sw"] - m["mw"]) < 2 and m["mw"] > 340                                                        # volle Breite
    assert 64 <= m["ch"] <= 72 and m["rw"] == 48 and m["sh"] >= 44
    assert min(m["chips"]) >= 44 and m["q"] >= 44 and m["o"] >= 44
    assert m["ink"] != m["bg"] and m["ringInk"] != m["bg"] and m["fs"] >= 14
    _shots(pg, f"wf-390-{scheme}-eingeklappt.png", pg.locator("#plb .sec", has_text="Wanderführer-Fortschritt"))
    c1 = _card(pg, B1)
    c1.locator("summary").click()
    expect(c1.locator(".gfrows .r")).to_have_count(60, timeout=T)
    hs = pg.evaluate("() => [...document.querySelectorAll('#gfl .gfrows .r')].slice(0, 10).map(r => r.getBoundingClientRect().height)")
    assert min(hs) >= 44
    assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
    _shots(pg, f"wf-390-{scheme}-aufgeklappt.png", c1)
    pg.click("[data-gff=offen]")
    expect(c1.locator(".gfrows .r")).to_have_count(50, timeout=T)
    _shots(pg, f"wf-390-{scheme}-offen.png", pg.locator(".gfbar"))
    pg.click("[data-gff='']")
    pg.fill("#gfq", "Zwergensee")
    pg.wait_for_function("() => document.querySelectorAll('#gfl details.gfb').length === 1", timeout=T)
    _shots(pg, f"wf-390-{scheme}-suche.png", pg.locator(".gfbar"))
    pg.fill("#gfq", "")
    pg.wait_for_function("() => document.querySelectorAll('#gfl details.gfb').length === 5", timeout=T)
    c1 = _card(pg, B1)
    if c1.evaluate("d => d.open"):
        c1.locator("summary").click()
    assert not pg.errors, pg.errors
    ctx.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_desktop(pw, app, scheme):
    ctx = _ctx(pw, 1280, scheme)
    pg = _page(ctx)
    _open(pg, app)
    m = pg.evaluate("() => { const d = document.querySelector('#gfl details.gfb'); return [d.querySelector('.gfc').getBoundingClientRect().height, d.querySelector('.gfring').getBoundingClientRect().width]; }")
    assert m == [72, 56]
    _shots(pg, f"wf-1280-{scheme}-eingeklappt.png", pg.locator("#plb .sec", has_text="Wanderführer-Fortschritt"))
    c2 = _card(pg, B2)
    c2.locator("summary").click()
    expect(c2.locator(".gfrows .r")).to_have_count(60, timeout=T)
    _shots(pg, f"wf-1280-{scheme}-aufgeklappt.png", c2)
    pg.click("[data-gff=offen]")
    pg.fill("#gfq", "Moosbach")
    pg.wait_for_function("() => document.querySelectorAll('#gfl details.gfb[open]').length >= 4", timeout=T)
    _shots(pg, f"wf-1280-{scheme}-offen-suche.png", pg.locator(".gfbar"))
    pg.fill("#gfq", "")
    pg.click("[data-gff='']")
    pg.wait_for_function("() => location.hash === '#/places'")
    c2 = _card(pg, B2)
    if c2.evaluate("d => d.open"):
        c2.locator("summary").click()
    assert not pg.errors, pg.errors
    ctx.browser_.close()


@pytest.mark.parametrize("lang,done,chips,search,ring", [
    ("en", "30 of 80 hiked", ["All", "Open", "Hiked"], "Search guide or tour", "37%"),
    ("fr", "30 sur 80 randonnés", ["Tous", "À faire", "Randonnés"], "Rechercher un guide ou un parcours", "37 %"),
    ("es", "30 de 80 recorridas", ["Todas", "Pendientes", "Recorridas"], "Buscar guía o ruta", "37 %"),
])
def test_sprachen(pw, app, lang, done, chips, search, ring):
    ctx = _ctx(pw, 390, lang=lang)
    pg = _page(ctx)
    _open(pg, app)
    c1 = _card(pg, B1)
    expect(c1.locator(".gfn")).to_have_text(done)
    assert pg.locator("[data-gff]").all_inner_texts() == chips
    assert pg.locator("#gfq").get_attribute("placeholder") == search
    assert c1.locator("svg.gfring text").text_content() == ring
    assert c1.locator(".gfname").inner_text() == B1                                                            # Buchname bleibt
    c1.locator("summary").click()
    expect(c1.locator(".gfrows .r")).to_have_count(60, timeout=T)
    assert c1.locator(".gfrows .r span[translate=no]").first.inner_text() == "1 Rundweg bei Moosbach"         # Tourtitel bleibt
    expect(c1.locator(".gfmapb")).not_to_have_text("Offene Touren auf der Karte")
    _shots(pg, f"wf-390-{lang}.png", c1)
    c1.locator("summary").click()
    assert not pg.errors, pg.errors
    ctx.browser_.close()
