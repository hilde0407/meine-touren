"""3.72.0 – Textfilter und Sortierung der Tourenliste stehen in der Adresse (#/tours?q=…&so=…&g=…): Neuladen, Zurück-Taste und geteilter Link erhalten sie;
bisherige Parameter (?g=, Kennzahl-Filter) bleiben gültig; die Eingabe legt keine Einträge im Verlauf an (replaceState, entprellt)."""
import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.helpers_ui import settled  # noqa: E402
from tests.test_audit_371_ui import app, _page  # noqa: F401, E402
from tests.test_seitenlayout_ui import T, pw  # noqa: F401, E402


def _rows(pg):
    return pg.evaluate("() => document.querySelectorAll('#tl .tr, #tl > a, #tl > div:not(.empty)').length")


def test_filter_in_der_adresse_neuladen_link_und_verlauf(pw, app):
    pg = _page(pw, app, "tours", 1100, "light", "#q")
    try:
        pg.evaluate("() => sessionStorage.clear()")
        pg.goto(f"{app}/#/tours")
        pg.wait_for_selector("#q", timeout=T)
        n0 = pg.evaluate("() => history.length")
        for ch in "Vorjahr":                                               # Eingabe Zeichen für Zeichen
            pg.type("#q", ch)
        pg.select_option("#so", "km")
        pg.wait_for_function("() => location.hash.includes('q=Vorjahr') && location.hash.includes('so=km')", timeout=T)
        assert pg.evaluate("() => history.length") == n0                  # replaceState: kein Eintrag je Tastendruck
        h = pg.evaluate("() => location.hash")
        assert h.startswith("#/tours?") and "q=Vorjahr" in h and "so=km" in h, h
        z = pg.evaluate("() => document.querySelector('#cnt').textContent")
        # Neuladen in einem frischen Tab (kein sessionStorage): der Link allein stellt den Filter her
        pg2 = pg.context.new_page()
        pg2.goto(app + "/" + h)
        pg2.wait_for_selector("#q", timeout=T)
        settled(pg2)
        assert pg2.input_value("#q") == "Vorjahr" and pg2.input_value("#so") == "km"
        assert pg2.evaluate("() => document.querySelector('#cnt').textContent") == z
        pg2.close()
        # Filter leeren: die Parameter verschwinden wieder
        pg.fill("#q", "")
        pg.select_option("#so", "date")
        pg.wait_for_function("() => location.hash === '#/tours'", timeout=T)
    finally:
        pg.browser_.close()


def test_zurueck_taste_und_bestehende_parameter(pw, app):
    pg = _page(pw, app, "tours?g=alpen", 1100, "light", "#q")
    try:
        assert pg.evaluate("() => document.querySelector('#fg').value") in ("alpen", "")        # ?g= bleibt gültig (leer, wenn dort keine Tour liegt)
        pg.evaluate("() => sessionStorage.clear()")
        pg.goto(f"{app}/#/tours?q=Vorjahr&so=old")
        pg.wait_for_selector("#q", timeout=T)
        settled(pg)
        assert pg.input_value("#q") == "Vorjahr" and pg.input_value("#so") == "old"
        pg.click("#tl a >> nth=0")
        pg.wait_for_function("() => location.hash.startsWith('#/tour/')", timeout=T)
        pg.go_back()
        pg.wait_for_selector("#q", timeout=T)
        settled(pg)
        assert pg.input_value("#q") == "Vorjahr" and pg.input_value("#so") == "old"
        assert "q=Vorjahr" in pg.evaluate("() => location.hash")
        # Kennzahl-Parameter bleiben beim Tippen erhalten
        pg.goto(f"{app}/#/tours?kz=Test&minkm=1")
        pg.wait_for_selector("#q", timeout=T)
        pg.fill("#q", "x")
        pg.wait_for_function("() => location.hash.includes('q=x')", timeout=T)
        h = pg.evaluate("() => location.hash")
        assert "kz=Test" in h and "minkm=1" in h, h
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
