"""3.72.0 (M-10) – Leere Gebiete- und Reisen-Seiten haben genau eine Überschrift (Seitentitel); der Leerzustand steht als ruhige Zeile darunter.
Eigener Server mit einer einzigen Tour mitten im Atlantik (kein bekanntes Gebiet, keine Reise)."""
import os
import socket
import subprocess
import sys

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.helpers_ui import settled  # noqa: E402
from tests.test_seitenlayout_ui import ROOT, T, _browser, pw  # noqa: F401, E402
from tests.test_tourseite_ui import LAUNCH, _wait  # noqa: E402

SEED = r"""
import sys, os, time; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db
ts = int(time.time()) - 5 * 86400
db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,'t','komoot')", ("m1", "Atlantiktour", "hike", ts, ts + 7200, 9000, 7200, 300, 300, 0.5, -30.0))
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("lz372")
    data = tmp / "data"
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data)}], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
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


HEAD = """(name) => [...document.querySelectorAll('#main h1, #main h2, #main h3')].filter(e => e.offsetParent !== null && e.textContent.trim() === name).length"""


@pytest.mark.parametrize("seite,titel", [("areas", "Gebiete"), ("trips", "Reisen")])
@pytest.mark.parametrize("w", (390, 1280))
def test_leere_seite_hat_genau_eine_ueberschrift(pw, app, seite, titel, w):
    pg = _browser(pw, app, width=w, height=900, devs=None)
    try:
        pg.goto(f"{app}/#/{seite}")
        pg.wait_for_function("() => document.querySelector('main') && document.querySelector('main').children.length > 0", timeout=T)
        settled(pg)
        pg.wait_for_timeout(300)
        assert pg.evaluate(HEAD, titel) == 1
        assert pg.evaluate("(s) => !!document.querySelector(s) && document.querySelector(s).offsetParent !== null", ".gbnone" if seite == "areas" else "#tr")   # der Leerzustand selbst bleibt sichtbar
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
