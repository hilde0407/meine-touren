"""3.74.0 – Wanderführer: Ordner für Bücher, Buch und Buchtour umbenennen/verschieben, Import der Tagebuch-Datei, Tournamen angleichen (auch bei Komoot, gemockt).
Alles datumsunabhängig (feste Zeitstempel relativ zu „jetzt“ nur für die Reihenfolge), Komoot nie echt: sync._komoot wird ersetzt, Zugangsdaten sind Platzhalter."""
import base64
import io
import json
import os
import shutil
import sqlite3
import subprocess
import time
from pathlib import Path

import pytest
from PIL import Image

from tests.test_core import fresh  # noqa: F401  (autouse: frische Datenbank je Test)
from app import db, routes, sync

ROOT = Path(__file__).resolve().parent.parent
TAGEBUCH_JS = Path(os.environ.get("MT_TAGEBUCH_REPO", ROOT.parent / "mein-tourentagebuch")) / "android/app/src/main/assets/www/js"


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _setup(c):
    assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200


def _line(lat, lon, n=60):
    return [[round(lat + j * 0.0005, 5), round(lon + j * 0.0004, 5)] for j in range(n)]


def _book(book="Rother Testgebirge", n=3, lat=47.5, lon=11.0):
    for i in range(n):
        db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES(?,?,?,?,?)", (book, f"{i + 1} Tour {i + 1}", json.dumps(_line(lat + i * 0.02, lon)), 3.0 + i, 200 + 10 * i))
    return book


def _walk(tid, name, lat, lon, ts, source=None):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,status,source) VALUES(?,?,?,?,?,?,?,?,?)", (tid, name, "hike", ts, ts + 3600, 3000, 3600, "x", source))
    routes.store(tid, [(lat + j * 0.0005, lon + j * 0.0004 + 0.0002, 500, j) for j in range(60)])


def _png():
    im = Image.new("RGB", (400, 560), (30, 90, 140))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def _packe(pts):
    la = [round(p[0] * 1e5) for p in pts]
    lo = [round(p[1] * 1e5) for p in pts]
    d = lambda a: [v - a[i - 1] if i else v for i, v in enumerate(a)]
    return {"la": d(la), "lo": d(lo)}


def _datei(buecher):
    return {"format": "tourentagebuch-wanderfuehrer", "version": 1, "app": "Mein Tourentagebuch 2.x", "erstellt": "2026-01-01T00:00:00Z", "buecher": buecher}


def _fb(name, touren, **kw):
    return dict({"id": "abc123", "name": name, "touren": [{"id": f"t{i}", "ord": i, "title": t, "km": km, "up": 300, "f": "", "pts": _packe(_line(lat, 9.0))} for i, (t, km, lat) in enumerate(touren)]}, **kw)


def _post(c, url, d):
    return c.post(url, content=json.dumps(d), headers={"content-type": "application/json"})


def _tours(book=None):
    q = "SELECT book,title,km FROM guide_tours" + (" WHERE COALESCE(book,'')=?" if book is not None else "") + " ORDER BY id"
    return db.query(q, (book,) if book is not None else ())


# ------------------------------------------------------------------ Ordner
def test_ordner_anlegen_namen_und_loeschen_behaelt_buecher():
    a, b = _book("Rother Allgäu"), _book("Rother Harz", lat=51.7)
    with _client() as c:
        assert c.get("/api/guides/folders").json() == {"folders": []}
        assert c.post("/api/guides/folders", json={"name": "  Süddeutschland   Wanderungen "}).json()["name"] == "Süddeutschland Wanderungen"
        assert c.post("/api/guides/folders", json={"name": "süddeutschland wanderungen"}).status_code == 409        # ohne Rücksicht auf Groß-/Kleinschreibung und Leerzeichen
        for bad in ("", "   ", "x" * 61, "ohne  ORDNER"):
            assert c.post("/api/guides/folders", json={"name": bad}).status_code == 400, bad
        assert c.post("/api/guides/folders", json={"name": "Mittelgebirge 10"}).status_code == 200
        assert c.post("/api/guides/folders", json={"name": "Mittelgebirge 2"}).status_code == 200
        assert c.get("/api/guides/folders").json()["folders"] == ["Mittelgebirge 2", "Mittelgebirge 10", "Süddeutschland Wanderungen"]   # natürlich sortiert
        assert c.post("/api/guides/folders/move", json={"books": [a, b], "folder": "Mittelgebirge 2"}).json()["moved"] == 2
        g = {x["key"]: x for x in c.get("/api/guides/progress").json()}
        assert g[a]["folder"] == "Mittelgebirge 2" and g[b]["folder"] == "Mittelgebirge 2"
        # Umbenennen: Bücher folgen, Schreibweise ändern geht, vorhandener Name nicht
        assert c.post("/api/guides/folders/rename", json={"name": "mittelgebirge 2", "new": "Mittelgebirge Nord"}).json()["name"] == "Mittelgebirge Nord"
        assert c.post("/api/guides/folders/rename", json={"name": "Mittelgebirge Nord", "new": "mittelgebirge 10"}).status_code == 409
        assert c.post("/api/guides/folders/rename", json={"name": "gibt es nicht", "new": "X"}).status_code == 404
        g = {x["key"]: x for x in c.get("/api/guides/progress").json()}
        assert g[a]["folder"] == "Mittelgebirge Nord"
        # Löschen: nur der Ordner, nie Bücher
        r = c.delete("/api/guides/folders", params={"name": "Mittelgebirge Nord"}).json()
        assert r["books"] == 2
        g = {x["key"]: x for x in c.get("/api/guides/progress").json()}
        assert g[a]["folder"] is None and len(g) == 2 and len(_tours()) == 6
        assert c.delete("/api/guides/folders", params={"name": "Mittelgebirge Nord"}).status_code == 404
        # neuer Name beim Verschieben legt den Ordner an; null nimmt aus dem Ordner
        assert c.post("/api/guides/folders/move", json={"books": [a], "folder": "Neu angelegt"}).status_code == 200
        assert "Neu angelegt" in c.get("/api/guides/folders").json()["folders"]
        assert c.post("/api/guides/folders/move", json={"books": [a], "folder": None}).status_code == 200
        assert {x["key"]: x["folder"] for x in c.get("/api/guides/progress").json()}[a] is None
        assert c.post("/api/guides/folders/move", json={"books": ["Unbekannt"], "folder": "X"}).status_code == 404
        assert c.post("/api/guides/folders/move", json={"books": [], "folder": "X"}).status_code == 400


def test_buch_loeschen_raeumt_ordnerzuordnung_auf_und_leere_ordner_bleiben():
    a = _book("Rother Allgäu")
    with _client() as c:
        c.post("/api/guides/folders", json={"name": "Leer"})
        c.post("/api/guides/folders/move", json={"books": [a], "folder": "Süd"})
        assert c.delete("/api/guides/" + "book:" + a).status_code == 200
        assert db.query("SELECT * FROM guide_book_folder") == []
        assert c.get("/api/guides/folders").json()["folders"] == ["Leer", "Süd"]            # auch Ordner ohne Buch bleiben


def test_ordner_rechte_betrachter_liest_schreibt_nicht():
    a = _book()
    with _client() as c:
        _setup(c)
        c.post("/api/guides/folders/move", json={"books": [a], "folder": "Alpen"})
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        o = _client()
        assert o.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert o.get("/api/guides/folders").json()["folders"] == ["Alpen"]
        assert o.get("/api/guides/progress").json()[0]["folder"] == "Alpen"
        for m, u, kw in (("post", "/api/guides/folders", {"json": {"name": "X"}}), ("post", "/api/guides/folders/rename", {"json": {"name": "Alpen", "new": "Y"}}),
                         ("post", "/api/guides/folders/move", {"json": {"books": [a], "folder": None}}), ("delete", "/api/guides/folders?name=Alpen", {}),
                         ("post", "/api/guides/book/rename", {"json": {"book": a, "name": "Z"}}), ("post", "/api/guides/tour/1", {"json": {"title": "Z"}}),
                         ("post", "/api/guides/import", {"content": "{}"}), ("post", "/api/guides/import/preview", {"content": "{}"}),
                         ("post", "/api/guides/rename-tours", {"json": {"items": []}}), ("post", "/api/guides/rename-undo", {"json": {"batch": "x"}}),
                         ("get", "/api/guides/rename-suggestions", {}), ("get", "/api/guides/rename-log", {})):
            assert getattr(o, m)(u, **kw).status_code == 403, (m, u)
        anon = _client()
        assert anon.get("/api/guides/folders").status_code == 401
        e = _client()
        c.post("/api/users", json={"name": "Eva", "email": "eva@example.com", "password": "evas-pass123", "role": "user"})
        assert e.post("/api/login", json={"name": "eva", "password": "evas-pass123"}).status_code == 200
        assert e.get("/api/guides/folders").json() == {"folders": []}                      # eigene Daten, nicht die fremden


# ------------------------------------------------------------------ Buch und Buchtour
def test_buch_umbenennen_titelbild_und_ordner_folgen():
    a = _book("Rother Allgäu")
    _book("Rother Harz", lat=51.7)
    with _client() as c:
        c.post("/api/guides/cover", params={"book": a}, files={"file": ("x.png", _png(), "image/png")})
        c.post("/api/guides/folders/move", json={"books": [a], "folder": "Süd"})
        assert c.post("/api/guides/book/rename", json={"book": a, "name": "  Rother   Allgäuer Alpen "}).json()["book"] == "Rother Allgäuer Alpen"
        g = {x["key"]: x for x in c.get("/api/guides/progress").json()}
        assert "Rother Allgäu" not in g and g["Rother Allgäuer Alpen"]["cover"] and g["Rother Allgäuer Alpen"]["folder"] == "Süd" and g["Rother Allgäuer Alpen"]["total"] == 3
        assert c.get("/api/guides/cover", params={"book": "Rother Allgäuer Alpen"}).status_code == 200
        assert c.post("/api/guides/book/rename", json={"book": "Rother Allgäuer Alpen", "name": "rother harz"}).status_code == 409   # nie zusammenführen
        assert c.post("/api/guides/book/rename", json={"book": "Rother Allgäuer Alpen", "name": "rother allgäuer alpen"}).status_code == 200   # nur Schreibweise
        assert c.post("/api/guides/book/rename", json={"book": "Nope", "name": "X"}).status_code == 404
        assert c.post("/api/guides/book/rename", json={"book": "Rother Harz", "name": " "}).status_code == 400
        assert c.post("/api/guides/book/rename", json={"book": "Rother Harz", "name": "x" * 81}).status_code == 400


def test_buchtour_umbenennen_verschieben_und_nichts_zusammenfuehren():
    a, b = _book("A", n=2), _book("B", n=1, lat=51.0)
    ids = [r["id"] for r in db.query("SELECT id FROM guide_tours ORDER BY id")]
    with _client() as c:
        assert c.post(f"/api/guides/tour/{ids[0]}", json={"title": "  Neuer   Titel "}).json()["title"] == "Neuer Titel"
        assert c.post(f"/api/guides/tour/{ids[0]}", json={"title": ""}).status_code == 400
        assert c.post("/api/guides/tour/99999", json={"title": "X"}).status_code == 404
        # in ein anderes Buch (vorhandenes ohne Rücksicht auf Schreibweise, sonst neu)
        assert c.post(f"/api/guides/tour/{ids[1]}", json={"book": "b"}).json()["book"] == "B"
        assert sorted(t["title"] for t in _tours("B")) == ["1 Tour 1", "2 Tour 2"] and len(_tours("A")) == 1
        assert c.post(f"/api/guides/tour/{ids[0]}", json={"book": "Ganz neu"}).json()["book"] == "Ganz neu"
        # gleiche Buchtour (Titel und Länge auf 50 m) im Zielbuch: Konflikt, nichts ändert sich
        db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES('A','2 Tour 2',?,4.01,1)", (json.dumps(_line(46, 9)),))
        gid = db.one("SELECT id FROM guide_tours WHERE book='A'")["id"]
        assert c.post(f"/api/guides/tour/{gid}", json={"book": "B"}).status_code == 409
        assert db.one("SELECT book FROM guide_tours WHERE id=?", (gid,))["book"] == "A"
        # gleiche Titel, andere Länge: erlaubt
        db.execute("UPDATE guide_tours SET km=9 WHERE id=?", (gid,))
        assert c.post(f"/api/guides/tour/{gid}", json={"book": "B"}).status_code == 200


def test_letzte_buchtour_verschieben_raeumt_buch_titelbild_und_ordner_auf():
    a, b = _book("Einzel", n=1), _book("Ziel", n=1, lat=51.0)
    db.execute("UPDATE guide_tours SET title='Andere Tour' WHERE book='Ziel'")
    with _client() as c:
        c.post("/api/guides/cover", params={"book": a}, files={"file": ("x.png", _png(), "image/png")})
        c.post("/api/guides/folders/move", json={"books": [a], "folder": "Ordner"})
        gid = db.one("SELECT id FROM guide_tours WHERE book='Einzel'")["id"]
        c.post("/api/wishlist", json={"id": gid, "on": True})
        assert c.post(f"/api/guides/tour/{gid}", json={"book": "Ziel"}).status_code == 200
        assert db.query("SELECT * FROM guide_cover") == [] and db.query("SELECT * FROM guide_book_folder") == []
        assert [x["key"] for x in c.get("/api/guides/progress").json()] == ["Ziel"]
        assert c.delete(f"/api/guides/{gid}").status_code == 200
        assert db.query("SELECT * FROM wishlist") == []                                    # Wunschliste räumt mit auf


def test_hochladen_gleiche_buchtour_nicht_doppelt():
    gpx = '<?xml version="1.0"?><gpx version="1.1" creator="t"><trk><name>%s</name><trkseg>%s</trkseg></trk></gpx>'
    pts = "".join(f'<trkpt lat="{47 + i * 0.001}" lon="11.0"><ele>{500 + i}</ele></trkpt>' for i in range(30))
    with _client() as c:
        items = [{"name": "a.gpx", "gpx": gpx % ("Gipfelrunde", pts)}]
        r = c.post("/api/guides", json={"book": "Rother Test", "items": items}).json()
        assert r["added"] == 1 and r["schon"] == 0
        r = c.post("/api/guides", json={"book": "rother  test", "items": items + [{"name": "b.gpx", "gpx": gpx % ("Andere Runde", pts)}]}).json()      # vorhandenes Buch, andere Schreibweise
        assert r["added"] == 1 and r["schon"] == 1
        assert [t["book"] for t in _tours()] == ["Rother Test", "Rother Test"]


# ------------------------------------------------------------------ Import
def test_import_vorschau_schreibt_nichts_und_importieren_fuegt_nur_neues_hinzu():
    _book("Rother Allgäu", n=2)                                    # Titel „1 Tour 1“ (3,0 km), „2 Tour 2“ (4,0 km)
    d = _datei([
        _fb("rother  allgäu", [("1 Tour 1", 3.02, 47.5), ("2 Tour 2", 9.0, 47.52), ("Ganz neue Tour", 7.5, 46.0)], cover="data:image/jpeg;base64," + base64.b64encode(_png()).decode()),
        _fb("Neues Buch", [("A", 5.0, 45.0), ("A", 5.01, 45.0), ("B", 6.0, 45.1)], ordner="Frankreich", cover="data:image/jpeg;base64," + base64.b64encode(_png()).decode()),
        {"name": "Kaputt", "touren": "x"},
        _fb("Mit kaputter Tour", [("Gut", 4.0, 44.0)]),
    ])
    d["buecher"][3]["touren"].append({"id": "x", "title": "Zu kurz", "km": 1, "pts": {"la": [1], "lo": [1]}})
    with _client() as c:
        before = (_tours(), db.query("SELECT * FROM guide_folders"), db.query("SELECT book FROM guide_cover"))
        p = _post(c, "/api/guides/import/preview", d).json()
        assert (p["neueBuecher"], p["neueTourenInVorhandenen"], p["schon"], p["titelbilder"], p["defekt"]) == (2, 1, 2, 2, 2)
        assert {k["art"] for k in p["konflikte"]} == {"laenge"} and p["konflikte"][0]["titel"] == "2 Tour 2" and p["konflikte"][0]["km_datei"] == 9.0 and p["konflikte"][0]["km_hier"] == 4.0
        assert before == (_tours(), db.query("SELECT * FROM guide_folders"), db.query("SELECT book FROM guide_cover"))        # Vorschau ändert nichts
        r = _post(c, "/api/guides/import", d).json()
        assert (r["neueBuecher"], r["neueTourenInVorhandenen"], r["schon"]) == (2, 1, 2)
        assert [t["title"] for t in _tours("Rother Allgäu")] == ["1 Tour 1", "2 Tour 2", "Ganz neue Tour"]                  # Vorhandenes blieb, nichts überschrieben
        assert db.one("SELECT km FROM guide_tours WHERE title='2 Tour 2'")["km"] == 4.0
        assert [t["title"] for t in _tours("Neues Buch")] == ["A", "B"] and [t["title"] for t in _tours("Mit kaputter Tour")] == ["Gut"]
        assert {r["book"] for r in db.query("SELECT book FROM guide_cover")} == {"Rother Allgäu", "Neues Buch"}
        g = {x["key"]: x for x in c.get("/api/guides/progress").json()}
        assert g["Neues Buch"]["folder"] == "Frankreich" and g["Rother Allgäu"]["folder"] is None and g["Neues Buch"]["cover"] and g["Rother Allgäu"]["total"] == 3
        pts = json.loads(db.one("SELECT pts FROM guide_tours WHERE title='Ganz neue Tour'")["pts"])
        assert len(pts) == 60 and pts[0] == [46.0, 9.0] and abs(pts[-1][0] - (46.0 + 59 * 0.0005)) < 1e-6
        # zweiter Import derselben Datei: nichts Neues, Titelbild „deines bleibt“
        p2 = _post(c, "/api/guides/import/preview", d).json()
        assert (p2["neueBuecher"], p2["neueTourenInVorhandenen"], p2["titelbilder"]) == (0, 0, 0) and any(k["art"] == "cover" for k in p2["konflikte"])
        n = len(_tours())
        _post(c, "/api/guides/import", d)
        assert len(_tours()) == n


def test_import_fremde_datei_version_und_ohne_buch():
    with _client() as c:
        assert _post(c, "/api/guides/import/preview", {"a": 1}).status_code == 400
        assert c.post("/api/guides/import/preview", content="kein json").status_code == 400
        assert _post(c, "/api/guides/import/preview", dict(_datei([]), version=2)).status_code == 400
        assert _post(c, "/api/guides/import/preview", dict(_datei([]), buecher="x")).status_code == 400
        assert _post(c, "/api/guides/import/preview", dict(_datei([]), format="anderes")).status_code == 400
        assert _post(c, "/api/guides/import", _datei([])).json()["neueBuecher"] == 0
        # „(ohne Buch)“ aus dem Export von Meine Touren geht zurück in „ohne Buch“; Strecke auch als Punktliste
        d = _datei([{"name": "(ohne Buch)", "touren": [{"title": "Lose Tour", "km": 2.5, "up": None, "pts": [[47.0, 11.0, 500], [47.001, 11.0], [47.002, 11.0, 510]]}]}])
        assert _post(c, "/api/guides/import", d).json()["neueBuecher"] == 1
        assert db.one("SELECT COALESCE(book,'') b, up FROM guide_tours") == {"b": "", "up": None}
        assert _post(c, "/api/guides/import", d).json()["schon"] == 1


def test_kreislauf_export_import_mit_ordner_und_titelbild():
    a = _book("Rother Allgäu")
    with _client() as c:
        c.post("/api/guides/cover", params={"book": a}, files={"file": ("x.png", _png(), "image/png")})
        c.post("/api/guides/folders/move", json={"books": [a], "folder": "Süd"})
        ex = c.get("/api/guides/export", params={"cover": 1}).json()
        assert ex["buecher"][0]["ordner"] == "Süd" and ex["buecher"][0]["cover"].startswith("data:image/jpeg")
        assert c.get("/api/guides/export").json()["buecher"][0]["ordner"] == "Süd"
        c.delete("/api/guides/book:" + a)
        assert c.get("/api/guides/progress").json() == []
        r = _post(c, "/api/guides/import", ex).json()
        assert (r["neueBuecher"], r["titelbilder"]) == (1, 1)
        g = c.get("/api/guides/progress").json()[0]
        assert g["key"] == a and g["total"] == 3 and g["folder"] == "Süd" and g["cover"]
        assert [t["title"] for t in _tours()] == ["1 Tour 1", "2 Tour 2", "3 Tour 3"] and [t["km"] for t in _tours()] == [3.0, 4.0, 5.0]


@pytest.mark.skipif(not shutil.which("node") or not (TAGEBUCH_JS / "calc-fuehrer-datei.js").exists(), reason="Node oder Tagebuch-Repo nicht vorhanden")
def test_echte_datei_des_tagebuchs_wird_gelesen(tmp_path):
    code = ("const Fu = require(%r), D = require(%r);"
            "const pts = n => Array.from({length: n}, (_, i) => ({lat: 47.1 + i * 0.0005, lon: 11.2 + i * 0.0004, ele: 800 + i}));"
            "const buecher = [{id: 'k3j2h1g0a', name: 'Rother Karwendel', created: 1, next: 2, cover: 0, touren: [{id: 't0', ord: 0, title: '1 Karwendelrunde', km: 12.3, up: 640, f: ''}, {id: 't1', ord: 1, title: '2 Seetour', km: 5.5, up: null, f: ''}]}];"
            "const p = {k3j2h1g0a: {t0: Fu.packe(pts(80)), t1: Fu.packe(pts(40))}};"
            "console.log(JSON.stringify(D.exportiere(buecher, p, {}, {k3j2h1g0a: {t0: [{start: 1700000000000, name: 'Meine Runde'}]}}, {})));"
            ) % (str(TAGEBUCH_JS / "calc-fuehrer.js"), str(TAGEBUCH_JS / "calc-fuehrer-datei.js"))
    text = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout
    with _client() as c:
        p = c.post("/api/guides/import/preview", content=text, headers={"content-type": "application/json"}).json()
        assert (p["neueBuecher"], p["defekt"], p["neueTourenInNeuenBuechern"]) == (1, 0, 2)
        assert c.post("/api/guides/import", content=text, headers={"content-type": "application/json"}).json()["neueBuecher"] == 1
        assert [(t["title"], t["km"]) for t in _tours("Rother Karwendel")] == [("1 Karwendelrunde", 12.3), ("2 Seetour", 5.5)]
        assert db.one("SELECT up FROM guide_tours WHERE title LIKE '1 %'")["up"] == 640
        back = c.get("/api/guides/export").json()["buecher"][0]                              # und zurück: das Tagebuch liest die Meine-Touren-Datei
    f = tmp_path / "e.json"
    f.write_text(json.dumps(dict(back, **{})) if False else json.dumps({"format": "tourentagebuch-wanderfuehrer", "version": 1, "buecher": [back]}), encoding="utf-8")
    out = subprocess.run(["node", "-e", f"const D=require({str(TAGEBUCH_JS / 'calc-fuehrer-datei.js')!r}); const r=D.lies(require('fs').readFileSync({str(f)!r},'utf8')); console.log(r.defekt, r.buecher[0].touren.length, r.buecher[0].name)"],
                         capture_output=True, text=True, check=True).stdout.split()
    assert out[0] == "0" and out[1] == "2"


# ------------------------------------------------------------------ Sicherung und Migration
def test_ordner_in_der_sicherung_und_alte_datenbank_ohne_tabellen(tmp_path):
    from app import extras, backup_check
    a = _book()
    with _client() as c:
        c.post("/api/guides/folders", json={"name": "Leerer Ordner"})
        c.post("/api/guides/folders/move", json={"books": [a], "folder": "Süd"})
    p = extras.make_backup(tmp_path, keep=0)
    import zipfile
    with zipfile.ZipFile(p) as z:
        z.extract("komoot_hub.sqlite", tmp_path / "x")
    con = sqlite3.connect(tmp_path / "x" / "komoot_hub.sqlite")
    assert sorted(r[0] for r in con.execute("SELECT name FROM guide_folders")) == ["Leerer Ordner", "Süd"]
    assert con.execute("SELECT book, fk FROM guide_book_folder").fetchall() == [(a, "süd")]
    con.close()
    assert backup_check.pruefe_zip(p, tief=True)["ok"]
    # abwärtskompatibel: eine Datenbank ohne die neuen Tabellen wird beim Öffnen ergänzt, vorhandene Bücher bleiben
    db.execute("DROP TABLE guide_folders")
    db.execute("DROP TABLE guide_book_folder")
    db.execute("DROP TABLE guide_rename_log")
    db.close_all()
    db.init()
    db.init()                                                                          # idempotent
    assert len(_tours(a)) == 3 and db.query("SELECT * FROM guide_folders") == []
    with _client() as c:
        assert c.get("/api/guides/progress").json()[0]["folder"] is None


# ------------------------------------------------------------------ Tournamen angleichen (Komoot gemockt)
class FakeK:
    def __init__(self, fail=()):
        self.renamed, self.fail = [], set(fail)

    def rename(self, tid, name):
        if str(tid) in self.fail:
            raise RuntimeError("Umbenennen bei Komoot fehlgeschlagen (HTTP 403): Forbidden")
        self.renamed.append((str(tid), name))


def _aufbau():
    """Zwei Bücher, drei gewanderte Touren (zwei bei Komoot, eine lokal), die Namen weichen ab; eine Tour heißt schon wie die Buchtour."""
    _book("Rother Testgebirge", n=3)
    now = int(time.time())
    _walk("k1", "Mittwochsrunde", 47.5, 11.0, now - 86400 * 3)                          # Buchtour 1
    _walk("k2", "Seeumrundung", 47.52, 11.0, now - 86400 * 2)                           # Buchtour 2
    _walk("l1", "Lokale Tour", 47.54, 11.0, now - 86400, source="local")               # Buchtour 3
    return now


def test_vorschlaege_aus_dem_gewandert_abgleich(monkeypatch):
    _aufbau()
    with _client() as c:
        d = c.get("/api/guides/rename-suggestions").json()
        assert d["komoot_moeglich"] is False and d["komoot_grund"] == "Komoot ist nicht verbunden"
        by = {x["tour"]: x for x in d["items"]}
        assert set(by) == {"k1", "k2", "l1"} and by["k1"]["title"] == "1 Tour 1" and by["k1"]["name"] == "Mittwochsrunde" and by["k1"]["komoot"] is True and by["l1"]["komoot"] is False
        assert [x["tour"] for x in d["items"]] == ["l1", "k2", "k1"]                    # neueste zuerst
        db.execute("UPDATE tours SET name='1 tour  1' WHERE id='k1'")                  # schon gleich (Schreibweise egal) -> kein Vorschlag
        assert "k1" not in {x["tour"] for x in c.get("/api/guides/rename-suggestions").json()["items"]}
        db.put("komoot_email", "geheim@example.com"); db.put("komoot_password", "Pw-nicht-im-Log")
        assert c.get("/api/guides/rename-suggestions").json()["komoot_moeglich"] is True


def test_umbenennen_nur_lokal_ruft_komoot_nie_auf_protokoll_und_rueckgaengig(monkeypatch):
    _aufbau()
    monkeypatch.setattr(sync, "_komoot", lambda fresh=False: (_ for _ in ()).throw(AssertionError("Komoot darf nicht aufgerufen werden")))
    with _client() as c:
        r = c.post("/api/guides/rename-tours", json={"items": [{"tour": "k1", "name": "1 Tour 1"}, {"tour": "l1", "name": "3 Tour 3"}]}).json()
        assert r["umbenannt"] == 2 and r["bei_komoot"] == 0 and r["fehler"] == 0
        assert db.one("SELECT name FROM tours WHERE id='k1'")["name"] == "1 Tour 1"
        log = c.get("/api/guides/rename-log").json()["items"]
        assert {(x["tour_id"], x["old"], x["new"], x["komoot"]) for x in log} == {("k1", "Mittwochsrunde", "1 Tour 1", 0), ("l1", "Lokale Tour", "3 Tour 3", 0)}
        # Rückgängig: nur Touren, die noch den protokollierten Namen tragen
        db.execute("UPDATE tours SET name='Von Hand geändert' WHERE id='l1'")
        u = c.post("/api/guides/rename-undo", json={"batch": r["batch"]}).json()
        assert u["zurueckgesetzt"] == 1 and u["fehler"] == 1
        assert db.one("SELECT name FROM tours WHERE id='k1'")["name"] == "Mittwochsrunde" and db.one("SELECT name FROM tours WHERE id='l1'")["name"] == "Von Hand geändert"
        assert c.post("/api/guides/rename-undo", json={"batch": r["batch"]}).status_code == 200          # l1 war nicht zurückgesetzt -> bleibt offen
        assert c.post("/api/guides/rename-undo", json={"batch": "gibtesnicht"}).status_code == 404
        # ungültige Namen und unbekannte Touren: Fehler je Tour, der Rest läuft
        r2 = c.post("/api/guides/rename-tours", json={"items": [{"tour": "k2", "name": "  "}, {"tour": "nix", "name": "X"}, {"tour": "k2", "name": "2 Tour 2"}]}).json()
        assert [x["ok"] for x in r2["ergebnisse"]] == [False, False, True] and r2["umbenannt"] == 1 and r2["fehler"] == 2
        assert c.post("/api/guides/rename-tours", json={"items": []}).status_code == 400


def test_bei_komoot_umbenennen_braucht_bestaetigung_zugang_und_meldet_fehler_je_tour(monkeypatch):
    _aufbau()
    k = FakeK(fail={"k2"})
    monkeypatch.setattr(sync, "_komoot", lambda fresh=False: k)
    items = [{"tour": "k1", "name": "1 Tour 1"}, {"tour": "k2", "name": "2 Tour 2"}, {"tour": "l1", "name": "3 Tour 3"}]
    with _client() as c:
        # ohne Zugangsdaten: klare Meldung, nichts geändert
        r = c.post("/api/guides/rename-tours", json={"items": items, "komoot": True, "bestaetigt": 2})
        assert r.status_code == 400 and "nicht verbunden" in r.json()["detail"] and not k.renamed
        assert db.one("SELECT name FROM tours WHERE id='k1'")["name"] == "Mittwochsrunde"
        db.put("komoot_email", "geheim@example.com"); db.put("komoot_password", "Pw-nicht-im-Log")
        # ohne (oder mit falscher) Bestätigung der Anzahl: nichts geschieht
        for bad in (None, 1, 3, "2"):
            body = {"items": items, "komoot": True}
            if bad is not None:
                body["bestaetigt"] = bad
            assert c.post("/api/guides/rename-tours", json=body).status_code == 400, bad
        assert not k.renamed and db.one("SELECT name FROM tours WHERE id='k1'")["name"] == "Mittwochsrunde"
        # ohne den Schalter nie bei Komoot (Vorgabe aus), auch wenn Zugangsdaten da sind
        c.post("/api/guides/rename-tours", json={"items": [{"tour": "k1", "name": "Nur lokal"}]})
        assert not k.renamed
        c.post("/api/guides/rename-tours", json={"items": [{"tour": "k1", "name": "Mittwochsrunde"}]})
        # mit Bestätigung: k1 klappt, k2 scheitert bei Komoot (lokal trotzdem umbenannt, Fehler genannt), l1 (lokale Tour) hat keinen Komoot-Eintrag
        r = c.post("/api/guides/rename-tours", json={"items": items, "komoot": True, "bestaetigt": 2}).json()
        by = {x["tour"]: x for x in r["ergebnisse"]}
        assert k.renamed == [("k1", "1 Tour 1")] and by["k1"]["komoot"] is True and by["k2"]["komoot"] is False and by["l1"]["komoot"] is None
        assert "HTTP 403" in by["k2"]["komoot_fehler"] and "geheim@example.com" not in json.dumps(r) and "Pw-nicht-im-Log" not in json.dumps(r)
        assert r["umbenannt"] == 3 and r["bei_komoot"] == 1 and r["fehler"] == 1
        assert db.one("SELECT name FROM tours WHERE id='k2'")["name"] == "2 Tour 2"
        log = {x["tour_id"]: x for x in c.get("/api/guides/rename-log").json()["items"] if x["batch"] == r["batch"]}
        assert log["k1"]["komoot"] == 1 and log["k2"]["komoot"] == 0 and log["l1"]["komoot"] == 0
        # Rückgängig bei Komoot nur mit Schalter und Bestätigung der Anzahl (hier 1)
        assert c.post("/api/guides/rename-undo", json={"batch": r["batch"], "komoot": True}).status_code == 400
        u = c.post("/api/guides/rename-undo", json={"batch": r["batch"], "komoot": True, "bestaetigt": 1}).json()
        assert u["zurueckgesetzt"] == 3 and k.renamed[-1] == ("k1", "Mittwochsrunde") and len(k.renamed) == 2
        assert db.one("SELECT name FROM tours WHERE id='k2'")["name"] == "Seeumrundung"


def test_komoot_zugangsdaten_stehen_nie_in_der_fehlermeldung(monkeypatch):
    _aufbau()
    db.put("komoot_email", "geheim@example.com"); db.put("komoot_password", "Pw-nicht-im-Log")

    def boom(fresh=False):
        raise RuntimeError("Anmeldung für geheim@example.com mit Pw-nicht-im-Log abgelehnt")
    monkeypatch.setattr(sync, "_komoot", boom)
    with _client() as c:
        r = c.post("/api/guides/rename-tours", json={"items": [{"tour": "k1", "name": "1 Tour 1"}], "komoot": True, "bestaetigt": 1}).json()
        t = json.dumps(r, ensure_ascii=False)
        assert "geheim@example.com" not in t and "Pw-nicht-im-Log" not in t and r["fehler"] == 1 and r["ergebnisse"][0]["komoot"] is False
        assert db.one("SELECT name FROM tours WHERE id='k1'")["name"] == "1 Tour 1"        # lokal trotzdem umbenannt


def test_rechte_liste_buchtour_ordner():
    from app import main
    assert main.VIEWER_GET.match("/api/guides/folders") and main.VIEWER_GET.match("/api/guides/export")
    for u in ("/api/guides/rename-suggestions", "/api/guides/rename-log", "/api/guides/import", "/api/guides/book/rename", "/api/guides/folders/move"):
        assert not main.VIEWER_GET.match(u), u


def test_zip_upload_doppel_pruefung_und_buchname_ohne_gross_klein():
    """3.74.0: der ZIP-Upload (3.73.0) nutzt dieselbe Doppel-Prüfung und denselben Buchnamen-Vergleich wie der GPX-Upload."""
    import io
    import zipfile
    from fastapi.testclient import TestClient
    from app import main
    pts = "".join(f'<trkpt lat="{47.5 + j * 0.0005:.5f}" lon="{11.0 + j * 0.0004:.5f}"><ele>{500 + j}</ele></trkpt>' for j in range(30))
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        z.writestr("a.gpx", f'<?xml version="1.0"?><gpx version="1.1"><trk><name>Runde Eins</name><trkseg>{pts}</trkseg></trk></gpx>')
    c = TestClient(main.app)
    up = lambda book: c.post("/api/guides/zip", params={"book": book}, files={"file": ("x.zip", b.getvalue(), "application/zip")}).json()
    r1 = up("Rother Süd")
    assert r1["added"] == 1 and r1["schon"] == 0
    r2 = up("rother  süd")
    assert r2["added"] == 0 and r2["schon"] == 1 and r2["existing"] == 1 and r2["book"] == "Rother Süd"
    assert db.one("SELECT COUNT(DISTINCT book) n FROM guide_tours")["n"] == 1
