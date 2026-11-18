"""3.38.0 „Sicher planen“ (Server): robuste Sicherung, Prüfung der letzten Sicherung, Machbarkeits-Check, Plan <-> gelaufene Tour.
Alles mit tmp-Pfaden und simulierten Fehlern (voller Datenträger, defekte ZIP) – keine echten Daten."""
import io
import json
import sqlite3
import sys
import time
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401
from app import backup_check, config, db, extras, plan, plan_check, updater  # noqa: E402


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _tour(tid, km=10.0, up=300, down=300, sport="hike", tage=10, dur_h=3.0, name=None):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
               (tid, name or f"Tour {tid}", sport, int(time.time() - tage * 86400), int(time.time() - tage * 86400 + 100), km * 1000 if km is not None else None,
                dur_h * 3600, up, down, 48.0, 8.0, "tour_recorded"))


# ------------------------------------------------------------------------------------------------ 1. robuste Sicherung
def test_sicherung_ok_ohne_part_und_geprueft(tmp_path):
    _tour("a1")
    p = extras.make_backup(str(tmp_path / "b"))
    assert p.exists() and p.suffix == ".zip" and not list((tmp_path / "b").glob("*.part"))
    r = backup_check.pruefe_zip(p)
    assert r["ok"] and r["touren"] == 1 and r["db_pruefung"] == "ok" and r["layouts"] is not None


def test_zu_wenig_platz_gibt_klare_meldung_und_keine_datei(tmp_path, monkeypatch):
    d = tmp_path / "b"; d.mkdir()
    alt = d / "meine-touren-2020-01-01_0300.zip"; alt.write_bytes(b"alt")
    monkeypatch.setattr(extras.shutil, "disk_usage", lambda p: type("U", (), {"free": 1000, "total": 10, "used": 9})())
    with pytest.raises(extras.BackupError) as e:
        extras.make_backup(str(d), keep=1)
    assert "Zu wenig freier Speicher" in str(e.value) and "MB" in str(e.value)
    assert sorted(f.name for f in d.iterdir()) == [alt.name]                     # nichts Neues, nichts Halbes, die alte bleibt


def test_schreibfehler_mitten_im_zip_loescht_part_und_laesst_alte_sicherungen(tmp_path, monkeypatch):
    d = tmp_path / "b"; d.mkdir()
    alte = []
    for i in range(3):
        f = d / f"meine-touren-2020-01-0{i + 1}_0300.zip"; f.write_bytes(b"alt"); alte.append(f.name)

    def kaputt(fh, td, strip):
        fh.write(b"PK\x03\x04halb")
        raise OSError(28, "No space left on device")
    monkeypatch.setattr(extras, "_write_zip", kaputt)
    with pytest.raises(extras.BackupError) as e:
        extras.make_backup(str(d), keep=1)                                          # keep=1 würde bei Erfolg zwei alte löschen
    assert "No space left" in str(e.value)
    assert sorted(f.name for f in d.iterdir()) == alte


def test_defekte_neue_zip_wird_nicht_uebernommen(tmp_path, monkeypatch):
    d = tmp_path / "b"; d.mkdir()
    monkeypatch.setattr(extras, "_write_zip", lambda fh, td, strip: fh.write(b"das ist kein zip"))
    with pytest.raises(extras.BackupError) as e:
        extras.make_backup(str(d))
    assert "Prüfung" in str(e.value)
    assert list(d.iterdir()) == []
    assert extras.newest_backup() is None or extras.newest_backup().parent != d


def test_alte_part_reste_werden_aufgeraeumt(tmp_path):
    d = tmp_path / "b"; d.mkdir()
    stale = d / "meine-touren-2020-01-01_0300.zip.part"; stale.write_bytes(b"x")
    import os
    os.utime(stale, (time.time() - 3600, time.time() - 3600))
    extras.make_backup(str(d))
    assert not stale.exists()


def test_part_datei_zaehlt_nicht_als_neueste_sicherung(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "backup_dirs", lambda uid=None: [tmp_path])
    (tmp_path / "meine-touren-2030-01-01_0300.zip.part").write_bytes(b"halb")
    assert extras.newest_backup() is None


def test_auto_backup_merkt_fehler_und_loescht_ihn_bei_erfolg(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "backup_dirs", lambda uid=None: [tmp_path / "x", tmp_path / "y"])
    monkeypatch.setattr(extras.shutil, "disk_usage", lambda p: type("U", (), {"free": 5, "total": 10, "used": 9})())
    assert extras.auto_backup(max_age_s=0) is None
    assert "Zu wenig freier Speicher" in db.get("backup_err") and int(db.get("backup_err_ts")) > 0
    monkeypatch.undo()
    monkeypatch.setattr(config, "backup_dirs", lambda uid=None: [tmp_path / "x"])
    assert extras.auto_backup(max_age_s=0) is not None
    assert db.get("backup_err") == "" and db.get("backup_err_ts") == ""


def test_fehlgeschlagene_neue_sicherung_verdraengt_keine_gute_durch_aufbewahrung(tmp_path, monkeypatch):
    d = tmp_path / "x"; d.mkdir()
    for i in range(14):
        (d / f"meine-touren-2020-01-{i + 1:02d}_0300.zip").write_bytes(b"alt")
    monkeypatch.setattr(config, "backup_dirs", lambda uid=None: [d])
    monkeypatch.setattr(extras, "_write_zip", lambda fh, td, strip: fh.write(b"kaputt"))
    assert extras.auto_backup(max_age_s=0) is None
    assert len(list(d.glob("*.zip"))) == 14


def test_update_meldet_fehlgeschlagene_sicherung(monkeypatch):
    monkeypatch.setattr(extras, "auto_backup", lambda max_age_s=0: None)
    db.put("backup_err", "Platte voll")
    assert updater.backup_all() == 0
    assert any("Platte voll" in f for f in updater.backup_failures())
    monkeypatch.setattr(extras, "auto_backup", lambda max_age_s=0: (_ for _ in ()).throw(RuntimeError("kaputt")))
    updater.backup_all()
    assert any("kaputt" in f for f in updater.backup_failures())


def test_warnschwelle_ist_eine_konstante():
    assert config.BACKUP_WARN_S == 36 * 3600 and backup_check.WARN_S == config.BACKUP_WARN_S


# ------------------------------------------------------------------------------------------------ 2. Prüfung der Sicherung
def _zip(path, files):
    with zipfile.ZipFile(path, "w") as z:
        for n, b in files.items():
            z.writestr(n, b)
    return path


def test_pruefe_zip_faelle(tmp_path):
    assert not backup_check.pruefe_zip(tmp_path / "gibtsnicht.zip")["ok"]
    leer = tmp_path / "leer.zip"; leer.write_bytes(b"")
    assert "leer" in backup_check.pruefe_zip(leer)["fehler"]
    kein = tmp_path / "kein.zip"; kein.write_bytes(b"kein zip" * 20)
    assert "kein lesbares ZIP" in backup_check.pruefe_zip(kein)["fehler"]
    ohne = _zip(tmp_path / "ohne.zip", {"INFO.txt": "x"})
    assert "fehlt" in backup_check.pruefe_zip(ohne)["fehler"]
    bad = _zip(tmp_path / "bad.zip", {"komoot_hub.sqlite": b"SQLite-Unsinn" * 100})
    assert not backup_check.pruefe_zip(bad)["ok"]
    abgeschnitten = tmp_path / "abg.zip"
    p = extras.make_backup(str(tmp_path / "b"))
    abgeschnitten.write_bytes(p.read_bytes()[:-200])
    assert not backup_check.pruefe_zip(abgeschnitten)["ok"]


def test_pruefe_zip_zaehlt_touren_tracks_layouts(tmp_path):
    _tour("a1"); _tour("a2")
    p = extras.make_backup(str(tmp_path / "b"))
    with zipfile.ZipFile(p, "a") as z:
        z.writestr("tracks/x.gpx", "<gpx/>")
    r = backup_check.pruefe_zip(p)
    assert r["ok"] and r["touren"] == 2 and r["tracks"] == 1


def _users(c):
    c.post("/api/setup", json={"name": "chef", "email": "chef@example.com", "password": "geheim123"})
    c.post("/api/login", json={"name": "chef", "password": "geheim123"})
    c.post("/api/users", json={"name": "gast", "email": "gast@example.com", "password": "geheim456", "role": "user"})
    c.post("/api/users", json={"name": "oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})


def _login(c, n, p):
    c.post("/api/logout")
    assert c.post("/api/login", json={"name": n, "password": p}).status_code == 200


def test_pruef_endpunkt_fehlende_leere_defekte_und_gute_sicherung(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "backup_dirs", lambda uid=None: [tmp_path / "b"])
    with _client() as c:
        r = c.post("/api/backup/check").json()
        assert r["ok"] is False and "noch keine Sicherung" in r["fehler"]
        assert c.get("/api/backup/status").json()["geprueft"]["ok"] is False
        (tmp_path / "b").mkdir()
        _tour("a1")
        gut = extras.make_backup(str(tmp_path / "b"))
        r = c.post("/api/backup/check").json()
        assert r["ok"] and r["touren"] == 1 and r["name"] == gut.name and r["alter_h"] < 1 and r["ts"] > 0
        st = c.get("/api/backup/status").json()
        assert st["geprueft"]["ok"] and st["neueste"]["name"] == gut.name and not st["ueberfaellig"]
        leer = tmp_path / "b" / "meine-touren-2099-01-01_0000.zip"; leer.write_bytes(b"")
        r = c.post("/api/backup/check").json()
        assert r["ok"] is False and "leer" in r["fehler"] and r["name"] == leer.name
        leer.write_bytes(gut.read_bytes()[:300])
        assert c.post("/api/backup/check").json()["ok"] is False
    assert gut.exists()                                                                # die Prüfung ändert nichts an den Sicherungen


def test_pruef_endpunkt_aendert_live_daten_nicht_und_hinterlaesst_kein_temp(tmp_path, monkeypatch):
    import tempfile
    monkeypatch.setattr(config, "backup_dirs", lambda uid=None: [tmp_path / "b"])
    _tour("a1")
    extras.make_backup(str(tmp_path / "b"))
    tmp = tmp_path / "tmp"; tmp.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(tmp))
    vor = [dict(r) for r in db.query("SELECT * FROM tours")]
    with _client() as c:
        assert c.post("/api/backup/check").json()["ok"]
    assert [dict(r) for r in db.query("SELECT * FROM tours")] == vor
    assert list(tmp.iterdir()) == []


def test_pruef_endpunkt_nur_admin(tmp_path):
    with _client() as c:
        _users(c)
        for n, p in (("gast", "geheim456"), ("oma", "omas-pass12")):
            _login(c, n, p)
            assert c.post("/api/backup/check").status_code == 403
            assert c.get("/api/backup/status").status_code == 403
        _login(c, "chef", "geheim123")
        assert c.post("/api/backup/check").status_code == 200


def test_status_ueberfaellig_nach_36_stunden(tmp_path, monkeypatch):
    import os
    monkeypatch.setattr(config, "backup_dirs", lambda uid=None: [tmp_path])
    _tour("a1")
    p = extras.make_backup(str(tmp_path))
    assert not backup_check.status()["ueberfaellig"]
    os.utime(p, (time.time() - 37 * 3600,) * 2)
    assert backup_check.status()["ueberfaellig"]


# ------------------------------------------------------------------------------------------------ 3. Machbarkeits-Check
def _hist(n=8, **kw):
    for i in range(n):
        _tour(f"h{i}", km=10 + i, up=300 + 100 * i, down=300 + 100 * i, tage=10 + i, **kw)       # längste: 17 km mit 1.000 m


def test_check_zu_wenig_touren_keine_scheinzahlen():
    _hist(5)
    r = plan_check.check({"km": 12, "up": 400, "down": 400, "sport": "hike"})
    assert r["stufe"] == "zu_wenig" and r["n"] == 5 and r["laengste"] is None and r["laenger"] is None and r["gruende"] == []


def test_check_leere_datenbank():
    r = plan_check.check({"km": 12, "up": 400, "down": 400, "sport": "hike"})
    assert r["stufe"] == "zu_wenig" and r["n"] == 0


def test_check_drei_stufen_mit_konkreten_zahlen():
    _hist()
    g = plan_check.check({"km": 15, "up": 800, "down": 800, "sport": "hike"})
    assert g["stufe"] == "gewohnt" and g["gruende"] == [] and g["laengste"]["km"] == 17.0 and g["laengste"]["up"] == 1000 and g["laenger"] == 2
    e = plan_check.check({"km": 19, "up": 800, "down": 800, "sport": "hike"})            # 19/17 = 1,12
    assert e["stufe"] == "etwas_mehr" and e["gruende"] == ["km"]
    e2 = plan_check.check({"km": 15, "up": 1250, "down": 1250, "sport": "hike"})        # 1,25 × der höchste Aufstieg
    assert e2["stufe"] == "etwas_mehr" and e2["gruende"] == ["up"] and e2["hoechster_aufstieg"]["up"] == 1000
    d = plan_check.check({"km": 25, "up": 800, "down": 800, "sport": "hike"})
    assert d["stufe"] == "deutlich_mehr"
    d2 = plan_check.check({"km": 17, "up": 1500, "down": 1500, "sport": "hike"})
    assert d2["stufe"] == "deutlich_mehr" and d2["gruende"] == ["up"]
    both = plan_check.check({"km": 19, "up": 1500, "down": 1500, "sport": "hike"})
    assert both["stufe"] == "deutlich_mehr" and both["gruende"] == ["km", "up"]
    gleich = plan_check.check({"km": 17, "up": 1000, "down": 1000, "sport": "hike"})   # genau der bisherige Höchstwert
    assert gleich["stufe"] == "gewohnt"


def test_check_ohne_angabe_zaehlt_nie_als_null():
    for i in range(7):
        _tour(f"n{i}", km=10 + i, up=None, down=None, tage=5 + i)
    r = plan_check.check({"km": 12, "up": 5000, "down": 5000, "sport": "hike"})
    assert r["stufe"] == "gewohnt" and r["hoechster_aufstieg"] is None and r["gruende"] == []     # kein Vergleich der Höhenmeter mit „0“
    r2 = plan_check.check({"km": 12, "sport": "hike"})                                        # Plan ohne Höhen
    assert r2["diese"]["up"] is None and r2["gehzeit"] is None and r2["stufe"] == "gewohnt"
    assert r2["aehnlich"]["up"] is None and r2["aehnlich"]["n"] >= 1


def test_check_nur_letzte_12_monate_und_gleiche_sportgruppe():
    for i in range(6):
        _tour(f"alt{i}", km=50, tage=400 + i)                              # zu alt
        _tour(f"rad{i}", km=80, sport="racebike", tage=5 + i)               # andere Sportgruppe
    assert plan_check.check({"km": 30, "up": 100, "down": 100, "sport": "hike"})["n"] == 0
    r = plan_check.check({"km": 70, "up": 100, "down": 100, "sport": "mtb"})
    assert r["n"] == 6 and r["laengste"]["km"] == 80.0
    _hist(6)
    assert plan_check.check({"km": 12, "up": 100, "down": 100, "sport": "nordicwalking"})["n"] == 6      # Wandern = eine Gruppe


def test_check_aehnliche_touren_und_gehzeit():
    _hist()
    r = plan_check.check({"km": 13, "up": 600, "down": 600, "sport": "hike"})
    assert r["aehnlich"]["n"] >= 3 and r["aehnlich"]["dauer_h"] == 3.0
    assert r["gehzeit"] and r["gehzeit"]["sekunden"] > 0 and r["gehzeit"]["quelle"] in ("standard", "teilweise", "eigene")
    assert plan_check.check({"km": 40, "up": 100, "down": 100, "sport": "mtb"})["gehzeit"] is None          # Gehzeit nur Wandern/Laufen


def test_check_endpunkt_validierung_und_ausschaltbar():
    with _client() as c:
        ok = c.post("/api/plan/check", json={"km": 12, "up": 400, "down": 400, "sport": "hike"})
        assert ok.status_code == 200 and ok.json()["stufe"] == "zu_wenig"
        for bad in ({}, {"km": 0}, {"km": -3}, {"km": "x"}, {"km": 5000}, {"km": 10, "up": -1}, {"km": 10, "up": "viel"}, {"km": float("nan")} if False else {"km": True},
                    {"km": 10, "max_alt": 99999}):
            assert c.post("/api/plan/check", json=bad).status_code == 400, bad
        db.put("plan_enabled", "0")
        assert c.post("/api/plan/check", json={"km": 12}).status_code == 403


def test_check_endpunkt_nur_angemeldete(tmp_path):
    with _client() as c:
        _users(c)
        c.post("/api/logout")
        assert c.post("/api/plan/check", json={"km": 12}).status_code in (401, 403)
        _login(c, "oma", "omas-pass12")
        assert c.post("/api/plan/check", json={"km": 12}).status_code == 403          # Betrachter darf nichts schreiben/rechnen lassen
        _login(c, "gast", "geheim456")
        assert c.post("/api/plan/check", json={"km": 12}).status_code == 200


# ------------------------------------------------------------------------------------------------ 4. Migration
def test_migration_alter_plans_tabelle(tmp_path):
    f = tmp_path / "alt.sqlite"
    con = sqlite3.connect(str(f))
    con.execute("CREATE TABLE plans (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, sport TEXT, pts TEXT, km REAL, up REAL, down REAL, max_alt REAL, est_h REAL, note TEXT, ts INTEGER)")
    con.execute("INSERT INTO plans(name,sport,pts,km,ts) VALUES('Alte Runde','hike','[[48,8],[48.1,8.1]]',5,1)")
    con.commit(); con.close()
    c = db.init(f)
    cols = {r["name"] for r in c.execute("PRAGMA table_info(plans)")}
    assert {"wps", "tour_id", "status"} <= cols
    r = c.execute("SELECT name,tour_id,status FROM plans").fetchone()
    assert (r["name"], r["tour_id"], r["status"]) == ("Alte Runde", None, "geplant")
    db.init(f)                                                                          # zweiter Start: nichts passiert (idempotent)
    assert c.execute("SELECT COUNT(*) n FROM plans").fetchone()["n"] == 1


# ------------------------------------------------------------------------------------------------ 5. Verknüpfung
PTS = [[48.0 + 0.001 * i, 8.0 + 0.0005 * i] for i in range(60)]          # ca. 6,7 km Nordost


def _plan(c, name="Runde", pts=None, km=6.7, sport="hike", est=2.0):
    return c.post("/api/plans", json={"name": name, "sport": sport, "pts": pts or PTS, "km": km, "up": 200, "down": 200, "est_h": est}).json()["id"]


def _lauf(tid, pts, km=6.7, up=190, dur_h=1.9, sport="hike", tage=1):
    from app import routes
    _tour(tid, km=km, up=up, down=up, sport=sport, tage=tage, dur_h=dur_h)
    routes.store(tid, [(a, b, 500.0, i * 1000) for i, (a, b) in enumerate(pts)])


def test_verknuepfen_loesen_und_status():
    with _client() as c:
        pid = _plan(c)
        _tour("t1", km=6.9, dur_h=1.7)
        row = c.get("/api/plans").json()[0]
        assert row["status"] == "geplant" and row["tour_id"] is None and row["tour"] is None
        r = c.post(f"/api/plans/{pid}/tour", json={"tour_id": "t1"}).json()
        assert r == {"ok": True, "tour_id": "t1", "status": "gegangen"}
        row = c.get("/api/plans").json()[0]
        assert row["tour"]["km"] == 6.9 and row["tour"]["h"] == 1.7 and row["status"] == "gegangen"
        assert c.get(f"/api/plans/{pid}").json()["tour_id"] == "t1"
        c.post("/api/plans", json={"id": pid, "name": "Neu benannt", "pts": PTS})                  # Speichern ändert die Verknüpfung nicht
        assert c.get("/api/plans").json()[0]["tour_id"] == "t1"
        r = c.post(f"/api/plans/{pid}/tour", json={"tour_id": None}).json()
        assert r["tour_id"] is None and r["status"] == "geplant"
        c.post(f"/api/plans/{pid}/tour", json={"tour_id": "t1"})
        assert c.post(f"/api/plans/{pid}/status", json={"status": "verworfen"}).json()["status"] == "verworfen"
        row = c.get("/api/plans").json()[0]
        assert row["tour_id"] is None and row["status"] == "verworfen"
        assert c.post(f"/api/plans/{pid}/status", json={"status": "gegangen"}).status_code == 200


def test_verknuepfung_validierung():
    with _client() as c:
        pid = _plan(c)
        assert c.post(f"/api/plans/{pid}/tour", json={"tour_id": "gibtsnicht"}).status_code == 404
        assert c.post("/api/plans/9999/tour", json={"tour_id": "x"}).status_code == 404
        assert c.post("/api/plans/9999/status", json={"status": "geplant"}).status_code == 404
        assert c.post(f"/api/plans/{pid}/status", json={"status": "fertig"}).status_code == 400
        assert c.post(f"/api/plans/{pid}/status", json={}).status_code == 400
        assert c.post(f"/api/plans/{pid}/tour", json={"tour_id": ["a"]}).status_code == 400
        assert c.post(f"/api/plans/{pid}/tour", json={"tour_id": "x" * 100}).status_code == 400
        assert c.post(f"/api/plans/{pid}/tour", json={"tour_id": True}).status_code == 400
        assert c.get("/api/plans").json()[0]["status"] == "geplant"


def test_geloeschte_tour_loest_verknuepfung_in_der_liste():
    with _client() as c:
        pid = _plan(c)
        _tour("t1")
        c.post(f"/api/plans/{pid}/tour", json={"tour_id": "t1"})
        db.execute("DELETE FROM tours WHERE id='t1'")
        row = c.get("/api/plans").json()[0]
        assert row["tour_id"] is None and row["tour"] is None


def test_verknuepfung_rechte():
    with _client() as c:
        _users(c)
        _login(c, "gast", "geheim456")
        pid = _plan(c)
        assert c.post(f"/api/plans/{pid}/status", json={"status": "gegangen"}).status_code == 200
        assert c.post(f"/api/plans/{pid}/tour", json={"tour_id": "gibtsnicht"}).status_code == 404
        _login(c, "oma", "omas-pass12")
        assert c.post(f"/api/plans/{pid}/tour", json={"tour_id": None}).status_code == 403
        assert c.post(f"/api/plans/{pid}/status", json={"status": "verworfen"}).status_code == 403
        assert c.get("/api/plans/vorschlaege").status_code == 403


def test_vorschlag_bei_80_prozent_ueberdeckung_nie_automatisch():
    with _client() as c:
        pid = _plan(c)
        _lauf("gut", PTS)                                                       # deckt alles
        v = c.get("/api/plans/vorschlaege").json()
        assert v[str(pid)]["tour_id"] == "gut" and v[str(pid)]["ueberdeckung"] >= 0.8 and v[str(pid)]["datum"]
        assert c.get("/api/plans").json()[0]["tour_id"] is None               # nicht automatisch verknüpft
        c.post(f"/api/plans/{pid}/tour", json={"tour_id": "gut"})
        assert c.get("/api/plans/vorschlaege").json() == {}                    # verknüpft: kein Vorschlag mehr


def test_kein_vorschlag_bei_zu_wenig_ueberdeckung_falscher_laenge_oder_sportart():
    with _client() as c:
        pid = _plan(c)
        halb = PTS[:40] + [[a + 0.05, b + 0.05] for a, b in PTS[40:]]           # nur ca. zwei Drittel
        _lauf("halb", halb)
        _lauf("lang", PTS, km=12.0)                                            # Länge außerhalb ±25 %
        _lauf("rad", PTS, sport="racebike")                                    # andere Sportgruppe
        _lauf("woanders", [[a + 1, b] for a, b in PTS])
        assert c.get("/api/plans/vorschlaege").json() == {}
        _plan(c, name="ohne Länge", km=None)
        assert c.get("/api/plans/vorschlaege").json() == {}


def test_vorschlag_nur_fuer_offene_plaene_und_eine_tour_nicht_doppelt():
    with _client() as c:
        a, b, v = _plan(c, name="A"), _plan(c, name="B"), _plan(c, name="V")
        c.post(f"/api/plans/{v}/status", json={"status": "verworfen"})
        _lauf("gut", PTS)
        r = c.get("/api/plans/vorschlaege").json()
        assert set(r) == {str(a), str(b)}
        c.post(f"/api/plans/{a}/tour", json={"tour_id": "gut"})
        assert c.get("/api/plans/vorschlaege").json() == {}                    # die Tour gehört schon zu Plan A
