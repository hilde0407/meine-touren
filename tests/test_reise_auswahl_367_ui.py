"""3.67.0 – Reise erstellen/bearbeiten: Auswahl der Touren (Browser): nichts vorgewählt, nach Tag/Gebiet gruppiert (neueste zuerst), Zeitraum markieren, Gruppenkopf (auch teilweise gewählt),
Suche, Alle/Keine, Summenzeile (Anzahl · Zeitraum · Gebiete), Warnungen (Länder, Entfernung, viele Gebiete, Lücken über 14 Tage), „in Reise X“, 390 px."""
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.test_core import fresh  # noqa: F401
from tests.test_seitenlayout_ui import T, _api, _browser, pw  # noqa: F401
from tests.test_reise_seiten_ui import TL, _trips_page, app, clean  # noqa: F401
from tests.test_reise_erstellen_363_ui import _get, _post, aufraeumen  # noqa: F401

def _tag(zurueck):
    """3.71.1: Die Testtouren liegen relativ zu heute (Reise „La Gomera“ beginnt 40 Tage zurück, die Heimrunde h0 20 Tage zurück); die Daten der Prüfungen daher auch relativ – feste Daten brachen am Folgetag."""
    return datetime.now(timezone.utc).replace(hour=9, minute=0, second=0, microsecond=0) - timedelta(days=zurueck)


def _iso(zurueck):
    return _tag(zurueck).strftime("%Y-%m-%d")


def _dmy(zurueck):
    return _tag(zurueck).strftime("%d.%m.")


WOCHENTAGE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
MONATE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"]


GOM = ["r0_0_0", "r0_1_0", "r0_1_1", "r0_2_0", "r0_3_0", "r0_4_0", "r0_5_0"]


def _dialog(pw, app, **kw):
    pg = _trips_page(pw, app, **kw)
    pg.locator("#trnew").click()
    pg.wait_for_selector("#tcn", timeout=T)
    pg.wait_for_function("() => document.querySelectorAll('#tcl .cb').length > 20", timeout=T)
    return pg


def _summe(pg):
    return pg.locator("#tcc").inner_text().strip()


def test_nichts_vorgewaehlt_gruppiert_nach_tag_neueste_zuerst(pw, app):
    pg = _dialog(pw, app)
    try:
        assert pg.locator("#tcl .cb:checked").count() == 0 and _summe(pg) == "0 Touren gewählt"
        assert pg.locator("#tcw .tcw").count() == 0
        # Zeitraumfelder bleiben leer; eine Änderung wählt nichts
        assert pg.locator("#tcf").input_value() == "" and pg.locator("#tct").input_value() == ""
        pg.fill("#tcf", _iso(40)); pg.fill("#tct", _iso(35))
        pg.locator("#tcf").dispatch_event("change"); pg.locator("#tct").dispatch_event("change")
        assert pg.locator("#tcl .cb:checked").count() == 0
        # Gruppen = Tage, neueste zuerst; der zweite Tag der Reise (39 Tage zurück) hat zwei Touren
        tage = pg.evaluate("() => [...document.querySelectorAll('#tcl .tcg')].map(g => g.dataset.k)")
        assert tage == sorted(tage, reverse=True) and tage[0] == _iso(20) and len(tage) == len(set(tage))
        g19 = pg.locator(f'#tcl .tcg[data-k="{_iso(39)}"]')
        assert g19.locator(".tcr").count() == 2 and "2 Touren" in g19.locator(".tch").inner_text()
        z = pg.locator('#tcl .tcr:has(.cb[data-i="r0_0_0"])')
        txt = z.inner_text()
        assert _tag(40).strftime("%d.%m.%Y") in txt and "La Gomera Tag 1" in txt and "Spanien" in txt and re.search(r"\d+,\d\s*km", txt)
        assert pg.locator(f'#tcl .tcg[data-k="{_iso(39)}"] .tch').inner_text().startswith(f"{WOCHENTAGE[_tag(39).weekday()]}, {_tag(39).day}. {MONATE[_tag(39).month - 1]} {_tag(39).year}")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_zeitraum_markieren_summe_und_gruppenkopf(pw, app):
    pg = _dialog(pw, app)
    try:
        pg.locator("#tcz").click()
        assert "Anfang und Ende" in pg.locator("#tcer").inner_text()
        pg.fill("#tcf", _iso(35)); pg.fill("#tct", _iso(40))
        pg.locator("#tcz").click()
        assert "Ende liegt vor dem Beginn" in pg.locator("#tcer").inner_text()
        pg.fill("#tcf", _iso(40)); pg.fill("#tct", _iso(35))
        pg.locator("#tcz").click()
        assert pg.locator("#tcl .cb:checked").count() == 7 and pg.locator("#tcer").inner_text() == ""
        s = _summe(pg)
        assert re.match(rf"7 Touren · {re.escape(_dmy(40))}(\d{{4}})?–{re.escape(_dmy(35))}(\d{{4}})? · La Gomera", s), s
        assert "7 Touren im Zeitraum markiert" in s
        # ein Tag teilweise: Kopf zeigt „gemischt“, ein Klick wählt den ganzen Tag, ein zweiter nimmt ihn heraus
        pg.locator('#tcl .cb[data-i="r0_1_1"]').uncheck()
        kopf = pg.locator(f'#tcl .tcg[data-k="{_iso(39)}"] .cg')
        assert kopf.evaluate("c => c.indeterminate") and "1 gewählt" in pg.locator(f'#tcl .tcg[data-k="{_iso(39)}"] .tch').inner_text()
        assert _summe(pg).startswith("6 Touren")
        kopf.click()
        assert pg.locator(f'#tcl .tcg[data-k="{_iso(39)}"] .cb:checked').count() == 2 and kopf.is_checked() and not kopf.evaluate("c => c.indeterminate")
        kopf.click()
        assert pg.locator(f'#tcl .tcg[data-k="{_iso(39)}"] .cb:checked').count() == 0 and not kopf.is_checked()
        assert _summe(pg).startswith("5 Touren")
        # eine Gruppe wählen, ohne dass die Liste springt: Bildlauf bleibt
        pg.evaluate("() => (document.querySelector('#tcl').scrollTop = 700)")
        pg.evaluate("""() => { const l = document.querySelector('#tcl').getBoundingClientRect(); [...document.querySelectorAll('#tcl .cb:not(:checked)')].find(c => { const r = c.getBoundingClientRect(); return r.top > l.top + 5 && r.bottom < l.bottom - 5; }).click(); }""")
        assert pg.evaluate("() => document.querySelector('#tcl').scrollTop") == 700 and _summe(pg).startswith("6 Touren")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_suche_alle_keine_und_gruppe_nach_gebiet(pw, app):
    pg = _dialog(pw, app)
    try:
        pg.fill("#tcs", "Südtirol")
        pg.wait_for_function("() => document.querySelectorAll('#tcl .cb').length === 6", timeout=T)
        pg.locator("#tca").click()
        assert _summe(pg).startswith("6 Touren")
        pg.fill("#tcs", "Gran Canaria")                                     # Alle/Keine wirken nur auf die gefilterte Liste
        pg.wait_for_function("() => document.querySelectorAll('#tcl .cb').length === 6", timeout=T)
        pg.locator("#tca").click()
        assert _summe(pg).startswith("12 Touren")
        pg.locator("#tck").click()
        assert _summe(pg).startswith("6 Touren")
        pg.fill("#tcs", "gibtesnicht")
        assert "Keine Tour passt zur Suche" in pg.locator("#tcl").inner_text()
        pg.fill("#tcs", "")
        # nach Gebiet gruppieren: eine Gruppe je Gebiet, Kopf wählt alle Touren des Gebiets
        pg.locator("#tcgg").click()
        assert pg.locator("#tcgg").get_attribute("aria-pressed") == "true" and pg.locator("#tcgt").get_attribute("aria-pressed") == "false"
        keys = pg.evaluate("() => [...document.querySelectorAll('#tcl .tcg')].map(g => g.dataset.k)")
        assert {"La Gomera", "Südtirol", "Gran Canaria"} <= set(keys)
        pg.locator('#tcl .tcg[data-k="La Gomera"] .cg').click()
        assert _summe(pg).startswith("13 Touren")
        assert pg.locator('#tcl .tcg[data-k="La Gomera"] .cb:checked').count() == 7
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_warnungen_land_luecke_und_hinweis_erkannte_reise(pw, app):
    pg = _dialog(pw, app)
    try:
        # eine erkannte Reise: Touren tragen „in Reise …“, Hinweis auf den Wechsel, aber keine Warnung zur Lage
        pg.fill("#tcs", "La Gomera Tag 1")
        pg.wait_for_function("() => document.querySelectorAll('#tcl .cb').length === 1", timeout=T)
        assert "in Reise „La Gomera“" in pg.locator("#tcl").inner_text()
        pg.locator("#tcl .cb").check()
        w = pg.locator("#tcw").inner_text()
        assert "1 Tour gehört zu der Reise „La Gomera“ und wechselt beim Speichern" in w and "wirklich eine Reise" not in w
        pg.fill("#tcs", "")
        # Spanien + Italien: Länder-Warnung, nicht blockierend (Speichern geht)
        pg.fill("#tcf", _iso(100)); pg.fill("#tct", _iso(96))
        pg.locator("#tcz").click()
        w = pg.locator("#tcw").inner_text()
        assert "2 Ländern" in w and "wirklich eine Reise?" in w, w
        assert "Tage ohne gewählte Tour" in w                               # 19.08. bis 18.10.: 60 Tage
        pg.fill("#tcn", "Mix")
        pg.locator("#tcok").click()
        pg.wait_for_function("() => location.hash.startsWith('#/trip/eigen-')", timeout=TL)
        assert len([t for t in _get(app, "/api/trips") if t.get("custom")]) == 1
        # Gesamtlauf der Auswertung mit Ersatzdaten: drei Gebiete im selben Land, nah beieinander, ohne Lücke
        r = pg.evaluate("""() => { const mk = (d, n, lat) => ({date: d, g_state: n, g_country: 'Spanien', lat, lng: -15}); return tripAuswahlInfo([mk('2026-01-01', 'A', 28), mk('2026-01-03', 'B', 28.1), mk('2026-01-20', 'C', 28.2)]); }""")
        assert r["geb"] == ["A", "B", "C"] and r["laender"] == ["Spanien"] and r["fern"] < 300 and r["luecken"] == [{"von": "2026-01-03", "bis": "2026-01-20", "tage": 17}]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_warnung_drei_gebiete_und_entfernung(pw, app):
    pg = _dialog(pw, app)
    try:
        pg.evaluate("""() => { window._t = (n, lat) => ({date: '2026-01-0' + n, g_state: 'G' + n, g_country: 'Spanien', lat, lng: -15}); }""")
        a = pg.evaluate("() => tripAuswahlInfo([_t(1, 28), _t(2, 28.1), _t(3, 28.2)])")
        assert len(a["geb"]) == 3 and a["fern"] < 100
        b = pg.evaluate("() => tripAuswahlInfo([_t(1, 28), _t(2, 40)])")
        assert b["fern"] > 300
        assert re.fullmatch(r"01\.01\.(2026)?–03\.01\.(2026)?", pg.evaluate("() => tripZeitraumText('2026-01-01', '2026-01-03')"))
        assert pg.evaluate("() => tripZeitraumText('2024-01-01', '2024-01-03')") == "01.01.2024–03.01.2024"
        assert pg.evaluate("() => tripZeitraumText('2024-01-01', '2024-01-01')") == "01.01.2024"
        # die Warntexte stehen im Dialog (nicht blockierend): Quelltext enthält die drei Formulierungen
        src = pg.evaluate("() => tripDialog.toString()")
        for t in ("wirklich eine Reise?", "Gebieten", "Tage ohne gewählte Tour", "auseinander"):
            assert t in src
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_andere_eigene_reise_gesperrt_und_bearbeiten_ohne_vorauswahl(pw, app):
    cid = _post(app, "/api/trips", {"name": "Gomera-Ende", "tours": GOM[:2]})["id"]
    cid2 = _post(app, "/api/trips", {"name": "Ostsee", "tours": ["h0", "h1"]})["id"]
    pg = _trips_page(pw, app)
    try:
        pg.locator("#trnew").click()
        pg.wait_for_selector("#tcn", timeout=T)
        pg.wait_for_function("() => document.querySelectorAll('#tcl .cb:disabled').length === 4", timeout=T)
        assert pg.locator("#tcl .tcin", has_text="in eigener Reise „Gomera-Ende“").count() == 2
        pg.fill("#tcf", _iso(40)); pg.fill("#tct", _iso(35))
        pg.locator("#tcz").click()
        assert pg.locator("#tcl .cb:checked").count() == 5 and _summe(pg).startswith("5 Touren")     # gesperrte Touren werden nicht markiert
        pg.locator("#tcno").click()
        # Bearbeiten: nur die Touren der Reise sind gewählt, andere Touren stehen zur Auswahl
        pg.goto(f"{app}/#/trip/{cid2}")
        pg.wait_for_function("() => !!document.querySelector('#tredit')", timeout=TL)
        pg.locator("#tredit").click()
        pg.wait_for_selector("#tcn", timeout=T)
        pg.wait_for_function("() => document.querySelectorAll('#tcl .cb').length > 20", timeout=T)
        assert pg.locator("#tcl .cb:checked").count() == 2 and _summe(pg).startswith("2 Touren")
        assert {x.get_attribute("data-i") for x in pg.locator("#tcl .cb:checked").all()} == {"h0", "h1"}
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
        _post(app, f"/api/trips/{cid}", {}, "DELETE"); _post(app, f"/api/trips/{cid2}", {}, "DELETE")


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_mobil_390_auswahl_ohne_seitliches_scrollen(pw, app, scheme):
    pg = _dialog(pw, app, width=390, height=780, scheme=scheme)
    try:
        pg.fill("#tcf", _iso(100)); pg.fill("#tct", _iso(35))
        pg.locator("#tcz").click()
        assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert pg.evaluate("() => { const b = document.querySelector('.uidlg .uibox'); const r = b.getBoundingClientRect(); return r.left >= 0 && r.right <= window.innerWidth + 1 && b.scrollWidth <= b.clientWidth + 1; }")
        assert pg.evaluate("() => { const l = document.querySelector('#tcl'); return l.scrollWidth <= l.clientWidth + 1; }")
        # Berührungsziele: Zeilen und Köpfe mindestens 44 px hoch, Kontrollkästchen 20 px
        assert pg.evaluate("() => [...document.querySelectorAll('#tcl .tcr, #tcl .tch')].slice(0, 30).every(e => e.getBoundingClientRect().height >= 43)")
        # Summenzeile und Warnung bleiben beim Blättern sichtbar (sticky im Dialog)
        pg.evaluate("() => { const b = document.querySelector('.uidlg .uibox'); b.scrollTop = 120; }")
        r = pg.evaluate("() => { const s = document.querySelector('#tcc').getBoundingClientRect(), b = document.querySelector('.uidlg .uibox').getBoundingClientRect(); return s.top >= b.top - 1 && s.bottom <= b.bottom; }")
        assert r
        assert pg.locator("#tcw .tcw").count() >= 1
        pg.locator("#tcok").scroll_into_view_if_needed()
        assert pg.locator("#tcok").is_visible() and pg.locator("#tcno").is_visible()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_uebersetzungen_vorhanden():
    from pathlib import Path
    neu = (Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "00-i18n-neu.js").read_text(encoding="utf8")
    for t in ("Zeitraum markieren:", "Gruppieren:", "Nach Tag", "Nach Gebiet", "Markieren", "Weitere Touren anzeigen", "Keine Tour passt zur Suche.", "wirklich eine Reise?"):
        assert t in neu, t
