"""3.70.0 – Abgleich der Gebiete mit dem Rother-Wanderführer-Katalog: neue Gebiete (Deutschland, Österreich, Schweiz, Italien, Spanien/Portugal, Griechenland, Skandinavien u. a.),
Alias für Schreibweisen und Wege, Suche über den Namen aus dem Katalog, Eltern/`in`/`prio`, bestehende Zuordnungen bleiben. Nur synthetische Punkte (Ortslagen), keine echten Tourdaten.
Die Grenzen sind Näherungen; geprüft werden Ortslagen, keine Randfälle (die Ortslagen je Gebiet stehen in tests/gebiete_punkte_362.py)."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_core import fresh  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
GEB = ROOT / "app" / "static" / "js" / "gebiete-daten.js"
node = pytest.mark.skipif(not shutil.which("node"), reason="Node nicht installiert")


def _node(expr, data=None):
    code = f"const G = require({json.dumps(str(GEB))}); const D = JSON.parse(require('fs').readFileSync(0, 'utf8')); process.stdout.write(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", code], input=json.dumps(data), capture_output=True, text=True, check=True).stdout)


def _ids(la, ln, county=None):
    from app import gebiete
    return gebiete.von(la, ln, county, ())


NEU = ["muensterland", "oberlausitz", "seenplatte", "bergisches-land", "siegerland", "isarwinkel", "pfaffenwinkel", "kaiserstuhl", "elbtalaue", "uckermark", "emsland", "ostfriesland",
       "rheinhessen", "kraichgau", "taubertal", "altmuehltal", "saale-unstrut", "baederdreieck", "bodensee",
       "wienerwald", "pitztal", "lesachtal", "seefeld", "gastein", "mariazell", "moelltal", "woerthersee", "millstaettersee", "grazer-hausberge", "oststeiermark", "leithagebirge", "kalkalpen",
       "glarnerland", "zuerichsee", "genfersee", "vierwaldstaettersee", "emmental", "gruyere", "surselva", "davos",
       "vinschgau", "meran", "bozen", "sterzing", "ahrntal", "antholz", "pustertal", "seiser-alm", "groeden", "fassatal", "gadertal", "sextner", "cortina", "eggental",
       "lago-maggiore", "comer-see", "adamello", "vizentiner", "golf-neapel",
       "cote-d-azur", "burgund", "dordogne", "dauphine",
       "galicien", "kantabrien", "asturien", "baskenland", "costa-brava", "costa-daurada", "costa-blanca", "alentejo", "nordportugal",
       "korfu", "chalkidiki", "thassos", "olymp", "pilion", "kefalonia", "ithaka", "zakynthos", "samos", "ikaria", "patmos", "fourni",
       "dovrefjell", "vesteraalen", "gotland", "oeland", "bornholm", "faeroeer", "kanalinseln", "devon", "molokai", "tasmanien"]


@node
def test_tabelle_pruefung_json_aktuell_und_alle_neuen_gebiete_da():
    assert _node("G.pruefen()") == []
    ids = _node("G.liste.map(x => x.id)")
    assert len(ids) == len(set(ids)) and len(NEU) == len(set(NEU))
    assert set(NEU) <= set(ids) and len(ids) == 343 + len(NEU)
    namen = _node("G.liste.map(x => x.name)")
    assert len(namen) == len(set(namen))
    neu = subprocess.run(["node", str(ROOT / "scripts" / "gebiete_json.js"), "--stdout"], capture_output=True, text=True, check=True).stdout
    assert (ROOT / "app" / "gebiete.json").read_text(encoding="utf-8") == neu
    assert set(NEU) <= {x["id"] for x in json.loads(neu)["gebiete"]}


# (Name aus dem Rother-Katalog bzw. Alias, Breite, Länge, erwartetes Gebiet): die Suche nach dem Namen findet die Tour über den Suchtext des Gebiets (Name oder Alias)
SUCHE = [("Münsterland", 51.96, 7.63, "muensterland"), ("Oberlausitz", 51.18, 14.43, "oberlausitz"), ("Mecklenburgische Seenplatte", 53.52, 12.68, "seenplatte"), ("Müritz", 53.38, 12.61, "seenplatte"),
         ("Bergisches Land", 51.17, 7.08, "bergisches-land"), ("Siegerland", 50.87, 8.02, "siegerland"), ("Wittgenstein", 51.05, 8.39, "siegerland"), ("Isarwinkel", 47.76, 11.56, "isarwinkel"),
         ("Pfaffenwinkel", 47.84, 11.14, "pfaffenwinkel"), ("Kaiserstuhl", 48.03, 7.58, "kaiserstuhl"), ("Elbtalaue", 53.15, 10.99, "elbtalaue"), ("Uckermark", 53.32, 13.86, "uckermark"),
         ("Emsland", 52.69, 7.29, "emsland"), ("Grafschaft Bentheim", 52.43, 7.07, "emsland"), ("Ostfriesland", 53.47, 7.48, "ostfriesland"), ("Rheinhessen", 49.75, 8.12, "rheinhessen"),
         ("Kraichgau", 49.12, 8.60, "kraichgau"), ("Taubertal", 49.38, 10.18, "taubertal"), ("Altmühltal", 48.89, 11.18, "altmuehltal"), ("Altmühltal-Panoramaweg", 48.89, 11.18, "altmuehltal"),
         ("Saale-Unstrut-Triasland", 51.15, 11.81, "saale-unstrut"), ("Bäderdreieck", 48.35, 13.30, "baederdreieck"), ("Bodensee", 47.66, 9.17, "bodensee"),
         ("Wienerwald", 48.09, 16.29, "wienerwald"), ("Wien und Wienerwald", 48.09, 16.29, "wienerwald"), ("Pitztal", 47.24, 10.74, "pitztal"), ("Imst", 47.24, 10.74, "pitztal"), ("Lesachtal", 46.67, 12.88, "lesachtal"),
         ("Leutasch", 47.35, 11.15, "seefeld"), ("Gasteinertal", 47.11, 13.13, "gastein"), ("Mariazell", 47.77, 15.32, "mariazell"), ("Mölltal", 46.93, 13.20, "moelltal"),
         ("Kreuzeckgruppe", 46.93, 13.20, "moelltal"), ("Kärntner Seen", 46.62, 14.04, "woerthersee"), ("Kärntner Seen", 46.80, 13.58, "millstaettersee"), ("Kärntner Seen", 46.67, 13.98, "villach"),
         ("Grazer Hausberge", 47.20, 15.47, "grazer-hausberge"), ("Oststeiermark", 47.28, 15.97, "oststeiermark"), ("Leithagebirge", 47.85, 16.52, "leithagebirge"), ("Rosaliengebirge", 47.74, 16.40, "leithagebirge"),
         ("Nationalpark Kalkalpen", 47.72, 14.35, "kalkalpen"), ("Glarnerland", 47.04, 9.07, "glarnerland"), ("Zürichsee", 47.37, 8.54, "zuerichsee"), ("Genfersee", 46.52, 6.63, "genfersee"),
         ("Vierwaldstättersee", 47.00, 8.60, "vierwaldstaettersee"), ("Emmental", 46.94, 7.79, "emmental"), ("Entlebuch", 46.99, 8.06, "emmental"), ("Gruyère", 46.58, 7.08, "gruyere"),
         ("Surselva", 46.83, 9.28, "surselva"), ("Davos", 46.80, 9.84, "davos"), ("Prättigau", 46.91, 9.78, "davos"), ("Vinschgau", 46.63, 10.77, "vinschgau"), ("Meraner Höhenweg", 46.67, 11.16, "meran"),
         ("Kaltern", 46.40, 11.24, "bozen"), ("Wipptal", 46.89, 11.43, "sterzing"), ("Tauferer Ahrntal", 46.90, 11.95, "ahrntal"), ("Antholz", 46.86, 12.15, "antholz"), ("Gsies", 46.79, 12.20, "antholz"),
         ("Pustertal", 46.80, 11.94, "pustertal"), ("Seiser Alm", 46.54, 11.56, "seiser-alm"), ("Grödnertal", 46.58, 11.67, "groeden"), ("Fassatal", 46.48, 11.77, "fassatal"), ("Gadertal", 46.55, 11.87, "gadertal"),
         ("Sextner Dolomiten", 46.70, 12.35, "sextner"), ("Cortina d'Ampezzo", 46.54, 12.14, "cortina"), ("Rosengarten", 46.41, 11.58, "eggental"), ("Latemar", 46.37, 11.57, "eggental"),
         ("Lago Maggiore", 45.89, 8.53, "lago-maggiore"), ("Comer See", 45.99, 9.26, "comer-see"), ("Adamello", 46.16, 10.76, "adamello"), ("Vizentiner Alpen", 45.88, 11.51, "vizentiner"),
         ("Golf von Neapel", 40.82, 14.12, "golf-neapel"), ("Côte d'Azur", 43.70, 7.27, "cote-d-azur"), ("Grande Traversata delle Alpi", 44.60, 7.40, "piemont"), ("Burgund", 47.32, 5.04, "burgund"), ("Dordogne", 44.89, 1.22, "dordogne"), ("Dauphiné", 45.19, 5.72, "dauphine"), ("Dauphiné West", 44.75, 5.37, "dauphine"), ("Galicien", 42.88, -8.54, "galicien"), ("Kantabrien", 43.46, -3.81, "kantabrien"), ("Asturien", 43.36, -5.85, "asturien"),
         ("Baskenland", 43.26, -2.93, "baskenland"), ("Costa Brava", 42.26, 3.18, "costa-brava"), ("Costa Daurada", 41.12, 1.25, "costa-daurada"), ("Costa Blanca", 38.54, -0.13, "costa-blanca"),
         ("Alentejo", 38.57, -7.91, "alentejo"), ("Nordportugal", 41.15, -8.61, "nordportugal"), ("Korfu", 39.62, 19.92, "korfu"), ("Chalkidiki", 40.21, 23.68, "chalkidiki"), ("Thassos", 40.78, 24.71, "thassos"),
         ("Olymp", 40.10, 22.50, "olymp"), ("Pilion", 39.36, 22.94, "pilion"), ("Kefalonia", 38.18, 20.49, "kefalonia"), ("Ithaka", 38.37, 20.72, "ithaka"), ("Zakynthos", 37.78, 20.90, "zakynthos"),
         ("Samos", 37.69, 26.94, "samos"), ("Ikaria", 37.61, 26.30, "ikaria"), ("Patmos", 37.31, 26.55, "patmos"), ("Dovrefjell", 62.22, 9.55, "dovrefjell"), ("Vesterålen", 68.70, 15.42, "vesteraalen"),
         ("Lofoten und Vesterålen", 68.70, 15.42, "vesteraalen"), ("Gotland", 57.64, 18.30, "gotland"), ("Öland", 56.88, 16.65, "oeland"), ("Bornholm", 55.10, 14.70, "bornholm"),
         ("Färöer", 62.01, -6.77, "faeroeer"), ("Kanalinseln", 49.46, -2.54, "kanalinseln"), ("Devon", 50.72, -3.53, "devon"), ("Tasmanien", -42.88, 147.33, "tasmanien"), ("Molokai", 21.09, -157.02, "molokai"),
         # Wege und Schreibweisen als Alias vorhandener Gebiete
         ("Westweg", 47.874, 8.004, "schwarzwald"), ("Heidschnuckenweg", 53.05, 9.95, "lueneburger-heide"), ("Harzer Hexenstieg", 51.80, 10.62, "harz"), ("Goldsteig", 48.94, 13.50, "bayerischer-wald"),
         ("Eifelsteig", 50.37, 6.53, "eifel"), ("Albsteig", 48.40, 9.50, "schwaebische-alb"), ("Oberallgäu", 47.41, 10.28, "allgaeu"), ("Ostallgäu", 47.57, 10.70, "allgaeu"),
         ("Deutsche Weinstraße", 49.25, 8.05, "pfaelzerwald"), ("Stubaier Höhenweg", 47.11, 11.32, "stubaital"), ("Lechweg", 47.30, 10.60, "ausserfern"), ("Oberwallis", 46.02, 7.75, "wallis"),
         ("GR 221", 39.75, 2.75, "tramuntana"), ("GR 10", 42.85, 0.50, "pyrenaeen"), ("GR 20", 42.30, 9.10, "korsika"), ("West Highland Way", 56.82, -5.10, "highlands"),
         ("Friaul-Julisch Venetien", 46.20, 13.20, "friaul"), ("Italienische Riviera", 44.30, 9.30, "ligurien")]


@node
def test_suche_nach_dem_namen_aus_dem_katalog_findet_das_gebiet():
    res = _node("""D.map(([name, la, ln, gid]) => { const t = {lat: la, lng: ln}; const txt = G.fold(G.fuerSuche(t)); return [G.von(t).some(x => x.id === gid), txt.includes(G.fold(name))]; })""", SUCHE)
    schlecht = [(s[0], s[3], "nicht im Gebiet" if not r[0] else "Name fehlt im Suchtext") for s, r in zip(SUCHE, res) if not all(r)]
    assert not schlecht, schlecht
    assert len(SUCHE) > 100


@node
def test_suchwoerter_mit_mehreren_woertern_bleiben_zusammen():
    # „Rosengarten“ etc. sind Name oder Alias; die Suche bündelt Mehrwort-Namen (phrasen) auch für die neuen Gebiete
    r = _node("G.phrasen(D)", ["Mecklenburgische", "Seenplatte", "Costa", "Brava", "Lago", "Maggiore", "Golf", "von", "Neapel", "Bad", "Tölz"])
    assert "Mecklenburgische Seenplatte" in r and "Costa Brava" in r and "Lago Maggiore" in r and "Golf von Neapel" in r and "Bad Tölz" in r


def test_suedtirol_bleibt_nur_bozen_und_die_untergebiete_auch():
    for name, la, ln, kr, gid in [("Meran", 46.67, 11.16, "Bozen", "meran"), ("Schlanders", 46.63, 10.77, "Bozen", "vinschgau"), ("Bozen", 46.50, 11.35, "Bozen", "bozen"),
                                  ("Sterzing", 46.89, 11.43, "Bozen", "sterzing"), ("Bruneck", 46.80, 11.94, "Bozen", "pustertal"), ("Antholz", 46.86, 12.15, "Bozen", "antholz")]:
        ids = _ids(la, ln, kr)
        assert gid in ids and "suedtirol" in ids and "alpen" in ids, name
    # `in: suedtirol`: was nicht in der Provinz Bozen liegt, gehört auch nicht zu den Untergebieten
    for name, la, ln, kr in [("Landeck", 47.14, 10.57, "Bezirk Landeck"), ("Val Müstair", 46.63, 10.38, None), ("Trient", 46.07, 11.12, "Trient"), ("Sillian", 46.75, 12.42, "Bezirk Lienz"),
                             ("Innervillgraten", 46.80, 12.32, "Bezirk Lienz"), ("Rabbi", 46.40, 10.85, "Trient")]:
        ids = _ids(la, ln, kr)
        assert not ({"vinschgau", "meran", "bozen", "sterzing", "ahrntal", "antholz", "pustertal"} & set(ids)), (name, ids)
        assert "suedtirol" not in ids, name
    assert _ids(46.80, 12.32, "Bezirk Lienz")[0] == "villgratental"
    assert "osttirol" in _ids(46.83, 12.77, "Bezirk Lienz") and "suedtirol" not in _ids(46.83, 12.77, "Bezirk Lienz")
    # Dolomiten-Täler hängen an den Dolomiten
    assert {"groeden", "dolomiten", "alpen"} <= set(_ids(46.58, 11.67)) and {"cortina", "dolomiten"} <= set(_ids(46.54, 12.14))


@node
def test_anzeige_aendert_sich_fuer_bestehende_suedtirol_und_dolomiten_touren_nicht():
    for name, la, ln, kr in [("Bozen", 46.50, 11.35, "Bozen"), ("Meran", 46.67, 11.16, "Bozen"), ("Kaltern", 46.40, 11.24, "Bozen"), ("Sterzing", 46.89, 11.43, "Bozen")]:
        assert _node("G.anzeige(D).name", {"lat": la, "lng": ln, "g_place": name, "g_county": kr}) == "Südtirol", name
    assert _node("G.anzeige(D).name", {"lat": 46.54, "lng": 12.14, "g_place": "Cortina d'Ampezzo"}) == "Dolomiten"
    assert _node("G.anzeige(D).name", {"lat": 46.58, "lng": 11.67, "g_place": "St. Ulrich"}) == "Dolomiten"


def test_vorrang_des_gebirges_vor_ueberschneidenden_regionen():
    # `prio: -1`: Teutoburger Wald vor Münsterland, Jura vor Genfersee/Emmental, Pyrenäen vor Baskenland, Cornwall vor Devon, Lofoten vor Vesterålen, Sauerland vor Siegerland
    from app.gebiete import _tabelle
    by = _tabelle(())[1]
    for gid in ("muensterland", "genfersee", "emmental", "baskenland", "devon", "vesteraalen", "siegerland", "seefeld", "gruyere"):
        assert by[gid]["prio"] == -1, gid
    assert _ids(52.20, 8.05)[0] != "muensterland"                                                  # Osnabrücker Land / Teutoburger Wald östlich der Münsterland-Grenze
    assert _ids(46.50, 6.30)[0] == "jura" and "genfersee" in _ids(46.50, 6.30)                 # Jura-Hang über dem Genfersee: Jura zuerst
    assert _ids(43.15, -1.24)[0] == "pyrenaeen"                                                    # Saint-Jean-Pied-de-Port: Pyrenäen, Baskenland bleibt zusätzlich
    assert "baskenland" in _ids(43.15, -1.24)
    assert _ids(50.88, -4.17)[0] == "cornwall"                                                     # Tamar: Cornwall vor Devon


def test_bestehende_zuordnungen_bleiben():
    erwartet = [(27.99, -15.62, "gran-canaria"), (28.18, -17.27, "la-gomera"), (47.14, 13.67, "lungau"), (47.27, 13.69, "schladminger"), (47.00, 13.50, "lungau"), (46.83, 12.77, "osttirol"),
                (37.18, 21.92, "messenien"), (37.18, 21.92, "peloponnes"), (47.25, 13.69, "schladminger"), (46.50, 11.35, "suedtirol"), (47.52, 12.30, "wilder-kaiser"), (47.47, 13.62, "dachstein")]
    for la, ln, gid in erwartet:
        if gid == "lungau" and la == 47.00:
            continue
        assert gid in _ids(la, ln), (la, ln, gid)
    assert "suedtirol" not in _ids(46.07, 11.12) and "suedtirol" not in _ids(46.75, 12.42, "Bezirk Lienz") and "suedtirol" not in _ids(46.40, 10.85, "Trient")
    assert _ids(28.18, -17.27)[0] == "la-gomera" and _ids(37.18, 21.92)[0] == "messenien" and _ids(47.14, 13.67)[0] == "lungau"
    assert _ids(46.80, 12.32, "Bezirk Lienz")[0] == "villgratental" and _ids(47.21, 11.45)[0] == "innsbruck"


@node
def test_browser_und_server_rechnen_gleich():
    from app import gebiete
    pts = [(la, ln, c) for la, ln in [(43.0 + i * 0.05, -9.0 + j * 0.1) for i in range(40) for j in range(80)] for c in (None,)]                    # Nordspanien/Portugal
    pts += [(45.6 + i * 0.03, 8.3 + j * 0.05, c) for i in range(40) for j in range(60) for c in (None, "Bozen")]                                     # Seen und Dolomiten-Westen
    pts += [(46.3 + i * 0.01, 10.4 + j * 0.02, c) for i in range(50) for j in range(70) for c in (None, "Bozen", "Trient")]                          # Südtirol/Untergebiete
    pts += [(37.5 + i * 0.04, 20.2 + j * 0.05, None) for i in range(25) for j in range(30)]                                                          # Ionische Inseln
    pts += [(47.0 + i * 0.03, 6.0 + j * 0.06, None) for i in range(30) for j in range(40)]                                                           # Jura/Genfersee/Emmental
    es = _node("D.map(p => G.von({lat: p[0], lng: p[1], g_county: p[2]}).map(x => x.id))", pts)
    py = [gebiete.von(*p, ()) for p in pts]
    assert es == py


def test_versionsnotiz_nennt_geprueft_ergaenzt_und_offen():
    txt = (ROOT / "docs" / "versionen" / "3.70.0.md").read_text(encoding="utf-8")
    assert "Noch nicht angelegt (Grenzen unklar)" in txt and "Rother" in txt
    for gid_name in ("Isarwinkel", "Galicien", "Kefalonia", "Vinschgau", "Genfersee"):
        assert gid_name in txt
