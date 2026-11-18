"""3D-Flug, freie Kamera (3.39.0, in 3.40.0 neu geordnet): Bedienleiste statt Drehen-Modus, Zweifinger-Wischen dreht und neigt um den Tourpunkt, Maus/Touchpad-Erkennung, Einstellung,
einmaliger Hinweis. Die reinen Funktionen (js/07-flugsteuerung.js) werden mit Node geprüft, die Verdrahtung im Quelltext und – wenn der Testbrowser WebGL kann – in Chromium.
Echte Touchpads, Safari-Gesten und Mäuse lassen sich hier nur nachbilden (synthetische wheel-Ereignisse und Delta-Folgen), nicht an Hardware prüfen. Mit TS_SHOTS=<Ordner>: Screenshots."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "app" / "static" / "js"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="Node nicht installiert")


def _node(expr, pre=""):
    code = f"const m = require({json.dumps(str(JS / '07-flugsteuerung.js'))}); {pre} process.stdout.write(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)


# Delta-Folgen, wie sie Browser für eine Geste liefern (Beginn der Geste zuerst)
MAC_TOUCHPAD = [(0, 1), (0, 3), (-1, 6), (-1, 11), (-2, 17), (0, 24), (0, 31), (1, 18), (0, 9), (0, 4), (0, 1)]              # Chrome/Safari macOS: kleine ganze Zahlen, wechselnd, mit Querdrift
WIN_TOUCHPAD = [(0, 2.5), (0.5, 6.25), (0, 11.25), (-1.25, 17.5), (0, 8.75), (0, 3.75)]                                     # Windows-Präzisionstouchpad: Bruchteile
TOUCHPAD_QUER = [(4, 0), (9, 0), (15, 1), (22, 0), (12, 0)]
MAUS_WIN = [(0, 100), (0, 100), (0, 100)]                                                                                    # Chrome/Edge Windows: 100 je Raste
MAUS_120 = [(0, -120), (0, -240)]                                                                                            # Firefox/ältere: 120 je Raste, schnelles Drehen = Vielfache
MAUS_125 = [(0, 125), (0, 125)]                                                                                              # Windows mit 125 % Skalierung
MAUS_MAC = [(0, 4.000244140625), (0, 12.000732421875), (0, 40.00244140625), (0, -4.000244140625)]                            # Mausrad unter macOS (beschleunigt): Vielfache von 4,000244…
MAUS_UMSCHALT = [(100, 0), (100, 0)]                                                                                         # Umschalt + Mausrad: der Browser liefert deltaX


def _folge(seq, pref="auto", extra=""):
    ev = json.dumps([{"deltaX": x, "deltaY": y} for x, y in seq])
    return _node("r", f"const st = {{t: 0, kind: null}}; let t = 1000; const r = {ev}.map(e => {{ t += 16; return m.flWheelKind(Object.assign(e, {{{extra}}}), st, t, {json.dumps(pref)}); }});")


# ------------------------------------------------------------------  Maus oder Touchpad  ------------------------------------------------------------------
@pytest.mark.parametrize("seq,kind", [(MAC_TOUCHPAD, "touchpad"), (WIN_TOUCHPAD, "touchpad"), (TOUCHPAD_QUER, "touchpad"), (MAUS_WIN, "maus"), (MAUS_120, "maus"), (MAUS_125, "maus"), (MAUS_MAC, "maus")])
def test_klassifikation_mit_realistischen_delta_folgen(seq, kind):
    r = _folge(seq)
    assert set(r) == {kind}, r                                                    # einmal am Beginn entschieden und für die ganze Geste beibehalten


def test_klassifikation_zeilenmodus_und_umschalt_mausrad():
    assert set(_folge([(0, 3), (0, 3)], extra="deltaMode: 1")) == {"maus"}        # Firefox: Zeilen
    assert set(_folge([(0, 1)], extra="deltaMode: 2")) == {"maus"}
    assert set(_folge(MAUS_UMSCHALT, extra="shiftKey: true")) == {"maus"}         # kein seitliches Wischen
    assert _node("m.flWheelGuess({deltaX: 100, deltaY: 0})") == "maus"            # Rastschritt bleibt Maus (Kippen des Mausrads)
    assert _node("m.flWheelGuess({deltaX: -7, deltaY: 2})") == "touchpad"
    assert _node("m.flWheelGuess({deltaX: 0, deltaY: 53})") == "maus"             # großer ganzzahliger Schritt als erstes Ereignis
    assert _node("m.flWheelGuess({deltaX: 0, deltaY: 53.5})") == "touchpad"


def test_entscheidung_gilt_je_geste_und_faellt_nach_400_ms_ruhe_neu():
    # Touchpad-Geste erreicht mitten drin 100 (wäre allein „Maus“): bleibt Touchpad; nach 400 ms Ruhe entscheidet das nächste Ereignis neu
    r = _node("r", "const st = {t: 0, kind: null}; const r = [[1000, 2], [1016, 40], [1032, 100], [1048, 100], [1300, 100], [1701, 100], [1717, 3], [2200, 3]].map(([t, y]) => m.flWheelKind({deltaX: 0, deltaY: y}, st, t, 'auto'));")
    assert r == ["touchpad", "touchpad", "touchpad", "touchpad", "touchpad", "maus", "maus", "touchpad"]
    assert _node("m.FL_GESTE_MS") == 400


def test_einstellung_ueberschreibt_die_heuristik():
    assert set(_folge(MAUS_WIN, pref="touchpad")) == {"touchpad"}
    assert set(_folge(MAC_TOUCHPAD, pref="maus")) == {"maus"}
    assert set(_folge(MAUS_MAC, pref="touchpad")) == {"touchpad"}
    assert set(_folge(MAC_TOUCHPAD, pref="auto")) == {"touchpad"}
    # nach dem Zurückstellen auf „auto“ gilt wieder die Schätzung (07-flug.js verwirft dabei die gemerkte Geste)
    assert _node("r", "const st = {t: 0, kind: null}; m.flWheelKind({deltaY: 100}, st, 1000, 'touchpad'); st.kind = null; const r = m.flWheelKind({deltaY: 100}, st, 1010, 'auto');") == "maus"


# ------------------------------------------------------------------  was ein wheel-Ereignis tut  ------------------------------------------------------------------
def test_touchpad_wischen_dreht_und_neigt_maus_und_pinch_zoomen():
    assert _node("m.flWheelAction({deltaX: 40, deltaY: 0}, 'touchpad', false)") == {"bearing": 10, "pitch": 0}
    assert _node("m.flWheelAction({deltaX: 0, deltaY: 30}, 'touchpad', false)") == {"bearing": 0, "pitch": 6}            # senkrecht neigt (3.39.0: zoomte)
    d = _node("m.flWheelAction({deltaX: -20, deltaY: -10}, 'touchpad', false)")
    assert d == {"bearing": -5, "pitch": -2}                                                                               # schräg: beides zugleich
    assert _node("m.flWheelAction({deltaX: 0, deltaY: 100}, 'maus', false)") is None                                       # Mausrad: MapLibre zoomt
    assert _node("m.flWheelAction({deltaX: 100, deltaY: 0}, 'maus', false)") is None
    assert _node("m.flWheelAction({deltaX: 0, deltaY: 5, ctrlKey: true}, 'touchpad', false)") is None                      # Pinch = Strg+wheel: MapLibre zoomt
    assert _node("m.flWheelAction({deltaX: 0, deltaY: 5, metaKey: true}, 'touchpad', false)") is None
    assert _node("m.flWheelAction({deltaX: 0, deltaY: 0}, 'touchpad', false)") is None
    assert _node("m.flWheelAction({deltaX: 0, deltaY: 50, altKey: true}, 'maus', false)") == {"bearing": 0, "pitch": 10}  # Alt + Rad neigt, bei Maus und Touchpad
    assert _node("m.flWheelAction({deltaX: 30, deltaY: 0, altKey: true}, 'touchpad', false)")["pitch"] == 6               # macOS macht aus Alt+Wischen teils deltaX
    assert _node("m.flWheelAction({deltaX: 0, deltaY: 3, deltaMode: 1, altKey: true}, 'maus', false)")["pitch"] == pytest.approx(9.6)


def test_safari_geste_dreht_und_zoomt_ohne_doppelzoom():
    # während einer Geste meldet Safari den Pinch zusätzlich als Strg+wheel: verwerfen (nicht an MapLibre durchlassen)
    assert _node("m.flWheelAction({deltaX: 0, deltaY: -12, ctrlKey: true}, null, true)") == {"skip": True}
    assert _node("m.flWheelAction({deltaX: 0, deltaY: -12, ctrlKey: true}, null, false)") is None
    assert _node("m.flGestureDelta(10, 25)") == -15                                              # im Uhrzeigersinn: Richtung nimmt ab, die Karte dreht mit
    assert _node("m.flGestureStep({rotation: 0, scale: 1}, {rotation: 10, scale: 2})") == {"bearing": -10, "zoom": 1}
    # die Schritte einer Geste summieren sich genau zum Gesamtwert (kein doppeltes Anrechnen)
    r = _node("r", "const ev = [[0, 1], [2, 1.1], [5, 1.3], [9, 1.6], [12, 2], [12, 4]]; let z = 0, b = 0; for (let i = 1; i < ev.length; i++) { const d = m.flGestureStep({rotation: ev[i - 1][0], scale: ev[i - 1][1]}, {rotation: ev[i][0], scale: ev[i][1]}); z += d.zoom; b += d.bearing; } const r = [z, b];")
    assert r[0] == pytest.approx(2) and r[1] == pytest.approx(-12)
    assert _node("m.flGestureStep({rotation: 0, scale: 0}, {rotation: 0, scale: 0})")["zoom"] == 0


# ------------------------------------------------------------------  Orbit, Voreinstellungen, Tasten  ------------------------------------------------------------------
def test_orbit_dreht_die_kartenmitte_um_den_tourpunkt():
    p = {"lng": 8.0, "lat": 48.0}
    assert _node(f"m.flOrbit({json.dumps(p)}, {json.dumps(p)}, 77)") == pytest.approx(p)          # Mitte auf dem Punkt: bleibt
    z = _node(f"m.flOrbit({{lng: 8, lat: 47.99}}, {json.dumps(p)}, 90)")                          # Mitte südlich des Punkts, Blick dreht von Nord nach Ost: Mitte liegt danach westlich
    assert z["lat"] == pytest.approx(48.0, abs=1e-9) and z["lng"] < 8 and z["lng"] == pytest.approx(8 - 0.01 / 0.6691, abs=2e-4)
    z = _node(f"m.flOrbit({{lng: 8.01, lat: 48}}, {json.dumps(p)}, 180)")
    assert z["lng"] == pytest.approx(7.99) and z["lat"] == pytest.approx(48.0, abs=1e-9)
    # vier Vierteldrehungen = Ausgangslage; hin und zurück ebenso
    r = _node("c", f"let c = {{lng: 8.013, lat: 47.994}}; for (let i = 0; i < 4; i++) c = m.flOrbit(c, {json.dumps(p)}, 90);")
    assert r == pytest.approx({"lng": 8.013, "lat": 47.994}, abs=1e-9)
    r = _node("c", f"let c = {{lng: 8.013, lat: 47.994}}; c = m.flOrbit(c, {json.dumps(p)}, 33); c = m.flOrbit(c, {json.dumps(p)}, -33);")
    assert r == pytest.approx({"lng": 8.013, "lat": 47.994}, abs=1e-9)
    # der Abstand zum Punkt (in der Mercator-Ebene) bleibt gleich
    r = _node("[d(c0), d(c1)]", f"const P = {json.dumps(p)}, my = l => Math.log(Math.tan(Math.PI / 4 + l * Math.PI / 360)), d = c => Math.hypot((c.lng - P.lng) * Math.PI / 180, my(c.lat) - my(P.lat)); const c0 = {{lng: 8.02, lat: 48.01}}, c1 = m.flOrbit(c0, P, 47);")
    assert r[0] == pytest.approx(r[1], rel=1e-9)


def test_voreinstellungen():
    now = "{bearing: 40, pitch: 60}"
    assert _node(f"m.flPreset('nord', {now}, 123)") == {"bearing": 0, "pitch": 0, "zentrieren": False}
    assert _node(f"m.flPreset('oben', {now}, 123)") == {"bearing": 40, "pitch": 0, "zentrieren": True}
    assert _node(f"m.flPreset('schraeg', {now}, 123)") == {"bearing": 40, "pitch": 55, "zentrieren": True}
    assert _node(f"m.flPreset('hinter', {now}, 200)") == {"bearing": -160, "pitch": 72, "zentrieren": True}
    assert _node(f"m.flPreset('quatsch', {now}, 0)") is None


def test_ziehen_pfeiltasten_grenzen_und_richtungsworte():
    assert _node("m.flDragDelta(10, 0)")["bearing"] == 5
    assert _node("m.flDragDelta(-8, -4)") == {"bearing": -4, "pitch": 2}
    assert _node("m.flKeyDelta('ArrowLeft', false)") == {"bearing": -10, "pitch": 0}
    assert _node("m.flKeyDelta('ArrowRight', true)") == {"bearing": 20, "pitch": 0}
    assert _node("m.flKeyDelta('ArrowUp', false)") == {"bearing": 0, "pitch": 5}
    assert _node("m.flKeyDelta('a', false)") is None and _node("m.flKeyDelta('Tab', false)") is None
    assert _node("[m.flClampPitch(-5), m.flClampPitch(50), m.flClampPitch(99)]") == [0, 50, 85]
    assert _node("[m.flNorm(190), m.flNorm(-190), m.flNorm(360), m.flNorm(45)]") == [-170, 170, 0, 45]
    assert _node("[0, 44, 90, 135, 180, -135, -90, -45, 350, 720].map(m.flRichtung)") == ["Norden", "Nordosten", "Osten", "Südosten", "Süden", "Südwesten", "Westen", "Nordwesten", "Norden", "Norden"]


def test_verdrahtung_im_flug():
    src = (JS / "07-flug.js").read_text(encoding="utf-8")
    for weg in ('id="frot"', "aria-pressed", "frotmode", "setRot", 'id="fhelp"', "↻ Drehen"):                # der Drehen-Modus ist entfernt
        assert weg not in src, weg
    css = (ROOT / "app" / "static" / "style.css").read_text(encoding="utf-8")
    assert "frot" not in css and "overscroll-behavior:contain" in css
    i18n = (JS / "00-i18n-neu.js").read_text(encoding="utf-8")
    assert "Drehen-Modus" not in i18n and "↻ Drehen" not in i18n
    for k in ('id="fnav"', 'id="fnn"', 'id="fnl"', 'id="fnr"', 'id="fnf"', 'id="fns"', 'id="fpo"', 'id="fps"', 'id="fpt"', 'id="fnh"', 'id="fin"', 'id="fhint"', 'aria-live="polite"',
              "pointerdown", "wheel", "keydown", "gesturechange", "gestureend", "flDragDelta", "flWheelKind", "flWheelAction", "flOrbit", "flPreset", "flGestureStep", "flKeyDelta",
              "prefers-reduced-motion", "flug_bedienung", "flug_hinweis"):
        assert k in src, k
    assert "passive: false" in src and "alert(" not in src.replace("uiAlert(", "")                            # wheel muss abbrechbar sein; kein window.alert
    for t in ("Bedienung: Automatisch", "Norden / Draufsicht", "Hinter der Tour", "Zwei Finger wischen: drehen und neigen · Zwei Finger spreizen: zoomen · oder die Tasten rechts", "Blick nach Nordosten",
              "Neigung {} Grad", "Alt + Mausrad: neigen"):
        assert ("\n" + t + " || ") in i18n, t
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("js/07-flug.js") < html.index("js/07-flugsteuerung.js")


# ------------------------------------------------------------------  Browser (nur mit WebGL)  ------------------------------------------------------------------
from tests.helpers_ui import T, press_until_gone, quiet, settled  # noqa: E402
from tests.test_seitenlayout_ui import _browser, pw  # noqa: E402,F401
from tests.test_reise_seiten_ui import app  # noqa: E402,F401

MAP = "document.getElementById('fm')._map"


def _flug(pw, app, width=1280, height=800, scheme="light", locale="de-DE", hinweis_gesehen=True, lang="de"):
    pytest.importorskip("playwright.sync_api")
    pg = _browser(pw, app, devs=None, width=width, height=height, scheme=scheme, locale=locale)
    pg.context.add_init_script("try { if (!sessionStorage.getItem('_init')) { sessionStorage.setItem('_init', '1'); localStorage.removeItem('flug_bedienung'); localStorage.setItem('lang', %r); %s } } catch (e) {}"
                               % (lang, "localStorage.setItem('flug_hinweis', '1');" if hinweis_gesehen else "localStorage.removeItem('flug_hinweis');"))
    _start(pg, app)
    return pg


def _start(pg, app):
    pg.goto(f"{app}/#/flight/h0")
    pg.wait_for_function("() => !!document.getElementById('fm') && (!!document.getElementById('fm')._map || /WebGL|noch keine Strecke/.test(document.getElementById('fmsg').textContent))", timeout=30000)
    if not pg.evaluate("() => !!document.getElementById('fm')._map"):
        msg = pg.evaluate("() => document.getElementById('fmsg').textContent")
        pg.browser_.close()
        pytest.skip("kein WebGL im Testbrowser: " + msg)
    pg.wait_for_function("() => !!document.getElementById('fnn').onclick && !!document.getElementById('fp').onclick", timeout=T)


def _view(pg):
    return pg.evaluate(f"() => {{ const m = {MAP}; return [m.getBearing(), m.getPitch(), m.getZoom()]; }}")


def _klick(pg, sel):
    """Knopf per Ereignis auslösen (die WebGL-Seite zeichnet im Testbrowser langsam; die Stabilitätsprüfung von Playwright würde warten)."""
    pg.evaluate("(s) => document.querySelector(s).click()", sel)


def _pause(pg):
    """Flug anhalten: der Tourpunkt (Drehpunkt) steht still."""
    if pg.evaluate("() => document.getElementById('fp').textContent.includes('Pause')"):
        _klick(pg, "#fp")
    pg.wait_for_function("() => !document.getElementById('fp').textContent.includes('Pause')", timeout=T)


def _punkt(pg):
    """Bildposition des Tourpunkts (Marker)."""
    return pg.evaluate(f"() => {{ const m = {MAP}, h = document.getElementById('fm')._hier(), p = m.project([h.lng, h.lat]); return [p.x, p.y]; }}")


def _wheel(pg, dx, dy, **mods):
    """Synthetisches wheel-Ereignis genau mit diesen Deltas (pg.mouse.wheel rundet/teilt je nach Plattform)."""
    return pg.evaluate("([dx, dy, mods]) => { const c = document.querySelector('#fm canvas'), r = c.getBoundingClientRect(); return c.dispatchEvent(new WheelEvent('wheel', Object.assign({deltaX: dx, deltaY: dy, clientX: r.left + r.width / 2, clientY: r.top + r.height / 3, bubbles: true, cancelable: true}, mods))); }",
                       [dx, dy, mods])


def _wheels(pg, seq, **mods):
    """Eine Geste: mehrere wheel-Ereignisse unmittelbar nacheinander (ein Aufruf – zwischen einzelnen Aufrufen vergeht im langsamen WebGL-Testbrowser mehr als die Gestenpause)."""
    return pg.evaluate("([seq, mods]) => { const c = document.querySelector('#fm canvas'), r = c.getBoundingClientRect(); return seq.map(([dx, dy]) => c.dispatchEvent(new WheelEvent('wheel', Object.assign({deltaX: dx, deltaY: dy, clientX: r.left + r.width / 2, clientY: r.top + r.height / 3, bubbles: true, cancelable: true}, mods)))); }",
                       [[list(x) for x in seq], mods])


def _ruhe_geste(pg):
    """Auf das Ende der Geste warten: hier ist die verstrichene Zeit selbst der Zustand (neu entschieden wird nach 400 ms ohne wheel-Ereignis)."""
    t0 = pg.evaluate("() => performance.now()")
    pg.wait_for_function("(t) => performance.now() - t > 450", arg=t0, timeout=T)


def _ueberlappt(pg, a, b):
    return pg.evaluate("([a, b]) => { const x = document.querySelector(a), y = document.querySelector(b); if (!x || !y) return false; const r = x.getBoundingClientRect(), s = y.getBoundingClientRect(); if (!r.width || !s.width) return false; return !(r.right <= s.left || s.right <= r.left || r.bottom <= s.top || s.bottom <= r.top); }", [a, b])


def _shot(pg, name):
    d = os.environ.get("TS_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        quiet(pg, 3000)
        pg.screenshot(path=str(Path(d) / name), timeout=60000)


def test_bedienleiste_dreht_neigt_um_den_tourpunkt_und_voreinstellungen(pw, app):
    pg = _flug(pw, app)
    try:
        # echte Knöpfe mit Namen, mindestens 40 px, immer sichtbar (auch wenn sich das Bedienfeld ausblendet)
        infos = pg.evaluate("() => [...document.querySelectorAll('#fnav .fnb')].map(b => { const r = b.getBoundingClientRect(); return [b.tagName, b.type, (b.getAttribute('aria-label') || b.textContent).trim(), r.width, r.height]; })")
        assert len(infos) == 9 and all(i[0] == "BUTTON" and i[1] == "button" and i[2] and i[3] >= 40 and i[4] >= 40 for i in infos), infos
        assert [i[2] for i in infos] == ["Norden / Draufsicht", "Hilfe zur Bedienung", "Nach links drehen", "Nach rechts drehen", "Flacher neigen", "Steiler neigen", "Von oben", "Schräg", "Hinter der Tour"]
        assert pg.get_attribute("#fnav", "role") == "group" and pg.get_attribute("#fnav", "aria-label") == "Kamera steuern"
        pg.evaluate("() => document.getElementById('fl').classList.add('idle')")
        assert pg.evaluate("() => getComputedStyle(document.getElementById('fnav')).opacity") == "1"
        pg.evaluate("() => document.getElementById('fnr').focus()")
        assert pg.evaluate("() => { const b = document.getElementById('fnr'); return b.matches(':focus-visible') ? getComputedStyle(b).outlineStyle !== 'none' && parseFloat(getComputedStyle(b).outlineWidth) >= 2 : true; }")
        for a, b in ((".fnav", ".fbar"), (".fnav", ".fctl"), (".fnav", "#fph")):
            assert not _ueberlappt(pg, a, b), (a, b)
        _pause(pg)
        assert pg.evaluate("() => document.getElementById('fc').value") == "follow"
        # Bedienen der Leiste wechselt in die freie Kamera
        _klick(pg, "#fnr")
        pg.wait_for_function("() => document.getElementById('fc').value === 'free'", timeout=T)
        # Drehen: 15 Grad, der Tourpunkt bleibt an seiner Stelle im Bild (Orbit) – auch wenn er nicht in der Bildmitte liegt
        pg.evaluate(f"() => {{ const m = {MAP}; m.jumpTo({{center: [m.getCenter().lng + 0.004, m.getCenter().lat - 0.003]}}); }}")
        b0, p0, z0 = _view(pg)
        x0, y0 = _punkt(pg)
        _klick(pg, "#fnr")
        pg.wait_for_function(f"(b) => Math.abs(((({MAP}.getBearing() - b) % 360) + 540) % 360 - 180 - 15) < 0.01", arg=b0, timeout=T)
        x1, y1 = _punkt(pg)
        assert abs(x1 - x0) < 1.5 and abs(y1 - y0) < 1.5, (x0, y0, x1, y1)
        _klick(pg, "#fnl"); _klick(pg, "#fnl")
        pg.wait_for_function(f"(b) => Math.abs(((({MAP}.getBearing() - b) % 360) + 540) % 360 - 180 + 15) < 0.01", arg=b0, timeout=T)
        x2, y2 = _punkt(pg)
        assert abs(x2 - x0) < 1.5 and abs(y2 - y0) < 1.5
        # Neigen: steiler −10, flacher +10, an den Grenzen fest
        _klick(pg, "#fns")
        pg.wait_for_function(f"(p) => Math.abs({MAP}.getPitch() - (p - 10)) < 0.01", arg=p0, timeout=T)
        _klick(pg, "#fnf"); _klick(pg, "#fnf")
        pg.wait_for_function(f"(p) => Math.abs({MAP}.getPitch() - (p + 10)) < 0.01", arg=p0, timeout=T)
        for _ in range(4):
            _klick(pg, "#fnf")
        assert _view(pg)[1] == pytest.approx(85)
        assert _view(pg)[2] == pytest.approx(z0)                                                             # nichts davon zoomt
        # Voreinstellungen (Testbrowser: Bewegung reduziert → ohne Animation, sofort am Ziel)
        _klick(pg, "#fpo")
        assert _view(pg)[1] == pytest.approx(0, abs=0.01)
        c = pg.evaluate(f"() => {{ const m = {MAP}, a = m.getCenter(), b = document.getElementById('fm')._hier(); return [a.lng - b.lng, a.lat - b.lat]; }}")
        assert abs(c[0]) < 1e-6 and abs(c[1]) < 1e-6                                                         # Tourpunkt in der Bildmitte
        _klick(pg, "#fps")
        assert _view(pg)[1] == pytest.approx(55, abs=0.01)
        _klick(pg, "#fnr")
        _klick(pg, "#fpt")
        v = _view(pg)
        assert v[1] == pytest.approx(72, abs=0.01)
        assert v[0] == pytest.approx(pg.evaluate("() => { const t = document.getElementById('fm')._hier().tgt; return ((t + 180) % 360 + 360) % 360 - 180; }"), abs=0.01)      # Laufrichtung der Tour
        hinter = v[0]
        _klick(pg, "#fnr"); _klick(pg, "#fpt")
        assert _view(pg)[0] == pytest.approx(hinter, abs=0.01)                                               # „Hinter der Tour“ stellt die Laufrichtung wieder her
        _klick(pg, "#fnn")
        v = _view(pg)
        assert v[0] == pytest.approx(0, abs=0.01) and v[1] == pytest.approx(0, abs=0.01)
        # Kompassnadel folgt, Text für Screenreader kommt höflich und gedrosselt
        _klick(pg, "#fnr")
        pg.wait_for_function("() => /rotate\\(-15/.test(document.getElementById('fnk').style.transform)", timeout=T)
        assert pg.get_attribute("#fsr", "aria-live") == "polite"
        pg.wait_for_function("() => document.getElementById('fsr').textContent === 'Blick nach Norden · Neigung 0 Grad'", timeout=T)
        _klick(pg, "#fnr"); _klick(pg, "#fnr"); _klick(pg, "#fnf")
        pg.wait_for_function("() => document.getElementById('fsr').textContent === 'Blick nach Nordosten · Neigung 10 Grad'", timeout=T)
        _shot(pg, "flug-leiste-1280-hell.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_wischen_dreht_und_neigt_mausrad_zoomt_einstellung_geht_vor(pw, app):
    pg = _flug(pw, app)
    try:
        _pause(pg)
        pg.select_option("#fc", "free")
        assert pg.evaluate("() => document.getElementById('fin').value") == "auto"
        # Touchpad-Folge (klein, wechselnd, mit Querbewegung): dreht und neigt, zoomt nicht, die Seite scrollt nicht
        b0, p0, z0 = _view(pg)
        x0, y0 = _punkt(pg)
        assert _wheels(pg, ((2, 1), (6, 2), (12, 5), (20, 8), (10, 4))) == [False] * 5                        # preventDefault: die Seite scrollt nicht
        b1, p1, z1 = _view(pg)
        assert b1 - b0 == pytest.approx(50 * 0.25, abs=0.01) and p1 - p0 == pytest.approx(20 * 0.2, abs=0.01) and z1 == pytest.approx(z0)
        x1, y1 = _punkt(pg)
        assert abs(x1 - x0) < 1.5                                                                            # gedreht um den Tourpunkt
        # Mausrad (Rastschritte) nach einer Pause: zoomt, dreht und neigt nicht
        _ruhe_geste(pg)
        n0 = pg.evaluate("() => document.getElementById('fm').dataset.rot")
        _wheels(pg, ((0, -100), (0, -100)))
        pg.wait_for_function(f"(z) => {MAP}.getZoom() > z + 0.05", arg=z1, timeout=T)
        assert pg.evaluate("() => document.getElementById('fm').dataset.rot") == n0
        b2, p2, _ = _view(pg)
        assert b2 == pytest.approx(b1) and p2 == pytest.approx(p1)
        # Pinch (Strg + wheel) zoomt ebenfalls, Alt + Rad neigt
        _ruhe_geste(pg)
        pg.wait_for_function(f"() => !{MAP}.isZooming()", timeout=T)
        z2 = _view(pg)[2]
        _wheels(pg, ((0, -8), (0, -8)), ctrlKey=True)
        pg.wait_for_function(f"(z) => {MAP}.getZoom() > z + 0.01", arg=z2, timeout=T)
        assert pg.evaluate("() => document.getElementById('fm').dataset.rot") == n0
        _wheel(pg, 0, -50, altKey=True)
        assert _view(pg)[1] == pytest.approx(p1 - 10, abs=0.01)
        # Einstellung „Touchpad“: auch Rastschritte neigen (kein Zoom); bleibt im Browser gemerkt
        pg.select_option("#fin", "touchpad")
        assert pg.evaluate("() => localStorage.getItem('flug_bedienung')") == "touchpad"
        pg.wait_for_function(f"() => !{MAP}.isZooming()", timeout=T)
        _, p3, z3 = _view(pg)
        _wheel(pg, 0, 100)
        _, p4, z4 = _view(pg)
        assert p4 - p3 == pytest.approx(20, abs=0.01) and z4 == pytest.approx(z3)
        # Einstellung „Maus“: auch kleine Wisch-Deltas drehen nicht
        pg.select_option("#fin", "maus")
        b5, p5, _ = _view(pg)
        n1 = pg.evaluate("() => document.getElementById('fm').dataset.rot")
        _wheels(pg, ((6, 2), (12, 5)))
        assert pg.evaluate("() => document.getElementById('fm').dataset.rot") == n1 and _view(pg)[0] == pytest.approx(b5) and _view(pg)[1] == pytest.approx(p5)
        # Umschalt + Ziehen und Pfeiltasten gehen weiter
        box = pg.locator("#fm").bounding_box()
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 3
        b6 = _view(pg)[0]
        pg.keyboard.down("Shift")
        pg.mouse.move(cx, cy); pg.mouse.down(); pg.mouse.move(cx - 80, cy, steps=6); pg.mouse.up()
        pg.keyboard.up("Shift")
        pg.wait_for_function(f"(b) => Math.abs({MAP}.getBearing() - b) > 10", arg=b6, timeout=T)
        b7 = _view(pg)[0]
        pg.evaluate("() => document.querySelector('#fm canvas').focus()")
        pg.keyboard.press("ArrowRight")
        pg.wait_for_function(f"(b) => Math.abs({MAP}.getBearing() - b) > 5", arg=b7, timeout=T)
        assert pg.evaluate("() => window.scrollY") == 0
        assert pg.evaluate("() => getComputedStyle(document.getElementById('fm')).overscrollBehaviorY") == "contain"
        # nach dem Neuladen ist die Einstellung wieder da
        pg.reload()
        _start(pg, app)
        assert pg.evaluate("() => document.getElementById('fin').value") == "maus"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_kamera_folgt_bleibt_unveraendert(pw, app):
    pg = _flug(pw, app, hinweis_gesehen=False)
    try:
        assert pg.evaluate("() => document.getElementById('fc').value") == "follow"
        assert pg.evaluate("() => document.getElementById('fhint').hidden")                             # solange die Kamera folgt, erscheint kein Hinweis
        _wheels(pg, ((1, 2), (3, 5), (6, 8), (12, 20), (20, 31), (9, 12)))                            # eine Touchpad-Geste: MapLibre zoomt wie bisher (und beendet damit das Folgen)
        quiet(pg, 1000)
        assert pg.evaluate("() => document.getElementById('fm').dataset.rot || '0'") == "0"            # im Modus „folgt“ greift die neue Steuerung nicht
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_hinweis_nur_einmal_und_ueber_das_fragezeichen_wieder(pw, app):
    pg = _flug(pw, app, hinweis_gesehen=False)
    pg.on("dialog", lambda d: (pg.errors.append("window-Dialog: " + d.message), d.dismiss()))
    try:
        h = pg.locator("#fhint")
        assert pg.evaluate("() => document.getElementById('fhint').hidden")
        _klick(pg, "#fnr")                                                                              # erster Wechsel in die freie Kamera
        pg.wait_for_function("() => !document.getElementById('fhint').hidden", timeout=T)
        assert pg.evaluate("() => document.getElementById('fhk').textContent") == "Zwei Finger wischen: drehen und neigen · Zwei Finger spreizen: zoomen · oder die Tasten rechts"
        assert pg.evaluate("() => document.getElementById('fhp').hidden")                               # kurz: ohne die Belegungen für Geübte
        assert pg.get_attribute("#fnh", "aria-expanded") == "true"
        assert pg.evaluate("() => document.activeElement.id") != "fhx"                                  # der Hinweis nimmt den Fokus nicht weg
        for a, b in ((".fhint", ".fnav"), (".fhint", ".fbar"), (".fhint", ".fctl")):
            assert not _ueberlappt(pg, a, b), (a, b)
        _klick(pg, "#fhx")
        pg.wait_for_function("() => document.getElementById('fhint').hidden", timeout=T)
        assert pg.get_attribute("#fnh", "aria-expanded") == "false"
        _klick(pg, "#fnl"); pg.select_option("#fc", "follow"); pg.select_option("#fc", "free")
        assert pg.evaluate("() => document.getElementById('fhint').hidden")                             # kommt nicht wieder
        # „?“ ruft die Hilfe mit allen Belegungen auf; Fokus hinein, Escape schließt und gibt den Fokus zurück
        _klick(pg, "#fnh")
        pg.wait_for_function("() => !document.getElementById('fhint').hidden && !document.getElementById('fhp').hidden", timeout=T)
        txt = pg.evaluate("() => document.getElementById('fhint').innerText")
        for t in ("Umschalt + Ziehen", "Rechte Maustaste oder Strg/Cmd + Ziehen", "Pfeiltasten", "Alt + Mausrad", "Mausrad: zoomen", "Bedienung"):
            assert t in txt, t
        assert pg.evaluate("() => document.activeElement.id") == "fhx"
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => document.getElementById('fhint').hidden", timeout=T)
        assert pg.evaluate("() => document.activeElement.id") == "fnh" and pg.evaluate("() => location.hash").startswith("#/flight/")
        _klick(pg, "#fnh"); _klick(pg, "#fnh")                                                           # „?“ schaltet um
        assert pg.evaluate("() => document.getElementById('fhint').hidden")
        # nach dem Neuladen: kein Hinweis mehr
        pg.reload()
        _start(pg, app)
        _klick(pg, "#fnr")
        pg.wait_for_function("() => document.getElementById('fc').value === 'free'", timeout=T)
        assert pg.evaluate("() => document.getElementById('fhint').hidden")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("lang,scheme", [("de", "dark"), ("en", "dark")])
def test_390_px_ohne_ueberlappung_dunkel_und_englisch(pw, app, lang, scheme):
    pg = _flug(pw, app, width=390, height=844, scheme=scheme, hinweis_gesehen=False, lang=lang, locale="en-GB" if lang == "en" else "de-DE")
    try:
        _pause(pg)
        quiet(pg, 3000)
        assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        for a, b in ((".fnav", ".fbar"), (".fnav", ".fctl"), (".fnav", "#fph")):
            assert not _ueberlappt(pg, a, b), (a, b)
        r = pg.evaluate("() => { const r = document.getElementById('fnav').getBoundingClientRect(); return [r.left, r.right, r.top, r.bottom, window.innerWidth, window.innerHeight]; }")
        assert r[0] >= 0 and r[1] <= r[4] and r[2] >= 0 and r[3] <= r[5], r
        assert pg.evaluate("() => [...document.querySelectorAll('#fnav .fnb')].every(b => { const r = b.getBoundingClientRect(); return r.width >= 40 && r.height >= 40 && b.scrollWidth <= b.clientWidth + 1; })")
        if lang == "en":
            assert pg.evaluate("() => [...document.querySelectorAll('#fnav .fnb')].map(b => (b.getAttribute('aria-label') || b.textContent).trim())") == \
                ["North / top view", "Help with the controls", "Rotate left", "Rotate right", "Tilt flatter", "Tilt steeper", "From above", "Angled", "Behind the tour"]
            assert pg.evaluate("() => [...document.getElementById('fin').options].map(o => o.textContent)") == ["Controls: automatic", "Controls: mouse", "Controls: touchpad"]
        _klick(pg, "#fnr")
        pg.wait_for_function("() => !document.getElementById('fhint').hidden", timeout=T)
        if lang == "en":
            assert pg.evaluate("() => document.getElementById('fhk').textContent") == "Swipe with two fingers: rotate and tilt · Spread two fingers: zoom · or use the buttons on the right"
            pg.wait_for_function("() => document.getElementById('fsr').textContent.startsWith('Looking ')", timeout=T)
        for a, b in ((".fhint", ".fnav"), (".fhint", ".fbar"), (".fhint", ".fctl")):
            assert not _ueberlappt(pg, a, b), (a, b)
        r = pg.evaluate("() => { const r = document.getElementById('fhint').getBoundingClientRect(); return [r.left, r.right, window.innerWidth]; }")
        assert r[0] >= 0 and r[1] <= r[2]
        _shot(pg, f"flug-leiste-390-dunkel{'-en' if lang == 'en' else ''}.png")
        _klick(pg, "#fnh"); _klick(pg, "#fnh")
        pg.wait_for_function("() => !document.getElementById('fhint').hidden && !document.getElementById('fhp').hidden", timeout=T)
        assert not _ueberlappt(pg, ".fhint", ".fnav")
        r = pg.evaluate("() => { const r = document.getElementById('fhint').getBoundingClientRect(); return [r.left, r.right, window.innerWidth, r.top, r.bottom, window.innerHeight]; }")
        assert r[0] >= 0 and r[1] <= r[2] and r[4] <= r[5]
        _shot(pg, f"flug-hilfe-390-dunkel{'-en' if lang == 'en' else ''}.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
