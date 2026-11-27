"""3.64.0 – Gebiete auf dem Server: app/gebiete.json (aus gebiete-daten.js erzeugt) ist aktuell, app/gebiete.py liefert dieselben Gebiete wie der Browser (kein zweites Regelwerk),
automatische Reisenamen aus dem genauesten passenden Gebiet (La Gomera, Lungau, Kanaren …), Vorrang für eigene Namen und eigene Reisen, Eindeutigkeit (Ort, Monat nur wenn nötig).
Die Grenzen der Gebietstabelle sind Näherungen; geprüft wird die Logik, nicht die Lage der Grenzen."""
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401
from tests.gebiete_punkte_362 import PUNKTE

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "app" / "static" / "js" / "gebiete-daten.js"
node = pytest.mark.skipif(not shutil.which("node"), reason="Node nicht installiert")


def _node(expr, data=None):
    code = f"const G = require({json.dumps(str(JS))}); const D = JSON.parse(require('fs').readFileSync(0, 'utf8')); process.stdout.write(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", code], input=json.dumps(data), capture_output=True, text=True, check=True).stdout)


@node
def test_json_ist_aktuell():
    """Die Datei muss genau das enthalten, was das Skript aus gebiete-daten.js erzeugt (sonst: node scripts/gebiete_json.js)."""
    neu = subprocess.run(["node", str(ROOT / "scripts" / "gebiete_json.js"), "--stdout"], capture_output=True, text=True, check=True).stdout
    assert (ROOT / "app" / "gebiete.json").read_text(encoding="utf-8") == neu, "app/gebiete.json ist veraltet: node scripts/gebiete_json.js ausführen"


@node
def test_server_liefert_dieselben_gebiete_wie_der_browser():
    from app import gebiete
    pts = [(p[2], p[3], None) for p in PUNKTE]
    lat = [30 + i * 0.41 for i in range(95)]                 # Raster über Europa, Nordafrika, Kanaren
    lng = [-20 + j * 0.53 for j in range(110)]
    pts += [(a, b, None) for a in lat for b in lng]
    pts += [(-21.07, 55.43, None), (28.18, -17.27, "Irgendwas"), (None, None, "Bezirk Tamsweg"), (None, None, "Landkreis Tamsweg"), (None, None, "Bolzano - Bozen"), (None, None, "Provinz Trient"),
            (None, None, "Savoie"), (None, None, "Reutte"), (0, 0, "Tamsweg"), (99, 200, None), (47.14, 13.67, "Berchtesgadener Land"), ("x", "y", None)]
    # die Bezirke der Tabelle selbst (mit allen Präfixen)
    for x in gebiete._tabelle()[0]:
        for c in x["county"]:
            pts += [(None, None, c), (None, None, "Landkreis " + c), (None, None, "Bezirk " + c), (47.0, 11.0, "Provinz " + c)]
    es = _node("D.map(p => G.von({lat: p[0], lng: p[1], g_county: p[2]}).map(x => x.id))", pts)
    py = [gebiete.von(*p) for p in pts]
    schlecht = [(p, a, b) for p, a, b in zip(pts, es, py) if a != b]
    assert not schlecht, schlecht[:5]
    assert len(pts) > 10000 and sum(1 for x in py if x) > 1000      # es wurde wirklich etwas zugeordnet


@node
def test_fold_wie_im_browser():
    from app import gebiete
    s = ["Straße", "Réunion", "Łódź", "Þórsmörk", "Ærø", "Đakovo", "Sankt Michael im Lungau", "Saint-Martin-Vésubie", "Ðord", "İstanbul", "  ", None, "Bolzano - Bozen", "Œuvre ı"]
    assert gebiete.fold  # vorhanden
    assert [gebiete.fold(x) for x in s] == _node("D.map(x => G.fold(x))", s)


def T(la, ln, county=None):
    return {"lat": la, "lng": ln, "g_county": county}


GOMERA, TENERIFFA, TEIDE, LUNGAU, PONGAU, PINZGAU = (28.18, -17.27), (28.50, -16.40), (28.27, -16.64), (47.14, 13.67), (47.35, 13.20), (47.32, 12.80)


def test_trip_gebiet_regeln():
    from app import gebiete as g
    n = lambda ts: (g.trip_gebiet(ts) or {}).get("name")
    assert n([T(*GOMERA)] * 5) == "La Gomera"                                   # eine Insel: die Insel, nicht der Archipel
    assert n([T(*GOMERA)] * 3 + [T(*TENERIFFA)] * 3) == "Kanaren"               # Rundreise über zwei Inseln: der Oberbegriff, in dem alle liegen
    assert n([T(*GOMERA)] * 4 + [T(*TENERIFFA)] * 2) == "La Gomera"             # 2/3 reichen (mindestens 60 %), häufigstes Gebiet
    assert n([T(*GOMERA)] * 3 + [T(*TENERIFFA)] * 2) == "La Gomera"             # genau 60 %
    assert n([T(*GOMERA)] * 2 + [T(*TENERIFFA)] * 3) == "Teneriffa"
    assert n([T(*TEIDE)] * 3 + [T(*TENERIFFA)] * 2) == "Teide"                  # das genaueste Gebiet mit mindestens 60 % (Teide liegt in Teneriffa)
    assert n([T(*TEIDE)] * 2 + [T(*TENERIFFA)] * 3) == "Teneriffa"
    assert n([T(*LUNGAU)] * 5) == "Lungau"
    assert n([T(None, None, "Tamsweg")] * 4) == "Lungau"                         # nur Bezirk (Touren bis 2025 mit Bezirk, ohne brauchbare Koordinate)
    assert n([T(*LUNGAU)] * 4 + [T(54.1, 12.1)]) == "Lungau"                    # eine Tour außerhalb aller Gebiete zählt mit, 80 %
    assert n([T(*LUNGAU)] * 2 + [T(54.1, 12.1)] * 3) is None                    # zu wenig: Rückfall (Bundesland/Land)
    # Alpen ist als Name zu grob: Lungau/Pongau/Pinzgau gleich verteilt -> kein Gebiet reicht (nur der Oberbegriff) -> Rückfall
    assert n([T(*LUNGAU)] * 3 + [T(*PONGAU)] * 3 + [T(*PINZGAU)] * 3) in (None, "Hohe Tauern")
    assert n([T(54.1, 12.1)] * 5) is None and n([T(None, None)] * 3) is None and n([]) is None
    assert g.trip_gebiet([T(*GOMERA)] * 5)["id"] == "la-gomera" and "alpen" in g.ZU_GROB
    assert n([T(47.30, 11.0)] * 2 + [T(46.50, 11.35)] * 2 + [T(47.14, 13.67)] * 2) is None      # Tirol/Südtirol/Lungau gemischt: nur „Alpen“ gemeinsam -> nicht als Name


def _seed(rows, home=True):
    """rows: [(Name-Kennung, Datum, lat, lng, (Land, Bundesland, Bezirk, Ort) | None)]; dazu 10 Touren zu Hause (München)."""
    from app import db
    from app.gpxtools import TZ
    ts = lambda d: int(datetime.fromisoformat(d + "T10:00:00").replace(tzinfo=TZ).timestamp())

    def add(i, d, la, ln, g):
        db.execute("INSERT INTO tours(id,name,sport,start_ts,dist_m,up_m,dur_s,lat,lng) VALUES(?,?,?,?,?,?,?,?,?)", (i, f"Tour {i}", "hike", ts(d), 10000, 300, 3600, la, ln))
        if g:
            db.execute("INSERT INTO tour_geo(id,country,state,county,place,ts) VALUES(?,?,?,?,?,0)", (i, *g, ))
    if home:
        for k in range(10):
            add(f"h{k}", f"2025-03-{k + 1:02d}", 48.1, 11.5, ("Deutschland", "Bayern", "München", "München"))
    for r in rows:
        add(*r)


def _reisen(monkeypatch):
    from app import more2
    monkeypatch.setattr(more2, "cover_photo", lambda ids: None)
    return more2


KAN = ("Spanien", "Kanarische Inseln", "Santa Cruz de Tenerife", "Vallehermoso")


def test_reisenamen_aus_gebieten(monkeypatch):
    m = _reisen(monkeypatch)
    rows = [(f"g{k}", f"2026-02-{k + 1:02d}", 28.18, -17.27, KAN) for k in range(5)]                                   # La Gomera
    rows += [(f"u{k}", f"2026-05-{k + 1:02d}", 28.18 if k % 2 else 28.27, -17.27 if k % 2 else -16.64, KAN) for k in range(6)]   # beide Inseln
    rows += [(f"l{k}", f"2026-07-{k + 1:02d}", 47.14, 13.67, ("Österreich", "Salzburg", "Bezirk Tamsweg", "Mauterndorf")) for k in range(5)]   # Lungau
    rows += [(f"r{k}", f"2026-09-{k + 1:02d}", 54.1, 12.1, ("Deutschland", "Mecklenburg-Vorpommern", "Rostock", "Rostock")) for k in range(5)]   # kein Gebiet -> wie bisher
    _seed(rows)
    t = {x["id"]: x for x in m.api_trips()}
    assert t["g0"]["region"] == "La Gomera" and t["g0"]["country"] == "Spanien" and t["g0"]["area"] == "la-gomera"
    assert t["u0"]["region"] == "Kanaren" and t["u0"]["base_region"] == "Kanaren"
    assert t["l0"]["region"] == "Lungau" and t["l0"]["country"] == "Österreich"
    assert t["r0"]["region"] == "Mecklenburg-Vorpommern" and t["r0"]["area"] is None
    # Hilfsfelder und Zählung unverändert
    assert t["g0"]["days"] == 5 and len(t["g0"]["tours"]) == 5


def test_eindeutigkeit_ort_und_monat_nur_wenn_noetig(monkeypatch):
    m = _reisen(monkeypatch)
    rows = [(f"a{k}", f"2026-02-{k + 1:02d}", 28.18, -17.27, ("Spanien", "Kanarische Inseln", "Santa Cruz de Tenerife", "Vallehermoso")) for k in range(5)]
    rows += [(f"b{k}", f"2026-03-{k + 1:02d}", 28.12, -17.33, ("Spanien", "Kanarische Inseln", "Santa Cruz de Tenerife", "Valle Gran Rey")) for k in range(5)]
    rows += [(f"c{k}", f"2026-04-{k + 1:02d}", 28.12, -17.33, ("Spanien", "Kanarische Inseln", "Santa Cruz de Tenerife", "Valle Gran Rey")) for k in range(5)]
    rows += [(f"z{k}", f"2026-08-{k + 1:02d}", 47.14, 13.67, ("Österreich", "Salzburg", "Bezirk Tamsweg", "Mauterndorf")) for k in range(5)]
    _seed(rows)
    t = {x["id"]: x for x in m.api_trips()}
    assert t["z0"]["region"] == "Lungau"                                                    # einzige Reise im Gebiet: nur der Name
    assert t["a0"]["region"] == "La Gomera – Vallehermoso"                                  # mehrere im selben Gebiet: Ort
    assert t["b0"]["region"].startswith("La Gomera – Valle Gran Rey (") and t["c0"]["region"].startswith("La Gomera – Valle Gran Rey (")   # gleicher Ort: zusätzlich der Monat
    assert t["b0"]["region"] != t["c0"]["region"] and "Mär" in t["b0"]["region"] and "Apr" in t["c0"]["region"]
    assert len({x["region"] for x in t.values()}) == len(t)


def test_eigener_name_und_eigene_reise_haben_vorrang(monkeypatch):
    m = _reisen(monkeypatch)
    _seed([(f"g{k}", f"2026-02-{k + 1:02d}", 28.18, -17.27, KAN) for k in range(5)])
    assert m.api_trips()[0]["region"] == "La Gomera"
    m.api_trip_edit("g0", {"name": "Wanderwoche Gomera"})
    t = m.api_trips()[0]
    assert t["region"] == "Wanderwoche Gomera" and t["auto_region"] == "La Gomera" and t["edited"]
    m.api_trip_edit("g0", {"name": ""})                                                       # Name leeren: wieder der automatische Name (Gebiet)
    assert m.api_trips()[0]["region"] == "La Gomera"
    c = m.api_trip_create({"name": "Meine Gomera-Reise", "tours": ["g0", "g1", "g2", "g3", "g4"]})["id"]
    assert [x["region"] for x in m.api_trips() if x["id"] == c] == ["Meine Gomera-Reise"]
    assert not any(x["region"] == "La Gomera" for x in m.api_trips())                         # die erkannte Reise ist ersetzt, nicht doppelt


def test_ohne_gebietsdatei_kein_absturz_der_reisenamen(monkeypatch):
    """Die Tabelle wird beim ersten Gebrauch gelesen und gemerkt; ein Name ohne Treffer bleibt Bundesland/Land (kein Gebiet = None)."""
    from app import gebiete
    assert gebiete.von(None, None, None) == [] and gebiete.von("abc", 3) == [] and gebiete.von(0, 0) == []
    assert gebiete.trip_gebiet([{}] * 3) is None
