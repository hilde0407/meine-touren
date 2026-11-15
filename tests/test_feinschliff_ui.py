"""3.24.0 – Feinschliff (Browser, Chromium): Knopf „Ansichten“ immer neben „Seite anpassen“, kompakte Bearbeitungsleiste mit „⋯“-Menü auf 390 px, Seitenfuß-Abstand,
Platzhalter für leere Zellen, „⋯“-Menü im Bausteinkopf schmaler Bausteine, Kontrast hell/dunkel, Tastatur. Wettlauf-Regel: nach jeder Aktion auf den Zustand warten (15 s).
Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import os
import socket
import subprocess
import sys

import pytest

from tests.test_seitenlayout_ui import ROOT, T, _api, _browser, _dash, _edit, pw  # noqa: F401
from tests.test_tourseite_ui import CONTRAST, LAUNCH, SEED, _shot, _wait

KEYS = ("tour-haupt", "tour-auswertung", "uebersicht")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    tmp = tmp_path_factory.mktemp("fs")
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


@pytest.fixture(autouse=True)
def clean(app):
    for k in KEYS:
        _api(app, k, "DELETE")
    yield


def test_ansichten_knopf_immer_da_und_oeffnet_die_verwaltung(pw, app):
    pg = _dash(pw, app)
    try:
        assert pg.locator("#slviews").is_visible() and pg.locator("#slview").count() == 0          # eine Ansicht: Knopf ja, Auswahlliste nein
        assert pg.evaluate("() => document.querySelector('#slviews').getBoundingClientRect().height") >= 40
        pg.locator("#slviews").click()
        pg.wait_for_selector(".slvws .slvr", timeout=T)
        assert pg.evaluate("() => document.activeElement.closest('.slvws') !== null")
        pg.locator(".slvws [data-close]").click()
        pg.wait_for_function("() => !document.querySelector('.slvws')", timeout=T)
        _api(app, "uebersicht", "PUT", {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1}}, {"id": "v1", "name": "Kompakt", "layout": {"v": 1}}], "active": "standard"})
        pg.reload()
        pg.wait_for_function("() => !!document.querySelector('#slview') && document.querySelector('#slviews').offsetParent !== null", timeout=T)       # ab zwei Ansichten zusätzlich die Liste
        _edit(pg)
        pg.wait_for_function("() => document.querySelector('#slviews').offsetParent === null", timeout=T)                                          # im Bearbeitungsmodus sitzt er in der Leiste
        assert pg.locator("#slbar [data-a=views]").is_visible()
    finally:
        pg.browser_.close()


def test_ansichten_knopf_auf_der_tourseite(pw, app):
    from tests.test_seitenlayout_ui import _tour
    pg = _tour(pw, app)
    try:
        assert pg.locator("#slviews").is_visible()
        pg.locator("#slviews").click()
        pg.wait_for_selector(".slvws .slvr", timeout=T)
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_leiste_390_kompakt_mit_mehr_menue(pw, app, scheme):
    pg = _dash(pw, app, width=390, height=800, scheme=scheme, dpr=2)
    try:
        _edit(pg)
        bar = "#slbar"
        pg.wait_for_function("() => { const b = document.querySelector('#slbar'); return !!b && b.getBoundingClientRect().height > 0; }", timeout=T)
        h = pg.evaluate("() => document.querySelector('#slbar').getBoundingClientRect().height")
        assert h <= 130, h                                                                        # vorher mehrzeilig (über 190)
        for sel in ("[data-a=views]", "[data-a=add]", "[data-a=more]", "[data-a=done]"):
            assert pg.locator(f"{bar} {sel}").is_visible(), sel
        for sel in ("reset", "savenew", "discard"):
            assert not pg.locator(f"{bar} [data-a={sel}]").is_visible(), sel
        tops = pg.evaluate("() => [...document.querySelectorAll('#slbar .slbb > .btn:not([hidden])')].filter(b => b.offsetParent).map(b => Math.round(b.getBoundingClientRect().top))")
        assert len(set(tops)) == 1, tops                                                         # alle vier in einer Zeile
        assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
        # Seitenfuß: Abstand mindestens so hoch wie die Leiste
        pg.wait_for_function("() => parseFloat(getComputedStyle(document.body).paddingBottom) >= document.querySelector('#slbar').getBoundingClientRect().height", timeout=T)
        # Menü
        pg.locator(f"{bar} [data-a=more]").click()
        pg.wait_for_function("() => document.querySelector('#slbar').classList.contains('mo-open')", timeout=T)
        assert pg.locator(f"{bar} [data-a=more]").get_attribute("aria-expanded") == "true"
        for sel in ("reset", "savenew", "discard"):
            assert pg.locator(f"{bar} [data-a={sel}]").is_visible(), sel
        assert pg.evaluate("() => [...document.querySelectorAll('#slbar .slbmo .btn')].every(b => b.getBoundingClientRect().height >= 40 && b.getBoundingClientRect().right <= innerWidth)")
        c = pg.evaluate(CONTRAST, ["#slbar .slbmo .btn", "#slbar [data-a=done]", "#slbar [data-a=views]", "#slbar .slbi b"])
        assert c and all(v >= 4.5 for v in c.values()), c
        _shot(pg, f"bar-menu-390-{scheme}.png", full=False)
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('#slbar').classList.contains('mo-open')", timeout=T)
        assert pg.evaluate("() => document.activeElement.dataset.a") == "more"
    finally:
        pg.browser_.close()


def test_leere_zelle_platzhalter_und_bausteinkopf_menue(pw, app):
    pg = _dash(pw, app, width=390, height=800, dpr=2)
    try:
        _edit(pg)
        pg.wait_for_selector('.slit[data-sl="erinn"]', timeout=T, state="attached")
        ph = pg.locator('.slit[data-sl="erinn"] .slempty')
        pg.wait_for_function("() => { const p = document.querySelector('.slit[data-sl=erinn] .slempty'); return !!p && p.offsetParent !== null; }", timeout=T)
        assert "Gerade leer" in ph.inner_text()
        assert pg.evaluate("() => document.querySelector('.slit[data-sl=erinn]').getBoundingClientRect().height") < 260        # kompakt statt hoher leerer Fläche
        # schmaler Baustein: Einstellungen im Menü
        pg.wait_for_selector('.slit[data-sl="jahr"] .slst', timeout=T)
        cfg = pg.locator('.slit[data-sl="jahr"] [data-a=cfg]')
        more = pg.locator('.slit[data-sl="jahr"] [data-a=more]')
        assert not cfg.is_visible() and more.is_visible()
        more.click()
        pg.wait_for_function("() => document.querySelector('.slit[data-sl=jahr] .slst').classList.contains('mo-open')", timeout=T)
        assert cfg.is_visible() and more.get_attribute("aria-expanded") == "true"
        assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
        cfg.click()
        pg.wait_for_selector(".slbox", timeout=T)
        _shot(pg, "strip-menu-390.png", full=False)
    finally:
        pg.browser_.close()


def test_breiter_baustein_zeigt_alles_ohne_menue(pw, app):
    pg = _dash(pw, app, width=1280, height=900)
    try:
        _edit(pg)
        pg.wait_for_selector('.slit[data-sl="jahr"] .slst', timeout=T)
        assert pg.locator('.slit[data-sl="jahr"] [data-a=cfg]').is_visible() and not pg.locator('.slit[data-sl="jahr"] [data-a=more]').is_visible()
        assert pg.locator("#slbar [data-a=reset]").is_visible() and not pg.locator("#slbar [data-a=more]").is_visible()
        assert pg.evaluate("() => document.querySelector('#slbar').getBoundingClientRect().height") < 90
    finally:
        pg.browser_.close()
