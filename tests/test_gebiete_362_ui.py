"""3.62.1 – Gebiete in der Suche (Browser, Chromium): „Gomera“, „Kanaren“, „Lungau“, „Mafate“, „Zillertal“ (Tour ohne Regionsdaten) finden Touren, deren Name und Regionsdaten das Gebiet nicht nennen;
„Südtirol“ findet nur die Provinz Bozen, „Trentino“ die Provinz Trient; Abschnitt „Reisen“ über den Touren (Treffer über Gebiete, Kopfzeile „n Reisen, m Touren, x km“, Link auf die Reise);
Regionszeile der Tourseite mit dem genauesten Gebiet ohne Doppelungen; Prüfbericht im Browser; Handy 390 px ohne seitlichen Überlauf."""
import json
import os
import socket
import subprocess
import sys

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.test_seitenlayout_ui import ROOT, T, _browser, pw  # noqa: F401
from tests.test_reise_seiten_ui import SEED as SEED_REISEN, TRIPS
from tests.test_tourseite_ui import LAUNCH, _wait

# Zusätzliche Einzeltouren (je an einem eigenen Tag, weit auseinander: keine Reise). Regionsdaten wie von Nominatim bei Touren bis 2025 (mit Bezirk) bzw. ab 2026 (ohne Bezirk, hier sogar ohne Zeile).
EXTRA = r'''
def geo(tid, country, state, county, place):
    db.execute("INSERT INTO tour_geo(id,country,state,county,place,ts) VALUES(?,?,?,?,?,0)", (tid, country, state, county, place))
for k, (tid, name, la, ln, g) in enumerate([
    ("x1", "Morgenrunde Alpha", 28.18, -17.27, ("Spanien", "Kanarische Inseln", "Santa Cruz de Tenerife", "Vallehermoso")),
    ("x2", "Gipfeltour Beta", 47.14, 13.67, ("Österreich", "Salzburg", "Bezirk Tamsweg", "Mauterndorf")),
    ("x3", "Sonnenweg Gamma", 46.50, 11.35, ("Italien", "Trentino-Südtirol", "Bozen", "Bozen")),
    ("x4", "Waldweg Delta", 46.07, 11.12, ("Italien", "Trentino-Südtirol", "Trient", "Trient")),
    ("x5", "Talweg Epsilon", -21.07, 55.43, ("Frankreich", "Réunion", "", "Marla")),
    ("x6", "Hüttenweg Zeta", 47.16, 11.86, None),                                   # ab 2026: keine Regionsdaten (Nominatim ohne Bezirk)
    ("x7", "Inselrunde Eta", 28.50, -16.40, ("Spanien", "Kanarische Inseln", "Santa Cruz de Tenerife", "Teneriffa")),
    ("x8", "Seerunde Theta", 47.10, 13.64, ("Österreich", "Salzburg", "Bezirk Tamsweg", "Sankt Michael im Lungau")),
]):
    tour(tid, base - (520 + k * 25) * day, name, 9000, 9000, 300, 280, la, ln)
    if g:
        geo(tid, *g)
'''


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("gb")
    data = tmp / "data"
    code = SEED_REISEN % {"root": str(ROOT), "data": str(data), "trips": TRIPS} + EXTRA
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / "launch.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    pr = subprocess.Popen([sys.executable, str(script)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    yield url
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)


def _suche(pg, app, q):
    pg.goto(f"{app}/#/search?q={q}")
    pg.wait_for_function("(q) => location.hash.includes('search') && document.querySelector('#sres') && !!document.querySelector('#main .sec h2')", arg=q, timeout=T)


def _namen(pg):
    """Namen der Touren in der Trefferliste der Suche (ohne Reisen-Karten)"""
    return pg.evaluate("() => [...document.querySelectorAll('#stouren .tr .nm')].map(e => e.textContent.trim().replace(/\\s+/g, ' '))")


def _warte_reisen(pg):
    pg.wait_for_function("() => !!document.querySelector('#sreisen .otd')", timeout=T)


def test_gomera_kanaren_lungau_mafate_zillertal(pw, app):
    pg = _browser(pw, app, devs=None)
    for q, will in (("Gomera", {"Morgenrunde Alpha"}), ("Kanaren", {"Morgenrunde Alpha", "Inselrunde Eta"}), ("Lungau", {"Gipfeltour Beta", "Seerunde Theta"}), ("Mafate", {"Talweg Epsilon"}),
                    ("Zillertal", {"Hüttenweg Zeta"}), ("Teneriffa", {"Inselrunde Eta"}), ("Tenerife", {"Inselrunde Eta"}), ("lungau", {"Gipfeltour Beta", "Seerunde Theta"})):
        _suche(pg, app, q)
        pg.wait_for_function("(n) => document.querySelectorAll('#stouren .tr').length >= n", arg=len(will), timeout=T)
        namen = set(_namen(pg))
        # die Seed-Reisen tragen den Namen des Gebiets in ihren Regionsdaten (Gomera, Gran Canaria): nur die Einzeltouren x1–x8 prüfen
        assert will <= namen, (q, namen)
        assert not (namen & {"Waldweg Delta", "Sonnenweg Gamma"}) or q in ("Südtirol",), (q, namen)
    assert not pg.errors
    pg.browser_.close()


def test_suedtirol_nur_provinz_bozen(pw, app):
    pg = _browser(pw, app, devs=None)
    _suche(pg, app, "Südtirol")
    pg.wait_for_function("() => document.querySelectorAll('#stouren .tr').length >= 2", timeout=T)
    n = set(_namen(pg))
    assert "Sonnenweg Gamma" in n and "Waldweg Delta" not in n, n                     # Bozen ja, Trient nein (Bundesland „Trentino-Südtirol“ zählt nicht)
    _suche(pg, app, "South Tyrol")
    pg.wait_for_function("() => [...document.querySelectorAll('#stouren .nm')].some(e => e.textContent.includes('Sonnenweg Gamma'))", timeout=T)
    assert "Waldweg Delta" not in set(_namen(pg))
    _suche(pg, app, "Trentino")
    pg.wait_for_function("() => [...document.querySelectorAll('#stouren .nm')].some(e => e.textContent.includes('Waldweg Delta'))", timeout=T)
    n = set(_namen(pg))
    assert "Waldweg Delta" in n and "Sonnenweg Gamma" not in n, n
    _suche(pg, app, "Trient")
    pg.wait_for_function("() => [...document.querySelectorAll('#stouren .nm')].some(e => e.textContent.includes('Waldweg Delta'))", timeout=T)
    assert not pg.errors
    pg.browser_.close()


def test_keine_treffer_text(pw, app):
    pg = _browser(pw, app, devs=None)
    _suche(pg, app, "gibtesnirgends")
    txt = pg.inner_text("#stouren")
    assert "Keine Treffer" in txt and "Gebiet (Gebirge, Tal, Insel)" in txt and "Reisen" in txt
    assert pg.inner_text("#sres").replace("\xa0", " ") == "0 Touren, 0 km"
    pg.wait_for_timeout(500)
    assert pg.locator("#sreisen .otd").count() == 0
    pg.browser_.close()


def test_reisen_abschnitt_ueber_gebiete(pw, app):
    """„Kanaren“ steht in keinem Reisenamen und keiner Regionszeile der Reise-Touren; die Reisen „La Gomera“ und „Gran Canaria“ kommen über die Gebiete ihrer Touren."""
    pg = _browser(pw, app, devs=None)
    _suche(pg, app, "Kanaren")
    _warte_reisen(pg)
    karten = pg.evaluate("() => [...document.querySelectorAll('#sreisen .otd')].map(a => ({h: a.getAttribute('href'), t: a.innerText.replace(/\\s+/g, ' ')}))")
    namen = " | ".join(k["t"] for k in karten)
    assert len(karten) == 2 and "La Gomera" in namen and "Gran Canaria" in namen and "Südtirol" not in namen, karten
    assert all(k["h"].startswith("#/trip/") for k in karten)
    assert pg.inner_text("#sreisen h2") == "Reisen" and pg.locator("#sreisen + #stouren .tl").count() == 1
    kopf = pg.inner_text("#sres").replace("\xa0", " ")
    import re
    m = re.fullmatch(r"2 Reisen, (\d+) Touren, ([\d.,]+) km", kopf)
    assert m, kopf
    assert int(m.group(1)) == len(_namen(pg)) and int(m.group(1)) >= 12            # 6 + 5 + 2 Touren der Reisen plus 2 Einzeltouren (höchstens 200 Zeilen)
    assert pg.evaluate("() => document.querySelector('#sreisen').compareDocumentPosition(document.querySelector('#stouren')) & Node.DOCUMENT_POSITION_FOLLOWING") > 0    # Reisen stehen über den Touren
    # Link: öffnet die Reise
    pg.click("#sreisen .otd >> text=La Gomera")
    pg.wait_for_function("() => location.hash.startsWith('#/trip/')", timeout=T)
    pg.wait_for_function("() => document.querySelector('#main h1, #main h2') && document.querySelector('#main').innerText.includes('La Gomera')", timeout=T)
    assert not pg.errors
    pg.browser_.close()


def test_reisen_nach_name_land_jahr_und_ohne_treffer(pw, app):
    pg = _browser(pw, app, devs=None)
    _suche(pg, app, "Gran Canaria")
    _warte_reisen(pg)
    assert pg.locator("#sreisen .otd").count() == 1 and "Gran Canaria" in pg.inner_text("#sreisen")
    assert pg.inner_text("#sres").replace("\xa0", " ").startswith("1 Reise, ")                    # Einzahl
    _suche(pg, app, "Italien")                                                                       # Land der Reise „Südtirol“
    _warte_reisen(pg)
    assert "Südtirol" in pg.inner_text("#sreisen")
    _suche(pg, app, "Mafate")                                                                        # Einzeltour, keine Reise: kein Abschnitt, Kopfzeile ohne Reisen
    pg.wait_for_function("() => document.querySelectorAll('#stouren .tr').length === 1", timeout=T)
    pg.wait_for_timeout(600)
    assert pg.locator("#sreisen .otd").count() == 0 and pg.inner_text("#sres").replace("\xa0", " ").startswith("1 Tour, ")
    assert not pg.errors
    pg.browser_.close()


def test_region_der_tourseite(pw, app):
    pg = _browser(pw, app, devs=None)

    def zeile(tid):
        pg.goto(f"{app}/#/tour/{tid}")
        pg.wait_for_function("(id) => location.hash.includes(id) && !!document.querySelector('#tname')", arg=tid, timeout=T)
        return pg.evaluate("() => [...document.querySelectorAll('#main > div.mt18 span.mut')].map(e => e.textContent.trim()).find(t => t.startsWith('·') && !/\\d{2}:\\d{2}/.test(t)) || ''")
    assert zeile("x1") == "· Vallehermoso, La Gomera, Kanarische Inseln, Spanien"
    assert zeile("x2") == "· Mauterndorf, Lungau, Salzburg, Österreich"
    z8 = zeile("x8")
    assert z8 == "· Sankt Michael im Lungau, Salzburg, Österreich" and z8.count("Lungau") == 1
    assert zeile("x7") == "· Teneriffa, Kanarische Inseln, Spanien"                                  # nicht „Teneriffa, Teneriffa“
    assert zeile("x3") == "· Bozen, Südtirol, Trentino-Südtirol, Italien"
    z4 = zeile("x4")
    assert "Südtirol" not in z4.replace("Trentino-Südtirol", "")
    assert zeile("x6") == "· Zillertal"                                                                # ohne Regionsdaten (ab 2026): allein die Koordinate bestimmt das Gebiet
    assert not pg.errors
    pg.browser_.close()


def test_bericht_im_browser(pw, app):
    pg = _browser(pw, app, devs=None)
    pg.goto(f"{app}/#/tours")
    pg.wait_for_selector("#q", timeout=T)
    b = pg.evaluate("() => { const r = Gebiete.bericht(TOURS); return {n: r.touren, mit: r.mitGebiet, g: r.gebiete.map(e => e.id), ohne: r.ohneGebiet.map(e => e.land), text: r.text.slice(0, 80), p: Gebiete.pruefen()}; }")
    assert b["p"] == [] and b["n"] >= 20 and b["mit"] >= 15
    assert {"la-gomera", "kanaren", "lungau", "suedtirol", "trentino", "mafate", "reunion", "zillertal"} <= set(b["g"])
    assert "Touren, davon" in b["text"]
    # Der Bericht erzeugt keine Oberfläche
    assert pg.evaluate("() => !document.body.innerText.includes('Gebiete (Touren)')")
    pg.browser_.close()


def test_handy_ohne_ueberlauf(pw, app):
    pg = _browser(pw, app, width=390, height=844, devs=None)
    for q in ("Kanaren", "Südtirol", "gibtesnirgends"):
        _suche(pg, app, q)
        if q == "Kanaren":
            _warte_reisen(pg)
        pg.wait_for_timeout(200)
        assert pg.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1"), q
        assert pg.evaluate("() => [...document.querySelectorAll('#main .otd, #main .tr, #main .sec')].every(e => e.getBoundingClientRect().right <= innerWidth + 1)"), q
    pg.goto(f"{app}/#/tour/x1")
    pg.wait_for_function("() => !!document.querySelector('#tname')", timeout=T)
    assert pg.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")
    assert not pg.errors
    pg.browser_.close()


def test_leitfaden_woerter_in_der_suche(pw, app):
    """Begriffe nach docs/LEITFADEN-BEGRIFFE.md: Sportart, Schlagwörter, Touren – in den neuen Texten der Suche keine verbotenen Wörter"""
    pg = _browser(pw, app, devs=None)
    _suche(pg, app, "gibtesnirgends")
    txt = pg.inner_text("#main")
    for w in ("Aktivität", "Tags", "Distanz", "Dashboard", "Rekord"):
        assert w not in txt, w
    pg.browser_.close()
