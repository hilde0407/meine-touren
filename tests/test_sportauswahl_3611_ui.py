"""3.61.1 Sportart-Auswahl (Leitfaden 2.6, Muster „Filtern“): im Auswahlfeld nur der Gruppenname ohne „= A + B + …“ (Zusammensetzung im Tooltip), keine Einrückung per Leerzeichen;
am Handy (390 px) öffnet das Feld ein kompaktes Blatt mit Chips (44 px hoch, keine abgeschnittenen Texte, Reihenfolge wie im Feld), die Wahl filtert die Tourenliste; am Computer bleibt das native Feld.
Die Zuweisen-Auswahl (sportWahlHtml) läuft im Handy-Format ohne Überlauf."""
import pytest
from playwright.sync_api import expect

from tests.test_bausteine_ui import T, _browser, _shot  # noqa: F401
from tests.test_bausteine_ui import app, pw  # noqa: F401  (Fixtures)


GRP = {"gruppen": [{"id": "wg", "name": "Wandern (gesamt)", "sports": ["hike", "mountaineering", "snowshoe"]},
                   {"id": "rg", "name": "Rad fahren (gesamt)", "sports": ["touringbicycle", "mtb", "gravel", "e_touringbicycle"]}]}


def _liste(pw, app, **kw):
    pg = _browser(pw, app, **kw)
    pg.route("**/api/stats/gruppen", lambda r: r.fulfill(json=GRP))                                           # feste Statistik-Gruppen (lange Beschriftung „Name = A + B + …“)
    pg.goto(f"{app}/#/tours")
    pg.wait_for_selector("#tl a.tr", timeout=T)
    return pg


def test_feld_nur_gruppenname_ohne_einrueckung(pw, app):
    pg = _liste(pw, app, width=1280, height=900)
    try:
        r = pg.evaluate("""() => ({opts: [...document.querySelectorAll('#fs option')].map(o => [o.value, o.textContent, o.title]),
          groups: [...document.querySelectorAll('#fs optgroup')].map(g => g.label)})""")
        assert r["opts"][0][1] == "Alle Sportarten" and r["groups"][0] == "Statistik-Gruppen", r              # Regel 6: Reihenfolge
        sg = [o for o in r["opts"] if o[0].startswith("sgrp:")]
        assert sg, r
        for _, text, title in sg:
            assert "=" not in text and "+" not in text and len(text) <= 28, text                               # nur der Name
            assert "=" in title, title                                                                         # Zusammensetzung im Tooltip
        assert all(o[1] == o[1].strip() and " " not in o[1] for o in r["opts"]), r
        expect(pg.locator("#fs")).to_be_visible(timeout=T)
        assert pg.locator(".spsheet").count() == 0
        pg.locator("#fs").click()                                                                              # Computer: natives Feld, kein Blatt
        assert pg.locator(".spsheet").count() == 0
    finally:
        pg.browser_.close()


def test_handy_blatt_kompakt_und_filtert(pw, app):
    pg = _liste(pw, app, width=390, height=844)
    try:
        assert pg.evaluate("() => document.documentElement.classList.contains('mob')")
        vorher = pg.evaluate("() => +document.querySelector('#cnt').textContent.match(/^\\d+/)[0]")
        pg.locator("#fs").click()
        expect(pg.locator(".spsheet")).to_be_visible(timeout=T)
        r = pg.evaluate("""() => { const b = document.querySelector('.spsheet').getBoundingClientRect();
          const c = [...document.querySelectorAll('.spsheet .chip')].map(e => { const q = e.getBoundingClientRect(); return [e.textContent, Math.round(q.height), e.scrollWidth > e.clientWidth + 1, q.right <= b.right + 1]; });
          return {c, w: Math.round(b.width), sw: document.documentElement.scrollWidth, first: document.querySelector('.spsheet').firstElementChild.textContent}; }""")
        assert r["first"] == "Alle Sportarten" and len(r["c"]) >= 4, r
        assert all(h == 44 or h >= 44 for _, h, _, _ in r["c"]) and all(h <= 60 for _, h, _, _ in r["c"]), r["c"]     # eine Zeile je Chip
        assert not any(o for _, _, o, _ in r["c"]) and all(i for _, _, _, i in r["c"]), r["c"]                 # nichts abgeschnitten
        assert r["sw"] <= 391, r
        _shot(pg, "sportblatt-390.png", full=False)
        sport = pg.evaluate("() => document.querySelector('.spsheet .chip[data-v]:not([data-v=\"\"]):not([data-v^=\"sgrp:\"])').dataset.v")
        pg.locator(f'.spsheet .chip[data-v="{sport}"]').click()
        expect(pg.locator(".spsheet")).to_have_count(0, timeout=T)
        assert pg.locator("#fs").input_value() == sport
        erw = pg.evaluate("(v) => TOURS.filter(t => sNorm(t.sport) === v).length", sport)
        assert 0 < erw <= vorher, (erw, vorher)
        pg.wait_for_function("(n) => document.querySelector(\"#cnt\").textContent.startsWith(n + \" Touren\")", arg=str(erw), timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_handy_zuweisen_ohne_ueberlauf(pw, app):
    pg = _browser(pw, app, width=390, height=844)
    try:
        pg.goto(f"{app}/#/tour/r3")
        pg.wait_for_selector("#main", timeout=T)
        pg.evaluate("() => document.body.insertAdjacentHTML('beforeend', '<div id=\"zz\" style=\"padding:0 16px\"></div>')")
        pg.evaluate("() => { document.querySelector('#zz').innerHTML = sportWahlHtml('wandern', {id: 'zzs', moreId: 'zzm'}); document.querySelector('#zzm').open = true; }")
        r = pg.evaluate("""() => [...document.querySelectorAll('#zz [data-sp]')].map(e => { const q = e.getBoundingClientRect(); return [Math.round(q.height), e.scrollWidth > e.clientWidth + 1, q.right <= 391]; })""")
        assert r and all(h >= 44 for h, _, _ in r) and not any(o for _, o, _ in r) and all(i for _, _, i in r), r
    finally:
        pg.browser_.close()
