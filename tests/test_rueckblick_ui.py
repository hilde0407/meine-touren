"""3.26.0 – Jahresrückblick als teilbare Seite (Browser, Chromium): Dialog „Was wird gezeigt?“, Link, öffentliche Seite (hell/dunkel, 390 px), Druckansicht/PDF, Link-Liste.
Wettlauf-Regel: nach jeder Aktion auf den Zustand warten (expect / wait_for_function mit Arrow-Funktion, 15 s). Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import os
import re
import urllib.request

import pytest

from tests.test_freigabe_ansicht_ui import PRIVATE, T, _get, _page, _public, _req, app, pw  # noqa: F401
from tests.test_tourseite_ui import CONTRAST, _shot

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect  # noqa: E402


@pytest.fixture(autouse=True)
def clean(app):
    for x in _get(app, "/api/shares"):
        _req(app, "/api/share/" + x["token"], "DELETE")
    yield


def _year(app):
    return int(_get(app, "/api/tours")[0]["date"][:4])


def _create(pg, app, uncheck=()):
    pg.goto(f"{app}/#/recap/{_year(app)}")
    btn = pg.locator("#rcshare")
    expect(btn).to_be_visible(timeout=T)
    btn.click()
    expect(pg.locator(".uidlg .rbdlg")).to_be_visible(timeout=T)
    for k in uncheck:
        pg.locator(f".rbdlg [data-b={k}]").uncheck()
    pg.locator(".uifoot .btn", has_text="Link erstellen").click()
    expect(pg.locator(".rbres [data-rb=url]")).to_be_visible(timeout=T)
    return pg.locator(".rbres [data-rb=url]").input_value().rsplit("/s/", 1)[1]


def test_dialog_auswahl_und_link(pw, app):
    pg = _page(pw, app)
    try:
        pg.goto(f"{app}/#/recap/{_year(app)}")
        expect(pg.locator("#rcshare")).to_be_visible(timeout=T)
        pg.locator("#rcshare").click()
        expect(pg.locator(".rbdlg [data-rb=sum]")).to_have_text("Kennzahlen, Bestwerte, Heatmap, Beste Fotos", timeout=T)
        assert pg.locator(".rbdlg [data-rb=year]").input_value() == str(_year(app)) and pg.locator(".rbdlg [data-rb=sport] option").count() >= 2
        pg.locator(".rbdlg [data-b=rekorde]").uncheck()
        expect(pg.locator(".rbdlg [data-rb=sum]")).to_have_text("Kennzahlen, Heatmap, Beste Fotos", timeout=T)
        for k in ("kennzahlen", "heatmap", "fotos"):
            pg.locator(f".rbdlg [data-b={k}]").uncheck()
        expect(pg.locator(".rbdlg [data-rb=none]")).to_be_visible(timeout=T)
        expect(pg.locator(".uifoot .btn", has_text="Link erstellen")).to_be_disabled(timeout=T)
        pg.keyboard.press("Escape")                                                       # Abbrechen erstellt nichts
        pg.wait_for_function("() => !document.querySelector('.uidlg')", timeout=T)
        assert _get(app, "/api/shares") == []
        tok = _create(pg, app, uncheck=("rekorde", "fotos"))
        row = _get(app, "/api/shares")[0]
        assert row["token"] == tok and row["kind"] == "rueckblick" and row["blocks"] == ["kennzahlen", "heatmap"] and row["exp"]
        assert pg.locator(".rbres [data-rb=pdf]").get_attribute("href").endswith("?print=1")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_oeffentliche_seite_zeigt_nur_gewaehltes(pw, app):
    y = _year(app)
    tok = _req(app, "/api/rueckblick/share", "POST", {"year": y, "blocks": ["kennzahlen", "rekorde", "heatmap", "fotos"], "days": 7})["token"]
    pg = _page(pw, app)
    try:
        pub = _public(pg, tok)
        ids = pub.evaluate("() => [...document.querySelectorAll('#b > section')].map(s => s.id)")
        assert ids == ["bz", "br", "bh", "bf"], ids
        pub.wait_for_function("() => document.querySelectorAll('#p img').length >= 1 && [...document.querySelectorAll('#p img')].every(i => i.complete && i.naturalWidth > 0)", timeout=T)
        assert pub.locator(".months .mo").count() == 12 and pub.locator(".cal i.l1, .cal i.l2, .cal i.l3, .cal i.l4").count() >= 3
        html = pub.content() + pub.inner_text("body")
        assert not any(w in html for w in PRIVATE) and "leaflet" not in html.lower() and 'id="m"' not in html
        assert str(y) in pub.inner_text("h1") and pub.locator("#pr").is_visible()
        nur = _public(pg, _req(app, "/api/rueckblick/share", "POST", {"year": y, "blocks": ["rekorde"]})["token"])
        assert nur.evaluate("() => [...document.querySelectorAll('#b > section')].map(s => s.id)") == ["br"] and nur.locator("#bf").count() == 0
        gone = _req(app, "/api/rueckblick/share", "POST", {"year": y, "blocks": ["heatmap"], "days": 7})["token"]
        _req(app, "/api/share/" + gone, "DELETE")
        pub3 = pg.context.new_page()
        pub3.goto(f"{app}/s/{gone}")
        expect(pub3.locator("body")).to_contain_text("nicht (mehr) gültig", timeout=T)
    finally:
        pg.browser_.close()


def test_druckansicht_und_pdf(pw, app):
    tok = _req(app, "/api/rueckblick/share", "POST", {"year": _year(app), "blocks": ["kennzahlen", "rekorde", "heatmap", "fotos"], "days": 7})["token"]
    pg = _page(pw, app, scheme="dark")                                                    # Druck ist immer hell, auch bei dunklem Systemdesign
    try:
        pub = _public(pg, tok)
        pub.wait_for_function("() => [...document.querySelectorAll('#p img')].every(i => i.complete)", timeout=T)
        pub.emulate_media(media="print", color_scheme="dark")
        p = pub.evaluate("() => ({bg: getComputedStyle(document.body).backgroundColor, ink: getComputedStyle(document.body).color, btn: getComputedStyle(document.querySelector('#pr')).display, hb: getComputedStyle(document.querySelector('header')).backgroundColor})")
        assert p["bg"] == "rgb(255, 255, 255)" and p["hb"] == "rgb(255, 255, 255)" and p["btn"] == "none" and p["ink"] != "rgb(255, 255, 255)", p
        brk = pub.evaluate("() => [...document.querySelectorAll('.blk, .rec, .fig, .mo')].every(e => getComputedStyle(e).breakInside === 'avoid')")
        assert brk
        pdf = pub.pdf(format="A4", print_background=True)
        assert pdf.startswith(b"%PDF") and 1 <= len(re.findall(rb"/Type\s*/Page[^s]", pdf)) <= 4
        d = os.environ.get("TS_SHOTS")
        if d:
            os.makedirs(d, exist_ok=True)
            open(os.path.join(d, "rueckblick-druck.pdf"), "wb").write(pdf)
        pub.emulate_media(media="screen")
        pub.evaluate("() => { window._p = 0; window.print = () => { window._p++; }; }")
        pub.locator("#pr").click()
        pub.wait_for_function("() => window._p === 1", timeout=T)
        auto = pg.context.new_page()                                                      # ?print=1 startet den Druckdialog von selbst
        auto.route("**/*", lambda r: r.abort() if not r.request.url.startswith(app) or "/tiles/" in r.request.url else r.continue_())
        auto.add_init_script("window._p = 0; window.print = () => { window._p++; };")
        auto.goto(f"{app}/s/{tok}?print=1")
        auto.wait_for_function("() => window._p === 1", timeout=T)
    finally:
        pg.browser_.close()


def test_link_liste_zeigt_typ_und_aendert_auswahl(pw, app):
    y = _year(app)
    tok = _req(app, "/api/rueckblick/share", "POST", {"year": y, "blocks": ["kennzahlen", "heatmap"]})["token"]
    alt = _req(app, "/api/tours/r3/share", "POST", {"blocks": ["karte", "fotos"]})["token"]
    pg = _page(pw, app)
    try:
        pg.goto(f"{app}/#/links")
        z = pg.locator(f"[data-t='{tok}'] [data-zeigt]")
        expect(z).to_have_text("Zeigt: Kennzahlen, Heatmap", timeout=T)
        expect(pg.locator(f"[data-t='{tok}']")).to_contain_text("Jahresrückblick", timeout=T)
        expect(pg.locator(f"[data-t='{alt}'] [data-zeigt]")).to_have_text("Zeigt: Karte, Fotos", timeout=T)
        pg.locator("[data-f=rb]").click()
        expect(pg.locator("[data-t]")).to_have_count(1, timeout=T)
        _shot(pg, "links-rueckblick-hell.png")
        pg.locator(f"[data-t='{tok}'] [data-bl]").click()
        expect(pg.locator(".rbdlg")).to_be_visible(timeout=T)
        assert pg.locator(".rbdlg [data-rb=year]").count() == 0 and pg.locator(".rbdlg [data-rb=days]").count() == 0
        pg.locator(".rbdlg [data-b=rekorde]").check()
        pg.locator(".uifoot .btn", has_text="Speichern").click()
        expect(pg.locator(f"[data-t='{tok}'] [data-zeigt]")).to_have_text("Zeigt: Kennzahlen, Bestwerte, Heatmap", timeout=T)
        assert _get(app, "/api/shares")[1 if _get(app, "/api/shares")[0]["token"] == alt else 0]["blocks"] == ["kennzahlen", "rekorde", "heatmap"]
        assert "rek" in _get(app, "/api/public/" + tok)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width", [1280, 390])
def test_layout_kontrast_screenshots(pw, app, scheme, width):
    y = _year(app)
    tok = _req(app, "/api/rueckblick/share", "POST", {"year": y, "blocks": ["kennzahlen", "rekorde", "heatmap", "fotos"], "days": 7})["token"]
    pg = _page(pw, app, width=width, height=900 if width > 500 else 844, scheme=scheme, dpr=2)
    try:
        pg.goto(f"{app}/#/recap/{y}")
        expect(pg.locator("#rcshare")).to_be_visible(timeout=T)
        pg.locator("#rcshare").click()
        expect(pg.locator(".rbdlg")).to_be_visible(timeout=T)
        c = pg.evaluate(CONTRAST, [".uibox h2", ".uitext p", ".rbdlg legend", ".shrsum", ".shrnote", ".flchip", ".shrsel"])
        assert len(c) >= 6 and not {k: round(v, 2) for k, v in c.items() if v < 4.5}, c
        m = pg.evaluate("() => { const b = document.querySelector('.uibox').getBoundingClientRect(); return {sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, l: b.left, r: b.right, w: innerWidth}; }")
        assert m["sw"] <= m["cw"] and m["l"] >= 0 and m["r"] <= m["w"], m
        assert pg.evaluate("() => [...document.querySelectorAll('.rbdlg .flchip, .uifoot .btn')].filter(e => e.getBoundingClientRect().height < 43).length") == 0
        _shot(pg, f"rueckblick-dialog-{scheme}-{width}.png", full=False)
        pg.keyboard.press("Escape")
        pub = _public(pg, tok)
        pub.wait_for_function("() => [...document.querySelectorAll('#p img')].every(i => i.complete)", timeout=T)
        c = pub.evaluate(CONTRAST, [".fig span", ".blk h2", ".rec .l", ".rec .w span", ".mo h3", ".leg", ".cmp", "footer", ".k", ".pbtn", "h1"])
        assert len(c) >= 8 and not {k: round(v, 2) for k, v in c.items() if v < 4.5}, c
        ov = pub.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth ? [] : [...document.querySelectorAll('body *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1).slice(0, 8).map(e => e.tagName + '.' + e.className + ': ' + e.textContent.slice(0, 50) + ' @' + Math.round(e.getBoundingClientRect().right))")
        assert not ov, ov
        small = pub.evaluate("() => [...document.querySelectorAll('.pbtn')].filter(e => e.getBoundingClientRect().height < 43).length")
        assert small == 0
        _shot(pub, f"rueckblick-public-{scheme}-{width}.png")
    finally:
        pg.browser_.close()
