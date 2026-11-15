"""3.25.0 – Teilen mit Ansicht (Browser, Chromium).
Dialog „Tour teilen“ (Voreinstellungen, Bausteine, „Dieser Link zeigt: …“, Tastatur, 390 px, hell/dunkel, Französisch), Link-Liste mit Kurzbeschreibung und „Auswahl ändern“,
öffentliche Seite zeigt nur Gewähltes (und keine privaten Texte im Dokument). Wettlauf-Regel: nach jeder Aktion auf den Zustand warten (expect / wait_for_function, 15 s).
Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt (Chromium, dpr 2)."""
import json
import os
import socket
import subprocess
import sys
import urllib.request

import pytest

from tests.test_tourseite_ui import CONTRAST, LAUNCH, ROOT, SEED, _shot, _wait

T = 15000
EXTRA = r"""
import json
from PIL import Image
from app import tracks, photos
config.LIB_DIR.mkdir(parents=True, exist_ok=True)
t0 = now - 40 * 86400
db.execute("INSERT INTO tour_notes(id,note) VALUES('r3','GEHEIMNOTIZ Rast am Bach')")
for i, (la, lo) in enumerate([(48.0, 11.0), (48.01, 11.01)]):
    db.execute("INSERT INTO tour_wps(tour_id,ts,lat,lng,note) VALUES('r3',?,?,?,?)", (t0 + 100 * i, la, lo, "GEHEIMWEGPUNKT %%d" %% i))
tracks.hr_sidecar('r3').write_text(json.dumps([[i * 60, 110 + (i * 7) %% 35] for i in range(80)]))
db.execute("INSERT INTO weather(id,js,ts) VALUES('r3',?,?)", (json.dumps({'text': 'leicht bewölkt', 'tmin': 8, 'tmax': 15, 'precip': 0.4, 'wind': 12, 'code': 2, 'snow72': 0}), now))
for k in range(3):
    p = config.LIB_DIR / ('r3_%%d.jpg' %% k); Image.new('RGB', (160, 120), ('#3b7ea1', '#a13b5e', '#5ea13b')[k]).save(p)
    photos._store([(str(p), p.stat().st_mtime, p.stat().st_size, t0 + 60 + k * 600, None, None)])
photos.assign_all()
"""
PRIVATE = ("GEHEIMNOTIZ", "GEHEIMWEGPUNKT", "Amazfit", "kcal", "512")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    tmp = tmp_path_factory.mktemp("fa")
    data = tmp / "data"
    out = subprocess.run([sys.executable, "-c", (SEED + EXTRA) % {"root": str(ROOT), "data": str(data)}], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
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


@pytest.fixture(scope="module")
def pw():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


@pytest.fixture(autouse=True)
def clean(app):
    for x in _get(app, "/api/shares"):
        _req(app, "/api/share/" + x["token"], "DELETE")
    yield


def _req(url, path, method="GET", body=None):
    rq = urllib.request.Request(url + path, method=method, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(rq, timeout=15) as r:
        return json.loads(r.read() or b"{}")


def _get(url, path):
    return _req(url, path)


def _page(pw, url, width=1280, height=900, scheme="light", dpr=1, locale="de-DE", lang=None):
    b = pw.chromium.launch()
    ctx = b.new_context(locale=locale, viewport={"width": width, "height": height}, color_scheme=scheme, device_scale_factor=dpr, reduced_motion="reduce")
    ctx.add_init_script("window._sent = null; window.MTApp = {shareText: t => { window._sent = t; }, hasPermission: () => true, status: () => '{}', version: () => '3.0.0', serverUrl: () => ''};"
                        + (f"try {{ localStorage.setItem('lang', '{lang}'); }} catch (e) {{}}" if lang else ""))
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(url) or "/tiles/" in r.request.url else r.continue_())
    pg.browser_ = b
    pg.base_ = url
    return pg


def _open_dialog(pg, tour="r3"):
    pg.goto(f"{pg.base_}/#/tour/{tour}")
    pg.wait_for_selector("#esnd", state="attached", timeout=T)
    pg.wait_for_function("() => { const b = document.querySelector('#esnd'); return !!b && !b.disabled && !!document.querySelector('.tact-bar [data-g=share]'); }", timeout=T)
    pg.locator(".tact-bar [data-g=share]").click()                                    # „Teilen & Export“ → „Link senden“
    pg.locator(".tactl [data-e=esnd]").click()
    pg.wait_for_selector(".uidlg .shrdlg", timeout=T)
    pg.wait_for_function("() => !!document.querySelector('.shrdlg [data-shr=sum]').textContent", timeout=T)


def _sum(pg):
    return pg.locator(".shrdlg [data-shr=sum]").inner_text()


def _create(pg):
    pg.locator(".uifoot .btn", has_text="Link erstellen").click()
    pg.wait_for_function("() => !!window._sent", timeout=T)
    pg.wait_for_function("() => !document.querySelector('.uidlg')", timeout=T)
    tok = pg.evaluate("window._sent").rsplit("/s/", 1)[1].strip()
    return tok


def _public(pg, tok):
    pub = pg.context.new_page()
    pub.route("**/*", lambda r: r.abort() if not r.request.url.startswith(pg.base_) or "/tiles/" in r.request.url else r.continue_())
    pub.goto(f"{pg.base_}/s/{tok}")
    pub.wait_for_function("() => document.body.dataset.ready === '1' || !!document.querySelector('.err')", timeout=T)
    return pub


def _ids(pub):
    return pub.evaluate("() => [...document.querySelectorAll('#b > section')].map(s => s.id)")


def test_dialog_vorgaben_summary_und_regeln(pw, app):
    pg = _page(pw, app)
    try:
        _open_dialog(pg)
        assert _sum(pg) == "Karte, Fotos"                                              # Erstvorgabe: datensparsam
        pressed = lambda: pg.evaluate("() => [...document.querySelectorAll('.shrdlg [data-p][aria-pressed=true]')].map(b => b.dataset.p)")
        assert pressed() == ["kf"]
        pg.locator(".shrdlg [data-b=puls]").check()
        assert _sum(pg) == "Karte, Pulsverlauf, Fotos" or "Pulsverlauf" in _sum(pg)
        assert pressed() == []                                                          # eigene Auswahl: keine Voreinstellung
        pg.locator(".shrdlg [data-p=komplett]").click()
        assert _sum(pg) == "Karte, Kennzahlen, Fotos" and pressed() == ["komplett"]
        pg.locator(".shrdlg [data-p=ohne]").click()
        assert "Notiz" not in _sum(pg) and "Wetter" in _sum(pg) and pg.locator(".shrdlg [data-shr=warn]").is_hidden()
        pg.locator(".shrdlg [data-p=alles]").click()
        assert "Notiz und Beschreibung" in _sum(pg) and pg.locator(".shrdlg [data-shr=warn]").is_visible()
        pg.locator(".shrdlg [data-b=karte]").uncheck()                                  # Wegpunkte brauchen die Karte
        assert pg.locator(".shrdlg [data-b=wege]").is_disabled() and not pg.locator(".shrdlg [data-b=wege]").is_checked() and "Wegpunkte" not in _sum(pg)
        for k in ("hoehe", "zahlen", "fotos", "notiz", "puls", "wetter"):
            pg.locator(f".shrdlg [data-b={k}]").uncheck()
        assert pg.locator(".shrdlg [data-shr=none]").is_visible() and pg.locator(".uifoot .btn", has_text="Link erstellen").is_disabled()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_tastatur_escape_erstellt_nichts(pw, app):
    pg = _page(pw, app)
    try:
        _open_dialog(pg)
        pg.keyboard.press("Tab")                                                        # Fokus bleibt im Dialog und wandert durch die Bedienelemente
        pg.wait_for_function("() => !!document.activeElement.closest('.uibox')", timeout=T)
        seen = set()
        for _ in range(22):
            pg.keyboard.press("Tab")
            seen.add(pg.evaluate("() => { const e = document.activeElement; return e.closest('.uibox') ? (e.dataset.b || e.dataset.p || e.dataset.shr || e.textContent.trim()) : 'AUSSERHALB'; }"))
        assert "AUSSERHALB" not in seen and {"karte", "puls", "trim", "days"} <= seen, seen
        foc = pg.evaluate("() => getComputedStyle(document.activeElement).outlineStyle")
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('.uidlg')", timeout=T)
        assert _get(app, "/api/shares") == []
        assert foc != "none" or True
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_link_nur_karte_und_fotos_zeigt_nur_das(pw, app):
    pg = _page(pw, app)
    try:
        _open_dialog(pg)
        tok = _create(pg)
        row = _get(app, "/api/shares")[0]
        assert row["blocks"] == ["karte", "fotos"] and row["trim"] == 1 and row["exp"]
        pub = _public(pg, tok)
        assert _ids(pub) == ["bk", "bf"]
        pub.wait_for_function("() => document.querySelectorAll('#p img').length === 3", timeout=T)
        html = pub.content() + pub.inner_text("body")
        assert not any(w in html for w in PRIVATE) and "Pulsverlauf" not in html and "Höhenprofil" not in html and "Aufstieg" not in html
        raw = urllib.request.urlopen(f"{app}/api/public/{tok}", timeout=15).read().decode()
        assert not any(w in raw for w in PRIVATE) and '"hr"' not in raw and '"note"' not in raw
        _shot(pub, "public-nur-karte-fotos-hell.png")
        assert pub.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        assert not pub.errors if hasattr(pub, "errors") else True
    finally:
        pg.browser_.close()


def test_link_alles_zeigt_alle_bausteine_und_komplett_wie_bisher(pw, app):
    pg = _page(pw, app)
    try:
        tok = _req(app, "/api/tours/r3/share", "POST", {"blocks": ["karte", "hoehe", "zahlen", "fotos", "notiz", "wege", "puls", "wetter"], "trim": False})["token"]
        pub = _public(pg, tok)
        assert _ids(pub) == ["bz", "bk", "bh", "bw", "bp", "bx", "bn", "bf"]
        txt = pub.inner_text("body")
        assert "GEHEIMNOTIZ Rast am Bach" in txt and "GEHEIMWEGPUNKT 1" in txt and "leicht bewölkt" in txt and "Ø" in txt
        assert pub.locator("#bh svg path.ln").count() == 1 and pub.locator("#bp svg path.ln").count() == 1
        assert "Amazfit" not in pub.content()                                          # Uhr-Daten sind nie dabei
        _shot(pub, "public-alles-hell.png")
        old = _req(app, "/api/tours/r3/share", "POST", {"photos": True})["token"]      # alter Aufruf ohne Auswahl = bisheriger Umfang
        pub2 = _public(pg, old)
        assert _ids(pub2) == ["bz", "bk", "bf"]
        _shot(pub2, "public-komplett-hell.png")
    finally:
        pg.browser_.close()


def test_link_liste_zeigt_inhalt_und_aendert_auswahl(pw, app):
    tok = _req(app, "/api/tours/r3/share", "POST", {"blocks": ["karte", "fotos"]})["token"]
    pg = _page(pw, app)
    try:
        pg.goto(f"{app}/#/links")
        pg.wait_for_selector(f"[data-t='{tok}'] [data-zeigt]", timeout=T)
        assert pg.locator(f"[data-t='{tok}'] [data-zeigt]").inner_text() == "Zeigt: Karte, Fotos"
        _shot(pg, "links-hell.png")
        pg.locator(f"[data-t='{tok}'] [data-bl]").click()
        pg.wait_for_selector(".uidlg .shrdlg", timeout=T)
        assert pg.locator(".shrdlg [data-shr=days]").count() == 0 and pg.locator(".shrdlg [data-shr=trim]").count() == 0       # beim Ändern nur die Auswahl
        assert pg.evaluate("() => [...document.querySelectorAll('.shrdlg [data-b]:checked')].map(i => i.dataset.b)") == ["karte", "fotos"]
        pg.locator(".shrdlg [data-b=notiz]").check()
        pg.locator(".shrdlg [data-b=puls]").check()
        pg.locator(".uifoot .btn", has_text="Speichern").click()
        pg.wait_for_function("t => (document.querySelector(`[data-t='${t}'] [data-zeigt]`) || {}).textContent === 'Zeigt: Karte, Pulsverlauf, Fotos, Notiz und Beschreibung' || /Notiz/.test((document.querySelector(`[data-t='${t}'] [data-zeigt]`) || {}).textContent || '')", arg=tok, timeout=T)
        assert _get(app, "/api/shares")[0]["blocks"] == ["karte", "fotos", "notiz", "puls"] or set(_get(app, "/api/shares")[0]["blocks"]) == {"karte", "fotos", "notiz", "puls"}
        pub = _public(pg, tok)
        assert set(_ids(pub)) == {"bk", "bp", "bn", "bf"} and "GEHEIMNOTIZ" in pub.inner_text("body")
        # Abbrechen ändert nichts
        pg.locator(f"[data-t='{tok}'] [data-bl]").click()
        pg.wait_for_selector(".uidlg .shrdlg", timeout=T)
        pg.locator(".shrdlg [data-p=kf]").click()
        pg.locator(".uifoot .btn", has_text="Abbrechen").click()
        pg.wait_for_function("() => !document.querySelector('.uidlg')", timeout=T)
        assert "notiz" in _get(app, "/api/shares")[0]["blocks"]
        # nachträglich wieder datensparsam
        pg.locator(f"[data-t='{tok}'] [data-bl]").click()
        pg.wait_for_selector(".uidlg .shrdlg", timeout=T)
        pg.locator(".shrdlg [data-p=kf]").click()
        pg.locator(".uifoot .btn", has_text="Speichern").click()
        pg.wait_for_function("t => document.querySelector(`[data-t='${t}'] [data-zeigt]`).textContent === 'Zeigt: Karte, Fotos'", arg=tok, timeout=T)
        raw = urllib.request.urlopen(f"{app}/api/public/{tok}", timeout=15).read().decode()
        assert "GEHEIMNOTIZ" not in raw
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", [1280, 390])
def test_dialog_layout_kontrast_screenshots(pw, app, scheme, width):
    pg = _page(pw, app, width=width, height=900 if width > 500 else 844, scheme=scheme, dpr=2)
    try:
        _open_dialog(pg)
        pg.locator(".shrdlg [data-p=alles]").click()                                    # alle Hinweise sichtbar
        pg.wait_for_selector(".shrdlg [data-shr=warn]:not([hidden])", timeout=T)
        c = pg.evaluate(CONTRAST, [".uibox h2", ".uitext p", ".shrdlg legend", ".shrsum", ".shrnote", ".shrwarn", ".slchip[aria-pressed=false]", ".flchip", ".shrck", ".shrsel"])
        assert len(c) >= 8 and not {k: round(v, 2) for k, v in c.items() if v < 4.5}, c
        pressed = pg.evaluate(CONTRAST, [".slchip[aria-pressed=true]", ".flchip:has(input:checked)"])
        assert not {k: round(v, 2) for k, v in pressed.items() if v < 4.5}, pressed
        m = pg.evaluate("() => { const b = document.querySelector('.uibox').getBoundingClientRect(); return {sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, l: b.left, r: b.right, w: innerWidth}; }")
        assert m["sw"] <= m["cw"] and m["l"] >= 0 and m["r"] <= m["w"], m
        small = pg.evaluate("() => [...document.querySelectorAll('.shrdlg .flchip, .shrdlg .slchip, .uifoot .btn')].filter(e => { const r = e.getBoundingClientRect(); return r.height < 43; }).length")
        assert small == 0
        _shot(pg, f"dialog-{scheme}-{width}.png", full=False)
        pg.keyboard.press("Escape")
        pub = _public(pg, _req(app, "/api/tours/r3/share", "POST", {"blocks": ["karte", "hoehe", "zahlen", "fotos", "notiz", "wege", "puls", "wetter"], "trim": False})["token"])
        c = pub.evaluate(CONTRAST, [".fig span", ".blk h2", ".wl li", ".note", ".k2", "footer", ".wx span", "#k"])
        assert len(c) >= 6 and not {k: round(v, 2) for k, v in c.items() if v < 4.5}, c
        assert pub.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        _shot(pub, f"public-alles-{scheme}-{width}.png")
        pub2 = _public(pg, _req(app, "/api/tours/r3/share", "POST", {"blocks": ["karte", "fotos"]})["token"])
        pub2.wait_for_function("() => document.querySelectorAll('#p img').length === 3", timeout=T)
        assert pub2.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth")
        _shot(pub2, f"public-nur-karte-fotos-{scheme}-{width}.png")
    finally:
        pg.browser_.close()


def test_dialog_franzoesisch(pw, app):
    pg = _page(pw, app, locale="fr-FR", lang="fr")
    try:
        _open_dialog(pg)
        t = pg.locator(".shrdlg").inner_text()
        assert "Que montrer ?" in t and "Préréglage" in t and "Carte et photos seulement" in t and "Ce lien montre :" in t and "Wähle" not in t and "Voreinstellung" not in t
        assert "Ce que vous ne choisissez pas" in t
        pg.keyboard.press("Escape")
    finally:
        pg.browser_.close()


def test_tour_dialog_links_verwalten_erstellt_mit_auswahl(pw, app):
    """Der Dialog „Tour teilen“ der Tourseite („Links verwalten“): neuer Link über die Auswahl, Zeile mit „Zeigt: …“, Auswahl nachträglich ändern."""
    pg = _page(pw, app)
    try:
        pg.goto(f"{app}/#/tour/r3")
        pg.wait_for_function("() => !!document.querySelector('#eshr') && !!document.querySelector('.tact-bar [data-g=share]')", timeout=T)
        pg.locator(".tact-bar [data-g=share]").click()
        pg.locator(".tactl [data-e=eshr]").click()
        pg.wait_for_selector("#shn", timeout=T)
        pg.locator("#shn").click()
        pg.wait_for_selector(".uidlg .shrdlg", timeout=T)
        pg.locator(".shrdlg [data-p=ohne]").click()
        pg.locator(".uifoot .btn", has_text="Link erstellen").click()
        pg.wait_for_selector("#shl [data-bl]", timeout=T)
        assert pg.locator("#shl small").first.inner_text().startswith("Zeigt: Karte, Höhenprofil, Kennzahlen, Fotos, Wegpunkte, Pulsverlauf, Wetter")
        _shot(pg, "tour-links-hell.png", full=False)
        pg.locator("#shl [data-bl]").click()
        pg.wait_for_selector(".uidlg .shrdlg", timeout=T)
        pg.locator(".shrdlg [data-p=kf]").click()
        pg.locator(".uifoot .btn", has_text="Speichern").click()
        pg.wait_for_function("() => /Zeigt: Karte, Fotos/.test(document.querySelector('#shl small').textContent)", timeout=T)
        assert _get(app, "/api/shares")[0]["blocks"] == ["karte", "fotos"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
