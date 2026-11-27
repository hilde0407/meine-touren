"""3.66.0 – Seiten anpassen: Entfernen, „Standard wiederherstellen“ mit zwei Wegen, „Alle Seiten auf Werkseinstellung zurücksetzen …“ (Browser, Chromium, Desktop und 390 px).
Wettlauf-Regel: nach jeder Aktion auf den Zustand warten, nie nur schlafen."""
import pytest

expect = pytest.importorskip("playwright.sync_api").expect
from tests.helpers_ui import entferne, quiet, wieder_hinzufuegen  # noqa: E402
from tests.test_seitenlayout_ui import KEYS, T, _api, _browser, _dash, _edit, _saved, _tour, app, pw  # noqa: F401,E402

ALLE = ("tour-haupt", "tour-auswertung", "uebersicht", "statistik", "reise", "serie", "reisen", "gebiete", "gebiet", "fotos", "karte")


def _leer(app):
    for k in ALLE:
        _api(app, k, "DELETE")


def _box(own_hidden=("jahr",), std_hidden=("zuletzt",), active="v1", rules=None):
    return {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1, "hidden": list(std_hidden)}},
                              {"id": "v1", "name": "Meine Ansicht", "layout": {"v": 1, "hidden": list(own_hidden), "w": {"zuletzt": "zweidrittel"}}}], "active": active, "rules": rules or {}}


def _cont(app, key):
    return _api(app, key).get("container")


def _units(pg):
    return pg.evaluate("() => [...document.querySelectorAll('main.home > *')].filter(e => e.id && !e.classList.contains('sl-off')).map(e => e.id)")


def _warte_server(app, key, fn, what="", pg=None):
    """Wartet auf den Server-Zustand. Mit „pg“ wird die Seite dabei bedient (Playwright-Sync: reines time.sleep lässt die Seite nicht laufen, ihr Speichern bliebe aus)."""
    import time
    t = time.time()
    while time.time() - t < 15:
        c = _cont(app, key)
        if fn(c):
            return c
        pg.wait_for_timeout(150) if pg else time.sleep(0.15)
    raise AssertionError(f"Server-Zustand nicht erreicht: {what} {c}")


# ------------------------------------------------------------------  Entfernen ist der einzige Weg  ------------------------------------------------------------------

def test_tourseite_entfernen_pflicht_hat_keinen_knopf_und_gruppen_ueberschrift(pw, app):
    _leer(app)
    pg = _tour(pw, app)
    try:
        _edit(pg)
        assert pg.locator(".slit [data-a=eye]").count() == 0 and pg.locator('.slit[data-sl="sum"] [data-a="del"]').count() == 0          # Pflicht: nicht entfernbar
        assert pg.locator('.slit[data-sl="sum"] .slmust').is_visible()
        n = pg.locator(".slit:not([data-sl=sum]) [data-a=del]").count()
        assert n == pg.locator(".slit").count() - 1 and n >= 5
        for s in ("map", "prof", "puls", "wp"):
            assert pg.locator(f'.slit[data-sl="{s}"] [data-a=del]').get_attribute("aria-label").startswith("Baustein entfernen: ")
        entferne(pg, "wp")
        live = pg.locator("#sllive")
        expect(live).to_contain_text("entfernt", timeout=T)
        assert pg.evaluate("document.activeElement && document.activeElement.dataset.a") == "add"             # Fokus bleibt in der Leiste
        # Rückgängig holt ihn zurück
        pg.locator('#slbar [data-a="undo"]').click()
        pg.wait_for_selector('.slit[data-sl="wp"]', timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_bereits_ausgeblendet_gilt_als_entfernt_und_bleibt_erhalten(pw, app):
    """Altes Layout mit hidden: kein Datenverlust, keine Migration, der Baustein steht im Katalog als „Wieder hinzufügen“ und kommt mit Reihenfolge und Breite zurück."""
    _leer(app)
    _api(app, "uebersicht", "PUT", {"v": 1, "hidden": ["zuletzt"], "w": {"zuletzt": "zweidrittel"}, "order": ["zuletzt", "jahr"]})
    pg = _dash(pw, app)
    try:
        assert "hrecent" not in _units(pg)
        _edit(pg)
        assert pg.locator('.slit[data-sl="zuletzt"]').count() == 0
        wieder_hinzufuegen(pg, "zuletzt")
        assert pg.locator('.slit[data-sl="zuletzt"]').get_attribute("data-cw") == "zweidrittel"
        _saved(pg)
        lay = _api(app, "uebersicht")["layout"]
        assert not lay.get("hidden") and lay["w"] == {"zuletzt": "zweidrittel"} and lay["order"][:2] == ["zuletzt", "jahr"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Standard wiederherstellen: zwei Wege  ------------------------------------------------------------------

def _reset_dialog(pg):
    pg.locator('#slbar [data-a="reset"]').click()
    pg.wait_for_selector(".uidlg .uibox", timeout=T)
    return pg.locator(".uidlg .uibox")


def test_standard_wiederherstellen_zwei_wege_bei_eigener_standardansicht(pw, app):
    _leer(app)
    _api(app, "uebersicht", "PUT", _box())
    pg = _dash(pw, app)
    try:
        assert "hyear" not in _units(pg) and "hrecent" in _units(pg)                              # angezeigt: die eigene Standardansicht (jahr entfernt)
        pg.locator("#slview").select_option(label="Standard")                                     # eine andere Ansicht anzeigen: Standard (zuletzt entfernt)
        pg.wait_for_function("() => !document.querySelector('#hrecent:not(.sl-off)')", timeout=T)
        _edit(pg)
        box = _reset_dialog(pg)
        assert "Standard wiederherstellen?" in box.locator("h2").inner_text()
        buttons = [b.inner_text().strip() for b in box.locator(".uifoot button").all()]
        assert buttons == ["Abbrechen", "Auf meine Standardansicht", "Auf die Werkseinstellung"], buttons
        assert "Meine Ansicht" in box.inner_text() and box.get_attribute("role") == "alertdialog"
        assert "uidanger" in box.locator(".uifoot button").last.get_attribute("class")
        # Abbrechen ändert nichts
        box.locator(".uifoot button", has_text="Abbrechen").click()
        pg.wait_for_selector(".uidlg", state="detached", timeout=T)
        assert "hrecent" not in _units(pg)
        # Auf meine Standardansicht: die angezeigte Ansicht „Standard“ wird wie „Meine Ansicht“
        box = _reset_dialog(pg)
        box.locator("#slresetown").click()
        pg.wait_for_function("() => !!document.querySelector('#hrecent:not(.sl-off)') && !!document.querySelector('#hyear.sl-off, #hyear:not(.sl-off)') && SL.docs.uebersicht.hidden.join() === 'jahr'", timeout=T)
        expect(pg.locator("#sllive")).to_contain_text("Auf deine Standardansicht „Meine Ansicht“ zurückgesetzt", timeout=T)
        c = _warte_server(app, "uebersicht", lambda c: c["views"][0]["layout"].get("hidden") == ["jahr"], "Standard wie meine Ansicht", pg)
        assert c["views"][1]["layout"]["hidden"] == ["jahr"] and c["active"] == "v1" and c["views"][0]["layout"]["w"] == {"zuletzt": "zweidrittel"}
        # Auf die Werkseinstellung: die angezeigte Ansicht wird leer, die andere bleibt
        _reset_dialog(pg).locator(".uifoot button", has_text="Auf die Werkseinstellung").click()
        pg.wait_for_function("() => !document.querySelector('.uidlg') && !(SL.docs.uebersicht && Object.keys(SL.docs.uebersicht).some(k => k !== 'v'))", timeout=T)
        c = _warte_server(app, "uebersicht", lambda c: c["views"][0]["layout"] in ({}, {"v": 1}), "Werkseinstellung", pg)
        assert c["views"][1]["layout"]["hidden"] == ["jahr"] and c["active"] == "v1"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_standard_wiederherstellen_wie_bisher_bei_einer_ansicht_und_ohne_eigene_standardansicht(pw, app):
    _leer(app)
    pg = _dash(pw, app)
    try:
        _edit(pg)
        entferne(pg, "zuletzt")
        box = _reset_dialog(pg)                                                                    # eine Ansicht: ein Weg, wie bisher
        assert [b.inner_text().strip() for b in box.locator(".uifoot button").all()] == ["Abbrechen", "Standard wiederherstellen"]
        assert "entfernte" in box.inner_text() and "ausgeblendet" not in box.inner_text()
        box.locator(".uifoot button", has_text="Standard wiederherstellen").click()
        pg.wait_for_function("() => !document.querySelector('.uidlg') && !!document.querySelector('#hrecent:not(.sl-off)')", timeout=T)
        expect(pg.locator("#sllive")).to_contain_text("Standard wiederhergestellt", timeout=T)
    finally:
        pg.browser_.close()
    # mehrere Ansichten, aber die mitgelieferte ist Standardansicht: auch nur ein Weg
    _api(app, "uebersicht", "PUT", _box(active="standard"))
    pg = _dash(pw, app)
    try:
        pg.locator("#slview").select_option(label="Meine Ansicht")
        _edit(pg)
        box = _reset_dialog(pg)
        assert [b.inner_text().strip() for b in box.locator(".uifoot button").all()] == ["Abbrechen", "Standard wiederherstellen"]
        box.locator(".uifoot button", has_text="Abbrechen").click()
    finally:
        pg.browser_.close()
    # eigene Standardansicht wird angezeigt: „Auf meine Standardansicht“ würde nichts ändern, also nur die Werkseinstellung
    _api(app, "uebersicht", "PUT", _box(active="v1"))
    pg = _dash(pw, app)
    try:
        _edit(pg)
        box = _reset_dialog(pg)
        assert pg.locator("#slresetown").count() == 0
        box.locator(".uifoot button", has_text="Abbrechen").click()
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Alle Seiten auf Werkseinstellung  ------------------------------------------------------------------

def _fuellen(app):
    _leer(app)
    _api(app, "uebersicht", "PUT", _box())
    _api(app, "tour-haupt", "PUT", _box(rules={"hike": "v1"}))
    _api(app, "tour-auswertung", "PUT", _box())
    _api(app, "statistik", "PUT", {"v": 1, "hidden": ["ziele"], "w": {"kpi": "halb"}})            # altes Format
    _api(app, "fotos", "PUT", {"v": 1, "hidden": ["jahre"]})


def _ansichten_dialog(pg):
    pg.locator("#slopenw #slviews").click()
    pg.wait_for_selector(".slvws .slvr", timeout=T)


def _faktor(pg):
    """Knopf im Ansichten-Dialog drücken, die Rückfrage lesen und Kästchen setzen."""
    pg.locator('.slvws [data-a="factory"]').click()
    pg.wait_for_selector(".uidlg .uibox h2", timeout=T)
    return pg.locator(".uidlg").last.locator(".uibox")


@pytest.mark.parametrize("breite", [1280, 390])
def test_werksreset_ohne_haken_eigene_ansichten_bleiben(pw, app, breite):
    _fuellen(app)
    pg = _dash(pw, app, width=breite, height=900)
    try:
        pg.evaluate("() => { localStorage.setItem('mt_trf_tl_map', '0'); localStorage.setItem('mt_trf_zr_uebersicht', '1'); sessionStorage.setItem('mt_slv_x_uebersicht', 'v1'); }")
        assert pg.evaluate("() => Object.keys(localStorage).some(k => k.startsWith('mt_sl_'))")
        if breite == 390:
            pg.locator("#slviews").click()
            pg.locator('#slvmenu [data-m="manage"]').click()
            pg.wait_for_selector(".slvws .slvr", timeout=T)
        else:
            _ansichten_dialog(pg)
        assert pg.locator(".slvfw").count() == 1 and "Alle Seiten" in pg.locator(".slvfw h3").inner_text()
        box = _faktor(pg)
        txt = box.inner_text()
        for w in ("Alle Seiten auf Werkseinstellung zurücksetzen?", "Layouts", "Reihenfolge", "Breiten", "entfernte und hinzugefügte Bausteine", "Ansichten aller Seiten", "Touren, Ziele, Einstellungen"):
            assert w in txt, (w, txt)
        cb = box.locator("#slfown")
        assert not cb.is_checked() and box.get_attribute("role") == "alertdialog"
        assert [b.inner_text().strip() for b in box.locator(".uifoot button").all()] == ["Abbrechen", "Alle Seiten zurücksetzen"]
        if breite == 390:
            assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
            ob = box.bounding_box()
            assert ob["x"] >= 0 and ob["x"] + ob["width"] <= 391
        # Abbrechen: nichts passiert
        box.locator(".uifoot button", has_text="Abbrechen").click()
        pg.wait_for_selector(".uidlg .uibox h2:has-text('Alle Seiten')", state="detached", timeout=T)
        assert _cont(app, "uebersicht")["views"][1]["layout"]["hidden"] == ["jahr"] and len(_cont(app, "uebersicht")["views"]) == 2
        # Zurücksetzen
        box = _faktor(pg)
        box.locator(".uifoot button", has_text="Alle Seiten zurücksetzen").click()
        expect(pg.locator("#slvlive")).to_contain_text("Alle Seiten auf Werkseinstellung zurückgesetzt. 2 eigene Ansichten bleiben bestehen.", timeout=T)
        # Server: Standard zurückgesetzt, eigene Ansichten und Regeln bleiben, Festlegung auf die mitgelieferte
        u = _cont(app, "uebersicht")
        assert u["active"] == "standard" and u["views"][0]["layout"] in ({}, {"v": 1}) and u["views"][1]["layout"]["hidden"] == ["jahr"]
        t = _cont(app, "tour-haupt")
        assert t["rules"] == {"hike": "v1"} and t["active"] == "standard" and _cont(app, "tour-auswertung")["active"] == "standard"
        assert _cont(app, "statistik") is None and _cont(app, "fotos") is None                       # altes Format, nur Standard: Dokument gelöscht
        # Browser: Wirkung sofort, Zwischenspeicher gleichgezogen, gemerkte Zustände weg
        pg.wait_for_function("() => SL.view.uebersicht === 'standard' && !SL.docs.uebersicht", timeout=T)
        assert pg.evaluate("() => !localStorage.getItem('mt_trf_tl_map') && !localStorage.getItem('mt_trf_zr_uebersicht') && !sessionStorage.getItem('mt_slv_x_uebersicht')")
        assert pg.evaluate("() => JSON.parse(localStorage.getItem(Object.keys(localStorage).find(k => k.startsWith('mt_sl_') && k.endsWith('_uebersicht')))).active") == "standard"
        pg.wait_for_function("() => !!document.querySelector('#hrecent:not(.sl-off)') && !!document.querySelector('#hyear:not(.sl-off)')", timeout=T)          # beides wieder sichtbar
        assert pg.locator("#slview").input_value() == "standard"
        assert pg.locator(".slvws .slvr").count() == 2                                               # der Dialog zeigt den neuen Stand
        assert not pg.errors, pg.errors
        # nach Neuladen bleibt es so
        pg.reload()
        pg.wait_for_selector("main.home #hlast", timeout=T)
        pg.wait_for_function("() => !!document.querySelector('#hyear:not(.sl-off)') && SL.view.uebersicht === 'standard'", timeout=T)
    finally:
        pg.browser_.close()


def test_werksreset_mit_haken_loescht_auch_eigene_ansichten(pw, app):
    _fuellen(app)
    pg = _dash(pw, app)
    try:
        _ansichten_dialog(pg)
        box = _faktor(pg)
        box.locator("#slfown").check()
        box.locator(".uifoot button", has_text="Alle Seiten zurücksetzen").click()
        expect(pg.locator("#slvlive")).to_contain_text("Alle Seiten auf Werkseinstellung zurückgesetzt. Eigene Ansichten gelöscht.", timeout=T)
        for k in ALLE:
            g = _api(app, k)
            assert g["layout"] is None and g["container"] is None, k
        pg.wait_for_function("() => document.querySelectorAll('.slvws .slvr').length === 1", timeout=T)
        assert pg.evaluate("() => !Object.keys(localStorage).some(k => k.startsWith('mt_sl_') && localStorage.getItem(k) && localStorage.getItem(k) !== 'null')")
        pg.keyboard.press("Escape")
        assert pg.locator("#slview").count() == 0                                                    # nur noch eine Ansicht: keine Auswahl
        pg.wait_for_function("() => !!document.querySelector('#hrecent:not(.sl-off)') && !!document.querySelector('#hyear:not(.sl-off)')", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_werksreset_aus_der_verwaltung_und_im_bearbeitungsmodus(pw, app):
    _fuellen(app)
    pg = _browser(pw, app, width=390, height=900, devs=None)
    try:
        pg.goto(f"{app}/#/admin?tab=allgemein")
        pg.wait_for_selector("#slfacb", timeout=T)
        assert "Seitenanordnung" in pg.locator("#slfacp h2").inner_text()
        pg.locator("#slfacb").scroll_into_view_if_needed()
        assert pg.locator("#slfacb").is_visible() and pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
        pg.locator("#slfacb").click()
        pg.wait_for_selector(".uidlg .uibox", timeout=T)
        pg.locator(".uidlg #slfown").check()
        pg.locator(".uidlg .uifoot button", has_text="Alle Seiten zurücksetzen").click()
        expect(pg.locator("#slfacok")).to_have_text("Alle Seiten auf Werkseinstellung zurückgesetzt. Eigene Ansichten gelöscht.", timeout=T)
        assert pg.locator("#slfacok").get_attribute("role") == "status"
        assert all(_api(app, k)["container"] is None for k in ALLE)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    # aus dem Bearbeitungsmodus heraus: der Modus wird beendet, Ungespeichertes gesichert, dann zurückgesetzt
    _fuellen(app)
    pg = _dash(pw, app)
    try:
        _edit(pg)
        entferne(pg, "tag") if pg.locator('.slit[data-sl="tag"]').count() else None
        pg.locator('#slbar [data-a="views"]').click()
        pg.wait_for_selector(".slvws .slvr", timeout=T)
        box = _faktor(pg)
        box.locator(".uifoot button", has_text="Alle Seiten zurücksetzen").click()
        expect(pg.locator("#slvlive")).to_contain_text("2 eigene Ansichten bleiben bestehen", timeout=T)
        pg.wait_for_function("() => !document.querySelector('#slbar') && !document.querySelector('.slit')", timeout=T)
        assert _cont(app, "uebersicht")["active"] == "standard"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_werksreset_fehler_wird_gemeldet_und_aendert_nichts(pw, app):
    _fuellen(app)
    pg = _dash(pw, app)
    try:
        pg.route("**/api/layout/werkseinstellung", lambda r: r.fulfill(status=500, json={"detail": "Datenbank gesperrt"}))
        _ansichten_dialog(pg)
        _faktor(pg).locator(".uifoot button", has_text="Alle Seiten zurücksetzen").click()
        pg.wait_for_selector(".uidlg .uibox h2:has-text('Zurücksetzen nicht möglich')", timeout=T)
        assert "Datenbank gesperrt" in pg.locator(".uidlg .uitext").last.inner_text()
        pg.locator(".uidlg .uifoot button").last.click()
        assert len(_cont(app, "uebersicht")["views"]) == 2 and pg.evaluate("() => SL.view.uebersicht") == "v1"
    finally:
        pg.browser_.close()


def test_katalog_wieder_hinzufuegen_in_allen_seitenarten(pw, app):
    """Entfernte mitgelieferte Bausteine stehen im Katalog mit „Wieder hinzufügen“: auf ihrer Karte (Touren holen) oder in der Gruppe „Entfernte Bausteine“ (Letzte Touren, ohne Karte;
    „Ziele“ der Statistik darf mehrfach stehen und steht deshalb ebenfalls in der Gruppe). Serverseitig vorbereitete Layouts, die Oberfläche liest sie."""
    _leer(app)
    _api(app, "uebersicht", "PUT", {"v": 1, "hidden": ["zepp", "zuletzt"]})
    pg = _dash(pw, app)
    try:
        _edit(pg)
        pg.locator('#slbar [data-a="add"]').click()
        pg.wait_for_selector(".slcard [data-readd]", timeout=T)
        assert pg.locator('[data-readd="zepp"]').inner_text() == "Wieder hinzufügen" and pg.locator('.slre [data-readd="zepp"]').count() == 0      # Baustein mit eigener Karte
        assert pg.locator('.slre [data-readd="zuletzt"]').count() == 1                                                                                # Abschnitt ohne Karte: Gruppe „Entfernte Bausteine“
        pg.locator('[data-readd="zuletzt"]').click()
        pg.wait_for_selector('.slit[data-sl="zuletzt"]', timeout=T)
        assert pg.locator('.slit[data-sl="zepp"]').count() == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    _api(app, "statistik", "PUT", {"v": 1, "hidden": ["ziele", "kmmonat"]})
    pg = _browser(pw, app, width=1280, height=900, devs=None)
    try:
        pg.goto(f"{app}/#/stats")
        pg.wait_for_selector("#stx", timeout=T)
        pg.wait_for_function("() => !!document.querySelector('#slopen')", timeout=T)
        _edit(pg)
        pg.locator('#slbar [data-a="add"]').click()
        pg.wait_for_selector(".slcard [data-readd]", timeout=T)
        assert pg.locator('.slre [data-readd="kmmonat"]').count() == 1 and pg.locator('.slre [data-readd="ziele"]').count() == 1
        pg.locator('[data-readd="kmmonat"]').click()
        pg.wait_for_selector('.slit[data-sl="kmmonat"]', timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
