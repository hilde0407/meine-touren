"""3.39.0 App-Start: boot() läuft erst nach dem letzten Skript. Regressionstest: ein spätes Skript (65-zeitraum.js bzw. 62-reiseseiten.js) wird künstlich festgehalten, während die
Antworten der App (/api/me, /api/tours, /api/settings) längst da sind; bis zum Freigeben darf nichts gezeichnet werden, danach rendert die Seite fehlerfrei („… is not defined“ darf nie auftreten).
Wettlauf-Regel: auf Zustände warten (wait_for_function mit Pfeilfunktion, expect mit 15 s), keine festen Pausen."""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

from tests.helpers_ui import T, quiet

ROOT = Path(__file__).resolve().parent.parent
expect = pytest.importorskip("playwright.sync_api").expect


@pytest.fixture(scope="module")
def app():
    d = Path(tempfile.mkdtemp(prefix="st339"))
    env = dict(os.environ, DATA_DIR=str(d / "data"), PHOTOS_DIR=str(d / "p"), BACKUP_DIR=str(d / "b"), MT_NO_SCHEDULER="1")
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    pr = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(150):
        try:
            urllib.request.urlopen(url + "/api/version", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
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


def _html(app):
    return urllib.request.urlopen(app + "/").read().decode("utf-8")


def test_boot_ist_das_letzte_skript_vor_dem_service_worker(app):
    html = _html(app)
    scripts = [l.split('src="')[1].split('"')[0].split("?")[0] for l in html.splitlines() if l.startswith("<script src=")]
    assert scripts[-2:] == ["js/69-start.js", "js/39-sw.js"]
    assert "boot();" in (ROOT / "app/static/js/69-start.js").read_text(encoding="utf-8")
    assert "\nboot();" not in (ROOT / "app/static/js/13-start.js").read_text(encoding="utf-8")


@pytest.mark.parametrize("script,hash_", [("65-zeitraum.js", "#/dash"), ("62-reiseseiten.js", "#/trips"), ("66-gruppen.js", "#/dash")])
def test_spaetes_skript_verzoegert_kein_not_defined(pw, app, script, hash_):
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": 1280, "height": 900}, locale="de-DE")
    pg = ctx.new_page()
    errors = []
    pg.on("pageerror", lambda e: errors.append(str(e)))
    held = []
    pg.route(f"**/js/{script}*", lambda r: held.append(r))                    # festhalten, bis der Test es freigibt
    pg.goto(f"{app}/{hash_}", wait_until="commit")
    pg.wait_for_function("() => true")                                       # Seite ist da
    expect_wait = time.time() + 15
    while not held and time.time() < expect_wait:
        pg.wait_for_timeout(50)                                              # nur auf das Festhalten warten (Zustand: Skript angefordert)
    assert held, "Skript wurde nie angefordert"
    # Antworten des Servers eintreffen lassen, während das Skript noch fehlt: eigene Anfrage hinterher, dann auf „keine Anfrage läuft“ warten
    pg.evaluate("() => fetch('/api/me').then(r => r.json())")
    pg.wait_for_function("() => !window.__mtq || window.__mtq.pend === 0", timeout=T)
    assert not pg.evaluate("() => !!window._rt"), "boot()/route() lief, bevor alle Skripte geladen waren"
    assert not errors, errors
    held[0].continue_()
    pg.wait_for_function("() => !!window._rt && !!document.querySelector('#main') && document.querySelector('#main').children.length > 0", timeout=T)
    quiet(pg, 3000)
    assert not [e for e in errors if "is not defined" in e], errors
    assert not errors, errors
    if hash_ == "#/dash":
        expect(pg.locator("#main")).to_contain_text("Touren", timeout=T)
    else:
        expect(pg.locator("#tr, #cm, #main h1").first).to_be_visible(timeout=T)
    b.close()
