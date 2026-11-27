"""3.63.0 – Reise selbst erstellen (Browser): Dialog (Name, Zeitraum, Touren abhaken), Reise-Seite, Liste, Suche, Bearbeiten, Löschen mit Rückfrage, Vorrang vor erkannten Reisen,
Name leeren entfernt keine Reise, entfernte Reisen mit Hinweis wiederherstellen, 390 px."""
import json
import urllib.request

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.test_core import fresh  # noqa: F401
from tests.test_seitenlayout_ui import T, _api, _browser, pw  # noqa: F401
from tests.test_reise_seiten_ui import TL, _trips_page, _trip, app, clean, _tid  # noqa: F401


def _get(url, path):
    with urllib.request.urlopen(url + path, timeout=10) as r:
        return json.loads(r.read())


def _post(url, path, body, method="POST"):
    req = urllib.request.Request(url + path, method=method, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read() or b"{}")


@pytest.fixture(autouse=True)
def aufraeumen(app):
    def weg():
        for t in _get(app, "/api/trips"):
            if t.get("custom"):
                _post(app, f"/api/trips/{t['id']}", {}, "DELETE")
        for t in _get(app, "/api/trips?hidden=1"):
            _post(app, f"/api/trips/{t['id']}/hide", {"hide": False})
        for t in _get(app, "/api/trips"):
            if t.get("edited"):
                _post(app, f"/api/trips/{t['id']}/edit", {})
    weg()
    yield
    weg()


def _dates(pg, tid):
    return pg.evaluate("(i) => BY[i].date.slice(0, 10)", tid)


def _custom(app):
    return [t for t in _get(app, "/api/trips") if t.get("custom")]


def test_reise_erstellen_dialog_liste_seite_suche(pw, app):
    pg = _trips_page(pw, app)
    try:
        pg.locator("#trnew").click()
        pg.wait_for_selector("#tcn", timeout=T)
        assert pg.locator(".uidlg h2").first.inner_text() == "Reise erstellen"
        pg.fill("#tcn", "Rostock")
        # 3.67.0: nichts ist vorgewählt; erst der Knopf „Markieren“ wählt die Touren des Zeitraums
        pg.wait_for_function("() => document.querySelectorAll('#tcl .cb').length > 20", timeout=T)
        assert pg.locator("#tcl .cb:checked").count() == 0 and "0 Touren gewählt" in pg.locator("#tcc").inner_text()
        pg.locator("#tcok").click()
        assert "mindestens eine Tour" in pg.locator("#tcer").inner_text()
        pg.locator("#tck").click()
        assert "0 Touren gewählt" in pg.locator("#tcc").inner_text()
        pg.fill("#tcs", "Heimrunde 1")
        pg.wait_for_function("() => document.querySelectorAll('#tcl .cb').length === 1", timeout=T)
        pg.locator("#tcl .cb").check()
        pg.fill("#tcs", "Heimrunde 3")
        pg.wait_for_function("() => document.querySelectorAll('#tcl .cb').length === 1", timeout=T)
        pg.locator("#tcl .cb").check()
        pg.fill("#tcs", "")
        assert "2 Touren" in pg.locator("#tcc").inner_text()
        pg.locator("#tcok").click()
        pg.wait_for_selector("#trx #tls-touren", state="attached", timeout=TL)
        assert pg.url.split("#/trip/")[1].startswith("eigen-")
        assert pg.locator("#main h1").inner_text().strip() == "Rostock"
        pg.wait_for_function("() => !!document.querySelector('#trdel') && !!document.querySelector('#trpdf')", timeout=TL)
        assert pg.locator("#tredit").count() == 1 and pg.locator("#trdel").count() == 1 and pg.locator("#trhide").count() == 0 and pg.locator("#trpdf").count() == 1
        c = _custom(app)
        assert len(c) == 1 and c[0]["region"] == "Rostock" and sorted(c[0]["tours"]) == ["h1", "h3"]
        # Liste und Suche
        pg.goto(f"{app}/#/trips")
        pg.wait_for_function("() => [...document.querySelectorAll('#rsx .otd b')].some(b => b.textContent === 'Rostock')", timeout=TL)
        pg.goto(f"{app}/#/search?q=Rostock")
        pg.wait_for_function("() => !!document.querySelector('#sreisen a.otd')", timeout=TL)
        assert "Rostock" in pg.locator("#sreisen").inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_bearbeiten_und_loeschen_mit_rueckfrage(pw, app):
    cid = _post(app, "/api/trips", {"name": "Ostsee", "tours": ["h0", "h1"]})["id"]
    pg = _browser(pw, app, devs=None)
    try:
        pg.goto(f"{app}/#/trip/{cid}")
        pg.wait_for_selector("#trx #tls-touren", state="attached", timeout=TL)
        pg.wait_for_function("() => !!document.querySelector('#trdel') && !!document.querySelector('#tredit')", timeout=TL)
        pg.locator("#tredit").click()
        pg.wait_for_selector("#tcn", timeout=T)
        assert pg.locator("#tcn").input_value() == "Ostsee" and pg.locator("#tcl .cb:checked").count() == 2 and "2 Touren" in pg.locator("#tcc").inner_text()
        pg.fill("#tcn", "Ostsee 2026")
        pg.locator("#tcl .cb:checked").first.uncheck()
        pg.locator("#tcok").click()
        pg.wait_for_function("() => document.querySelector('#main h1') && document.querySelector('#main h1').textContent.trim() === 'Ostsee 2026'", timeout=TL)
        assert len(_custom(app)[0]["tours"]) == 1
        # leerer Name im Dialog: Hinweis, nichts gespeichert
        pg.locator("#tredit").click()
        pg.fill("#tcn", "")
        pg.locator("#tcok").click()
        assert "Name" in pg.locator("#tcer").inner_text()
        pg.locator("#tcno").click()
        assert _custom(app)[0]["region"] == "Ostsee 2026"
        # Löschen: Abbrechen behält, Löschen entfernt
        pg.locator("#trdel").click()
        pg.wait_for_selector(".uidlg .uidanger", timeout=T)
        assert pg.locator(".uidlg h2").inner_text() == "„Ostsee 2026“ löschen?"
        pg.get_by_role("button", name="Abbrechen").click()
        assert len(_custom(app)) == 1
        pg.locator("#trdel").click()
        pg.locator(".uidlg .uidanger").click()
        pg.wait_for_function("() => location.hash === '#/trips'", timeout=T)
        assert _custom(app) == []
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_eigene_reise_hat_vorrang_keine_doppelten_touren(pw, app):
    gom = _get(app, "/api/trips")
    g = next(t for t in gom if t["region"].startswith("La Gomera") and not t.get("custom"))
    n0 = len(g["tours"])
    cid = _post(app, "/api/trips", {"name": "Gomera-Ende", "tours": [g["tours"][-1], g["tours"][-2]]})["id"]
    trips = _get(app, "/api/trips")
    alle = [i for t in trips for i in t["tours"]]
    assert len(alle) == len(set(alle))
    assert len(next(t for t in trips if t["id"] == g["id"])["tours"]) == n0 - 2
    pg = _trips_page(pw, app)
    try:
        assert pg.evaluate("() => [...document.querySelectorAll('#rsx .otd b')].filter(b => b.textContent === 'Gomera-Ende').length") == 1
        # im Dialog einer zweiten eigenen Reise sind diese Touren gesperrt
        pg.locator("#trnew").click()
        pg.wait_for_selector("#tcn", timeout=T)
        pg.wait_for_function("() => document.querySelectorAll('#tcl .cb:disabled').length === 2", timeout=T)
        assert "in eigener Reise „Gomera-Ende“" in pg.locator("#tcl").inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    _post(app, f"/api/trips/{cid}", {}, "DELETE")
    assert len(next(t for t in _get(app, "/api/trips") if t["id"] == g["id"])["tours"]) == n0


def test_name_leeren_entfernt_keine_reise(pw, app):
    pg = _trip(pw, app)
    try:
        pg.locator("#tredit").click()
        pg.wait_for_selector("#tn", timeout=T)
        pg.fill("#tn", "Mein Gomera")
        pg.locator("#tok").click()
        pg.wait_for_function("() => /Mein Gomera/.test(document.querySelector('#main h1').textContent)", timeout=TL)
        pg.locator("#tredit").click()
        pg.fill("#tn", "")
        pg.locator("#tok").click()
        assert pg.locator("#tn").input_value() == "La Gomera" and "Name war leer" in pg.locator("#ter").inner_text()
        pg.locator("#tok").click()                                          # zweites Speichern übernimmt den automatischen Namen
        pg.wait_for_function("() => document.querySelector('#main h1') && !/Mein Gomera/.test(document.querySelector('#main h1').textContent)", timeout=TL)
        assert any(t["region"].startswith("La Gomera") for t in _get(app, "/api/trips"))
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_entfernte_reisen_hinweis_und_wiederherstellen(pw, app):
    tid = _tid(app)
    pg = _trip(pw, app)
    try:
        pg.locator("#trhide").click()
        pg.get_by_role("button", name="Entfernen").click()
        pg.wait_for_function("() => location.hash === '#/trips'", timeout=T)
        pg.wait_for_selector("#trrest", timeout=TL)
        assert pg.locator("#trrest").inner_text().strip() == "1 entfernte Reise – wiederherstellen …"
        pg.locator("#trrest").click()
        pg.wait_for_selector(".uidlg [data-rt]", timeout=T)
        assert "La Gomera" in pg.locator(".uidlg").inner_text()
        pg.locator(".uidlg [data-rt]").click()
        pg.wait_for_function("() => !document.querySelector('#trrest') && [...document.querySelectorAll('#rsx .otd b')].some(b => b.textContent.startsWith('La Gomera'))", timeout=TL)
        assert tid in [t["id"] for t in _get(app, "/api/trips")]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_mobil_390_dialog_ohne_seitliches_scrollen(pw, app, scheme):
    pg = _trips_page(pw, app, width=390, height=900, scheme=scheme)
    try:
        pg.locator("#trnew").click()
        pg.wait_for_selector("#tcn", timeout=T)
        pg.wait_for_function("() => document.querySelectorAll('#tcl .cb').length >= 1", timeout=T)
        assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert pg.evaluate("() => { const b = document.querySelector('.uidlg .uibox').getBoundingClientRect(); return b.left >= 0 && b.right <= window.innerWidth + 1; }")
        assert pg.locator("#tcok").is_visible() and pg.locator("#tcno").is_visible()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_api_eigene_reise_pdf_und_reise_seite(pw, app):
    cid = _post(app, "/api/trips", {"name": "PDF-Reise", "tours": ["h0", "h1"]})["id"]
    with urllib.request.urlopen(f"{app}/api/trips/{cid}/pdf", timeout=60) as r:
        assert r.read(4) == b"%PDF"
