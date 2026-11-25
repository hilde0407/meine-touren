"""3.47.0 Planung ausbauen (Oberfläche, Chromium): Abschnitte „Notizen & Quellen“ und „Passt die Tour zu mir?“ auf der Planseite, Links anlegen/ändern/löschen, Planliste-Marken,
Desktop 1280 und 390 px, hell und dunkel, vier Sprachen, kein horizontales Scrollen. Synchronisation nur über wait_for_function (Pfeilfunktionen) und expect(..., timeout=15000); keine festen Pausen.
Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import json
import os
import re
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from urllib.parse import urlparse
from pathlib import Path

import pytest
from tests.helpers_ui import quiet, set_lang  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
pw_api = pytest.importorskip("playwright.sync_api")
expect = pw_api.expect
TL = 15000

SEED = """
import sys, os; sys.path.insert(0, {root!r}); os.environ['DATA_DIR'] = {data!r}
import time
from app import db, routes
db.init()
now = int(time.time())
for i in range(8):                                    # längste: 17 km mit 1.000 m
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
               ('h%d' % i, 'Wanderung %d' % i, 'hike', now - (10 + 7 * i) * 86400, now - (10 + 7 * i) * 86400 + 100, (10 + i) * 1000, 3.0 * 3600, 300 + 100 * i, 300 + 100 * i, 48.0, 8.0, 'tour_recorded', 'komoot'))
PTS = [(48.0 + 0.001 * i, 8.0 + 0.0005 * i) for i in range(60)]
db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES('lauf','Gipfelrunde gelaufen','hike',?,?,?,?,?,?,48.0,8.0,'tour_recorded','komoot')",
           (now - 2 * 86400, now - 2 * 86400 + 100, 6900, 1.7 * 3600, 190, 190))
routes.store('lauf', [(a, b, 500.0, i * 1000) for i, (a, b) in enumerate(PTS)])
"""


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    return p


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    d = tmp_path_factory.mktemp("ph347")
    data, bak = d / "data", d / "bak"
    out = subprocess.run([sys.executable, "-c", SEED.format(root=str(ROOT), data=str(data))], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr
    port = _free_port()
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(d / "p"), BACKUP_DIR=str(bak))
    pr = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/api/version", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
    yield {"url": url, "data": data, "bak": bak}
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


def _req(app, path, method="GET", body=None):
    r = urllib.request.Request(app["url"] + path, method=method, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=20) as x:
        return json.loads(x.read() or b"{}")


def _page(pw, app, width=1280, height=1000, scheme="light", locale="de-DE"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale=locale, viewport={"width": width, "height": height}, color_scheme=scheme, reduced_motion="reduce")
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(app["url"]) else r.continue_())
    pg.browser_ = b

    def elev(r):                                           # Höhen für genau die gesendeten Punkte: Aufstieg 800 m
        pts = json.loads(r.request.post_data)["points"]
        n = len(pts)
        ele = [500 + 800 * i / max(1, n - 1) for i in range(n)]
        r.fulfill(json={"ele": ele, "up": 800, "down": 20, "max": 1300, "min": 500})
    pg.route("**/api/plan/elevation", elev)
    pg.route("**/api/plan/route", lambda r: r.fulfill(status=502, json={"detail": "kein Routing im Test"}))
    return pg


def _shot(pg, name):
    d = os.environ.get("TS_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        _ruhe(pg)
        pg.screenshot(path=str(Path(d) / name), full_page=True, timeout=60000)


def _ruhe(pg):
    """Netzwerk-Ruhe abwarten (die Karte fragt gelegentlich weiter Kacheln an, die im Test abgebrochen werden): nach 8 s trotzdem weiter, die Layoutmessung folgt danach."""
    try:
        quiet(pg, 5000)
    except Exception:
        pass
    pg.wait_for_function("() => document.readyState === 'complete'", timeout=TL)


def _line(n, dlat):
    return [[48.0 + dlat * i, 8.0 + 0.0005 * i] for i in range(n)]


def _new_plan(app, name, pts, km, sport="hike", est=2.0):
    return _req(app, "/api/plans", "POST", {"name": name, "sport": sport, "pts": pts, "km": km, "up": 800, "down": 800, "est_h": est})["id"]


def _no_hscroll(pg):
    return pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")


def _contrast(pg, sel):
    """Kontrast Text/Hintergrund (WCAG) eines Elements; Farben über ein Canvas normalisiert (auch color-mix)."""
    return pg.evaluate("""(sel) => {
      const el = document.querySelector(sel), cs = getComputedStyle(el);
      const rgb = c => { const x = document.createElement('canvas').getContext('2d'); x.fillStyle = '#000'; x.fillStyle = c; x.fillRect(0, 0, 1, 1); return [...x.getImageData(0, 0, 1, 1).data]; };
      const lum = ([r, g, b]) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
      const a = lum(rgb(cs.color)), b = lum(rgb(cs.backgroundColor));
      return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    }""", sel)


def _admin(pg, app):
    """Verwaltung, Reiter „Sicherung & Zugang“: der Reiter wird ausdrücklich gewählt (nicht auf die Adresse verlassen), dann auf den Knopf gewartet."""
    pg.goto(app["url"] + "#/admin?tab=sicher")
    pg.wait_for_function("() => !!document.querySelector('#atabs [data-t=sicher]') && !!document.querySelector('#bkchk')", timeout=TL)
    t = pg.evaluate("() => document.querySelector('#bkchk').closest('.atab').dataset.t")          # in anderen Sprachen ordnet die Verwaltung die Karte einem anderen Reiter zu
    pg.click(f"#atabs [data-t={t}]")
    expect(pg.locator("#bkchk")).to_be_visible(timeout=TL)


def _open_plan_page(pg, app, pid=None):
    pg.goto(app["url"] + ("#/plan/%s" % pid if pid else "#/plan"))
    pg.wait_for_function("() => !!document.querySelector('#pn')", timeout=TL)


# ------------------------------------------------------------------  Hilfsfunktionen  ------------------------------------------------------------------
def _shot(pg, name):
    d = os.environ.get("TS_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        _ruhe(pg)
        pg.screenshot(path=str(Path(d) / name), full_page=True, timeout=60000)


def _sauber(app):
    for p in _req(app, "/api/plans"):
        _req(app, f"/api/plans/{p['id']}", "DELETE")


LINKS = [{"titel": "Warndienst Testland", "url": "https://lawine.example/bericht?tag=1", "art": "wetter"},
         {"titel": "Wanderführer Seite 12", "url": "https://fuehrer.example/s12", "art": "fuehrer"}]


def _plan(app, name="Lange Runde", km=19.0, est=4.0, sport="hike", **kw):
    d = {"name": name, "sport": sport, "pts": [[48.0 + 0.0017 * i, 8.0 + 0.0005 * i] for i in range(100)], "km": km, "up": 800, "down": 800, "est_h": est, "note": "Anfahrt mit dem Zug\nEinkehr unterwegs", "links": LINKS,
         "quelle": "outdooractive", "quelle_text": "Tour 4711"}
    d.update(kw)
    return _req(app, "/api/plans", "POST", d)["id"]


def _open(pg, app, pid):
    pg.goto(app["url"] + f"#/plan/{pid}")
    pg.wait_for_function("() => !!document.querySelector('#pn') && !!document.querySelector('#pnq')", timeout=TL)


# ------------------------------------------------------------------  Abschnitte  ------------------------------------------------------------------
def test_abschnitte_desktop_mobil_hell_dunkel(pw, app):
    _sauber(app)
    pid = _plan(app)
    for width, scheme, tag in ((1280, "light", "d-hell"), (1280, "dark", "d-dunkel"), (390, "light", "m-hell"), (390, "dark", "m-dunkel")):
        pg = _page(pw, app, width=width, scheme=scheme)
        try:
            _open(pg, app, pid)
            expect(pg.locator("#phsum")).to_contain_text("Tageslicht: Rückkehr vor Sonnenuntergang", timeout=TL)
            expect(pg.locator("#phsum")).to_contain_text("Form:")
            body = pg.locator("#phb")
            expect(body).to_contain_text("Orientierung, keine Sicherheitsgarantie.")
            expect(body).to_contain_text("Wetter, Lawinenlage und Gelände selbst prüfen.")
            expect(body).to_contain_text("Sonnenaufgang")
            expect(body).to_contain_text("Geschätzte Dauer")                          # Form-Zeilen mit Zahlen
            expect(body).to_contain_text("Strecke 19,0 km")
            w = body.locator("a[href^='https://lawine.example/']")
            expect(w).to_have_count(1)
            assert w.get_attribute("target") == "_blank" and "noopener" in w.get_attribute("rel") and "noreferrer" in w.get_attribute("rel")
            assert "Wanderführer Seite 12" not in body.inner_text()                           # nur Wetter/Lawinenbericht
            assert "✓" in pg.inner_text("#phsum")                                              # Symbol zusätzlich zur Farbe
            # Notizen & Quellen
            expect(pg.locator("#pnote")).to_have_value("Anfahrt mit dem Zug\nEinkehr unterwegs")
            expect(pg.locator("#pquelle")).to_have_value("outdooractive")
            expect(pg.locator("#pqtext")).to_have_value("Tour 4711")
            expect(pg.locator("#plinks li")).to_have_count(2)
            expect(pg.locator("#pnqsum")).to_contain_text("Notiz")
            expect(pg.locator("#pnqsum")).to_contain_text("2 Links")
            # einklappbar
            for sel, inner in (("#philfe", "#phb"), ("#pnq", "#pnote")):
                pg.evaluate("(s) => { document.querySelector(s).open = false; }", sel)
                expect(pg.locator(inner)).to_be_hidden(timeout=TL)
                pg.evaluate("(s) => { document.querySelector(s).open = true; }", sel)
                expect(pg.locator(inner)).to_be_visible(timeout=TL)
            _ruhe(pg)
            assert _no_hscroll(pg)
            assert _contrast(pg, "#phsum .pcs") >= 4.5 and _contrast(pg, "#phb .pcst") >= 4.5
            assert pg.get_attribute("#phb", "aria-live") == "polite" and pg.get_attribute("#pnote", "aria-label")
            _shot(pg, f"planhilfe-{tag}.png")
            assert not pg.errors, pg.errors
        finally:
            pg.browser_.close()


def test_entscheidungshilfe_datum_start_puffer(pw, app):
    _sauber(app)
    pid = _plan(app, est=4.0)
    pg = _page(pw, app)
    try:
        _open(pg, app, pid)
        expect(pg.locator("#phsum")).to_contain_text("Rückkehr vor Sonnenuntergang", timeout=TL)
        expect(pg.locator("#phb")).to_contain_text("Start 09:00 Uhr, geschätzte Dauer 4:00 Std., Puffer 48 Min. (20 %): Rückkehr gegen 13:48 Uhr")
        pg.fill("#phs", "20:00")
        pg.fill("#php", "50")
        expect(pg.locator("#phsum")).to_contain_text("Tageslicht: nach Sonnenuntergang", timeout=TL)
        expect(pg.locator("#phb")).to_contain_text("Puffer 2:00 Std. (50 %): Rückkehr gegen 02:00 Uhr am Folgetag")
        expect(pg.locator("#phb .pcst")).to_contain_text("nach Sonnenuntergang")
        assert "⚠" in pg.inner_text("#phb .pcst")
        assert _req(app, f"/api/plans/{pid}")["plan_start"] is None                           # Vorschau speichert nichts
        pg.fill("#phd", "2026-06-21")
        expect(pg.locator("#phb")).to_contain_text("Sonnenaufgang 05:", timeout=TL)
        pg.click("#psave")
        expect(pg.locator("#pmsg")).to_contain_text("gespeichert", timeout=TL)
        p = _req(app, f"/api/plans/{pid}")
        assert (p["plan_start"], p["puffer_pct"], p["plan_datum"]) == ("20:00", 50, "2026-06-21")
        pg.fill("#php", "150")                                                                   # ungültig: Meldung statt Scheinwerte
        expect(pg.locator("#phb")).to_contain_text("nicht möglich", timeout=TL)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_zu_wenig_vergleichstouren_und_ungespeichert(pw, app):
    _sauber(app)
    pid = _plan(app, name="Radrunde", sport="racebike", links=[])
    pg = _page(pw, app)
    try:
        _open(pg, app, pid)
        expect(pg.locator("#phsum")).to_contain_text("Form: zu wenig Vergleichstouren", timeout=TL)
        expect(pg.locator("#phb")).to_contain_text("Zu wenig Vergleichstouren: 0 Touren dieser Sportart in den letzten 12 Monaten, nötig sind mindestens 5.")
        txt = pg.inner_text("#phb")
        assert "Median" not in txt and "Länger als" not in txt
        expect(pg.locator("#phb")).to_contain_text("Noch keine Quelle für Wetter oder Lawinenbericht gespeichert")
        # neue, ungespeicherte Planung: Hinweis statt Zahlen
        pg.click("#pclr")
        expect(pg.locator("#philfe")).to_be_hidden(timeout=TL)
        pg.evaluate("() => { document.querySelector('#pg').dispatchEvent(new Event('change')); }")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_ungespeicherte_planung_zeigt_hinweis(pw, app):
    _sauber(app)
    pg = _page(pw, app)
    try:
        pg.goto(app["url"] + "#/plan")
        pg.wait_for_function("() => !!document.querySelector('#pg')", timeout=TL)
        gpx = '<?xml version="1.0"?><gpx version="1.1"><trk><trkseg>' + "".join(f'<trkpt lat="{48 + 0.002 * i}" lon="{8 + 0.001 * i}"></trkpt>' for i in range(30)) + "</trkseg></trk></gpx>"
        pg.set_input_files("#pg", {"name": "t.gpx", "mimeType": "application/gpx+xml", "buffer": gpx.encode()})
        expect(pg.locator("#philfe")).to_be_visible(timeout=TL)
        expect(pg.locator("#phb")).to_contain_text("Speichere die Planung, dann erscheint hier die Entscheidungshilfe.")
        pg.fill("#pn", "Aus Datei")
        pg.click("#pladd")
        pg.fill("#plu", "https://karte.example/x")
        pg.fill("#plt", "Karte")
        pg.click("#plok")
        expect(pg.locator("#plinks li")).to_have_count(1)
        pg.click("#psave")
        expect(pg.locator("#pmsg")).to_contain_text("gespeichert", timeout=TL)
        expect(pg.locator("#phsum")).to_contain_text("Tageslicht:", timeout=TL)             # nach dem Speichern rechnet die Hilfe
        assert _req(app, "/api/plans")[0]["n_links"] == 1
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Links  ------------------------------------------------------------------
def test_links_anlegen_aendern_loeschen(pw, app):
    _sauber(app)
    pid = _plan(app, links=[])
    for width, scheme, tag in ((1280, "light", "d-hell"), (390, "dark", "m-dunkel")):
        _req(app, "/api/plans", "POST", {"id": pid, "name": "Lange Runde", "pts": [[48.0, 8.0], [48.1, 8.1]], "links": []})
        pg = _page(pw, app, width=width, scheme=scheme)
        angefragt = []
        pg.on("request", lambda r: angefragt.append(r.url) if (urlparse(r.url).hostname or "").endswith(".example") else None)
        try:
            _open(pg, app, pid)
            expect(pg.locator("#plinks li")).to_have_count(0)
            # anlegen: ungültige Adresse wird abgewiesen, Abbrechen verwirft
            pg.click("#pladd")
            dlg = pg.locator(".uimod .uibox")
            expect(dlg).to_be_visible(timeout=TL)
            pg.fill("#plu", "javascript:alert(1)")
            pg.click("#plok")
            expect(pg.locator("#plerr")).to_contain_text("http:// oder https://", timeout=TL)
            assert pg.locator("#plinks li").count() == 0
            b1, b2 = pg.locator("#plx").bounding_box(), pg.locator("#plok").bounding_box()
            assert pg.evaluate("() => [...document.querySelectorAll('.uimod .uifoot .btn')].map(b => b.id)") == ["plx", "plok"]     # Reihenfolge wie 3.42.0
            if width > 420:
                assert b1["x"] < b2["x"] and abs(b1["y"] - b2["y"]) < 6                          # Abbrechen links, Hauptknopf rechts
            else:
                assert b1["y"] > b2["y"]                                                         # Handy: Hauptknopf oben, Abbrechen darunter (column-reverse wie alle Fenster)
            _shot(pg, f"planhilfe-linkdialog-{tag}.png")
            pg.click("#plx")
            expect(dlg).to_have_count(0, timeout=TL)
            assert pg.locator("#plinks li").count() == 0
            # anlegen: gültig
            pg.click("#pladd")
            pg.fill("#plt", "Wetter Testtal")
            pg.fill("#plu", "https://wetter.example/testtal")
            pg.select_option("#pla", "wetter")
            pg.click("#plok")
            expect(dlg).to_have_count(0, timeout=TL)
            li = pg.locator("#plinks li")
            expect(li).to_have_count(1)
            a = li.locator("a.plkt")
            assert a.get_attribute("href") == "https://wetter.example/testtal" and a.get_attribute("target") == "_blank" and a.get_attribute("rel") == "noopener noreferrer"
            expect(li).to_contain_text("Wetter/Lawinenbericht")
            expect(pg.locator("#pnqsum")).to_contain_text("1 Link")
            assert _req(app, f"/api/plans/{pid}")["links"] == []                                  # erst „Plan speichern“ sichert
            pg.click("#psave")
            expect(pg.locator("#pmsg")).to_contain_text("gespeichert", timeout=TL)
            assert [x["titel"] for x in _req(app, f"/api/plans/{pid}")["links"]] == ["Wetter Testtal"]
            expect(pg.locator("#phb a[href^='https://wetter.example/']")).to_have_count(1, timeout=TL)
            # ändern
            li.locator("[data-le]").click()
            expect(dlg).to_be_visible(timeout=TL)
            assert pg.input_value("#plt") == "Wetter Testtal" and pg.input_value("#pla") == "wetter"
            pg.fill("#plt", "Wetter Testtal neu")
            pg.select_option("#pla", "karte")
            pg.click("#plok")
            expect(li.locator("a.plkt")).to_have_text("Wetter Testtal neu", timeout=TL)
            expect(li).to_contain_text("Karte/Route")
            # Esc schließt ohne Änderung
            li.locator("[data-le]").click()
            expect(dlg).to_be_visible(timeout=TL)
            pg.fill("#plt", "verworfen")
            pg.keyboard.press("Escape")
            expect(dlg).to_have_count(0, timeout=TL)
            expect(li.locator("a.plkt")).to_have_text("Wetter Testtal neu")
            _ruhe(pg)
            assert _no_hscroll(pg)
            _shot(pg, f"planhilfe-links-{tag}.png")
            # löschen: Rückfrage, Abbrechen behält
            li.locator("[data-lx]").click()
            expect(pg.locator(".uidlg")).to_be_visible(timeout=TL)
            pg.locator(".uidlg .uifoot .btn.ghost").first.click()
            expect(pg.locator(".uidlg")).to_have_count(0, timeout=TL)
            expect(li).to_have_count(1)
            li.locator("[data-lx]").click()
            expect(pg.locator(".uidlg")).to_be_visible(timeout=TL)
            pg.locator(".uidlg .uifoot .btn:not(.ghost)").first.click()
            expect(li).to_have_count(0, timeout=TL)
            pg.click("#psave")
            expect(pg.locator("#pmsg")).to_contain_text("gespeichert", timeout=TL)
            assert _req(app, f"/api/plans/{pid}")["links"] == []
            assert angefragt == [], angefragt                                                          # Links werden nie vom Browser aufgerufen (kein Abruf, keine Vorschau)
            assert not pg.errors, pg.errors
        finally:
            pg.browser_.close()


def test_link_grenze_20(pw, app):
    _sauber(app)
    pid = _plan(app, links=[{"titel": f"L{i}", "url": f"https://example.org/{i}"} for i in range(20)])
    pg = _page(pw, app)
    try:
        _open(pg, app, pid)
        expect(pg.locator("#plinks li")).to_have_count(20, timeout=TL)
        expect(pg.locator("#pladd")).to_be_disabled()
        expect(pg.locator("#pnqsum")).to_contain_text("20 Links")
        pg.locator("#plinks li [data-lx]").first.click()
        pg.locator(".uidlg .uifoot .btn:not(.ghost)").first.click()
        expect(pg.locator("#pladd")).to_be_enabled(timeout=TL)
    finally:
        pg.browser_.close()


def test_planliste_marken(pw, app):
    _sauber(app)
    pid = _plan(app, name="Mit allem")
    pid2 = _plan(app, name="Ohne alles", links=[], note="", quelle="")
    pid3 = _plan(app, name="Ein Link", links=LINKS[:1], note="")
    pg = _page(pw, app)
    try:
        pg.goto(app["url"] + "#/plan")
        pg.wait_for_function("() => document.querySelectorAll('#plist [data-p]').length === 3", timeout=TL)
        r1, r2, r3 = (pg.locator(f'#plist [data-p="{i}"]') for i in (pid, pid2, pid3))
        expect(r1.locator(".pmk")).to_have_count(2)
        expect(r1).to_contain_text("Notiz")
        expect(r1).to_contain_text("2 Links")
        expect(r2.locator(".pmk")).to_have_count(0)
        expect(r3).to_contain_text("1 Link")
        assert "Notiz" not in r3.inner_text()
        _ruhe(pg)
        assert _no_hscroll(pg)
        _shot(pg, "planhilfe-liste.png")
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Sprachen  ------------------------------------------------------------------
DEUTSCH = re.compile(r"\b(Rückkehr|Sonnenuntergang|Sonnenaufgang|Vergleichstouren|Notiz|Planung|Strecke|Aufstieg|Herkunft|Quellen|Entscheidungshilfe|Sicherheitsgarantie|Lawinenbericht|Hütte|Bearbeiten|Löschen|deine|deiner|deinen)\b")


@pytest.mark.parametrize("lang,locale,texte", [
    ("en", "en-GB", ["Does this tour suit me?", "Notes & sources", "Guidance, not a safety guarantee.", "Check weather, avalanche conditions and terrain yourself.", "Daylight: back before sunset", "Fitness:", "Weather/avalanche report", "Add link", "2 links"]),
    ("fr", "fr-FR", ["Cette sortie me convient-elle ?", "Notes et sources", "À titre indicatif, pas une garantie de sécurité.", "Vérifiez vous-même la météo, le risque d’avalanche et le terrain.", "Lumière du jour : retour avant le coucher du soleil", "Forme :", "Météo/bulletin d’avalanches", "Ajouter un lien", "2 liens"]),
    ("es", "es-ES", ["¿Me conviene esta ruta?", "Notas y fuentes", "Orientación, no una garantía de seguridad.", "Comprueba tú mismo el tiempo, el riesgo de aludes y el terreno.", "Luz del día: regreso antes de la puesta de sol", "Forma:", "Tiempo/boletín de aludes", "Añadir enlace", "2 enlaces"]),
])
def test_vier_sprachen(pw, app, lang, locale, texte):
    _sauber(app)
    pid = _plan(app)
    pg = _page(pw, app, locale=locale, width=390)
    try:
        _open(pg, app, pid)
        pg.wait_for_function("(l) => document.documentElement.lang === l", arg=lang, timeout=TL)
        expect(pg.locator("#phsum")).to_contain_text("Form" if lang == "fr" else "Fit" if lang == "en" else "Forma", timeout=TL)
        pg.wait_for_function("() => !!document.querySelector('#phb .pcst')", timeout=TL)
        quiet(pg)
        ganz = pg.inner_text("#philfe") + "\n" + pg.inner_text("#pnq") + "\n" + (pg.get_attribute("#pquelle", "aria-label") or "")
        for t in texte:
            assert t in ganz, (lang, t, ganz[:1500])
        assert not DEUTSCH.findall(ganz), (lang, DEUTSCH.findall(ganz))
        # Dialog und Meldungen übersetzt
        pg.click("#pladd")
        expect(pg.locator(".uimod .uibox")).to_be_visible(timeout=TL)
        pg.fill("#plu", "ftp://x.example")
        pg.click("#plok")
        err = pg.inner_text("#plerr")
        assert not re.search(r"Bitte|Adresse", err) and "http://" in err, err
        pg.click("#plx")
        _ruhe(pg)
        assert _no_hscroll(pg)
        _shot(pg, f"planhilfe-{lang}-m.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
        _sauber(app)
