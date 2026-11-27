"""3.62.1 – eingebaute Gebietstabelle (app/static/js/gebiete-daten.js), Rechenlogik mit Node: Konsistenz der Tabelle (eindeutige Kennungen, gültige Eltern, Rechtecke und Vielecke),
bekannte Orte und Gipfel je Gebiet liegen im Gebiet, bekannte Nachbarn nicht (Südtirol ≠ Trentino), Mehrfachzuordnung, Bezirk, Suchtext mit Alias, Regionszeile ohne Doppelungen, Prüfbericht.
Die Grenzen der Tabelle sind Näherungen; geprüft werden Ortslagen, keine Randfälle."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.gebiete_punkte_362 import NEG, POS, PUNKTE

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "app" / "static" / "js" / "gebiete-daten.js"
pytestmark = pytest.mark.skipif(not shutil.which("node"), reason="Node nicht installiert")


def _node(expr, data=None):
    code = f"const G = require({json.dumps(str(JS))}); const D = JSON.parse(require('fs').readFileSync(0, 'utf8')); process.stdout.write(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", code], input=json.dumps(data), capture_output=True, text=True, check=True).stdout)


def _ids(la, ln, **kw):
    return _node("G.von(D).map(x => x.id)", dict(lat=la, lng=ln, **kw))


def test_tabelle_konsistent():
    assert _node("G.pruefen()") == []
    liste = _node("G.liste.map(x => ({id: x.id, typ: x.typ, eltern: x.eltern, eigen: x.eigen, n: x.boxen.length + x.poly.length}))")
    ids = [x["id"] for x in liste]
    assert len(ids) == len(set(ids)) and len(ids) >= 300
    assert {x["typ"] for x in liste} == {"gebirge", "tal", "insel", "kueste", "region"}
    assert all(x["eltern"] in ids for x in liste if x["eltern"])
    assert sum(1 for x in liste if not x["eigen"]) == 13                      # reine Oberbegriffe (Alpen, Kanaren, Azoren, Niedere Tauern, …)


def test_boxen_und_vielecke_gueltig():
    r = _node("""(() => { const bad = [];
      for (const x of G.liste) {
        for (const b of x.boxen.concat(x.nicht.filter(n => Array.isArray(n)))) if (!(b[0] < b[2] && b[1] < b[3])) bad.push(x.id + " box");
        for (const p of x.poly) { if (p.length < 3) bad.push(x.id + " poly"); const la = p.map(q => q[0]), ln = p.map(q => q[1]); if (Math.max(...la) - Math.min(...la) < 0.05 || Math.max(...ln) - Math.min(...ln) < 0.05) bad.push(x.id + " poly klein"); }
      } return bad; })()""")
    assert r == []


def test_jedes_gebiet_hat_einen_pruefpunkt():
    r = _node("G.liste.map(x => x.id)")
    mit = {p[0] for p in PUNKTE if not p[4]}
    # reine Oberbegriffe zählen über ihre Kinder; alle anderen brauchen mindestens einen bekannten Punkt
    fehlt = [i for i in r if i not in mit]
    assert set(fehlt) <= {"alpen", "elbsandstein", "karpaten", "tatra", "skandinavien", "hawaii", "patagonien", "neuseeland", "madeira-archipel", "balearen", "niedere-tauern"}, fehlt


def test_bekannte_punkte_liegen_im_gebiet_und_nachbarn_nicht():
    res = _node("D.map(p => G.von({lat: p[2], lng: p[3]}).some(x => x.id === p[0]))", PUNKTE)
    schlecht = [(p[0], p[1], "darf nicht" if p[4] else "fehlt") for p, ok in zip(PUNKTE, res) if ok == p[4]]
    assert not schlecht, schlecht
    assert len(PUNKTE) > 900 and sum(1 for p in PUNKTE if p[4]) > 80


def test_vorgegebene_punkte_aus_der_aufgabe():
    # Volker: La Gomera, La Palma, Teneriffa, Gran Canaria, Lungau, Mafate, Zillertal, Dachstein, Wilder Kaiser, Südtirol/Trient, Madeira, Azoren, Sizilien
    erwartet = [(28.18, -17.27, "la-gomera"), (28.76, -17.89, "la-palma"), (28.27, -16.64, "teneriffa"), (27.99, -15.62, "gran-canaria"), (47.14, 13.67, "lungau"), (-21.07, 55.43, "mafate"),
                (47.16, 11.86, "zillertal"), (47.47, 13.62, "dachstein"), (47.52, 12.30, "wilder-kaiser"), (46.50, 11.35, "suedtirol"), (32.76, -16.94, "madeira"), (38.47, -28.40, "pico"),
                (37.75, 15.00, "sizilien")]
    for la, ln, i in erwartet:
        assert i in _ids(la, ln), (la, ln, i)
    assert "suedtirol" not in _ids(46.07, 11.12) and "trentino" in _ids(46.07, 11.12)
    assert "trentino" not in _ids(46.50, 11.35)


def test_mehrfachzuordnung_mit_eltern():
    assert {"feldberg", "schwarzwald-sued", "schwarzwald"} <= set(_ids(47.874, 8.004))
    assert {"la-gomera", "kanaren"} <= set(_ids(28.18, -17.27))
    assert {"mafate", "reunion"} <= set(_ids(-21.07, 55.43))
    assert {"pico", "azoren"} <= set(_ids(38.47, -28.40))
    assert {"hohetatra", "tatra", "karpaten"} <= set(_ids(49.164, 20.134))
    assert {"stromboli", "aeolische", "sizilien"} <= set(_ids(38.79, 15.21))
    assert {"ellmau" if False else "wilder-kaiser", "kitzbueheler", "alpen"} <= set(_ids(47.52, 12.30))           # Ellmau: Wilder Kaiser und Kitzbüheler Alpen
    # spezifischstes Gebiet zuerst
    assert _ids(47.874, 8.004)[0] == "feldberg" and _ids(28.18, -17.27)[0] == "la-gomera"


def test_bezirk_ist_nur_zusaetzlich():
    assert "lungau" in _ids(None, None, g_county="Bezirk Tamsweg")                    # ohne Koordinate über den Bezirk
    assert "lungau" in _ids(47.14, 13.67, g_county="")                                 # 2026: kein Bezirk, Koordinate genügt
    assert "suedtirol" in _ids(None, None, g_county="Bozen") and "suedtirol" in _ids(None, None, g_county="Provinz Bozen")
    assert "suedtirol" not in _ids(None, None, g_county="Trient") and "trentino" in _ids(None, None, g_county="Trient")
    assert _ids(None, None, g_county="Landkreis Irgendwo") == []
    assert _ids(None, None) == [] and _ids(0, 0) == [] and _ids("x", 5) == []
    # der Bezirk allein macht aus einem Punkt außerhalb nichts Falsches: Trient bleibt Trient, auch wenn der Bezirk „Bozen“ fehlt
    assert "suedtirol" not in _ids(46.07, 11.12, g_county="")


def test_suchtext_mit_alias_und_suedtirol_ohne_trient():
    t = _node("G.namen(D)", dict(lat=48.94, lng=13.50))                                # Lusen
    assert "Šumava" in t and "Bohemian Forest" in t and "Bayerischer Wald" in t
    assert "Tatras" in _node("G.namen(D)", dict(lat=49.164, lng=20.134))
    assert "Mafate" in _node("G.namen(D)", dict(lat=-21.07, lng=55.43)) and "La Réunion" in _node("G.namen(D)", dict(lat=-21.07, lng=55.43))
    assert "Kanarische Inseln" in _node("G.namen(D)", dict(lat=28.18, lng=-17.27))
    tr = _node("G.fuerSuche(D)", dict(lat=46.07, lng=11.12, g_place="Trient", g_county="Trient", g_state="Trentino-Südtirol", g_country="Italien"))
    assert "Trentino" in tr and "dtirol" not in tr
    bz = _node("G.fuerSuche(D)", dict(lat=46.50, lng=11.35, g_place="Bozen", g_county="Bozen", g_state="Trentino-Südtirol", g_country="Italien"))
    assert "Südtirol" in bz and "Alto Adige" in bz and "Trentino" not in bz
    ohne = _node("G.fuerSuche(D)", dict(g_place="Trient", g_state="Trentino-Alto Adige/Südtirol", g_country="Italien"))      # ohne Koordinate: Trentino, nicht Südtirol
    assert "Trentino" in ohne and "dtirol" not in ohne
    andere = _node("G.fuerSuche(D)", dict(lat=47.14, lng=13.67, g_state="Salzburg", g_county="Bezirk Tamsweg"))
    assert "Salzburg" in andere and "Lungau" in andere


def test_region_anzeige_ohne_doppelungen():
    def zeile(**t):
        return _node("G.regionText(D)", t)
    assert zeile(lat=28.18, lng=-17.27, g_place="Vallehermoso", g_state="Kanarische Inseln", g_country="Spanien") == "Vallehermoso, La Gomera, Kanarische Inseln, Spanien"
    assert zeile(lat=47.14, lng=13.67, g_place="Mauterndorf", g_state="Salzburg", g_country="Österreich") == "Mauterndorf, Lungau, Salzburg, Österreich"
    assert zeile(lat=47.10, lng=13.64, g_place="Sankt Michael im Lungau", g_state="Salzburg", g_country="Österreich") == "Sankt Michael im Lungau, Salzburg, Österreich"      # nicht zweimal „Lungau“
    assert zeile(lat=28.50, lng=-16.40, g_place="Teneriffa", g_state="Kanarische Inseln", g_country="Spanien") == "Teneriffa, Kanarische Inseln, Spanien"
    assert zeile(lat=28.50, lng=-16.40, g_place="Teneriffa", g_county="Santa Cruz de Tenerife", g_state="Kanarische Inseln", g_country="Spanien") == "Teneriffa, Kanarische Inseln, Spanien"
    assert zeile(lat=46.50, lng=11.35, g_place="Bozen", g_county="Bozen", g_state="Trentino-Südtirol", g_country="Italien") == "Bozen, Südtirol, Trentino-Südtirol, Italien"
    assert zeile(lat=52.5, lng=13.4, g_place="Berlin", g_state="Berlin", g_country="Deutschland") == "Berlin, Deutschland"                                   # kein Gebiet, keine Doppelung Ort/Bundesland
    assert zeile(g_place="Berlin", g_country="Deutschland") == "Berlin, Deutschland"
    assert zeile() == ""
    # genau ein Gebiet, auch bei Mehrfachzuordnung
    z = zeile(lat=47.874, lng=8.004, g_place="Feldberg", g_state="Baden-Württemberg", g_country="Deutschland")
    assert z.count(",") == 3 and "Feldberg (Schwarzwald)" in z and "Südschwarzwald" not in z
    # das spezifischste Gebiet sagt nichts Neues: nichts statt eines gröberen
    assert zeile(lat=-21.07, lng=55.43, g_place="Mafate", g_country="Frankreich") == "Mafate, Frankreich"


def test_region_typ_region_nur_mit_anz():
    # „Piemont“ ist eine Region ohne Anzeige (das Bundesland steht schon da), „Lungau“ eine Landschaft mit Anzeige
    assert _node("G.anzeige(D)", dict(lat=45.07, lng=7.69)) is None
    assert _node("(G.anzeige(D) || {}).id", dict(lat=47.14, lng=13.67)) == "lungau"


def test_bericht():
    touren = [dict(id="a", name="Gomera-Runde", lat=28.18, lng=-17.27, g_country="Spanien"), dict(id="b", name="Irgendwo", lat=0, lng=0, g_country="Spanien"),
              dict(id="c", name="Nirgendwo", lat=52.5, lng=13.4, g_country="Deutschland"), dict(id="d", name="Gomera 2", lat=28.12, lng=-17.24, g_country="Spanien")]
    b = _node("G.bericht(D)", touren)
    assert b["touren"] == 4 and b["mitGebiet"] == 2
    gom = next(e for e in b["gebiete"] if e["id"] == "la-gomera")
    assert gom["n"] == 2 and set(gom["beispiele"]) == {"Gomera-Runde", "Gomera 2"}
    assert {e["land"]: e["n"] for e in b["ohneGebiet"]} == {"Spanien": 1, "Deutschland": 1}
    assert b["mehrfach"] == [] and "La Gomera" in b["text"] and "Touren ohne Gebiet nach Land" in b["text"]
    viele = _node("G.bericht(D, {viele: 1}).mehrfach.map(m => m.name)", touren)                     # Schwelle einstellbar: „mehr als 1 Gebiet“ trifft La Gomera + Kanaren
    assert sorted(viele) == ["Gomera 2", "Gomera-Runde"]


def test_pruefskript_node(tmp_path):
    f = tmp_path / "tours.json"
    f.write_text(json.dumps([dict(id="a", name="Gomera-Runde", lat=28.18, lng=-17.27, g_country="Spanien"), dict(id="c", name="Nirgendwo", lat=52.5, lng=13.4, g_country="Deutschland")]), encoding="utf-8")
    out = subprocess.run(["node", str(ROOT / "tests" / "gebiete_pruefen.js"), str(f)], capture_output=True, text=True, check=True).stdout
    assert "La Gomera (insel): 1" in out and "Deutschland: 1" in out and "2 Touren, davon 1 mit Gebiet" in out
    assert json.loads(subprocess.run(["node", str(ROOT / "tests" / "gebiete_pruefen.js"), str(f), "--json"], capture_output=True, text=True, check=True).stdout)["mitGebiet"] == 1


def test_schnell_genug():
    r = _node("""(() => { const t0 = Date.now(); let n = 0; for (let i = 0; i < 4000; i++) n += G.von({lat: 40 + (i % 97) * 0.13, lng: -5 + (i % 89) * 0.37 + i * 1e-4, g_county: ""}).length; return [Date.now() - t0, n]; })()""")
    assert r[0] < 4000, r


def test_eingebunden():
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("js/gebiete-daten.js") < html.index("js/06-erweiterungen.js")
    s = (ROOT / "app" / "static" / "js" / "06-erweiterungen.js").read_text(encoding="utf-8")
    assert "Gebiete.fuerSuche(t)" in s and "sucheReisen" in s and "tripKarte" in s
    assert "Gebiete.regionText(t)" in (ROOT / "app" / "static" / "js" / "03-tour.js").read_text(encoding="utf-8")
    assert "Gebiete.regionText(t)" in (ROOT / "app" / "static" / "js" / "17-tourblatt.js").read_text(encoding="utf-8")
    assert "NÄHERUNGEN" in JS.read_text(encoding="utf-8")[:2500]


def test_neue_texte_uebersetzt():
    neu = (ROOT / "app" / "static" / "js" / "00-i18n-neu.js").read_text(encoding="utf-8")
    for k in ("{} Tour ||", "{} Reise ||", "Gesucht wird in Name, Notiz, Sportart, Datum, Monat, Region (Land, Bundesland, Landkreis, Ort), Gebiet (Gebirge, Tal, Insel) und Reisen. ||"):
        assert "\n" + k in neu, k


def test_suchwoerter_zusammenfassen():
    assert _node("G.phrasen(D)", ["Gran", "Canaria"]) == ["Gran Canaria"]
    assert _node("G.phrasen(D)", ["la", "palma", "wandern"]) == ["la palma", "wandern"]
    assert _node("G.phrasen(D)", ["Wilder", "Kaiser", "Ellmau"]) == ["Wilder Kaiser", "Ellmau"]
    assert _node("G.phrasen(D)", ["Val", "d'Orcia"]) == ["Val d'Orcia"]
    assert _node("G.phrasen(D)", ["Gipfel", "Runde"]) == ["Gipfel", "Runde"]
    assert _node("G.phrasen(D)", ["Lungau"]) == ["Lungau"] and _node("G.phrasen(D)", []) == []
