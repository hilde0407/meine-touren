"""3.55.1 Kennzahlen (`.figs`): keine Zahl ragt über ihre Spalte oder den Rand der Karte hinaus – auch nicht mit sechs- bis siebenstelligen Zahlen samt Einheit
(„403.707 m“, „2.743 Std.“, „10.038 km“), bei Breiten von 320 bis 1400 px, mit und ohne Handy-Darstellung (html.mob) und mit großer Systemschrift (130 %, nur bei Handybreiten).
Geprüft werden die vier Orte Übersicht „Gesamt“ (#/stats?z=all, Baustein „Kennzahlen“), Jahresansicht (#/dash?y=2024), Statistik (#/stats, `.stb>.figs`) und Tourseite (`.figs.sm`).

Große Systemschrift: Der Android-WebView vergrößert (textZoom) die berechnete Schriftgröße; nachgestellt, indem jede Schriftgröße in den Kennzahlen mit 1,3 malgenommen wird.
Die langen Zahlen werden per JavaScript in die fertig aufgebauten Kennzahlen geschrieben (Datenlage mit 403.707 m Aufstieg ist für die Darstellung gleichwertig)."""
import os
import subprocess
import sys
import time

import pytest

pytest.importorskip("playwright.sync_api")
from tests.helpers_ui import T, free_port, quiet, settled, wait_http  # noqa: E402
from tests.test_browser import ROOT, _seed  # noqa: E402

FILL = """() => {
  const kpi = ['783', '10.038', '403.707', '2.743', '12,8'];
  document.querySelectorAll('.figs').forEach(f => [...f.querySelectorAll('.fig .v')].forEach((v, i) => {
    const u = v.querySelector('.u'); let ut = u ? u.textContent : '';
    if (/Min|Std/.test(ut)) ut = 'Std.';
    const n = f.closest('#tlsb-kpi') ? kpi[i % 5] : ut === '' ? '783' : ut === 'Std.' ? '2.743' : ut === 'km' ? '10.038' : '403.707';
    v.innerHTML = n + (ut ? `<span class="u">${ut}</span>` : '');
    v.closest('.fig').style.display = '';
  }));
}"""

ZOOM = """(f) => {
  const els = [...document.querySelectorAll('.figs .fig, .figs .fig *')], px = els.map(e => parseFloat(getComputedStyle(e).fontSize));
  els.forEach((e, i) => { e.style.fontSize = (px[i] * f) + 'px'; });
}"""

# Je Kennzahl: rechter Rand des Texts (Zahl + Einheit) gegen rechten Inhaltsrand der Spalte (.fig) und gegen den rechten Rand der Karte; dazu scrollWidth/clientWidth.
GEO = """(sel) => [...document.querySelectorAll(sel)].filter(f => f.offsetParent).flatMap(f => {
  const card = (f.closest('.tlsb') || f.parentElement).getBoundingClientRect();
  return [...f.querySelectorAll('.fig .v')].filter(v => v.offsetParent).map(v => {
    const fig = v.closest('.fig'), r = document.createRange(); r.selectNodeContents(v);
    const t = r.getBoundingClientRect(), fr = fig.getBoundingClientRect(), cs = getComputedStyle(fig);
    return {txt: v.textContent, fs: getComputedStyle(v).fontSize, right: t.right, col: fr.right - parseFloat(cs.paddingRight), card: card.right,
            sw: fig.scrollWidth, cw: fig.clientWidth, vsw: v.scrollWidth, vcw: v.clientWidth};
  });
})"""

PLACES = [("stats?z=all", "#tlsb-kpi > .figs"), ("dash?y=2024", "#tlsb-kpi > .figs"), ("stats", ".stb > .figs"), ("tour", ".figs.sm")]   # Übersicht „Gesamt“, Jahr, Statistik (laufendes Jahr), Tour


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    d = tmp_path_factory.mktemp("kz")
    _seed(d / "data")
    now = int(time.time()) - 86400          # eine Tour im laufenden Jahr: auch #/stats (laufendes Jahr) zeigt Kennzahlen
    code = (f"import sys, os; sys.path.insert(0, {str(ROOT)!r}); os.environ['DATA_DIR'] = {str(d / 'data')!r}\nfrom app import db\n"
            f"db.execute(\"INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) "
            f"VALUES('k9','Neue Runde','hike',{now},{now + 7200},12000,7200,400,400,48,8,'tour_recorded','komoot')\")")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, out.stderr
    port = free_port()
    env = dict(os.environ, DATA_DIR=str(d / "data"), PHOTOS_DIR=str(d / "p"), BACKUP_DIR=str(d / "b"))
    pr = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    wait_http(url + "/api/version")
    yield url
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)


@pytest.mark.kern                     # Stichprobe im schnellen Kern (tests/README.md): Kennzahlen passen in ihre Spalte
def test_kennzahlen_ragen_nicht_heraus(app):
    from playwright.sync_api import sync_playwright
    bad, seen = [], set()
    with sync_playwright() as p:
        b = p.chromium.launch()
        for w, h, dsf in [(320, 640, 2), (390, 844, 3), (412, 900, 2.625), (700, 900, 2), (1280, 900, 1), (1400, 900, 1)]:
            for mode in (["auto", "desktop"] if w <= 760 else ["auto"]):       # schmal: einmal mit html.mob (auto), einmal ohne (Darstellung „Desktop“ gewählt)
                ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=dsf, is_mobile=w <= 760, has_touch=w <= 760, locale="de-DE")
                ctx.add_init_script(f"try {{ localStorage.setItem('viewmode', '{mode}'); }} catch (e) {{}}")
                pg = ctx.new_page()
                pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(app) else r.continue_())
                pg.goto(app + "/#/dash"); quiet(pg, 3000)
                tid = pg.evaluate("TOURS.find(t => t.source === 'local').id")
                mob = pg.evaluate("document.documentElement.classList.contains('mob')")
                assert mob == (mode == "auto" and w <= 760), (w, mode, mob)
                for route, sel in PLACES:
                    pg.goto(app + "/#/" + (f"tour/{tid}" if route == "tour" else route))
                    pg.wait_for_selector(sel + " .fig .v", timeout=T)
                    settled(pg)
                    pg.evaluate("(s) => document.querySelectorAll(s).forEach(f => { const d = f.closest('details'); if (d) d.open = true; })", sel)
                    pg.evaluate(FILL)
                    for zoom in ((1, 1.3) if w <= 760 else (1,)):          # große Systemschrift gibt es im Android-WebView (textZoom), nicht am Desktop
                        if zoom != 1:
                            pg.evaluate(ZOOM, zoom)
                        pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
                        g = pg.evaluate(GEO, sel)
                        assert g, (w, mode, route)
                        seen.add(route)
                        for x in g:
                            if x["right"] > x["col"] + 0.5 or x["right"] > x["card"] + 0.5 or x["sw"] > x["cw"] or x["vsw"] > x["vcw"]:
                                bad.append((w, mode, route, zoom, x))
                            if w >= 1280:                                # Desktop sieht aus wie bisher: volle Schriftgröße auch mit langen Zahlen
                                assert x["fs"] == ("34px" if route == "tour" else "50px"), (w, route, x)
                ctx.close()
    assert seen == {r for r, _ in PLACES}
    assert not bad, f"{len(bad)} Kennzahlen ragen heraus, z. B. " + "\n".join(map(str, bad[:12]))
