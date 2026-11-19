"""3.43.0 Karten-Paket (Browser, Chromium): feste Reihenfolge der Bedienkästen (Filter | Ebenen | Aktionen), Panels schließen einheitlich (Esc, Klick daneben, Auslöser, Fenster, Bearbeiten),
nie zwei Panels zugleich und nie überlappend, mobil (390 px) ein Knopf „Filter & Ebenen“ statt Wischleiste, „Touren im Ausschnitt“ nur einmal (Baustein ODER Knopf).
Kartenkacheln sind in der Testumgebung nicht erreichbar: geprüft wird das DOM (Reihenfolge, Rechtecke, elementFromPoint), nicht das Kartenbild.
Wettlauf-Regel: auf Zustände warten (expect/wait_for_function mit 15 s), keine festen Pausen. Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.test_seitenlayout_ui import T, _api, _browser, pw  # noqa: F401
from tests.test_reise_seiten_ui import app  # noqa: F401
from tests.test_foto_karte_ui import clean, _mapok  # noqa: F401
from tests.test_tourseite_ui import _shot
from tests.helpers_ui import press_until_gone, quiet

TL = 30000
ORDER = ["jahr", "sport", "stil", "ebenen", "standort", "ausschnitt"]
BOXES = "() => [...document.querySelectorAll('.mapui > .kapw')].map(w => w.dataset.kp)"
RECT = """(sel) => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height}; }"""
TOP = """(sel) => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(), t = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); return !!t && (e === t || e.contains(t)); }"""
OVER = "() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)"


def _karte(pw, url, lang="de", **kw):
    pg = _browser(pw, url, devs=None, locale={"de": "de-DE", "en": "en-GB", "fr": "fr-FR", "es": "es-ES"}[lang], **kw)
    pg.context.add_init_script("try { localStorage.setItem('lang', %r); } catch (e) {}" % lang)
    pg.goto(f"{url}/#/map", timeout=TL)
    pg.wait_for_function("() => !!document.querySelector('#kax #bigmap') && typeof map !== 'undefined' && !!map && !!document.getElementById('mbx') && !!document.getElementById('mfb') && document.getElementById('bigmap').clientWidth > 300", timeout=TL)
    quiet(pg, 3000, 500)
    return pg


def _zu(pg):
    """kein Panel offen: Streckenfarbe, Ebenenwahl, Blatt „Filter & Ebenen“"""
    return pg.evaluate("() => !document.querySelector('.tpanel') && !document.querySelector('.mapui.mfo') && !document.querySelector('.leaflet-control-layers-expanded')")


def _auf(pg):
    return pg.evaluate("() => [!!document.querySelector('.tpanel'), !!document.querySelector('.mapui.mfo'), !!document.querySelector('.leaflet-control-layers-expanded')].filter(Boolean).length")


def _schnitt(a, b):
    return a["l"] < b["r"] - 1 and b["l"] < a["r"] - 1 and a["t"] < b["b"] - 1 and b["t"] < a["b"] - 1


# ------------------------------------------------------------------  Reihenfolge und Lage  ------------------------------------------------------------------

def test_reihenfolge_desktop(pw, app, clean):
    pg = _karte(pw, app)
    try:
        assert pg.evaluate(BOXES) == ORDER
        # Lesereihenfolge (Zeile, dann links): Filter, Ebenen, Aktionen; nichts überlappt, nichts ragt aus dem Bild
        pos = {k: pg.evaluate(RECT, f"#kap-{k} > .box") for k in ORDER}
        reading = sorted(ORDER, key=lambda k: (round(pos[k]["t"] / 20), pos[k]["l"]))
        assert reading == ORDER, pos
        for k, r in pos.items():
            assert r["l"] >= 0 and r["r"] <= 1280 and r["h"] > 20, (k, r)
        for i, a in enumerate(ORDER):
            for b in ORDER[i + 1:]:
                assert not _schnitt(pos[a], pos[b]), (a, b, pos)
        # Schalter melden ihren Zustand, Öffner tun es als Öffner
        assert pg.evaluate("() => [...document.querySelectorAll('#ms .chip')].every(c => c.getAttribute('aria-pressed') === 'true')")
        pg.locator("#mht").click()
        expect(pg.locator("#mht")).to_have_attribute("aria-pressed", "true", timeout=T)
        pg.locator("#mht").click()
        expect(pg.locator("#mht")).to_have_attribute("aria-pressed", "false", timeout=T)
        pg.locator("#ms .chip").first.click()
        expect(pg.locator("#ms .chip").first).to_have_attribute("aria-pressed", "false", timeout=T)
        assert pg.locator("#mtc").get_attribute("aria-haspopup") and pg.locator("#mbx").get_attribute("aria-haspopup") == "dialog"
        # der Standort-Knopf nennt die Funktion, nicht den Benutzernamen
        assert "Mein Standort" in pg.locator("#mloc").inner_text()
        # die mobile Leiste ist am Desktop unsichtbar
        assert pg.locator("#mfb").is_hidden()
        assert pg.evaluate(OVER) == 0
        _shot(pg, "karte-343-1280-hell")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_gespeicherte_reihenfolge_gilt_weiter(pw, app, clean):
    """Wer die Bedienfelder schon selbst geordnet hat, behält seine Reihenfolge (nur der Standard ist neu)."""
    _api(app, "karte", "PUT", {"order": ["karte", "standort", "jahr", "sport", "stil", "ebenen", "ausschnitt"]})
    pg = _karte(pw, app)
    try:
        assert pg.evaluate(BOXES) == ["standort", "jahr", "sport", "stil", "ebenen", "ausschnitt"]
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Panels schließen einheitlich  ------------------------------------------------------------------

def test_streckenfarbe_schliesst_wie_alles_andere(pw, app, clean):
    pg = _karte(pw, app)
    try:
        # Esc, Fokus kehrt zum Auslöser zurück
        pg.locator("#mtc").click()
        expect(pg.locator(".tpanel")).to_have_count(1, timeout=T)
        assert pg.locator("#mtc").get_attribute("aria-expanded") == "true"
        pg.keyboard.press("Escape")
        expect(pg.locator(".tpanel")).to_have_count(0, timeout=T)
        assert pg.locator("#mtc").get_attribute("aria-expanded") == "false"
        assert pg.evaluate("() => document.activeElement.id") == "mtc"
        # erneuter Klick auf den Auslöser
        pg.locator("#mtc").click()
        expect(pg.locator(".tpanel")).to_have_count(1, timeout=T)
        pg.locator("#mtc").click()
        expect(pg.locator(".tpanel")).to_have_count(0, timeout=T)
        # Klick auf die Karte daneben
        pg.locator("#mtc").click()
        expect(pg.locator(".tpanel")).to_have_count(1, timeout=T)
        pg.mouse.click(1000, 600)
        expect(pg.locator(".tpanel")).to_have_count(0, timeout=T)
        # eigener Knopf „Schließen“
        pg.locator("#mtc").click()
        pg.locator("#tsx").click()
        expect(pg.locator(".tpanel")).to_have_count(0, timeout=T)
        # Bedienen im Panel schließt nicht
        pg.locator("#mtc").click()
        pg.locator(".tpanel [name=tsm][value=one]").check()
        pg.locator(".tpanel #tsb").focus()
        assert pg.locator(".tpanel").count() == 1
        pg.keyboard.press("Escape")
        expect(pg.locator(".tpanel")).to_have_count(0, timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_panel_liegt_im_bild_und_vorne(pw, app, clean):
    pg = _karte(pw, app)
    try:
        pg.locator("#mtc").click()
        expect(pg.locator(".tpanel")).to_have_count(1, timeout=T)
        r = pg.evaluate(RECT, ".tpanel")
        assert r["l"] >= 8 - 1 and r["r"] <= 1280 and r["b"] <= 1000, r
        assert pg.evaluate(TOP, ".tpanel") is True                                    # nichts liegt davor (Bedienkästen, Karte)
        # Stapel: Panel (in .mapui, 500) liegt unter den Fenstern (.uidlg, 3000)
        assert pg.evaluate("() => +getComputedStyle(document.querySelector('.tpanel')).zIndex") < 3000 <= pg.evaluate("() => { const d = document.createElement('div'); d.className = 'uidlg'; document.body.appendChild(d); const z = +getComputedStyle(d).zIndex; d.remove(); return z; }")
        # Panel und Ebenenwahl nie zugleich: Klick auf die Ebenenwahl schließt das Panel, und umgekehrt
        pg.evaluate("() => document.querySelector('.leaflet-control-layers-toggle').click()")
        expect(pg.locator(".tpanel")).to_have_count(0, timeout=T)
        pg.evaluate("() => map._lc.expand()")
        assert _auf(pg) == 1
        pg.locator("#mtc").click()
        expect(pg.locator(".tpanel")).to_have_count(1, timeout=T)
        assert _auf(pg) == 1, "Ebenenwahl muss zugeklappt sein, solange das Panel offen ist"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_fenster_und_bearbeiten_schliessen_das_panel(pw, app, clean):
    pg = _karte(pw, app)
    try:
        pg.locator("#mtc").click()
        expect(pg.locator(".tpanel")).to_have_count(1, timeout=T)
        pg.locator("#mbx").click()                                                     # Fenster „Touren im Ausschnitt“ öffnet: Panel zu
        expect(pg.locator(".uimod")).to_have_count(1, timeout=T)
        assert _zu(pg)
        press_until_gone(pg, "Escape", ".uimod")
        pg.locator("#mtc").click()
        expect(pg.locator(".tpanel")).to_have_count(1, timeout=T)
        pg.evaluate("() => { uiAlert('x'); }")                                         # jeder andere Dialog ebenso
        expect(pg.locator(".uidlg")).to_have_count(1, timeout=T)
        assert _zu(pg)
        press_until_gone(pg, "Escape", ".uidlg")
        pg.locator("#mtc").click()
        expect(pg.locator(".tpanel")).to_have_count(1, timeout=T)
        pg.locator("#slopen").click()                                                  # Bearbeitungsmodus: Panel zu
        expect(pg.locator(".kapedit").first).to_be_visible(timeout=T)
        assert _zu(pg)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_seitenwechsel_schliesst_panel(pw, app, clean):
    pg = _karte(pw, app)
    try:
        pg.locator("#mtc").click()
        expect(pg.locator(".tpanel")).to_have_count(1, timeout=T)
        pg.evaluate("() => { location.hash = '#/tours'; }")
        pg.wait_for_function("() => !document.getElementById('bigmap') && !document.querySelector('.tpanel')", timeout=T)
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Handy (390 px)  ------------------------------------------------------------------

@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_mobil_leiste_und_blatt(pw, app, clean, scheme):
    pg = _karte(pw, app, width=390, height=844, scheme=scheme)
    try:
        assert pg.evaluate("() => document.documentElement.classList.contains('mob')")
        # zugeklappt: höchstens drei Elemente in einer Zeile, kein Wischstreifen, Ziele ≥ 40 px
        vis = pg.evaluate("""() => [...document.querySelectorAll('.mapui > .box, .mapui > .kapw > .box, .mapui > .kaopen')].filter(e => e.offsetParent !== null).map(e => { const r = e.getBoundingClientRect(); return [e.parentElement.dataset.kp || e.className.split(' ')[1] || e.id, r.left, r.top, r.right, r.height]; })""")
        vis.sort(key=lambda v: v[1])                                                     # sichtbare Reihenfolge: Standort | Filter & Ebenen | Seite anpassen
        assert [v[0] for v in vis] == ["standort", "mfbw", "kaopen"], vis
        assert all(abs(v[2] - vis[0][2]) < 4 for v in vis), vis                         # eine Zeile
        assert all(v[3] <= 390 for v in vis), vis
        assert pg.evaluate("() => { const u = document.querySelector('.mapui'); return u.scrollWidth <= u.clientWidth + 1; }")
        assert pg.evaluate(RECT, "#mfb")["h"] >= 40 and pg.evaluate(RECT, "#mloc")["h"] >= 40
        for s in ("#my", "#ms", "#mtc", "#mht", "#mph", "#mbx"):
            assert pg.locator(s).first.is_hidden(), s
        assert pg.evaluate(OVER) == 0
        _shot(pg, f"karte-343-390-{scheme}")
        # Blatt öffnen: alle Filter und Ebenen sichtbar, im Bild, in der Reihenfolge Filter | Ebenen | Aktionen
        pg.locator("#mfb").click()
        expect(pg.locator(".mapui.mfo")).to_have_count(1, timeout=T)
        assert pg.locator("#mfb").get_attribute("aria-expanded") == "true"
        ys = []
        for s in ("#my", "#ms", "#mtc", "#mht", "#mbx"):
            expect(pg.locator(s)).to_be_visible(timeout=T)
            r = pg.evaluate(RECT, s)
            assert r["l"] >= 0 and r["r"] <= 390 and r["b"] <= 844 - 53, (s, r)
            ys.append(r["t"])
        assert ys == sorted(ys), ys
        assert pg.evaluate(OVER) == 0
        _shot(pg, f"karte-343-390-blatt-{scheme}")
        # Esc schließt, Fokus zurück auf den Knopf
        pg.keyboard.press("Escape")
        expect(pg.locator(".mapui.mfo")).to_have_count(0, timeout=T)
        assert pg.evaluate("() => document.activeElement.id") == "mfb"
        # Tippen auf die Karte schließt
        pg.locator("#mfb").click()
        expect(pg.locator(".mapui.mfo")).to_have_count(1, timeout=T)
        pg.mouse.click(300, 700)
        expect(pg.locator(".mapui.mfo")).to_have_count(0, timeout=T)
        # Knopf zweimal = auf/zu
        pg.locator("#mfb").click()
        pg.locator("#mfb").click()
        expect(pg.locator(".mapui.mfo")).to_have_count(0, timeout=T)
        assert pg.locator("#mfb").get_attribute("aria-expanded") == "false"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_mobil_panel_aus_dem_blatt_und_ebenenwahl(pw, app, clean):
    pg = _karte(pw, app, width=390, height=844)
    try:
        pg.locator("#mfb").click()
        pg.locator("#mtc").click()                                                       # Streckenfarbe aus dem Blatt: Blatt zu, Panel unten
        expect(pg.locator(".tpanel")).to_have_count(1, timeout=T)
        assert _auf(pg) == 1
        p = pg.evaluate(RECT, ".tpanel")
        assert p["l"] >= 0 and p["r"] <= 390 and p["b"] <= 844 - 53 and p["t"] >= 0, p
        assert pg.evaluate(TOP, ".tpanel") is True
        # überdeckt weder die Ebenenwahl noch die Leiste oben
        lc = pg.evaluate(RECT, ".leaflet-control-layers")
        assert not _schnitt(p, lc), (p, lc)
        top = pg.evaluate(RECT, ".mapui > .kaopen")
        assert not _schnitt(p, top), (p, top)
        pg.keyboard.press("Escape")
        expect(pg.locator(".tpanel")).to_have_count(0, timeout=T)
        # Ebenenwahl öffnen schließt das Blatt
        pg.locator("#mfb").click()
        expect(pg.locator(".mapui.mfo")).to_have_count(1, timeout=T)
        pg.evaluate("() => document.querySelector('.leaflet-control-layers-toggle').click()")
        expect(pg.locator(".mapui.mfo")).to_have_count(0, timeout=T)
        assert _auf(pg) == 1
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('.leaflet-control-layers-expanded')", timeout=T)
        # Fenster öffnen schließt das Blatt
        pg.locator("#mfb").click()
        pg.locator("#mbx").click()
        expect(pg.locator(".uimod")).to_have_count(1, timeout=T)
        assert _zu(pg)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_mobil_ohne_blattinhalt_kein_knopf(pw, app, clean):
    """Sind alle Bedienfelder bis auf den Standort ausgeblendet, gibt es kein leeres Blatt."""
    _api(app, "karte", "PUT", {"hidden": ["jahr", "sport", "stil", "ebenen", "ausschnitt"]})
    pg = _browser(pw, app, devs=None, width=390, height=844)
    try:
        pg.goto(f"{app}/#/map", timeout=TL)
        pg.wait_for_function("() => !!document.querySelector('#kax #bigmap') && !!document.getElementById('mfb')", timeout=TL)
        quiet(pg, 3000, 500)
        expect(pg.locator("#mfb")).to_be_hidden(timeout=T)
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  „Touren im Ausschnitt“ nur einmal  ------------------------------------------------------------------

def test_ausschnitt_nur_einmal(pw, app, clean):
    pg = _karte(pw, app)
    try:
        expect(pg.locator("#mbx")).to_be_visible(timeout=T)                              # ohne Baustein: der Knopf
        assert pg.locator(".kalist, #kax .slcell [data-wtype=kliste]").count() == 0
    finally:
        pg.browser_.close()
    _api(app, "karte", "PUT", {"widgets": [{"id": "wk1", "type": "kliste", "cfg": {}}], "order": ["karte", "wk1", "jahr", "sport", "stil", "ebenen", "standort", "ausschnitt"], "w": {"wk1": "drittel", "karte": "zweidrittel"}})
    pg = _karte(pw, app)
    try:
        expect(pg.locator("#mbx")).to_be_hidden(timeout=T)                               # mit Baustein „Touren im Kartenausschnitt“: nur die seitliche Liste
        expect(pg.locator("#kax .kalist, #kax .slnote").first).to_be_visible(timeout=T)
        assert pg.locator("#kap-ausschnitt").evaluate("e => getComputedStyle(e).display") == "none"
        assert pg.evaluate("() => document.querySelectorAll('.uimod').length") == 0
        # im Bearbeitungsmodus bleibt das Bedienfeld als Block erreichbar (man kann es ein- und ausblenden)
        pg.locator("#slopen").click()
        expect(pg.locator("#kap-ausschnitt")).to_be_visible(timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Sprachen  ------------------------------------------------------------------

@pytest.mark.parametrize("lang,mein,filt", [("en", "My location", "Filters & layers"), ("fr", "Ma position", "Filtres et couches"), ("es", "Mi ubicación", "Filtros y capas")])
def test_texte_in_vier_sprachen(pw, app, clean, lang, mein, filt):
    pg = _karte(pw, app, lang=lang, width=390, height=844)
    try:
        assert pg.locator("#mfb").inner_text().strip() == filt
        assert pg.locator("#mloc").get_attribute("aria-label") == mein
        pg.locator("#mfb").click()
        expect(pg.locator(".mapui.mfo")).to_have_count(1, timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
