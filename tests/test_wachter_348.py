"""3.48.0 – Sicherungs-Wächter, Server: GET /api/backup/waechter (backup_check.waechter) nutzt die Hinweis-Regel „Sicherung“ und den Sicherungszustand; nur Administratoren."""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import config, db, extras  # noqa: E402


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _tour(tid="a"):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,?,?,'t','komoot')",
               (tid, tid, "hike", int(time.time()) - 86400, int(time.time()), 5000, 3600, 100, 100))


def _zip(d, age_days):
    d.mkdir(exist_ok=True)
    f = extras.make_backup(str(d))
    t = time.time() - age_days * 86400 - 600
    os.utime(f, (t, t))
    return f


def test_waechter_faelle(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "backup_dirs", lambda uid=None: [tmp_path / "b"])
    with _client() as c:
        assert c.get("/api/backup/waechter").json()["zeige"] is False                 # ohne Touren gibt es nichts zu sichern
        _tour()
        r = c.get("/api/backup/waechter").json()                                       # (c) noch nie eine Sicherung
        assert r["zeige"] and r["art"] == "keine" and r["alter_tage"] is None and r["ausblendbar"] is True
        _zip(tmp_path / "b", 2)
        assert c.get("/api/backup/waechter").json()["zeige"] is False                 # frisch genug
        _zip(tmp_path / "b", 9)
        for p in (tmp_path / "b").glob("*.zip"):                                       # nur die 9 Tage alte Datei übrig lassen
            if time.time() - p.stat().st_mtime < 5 * 86400:
                p.unlink()
        r = c.get("/api/backup/waechter").json()                                       # (a) älter als die Schwelle
        assert r["zeige"] and r["art"] == "alt" and r["alter_tage"] == 9 and r["schwelle"] == 7 and r["ausblendbar"] is True and r["datum"]
        assert c.get("/api/backup/waechter?tage=10").json()["zeige"] is False         # eigene Schwelle
        assert c.get("/api/backup/waechter?tage=0").json()["schwelle"] == 1           # begrenzt auf 1–365
        assert c.get("/api/backup/waechter?tage=x").status_code == 400


def test_waechter_fehlerfall_nicht_ausblendbar(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "backup_dirs", lambda uid=None: [tmp_path / "b"])
    _tour()
    f = _zip(tmp_path / "b", 0)
    gut = f.read_bytes()
    with _client() as c:
        assert c.get("/api/backup/waechter").json()["zeige"] is False
        db.put("backup_err", "Ordner nicht beschreibbar")                              # (b) Anlegen fehlgeschlagen
        r = c.get("/api/backup/waechter").json()
        assert r["zeige"] and r["art"] == "fehler" and r["grund"] == "angelegt" and r["ausblendbar"] is False
        db.put("backup_err", "")
        f.write_bytes(f.read_bytes()[:300])                                            # (b) nicht lesbar: die Prüfung merkt es
        assert c.post("/api/backup/check").json()["ok"] is False
        r = c.get("/api/backup/waechter").json()
        assert r["zeige"] and r["art"] == "fehler" and r["grund"] == "pruefung" and r["ausblendbar"] is False and r["alter_tage"] == 0
        (tmp_path / "b" / "meine-touren-2099-01-01_0000.zip").write_bytes(gut)          # neuere Datei: die alte Fehlprüfung betrifft eine andere Datei
        os.utime(tmp_path / "b" / "meine-touren-2099-01-01_0000.zip", (time.time() + 5, time.time() + 5))
        assert c.get("/api/backup/waechter").json()["zeige"] is False


def test_waechter_nur_admin(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "backup_dirs", lambda uid=None: [tmp_path / "b"])
    _tour()
    with _client() as c:
        c.post("/api/setup", json={"name": "chef", "email": "chef@example.com", "password": "geheim123"})
        c.post("/api/login", json={"name": "chef", "password": "geheim123"})
        c.post("/api/users", json={"name": "oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        assert c.get("/api/backup/waechter").status_code == 200
        c.post("/api/logout")
        c.post("/api/login", json={"name": "oma", "password": "omas-pass12"})
        assert c.get("/api/backup/waechter").status_code == 403
