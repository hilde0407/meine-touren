"""Browser-Rauchtest: alle Ansichten mit Beispieldaten laden, keine JavaScript-Fehler; schneller Seitenwechsel ohne Fehler."""
import os, socket, subprocess, sys, time, urllib.request
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
VIEWS = ["dash", "map", "tours", "records", "records?s=hike", "recap/2024", "trips", "places", "photos", "check", "admin", "account",
         "search?q=Runde", "tour/g1717225200", "compare"]


def _seed(data):
    code = f"""
import sys, os; sys.path.insert(0, {str(ROOT)!r}); os.environ['DATA_DIR'] = {str(data)!r}
from app import db, tracks, photos, gpxtools
import math
from datetime import datetime, timedelta, timezone
def gpx(d):
    t0 = datetime.strptime(d, '%Y-%m-%d--%H-%M-%S').replace(tzinfo=gpxtools.TZ).astimezone(timezone.utc); pts = []
    for i in range(400):
        a = 2 * math.pi * i / 399
        t = (t0 + timedelta(seconds=6 * i)).strftime('%Y-%m-%dT%H:%M:%SZ')
        pts.append(f'<trkpt lat="{{48 + 0.004 * math.sin(a):.6f}}" lon="{{8 + 0.006 * (1 - math.cos(a)):.6f}}"><ele>{{400 + 60 * math.sin(2 * a):.1f}}</ele><time>{{t}}</time></trkpt>')
    return '<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><type>hiking</type><trkseg>' + ''.join(pts) + '</trkseg></trk></gpx>'
db.init()
for i, d in enumerate(['2024-06-01--07-00-00', '2024-07-14--09-30-00', '2025-05-03--10-00-00', '2025-08-20--08-15-00']):
    t, _ = tracks.adopt(gpx(d), f'w{{i}}.gpx', name=f'Runde {{i}}')
db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES('k1','Komoot-Tour','touringbicycle',1720000000,1720007200,40000,7200,300,300,48,8,'tour_recorded','komoot')")
db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES('k2','Wanderung 01.03.2020 13:18','hike',1583000000,1583000060,51,60,0,0,48,8,'tour_recorded','komoot')")
lt = db.query("SELECT id,start_ts FROM tours WHERE source='local' ORDER BY start_ts LIMIT 1")[0]
for j in range(6):   # 6 Fotos am selben Tag (Dateien fehlen absichtlich – es geht nur um die Auswahl)
    db.execute("INSERT INTO photos(path,taken_ts,dated,tour_id) VALUES(?,?,1,?)", (f"/x/p{{j}}.jpg", lt["start_ts"] + 300 * j, lt["id"]))
print(db.query("SELECT id FROM tours"))
"""
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr


@pytest.fixture(scope="module")
def app_url(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    d = tmp_path_factory.mktemp("bt")
    _seed(d / "data")
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    env = dict(os.environ, DATA_DIR=str(d / "data"), PHOTOS_DIR=str(d / "p"), BACKUP_DIR=str(d / "b"))
    pr = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/version", timeout=1); break
        except Exception:
            time.sleep(0.2)
    yield f"http://127.0.0.1:{port}"
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:      # Beenden dauert auf langsamen Runnern manchmal länger
        pr.kill(); pr.wait(5)


@pytest.fixture(scope="module")
def page(app_url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(locale="de-DE", viewport={"width": 1280, "height": 900})
        pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(app_url) else r.continue_())   # keine Kartenkacheln/Internet
        pg.errors = []
        pg.on("pageerror", lambda e: pg.errors.append(str(e) + " @ " + (e.stack or "")[:1500]))
        pg.goto(app_url + "/#/dash"); pg.wait_for_timeout(1500)
        yield pg
        b.close()


def _tour_id(page):
    return page.evaluate("TOURS.find(t => t.source === 'local').id")


@pytest.mark.parametrize("view", VIEWS)
def test_view_loads_without_errors(page, view):
    if view.startswith("tour/"):
        view = "tour/" + _tour_id(page)
    page.errors.clear()
    page.evaluate(f"location.hash = '#/{view}'")
    page.wait_for_timeout(1200)
    txt = page.inner_text("#main")
    assert len(txt) > 20, f"{view}: leer"
    assert "Fehler" not in txt[:200], f"{view}: {txt[:200]}"
    assert not page.errors, f"{view}: {page.errors}"


@pytest.mark.parametrize("pause", [15, 40, 90, 200])
def test_fast_navigation_no_errors(page, pause):
    cdp = page.context.new_cdp_session(page); cdp.send("Emulation.setCPUThrottlingRate", {"rate": int(os.environ.get("MT_CPU_RATE", "4"))})   # langsamer Rechner (wie GitHub Actions)
    page.errors.clear()
    tid = _tour_id(page)
    for v in ["map", "tour/" + tid, "dash", "map", "records", "tour/" + tid, "check", "map", "admin", "photos", "tours"] * 2:
        page.evaluate(f"location.hash = '#/{v}'"); page.wait_for_timeout(pause)
    page.wait_for_timeout(3000)
    cdp.send("Emulation.setCPUThrottlingRate", {"rate": 1})
    assert not page.errors, page.errors


def test_fresh_load_without_errors(page, app_url):
    pg = page.context.browser.new_page(locale="de-DE"); errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(app_url) else r.continue_())
    for v in ["dash", "tours", "check", "admin"]:
        pg.goto(app_url + "/#/" + v); pg.wait_for_timeout(900)
    pg.close()
    assert not errs, errs


def test_interactions(page):
    page.errors.clear()
    page.evaluate("location.hash = '#/tour/' + TOURS.find(t => t.source === 'local').id"); page.wait_for_timeout(1200)
    page.click("#eup"); page.wait_for_selector(".modal .pp"); page.click("#ucx")
    page.evaluate("location.hash = '#/records'"); page.wait_for_timeout(800)
    page.click("a.chip:has-text('Radtour')"); page.wait_for_timeout(800)
    assert "Radtour" in page.inner_text("#main .sec")
    page.evaluate("location.hash = '#/check'"); page.wait_for_selector("#impl")
    page.click("#impl [data-idel]"); page.wait_for_selector("#dok"); page.click("#dx")
    page.evaluate("location.hash = '#/admin'"); page.wait_for_timeout(1500)
    assert "Zustand" in page.inner_text("#hlt")
    assert not page.errors, page.errors


def test_photo_selection_from_clicked(page):
    page.errors.clear()
    page.evaluate("location.hash = '#/tour/' + TOURS.filter(t => t.source === 'local').sort((a, b) => a.start_ts - b.start_ts)[0].id")
    page.wait_for_timeout(1500)
    page.click("button:has-text('Fotos bearbeiten')")
    imgs = page.locator(".thumbs img[data-i]")
    assert imgs.count() == 6
    cap = lambda sel: page.evaluate(f"[...document.querySelectorAll('.thumbs {sel}')].map(i => i.parentElement.querySelector('.cap').textContent.slice(-5)).sort()")
    clicked = page.evaluate("document.querySelectorAll('.thumbs img[data-i]')[2].parentElement.querySelector('.cap').textContent.slice(-5)")
    alle = cap("img[data-i]")
    page.evaluate("document.querySelectorAll('.thumbs img[data-i]')[2].scrollIntoView({block: 'start'})")     # nicht unter der Auswahlleiste klicken
    imgs.nth(2).click(force=True)
    assert cap("img.sel") == [x for x in alle if x >= clicked]
    page.click("[data-a=off]"); page.click("button:has-text('Fotos bearbeiten')")
    imgs.nth(2).click(force=True, modifiers=["Shift"])
    assert cap("img.sel") == [x for x in alle if x <= clicked]
    imgs.nth(0).click(force=True)                      # danach: einzelnes Foto umschalten
    assert len(cap("img.sel")) in (len([x for x in alle if x <= clicked]) - 1, len([x for x in alle if x <= clicked]) + 1)
    assert not page.errors, page.errors


def test_photo_shift_dialog_moves_selected(page):
    page.errors.clear()
    tid = page.evaluate("TOURS.filter(t => t.source === 'local').sort((a, b) => a.start_ts - b.start_ts)[0].id")
    page.evaluate("location.hash = '#/dash'"); page.wait_for_timeout(600)          # frisch aufbauen (Auswahlmodus des vorigen Tests zurücksetzen)
    page.evaluate(f"location.hash = '#/tour/{tid}'"); page.wait_for_timeout(1500)
    before = page.evaluate(f"fetch('/api/photos?tour_id={tid}&limit=50').then(r => r.json()).then(j => j.map(p => p.taken_ts).sort())")
    assert len(before) == 6
    page.click("button:has-text('Fotos bearbeiten')")
    page.evaluate("document.querySelectorAll('.thumbs img[data-i]')[5].scrollIntoView({block: 'start'})")
    page.locator(".thumbs img[data-i]").nth(5).click(force=True)           # letztes Foto (und alle späteren: nur dieses)
    page.click("[data-a=shift]"); page.wait_for_selector("#shok")
    page.click("[data-p='-3600']")
    assert "Neue Zeit" in page.inner_text("#shp")
    page.click("#shok"); page.wait_for_timeout(1500)
    after = page.evaluate("fetch('/api/photos?limit=500').then(r => r.json()).then(j => j.map(p => p.taken_ts))")
    assert any(b - 3600 in after for b in before[-1:]), (before, after)
    # zurückschieben, damit die übrigen Tests unverändert laufen
    page.evaluate("fetch('/api/photo-shift-ids', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({ids: [...document.querySelectorAll('.nothing')].map(x => 0), delta_s: 0})})")
    ids = page.evaluate("fetch('/api/photos?limit=500').then(r => r.json()).then(j => j.filter(p => p.offset_s === -3600).map(p => p.id))")
    assert ids
    page.evaluate(f"fetch('/api/photo-shift-ids', {{method: 'POST', headers: {{'content-type': 'application/json'}}, body: JSON.stringify({{ids: {ids}, delta_s: 3600}})}})")
    page.wait_for_timeout(800)
    assert not page.errors, page.errors


def test_photo_chain_drag_moves_all_and_saves(page):
    page.errors.clear()
    tid = page.evaluate("TOURS.filter(t => t.source === 'local').sort((a, b) => a.start_ts - b.start_ts)[0].id")
    page.evaluate(f"location.hash = '#/tour/{tid}'")
    page.wait_for_selector("#chb", timeout=15000)
    page.wait_for_timeout(500)
    ts = lambda: page.evaluate(f"fetch('/api/photos?tour_id={tid}').then(r => r.json()).then(a => a.map(p => p.taken_ts))")
    before = ts()
    assert len(before) == 6
    page.click("#chb")
    pos = page.evaluate("""() => {
      const c = window._chain, m = c.items[0].m, tgt = c.atTime(1200 * 1000);
      const f = map.latLngToContainerPoint(m.getLatLng()), to = map.latLngToContainerPoint(L.latLng(tgt[0], tgt[1])), r = document.getElementById('tm').getBoundingClientRect();
      return {fx: r.left + f.x, fy: r.top + f.y, tx: r.left + to.x, ty: r.top + to.y};
    }""")
    page.mouse.move(pos["fx"], pos["fy"]); page.mouse.down()
    page.mouse.move((pos["fx"] + pos["tx"]) / 2, (pos["fy"] + pos["ty"]) / 2, steps=6)
    page.mouse.move(pos["tx"], pos["ty"], steps=6); page.mouse.up()
    assert "Min." in page.inner_text("#chi") and not page.is_disabled("#chok")
    # die anderen Fotos sind mitgewandert: Foto 5 (25 min nach Start) liegt jetzt am Streckenende (Zeit begrenzt)
    moved = page.evaluate("window._chain.items.map(i => [i.m.getLatLng().lat, i.m.getLatLng().lng])")
    assert len({tuple(round(x, 5) for x in m) for m in moved}) >= 5
    page.click("#chok"); page.wait_for_timeout(1500)
    after = ts()
    diffs = {a - b for a, b in zip(after, before)}
    assert len(diffs) == 1 and abs(diffs.pop() - 1200) < 60              # alle Fotos um denselben Betrag verschoben
    page.once("dialog", lambda d: d.accept())
    page.click("#chb"); page.click("#chre"); page.wait_for_timeout(1500)
    assert ts() == before                                                # Original-Zeiten wiederhergestellt
    assert not page.errors, page.errors


def test_english_ui(page, app_url):
    """Englische Oberfläche: Navigation und Datumsformat übersetzt, keine JavaScript-Fehler, Umschalten zurück funktioniert."""
    if True:
        b = page.context.browser
        ctx = b.new_context(locale="en-US")
        pg = ctx.new_page()
        pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(app_url) else r.continue_())
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(app_url + "/#/dash"); pg.wait_for_timeout(1500)
        nav = pg.inner_text("#nav")
        assert "Overview" in nav and "Tours" in nav and "Photos" in nav and "Übersicht" not in nav
        for v in ("tours", "photos", "admin", "check", "records"):
            pg.goto(app_url + f"/#/{v}"); pg.wait_for_timeout(600)
        assert pg.evaluate("document.documentElement.lang") == "en"
        pg.select_option("#langsw", "de"); pg.wait_for_timeout(1200)
        assert "Übersicht" in pg.inner_text("#nav")
        assert not errs, errs
        ctx.close()


def test_trackfix_dialog_opens(page):
    page.goto(page.url.split("#")[0] + "#/dash"); page.wait_for_timeout(300)
    tid = _tour_id(page)
    page.goto(page.url.split("#")[0] + f"#/tour/{tid}"); page.wait_for_timeout(1200)
    page.click("#etfix"); page.wait_for_selector("#tfb #tfno", timeout=8000)
    assert "Track" in page.inner_text(".mbox")
    page.click("#tfno")
    assert not page.errors, page.errors


def test_french_and_spanish_ui(page, app_url):
    """Französische und spanische Oberfläche: Navigation übersetzt, Datumsformat, keine JavaScript-Fehler."""
    for loc, word, nope in (("fr-FR", "Aperçu", "Übersicht"), ("es-ES", "Resumen", "Übersicht")):
        ctx = page.context.browser.new_context(locale=loc)
        pg = ctx.new_page()
        pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(app_url) else r.continue_())
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.goto(app_url + "/#/dash"); pg.wait_for_timeout(1500)
        nav = pg.inner_text("#nav")
        assert word in nav and nope not in nav, nav
        for v in ("tours", "photos", "admin", "check"):
            pg.goto(app_url + f"/#/{v}"); pg.wait_for_timeout(500)
        assert pg.evaluate("document.documentElement.lang") == loc[:2]
        assert not errs, errs
        ctx.close()


def test_multiday_series_view(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/dash"); page.wait_for_timeout(300)
    r = page.evaluate("""() => {
      const loc = TOURS.filter(t => t.source === 'local').slice(0, 3), old = loc.map(t => t.name);
      loc.forEach((t, i) => (t.name = 'Alpenüberquerung E5 - Tag ' + (i + 4)));
      const L = seriesList();
      window.__old = old; window.__loc = loc;
      return {n: L.length, e: L[0] && L[0].n, id: L[0] && L[0].id};
    }""")
    assert r["n"] == 1 and r["e"] == 3
    page.goto(base + "#/trips"); page.wait_for_timeout(1200)
    assert "Mehrtagestouren" in page.inner_text("main") and "Alpenüberquerung E5" in page.inner_text("main")
    has = page.evaluate("async () => { const ids = new Set(window.__loc.map(t => t.id)); return (await api('/api/photos?limit=5000')).some(p => ids.has(p.tour_id)); }")
    bg = page.evaluate("document.querySelector('.otdg .otd').style.backgroundImage")
    assert (not has) or "/pic/" in bg, bg
    page.goto(base + "#/series/" + r["id"]); page.wait_for_timeout(1500)
    assert "3 Etappen" in page.inner_text("main")
    page.evaluate("() => window.__loc.forEach((t, i) => (t.name = window.__old[i]))")
    page.goto(base + "#/dash"); page.wait_for_timeout(300)
    assert not page.errors, page.errors


def test_profile_photo_markers(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/dash"); page.wait_for_timeout(300)
    tid = page.evaluate("""async () => { const ph = await api('/api/photos?limit=500'); const p = ph.find(x => x.tour_id); return p && p.tour_id; }""")
    if not tid:
        return
    page.goto(base + "#/tour/" + tid); page.wait_for_timeout(2500)
    n = page.evaluate("document.querySelectorAll('#psvg .pph').length")
    if n:
        page.evaluate("document.querySelector('#psvg .pph').dispatchEvent(new MouseEvent('click', {bubbles: true}))")
        page.wait_for_timeout(300)
        assert page.evaluate("document.querySelector('#lb').classList.contains('on')")
    assert not page.errors, page.errors


def test_tourblatt(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/dash"); page.wait_for_timeout(300)
    tid = page.evaluate("TOURS[0].id")
    page.goto(base + "#/tour/" + tid); page.wait_for_timeout(1500)
    assert page.locator("#esheet").count() == 1
    page.goto(base + "#/sheet/" + tid); page.wait_for_timeout(2000)
    assert page.locator(".sheet h1").count() == 1 and page.locator("#shp").count() == 1
    assert page.locator(".sheet .leaflet-container").count() == 1
    assert not page.errors, page.errors


def test_goal_forecast_text(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/dash"); page.wait_for_timeout(300)
    page.evaluate("""async () => { const y = new Date().getFullYear(); window.__g = []; for (const t of [1, 99999]) { await api('/api/goals', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({year: y, metric: 'km', sport: '', target: t})}); } }""")
    page.goto(base + "#/dash?y=" + str(__import__("datetime").date.today().year)); page.wait_for_timeout(1500)
    txt = page.inner_text("#goals")
    assert "Ziel erreicht" in txt or "Prognose" in txt, txt
    assert "verfehlt" in txt or "voraussichtlich" in txt or "Ziel erreicht" in txt, txt
    page.evaluate("""async () => { for (const g of await api('/api/goals')) await api('/api/goals/' + g.id, {method: 'DELETE'}); }""")
    assert not page.errors, page.errors


def test_best_photos_button(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/dash"); page.wait_for_timeout(300)
    tid = page.evaluate("""async () => { const ph = await api('/api/photos?limit=500'); const p = ph.find(x => x.tour_id); return p && p.tour_id; }""")
    assert tid
    page.goto(base + "#/tour/" + tid); page.wait_for_timeout(2000)
    assert page.locator("#pbest").count() == 1
    page.click("#pbest"); page.wait_for_timeout(1200)
    assert "beste von" in page.inner_text("#pc"), page.inner_text("#pc")
    assert page.locator("#ss").get_attribute("href").endswith("best=10")
    assert not page.errors, page.errors
