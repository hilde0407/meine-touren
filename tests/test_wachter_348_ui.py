"""3.48.0 – Sicherungs-Wächter (Browser, Chromium): Warnleiste unter der Kopfzeile nur für Administratoren, Fälle (alt / fehlerhaft / keine), „Morgen erinnern“ (nicht im Fehlerfall),
Ablauf am nächsten Tag, Knopf „Zur Sicherung“, kein Polling, 390 px, hell/dunkel, Englisch, Betrachter ohne Leiste. Screenshots mit TS_SHOTS=<Ordner>."""
import json
import os
import socket
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from tests.test_bausteine_ui import T, _shot  # noqa: F401
from tests.test_bausteine_ui import pw  # noqa: F401  (Fixture)
from tests.test_tourseite_ui import LAUNCH, SEED, _wait

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    tmp = tmp_path_factory.mktemp("wb")
    data = tmp / "data"
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data)}], capture_output=True, text=True, cwd=ROOT, env=env)
    assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / "launch.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    pr = subprocess.Popen([sys.executable, str(script)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    yield {"url": url, "data": data, "b": tmp / "b"}
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)


def _db(app, sql, args=()):
    c = sqlite3.connect(app["data"] / "komoot_hub.sqlite", timeout=15)
    try:
        c.execute(sql, args)
        c.commit()
    finally:
        c.close()


def _state(app, tage=None, fehler=""):
    """Alle Sicherungen entfernen, ggf. eine Sicherungsdatei mit Alter anlegen und den Fehlerzustand setzen."""
    for d in (app["b"], app["data"] / "backups"):
        if d.exists():
            for f in d.glob("*.zip"):
                f.unlink()
    if tage is not None:
        d = app["data"] / "backups"
        d.mkdir(parents=True, exist_ok=True)
        f = d / "meine-touren-test.zip"
        f.write_bytes(b"x")
        t = time.time() - tage * 86400 - 600
        os.utime(f, (t, t))
    _db(app, "INSERT INTO settings(k,v) VALUES('backup_err',?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (fehler,))
    _db(app, "DELETE FROM settings WHERE k='backup_check'")


def _page(pw, app, scheme="light", width=1280, locale="de-DE", route="#/dash", warten=True):
    b = pw.chromium.launch()
    ctx = b.new_context(locale=locale, viewport={"width": width, "height": 900 if width > 500 else 844}, color_scheme=scheme, device_scale_factor=1, reduced_motion="reduce")
    pg = ctx.new_page()
    pg.errors, pg.calls = [], []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("request", lambda r: pg.calls.append(r.url) if "/api/backup/waechter" in r.url else None)
    pg.browser_ = b
    pg.goto(app["url"] + "/" + route)
    if warten:
        pg.wait_for_function("() => document.querySelectorAll('#main *').length > 3", timeout=T)
    return pg


def _bar(pg, sichtbar=True):
    if sichtbar:
        pg.wait_for_selector("#wbar", timeout=T)
    else:
        pg.wait_for_function("() => !document.getElementById('wbar')", timeout=T)


def test_old_backup_text_buttons_dismiss_and_expiry(pw, app):
    _state(app, tage=9)
    pg = _page(pw, app)
    try:
        _bar(pg)
        txt = pg.locator("#wbar").inner_text()
        assert "Sicherung" in txt and "Letzte Sicherung vor 9 Tagen." in txt and "Zur Sicherung" in txt and "Morgen erinnern" in txt
        assert pg.evaluate("() => document.querySelector('header.top').nextElementSibling.id") == "wbar"          # direkt unter der Kopfzeile
        order = pg.evaluate("() => [...document.querySelectorAll('#wbar .wba > *')].map(e => e.textContent.trim())")
        assert order == ["Morgen erinnern", "Zur Sicherung"]                                                     # sekundär links, Hauptknopf rechts
        assert pg.evaluate("() => document.getElementById('wbar').getBoundingClientRect().height") < 60            # schmal
        pg.locator("#wbgo").click()
        pg.wait_for_function("() => location.hash === '#/admin?tab=sicher'", timeout=T)
        pg.wait_for_selector("#bkst", timeout=T)
        pg.wait_for_selector("#wbar", timeout=T)                                                                   # auf allen Seiten, auch in der Verwaltung
        pg.locator("#wbhide").click()
        pg.wait_for_function("() => !document.getElementById('wbar')", timeout=T)
        pg.evaluate("() => { location.hash = '#/stats'; }")                                                       # Seitenwechsel: bleibt weg
        pg.wait_for_function("() => location.hash === '#/stats'", timeout=T)
        pg.reload()
        pg.wait_for_function("() => document.querySelectorAll('#main *').length > 3", timeout=T)
        assert pg.evaluate("() => !document.getElementById('wbar')")
        key = pg.evaluate("() => Object.keys(localStorage).find(k => k.startsWith('wachterBis:'))")
        assert key
        pg.evaluate("(k) => localStorage.setItem(k, '2000-01-01')", key)                                          # gestern oder früher: erscheint wieder
        pg.reload()
        pg.wait_for_selector("#wbar", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_missing_backup_and_error_cases_not_dismissable(pw, app):
    _state(app, tage=None)
    pg = _page(pw, app)
    try:
        _bar(pg)
        assert "Es gibt noch keine Sicherung deiner Touren." in pg.locator("#wbar").inner_text()
        assert pg.locator("#wbhide").count() == 1
    finally:
        pg.browser_.close()
    _state(app, tage=1, fehler="Ordner nicht beschreibbar")
    pg = _page(pw, app)
    try:
        _bar(pg)
        assert "Die letzte Sicherung ist fehlgeschlagen." in pg.locator("#wbar").inner_text()
        assert pg.locator("#wbhide").count() == 0 and pg.get_attribute("#wbar", "role") == "alert"
        assert pg.locator("#wbar .wbi").inner_text() == "✗"                                                         # Text und Symbol, nicht nur Farbe
    finally:
        pg.browser_.close()
    _state(app, tage=0)                                                                                           # frisch, aber nicht lesbar (Prüfung)
    req = urllib.request.Request(app["url"] + "/api/backup/check", method="POST")
    assert json.loads(urllib.request.urlopen(req, timeout=20).read())["ok"] is False
    pg = _page(pw, app)
    try:
        _bar(pg)
        assert "nicht lesbar oder beschädigt" in pg.locator("#wbar").inner_text() and pg.locator("#wbhide").count() == 0
    finally:
        pg.browser_.close()


def test_fresh_backup_has_no_bar(pw, app):
    _state(app, tage=1)
    pg = _page(pw, app)
    try:
        pg.wait_for_function("() => performance.getEntriesByType('resource').some(r => r.name.includes('/api/backup/waechter'))", timeout=T)
        assert pg.locator("#wbar").count() == 0
    finally:
        pg.browser_.close()


def test_no_polling_and_throttled_on_navigation(pw, app):
    _state(app, tage=9)
    pg = _page(pw, app)
    try:
        _bar(pg)
        for h in ("#/stats", "#/dash", "#/tours", "#/dash"):
            pg.evaluate("(h) => { location.hash = h; }", h)
            pg.wait_for_function("(h) => location.hash === h", arg=h, timeout=T)
            pg.wait_for_selector("#wbar", timeout=T)
        assert len(pg.calls) == 1, pg.calls                                                                        # einmal geladen, Seitenwechsel aus dem Speicher
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme,width", [("light", 390), ("dark", 390), ("light", 1280), ("dark", 1280)])
def test_look_and_screenshots(pw, app, scheme, width):
    for fall, tage, fehler in (("alt", 9, ""), ("fehler", 1, "Ordner nicht beschreibbar")):
        _state(app, tage=tage, fehler=fehler)
        pg = _page(pw, app, scheme=scheme, width=width)
        try:
            _bar(pg)
            assert pg.evaluate("() => document.documentElement.scrollWidth - window.innerWidth") <= 0
            r = pg.evaluate("""() => { const b = document.getElementById('wbar'); const r = b.getBoundingClientRect();
              return {h: Math.round(r.height), btn: [...b.querySelectorAll('.btn')].map(x => Math.round(x.getBoundingClientRect().height)), out: [...b.querySelectorAll('*')].some(x => x.getBoundingClientRect().right > innerWidth + 1)}; }""")
            assert not r["out"] and min(r["btn"]) >= (36 if width < 500 else 28), r
            assert r["h"] < (110 if width < 500 else 60), r
            c = pg.evaluate("() => { const b = document.getElementById('wbar'); return [getComputedStyle(b).color, getComputedStyle(b).backgroundColor]; }")
            assert c[0] != c[1]
            _shot(pg, f"waechter-{fall}-{width}-{scheme}.png", full=False)
            assert not pg.errors, pg.errors
        finally:
            pg.browser_.close()


def test_english_and_french(pw, app):
    _state(app, tage=9)
    pg = _page(pw, app, locale="en-US")
    try:
        pg.evaluate("() => localStorage.setItem('lang', 'en')")
        pg.reload()
        _bar(pg)
        txt = pg.locator("#wbar").inner_text()
        assert "Last backup 9 days ago." in txt and "Remind me tomorrow" in txt and "Go to backup" in txt, txt
        pg.evaluate("() => localStorage.setItem('lang', 'fr')")
        pg.reload()
        _bar(pg)
        txt = pg.locator("#wbar").inner_text()
        assert "il y a 9 jours" in txt and "Me le rappeler demain" in txt, txt
        pg.evaluate("() => localStorage.setItem('lang', 'de')")
    finally:
        pg.browser_.close()


def test_viewer_sees_no_bar_admin_does(pw, app):
    """Zuletzt: schaltet die Benutzerverwaltung ein (Administrator, Betrachter)."""
    _state(app, tage=9)
    base = app["url"]

    def post(path, body, cookie=None):
        req = urllib.request.Request(base + path, method="POST", data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **({"Cookie": cookie} if cookie else {})})
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.headers.get("Set-Cookie", "")
    post("/api/setup", {"name": "chef", "email": "chef@example.com", "password": "geheim123"})
    ck = post("/api/login", {"name": "chef", "password": "geheim123"}).split(";")[0]
    post("/api/users", {"name": "oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"}, ck)
    for name, pw_, erwartet in (("chef", "geheim123", True), ("oma", "omas-pass12", False)):
        pg = _page(pw, app, route="", warten=False)
        try:
            pg.wait_for_selector(".authbox", timeout=T)
            pg.evaluate("""async ([n, p]) => { const r = await fetch('/api/login', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: n, password: p})}); if (!r.ok) throw new Error('login'); }""", [name, pw_])
            pg.reload()
            pg.wait_for_selector("#umenu", timeout=T)
            if erwartet:
                pg.wait_for_selector("#wbar", timeout=T)
            else:
                pg.wait_for_function("() => !!document.getElementById('umenu') && !document.querySelector('.authbox')", timeout=T)
                assert pg.locator("#wbar").count() == 0 and not pg.calls, pg.calls                              # Betrachter: keine Leiste, nicht einmal eine Abfrage
        finally:
            pg.browser_.close()
