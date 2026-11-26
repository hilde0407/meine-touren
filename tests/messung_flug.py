#!/usr/bin/env python3
"""Messung des 3D-Flugs (3.61.4): Aufwand je Bild, Zahl der Aktualisierungen der gelben Linie und der Kopfzeile, Schreibvorgänge im Dokument.

    python3 tests/messung_flug.py [--root ORDNER] [--stufe fluessig|normal|schoen] [--tempo 4] [--sek 10]

--root: Stand der App (Vorgabe: dieses Verzeichnis); so lässt sich auch ein älterer Stand messen (git archive <Stand> | tar -x -C <Ordner>).
Tour mit 3000 Punkten und 30 Fotos (Strecke und Fotos werden im Browser nachgestellt), Fenster 390 × 844 mit Pixeldichte 2,75, html.mob, Kartenkacheln nicht erreichbar (Gelände flach).
WICHTIG: Headless Chromium zeichnet WebGL in Software. Die Bildzeiten sagen deshalb über ein Handy nichts; aussagekräftig sind Zählwerte und Skriptzeit im Hauptthread."""
import argparse
import json
import math
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
SEED = r"""
import sys, os, time; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db, routes
db.init()
now = int(time.time()) - 86400
db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,'t','komoot')", ('h0', 'Messrunde', 'hike', now, now + 30000, 30000, 30000, 600, 600, 48.0, 11.0))
routes.store('h0', [(48.0, 11.0, 500.0, i * 10000) for i in range(10)])
"""
LAUNCH = "import sys; sys.path.insert(0, %(root)r)\nimport uvicorn\nfrom app.main import app\nuvicorn.run(app, host='127.0.0.1', port=%(port)d, log_level='warning')\n"


def spur(n=3000):
    """Kurvige Strecke (Zickzack-Spirale) mit n Punkten, Höhe und Zeit; [lat, lng, ele, t_ms]."""
    out = []
    for i in range(n):
        a = i / 60.0
        r = 0.002 + 0.00001 * i
        out.append([48.0 + r * math.sin(a) + 0.00005 * math.sin(i * 1.7), 11.0 + r * math.cos(a) * 1.5, 500 + 80 * math.sin(i / 90), i * 10000])
    return out


def fotos(n, start):
    return [{"id": 1000 + k, "taken_ts": start + int(30000 * (k + 0.5) / n), "tour_id": "h0", "v": 1} for k in range(n)]


PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cf00000301010018dd8db40000000049454e44ae426082")

INSTR = """() => {
  const Z = window.__mz = {tick: 0, tickMs: 0, tickMax: 0, setData: 0, coords: 0, read: 0, mut: 0, val: 0, fh: 0, frames: []};
  const raf = window.requestAnimationFrame.bind(window);
  window.requestAnimationFrame = cb => raf(t => { if (cb.name !== 'tick') return cb(t); const a = performance.now(); try { return cb(t); } finally { const d = performance.now() - a; Z.tick++; Z.tickMs += d; if (d > Z.tickMax) Z.tickMax = d; Z.frames.push(t); } });
  for (const C of [window.WebGLRenderingContext, window.WebGL2RenderingContext]) if (C) { const f = C.prototype.readPixels; C.prototype.readPixels = function () { Z.read++; return f.apply(this, arguments); }; }
  const d = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value');
  Object.defineProperty(HTMLInputElement.prototype, 'value', { get: d.get, set(v) { if (this.id === 'fs') Z.val++; return d.set.call(this, v); }, configurable: true });
}"""
HOOK = """() => {
  const Z = window.__mz, m = document.getElementById('fm')._map, s = m.getSource('done');
  if (!s || s.__w) return !!s;
  s.__w = 1; const f = s.setData.bind(s);
  s.setData = g => { Z.setData++; const c = g.geometry.coordinates; Z.coords += Array.isArray(c[0][0]) ? c.reduce((a, x) => a + x.length, 0) : c.length; return f(g); };
  new MutationObserver(r => { Z.mut += r.length; }).observe(document.getElementById('fl'), {subtree: true, childList: true, attributes: true, characterData: true});
  new MutationObserver(r => { Z.fh += r.length; }).observe(document.getElementById('fh'), {subtree: true, childList: true, characterData: true});
  return true;
}"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(HERE))
    ap.add_argument("--stufe", default="")
    ap.add_argument("--tempo", default="4")
    ap.add_argument("--sek", type=float, default=10)
    ap.add_argument("--start", type=float, default=0.5, help="Startposition 0…1 (in der Mitte ist die gelbe Linie schon lang)")
    a = ap.parse_args()
    root = Path(a.root).resolve()
    tmp = Path(tempfile.mkdtemp())
    data = tmp / "data"
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    r = subprocess.run([sys.executable, "-c", SEED % {"root": str(root), "data": str(data)}], capture_output=True, text=True, cwd=root, env=env)
    assert r.returncode == 0, r.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    (tmp / "launch.py").write_text(LAUNCH % {"root": str(root), "port": port})
    pr = subprocess.Popen([sys.executable, str(tmp / "launch.py")], cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(150):
            try:
                urllib.request.urlopen(url + "/api/version", timeout=1); break
            except Exception:
                time.sleep(0.2)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=2.75, is_mobile=True, has_touch=True, locale="de-DE", reduced_motion="reduce")
            ctx.add_init_script("try { localStorage.setItem('viewmode', 'mobile'); localStorage.setItem('flug_hinweis', '1'); %s } catch (e) {}" % (f"localStorage.setItem('flug_stufe', '{a.stufe}');" if a.stufe else ""))
            pg = ctx.new_page()
            pg.route("**/*", lambda q: q.abort() if not q.request.url.startswith(url) else q.fallback())
            pg.route("**/api/tours/h0/coords", lambda q: q.fulfill(json=spur()))
            start = int(time.time()) - 86400
            pg.route("**/api/photos?tour_id=h0*", lambda q: q.fulfill(json=fotos(30, start)))
            pg.route("**/pic/*", lambda q: q.fulfill(body=PNG, content_type="image/png"))
            pg.add_init_script("(" + INSTR + ")()")
            pg.goto(f"{url}/#/flight/h0")
            pg.wait_for_function("() => !!document.getElementById('fm') && !!document.getElementById('fm')._map && !!document.getElementById('fm')._map.getSource('done')", timeout=60000)
            pg.evaluate(HOOK)
            pg.evaluate("(v) => { const s = document.getElementById('fv'); s.value = v; s.dispatchEvent(new Event('change')); }", a.tempo)
            pg.evaluate("(v) => { const s = document.getElementById('fs'); s.value = v; s.dispatchEvent(new Event('input')); }", str(round(a.start * 1000)))
            pg.wait_for_timeout(1500)
            cdp = ctx.new_cdp_session(pg)
            cdp.send("Performance.enable")
            met0 = {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}
            pg.evaluate("() => { const Z = window.__mz; for (const k in Z) Z[k] = Array.isArray(Z[k]) ? [] : 0; }")
            t0 = time.time()
            pg.wait_for_timeout(int(a.sek * 1000))
            sek = time.time() - t0
            met1 = {m["name"]: m["value"] for m in cdp.send("Performance.getMetrics")["metrics"]}
            Z = pg.evaluate("() => window.__mz")
            info = pg.evaluate("() => { const m = document.getElementById('fm')._map, c = m.getCanvas(); return {pr: m.getPixelRatio(), px: c.width * c.height, stufe: (document.getElementById('fm')._flug && document.getElementById('fm')._flug.stufe()) || null, u: document.getElementById('fs').value}; }")
            b.close()
        n = max(1, Z["tick"])
        res = {
            "stand": str(root), "stufe": info["stufe"], "tempo": a.tempo, "sekunden": round(sek, 1), "bilder": Z["tick"], "bilder_je_s": round(Z["tick"] / sek, 1),
            "tick_ms_je_bild": round(Z["tickMs"] / n, 3), "tick_ms_max": round(Z["tickMax"], 1),
            "setData_je_s": round(Z["setData"] / sek, 1), "setData_punkte_je_s": round(Z["coords"] / sek), "punkte_je_setData": round(Z["coords"] / max(1, Z["setData"])), "readPixels_je_bild": round(Z["read"] / n, 2),
            "dokument_aenderungen_je_bild": round(Z["mut"] / n, 2), "dokument_aenderungen_je_s": round(Z["mut"] / sek, 1), "kopfzeile_schreibvorgaenge_je_s": round(Z["fh"] / sek, 1),
            "schieberegler_schreibvorgaenge_je_s": round(Z["val"] / sek, 1), "bildpunkte": info["px"], "pixelRatio": info["pr"],
            "skriptzeit_hauptthread_ms_je_bild": round((met1["ScriptDuration"] - met0["ScriptDuration"]) * 1000 / n, 2),
            "aufgabenzeit_hauptthread_ms_je_bild": round((met1["TaskDuration"] - met0["TaskDuration"]) * 1000 / n, 2),
        }
        print(json.dumps(res, ensure_ascii=False, indent=1))
    finally:
        pr.terminate()


if __name__ == "__main__":
    main()
