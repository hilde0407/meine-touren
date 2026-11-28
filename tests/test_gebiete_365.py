"""3.65.0 – Eigene Gebiete und Gebiete-Seiten (Server): Tabelle gebiet_custom, Anlegen/Ändern/Löschen mit Prüfung, Vorrang beim Reisenamen, gleiche Zuordnung wie im Browser (Node),
Suche über Nominatim (ohne Netz: die Rohantwort wird ersetzt; Reihenfolge der boundingbox, Zwischenspeicher, veralteter Treffer bei Ausfall, Nutzungsbedingungen), Fotos nach Gebiet,
Bausteine und Vorlagen der neuen Seiten (Layout), Standard-Abschnitte wie in der Oberfläche, Datensicherung (die Tabelle liegt in der Datenbankdatei).
Die Grenzen der eingebauten Gebiete sind Näherungen; geprüft wird die Logik."""
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "app" / "static" / "js" / "gebiete-daten.js"
node = pytest.mark.skipif(not shutil.which("node"), reason="Node nicht installiert")

GOMERA, TENERIFFA, LUNGAU = (28.18, -17.27), (28.50, -16.40), (47.14, 13.67)
BOX = [47.0, 13.5, 47.3, 13.9]                                    # um den Lungau
KAN = ("Spanien", "Kanarische Inseln", "Santa Cruz de Tenerife", "Vallehermoso")


def _node(expr, data=None):
    code = f"const G = require({json.dumps(str(JS))}); const D = JSON.parse(require('fs').readFileSync(0, 'utf8')); process.stdout.write(JSON.stringify({expr}));"
    return json.loads(subprocess.run(["node", "-e", code], input=json.dumps(data), capture_output=True, text=True, check=True).stdout)


def _neu(name="Mein Revier", typ="region", box=BOX, **kw):
    from app import gebiete as g
    return g.api_eigene_neu({"name": name, "typ": typ, "box": box, **kw})["id"]


def _tour(i, d, la, ln, geo=None):
    from app import db
    from app.gpxtools import TZ
    ts = int(datetime.fromisoformat(d + "T10:00:00").replace(tzinfo=TZ).timestamp())
    db.execute("INSERT INTO tours(id,name,sport,start_ts,dist_m,up_m,dur_s,lat,lng) VALUES(?,?,?,?,?,?,?,?,?)", (i, f"Tour {i}", "hike", ts, 10000, 300, 3600, la, ln))
    if geo:
        db.execute("INSERT INTO tour_geo(id,country,state,county,place,ts) VALUES(?,?,?,?,?,0)", (i, *geo))


# ---------- Anlegen, Ändern, Löschen ----------
def test_tabelle_und_anlegen_aendern_loeschen():
    from app import db, gebiete as g
    cols = [r["name"] for r in db.query("PRAGMA table_info(gebiet_custom)")]
    assert cols == ["id", "name", "typ", "box", "land", "quelle", "created"]
    assert g.api_eigene() == []
    gid = _neu("  Mein   Revier ", "tal", [47.0, 13.5, 47.3, 13.9], land="Österreich", quelle="von Hand")
    assert gid.startswith("eigen-")
    e = g.api_eigene()
    assert len(e) == 1 and e[0]["name"] == "Mein Revier" and e[0]["typ"] == "tal" and e[0]["box"] == BOX and e[0]["land"] == "Österreich" and e[0]["quelle"] == "von Hand"
    g.api_eigene_aendern(gid, {"name": "Neues Revier", "typ": "gebirge", "box": [47.0, 13.0, 47.5, 14.0]})
    e = g.api_eigene()[0]
    assert e["name"] == "Neues Revier" and e["typ"] == "gebirge" and e["box"] == [47.0, 13.0, 47.5, 14.0]
    g.api_eigene_aendern(gid, {"name": "Neues Revier", "typ": "gebirge", "box": [47.0, 13.0, 47.5, 14.0]})      # der eigene Name ist kein Doppelgänger
    g.api_eigene_loeschen(gid)
    assert g.api_eigene() == [] and g.eigene_laden() == ()
    for f in (lambda: g.api_eigene_aendern(gid, {"name": "X", "typ": "tal", "box": BOX}), lambda: g.api_eigene_loeschen(gid)):
        with pytest.raises(HTTPException) as ex:
            f()
        assert ex.value.status_code == 404


@pytest.mark.parametrize("body", [
    {"name": "", "typ": "tal", "box": BOX}, {"name": "   ", "typ": "tal", "box": BOX}, {"name": "a<b", "typ": "tal", "box": BOX}, {"name": "x" * 81, "typ": "tal", "box": BOX},
    {"name": "A", "typ": "see", "box": BOX}, {"name": "A", "box": BOX}, {"name": "A", "typ": "tal"},
    {"name": "A", "typ": "tal", "box": [47, 13]}, {"name": "A", "typ": "tal", "box": "x"}, {"name": "A", "typ": "tal", "box": ["a", 1, 2, 3]},
    {"name": "A", "typ": "tal", "box": [47.3, 13.5, 47.0, 13.9]}, {"name": "A", "typ": "tal", "box": [47.0, 13.9, 47.3, 13.5]},      # Süd > Nord, West > Ost
    {"name": "A", "typ": "tal", "box": [47.0, 13.5, 47.0, 13.9]},                                                                      # leeres Rechteck
    {"name": "A", "typ": "tal", "box": [-91, 0, 0, 1]}, {"name": "A", "typ": "tal", "box": [0, -181, 1, 0]}, {"name": "A", "typ": "tal", "box": [0, 0, 1, 181]},
    {"name": "A", "typ": "tal", "box": [0, 0, 1, float("nan")]}, {"name": "A", "typ": "tal", "box": [0, 0, float("inf"), 1]},
    {"name": "A", "typ": "tal", "box": [0, 0, 31, 1]}, {"name": "A", "typ": "tal", "box": [0, 0, 1, 61]},                              # zu groß
    {"name": "Lungau", "typ": "tal", "box": BOX}, {"name": "lungau", "typ": "tal", "box": BOX},                                       # gibt es eingebaut
])
def test_pruefung_lehnt_ab(body):
    from app import gebiete as g
    with pytest.raises(HTTPException) as ex:
        g.api_eigene_neu(body)
    assert ex.value.status_code == 400
    assert g.api_eigene() == []


def test_name_eindeutig_und_obergrenze(monkeypatch):
    from app import gebiete as g
    a = _neu("Mein Revier")
    with pytest.raises(HTTPException):
        _neu("mein revier")                                     # gleicher Name (ohne Beachtung von Groß/Klein)
    b = _neu("Anderes Revier")
    with pytest.raises(HTTPException):
        g.api_eigene_aendern(b, {"name": "Mein Revier", "typ": "tal", "box": BOX})
    assert a != b
    monkeypatch.setattr(g, "MAX_EIGENE", 2)
    with pytest.raises(HTTPException) as ex:
        _neu("Drittes Revier")
    assert ex.value.status_code == 400 and "Höchstens 2" in ex.value.detail


# ---------- Zuordnung ----------
def test_von_und_reisename_mit_eigenem_gebiet():
    from app import gebiete as g
    assert "lungau" in g.von(*LUNGAU, None)
    gid = _neu("Mein Revier", "tal", BOX)
    ids = g.von(*LUNGAU, None)
    assert gid in ids and "lungau" in ids                        # eingebaute bleiben zusätzlich zugeordnet
    assert g.von(*GOMERA, None) == g.von(*GOMERA, None, ()) and gid not in g.von(*GOMERA, None)
    t = lambda la, ln: {"lat": la, "lng": ln, "g_county": None}
    assert g.trip_gebiet([t(*LUNGAU)] * 4)["name"] == "Mein Revier"          # eigene Gebiete gehen vor (Tiefe 99)
    assert g.trip_gebiet([t(*LUNGAU)] * 4)["id"] == gid
    assert g.trip_gebiet([t(*LUNGAU)] * 1 + [t(54.1, 12.1)] * 4) is None
    g.api_eigene_loeschen(gid)
    assert g.trip_gebiet([t(*LUNGAU)] * 4)["name"] == "Lungau"               # nach dem Löschen wieder der bisherige Name
    assert g.tour_ids(gid) == []


def test_tour_ids_und_reisenamen(monkeypatch):
    from app import gebiete as g, more2
    monkeypatch.setattr(more2, "cover_photo", lambda ids: None)
    for k in range(10):
        _tour(f"h{k}", f"2025-03-{k + 1:02d}", 48.1, 11.5, ("Deutschland", "Bayern", "München", "München"))
    for k in range(4):
        _tour(f"l{k}", f"2026-07-{k + 1:02d}", 47.14, 13.67, ("Österreich", "Salzburg", "Bezirk Tamsweg", "Mauterndorf"))
    _tour("x0", "2026-07-20", 28.18, -17.27, KAN)
    assert {x["id"]: x for x in more2.api_trips()}["l0"]["region"] == "Lungau"
    gid = _neu("Mein Revier", "tal", BOX)
    assert g.tour_ids(gid) == ["l0", "l1", "l2", "l3"]                        # nach Startzeit
    tr = {x["id"]: x for x in more2.api_trips()}
    assert tr["l0"]["region"] == "Mein Revier" and tr["l0"]["area"] == gid
    g.api_eigene_loeschen(gid)
    assert {x["id"]: x for x in more2.api_trips()}["l0"]["region"] == "Lungau"


@node
def test_server_und_browser_rechnen_mit_eigenen_gebieten_gleich():
    """Dasselbe Raster wie in 3.64.0, jetzt mit drei eigenen Gebieten (Rechteck um den Lungau, Insel, Küste): Gebiete je Punkt in Python und im Browser-Code gleich."""
    from app import gebiete as g
    _neu("Mein Revier", "tal", BOX)
    _neu("Gomera-Süd", "kueste", [28.0, -17.4, 28.1, -17.1])
    _neu("Tiny", "region", [46.9, 11.0, 47.0, 11.1])
    eig = g.api_eigene()
    pts = [(p[0], p[1], None) for p in ([LUNGAU, GOMERA, (28.05, -17.3), (46.95, 11.05), (47.0, 13.5), (47.3, 13.9), (47.3001, 13.9), (46.9, 11.0), (0, 0)])]
    pts += [(30 + i * 0.4, -20 + j * 0.55, None) for i in range(60) for j in range(70)]
    pts += [(None, None, "Tamsweg"), (28.18, -17.27, "Irgendwas"), ("x", "y", None), (99, 200, None)]
    pts += [(47.0 + i * 0.03, 13.5 + j * 0.05, None) for i in range(11) for j in range(9)]
    es = _node("(() => { G.setEigene(D.eig); return D.pts.map(p => G.von({lat: p[0], lng: p[1], g_county: p[2]}).map(x => x.id)); })()", {"eig": eig, "pts": pts})
    py = [g.von(*p) for p in pts]
    schlecht = [(p, a, b) for p, a, b in zip(pts, es, py) if a != b]
    assert not schlecht, schlecht[:5]
    assert sum(1 for x in py if any(i.startswith("eigen-") for i in x)) > 50
    # Reihenfolge der Anzeige: das eigene Gebiet zuerst (Tiefe 99) – auch im Browser
    namen = _node("(() => { G.setEigene(D); return [G.von({lat: 47.14, lng: 13.67}).map(x => x.name), G.nach[D[0].id].quelle, G.nach.lungau.quelle]; })()", eig)
    assert namen[0][0] == "Mein Revier" and "Lungau" in namen[0] and namen[1] == "eigen" and namen[2] == "eingebaut"
    # Reisename aus Tourenliste: gleiche Wahl in beiden Welten
    pj = g.trip_gebiet([{"lat": 47.14, "lng": 13.67, "g_county": None}] * 3)["name"]
    assert pj == "Mein Revier"


@node
def test_json_bleibt_aktuell():
    neu = subprocess.run(["node", str(ROOT / "scripts" / "gebiete_json.js"), "--stdout"], capture_output=True, text=True, check=True).stdout
    assert (ROOT / "app" / "gebiete.json").read_text(encoding="utf-8") == neu


# ---------- Suche (OpenStreetMap / Nominatim) ----------
ROH = [
    {"name": "Lungau", "addresstype": "region", "type": "administrative", "boundingbox": ["47.0", "47.3", "13.5", "13.9"], "display_name": "Lungau, Salzburg, Österreich", "address": {"country": "Österreich"}},
    {"name": "Lungau", "addresstype": "region", "type": "administrative", "boundingbox": ["47.01", "47.31", "13.51", "13.91"], "display_name": "Doppelt", "address": {}},
    {"name": "Wilder Kaiser", "addresstype": "mountain_range", "boundingbox": ["47.5", "47.6", "12.2", "12.4"], "display_name": "Wilder Kaiser, Tirol", "address": {"country": "Österreich"}},
    {"name": "Riesig", "addresstype": "country", "boundingbox": ["30", "70", "0", "70"], "display_name": "Riesig", "address": {}},
    {"name": "Kaputt", "boundingbox": ["a", "b"], "display_name": "Kaputt"},
    {"name": "", "boundingbox": ["1", "2", "3", "4"], "display_name": ""},
    {"name": "Ohne Box"},
    "kein Objekt",
]


def test_treffer_reihenfolge_der_box_und_filter():
    from app import gebiete as g
    r = g._treffer(ROH)
    assert [x["name"] for x in r] == ["Lungau", "Wilder Kaiser", "Riesig"]                       # Doppelgänger, Kaputtes und Namenloses fallen weg
    assert r[0]["box"] == [47.0, 13.5, 47.3, 13.9]                                                 # Nominatim: [Süd, Nord, West, Ost] -> [Süd, West, Nord, Ost]
    assert r[0]["typ"] == "region" and r[0]["land"] == "Österreich" and r[1]["typ"] == "gebirge" and r[1]["art"] == "Gebirge"
    assert r[0]["gross"] is False and r[2]["gross"] is True                                       # zu große Treffer sind gekennzeichnet
    assert g._treffer(None) == [] and g._treffer({"a": 1}) == []


def test_suche_zwischenspeicher_und_ausfall(monkeypatch):
    from app import db, gebiete as g
    n = []

    def fake(q):
        n.append(q)
        return ROH
    monkeypatch.setattr(g, "_nominatim", fake)
    a = g.api_suche("  Lungau  ")
    b = g.api_suche("lungau")                                                                      # gleicher Schlüssel (ohne Groß/Klein): kein zweiter Aufruf
    assert a == b and len(n) == 1 and n[0] == "Lungau"
    # abgelaufen: neu holen
    db.execute("UPDATE geocache SET ts=? WHERE k LIKE 'gsuche:%'", (int(time.time()) - g.SUCHE_TTL - 10,))
    g.api_suche("Lungau")
    assert len(n) == 2

    def down(q):
        raise RuntimeError("nicht erreichbar (ConnectionError)")
    monkeypatch.setattr(g, "_nominatim", down)
    db.execute("UPDATE geocache SET ts=? WHERE k LIKE 'gsuche:%'", (int(time.time()) - g.SUCHE_TTL - 10,))
    assert g.api_suche("Lungau") == a                                                              # Dienst weg: veraltete Treffer statt Fehler
    with pytest.raises(HTTPException) as ex:
        g.api_suche("Unbekanntes Gebiet")
    assert ex.value.status_code == 502 and "Gebietssuche nicht möglich" in ex.value.detail
    with pytest.raises(HTTPException) as ex:
        g.api_suche("x")
    assert ex.value.status_code == 400
    assert g.api_suche("Lungau") == a


def test_nominatim_anfrage_regeln(monkeypatch):
    """Nutzungsbedingungen: eigener User-Agent, höchstens 1 Anfrage je Sekunde (gemeinsame Sperre), nur Suchbegriff und feste Parameter; HTTP-Fehler und Netzfehler werden zu RuntimeError."""
    import requests
    from app import extras, gebiete as g
    calls = []

    class R:
        status_code = 200
        def json(self):
            return []

    def get(url, headers=None, timeout=None, params=None):
        calls.append((url, headers, timeout, params, time.time()))
        return R()
    monkeypatch.setattr(requests, "get", get)
    monkeypatch.setattr(extras, "_last_geo", [time.time()])
    t0 = time.time()
    g._nominatim("Lungau")
    g._nominatim("Pinzgau")
    assert time.time() - t0 >= 1.0                                                                 # die erste Anfrage wartet auf die Sekunde nach der letzten Ortsabfrage
    assert calls[1][4] - calls[0][4] >= 1.0
    url, headers, timeout, params, _ = calls[0]
    assert url == "https://nominatim.openstreetmap.org/search" and headers == extras.UA and "MeineTouren" in headers["User-Agent"]
    assert params["q"] == "Lungau" and params["limit"] == 8 and timeout and set(params) == {"q", "format", "limit", "accept-language", "addressdetails", "dedupe"}
    R.status_code = 429
    with pytest.raises(RuntimeError, match="429"):
        g._nominatim("Lungau")

    def boom(*a, **k):
        raise requests.ConnectionError("x")
    monkeypatch.setattr(requests, "get", boom)
    with pytest.raises(RuntimeError, match="nicht erreichbar"):
        g._nominatim("Lungau")


# ---------- Fotos nach Gebiet ----------
def test_fotos_nach_gebiet():
    from app import db, main
    _tour("l0", "2026-07-01", 47.14, 13.67)
    _tour("x0", "2026-07-02", 28.18, -17.27)
    for i, t in enumerate(("l0", "l0", "x0")):
        db.execute("INSERT INTO photos(path,mtime,size,taken_ts,tour_id) VALUES(?,?,?,?,?)", (f"/p/{i}.jpg", 1.0, 10, 1000 + i, t))
    assert len(main.api_photos(gebiet="lungau")) == 2
    assert len(main.api_photos(gebiet="la-gomera")) == 1
    assert main.api_photos(gebiet="gibt-es-nicht") == []
    gid = _neu("Mein Revier", "tal", BOX)
    assert len(main.api_photos(gebiet=gid)) == 2
    assert len(main.api_photos()) == 3
    assert main.api_photos(gebiet="lungau", limit=1)[0]["tour_name"] == "Tour l0"


def test_backup_enthaelt_die_tabelle(tmp_path):
    """Die Datensicherung ist die ganze Datenbankdatei: die Tabelle gebiet_custom und ihre Zeilen sind in der Sicherung (und damit nach dem Zurückspielen wieder da)."""
    import io
    import zipfile
    from app import extras
    _neu("Mein Revier", "tal", BOX)
    name, data = extras.make_backup()
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        z.extract("komoot_hub.sqlite", tmp_path)
    with sqlite3.connect(tmp_path / "komoot_hub.sqlite") as c:
        assert c.execute("SELECT name, typ FROM gebiet_custom").fetchall() == [("Mein Revier", "tal")]


# ---------- Layout: Seiten, Bausteine, Vorlagen ----------
def test_layout_schluessel_und_standardabschnitte():
    import re
    from app import layout
    assert "gebiete" in layout.KEYS and "gebiet" in layout.KEYS and "gebiete" in layout.NEUE_SEITEN and "gebiet" in layout.NEUE_SEITEN
    assert layout.STD_IDS["gebiete"] == frozenset(("kopf", "liste")) and layout.STD_IDS["gebiet"] == frozenset(("kopf", "kennzahlen", "karte", "monate", "fotos", "vorjahr", "reisen", "touren"))
    js = ROOT / "app" / "static" / "js"
    src = (js / "68-gebiete.js").read_text(encoding="utf-8")
    for key in ("gebiete", "gebiet"):
        i = src.index(f"SL_REG.{key} = [")
        ids = set(re.findall(r'\{id: "([a-z]+)"', src[i:src.index("];", i)]))
        assert ids == layout.STD_IDS[key], key


def test_layout_dokumente_pruefen():
    from app import layout
    assert layout.clean({"order": ["kopf", "liste"], "hidden": []}, "gebiete")["order"] == ["kopf", "liste"]
    assert layout.clean({"order": ["kopf", "kennzahlen", "karte", "monate", "fotos", "reisen", "touren"]}, "gebiet")["order"][0] == "kopf"
    grp = lambda x: {"groups": [{"id": "grpab", "title": "A", "ids": [x]}]}
    assert layout.clean(grp("karte"), "gebiet")["groups"][0]["ids"] == ["karte"]
    assert layout.clean(grp("liste"), "gebiete")["groups"][0]["ids"] == ["liste"]
    for key, x in (("gebiete", "karte"), ("gebiet", "liste"), ("gebiete", "gibtsnicht")):
        with pytest.raises(HTTPException):
            layout.clean(grp(x), key)
    assert "gbzahlen" in layout.GEBIETE_TYPEN and {"gfotos", "gmonate"} <= set(layout.GEBIET_TYPEN)


def test_version_und_dateien_365():
    from app import config
    assert config.VERSION.startswith("3.73.0 · Meine Touren")
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert "js/68-gebiete.js" in html
    assert 'const V = "mt-v165"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    assert 'SL_APPV = "3.73.0"' in (ROOT / "app" / "static" / "js" / "54-ansichten.js").read_text(encoding="utf-8")
