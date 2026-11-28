"""3.35.0 – Eigene Kennzahl weiterentwickelt im Browser (Chromium): Ziel mit Fortschrittsbalken (role=progressbar) und „Im Plan?“, Trendpfeil, Sparkline, Antippen (Tourenliste mit Filtern der Kennzahl,
Rekordtour, Hinweis bei nicht abbildbaren Filtern), Einstellungsdialog mit einklappbaren Gruppen und Vorschau, 390 px hell/dunkel ohne Überlauf.
Testdaten: die Touren aus test_statistik_ui.py (Wandern: 14, 10, 25, 18 und 22 km = 89 km; Rad: 40, 60, 80 km; Laufen: 8 und 10 km).
Wettlauf-Regel: nach jeder Aktion auf den Zustand warten (wait_for_function/expect mit 15 s); auf-/zuklappbare Elemente werden explizit gesetzt, nicht angeklickt. Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import pytest

from tests.test_statistik_ui import _api, _edit, _saved, _shot, _stats, app, clean, pw, T  # noqa: F401
from tests.test_tourseite_ui import _settled
from tests.test_eigene_kennzahl_ui import _open_new, _widgets
from tests.helpers_ui import glyph_text  # noqa: E402

expect = pytest.importorskip("playwright.sync_api").expect

LAYOUT = [
    {"id": "k1", "type": "eigenkz", "cfg": {"title": "Jahresziel", "symbol": "🎯", "mess": "km", "agg": "sum", "range": "year", "ziel": 500, "plan": True, "vgl": True, "vglart": "jahr", "spark": "linie", "touren": True}},
    {"id": "k2", "type": "eigenkz", "cfg": {"title": "Wanderkilometer", "symbol": "🥾", "mess": "km", "agg": "sum", "sports": ["hike"], "range": "all", "spark": "linie", "touren": True}},
    {"id": "k3", "type": "eigenkz", "cfg": {"title": "Lange Wanderungen", "mess": "km", "agg": "sum", "sports": ["hike"], "minkm": 15, "range": "all", "touren": True}},
    {"id": "k4", "type": "eigenkz", "cfg": {"title": "Längste Wanderung", "symbol": "🏆", "mess": "km", "agg": "record", "sports": ["hike"], "range": "all", "touren": True}},
    {"id": "k5", "type": "eigenkz", "cfg": {"title": "Puls", "mess": "puls", "agg": "count", "range": "all", "touren": True, "spark": "aus"}},
]


def _put(app, widgets):
    _api(app, "statistik", "PUT", {"v": 1, "widgets": widgets})


def _wait_tiles(pg, n):
    pg.wait_for_function("n => document.querySelectorAll('#stx .tlw[data-wtype=eigenkz] .kzval').length === n && [...document.querySelectorAll('#stx .tlw[data-wtype=eigenkz] .kzval')].every(e => e.textContent.trim() !== '')", arg=n, timeout=T)


def test_tile_goal_trend_sparkline_accessible(pw, app):
    _put(app, LAYOUT)
    pg = _stats(pw, app)
    try:
        _wait_tiles(pg, 5)
        _settled(pg)
        t = pg.locator("#tlw-k1")
        bar = t.locator(".kzbar")
        expect(bar).to_have_attribute("role", "progressbar", timeout=T)
        assert bar.get_attribute("aria-valuemin") == "0" and bar.get_attribute("aria-valuemax") == "100" and bar.get_attribute("aria-valuenow").isdigit()
        assert "500" in bar.get_attribute("aria-valuetext") and "%" in bar.get_attribute("aria-valuetext")
        expect(t.locator(".kzgt")).to_contain_text("% von", timeout=T)
        expect(t.locator(".kzrest")).to_contain_text("bis zum Ziel", timeout=T)
        expect(t.locator(".kzplan")).to_contain_text("Soll", timeout=T)                          # Vor dem / Im / Hinter dem Plan: immer als Text
        expect(t.locator(".kzplan")).to_contain_text("Soll bis heute", timeout=T)
        assert t.locator(".kzsoll").count() == 1
        # Trend: Pfeil plus Text für Vorlesehilfen, neutrale Farbe
        expect(t.locator(".kztr")).to_contain_text("gegenüber dem selben Zeitraum im Vorjahr", timeout=T)
        assert t.locator(".kztr .slsr").inner_text().strip() in ("Zunahme:", "Rückgang:", "Unverändert:")
        assert glyph_text(t, ".kztr .kzd span[aria-hidden]").strip() in ("↑", "↓", "→")
        assert pg.evaluate("() => getComputedStyle(document.querySelector('#tlw-k1 .kzd')).color === getComputedStyle(document.querySelector('#tlw-k1 .kzval')).color")
        # Sparkline als Linie (SVG) mit Beschriftung, Säulen nur bei „saeulen“
        sp = t.locator("svg.kzspk")
        assert sp.count() == 1 and sp.get_attribute("role") == "img" and "Verlauf je" in sp.get_attribute("aria-label") and sp.locator("path.l").count() >= 1 and t.locator("svg.slcol").count() == 0
        assert pg.locator("#tlw-k5 svg.kzspk, #tlw-k5 svg.slcol").count() == 0                       # Verlauf aus
        assert pg.locator("#tlw-k2 svg.kzspk").count() == 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_tap_opens_tours_with_filters_record_and_honest_hint(pw, app):
    _put(app, LAYOUT)
    pg = _stats(pw, app)
    try:
        _wait_tiles(pg, 5)
        # Kachel antippen: Tourenliste mit Aktivität (Zeitraum „gesamt“: kein von/bis)
        pg.locator("#tlw-k2 .kzmain").click()
        pg.wait_for_function("() => location.hash.startsWith('#/tours?sp=hike') && !!document.querySelector('.kzxf') && /5 Touren/.test(((document.querySelector('#cnt') || {}).textContent || ''))", timeout=T)
        expect(pg.locator(".kzxt")).to_contain_text("Wanderkilometer", timeout=T)
        assert pg.locator(".kzchip").all_inner_texts() == ["Wandern"] and not pg.locator(".kzxh").count()
        assert pg.locator("#fs").input_value() == ""                                              # die Auswahlfelder bleiben leer, die Kennzahl filtert
        # Filter aufheben: alle Touren
        pg.locator(".kzxt a").click()
        pg.wait_for_function("() => location.hash === '#/tours' && !document.querySelector('.kzxf') && /10 Touren/.test(((document.querySelector('#cnt') || {}).textContent || ''))", timeout=T)
        # Mindeststrecke
        pg.goto(f"{app}/#/stats")
        pg.wait_for_selector("#stx #tlw-k3 .kzgo a", timeout=T)
        pg.locator("#tlw-k3 .kzgo a").click()
        pg.wait_for_function("() => location.hash.includes('minkm=15') && /3 Touren/.test(((document.querySelector('#cnt') || {}).textContent || ''))", timeout=T)
        assert "mindestens 15 km" in pg.locator(".kzchip").all_inner_texts()
        # Rekord: direkt die Rekordtour
        pg.goto(f"{app}/#/stats")
        pg.wait_for_selector("#stx #tlw-k4 .kzgo a", timeout=T)
        expect(pg.locator("#tlw-k4 .kzgo a")).to_contain_text("Tour mit dem Bestwert öffnen", timeout=T)
        pg.locator("#tlw-k4 .kzmain").click()
        pg.wait_for_function("() => /^#\\/tour\\/[^?]+$/.test(location.hash)", timeout=T)
        # nicht abbildbar (Puls): ehrlicher Hinweis in Kachel und Liste
        pg.goto(f"{app}/#/stats")
        pg.wait_for_selector("#stx #tlw-k5 .kzhn", timeout=T)
        assert "ohne die nötige Angabe" in pg.locator("#tlw-k5 .kzhn").inner_text()
        pg.locator("#tlw-k5 .kzgo a").click()
        pg.wait_for_function("() => location.hash.includes('hn=a') && !!document.querySelector('.kzxh')", timeout=T)
        assert "auch solche ohne die nötige Angabe" in pg.locator(".kzxh").inner_text() and "10 Touren" in pg.locator("#cnt").inner_text()
        # ungültige Parameter in der Adresse: nichts davon landet als HTML in der Seite
        pg.goto(f"{app}/#/tours?kz=%3Cb%3EX%3C%2Fb%3E&sp=hike,%3Cimg%3E&von=kaputt&minkm=-4&hn=zzz")
        pg.wait_for_selector(".kzxf", timeout=T)
        assert pg.locator(".kzxf b b").count() == 0 and pg.locator(".kzxf img").count() == 0 and pg.locator(".kzxh").count() == 0
        assert "<b>X</b>" in pg.locator(".kzxt b").inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_edit_mode_tap_does_not_navigate(pw, app):
    _put(app, LAYOUT[:2])
    pg = _stats(pw, app)
    try:
        _wait_tiles(pg, 2)
        _edit(pg)
        pg.evaluate("() => document.querySelector('#tlw-k2 .kz[data-go]').click()")
        pg.wait_for_timeout(300)
        assert pg.evaluate("() => location.hash.startsWith('#/stats')")
    finally:
        pg.browser_.close()


def test_dialog_groups_preview_and_saved_fields(pw, app):
    _put(app, [])
    pg = _stats(pw, app)
    try:
        _edit(pg)
        _open_new(pg)
        assert pg.locator(".slkz .kzdet").count() == 4
        pg.locator(".slkz .kzdet").evaluate_all("l => l.forEach(d => (d.open = true))")                 # Zustand explizit setzen
        pg.locator(".slkz #kz-title").fill("Ziel km")
        pg.locator(".slkz #kz-ziel").fill("500")
        pg.wait_for_function("() => !!document.querySelector('.slkz .kzpvb .kzgoal')", timeout=T)
        assert pg.locator(".slkz #kz-plan").is_enabled()                                              # laufendes Jahr, Summe: Soll möglich
        pg.locator(".slkz #kz-plan").check()
        expect(pg.locator(".slkz .kzpvb .kzplan")).to_contain_text("Soll bis heute", timeout=T)
        assert pg.locator(".slkz #kz-spark").input_value() == "linie" and pg.locator(".slkz #kz-touren").is_checked()       # neue Kennzahlen starten mit Linie und Antippen
        expect(pg.locator(".slkz .kzpvb .kzgo")).to_have_text("Antippen öffnet die Touren", timeout=T)
        assert pg.locator(".slkz .kzpvb a").count() == 0                                              # Vorschau ist nicht bedienbar (kein Link)
        # Vergleich
        assert pg.locator(".slkz #kz-vglart").is_disabled()
        pg.locator(".slkz #kz-vgl").check()
        assert pg.locator(".slkz #kz-vglart").is_enabled()
        pg.locator(".slkz #kz-vglart").select_option("monat")
        expect(pg.locator(".slkz .kzpvb .kztr")).to_contain_text("einen Monat früher", timeout=T)
        pg.locator(".slkz #kz-vglart").select_option("jahr")
        expect(pg.locator(".slkz .kzpvb .kztr")).to_contain_text("im Vorjahr", timeout=T)
        # Verlauf aus: keine Grafik
        pg.locator(".slkz #kz-spark").select_option("aus")
        pg.wait_for_function("() => !document.querySelector('.slkz .kzpvb svg.kzspk') && !document.querySelector('.slkz .kzpvb svg.slcol')", timeout=T)
        pg.locator(".slkz #kz-spark").select_option("saeulen")
        pg.wait_for_function("() => !!document.querySelector('.slkz .kzpvb svg.slcol')", timeout=T)
        # Soll nur, wo sinnvoll: „Gesamte Zeit“ schaltet es ab
        pg.locator(".slkz #kz-range").select_option("all")
        pg.wait_for_function("() => document.querySelector('.slkz #kz-plan').disabled && !document.querySelector('.slkz #kz-plan').checked && !!document.querySelector('.slkz .kzplh').textContent", timeout=T)
        assert pg.locator(".slkz #kz-vglart").is_disabled()
        pg.locator(".slkz #kz-range").select_option("year")
        pg.wait_for_function("() => !document.querySelector('.slkz #kz-plan').disabled", timeout=T)
        pg.locator(".slkz #kz-plan").check()
        pg.locator(".slkz #kz-vgl").check()
        # Gruppe einklappen: Zustand explizit, Feld verschwindet
        pg.locator(".slkz .kzdet").first.evaluate("d => (d.open = false)")
        expect(pg.locator(".slkz #kz-ziel")).to_be_hidden(timeout=T)
        pg.locator(".slkz .kzdet").first.evaluate("d => (d.open = true)")
        expect(pg.locator(".slkz #kz-ziel")).to_be_visible(timeout=T)
        pg.locator(".slkz button[type=submit]").click()
        pg.wait_for_selector("#stx .tlw[data-wtype='eigenkz'] .kzgoal", timeout=T)
        _saved(pg)
        c = _widgets(app)[0]["cfg"]
        assert c["ziel"] == 500 and c["plan"] is True and c["vgl"] is True and c["vglart"] == "jahr" and c["touren"] is True and "spark" not in c        # Säulen = Standard
        # Bearbeiten: Werte kommen zurück
        wid = _widgets(app)[0]["id"]
        more = pg.locator(f'.slit[data-sl="{wid}"] .slmorebtn')
        if more.is_visible():
            more.click()
        pg.locator(f'.slit[data-sl="{wid}"] [data-a=cfg]').click()
        pg.wait_for_selector(".slkz form.kzform", timeout=T)
        assert pg.locator(".slkz #kz-plan").is_checked() and pg.locator(".slkz #kz-vglart").input_value() == "jahr" and pg.locator(".slkz #kz-spark").input_value() == "saeulen" and pg.locator(".slkz #kz-touren").is_checked()
        assert not pg.errors, pg.errors
    finally:
        _put(app, [])
        pg.browser_.close()


def test_tile_and_dialog_390_light_dark_no_overflow_and_screens(pw, app):
    _put(app, LAYOUT)
    for width, scheme in ((1280, "light"), (1280, "dark"), (390, "light"), (390, "dark")):
        pg = _stats(pw, app, width=width, height=900, scheme=scheme, dpr=2 if width == 390 else 1)
        try:
            _wait_tiles(pg, 5)
            pg.wait_for_function("() => !!document.querySelector('#tlw-k1 .kzplan') && !!document.querySelector('#tlw-k1 svg.kzspk')", timeout=T)
            _settled(pg)
            assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
            assert pg.evaluate("() => [...document.querySelectorAll('#stx .tlw[data-wtype=eigenkz]')].every(e => e.scrollWidth <= e.clientWidth + 1)")
            _shot(pg, f"kz350-kacheln-{width}-{scheme}.png")
            assert not pg.errors, pg.errors
        finally:
            pg.browser_.close()
        pg = _stats(pw, app, width=width, height=900, scheme=scheme, dpr=2 if width == 390 else 1)
        try:
            _edit(pg)
            _open_new(pg)
            pg.locator(".slkz .kztplb").evaluate("d => (d.open = false)")
            pg.locator(".slkz .kzdet").evaluate_all("l => l.forEach(d => (d.open = true))")
            pg.locator(".slkz #kz-ziel").fill("500")
            pg.locator(".slkz #kz-plan").check()
            pg.locator(".slkz #kz-vgl").check()
            pg.wait_for_function("() => !!document.querySelector('.slkz .kzpvb .kzplan') && !!document.querySelector('.slkz .kzpvb .kztr') && !!document.querySelector('.slkz .kzpvb svg.kzspk')", timeout=T)
            assert pg.evaluate("() => document.querySelector('.slkz').scrollWidth <= document.querySelector('.slkz').clientWidth + 1")
            _shot(pg, f"kz350-dialog-oben-{width}-{scheme}.png", full=False)
            pg.locator(".slkz .kzdet").last.scroll_into_view_if_needed()
            _shot(pg, f"kz350-dialog-unten-{width}-{scheme}.png", full=False)
        finally:
            pg.browser_.close()
    _put(app, [])
