"""3.40.0 „Wiederherstellung in der Oberfläche“ (Server): Vorprüfung, Token, Tausch der Datenbank im Betrieb, Sicherheitskopie, Rückweg, Rückfall, Grenzen.
Nur Wegwerf-Daten: DATA_DIR der Testumgebung (tests/test_core.py) und tmp_path als Sicherungsordner."""
import io
import os
import sqlite3
import sys
import threading
import time
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401
from app import auth, config, ctx, db, extras, jobs, umzug, wiederherstellung as wh  # noqa: E402


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def bak(tmp_path, monkeypatch):
    """Sicherungsordner je Test (und je Benutzer ein Unterordner, wie im Betrieb)."""
    root = tmp_path / "bak"
    monkeypatch.setattr(config, "backup_dirs", lambda uid=None: [root / uid if uid else root])
    wh._tokens.clear()
    yield root
    wh._tokens.clear()


def _tour(tid, name=None, tage=10):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
               (tid, name or f"Tour {tid}", "hike", int(time.time() - tage * 86400), int(time.time() - tage * 86400 + 100), 10000, 3600, 300, 300, 48.0, 8.0, "tour_recorded"))


def _plan(name):
    db.execute("INSERT INTO plans(name,sport,pts,km,ts) VALUES(?,?,?,?,?)", (name, "hike", "[]", 5.0, int(time.time())))


def _stand():
    """Vollständiger Inhalt der Live-Datenbank (alle Tabellen) – zum Vergleich „nichts verändert“."""
    out = {}
    for t in [r["name"] for r in db.query("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]:
        out[t] = sorted((tuple(r.values()) for r in db.query(f"SELECT * FROM {t}")), key=repr)
    return out


def _baum(*roots):
    """Alle Dateien unter den Ordnern (ohne die flüchtigen -wal/-shm der Datenbanken) mit Größe."""
    out = {}
    for root in roots:
        for p in sorted(Path(root).rglob("*")) if Path(root).exists() else []:
            if p.is_file() and not p.name.endswith(("-wal", "-shm")) and p.suffix != ".sqlite":
                out[str(p)] = p.stat().st_size
            elif p.is_dir():
                out[str(p)] = "dir"
    return out


def _kein_temp():
    return not (config.DATA_DIR / "restore-tmp").exists()


def _check(c, sid, status=200):
    r = c.post("/api/restore/check", json={"id": sid})
    assert r.status_code == status, r.text
    return r.json()


def _run(c, v, status=200, **over):
    body = {"id": v["id"], "token": v["token"], "bestaetigt": True}
    body.update(over)
    r = c.post("/api/restore/run", json=body)
    assert r.status_code == status, r.text
    return r.json()


def _sid(p):
    return f"s:0:{Path(p).name}"


def _upload(c, data, name="sicherung.zip", status=200):
    r = c.post("/api/restore/upload?name=" + name, content=data, headers={"content-type": "application/zip"})
    assert r.status_code == status, r.text
    return r.json()


def _dbbytes(fn=None, schema=True, page_size=None):
    """Bytes einer SQLite-Datei: mit dem heutigen Schema (über die App angelegt) oder roh; fn(conn) füllt sie."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        f = Path(td) / "x.sqlite"
        c = sqlite3.connect(str(f))
        if page_size:
            c.execute(f"PRAGMA page_size={page_size}")
        c.row_factory = sqlite3.Row
        if schema:
            db.migrate(c)
        if fn:
            fn(c)
        c.commit(); c.close()
        return f.read_bytes()


def _zip(path, dbdata=None, extra=None):
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        if dbdata is not None:
            z.writestr("komoot_hub.sqlite", dbdata)
        for n, d in (extra or {}).items():
            z.writestr(n, d)
    return path


def _touren_im_zip(p, tmp_path):
    with zipfile.ZipFile(p) as z:
        z.extract("komoot_hub.sqlite", tmp_path / "ausgepackt")
    m = sqlite3.connect(str(tmp_path / "ausgepackt" / "komoot_hub.sqlite"))
    try:
        return {x[0] for x in m.execute("SELECT id FROM tours")}
    finally:
        m.close()


def _zipbytes(dbdata=None, extra=None):
    b = io.BytesIO()
    _zip(b, dbdata, extra)
    return b.getvalue()


# ------------------------------------------------------------------------------------------------ Liste
def test_liste_neueste_zuerst_mit_groesse_und_kennzeichnung(bak):
    _tour("a1")
    alt = extras.make_backup(str(bak)); os.utime(alt, (time.time() - 5 * 86400,) * 2)
    alt = alt.rename(bak / "meine-touren-2020-01-01_0300.zip")
    kopie = extras.make_backup(str(bak), keep=0, kennung=extras.VOR_RESTORE); os.utime(kopie, (time.time() - 86400,) * 2)
    neu = extras.make_backup(str(bak))
    (bak / "notiz.txt").write_text("kein zip")
    with _client() as c:
        r = c.get("/api/restore/list").json()
    assert [x["name"] for x in r["sicherungen"]] == [neu.name, kopie.name, alt.name]
    assert [x["sicherheitskopie"] for x in r["sicherungen"]] == [False, True, False]
    assert all(x["groesse"] > 100 and x["ts"] > 0 and x["id"].startswith("s:0:") for x in r["sicherungen"])
    assert r["max_mb"] == wh.MAX_UPLOAD // 1_000_000
    assert "vor-wiederherstellung" in kopie.name and len(kopie.stem.rsplit("_", 1)[1]) == 6          # Sekunden im Namen


# ------------------------------------------------------------------------------------------------ Vorprüfung
def test_vorpruefung_zeigt_zahlen_und_aendert_nichts(bak):
    _tour("a1"); _tour("a2"); _plan("P1")
    config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
    (config.TRACK_DIR / "a1.gpx").write_text("<gpx/>")
    p = extras.make_backup(str(bak))
    _tour("a3"); db.execute("DELETE FROM plans"); db.put("home_name", "Zuhause")
    (config.TRACK_DIR / "a3.gpx").write_text("<gpx/>")
    with _client() as c:
        vor_db, vor_baum = _stand(), _baum(config.DATA_DIR, bak)
        v = _check(c, _sid(p))
        assert v["ok"] and v["name"] == p.name and v["token"] and v["gueltig_s"] == wh.TOKEN_TTL
        assert v["zahlen"]["sicherung"] == {"touren": 2, "strecken": 1, "reisen": 0, "plaene": 1, "layouts": 0}
        assert v["zahlen"]["jetzt"] == {"touren": 3, "strecken": 2, "reisen": 0, "plaene": 0, "layouts": 0}
        assert v["alter_h"] is not None and v["alter_h"] < 1 and abs(v["erstellt_ts"] - time.time()) < 120
        assert v["benutzer"] == {"uid": "", "name": "", "ohne_angabe": False} and v["sicherheitskopie"] is False and "db" not in v
        assert v["version_jetzt"] == config.VERSION.split(" ")[0]
        _check(c, _sid(p))                                                           # mehrfach prüfen ist harmlos
    assert _stand() == vor_db and _baum(config.DATA_DIR, bak) == vor_baum and _kein_temp()
    assert len(db._conns) == 1                                                       # die Verbindung zur Kopie ist wieder geschlossen


def test_vorpruefung_zaehlt_reisen_der_sicherung_und_heute(bak):
    now = int(time.time())
    for i in range(12):                                                              # Heimat
        db.execute("INSERT INTO tours(id,name,sport,start_ts,dist_m,lat,lng) VALUES(?,?,?,?,?,?,?)", (f"h{i}", "H", "hike", now - (400 - 20 * i) * 86400, 5000, 48.0, 8.0))
    for i in range(5):                                                               # fünf Tage 600 km entfernt = eine Reise
        db.execute("INSERT INTO tours(id,name,sport,start_ts,dist_m,lat,lng) VALUES(?,?,?,?,?,?,?)", (f"r{i}", "R", "hike", now - (30 - i) * 86400, 5000, 43.0, 3.0))
    p = extras.make_backup(str(bak))
    db.execute("DELETE FROM tours WHERE id LIKE 'r%'")
    with _client() as c:
        v = _check(c, _sid(p))
    assert v["zahlen"]["sicherung"]["reisen"] == 1 and v["zahlen"]["jetzt"]["reisen"] == 0


# ------------------------------------------------------------------------------------------------ Wiederherstellung
def test_wiederherstellung_ersetzt_daten_legt_sicherheitskopie_an_und_ergaenzt_strecken(bak, tmp_path):
    from app import memo
    _tour("a1", "Alt eins"); _tour("a2"); _plan("P1")
    db.execute("INSERT INTO tour_notes(id,note) VALUES('a1','Notiz von damals')")
    db.execute("INSERT INTO shares(token,tour_id,photos,trim,ts) VALUES('tokalt','a1',0,1,1)")
    auth.q("INSERT OR REPLACE INTO share_index(token,uid) VALUES('tokalt','')")
    config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
    (config.TRACK_DIR / "a1.gpx").write_text("<gpx>damals</gpx>"); (config.TRACK_DIR / "a2.gpx").write_text("<gpx>zwei</gpx>")
    dd = config.DB_PATH.parent / "devices"; dd.mkdir(); (dd / "1.jpg").write_bytes(b"jpg")
    p = extras.make_backup(str(bak))
    # danach: Änderungen, die verloren gehen sollen
    db.execute("DELETE FROM tours WHERE id='a2'"); _tour("neu1", "Neu"); db.execute("UPDATE tours SET name='Umbenannt' WHERE id='a1'"); db.execute("DELETE FROM plans")
    db.execute("DELETE FROM tour_notes"); db.execute("DELETE FROM shares"); db.execute("INSERT INTO shares(token,tour_id,photos,trim,ts) VALUES('tokneu','neu1',0,1,2)")
    auth.q("DELETE FROM share_index"); auth.q("INSERT OR REPLACE INTO share_index(token,uid) VALUES('tokneu','')")
    (config.TRACK_DIR / "a1.gpx").write_text("<gpx>heute geändert</gpx>"); (config.TRACK_DIR / "a2.gpx").unlink(); (dd / "1.jpg").unlink()
    db.put("komoot_password", "geheim")                                              # heute gespeichert, in der Sicherung leer
    memo._C[(str(config.DB_PATH), "waechter", "()")] = ((), "alter Wert")            # etwas im Zwischenspeicher
    with _client() as c:
        v = _check(c, _sid(p))
        assert v["zugangsdaten"] == "bleiben"
        r = _run(c, v)
        assert r["ok"] and r["vorher"]["touren"] == 2 and r["nachher"]["touren"] == 2 and r["vorher"]["plaene"] == 0 and r["nachher"]["plaene"] == 1
        assert r["strecken_neu"] == 1 and r["geraete_neu"] == 1 and r["zugangsdaten_behalten"] == 1 and r["hinweise"] == []
        assert {t["id"]: t["name"] for t in db.query("SELECT id,name FROM tours")} == {"a1": "Alt eins", "a2": "Tour a2"}
        assert db.one("SELECT note FROM tour_notes WHERE id='a1'")["note"] == "Notiz von damals"
        assert [t["name"] for t in c.get("/api/tours").json()] and {t["id"] for t in c.get("/api/tours").json()} == {"a1", "a2"}      # die laufende App liefert sofort den neuen Stand
        # Sicherheitskopie: in derselben Liste, erkennbar, enthält den Stand von eben
        ls = c.get("/api/restore/list").json()["sicherungen"]
        k = next(x for x in ls if x["sicherheitskopie"])
        assert k["name"] == r["sicherheitskopie"] and (bak / k["name"]).is_file() and p.is_file()
        assert _touren_im_zip(bak / k["name"], tmp_path) == {"a1", "neu1"}
    # Strecken: fehlende ergänzt, vorhandene nicht überschrieben
    assert (config.TRACK_DIR / "a1.gpx").read_text() == "<gpx>heute geändert</gpx>" and (config.TRACK_DIR / "a2.gpx").read_text() == "<gpx>zwei</gpx>" and (dd / "1.jpg").read_bytes() == b"jpg"
    # Datenbank weiter im WAL-Betrieb, in sich stimmig, dieselbe offene Verbindung
    assert db.one("PRAGMA journal_mode")["journal_mode"] == "wal" and db.one("PRAGMA quick_check")["quick_check"] == "ok"
    assert db.get("komoot_password") == "geheim"                                     # Zugangsdaten von heute behalten
    assert db.get("last_version") == config.VERSION
    assert {r["token"] for r in auth.q("SELECT token FROM share_index")} == {"tokalt"}        # Freigabelinks passen zur zurückgespielten Datenbank
    assert (str(config.DB_PATH), "waechter", "()") not in memo._C                    # Zwischenspeicher geleert
    assert _kein_temp() and not list(bak.glob("*.part"))


def test_rueckweg_ueber_die_sicherheitskopie(bak):
    _tour("a1")
    p = extras.make_backup(str(bak))
    _tour("b1"); _tour("b2"); _plan("heute")
    heute = _stand()
    with _client() as c:
        r = _run(c, _check(c, _sid(p)))
        assert {t["id"] for t in db.query("SELECT id FROM tours")} == {"a1"}
        v = _check(c, _sid(bak / r["sicherheitskopie"]))
        assert v["sicherheitskopie"] is True and v["zahlen"]["sicherung"]["touren"] == 3 and v["zahlen"]["jetzt"]["touren"] == 1
        r2 = _run(c, v)
        assert r2["nachher"]["touren"] == 3 and r2["sicherheitskopie"] != r["sicherheitskopie"]
    jetzt = _stand()
    for t in heute:
        if t != "settings":
            assert jetzt[t] == heute[t], t
    assert len(list(bak.glob("*vor-wiederherstellung*.zip"))) == 2 and p.is_file()


def test_sicherheitskopie_loescht_keine_aelteren_sicherungen(bak):
    _tour("a1")
    p = extras.make_backup(str(bak))
    for i in range(20):
        f = bak / f"meine-touren-2019-01-{i + 1:02d}_0300.zip"; f.write_bytes(p.read_bytes()); os.utime(f, (time.time() - (100 + i) * 86400,) * 2)
    with _client() as c:
        _run(c, _check(c, _sid(bak / "meine-touren-2019-01-20_0300.zip")))           # die älteste wählen
    assert len(list(bak.glob("meine-touren-2019-*.zip"))) == 20


def test_alte_sicherung_wird_auf_das_heutige_schema_umgestellt_auch_mit_anderer_seitengroesse(bak):
    def alt(c):                                                                      # Stand vor 3.17/3.38: plans ohne wps/tour_id/status, kein user_layout
        c.executescript("CREATE TABLE settings (k TEXT PRIMARY KEY, v TEXT);"
                        "CREATE TABLE tours (id TEXT PRIMARY KEY, name TEXT, sport TEXT, start_ts INTEGER, end_ts INTEGER, dist_m REAL, dur_s REAL, up_m REAL, down_m REAL, lat REAL, lng REAL, status TEXT);"
                        "CREATE TABLE plans (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, sport TEXT, pts TEXT, km REAL, up REAL, down REAL, max_alt REAL, est_h REAL, note TEXT, ts INTEGER);"
                        "INSERT INTO settings VALUES('last_version','3.10.0 · Meine Touren (2025-01-01)');"
                        "INSERT INTO tours(id,name,start_ts) VALUES('alt1','Uralt',1600000000);INSERT INTO plans(name) VALUES('Alter Plan');")
    _zip(bak.parent / "x.zip", _dbbytes(alt, schema=False, page_size=1024))
    bak.mkdir(); (bak.parent / "x.zip").rename(bak / "alt.zip")
    _tour("heute1")
    assert db.one("PRAGMA page_size")["page_size"] != 1024
    with _client() as c:
        v = _check(c, "s:0:alt.zip")
        assert v["version"] == "3.10.0" and v["zahlen"]["sicherung"] == {"touren": 1, "strecken": 0, "reisen": 0, "plaene": 1, "layouts": 0}
        _run(c, v)
        assert c.get("/api/plans").status_code == 200
    assert db.one("SELECT name, status, tour_id FROM plans") == {"name": "Alter Plan", "status": "geplant", "tour_id": None}
    assert db.one("SELECT source FROM tours WHERE id='alt1'")["source"] == "komoot" and db.query("SELECT * FROM user_layout") == []
    assert db.one("PRAGMA journal_mode")["journal_mode"] == "wal" and db.one("PRAGMA quick_check")["quick_check"] == "ok"
    _tour("danach")                                                                  # Schreiben geht weiter


# ------------------------------------------------------------------------------------------------ Token
def test_token_nur_fuer_die_gepruefte_datei_einmalig_und_nicht_abgelaufen(bak, monkeypatch):
    _tour("a1")
    p = extras.make_backup(str(bak))
    q = bak / "meine-touren-2021-01-01_0300.zip"; q.write_bytes(p.read_bytes())
    _tour("b1")
    vor = _stand()
    with _client() as c:
        v = _check(c, _sid(p))
        assert "bestätigen" in _run(c, v, 400, bestaetigt=False)["detail"]
        assert "bestätigen" in _run(c, v, 400, bestaetigt="ja")["detail"]
        assert "abgelaufen" in _run(c, v, 409, token="erfunden")["detail"]
        assert "abgelaufen" in _run(c, v, 409, token="")["detail"]
        assert "gehört nicht zu dieser Sicherung" in _run(c, v, 409, id=_sid(q))["detail"]      # Token einer anderen Datei
        # Datei nach der Prüfung verändert (gleicher Name): der Hash passt nicht mehr
        v = _check(c, _sid(p))
        orig = p.read_bytes()
        with zipfile.ZipFile(p, "a") as z:
            z.writestr("tracks/untergeschoben.gpx", "<gpx/>")
        assert "seit der Vorprüfung geändert" in _run(c, v, 409)["detail"]
        p.write_bytes(orig)
        assert "abgelaufen" in _run(c, v, 409)["detail"]                              # und das Token ist damit verbraucht
        # abgelaufen
        v = _check(c, _sid(p))
        wh._tokens[v["token"]]["exp"] = time.time() - 1
        assert "abgelaufen" in _run(c, v, 409)["detail"]
        assert _stand() == vor and not list(bak.glob("*vor-wiederherstellung*")) and _kein_temp()
        # gültig: geht genau einmal
        v = _check(c, _sid(p))
        _run(c, v)
        assert "abgelaufen" in _run(c, v, 409)["detail"]
    assert {t["id"] for t in db.query("SELECT id FROM tours")} == {"a1"}


def _users(c):
    c.post("/api/setup", json={"name": "chef", "email": "chef@example.com", "password": "geheim123"})
    c.post("/api/login", json={"name": "chef", "password": "geheim123"})
    for n, pw, role in (("gast", "geheim456", "user"), ("oma", "omas-pass12", "viewer"), ("zwei", "geheim789", "admin")):
        assert c.post("/api/users", json={"name": n, "email": n + "@example.com", "password": pw, "role": role}).status_code == 200


def _login(n, pw):
    c = _client()
    assert c.post("/api/login", json={"name": n, "password": pw}).status_code == 200
    return c


def test_token_eines_anderen_administrators_gilt_nicht(bak):
    with _client() as c:
        _users(c)
        with ctx.as_user("chef"):
            _tour("c1")
            p = extras.make_backup(str(bak / "chef"))
            _tour("c2")
        v = _check(c, _sid(p))
        assert v["benutzer"] == {"uid": "chef", "name": "chef", "ohne_angabe": False}
        z = _login("zwei", "geheim789")
        r = z.post("/api/restore/run", json={"id": v["id"], "token": v["token"], "bestaetigt": True})
        assert r.status_code == 409 and "gehört nicht" in r.json()["detail"]
        assert z.post("/api/restore/check", json={"id": v["id"]}).status_code == 404         # „zwei“ sieht chefs Sicherungsordner nicht
        assert z.get("/api/restore/list").json()["sicherungen"] == []
        with ctx.as_user("chef"):
            assert db.one("SELECT COUNT(*) n FROM tours")["n"] == 2
        _run(c, v)                                                                            # chef selbst darf
        with ctx.as_user("chef"):
            assert db.one("SELECT COUNT(*) n FROM tours")["n"] == 1
        with ctx.as_user("zwei"):
            assert db.one("SELECT COUNT(*) n FROM tours")["n"] == 0


# ------------------------------------------------------------------------------------------------ Rechte und Benutzer
def test_nur_administratoren_403_fuer_benutzer_und_betrachter(bak):
    with _client() as c:
        _users(c)
        with ctx.as_user("chef"):
            _tour("c1")
            p = extras.make_backup(str(bak / "chef"))
        for n, pw in (("gast", "geheim456"), ("oma", "omas-pass12")):
            x = _login(n, pw)
            assert x.get("/api/restore/list").status_code == 403
            assert x.post("/api/restore/check", json={"id": _sid(p)}).status_code == 403
            assert x.post("/api/restore/run", json={"id": _sid(p), "token": "x", "bestaetigt": True}).status_code == 403
            assert x.post("/api/restore/upload?name=a.zip", content=p.read_bytes()).status_code == 403
            assert x.delete("/api/restore/upload").status_code == 403
        anon = _client()
        assert anon.get("/api/restore/list").status_code == 401 and anon.post("/api/restore/run", json={}).status_code == 401
        assert c.get("/api/restore/list").status_code == 200
    assert _kein_temp()


def test_sicherung_eines_anderen_benutzers_wird_abgelehnt_ohne_angabe_geht_ins_eigene_konto(bak):
    with _client() as c:
        _users(c)
        with ctx.as_user("gast"):
            _tour("g1")
            fremd = extras.make_backup(str(bak / "gast"))
        with ctx.as_user("chef"):
            _tour("c1"); _tour("c2")
            vor = _stand()
        up = _upload(c, fremd.read_bytes(), "von-gast.zip")
        r = c.post("/api/restore/check", json={"id": up["id"]})
        assert r.status_code == 403 and "anderen Benutzer" in r.json()["detail"]
        with ctx.as_user("chef"):
            assert _stand() == vor
        with ctx.as_user("gast"):
            assert db.one("SELECT COUNT(*) n FROM tours")["n"] == 1
        # ohne UID.txt (Sicherung aus dem Betrieb ohne Benutzer): klarer Hinweis, Ziel ist das eigene Konto
        ohne = _zipbytes(_dbbytes(lambda k: k.execute("INSERT INTO tours(id,name,start_ts) VALUES('x1','X',1700000000)")))
        v = _check(c, _upload(c, ohne)["id"])
        assert v["benutzer"] == {"uid": "", "name": "chef", "ohne_angabe": True} and v["upload"] is True
        _run(c, v)
        with ctx.as_user("chef"):
            assert [t["id"] for t in db.query("SELECT id FROM tours")] == ["x1"]
        with ctx.as_user("gast"):
            assert db.one("SELECT COUNT(*) n FROM tours")["n"] == 1
    assert _kein_temp()


def test_ohne_benutzerverwaltung_wird_eine_sicherung_mit_benutzerangabe_abgelehnt(bak):
    _tour("a1")
    data = _zipbytes(_dbbytes(), {"UID.txt": "anna"})
    with _client() as c:
        r = c.post("/api/restore/check", json={"id": _upload(c, data)["id"]})
    assert r.status_code == 403 and "anderen Benutzer" in r.json()["detail"]


# ------------------------------------------------------------------------------------------------ Umzugspaket, defekte und falsche Dateien
def test_umzugspaket_wird_erkannt_und_abgelehnt(bak, tmp_path):
    _tour("a1")
    vor = _stand()
    pkg = umzug.make(config.DATA_DIR, tmp_path / "umz", "test")
    assert umzug.is_package(pkg)
    with _client() as c:
        r = c.post("/api/restore/check", json={"id": _upload(c, pkg.read_bytes(), pkg.name)["id"]})
        assert r.status_code == 400 and "Umzugspaket" in r.json()["detail"] and "Skript" in r.json()["detail"]
        # auch mit Datenbank und Marker zusammen
        r = c.post("/api/restore/check", json={"id": _upload(c, _zipbytes(_dbbytes(), {"UMZUG.txt": "x"}))["id"]})
        assert r.status_code == 400 and "Umzugspaket" in r.json()["detail"]
        c.delete("/api/restore/upload")
    assert _stand() == vor and _kein_temp()


def test_defekte_leere_und_falsche_dateien_mit_verstaendlicher_meldung_und_ohne_aenderung(bak, monkeypatch):
    _tour("a1")
    gut = extras.make_backup(str(bak))
    vor_db = _stand()
    faelle = {
        "kein-zip.zip": (b"das ist kein zip, nur text" * 20, "kein lesbares ZIP"),
        "abgeschnitten.zip": (gut.read_bytes()[:400], "kein lesbares ZIP"),
        "ohne-db.zip": (_zipbytes(None, {"INFO.txt": "x", "tracks/a.gpx": "<gpx/>"}), "fehlt in der Sicherung"),
        "db-kaputt.zip": (_zipbytes(b"SQLite format 3\x00" + os.urandom(5000)), "Datenbank in der Sicherung ist beschädigt"),
        "db-muell.zip": (_zipbytes(b"kein sqlite" * 100), "Datenbank in der Sicherung ist beschädigt"),
        "fremde-db.zip": (_zipbytes(_dbbytes(lambda k: k.execute("CREATE TABLE rezepte (id INTEGER)"), schema=False)), "gehört nicht zu Meine Touren"),
        "neuer.zip": (_zipbytes(_dbbytes(lambda k: k.execute("INSERT INTO settings VALUES('last_version','99.1.0 · Meine Touren (2031-01-01)')"))), "neueren Programmversion (99.1.0)"),
    }
    with _client() as c:
        for name, (data, erwartet) in faelle.items():
            for weg in ("upload", "server"):
                if weg == "upload":
                    sid = _upload(c, data, name)["id"]
                else:
                    (bak / name).write_bytes(data); sid = "s:0:" + name
                r = c.post("/api/restore/check", json={"id": sid})
                assert r.status_code == 400 and erwartet in r.json()["detail"], (name, weg, r.text)
                assert "Traceback" not in r.text and len(r.json()["detail"]) < 400
                assert c.post("/api/restore/run", json={"id": sid, "token": "", "bestaetigt": True}).status_code == 409
                (bak / name).unlink(missing_ok=True)
        # leer
        assert "leer" in _upload(c, b"", "leer.zip", 400)["detail"]
        (bak / "leer.zip").write_bytes(b"")
        r = c.post("/api/restore/check", json={"id": "s:0:leer.zip"}); assert r.status_code == 400 and "leer" in r.json()["detail"]
        (bak / "leer.zip").unlink()
        # zu groß (Limit für den Test klein)
        monkeypatch.setattr(wh, "MAX_UPLOAD", 1000)
        assert "zu groß (höchstens 0 MB)" in _upload(c, b"x" * 5000, "gross.zip", 413)["detail"]
        # unbekannte und unzulässige Kennungen
        for sid in ("s:0:gibtsnicht.zip", "s:0:../../etc/passwd", "s:9:x.zip", "u:0123456789abcdef", "u:../x", "", None, 7):
            assert c.post("/api/restore/check", json={"id": sid}).status_code == 404, sid
        c.delete("/api/restore/upload")
    assert _stand() == vor_db and _kein_temp() and sorted(f.name for f in bak.iterdir()) == [gut.name]


def test_schema_umstellung_scheitert_an_der_kopie_dann_ablehnung(bak):
    # „tours“ ist in dieser Datei eine Sicht: die Umstellung (ALTER TABLE) kann nicht laufen
    def kaputt(k):
        k.executescript("CREATE TABLE settings (k TEXT PRIMARY KEY, v TEXT); CREATE TABLE tours (id TEXT); CREATE TABLE photos (id INTEGER); CREATE VIEW shares AS SELECT 1 AS token;")
    _tour("a1")
    vor = _stand()
    with _client() as c:
        r = c.post("/api/restore/check", json={"id": _upload(c, _zipbytes(_dbbytes(kaputt, schema=False)))["id"]})
        assert r.status_code == 400 and "passt nicht zu dieser Programmversion" in r.json()["detail"]
        c.delete("/api/restore/upload")
    assert _stand() == vor and _kein_temp() and len(db._conns) == 1


# ------------------------------------------------------------------------------------------------ Zip-Slip
def test_zip_slip_wird_abgelehnt_und_nichts_landet_ausserhalb(bak, tmp_path):
    _tour("a1")
    vor_db = _stand()
    boese = ["../boese.gpx", "tracks/../../boese.gpx", "/tmp/boese.gpx", "tracks\\..\\boese.gpx", "devices/../../../boese.jpg", "C:/boese.gpx"]
    with _client() as c:
        for n in boese:
            vor = _baum(config.DATA_DIR.parent)
            r = c.post("/api/restore/check", json={"id": _upload(c, _zipbytes(_dbbytes(), {n: "<gpx>böse</gpx>"}))["id"]})
            assert r.status_code == 400 and "unzulässige Dateipfade" in r.json()["detail"], n
            c.delete("/api/restore/upload")
            assert _baum(config.DATA_DIR.parent) == vor, n
        # harmlose, aber unpassende Einträge werden schlicht nicht ausgepackt
        extra = {"tracks/gut.gpx": "<gpx>gut</gpx>", "tracks/gut.hr.json": "{}", "tracks/unter/ordner.gpx": "x", "tracks/.versteckt.gpx": "x", "tracks/skript.sh": "x",
                 "devices/7.jpg": "jpg", "devices/7.exe": "x", "anderes/x.gpx": "x", "system.sqlite": "x", "tracks/": ""}
        config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
        v = _check(c, _upload(c, _zipbytes(_dbbytes(), extra))["id"])
        assert v["zahlen"]["sicherung"]["strecken"] == 1
        r = _run(c, v)
        assert r["strecken_neu"] == 2 and r["geraete_neu"] == 1
    assert sorted(f.name for f in config.TRACK_DIR.iterdir()) == ["gut.gpx", "gut.hr.json"]
    assert sorted(f.name for f in (config.DB_PATH.parent / "devices").iterdir()) == ["7.jpg"]
    assert not list(config.DATA_DIR.parent.rglob("boese*")) and not list(config.DATA_DIR.rglob("*.sh")) and _kein_temp()
    assert vor_db["tours"] != _stand()["tours"]


def test_strecken_ergaenzen_folgt_keinem_symlink(bak, tmp_path):
    _tour("a1")
    config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
    ziel = tmp_path / "ausserhalb.txt"; ziel.write_text("bleibt")
    try:
        (config.TRACK_DIR / "link.gpx").symlink_to(ziel)
    except OSError:
        pytest.skip("keine Symlinks")
    z = _zip(tmp_path / "s.zip", _dbbytes(), {"tracks/link.gpx": "<gpx>überschreiben?</gpx>"})
    assert wh._ergaenzen(z) == (0, 0) and ziel.read_text() == "bleibt"


# ------------------------------------------------------------------------------------------------ Sperre
def test_sperre_gegen_gleichzeitige_sicherung_und_wiederherstellung(bak, monkeypatch):
    _tour("a1")
    p = extras.make_backup(str(bak))
    _tour("b1")
    vor = _stand()
    with _client() as c:
        v = _check(c, _sid(p))
        with extras.BACKUP_LOCK:                                                     # dieser Thread „sichert gerade“; der Endpunkt läuft in einem anderen Thread
            r = c.post("/api/restore/run", json={"id": v["id"], "token": v["token"], "bestaetigt": True})
            assert r.status_code == 409 and "läuft gerade eine Sicherung" in r.json()["detail"]
            # umgekehrt: eine Sicherung wartet und gibt dann mit klarer Meldung auf
            monkeypatch.setattr(extras, "BACKUP_LOCK_WAIT_S", 0.2)
            err = []
            t = threading.Thread(target=lambda: err.append(pytest.raises(extras.BackupError, extras.make_backup, str(bak)).value))
            t.start(); t.join(20)
            assert err and "andere Sicherung oder ein Zurückspielen" in str(err[0])
        assert _stand() == vor and len(list(bak.glob("*.zip"))) == 1
        # das Token ist nach der Ablehnung noch gültig; ein laufender Hintergrundjob blockiert ebenfalls
        start, ende = threading.Event(), threading.Event()
        assert jobs.start("Testjob", lambda: (start.set(), ende.wait(20)))
        assert start.wait(10)
        try:
            r = c.post("/api/restore/run", json={"id": v["id"], "token": v["token"], "bestaetigt": True})
            assert r.status_code == 409 and "Hintergrundjob" in r.json()["detail"]
        finally:
            ende.set()
        for _ in range(200):
            if not jobs.get_state()["running"]:
                break
            time.sleep(0.02)
        assert _stand() == vor
        _run(c, v)
        assert extras.BACKUP_LOCK.acquire(blocking=False); extras.BACKUP_LOCK.release()          # Sperre wieder frei
        assert jobs.start("Danach", lambda: None)                                                # und Jobs laufen wieder
    assert {t["id"] for t in db.query("SELECT id FROM tours")} == {"a1"}


def test_waehrend_der_wiederherstellung_startet_kein_job(bak, monkeypatch):
    _tour("a1")
    p = extras.make_backup(str(bak))
    gesehen = []
    orig = wh.einspielen
    monkeypatch.setattr(wh, "einspielen", lambda q: (gesehen.append(jobs.start("Zwischendurch", lambda: None)), orig(q))[1])
    with _client() as c:
        _run(c, _check(c, _sid(p)))
    assert gesehen == [False]


# ------------------------------------------------------------------------------------------------ Fehler
def test_sicherheitskopie_scheitert_dann_abbruch_ohne_aenderung(bak, monkeypatch):
    _tour("a1")
    p = extras.make_backup(str(bak))
    _tour("b1")
    vor = _stand()
    echt = extras.make_backup

    def voll(*a, **k):
        raise extras.BackupError("Zu wenig freier Speicher im Sicherungsordner: 1 MB frei, mindestens 60 MB nötig")
    monkeypatch.setattr(extras, "make_backup", voll)
    with _client() as c:
        r = _run(c, _check(c, _sid(p)), 500)
        assert "Sicherheitskopie" in r["detail"] and "nichts verändert" in r["detail"] and "Zu wenig freier Speicher" in r["detail"]
        assert _stand() == vor and _kein_temp() and len(list(bak.glob("*.zip"))) == 1
        monkeypatch.setattr(extras, "make_backup", echt)
        _run(c, _check(c, _sid(p)))                                                   # danach geht es wieder


def test_fehler_nach_dem_tausch_automatischer_rueckfall_auf_die_sicherheitskopie(bak, monkeypatch):
    _tour("a1")
    p = extras.make_backup(str(bak))
    _tour("b1"); _tour("b2"); _plan("heute"); db.put("home_name", "Zuhause")
    vor = _stand()
    monkeypatch.setattr(wh, "nachpruefung", lambda erwartet: "*** in database main ***: Seite 7 ist beschädigt")
    with _client() as c:
        r = _run(c, _check(c, _sid(p)), 500)
        assert "fehlgeschlagen" in r["detail"] and "automatisch zurückgeholt" in r["detail"] and "Seite 7" in r["detail"]
        assert _stand() == vor                                                       # exakt der Stand von vorher, auch die Einstellungen
        assert {t["id"] for t in c.get("/api/tours").json()} == {"a1", "b1", "b2"}
    assert len(list(bak.glob("*vor-wiederherstellung*.zip"))) == 1 and p.is_file() and _kein_temp()
    assert db.one("PRAGMA journal_mode")["journal_mode"] == "wal" and db.one("PRAGMA quick_check")["quick_check"] == "ok"
    assert any("Rückfall" in line and "gelungen" in line for line in jobs.snapshot()["log"])


def test_tausch_bricht_ab_dann_bleibt_der_alte_stand(bak, monkeypatch):
    _tour("a1")
    p = extras.make_backup(str(bak))
    _tour("b1")
    vor = _stand()
    orig, n = wh.einspielen, []

    def einmal_kaputt(q):
        n.append(1)
        if len(n) == 1:
            raise sqlite3.OperationalError("disk I/O error")
        return orig(q)
    monkeypatch.setattr(wh, "einspielen", einmal_kaputt)
    with _client() as c:
        r = _run(c, _check(c, _sid(p)), 500)
    assert "automatisch zurückgeholt" in r["detail"] and "disk I/O error" in r["detail"] and len(n) == 2
    assert _stand() == vor and _kein_temp()


def test_rueckfall_scheitert_auch_dann_nennt_die_meldung_die_sicherheitskopie(bak, monkeypatch, tmp_path):
    _tour("a1")
    p = extras.make_backup(str(bak))
    _tour("b1")
    monkeypatch.setattr(wh, "nachpruefung", lambda erwartet: "kaputt")
    monkeypatch.setattr(wh, "_zurueck", lambda kopie, work: False)
    with _client() as c:
        r = _run(c, _check(c, _sid(p)), 500)
    k = list(bak.glob("*vor-wiederherstellung*.zip"))
    assert len(k) == 1 and k[0].name in r["detail"] and "nicht automatisch zurückgeholt" in r["detail"] and "Skript" in r["detail"] and _kein_temp()
    assert _touren_im_zip(k[0], tmp_path) == {"a1", "b1"}                             # die Kopie enthält den Stand von vorher


def test_einspielen_laesst_bei_defekter_quelle_die_live_datenbank_unveraendert(bak, tmp_path):
    _tour("a1"); _tour("a2")
    vor = _stand()
    f = tmp_path / "muell.sqlite"; f.write_bytes(b"SQLite format 3\x00" + os.urandom(8000))
    with pytest.raises(sqlite3.Error):
        wh.einspielen(f)
    assert _stand() == vor and db.one("PRAGMA quick_check")["quick_check"] == "ok"
    _tour("a3")


def test_gleichzeitige_zugriffe_waehrend_des_tauschs_sehen_alt_oder_neu_nie_einen_fehler(bak):
    for i in range(300):
        _tour(f"a{i}")
    p = extras.make_backup(str(bak))
    db.execute("DELETE FROM tours WHERE id>'a2'")
    n_neu = db.one("SELECT COUNT(*) n FROM tours")["n"]
    stop, fehler, gesehen = threading.Event(), [], set()

    def leser():
        while not stop.is_set():
            try:
                gesehen.add(db.one("SELECT COUNT(*) n FROM tours")["n"])
                db.put("zaehler", "1")                                               # auch Schreiber
            except Exception as e:  # noqa
                fehler.append(repr(e))
    ts = [threading.Thread(target=leser) for _ in range(4)]
    [t.start() for t in ts]
    try:
        with _client() as c:
            for _ in range(3):
                _run(c, _check(c, _sid(p)))
                db.execute("DELETE FROM tours WHERE id>'a2'")
    finally:
        stop.set(); [t.join(20) for t in ts]
    assert not fehler, fehler[:3]
    assert gesehen <= {300, n_neu} and 300 in gesehen
    assert db.one("PRAGMA quick_check")["quick_check"] == "ok"


# ------------------------------------------------------------------------------------------------ Upload und Aufräumen
def test_upload_landet_nur_im_temporaeren_bereich_und_wird_aufgeraeumt(bak):
    _tour("a1")
    p = extras.make_backup(str(bak))
    _tour("b1")
    data = p.read_bytes(); p.unlink()
    with _client() as c:
        up = _upload(c, data, "../../meine sicherung<1>.zip")
        assert up["groesse"] == len(data) and up["name"] == "meine sicherung_1_.zip" and up["id"].startswith("u:")
        area = config.DATA_DIR / "restore-tmp" / "_"
        assert sorted(f.suffix for f in area.iterdir()) == [".name", ".zip"] and not list(bak.glob("*"))
        assert oct((area / f"upload-{up['id'][2:]}.zip").stat().st_mode & 0o777) == "0o600" or os.name == "nt"
        up2 = _upload(c, data, "zweite.zip")                                         # ein neuer Upload ersetzt den alten
        assert len(list(area.glob("*.zip"))) == 1 and c.post("/api/restore/check", json={"id": up["id"]}).status_code == 404
        v = _check(c, up2["id"])
        assert v["name"] == "zweite.zip" and v["upload"] is True and abs(v["erstellt_ts"] - time.time()) < 120
        assert c.delete("/api/restore/upload").json() == {"ok": True} and _kein_temp()
        assert "abgelaufen" in _run(c, v, 409)["detail"]                              # verworfen: das Token gilt nicht mehr
        v = _check(c, _upload(c, data)["id"])
        r = _run(c, v)
        assert r["nachher"]["touren"] == 1 and _kein_temp()                          # nach Erfolg ist die hochgeladene Datei weg
    assert len(list(bak.glob("*vor-wiederherstellung*.zip"))) == 1


def test_reste_werden_beim_start_und_nach_einer_stunde_geloescht(bak):
    area = config.DATA_DIR / "restore-tmp" / "_"
    (area / "work-abc").mkdir(parents=True); (area / "work-abc" / "komoot_hub.sqlite").write_bytes(b"x")
    (area / "upload-0123456789abcdef.zip").write_bytes(b"x"); (area / "upload-ffff.zip.part").write_bytes(b"x")
    wh._tokens["alt"] = {"wer": "", "id": "u:x", "sha": "", "exp": time.time() - 5}
    wh.aufraeumen()
    assert len(list(area.iterdir())) == 3                                            # frisch: bleibt
    for f in area.iterdir():
        os.utime(f, (time.time() - 2 * 3600,) * 2)
    wh.aufraeumen()
    assert _kein_temp() and "alt" not in wh._tokens
    (area / "work-neu").mkdir(parents=True)
    with _client():                                                                  # Programmstart räumt alles weg
        assert _kein_temp()


def test_temporaerer_bereich_ist_nicht_im_umzugspaket(bak, tmp_path):
    _tour("a1")
    area = config.DATA_DIR / "restore-tmp" / "_"; area.mkdir(parents=True); (area / "upload-0123456789abcdef.zip").write_bytes(b"geheim")
    pkg = umzug.make(config.DATA_DIR, tmp_path / "umz", "test")
    with zipfile.ZipFile(pkg) as z:
        assert not [n for n in z.namelist() if "restore-tmp" in n]


# ------------------------------------------------------------------------------------------------ Buchhaltung
def test_version_und_skript_bleiben():
    root = Path(__file__).resolve().parent.parent
    assert config.VERSION.startswith("3.71.1")
    assert "komoot_hub.sqlite.vor-restore" in (root / "deploy" / "restore.sh").read_text(encoding="utf-8")      # das Skript gibt es weiterhin
    html = (root / "app/static/index.html").read_text(encoding="utf-8")
    assert html.index("js/68-wiederherstellen.js") < html.index("js/69-start.js")
    js = (root / "app/static/js/68-wiederherstellen.js").read_text(encoding="utf-8")
    assert "confirm(" not in js.replace("uiConfirm(", "") and "eval(" not in js and 'style="' not in js
    i18n = (root / "app/static/js/00-i18n-neu.js").read_text(encoding="utf-8")
    src = (root / "app/wiederherstellung.py").read_text(encoding="utf-8")
    import re
    for m in re.finditer(r'(?:Abgelehnt|HTTPException)\(\s*(?:\d+,\s*)?f?"([^"]{12,})"', src):       # jede Meldung des Servers hat eine Zeile in der Übersetzungstabelle
        anfang = re.split(r"\{[^}]*\}", m.group(1))[0].strip()
        assert anfang[:60] in i18n, anfang
