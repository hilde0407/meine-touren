"""3.61.4 – 3D-Flug flüssiger (Handy-WebView mit MapLibre GL). Vorbild: Mein Tourentagebuch 2.16.0.
Rechenlogik (js/07-flugrechnung.js) mit Node; Verdrahtung in Chromium (Handy-Fenster 390 × 844, html.mob, Pixeldichte 2,75, Tour mit 3000 Punkten und 30 Fotos):
Linie und Kopfzeile nur im Takt, keine readPixels-Bremse, Fotos als Kartenebene, Pixeldichte begrenzt, Anpassung mit Hysterese, Kamera hängt nur von der Position ab,
Flug läuft / Pause / Schieberegler / Foto-Einblendung / Reiseflug / Aufnahme funktionieren weiter. Software-Zeichnen: gemessen wird die Zahl der Aktualisierungen, nicht die Bildzeit."""
import json
import math
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

import pytest

from tests.helpers_ui import T
from tests.test_seitenlayout_ui import _browser, pw  # noqa: F401
from tests.test_reise_seiten_ui import app  # noqa: E402,F401

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "app" / "static" / "js"
MAP = "document.getElementById('fm')._map"
FL = "document.getElementById('fm')._flug"
node = pytest.mark.skipif(not shutil.which("node"), reason="Node nicht installiert")


def _node(expr, pre=""):
    code = f"const m = require({json.dumps(str(JS / '07-flugrechnung.js'))}); {pre} process.stdout.write(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)


# ------------------------------------------------------------------  Rechenlogik (Node)  ------------------------------------------------------------------
@node
def test_stufen_vorgabe_und_pixelratio():
    assert _node("[m.stufe('', true), m.stufe(null, false), m.stufe('normal', true), m.stufe('quatsch', true)]") == ["fluessig", "schoen", "normal", "fluessig"]
    # nie über dem Gerät und nie über der Grenze der Stufe (Handy mit Pixeldichte 3: „Flüssig“ zeichnet mit 1, also ein Neuntel der Bildpunkte)
    assert _node("[m.pixelRatio('fluessig', 3), m.pixelRatio('normal', 3), m.pixelRatio('schoen', 3), m.pixelRatio('schoen', 2), m.pixelRatio('schoen', 5), m.pixelRatio('normal', 1), m.pixelRatio('normal', 0)]") == [1, 1.5, 3, 2, 3, 1, 1]
    s = _node("m.STUFEN")
    assert s["fluessig"]["dem"] < s["normal"]["dem"] < s["schoen"]["dem"] and s["fluessig"]["spur"] > s["schoen"]["spur"] and s["fluessig"]["tol"] > s["schoen"]["tol"]
    assert s["schoen"]["ueber"] == 1.5 and s["schoen"]["neig"] == 68 and s["schoen"]["dem"] == 15      # „Schön“ = bisheriges Aussehen
    assert _node("m.BILD_MIN_MS") == 10 and _node("[m.tiefer('schoen'), m.tiefer('normal'), m.tiefer('fluessig')]") == ["normal", "fluessig", None]


@node
def test_duennen_behaelt_enden_und_form():
    # gerade Strecke mit Zickzack unter 1 m: bei 3 m Toleranz bleiben nur die Enden; ein Knick von 50 m bleibt
    r = _node("m.duenneIdx(pts, 3)", "const pts = Array.from({length: 200}, (_, i) => [11 + i * 1e-5, 48 + (i % 2) * 4e-6]);")
    assert r == [0, 199]
    r = _node("m.duenneIdx(pts, 3)", "const pts = Array.from({length: 101}, (_, i) => [11 + Math.min(i, 50) * 1e-5, 48 + Math.max(0, i - 50) * 1e-5]);")
    assert r[0] == 0 and r[-1] == 100 and 50 in r and len(r) <= 4
    assert _node("m.duenneIdx([[1, 1], [2, 2]], 3)") == [0, 1] and _node("m.duenneIdx([], 3)") == []


@node
def test_anpassung_mit_hysterese():
    # 30 langsame Bilder → eine Stufe herunter; danach 60 Bilder Ruhe, nie wieder hinauf, kein Hin und Her
    r = _node("log", "const a = m.adaptiv('schoen'); const log = []; for (let i = 0; i < 400; i++) { const n = m.adaptivSchritt(a, 60); if (n) log.push([i, n]); }")
    assert r == [[29, "normal"], [29 + 60 + 30, "fluessig"]]               # unten angekommen: keine weitere Stufe
    # schnell genug: nichts; Ausreißer (> 1 s) und 0 zählen nicht
    assert _node("log", "const a = m.adaptiv('schoen'); const log = []; for (let i = 0; i < 300; i++) { const n = m.adaptivSchritt(a, i % 10 === 0 ? 5000 : 16); if (n) log.push(n); }") == []
    assert _node("[m.adaptivSchritt(m.adaptiv('schoen'), 0), m.adaptivSchritt(m.adaptiv('schoen'), 2000)]") == [None, None]
    # Schnitt knapp unter 40 ms: nichts
    assert _node("log", "const a = m.adaptiv('schoen'); const log = []; for (let i = 0; i < 300; i++) { const n = m.adaptivSchritt(a, 39); if (n) log.push(n); }") == []


@node
def test_kamera_ist_reine_funktion_der_position():
    pre = """const N = 300, S = Array.from({length: N}, (_, i) => ({lng: 11 + 0.0002 * i, lat: 48 + 0.001 * Math.sin(i / 30)}));
      const P = S.map((s, i) => Object.assign({lng: s.lng, lat: s.lat}, i > 100 && i < 140 ? {trans: true, tq: (i - 100) / 40, lift: 2} : {}));
      const B = {S, P, brg: m.peilungen(S, 6, 3), neig: m.neigTabelle(N, 3)}; B.neig.w[10] = 50;
      const o = {neigung: 'auto', basis: 68, zBase: 14.8, set: true, rec: false};"""
    r = _node("[m.kamera(150.5, B, o), m.kamera(30, B, o), m.kamera(150.5, B, o)]", pre)
    assert r[0] == r[2]                                                     # gleiche Position → gleiche Kamera, egal was dazwischen berechnet wurde
    assert r[1]["pitch"] < 68 and 0 <= r[1]["bearing"] < 360
    # Übergang: herauszoomen (lift 2 in der Mitte) und steiler von oben
    t = _node("m.kamera(120, B, o)", pre)
    assert abs(t["zoom"] - (14.8 - 2)) < 1e-9 and abs(t["pitch"] - (68 - 22)) < 1e-9
    # Einzelflug ohne Aufnahme: Zoom bleibt dem Menschen überlassen; feste Neigung: keine Vorgabe; Aufnahme: näher
    e = _node("[m.kamera(50, B, {neigung: null, basis: 68, zBase: 14.8, set: false, rec: false}), m.kamera(50, B, {neigung: 'auto', basis: 68, zBase: 14.8, set: false, rec: true})]", pre)
    assert e[0]["zoom"] is None and e[0]["pitch"] is None and abs(e[1]["zoom"] - 15.7) < 1e-9
    # Blickrichtung zeigt die Laufrichtung (Osten ≈ 90°), auch über 0°/360° gemittelt
    assert abs(_node("m.peilungen(S, 6, 3)[100]", pre) - 90) < 15
    assert _node("m.winkelLerp(350, 10, 0.5)") == 0


@node
def test_neigung_nimmt_berge_voraus():
    # Berg direkt vor dem Punkt → steilerer Blick (kleinerer Winkel), ohne Höhendaten: voll = false
    assert _node("m.freieNeigung(() => 0, 11, 48, 0, 68, 400).th") == 68
    r = _node("m.freieNeigung((a, b) => b < 48 - 0.0003 ? 600 : 0, 11, 48, 0, 68, 400)")
    assert r["th"] < 68 and r["voll"]
    assert _node("m.freieNeigung(() => null, 11, 48, 0, 68, 400).voll") is False
    assert _node("[m.neigBei(null, 5, 64), m.neigBei(m.neigTabelle(100, 5), 17.3, 64)]") == [64, 64]


def test_quelltext_verdrahtung():
    s = (JS / "07-flug.js").read_text(encoding="utf8")
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf8")
    assert html.index("js/07-flugrechnung.js") < html.index("js/07-flug.js") < html.index("js/07-flugsteuerung.js")
    assert "pixelRatio: FlugCalc.pixelRatio" in s and "BILD_MIN_MS" in s and "_updateOpacity" in s and '"circle"' in s
    assert "setData(line(" in s and s.count("setData(") == 1                  # nur eine Stelle, die die Linie neu setzt (gedrosselt in draw())
    assert 'class="fcam"' not in s and 'el.className = "fcam"' not in s       # keine HTML-Marker mehr für Fotos
    for sprache in ("Darstellung: Flüssig", "Darstellung: Normal", "Darstellung: Schön", "3D-Flug: Darstellung", "Flug vereinfacht"):
        assert sprache in (JS / "00-i18n-neu.js").read_text(encoding="utf8")


# ------------------------------------------------------------------  Browser  ------------------------------------------------------------------
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cf00000301010018dd8db40000000049454e44ae426082")
INSTR = """() => {
  const Z = window.__mz = {setData: 0, read: 0, fh: 0, val: 0, mut: 0};
  for (const C of [window.WebGLRenderingContext, window.WebGL2RenderingContext]) if (C) { const f = C.prototype.readPixels; C.prototype.readPixels = function () { Z.read++; return f.apply(this, arguments); }; }
  const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
  Object.defineProperty(HTMLInputElement.prototype, 'value', { get: d.get, set(v) { if (this.id === 'fs') Z.val++; return d.set.call(this, v); }, configurable: true });
}"""
HOOK = """() => {
  const Z = window.__mz, m = document.getElementById('fm')._map, s = m.getSource('done');
  if (!s) return false;
  if (!s.__w) { s.__w = 1; const f = s.setData.bind(s); s.setData = g => { Z.setData++; return f(g); };
    new MutationObserver(r => { Z.fh += r.length; }).observe(document.getElementById('fh'), {subtree: true, childList: true, characterData: true});
    new MutationObserver(r => { Z.mut += r.length; }).observe(document.getElementById('fl'), {subtree: true, childList: true, attributes: true, characterData: true}); }
  return true;
}"""


def _spur(n=3000, off=0.0):
    out = []
    for i in range(n):
        a = i / 60.0
        r = 0.002 + 0.00001 * i
        out.append([48.0 + off + r * math.sin(a) + 0.00005 * math.sin(i * 1.7), 11.0 + r * math.cos(a) * 1.5, 500 + 80 * math.sin(i / 90), i * 10000])
    return out


def _flug(pw, app, mob=True, dpr=2.75, flug_id="h0", stufe=None, fotos=30, width=390, height=844):
    pytest.importorskip("playwright.sync_api")
    pg = _browser(pw, app, devs=None, width=width, height=height, dpr=dpr)
    ini = "try { if (!sessionStorage.getItem('_i')) { sessionStorage.setItem('_i', '1'); localStorage.setItem('flug_hinweis', '1'); localStorage.setItem('viewmode', %r); %s } } catch (e) {}" % (
        "mobile" if mob else "desktop", f"localStorage.setItem('flug_stufe', {stufe!r});" if stufe else "localStorage.removeItem('flug_stufe');")
    pg.context.add_init_script(ini)
    pg.context.add_init_script("(" + INSTR + ")()")
    with urllib.request.urlopen(f"{app}/api/tours", timeout=10) as r:
        start = next(t["start_ts"] for t in json.loads(r.read()) if t["id"] == "h0")
    pg.route("**/api/tours/h0/coords", lambda q: q.fulfill(json=_spur()))
    pg.route("**/api/tours/h1/coords", lambda q: q.fulfill(json=_spur(1500, 0.3)))
    # Fotos über die Strecke verteilt (Zeit der Strecke: 10 s je Punkt, 30000 s im Ganzen)
    pg.route("**/api/photos?tour_id=h0*", lambda q: q.fulfill(json=[{"id": 1000 + k, "taken_ts": start + int(29900 * (k + 0.5) / fotos), "tour_id": "h0", "v": 1} for k in range(fotos)]))
    pg.route("**/pic/*", lambda q: q.fulfill(body=PNG, content_type="image/png"))
    pg.goto(f"{app}/#/flight/{flug_id}")
    try:
        pg.wait_for_function("() => !!document.getElementById('fm') && (!!(document.getElementById('fm')._map && document.getElementById('fm')._map.getSource('done')) || /WebGL|noch keine Strecke/.test(document.getElementById('fmsg').textContent))", timeout=60000)
    except Exception:
        pass
    if not pg.evaluate("() => !!(document.getElementById('fm') && document.getElementById('fm')._map && document.getElementById('fm')._map.getSource('done'))"):
        msg = pg.evaluate("() => document.getElementById('fmsg') && document.getElementById('fmsg').textContent")
        pg.browser_.close()
        pytest.skip("kein WebGL im Testbrowser: " + str(msg))
    pg.wait_for_function("() => !!document.getElementById('fm')._flug", timeout=T)
    pg.evaluate(HOOK)
    return pg


def _zahlen(pg):
    return pg.evaluate("() => Object.assign({}, window.__mz)")


def _fenster(pg, sek):
    """Zählwerke über `sek` Sekunden: Unterschied zwischen zwei Ständen."""
    a = _zahlen(pg)
    t0 = time.time()
    pg.wait_for_timeout(int(sek * 1000))
    b = _zahlen(pg)
    return {k: b[k] - a[k] for k in b}, time.time() - t0


def _slider(pg, v):
    pg.evaluate("(v) => { const s = document.getElementById('fs'); s.value = v; s.dispatchEvent(new Event('input')); }", str(v))


def _pause(pg):
    if pg.evaluate("() => document.getElementById('fp').textContent.includes('Pause')"):
        pg.evaluate("() => document.getElementById('fp').click()")
    pg.wait_for_function("() => !document.getElementById('fp').textContent.includes('Pause')", timeout=T)


@pytest.mark.browser
def test_handy_vorgabe_fluessig_pixelratio_begrenzt_und_ebenen(pw, app):
    pg = _flug(pw, app)
    try:
        assert pg.evaluate("() => document.documentElement.classList.contains('mob')")
        assert pg.evaluate(f"() => {FL}.stufe()") == "fluessig" and pg.input_value("#fst") == "fluessig"
        assert pg.evaluate("() => window.devicePixelRatio") == 2.75
        assert pg.evaluate(f"() => {MAP}.getPixelRatio()") == 1                                      # Handy: ein Neuntel der Bildpunkte von 3
        c = pg.evaluate(f"() => {{ const c = {MAP}.getCanvas(); return [c.width, c.clientWidth]; }}")
        assert c[0] <= c[1] * 1.01
        # Fotos: Kartenebene statt HTML-Marker (jeder HTML-Marker kostet bei Gelände ein readPixels je 100 ms)
        assert pg.evaluate("() => document.querySelectorAll('#fm .fcam').length") == 0
        assert pg.evaluate("() => document.querySelectorAll('#fm .maplibregl-marker').length") == 1       # nur der gelbe Punkt
        assert pg.evaluate(f"() => {MAP}.getLayer('fotos').type") == "circle"
        assert pg.evaluate(f"() => {MAP}.getSource('fotos')._data.features.length") == 30
        # Die Linie ist ausgedünnt, aber nicht leer; Gesamtlinie und Fortschritt am Ende gleich
        z = pg.evaluate(f"() => {FL}.zahlen()")
        assert 2 < z["linie"] <= z["punkte"] == 900
        assert pg.evaluate(f"() => {MAP}.getTerrain().exaggeration") == 1.3
    finally:
        pg.browser_.close()


@pytest.mark.browser
def test_linie_kopfzeile_und_regler_nur_im_takt_keine_readpixels(pw, app):
    pg = _flug(pw, app)
    try:
        pg.evaluate("() => { const s = document.getElementById('fv'); s.value = '8'; s.dispatchEvent(new Event('change')); }")        # schnell: viele neue Streckenpunkte je Sekunde
        _slider(pg, 300)
        pg.wait_for_timeout(1000)
        z, dt = _fenster(pg, 4)
        assert z["setData"] <= dt * 1000 / 250 + 1.5, z      # Takt der Linie in „Flüssig“: 250 ms                                                   # höchstens 4 je Sekunde (vorher: bei jedem neuen Punkt)
        assert z["fh"] <= dt * 10 + 4, z                                                                   # Kopfzeile höchstens 5 × je Sekunde (je Schreibvorgang 1–2 Änderungsmeldungen)
        assert z["val"] <= dt * 5 + 3, z                                                                   # Schieberegler ebenso
        assert z["read"] == 0, z                                                                           # keine readPixels-Bremse
        assert z["setData"] >= 1 and z["val"] >= 1                                                         # es läuft also, es wird nur nicht jedes Bild geschrieben
        zz = pg.evaluate(f"() => {FL}.zahlen()")
        assert zz["bilder"] >= zz["spur"] and zz["bilder"] >= zz["hud"]      # auf langsamen Rechnern (CI) dauert ein Bild länger als der Takt, dann sind es gleich viele; die Obergrenzen oben sind der eigentliche Beweis
    finally:
        pg.browser_.close()


@pytest.mark.browser
def test_flug_laeuft_pause_slider_tempo_und_foto(pw, app):
    pg = _flug(pw, app)
    try:
        a = int(pg.input_value("#fs"))
        pg.wait_for_function("(a) => +document.getElementById('fs').value > a", arg=a, timeout=T)         # läuft
        assert "Pause" in pg.inner_text("#fp")
        _pause(pg)
        b = pg.input_value("#fs")
        pg.wait_for_timeout(600)
        assert pg.input_value("#fs") == b                                                                  # Pause hält an
        # Schieberegler: Position, Kopfzeile folgt (auch im Takt, nicht sofort)
        _slider(pg, 500)
        pg.wait_for_function("() => /\\//.test(document.getElementById('fh').textContent)", timeout=T)
        h1 = pg.inner_text("#fh")
        _slider(pg, 900)
        pg.wait_for_function("(h) => document.getElementById('fh').textContent !== h", arg=h1, timeout=T)
        assert "km" in pg.inner_text("#fh").replace(" ", " ")
        # Tempo ändern wirkt
        pg.evaluate("() => { const s = document.getElementById('fv'); s.value = '8'; s.dispatchEvent(new Event('change')); document.getElementById('fp').click(); }")
        c = int(pg.input_value("#fs"))
        pg.wait_for_function("(c) => +document.getElementById('fs').value > c + 5", arg=c, timeout=T)
        _pause(pg)
        # Foto-Einblendung: kurz vor dem ersten Foto (u ≈ 0,0167) starten
        pg.evaluate("() => { document.getElementById('fph').classList.remove('on'); const s = document.getElementById('fs'); s.value = 0; s.dispatchEvent(new Event('input')); const v = document.getElementById('fv'); v.value = '8'; v.dispatchEvent(new Event('change')); document.getElementById('fp').click(); }")
        pg.wait_for_function("() => document.getElementById('fph').classList.contains('on')", timeout=40000)
        assert pg.evaluate("() => document.getElementById('fphi').getAttribute('src')").startswith("/pic/10")
        assert not pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.browser
def test_stufen_wechsel_speichert_und_anpassung_im_flug_mit_hysterese(pw, app):
    pg = _flug(pw, app)
    try:
        _pause(pg)
        pg.select_option("#fst", "schoen")
        assert pg.evaluate(f"() => {MAP}.getPixelRatio()") == 2.75                                        # min(Gerät 2,75; Grenze 3)
        assert pg.evaluate(f"() => {MAP}.getTerrain().exaggeration") == 1.5
        assert pg.evaluate("() => localStorage.getItem('flug_stufe')") == "schoen"                         # die Wahl gehört zum Gerät und bleibt
        pg.select_option("#fst", "normal")
        assert pg.evaluate(f"() => {MAP}.getPixelRatio()") == 1.5
        pg.select_option("#fst", "schoen")
        # Anpassung: 30 langsame Bilder → eine Stufe herunter, gespeicherte Wahl bleibt „Schön“; keine weitere Stufe vor dem nächsten vollen Fenster
        assert pg.evaluate(f"() => {FL}.bildzeiten(Array(29).fill(60))") is None
        assert pg.evaluate(f"() => {FL}.bildzeiten([60])") == "normal"
        assert pg.evaluate(f"() => {FL}.stufe()") == "normal" and pg.input_value("#fst") == "normal"
        assert pg.evaluate(f"() => {MAP}.getPixelRatio()") == 1.5
        assert pg.evaluate("() => localStorage.getItem('flug_stufe')") == "schoen"
        assert "Flug vereinfacht" in pg.inner_text("#fmsg")
        assert pg.evaluate(f"() => {FL}.bildzeiten(Array(89).fill(60))") is None                           # 60 Bilder Ruhe + 29 Bilder des neuen Fensters
        assert pg.evaluate(f"() => {FL}.bildzeiten([60])") == "fluessig"
        assert pg.evaluate(f"() => {MAP}.getPixelRatio()") == 1
        assert pg.evaluate(f"() => {FL}.bildzeiten(Array(300).fill(60))") is None                          # unten: Schluss
        # schnelle Bilder schalten nie hinauf
        assert pg.evaluate(f"() => {FL}.bildzeiten(Array(300).fill(10))") is None and pg.evaluate(f"() => {FL}.stufe()") == "fluessig"
        # nach Neuladen gilt die gespeicherte Wahl
        pg.reload()
        pg.wait_for_function("() => !!(document.getElementById('fm') && document.getElementById('fm')._flug)", timeout=60000)
        assert pg.evaluate(f"() => {FL}.stufe()") == "schoen"
    finally:
        pg.browser_.close()


@pytest.mark.browser
def test_computer_vorgabe_schoen_wie_bisher(pw, app):
    pg = _flug(pw, app, mob=False, dpr=2, width=1280, height=800)
    try:
        assert not pg.evaluate("() => document.documentElement.classList.contains('mob')")
        assert pg.evaluate(f"() => {FL}.stufe()") == "schoen" and pg.input_value("#fst") == "schoen"
        assert pg.evaluate(f"() => {MAP}.getPixelRatio()") == 2
        assert pg.evaluate(f"() => {MAP}.getPitch()") >= 60
    finally:
        pg.browser_.close()


@pytest.mark.browser
def test_kamera_haengt_nur_von_der_position_ab(pw, app):
    pg = _flug(pw, app)
    try:
        _pause(pg)
        a = pg.evaluate(f"() => {FL}.kameraBei(0.4)")
        for _ in range(3):
            pg.evaluate(f"() => {FL}.stelleZeit(0.1)")
            pg.evaluate(f"() => {FL}.stelleZeit(0.7)")
        assert pg.evaluate(f"() => {FL}.kameraBei(0.4)") == a                                              # egal, was dazwischen gerechnet wurde
        k = pg.evaluate(f"() => {FL}.stelleZeit(0.4)")
        assert k == a
        # und die Karte steht danach dort (Pause: Kamera folgt der Bahn)
        pg.wait_for_function(f"([lng, lat]) => {{ const c = {MAP}.getCenter(); return Math.abs(c.lng - lng) < 1e-6 && Math.abs(c.lat - lat) < 1e-6; }}", arg=a["center"], timeout=T)
        assert abs(pg.evaluate(f"() => {MAP}.getBearing()") - ((a["bearing"] + 540) % 360 - 180)) < 0.01
    finally:
        pg.browser_.close()


@pytest.mark.browser
def test_reiseflug_ueberflug_zoomt_heraus_und_laeuft(pw, app):
    pg = _flug(pw, app, flug_id="set:h0,h1")
    try:
        assert pg.evaluate("() => /Flug über 2 Touren/.test(document.querySelector('.ft').textContent)")
        zs = pg.evaluate(f"() => {{ const f = {FL}; const r = []; for (let i = 0; i <= 200; i++) r.push(f.kameraBei(i / 200).zoom); return r; }}")
        assert all(z is not None for z in zs) and max(zs) <= 14.8 + 1e-9 and min(zs) < 14.8 - 1.0        # im Überflug höher (herausgezoomt), sonst mittlere Flughöhe
        assert zs[0] == 14.8 and zs[-1] == 14.8
        a = int(pg.input_value("#fs"))
        pg.wait_for_function("(a) => +document.getElementById('fs').value > a", arg=a, timeout=T)
        i = zs.index(min(zs)) / 200
        _pause(pg)
        _slider(pg, round(i * 1000))
        pg.wait_for_function("() => /weiter zu/.test(document.getElementById('fh').textContent)", timeout=T)
        assert not pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.browser
def test_aufnahme_setzt_pixeldichte_hoch_und_danach_zurueck(pw, app):
    pg = _flug(pw, app)
    try:
        if not pg.evaluate("() => !!window.MediaRecorder && ['video/mp4;codecs=avc1.42E01E', 'video/webm;codecs=vp9', 'video/webm;codecs=vp8', 'video/webm'].some(x => MediaRecorder.isTypeSupported(x))"):
            pytest.skip("kein MediaRecorder im Testbrowser")
        assert pg.evaluate(f"() => {MAP}.getPixelRatio()") == 1
        pg.evaluate("() => document.getElementById('frec').click()")
        pg.wait_for_function("() => /Aufnahme beenden/.test(document.getElementById('frec').textContent)", timeout=120000)    # Vorlauf (Kacheln) ist durch
        assert pg.evaluate(f"() => {MAP}.getPixelRatio()") > 1                                              # Aufnahme in Videoqualität, nicht in der Handy-Stufe
        a = int(pg.input_value("#fs"))
        pg.wait_for_function("(a) => +document.getElementById('fs').value > a", arg=a, timeout=60000)      # die Aufnahme fährt die Strecke ab
        with pg.expect_download(timeout=60000) as dl:
            pg.evaluate("() => document.getElementById('frec').click()")
        assert dl.value.suggested_filename.endswith((".webm", ".mp4"))
        pg.wait_for_function(f"() => {MAP}.getPixelRatio() === 1", timeout=T)                              # danach wieder die gewählte Stufe
        assert not pg.errors
    finally:
        pg.browser_.close()
