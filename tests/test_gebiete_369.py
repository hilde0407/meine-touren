"""3.69.0 – Gebiete ergänzen: Osttirol (mit Villgratental, Defereggen, Virgental, Lienzer Dolomiten), Innsbruck/Mittelgebirge, Tuxer Voralpen, Rätikon/Brandnertal, Ötscher, Wachau,
Neusiedler See, Villach/Ossiacher See und der Peloponnes (mit Messenien, Mani, Taygetos, Parnon, Arkadien, Argolis, Olympia/Elis). Nur synthetische Punkte (Ortslagen), keine echten Tourdaten.
Die Grenzen der Gebietstabelle sind Näherungen; geprüft werden Ortslagen und die beiden Randfälle Osttirol ≠ Südtirol und Patsch ≠ Nordtirol (Kitzbühel)."""
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


NEU = ["osttirol", "villgratental", "defereggen", "virgental", "lienzer-dolomiten", "innsbruck", "tuxer", "raetikon", "brandnertal", "oetscher", "wachau", "neusiedlersee", "villach",
       "peloponnes", "messenien", "mani", "taygetos", "parnon", "arkadien", "argolis", "ilia"]


@node
def test_tabelle_pruefung_json_aktuell_und_keine_doppelten_namen():
    assert _node("G.pruefen()") == []
    assert all(_node("G.liste.map(x => x.id)").count(i) == 1 for i in NEU)
    namen = _node("G.liste.map(x => x.name)")
    assert len(namen) == len(set(namen))
    neu = subprocess.run(["node", str(ROOT / "scripts" / "gebiete_json.js"), "--stdout"], capture_output=True, text=True, check=True).stdout
    assert (ROOT / "app" / "gebiete.json").read_text(encoding="utf-8") == neu
    daten = {x["id"] for x in json.loads(neu)["gebiete"]}
    assert set(NEU) <= daten


# (Ort, Breite, Länge, Bezirk, erwartetes Gebiet)
ORTE = [("Patsch", 47.21, 11.45, None, "innsbruck"), ("Igls", 47.23, 11.42, None, "innsbruck"), ("Innervillgraten", 46.80, 12.32, "Bezirk Lienz", "villgratental"),
        ("Innervillgraten ohne Bezirk", 46.80, 12.32, None, "villgratental"), ("Bürserberg", 47.13, 9.74, None, "brandnertal"), ("Brand", 47.07, 9.72, None, "raetikon"),
        ("Lienz", 46.83, 12.77, "Bezirk Lienz", "osttirol"), ("St. Jakob in Defereggen", 46.91, 12.35, None, "defereggen"), ("Virgen", 47.00, 12.45, None, "virgental"),
        ("Dolomitenhütte", 46.77, 12.79, None, "lienzer-dolomiten"), ("Glungezer", 47.22, 11.67, None, "tuxer"), ("Ötscher", 47.86, 15.21, None, "oetscher"), ("Dürnstein", 48.39, 15.52, None, "wachau"),
        ("Illmitz", 47.77, 16.84, None, "neusiedlersee"), ("Ossiach", 46.67, 13.98, None, "villach"),
        ("Mavromati", 37.18, 21.92, None, "messenien"), ("Mavromati mit Land", 37.18, 21.92, "Messenien", "peloponnes"), ("Olympia", 37.64, 21.63, None, "ilia"), ("Tripoli", 37.51, 22.37, None, "arkadien"),
        ("Nafplio", 37.57, 22.80, None, "argolis"), ("Areopoli", 36.67, 22.38, None, "mani"), ("Mystras", 37.07, 22.37, None, "taygetos"), ("Kosmas", 37.12, 22.63, None, "parnon")]


@pytest.mark.parametrize("ort", ORTE, ids=lambda o: o[0])
def test_ortslagen(ort):
    assert ort[4] in [x for x in _ids(*ort[1:4])], ort


def test_osttirol_ist_nicht_suedtirol():
    for name, la, ln, kr in [("Sillian", 46.7467, 12.4167, None), ("Sillian mit Bezirk", 46.7467, 12.4167, "Bezirk Lienz"), ("Innervillgraten", 46.80, 12.32, "Bezirk Lienz"),
                             ("Kartitsch", 46.74, 12.50, "Bezirk Lienz"), ("Lienz", 46.83, 12.77, None)]:
        ids = _ids(la, ln, kr)
        assert "osttirol" in ids and "suedtirol" not in ids, name
    for name, la, ln in [("Sexten", 46.70, 12.35), ("Innichen", 46.735, 12.28), ("Bruneck", 46.80, 11.94), ("Meran", 46.67, 11.16)]:
        ids = _ids(la, ln, "Bozen")
        assert "suedtirol" in ids and "osttirol" not in ids and "villgratental" not in ids, name
    assert "osttirol" in _ids(None, None, "Bezirk Lienz") and "suedtirol" not in _ids(None, None, "Bezirk Lienz")        # nur über den Bezirk (ohne Koordinate)
    assert "osttirol" not in _ids(None, None, "Bozen")
    assert _ids(46.80, 12.32, "Bezirk Lienz")[0] == "villgratental"                                                      # das genaueste zuerst


def test_patsch_ist_nicht_kitzbuehel_und_nicht_zillertal():
    ids = _ids(47.21, 11.45)
    assert ids[0] == "innsbruck" and "tuxer" in ids and "alpen" in ids
    assert "kitzbueheler" not in ids and "zillertal" not in ids and "stubaital" not in ids and "karwendel" not in ids
    kb = _ids(47.45, 12.39)
    assert "kitzbueheler" in kb and "innsbruck" not in kb and "tuxer" not in kb
    assert "innsbruck" not in _ids(47.34, 11.71) and "stubaital" in _ids(47.11, 11.32) and "innsbruck" not in _ids(47.11, 11.32)


def test_vorarlberg_nachbarn():
    ids = _ids(47.13, 9.74)
    assert ids[0] == "brandnertal" and "raetikon" in ids and "montafon" not in ids and "bregenzerwald" not in ids
    assert "montafon" in _ids(47.08, 9.91) and "brandnertal" not in _ids(47.08, 9.91) and "raetikon" not in _ids(47.08, 9.91)


def test_peloponnes_halbinsel_und_nachbarn():
    ids = _ids(37.18, 21.92)
    assert ids == ["messenien", "peloponnes"]
    for name, la, ln in [("Patras", 38.25, 21.73), ("Kalamata", 37.04, 22.11), ("Korinth", 37.94, 22.93), ("Monemvasia", 36.69, 23.04), ("Kap Tenaro", 36.40, 22.48), ("Methoni", 36.82, 21.70),
                         ("Epidavros", 37.63, 23.08), ("Isthmus", 37.91, 23.00), ("Kyllini", 37.93, 21.15)]:
        assert "peloponnes" in _ids(la, ln), name
    for name, la, ln in [("Athen", 37.98, 23.73), ("Megara", 37.99, 23.34), ("Delphi", 38.48, 22.50), ("Nafpaktos", 38.39, 21.83), ("Kythira", 36.20, 22.99), ("Zakynthos", 37.78, 20.90),
                         ("Kefalonia", 38.20, 20.55), ("Aegina", 37.74, 23.43), ("Kreta", 35.34, 25.13), ("Mesolongi", 38.37, 21.43)]:
        assert "peloponnes" not in _ids(la, ln), name
    assert _ids(35.34, 25.13)[0] == "kreta"
    assert "messenien" not in _ids(37.07, 22.43) and "taygetos" in _ids(37.07, 22.37) and "mani" not in _ids(37.51, 22.37)


@node
def test_browser_und_server_rechnen_gleich():
    from app import gebiete
    pts = [(47.0 + i * 0.012, 9.5 + j * 0.05, c) for i in range(25) for j in range(60) for c in (None, "Bezirk Lienz", "Bozen")]
    pts += [(36.2 + i * 0.04, 20.9 + j * 0.03, None) for i in range(60) for j in range(90)]
    pts += [(46.60 + i * 0.01, 12.1 + j * 0.02, c) for i in range(30) for j in range(60) for c in (None, "Bezirk Lienz", "Bozen")]
    pts += [(None, None, "Bezirk Lienz"), (None, None, "Lienz")]
    es = _node("D.map(p => G.von({lat: p[0], lng: p[1], g_county: p[2]}).map(x => x.id))", pts)
    py = [gebiete.von(*p, ()) for p in pts]
    assert es == py


@node
def test_anzeige_namen_und_suche():
    assert _node("G.regionText(D)", {"g_place": "Mavromati", "g_state": "Peloponnes, Westgriechenland und Ionische Inseln", "g_country": "Griechenland", "lat": 37.18, "lng": 21.92}).startswith("Mavromati, Messenien")
    assert "Peloponnes" in _node("G.namen(D)", {"lat": 37.18, "lng": 21.92})
    for wort in ("Peloponnese", "Morea", "Ithomi", "Taygetus"):
        assert wort in _node("G.namen(D)", {"lat": 37.0, "lng": 22.37}) or wort in _node("G.namen(D)", {"lat": 37.18, "lng": 21.92}), wort
    assert "Patsch" in _node("G.namen(D)", {"lat": 47.21, "lng": 11.45}) and "Tuxer" in _node("G.namen(D)", {"lat": 47.21, "lng": 11.45})
    assert "Villgraten" in _node("G.namen(D)", {"lat": 46.80, "lng": 12.32, "g_county": "Bezirk Lienz"})
    assert _node("G.anzeige(D).name", {"lat": 47.21, "lng": 11.45, "g_place": "Patsch"}) == "Innsbruck und Mittelgebirge"


@node
def test_pruefbericht_nennt_neue_gebiete():
    r = _node("G.bericht(D).gebiete.map(x => x.id)", [{"name": "A", "lat": 37.18, "lng": 21.92}, {"name": "B", "lat": 47.21, "lng": 11.45}, {"name": "C", "lat": 46.80, "lng": 12.32, "g_county": "Bezirk Lienz"}])
    assert {"peloponnes", "messenien", "innsbruck", "osttirol", "villgratental"} <= set(r)
    ohne = _node("G.bericht(D).ohneGebiet", [{"name": "Athen", "lat": 37.98, "lng": 23.73, "g_country": "Griechenland"}])
    assert ohne[0]["land"] == "Griechenland"
