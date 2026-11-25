"""3.39.0 Verwaltung in en/fr/es: Warnmeldungen des Gesundheitschecks, Backup-Hinweise und der Abschnitt „Umzug auf einen neuen Server“ sind übersetzt (kein deutscher Restsatz).
Prüfliste je Sprache und je Reiter; Synchronisation nur über expect(..., timeout=15000)/wait_for_function (Pfeilfunktionen), keine festen Pausen."""
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import pytest

from tests.helpers_ui import quiet

ROOT = Path(__file__).resolve().parent.parent
expect = pytest.importorskip("playwright.sync_api").expect
TL = 15000
TABS = ["uebersicht", "sportarten", "quellen", "weitergabe", "fotos", "auto", "handy", "sicher"]
LOC = {"en": "en-GB", "fr": "fr-FR", "es": "es-ES"}

# Erwartete Übersetzungen (Auszug der Prüfliste): Warnleiste, Backup, Umzug
ERW = {
    "en": {"warn": ["No tours yet: enter your Komoot access", "There is no backup yet – the first one is created automatically (at night), or right now:"],
           "sicher": ["Passwords and tokens are not included in the download. Photos and routes are not included.", "Moving to a new server", "The moving package contains everything", "Create moving package", "No moving package created yet."]},
    "fr": {"warn": ["Aucun parcours pour l’instant : saisissez votre accès Komoot", "Il n’y a pas encore de sauvegarde – la première sera créée automatiquement (la nuit), ou tout de suite :"],
           "sicher": ["Les mots de passe et les jetons ne sont pas inclus dans le téléchargement.", "Déménagement vers un nouveau serveur", "Le paquet de déménagement contient tout", "Créer un paquet de déménagement", "Aucun paquet de déménagement créé pour l’instant."]},
    "es": {"warn": ["Aún no hay rutas: introduce tu acceso a Komoot", "Todavía no hay ninguna copia de seguridad: la primera se crea automáticamente (por la noche) o ahora mismo:"],
           "sicher": ["Las contraseñas y los tokens no están incluidos en la descarga.", "Traslado a un servidor nuevo", "El paquete de traslado contiene todo", "Crear paquete de traslado", "Todavía no se ha creado ningún paquete de traslado."]},
}
# Deutsche Satzreste, die in keiner anderen Sprache in der Verwaltung stehen dürfen (Ganzseitenprüfung je Reiter)
VERBOTEN = ["Komoot-Zugang eintragen", "noch kein Backup", "Passwörter und Tokens", "Umzug auf einen", "Umzugspaket", "kein Umzugspaket", " to go", "Das letzte Backup ist älter", "Zepp-Token ist abgelaufen",
            "Mit Suunto verbinden", "Mit Strava verbinden", "Im selben Browser", "nachladen (Touren bleiben"]
# Wörter, die ein deutscher Satz enthält; geprüft in Warnleiste und Reiter „Sicherung“ (Code und Markenname „Meine Touren“ ausgenommen)
DE = r"\b(der|die|das|und|nicht|ist|wird|werden|für|mit|auf|noch|oder|kein|keine|enthält|Sicherung|Umzug|Umzugspaket|Zugangsdaten|Verwaltung|eintragen|Passwörter|Schlüssel|Fotos und Routen|erstellt)\b"
SCAN = """([sel, re]) => { const R = new RegExp(re, 'i'), out = [];
  document.querySelectorAll(sel).forEach(root => {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); let n;
    while (n = w.nextNode()) { const p = n.parentElement; if (!p || p.closest('code,pre,script,style,option')) continue; const t = n.nodeValue.replace(/Meine Touren/g, '').trim(); if (t.length > 2 && R.test(t)) out.push(t.slice(0, 160)); }
    root.querySelectorAll('[title],[aria-label],[placeholder]').forEach(e => ['title', 'aria-label', 'placeholder'].forEach(a => { const t = e.getAttribute(a); if (t && R.test(t.replace(/Meine Touren/g, ''))) out.push('@' + a + ' ' + t.slice(0, 160)); }));
  });
  return [...new Set(out)]; }"""


@pytest.fixture(scope="module")
def app():
    d = Path(tempfile.mkdtemp(prefix="i18n339"))
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


def _admin(pw, url, lang, tab):
    b = pw.chromium.launch()
    ctx = b.new_context(locale=LOC[lang], viewport={"width": 1280, "height": 1000}, reduced_motion="reduce")
    ctx.add_init_script("try { localStorage.setItem('lang', %r); localStorage.removeItem('admtab'); } catch (e) {}" % lang)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(url) else r.continue_())
    pg.browser_ = b
    pg.goto(f"{url}/#/admin?tab={tab}")
    pg.wait_for_function("() => document.querySelectorAll('.atab').length === 8 && !!document.querySelector('#umzls') && !!document.querySelector('.warnbar')", timeout=TL)
    pg.wait_for_function("() => !!document.querySelector('#umzls').textContent.trim()", timeout=TL)       # Liste der Umzugspakete geladen
    quiet(pg, 4000)
    return pg


@pytest.mark.parametrize("lang", ["en", "fr", "es"])
def test_warnleiste_backup_und_umzug_uebersetzt(pw, app, lang):
    pg = _admin(pw, app, lang, "sicher")
    try:
        bar = pg.locator(".warnbar").first
        for t in ERW[lang]["warn"]:
            expect(bar).to_contain_text(t, timeout=TL)
        tab = pg.locator('.atab[data-t="sicher"]')
        expect(tab).to_be_visible(timeout=TL)
        for t in ERW[lang]["sicher"]:
            expect(tab).to_contain_text(t, timeout=TL)
        # kein deutscher Restsatz in Warnleiste und Reiter „Sicherung“
        rest = pg.evaluate(SCAN, [".warnbar, .atab[data-t=sicher]", DE])
        assert rest == [], (lang, rest)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("lang", ["en", "fr", "es"])
@pytest.mark.parametrize("tab", TABS)
def test_jeder_reiter_ohne_deutsche_restsaetze(pw, app, lang, tab):
    pg = _admin(pw, app, lang, tab)
    try:
        text = pg.evaluate("() => document.querySelector('#main').innerText + ' ' + [...document.querySelectorAll('#main [title],#main [aria-label]')].map(e => (e.title || '') + ' ' + (e.getAttribute('aria-label') || '')).join(' ')")
        gefunden = [v for v in VERBOTEN if v in text]
        assert gefunden == [], (lang, tab, gefunden)
        # der aktive Reiter ist sichtbar und nicht leer
        expect(pg.locator(f'.atab[data-t="{tab}"]')).to_be_visible(timeout=TL)
    finally:
        pg.browser_.close()


def test_deutsch_bleibt_unveraendert(pw, app):
    b = pw.chromium.launch()
    ctx = b.new_context(locale="de-DE", viewport={"width": 1280, "height": 1000}, reduced_motion="reduce")
    ctx.add_init_script("try { localStorage.setItem('lang', 'de'); localStorage.removeItem('admtab'); } catch (e) {}")
    pg = ctx.new_page()
    pg.goto(f"{app}/#/admin?tab=sicher")
    tab = pg.locator('.atab[data-t="sicher"]')
    expect(tab).to_contain_text("Umzug auf einen neuen Server", timeout=TL)
    expect(tab).to_contain_text("Das Umzugspaket enthält alles", timeout=TL)
    expect(pg.locator(".warnbar").first).to_contain_text("Es gibt noch keine Sicherung", timeout=TL)
    b.close()
