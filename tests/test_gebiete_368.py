"""3.68.0 – Gebiete korrigieren und ergänzen, Baustein „Vor einem Jahr in dieser Gegend“ (Server und Quelltext, ohne Browser).
Südtirol ist nur die Provinz Bozen (Sillian, Innervillgraten = Bezirk Lienz und Rabbi = Provinz Trient gehören nicht dazu); neue Gebiete (Niedere Tauern mit Schladminger und Radstädter Tauern, Maltatal,
Gailtaler Alpen, Sierra de las Nieves) und die erweiterte Box des Wilden Kaisers; Browser und Server rechnen mit nichtKreis gleich; die Gebiete-Datei ist aktuell; Server-Prüfung des neuen Bausteins.
Die Grenzen der Gebietstabelle sind Näherungen; geprüft werden Ortslagen, keine Randfälle."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from fastapi import HTTPException

from tests.test_core import fresh  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "app" / "static" / "js"
GEB = JS / "gebiete-daten.js"
node = pytest.mark.skipif(not shutil.which("node"), reason="Node nicht installiert")


def _node(expr, data=None):
    code = f"const G = require({json.dumps(str(GEB))}); const D = JSON.parse(require('fs').readFileSync(0, 'utf8')); process.stdout.write(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", code], input=json.dumps(data), capture_output=True, text=True, check=True).stdout)


def _ids(la, ln, county=None):
    from app import gebiete
    return gebiete.von(la, ln, county, ())


# (Ort, Breite, Länge, Bezirk laut Geocoder)
SUED = [("Meran", 46.67, 11.16, "Autonome Provinz Bozen - Südtirol"), ("Martell", 46.53, 10.72, "Bozen"), ("Riffian", 46.70, 11.17, "Bozen"), ("Sexten", 46.70, 12.35, "Bozen"),
        ("Innichen", 46.735, 12.28, "Bozen"), ("Kalterer See", 46.37, 11.25, None), ("Bruneck", 46.80, 11.94, None)]
NICHT_SUED = [("Sillian", 46.7467, 12.4167, "Bezirk Lienz"), ("Sillian ohne Bezirk", 46.7467, 12.4167, None), ("Innervillgraten", 46.78, 12.37, "Bezirk Lienz"),
              ("Innervillgraten (Rand)", 46.80, 12.30, "Bezirk Lienz"), ("Kartitsch", 46.74, 12.50, "Bezirk Lienz"),
              ("Rabbi", 46.3833, 10.8667, "Autonome Provinz Trient"), ("Rabbi (Rand des Vielecks)", 46.452, 10.80, "Autonome Provinz Trient"), ("Trient", 46.07, 11.12, "Trient")]


@pytest.mark.parametrize("ort", SUED, ids=lambda o: o[0])
def test_suedtirol_ist_die_provinz_bozen(ort):
    assert "suedtirol" in _ids(*ort[1:])


@pytest.mark.parametrize("ort", NICHT_SUED, ids=lambda o: o[0])
def test_osttirol_und_trentino_gehoeren_nicht_zu_suedtirol(ort):
    assert "suedtirol" not in _ids(*ort[1:])


def test_rabbi_am_rand_ist_trentino_nicht_nichts():
    """Das Val di Rabbi liegt im Trentino; die Fläche Südtirols reicht am Rand darüber, der Bezirk entscheidet (und Trentino wird nicht von der Südtirol-Fläche verdrängt)."""
    assert "trentino" in _ids(46.452, 10.80, "Autonome Provinz Trient")
    assert "trentino" in _ids(46.3833, 10.8667, "Autonome Provinz Trient")
    assert "trentino" not in _ids(46.67, 11.16, "Bozen")                             # Meran ist nie im Trentino


def test_bezirk_ohne_koordinate_und_praefixe():
    assert "suedtirol" in _ids(None, None, "Bolzano - Bozen") and "suedtirol" in _ids(None, None, "Autonome Provinz Bozen - Südtirol") and "suedtirol" in _ids(None, None, "Provincia autonoma di Bolzano")
    assert "trentino" in _ids(None, None, "Autonome Provinz Trient") and "suedtirol" not in _ids(None, None, "Bezirk Lienz")


@node
def test_browser_und_server_rechnen_mit_nichtkreis_gleich():
    from app import gebiete
    pts = [(la, ln, c) for _, la, ln, c in SUED + NICHT_SUED]
    pts += [(46.452, 10.80, "Provinz Trento"), (46.75, 12.42, "Bezirk Lienz"), (46.60, 11.2, "Landeck"), (46.6, 11.2, "Imst"), (None, None, "Autonome Provinz Trient"), (None, None, "Provincia autonoma di Bolzano")]
    pts += [(46.3 + i * 0.013, 10.5 + j * 0.017, c) for i in range(30) for j in range(40) for c in (None, "Autonome Provinz Trient", "Bozen", "Bezirk Lienz")]
    es = _node("D.map(p => G.von({lat: p[0], lng: p[1], g_county: p[2]}).map(x => x.id))", pts)
    py = [gebiete.von(*p, ()) for p in pts]
    assert es == py


@node
def test_nichtkreis_ist_in_der_tabelle_und_json_aktuell():
    r = _node("G.nach.suedtirol.nichtKreis")
    assert "Lienz" in r and "Trient" in r and "Trento" in r
    neu = subprocess.run(["node", str(ROOT / "scripts" / "gebiete_json.js"), "--stdout"], capture_output=True, text=True, check=True).stdout
    assert (ROOT / "app" / "gebiete.json").read_text(encoding="utf-8") == neu
    daten = json.loads(neu)["gebiete"]
    assert next(x for x in daten if x["id"] == "suedtirol")["nichtKreis"] == r


# ---------- neue Gebiete ----------
NEU = [("schladminger", "Schladming", 47.3933, 13.6886), ("schladminger", "Haus im Ennstal", 47.3667, 13.53), ("schladminger", "Rohrmoos", 47.36, 13.70), ("schladminger", "Irdning-Donnersbachtal (Donnersbachtal)", 47.40, 14.05),
       ("radstaedter", "Obertauern", 47.25, 13.56), ("maltatal", "Malta", 46.98, 13.37), ("gailtaler", "Greifenburg", 46.75, 13.18), ("sierra-nieves", "Yunquera", 36.7367, -4.94),
       ("wilder-kaiser", "Kirchdorf in Tirol", 47.55, 12.43), ("wilder-kaiser", "St. Johann in Tirol", 47.52, 12.42)]


@pytest.mark.parametrize("gid,ort,la,ln", NEU, ids=lambda x: x if isinstance(x, str) else "")
def test_neue_gebiete(gid, ort, la, ln):
    assert gid in _ids(la, ln)


def test_eltern_und_nachbarn():
    ids = _ids(47.3933, 13.6886)
    assert ids[0] == "schladminger" and "niedere-tauern" in ids and "alpen" in ids              # Schladming: Schladminger Tauern vor dem Dachstein
    assert "radstaedter" in _ids(47.25, 13.56) and "niedere-tauern" in _ids(47.25, 13.56)
    assert "dachstein" in _ids(47.4167, 13.64) and "schladminger" not in _ids(47.4167, 13.64)   # Ramsau bleibt beim Dachstein
    assert "hohetauern" in _ids(46.98, 13.37) and _ids(46.98, 13.37)[0] == "maltatal"
    assert "gailtaler" not in _ids(46.66, 13.00) and "karnische" in _ids(46.60, 12.95)           # Kötschach/Plöckenpass: Karnische Alpen, nicht Gailtaler
    assert [i for i in _ids(36.7367, -4.94) if i != "andalusien"] == ["sierra-nieves"] and "sierra-nieves" not in _ids(36.74, -5.17)   # Ronda liegt außerhalb (Grazalema-Seite)


@node
def test_tabelle_pruefung_und_kennungen():
    assert _node("G.pruefen()") == []
    r = _node("['niedere-tauern', 'schladminger', 'radstaedter', 'maltatal', 'gailtaler', 'sierra-nieves'].map(i => !!G.nach[i])")
    assert all(r)
    assert _node("G.nach['niedere-tauern'].eigen") is False                                       # reiner Oberbegriff, gilt über seine Kinder


# ---------- Baustein „Vor einem Jahr in dieser Gegend“: Server ----------
def test_vorjahr_ist_standardabschnitt_nur_auf_uebersicht_und_gebiet():
    from app import layout
    assert "vorjahr" in layout.STD_IDS["uebersicht"] and "vorjahr" in layout.STD_IDS["gebiet"]
    assert "vorjahr" not in layout.STD_IDS["statistik"] and "vorjahr" not in layout.STD_IDS["reise"]
    doc = {"v": 1, "widgets": [{"id": "vj1", "type": "vorjahr", "cfg": {"n": 8, "title": "Früher hier"}}], "order": ["vj1"], "cfg": {"vorjahr": {"n": 3}}}
    for key in ("uebersicht", "gebiet"):
        out = layout.clean(doc, key)
        assert out["widgets"][0]["type"] == "vorjahr" and out["widgets"][0]["cfg"] == {"n": 8, "title": "Früher hier"} and out["cfg"]["vorjahr"] == {"n": 3}
    for key in ("reise", "statistik", "tour-haupt", "gebiete", "fotos", "karte"):
        with pytest.raises(HTTPException) as e:
            layout.clean({"v": 1, "widgets": [{"id": "vj1", "type": "vorjahr", "cfg": {}}]}, key)
        assert e.value.status_code == 400


def test_vorjahr_konfiguration_streng():
    from app import layout
    for bad in ({"n": 99}, {"n": "x"}, {"n": True}, {"title": "x" * 61}):
        with pytest.raises(HTTPException):
            layout.clean({"v": 1, "widgets": [{"id": "vj1", "type": "vorjahr", "cfg": bad}]}, "uebersicht")


# ---------- Quelltext: Baustein, Filter, Hinweis, Begriff ----------
def test_quelltext_baustein_registry_und_katalog():
    reg = (JS / "49-seitenlayout.js").read_text(encoding="utf-8")
    geb = (JS / "68-gebiete.js").read_text(encoding="utf-8")
    er = (JS / "60-bausteine-erinnerungen.js").read_text(encoding="utf-8")
    assert 'id: "vorjahr", w: "halb", title: "Vor einem Jahr in dieser Gegend", page: "uebersicht", build: "vorjahr"' in reg
    assert 'id: "vorjahr", w: "halb", title: "Vor einem Jahr in dieser Gegend", page: "gebiet", build: "vorjahr"' in geb
    assert 'window.SL_WT.vorjahr = {' in er and 'seiten: ["uebersicht", "gebiet"]' in er and 'cat: "rueck"' in er
    assert "Neu mischen" in er[er.index("window.SL_WT.vorjahr"):] and 'hnState(c, "aus")' in er                # leer = unsichtbar
    assert "heutevor" in (JS / "50-bausteine.js").read_text(encoding="utf-8")                                 # „Heute vor X Jahren“ bleibt daneben bestehen


def test_quelltext_hinweis_nutzt_die_pruefung_des_dialogs():
    src = (JS / "28-reisen.js").read_text(encoding="utf-8")
    assert src.count("TRIP_FERN_KM") == 2 and src.count("TRIP_GEB_MAX") == 2                              # Definition + eine Prüfung (tripAuffaellig) – nicht zweimal
    assert src.count("tripAuffaellig(") == 3                                                                # Definition, Dialog, Reiseseite


def test_quelltext_fotos_filter_wie_tourenliste():
    src = (JS / "04-fotos.js").read_text(encoding="utf-8")
    assert 'data-gsheet id="pgg"' in src and "gebietOpts(G)" in src and "inGebiet(BY[p.tour_id], G)" in src and 'q.get("g")' in src


def test_begriff_holen_einheitlich():
    uebersicht = (JS / "52-bausteine-uebersicht.js").read_text(encoding="utf-8")
    assert "Alle holen" not in uebersicht and "<span>Alle Touren holen</span>" in uebersicht
    for p in list(JS.glob("*.js")) + [ROOT / "docs" / "HANDBUCH.md"]:
        assert "„Alle holen“" not in p.read_text(encoding="utf-8"), p.name
    neu = (JS / "00-i18n-neu.js").read_text(encoding="utf-8")
    assert "Alle Touren holen || Fetch all tours || Récupérer tous les parcours || Obtener todas las rutas" in neu and "Alle holen ||" not in neu
