"""3.71.0 – Umsetzung des Prüfberichts (Browser, Chromium): kein seitliches Überlaufen bei 360/390/430 px hell und dunkel auf den behobenen Seiten, Touch-Ziele am Handy,
Kontrast (WCAG AA) der Farben-Token, klebender Dialogfuß, Deep Link nach der Anmeldung, gemeinsame Fehlerkarte mit Rückweg, Leerzustände, Sicherungs-Banner.
Eigener Server mit den Reisen aus test_reise_seiten_ui plus Touren aus dem Vorjahr (damit „Tempo“ und „Aufstieg pro Stunde“ der Seite „Orte & Ausrüstung“ erscheinen)."""
import json
import os
import socket
import subprocess
import sys
import urllib.request

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.helpers_ui import quiet, settled  # noqa: E402
from tests.test_seitenlayout_ui import ROOT, T, _browser, pw  # noqa: F401, E402
from tests.test_reise_seiten_ui import SEED as SEED_REISEN, TRIPS  # noqa: E402
from tests.test_tourseite_ui import LAUNCH, _wait  # noqa: E402

EXTRA = r"""
import sys, os, time, math; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db, routes
now = int(time.time()); day = 86400
def loop(lat0, lng0, r=0.01, n=60):
    return [(lat0 + r * math.sin(2 * math.pi * i / (n - 1)), lng0 + r * (1 - math.cos(2 * math.pi * i / (n - 1))), 500 + 60 * math.sin(i / 14), i * 40000) for i in range(n)]
for i in range(4):                                    # Touren im Vorjahr: zusammen mit den Touren dieses Jahres entstehen die Leistungsdiagramme
    tid = "v%%d" %% i
    ts = now - (380 + i * 9) * day
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,'t','komoot')", (tid, "Vorjahresrunde %%d" %% i, "hike", ts, ts + 7200, 9000, 7200, 300, 300, 48.0, 11.0))
    routes.store(tid, loop(48.0, 11.0))
"""
WIDTHS = (360, 390, 430)
SCHEMES = ("light", "dark")

# Zeigt Elemente, die rechts über den Bildschirm (oder links hinaus) ragen – ausgenommen eigene seitlich scrollende Leisten, Karten, Diagramme (SVG) und feste Leisten.
OVER = """() => {
  const W = document.documentElement.clientWidth, out = [];
  const scroller = e => { for (let p = e.parentElement; p; p = p.parentElement) { const cs = getComputedStyle(p); if ((cs.overflowX === 'auto' || cs.overflowX === 'scroll') && p.scrollWidth > p.clientWidth) return true; } return false; };
  document.querySelectorAll('main *, .uibox *').forEach(e => {
    const r = e.getBoundingClientRect(), cs = getComputedStyle(e);
    if (!r.width || !r.height || cs.visibility === 'hidden' || cs.display === 'none') return;
    if ((r.right > W + 1 || r.left < -1) && !scroller(e) && !e.closest('.leaflet-container, svg, #tabbar') && cs.position !== 'fixed') out.push(e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + '.' + String(e.className).slice(0, 30) + ' ' + Math.round(r.left) + '-' + Math.round(r.right));
  });
  return {sw: document.documentElement.scrollWidth, W, out: out.slice(0, 8)};
}"""


def _ready(pg):
    pg.wait_for_function("() => document.querySelector('main') && document.querySelector('main').children.length > 0", timeout=T)
    settled(pg)


def _kein_ueberlauf(pg, was):
    m = pg.evaluate(OVER)
    assert m["sw"] <= m["W"] + 1, f"{was}: Seite scrollt seitlich ({m['sw']} > {m['W']})"
    assert not m["out"], f"{was}: ragt über den Rand: {m['out']}"


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("au371")
    data = tmp / "data"
    for code in (SEED_REISEN % {"root": str(ROOT), "data": str(data), "trips": TRIPS}, EXTRA % {"root": str(ROOT), "data": str(data)}):
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
        assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / "launch.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    pr = subprocess.Popen([sys.executable, str(script)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    yield url
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)


def _page(pw, url, h, w, scheme, wait="main"):
    pg = _browser(pw, url, width=w, height=844, scheme=scheme, devs=None)
    pg.goto(f"{url}/#/{h}")
    pg.wait_for_selector(wait, state="attached", timeout=T)
    _ready(pg)
    return pg


# ------------------------------------------------------------------  Welle 1: H-01 … H-05  ------------------------------------------------------------------

@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("w", WIDTHS)
def test_h01_statistik_jahresrueckblick_knopf_nicht_abgeschnitten(pw, app, w, scheme):
    pg = _page(pw, app, "stats", w, scheme, "#stf .years")
    try:
        _kein_ueberlauf(pg, f"stats {w} {scheme}")
        b = pg.locator("#stf .recaplink")
        assert b.count() == 1 and b.get_attribute("href").startswith("#/recap/")
        r = b.bounding_box()
        assert r["x"] >= 0 and r["x"] + r["width"] <= w, r                      # ganz im Bild, nicht in der scrollenden Jahresleiste
        assert pg.evaluate("() => !document.querySelector('.years .recaplink')")
        assert pg.evaluate("() => { const y = document.querySelector('.years'); return y.scrollWidth <= y.clientWidth + 1 || getComputedStyle(y).overflowX === 'auto'; }")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("w", WIDTHS)
def test_h02_orte_leistungsdiagramme_passen_auf_den_bildschirm(pw, app, w, scheme):
    pg = _page(pw, app, "places", w, scheme, "#plb")
    try:
        pg.wait_for_function("() => [...document.querySelectorAll('h2')].some(h => h.textContent.trim() === 'Tempo')", timeout=T)
        settled(pg)
        _kein_ueberlauf(pg, f"places {w} {scheme}")
        for t in ("Tempo", "Aufstieg pro Stunde"):
            r = pg.evaluate("(t) => { const h = [...document.querySelectorAll('h2')].find(h => h.textContent.trim() === t); const p = h.closest('.panel').getBoundingClientRect(); return [p.left, p.right]; }", t)
            assert r[0] >= 0 and r[1] <= w, (t, r)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("w", WIDTHS)
def test_h03_verwaltung_werkseinstellung_knopf_bricht_um(pw, app, w, scheme):
    pg = _page(pw, app, "admin", w, scheme, "#slfacb")
    try:
        _kein_ueberlauf(pg, f"admin {w} {scheme}")
        r = pg.locator("#slfacb").bounding_box()
        assert r["x"] >= 0 and r["x"] + r["width"] <= w, r
        assert pg.evaluate("() => { const b = document.getElementById('slfacb'); return b.scrollWidth <= b.clientWidth + 1; }")      # Text nicht abgeschnitten
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", SCHEMES)
@pytest.mark.parametrize("w", WIDTHS)
def test_h04_reise_erstellen_fuss_klebt_unten(pw, app, w, scheme):
    pg = _page(pw, app, "trips", w, scheme, "#trnew")
    try:
        pg.locator("#trnew").click()
        pg.wait_for_selector("#tcn", timeout=T)
        pg.wait_for_function("() => document.querySelectorAll('#tcl .cb').length > 10", timeout=T)
        box = pg.locator(".uibox").bounding_box()
        for sel in ("#tcok", "#tcno"):                                          # ohne zu scrollen im Bild und im Dialog
            r = pg.locator(sel).bounding_box()
            assert r["y"] >= box["y"] and r["y"] + r["height"] <= box["y"] + box["height"] + 1 and r["y"] + r["height"] <= 844, (sel, r, box)
        assert pg.evaluate("() => { const b = document.querySelector('.uibox'); return b.scrollHeight > b.clientHeight; }")      # der Dialog ist länger als das Fenster – der Fuß klebt trotzdem
        pg.evaluate("() => { const b = document.querySelector('.uibox'); b.scrollTop = b.scrollHeight; }")
        r = pg.locator("#tcok").bounding_box()
        assert r["y"] + r["height"] <= 844
        _kein_ueberlauf(pg, f"reise erstellen {w} {scheme}")
        pg.locator("#tcno").click()
        expect(pg.locator("#tcn")).to_have_count(0, timeout=T)
    finally:
        pg.browser_.close()


def test_h04_weitere_dialoge_haben_klebenden_fuss(pw, app):
    """Gemeinsame Lösung in .uifoot: position sticky in jedem Dialog (Mehrtagestour, Gebiet, Tour hochladen …)."""
    pg = _page(pw, app, "trips", 390, "light", "#trnew")
    try:
        pg.locator("#trnew").click()
        pg.wait_for_selector("#tcn", timeout=T)
        assert pg.evaluate("() => getComputedStyle(document.querySelector('.uibox .uifoot')).position") == "sticky"
        pg.locator("#tcno").click()
        pg.locator("#sbbtn").click()
        pg.wait_for_selector(".uibox .uifoot", timeout=T)
        assert pg.evaluate("() => getComputedStyle(document.querySelector('.uibox .uifoot')).position") == "sticky"
    finally:
        pg.browser_.close()


@pytest.fixture(scope="module")
def app_login(tmp_path_factory):
    """Eigener Server mit Benutzerverwaltung (ein Administrator), damit die Anmeldung erscheint."""
    tmp = tmp_path_factory.mktemp("au371l")
    data = tmp / "data"
    out = subprocess.run([sys.executable, "-c", SEED_REISEN % {"root": str(ROOT), "data": str(data), "trips": TRIPS}], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / "launch.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    pr = subprocess.Popen([sys.executable, str(script)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    req = urllib.request.Request(url + "/api/setup", method="POST", data=json.dumps({"name": "Admin", "password": "geheim-1234", "email": "a@example.org"}).encode(), headers={"Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()
    yield url
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)


@pytest.mark.parametrize("ziel", ["#/tours?g=alpen", "#/trips", "#/stats"])
def test_h05_deep_link_nach_anmeldung_bleibt_erhalten(pw, app_login, ziel):
    pg = _browser(pw, app_login, width=390, height=844, devs=None)
    try:
        pg.goto(f"{app_login}/{ziel}")
        pg.wait_for_selector("#au_n", timeout=T)
        pg.fill("#au_n", "Admin")
        pg.fill("#au_p", "geheim-1234")
        pg.locator(".authbox button[type=submit]").click()
        pg.wait_for_selector("#au_n", state="detached", timeout=T)
        pg.wait_for_function("() => document.querySelector('main') && document.querySelector('main').children.length > 0", timeout=T)
        assert pg.evaluate("() => location.hash") == ziel
        assert pg.evaluate("() => sessionStorage.getItem('mt_after_login')") is None
    finally:
        pg.browser_.close()


def test_h05_ohne_adresse_startseite(pw, app_login):
    pg = _browser(pw, app_login, width=390, height=844, devs=None)
    try:
        pg.goto(app_login + "/")
        pg.wait_for_selector("#au_n", timeout=T)
        pg.fill("#au_n", "Admin")
        pg.fill("#au_p", "geheim-1234")
        pg.locator(".authbox button[type=submit]").click()
        pg.wait_for_selector("#au_n", state="detached", timeout=T)
        pg.wait_for_function("() => location.hash === '#/dash'", timeout=T)
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Welle 2: M-01 … M-14  ------------------------------------------------------------------

def test_m01_m02_fotos_seite_wort_und_mehrzahl(pw, app):
    pg = _page(pw, app, "photos", 390, "light", "main .sec")
    try:
        pg.wait_for_function("() => /Fotos/.test(document.querySelector('main').innerText)", timeout=T)
        txt = pg.locator("main").inner_text()
        assert "Bilder" not in txt and not __import__("re").search(r"\b1 Fotos\b", txt), txt[:400]
        assert pg.evaluate("() => [fmtAnzahl(1, 'Foto', 'Fotos'), fmtAnzahl(0, 'Foto', 'Fotos'), fmtAnzahl(2, 'Foto', 'Fotos'), fmtAnzahl(1, 'Tour', 'Touren')]") == ["1 Foto", "0 Fotos", "2 Fotos", "1 Tour"]
    finally:
        pg.browser_.close()


def test_m01_m02_quelltext_keine_1_fotos_mehr():
    """Kein „${…} Fotos“/„${…} Touren“ mehr ohne fmtAnzahl, wo kein Verb folgt (Einzahl wäre sonst „1 Fotos“)."""
    import re
    from pathlib import Path
    js = Path(ROOT / "app" / "static" / "js")
    bad = []
    for f in sorted(js.glob("*.js")):
        if "i18n" in f.name or f.name == "gebiete-daten.js":
            continue
        for i, line in enumerate(f.read_text(encoding="utf-8").split("\n"), 1):
            for m in re.finditer(r"\$\{[^{}`]+?\} (Fotos|Touren)(?=$|[<,.:;)·\]&–\"`]|\s[·(–|])", line):
                bad.append(f"{f.name}:{i}: {m.group(0)}")
    assert not bad, bad[:10]


def test_m03_schlagwort_feld_heisst_schlagwort(pw, app):
    pg = _page(pw, app, "tour/h0", 390, "light", "#etag")
    try:
        pg.evaluate("() => document.getElementById('etag').click()")
        pg.wait_for_selector("#tgi", timeout=T)
        assert pg.get_attribute("#tgi", "placeholder") == "Neues Schlagwort + Enter"
        pg.locator("#tgx").click()
    finally:
        pg.browser_.close()


def test_m04_dialogknoepfe_abbrechen_links_hauptaktion_rechts(pw, app):
    pg = _page(pw, app, "tour/h0", 390, "light", "#etag")
    try:
        pg.evaluate("() => { const t = BY['h0']; uploadDialog(t); }")
        pg.wait_for_selector("#ucx", timeout=T)
        assert [b.inner_text() for b in pg.locator(".uibox .uifoot .btn").all()] == ["Abbrechen", "Hochladen"]
        pg.locator("#ucx").click()
        pg.evaluate("() => { komootPaketDialog(BY['h0']); }")
        pg.wait_for_selector("#kpx", timeout=T)
        assert [b.inner_text() for b in pg.locator(".uibox .uifoot .btn, .uibox .uifoot a").all()] == ["Abbrechen", "Exportieren"]
        pg.locator("#kpx").click()
        pg.evaluate("() => { seriesBuildDialog(); }")
        pg.wait_for_selector("#sbok", timeout=T)
        assert pg.locator("#sbok").inner_text() == "Speichern"
        pg.locator("#sbno").click()
        assert pg.evaluate("() => { showAuth('setup'); return [...document.querySelectorAll('.authbox .row .btn')].map(b => b.innerText); }") == ["Abbrechen", "Einrichten"]
    finally:
        pg.browser_.close()


def test_m05_loeschen_text_sagt_geloescht_und_sicherung():
    from pathlib import Path
    for f in ("03-tour.js", "09-pruefen.js"):
        t = (ROOT / "app" / "static" / "js" / f).read_text(encoding="utf-8")
        assert "wird in Meine Touren gelöscht" in t and "nur aus einer Sicherung" in t and "aus Meine Touren entfernt" not in t, f


def test_m06_technische_fehler_werden_lesbar():
    from app.fehler import lesbar
    raw = "HTTPSConnectionPool(host='s3.amazonaws.com', port=443): Max retries exceeded with url: /elevation-tiles-prod/skadi/N47/N47E011.hgt.gz (Caused by NameResolutionError(\"<urllib3.connection.HTTPSConnection object at 0x7f>: Failed to resolve\"))"
    assert lesbar(raw) == "Geländemodell nicht erreichbar (kein Internet?)"
    assert lesbar("Wetterdienst nicht erreichbar: ConnectionError") == "Wetterdienst nicht erreichbar (kein Internet?)"
    assert lesbar("Gebietssuche nicht möglich: " + raw.replace("s3.amazonaws.com", "nominatim.openstreetmap.org")) == "Gebietssuche nicht möglich: Ortssuche nicht erreichbar (kein Internet?)"
    assert lesbar("KeyError: 'x'") == "Unerwarteter Fehler im Server. Bitte noch einmal versuchen."
    for ok in ("Tour nicht gefunden", "Komoot: Anmeldung fehlgeschlagen", "Das Passwort braucht mindestens 8 Zeichen.", ""):
        assert lesbar(ok) == ok


def test_m06_server_gibt_keine_rohen_ausnahmen_aus(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    from app.main import app
    def _net():
        raise HTTPException(502, "HTTPSConnectionPool(host='s3.amazonaws.com', port=443): Max retries exceeded with url: /x")
    def _boom():
        raise RuntimeError("kaputt <object at 0x1>")
    for pfad, fn in (("/api/_audit371_net", _net), ("/api/_audit371_boom", _boom)):
        app.add_api_route(pfad, fn, methods=["GET"])
        app.router.routes.insert(0, app.router.routes.pop())                                # vor die Datei-Auslieferung (Mount „/“)
    c = TestClient(app, raise_server_exceptions=False)
    r = c.get("/api/_audit371_net")
    assert r.status_code == 502 and r.json()["detail"] == "Geländemodell nicht erreichbar (kein Internet?)"
    r = c.get("/api/_audit371_boom")
    assert r.status_code == 500 and r.json()["detail"] == "Unerwarteter Fehler im Server. Bitte noch einmal versuchen." and "kaputt" not in r.text


@pytest.mark.parametrize("scheme", SCHEMES)
def test_m06_fehlerdialog_mit_wiederholen(pw, app, scheme):
    pg = _page(pw, app, "dash", 390, scheme)
    try:
        pg.evaluate("() => { window.__n = 0; uiRetry({vorgang: 'Höhe korrigieren', text: 'Geländemodell nicht erreichbar (kein Internet?)', retry: () => { window.__n++; }}); }")
        pg.wait_for_selector(".uibox", timeout=T)
        assert pg.locator(".uibox h2").inner_text() == "Höhe korrigieren nicht möglich"
        assert [b.inner_text() for b in pg.locator(".uibox .uifoot .btn").all()] == ["Schließen", "Noch einmal versuchen"]
        pg.locator(".uibox .uifoot .btn").nth(1).click()
        pg.wait_for_function("() => window.__n === 1", timeout=T)
        pg.evaluate("() => { uiAlert('Umbenennen nicht möglich: Name fehlt'); }")
        pg.wait_for_selector(".uibox", timeout=T)
        assert pg.locator(".uibox h2").inner_text() == "Umbenennen nicht möglich"           # nicht der allgemeine Titel „Hinweis“
    finally:
        pg.browser_.close()


# Seiten, auf denen am Handy alles Antippbare mindestens 44 px groß sein muss (gleiche Ausnahmen wie im Prüfbericht: Text-Links im Fließtext)
SMALL = """() => {
  const out = [], vis = e => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  document.querySelectorAll('a[href],button,input:not([type=hidden]),select,textarea,summary,[role=button]').forEach(e => {
    if (!vis(e) || e.disabled || e.closest('.leaflet-container, .maplibregl-map')) return;
    if (e.matches('input[type=checkbox],input[type=radio]') && e.closest('label')) { const l = e.closest('label').getBoundingClientRect(); if (l.height >= 44 && l.width >= 44) return; }
    if (e.tagName === 'A' && e.closest('p,li,.mut') && e.parentElement && e.parentElement.childNodes.length > 1 && getComputedStyle(e).display === 'inline') return;
    const r = e.getBoundingClientRect();
    if (r.height < 43.5 || r.width < 43.5) out.push(e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + '.' + String(e.className).slice(0, 24) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' ' + (e.innerText || e.getAttribute('aria-label') || '').trim().slice(0, 20));
  });
  return out;
}"""
SEITEN = ["dash", "stats", "tours", "tour/s0", "trips", "areas", "photos", "records", "places", "admin", "check"]


@pytest.mark.parametrize("w", (360, 390, 430))
def test_m07_touch_ziele_am_handy(pw, app, w):
    pg = _browser(pw, app, width=w, height=844, devs=None)
    try:
        for h in SEITEN:
            pg.goto(f"{app}/#/{h}")
            pg.wait_for_selector("main", timeout=T)
            _ready(pg)
            kl = pg.evaluate(SMALL)
            assert not kl, f"{h} {w}: {kl[:6]}"
    finally:
        pg.browser_.close()


CONTRAST_JS = """() => {
  const cv = document.createElement('canvas').getContext('2d', {willReadFrequently: true});
  const rgb = s => { cv.clearRect(0, 0, 1, 1); cv.fillStyle = '#000'; cv.fillStyle = s; cv.fillRect(0, 0, 1, 1); return [...cv.getImageData(0, 0, 1, 1).data].slice(0, 3); };
  const lum = c => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2]); };
  const cr = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
  const col = cls => { const e = document.createElement('span'); e.className = cls; e.textContent = 'x'; document.getElementById('main').appendChild(e); const c = getComputedStyle(e).color; e.remove(); return rgb(c); };
  const bg = rgb(getComputedStyle(document.body).backgroundColor), card = rgb(getComputedStyle(document.documentElement).getPropertyValue('--card') || '#fff');
  return {ok: Math.min(cr(col('ok'), bg), cr(col('ok'), card)), bad: Math.min(cr(col('bad'), bg), cr(col('bad'), card)), stars: cr(col('stars'), bg)};
}"""


@pytest.mark.parametrize("scheme", SCHEMES)
def test_m08_kontrast_ok_bad_sterne(pw, app, scheme):
    pg = _page(pw, app, "stats", 390, scheme)
    try:
        r = pg.evaluate(CONTRAST_JS)
        assert r["ok"] >= 4.5 and r["bad"] >= 4.5, r
        assert r["stars"] >= 3, r                                                            # Sterne sind Zeichen: Nicht-Text-Kontrast 3 : 1
    finally:
        pg.browser_.close()


def test_m08_sport_etikett_kontrast_aller_katalogfarben():
    """Weiße Schrift auf der um 30 % abgedunkelten Sportartfarbe (.tag): mindestens 4,5 : 1 für jede Farbe aus style.css."""
    import re
    css = (ROOT / "app" / "static" / "style.css").read_text(encoding="utf-8")
    assert re.search(r"\.tag\{box-shadow:inset 0 0 0 999px rgba\(0,0,0,\.3\)\}", css)
    cols = dict(re.findall(r"--((?:sp-[\w]+|hike|bike|ebike|ski|snow|run|other|water)):(#[0-9a-fA-F]{6})", css))
    assert len(cols) > 20

    def lum(h):
        c = [int(h[i:i + 2], 16) * .7 / 255 for i in (1, 3, 5)]
        f = lambda v: v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4
        return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2])
    for n, h in cols.items():
        assert 1.05 / (lum(h) + .05) >= 4.5, (n, h)


@pytest.mark.parametrize("h,titel,zurueck", [("tour/nix", "Tour nicht gefunden", "Alle Touren"), ("trip/nix", "Reise nicht gefunden", "Alle Reisen"),
                                             ("area/nix", "Gebiet nicht gefunden", "Alle Gebiete"), ("compare?a=x&b=y", "Touren zum Vergleichen nicht gefunden", "Alle Touren"),
                                             ("tour/nix/auswertung", "Tour nicht gefunden", "Alle Touren")])
def test_m09_fehlerkarte_mit_rueckweg(pw, app, h, titel, zurueck):
    pg = _page(pw, app, h, 390, "light", "#main .errcard")
    try:
        assert pg.locator("#main .errcard h2").inner_text() == titel
        assert pg.locator("#main .errcard .btn").first.inner_text() == "‹ " + zurueck
        assert pg.locator("#main .errcard a[href='#/dash']").inner_text() == "Zur Übersicht"
        pg.locator("#main .errcard .btn").first.click()
        pg.wait_for_function("() => /^#\\/(tours|trips|areas)/.test(location.hash)", timeout=T)
        _kein_ueberlauf(pg, h)
    finally:
        pg.browser_.close()


def test_m09_serverfehler_hat_wiederholen(pw, app):
    pg = _browser(pw, app, width=390, height=844, devs=None)
    try:
        n = {"c": 0}
        def fail(r):
            n["c"] += 1
            r.fulfill(status=500, json={"detail": "Unerwarteter Fehler im Server. Bitte noch einmal versuchen."})
        pg.route("**/api/trips", fail)
        pg.goto(f"{app}/#/trips")
        pg.wait_for_selector("#main .errcard [data-errretry]", timeout=T)
        assert "Unerwarteter Fehler" in pg.locator("#main .errcard p").first.inner_text()
        pg.unroute("**/api/trips")
        pg.locator("[data-errretry]").click()
        pg.wait_for_selector("#rsx #tls-reisen", state="attached", timeout=T)
    finally:
        pg.browser_.close()


@pytest.fixture(scope="module")
def app_leer(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("au371e")
    data = tmp / "data"
    data.mkdir()
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / "launch.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    pr = subprocess.Popen([sys.executable, str(script)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    yield url
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)


@pytest.mark.parametrize("h", ["dash", "tours", "map", "stats", "records", "places"])
def test_m10_leerer_bestand_ueberall_dieselbe_karte(pw, app_leer, h):
    pg = _browser(pw, app_leer, width=390, height=844, devs=None)
    try:
        pg.goto(f"{app_leer}/#/{h}")
        pg.wait_for_selector("#main .empty h2", timeout=T)
        assert pg.locator("#main .empty h2").inner_text() == "Noch keine Touren"
        assert pg.locator("#main .empty h2").count() == 1 and pg.locator("#main .warnbar, .wbar").count() == 0
        assert pg.locator("#main #tl, #main .filters, #main .mapbox").count() == 0              # keine leeren Filter, keine leere Karte
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("lang,erwartet", [("en", "You can import Zepp workouts"), ("fr", "Vous pouvez importer des entraînements Zepp"), ("es", "Puedes importar entrenamientos de Zepp")])
def test_m10_leerer_bestand_uebersetzt(pw, app_leer, lang, erwartet):
    """3.71.1: Die gemeinsame Leerzustands-Karte hat keinen deutschen Restsatz (der Text wurde in Sätze ohne Verknüpfung im Satz zerlegt, damit er übersetzt wird)."""
    pg = _browser(pw, app_leer, width=390, height=844, devs=None)
    try:
        pg.add_init_script("try { localStorage.setItem('lang', %r); } catch (e) {}" % lang)
        pg.goto(f"{app_leer}/#/dash")
        pg.reload()
        pg.wait_for_selector("#main .empty h2", timeout=T)
        pg.wait_for_function("t => document.querySelector('#main .empty').innerText.includes(t)", arg=erwartet, timeout=T)
        t = pg.locator("#main .empty").inner_text()
        assert "Zepp-Trainings" not in t and "kannst" not in t and "Verwaltung" not in t, t
    finally:
        pg.browser_.close()


def test_m10_leere_reisen_formulierung(pw, app_leer):
    pg = _browser(pw, app_leer, width=390, height=844, devs=None)
    try:
        pg.goto(f"{app_leer}/#/trips")
        pg.wait_for_function("() => /Noch keine Reisen erkannt/.test(document.querySelector('main').innerText)", timeout=T)
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("w,scheme", [(360, "light"), (390, "dark"), (430, "light")])
def test_m11_sicherungs_banner_kompakt(pw, app, w, scheme):
    pg = _browser(pw, app, width=w, height=844, scheme=scheme, devs=None)
    try:
        pg.route("**/api/backup/waechter", lambda r: r.fulfill(json={"zeige": True, "art": "keine", "grund": "", "alter_tage": None, "datum": None, "schwelle": 7, "ausblendbar": True}))
        pg.goto(f"{app}/#/dash")
        pg.wait_for_selector("#wbar", timeout=T)
        settled(pg)
        h = pg.evaluate("() => document.getElementById('wbar').getBoundingClientRect().height")
        assert h <= 64, h                                                                    # vorher ca. 100 px (drei Zeilen und zwei Knöpfe untereinander)
        assert pg.locator("#wbhide").inner_text() == "Später" and pg.locator("#wbgo").inner_text() == "Jetzt sichern"
        assert pg.locator("#wbar .wbk").is_visible() and not pg.locator("#wbar .wbl").is_visible()
        _kein_ueberlauf(pg, "banner")
        pg.goto(f"{app}/#/admin")                                                           # in der Verwaltung steht dieselbe Meldung schon im Abschnitt „Zustand“
        pg.wait_for_selector("#atabs", timeout=T)
        pg.wait_for_function("() => !document.getElementById('wbar')", timeout=T)
    finally:
        pg.browser_.close()


def test_m12_aufzeichnen_im_browser_verweist_auf_die_verwaltung(pw, app):
    pg = _page(pw, app, "record", 390, "light", "#main .panel")
    try:
        t = pg.locator("#main .panel").inner_text()
        assert "README" not in t and "Verwaltung → Handy & App" in t
        assert pg.locator("#main .panel a[href='#/admin']").count() == 1
    finally:
        pg.browser_.close()


def test_m13_keine_401_im_einzelbetrieb(pw, app):
    pg = _browser(pw, app, width=390, height=844, devs=None)
    try:
        bad = []
        pg.on("response", lambda r: bad.append(f"{r.status} {r.url}") if r.status in (401, 403) else None)
        for h in ("admin", "account", "admin?tab=auto", "admin?tab=sicher"):
            pg.goto(f"{app}/#/{h}")
            pg.wait_for_selector("main", timeout=T)
            _ready(pg)
        assert not bad, bad
    finally:
        pg.browser_.close()


# ---------------------------------------------------------------- Welle 3 (N-Funde)
def test_n01_n02_n04_beschriftungen_und_orientierung(pw, app):
    pg = _browser(pw, app, width=390, height=844, devs=None)
    try:
        pg.goto(f"{app}/#/tours")
        pg.wait_for_selector("#so", timeout=T)
        _ready(pg)
        pg.wait_for_timeout(200)
        r = pg.evaluate("""() => ({
          so: document.getElementById('so').getAttribute('aria-label'),
          fy: document.getElementById('fy') && document.getElementById('fy').getAttribute('aria-label'),
          gs: document.getElementById('gs') && document.getElementById('gs').getAttribute('aria-label'),
          tab: document.getElementById('tabbar').getAttribute('aria-label'),
          nav: document.getElementById('nav').getAttribute('aria-label'),
          noalt: document.querySelectorAll('img:not([alt])').length,
          skip: !!document.querySelector('a.skip'), main: document.getElementById('main').tabIndex})""")
        assert r["so"] and r["gs"] and r["tab"] and r["nav"], r
        assert r["fy"], r
        assert r["noalt"] == 0 and r["skip"] and r["main"] == -1, r
        pg.focus("a.skip")
        pg.keyboard.press("Enter")
        assert pg.evaluate("location.hash").startswith("#/tours")          # Sprunglink ändert die Adresse nicht
        assert pg.evaluate("document.activeElement.id") == "main"
    finally:
        pg.browser_.close()


def test_n03_sterne_einzahl():
    src = open(os.path.join(ROOT, "app/static/js/26-tagebuch.js"), encoding="utf-8").read()
    assert '"Sterne" : "Stern"' in src


def test_n06_ansichten_knopf_oeffnet_bei_einer_ansicht_direkt_den_dialog(pw, app):
    pg = _browser(pw, app, width=390, height=844, devs=None)
    try:
        pg.goto(f"{app}/#/dash")
        pg.wait_for_selector("#slviews", timeout=T)
        _ready(pg)
        n = pg.evaluate("document.getElementById('slview') ? document.getElementById('slview').options.length : 0")
        pg.click("#slviews")
        if n <= 1:
            pg.wait_for_selector(".sldlg", timeout=T)
            assert not pg.query_selector("#slvmenu")
        else:
            pg.wait_for_selector("#slvmenu", timeout=T)
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("w", (360, 430))
def test_n07_admin_tabs_umbrechen_am_handy(pw, app, w):
    pg = _browser(pw, app, width=w, height=844, devs=None)
    try:
        pg.goto(f"{app}/#/admin")
        pg.wait_for_selector(".atabs", timeout=T)
        _ready(pg)
        r = pg.evaluate("""() => { const t = document.querySelector('.atabs'); return {sw: t.scrollWidth, cw: t.clientWidth, dw: document.documentElement.scrollWidth, iw: innerWidth}; }""")
        assert r["sw"] <= r["cw"] + 1 and r["dw"] <= r["iw"] + 1, r
    finally:
        pg.browser_.close()


# ---------------------------------------------------------------- Welle 4 (Optimierung)
def test_o_suche_begrenzt_zeilen_und_mehr_anzeigen(pw, app):
    pg = _browser(pw, app, width=390, height=844, devs=None)
    try:
        pg.goto(f"{app}/#/dash")
        pg.wait_for_selector("main", timeout=T)
        _ready(pg)
        n = pg.evaluate("""() => { const b = TOURS[0]; for (let i = 0; i < 450; i++) TOURS.push(Object.assign({}, b, {id: 'x' + i, name: 'Zzyzx ' + i})); return TOURS.length; }""")
        pg.evaluate("location.hash = '#/search?q=Zzyzx'")
        pg.wait_for_selector(".smore button", timeout=T)
        assert pg.evaluate("document.querySelectorAll('#stl .tr, #stl > *').length") <= 210
        assert "200 von 450" in pg.inner_text(".smore")
        pg.click(".smore button")
        assert "400 von 450" in pg.inner_text(".smore")
        pg.click(".smore button")
        assert pg.query_selector(".smore") is None
        assert pg.evaluate("document.getElementById('stl').children.length") == 450
    finally:
        pg.browser_.close()
