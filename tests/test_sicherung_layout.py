"""3.24.0 – Sicherung und Umzug enthalten die Layout-Daten (user_layout: Ansichten, Filter, Hinweis-Pausen) und die Qualitätsdaten
(quality_ack, quality_batch, elev_fix, track_fix); Wiederherstellung in einen leeren Benutzer bringt alles unverändert zurück; alte Sicherungen ohne diese Tabellen bleiben importierbar."""
import io
import shutil
import sqlite3
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _reset():
    """Leerer Benutzer: Datenordner löschen und Datenbank neu anlegen (wie die Test-Vorrichtung „fresh“, die sich nicht mitten im Test aufrufen lässt)."""
    from app import auth, config, db, jobs
    import time
    for _ in range(100):
        if not any(v["state"]["running"] for v in list(jobs._S.values())):
            break
        time.sleep(0.05)
    db.close_all(); auth.reset()
    shutil.rmtree(config.DATA_DIR, ignore_errors=True)
    db.close_all(); db.init()

import time
SNOOZE = f"pause:{int(time.time()) + 5 * 86400}"
TABLES = ("user_layout", "quality_ack", "quality_batch", "elev_fix", "track_fix")
BOX = {"v": 2, "active": "v1", "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1}},
                                          {"id": "v1", "name": "Wandern", "layout": {"v": 1, "hidden": ["hlast"], "widgets": [{"id": "hn1", "type": "hnpause", "cfg": {"tage": 21, "snoozes": [SNOOZE]}}], "filter": {"sports": [], "range": "all"}}}]}


def _seed():
    from app import db
    db.execute("INSERT OR REPLACE INTO quality_ack(tour_id,kinds,ts) VALUES('t1','height,gps',1700000100)")
    db.execute("INSERT OR REPLACE INTO elev_fix(id,orig_up,orig_down,up_m,down_m,ts) VALUES('t1',500,480,320,310,1700000200)")
    db.execute("INSERT OR REPLACE INTO track_fix(id,orig_dist,orig_dur,dist,dur,removed,excluded,ts) VALUES('t1',9000,4000,5000,3600,12,3,1700000300)")
    db.execute("INSERT OR REPLACE INTO quality_batch(batch_id,tour_id,device_id,method,ts,orig_up,orig_down,new_up,new_down,state) VALUES('b1','t1',1,'dem',1700000400,500,480,320,310,'done')")


def _dump(path):
    c = sqlite3.connect(str(path))
    try:
        return {t: sorted(c.execute(f"SELECT * FROM {t}").fetchall()) for t in TABLES}
    finally:
        c.close()


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _backup_sqlite(tmp_path, strip=False):
    from app import extras
    name, data = extras.make_backup(strip_secrets=strip)
    z = zipfile.ZipFile(io.BytesIO(data))
    assert "komoot_hub.sqlite" in z.namelist()
    out = tmp_path / ("b_strip.sqlite" if strip else "b.sqlite")
    out.write_bytes(z.read("komoot_hub.sqlite"))
    return out


def test_sicherung_enthaelt_layout_und_qualitaet_und_stellt_sie_wieder_her(tmp_path):
    from app import config, db
    _reset()
    with _client() as c:
        assert c.put("/api/layout/uebersicht", json=BOX).status_code == 200
        _seed()
        want = _dump(config.DB_PATH)
        assert want["user_layout"] and all(want[t] for t in TABLES)
        saved = _backup_sqlite(tmp_path)
        assert _dump(saved) == want                                                     # die Sicherung hat alle Tabellen mit Inhalt
        assert _dump(_backup_sqlite(tmp_path, strip=True)) == want                      # auch die Fassung ohne Geheimnisse (Download)
    _reset()                                                                             # leerer Benutzer
    assert all(not v for v in _dump(config.DB_PATH).values())
    db.close_all()
    shutil.copy(saved, config.DB_PATH)                                                  # so arbeitet deploy/restore.sh
    for sfx in ("-wal", "-shm"):
        Path(str(config.DB_PATH) + sfx).unlink(missing_ok=True)
    db.init()
    with _client() as c:
        g = c.get("/api/layout/uebersicht").json()
        assert g["container"]["active"] == "v1" and [v["name"] for v in g["container"]["views"]] == ["Standard", "Wandern"]
        assert g["container"]["views"][1]["layout"]["widgets"][0]["cfg"]["snoozes"] == [SNOOZE]      # Hinweis-Pause kommt mit zurück
    assert _dump(config.DB_PATH) == want


def test_alte_sicherung_ohne_neue_tabellen_bleibt_importierbar(tmp_path):
    from app import config, db
    _reset()
    with _client() as c:
        assert c.get("/api/layout/uebersicht").status_code == 200
    old = _backup_sqlite(tmp_path)
    con = sqlite3.connect(str(old))
    for t in ("user_layout", "quality_ack", "quality_batch"):                           # Stand vor 3.16.1 / 3.17.0
        con.execute(f"DROP TABLE {t}")
    con.commit(); con.close()
    _reset(); db.close_all()
    shutil.copy(old, config.DB_PATH)
    db.init()
    with _client() as c:
        g = c.get("/api/layout/uebersicht").json()
        assert g["layout"] is None and g["container"] is None                           # leer, aber kein Fehler
        assert c.put("/api/layout/uebersicht", json=BOX).status_code == 200
    assert not _dump(config.DB_PATH)["quality_ack"] and _dump(config.DB_PATH)["user_layout"]


def test_umzugspaket_round_trip(tmp_path):
    from app import config, db, umzug
    _reset()
    with _client() as c:
        assert c.put("/api/layout/uebersicht", json=BOX).status_code == 200
        _seed()
        want = _dump(config.DB_PATH)
    pkg = umzug.make(config.DATA_DIR, tmp_path / "pk", "3.24.0")
    target = tmp_path / "neu"
    assert umzug.restore(pkg, target) > 0
    sq = [p for p in target.rglob("komoot_hub.sqlite")]
    assert sq and _dump(sq[0]) == want
