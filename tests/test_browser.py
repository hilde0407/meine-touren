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
import json as _json
_g = db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES('Testbuch','Winterrunde',?,6,200)", (_json.dumps([[48.0, 8.0], [48.01, 8.01], [48.0, 8.02]]),))
db.execute("INSERT INTO wishlist(gid,ts) VALUES(?,1)", (_g,))
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
    has = page.evaluate("async () => { const ids = new Set(window.__loc.map(t => t.id)); const cv = await api('/api/tour-covers'); return [...ids].some(i => cv[i]); }")
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
    assert n >= 1, "keine Foto-Marker im Höhenprofil"      # Testfotos haben keine GPS-Position: Zuordnung über die Zeit
    page.evaluate("document.querySelector('#psvg .pph').dispatchEvent(new MouseEvent('click', {bubbles: true}))")
    page.wait_for_timeout(300)
    assert page.evaluate("document.querySelector('#lb').classList.contains('on')")
    page.evaluate("document.querySelector('#lb').classList.remove('on')")        # Foto-Ansicht schließen, damit Folgetests nicht verdeckt werden
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


def test_admin_tabs(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/dash"); page.wait_for_timeout(300)
    page.evaluate("localStorage.removeItem('admtab')")
    page.goto(base + "#/admin"); page.wait_for_timeout(2500)
    tabs = page.evaluate("[...document.querySelectorAll('#atabs button')].map(b => b.textContent)")
    assert tabs == ["Übersicht", "Touren & Quellen", "Fotos", "Automatik", "Sicherung & Zugang"], tabs
    vis = lambda: page.evaluate("[...document.querySelectorAll('.atab')].filter(s => s.style.display !== 'none').map(s => s.dataset.t)")
    assert vis() == ["uebersicht"]
    for t, word in (("quellen", "Komoot"), ("fotos", "Fotos importieren"), ("auto", "Automatik"), ("sicher", "Sicherung")):
        page.click(f"#atabs [data-t={t}]")
        assert vis() == [t] and word in page.inner_text(f".atab[data-t={t}]"), (t, word)
    assert "tab=sicher" in page.url
    assert page.locator("#save").is_visible()                      # Speichern-Leiste bleibt auf jedem Reiter erreichbar
    page.goto(base + "#/admin?strava=ok"); page.wait_for_timeout(1500)
    assert vis() == ["quellen"]
    assert not page.errors, page.errors


def test_repeat_badge(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/dash"); page.wait_for_timeout(800)
    page.evaluate("REP = Object.fromEntries(TOURS.slice(0, 2).map((t, i) => [t.id, {n: 3, start_ts: t.start_ts, with: [{id: TOURS[2].id, start_ts: TOURS[2].start_ts}, {id: TOURS[3].id, start_ts: TOURS[3].start_ts}]}]))")
    page.goto(base + "#/tours"); page.wait_for_timeout(1200)
    assert page.locator(".tr .rep").count() >= 1
    tid = page.evaluate("TOURS[0].id")
    page.goto(base + "#/tour/" + tid); page.wait_for_timeout(1500)
    assert "3-mal" in page.inner_text("#repnote")
    assert not page.errors, page.errors


def test_clean_unused_dialog(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/dash"); page.wait_for_timeout(300)
    ids = page.evaluate("""async () => { const ph = await api('/api/photos?limit=500'); const id = ph[0].id; await api('/api/photo-unassign', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({ids: [id], exclude: true})}); return id; }""")
    page.goto(base + "#/photos"); page.wait_for_timeout(1800)
    assert page.locator("#pclean").count() == 1
    page.click("#pclean"); page.wait_for_timeout(800)
    assert page.locator("#cudo").is_disabled()                    # erst nach Auswahl eines Jahres möglich
    page.click("#cuy input"); assert "endgültig löschen" in page.inner_text("#cudo")
    page.click("#cuno")
    assert not page.errors, page.errors


def test_update_panel_inside_tab_and_check_button(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/admin?tab=uebersicht"); page.wait_for_timeout(2500)
    assert page.evaluate("document.querySelectorAll('#ucheck').length") == 1
    assert page.evaluate("!!document.querySelector('#upd #ucheck')"), "Update-Bereich liegt nicht mehr in seinem Container"
    page.click("#ucheck"); page.wait_for_timeout(2500)
    assert "Installiert" in page.inner_text("#upd")
    assert not page.errors, page.errors


def test_sport_figs_and_steep_button(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/dash"); page.wait_for_timeout(600)
    tid = page.evaluate("TOURS.find(t => t.sport === 'hike' && t.source === 'local').id")
    page.goto(base + "#/tour/" + tid); page.wait_for_timeout(2500)
    txt = page.inner_text("#sfigs")
    assert "Gehzeit" in txt and "steilster Abschnitt" in txt
    assert page.locator("#tm .smap").count() == 1
    page.click("#tm .smap"); page.wait_for_timeout(300)
    assert page.locator("#tm .sleg").count() == 1
    assert not page.errors, page.errors


def test_sport_metrics_ski_and_bike(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/dash"); page.wait_for_timeout(600)
    r = page.evaluate("""() => {
      // 2 km bergauf (10 %), dann 2 km bergab (-12 %) mit Pause dazwischen; alle 20 m ein Punkt, 4 km/h hoch, 30 km/h runter
      const pts = []; let t = 0, z = 1000, lat = 47;
      for (let i = 0; i < 100; i++) { pts.push([lat, 10, z, t]); lat += 20 / 111320; z += 2; t += 18000; }
      pts.push([lat, 10, z, t + 600000]); t += 600000;
      for (let i = 0; i < 100; i++) { lat += 20 / 111320; z -= 2.4; t += 2400; pts.push([lat, 10, z, t]); }
      const m = sportMetrics(pts);
      return {m: {tUp: m.tUp, tDown: m.tDown, tPause: m.tPause, down: m.down, maxV: m.maxV, maxG: m.maxG},
              ski: sportFigs({sport: 'skitour'}, m).map(x => x[2]), bike: sportFigs({sport: 'mtb'}, m).map(x => x[2]), run: sportFigs({sport: 'jogging'}, m).map(x => x[1])};
    }""")
    m = r["m"]
    assert 1700 < m["tUp"] < 1900 and 150 < m["tDown"] < 260
    assert 500 < m["tPause"] < 700 and 220 < m["down"] < 260
    assert 25 < m["maxV"] < 33 and -14 < m["maxG"] < -10
    assert "Aufstieg" in r["ski"] and "Abfahrtshöhenmeter" in r["ski"] and "Höchstes Tempo" in r["bike"] and "min/km" in r["run"]
    assert not page.errors, page.errors


def test_gear_row_and_season_filter(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/dash"); page.wait_for_timeout(600)
    tid = page.evaluate("""async () => { await api('/api/gear', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({name: 'Testschuhe', kind: 'Schuhe', sports: ['hike'], limit_km: 5})}); return TOURS.find(t => t.sport === 'hike' && t.source === 'local').id; }""")
    page.goto(base + "#/tour/" + tid); page.wait_for_timeout(2000)
    assert "Testschuhe" in page.inner_text("#gearrow")
    page.goto(base + "#/places"); page.wait_for_timeout(2500)
    assert "Testschuhe" in page.inner_text("#gearsec") and "Wechsel fällig" in page.inner_text("#gearsec")
    page.goto(base + "#/tours"); page.wait_for_timeout(1200)
    n_all = page.evaluate("TOURS.length")
    page.select_option("#fz", "winter"); page.wait_for_timeout(300)
    cnt = page.evaluate("TOURS.filter(t => seasonOf(t.date) === 'winter').length")
    assert page.locator(".tr").count() == cnt < n_all
    assert not page.errors, page.errors


def test_wishlist_season_select(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/places"); page.wait_for_timeout(2500)
    sel = page.locator("#wlist .wseason")
    assert sel.count() == 1
    now = page.evaluate("seasonOfMonth(new Date().getMonth() + 1)")
    sel.select_option(now); page.wait_for_timeout(500)
    assert "passt jetzt" in page.inner_text("#wlist")
    assert page.locator("#wlist .plan-g").count() == 1 and page.locator("#wlist .plan-l").count() == 1
    assert page.evaluate("api('/api/wishlist').then(l => l.find(x => x.title === 'Winterrunde').season)") == now
    assert not page.errors, page.errors


def test_stars_safety_compare_and_note_size(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/dash"); page.wait_for_timeout(700)
    tid = page.evaluate("TOURS.find(t => t.sport === 'hike' && t.source === 'local').id")
    other = page.evaluate("TOURS.filter(t => t.source === 'local')[1].id")
    page.evaluate("""async id => { await api('/api/tours/' + id + '/sport', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({sport: 'skitour'})}); await loadTours(); }""", tid)
    page.evaluate("window.REPP")      # echte Wiederholungs-Auswertung abwarten (4 gleiche Runden)
    page.goto(base + "#/tour/" + tid); page.wait_for_selector("#starrow", timeout=20000); page.wait_for_selector("#cmpseg", timeout=10000)
    # Sterne
    page.click("#starrow .st[data-n='4']"); page.wait_for_timeout(400)
    assert page.evaluate("BY[%r].stars" % tid) == 4 and page.locator("#starrow .st.on").count() == 4
    # Sicherheit (Skitour)
    assert page.locator("#safety").count() == 1
    page.click("#safety summary"); page.click("#slvl [data-l='3']")
    page.click("#sgear label:has-text('LVS')"); page.fill("#snote", "Triebschnee am Grat"); page.click("#ssave"); page.wait_for_timeout(500)
    assert "gespeichert" in page.inner_text("#smsg")
    assert page.evaluate("api('/api/tours/%s/safety').then(s => [s.level, s.gear, s.note])" % tid) == [3, ["lvs"], "Triebschnee am Grat"]
    # Vergleich derselben Strecke
    assert page.locator("#cmpseg").count() == 1 and "schnellste von" in page.inner_text("#cmpseg")
    # Größe der Notizbox wird gemerkt
    page.evaluate("document.querySelector('#note').style.height = '210px'"); page.wait_for_timeout(900)
    assert "210" in page.evaluate("localStorage.getItem('size:note')")
    page.goto(base + "#/tour/" + other); page.wait_for_selector("#starrow", timeout=20000)
    assert 200 <= page.evaluate("document.querySelector('#note').offsetHeight") <= 220
    # lange Notiz: Box wächst mit, damit der ganze Text lesbar ist
    page.fill("#note", "\n".join(f"Zeile {i}" for i in range(30)))
    assert page.evaluate("document.querySelector('#note').offsetHeight >= document.querySelector('#note').scrollHeight")
    # Regression: Tippen darf die Box nicht Zeichen für Zeichen aufblähen
    page.fill("#note", "")
    page.evaluate("document.querySelector('#note').style.height = '120px'"); page.wait_for_timeout(500)
    page.click("#note"); page.keyboard.type("x" * 40)
    h = page.evaluate("document.querySelector('#note').offsetHeight")
    assert h <= 140, h
    # Liste: Bewertungsfilter
    page.evaluate("sessionStorage.clear()")
    page.goto(base + "#/tours"); page.wait_for_timeout(1200)
    page.select_option("#fb", "4"); page.wait_for_timeout(300)
    assert page.locator(".tr").count() == 1 and "★" in page.inner_text(".tr")
    assert not page.errors, page.errors


def test_goal_sport_groups(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/dash"); page.wait_for_timeout(700)
    r = page.evaluate("""() => { const y = TOURS[0].y; return ['grp:foot', 'grp:bike', 'grp:ski', 'hike', ''].map(s => goalVal({year: y, sport: s, metric: 'count'}, TOURS)); }""")
    assert r[0] + r[1] + r[2] >= 1 and r[4] >= r[3]
    page.goto(base + "#/dash"); page.wait_for_timeout(1500)
    assert page.evaluate("[...document.querySelectorAll('#gsp option')].map(o => o.textContent).join('|')").count("Alle Rad-Sportarten") == 1
    assert not page.errors, page.errors


def test_ui_password_panel(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/admin?tab=sicher"); page.wait_for_timeout(1500)
    assert page.locator("#uipws").count() == 1 and "nicht passwortgeschützt" in page.inner_text("#uipw")
    page.fill("#uipw1", "abcdef"); page.fill("#uipw2", "abcdeX"); page.click("#uipws")
    assert "stimmen nicht überein" in page.inner_text("#uipwm")
    page.fill("#uipw1", "abc"); page.fill("#uipw2", "abc"); page.click("#uipws")
    assert "mindestens 6" in page.inner_text("#uipwm")
    assert not page.errors, page.errors


def test_plan_page(page):
    import json as _j
    base = page.url.split("#")[0]
    page.route("**/api/plan/elevation", lambda r: r.fulfill(status=200, content_type="application/json", body='{"ele":[500,520,560,540,600,640],"up":140,"down":20,"max":640,"min":500}'))

    def route(r):
        b = _j.loads(r.request.post_data)
        (la1, lo1), (la2, lo2), alt = b["a"], b["b"], b.get("alt", 0)
        mid = [(la1 + la2) / 2 + 0.02 * (alt + 1), (lo1 + lo2) / 2]                     # Umweg: je Alternative weiter weg
        pts = [[la1, lo1, 500], mid + [520], [la2, lo2, 540]]
        r.fulfill(status=200, content_type="application/json", body=_j.dumps({"pts": pts, "km": 2.0 + alt, "up": 40 + 10 * alt, "time_s": 1800, "alt": alt}))
    page.route("**/api/plan/route", route)
    page.goto(base + "#/tours"); page.wait_for_timeout(1200)
    assert page.locator("#plink").count() == 1
    page.click("#plink"); page.wait_for_timeout(1200)
    page.evaluate("""() => { const m = map; [[48.0, 8.0], [48.01, 8.01], [48.02, 8.0]].forEach(p => m.fire('click', {latlng: L.latLng(p[0], p[1])})); }""")
    page.wait_for_timeout(1800)
    txt = page.inner_text("#pf")
    assert "Strecke" in txt and "140" in txt and "Geschätzte Zeit" in txt
    km = lambda: float(page.inner_text("#pf").split("km")[0].replace(",", "."))
    k0 = km()
    assert k0 > 6                                                                      # geroutete Umwege statt Luftlinie (≈ 2,7 km)
    assert page.locator("#pprof svg").count() == 1
    # Alternativen für den ausgewählten (letzten) Abschnitt
    assert "Abschnitt 2 von 2" in page.inner_text("#pseg")
    page.click("#palts"); page.wait_for_timeout(1200)
    assert page.locator("#paltl .alt-c").count() == 4
    page.click("#paltl .alt-c[data-a='2']"); page.wait_for_timeout(1800)
    k1 = km()
    assert k1 > k0 + 1                                                                 # gewählte Alternative ist länger
    r = page.evaluate("""() => { const d = densify([[48, 8], [48.01, 8]], 50); return [d.length, paceModel('hike').n >= 0, parseGpxPts('<gpx><trk><trkseg><trkpt lat="1" lon="2"/><trkpt lat="3" lon="4"/></trkseg></trk></gpx>').length]; }""")
    assert 20 <= r[0] <= 25 and r[2] == 2
    page.fill("#pn", "Meine Testplanung"); page.click("#psave"); page.wait_for_timeout(800)
    assert "gespeichert" in page.inner_text("#pmsg") and "Meine Testplanung" in page.inner_text("#plist")
    page.click("#pclr"); page.wait_for_timeout(300)
    assert page.evaluate("document.querySelector('#pf').innerText").startswith("Setze")
    page.click("#plist [data-p]"); page.wait_for_timeout(1800)
    assert page.input_value("#pn") == "Meine Testplanung" and abs(km() - k1) < 0.05      # gewählte Alternative bleibt erhalten
    # „Wegen folgen“ aus: gerade Linien (Luftlinie ≈ 2,5 km statt 5 km)
    page.click("#prt + *") if False else page.evaluate("document.querySelector('#prt').click()")
    page.wait_for_timeout(1500)
    assert 2.5 < km() < 2.9
    assert not page.errors, page.errors


def test_plan_switch_ui_and_album_stats(page):
    base = page.url.split("#")[0]
    page.evaluate("api('/api/settings', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({plan_enabled: '1', plan_mode: '', brouter_url: ''})})")
    page.goto(base + "#/tours"); page.wait_for_timeout(1200)
    assert page.locator("#plink").count() == 1
    page.goto(base + "#/admin?tab=quellen"); page.wait_for_timeout(1500)
    assert page.locator("#brpanel").count() == 1 and page.is_visible("#brpanel")
    page.check('input[name="pm"][value="local"]')
    assert page.is_visible("#pinst") and "install-brouter.sh" in page.inner_text("#pinst")
    assert ":17777/brouter" in page.input_value("#purl")
    page.route("**/api/plan/test", lambda r: r.fulfill(status=200, content_type="application/json", body='{"ok": true, "msg": "BRouter antwortet, Routen werden berechnet ✓"}'))
    page.click("#ptest"); page.wait_for_timeout(500)
    assert "antwortet" in page.inner_text("#ptm")
    page.select_option("#pon", "0"); assert not page.is_visible("#pbox")
    page.click("#save"); page.wait_for_timeout(600)
    page.goto(base + "#/tours"); page.wait_for_timeout(1200)
    assert page.locator("#plink").count() == 0
    page.goto(base + "#/plan"); page.wait_for_timeout(800)
    assert "ausgeschaltet" in page.inner_text("main")
    page.evaluate("api('/api/settings', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({plan_enabled: '1', plan_mode: '', brouter_url: ''})})")
    # Statistik je Aktivität in Alben/Reisen
    tid = page.evaluate("TOURS.filter(t => t.sport === 'hike')[0].id")
    page.evaluate("api('/api/tours/%s/tags', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({tags: ['statstest']})})" % tid)
    page.goto(base + "#/tours"); page.reload(); page.wait_for_timeout(800)
    page.goto(base + "#/album/statstest"); page.wait_for_timeout(1500)
    txt = page.inner_text("main")
    assert "Statistik nach Aktivität" in txt and "Abstieg" in txt and "Wandern" in txt, txt[:400]


def test_trip_edit_and_pdf_sheet(page):
    import json as _j
    base = page.url.split("#")[0]
    page.goto(base + "#/tours"); page.wait_for_timeout(1000)
    ids = page.evaluate("TOURS.slice(0, 3).map(t => t.id)")
    day = lambda i: page.evaluate("TOURS.find(t => t.id === '%s').date.slice(0, 10)" % ids[i])
    fake = [{"id": ids[0], "region": "Kanaren", "country": "Spanien", "start": day(0), "end": day(0), "days": 1, "tours": ids, "km": 10, "up_m": 100, "h": 2, "photo": None}]
    page.route("**/api/trips", lambda r: r.fulfill(status=200, content_type="application/json", body=_j.dumps(fake)))
    page.goto(base + "#/trip/" + ids[0]); page.wait_for_timeout(1500)
    assert page.locator("#tredit").count() == 1 and page.locator("#trpdf").count() == 1
    assert "Statistik nach Aktivität" in page.inner_text("main")
    page.click("#tredit")
    assert page.input_value("#tn") == "Kanaren" and page.locator("#tf").count() == 1
    page.click("#tno")
    page.click("#trpdf"); page.wait_for_timeout(1800)
    txt = page.inner_text("main")
    assert "Kanaren" in txt and "Tag für Tag" in txt and "Statistik nach Aktivität" in txt and "Drucken" in txt
    assert page.locator("#tm").count() == 1 and page.locator("#pdfdl").count() == 1


def test_pdf_photo_choice(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/tours"); page.wait_for_timeout(1000)
    tid = page.evaluate("(TOURS.find(t => t.photos) || TOURS[0]).id")
    page.goto(base + "#/sheet/" + tid); page.wait_for_timeout(1500)
    assert page.locator("#pdfon").is_checked() and page.input_value("#pdfn") == "6"
    n_on = page.locator("#th .th").count()
    page.select_option("#pdfn", "3"); page.wait_for_timeout(800)
    assert page.locator("#th .th").count() <= 3
    s = page.evaluate("api('/api/settings').then(s => [s.pdf_photos, s.pdf_photo_n])")
    assert s == ["1", "3"]
    page.uncheck("#pdfon"); page.wait_for_timeout(800)
    assert page.locator("#th .th").count() == 0 and page.is_disabled("#pdfn")
    assert page.evaluate("api('/api/settings').then(s => s.pdf_photos)") == "0"
    # gilt appweit: auch im Jahresrückblick
    page.goto(base + "#/recap/2024"); page.wait_for_timeout(1500)
    assert page.locator("#pdfon").count() == 1 and not page.locator("#pdfon").is_checked()
    page.evaluate("api('/api/settings', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({pdf_photos: '1', pdf_photo_n: '6'})})")


def test_share_result_and_handy_panel(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/shared?t=1&d=0&a=1&p=2&x=1"); page.wait_for_timeout(1200)
    txt = page.inner_text("main")
    assert "1 Tour importiert" in txt and "2 Fotos empfangen" in txt and "nicht unterstützt" in txt
    page.goto(base + "#/shared?t=0&d=1&a=1"); page.wait_for_timeout(800)
    assert "schon vorhanden" in page.inner_text("main")
    page.goto(base + "#/admin?tab=uebersicht"); page.wait_for_timeout(1500)
    assert page.locator("#handy").count() == 1 and page.is_visible("#handy")
    assert "Teilen-Menü" in page.inner_text("#handy")


def test_offline_banner(page):
    base = page.url.split("#")[0]
    page.goto(base + "#/tours"); page.wait_for_timeout(800)
    assert page.locator("#offbar").count() == 0
    page.context.set_offline(True)
    page.evaluate("window.dispatchEvent(new Event('offline'))"); page.wait_for_timeout(300)
    assert page.locator("#offbar").count() == 1 and "Offline" in page.inner_text("#offbar")
    page.context.set_offline(False)
    page.evaluate("window.dispatchEvent(new Event('online'))"); page.wait_for_timeout(300)
    assert page.locator("#offbar").count() == 0


def test_record_view_app(page):
    """Aufzeichnungsseite mit nachgebildeter Android-Brücke (window.MTApp)."""
    base = page.url.split("#")[0]
    page.add_init_script("""
      window._st = {state:'idle', sport:'hike', name:'', count:0, dist_m:0, up_m:0, down_m:0, active_s:0, gps:true};
      window._g = '<?xml version="1.0"?><gpx version="1.1"><trk><type>hike</type><trkseg>' + Array.from({length:30},(_, i)=>`<trkpt lat="${47+i*0.0006}" lon="11"><ele>${900+i*4}</ele><time>2026-08-01T07:${String(i).padStart(2,'0')}:00Z</time></trkpt>`).join('') + '</trkseg></trk></gpx>';
      window.MTApp = {version:()=>'2.0.0', serverUrl:()=>location.origin, hasPermission:()=>true, requestPermission(){}, openBatterySettings(){}, changeServer(){},
        status:()=>JSON.stringify(window._st), points:()=>'[[47,11],[47.001,11.001]]',
        startRecording(s,n){window._st={...window._st,state:'recording',sport:s,name:n,dist_m:1234,up_m:56,active_s:75}},
        pauseRecording(){window._st.state='paused'}, resumeRecording(){window._st.state='recording'},
        stopRecording(){window._st.state='finished'}, takeFinished:()=>window._g, markUploaded(){window._st.state='idle'}, discardRecording(){window._st.state='idle'},
        diagnose:()=>JSON.stringify({version:'2.0.0',android:'14',device:'Test',server:location.origin,loc_perm:true,gps_on:true,notif_perm:true,battery_free:false,status:window._st}), logText:()=>'Start', clearLog(){}, appLog(){}, shareText(){}};
    """)
    page.goto(base + "#/dash"); page.reload(); page.wait_for_timeout(800)
    assert page.locator('nav a[data-k="record"]').count() == 1
    page.set_viewport_size({"width": 390, "height": 800}); page.wait_for_timeout(500)
    page.click("#tmore"); page.wait_for_timeout(300)
    assert page.locator('.moregrid a[href="#/record"]').count() == 1
    assert page.locator('.moregrid a[href="#/record"]').is_visible(), 'Menüpunkt nicht sichtbar'
    page.locator('.moregrid a[href="#/record"]').dispatch_event('click'); page.wait_for_timeout(500)
    page.set_viewport_size({"width": 1280, "height": 800})
    page.fill("#rname", "Testrunde"); page.click("#rstart"); page.wait_for_timeout(700)
    assert "1,23" in page.inner_text("#rd") and page.locator("#rmap").count() == 1
    page.once("dialog", lambda d: d.accept())
    page.click("#rstop"); page.wait_for_timeout(700)
    assert page.locator("#rsend").count() == 1
    page.click("#rsend"); page.wait_for_function("location.hash.startsWith('#/tour/')", timeout=8000)

    page.goto(base + "#/apptest"); page.wait_for_timeout(800)
    t = page.inner_text("#main")
    assert "Server erreichbar" in t and "Akku-Optimierung ist aktiv" in t and "GPS ist eingeschaltet" in t


def test_mobile_more_sheet_not_covered(page):
    """„Mehr“-Fenster liegt über der Tab-Leiste und ist bis ganz unten erreichbar."""
    base = page.url.split("#")[0]
    page.set_viewport_size({"width": 360, "height": 640})
    page.goto(base + "#/dash"); page.reload(); page.wait_for_timeout(800)
    page.click("#tmore"); page.wait_for_timeout(400)
    z = page.evaluate("(()=>{const m=document.querySelector('.modal'),t=document.querySelector('#tabbar');return [+getComputedStyle(m).zIndex,+getComputedStyle(t).zIndex,getComputedStyle(m.querySelector('.mbox')).overflowY]})()")
    assert z[0] > z[1] and z[2] in ("auto", "scroll")
    box = page.evaluate("(()=>{const b=document.querySelector('.modal .mbox');b.scrollTop=1e5;const r=document.querySelector('.modal .mbox').getBoundingClientRect();return [r.bottom,innerHeight]})()")
    assert box[0] <= box[1] + 1
