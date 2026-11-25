"""3.49.0 – App: Aufzeichnen im Fokus (Browser, Chromium, mit nachgestellter Android-Brücke window.MTApp).

Geprüft wird: Tab-Leiste der App (mittiger Reiter „Aufzeichnen“ mit Zustand, höchstens fünf Reiter, Fotos unter „Mehr“), Startseite der App (Aufzeichnen/Übersicht,
laufende Aufzeichnung gewinnt), die Aufzeichnungsseite in den Zuständen bereit / läuft / pausiert / fertig (große Ziffern, Touch-Ziele ≥ 48 px, GPS in Worten,
Beenden nur mit Rückfrage, automatisches Hochladen, „wartet auf Netz“, „später senden“), Geräteanmeldung (deviceInfo wird mitgeschickt, „Meine Geräte“),
ältere APK ohne deviceInfo, 360–430 px ohne Querrollen, hell/dunkel, vier Sprachen, reduzierte Bewegung, Warnleiste (--wbh) – und dass ein Browser OHNE Brücke unverändert bleibt.
Regeln (tests/README.md): keine festen Wartezeiten, wait_for_function nur als Pfeilfunktion, Wartezeit 15 s. Screenshots mit TS_SHOTS=<Ordner>."""
import json
import os
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.helpers_ui import open_details, quiet, settled
from tests.test_tourseite_ui import CONTRAST, LAUNCH, SEED, _wait

ROOT = Path(__file__).resolve().parent.parent
T = 15000
IID = "5b0e7a52-3c1d-4b8e-9f10-2a6c7d8e9f01"
REC = {"state": "recording", "count": 412, "dist_m": 8460, "up_m": 612, "down_m": 118, "active_s": 9252, "alt_m": 1534, "max_alt_m": 1602, "speed_ms": 1.25, "wps": 2,
       "fix_age_s": 2, "fix_acc_m": 5}

# Nachgestellte Brücke. %(dev)s = Zusatzmethoden der neuen APK (deviceInfo); ohne sie verhält sich die Attrappe wie eine ältere installierte App.
MOCK = r"""
(() => {
  window._st = Object.assign({state:'idle', sport:'hike', name:'', count:0, dist_m:0, up_m:0, down_m:0, active_s:0, gps:true, wps:0}, %(state)s);
  window._pi = {taken:0, pending:0, busy:false, error:''};
  window._calls = [];
  window._bk = [];
  window._day = %(day)s;
  window._gpx = () => '<?xml version="1.0"?><gpx version="1.1" creator="Meine Touren (Android)"><trk><type>' + (window._st.sport || 'hike') + '</type><trkseg>' + Array.from({length:40},(_, i)=>`<trkpt lat="${47.42+i*0.0006}" lon="${10.98+i*0.0004}"><ele>${900+i*9}</ele><time>2026-08-${String(window._day).padStart(2,'0')}T07:${String(i).padStart(2,'0')}:00Z</time></trkpt>`).join('') + '</trkseg></trk></gpx>';
  const pts = Array.from({length:60},(_, i)=>[47.42+i*0.0006, 10.98+i*0.0004]);
  window.MTApp = {version:()=>'%(ver)s', serverUrl:()=>location.origin, hasPermission:()=>%(perm)s, requestPermission(){window._calls.push('perm')}, openBatterySettings(){window._calls.push('bat')}, changeServer(){},
    status:()=>JSON.stringify(window._st), points:()=>JSON.stringify(pts), lang:()=>'de', setLang(){},
    startRecording(s,n){window._calls.push('start:'+s+':'+n); window._st=Object.assign({}, window._st, %(rec)s, {state:'recording', sport:s, name:n})},
    pauseRecording(){window._calls.push('pause'); window._st.state='paused'}, resumeRecording(){window._calls.push('resume'); window._st.state='recording'},
    stopRecording(){window._calls.push('stop'); window._st.state='finished'}, takeFinished:()=>window._gpx(),
    markUploaded(){window._calls.push('uploaded'); window._bk.unshift({file:'rec_'+window._day+'.gpx', size:51200, ts:Date.now(), gpx:window._gpx()}); window._st.state='idle'; window._day++},
    discardRecording(){window._calls.push('discard'); window._bk.unshift({file:'rec_'+window._day+'.gpx', size:51200, ts:Date.now(), gpx:window._gpx()}); window._st.state='idle'; window._day++},
    backups:()=>JSON.stringify(window._bk.map(b => ({file:b.file, size:b.size, ts:b.ts}))), backupGpx:f=>(window._bk.find(b => b.file === f) || {gpx:''}).gpx,
    diagnose:()=>JSON.stringify({version:'%(ver)s',android:'14 (API 34)',device:'Google Pixel 8',server:location.origin,loc_perm:%(perm)s,gps_on:true,notif_perm:true,battery_free:%(bat)s,status:window._st}),
    logText:()=>'Start', clearLog(){}, appLog(){}, shareText(t){window._shared=t}, openUrl(){}%(full)s%(dev)s};
})();
"""
FULL = """, addWaypoint(n){window._calls.push('wp:'+n); window._st.wps=(window._st.wps||0)+1; return true}, waypoints:()=>'[]',
    takePhoto(){window._calls.push('photo'); window._pi.taken++; return true}, photoMode:()=>'now', setPhotoMode(){}, photoInfo:()=>JSON.stringify(window._pi), uploadPhotos(){window._pi.pending=0},
    setRoute(){}, clearRoute(){}, routeInfo:()=>'{"has":false,"on":true}', routePoints:()=>'[]', setGuide(){}, guideTest(){},
    weatherOn:()=>true, setWeather(){}, weatherInfo:()=>'{}'"""
DEV = ", deviceInfo:()=>JSON.stringify({install_id:'%s', hersteller:'Google', modell:'Pixel 8', android:'14', app_version:'3.49.0'})"


def _mock(state=None, perm="true", bat="true", ver="3.49.0", dev=IID, full=True, day=1):
    return MOCK % {"state": json.dumps(state or {}), "rec": json.dumps({k: v for k, v in REC.items() if k != "state"}), "perm": perm, "bat": bat, "ver": ver,
                   "full": FULL if full else "", "dev": (DEV % dev) if dev else "", "day": day}


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    tmp = tmp_path_factory.mktemp("rec349")
    data = tmp / "data"
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data)}], capture_output=True, text=True, cwd=ROOT, env=env)
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


@pytest.fixture(scope="module")
def pw():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


def _api(url, path, body=None, method=None):
    req = urllib.request.Request(url + path, method=method or ("POST" if body is not None else "GET"), data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read() or b"{}")


def _open(pw, url, hsh="/#/record", mock=None, width=390, height=800, scheme="light", lang="de", geo=False, ls=None, before=None, **kw):
    """Seite in der „App“ öffnen (mock=False: gewöhnlicher Browser ohne Brücke). before(pg) läuft vor dem ersten Laden (z. B. Anfragen abfangen)."""
    b = pw.chromium.launch()
    opts = dict(locale={"de": "de-DE", "en": "en-GB", "fr": "fr-FR", "es": "es-ES"}[lang], viewport={"width": width, "height": height}, color_scheme=scheme,
                device_scale_factor=2 if width < 500 else 1, reduced_motion="reduce")
    if geo:
        opts.update(geolocation={"latitude": 47.42, "longitude": 10.98, "accuracy": 5}, permissions=["geolocation"])
    ctx = b.new_context(**opts)
    if mock is not False:
        ctx.add_init_script(mock or _mock(**kw))
    store = dict(ls or {})
    if lang != "de":
        store["lang"] = lang
    if store:                                             # nur setzen, was noch nicht gesetzt ist: spätere Änderungen der Seite überstehen ein Neuladen
        ctx.add_init_script("(() => { const s = %s; for (const k in s) { try { if (localStorage.getItem(k) === null) localStorage.setItem(k, s[k]); } catch (e) {} } })()" % json.dumps(store))
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(url) else r.continue_())
    pg.browser_ = b
    if before:
        before(pg)
    pg.goto(url + hsh)
    pg.wait_for_selector("#main > *", state="attached", timeout=T)
    quiet(pg)
    return pg


def _shot(pg, name, full=False):
    d = os.environ.get("TS_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        settled(pg)
        pg.evaluate("() => window.scrollTo(0, 0)")
        pg.screenshot(path=str(Path(d) / name), full_page=full)


def _no_hscroll(pg):
    r = pg.evaluate("() => [document.documentElement.scrollWidth, innerWidth]")
    assert r[0] <= r[1], f"Seite rollt quer: {r}"


def _small_targets(pg, root=".rec"):
    """Sichtbare Bedienelemente der Aufzeichnungsseite unter 48 px Höhe (Schalter zählen mit ihrer Beschriftung)."""
    return pg.evaluate("""(root) => [...document.querySelectorAll(root + ' button, ' + root + ' a.btn, ' + root + ' select, ' + root + ' input:not([type=checkbox]), ' + root + ' summary, ' + root + ' label.chk')]
      .filter(e => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; })
      .map(e => [e.id || e.className || e.tagName, Math.round(e.getBoundingClientRect().height)]).filter(x => x[1] < 48)""", root)


def _state(pg, **kw):
    """Zustand der nachgestellten App ändern und die Seite darauf reagieren lassen (wie die Rückkehr in die App)."""
    pg.evaluate("(kw) => { Object.assign(window._st, kw); window.dispatchEvent(new Event('mtresume')); }", kw)


# ---------------------------------------------------------------------------------------------- ohne App: alles wie bisher
def test_browser_ohne_app_unveraendert(pw, app):
    pg = _open(pw, app, "/", mock=False)
    try:
        pg.wait_for_selector("#tabbar a", timeout=T)
        assert pg.evaluate("() => [...document.querySelectorAll('#tabbar > *')].map(e => e.dataset.k || e.id)") == ["dash", "map", "tours", "photos", "tmore"]
        assert pg.locator("#tabbar .trec").count() == 0 and not pg.evaluate("() => document.querySelector('#tabbar').classList.contains('app')")
        assert pg.locator('#nav a[data-k="record"]').count() == 0
        assert pg.evaluate("() => location.hash") == ""                       # kein Umleiten auf die Aufzeichnung
        pg.wait_for_selector("main.home", timeout=T)
        pg.locator("#tmore").click()
        pg.wait_for_selector(".moregrid a", timeout=T)
        links = pg.evaluate("() => [...document.querySelectorAll('.uimod .moregrid a')].map(a => a.getAttribute('href'))")
        assert "#/record" not in links and "#/photos" not in links and "#/apptest" not in links, links
        pg.evaluate("() => { location.hash = '#/record'; }")
        expect(pg.locator("#main")).to_contain_text("nur in der Android-App", timeout=T)
        assert pg.locator(".rec").count() == 0 and not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ---------------------------------------------------------------------------------------------- Navigation in der App
def test_tableiste_aufzeichnen_in_der_mitte(pw, app):
    pg = _open(pw, app, "/#/tours", before=lambda p: p.route("**/api/record/upload", lambda r: r.abort()))     # „wartet auf das Hochladen“ soll stehen bleiben (sonst sendet die Seite von selbst)
    try:
        pg.wait_for_selector("#tabbar a.trec", timeout=T)
        keys = pg.evaluate("() => [...document.querySelectorAll('#tabbar > *')].map(e => e.dataset.k || e.id)")
        assert keys == ["dash", "tours", "record", "map", "tmore"], keys                 # höchstens fünf, Aufzeichnen in der Mitte
        r = pg.evaluate("""() => { const c = document.querySelector('#tabbar .trc').getBoundingClientRect(), t = document.querySelector('#tabbar').getBoundingClientRect(),
          o = document.querySelector('#tabbar a[data-k=tours] .ti').getBoundingClientRect(); return {w: c.width, h: c.height, above: t.top - c.top, mid: Math.abs((c.left + c.right) / 2 - innerWidth / 2), other: o.height, bar: t.height}; }""")
        assert r["w"] >= 52 and r["h"] >= 52 and r["above"] >= 10 and r["mid"] <= 2 and r["w"] > 2 * r["other"], r     # rund, groß, ragt heraus, mittig
        assert abs(r["bar"] - 53) <= 1, r                                                   # die Leiste selbst ist so hoch wie ohne App (Karte und Flug rechnen mit dieser Höhe)
        expect(pg.locator("#tabbar .trl")).to_have_text("Aufzeichnen", timeout=T)
        idle_bg = pg.evaluate("() => getComputedStyle(document.querySelector('#tabbar .trc')).backgroundColor")
        _no_hscroll(pg)
        # was gewichen ist, liegt unter „Mehr“
        pg.locator("#tmore").click()
        pg.wait_for_selector('.uimod .moregrid a[href="#/photos"]', timeout=T)
        expect(pg.locator('.uimod .moregrid a[href="#/photos"]')).to_be_visible()
        assert pg.locator('.uimod .moregrid a[href="#/record"]').count() == 0
        pg.locator('.uimod .moregrid a[href="#/photos"]').click()
        pg.wait_for_function("() => location.hash === '#/photos'", timeout=T)
        # läuft: Wort, Zeit und Farbe – auf jeder Seite
        _state(pg, **REC)
        pg.wait_for_function("() => document.querySelector('#tabbar a.trec').dataset.s === 'recording' && document.querySelector('#tabbar .trl').textContent === 'Läuft'", timeout=T)
        assert pg.inner_text("#tabbar .trc") == "2:34" and pg.get_attribute("#tabbar a.trec", "aria-label") == "Aufzeichnung läuft"
        run_bg = pg.evaluate("() => getComputedStyle(document.querySelector('#tabbar .trc')).backgroundColor")
        assert run_bg != idle_bg and run_bg == "rgb(179, 64, 45)", (idle_bg, run_bg)
        assert pg.evaluate("() => getComputedStyle(document.querySelector('#tabbar .trc'), '::after').animationName") == "none"       # reduzierte Bewegung: kein Pulsieren
        _shot(pg, "tab-laeuft-390-light.png")
        _state(pg, state="recording", active_s=59)
        pg.wait_for_function("() => /^(0:59|1:0\\d)$/.test(document.querySelector('#tabbar .trc').textContent)", timeout=T)                # unter einer Stunde: Minuten und Sekunden, zählt weiter
        _state(pg, state="paused")
        pg.wait_for_function("() => document.querySelector('#tabbar .trl').textContent === 'Pausiert' && !!document.querySelector('#tabbar .trc svg')", timeout=T)
        _state(pg, state="finished")
        pg.wait_for_function("() => document.querySelector('#tabbar .trl').textContent === 'Hochladen'", timeout=T)
        pg.locator("#tabbar a.trec").click()
        pg.wait_for_function("() => location.hash === '#/record' && document.querySelector('#tabbar a.trec').classList.contains('on')", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_menueleiste_computer_ansicht(pw, app):
    """Ansicht „Computer“ in der App: Aufzeichnen steht vorn als hervorgehobener Menüpunkt und zeigt den Zustand mit Zeit."""
    pg = _open(pw, app, "/#/tours", width=1280, height=900, state=REC)
    try:
        a = pg.locator('#nav a[data-k="record"]')
        expect(a).to_be_visible(timeout=T)
        assert pg.evaluate("() => document.querySelector('#nav a').dataset.k") == "record"
        pg.wait_for_function("() => document.querySelector('#nav a[data-k=record]').dataset.s === 'recording' && /2:34:\\d\\d/.test(document.querySelector('#nav a[data-k=record]').textContent)", timeout=T)
        assert "Läuft" in a.inner_text()
        r = pg.evaluate("""() => { const e = document.querySelector('#nav a[data-k=record]'), n = document.querySelector('#nav').getBoundingClientRect(), b = e.getBoundingClientRect(), cs = getComputedStyle(e);
          return {bg: cs.backgroundColor, radius: parseFloat(cs.borderRadius), inside: b.left >= n.left - 1 && b.right <= n.right + 1}; }""")
        assert r["bg"] == "rgb(179, 64, 45)" and r["radius"] > 15 and r["inside"], r
        _state(pg, state="idle")
        pg.wait_for_function("() => document.querySelector('#nav a[data-k=record]').textContent.trim() === 'Aufzeichnen'", timeout=T)
        assert pg.evaluate("() => getComputedStyle(document.querySelector('#nav a[data-k=record]')).backgroundColor") == "rgb(242, 194, 48)"
        _shot(pg, "menue-1280-light.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.kern                     # Stichprobe im schnellen Kern (tests/README.md)
def test_startseite_der_app(pw, app):
    pg = _open(pw, app, "/")
    try:
        pg.wait_for_function("() => location.hash === '#/record'", timeout=T)       # Kaltstart ohne Ziel: Aufzeichnen (Standard)
        pg.wait_for_selector("#rstart", timeout=T)
        assert pg.evaluate("() => history.length") <= 2                             # ersetzt, nicht angehängt: „Zurück“ verlässt die App wie bisher
        pg.goto(app + "/#/tours")
        pg.wait_for_selector("#tl", timeout=T)
        assert pg.evaluate("() => location.hash") == "#/tours"                       # ein konkretes Ziel bleibt
        # Einstellung „Startseite der App“ (auf der Aufzeichnungsseite), je Gerät gemerkt
        pg.goto(app + "/#/record")
        pg.wait_for_selector("#rset", timeout=T)
        open_details(pg, "#rset")
        expect(pg.locator('#rset [data-as="record"]')).to_have_attribute("aria-pressed", "true", timeout=T)
        pg.locator('#rset [data-as="dash"]').click()
        expect(pg.locator('#rset [data-as="dash"]')).to_have_attribute("aria-pressed", "true", timeout=T)
        assert pg.evaluate("() => document.querySelector('#rset').open")             # die Einstellungen bleiben beim Neuaufbau offen
        pg.goto(app + "/")
        pg.wait_for_selector("main.home", timeout=T)
        assert pg.evaluate("() => location.hash") == "#/dash"
        # dieselbe Einstellung in der Verwaltung → „Handy & App“
        pg.goto(app + "/#/admin?tab=handy")
        pg.wait_for_selector('#appstart [data-as="dash"][aria-pressed="true"]', timeout=T)
        pg.locator('#appstart [data-as="record"]').click()
        pg.wait_for_selector('#appstart [data-as="record"][aria-pressed="true"]', timeout=T)
        assert pg.evaluate("() => localStorage.getItem('mt_app_start')") == "record"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    # läuft schon eine Aufzeichnung, immer dorthin – auch wenn „Übersicht“ gewählt ist
    pg = _open(pw, app, "/", state=REC, ls={"mt_app_start": "dash"})
    try:
        pg.wait_for_function("() => location.hash === '#/record'", timeout=T)
        pg.wait_for_selector("#rstop", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ---------------------------------------------------------------------------------------------- bereit
@pytest.mark.kern                     # Stichprobe im schnellen Kern (tests/README.md)
def test_bereit_start_sportart_gps(pw, app):
    pg = _open(pw, app, geo=True)
    try:
        pg.wait_for_selector("#rstart", timeout=T)
        expect(pg.locator("#rgpst")).to_have_text("GPS bereit, ±5 m", timeout=T)       # Zustand in Worten, nicht nur als Farbe
        assert pg.get_attribute("#rgps", "data-q") == "ok"
        r = pg.evaluate("""() => { const b = document.querySelector('#rstart').getBoundingClientRect(); return {w: b.width, h: b.height, bottom: b.bottom, ih: innerHeight, tab: document.querySelector('#tabbar').getBoundingClientRect().top,
          fs: parseFloat(getComputedStyle(document.querySelector('#rstart')).fontSize)}; }""")
        assert r["h"] >= 88 and r["w"] >= 340 and r["fs"] >= 30 and r["bottom"] <= r["tab"], r        # ein großer Start-Knopf, ohne Rollen erreichbar
        assert pg.locator(".recsp").count() == 5 and pg.locator('.recsp[aria-checked="true"]').count() == 1          # 3.59.0: die Favoriten-Aktivitäten (Vorgabe: 5), alle übrigen unter „Mehr …“
        assert pg.evaluate("() => document.querySelector('.recsp').dataset.sp") == "hike"
        assert _small_targets(pg) == []
        for hint in ("#rhperm", "#rhbat", "#rhgps", "#rhnotif", "#rbk", "#rhph"):          # Hinweise nur, wenn nötig
            assert pg.locator(hint).count() == 0, hint
        assert not pg.evaluate("() => document.querySelector('#rset').open")               # Seltenes ist eingeklappt
        _no_hscroll(pg)
        _shot(pg, "bereit-390-light.png")
        # Sportart wählen, starten: die zuletzt genutzte steht beim nächsten Mal vorn
        pg.locator('.recsp[data-sp="skitour"]').click()
        expect(pg.locator('.recsp[data-sp="skitour"]')).to_have_attribute("aria-checked", "true", timeout=T)
        open_details(pg, "#rset")
        pg.fill("#rname", "Morgenrunde")
        pg.locator("#rstart").click()
        pg.wait_for_selector("#rstop", timeout=T)
        assert "start:skitour:Morgenrunde" in pg.evaluate("() => window._calls")
        _state(pg, state="idle")
        pg.wait_for_selector("#rstart", timeout=T)
        assert pg.evaluate("() => [document.querySelector('.recsp').dataset.sp, document.querySelector('.recsp').getAttribute('aria-checked')]") == ["skitour", "true"]
        # die selten gebrauchten Dinge sind alle noch da
        open_details(pg, "#rset")
        for sel in ("#rname", "#rphm", "#rwxon", "#rlh", "#rlink", "#rbat", "#rdev", '#rset [data-as="record"]'):
            expect(pg.locator(sel)).to_be_visible(timeout=T)
        assert pg.locator('#rset a[href="#/apptest"]').count() == 1               # App-Test und Protokoll: wie bisher nur im Entwicklermodus sichtbar
        assert pg.locator("#rroute").is_visible()
        assert _small_targets(pg) == []
        _no_hscroll(pg)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_bereit_hinweise_mit_handlung(pw, app):
    pg = _open(pw, app, perm="false", bat="false")
    try:
        pg.wait_for_selector("#rhperm", timeout=T)
        expect(pg.locator("#rgpst")).to_have_text("Standort-Berechtigung fehlt", timeout=T)
        assert pg.get_attribute("#rgps", "data-q") == "bad"
        r = pg.evaluate("() => [document.querySelector('#rhperm').getBoundingClientRect().top < document.querySelector('#rstart').getBoundingClientRect().top, document.querySelector('#rhbat').getBoundingClientRect().top > document.querySelector('#rstart').getBoundingClientRect().bottom]")
        assert r == [True, True], r                                   # was das Starten hindert, steht davor; der Rest darunter
        pg.locator("#rperm").click()
        pg.locator("#rbat2").click()
        assert pg.evaluate("() => window._calls") == ["perm", "bat"]
        pg.locator("#rstart").click()                                 # ohne Berechtigung startet nichts – es wird nach ihr gefragt
        assert pg.evaluate("() => window._calls") == ["perm", "bat", "perm"] and pg.evaluate("() => window._st.state") == "idle"
        assert _small_targets(pg) == []
        _shot(pg, "bereit-hinweise-390-light.png", full=True)
        pg.locator("#rbatx").click()
        expect(pg.locator("#rhbat")).to_have_count(0, timeout=T)
        pg.reload()
        pg.wait_for_selector("#rstart", timeout=T)
        assert pg.locator("#rhbat").count() == 0                      # ausgeblendet bleibt ausgeblendet; die Einstellung selbst bleibt erreichbar
        assert pg.locator("#rbat").count() == 1 and not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ---------------------------------------------------------------------------------------------- läuft / pausiert
def test_laeuft_grosse_ziffern_und_pausiert(pw, app):
    pg = _open(pw, app, state=REC)
    try:
        pg.wait_for_selector("#rstop", timeout=T)
        assert pg.get_attribute(".rec", "data-s") == "recording"
        expect(pg.locator("#rstt")).to_have_text("Aufnahme läuft", timeout=T)
        expect(pg.locator("#rgpst")).to_have_text("GPS ±5 m", timeout=T)
        assert pg.inner_text("#rd") == "8,46" and pg.inner_text("#ru") == "612" and pg.inner_text("#ralt") == "1.534" and pg.inner_text("#rspd") == "4,5"
        assert pg.inner_text("#rt").startswith("2:34:1")
        r = pg.evaluate("""() => { const fs = s => parseFloat(getComputedStyle(document.querySelector(s)).fontSize), cs = getComputedStyle(document.querySelector('#rt')), h = s => document.querySelector(s).getBoundingClientRect().height;
          return {t: fs('#rt'), d: fs('#rd'), row: fs('#ru'), nums: cs.fontVariantNumeric, pause: h('#rpause'), stop: h('#rstop'), photo: h('#rphoto'), wp: h('#rwpb'),
                  cp: getComputedStyle(document.querySelector('#rpause')).backgroundColor, cst: getComputedStyle(document.querySelector('#rstop')).backgroundColor,
                  dock: document.querySelector('.recdock').getBoundingClientRect().bottom, tab: document.querySelector('#tabbar').getBoundingClientRect().top}; }""")
        assert r["t"] >= 64 and r["d"] >= 56 and 24 <= r["row"] < r["d"] and "tabular-nums" in r["nums"], r           # Zeit und Strecke sehr groß, zweite Reihe kleiner
        assert r["pause"] >= 60 and r["stop"] >= 60 and r["cp"] != r["cst"] and r["cst"] == "rgb(179, 64, 45)", r      # zwei große, klar unterschiedene Knöpfe
        assert 48 <= r["photo"] < r["pause"] and 48 <= r["wp"] < r["stop"] and r["dock"] <= r["tab"] + 1, r            # Nebenaktionen kleiner; alles über der Tab-Leiste erreichbar
        pg.wait_for_function("() => document.querySelectorAll('#rmap path.leaflet-interactive').length >= 2", timeout=T)       # Karte mit Spur und Standort
        c = pg.evaluate(CONTRAST, ["#rt", "#rd", "#ru", "#rstop", "#rpause", "#rstt"])
        assert all(v >= 4.5 for v in c.values()), c
        assert _small_targets(pg) == []
        _no_hscroll(pg)
        _shot(pg, "laeuft-390-light.png")
        # restliche Werte: zurückhaltend, aufklappbar – und weiter vorhanden
        assert not pg.evaluate("() => document.querySelector('#rmore').open")
        open_details(pg, "#rmore")
        for sel, val in (("#rdn", "118"), ("#rmax", "1.602"), ("#ravg", "3,3"), ("#racc", "5")):
            expect(pg.locator(sel)).to_have_text(val, timeout=T)
        # Nebenaktionen: Foto und Wegpunkt
        pg.locator("#rphoto").click()
        pg.locator("#rwpb").click()
        pg.wait_for_selector(".uimod [data-wp]", timeout=T)
        assert pg.evaluate("() => [...document.querySelectorAll('.uimod [data-wp]')].every(b => b.getBoundingClientRect().height >= 48)")
        pg.locator('.uimod [data-wp="Gipfel"]').click()
        expect(pg.locator("#rwpm")).to_contain_text("„Gipfel“ gespeichert", timeout=T)
        assert pg.evaluate("() => window._calls") == ["photo", "wp:Gipfel"]
        # pausiert: unmissverständlich
        pg.locator("#rpause").click()
        pg.wait_for_selector("#rres", timeout=T)
        assert pg.get_attribute(".rec", "data-s") == "paused"
        expect(pg.locator("#rstt")).to_have_text("Pausiert", timeout=T)
        expect(pg.locator(".recstate .rsp")).to_contain_text("Es wird nichts aufgezeichnet", timeout=T)
        r = pg.evaluate("""() => { const s = getComputedStyle(document.querySelector('.recstate')), b = getComputedStyle(document.querySelector('#rres'));
          return {banner: s.backgroundColor, fs: parseFloat(getComputedStyle(document.querySelector('#rstt')).fontSize), go: b.backgroundColor, h: document.querySelector('#rres').getBoundingClientRect().height}; }""")
        assert r["banner"] == "rgb(242, 194, 48)" and r["fs"] >= 24 and r["go"] == "rgb(242, 194, 48)" and r["h"] >= 60, r
        expect(pg.locator("#tabbar .trl")).to_have_text("Pausiert", timeout=T)
        assert pg.evaluate("() => document.querySelector('#rmore').open")              # aufgeklappte Werte bleiben aufgeklappt
        _shot(pg, "pausiert-390-light.png")
        pg.locator("#rres").click()
        pg.wait_for_selector("#rpause", timeout=T)
        assert pg.evaluate("() => window._calls").count("resume") == 1 and not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_warnleiste_wird_bei_der_kartenhoehe_beruecksichtigt(pw, app):
    """Die Karte füllt die Resthöhe; die Warnleiste des Sicherungs-Wächters (--wbh) wird abgezogen."""
    pg = _open(pw, app, state=REC, height=980)
    try:
        pg.wait_for_selector("#rmap", timeout=T)
        hs = []
        for wbh in ("0px", "120px"):
            pg.evaluate("(v) => { document.documentElement.style.setProperty('--wbh', v); }", wbh)
            hs.append(pg.evaluate("() => document.querySelector('#rmap').getBoundingClientRect().height"))
        assert hs[0] >= 300 and abs(hs[0] - hs[1] - 120) <= 1, hs
    finally:
        pg.browser_.close()


def test_warnleiste_fehlt_auf_der_aufzeichnungsseite(pw, app):
    """Auf der Aufzeichnungsseite der App zählt nur die Aufnahme: die Sicherungs-Warnleiste bleibt dort weg und erscheint auf anderen Seiten wieder."""
    pg = _open(pw, app, state=REC)
    try:
        pg.wait_for_selector("#rmap", timeout=T)
        pg.evaluate("() => { location.hash = '#/tours'; }")
        expect(pg.locator("#wbar")).to_be_visible(timeout=T)
        pg.evaluate("() => { location.hash = '#/record'; }")
        expect(pg.locator("#wbar")).to_have_count(0, timeout=T)
        pg.wait_for_function("() => getComputedStyle(document.documentElement).getPropertyValue('--wbh').trim() === '0px'", timeout=T)
    finally:
        pg.browser_.close()


# ---------------------------------------------------------------------------------------------- beenden, hochladen, fertig
def test_beenden_rueckfrage_hochladen_und_geraet(pw, app):
    pg = _open(pw, app, state=REC, day=11)
    try:
        bodies = []
        pg.on("request", lambda rq: bodies.append(rq.post_data_json) if rq.url.endswith("/api/record/upload") else None)
        pg.wait_for_selector("#rstop", timeout=T)
        pg.locator("#rstop").click()                                  # ein Tipp beendet nicht
        pg.wait_for_selector(".uidlg .uibox", timeout=T)
        expect(pg.locator(".uidlg h2")).to_have_text("Aufzeichnung beenden?", timeout=T)
        assert pg.evaluate("() => window._st.state") == "recording" and "stop" not in pg.evaluate("() => window._calls")
        btns = pg.evaluate("() => [...document.querySelectorAll('.uidlg .uifoot button')].map(b => b.textContent)")
        assert btns == ["Weiter aufzeichnen", "Beenden"], btns          # Abbrechen zuerst, Hauptknopf zuletzt
        assert pg.evaluate("() => document.activeElement.textContent") == "Weiter aufzeichnen"      # der Fokus liegt nie auf „Beenden“
        pg.locator(".uidlg .uifoot button", has_text="Weiter aufzeichnen").click()
        expect(pg.locator(".uidlg")).to_have_count(0, timeout=T)
        assert pg.evaluate("() => window._st.state") == "recording" and pg.locator("#rstop").count() == 1
        pg.locator("#rstop").click()
        pg.wait_for_selector(".uidlg .uibox", timeout=T)
        pg.locator(".uidlg .uifoot button", has_text="Beenden").click()
        # fertig: Zusammenfassung, Name, Zustand in Worten – das Hochladen beginnt von selbst
        pg.wait_for_selector("#rup", timeout=T)
        pg.wait_for_selector('#rup[data-p="saved"]', timeout=T)
        expect(pg.locator("#rupt")).to_have_text("Gespeichert", timeout=T)
        expect(pg.locator("#rups")).to_contain_text("als „Meine Touren App · Pixel 8“ angemeldet", timeout=T)
        assert "8,5" in pg.inner_text(".recrow.sum") and "2:34" in pg.inner_text(".recrow.sum") and "612" in pg.inner_text(".recrow.sum")
        for sel, vis in (("#rview", True), ("#rnew", True), ("#rretry", False), ("#rlater", False), ("#rdrop", False)):
            assert pg.locator(sel).is_visible() is vis, sel
        assert pg.evaluate("() => window._calls").count("stop") == 1 and "uploaded" in pg.evaluate("() => window._calls")
        assert len(bodies) == 1 and bodies[0]["device"] == {"install_id": IID, "hersteller": "Google", "modell": "Pixel 8", "android": "14", "app_version": "3.49.0"}, bodies
        assert bodies[0]["sport"] == "hike" and "<trkpt" in bodies[0]["gpx"]
        assert _small_targets(pg) == []
        _no_hscroll(pg)
        _shot(pg, "fertig-gespeichert-390-light.png")
        # Name nachträglich ändern
        pg.fill("#rname", "Kramerspitz mit Volker")
        pg.locator("#rname").blur()
        expect(pg.locator("#rnamem")).to_have_text("Name geändert.", timeout=T)
        pg.locator("#rview").click()
        pg.wait_for_function("() => location.hash.startsWith('#/tour/g')", timeout=T)
        tid = pg.evaluate("() => location.hash.split('/')[2]")
        t = [x for x in _api(app, "/api/tours") if x["id"] == tid][0]
        assert t["name"] == "Kramerspitz mit Volker" and t["dev"] == "Meine Touren App · Pixel 8"
        # Tourseite (Auswertung): „Aufgezeichnet mit“ nennt das App-Gerät – automatisch zugeordnet, nicht „von Hand“
        pg.evaluate("(t) => { location.hash = '#/tour/' + t + '/auswertung'; }", tid)
        expect(pg.locator("#devrow")).to_contain_text("Meine Touren App · Pixel 8", timeout=T)
        assert "Aufgezeichnet mit" in pg.inner_text("#devrow") and "von Hand" not in pg.inner_text("#devrow")
        d = _api(app, f"/api/tours/{tid}/metrics")["device"]
        assert d["app"] is True and d["manual"] is False
        # zurück zur Aufzeichnung: wieder bereit; „Dieses Gerät“ ist dem Server bekannt
        pg.locator("#tabbar a.trec").click()
        pg.wait_for_selector("#rstart", timeout=T)
        open_details(pg, "#rset")
        expect(pg.locator("#rdev")).to_contain_text("Meine Touren App · Pixel 8", timeout=T)
        expect(pg.locator("#rdev")).to_contain_text("Beim Server bekannt seit", timeout=T)
        expect(pg.locator("#rdev")).to_contain_text("Google Pixel 8 · Android 14 · App 3.49.0", timeout=T)
        assert pg.locator("#rbk").count() == 0                         # die eben gesendete Aufzeichnung gilt nicht als „noch zu senden“
        assert pg.locator("[data-bk]").count() == 1                    # ihre Sicherung bleibt unter den Einstellungen erreichbar
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_wartet_auf_netz_und_spaeter_senden(pw, app):
    net = {"ok": False, "n": 0}

    def upload(route):
        net["n"] += 1
        route.continue_() if net["ok"] else route.abort()
    pg = _open(pw, app, state=dict(REC, state="finished"), day=14, before=lambda p: p.route("**/api/record/upload", upload))
    try:
        pg.wait_for_selector('#rup[data-p="waiting"]', timeout=T)
        expect(pg.locator("#rupt")).to_have_text("Wartet auf Netz – wird später gesendet", timeout=T)
        expect(pg.locator("#rups")).to_contain_text("bleibt sicher auf dem Handy", timeout=T)
        for sel, vis in (("#rview", False), ("#rnew", False), ("#rretry", True), ("#rlater", True), ("#rdrop", True)):
            (expect(pg.locator(sel)).to_be_visible(timeout=T) if vis else expect(pg.locator(sel)).to_be_hidden(timeout=T))      # (die Seite versucht es zwischendurch von selbst erneut)
        assert "uploaded" not in pg.evaluate("() => window._calls") and pg.evaluate("() => window._st.state") == "finished"       # nichts verworfen
        expect(pg.locator("#tabbar .trl")).to_have_text("Hochladen", timeout=T)
        pg.wait_for_function("() => document.querySelector('#rup').dataset.p === 'waiting' && !recUp.busy", timeout=T)
        assert _small_targets(pg) == []
        _shot(pg, "fertig-wartet-390-light.png")
        n0 = net["n"]
        pg.locator("#rretry").click()                                  # erneut versuchen: weiter kein Netz, weiter nichts verloren
        pg.wait_for_function("() => document.querySelector('#rup').dataset.p === 'waiting' && !recUp.busy", timeout=T)
        assert net["n"] > n0 and pg.evaluate("() => window._st.state") == "finished"
        # später senden: die Aufzeichnung wandert in die Sicherungen, die Seite ist wieder bereit und zeigt sie als „noch nicht auf dem Server“
        pg.fill("#rname", "Später gesendet")
        pg.locator("#rlater").click()
        pg.wait_for_selector(".uidlg .uibox", timeout=T)
        pg.locator(".uidlg .uifoot button", has_text="Später senden").click()
        pg.wait_for_selector("#rstart", timeout=T)
        expect(pg.locator("#rbkt")).to_have_text("1 Aufzeichnung ist noch nicht auf dem Server.", timeout=T)
        expect(pg.locator("#rbkup")).to_be_visible(timeout=T)
        assert pg.evaluate("() => window._calls").count("discard") == 1
        # Netz ist wieder da: „Jetzt hochladen“ sendet sie mit dem gewählten Namen
        net["ok"] = True
        pg.locator("#rbkup").click()
        expect(pg.locator("#rbkt")).to_have_text("1 Aufzeichnung hochgeladen.", timeout=T)
        expect(pg.locator("#rbkview")).to_be_visible(timeout=T)
        expect(pg.locator("#rbkup")).to_be_hidden(timeout=T)
        tid = pg.get_attribute("#rbkview", "href").split("/")[-1]
        t = [x for x in _api(app, "/api/tours") if x["id"] == tid][0]
        assert t["name"] == "Später gesendet" and t["dev"] == "Meine Touren App · Pixel 8"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_verwerfen_mit_rueckfrage(pw, app):
    pg = _open(pw, app, state=dict(REC, state="finished"), day=17, before=lambda p: p.route("**/api/record/upload", lambda r: r.abort()))
    try:
        pg.wait_for_selector('#rup[data-p="waiting"]', timeout=T)
        pg.locator("#rdrop").click()
        pg.wait_for_selector(".uidlg .uibox", timeout=T)
        pg.locator(".uidlg .uifoot button", has_text="Abbrechen").click()
        expect(pg.locator(".uidlg")).to_have_count(0, timeout=T)
        assert pg.evaluate("() => window._st.state") == "finished"
        pg.locator("#rdrop").click()
        pg.wait_for_selector(".uidlg .uibox", timeout=T)
        pg.locator(".uidlg .uifoot button", has_text="Verwerfen").click()
        pg.wait_for_selector("#rstart", timeout=T)
        assert pg.evaluate("() => window._calls").count("discard") == 1
        assert pg.locator("#rbk").count() == 0 and not pg.errors, pg.errors      # bewusst verworfen: wird nicht als „noch zu senden“ geführt
    finally:
        pg.browser_.close()


# ---------------------------------------------------------------------------------------------- ältere installierte APK
def test_aeltere_apk_ohne_deviceinfo(pw, app):
    """Eine ältere App (keine deviceInfo, kein Foto/Wegpunkt/Route/Wetter, Version 3.0.0) arbeitet mit der neuen Seite weiter – nur ohne Geräteanmeldung."""
    n_dev = len(_api(app, "/api/my-devices")["devices"])
    pg = _open(pw, app, "/", ver="3.0.0", dev=None, full=False, day=20)
    try:
        bodies = []
        pg.on("request", lambda rq: bodies.append(rq.post_data_json) if rq.url.endswith("/api/record/upload") else None)
        pg.wait_for_function("() => location.hash === '#/record'", timeout=T)
        pg.wait_for_selector("#rstart", timeout=T)
        for sel in ("#rroute", "#rphm", "#rwxon"):
            assert pg.locator(sel).count() == 0, sel
        open_details(pg, "#rset")
        expect(pg.locator("#rdev")).to_contain_text("meldet das Handy noch nicht als Aufzeichnungsgerät an", timeout=T)
        pg.locator("#rstart").click()
        pg.wait_for_selector("#rstop", timeout=T)
        assert pg.locator("#rphoto").count() == 0 and pg.locator("#rwpb").count() == 0 and pg.locator("#rpause").count() == 1
        pg.locator("#rstop").click()
        pg.wait_for_selector(".uidlg .uibox", timeout=T)
        pg.locator(".uidlg .uifoot button", has_text="Beenden").click()
        pg.wait_for_selector('#rup[data-p="saved"]', timeout=T)
        expect(pg.locator("#rups")).to_have_text("Die Tour ist auf deinem Server.", timeout=T)
        assert len(bodies) == 1 and "device" not in bodies[0], bodies
        assert len(_api(app, "/api/my-devices")["devices"]) == n_dev             # kein Gerät angelegt
        pg.locator("#rview").click()
        pg.wait_for_function("() => location.hash.startsWith('#/tour/g')", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ---------------------------------------------------------------------------------------------- Meine Geräte
def test_meine_geraete_zeigt_die_app(pw, app):
    gpx = ('<?xml version="1.0"?><gpx version="1.1" creator="Meine Touren (Android)"><trk><type>hike</type><trkseg>' +
           "".join(f'<trkpt lat="{47.6 + i * 0.0006}" lon="11.2"><ele>{900 + i * 5}</ele><time>2026-09-05T07:{i:02d}:00Z</time></trkpt>' for i in range(40)) + "</trkseg></trk></gpx>")
    dev = {"install_id": "9a1b2c3d-4e5f-4a6b-8c7d-0e1f2a3b4c5d", "hersteller": "samsung", "modell": "SM-G991B", "android": "13", "app_version": "3.49.0"}
    r = _api(app, "/api/record/upload", {"gpx": gpx, "name": "Geräte-Tour", "device": dev})
    did = r["device"]["id"]
    assert r["device"]["name"] == "Meine Touren App · SM-G991B"
    for width, scheme in ((1280, "light"), (390, "light"), (390, "dark")):
        pg = _open(pw, app, "/#/admin?tab=quellen", mock=False, width=width, height=900, scheme=scheme)
        try:
            card = pg.locator(f'#devsec .dvcard[data-dv="{did}"]')
            expect(card).to_be_visible(timeout=T)
            expect(card.locator(".dvn")).to_have_text("Meine Touren App · SM-G991B", timeout=T)
            expect(card.locator(".dvc.app")).to_have_text("Aufzeichnungs-App", timeout=T)
            txt = card.inner_text()
            assert "Handy-Aufzeichnung · Samsung SM-G991B" in txt and "Android 13 · App 3.49." in txt and "Zuletzt aufgezeichnet am 5. September 2026" in txt and "1 Tour" in txt, txt
            assert "Was liefert diese Uhr?" not in txt and "Zeitraum unbegrenzt" not in txt and dev["install_id"] not in pg.content()
            c = pg.evaluate(CONTRAST, [f'.dvcard[data-dv="{did}"] .dvc.app', f'.dvcard[data-dv="{did}"] .dvn', f'.dvcard[data-dv="{did}"] .dvapprec'])
            assert all(v >= 4.5 for v in c.values()), c
            _no_hscroll(pg)
            card.scroll_into_view_if_needed()
            if os.environ.get("TS_SHOTS"):
                settled(pg)
                Path(os.environ["TS_SHOTS"]).mkdir(parents=True, exist_ok=True)
                pg.locator("#devsec").screenshot(path=str(Path(os.environ["TS_SHOTS"]) / f"geraete-{width}-{scheme}.png"))
            if width == 1280:                                          # umbenennen: bleibt beim nächsten Upload erhalten
                card.locator(".dvmore").click()
                pg.locator(".dvmenu button", has_text="Bearbeiten").click()
                pg.wait_for_selector("#dvn", timeout=T)
                expect(pg.locator(".dvappnote")).to_be_visible(timeout=T)
                pg.fill("#dvn", "Volkers Galaxy")
                pg.locator(".dvbox .btn", has_text="Speichern").click()
                expect(pg.locator(f'#devsec .dvcard[data-dv="{did}"] .dvn')).to_have_text("Volkers Galaxy", timeout=T)
                r2 = _api(app, "/api/record/upload", {"gpx": gpx.replace("2026-09-05", "2026-09-06"), "name": "Zweite", "device": dict(dev, app_version="3.49.1")})
                assert r2["device"] == {"id": did, "name": "Volkers Galaxy", "new": False}
                _api(app, f"/api/devices/{did}", {"name": "Meine Touren App · SM-G991B"}, method="PATCH")
                _api(app, f"/api/tours/{r2['id']}", method="DELETE")
            assert not pg.errors, pg.errors
        finally:
            pg.browser_.close()


# ---------------------------------------------------------------------------------------------- Breiten, hell/dunkel, Sprachen
@pytest.mark.parametrize("width,scheme", [(360, "dark"), (390, "dark"), (430, "light")])
def test_breiten_hell_dunkel(pw, app, width, scheme):
    for name, st in (("bereit", None), ("laeuft", REC), ("pausiert", dict(REC, state="paused"))):
        pg = _open(pw, app, state=st, width=width, height=800, scheme=scheme, bat="false" if name == "bereit" else "true")
        try:
            pg.wait_for_selector("#rstart" if name == "bereit" else "#rstop", timeout=T)
            settled(pg)
            _no_hscroll(pg)
            assert _small_targets(pg) == [], name
            over = pg.evaluate("""() => [...document.querySelectorAll('.rec button, .rec .recrow b, .rec .recbig > div, .rec select')].filter(e => e.getBoundingClientRect().width > 0 && (e.scrollWidth > e.clientWidth + 1 || e.getBoundingClientRect().right > innerWidth + 0.5))
              .map(e => e.id || e.className)""")
            assert over == [], (name, over)                             # nichts abgeschnitten, nichts ragt hinaus
            sels = {"bereit": ["#rstart", "#rgpst", ".recsp", '.recsp[aria-checked="true"]', ".reclbl", "#rhbat b"], "laeuft": ["#rt", "#rd", "#ru", ".recrow span", "#rstop", "#rpause", "#rphoto", "#rstt", "#tabbar .trl"],
                    "pausiert": ["#rstt", ".rsp", "#rres", "#rstop", "#ru", "#tabbar .trl"]}[name]
            c = pg.evaluate(CONTRAST, sels)
            assert len(c) == len(sels) and all(v >= 4.5 for v in c.values()), (name, c)
            if name == "pausiert":                                      # die großen Ziffern treten zurück, bleiben aber lesbar
                assert pg.evaluate(CONTRAST, ["#rt"])["#rt"] >= 3
            _shot(pg, f"{name}-{width}-{scheme}.png", full=name == "bereit")
            assert not pg.errors, pg.errors
        finally:
            pg.browser_.close()


@pytest.mark.parametrize("lang,words", [
    ("en", {"start": "Start recording", "tab": "Record", "gps": "GPS is switched on", "set": "Recording settings", "run": "Recording", "pause": "Pause", "stop": "Stop", "ask": "Stop the recording?", "keep": "Keep recording",
            "wait": "Waiting for network – will be sent later", "retry": "Try again now", "paused": "Paused", "resume": "Resume", "tabrun": "Running"}),
    ("fr", {"start": "Démarrer l’enregistrement", "tab": "Enregistrer", "gps": "Le GPS est activé", "set": "Réglages de l’enregistrement", "run": "Enregistrement en cours", "pause": "Pause", "stop": "Arrêter",
            "ask": "Arrêter l’enregistrement ?", "keep": "Continuer l’enregistrement", "wait": "En attente de réseau – sera envoyé plus tard", "retry": "Réessayer maintenant", "paused": "En pause", "resume": "Reprendre", "tabrun": "En cours"}),
    ("es", {"start": "Iniciar grabación", "tab": "Grabar", "gps": "El GPS está activado", "set": "Ajustes de la grabación", "run": "Grabando", "pause": "Pausar", "stop": "Detener", "ask": "¿Detener la grabación?",
            "keep": "Seguir grabando", "wait": "Esperando red: se enviará más tarde", "retry": "Reintentar ahora", "paused": "En pausa", "resume": "Reanudar", "tabrun": "En curso"}),
])
def test_sprachen(pw, app, lang, words):
    pg = _open(pw, app, lang=lang, day=23, before=lambda p: p.route("**/api/record/upload", lambda r: r.abort()))
    try:
        pg.wait_for_selector("#rstart", timeout=T)
        expect(pg.locator("#rstart")).to_have_text(words["start"], timeout=T)
        expect(pg.locator("#tabbar .trl")).to_have_text(words["tab"], timeout=T)
        expect(pg.locator("#rgpst")).to_have_text(words["gps"], timeout=T)
        expect(pg.locator("#rset > summary")).to_have_text(words["set"], timeout=T)
        open_details(pg, "#rset")
        settled(pg)
        _no_hscroll(pg)
        assert _small_targets(pg) == []
        rest = pg.evaluate("""() => [...document.querySelectorAll('.rec *')].filter(e => e.children.length === 0 && e.getBoundingClientRect().width > 0).map(e => e.textContent.trim())
          .filter(t => /\\b(der|die|das|und|nicht|wird|auf|Aufzeichnung|läuft|Gerät|Handy|Einstellungen)\\b/.test(t))""")
        assert rest == [], rest                                         # keine deutschen Reste auf der Seite
        _shot(pg, f"bereit-390-{lang}.png", full=True)
        pg.locator("#rstart").click()
        pg.wait_for_selector("#rstop", timeout=T)
        expect(pg.locator("#rstt")).to_have_text(words["run"], timeout=T)
        expect(pg.locator("#rpause")).to_have_text(words["pause"], timeout=T)
        expect(pg.locator("#rstop")).to_have_text(words["stop"], timeout=T)
        expect(pg.locator("#tabbar .trl")).to_have_text(words["tabrun"], timeout=T)
        settled(pg)
        _no_hscroll(pg)
        over = pg.evaluate("() => [...document.querySelectorAll('.rec button, .rec .recrow b, .rec .recrow span')].filter(e => e.scrollWidth > e.clientWidth + 1).map(e => e.id || e.textContent)")
        assert over == [], over
        _shot(pg, f"laeuft-390-{lang}.png")
        pg.locator("#rpause").click()
        pg.wait_for_selector("#rres", timeout=T)
        expect(pg.locator("#rstt")).to_have_text(words["paused"], timeout=T)
        expect(pg.locator("#rres")).to_have_text(words["resume"], timeout=T)
        pg.locator("#rstop").click()
        pg.wait_for_selector(".uidlg .uibox", timeout=T)
        expect(pg.locator(".uidlg h2")).to_have_text(words["ask"], timeout=T)
        assert pg.evaluate("() => [...document.querySelectorAll('.uidlg .uifoot button')].map(b => b.textContent)") == [words["keep"], words["stop"]]
        pg.locator(".uidlg .uifoot button", has_text=words["stop"]).click()
        pg.wait_for_selector('#rup[data-p="waiting"]', timeout=T)
        expect(pg.locator("#rupt")).to_have_text(words["wait"], timeout=T)
        expect(pg.locator("#rretry")).to_have_text(words["retry"], timeout=T)
        settled(pg)
        _no_hscroll(pg)
        rest = pg.evaluate("""() => [...document.querySelectorAll('.rec *')].filter(e => e.children.length === 0 && e.getBoundingClientRect().width > 0).map(e => e.textContent.trim())
          .filter(t => /\\b(der|die|das|und|nicht|wird|auf|Aufzeichnung|später|Strecke|Dauer|Aufstieg)\\b/.test(t))""")
        assert rest == [], rest
        _shot(pg, f"fertig-390-{lang}.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ---------------------------------------------------------------------------------------------- Seiten der App selbst (assets): Einrichtung und „Server nicht erreichbar“
ASSETS = ROOT / "android/app/src/main/assets"
ASSET_MOCK = """(() => { window._calls = []; window._st = %(state)s;
  window.MTApp = {lang: () => '%(lang)s', version: () => '3.49.0', setServer(u) { window._calls.push('server:' + u); }, changeServer() { window._calls.push('change'); },
    hasPermission: () => %(perm)s, requestPermission() { window._calls.push('perm'); }, status: () => JSON.stringify(window._st),
    startRecording(s, n) { window._calls.push('start:' + s); window._st = {state: 'recording', active_s: 0, dist_m: 0}; }, pauseRecording() { window._st.state = 'paused'; }, resumeRecording() { window._st.state = 'recording'; },
    stopRecording() { window._calls.push('stop'); window._st.state = 'finished'; }}; })()"""


def _asset(pw, name, query="", lang="de", scheme="light", width=390, state=None, perm="true", mock=True):
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": width, "height": 800}, color_scheme=scheme, device_scale_factor=2, reduced_motion="reduce", locale="de-DE")
    if mock:
        ctx.add_init_script(ASSET_MOCK % {"lang": lang, "state": json.dumps(state or {"state": "idle"}), "perm": perm})
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.browser_ = b
    pg.goto((ASSETS / name).as_uri() + query)
    pg.wait_for_selector("h1", timeout=T)
    return pg


@pytest.mark.parametrize("lang,scheme,title,btn", [("de", "light", "Mit dem Server verbinden", "Verbinden"), ("en", "dark", "Connect to the server", "Connect"),
                                                   ("fr", "light", "Se connecter au serveur", "Se connecter"), ("es", "dark", "Conectar con el servidor", "Conectar")])
def test_app_einrichtung(pw, lang, scheme, title, btn):
    pg = _asset(pw, "setup.html", lang=lang, scheme=scheme, width=360)
    try:
        expect(pg.locator("h1")).to_have_text(title, timeout=T)
        expect(pg.locator("button")).to_have_text(btn, timeout=T)
        assert pg.evaluate("() => document.documentElement.lang") == lang and pg.inner_text("#ver") == "App 3.49.0"
        _no_hscroll(pg)
        assert pg.evaluate("() => [...document.querySelectorAll('input, button')].every(e => e.getBoundingClientRect().height >= 48)")
        c = pg.evaluate(CONTRAST, ["h1", "main p", "button", "label", "small"])
        assert len(c) == 5 and all(v >= 4.5 for v in c.values()), c
        pg.locator("button").click()                                    # leer: Hinweis statt stiller Untätigkeit
        assert pg.inner_text("#e") != "" and pg.evaluate("() => window._calls") == []
        pg.fill("#u", "  192.168.178.230  ")
        pg.locator("#u").press("Enter")
        assert pg.evaluate("() => window._calls") == ["server:192.168.178.230"] and pg.inner_text("#e") == ""
        _shot(pg, f"app-einrichtung-360-{scheme}-{lang}.png", full=True)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_app_fehlerseite_mit_aufzeichnung(pw):
    """Server nicht erreichbar: Die Seite nennt die Adresse; eine laufende Aufzeichnung lässt sich auch hier pausieren und (nur mit Rückfrage) beenden."""
    pg = _asset(pw, "error.html", "?u=http%3A%2F%2F192.168.1.5", state={"state": "recording", "active_s": 9252, "dist_m": 8460})
    try:
        expect(pg.locator("h1")).to_have_text("Server nicht erreichbar", timeout=T)
        assert pg.inner_text("#adr") == "http://192.168.1.5" and pg.inner_text("#ver") == "App 3.49.0"
        expect(pg.locator("#rh")).to_have_text("Aufzeichnung läuft", timeout=T)
        assert pg.inner_text("#rt") == "2:34:12" and pg.inner_text("#rd") == "8,46 km"
        assert pg.locator("#rstartbox").is_hidden() and pg.locator("#rrun").is_visible()
        assert pg.evaluate("() => [...document.querySelectorAll('button')].filter(b => b.getBoundingClientRect().width > 0).every(b => b.getBoundingClientRect().height >= 48)")
        _no_hscroll(pg)
        _shot(pg, "app-fehler-laeuft-390-light.png", full=True)
        pg.locator("#rtog").click()
        expect(pg.locator("#rh")).to_have_text("Aufzeichnung pausiert", timeout=T)
        expect(pg.locator("#rtog")).to_have_text("Fortsetzen", timeout=T)
        pg.locator("#rtog").click()
        expect(pg.locator("#rh")).to_have_text("Aufzeichnung läuft", timeout=T)
        pg.locator("#rstop").click()                                    # ein Tipp beendet nicht
        expect(pg.locator("#rask")).to_be_visible(timeout=T)
        assert pg.evaluate("() => [window._st.state, window._calls.length, document.activeElement.id]") == ["recording", 0, "rno"]
        pg.locator("#rno").click()
        expect(pg.locator("#rrun")).to_be_visible(timeout=T)
        pg.locator("#rstop").click()
        pg.locator("#ryes").click()
        expect(pg.locator("#rh")).to_have_text("Aufzeichnung beendet", timeout=T)
        assert pg.evaluate("() => window._calls") == ["stop"] and pg.locator("#rrun").is_hidden() and pg.locator("#rstartbox").is_hidden()
        pg.locator("#chg").click()
        assert pg.evaluate("() => window._calls") == ["stop", "change"] and not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("lang,head,start", [("de", "Aufzeichnen geht auch ohne Server", "Aufzeichnung starten"), ("en", "Recording works without the server too", "Start recording"),
                                             ("fr", "L’enregistrement fonctionne aussi sans serveur", "Démarrer l’enregistrement"), ("es", "También se puede grabar sin servidor", "Iniciar grabación")])
def test_app_fehlerseite_starten_und_sprachen(pw, lang, head, start):
    pg = _asset(pw, "error.html", "?u=https%3A%2F%2Ftouren.example", lang=lang, scheme="dark", width=360, perm="false")
    try:
        expect(pg.locator("#rh")).to_have_text(head, timeout=T)
        expect(pg.locator("#rstart")).to_have_text(start, timeout=T)
        assert pg.locator("#rsport option").count() == 9 and pg.evaluate("() => document.documentElement.lang") == lang
        c = pg.evaluate(CONTRAST, ["h1", "main p", "#retry", "#chg", "#rh", "#rp", "#rstart"])
        assert len(c) == 7 and all(v >= 4.5 for v in c.values()), c
        _no_hscroll(pg)
        pg.locator("#rstart").click()                                   # ohne Berechtigung: erst danach fragen, nichts starten
        assert pg.evaluate("() => [window._calls, window._st.state]") == [["perm"], "idle"] and pg.inner_text("#rp") != ""
        pg.evaluate("() => { MTApp.hasPermission = () => true; window.dispatchEvent(new CustomEvent('mtperm', {detail: true})); }")
        pg.select_option("#rsport", "skitour")
        pg.locator("#rstart").click()
        pg.wait_for_function("() => window._st.state === 'recording' && !document.querySelector('#rrun').hidden", timeout=T)
        assert pg.evaluate("() => window._calls") == ["perm", "start:skitour"]
        _shot(pg, f"app-fehler-360-dark-{lang}.png", full=True)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_app_seiten_ohne_bruecke_und_inhalt():
    """Die Seiten kommen ohne Brücke nicht ins Stolpern (kein Skriptfehler in den Texttabellen) und tragen keine fest eingetragene Version."""
    import re
    for name in ("setup.html", "error.html"):
        src = (ASSETS / name).read_text(encoding="utf8")
        assert 'name="color-scheme"' in src and "prefers-color-scheme:dark" in src and not re.search(r"\d+\.\d+\.\d+(?!\.)", src.replace("192.168.178.230", "")), name
        for lang in ("de:{", "en:{", "fr:{", "es:{"):
            assert lang in src, (name, lang)
        assert ' onclick="' not in src and "eval(" not in src, name          # keine Inline-Handler im Markup


def test_favoriten_und_mehr_359(pw, app):
    """3.59.0: angeboten werden die Favoriten-Aktivitäten (Verwaltung), alle übrigen nach Kategorien unter „Mehr …“; eine dort gewählte Aktivität steht beim nächsten Mal vorn."""
    def put(fav):
        rq = urllib.request.Request(app + "/api/aktivitaeten/favoriten", data=json.dumps({"favoriten": fav}).encode(), method="PUT", headers={"content-type": "application/json"})
        urllib.request.urlopen(rq, timeout=10).read()
    put(["kayak", "snowshoe"])
    pg = _open(pw, app, geo=True)
    try:
        pg.wait_for_selector("#rstart", timeout=T)
        assert pg.eval_on_selector_all(".recsp", "l => l.map(x => x.dataset.sp)") == ["kayak", "snowshoe"]
        expect(pg.locator('.recsp[data-sp="kayak"]')).to_have_text("Kajak/Kanu")
        assert not pg.evaluate("() => document.querySelector('#rspm').open")
        open_details(pg, "#rspm")
        cats = pg.eval_on_selector_all("#rspm .reclbl", "l => l.map(x => x.textContent)")
        assert cats == ["Zu Fuß", "Rad", "Winter", "Wasser", "Outdoor & Sonstige"]
        assert pg.locator('#rspm .recspx[data-sp="kayak"]').count() == 0 and pg.locator('#rspm .recspx[data-sp="skitour"]').count() == 1
        pg.locator('#rspm .recspx[data-sp="mtb_easy"]').click()
        expect(pg.locator('#rspm .recspx[data-sp="mtb_easy"]')).to_have_attribute("aria-checked", "true", timeout=T)
        assert pg.locator('.recsp[aria-checked="true"]').count() == 0
        pg.locator("#rstart").click()
        pg.wait_for_selector("#rstop", timeout=T)
        assert any(c.startswith("start:mtb_easy:") for c in pg.evaluate("() => window._calls"))
        _state(pg, state="idle")
        pg.wait_for_selector("#rstart", timeout=T)
        assert pg.eval_on_selector_all(".recsp", "l => l.map(x => x.dataset.sp)") == ["mtb_easy", "kayak", "snowshoe"]       # zuletzt benutzt: vorn und vorgewählt
        expect(pg.locator(".recsp").first).to_have_attribute("aria-checked", "true")
        assert _small_targets(pg) == []
        _no_hscroll(pg)
        assert not pg.errors, pg.errors
    finally:
        put(["hike", "jogging", "touringbicycle", "skitour", "mtb"])
        pg.browser_.close()
