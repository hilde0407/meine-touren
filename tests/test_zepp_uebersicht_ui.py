"""3.30.0/3.31.0 – Touren holen je nach Uhr auf der Übersicht (Browser, Chromium); 3.31.0: Marke im Knopf (Zepp, Garmin, Suunto), Menü bei mehreren Quellen, „Alle holen“ nacheinander,
Einrichten bzw. Dateihinweis ohne Konto, Baustein „Touren-Knopf“, Schalter des Schnell-Knopfs in „Seite anpassen“. Zepp-Import auf der Übersicht (Browser, Chromium): Baustein „zeppimport“ im Standard-Layout und im Katalog, Start per Knopf, Fortschritt, Ergebnis des letzten Laufs,
Fehlermeldungen, fehlender Zugang, kein Doppelstart, Betrachter, 390 px hell und dunkel. Der Server läuft echt, aber Zepp wird NIE kontaktiert: /api/jobs, /api/jobs/export und
/api/import-quellen werden im Browser abgefangen (page.route). Wettlauf-Regel: auf den Zustand warten (expect mit Wiederholung, wait_for_function mit Pfeilfunktion), nie nur schlafen."""
import json
import time

import pytest

from tests.helpers_ui import quiet
from tests.test_statistik_ui import _api, _browser, _shot, app, clean, pw, T  # noqa: F401
from tests.test_tourseite_ui import CONTRAST, _settled

expect = pytest.importorskip("playwright.sync_api").expect
LABEL = "Zepp-Import (ohne Upload)"
TS = int(time.time()) - 90


def _job(**kw):
    return {"running": None, "started": None, "finished": None, "ok": None, "progress": "", "done": None, "total": None, "log": [], **kw}


def _last(**kw):
    return {"ts": TS, "start": TS - 20, "ok": True, "gesamt": 40, "neu": 3, "gps": 3, "ohne_gps": 0, "uebernommen": 2, "fehler": 0, **kw}


JOBL = {"export": LABEL, "garmin-import": "Garmin-Import", "suunto-import": "Suunto-Import"}


class Fake:
    """Abgefangene Server-Antworten; posts zählt die Startversuche (keys: in welcher Reihenfolge, welche Quelle), tours die Abrufe von /api/tours (Neuladen nach dem Lauf).
    conf/garmin/suunto = Konto verbunden; geraete = Marken aus „Meine Geräte“ ohne Konto (Liste {kind, label, konto})."""

    def __init__(self, conf=True, last=None, job=None, garmin=False, suunto=False, geraete=None, glast=None, slast=None):
        self.conf, self.last, self.job, self.garmin, self.suunto, self.geraete, self.glast, self.slast = conf, last, job or _job(), garmin, suunto, geraete or [], glast, slast
        self.posts, self.tours, self.script, self.conflict, self.keys = 0, 0, [], False, []
        self.start_script = []                 # Verlauf, der erst NACH dem Start (POST) abgespielt wird: ein Abruf von /api/jobs vor dem Klick (Hintergrundabfrage der Seite) verbraucht ihn nicht

    def status(self):
        run = self.job.get("running")
        return {"quellen": [{"kind": "zepp", "label": "Zepp", "verbunden": self.conf, "laeuft": run == LABEL, "job": "export", "uebernimmt": False, "letzter": self.last},
                            {"kind": "garmin", "label": "Garmin", "verbunden": self.garmin, "laeuft": run == "Garmin-Import", "job": "garmin-import", "uebernimmt": True, "letzter": self.glast},
                            {"kind": "suunto", "label": "Suunto", "verbunden": self.suunto, "laeuft": run == "Suunto-Import", "job": "suunto-import", "uebernimmt": True, "letzter": self.slast}],
                "geraete": self.geraete, "laeuft": run}


def _page(pw, url, fake, width=1280, height=900, scheme="light", dpr=1, layout=None, viewer=False):
    if layout is not None:
        _api(url, "uebersicht", "PUT", layout)
    pg = _browser(pw, url, width=width, height=height, scheme=scheme, dpr=dpr, devs=None)

    def jobs(r):
        if fake.script:
            fake.job = fake.script.pop(0)
        r.fulfill(json=fake.job)

    def export(r):
        key = r.request.url.rsplit("/", 1)[1]
        fake.posts += 1
        fake.keys.append(key)
        if fake.conflict or fake.job.get("running"):                      # wie der Server: ein Lauf zur Zeit
            return r.fulfill(status=409, body=json.dumps({"detail": "Es läuft bereits ein Job"}), headers={"content-type": "application/json"})
        fake.job = _job(running=JOBL[key], started=time.time())
        if fake.start_script:
            fake.script, fake.start_script = list(fake.start_script), []
        r.fulfill(json={"started": JOBL[key]})

    def tours(r):
        fake.tours += 1
        r.continue_()

    pg.route("**/api/jobs", jobs)
    pg.route("**/api/jobs/*", export)
    pg.route("**/api/import-quellen", lambda r: r.fulfill(json=fake.status()))
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
        assert card.locator("summary").inner_text().startswith("Touren holen")
        btn = card.locator("button.zpb")
        expect(btn).to_contain_text("Zepp-Import starten", timeout=T)
        assert btn.bounding_box()["height"] >= 48
        expect(card.locator(".zpt")).to_contain_text("Letzter Lauf:", timeout=T)
        expect(card.locator(".zpt")).to_contain_text("Keine neuen Trainings.", timeout=T)
        before = fake.tours
        fake.start_script = [_job(running=LABEL, progress="Export 1/5", done=1, total=5), _job(running=LABEL, progress="Export 3/5", done=2, total=5)]
        btn.click()
        expect(btn).to_contain_text("Import läuft", timeout=T)
        assert btn.is_disabled() and fake.posts == 1
        pg.evaluate("() => document.querySelector('#tlw-zepp button.zpb').click()")    # kein Doppelstart: gesperrt, es geht kein zweiter Aufruf an den Server (per Skript: der Baustein zeichnet bei jedem Abruf neu, ein Playwright-Klick träfe sonst einen gerade ersetzten Knopf)
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
    fake = Fake(conf=False, geraete=[{"kind": "zepp", "label": "Zepp", "konto": True}])
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
    fake = Fake(last={"ts": TS, "start": TS - 5, "ok": False, "meldung": "Seltsamer Fehler", "code": code})
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
        assert card.get_attribute("data-cat") == "quellen" and card.locator("h3").inner_text() == "Touren holen"
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
        fake.last = {"ts": TS, "ok": False, "meldung": "x", "code": "anmeldung"}
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
        nb = pg.evaluate("() => [...document.querySelectorAll('.slopen .btn')].filter(e => e.id !== 'slzepp' && e.offsetParent !== null).map(e => { const r = e.getBoundingClientRect(); return [r.width, r.height, r.y, r.right]; })")
        assert len(nb) == 2, nb
        # 3.44.0: Zepp-Knopf allein in der ersten Zeile, „Seite anpassen“ und „Ansichten“ darunter in EINER Zeile (gleiche y, kein Umbruch), Desktop unverändert
        assert nb[0][2] == nb[1][2] and nb[0][2] >= b["y"] + b["height"] - 1 and nb[1][3] <= 390, (b, nb)
        assert b["x"] < nb[0][3] and abs(nb[0][0] - nb[1][0]) <= 2, (b, nb)
        nb = [(w, h) for w, h, _, _ in nb]
        # ganz oben ohne Scrollen; 3.43.0: gleich hoch wie „Seite anpassen“/„Ansichten“ (Touch-Ziel ≥ 44 px), nicht breiter als der breiteste Nachbar, keine volle Breite
        assert pg.evaluate("() => scrollY") == 0 and b["y"] + b["height"] <= 400 and b["height"] >= 44, b
        assert all(abs(h - b["height"]) <= 1 for _, h in nb) and b["width"] <= max(w for w, _ in nb) + 1 and b["width"] < 300, (b, nb)
        _shot(pg, "zepp-schnellknopf-390.png", full=False)
        fake.start_script = [_job(running=LABEL, done=0, total=4)]
        q.click()
        expect(q).to_contain_text("Zepp-Abruf läuft", timeout=T)
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
    fake = Fake(conf=False, geraete=[{"kind": "zepp", "label": "Zepp", "konto": True}])
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


# ----------------------------------------------------------------------------------------------------------------- 3.31.0: je nach Uhr
def _glast(**kw):
    return {"ts": TS, "ok": True, "neu": 2, "uebernommen": 2, "dup": 1, "ohne_gps": 0, "fehler": 0, "gps": 2, **kw}


def _gespeichert(pg):
    pg.wait_for_function("() => { const s = document.getElementById('slsaved'); return !!s && s.textContent.trim() === 'Gespeichert'; }", timeout=T)


def test_eine_quelle_garmin_beschriftung_start_und_ergebnis(pw, app, clean):
    fake = Fake(conf=False, garmin=True, glast=_glast())
    pg = _page(pw, app, fake)
    try:
        _ready(pg)
        card = pg.locator("#tlw-zepp")
        btn = card.locator("button.zpb")
        expect(btn).to_contain_text("Garmin-Import starten", timeout=T)
        expect(pg.locator("#slzepp")).to_contain_text("Garmin", timeout=T)
        assert "Zepp" not in pg.locator("#slzepp").inner_text() and pg.locator("#slzepp").get_attribute("aria-haspopup") is None
        expect(card.locator(".zpt")).to_contain_text("2 neue Touren übernommen", timeout=T)
        expect(card.locator(".zpt")).to_contain_text("1 schon vorhanden", timeout=T)
        fake.start_script = [_job(running="Garmin-Import", done=1, total=5)]
        btn.click()
        assert fake.keys == ["garmin-import"]                                             # der Garmin-Job, nicht der Zepp-Job
        expect(card.locator(".zpt")).to_contain_text("Tour 2 von 5", timeout=T)
        expect(pg.locator("#slzepp")).to_contain_text("Garmin-Abruf läuft", timeout=T)
        btn.click(force=True)
        assert fake.posts == 1
        fake.glast = _glast(neu=0, uebernommen=0, dup=0)
        fake.script = [_job(finished=time.time(), ok=True)]
        expect(card.locator(".zpt")).to_contain_text("Keine neuen Touren.", timeout=T)
        expect(card.locator("button.zpb")).to_be_enabled(timeout=T)
    finally:
        pg.browser_.close()


def test_eine_quelle_suunto_fehler_verstaendlich(pw, app, clean):
    fake = Fake(conf=False, suunto=True, slast={"ts": TS, "ok": False, "meldung": "kaputt", "code": "anmeldung"})
    pg = _page(pw, app, fake)
    try:
        _ready(pg)
        card = pg.locator("#tlw-zepp")
        expect(card.locator("button.zpb")).to_contain_text("Suunto-Import starten", timeout=T)
        expect(card.locator(".zpt")).to_contain_text("Suunto hat die Anmeldung abgelehnt", timeout=T)
        expect(pg.locator("#slzepp")).to_contain_text("Suunto (Fehler)", timeout=T)
    finally:
        pg.browser_.close()


def test_mehrere_quellen_zeilen_alle_holen_nacheinander(pw, app, clean):
    fake = Fake(garmin=True, suunto=True, last=_last(), glast=_glast())
    pg = _page(pw, app, fake)
    try:
        _ready(pg)
        card = pg.locator("#tlw-zepp")
        expect(card.locator(".zpsrc")).to_have_count(3, timeout=T)
        assert card.locator(".zpsrc .zph").all_inner_texts() == ["Zepp", "Garmin", "Suunto"]
        expect(card.locator('button.zpb[data-k="garmin"]')).to_contain_text("Garmin-Import starten", timeout=T)
        expect(card.locator(".zpall")).to_contain_text("Alle holen", timeout=T)
        assert card.locator(".zpall").bounding_box()["height"] >= 44
        card.locator(".zpall").click()
        expect(card.locator('button.zpb[data-k="zepp"]')).to_contain_text("Import läuft", timeout=T)
        assert fake.keys == ["export"] and all(b.is_disabled() for b in card.locator("button.zpb").all()) and card.locator(".zpall").is_disabled()
        fake.job = _job(finished=time.time(), ok=True)                      # Zepp fertig: erst jetzt die nächste Quelle, nie zwei zugleich
        expect(card.locator('button.zpb[data-k="garmin"]')).to_contain_text("Import läuft", timeout=T)
        assert fake.keys == ["export", "garmin-import"]
        fake.job = _job(finished=time.time(), ok=True)
        expect(card.locator('button.zpb[data-k="suunto"]')).to_contain_text("Import läuft", timeout=T)
        assert fake.keys == ["export", "garmin-import", "suunto-import"] and fake.posts == 3
        fake.job = _job(finished=time.time(), ok=True)
        expect(card.locator(".zpall")).to_be_enabled(timeout=T)
        assert fake.keys == ["export", "garmin-import", "suunto-import"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_mehrere_quellen_schnellknopf_menue(pw, app, clean):
    fake = Fake(garmin=True)
    pg = _page(pw, app, fake)
    try:
        _ready(pg)
        q = pg.locator("#slzepp")
        expect(q).to_contain_text("Touren holen", timeout=T)
        expect(q).to_have_attribute("aria-haspopup", "menu", timeout=T)           # der Knopf wird erst mit der Antwort von /api/import-quellen zum Menü-Knopf (vorher: einfacher Knopf)
        assert q.get_attribute("aria-expanded") == "false"
        menu = pg.locator("#slzmenu")
        assert menu.is_hidden()
        q.click()
        expect(menu).to_be_visible(timeout=T)
        assert q.get_attribute("aria-expanded") == "true"
        assert menu.locator("[role=menuitem]").all_inner_texts() == ["Zepp-Import starten", "Garmin-Import starten", "Alle holen"]
        assert all(i.bounding_box()["height"] >= 44 for i in menu.locator("[role=menuitem]").all())
        pg.wait_for_function("() => document.activeElement && document.activeElement.classList.contains('zpmi')", timeout=T)       # Fokus im Menü
        pg.keyboard.press("ArrowDown")
        pg.wait_for_function("() => document.activeElement.dataset.k === 'garmin'", timeout=T)
        pg.keyboard.press("Escape")                                          # Escape schließt und gibt den Fokus zurück
        expect(menu).to_be_hidden(timeout=T)
        pg.wait_for_function("() => document.activeElement && document.activeElement.id === 'slzepp'", timeout=T)
        q.click()
        expect(menu).to_be_visible(timeout=T)
        quiet(pg, 3000)
        pg.mouse.click(5, 600)                                               # Klick außerhalb schließt
        expect(menu).to_be_hidden(timeout=T)
        q.click()
        expect(menu).to_be_visible(timeout=T)
        pg.wait_for_function("() => document.activeElement && document.activeElement.classList.contains('zpmi')", timeout=T)       # Fokus im Menü, erst dann Tasten (sonst verpufft der Pfeil)
        pg.keyboard.press("ArrowDown")
        pg.wait_for_function("() => document.activeElement.dataset.k === 'garmin'", timeout=T)
        pg.keyboard.press("Enter")                                           # per Tastatur: Garmin starten
        expect(menu).to_be_hidden(timeout=T)
        expect(q).to_contain_text("Garmin-Abruf läuft", timeout=T)
        assert fake.keys == ["garmin-import"] and q.is_disabled()
    finally:
        pg.browser_.close()


def test_menue_alle_holen_und_handy_390(pw, app, clean):
    fake = Fake(suunto=True)
    pg = _page(pw, app, fake, width=390, height=844, dpr=2)
    try:
        _ready(pg)
        q = pg.locator("#slzepp")
        expect(q).to_contain_text("Touren holen", timeout=T)
        expect(q).to_have_attribute("aria-haspopup", "menu", timeout=T)           # erst Menü-Knopf, dann klicken (vorher startet der Klick einen Import)
        q.click()
        menu = pg.locator("#slzmenu")
        expect(menu).to_be_visible(timeout=T)
        _settled(pg)
        bm, bq = menu.bounding_box(), q.bounding_box()
        assert bm["x"] >= 0 and bm["x"] + bm["width"] <= 390 and bm["y"] >= bq["y"] + bq["height"] - 1, (bm, bq)
        assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
        r = pg.evaluate(CONTRAST, ["#slzmenu .zpmi"])
        assert r and all(v >= 4.5 for v in r.values()), r
        _shot(pg, "touren-holen-menue-390.png", full=False)
        menu.locator('[data-k="alle"]').click()
        expect(q).to_contain_text("Zepp-Abruf läuft", timeout=T)
        assert fake.keys == ["export"]
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("geraete,btn,text", [
    ([{"kind": "garmin", "label": "Garmin", "konto": True}], "Garmin einrichten", "Für Garmin fehlt noch die Verbindung"),
    ([{"kind": "suunto", "label": "Suunto", "konto": True}, {"kind": "garmin", "label": "Garmin", "konto": True}], "Touren holen einrichten", "Verbinde in der Verwaltung: Suunto, Garmin"),
    ([], "Touren holen einrichten", "Noch keine Quelle eingerichtet."),
])
def test_ohne_konto_einrichten_je_marke(pw, app, clean, geraete, btn, text):
    fake = Fake(conf=False, geraete=geraete)
    pg = _page(pw, app, fake)
    try:
        _ready(pg)
        card = pg.locator("#tlw-zepp")
        expect(card.locator("a.zpb")).to_have_text(btn, timeout=T)
        assert card.locator("a.zpb").get_attribute("href") == "#/admin?tab=quellen" and card.locator("button.zpb").count() == 0
        expect(card.locator(".zpt")).to_contain_text(text, timeout=T)
        expect(pg.locator("#slzepp")).to_contain_text(btn, timeout=T)
        pg.locator("#slzepp").click()
        pg.wait_for_function("() => location.hash.startsWith('#/admin')", timeout=T)
        assert fake.posts == 0
    finally:
        pg.browser_.close()


def test_polar_ohne_konto_hinweis_dateiimport_kein_knopf(pw, app, clean):
    fake = Fake(conf=False, geraete=[{"kind": "polar", "label": "Polar", "konto": False}])
    pg = _page(pw, app, fake)
    try:
        _ready(pg)
        card = pg.locator("#tlw-zepp")
        link = card.locator("a", has_text="Polar: Touren per Datei importieren")
        expect(link).to_have_count(1, timeout=T)
        assert link.get_attribute("href") == "#/admin?tab=quellen" and card.locator(".btn").count() == 0 and card.locator("button").count() == 0       # kein Fantasie-Knopf
        expect(pg.locator("#slzepp")).to_contain_text("Polar: Touren per Datei importieren", timeout=T)
        pg.locator("#slzepp").click()
        pg.wait_for_function("() => location.hash.startsWith('#/admin')", timeout=T)
        assert fake.posts == 0
    finally:
        pg.browser_.close()
    fake = Fake(conf=True, geraete=[{"kind": "polar", "label": "Polar", "konto": False}])           # Konto und Polar-Uhr zugleich: Zepp-Knopf plus Hinweis
    pg = _page(pw, app, fake)
    try:
        _ready(pg)
        expect(pg.locator("#tlw-zepp button.zpb")).to_contain_text("Zepp-Import starten", timeout=T)
        expect(pg.locator("#tlw-zepp")).to_contain_text("Polar: Touren per Datei importieren", timeout=T)
    finally:
        pg.browser_.close()


# ----------------------------------------------------------------------------------------------------------------- Baustein „Touren-Knopf“
def _add_knopf(pg):
    from tests.test_bausteine_ui import _catalog, _edit
    pg.wait_for_selector("#slopen", state="visible", timeout=30000)
    _edit(pg)
    _catalog(pg)
    pg.locator('[data-add="holenknopf"]').click()
    pg.wait_for_selector('[data-wtype="holenknopf"] .zpi', timeout=T)


def test_baustein_touren_knopf_eine_quelle_und_katalog(pw, app, clean):
    fake = Fake(conf=False, garmin=True, glast=_glast())
    pg = _page(pw, app, fake)
    try:
        from tests.test_bausteine_ui import _catalog, _edit
        pg.wait_for_selector("#slopen", state="visible", timeout=30000)
        _edit(pg)
        _catalog(pg)
        card = pg.locator('.slcard:has([data-add="holenknopf"])')
        assert card.get_attribute("data-cat") == "quellen" and card.locator("h3").inner_text() == "Touren-Knopf" and card.locator(".slpv").inner_html().strip()
        assert card.locator("[data-add]").is_enabled()
        pg.locator('[data-add="holenknopf"]').click()
        w = pg.locator('[data-wtype="holenknopf"]')
        btn = w.locator("button.zpb")
        expect(btn).to_contain_text("Garmin-Import starten", timeout=T)
        expect(w.locator(".zpt")).to_contain_text("Letzter Lauf:", timeout=T)
        expect(w.locator(".zpt")).to_contain_text("2 neue Touren übernommen", timeout=T)
        assert w.locator(".zpsrc, .zpall, ul").count() == 0                      # kompakt: nur Knopf und Statuszeile
        assert btn.bounding_box()["height"] >= 44
        fake.start_script = [_job(running="Garmin-Import", done=0, total=3)]
        btn.click()
        assert fake.keys == ["garmin-import"]
        expect(w.locator(".zpt")).to_contain_text("Tour 1 von 3", timeout=T)
        btn.click(force=True)
        assert fake.posts == 1
        _gespeichert(pg)
        assert [x["type"] for x in _api(app, "uebersicht")["layout"]["widgets"]] == ["holenknopf"]
        assert pg.evaluate("() => SL_WT.holenknopf.w") == "drittel" and pg.evaluate("() => SL_WT.holenknopf.ws.join()") == "drittel,halb" and pg.evaluate("() => SL_WT.holenknopf.seiten.join()") == "uebersicht"
    finally:
        pg.browser_.close()


def test_baustein_touren_knopf_mehrere_quellen_menue_und_einrichten(pw, app, clean):
    fake = Fake(garmin=True, last=_last())
    pg = _page(pw, app, fake)
    try:
        _add_knopf(pg)
        w = pg.locator('[data-wtype="holenknopf"]')
        mb = w.locator("button.zpmb")
        expect(mb).to_contain_text("Touren holen", timeout=T)
        expect(mb).to_have_attribute("aria-haspopup", "menu", timeout=T)           # Menü-Knopf erst nach der Antwort von /api/import-quellen
        expect(w.locator(".zpt")).to_contain_text("Letzter Lauf:", timeout=T)
        mb.click()
        menu = w.locator(".zpmenu")
        expect(menu).to_be_visible(timeout=T)
        assert menu.locator("[role=menuitem]").all_inner_texts() == ["Zepp-Import starten", "Garmin-Import starten", "Alle holen"]
        pg.keyboard.press("Escape")
        expect(menu).to_be_hidden(timeout=T)
        mb.click()
        menu.locator('[data-k="garmin"]').click()
        assert fake.keys == ["garmin-import"]
        expect(w.locator("button.zpmb")).to_contain_text("Import läuft", timeout=T)
        assert w.locator("button.zpmb").is_disabled()
        quiet(pg, 3000)                                                      # entprelltes Speichern des Layouts abwarten, bevor die Seite verschwindet
    finally:
        pg.browser_.close()
    _api(app, "uebersicht", "DELETE")                                        # zweiter Teil beginnt ohne den Baustein (sonst „Bereits hinzugefügt“: Zustand aus Teil 1)
    fake = Fake(conf=False, geraete=[{"kind": "garmin", "label": "Garmin", "konto": True}])
    pg = _page(pw, app, fake)
    try:
        _add_knopf(pg)
        expect(pg.locator('[data-wtype="holenknopf"] a.zpb')).to_have_text("Garmin einrichten", timeout=T)
    finally:
        pg.browser_.close()


def test_baustein_touren_knopf_betrachter_unsichtbar(pw, app, clean):
    fake = Fake()
    pg = _page(pw, app, fake, viewer=True)                              # Betrachter bekommen immer das Standard-Layout (ohne den Baustein) – und selbst gebaut bleibt er leer
    try:
        pg.wait_for_selector("main.home", timeout=30000)
        pg.wait_for_function("() => typeof SL_WT === 'object' && !!SL_WT.holenknopf && typeof isViewer === 'function' && isViewer()", timeout=T)
        assert pg.locator('[data-wtype="holenknopf"]').count() == 0
        r = pg.evaluate("() => { const c = document.createElement('section'); c.innerHTML = '<div class=\"tlsb\"></div>'; SL_WT.holenknopf.render(c, c.firstChild, {}); return [c.dataset.hn || '', c.querySelector('button') ? 1 : 0, c.dataset.zk || '']; }")
        assert r == ["aus", 0, ""] and fake.posts == 0
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("width,scheme", [(1280, "light"), (390, "light"), (390, "dark")])
def test_baustein_touren_knopf_390_kontrast(pw, app, clean, width, scheme):
    _api(app, "uebersicht", "PUT", {"v": 1, "widgets": [{"id": "hk1", "type": "holenknopf", "cfg": {}}], "w": {"hk1": "halb"}})
    fake = Fake(garmin=True, last=_last(), glast=_glast())
    pg = _page(pw, app, fake, width=width, height=844 if width == 390 else 900, scheme=scheme, dpr=2 if width == 390 else 1)
    try:
        pg.wait_for_selector('[data-wtype="holenknopf"] .zpi', timeout=30000)
        expect(pg.locator('[data-wtype="holenknopf"] .zpt')).to_contain_text("Garmin", timeout=T)
        _settled(pg)
        assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
        assert pg.evaluate("() => { const w = document.querySelector('[data-wtype=holenknopf]'); return w.scrollWidth <= w.clientWidth + 1; }")
        r = pg.evaluate(CONTRAST, ['[data-wtype="holenknopf"] .zpb', '[data-wtype="holenknopf"] .zpm'])
        assert len(r) == 2 and all(v >= 4.5 for v in r.values()), r
        pg.locator('[data-wtype="holenknopf"] button.zpmb').click()
        expect(pg.locator('[data-wtype="holenknopf"] .zpmenu')).to_be_visible(timeout=T)
        r = pg.evaluate(CONTRAST, ['[data-wtype="holenknopf"] .zpmi'])
        assert r and all(v >= 4.5 for v in r.values()), r
        _shot(pg, f"touren-knopf-{width}-{scheme}.png", full=False)
    finally:
        pg.browser_.close()


# ----------------------------------------------------------------------------------------------------------------- Schalter „Schnell-Knopf in der Kopfzeile“
def test_schalter_schnellknopf_an_aus_bleibt_nach_reload(pw, app, clean):
    from tests.test_bausteine_ui import _edit
    fake = Fake()
    pg = _page(pw, app, fake)
    try:
        _ready(pg)
        expect(pg.locator("#slzepp")).to_be_visible(timeout=T)                    # Standard: an (bestehende Nutzer sehen weiter den Knopf)
        _edit(pg)
        sw = pg.locator("#slkopfin")
        expect(pg.locator("#slkopf")).to_be_visible(timeout=T)
        assert sw.is_checked() and "Schnell-Knopf zum Touren holen in der Kopfzeile" in pg.locator("#slkopf").inner_text()
        assert pg.locator("#slkopf").bounding_box()["height"] >= 44
        sw.click()
        _gespeichert(pg)
        assert _api(app, "uebersicht")["layout"]["kopf"] == {"holen": False}
        pg.locator("#slbar").get_by_role("button", name="Fertig").click()
        pg.wait_for_function("() => !document.querySelector('.slit')", timeout=T)
        assert pg.locator("#slzepp").count() == 0 and pg.locator("#slzmenu").count() == 0
        assert pg.locator("#tlw-zepp button.zpb").count() == 1                      # der Baustein bleibt
        pg.reload()
        _ready(pg)
        pg.wait_for_selector("#slopen", state="visible", timeout=30000)
        assert pg.locator("#slzepp").count() == 0                                   # bleibt nach Reload aus
        _edit(pg)
        assert not pg.locator("#slkopfin").is_checked()
        pg.locator("#slkopfin").click()                                             # wieder an
        _gespeichert(pg)
        assert "kopf" not in _api(app, "uebersicht")["layout"]                      # Standard wird nicht gespeichert
        pg.locator("#slbar").get_by_role("button", name="Fertig").click()
        expect(pg.locator("#slzepp")).to_be_visible(timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_schalter_gehoert_zur_ansicht(pw, app, clean):
    from tests.test_bausteine_ui import _edit
    def doc(active):
        return {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1}}, {"id": "ruhig", "name": "Ruhig", "layout": {"v": 1, "kopf": {"holen": False}}}], "active": active, "rules": {}}
    _api(app, "uebersicht", "PUT", doc("ruhig"))
    pg = _page(pw, app, Fake())
    try:
        pg.wait_for_selector("#slopen", state="visible", timeout=30000)
        _ready(pg)
        assert pg.locator("#slzepp").count() == 0                                   # aktive Ansicht „Ruhig“: ohne Schnell-Knopf
        _edit(pg)
        assert not pg.locator("#slkopfin").is_checked()
        assert pg.evaluate("() => slHolenOn()") is False
    finally:
        pg.browser_.close()
    _api(app, "uebersicht", "PUT", doc("standard"))                                 # andere Ansicht aktiv: Knopf da
    pg = _page(pw, app, Fake())
    try:
        pg.wait_for_selector("#slopen", state="visible", timeout=30000)
        expect(pg.locator("#slzepp")).to_be_visible(timeout=T)
        _edit(pg)
        assert pg.locator("#slkopfin").is_checked()
    finally:
        pg.browser_.close()


def test_viewer_sieht_den_schalter_nie(pw, app, clean):
    pg = _page(pw, app, Fake(), viewer=True)
    try:
        pg.wait_for_selector("main.home", timeout=30000)
        assert pg.locator("#slkopf").count() == 0 and pg.locator("#slzepp").count() == 0 and pg.locator("#slopen").count() == 0
    finally:
        pg.browser_.close()
