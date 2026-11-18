"""3.39.0 3D-Flug: Steuerung für Touchpad und Tastatur. Die reinen Funktionen (js/07-flugsteuerung.js) werden mit Node geprüft; die Verdrahtung (Knopf „Drehen“) im Quelltext."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "app" / "static" / "js"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="Node nicht installiert")


def _node(expr):
    code = f"const m = require({json.dumps(str(JS / '07-flugsteuerung.js'))}); process.stdout.write(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)


def test_ziehen_dreht_und_kippt():
    assert _node("m.flDragDelta(10, 0)")["bearing"] == 5
    d = _node("m.flDragDelta(0, 20)")
    assert d["bearing"] == 0 and d["pitch"] == -10                   # nach unten ziehen: weniger Neigung (wie MapLibre)
    assert _node("m.flDragDelta(-8, -4)") == {"bearing": -4, "pitch": 2}


def test_zweifinger_wischen_seitwaerts_dreht_alt_kippt_senkrecht_und_pinch_zoomen():
    assert _node("m.flWheelDelta({deltaX: 40, deltaY: 3})") == {"bearing": 10, "pitch": 0}
    assert _node("m.flWheelDelta({deltaX: -20, deltaY: 0})")["bearing"] == -5
    assert _node("m.flWheelDelta({deltaX: 0, deltaY: 30})") is None                              # senkrecht: Zoom wie bisher
    assert _node("m.flWheelDelta({deltaX: 2, deltaY: 30})") is None
    assert _node("m.flWheelDelta({deltaX: 40, deltaY: 0, ctrlKey: true})") is None               # Pinch auf dem Touchpad = Strg+wheel: Zoom
    assert _node("m.flWheelDelta({deltaX: 0, deltaY: 50, altKey: true})") == {"bearing": 0, "pitch": 10}
    assert _node("m.flWheelDelta({deltaX: 30, deltaY: 0, altKey: true})")["pitch"] == 6          # macOS macht aus Alt+Wischen teils deltaX
    assert _node("m.flWheelDelta({deltaX: 0, deltaY: 0})") is None
    assert _node("m.flWheelDelta({deltaX: 1, deltaY: 0, deltaMode: 1})")["bearing"] == 4        # Zeilenmodus (Mausrad) hochgerechnet


def test_pfeiltasten():
    assert _node("m.flKeyDelta('ArrowLeft', false)") == {"bearing": -10, "pitch": 0}
    assert _node("m.flKeyDelta('ArrowRight', true)") == {"bearing": 20, "pitch": 0}
    assert _node("m.flKeyDelta('ArrowUp', false)") == {"bearing": 0, "pitch": 5}
    assert _node("m.flKeyDelta('ArrowDown', false)") == {"bearing": 0, "pitch": -5}
    assert _node("m.flKeyDelta('a', false)") is None and _node("m.flKeyDelta('Tab', false)") is None


def test_safari_geste_und_grenzen():
    assert _node("m.flGestureDelta(10, 25)") == -15                                              # im Uhrzeigersinn: Richtung nimmt ab, die Karte dreht mit
    assert _node("[m.flClampPitch(-5), m.flClampPitch(50), m.flClampPitch(99)]") == [0, 50, 85]
    assert _node("[m.flNorm(190), m.flNorm(-190), m.flNorm(360), m.flNorm(45)]") == [-170, 170, 0, 45]


def test_verdrahtung_im_flug():
    src = (JS / "07-flug.js").read_text(encoding="utf-8")
    assert 'id="frot"' in src and 'aria-pressed="false"' in src and 'id="fhelp"' in src
    for k in ("pointerdown", "wheel", "keydown", "gesturechange", "flDragDelta", "flWheelDelta", "flKeyDelta", "flGestureDelta"):
        assert k in src, k
    assert "passive: false" in src                                                                # wheel muss abbrechbar sein
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("js/07-flug.js") < html.index("js/07-flugsteuerung.js")


# ------------------------------------------------------------------  Browser (nur mit WebGL)  ------------------------------------------------------------------
from tests.helpers_ui import T, quiet  # noqa: E402
from tests.test_seitenlayout_ui import _browser, pw  # noqa: E402,F401
from tests.test_reise_seiten_ui import app  # noqa: E402,F401


def _flug(pw, app, width=1280, height=800):
    pytest.importorskip("playwright.sync_api")
    pg = _browser(pw, app, devs=None, width=width, height=height)
    pg.goto(f"{app}/#/flight/h0")
    pg.wait_for_function("() => !!document.getElementById('fm') && (!!document.getElementById('fm')._map || /WebGL|noch keine Strecke/.test(document.getElementById('fmsg').textContent))", timeout=30000)
    if not pg.evaluate("() => !!document.getElementById('fm')._map"):
        msg = pg.evaluate("() => document.getElementById('fmsg').textContent")
        pg.browser_.close()
        pytest.skip("kein WebGL im Testbrowser: " + msg)
    return pg


def _wake(pg, x, y):
    """Das Bedienfeld blendet sich nach ein paar Sekunden aus (Klasse idle, keine Zeigerereignisse); eine Mausbewegung weckt es."""
    pg.mouse.move(x, y + 10)
    pg.mouse.move(x + 3, y + 12)
    pg.wait_for_function("() => !document.getElementById('fl').classList.contains('idle')", timeout=T)


def _click(pg, btn, x, y):
    """Knopf im Bedienfeld mit der Maus anklicken (ohne die Stabilitätsprüfung von Playwright: die WebGL-Seite zeichnet im Testbrowser langsam). Erst wecken, dann genau auf den Knopf klicken."""
    _wake(pg, x, y)
    bb = btn.bounding_box()
    pg.mouse.click(bb["x"] + bb["width"] / 2, bb["y"] + bb["height"] / 2)


def _view(pg):
    return pg.evaluate("() => { const m = document.getElementById('fm')._map; return [m.getBearing(), m.getPitch()]; }")


def test_flug_browser_drehen_modus_wheel_und_tasten(pw, app):
    pg = _flug(pw, app)
    try:
        btn = pg.locator("#frot")
        assert btn.get_attribute("aria-pressed") == "false" and btn.bounding_box()["height"] >= 44
        pg.select_option("#fc", "free")
        b0, p0 = _view(pg)
        box = pg.locator("#fm").bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 3
        # seitliches Wischen dreht, Alt+Wischen kippt, senkrechtes Wischen ändert Richtung/Neigung nicht
        pg.mouse.move(cx, cy)
        pg.mouse.wheel(80, 0)
        pg.wait_for_function("(b) => Math.abs(document.getElementById('fm')._map.getBearing() - b) > 5", arg=b0, timeout=T)
        b1, p1 = _view(pg)
        pg.keyboard.down("Alt")
        pg.mouse.wheel(0, 100)
        pg.keyboard.up("Alt")
        pg.wait_for_function("(p) => Math.abs(document.getElementById('fm')._map.getPitch() - p) > 2", arg=p1, timeout=T)
        # Drehen-Modus: Ziehen mit der linken Taste dreht statt zu verschieben
        _click(pg, btn, cx, cy)
        assert btn.get_attribute("aria-pressed") == "true"
        b2, p2 = _view(pg)
        c0 = pg.evaluate("() => document.getElementById('fm')._map.getCenter().lng")
        pg.mouse.move(cx, cy)
        pg.mouse.down()
        pg.mouse.move(cx + 80, cy, steps=6)
        pg.mouse.up()
        pg.wait_for_function("(b) => Math.abs(document.getElementById('fm')._map.getBearing() - b) > 10", arg=b2, timeout=T)
        assert abs(pg.evaluate("() => document.getElementById('fm')._map.getCenter().lng") - c0) < 1e-6          # nichts verschoben
        # Umschalt+Ziehen ohne Modus
        _click(pg, btn, cx, cy)
        assert btn.get_attribute("aria-pressed") == "false"
        b3, _ = _view(pg)
        pg.keyboard.down("Shift")
        pg.mouse.move(cx, cy)
        pg.mouse.down()
        pg.mouse.move(cx - 80, cy, steps=6)
        pg.mouse.up()
        pg.keyboard.up("Shift")
        pg.wait_for_function("(b) => Math.abs(document.getElementById('fm')._map.getBearing() - b) > 10", arg=b3, timeout=T)
        # Pfeiltasten (Fokus auf der Karte)
        b4, _ = _view(pg)
        pg.evaluate("() => document.querySelector('#fm canvas').focus()")
        pg.keyboard.press("ArrowRight")
        pg.wait_for_function("(b) => Math.abs(document.getElementById('fm')._map.getBearing() - b) > 5", arg=b4, timeout=T)
        assert pg.evaluate("() => window.scrollY") == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_flug_browser_kamera_folgt_bleibt_unveraendert(pw, app):
    pg = _flug(pw, app)
    try:
        assert pg.evaluate("() => document.getElementById('fc').value") == "follow"
        box = pg.locator("#fm").bounding_box()
        pg.mouse.move(box["x"] + 300, box["y"] + 200)
        pg.mouse.wheel(80, 0)
        quiet(pg, 1000)
        assert pg.evaluate("() => document.getElementById('fm').dataset.rot || '0'") == "0"            # im Modus „folgt“ greift die neue Steuerung nicht
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
