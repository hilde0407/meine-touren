"""3.30.0 – Zepp-Import auf der Übersicht (Browser, Chromium): Baustein „zeppimport“ im Standard-Layout und im Katalog, Start per Knopf, Fortschritt, Ergebnis des letzten Laufs,
Fehlermeldungen, fehlender Zugang, kein Doppelstart, Betrachter, 390 px hell und dunkel. Der Server läuft echt, aber Zepp wird NIE kontaktiert: /api/jobs, /api/jobs/export und
/api/zepp-status werden im Browser abgefangen (page.route). Wettlauf-Regel: auf den Zustand warten (expect mit Wiederholung, wait_for_function mit Pfeilfunktion), nie nur schlafen."""
import json
import time

import pytest

from tests.test_statistik_ui import _api, _browser, _shot, app, clean, pw, T  # noqa: F401
from tests.test_tourseite_ui import CONTRAST, _settled

expect = pytest.importorskip("playwright.sync_api").expect
LABEL = "Zepp-Import (ohne Upload)"
TS = int(time.time()) - 90


def _job(**kw):
    return {"running": None, "started": None, "finished": None, "ok": None, "progress": "", "done": None, "total": None, "log": [], **kw}


def _last(**kw):
    return {"ts": TS, "start": TS - 20, "ok": True, "gesamt": 40, "neu": 3, "gps": 3, "ohne_gps": 0, "uebernommen": 2, "fehler": 0, **kw}


class Fake:
    """Abgefangene Server-Antworten; posts zählt die Startversuche, tours die Abrufe von /api/tours (Neuladen nach dem Lauf)."""

    def __init__(self, conf=True, last=None, job=None):
        self.conf, self.last, self.job = conf, last, job or _job()
        self.posts, self.tours, self.script, self.conflict = 0, 0, [], False

    def status(self):
        return {"konfiguriert": self.conf, "letzter": self.last}


def _page(pw, url, fake, width=1280, height=900, scheme="light", dpr=1, layout=None, viewer=False):
    if layout is not None:
        _api(url, "uebersicht", "PUT", layout)
    pg = _browser(pw, url, width=width, height=height, scheme=scheme, dpr=dpr, devs=None)

    def jobs(r):
        if fake.script:
            fake.job = fake.script.pop(0)
        r.fulfill(json=fake.job)

    def export(r):
        fake.posts += 1
        if fake.conflict:
            return r.fulfill(status=409, body=json.dumps({"detail": "Es läuft bereits ein Job"}), headers={"content-type": "application/json"})
        fake.job = _job(running=LABEL, started=time.time())
        r.fulfill(json={"started": LABEL})

    def tours(r):
        fake.tours += 1
        r.continue_()

    pg.route("**/api/jobs", jobs)
    pg.route("**/api/jobs/export", export)
    pg.route("**/api/zepp-status", lambda r: r.fulfill(json=fake.status()))
    pg.route("**/api/tours", tours)
    if viewer:
        def me(r):
            d = r.fetch().json()
            d["user"] = {**(d.get("user") or {}), "uid": "v1", "name": "oma", "role": "viewer"}
            r.fulfill(json=d)
        pg.route("**/api/me", me)
    pg.goto(f"{url}/#/dash")
    return pg


def _ready(pg):
    pg.wait_for_selector("#tlw-zepp", state="attached", timeout=30000)


def test_standard_layout_zeigt_knopf_und_startet_den_import(pw, app, clean):
    fake = Fake(last=_last(uebernommen=0, neu=0, gps=0))
    pg = _page(pw, app, fake)
    try:
        _ready(pg)
        card = pg.locator("#tlw-zepp")
        assert card.locator("summary").inner_text().startswith("Zepp-Import")
        btn = card.locator("button.zpb")
        expect(btn).to_contain_text("Zepp-Import starten", timeout=T)
        assert btn.bounding_box()["height"] >= 48
        expect(card.locator(".zpt")).to_contain_text("Letzter Lauf:", timeout=T)
        expect(card.locator(".zpt")).to_contain_text("Keine neuen Trainings.", timeout=T)
        before = fake.tours
        fake.script = [_job(running=LABEL, progress="Export 1/5", done=1, total=5), _job(running=LABEL, progress="Export 3/5", done=2, total=5)]
        btn.click()
        expect(btn).to_contain_text("Import läuft", timeout=T)
        assert btn.is_disabled() and fake.posts == 1
        btn.click(force=True)                                           # kein Doppelstart: gesperrt, es geht kein zweiter Aufruf an den Server
        expect(card.locator(".zpt")).to_contain_text("Training 3 von 5", timeout=T)
        assert fake.posts == 1 and card.locator(".tlk").inner_text().strip() == "läuft"
        # Lauf endet erfolgreich: Ergebnis erscheint, die Touren werden neu geladen
        fake.last = _last()
        fake.script = [_job(finished=time.time(), ok=True)]
        expect(card.locator(".zpt")).to_contain_text("3 neue Trainings gefunden", timeout=T)
        expect(card.locator(".zpt")).to_contain_text("2 als Tour übernommen", timeout=T)
        expect(card.locator("button.zpb")).to_be_enabled(timeout=T)
        assert fake.tours > before and fake.posts == 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_laeuft_schon_beim_laden_und_anderer_job_sperrt(pw, app, clean):
    fake = Fake(job=_job(running=LABEL, progress="Export 2/9", done=1, total=9))
    pg = _page(pw, app, fake)
    try:
        _ready(pg)
        card = pg.locator("#tlw-zepp")
        expect(card.locator("button.zpb")).to_be_disabled(timeout=T)
        expect(card.locator(".zpt")).to_contain_text("Training 2 von 9", timeout=T)
        assert card.locator(".zpt svg.slbr").count() == 1
        fake.job = _job(running="Fotos indizieren")                      # ein anderer Job: Knopf gesperrt, Hinweis nennt ihn
        fake.script = []
        pg.reload()
        _ready(pg)
        expect(pg.locator("#tlw-zepp .zpt")).to_contain_text("Es läuft gerade ein anderer Vorgang: Fotos indizieren", timeout=T)
        expect(pg.locator("#tlw-zepp button.zpb")).to_be_disabled(timeout=T)
        pg.locator("#tlw-zepp button.zpb").click(force=True)
        assert fake.posts == 0
    finally:
        pg.browser_.close()


def test_409_vom_server_zeigt_verstaendliche_meldung(pw, app, clean):
    fake = Fake()
    fake.conflict = True
    pg = _page(pw, app, fake)
    try:
        _ready(pg)
        expect(pg.locator("#tlw-zepp .zpt")).to_contain_text("Noch kein Import gestartet.", timeout=T)
        pg.locator("#tlw-zepp button.zpb").click()
        expect(pg.locator("#tlw-zepp .zpt")).to_contain_text("Der Import konnte nicht gestartet werden:", timeout=T)
        expect(pg.locator("#tlw-zepp button.zpb")).to_be_enabled(timeout=T)
        assert fake.posts == 1
    finally:
        pg.browser_.close()


def test_ohne_zugang_zeigt_einrichten_statt_start(pw, app, clean):
    fake = Fake(conf=False)
    pg = _page(pw, app, fake)
    try:
        _ready(pg)
        card = pg.locator("#tlw-zepp")
        expect(card.locator("a.zpb")).to_have_text("Zepp einrichten", timeout=T)
        assert card.locator("a.zpb").get_attribute("href") == "#/admin?tab=quellen" and card.locator("button.zpb").count() == 0
        expect(card.locator(".zpt")).to_contain_text("fehlt noch der Zepp-Zugang", timeout=T)
        assert card.locator("a.zpb").bounding_box()["height"] >= 48 and fake.posts == 0
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("code,text", [("kein_zugang", "Der Zepp-Zugang fehlt."), ("anmeldung", "Zepp hat die Anmeldung abgelehnt"), ("netz", "Zepp war nicht erreichbar"), ("sonst", "Meldung: Seltsamer Fehler")])
def test_fehler_des_letzten_laufs_verstaendlich(pw, app, clean, code, text):
    fake = Fake(last={"ts": TS, "start": TS - 5, "ok": False, "fehler": "Seltsamer Fehler", "code": code})
    pg = _page(pw, app, fake)
    try:
        _ready(pg)
        z = pg.locator("#tlw-zepp .zpt")
        expect(z).to_contain_text("ist fehlgeschlagen", timeout=T)
        expect(z).to_contain_text(text, timeout=T)
        assert z.locator("a[href='#/admin?tab=quellen']").count() == 1 and pg.locator("#tlw-zepp .tlk").inner_text().strip() == "Fehler"
    finally:
        pg.browser_.close()


def test_einklappbar_und_gespeichertes_layout_bleibt_unveraendert(pw, app, clean):
    saved = {"v": 1, "order": ["aufmacher", "jahr", "zuletzt"], "hidden": ["tag"]}
    fake = Fake()
    pg = _page(pw, app, fake, layout=saved)
    try:
        _ready(pg)
        d = pg.locator("#tlw-zepp details").first
        assert d.evaluate("e => e.open")
        d.locator("> summary").click()
        pg.wait_for_function("() => !document.querySelector('#tlw-zepp details').open", timeout=T)
        d.locator("> summary").click()
        pg.wait_for_function("() => document.querySelector('#tlw-zepp details').open", timeout=T)
        # steht gleich hinter „Dein Jahr“; das gespeicherte Dokument wurde nicht verändert
        order = pg.evaluate("() => [...document.querySelectorAll('main.home > *')].map(e => e.id).filter(Boolean)")
        assert order.index("tlw-zepp") == order.index("hyear") + 1, order
        assert _api(app, "uebersicht")["layout"] == saved
    finally:
        pg.browser_.close()


def test_katalog_kategorie_touren_holen(pw, app, clean):
    from tests.test_bausteine_ui import _catalog, _edit
    fake = Fake()
    pg = _page(pw, app, fake)
    try:
        _ready(pg)
        _edit(pg)
        _catalog(pg)
        card = pg.locator('.slcard:has([data-add="zeppimport"])')
        assert card.get_attribute("data-cat") == "quellen" and card.locator("h3").inner_text() == "Zepp-Import"
        assert "Touren holen" in pg.locator(".slcath:visible").all_inner_texts()
        assert card.locator(".slpv").inner_html().strip() and card.locator("p").inner_text().strip()
        btn = card.locator("[data-add]")                                 # steht schon als Standard-Abschnitt auf der Seite: nicht noch einmal
        assert btn.is_disabled() and btn.inner_text() == "Steht schon auf der Seite"
    finally:
        pg.browser_.close()


def test_katalog_fuegt_baustein_hinzu_wenn_standard_ausgeblendet(pw, app, clean):
    from tests.test_bausteine_ui import _catalog, _edit
    fake = Fake()
    pg = _page(pw, app, fake, layout={"v": 1, "hidden": ["zepp"]})
    try:
        pg.wait_for_selector("#slopen", state="visible", timeout=30000)
        _edit(pg)
        _catalog(pg)
        pg.locator('[data-add="zeppimport"]').click()
        pg.wait_for_selector('[data-wtype="zeppimport"] button.zpb', timeout=T)
        pg.wait_for_function("() => { const s = document.getElementById('slsaved'); return !!s && s.textContent.trim() === 'Gespeichert'; }", timeout=T)
        assert [x["type"] for x in _api(app, "uebersicht")["layout"]["widgets"]] == ["zeppimport"]
        _catalog(pg)
        assert pg.locator('[data-add="zeppimport"]').is_disabled()
    finally:
        pg.browser_.close()


def test_betrachter_sieht_den_baustein_nicht(pw, app, clean):
    fake = Fake()
    pg = _page(pw, app, fake, viewer=True)
    try:
        pg.wait_for_selector("#tlw-zepp", state="attached", timeout=30000)
        pg.wait_for_function("() => document.getElementById('tlw-zepp').dataset.hn === 'aus'", timeout=T)
        assert not pg.locator("#tlw-zepp").is_visible() and pg.locator("#tlw-zepp button").count() == 0
        assert fake.posts == 0
    finally:
        pg.browser_.close()


def test_nur_auf_der_uebersicht_waehlbar(pw, app, clean):
    pg = _browser(pw, app, width=1280, height=900, scheme="light", dpr=1, devs=None)
    try:
        pg.goto(f"{app}/#/dash")
        pg.wait_for_function("() => typeof SL_WT === 'object' && !!SL_WT.zeppimport", timeout=30000)
        assert pg.evaluate("() => SL_WT.zeppimport.seiten.join()") == "uebersicht" and pg.evaluate("() => SL_WT.zeppimport.cat") == "quellen"
        assert pg.evaluate("() => SL_CATS.some(([k, l]) => k === 'quellen' && l === 'Touren holen')")
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("width,scheme", [(1280, "light"), (390, "light"), (390, "dark")])
def test_390_ohne_ueberlauf_kontrast_und_touchziel(pw, app, clean, width, scheme):
    fake = Fake(last=_last(ohne_gps=1, fehler=1))
    pg = _page(pw, app, fake, width=width, height=844 if width == 390 else 900, scheme=scheme, dpr=2 if width == 390 else 1)
    try:
        _ready(pg)
        expect(pg.locator("#tlw-zepp .zpt")).to_contain_text("Letzter Lauf:", timeout=T)
        _settled(pg)
        assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
        assert pg.evaluate("() => { const w = document.getElementById('tlw-zepp'); return w.scrollWidth <= w.clientWidth + 1; }")
        b = pg.locator("#tlw-zepp button.zpb").bounding_box()
        c = pg.locator("#tlw-zepp .zpi").bounding_box()
        assert b["height"] >= 48 and b["width"] >= 44
        if width == 390:
            assert b["width"] >= c["width"] - 2, (b, c)                  # volle Breite des Bausteins
        r = pg.evaluate(CONTRAST, ["#tlw-zepp .zpb", "#tlw-zepp .zpm", "#tlw-zepp .zpl li", "#tlw-zepp .zpok"])
        low = {k: round(v, 2) for k, v in r.items() if v < 4.5}
        assert len(r) >= 3 and not low, f"{scheme}: Kontrast unter 4,5:1: {low}"
        _shot(pg, f"zepp-uebersicht-{width}-{scheme}.png")
        # Fehlerfall und Lauf-Zustand ebenfalls kontrastreich
        fake.last = {"ts": TS, "ok": False, "fehler": "x", "code": "anmeldung"}
        pg.reload()
        _ready(pg)
        expect(pg.locator("#tlw-zepp .zpbad")).to_be_visible(timeout=T)
        _settled(pg)
        r = pg.evaluate(CONTRAST, ["#tlw-zepp .zpbad", "#tlw-zepp .zpt a"])
        assert len(r) == 2 and all(v >= 4.5 for v in r.values()), r
        _shot(pg, f"zepp-uebersicht-fehler-{width}-{scheme}.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_handy_schnellknopf_in_der_kopfzeile_ohne_scrollen_und_startet(pw, app, clean):
    fake = Fake()
    pg = _page(pw, app, fake, width=390, height=844, dpr=2)
    try:
        _ready(pg)
        q = pg.locator("#slzepp")
        expect(q).to_be_visible(timeout=T)
        expect(q).to_contain_text("Zepp", timeout=T)
        _settled(pg)
        b = q.bounding_box()
        assert pg.evaluate("() => scrollY") == 0 and b["y"] + b["height"] <= 400 and b["height"] >= 48 and b["width"] >= 300, b       # ganz oben, volle Breite, Touch-Ziel
        _shot(pg, "zepp-schnellknopf-390.png", full=False)
        fake.script = [_job(running=LABEL, done=0, total=4)]
        q.click()
        expect(q).to_contain_text("Zepp läuft", timeout=T)
        assert q.is_disabled() and fake.posts == 1
        expect(pg.locator("#tlw-zepp button.zpb")).to_contain_text("Import läuft", timeout=T)        # die Karte zeigt denselben Lauf
        fake.last = _last()
        fake.script = [_job(finished=time.time(), ok=True)]
        expect(q).not_to_contain_text("läuft", timeout=T)
        assert fake.posts == 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_schnellknopf_ohne_zugang_fuehrt_zur_einrichtung_betrachter_ohne(pw, app, clean):
    fake = Fake(conf=False)
    pg = _page(pw, app, fake)
    try:
        _ready(pg)
        expect(pg.locator("#slzepp")).to_contain_text("Zepp einrichten", timeout=T)
        pg.locator("#slzepp").click()
        pg.wait_for_function("() => location.hash.startsWith('#/admin')", timeout=T)
        assert fake.posts == 0
    finally:
        pg.browser_.close()
    pg = _page(pw, app, Fake(), viewer=True)
    try:
        pg.wait_for_selector("main.home", timeout=30000)
        pg.wait_for_function("() => document.getElementById('tlw-zepp') && document.getElementById('tlw-zepp').dataset.hn === 'aus'", timeout=T)
        assert pg.locator("#slzepp").count() == 0
    finally:
        pg.browser_.close()
