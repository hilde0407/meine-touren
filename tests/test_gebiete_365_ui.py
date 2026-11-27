"""3.65.0 – Gebiete-Seiten und eigene Gebiete (Browser, Chromium): Gebiet in der Regionszeile (Tourseite, Tourblatt-Funktion, Reise-Seite) als Link auf die Tourenliste mit dem Filter,
Übersicht #/areas (Liste, Suche, Gliederung, Sortierung, Menüpunkt), Seite eines Gebiets #/area/<Kennung> (Kennzahlen, Karte, Touren, Fotos, Reisen), „Gebiet hinzufügen“ mit gespielter Suche
(Treffer, Ausfall der Suche, von Hand), Bearbeiten, Löschen, eigene Gebiete in Filter und Suche, Handy 390 px ohne seitlichen Überlauf. Die Gebietsgrenzen sind Näherungen.
Die Tests laufen in einer festen Reihenfolge: erst nur lesen, dann ein eigenes Gebiet anlegen, ändern und wieder löschen (der Server dieses Moduls ist gemeinsam)."""
import json
import urllib.request

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.test_seitenlayout_ui import T, _api, _browser, pw  # noqa: F401
from tests.test_gebiete_362_ui import app  # noqa: F401  (Daten: Einzeltouren x1–x8 in Lungau (x2, x8), Teneriffa (x7), Gomera (x1), Südtirol, Trentino, Réunion, Zillertal + drei Reisen mit Fotos)

TREFFER = [{"name": "Mein Mauterndorf", "art": "Tal", "typ": "tal", "land": "Österreich", "box": [47.0, 13.6, 47.2, 13.8], "gross": False, "quelle": "Mauterndorf, Salzburg, Österreich"},
           {"name": "Riesenland", "art": "Land", "typ": "region", "land": "Irgendwo", "box": [0.0, 0.0, 40.0, 70.0], "gross": True, "quelle": "Riesenland"}]
OVERFLOW = "() => document.documentElement.scrollWidth <= window.innerWidth + 1"


def _get(app, path):
    with urllib.request.urlopen(app + path, timeout=10) as r:
        return json.loads(r.read())


def _open(pg, app, hash_, sel):
    pg.goto(f"{app}/{hash_}")
    pg.wait_for_selector(sel, timeout=T)


def _namen(pg):
    return pg.evaluate("() => [...document.querySelectorAll('#tl .tr .nm')].map(e => e.textContent.trim().replace(/\\s+/g, ' '))")


def _liste(pg, app, g):
    pg.goto(f"{app}/#/tours?g={g}")
    pg.wait_for_function("() => document.querySelectorAll('#tl .tr').length > 0 && !!document.querySelector('#fg')", timeout=T)


# ------------------------------------------------------------------  Regionszeile  ------------------------------------------------------------------
def test_regionszeile_tourseite_link_auf_die_liste(pw, app):
    pg = _browser(pw, app, devs=None)
    _open(pg, app, "#/tour/x2", "a.gblink")
    a = pg.locator("a.gblink").first
    assert a.get_attribute("href") == "#/tours?g=lungau" and a.inner_text() == "Lungau"
    assert "Österreich" in pg.locator(".tag + .mut + .mut, .tag ~ .mut").last.inner_text()           # die übrigen Teile der Zeile bleiben Text
    a.click()
    pg.wait_for_function("() => document.querySelectorAll('#tl .tr').length > 0", timeout=T)
    assert pg.evaluate("() => location.hash") == "#/tours?g=lungau"
    assert set(_namen(pg)) == {"Gipfeltour Beta", "Seerunde Theta"} and pg.locator("#fg").input_value() == "lungau"
    assert not pg.errors
    pg.browser_.close()


def test_tour_ohne_gebiet_hat_keinen_link_und_tourblatt_nutzt_dieselbe_zeile(pw, app):
    pg = _browser(pw, app, devs=None)
    _open(pg, app, "#/tour/h0", ".tag")
    pg.wait_for_function("() => typeof regionHtml === 'function' && TOURS.length > 0", timeout=T)
    assert pg.locator(".tag ~ a.gblink").count() == 0
    r = pg.evaluate("() => [regionHtml(BY.x2), regionHtml(BY.h0)]")
    assert 'href="#/tours?g=lungau"' in r[0] and "gblink" not in r[1] and "<" not in r[1].replace("&amp;", "")
    src = open("app/static/js/17-tourblatt.js", encoding="utf-8").read()
    assert "regionHtml(t)" in src                                                                         # das Tourblatt zeigt dieselbe Zeile mit Link
    pg.browser_.close()


def test_regionszeile_reise_link(pw, app):
    tid = [t for t in _get(app, "/api/trips") if t["region"] == "La Gomera"][0]["id"]
    pg = _browser(pw, app, devs=None)
    _open(pg, app, f"#/trip/{tid}", ".rsgeb a.gblink")
    a = pg.locator(".rsgeb a.gblink")
    assert a.get_attribute("href") == "#/tours?g=la-gomera" and a.inner_text() == "La Gomera"
    assert not pg.errors
    pg.browser_.close()


# ------------------------------------------------------------------  Übersicht  ------------------------------------------------------------------
def test_uebersicht_liste_suche_gliederung_und_menue(pw, app):
    pg = _browser(pw, app, devs=None)
    _open(pg, app, "#/areas", "#gbl .gbrow")
    assert pg.locator("nav a[data-k=areas].on").count() == 1
    assert pg.locator("h2").first.inner_text() == "Gebiete" and pg.locator("#gbsub").inner_text().endswith("Gebiete")
    rows = pg.evaluate("() => [...document.querySelectorAll('#gbl .gbrow')].map(a => [a.getAttribute('href'), a.querySelector('b').textContent])")
    d = dict(rows)
    assert d["#/area/lungau"] == "Lungau" and "#/area/la-gomera" in d and "#/area/kanaren" in d
    assert "#/area/harz" not in d                                                                          # nur besuchte Gebiete
    lung = pg.locator('#gbl a[href="#/area/lungau"]')
    assert lung.locator(".gbc b").first.inner_text() == "2"                                              # Touren (danach Tage, Strecke, Aufstieg)
    assert pg.evaluate("() => [...document.querySelectorAll('#gbl .gbh')].map(h => h.textContent.replace(/\\s+/g, ' ').trim())")[0].startswith(("Gebirge", "Täler", "Inseln", "Küsten", "Landschaften"))
    # Suche: Alias und Teilwort, ohne Beachtung von Groß/Klein und Akzenten
    pg.fill("#gbq", "lung")
    assert pg.evaluate("() => [...document.querySelectorAll('#gbl .gbrow b')].map(b => b.textContent)").count("Lungau") == 1
    assert pg.locator("#gbl .gbrow").count() < len(rows)
    pg.fill("#gbq", "zzzzzz")
    assert pg.locator(".gbnone").inner_text() == "Kein Gebiet gefunden." and pg.locator("#gbl .gbrow").count() == 0
    pg.fill("#gbq", "")
    # Gliederung nach Land und Sortierung (gemerkt)
    pg.select_option("#gbgr", "land")
    heads = pg.evaluate("() => [...document.querySelectorAll('#gbl .gbh')].map(h => h.textContent.replace(/\\s+/g, ' ').trim())")
    assert any(h.startswith("Österreich") for h in heads) and any(h.startswith("Spanien") for h in heads)
    pg.select_option("#gbso", "n")
    first = pg.evaluate("() => +document.querySelector('#gbl .gbg2 .gbrow .gbc b').textContent.replace(/\\D/g, '')")
    assert first >= 1
    pg.reload()
    pg.wait_for_selector("#gbl .gbrow", timeout=T)
    assert pg.locator("#gbgr").input_value() == "land" and pg.locator("#gbso").input_value() == "n"
    pg.select_option("#gbgr", "typ"); pg.select_option("#gbso", "name")
    # Enter im Suchfeld öffnet den ersten Treffer
    pg.fill("#gbq", "lungau")
    pg.press("#gbq", "Enter")
    pg.wait_for_function("() => location.hash === '#/area/lungau'", timeout=T)
    assert not pg.errors
    pg.browser_.close()


# ------------------------------------------------------------------  Seite eines Gebiets  ------------------------------------------------------------------
def test_gebietsseite_kennzahlen_karte_touren(pw, app):
    pg = _browser(pw, app, devs=None)
    _open(pg, app, "#/area/lungau", "#gdx .gbh1")
    assert pg.locator(".gbh1").inner_text() == "Lungau" and pg.locator("nav a[data-k=areas].on").count() == 1
    pg.wait_for_selector("#cm .leaflet-container, #cm.leaflet-container", timeout=T)
    figs = pg.evaluate("() => [...document.querySelectorAll('#gdx .figs .fig')].map(f => f.textContent.replace(/\\s+/g, ' ').trim())")
    assert figs[0].startswith("2") and "Tour" in figs[0] and any("Strecke" in f for f in figs) and any("Erstes Mal" in f for f in figs)
    assert pg.locator("#gdx .tl .tr").count() == 2 and pg.locator("#gbedit").count() == 0              # eingebaut: nicht bearbeitbar
    assert pg.locator("#gballe").get_attribute("href") == "#/tours?g=lungau"
    assert pg.locator(".back").get_attribute("href") == "#/areas"
    assert "Eingebautes Gebiet" in pg.locator("#gdx").inner_text()
    pg.locator("#gballe").click()
    pg.wait_for_function("() => document.querySelectorAll('#tl .tr').length === 2", timeout=T)
    assert not pg.errors
    pg.browser_.close()


def test_gebietsseite_reisen_fotos_und_unbekanntes_gebiet(pw, app):
    pg = _browser(pw, app, devs=None)
    _open(pg, app, "#/area/la-gomera", "#gdx .gbh1")
    pg.wait_for_selector('#gdx [data-tls="fotos"] img', timeout=T)
    assert pg.locator('#gdx [data-tls="fotos"] img').count() >= 1
    assert pg.locator('#gdx [data-tls="reisen"] .otd, #gdx [data-tls="reisen"] a').count() >= 1       # die Reise nach La Gomera
    assert "Reisen in diesem Gebiet" in pg.locator("#gdx").inner_text()
    pg.goto(f"{app}/#/area/gibt-es-nicht")
    pg.wait_for_function("() => document.body.innerText.includes('Gebiet nicht gefunden')", timeout=T)
    # Gebiet ohne Tour (Harz): Seite mit Hinweis statt Kennzahlen, keine Fehlermeldung des Browsers
    pg.goto(f"{app}/#/area/harz")
    pg.wait_for_selector(".gbleer", timeout=T)
    assert pg.locator(".gbleer").inner_text() == "In diesem Gebiet gibt es noch keine Tour."
    assert not pg.errors
    pg.browser_.close()


def test_fotos_nach_gebiet_ueber_den_server(app):
    gomera = _get(app, "/api/photos?gebiet=la-gomera&limit=100")
    kanaren = _get(app, "/api/photos?gebiet=kanaren&limit=100")
    assert len(gomera) >= 1 and len(kanaren) >= len(gomera) and {p["id"] for p in gomera} <= {p["id"] for p in kanaren}
    assert _get(app, "/api/photos?gebiet=gibt-es-nicht") == [] and len(_get(app, "/api/photos?limit=500")) >= len(kanaren)
    assert all(p["tour_id"].startswith("r0_") for p in gomera)


def test_baustein_fotos_des_gebiets_in_der_seite(pw, app):
    _api(app, "gebiet", "PUT", {"v": 1, "widgets": [{"id": "wg1", "type": "gfotos", "cfg": {"mode": "all", "view": "grid"}}]})
    try:
        pg = _browser(pw, app, devs=None)
        _open(pg, app, "#/area/la-gomera", "#gdx .gbh1")
        pg.wait_for_selector("#gdx .erb img", timeout=T)
        assert pg.locator("#gdx .erb img").count() >= 1
        # ein Gebiet ohne Fotos: ehrlicher Hinweis statt leerer Fläche
        pg.goto(f"{app}/#/area/lungau")
        pg.wait_for_function("() => document.querySelector('#gdx') && document.querySelector('#gdx').innerText.includes('Zu diesem Gebiet gibt es keine Fotos.')", timeout=T)
        assert not pg.errors
        pg.browser_.close()
    finally:
        _api(app, "gebiet", "DELETE")


# ------------------------------------------------------------------  Eigene Gebiete  ------------------------------------------------------------------
def _suchen(pg, app, treffer=None, status=200, detail=None):
    def h(r):
        if r.request.method != "GET":
            return r.fallback()
        if status != 200:
            return r.fulfill(status=status, json={"detail": detail})
        r.fulfill(json=treffer)
    pg.route("**/api/gebiete/suche*", h)


def test_hinzufuegen_suche_ausfall_und_von_hand(pw, app):
    pg = _browser(pw, app, devs=None)
    _open(pg, app, "#/areas", "#gbadd")
    pg.click("#gbadd")
    pg.wait_for_selector("#gbsq", timeout=T)
    expect(pg.locator("#gbsq")).to_be_focused()
    pg.fill("#gbsq", "a")
    pg.click("#gbsb")
    assert pg.locator("#gbsr").inner_text() == "Bitte mindestens zwei Zeichen eingeben."                # kein Aufruf des Servers
    # Suche fällt aus (kein Netz beim Server): Hinweis und der Weg „von Hand“ bleibt, der Name wird mitgenommen
    _suchen(pg, app, status=502, detail="Gebietssuche nicht möglich: nicht erreichbar (ConnectionError)")
    pg.fill("#gbsq", "Mein Mauterndorf")
    pg.click("#gbsb")
    pg.wait_for_function("() => document.querySelector('#gbsr').innerText.includes('von Hand anlegen')", timeout=T)
    assert "Gebietssuche nicht möglich" in pg.locator("#gbsr").inner_text() and pg.locator("#gbsb").is_enabled()
    pg.click("#gbman")
    pg.wait_for_selector("#gbn", timeout=T)
    assert pg.locator("#gbn").input_value() == "Mein Mauterndorf" and pg.locator("#gbN").input_value() == "" and pg.locator("#gbt").input_value() == "region"
    pg.click("#gbok")
    assert pg.locator("#gber").inner_text() == "Bitte ein gültiges Rechteck angeben: Süd kleiner als Nord, West kleiner als Ost."
    pg.fill("#gbS", "48"); pg.fill("#gbN", "47"); pg.fill("#gbW", "13"); pg.fill("#gbE", "14")
    pg.click("#gbok")
    assert "gültiges Rechteck" in pg.locator("#gber").inner_text()
    assert _get(app, "/api/gebiete/eigene") == []
    pg.click("#gbno")
    pg.wait_for_selector(".uimod", state="detached", timeout=T)
    # keine Treffer
    pg.click("#gbadd")
    _suchen(pg, app, [])
    pg.fill("#gbsq", "Nirgendwo"); pg.click("#gbsb")
    pg.wait_for_function("() => document.querySelector('#gbsr').innerText.startsWith('Kein Gebiet gefunden.')", timeout=T)
    pg.keyboard.press("Escape")
    assert not pg.errors
    pg.browser_.close()


def test_hinzufuegen_bearbeiten_filtern_suchen_loeschen(pw, app):
    pg = _browser(pw, app, devs=None)
    _open(pg, app, "#/areas", "#gbadd")
    n0 = pg.locator("#gbl .gbrow").count()
    _suchen(pg, app, TREFFER)
    pg.click("#gbadd")
    pg.fill("#gbsq", "Mauterndorf")
    pg.press("#gbsq", "Enter")
    pg.wait_for_selector(".gbr", timeout=T)
    assert pg.locator(".gbr").count() == 2 and pg.locator(".gbr").nth(1).is_disabled()                  # zu großes Gebiet: nicht wählbar, mit Hinweis
    assert "zu groß" in pg.locator(".gbr").nth(1).inner_text()
    pg.locator(".gbr").first.click()
    pg.wait_for_selector("#gbn", timeout=T)
    assert pg.locator("#gbn").input_value() == "Mein Mauterndorf" and pg.locator("#gbt").input_value() == "tal" and pg.locator("#gbland").input_value() == "Österreich"
    assert [pg.locator(i).input_value() for i in ("#gbS", "#gbW", "#gbN", "#gbE")] == ["47", "13.6", "47.2", "13.8"]
    pg.wait_for_function("() => document.querySelector('#gbcnt').textContent.includes('2 Touren liegen in diesem Rechteck')", timeout=T)
    pg.click("#gbok")
    pg.wait_for_function("() => /^#\\/area\\/eigen-/.test(location.hash)", timeout=T)
    gid = pg.evaluate("() => location.hash.split('/')[2]")
    pg.wait_for_selector("#gdx .gbh1", timeout=T)
    assert pg.locator(".gbh1").inner_text().replace("\n", " ").startswith("Mein Mauterndorf") and pg.locator(".gbh1 .gbeigen").count() == 1
    assert pg.locator("#gdx .tl .tr").count() == 2 and "Eigenes Gebiet" in pg.locator("#gdx").inner_text() and pg.locator("#gbedit").count() == 1
    e = _get(app, "/api/gebiete/eigene")
    assert len(e) == 1 and e[0]["id"] == gid and e[0]["box"] == [47.0, 13.6, 47.2, 13.8] and e[0]["quelle"].startswith("Mauterndorf")
    # Übersicht: Zeile mit Kennzeichen „eigen“, Zähler
    pg.goto(f"{app}/#/areas")
    pg.wait_for_selector("#gbl .gbrow", timeout=T)
    assert pg.locator("#gbl .gbrow").count() == n0 + 1 and pg.locator(f'#gbl a[href="#/area/{gid}"] .gbeigen').count() == 1 and "1 eigenes" in pg.locator("#gbsub").inner_text()
    # Tourseite: das eigene Gebiet steht in der Regionszeile (vorn) und verlinkt die Liste
    pg.goto(f"{app}/#/tour/x2")
    pg.wait_for_selector("a.gblink", timeout=T)
    assert pg.locator("a.gblink").first.inner_text() == "Mein Mauterndorf" and pg.locator("a.gblink").first.get_attribute("href") == f"#/tours?g={gid}"
    # Filter der Tourenliste und Suche kennen das Gebiet
    _liste(pg, app, gid)
    assert set(_namen(pg)) == {"Gipfeltour Beta", "Seerunde Theta"}
    assert pg.evaluate("() => [...document.querySelectorAll('#fg option')].some(o => o.textContent.startsWith('Mein Mauterndorf (2)'))")
    pg.goto(f"{app}/#/search?q=Mauterndorf")
    pg.wait_for_function("() => document.querySelectorAll('#stouren .tr').length >= 2", timeout=T)
    assert {"Gipfeltour Beta", "Seerunde Theta"} <= set(_namen_suche(pg))
    # Foto-Filter des Servers kennt das eigene Gebiet
    assert _get(app, f"/api/photos?gebiet={gid}") == []
    # Bearbeiten: Name, Typ, Rechteck (die zweite Tour fällt heraus); Fehler vom Server bleiben im Fenster
    pg.goto(f"{app}/#/area/{gid}")
    pg.wait_for_selector("#gbedit", timeout=T)
    pg.click("#gbedit")
    pg.wait_for_selector("#gbn", timeout=T)
    assert pg.locator(".uimod h2").inner_text() == "Gebiet bearbeiten" and pg.locator("#gbN").input_value() == "47.2"
    pg.fill("#gbn", "Lungau")
    pg.click("#gbok")
    pg.wait_for_function("() => document.querySelector('#gber').textContent.includes('gibt es schon')", timeout=T)
    assert pg.locator("#gbok").is_enabled()
    pg.fill("#gbn", "Mein Revier"); pg.select_option("#gbt", "gebirge"); pg.fill("#gbS", "47.12")
    pg.wait_for_function("() => document.querySelector('#gbcnt').textContent.includes('1 Tour liegt in diesem Rechteck')", timeout=T)
    pg.click("#gbok")
    pg.wait_for_function("() => document.querySelector('.gbh1') && document.querySelector('.gbh1').textContent.startsWith('Mein Revier') && document.querySelectorAll('#gdx .tl .tr').length === 1", timeout=T)
    assert _get(app, "/api/gebiete/eigene")[0]["typ"] == "gebirge" and "Gebirge" in pg.locator("#gdx").inner_text()
    # Löschen: Rückfrage, danach ist das Gebiet überall weg, die Touren bleiben
    pg.click("#gbdel")
    pg.wait_for_selector(".uibox button.uidanger", timeout=T)
    pg.locator(".uibox button", has_text="Abbrechen").click()
    assert len(_get(app, "/api/gebiete/eigene")) == 1
    pg.click("#gbdel")
    pg.wait_for_selector(".uibox button.uidanger", timeout=T)
    pg.click(".uibox button.uidanger")
    pg.wait_for_function("() => location.hash === '#/areas'", timeout=T)
    pg.wait_for_selector("#gbl .gbrow", timeout=T)
    assert _get(app, "/api/gebiete/eigene") == [] and pg.locator("#gbl .gbrow").count() == n0 and pg.locator("#gbsub").inner_text().find("eigen") < 0
    pg.goto(f"{app}/#/tour/x2")
    pg.wait_for_selector("a.gblink", timeout=T)
    assert pg.locator("a.gblink").first.inner_text() == "Lungau"
    assert len(_namen_all(pg)) >= 8
    assert not pg.errors
    pg.browser_.close()


def _namen_suche(pg):
    return pg.evaluate("() => [...document.querySelectorAll('#stouren .tr .nm')].map(e => e.textContent.trim().replace(/\\s+/g, ' '))")


def _namen_all(pg):
    return pg.evaluate("() => TOURS.map(t => t.name)")


# ------------------------------------------------------------------  Handy  ------------------------------------------------------------------
def test_handy_390_ohne_ueberlauf(pw, app):
    pg = _browser(pw, app, width=390, height=800, devs=None)
    _open(pg, app, "#/areas", "#gbl .gbrow")
    assert pg.evaluate(OVERFLOW)
    row = pg.locator("#gbl .gbrow").first.bounding_box()
    assert row["x"] >= 0 and row["x"] + row["width"] <= 391
    _suchen(pg, app, TREFFER)
    pg.click("#gbadd")
    pg.fill("#gbsq", "Mauterndorf"); pg.press("#gbsq", "Enter")
    pg.wait_for_selector(".gbr", timeout=T)
    assert pg.evaluate(OVERFLOW)
    pg.locator(".gbr").first.click()
    pg.wait_for_selector("#gbmap .leaflet-container, #gbmap.leaflet-container", timeout=T)
    b = pg.locator(".uibox").bounding_box()
    assert b["x"] >= 0 and b["x"] + b["width"] <= 391 and pg.evaluate(OVERFLOW)
    assert pg.locator("#gbok").is_visible() or pg.evaluate("() => { document.querySelector('#gbok').scrollIntoView(); return true; }")
    pg.click("#gbno")
    for h in ("#/area/lungau", "#/area/la-gomera", "#/area/harz"):
        pg.goto(f"{app}/{h}")
        pg.wait_for_selector("#gdx .gbh1", timeout=T)
        pg.wait_for_timeout(300)
        assert pg.evaluate(OVERFLOW), h
    assert not pg.errors
    pg.browser_.close()


# ------------------------------------------------------------------  Sprachen  ------------------------------------------------------------------
ERLAUBT = {"Name", "Land", "Tour", "Karte", "Mal", "Nord", "Typ", "Tag", "Fotos"}          # gleich geschrieben in einer der Sprachen, oder Namen der Seed-Daten („La Gomera Tag 1“)
DEUTSCH = r"\b(Gebiet\w*|Touren?|Strecke|Aufstieg|Tage?|Zurück|Karte|Eigenes|Eingebautes|Löschen|Abbrechen|Speichern|Suchen|Reisen?|Fotos|Beste|Monate|Wann|Nach|Land|Kennzahlen|Zuletzt|Meiste|Längste|Erstes|Letztes|Mal|Rechteck|Grenzen|Näherung|Von Hand|Name|Typ|Süd|Nord|Ost|Treffer|Bitte|gibt|noch|keine|diesem|dieses|Alle|Schließen)\b"


@pytest.mark.parametrize("lang", ["en", "fr", "es"])
def test_oberflaeche_uebersetzt(pw, app, lang):
    """Übersicht, Gebietsseite und Dialog „Gebiet hinzufügen“ ohne deutsche Reste (Eigennamen wie Lungau, La Gomera, Österreich und Länder bleiben)."""
    pg = _browser(pw, app, devs=None, locale={"en": "en-US", "fr": "fr-FR", "es": "es-ES"}[lang])
    pg.context.add_init_script("try { localStorage.setItem('lang', %r); } catch (e) {}" % lang)
    _suchen(pg, app, TREFFER)
    _open(pg, app, "#/areas", "#gbl .gbrow")
    pg.click("#gbadd")
    pg.fill("#gbsq", "Mauterndorf"); pg.press("#gbsq", "Enter")
    pg.wait_for_selector(".gbr", timeout=T)
    dlg = pg.locator(".uibox").inner_text()
    pg.locator(".gbr").first.click()
    pg.wait_for_selector("#gbn", timeout=T)
    dlg += " " + pg.locator(".uibox").inner_text()
    pg.click("#gbno")
    page1 = pg.locator("#main").inner_text()
    pg.goto(f"{app}/#/area/la-gomera")
    pg.wait_for_selector("#gdx .gbh1", timeout=T)
    pg.wait_for_selector('#gdx [data-tls="fotos"] img', timeout=T)
    page2 = pg.locator("#main").inner_text()
    import re
    for name, txt in (("Übersicht", page1), ("Gebiet", page2), ("Dialog", dlg)):
        rest = sorted(set(re.findall(DEUTSCH, txt)))
        assert not [r for r in rest if r not in ERLAUBT], (lang, name, rest)
    pg.browser_.close()
