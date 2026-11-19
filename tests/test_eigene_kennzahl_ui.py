"""3.28.0 – Eigene Kennzahl im Browser (Chromium): Dialog → Baustein erscheint → Wert stimmt, Vorlage, Formel, Ziel, Vergleich, Bearbeiten, Duplizieren, Entfernen, Speicherung
(nach Neuladen, im Layout-Dokument), 390 px hell und dunkel ohne Überlauf, Tastatur (Dialog schließt mit Esc).
Testdaten: die Touren aus test_statistik_ui.py (Wandern: 14, 10, 25, 18 und 22 km = 89 km, 3350 Höhenmeter an Tag 30, 120, 400, 700, 260).
Wettlauf-Regel: nach jeder Aktion auf den Zustand warten (wait_for_function/expect mit 15 s), nie nur schlafen. Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import pytest

from tests.test_statistik_ui import _api, _edit, _saved, _shot, _stats, app, clean, pw, T  # noqa: F401
from tests.test_tourseite_ui import _settled

expect = pytest.importorskip("playwright.sync_api").expect


def _open_new(pg):
    pg.locator("#slbar [data-a=add]").click()
    pg.wait_for_selector('.slcat [data-neu="eigenkz"]', timeout=T)
    pg.locator('.slcat [data-neu="eigenkz"]').click()
    pg.wait_for_selector(".slkz form.kzform", timeout=T)


def _preview(pg, text):
    pg.wait_for_function("t => { const e = document.querySelector('.slkz .kzpvb .kzval'); return !!e && e.textContent.trim() === t; }", arg=text, timeout=T)


def _act(pg, wid, a):
    """Aktion im Rahmen eines Bausteins (auf schmalen Bildschirmen steckt sie im Menü „Weitere Aktionen“)."""
    more = pg.locator(f'.slit[data-sl="{wid}"] .slmorebtn')
    if more.is_visible():
        more.click()
    pg.locator(f'.slit[data-sl="{wid}"] [data-a={a}]').click()


def _widgets(url):
    return (_api(url, "statistik").get("layout") or {}).get("widgets") or []


def _build_hike_km(pg):
    pg.locator(".slkz #kz-title").fill("Wanderkilometer")
    pg.locator(".slkz #kz-mess").select_option("km")
    pg.locator(".slkz #kz-agg").select_option("sum")
    pg.locator(".slkz .flsp input[value='hike']").check()
    pg.locator(".slkz #kz-range").select_option("all")


def test_dialog_builds_block_with_correct_value_and_it_persists(pw, app):
    pg = _stats(pw, app)
    try:
        _edit(pg)
        _open_new(pg)
        assert pg.locator(".slkz .kztplb").evaluate("e => e.open")                    # neu: Vorlagen sind aufgeklappt
        _build_hike_km(pg)
        _preview(pg, "89,0")
        assert pg.locator(".slkz .kzpvb .kzun").inner_text() == "km"
        pg.locator(".slkz button[type=submit]").click()
        pg.wait_for_selector("#stx .tlw[data-wtype='eigenkz'] .kzval", timeout=T)
        pg.wait_for_function("() => document.querySelector(\"#stx .tlw[data-wtype='eigenkz'] .kzval\").textContent.trim() === '89,0'", timeout=T)
        _saved(pg)
        w = _widgets(app)
        assert len(w) == 1 and w[0]["type"] == "eigenkz" and w[0]["cfg"]["mess"] == "km" and w[0]["cfg"]["agg"] == "sum" and w[0]["cfg"]["sports"] == ["hike"] and w[0]["cfg"]["title"] == "Wanderkilometer"
        assert pg.locator("#stx .tlw[data-wtype='eigenkz'] summary").inner_text().startswith("Wanderkilometer")
        # nach dem Neuladen (nicht im Bearbeitungsmodus) steht der Baustein mit demselben Wert da
        pg.reload()
        pg.wait_for_selector("#stx .tlw[data-wtype='eigenkz'] .kzval", timeout=T)
        pg.wait_for_function("() => document.querySelector(\"#stx .tlw[data-wtype='eigenkz'] .kzval\").textContent.trim() === '89,0'", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_template_formula_goal_compare_edit_duplicate_remove(pw, app):
    pg = _stats(pw, app)
    try:
        _edit(pg)
        _open_new(pg)
        # Vorlage „Aufstieg je km“ übernimmt Name, Messgröße, Formel und Vergleich in den Dialog
        pg.locator(".slkz .kztpl", has_text="Aufstieg je km").first.click()
        pg.wait_for_function("() => document.querySelector('.slkz #kz-title').value === 'Aufstieg je km'", timeout=T)
        assert pg.locator(".slkz #kz-formel").is_checked() and pg.locator(".slkz .kzformel").is_visible() and pg.locator(".slkz #kz-vgl").is_checked()
        assert pg.locator(".slkz #kz-mess").input_value() == "hm" and pg.locator(".slkz #kz-bmess").input_value() == "km"
        pg.locator(".slkz #kz-range").select_option("all")                                 # Gesamt: alle Touren
        pg.wait_for_function("() => { const e = document.querySelector('.slkz .kzpvb .kzval'); return !!e && /^\\d+,\\d+$/.test(e.textContent.trim()); }", timeout=T)
        total_up, total_km = 300 + 500 + 600 + 300 + 80 + 1100 + 700 + 650 + 90 + 900, 40 + 14 + 60 + 10 + 8 + 25 + 80 + 18 + 10 + 22
        want = f"{total_up / total_km:.1f}".replace(".", ",")              # 5220 ÷ 287 = 18,19 (ab 10: eine Nachkommastelle)
        _preview(pg, want)
        assert pg.locator(".slkz .kzpvb .kzun").inner_text() == "m/km"
        assert pg.locator(".slkz #kz-vgl").is_disabled() and not pg.locator(".slkz #kz-vgl").is_checked()        # Gesamt: kein Vergleichszeitraum
        # Ziel: Fortschrittsbalken
        pg.locator(".slkz #kz-formel").uncheck()
        pg.locator(".slkz #kz-agg").select_option("sum")
        pg.locator(".slkz #kz-mess").select_option("km")
        pg.locator(".slkz #kz-ziel").fill("574")
        pg.wait_for_function("() => !!document.querySelector('.slkz .kzgoal .kzgt') && document.querySelector('.slkz .kzgt').textContent.includes('50 %')", timeout=T)
        assert "574" in pg.locator(".slkz .kzgt").inner_text()
        pg.locator(".slkz #kz-title").fill("Halbzeit")
        pg.locator(".slkz button[type=submit]").click()
        pg.wait_for_selector("#stx .tlw[data-wtype='eigenkz'] .kzgoal", timeout=T)
        _saved(pg)
        card = pg.locator("#stx .tlw[data-wtype='eigenkz']").first
        assert card.locator(".kzval").inner_text() == "287" and card.locator(".slbr").count() == 1 and card.locator(".kzspk").count() == 1
        # Bearbeiten über das Zahnrad (im Menü „Weitere Aktionen“)
        wid = _widgets(app)[0]["id"]
        _act(pg, wid, "cfg")
        pg.wait_for_selector(".slkz form.kzform", timeout=T)
        assert pg.locator(".slkz h2").inner_text() == "Eigene Kennzahl bearbeiten" and pg.locator(".slkz #kz-title").input_value() == "Halbzeit"
        assert not pg.locator(".slkz .kztplb").evaluate("e => e.open")
        pg.locator(".slkz #kz-title").fill("Gesamtstrecke")
        pg.locator(".slkz #kz-ziel").fill("")
        pg.locator(".slkz button[type=submit]").click()
        pg.wait_for_function("() => document.querySelector(\"#stx .tlw[data-wtype='eigenkz'] summary\").textContent.includes('Gesamtstrecke') && !document.querySelector(\"#stx .tlw[data-wtype='eigenkz'] .kzgoal\")", timeout=T)
        # Duplizieren: Kopie direkt dahinter
        _act(pg, wid, "dup")
        pg.wait_for_function("() => document.querySelectorAll(\"#stx .tlw[data-wtype='eigenkz']\").length === 2", timeout=T)
        _saved(pg)
        w = _widgets(app)
        assert [x["cfg"]["title"] for x in w] == ["Gesamtstrecke", "Gesamtstrecke (Kopie)"] and w[0]["id"] != w[1]["id"] and "ziel" not in w[0]["cfg"]
        order = _api(app, "statistik")["layout"]["order"]
        assert order.index(w[1]["id"]) == order.index(w[0]["id"]) + 1
        # Entfernen
        _act(pg, w[1]["id"], "del")
        pg.locator(".uibox [data-ok], .uibox .btn:not(.ghost)").last.click()
        pg.wait_for_function("() => document.querySelectorAll(\"#stx .tlw[data-wtype='eigenkz']\").length === 1", timeout=T)
        _saved(pg)
        assert len(_widgets(app)) == 1
        # „Standard wiederherstellen“ entfernt auch die eigenen Kennzahlen
        pg.locator("#slbar [data-a=reset]").click()
        pg.locator(".uibox .btn:not(.ghost)").last.click()
        pg.wait_for_function("() => document.querySelectorAll(\"#stx .tlw[data-wtype='eigenkz']\").length === 0", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_dialog_validation_escape_and_viewport_390(pw, app):
    for scheme in ("light", "dark"):
        pg = _stats(pw, app, width=390, height=800, scheme=scheme, dpr=2)
        try:
            _edit(pg)
            _open_new(pg)
            _shot(pg, f"kz-dialog-390-{scheme}.png", full=False)
            pg.locator(".slkz form").evaluate("f => f.scrollIntoView()")
            pg.locator(".slkz button[type=submit]").click()                              # ohne Namen
            pg.wait_for_function("() => document.querySelector('.slkz .kzerr').textContent.includes('Namen')", timeout=T)
            assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
            assert pg.evaluate("() => document.querySelector('.slkz').scrollWidth <= document.querySelector('.slkz').clientWidth + 1")
            pg.keyboard.press("Escape")
            pg.wait_for_function("() => !document.querySelector('.slkz')", timeout=T)
            assert _widgets(app) == []
        finally:
            pg.browser_.close()


def test_block_390_light_and_dark_no_overflow_and_screens(pw, app):
    cfgs = [{"id": "k1", "type": "eigenkz", "cfg": {"title": "Wanderkilometer", "symbol": "🥾", "mess": "km", "agg": "sum", "sports": ["hike"], "range": "all", "ziel": 100}},
            {"id": "k2", "type": "eigenkz", "cfg": {"title": "Längste Wanderung", "symbol": "🏆", "mess": "km", "agg": "record", "sports": ["hike"], "range": "all"}},
            {"id": "k3", "type": "eigenkz", "cfg": {"title": "Aufstieg je km", "symbol": "⛰️", "mess": "hm", "agg": "sum", "durch": {"mess": "km", "agg": "sum"}, "op": "div", "range": "12m", "vgl": True}}]
    _api(app, "statistik", "PUT", {"v": 1, "widgets": cfgs})
    for width, scheme in ((1280, "light"), (1280, "dark"), (390, "light"), (390, "dark")):
        pg = _stats(pw, app, width=width, height=900, scheme=scheme, dpr=2 if width == 390 else 1)
        try:
            pg.wait_for_function("() => document.querySelectorAll('#stx .tlw[data-wtype=eigenkz] .kzval').length === 3", timeout=T)
            pg.wait_for_function("() => [...document.querySelectorAll('#stx .tlw[data-wtype=eigenkz] .kzval')].every(e => /\\d/.test(e.textContent)) && !!document.querySelector('#tlw-k1 .kzgt') && !!document.querySelector('#tlw-k2 .kzsub a')", timeout=T)
            _settled(pg)                                                                 # Messung und Screenshot erst nach dem Layout
            vals = pg.evaluate("() => [...document.querySelectorAll('#stx .tlw[data-wtype=eigenkz]')].map(e => e.querySelector('.kzval').textContent.trim())")
            assert vals[0] == "89,0" and vals[1] == "25,0" and vals[2] != "–"
            expect(pg.locator("#tlw-k1 .kzgt")).to_contain_text("89 % von", timeout=T)
            expect(pg.locator("#tlw-k2 .kzsub a")).to_have_text("Tour 5 hike", timeout=T)
            assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
            _shot(pg, f"kz-seite-{width}-{scheme}.png")
            assert not pg.errors, pg.errors
        finally:
            pg.browser_.close()
