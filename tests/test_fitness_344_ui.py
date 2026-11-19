"""3.44.0 Fitness-Einordnung (Baustein „fitness“, nur im Katalog, nicht auf den Standardseiten): Katalog, Eingabe des Geburtsjahrs (im Baustein und im Dialog), Anzeige mit Gesamtwert, drei Balken,
Alter, Info und Hinweis, Zustände (ohne Geburtsjahr, keine Touren, keine aktuellen Touren, zu wenig Daten, Fehler), 1280/390 px hell/dunkel, de/en/fr/es.
Wettlauf-Regel: auf Zustände warten (expect/wait_for_function mit 15 s). Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import json
import re
import urllib.request

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.helpers_ui import quiet, settled, set_lang  # noqa: E402
from tests.test_seitenlayout_ui import T, _api, _browser, _edit, pw  # noqa: E402,F401
from tests.test_statistik_ui import TL, app  # noqa: E402,F401
from tests.test_tourseite_ui import CONTRAST, _shot  # noqa: E402

CARD = "#tlw-wf"
WIDGET = {"widgets": [{"id": "wf", "type": "fitness", "cfg": {}}]}
KEYS = ("tour-haupt", "tour-auswertung", "uebersicht", "statistik")


def _req(url, path, method="GET", body=None):
    r = urllib.request.Request(url + path, method=method, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=10) as x:
        return json.loads(x.read() or b"{}")


@pytest.fixture(autouse=True)
def clean(app):
    for k in KEYS:
        _api(app, k, "DELETE")
    _req(app, "/api/fitness/geburtsjahr", "DELETE")
    yield
    _req(app, "/api/fitness/geburtsjahr", "DELETE")


def _stats(pw, app, widget=True, route=None, **kw):
    if widget:
        _api(app, "statistik", "PUT", WIDGET)
    pg = _browser(pw, app, devs=None, **kw)
    if route is not None:
        pg.route("**/api/fitness", route)
    pg.goto(f"{app}/#/stats", timeout=TL)
    pg.wait_for_selector("#stx #tls-kpi", state="attached", timeout=TL)
    pg.wait_for_function("() => !!document.querySelector('#slopen') && typeof SL === 'object' && !!SL.view.statistik", timeout=T)
    return pg


def _fake(d, status=200):
    return lambda r: r.fulfill(status=status, json=d)


def _ok(**kw):
    d = {"status": "ok", "geburtsjahr": 1974, "alter": 52, "wochen": 12, "touren": 20, "gesamt": 72, "einordnung": "gut", "trend": "up", "vorher": 60,
         "umfang": {"wert": 85, "min_woche": 223.5, "who_min": 150, "who_max": 300, "ohne_dauer": 0},
         "regel": {"wert": 92, "wochen_aktiv": 11, "wochen": 12, "touren": 20},
         "intensitaet": {"wert": 40, "quelle": "puls", "mittel_bpm": 118, "mittel_pct": 69, "zone_pct": 40, "hfmax": 171, "sekunden": 40000}}
    d.update(kw)
    return d


def _jahr(pg, v, btn="Speichern"):
    f = pg.locator(CARD + " input#ftj0")
    f.fill(str(v))
    pg.locator(CARD + " form button").click()


# ------------------------------------------------------------------------------------------------ Katalog
def test_nicht_auf_standardseiten_nur_im_katalog(pw, app):
    for page in ("statistik", "uebersicht"):
        assert not json.dumps(_api(app, page).get("layout") or {}).count("fitness")
    pg = _stats(pw, app, widget=False)
    try:
        assert pg.locator(CARD).count() == 0 and pg.locator('[data-wtype="fitness"]').count() == 0 and "Fitness" not in pg.locator("#stx").inner_text()
        _edit(pg)
        pg.locator("#slbar [data-a=add]").click()
        c = pg.locator('.slcard:has([data-add="fitness"])')
        expect(c).to_have_count(1, timeout=T)
        assert "Fitness-Einordnung" in c.inner_text() and "keine medizinische Aussage" in c.inner_text() and c.locator(".slpv").inner_html().strip()
        assert "Zahlen" in pg.locator(".slcat .slcath").all_inner_texts()
        c.locator("[data-add=fitness]").click()
        expect(pg.locator('[data-wtype="fitness"]')).to_have_count(1, timeout=T)
        expect(pg.locator('[data-wtype="fitness"] input#ftj0')).to_be_visible(timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_katalog_der_tourseite_hat_ihn_nicht(pw, app):
    pg = _browser(pw, app, devs=None)
    try:
        pg.goto(f"{app}/#/tour/t0")
        pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen')", timeout=TL)
        _edit(pg)
        pg.locator("#slbar [data-a=add]").click()
        pg.wait_for_selector(".slcat .slcard", timeout=T)
        assert pg.locator('[data-add="fitness"]').count() == 0
    finally:
        pg.browser_.close()


def test_uebersicht_katalog_und_baustein(pw, app):
    _api(app, "uebersicht", "PUT", WIDGET)
    pg = _browser(pw, app, devs=None)
    try:
        pg.goto(f"{app}/#/dash")
        pg.wait_for_selector("main.home #hlast", timeout=TL)
        expect(pg.locator(CARD + " input#ftj0")).to_be_visible(timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------------------------------------ Eingabe
def test_ohne_geburtsjahr_nur_eingabe_dann_speichern_und_aendern(pw, app):
    pg = _stats(pw, app)
    try:
        c = pg.locator(CARD)
        expect(c.locator("input#ftj0")).to_be_visible(timeout=T)
        t = c.inner_text()
        assert "Geburtsjahr" in t and "bleibt privat" in t and "keine medizinische Aussage" in t
        assert c.locator(".ftz").count() == 0 and c.locator("svg.slbr").count() == 0 and "von 100" not in t and "Umfang" not in t      # keine Platzhalterwerte
        assert _req(app, "/api/fitness") == {"status": "kein_geburtsjahr"}
        # ungültig: Meldung im Baustein, nichts gespeichert
        for bad, msg in (("", "vier Ziffern"), ("19", "vier Ziffern"), ("1800", "muss zwischen"), ("2999", "muss zwischen")):
            _jahr(pg, bad)
            expect(c.locator(".ftfehl")).to_contain_text(msg, timeout=T)
        assert _req(app, "/api/fitness") == {"status": "kein_geburtsjahr"}
        # Enter im Feld speichert
        c.locator("input#ftj0").fill("1980")
        c.locator("input#ftj0").press("Enter")
        expect(c.locator(".ftz")).to_be_visible(timeout=T)
        assert _req(app, "/api/fitness")["geburtsjahr"] == 1980 and c.locator("input#ftj0").count() == 0
        assert "Jahrgang 1980" in c.inner_text()
        # ändern über den Dialog (Abbrechen links, Speichern rechts)
        c.locator("[data-a=ftjahr]").click()
        dlg = pg.locator(".uidlg .uibox")
        expect(dlg).to_be_visible(timeout=T)
        assert dlg.locator("input#ftj").input_value() == "1980"
        bs = dlg.locator(".uifoot button").all_inner_texts()
        assert bs == ["Abbrechen", "Speichern"], bs
        pg.keyboard.press("Escape")
        expect(pg.locator(".uidlg")).to_have_count(0, timeout=T)
        assert _req(app, "/api/fitness")["geburtsjahr"] == 1980
        c.locator("[data-a=ftjahr]").click()
        dlg.locator("input#ftj").fill("1700")
        dlg.get_by_role("button", name="Speichern").click()
        expect(dlg.locator(".ftfehl")).to_contain_text("muss zwischen", timeout=T)
        dlg.locator("input#ftj").fill("1965")
        dlg.get_by_role("button", name="Speichern").click()
        expect(pg.locator(".uidlg")).to_have_count(0, timeout=T)
        expect(c).to_contain_text("Jahrgang 1965", timeout=T)
        assert _req(app, "/api/fitness")["geburtsjahr"] == 1965
        # entfernen: zurück zur Eingabe
        c.locator("[data-a=ftjahr]").click()
        dlg.get_by_role("button", name="Geburtsjahr entfernen").click()
        expect(c.locator("input#ftj0")).to_be_visible(timeout=T)
        assert _req(app, "/api/fitness") == {"status": "kein_geburtsjahr"}
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------------------------------------ Anzeige und Zustände
def test_anzeige_echte_daten_und_info_einklappbar(pw, app):
    _req(app, "/api/fitness/geburtsjahr", "PUT", {"jahr": 1974})
    pg = _stats(pw, app)
    try:
        c = pg.locator(CARD)
        expect(c.locator(".ftz")).to_be_visible(timeout=T)
        d = _req(app, "/api/fitness")
        assert d["status"] == "ok" and c.locator(".ftz").inner_text() == str(d["gesamt"])
        rows = c.locator(".ftrow")
        expect(rows).to_have_count(3, timeout=T)
        t = c.inner_text()
        for w in ("Umfang", "Regelmäßigkeit", "Intensität", "Dein Alter:", "Geburtsjahr ändern", "Orientierung, keine medizinische Aussage.", "für dein Alter"):
            assert w in t, (w, t)
        assert c.locator("svg.slbr").count() == sum(1 for k in ("umfang", "regel", "intensitaet") if d[k].get("wert") is not None)
        info = c.locator("details.ftinfo")
        assert info.get_attribute("open") is None
        info.locator("summary").click()
        expect(info.locator("p").first).to_be_visible(timeout=T)
        it = info.inner_text()
        for w in ("208 − 0,7 × Alter", "Tanaka", "WHO", "150 bis 300", "12 Wochen"):
            assert w in it, (w, it)
        info.locator("summary").click()
        expect(info.locator("p").first).to_be_hidden(timeout=T)
        # der Baustein selbst ist einklappbar wie die anderen
        pg.locator(CARD + " summary").first.click()
        expect(c.locator(".ft")).to_be_hidden(timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("data,erwartet,fehlt", [
    ({"status": "keine_touren", "geburtsjahr": 1974, "alter": 52}, "Noch keine Touren", ".ftz,.ftrow"),
    ({"status": "keine_aktuellen", "geburtsjahr": 1974, "alter": 52}, "In den letzten 12 Wochen gab es keine Tour", ".ftz,.ftrow"),
    ({"status": "zu_wenig", "geburtsjahr": 1974, "alter": 52, "umfang": {"wert": None, "status": "keine_daten"}, "intensitaet": {"wert": None, "status": "keine_daten"},
      "regel": {"wert": 100, "wochen_aktiv": 12, "wochen": 12, "touren": 12}}, "Zu wenig Daten für eine Einordnung", ".ftz"),
])
def test_zustaende_ohne_platzhalter(pw, app, data, erwartet, fehlt):
    pg = _stats(pw, app, route=_fake(data))
    try:
        c = pg.locator(CARD)
        expect(c).to_contain_text(erwartet, timeout=T)
        assert c.locator(fehlt).count() == 0 if data["status"] != "zu_wenig" else c.locator(".ftz").count() == 0
        assert "Dein Alter: 52 (Jahrgang 1974)" in c.inner_text() and not re.search(r"(?<!\d)0 von 100", c.inner_text())
        if data["status"] == "zu_wenig":
            assert c.locator(".ftrow").count() == 3 and c.locator(".ftrow", has_text="Keine Daten").count() == 2 and c.locator("svg.slbr").count() == 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_fehlerzustand(pw, app):
    pg = _stats(pw, app, route=_fake({"detail": "kaputt"}, 500))
    try:
        expect(pg.locator(CARD)).to_contain_text("Die Einordnung konnte nicht geladen werden.", timeout=T)
        assert pg.locator(CARD + " .ftz").count() == 0
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("trend,text,pfeil", [("up", "Besser als in den 12 Wochen davor", "↑"), ("down", "Schwächer als in den 12 Wochen davor", "↓"), ("flat", "Ähnlich wie in den 12 Wochen davor", "→"),
                                              (None, "Ein Vergleich mit den 12 Wochen davor ist noch nicht möglich", "")])
def test_trend_und_einordnung_in_worten(pw, app, trend, text, pfeil):
    pg = _stats(pw, app, route=_fake(_ok(trend=trend)))
    try:
        c = pg.locator(CARD)
        expect(c.locator(".ftrend")).to_contain_text(text, timeout=T)
        assert pfeil in c.locator(".ftrend").inner_text()
        assert c.locator(".ftw").inner_text() == "Gut für dein Alter" and c.locator(".ftz").inner_text() == "72"
        t = c.inner_text()
        assert "3:44 Std. pro Woche" in t and "Empfehlung der WHO: 150–300 Min. pro Woche" in t and "11 von 12 Wochen mit Tour" in t, t
        seg = c.locator(".ftrow .slsegs span").all_inner_texts()
        assert "3:44 Std. pro Woche" in seg and "Empfehlung der WHO: 150–300 Min. pro Woche" in seg and "40 % der Pulszeit bei 60–90 % des Maximalpulses" in seg
        assert "Mittlerer Puls 118 bpm (69 % des geschätzten Maximalpulses von 171 bpm)" in t
    finally:
        pg.browser_.close()


def test_aufstieg_als_ersatz_ohne_puls(pw, app):
    d = _ok(intensitaet={"wert": 75, "quelle": "aufstieg", "m_h": 300, "ref_m_h": 400})
    pg = _stats(pw, app, route=_fake(d))
    try:
        t = pg.locator(CARD)
        expect(t).to_contain_text("300 m Aufstieg je Stunde", timeout=T)
        assert "Richtwert für dein Alter: 400 m je Stunde" in t.inner_text() and "Pulszeit" not in t.inner_text()
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------------------------------------ Sprachen, Größen, Farben
@pytest.mark.parametrize("lang,worte", [
    ("en", ("Volume", "Regularity", "Intensity", "Good for your age", "Better than in the 12 weeks before", "Your age: 52 (born 1974)", "Change year of birth", "Guidance only, not a medical statement.", "out of 100", "per week")),
    ("fr", ("Volume", "Régularité", "Intensité", "Bien pour ton âge", "Mieux que les 12 semaines précédentes", "Ton âge : 52 (né en 1974)", "Modifier l’année de naissance", "pas un avis médical", "sur 100", "par semaine")),
    ("es", ("Volumen", "Regularidad", "Intensidad", "Bien para tu edad", "Mejor que en las 12 semanas anteriores", "Tu edad: 52 (nacido en 1974)", "Cambiar el año de nacimiento", "no es una afirmación médica", "de 100", "por semana")),
])
def test_sprachen(pw, app, lang, worte):
    pg = _stats(pw, app, route=_fake(_ok()))
    try:
        expect(pg.locator(CARD + " .ftz")).to_be_visible(timeout=T)
        set_lang(pg, lang)
        c = pg.locator(CARD)
        expect(c.locator(".ftw")).not_to_have_text("Gut für dein Alter", timeout=T)
        pg.locator(CARD + " details.ftinfo summary").click()
        quiet(pg)
        t = c.inner_text()
        for w in worte:
            assert w in t, (lang, w, t)
        for de in ("für dein Alter", "Wochen davor", "Dein Alter", "Regelmäßigkeit", "Geburtsjahr", "So wird gerechnet", "Umfang:", "Quellen:", "Gesamtwert"):
            assert de not in t, (lang, de)
        pg.locator(CARD + " [data-a=ftjahr]").click()
        d = pg.locator(".uidlg .uibox")
        expect(d).to_be_visible(timeout=T)
        dt = d.inner_text()
        assert "Geburtsjahr" not in dt and "Abbrechen" not in dt and "Speichern" not in dt and "Es bleibt privat" not in dt, dt
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_sprachen_eingabe_ohne_geburtsjahr(pw, app):
    pg = _stats(pw, app)
    try:
        expect(pg.locator(CARD + " input#ftj0")).to_be_visible(timeout=T)
        set_lang(pg, "en")
        t = pg.locator(CARD).inner_text()
        assert "Year of birth (four digits)" in t and "stays private" in t and "Save" in t and "Geburtsjahr" not in t, t
        _jahr(pg, "1800")
        expect(pg.locator(CARD + " .ftfehl")).to_contain_text("The year of birth must be between", timeout=T)
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width,height", [(390, 844), (1280, 900)])
def test_responsiv_kontrast_screenshots(pw, app, scheme, width, height):
    pg = _stats(pw, app, route=_fake(_ok()), width=width, height=height, scheme=scheme)
    try:
        c = pg.locator(CARD)
        expect(c.locator(".ftz")).to_be_visible(timeout=T)
        c.locator("details.ftinfo summary").click()
        c.scroll_into_view_if_needed()
        settled(pg)
        assert pg.evaluate("() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)") == 0
        box = c.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= width + 1
        assert c.locator(".ft").evaluate("e => e.scrollWidth <= e.clientWidth + 1")
        assert c.locator("[data-a=ftjahr]").bounding_box()["height"] >= 43 and c.locator("details.ftinfo summary").bounding_box()["height"] >= 43
        r = pg.evaluate(CONTRAST, [CARD + " .ftz", CARD + " .ftw", CARD + " .ftrend", CARD + " .ftrow .slr2", CARD + " .ftalter", CARD + " .ftlink", CARD + " .ftorient", CARD + " .ftinfo p"])
        low = {k: round(v, 2) for k, v in r.items() if v < 4.5}
        assert len(r) >= 7 and not low, f"{scheme}: Kontrast unter 4,5:1: {low}"
        _shot(pg, f"fitness-{width}-{scheme}.png")
        # Eingabezustand und Dialog
        c.locator("[data-a=ftjahr]").click()
        expect(pg.locator(".uidlg .uibox")).to_be_visible(timeout=T)
        settled(pg)
        assert pg.evaluate("() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)") == 0
        for b in pg.locator(".uidlg .uifoot .btn").all():
            assert b.bounding_box()["height"] >= 43
        _shot(pg, f"fitness-dialog-{width}-{scheme}.png", full=False)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_eingabezustand_390(pw, app, scheme):
    pg = _stats(pw, app, width=390, height=844, scheme=scheme)
    try:
        c = pg.locator(CARD)
        expect(c.locator("input#ftj0")).to_be_visible(timeout=T)
        c.scroll_into_view_if_needed()
        settled(pg)
        assert pg.evaluate("() => Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth)") == 0
        assert c.locator("form button").bounding_box()["height"] >= 43 and c.locator("input#ftj0").bounding_box()["height"] >= 40
        _shot(pg, f"fitness-eingabe-390-{scheme}.png")
    finally:
        pg.browser_.close()
