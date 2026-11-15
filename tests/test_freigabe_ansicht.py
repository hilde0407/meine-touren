"""3.25.0 – Teilen mit Ansicht (Backend): Auswahl speichern/prüfen, Migration alter Links, serverseitige Auslieferung je Baustein, Rechte, Datenschutz."""
import json
import math
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401

GEHEIM = ("GEHEIMUHR", "GEHEIMNOTIZ", "GEHEIMWEGPUNKT")


def _seed(with_photo=True):
    """Tour mit Strecke (Höhen), Notiz, Wegpunkten (einer am Start), Puls, Wetter, Uhr-Daten und einem Foto."""
    from PIL import Image
    from app import config, db, metrics, photos, routes, tracks
    config.LIB_DIR.mkdir(parents=True, exist_ok=True)
    config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
    t0 = int(time.time()) - 86400
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES('f1','Freigabe-Tour','hike',?,?,8000,7200,420,400,48,11,'t','komoot')", (t0, t0 + 7200))
    routes.store("f1", [(48 + 0.02 * math.sin(i / 20), 11 + i * 0.0004, 500 + 80 * math.sin(i / 15), (t0 + i * 30) * 1000) for i in range(200)])
    db.execute("INSERT INTO tour_notes(id,note) VALUES('f1','GEHEIMNOTIZ privat')")
    for i, (la, lo) in enumerate([(48.0, 11.0), (48.01, 11.03)]):
        db.execute("INSERT INTO tour_wps(tour_id,ts,lat,lng,note) VALUES('f1',?,?,?,?)", (t0 + 100 * i, la, lo, f"GEHEIMWEGPUNKT {i}"))
    tracks.hr_sidecar("f1").write_text(json.dumps([[i * 60, 110 + i % 30] for i in range(60)]))
    db.execute("INSERT INTO weather(id,js,ts) VALUES('f1',?,?)", (json.dumps({"text": "klar", "tmin": 8, "tmax": 15, "precip": 0.4, "wind": 12, "code": 0, "snow72": 0, "lat": 48.123}), int(time.time())))
    db.execute("INSERT INTO devices(id,name,kind,model,active) VALUES(1,'GEHEIMUHR','zepp','X',1)")
    metrics.store("f1", {"v": 1, "src": "zepp", "device": "GEHEIMUHR", "t0": t0, "t": [0, 100], "series": {"cad": [100, 110]}, "sum": {"kcal": 512}})
    if with_photo:
        p = config.LIB_DIR / "f1.jpg"; Image.new("RGB", (40, 30), "blue").save(p)
        photos._store([(str(p), p.stat().st_mtime, p.stat().st_size, t0 + 60, None, None)]); photos.assign_all()


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _mk(c, **body):
    r = c.post("/api/tours/f1/share", json=body)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_normalize_und_validierung(fresh):
    from app import freigabe_inhalt as fi
    from fastapi import HTTPException
    import pytest
    assert fi.normalize(["fotos", "karte"]) == ["karte", "fotos"]               # feste Reihenfolge
    for bad in ([], ["karte", "uhr"], "karte", [1], ["wege", "fotos"]):          # leer, unbekannt, kein Array, falscher Typ, Wegpunkte ohne Karte
        with pytest.raises(HTTPException) as e:
            fi.normalize(bad)
        assert e.value.status_code == 400
    _seed()
    c = _client()
    assert c.post("/api/tours/f1/share", json={"blocks": ["uhr"]}).status_code == 400
    assert c.post("/api/tours/f1/share", json={"blocks": []}).status_code == 400
    assert c.post("/api/tours/f1/share", json={"blocks": ["karte"], "show": True}).status_code == 400     # Diashows haben feste Inhalte
    assert c.post("/api/tours/nix/share", json={"blocks": ["karte"]}).status_code == 404
    assert c.get("/api/shares").json() == []                                       # nichts wurde angelegt


def test_alte_links_bleiben_unveraendert(fresh):
    """Migration: Spalte per ALTER mit Standard NULL; alte Links liefern exakt den bisherigen Umfang (Karte + Kennzahlen, Fotos nur bei photos=1) – ohne die neuen Inhalte."""
    from app import config, db
    _seed()
    c = _client()
    db.close_all()
    con = sqlite3.connect(str(config.DB_PATH))
    cols = [r[1] for r in con.execute("PRAGMA table_info(shares)")]
    assert "blocks" in cols
    con.execute("ALTER TABLE shares RENAME TO shares_neu")                         # Zustand einer 3.24-Datenbank nachbauen: ohne Spalte blocks
    con.execute("CREATE TABLE shares (token TEXT PRIMARY KEY, tour_id TEXT, photos INTEGER, trim INTEGER, ts INTEGER, exp INTEGER, views INTEGER DEFAULT 0, best INTEGER DEFAULT 0, comments INTEGER DEFAULT 0)")
    con.execute("INSERT INTO shares(token,tour_id,photos,trim,ts) VALUES('alt0','f1',0,1,1),('alt1','f1',1,1,2)")
    con.execute("DROP TABLE shares_neu"); con.commit(); con.close()
    db.close_all()
    db.init()                                                                       # Öffnen ergänzt die Spalte
    from app import auth
    for tk in ("alt0", "alt1"):
        auth.q("INSERT OR REPLACE INTO share_index(token,uid) VALUES(?,?)", (tk, ""))
    a0, a1 = c.get("/api/public/alt0").json(), c.get("/api/public/alt1").json()
    assert a0["blocks"] == ["karte", "zahlen"] and a1["blocks"] == ["karte", "zahlen", "fotos"]
    assert a0["photos"] == [] and len(a1["photos"]) == 1
    assert set(a0) == {"name", "sport", "date", "km", "up_m", "down_m", "h", "coords", "photos", "photo_t", "show", "blocks"}
    assert all(len(p) == 3 for p in a0["coords"])                                  # bisher: mit Höhe, unverändert
    for k in ("prof", "note", "wps", "hr", "wx"):
        assert k not in a0 and k not in a1
    raw = json.dumps(a0) + json.dumps(a1)
    assert not any(g in raw for g in GEHEIM)
    lst = {x["token"]: x for x in c.get("/api/shares").json()}
    assert lst["alt0"]["blocks"] == ["karte", "zahlen"] and lst["alt0"]["custom"] is False
    assert lst["alt1"]["blocks"] == ["karte", "zahlen", "fotos"]
    assert c.get("/pub/alt1/photo/%d?size=200" % a1["photos"][0]).status_code == 200
    assert c.get("/s/alt0").status_code == 200


def test_nur_karte_und_fotos_liefert_nichts_privates(fresh):
    _seed()
    c = _client()
    tk = _mk(c, blocks=["karte", "fotos"])
    r = c.get(f"/api/public/{tk}")
    j = r.json()
    assert j["blocks"] == ["karte", "fotos"] and j["show"] is False
    assert set(j) == {"name", "sport", "date", "blocks", "show", "coords", "photos", "photo_t"}      # keine Kennzahlen, kein Profil, keine Notiz …
    assert all(len(p) == 2 for p in j["coords"])                                   # ohne Höhenwerte
    assert len(j["photos"]) == 1
    assert not any(g in r.text for g in GEHEIM)
    for w in ("note", "hr", "wps", "wx", "prof", "km", "kcal", "cad", "device"):
        assert f'"{w}"' not in r.text
    html = c.get(f"/s/{tk}").text
    assert not any(g in html for g in GEHEIM) and "Pulsverlauf" not in html
    assert c.get(f"/pub/{tk}/photo/{j['photos'][0]}?size=200").status_code == 200


def test_jeder_baustein_einzeln(fresh):
    _seed()
    c = _client()
    def get(*bl, **kw):
        return c.get("/api/public/" + _mk(c, blocks=list(bl), **kw)).json()
    j = get("zahlen")
    assert set(j) == {"name", "sport", "date", "blocks", "show", "km", "up_m", "down_m", "h"} and j["km"] == 8.0
    j = get("karte", trim=False)
    assert "coords" in j and "photos" not in j and "km" not in j
    j = get("hoehe", trim=False)
    assert "coords" not in j and len(j["prof"]) > 10 and all(len(p) == 2 for p in j["prof"]) and j["prof"][0][0] == 0
    j = get("puls")
    assert j["hr"]["max"] >= j["hr"]["avg"] >= j["hr"]["min"] and all(len(p) == 2 for p in j["hr"]["pts"]) and "coords" not in j
    j = get("wetter")
    assert j["wx"] == {"text": "klar", "tmin": 8, "tmax": 15, "precip": 0.4, "wind": 12}      # nur Weißliste: weder Koordinaten noch Schnee
    j = get("notiz")
    assert j["note"] == "GEHEIMNOTIZ privat" and "coords" not in j
    j = get("karte", "wege", trim=False)
    assert len(j["wps"]) == 2 and all("note" not in w for w in j["wps"])               # Wegpunkt-Notizen nur zusammen mit „Notiz“
    j = get("karte", "wege", "notiz", trim=False)
    assert [w["note"] for w in j["wps"]] == ["GEHEIMWEGPUNKT 0", "GEHEIMWEGPUNKT 1"]
    j = get("fotos")
    assert len(j["photos"]) == 1 and "coords" not in j


def test_wegpunkte_am_start_werden_mit_kuerzung_ausgeblendet(fresh):
    _seed()
    c = _client()
    j = c.get("/api/public/" + _mk(c, blocks=["karte", "wege"])).json()                # trim ist Standard
    assert len(j["wps"]) == 1 and abs(j["wps"][0]["lat"] - 48.01) < 1e-6              # der Wegpunkt direkt am Start fehlt
    j = c.get("/api/public/" + _mk(c, blocks=["karte", "wege"], trim=False)).json()
    assert len(j["wps"]) == 2


def test_aendern_per_patch_und_liste(fresh):
    _seed()
    c = _client()
    tk = _mk(c, blocks=["karte", "zahlen", "fotos"])
    assert c.get(f"/pub/{tk}/photo/1?size=200").status_code == 200
    r = c.patch(f"/api/share/{tk}", json={"blocks": ["puls", "karte"]})
    assert r.status_code == 200 and r.json()["blocks"] == ["karte", "puls"] and r.json()["custom"] is True
    j = c.get(f"/api/public/{tk}").json()
    assert "hr" in j and "photos" not in j and "km" not in j
    assert c.get(f"/pub/{tk}/photo/1?size=200").status_code == 404                     # Fotos nicht mehr abrufbar, nicht nur ausgeblendet
    for bad in ([], ["x"], ["wege"], "karte"):
        assert c.patch(f"/api/share/{tk}", json={"blocks": bad}).status_code == 400
    assert c.get(f"/api/public/{tk}").json()["blocks"] == ["karte", "puls"]            # fehlgeschlagene Änderung ändert nichts
    assert c.patch("/api/share/gibtsnicht", json={"blocks": ["karte"]}).status_code == 404
    row = next(x for x in c.get("/api/tours/f1/shares").json() if x["token"] == tk)
    assert row["blocks"] == ["karte", "puls"] and row["photos"] == 0
    c.patch(f"/api/share/{tk}", json={"days": 7})                                      # Laufzeit ändern lässt die Auswahl unberührt
    assert c.get(f"/api/public/{tk}").json()["blocks"] == ["karte", "puls"]
    ds = _mk(c, show=True)
    assert c.patch(f"/api/share/{ds}", json={"blocks": ["karte"]}).status_code == 400
    assert next(x for x in c.get("/api/shares").json() if x["token"] == ds)["blocks"] is None


def test_diashow_unveraendert(fresh):
    _seed()
    c = _client()
    ds = _mk(c, show=True)
    j = c.get(f"/api/public/{ds}").json()
    assert j["show"] is True and "blocks" not in j and len(j["photos"]) == 1 and "km" in j


def test_rechte_und_ungueltiger_token(fresh):
    """Nur der Besitzer ändert/legt an (andere Benutzer sehen den Link nicht, Gäste und Betrachter dürfen nicht), ungültige/widerrufene Token liefern nichts."""
    from fastapi.testclient import TestClient
    from app import main
    _seed()
    with TestClient(main.app) as c:
        assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200
        c.post("/api/users", json={"name": "Anna", "email": "anna@example.com", "password": "annas-pass1", "role": "user"})
        c.post("/api/users", json={"name": "Vera", "email": "vera@example.com", "password": "veras-pass1", "role": "viewer"})
        from app import db
        db.execute("INSERT OR IGNORE INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES('f1','x','hike',1,2,1,1,1,1,'t','komoot')")
        tk = c.post("/api/tours/f1/share", json={"blocks": ["karte"]}).json()["token"]
        gast = TestClient(main.app)
        assert gast.patch(f"/api/share/{tk}", json={"blocks": ["karte", "notiz"]}).status_code == 401
        assert gast.post("/api/tours/f1/share", json={"blocks": ["karte"]}).status_code == 401
        assert gast.get(f"/api/public/{tk}").status_code == 200                       # öffentlich lesbar, aber nur mit Token
        a = TestClient(main.app); a.post("/api/login", json={"name": "anna", "password": "annas-pass1"})
        assert a.patch(f"/api/share/{tk}", json={"blocks": ["karte", "notiz"]}).status_code == 404     # fremder Link
        assert a.delete(f"/api/share/{tk}").status_code == 200 and c.get(f"/api/public/{tk}").status_code == 200   # und er bleibt bestehen
        v = TestClient(main.app); v.post("/api/login", json={"name": "vera", "password": "veras-pass1"})
        assert v.patch(f"/api/share/{tk}", json={"blocks": ["karte", "notiz"]}).status_code in (403, 404)
        assert c.get(f"/api/public/{tk}").json()["blocks"] == ["karte"]
        assert gast.get("/api/public/ungueltig").status_code == 404 and gast.get("/pub/ungueltig/photo/1").status_code == 404
        assert c.patch(f"/api/share/{tk}", json={"blocks": ["karte", "notiz"]}).status_code == 200
        assert c.delete(f"/api/share/{tk}").status_code == 200
        assert gast.get(f"/api/public/{tk}").status_code == 404


def test_ablauf_und_auswahl_zusammen(fresh):
    from app import db
    _seed()
    c = _client()
    tk = _mk(c, blocks=["karte"], days=7)
    db.execute("UPDATE shares SET exp=1 WHERE token=?", (tk,))
    assert c.get(f"/api/public/{tk}").status_code == 410


def test_sicherung_enthaelt_die_auswahl(fresh, tmp_path):
    """Die Sicherung kopiert die ganze Benutzerdatenbank: die gespeicherte Auswahl kommt mit."""
    import io
    import zipfile
    from app import config, db, extras
    _seed()
    c = _client()
    tk = _mk(c, blocks=["karte", "puls"])
    name, data = extras.make_backup(strip_secrets=True)
    out = tmp_path / "b.sqlite"
    out.write_bytes(zipfile.ZipFile(io.BytesIO(data)).read("komoot_hub.sqlite"))
    con = sqlite3.connect(str(out))
    assert con.execute("SELECT blocks FROM shares WHERE token=?", (tk,)).fetchone()[0] == "karte,puls"
    con.close()
