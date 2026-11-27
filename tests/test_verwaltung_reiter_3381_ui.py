"""3.38.1 Verwaltung: jede Karte liegt in jeder Sprache (de/en/fr/es) im erwarteten Reiter. Der erwartete Reiter steht als feste Liste im Test (Karten über id bzw. deutschen Originaltitel erkannt).
Synchronisation nur über wait_for_function (Pfeilfunktionen) und expect(..., timeout=15000); keine festen Pausen. Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest
from tests.helpers_ui import quiet  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
pw_api = pytest.importorskip("playwright.sync_api")
expect = pw_api.expect
TL = 15000

# Reiterkennung -> Karten (Kennung: #id oder deutscher Titel der Überschrift)
ERWARTET = {
    "allgemein": ["#hlt", "#upd", "Selbsttest", "Protokoll", "#homep", "#slfacp", "Entwicklermodus"],
    "sportarten": ["#katp", "#favp", "#sgp"],                                       # 3.60.0: eigener Reiter (Katalog, Favoriten, Statistik-Gruppen); 3.60.1 „Sportarten“
    "quellen": ["#devsec", "Komoot (optional)", "Zepp-Import (optional)", "Garmin, Suunto & andere Uhren (Import)", "Wanderführer (z. B. Rother)"],
    "weitergabe": ["Portale (Upload)", "#brpanel"],
    "fotos": ["Fotos", "Foto-Eingang"],
    "auto": ["Automatik", "Benachrichtigung (optional)"],
    "handy": ["#livebox", "#rescue", "#handy"],
    "sicher": ["Sicherung", "#uipw", "#offprep"],
}
# Deutscher Originaltitel -> Überschrift in der Sprache (nur Stichproben für die Übersetzung selbst)
TITEL = {
    "en": {"Sicherung": "Backup", "Fotos": "Photos", "Automatik": "Automation", "Selbsttest": "Self-test", "Protokoll": "Log"},
    "fr": {"Sicherung": "Sauvegarde", "Fotos": "Photos", "Automatik": "Automatisation", "Selbsttest": "Autotest", "Protokoll": "Journal"},
    "es": {"Sicherung": "Copia de seguridad", "Fotos": "Fotos", "Automatik": "Automatización", "Selbsttest": "Autodiagnóstico", "Protokoll": "Registro"},
}
KARTEN = """() => [...document.querySelectorAll('.atab')].map(s => [s.dataset.t, [...s.querySelectorAll(':scope > .gbody > *')].map(e => e.id ? '#' + e.id : (() => { const h = e.querySelector(':scope > h2'); return h ? (h.dataset.de || h.textContent).trim() : '?'; })())])"""
VOLL = """(erw) => { const t = document.querySelectorAll('.atab'); if (t.length !== 8) return false; const have = new Set([...document.querySelectorAll('.atab > .gbody > *')].map(e => e.id ? '#' + e.id : (((e.querySelector(':scope > h2') || {}).dataset || {}).de || ((e.querySelector(':scope > h2') || {}).textContent || '')).trim())); return erw.every(k => have.has(k)); }"""


@pytest.fixture(scope="module")
def app():
    d = Path(tempfile.mkdtemp(prefix="vr3381"))
    env = dict(os.environ, DATA_DIR=str(d / "data"), PHOTOS_DIR=str(d / "p"), BACKUP_DIR=str(d / "b"), MT_NO_SCHEDULER="1")
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    pr = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
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


def _admin(pw, url, lang, tab=None, width=1280, height=1000):
    b = pw.chromium.launch()
    ctx = b.new_context(locale={"de": "de-DE", "en": "en-GB", "fr": "fr-FR", "es": "es-ES"}[lang], viewport={"width": width, "height": height}, reduced_motion="reduce")
    ctx.add_init_script("try { localStorage.setItem('lang', %r); localStorage.removeItem('admtab'); } catch (e) {}" % lang)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(url) else r.continue_())
    pg.browser_ = b
    pg.goto(f"{url}/#/admin" + (f"?tab={tab}" if tab else ""))
    alle = [k for v in ERWARTET.values() for k in v]
    pg.wait_for_function(VOLL, arg=alle, timeout=TL)
    try:
        quiet(pg, 5000)
    except Exception:
        pass
    pg.wait_for_function(VOLL, arg=alle, timeout=TL)
    return pg


@pytest.mark.parametrize("lang", ["de", "en", "fr", "es"])
def test_jede_karte_im_erwarteten_reiter(pw, app, lang):
    pg = _admin(pw, app, lang)
    try:
        ist = {t: sorted(k) for t, k in pg.evaluate(KARTEN)}
        assert ist == {t: sorted(k) for t, k in ERWARTET.items()}, (lang, ist)
        assert pg.locator("#atabs button").count() == 8 and pg.locator("#atabs button.on").count() == 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("lang", ["en", "fr", "es"])
def test_ueberschriften_uebersetzt_und_reiter_beschriftet(pw, app, lang):
    pg = _admin(pw, app, lang)
    try:
        for de, fremd in TITEL[lang].items():
            h = pg.locator(f'.atab h2[data-de="{de}"]')
            expect(h).to_have_text(fremd, timeout=TL)
        # Reiternamen sind übersetzt (nicht mehr deutsch), und Karten sind nicht unübersetzt deutsch
        namen = pg.locator("#atabs button").all_inner_texts()
        assert "Übersicht" not in namen and "Fotos" not in namen[:1] and len(set(namen)) == 8, namen
        assert pg.locator('.atab[data-t="weitergabe"] h2[data-de="Portale (Upload)"]').inner_text().startswith(("Portals", "Portails", "Portales")), lang
    finally:
        pg.browser_.close()


def test_sicherung_englisch_sichtbar_im_reiter_sicherung(pw, app):
    pg = _admin(pw, app, "en", tab="sicher")
    try:
        tab = pg.locator('.atab[data-t="sicher"]')
        expect(tab).to_be_visible(timeout=TL)
        expect(tab.locator('h2[data-de="Sicherung"]')).to_have_text("Backup", timeout=TL)
        expect(pg.locator('.atab[data-t="allgemein"]')).to_be_hidden(timeout=TL)
        assert pg.locator('.atab[data-t="allgemein"] h2[data-de="Sicherung"]').count() == 0
        d = os.environ.get("TS_SHOTS")
        if d:
            Path(d).mkdir(parents=True, exist_ok=True)
            tab.scroll_into_view_if_needed()
            pg.screenshot(path=str(Path(d) / "verwaltung-en-sicherung.png"), full_page=False, timeout=60000)
    finally:
        pg.browser_.close()


# 3.61.0 Reiterleiste: nie senkrecht scrollbar; am Computer (1500 px) alle Reiter samt „Prüfen & Aufräumen“ ohne Scrollen sichtbar (notfalls zweite Zeile);
# am Handy (390 px) waagerecht wischbar mit Verlauf am Rand, der aktive Reiter ist in Sicht. Dieselbe Regel für alle waagerechten Leisten der Seite.
LEISTE = """() => { const n = document.querySelector('#atabs'), r = n.getBoundingClientRect(), last = n.lastElementChild.getBoundingClientRect(),
  on = n.querySelector('button.on').getBoundingClientRect(), cs = getComputedStyle(n);
  const bars = [...document.querySelectorAll('nav, .chips, .segtabs, .years, .tlchips, .atabs')].filter(e => e.offsetParent !== null)
    .filter(e => e.scrollHeight > e.clientHeight + 1 && /(auto|scroll)/.test(getComputedStyle(e).overflowY)).map(e => e.className || e.tagName);
  return {sh: n.scrollHeight, ch: n.clientHeight, sw: n.scrollWidth, cw: n.clientWidth, oy: cs.overflowY, lastIn: last.right <= r.right + 1 && last.left >= r.left - 1,
    lastText: n.lastElementChild.textContent.trim(), onIn: on.left >= r.left - 1 && on.right <= r.right + 1, end: n.hasAttribute('data-end'),
    mask: cs.maskImage || cs.webkitMaskImage || 'none', bars}; }"""


@pytest.mark.parametrize("lang", ["de", "fr"])
def test_reiterleiste_computer_alles_sichtbar(pw, app, lang):
    pg = _admin(pw, app, lang, "allgemein", width=1500, height=900)
    try:
        pg.wait_for_function("() => !!document.querySelector('#atabs .atlink')", timeout=TL)
        r = pg.evaluate(LEISTE)
        assert r["sh"] <= r["ch"] + 1, r                                         # kein senkrechtes Scrollen
        assert r["sw"] <= r["cw"] + 1 and r["lastIn"], r                         # alles sichtbar, auch „Prüfen & Aufräumen“
        assert r["bars"] == [], r
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_reiterleiste_handy_wischen(pw, app):
    pg = _admin(pw, app, "de", "sicher", width=390, height=800)
    try:
        pg.wait_for_function("() => !!document.querySelector('#atabs .atlink')", timeout=TL)
        r = pg.evaluate(LEISTE)
        assert r["sh"] <= r["ch"] + 1 and r["oy"] == "hidden", r                # waagerecht wischen, nie senkrecht
        assert r["sw"] > r["cw"] and r["onIn"], r                                # der aktive Reiter („Sicherung & Zugang“) ist in Sicht gerollt
        assert r["bars"] == [], r
        pg.evaluate("() => { const n = document.querySelector('#atabs'); n.scrollLeft = 0; n.dispatchEvent(new Event('scroll')); }")
        r = pg.evaluate(LEISTE)
        assert not r["end"] and r["mask"] != "none", r                           # Verlauf am Rand: es geht weiter
        pg.evaluate("() => { const n = document.querySelector('#atabs'); n.scrollLeft = n.scrollWidth; n.dispatchEvent(new Event('scroll')); }")
        pg.wait_for_function("() => document.querySelector('#atabs').hasAttribute('data-end')", timeout=TL)
    finally:
        pg.browser_.close()


# 3.61.1 Reiterleiste am Computer: bei üblichen Breiten (ab 1280) EINE Zeile, bei 1024 gleichmäßiger Umbruch (gleiche Zeilenhöhe), nie senkrecht scrollbar
ZEILEN = """() => { const n = document.querySelector('#atabs'), k = [...n.children].map(e => e.getBoundingClientRect()),
  tops = [...new Set(k.map(r => Math.round(r.top)))].sort((a, b) => a - b), hs = [...new Set(k.map(r => Math.round(r.height)))];
  return {rows: tops.length, tops, hs, sh: n.scrollHeight, ch: n.clientHeight}; }"""


@pytest.mark.parametrize("breite", [1280, 1440, 1600, 1920])
def test_reiterleiste_eine_zeile(pw, app, breite):
    pg = _admin(pw, app, "de", "allgemein", width=breite, height=900)
    try:
        pg.wait_for_function("() => !!document.querySelector('#atabs .atlink')", timeout=TL)
        r = pg.evaluate(ZEILEN)
        assert r["rows"] == 1 and r["sh"] <= r["ch"] + 1 and len(r["hs"]) == 1, r
    finally:
        pg.browser_.close()


def test_reiterleiste_schmal_gleichmaessiger_umbruch(pw, app):
    pg = _admin(pw, app, "de", "allgemein", width=1024, height=900)
    try:
        pg.wait_for_function("() => !!document.querySelector('#atabs .atlink')", timeout=TL)
        r = pg.evaluate(ZEILEN)
        assert r["rows"] == 2 and len(r["hs"]) == 1 and r["hs"][0] >= 44, r        # alle Einträge gleich hoch
        assert r["tops"][1] - r["tops"][0] == r["hs"][0] + 2, r                    # gleicher Zeilenabstand
        assert r["sh"] <= r["ch"] + 1, r
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("breite", [360, 390, 430])
@pytest.mark.parametrize("farbe", ["light", "dark"])
def test_standort_teilen_laeuft_nicht_ueber_den_kartenrand(pw, app, breite, farbe):
    """3.70.0: #livem bleibt in der Karte (kein seitliches Scrollen), Löschknopf ruhig (ghost sm), Statustext darunter."""
    pg = _admin(pw, app, "de", tab="handy", width=breite, height=900)
    try:
        pg.emulate_media(color_scheme=farbe)
        pg.locator("#livebox").scroll_into_view_if_needed()
        r = pg.evaluate("""() => { const b = document.querySelector('#livebox'), s = document.querySelector('#livem'), x = document.querySelector('#livex'), br = b.getBoundingClientRect(), sr = s.getBoundingClientRect();
          return {sw: b.scrollWidth, cw: b.clientWidth, sRight: sr.right, bRight: br.right, doc: document.documentElement.scrollWidth, win: window.innerWidth, cls: x.className}; }""")
        assert r["sw"] <= r["cw"] and r["sRight"] <= r["bRight"] + 0.5 and r["doc"] <= r["win"], r
        assert "ghost" in r["cls"] and "alt" not in r["cls"].split()
    finally:
        pg.browser_.close()
