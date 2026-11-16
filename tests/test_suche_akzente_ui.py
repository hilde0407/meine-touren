"""3.31.0 – Suche ohne Akzente im Browser: Touren-Liste, globale Suche (Kopfzeile), Auswertung/Regionen, JS-Helfer sfold/smatch."""
import os
import socket
import subprocess
import sys

import pytest

expect = pytest.importorskip("playwright.sync_api").expect
from tests.test_seitenlayout_ui import ROOT, T, _browser, pw  # noqa: F401
from tests.test_tourseite_ui import LAUNCH, SEED, _wait

SEED3 = SEED + "\ndb.execute(\"INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES('re','Réunion Rundweg','hike',?,?,5000,3600,100,100,'t','komoot')\", (now - 9 * 86400, now - 9 * 86400 + 3600))\n"


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("sa")
    data = tmp / "data"
    out = subprocess.run([sys.executable, "-c", SEED3 % {"root": str(ROOT), "data": str(data)}], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ))
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


def test_js_helfer_wie_python(pw, app):
    pg = _browser(pw, app, devs=None)
    pg.goto(f"{app}/#/tours")
    pg.wait_for_selector("#q", timeout=T)
    r = pg.evaluate("""() => ({
      a: sfold("Réunion"), b: sfold("d’Azur"), c: sfold("Straße Ødegård Ålesund"),
      ok: [["Réunion", "reunion"], ["Lucía", "lucia"], ["Côte d'Azur", "dazur"], ["Côte d'Azur", "d azur"], ["Côte d’Azur", "d'Azur"], ["Köln", "koeln"], ["Köln", "koln"],
           ["Ärzte", "aerzte"], ["Ärzte", "arzte"], ["Groß", "GROSS"], ["Łódź", "lodz"]].map(([h, n]) => smatch(h, n)),
      nein: [["Réunion", "reunions"], ["Köln", "kon"]].map(([h, n]) => smatch(h, n)), leer: smatch("x", "  ") })""")
    assert (r["a"], r["b"], r["c"]) == ("reunion", "dazur", "strasse odegard alesund")
    assert all(r["ok"]) and not any(r["nein"]) and r["leer"]
    pg.browser_.close()


def test_touren_liste_und_globale_suche_finden_reunion(pw, app):
    pg = _browser(pw, app, devs=None)
    pg.goto(f"{app}/#/tours")
    pg.wait_for_selector("#q", timeout=T)
    pg.fill("#q", "reunion")
    pg.wait_for_function("() => document.body.innerText.includes('Réunion Rundweg') && !document.body.innerText.includes('Solo ohne Uhr')", timeout=T)
    pg.fill("#q", "REUNION RUND")
    pg.wait_for_function("() => document.body.innerText.includes('Réunion Rundweg')", timeout=T)
    pg.fill("#q", "")
    pg.fill("#gs", "reunion")
    pg.wait_for_function("() => location.hash.startsWith('#/search') && document.querySelector('main').innerText.includes('Réunion Rundweg')", timeout=T)
    pg.fill("#gs", "Reunión")
    pg.wait_for_function("() => location.hash.includes('q=Reuni') && document.querySelector('main').innerText.includes('Réunion Rundweg')", timeout=T)
    pg.fill("#gs", "gibtesnicht")
    pg.wait_for_function("() => location.hash.includes('gibtesnicht') && !document.querySelector('main').innerText.includes('Réunion Rundweg')", timeout=T)
    assert not pg.errors
    pg.browser_.close()
