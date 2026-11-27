"""3.63.0 – Mehrtagestouren (#/series/<id>) als anpassbare Seite wie die Reise (Schlüssel „serie“): Standardabschnitte, Foto-Baustein „Fotos“ mit dem Zeitraum der Serie (erste bis letzte Etappe),
Seite anpassen (Verschieben, Ausblenden, Katalog, Einstellungen), eigenes Layout (nicht das der Reise), Diashow starten/teilen (Zeitraum-Link), Neu mischen, Vorlagen, 390 px."""
import json
import urllib.request

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.test_core import fresh  # noqa: F401
from tests.test_seitenlayout_ui import T, _api, _edit, pw  # noqa: F401
from tests.test_reise_seiten_ui import TL, _saved_doc, _done, _chip, app, clean, KEYS as _K  # noqa: F401
from tests.test_bausteine_konfig_ui import click_gear, save_dialog  # noqa: E402
from tests.test_seitenlayout_ui import _browser

SID = "la%20gomera"
STD = ["kopf", "kennzahlen", "stat", "flug", "karte", "fotos", "touren"]
UNITS = "() => [...document.querySelectorAll('#srx #rs-kopf, #srx details.tls')].filter(e => !e.closest('.sl-off')).map(e => e.dataset.tls || 'kopf')"


@pytest.fixture(autouse=True)
def clean_serie(app):
    _api(app, "serie", "DELETE")
    yield
    _api(app, "serie", "DELETE")


def _serie(pw, url, sid=SID, **kw):
    pg = _browser(pw, url, devs=None, **kw)
    pg.goto(f"{url}/#/series/{sid}", timeout=TL)
    pg.wait_for_selector("#srx #tls-touren", state="attached", timeout=TL)
    pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen') && typeof map !== 'undefined' && !!map && !!map._cvFit && !!document.querySelector('#serren')", timeout=TL)
    return pg


def test_serie_standard_sieht_aus_wie_bisher_plus_fotos(pw, app):
    pg = _serie(pw, app)
    try:
        assert pg.evaluate(UNITS) == STD
        assert pg.locator("#main h1").inner_text().strip() == "La Gomera"
        assert "7 Etappen" in pg.locator("#rs-kopf").inner_text()
        assert [f.inner_text().split("\n")[-1] for f in pg.locator("#main .figs .fig").all()] == ["Touren", "Strecke", "Aufstieg", "Abstieg", "Unterwegs", "Tage"]
        assert pg.locator("#tls-touren .tl .trow, #tls-touren .tl a, #tls-touren .tl .row").count() >= 7
        assert pg.locator("#tls-stat .cstat").count() == 1 and pg.locator("#coff, #cofm, #cm").count() == 3
        assert "Etappen" in pg.locator("#tls-touren summary").inner_text()
        # Foto-Baustein „Fotos“: Alle (6 Fotos im Zeitraum der Serie), Diashow starten und teilen
        pg.wait_for_function("() => document.querySelectorAll('#tls-fotos .erb img').length === 6", timeout=TL)
        href = pg.locator("#tls-fotos a.erdia").get_attribute("href")
        assert "from=" in href and "to=" in href, href
        assert pg.locator("#tls-fotos .erdsh").count() == 1 and pg.locator("#tls-fotos .erdsh").inner_text() == "Diashow teilen"
        assert pg.locator("#tls-fotos .erdia").inner_text() == "Diashow starten"
        # Reihenfolge der Aktionen im Kopf: Umbenennen im Kopf (nicht mehr in der Flug-Zeile)
        assert pg.locator("#rs-kopf #serren").count() == 1 and pg.locator("#tls-flug #serren").count() == 0
        assert pg.locator("#slopen").count() == 1 and pg.locator("#slviews").count() == 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_serie_zeitraum_ist_erste_bis_letzte_etappe_und_link_passt(pw, app):
    pg = _serie(pw, app)
    try:
        pg.wait_for_function("() => document.querySelectorAll('#tls-fotos .erb img').length === 6", timeout=TL)
        d = pg.evaluate("() => { const s = seriesTrip(seriesList()[0].id ? seriesList().find(x => x.name === 'La Gomera') : null); return [s.start, s.end, s.tours.length]; }")
        assert d[2] == 7 and d[0] < d[1]
        href = pg.locator("#tls-fotos a.erdia").get_attribute("href")
        assert f"from={d[0]}" in href and f"to={d[1]}" in href, (href, d)
        # Diashow teilen: Zeitraum-Link „ds:<von>..<bis>“ am Server
        pg.evaluate("() => { navigator.share = async x => { window.__shared = x; }; }")
        pg.locator("#tls-fotos .erdsh").click()
        pg.wait_for_function("() => !!window.__shared", timeout=T)
        sh = pg.evaluate("() => window.__shared")
        assert "/s/" in sh["url"] or "/share" in sh["url"] or "ds" in sh["url"] or sh["url"].startswith("http"), sh
        assert sh["title"].startswith("Diashow La Gomera")
        assert "Mehrtagestour" in pg.locator("#tls-fotos .erdsn").inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("mode,n", [("best", 6), ("random", 3), ("recent", 6), ("all", 6)])
def test_serie_foto_baustein_modi(pw, app, mode, n):
    _api(app, "serie", "PUT", {"widgets": [{"id": "wd1", "type": "rdiashow", "cfg": {"mode": mode, "view": "grid", "n": n, "shuffle": True}}]})
    pg = _serie(pw, app)
    try:
        pg.wait_for_function("([n]) => document.querySelectorAll('#tlw-wd1 .erb img').length === n", arg=[n], timeout=TL)
        assert pg.locator("#tlw-wd1 .ernew").count() == 1 and pg.locator("#tlw-wd1 .erdia").count() == 1
        before = pg.evaluate("() => [...document.querySelectorAll('#tlw-wd1 .erf img')].map(i => i.getAttribute('src'))")
        for _ in range(4):
            pg.evaluate("() => { document.querySelector('#tlw-wd1 .erb').firstElementChild._alt = 1; }")
            pg.click("#tlw-wd1 .ernew")
            pg.wait_for_function("() => { const c = document.querySelector('#tlw-wd1 .erb').firstElementChild; return !!c && !c._alt; }", timeout=T)
            pg.wait_for_function("([n]) => document.querySelectorAll('#tlw-wd1 .erb img').length === n", arg=[n], timeout=T)
            now = pg.evaluate("() => [...document.querySelectorAll('#tlw-wd1 .erf img')].map(i => i.getAttribute('src'))")
            assert now != before or mode == "random"
            before = now
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_serie_seite_anpassen_eigenes_layout_katalog_einstellungen(pw, app):
    pg = _serie(pw, app)
    try:
        _edit(pg)
        assert pg.locator(".slit").count() == 7
        assert pg.locator('.slit[data-sl="kopf"] [data-a="eye"]').count() == 0 and pg.locator('.slit[data-sl="kopf"] .slmust').is_visible()
        # Karte „Kennzahlen“ ausblenden, Katalog: nur Reise-Bausteine, nicht die Reisen-Bausteine
        pg.locator('.slit[data-sl="kennzahlen"] [data-a="eye"]').click()
        pg.locator("#slbar [data-a=add]").click()
        pg.wait_for_selector(".slcat .slcard", timeout=T)
        names = pg.locator(".slcat .slcard h3").all_inner_texts()
        assert {"Reise-Kennzahlen", "Strecke je Tag", "Fotos"} <= set(names) and "Reisen-Kennzahlen" not in names and "Reisen je Jahr" not in names, names
        pg.locator('[data-add="rkmtag"]').click()
        pg.wait_for_function("() => !!document.querySelector('#srx [data-wtype=rkmtag] svg.slcol')", timeout=T)
        wid = pg.evaluate("() => document.querySelector('#srx [data-wtype=rkmtag]').dataset.wid")
        assert pg.locator("#srx [data-wtype=rkmtag] svg.slcol rect").count() == 6
        # Einstellungen des Foto-Bausteins (Standardabschnitt „Fotos“): auf „Beste“ stellen
        click_gear(pg, '.slit[data-sl="fotos"] [data-a="cfg"]')
        pg.wait_for_selector(".sldlg form.erform", timeout=T)
        assert pg.locator('.sldlg [name="f1"]').count() == 0
        _chip(pg, "Beste Fotos der Serie").click() if _chip(pg, "Beste Fotos der Serie").count() else pg.locator('.sldlg input[value="best"]').check()
        save_dialog(pg)
        _done(pg)
        doc = _saved_doc(pg, "serie", want=lambda d: d and "kennzahlen" in (d.get("hidden") or []) and any(w["type"] == "rkmtag" for w in d.get("widgets", [])))
        assert doc["hidden"] == ["kennzahlen"] and doc["widgets"][0]["id"] == wid
        assert doc.get("cfg", {}).get("fotos", {}).get("mode") == "best", doc
        assert _api(app, "reise").get("layout") in (None, {}), "das Layout der Reise bleibt unberührt"
        pg.reload()
        pg.wait_for_selector("#srx #tls-touren", state="attached", timeout=TL)
        pg.wait_for_function("() => !!document.querySelector('#srx [data-wtype=rkmtag] svg.slcol')", timeout=TL)
        assert "kennzahlen" not in pg.evaluate(UNITS)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def _cont_wait(pg, url, key, pred):
    c = None
    for _ in range(60):
        c = _api(url, key).get("container")
        if c and pred(c):
            return c
        pg.wait_for_timeout(250)
    raise AssertionError("Server hat den erwarteten Stand nicht erreicht: " + json.dumps(c)[:300])


def test_serie_vorlagen_ansichten_und_standard_wiederherstellen(pw, app):
    pg = _serie(pw, app)
    try:
        _edit(pg)
        pg.locator("#slbar [data-a=views]").click()
        pg.wait_for_selector(".slvws .slvr", timeout=T)
        pg.locator(".slvws").get_by_role("button", name="Aus Vorlage …", exact=True).click()
        pg.wait_for_selector(".slvt .slcard", timeout=T)
        assert pg.locator(".slvt .slcard h3").all_inner_texts() == ["Kompakt", "Mit Fotos", "Tag für Tag"]
        pg.get_by_role("button", name="Kompakt: Als neue Ansicht übernehmen", exact=True).click()
        pg.wait_for_function("() => !document.querySelector('.slvt')", timeout=T)
        pg.wait_for_function("() => slViewName('serie', SL.view.serie) === 'Kompakt'", timeout=T)
        pg.wait_for_function("() => !!document.querySelector('#srx [data-wtype=rkmtag] svg.slcol rect')", timeout=TL)
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('.uidlg') && !document.querySelector('.slvws')", timeout=T)
        c = _cont_wait(pg, app, "serie", lambda c: len(c["views"]) == 2)
        assert [v["name"] for v in c["views"]] == ["Standard", "Kompakt"]
        assert set(c["views"][1]["layout"]["hidden"]) >= {"stat", "flug", "fotos"}
        assert _api(app, "reise").get("container") is None or len(_api(app, "reise")["container"]["views"]) == 1       # Ansichten der Reise unberührt
        pg.locator("#slbar [data-a=more]").click() if pg.locator("#slbar [data-a=reset]").is_hidden() else None
        pg.locator("#slbar [data-a=reset]").click()
        pg.get_by_role("button", name="Standard wiederherstellen").last.click()
        pg.wait_for_function("() => !document.querySelector('[data-wtype]:not(#tlw-fotos)')", timeout=T)
        pg.wait_for_function("() => JSON.stringify([...document.querySelectorAll('#srx #rs-kopf, #srx details.tls')].map(e => e.dataset.tls || 'kopf')) === JSON.stringify(%s)" % json.dumps(STD), timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_serie_ansicht_export_import_seitenschluessel(app):
    """Export/Import und Ansichtscode kennen die Seite „serie“ (Server prüft die Seite)."""
    doc = {"format": "meine-touren-ansicht", "format_version": 1, "page": "serie", "name": "Meine Serie", "layouts": {"serie": {"v": 1, "order": ["kopf", "fotos"], "widgets": [{"id": "wd1", "type": "rdiashow", "cfg": {"mode": "best"}}]}}}
    req = urllib.request.Request(app + "/api/layout/check", method="POST", data=json.dumps(doc).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        j = json.loads(r.read())
    assert j.get("ok") and j.get("page") == "serie", j


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_serie_mobil_390_ohne_seitliches_scrollen(pw, app, scheme):
    pg = _serie(pw, app, width=390, height=900, scheme=scheme)
    try:
        pg.wait_for_function("() => document.querySelectorAll('#tls-fotos .erb img').length === 6", timeout=TL)
        assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1"), pg.evaluate("document.documentElement.scrollWidth")
        assert pg.locator("#tls-fotos .erdsh").is_visible() and pg.locator("#serren").is_visible()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_serie_api_layout(app):
    ok = {"widgets": [{"id": "wk1", "type": "rkennzahl", "cfg": {}}, {"id": "wd1", "type": "rdiashow", "cfg": {"mode": "best"}}], "cfg": {"fotos": {"mode": "all"}}, "order": ["kopf", "karte"]}
    _api(app, "serie", "PUT", ok)
    assert _api(app, "serie")["layout"]["widgets"][0]["type"] == "rkennzahl"
    for bad in ({"widgets": [{"id": "wn1", "type": "rnzahlen", "cfg": {}}]}, {"widgets": [{"id": "wn1", "type": "fkennzahl", "cfg": {}}]}):
        with pytest.raises(urllib.error.HTTPError) as e:
            _api(app, "serie", "PUT", bad)
        assert e.value.code == 400
