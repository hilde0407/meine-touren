"""3.64.0 – Filter „Gebiet“ (Browser, Chromium): Auswahl mit Suchfeld und Liste nach Typ mit Anzahl Touren (nur Gebiete mit Touren) in der Tourenliste und in „Umbenennen nach Regeln“,
Filter kombinierbar, gemerkt wie die übrigen Filter, Adresse #/tours?g=<Kennung>, Tastatur, Baustein „Meistbesuchte Orte“ nach Gebiet, Handy 390 px ohne Überlauf. Die Gebietsgrenzen sind Näherungen."""
import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.test_seitenlayout_ui import T, _browser, pw  # noqa: F401
from tests.test_gebiete_362_ui import app  # noqa: F401  (Daten: Einzeltouren x1–x8 in Lungau, Teneriffa, Südtirol, Trentino, Réunion, Zillertal + drei Reisen)


G = '.gbi:not([data-v=""]):visible'


def _liste(pg, app, hash_="#/tours", width=None):
    pg.goto(f"{app}/{hash_}")
    pg.wait_for_function("() => document.querySelectorAll('#tl .tr').length > 0 && !!document.querySelector('#fg')", timeout=T)


def _namen(pg):
    return pg.evaluate("() => [...document.querySelectorAll('#tl .tr .nm')].map(e => e.textContent.trim().replace(/\\s+/g, ' '))")


def _oeffnen(pg, mobil=False):
    if mobil and pg.locator("#fg").is_hidden():
        pg.click("#fmore")
    pg.click("#fg")
    pg.wait_for_selector(".gbl", timeout=T)


def test_auswahl_nur_gebiete_mit_touren_nach_typ(pw, app):
    pg = _browser(pw, app, devs=None)
    _liste(pg, app)
    o = pg.evaluate("""() => { const s = document.querySelector('#fg');
      return {first: s.options[0].textContent, groups: [...s.querySelectorAll('optgroup')].map(g => g.label), opts: [...s.querySelectorAll('option[value]:not([value=""])')].map(o => [o.value, o.dataset.name, +o.dataset.n, o.textContent]),
              sel: s.value, title: s.title, aria: s.getAttribute('aria-label')}; }""")
    assert o["first"] == "Alle Gebiete" and o["sel"] == "" and o["title"] == "Gebiet" and o["aria"] == "Gebiet"
    assert set(o["groups"]) <= {"Gebirge", "Täler", "Inseln", "Küsten", "Landschaften"} and "Inseln" in o["groups"] and "Landschaften" in o["groups"]
    d = {v: (n, name, txt) for v, name, n, txt in o["opts"]}
    assert d["lungau"][0] == 2 and d["lungau"][2] == "Lungau (2)"
    assert "la-gomera" in d and "kanaren" in d and "mafate" in d and "zillertal" in d and "suedtirol" in d and "trentino" in d
    assert d["kanaren"][0] >= d["la-gomera"][0] + 1                                   # Oberbegriff zählt alle Inseln
    assert "harz" not in d and "wallis" not in d and "sizilien" not in d              # kein Gebiet ohne Touren
    # Anzahl stimmt mit den Touren überein (ohne Doppelzählung je Tour)
    tot = pg.evaluate("() => TOURS.filter(t => Gebiete.von(t).some(v => v.id === 'kanaren')).length")
    assert d["kanaren"][0] == tot
    # alphabetisch je Gruppe
    for g in o["groups"]:
        ns = pg.evaluate("(g) => [...document.querySelectorAll('#fg optgroup')].find(x => x.label === g).children.length && [...[...document.querySelectorAll('#fg optgroup')].find(x => x.label === g).children].map(x => x.dataset.name)", g)
        assert ns == sorted(ns, key=lambda s: s.casefold().replace("ä", "a").replace("ö", "o").replace("ü", "u")) or len(ns) < 2
    assert not pg.errors
    pg.browser_.close()


def test_blatt_suche_waehlen_und_filtern(pw, app):
    pg = _browser(pw, app, devs=None)
    _liste(pg, app)
    alle = len(_namen(pg))
    _oeffnen(pg)
    expect(pg.locator(".gbq")).to_be_focused()                                         # Computer: Suchfeld sofort bedienbar
    assert pg.locator(".uibox h2").inner_text() == "Gebiet"
    assert pg.locator(".gbi.on").inner_text().startswith("Alle Gebiete")
    n0 = pg.locator(G).count()
    pg.fill(".gbq", "lung")
    vis = pg.locator(G)
    assert vis.count() == 1 and vis.inner_text().replace("\n", " ").startswith("Lungau") and vis.inner_text().strip().endswith("2")
    assert pg.locator(".gbnone").is_hidden() and pg.locator(G).count() < n0
    pg.fill(".gbq", "tamsweg")                                                          # Alias findet
    assert pg.locator(G).count() == 1
    pg.fill(".gbq", "KANAREN")                                                          # ohne Groß/Klein, Oberbegriff
    assert pg.locator(G).inner_text().startswith("Kanaren")
    pg.fill(".gbq", "österreich")                                                       # Land (Hinweis in der Zeile) findet
    assert pg.locator(G).count() >= 1 and "Lungau" in pg.locator(G).first.inner_text()
    pg.fill(".gbq", "xyzxyz")
    expect(pg.locator(".gbnone")).to_be_visible()
    assert pg.locator(G).count() == 0 and pg.locator(".gbg:visible").count() == 0 and pg.locator(".gbi:visible").count() == 1       # nur „Alle Gebiete“ bleibt (zum Aufheben)
    pg.fill(".gbq", "")
    assert pg.locator(G).count() == n0
    pg.fill(".gbq", "lungau")
    pg.click(G + " >> text=Lungau")
    pg.wait_for_selector(".gbl", state="detached", timeout=T)
    assert pg.input_value("#fg") == "lungau"
    expect(pg.locator("#cnt")).to_contain_text("2 Touren")
    assert sorted(_namen(pg)) == ["Gipfeltour Beta", "Seerunde Theta"]
    assert pg.inner_text("#fcnt") == "1"
    # kombinierbar mit Sportart und Jahr: weniger oder gleich viele, nie mehr
    pg.select_option("#fg", "kanaren")
    n_k = len(_namen(pg))
    assert n_k >= 8
    pg.select_option("#fs", "touringbicycle")
    n_r = len(_namen(pg))
    assert 0 < n_r < n_k
    pg.select_option("#fs", "")
    pg.select_option("#fr", "c|Spanien")
    assert len(_namen(pg)) == n_k                                                       # Land und Gebiet zusammen
    assert pg.inner_text("#fcnt") == "2"
    pg.select_option("#fr", "")
    pg.select_option("#fg", "")
    assert len(_namen(pg)) == alle
    assert not pg.errors
    pg.browser_.close()


def test_filter_wird_gemerkt_und_adresse(pw, app):
    pg = _browser(pw, app, devs=None)
    _liste(pg, app)
    pg.select_option("#fg", "mafate")
    assert _namen(pg) == ["Talweg Epsilon"]
    pg.goto(f"{app}/#/dash")
    pg.wait_for_function("() => location.hash === '#/dash' && !document.querySelector('#fg')", timeout=T)
    pg.goto(f"{app}/#/tours")
    pg.wait_for_function("() => !!document.querySelector('#fg') && document.querySelector('#fg').value !== undefined", timeout=T)
    pg.wait_for_function("() => document.querySelector('#fg').value === 'mafate'", timeout=T)       # wie die übrigen Filter: für diese Sitzung gemerkt
    assert _namen(pg) == ["Talweg Epsilon"]
    # Adresse: #/tours?g=<Kennung> startet mit genau diesem Filter (die übrigen Filter leer)
    pg.select_option("#fy", "2020") if pg.locator("#fy option[value='2020']").count() else None
    pg.goto(f"{app}/#/tours?g=lungau")
    pg.wait_for_function("() => document.querySelector('#fg') && document.querySelector('#fg').value === 'lungau'", timeout=T)
    assert sorted(_namen(pg)) == ["Gipfeltour Beta", "Seerunde Theta"] and pg.input_value("#fr") == "" and pg.input_value("#fy") == "0"
    pg.goto(f"{app}/#/tours?g=gibtesnicht")                                              # unbekannt: alle Gebiete, kein Fehler
    pg.wait_for_function("() => document.querySelector('#fg') && document.querySelector('#fg').value === '' && document.querySelectorAll('#tl .tr').length > 3", timeout=T)
    pg.goto(f"{app}/#/tours?g=%3Cimg%20src%3Dx%20onerror%3Dalert(1)%3E")                 # nie als HTML eingesetzt
    pg.wait_for_function("() => document.querySelector('#fg') && document.querySelectorAll('#tl .tr').length > 3", timeout=T)
    assert pg.input_value("#fg") == "" and not pg.errors
    pg.browser_.close()


def test_tastatur(pw, app):
    pg = _browser(pw, app, devs=None)
    _liste(pg, app)
    pg.focus("#fg")
    pg.keyboard.press("Enter")
    pg.wait_for_selector(".gbl", timeout=T)
    pg.keyboard.type("zillertal")
    pg.keyboard.press("Enter")                                                          # Enter im Suchfeld wählt den ersten Treffer
    pg.wait_for_selector(".gbl", state="detached", timeout=T)
    assert pg.input_value("#fg") == "zillertal" and _namen(pg) == ["Hüttenweg Zeta"]
    expect(pg.locator("#fg")).to_be_focused()                                           # Fokus kehrt zum Feld zurück
    pg.keyboard.press("ArrowDown")
    pg.wait_for_selector(".gbl", timeout=T)
    pg.keyboard.press("Escape")                                                         # Esc schließt ohne Änderung
    pg.wait_for_selector(".gbl", state="detached", timeout=T)
    assert pg.input_value("#fg") == "zillertal"
    pg.click("#fg")
    pg.click(".gbi >> text=Alle Gebiete")
    assert pg.input_value("#fg") == ""
    pg.click("#fg")
    pg.click(".uifoot >> text=Abbrechen")
    assert pg.input_value("#fg") == ""
    assert not pg.errors
    pg.browser_.close()


def test_umbenennen_nach_regeln_und_baustein_orte(pw, app):
    pg = _browser(pw, app, devs=None)
    pg.goto(f"{app}/#/check")
    pg.wait_for_selector("#rn_g", timeout=T)
    assert pg.locator("#rn_g option").first.inner_text() == "Alle Gebiete" and pg.locator("#rn_g option[value='lungau']").inner_text() == "Lungau (2)"
    pg.click("#rn_g")                                                                    # dasselbe Blatt wie in der Tourenliste
    pg.wait_for_selector(".gbl", timeout=T)
    pg.fill(".gbq", "lungau")
    pg.click(G + " >> text=Lungau")
    assert pg.input_value("#rn_g") == "lungau"
    pg.fill("#rn_x", "Z ")
    pg.click("#rn_p")
    expect(pg.locator("#rn_m")).to_have_text("2 Touren betroffen")
    # Baustein „Meistbesuchte Orte“ nach Gebiet: jede Tour einmal, im genauesten Gebiet; Touren ohne Gebiet werden benannt
    t = pg.evaluate("""() => { const c = document.createElement('details'); c.innerHTML = '<summary><span class="tlt">x</span></summary><div class="b"></div>';
      const b = c.querySelector('.b'); SL_WT.orte.render(c, b, {level: 'gebiet'}); const f = SL_WT.orte.fields[0].options.map(o => o[1]);
      const sum = [...b.querySelectorAll('.slr1 b')].reduce((s, e) => s + parseInt(e.textContent), 0);
      return {txt: b.innerText, opts: f, sum, miss: (b.querySelector('.slcap') || {}).textContent || ''}; }""")
    assert "Gebiet" in t["opts"] and t["opts"].index("Gebiet") == t["opts"].index("Bundesland oder Region") + 1
    assert "Lungau" in t["txt"] and "La Gomera" in t["txt"]
    assert "Kanaren" not in t["txt"] and "Alpen" not in t["txt"]                         # nur das genaueste Gebiet, keine Oberbegriffe doppelt
    assert not pg.errors
    pg.browser_.close()


def test_handy_390(pw, app):
    pg = _browser(pw, app, width=390, height=800, devs=None)
    pg.goto(f"{app}/#/tours")
    pg.wait_for_function("() => document.querySelectorAll('#tl .tr').length > 0 && !!document.querySelector('#fg')", timeout=T)
    assert pg.locator("#fg").is_hidden()                                                 # wie Region, Jahr, Bewertung: hinter dem Knopf „Filter“
    pg.click("#fmore")
    expect(pg.locator("#fg")).to_be_visible()
    _oeffnen(pg, mobil=True)
    assert pg.evaluate("() => document.documentElement.classList.contains('mob')")
    expect(pg.locator(".gbq")).not_to_be_focused()                                       # keine Tastatur, die die Liste verdeckt
    box = pg.locator(".uibox").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= 390 and box["y"] >= 0 and box["y"] + box["height"] <= 800
    assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth && document.querySelector('.gbl').scrollWidth <= document.querySelector('.gbl').clientWidth")
    hs = pg.evaluate("() => [...document.querySelectorAll('.gbi:not([hidden])')].map(b => b.getBoundingClientRect().height)")
    assert hs and min(hs) >= 44
    pg.fill(".gbq", "gomera")
    pg.click(G + " >> text=La Gomera")
    pg.wait_for_selector(".gbl", state="detached", timeout=T)
    assert pg.input_value("#fg") == "la-gomera" and pg.inner_text("#fcnt") == "1"
    assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth")
    pg.click("#fclear")                                                                  # „Filter zurücksetzen“ hebt auch das Gebiet auf
    assert pg.input_value("#fg") == "" and pg.locator("#fcnt").is_hidden()
    assert not pg.errors
    pg.browser_.close()
