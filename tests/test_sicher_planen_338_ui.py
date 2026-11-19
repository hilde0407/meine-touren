"""3.38.0 „Sicher planen“ (Oberfläche, Chromium): Planseite mit Machbarkeits-Karte, Planliste mit Status/Verknüpfung/Vorschlag, Verwaltung „Letzte Sicherung prüfen“.
Desktop 1280 und 390 px, hell und dunkel, Englisch. Synchronisation nur über wait_for_function (Pfeilfunktionen) und expect(..., timeout=15000); keine festen Pausen.
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
from pathlib import Path

import pytest
from tests.helpers_ui import quiet  # noqa: E402

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
    d = tmp_path_factory.mktemp("sp338")
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


# ------------------------------------------------------------------  Planseite: Machbarkeit  ------------------------------------------------------------------

def test_plan_check_karte_desktop_hell_dunkel_mobil(pw, app):
    pid = _new_plan(app, "Lange Runde", _line(100, 0.0017), 19.0)
    for width, scheme, tag in ((1280, "light", "d-hell"), (1280, "dark", "d-dunkel"), (390, "light", "m-hell"), (390, "dark", "m-dunkel")):
        pg = _page(pw, app, width=width, scheme=scheme)
        try:
            _open_plan_page(pg, app, pid)
            box = pg.locator("#pcheck")
            expect(box).to_be_visible(timeout=TL)
            pg.evaluate("() => { document.querySelector('#pcheck').open = true; }")
            expect(pg.locator("#pcsum")).to_contain_text("Etwas mehr als gewohnt", timeout=TL)
            body = pg.locator("#pcb")
            expect(body).to_contain_text(re.compile(r"Deine längste Tour der letzten 12 Monate: 17,0 km mit 1\.000 m; diese: 19,\d km mit 800 m"), timeout=TL)
            expect(body).to_contain_text("Länger als deine längste Tour (+12 %)")
            expect(body).to_contain_text("Reine Gehzeit ohne Pausen")
            assert "▲" in pg.inner_text("#pcheck")                                                # Symbol zusätzlich zur Farbe
            # eine Zeitzahl: Kennzahl oben und Karte zeigen dasselbe
            top = pg.evaluate("() => { const l = [...document.querySelectorAll('#pf .fig')].find(f => /Geschätzte Zeit/.test(f.innerText)); return l.querySelector('.v').innerText.replace(/Std\\./, '').trim(); }")
            assert f"Geschätzte Gesamtzeit inkl. Pausen: {top} Std. (wie oben)" in pg.inner_text("#pcb")
            # aria
            assert pg.get_attribute("#pcb", "aria-live") == "polite" and pg.get_attribute("#pcb", "role") == "status"
            assert pg.get_attribute("#pn", "aria-label") == "Name der Planung" and pg.get_attribute("#ps", "aria-label") == "Sportart"
            assert pg.get_attribute("#pm", "aria-label")
            # Einklappen
            pg.evaluate("() => { document.querySelector('#pcheck').open = false; }")
            expect(body).to_be_hidden(timeout=TL)
            expect(pg.locator("#pcsum")).to_be_visible()
            pg.evaluate("() => { document.querySelector('#pcheck').open = true; }")
            expect(body).to_be_visible(timeout=TL)
            _ruhe(pg)
            assert _no_hscroll(pg)
            assert _contrast(pg, "#pcb .pcst") >= 4.5 and _contrast(pg, "#pcsum .pcs") >= 4.5
            _shot(pg, f"plan-check-{tag}.png")
            assert not pg.errors, pg.errors
        finally:
            pg.browser_.close()


def test_plan_check_stufen_zu_wenig_und_englisch(pw, app):
    p_gewohnt = _new_plan(app, "Kleine Runde", _line(60, 0.0017), 11.0)
    p_rad = _new_plan(app, "Radrunde", _line(60, 0.0017), 11.0, sport="racebike")
    pg = _page(pw, app)
    try:
        _open_plan_page(pg, app, p_gewohnt)
        expect(pg.locator("#pcsum")).to_contain_text("Im gewohnten Rahmen", timeout=TL)
        assert "✓" in pg.inner_text("#pcsum")
        # andere Sportart: zu wenig Touren, keine Scheinzahlen
        _open_plan_page(pg, app, p_rad)
        expect(pg.locator("#pcsum")).to_contain_text("Zu wenig eigene Touren für eine persönliche Einschätzung", timeout=TL)
        expect(pg.locator("#pcb")).to_contain_text("Gefunden: 0 Touren dieser Sportart in den letzten 12 Monaten, nötig sind mindestens 6.")
        assert "Deine längste Tour" not in pg.inner_text("#pcb") and "Reine Gehzeit" not in pg.inner_text("#pcb")      # Gehzeit gibt es für Rad nicht
        # leere Planung: Karte verborgen
        pg.click("#pclr")
        expect(pg.locator("#pcheck")).to_be_hidden(timeout=TL)
    finally:
        pg.browser_.close()
    pg = _page(pw, app, locale="en-GB")
    try:
        _open_plan_page(pg, app, p_gewohnt)
        expect(pg.locator("#pcsum")).to_contain_text("Within your usual range", timeout=TL)
        expect(pg.locator("#pcb")).to_contain_text("Your longest tour of the last 12 months")
        txt = pg.inner_text("#pcheck")
        assert "Deine" not in txt and "Machbarkeit" not in txt
        assert pg.get_attribute("#pn", "aria-label") == "Name of the plan"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Planliste: Status, Verknüpfung, Vorschlag  ------------------------------------------------------------------

def test_planliste_vorschlag_bestaetigen_loesen_und_status(pw, app):
    pts = [[48.0 + 0.001 * i, 8.0 + 0.0005 * i] for i in range(60)]
    pid = _new_plan(app, "Gipfelrunde geplant", pts, 6.7, est=2.0)
    for width, scheme, tag in ((1280, "light", "d-hell"), (390, "dark", "m-dunkel")):
        _req(app, f"/api/plans/{pid}/tour", "POST", {"tour_id": None})
        _req(app, f"/api/plans/{pid}/status", "POST", {"status": "geplant"})
        pg = _page(pw, app, width=width, scheme=scheme)
        try:
            pg.goto(app["url"] + "#/plan")
            row = pg.locator(f'#plist [data-p="{pid}"]')
            sug = row.locator(".psug")
            expect(sug).to_be_visible(timeout=TL)
            expect(sug).to_contain_text("Gelaufen am")
            expect(sug).to_contain_text("vorschlagen")
            expect(sug).to_contain_text("Gipfelrunde gelaufen")
            assert _req(app, "/api/plans")[0]["tour_id"] is None                                      # nie automatisch verknüpft
            _ruhe(pg)
            assert _no_hscroll(pg)
            _shot(pg, f"planliste-vorschlag-{tag}.png")
            row.locator("[data-ok]").click()
            expect(row.locator(".pcmp")).to_contain_text("geplant 2:00 Std.", timeout=TL)
            expect(row.locator(".pcmp")).to_contain_text("gelaufen 1:42 Std. (−18 Min.)")
            expect(row.locator(".pcmp")).to_contain_text("Strecke: geplant 6,7 km, gelaufen 6,9 km (+0,2 km)")
            expect(row.locator(".pcmp")).to_contain_text("Aufstieg: geplant 800 m, gelaufen 190 m (−610 m)")
            expect(row.locator(".pst.g")).to_contain_text("gegangen")
            assert row.locator(".psug").count() == 0
            assert _req(app, "/api/plans")[0]["tour_id"] == "lauf"
            _ruhe(pg)
            assert _no_hscroll(pg)
            _shot(pg, f"planliste-verknuepft-{tag}.png")
            # Tastatur: Name ist ein Link, Status hat eine Beschriftung
            assert row.locator("a.prn").get_attribute("href") == f"#/plan/{pid}"
            assert "Status" in row.locator("select.pstat").get_attribute("aria-label")
            # Lösen
            row.locator("[data-un]").click()
            expect(row.locator(".pcmp")).to_have_count(0, timeout=TL)
            assert _req(app, "/api/plans")[0]["tour_id"] is None
            # Status verworfen: Vorschlag verschwindet, Abzeichen steht da
            row.locator("select.pstat").select_option("verworfen")
            expect(row.locator(".pst.v")).to_contain_text("verworfen", timeout=TL)
            assert row.locator(".psug").count() == 0
            assert _req(app, "/api/plans")[0]["status"] == "verworfen"
            assert not pg.errors, pg.errors
        finally:
            pg.browser_.close()


def test_planliste_nicht_passend_merkt_sich_die_ablehnung(pw, app):
    pid = _new_plan(app, "Gipfelrunde zwei", [[48.0 + 0.001 * i, 8.0 + 0.0005 * i] for i in range(60)], 6.7)
    for p in _req(app, "/api/plans"):
        if p["id"] != pid:
            _req(app, f"/api/plans/{p['id']}/status", "POST", {"status": "verworfen"})
    _req(app, f"/api/plans/{pid}/status", "POST", {"status": "geplant"})
    pg = _page(pw, app)
    try:
        pg.goto(app["url"] + "#/plan")
        row = pg.locator(f'#plist [data-p="{pid}"]')
        expect(row.locator(".psug")).to_be_visible(timeout=TL)
        row.locator("[data-no]").click()
        expect(row.locator(".psug")).to_have_count(0, timeout=TL)
        pg.reload()
        expect(pg.locator(f'#plist [data-p="{pid}"]')).to_be_visible(timeout=TL)
        pg.wait_for_function("() => !!document.querySelector('#plist [data-p]')", timeout=TL)
        _ruhe(pg)
        assert pg.locator(f'#plist [data-p="{pid}"] .psug').count() == 0
        assert _req(app, "/api/plans")[0]["tour_id"] is None
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Verwaltung: Sicherung prüfen  ------------------------------------------------------------------

def test_verwaltung_letzte_sicherung_pruefen(pw, app):
    _req(app, "/api/backup/now", "POST")
    for width, scheme, tag in ((1280, "light", "d-hell"), (390, "dark", "m-dunkel")):
        pg = _page(pw, app, width=width, scheme=scheme)
        try:
            _admin(pg, app)
            box = pg.locator("#bkst")
            expect(box).to_contain_text("Letzte Sicherung:", timeout=TL)
            expect(box).to_contain_text("wurde noch nicht geprüft") if tag == "d-hell" else None
            note = pg.locator("#bkchk").locator("xpath=following::p[1]")
            expect(note).to_contain_text("secret.key")
            expect(note).to_contain_text("Fotodateien")
            expect(note).to_contain_text("Zwischenspeicher")
            pg.click("#bkchk")
            expect(pg.locator("#bkok")).to_contain_text("Zuletzt geprüft:", timeout=TL)
            expect(pg.locator("#bkok")).to_contain_text("in Ordnung")
            expect(box).to_contain_text("Enthält 9 Touren")
            assert pg.locator("#bkbad").count() == 0
            _ruhe(pg)
            assert _no_hscroll(pg)
            _shot(pg, f"verwaltung-sicherung-{tag}.png")
            assert not pg.errors, pg.errors
        finally:
            pg.browser_.close()


def test_verwaltung_defekte_sicherung_und_fehlgeschlagene_sicherung_sichtbar(pw, app):
    newest = max(app["bak"].glob("meine-touren-*.zip"), key=lambda f: f.stat().st_mtime)
    kaputt = app["bak"] / "meine-touren-2099-01-01_0000.zip"
    kaputt.write_bytes(newest.read_bytes()[:400])
    con = sqlite3.connect(str(app["data"] / "komoot_hub.sqlite"))
    con.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('backup_err','Zu wenig freier Speicher im Sicherungsordner')")
    con.commit(); con.close()
    pg = _page(pw, app)
    try:
        _admin(pg, app)
        expect(pg.locator("#bkerr")).to_contain_text("Letzte Sicherung fehlgeschlagen: Zu wenig freier Speicher", timeout=TL)
        pg.click("#bkchk")
        expect(pg.locator("#bkbad")).to_contain_text("Fehler", timeout=TL)
        assert "✗" in pg.inner_text("#bkbad") and pg.locator("#bkok").count() == 0
        _shot(pg, "verwaltung-sicherung-fehler-d-hell.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
        kaputt.unlink(missing_ok=True)
        con = sqlite3.connect(str(app["data"] / "komoot_hub.sqlite"))
        con.execute("DELETE FROM settings WHERE k='backup_err'")
        con.commit(); con.close()


def test_verwaltung_englisch(pw, app):
    pg = _page(pw, app, locale="en-GB")
    try:
        _admin(pg, app)
        expect(pg.locator("#bkchk")).to_have_text("Check last backup", timeout=TL)
        pg.click("#bkchk")
        expect(pg.locator("#bkst")).to_contain_text("Last checked:", timeout=TL)
        assert "Zuletzt" not in pg.inner_text("#bkst")
    finally:
        pg.browser_.close()
