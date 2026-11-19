"""3.48.0 – Rückblick „Wie ist es gelaufen?“ an der Tourseite (Browser, Chromium): erweitert den Abschnitt „Plan und Ergebnis“ (kein neuer Baustein). Ohne Plan und mit mindestens 5 Vergleichstouren:
Einordnung (Symbol + Wort) und „n-ter Besuch“; mit zu wenigen Vergleichstouren gibt es den Abschnitt nicht; mit verknüpftem Plan bleibt „Plan und Ergebnis“ (nichts doppelt);
390 px hell/dunkel, Englisch. Screenshots mit TS_SHOTS=<Ordner>."""
import json
import os
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.helpers_ui import T, quiet  # noqa: E402
from tests.test_seitenlayout_ui import _browser, pw  # noqa: E402,F401
from tests.test_tourseite_ui import LAUNCH, SEED, _wait  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
CARD = "#tlw-planist"

MORE = r"""
import sys, os, time; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db
db.init()
now = int(time.time())
for i, days in enumerate((150, 120, 80, 60)):                  # vier weitere Wanderungen an anderer Stelle (zählen als Vergleichstouren, nicht als dieselbe Strecke)
    ts = now - days * 86400
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,'hike',?,?,?,?,?,?,49.0,9.0,'t','komoot')",
               ("x%%d" %% i, "Andere Runde %%d" %% i, ts, ts + 7200, 6000, 7200, 300, 300))
"""


def _req(url, path, method="GET", body=None):
    r = urllib.request.Request(url + path, method=method, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=10) as x:
        return json.loads(x.read() or b"{}")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("rb")
    data = tmp / "data"
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    for code in (SEED % {"root": str(ROOT), "data": str(data)}, MORE % {"root": str(ROOT), "data": str(data)}):
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, env=env)
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


@pytest.fixture(autouse=True)
def clean(app):
    for p in _req(app, "/api/plans"):
        _req(app, f"/api/plans/{p['id']}", "DELETE")
    yield


def _tour(pw, app, tid, **kw):
    pg = _browser(pw, app, devs=None, **kw)
    pg.goto(f"{app}/#/tour/{tid}")
    pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen') && !!document.querySelector('#tl')", timeout=30000)
    quiet(pg, 3000, 500)
    return pg


def test_ohne_plan_mit_genug_vergleichstouren_einordnung_und_besuch(pw, app):
    d = _req(app, "/api/tours/r4/rueckblick")
    assert d["status"] == "ok" and d["besuch"]["nr"] == 5 and d["eigene"]["n"] == 8
    pg = _tour(pw, app, "r4")
    try:
        c = pg.locator(CARD)
        expect(c).to_be_visible(timeout=T)
        expect(c.locator("summary h3")).to_have_text("Wie ist es gelaufen?", timeout=T)
        expect(c).to_contain_text("Dein 5. Besuch dieser Strecke", timeout=T)
        expect(c).to_contain_text("Gegenüber deinen 8 Touren dieser Sportart in den 12 Monaten davor")
        rows = c.locator(".plrow")
        assert rows.count() >= 3
        for i in range(rows.count()):
            t = rows.nth(i).inner_text()
            assert any(w in t for w in ("kürzer als üblich", "ähnlich lang wie üblich", "länger als üblich", "weniger Aufstieg als üblich", "ähnlich viel Aufstieg wie üblich", "mehr Aufstieg als üblich",
                                        "langsamer als üblich", "ähnlich schnell wie üblich", "schneller als üblich")), t           # Wort, nicht nur Symbol
            assert "NaN" not in t and "undefined" not in t and "ohne Angabe" not in t
        assert c.locator(".pld [aria-hidden=true]").count() == rows.count()
        assert pg.locator("#aehncard").count() <= 1                                                         # die Karte „Ähnliche Touren im Vergleich“ bleibt eigenständig
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_zu_wenig_vergleichstouren_kein_abschnitt(pw, app):
    assert _req(app, "/api/tours/r0/rueckblick")["status"] == "zu_wenig"                                   # älteste Tour: keine Vergleichstouren davor
    pg = _tour(pw, app, "r0")
    try:
        assert pg.locator(CARD).count() == 0 and pg.locator("#tls-planist").count() == 0
        assert "Wie ist es gelaufen?" not in pg.locator("#main").inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_mit_plan_bleibt_plan_und_ergebnis_ohne_doppelanzeige(pw, app):
    pid = _req(app, "/api/plans", "POST", {"name": "Rund um den See", "sport": "hike", "pts": [[48.0, 11.0], [48.01, 11.01]], "km": 8.0, "up": 150, "down": 150, "est_h": 3.0})["id"]
    _req(app, f"/api/plans/{pid}/tour", "POST", {"tour_id": "r4"})
    assert _req(app, "/api/tours/r4/rueckblick") == {"status": "hat_plan"}
    pg = _tour(pw, app, "r4")
    try:
        c = pg.locator(CARD)
        expect(c.locator("summary h3")).to_have_text("Plan und Ergebnis", timeout=T)
        assert pg.locator(CARD).count() == 1 and "Wie ist es gelaufen?" not in pg.locator("#main").inner_text()
        assert c.locator(".plrow").count() == 3
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme,width", [("light", 1280), ("light", 390), ("dark", 390)])
def test_look_und_screenshots(pw, app, scheme, width):
    pg = _tour(pw, app, "r4", width=width, height=900 if width > 500 else 844, scheme=scheme, dpr=1 if width > 500 else 2)
    try:
        c = pg.locator(CARD)
        expect(c).to_be_visible(timeout=T)
        c.scroll_into_view_if_needed()
        quiet(pg, 3000, 400)
        assert pg.evaluate("() => document.documentElement.scrollWidth - innerWidth") <= 0
        assert pg.evaluate("() => { const c = document.querySelector('#tlw-planist'); return c.scrollWidth <= c.clientWidth + 1; }")
        r = pg.evaluate("""() => { const p = s => { const m = s.match(/[\\d.]+/g).map(Number); return m; };
          const L = c => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2]); };
          const bg = e => { for (; e; e = e.parentElement) { const c = p(getComputedStyle(e).backgroundColor); if (c.length < 4 || c[3] > .5) return c; } return [255, 255, 255]; };
          return [...document.querySelectorAll('#tlw-planist .pld, #tlw-planist .plv small, #tlw-planist .slcap, #tlw-planist .rbh')].map(e => { const a = L(p(getComputedStyle(e).color)), b = L(bg(e)); return (Math.max(a, b) + .05) / (Math.min(a, b) + .05); }); }""")
        assert r and min(r) >= 4.5, r
        if os.environ.get("TS_SHOTS"):
            Path(os.environ["TS_SHOTS"]).mkdir(parents=True, exist_ok=True)
            c.screenshot(path=str(Path(os.environ["TS_SHOTS"]) / f"rueckblick-{width}-{scheme}.png"))
    finally:
        pg.browser_.close()


def test_englisch(pw, app):
    pg = _tour(pw, app, "r4", locale="en-US")
    try:
        pg.evaluate("() => localStorage.setItem('lang', 'en')")
        pg.reload()
        expect(pg.locator(CARD)).to_be_visible(timeout=T)
        expect(pg.locator(CARD + " summary h3")).to_have_text("How did it go?", timeout=T)
        t = pg.locator(CARD).inner_text()
        assert "Your visit number 5 to this route" in t and ("than usual" in t or "as usual" in t) and "Usual (median)" in t, t
        assert "üblich" not in t and "Gegenüber" not in t, t
        pg.evaluate("() => localStorage.setItem('lang', 'de')")
    finally:
        pg.browser_.close()
