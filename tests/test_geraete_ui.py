"""3.9.1 – Meine Geräte: Foto (Upload/Abruf/Löschen/Sicherheit/Sicherung/Umzug), „Aus Zepp ermitteln“ (gemockt), Zuordnung über die Zepp-Kennung, Migration.
Echte Zepp-Antworten gibt es hier nicht: die Verlaufseinträge sind nachgebaut (Felder wie im Code verwendet: trackid, type, dis, run_time, end_time, source)."""
import io
import sqlite3
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import config, db, extras, mydevices, umzug, zepp  # noqa: E402
from tests.test_messwerte import T0, _client, _tour  # noqa: E402


def _img(fmt="PNG", size=(1600, 900), mode="RGB"):
    from PIL import Image
    b = io.BytesIO()
    Image.new(mode, size, (200, 80, 40) if mode == "RGB" else (200, 80, 40, 128)).save(b, fmt)
    return b.getvalue()


def _put(c, did, data, name="x.png", ctype="image/png"):
    return c.post(f"/api/my-devices/{did}/photo", files={"file": (name, data, ctype)})


def _dev(c, **kw):
    return c.post("/api/devices", json=dict({"name": "Uhr", "kind": "zepp"}, **kw)).json()["id"]


# ---------------------------------------------------------------- Foto
def test_photo_upload_resize_get_delete():
    from PIL import Image
    c = _client()
    d = _dev(c)
    assert c.get(f"/api/my-devices/{d}/photo").status_code == 404
    r = _put(c, d, _img(size=(1600, 900)))
    assert r.status_code == 200 and r.json()["photo"] > 0
    g = c.get(f"/api/my-devices/{d}/photo")
    assert g.status_code == 200 and g.headers["content-type"] == "image/jpeg"
    im = Image.open(io.BytesIO(g.content))
    assert im.format == "JPEG" and max(im.size) == 512 and im.size == (512, 288)
    assert (config.DB_PATH.parent / "devices" / f"{d}.jpg").is_file()
    assert [x for x in c.get("/api/my-devices").json()["devices"] if x["id"] == d][0]["photo"] > 0
    assert _put(c, d, _img("PNG", (64, 64), "RGBA")).status_code == 200            # Transparenz, kleines Bild bleibt klein
    assert Image.open(io.BytesIO(c.get(f"/api/my-devices/{d}/photo").content)).size == (64, 64)
    assert c.delete(f"/api/my-devices/{d}/photo").json()["ok"]
    assert c.get(f"/api/my-devices/{d}/photo").status_code == 404
    assert [x for x in c.get("/api/my-devices").json()["devices"] if x["id"] == d][0]["photo"] == 0


def test_photo_rejects_non_images_unknown_device_and_big_files(monkeypatch):
    c = _client()
    d = _dev(c)
    assert _put(c, d, b"<?xml version='1.0'?><svg xmlns='http://www.w3.org/2000/svg'/>", "a.svg", "image/svg+xml").status_code == 400
    assert _put(c, d, b"MZ\x90\x00 nicht wirklich ein Bild", "a.png").status_code == 400
    assert _put(c, 999, _img()).status_code == 404
    assert c.delete("/api/my-devices/999/photo").status_code == 404
    monkeypatch.setattr(mydevices, "PHOTO_MAX_BYTES", 2000)
    assert _put(c, d, _img(size=(900, 900))).status_code == 413
    assert c.get(f"/api/my-devices/{d}/photo").status_code == 404                  # nichts gespeichert
    monkeypatch.setattr(mydevices, "PHOTO_MAX_BYTES", 8 * 1024 * 1024)
    monkeypatch.setattr(mydevices, "PHOTO_MAX_PIXELS", 100)
    assert _put(c, d, _img(size=(50, 50))).status_code == 400                       # Dekompressionsbombe / Riesenbild


def test_photo_path_safety():
    c = _client()
    d = _dev(c)
    _put(c, d, _img())
    for bad in ("../x", "..%2Fx", "1/../../x", "abc"):
        assert c.get(f"/api/my-devices/{bad}/photo").status_code in (404, 422)
    secret = config.DB_PATH.parent / "devices" / "geheim.txt"
    secret.write_text("x")
    assert c.get("/api/my-devices/geheim.txt/photo").status_code in (404, 422)
    assert mydevices.photo_path(d).parent == config.DB_PATH.parent / "devices"
    assert mydevices.photo_path("7").name == "7.jpg"
    with pytest.raises(ValueError):
        mydevices.photo_path("../x")


def test_photo_removed_with_device_and_in_backup_and_umzug(tmp_path):
    c = _client()
    a, b = _dev(c, name="A"), _dev(c, name="B")
    _put(c, a, _img()); _put(c, b, _img())
    z = zipfile.ZipFile(io.BytesIO(extras.make_backup()[1]))
    assert f"devices/{a}.jpg" in z.namelist() and f"devices/{b}.jpg" in z.namelist()
    assert not [n for n in zipfile.ZipFile(io.BytesIO(extras.make_backup(strip_secrets=True)[1])).namelist() if n.startswith("devices/")]   # Variante ohne Zugangsdaten: keine Fotos
    out = umzug.make(config.DATA_DIR, tmp_path / "out", "t")
    assert any(n.endswith(f"devices/{a}.jpg") for n in zipfile.ZipFile(out).namelist())
    n = umzug.restore(out, tmp_path / "neu")
    assert n > 0 and (tmp_path / "neu" / "devices" / f"{a}.jpg").read_bytes()[:3] == b"\xff\xd8\xff"
    assert c.delete(f"/api/devices/{a}").json()["ok"]                              # Foto wird mit dem Gerät entfernt
    assert not (config.DB_PATH.parent / "devices" / f"{a}.jpg").exists() and (config.DB_PATH.parent / "devices" / f"{b}.jpg").exists()


# ---------------------------------------------------------------- Zepp ermitteln (gemockt)
H = [{"trackid": str(T0 - 86400 * 400 + i * 1000), "type": "6", "dis": "5000", "run_time": "3000", "end_time": str(T0), "source": "run.46.huami.com"} for i in range(3)] + \
    [{"trackid": str(T0 + i * 1000), "type": "9", "dis": "9000", "run_time": "3000", "end_time": str(T0), "source": "watch.99.huami.com"} for i in range(2)] + \
    [{"trackid": str(T0 + 7000), "type": "6", "dis": "1", "run_time": "1", "end_time": str(T0)}, "kaputt"]


class _Api:
    def history(self): return H


def test_zepp_probe_groups_by_source(monkeypatch):
    from app import sync
    monkeypatch.setattr(sync, "_zepp_api", lambda: _Api())
    c = _client()
    r = c.post("/api/devices/zepp-probe")
    assert r.status_code == 200
    j = r.json()
    assert [s["zsrc"] for s in j["sources"]] == ["run.46.huami.com", "watch.99.huami.com"]       # nach erstem Datum
    a, b = j["sources"]
    assert a["n"] == 3 and b["n"] == 2 and j["total"] == 5 and j["without_source"] == 1
    assert a["first"] <= a["last"] < b["first"] and a["overlaps"] == [] and b["overlaps"] == []
    assert a["sports"][0]["n"] == 3 and a["device"] is None
    assert "source" in j["sample_keys"] and "trackid" in j["sample_keys"]
    assert "token" not in str(j).lower() and "password" not in str(j).lower()
    assert c.get("/api/my-devices").json()["devices"] == []                        # nichts angelegt


def test_zepp_probe_overlap_and_known_device(monkeypatch):
    from app import sync
    hist = [{"trackid": str(T0), "type": "6", "source": "a"}, {"trackid": str(T0 + 100000), "type": "6", "source": "a"},
            {"trackid": str(T0 + 50000), "type": "6", "source": "b"}]
    monkeypatch.setattr(sync, "_zepp_api", lambda: type("A", (), {"history": lambda s: hist})())
    c = _client()
    _dev(c, name="Schon da", zsrc="b")
    j = c.post("/api/devices/zepp-probe").json()
    by = {s["zsrc"]: s for s in j["sources"]}
    assert by["a"]["overlaps"] == ["b"] and by["b"]["overlaps"] == ["a"]
    assert by["b"]["device"]["name"] == "Schon da" and by["a"]["device"] is None


@pytest.mark.parametrize("exc", [zepp.ZeppError("Token abgelaufen"), RuntimeError("Zepp-Zugangsdaten fehlen (Einstellungen)"), ValueError("kaputt")])
def test_zepp_probe_access_errors_are_422(monkeypatch, exc):
    from app import sync
    def boom(): raise exc
    monkeypatch.setattr(sync, "_zepp_api", boom)
    r = _client().post("/api/devices/zepp-probe")
    assert r.status_code == 422 and str(exc) in r.json()["detail"]
    class A:
        def history(self): raise zepp.ZeppError("Kein Zepp-Server antwortet")
    monkeypatch.setattr(sync, "_zepp_api", lambda: A())
    r = _client().post("/api/devices/zepp-probe")
    assert r.status_code == 422 and "Kein Zepp-Server" in r.json()["detail"]


def test_zepp_probe_without_credentials_is_422():
    r = _client().post("/api/devices/zepp-probe")
    assert r.status_code == 422 and "Zugangsdaten" in r.json()["detail"]


def test_zepp_apply_creates_attaches_and_never_duplicates():
    c = _client()
    old = _dev(c, name="Meine Uhr")
    r = c.post("/api/devices/zepp-apply", json={"devices": [
        {"zsrc": "run.46.huami.com", "name": "Zepp-Uhr 1", "model": "", "since": "2021-05-01", "until": "2024-02-29"},
        {"zsrc": "watch.99.huami.com", "attach_to": old}]}).json()
    assert len(r["created"]) == 1 and r["attached"] == [old] and r["skipped"] == []
    devs = {d["name"]: d for d in c.get("/api/my-devices").json()["devices"]}
    assert devs["Zepp-Uhr 1"]["zsrc"] == "run.46.huami.com" and devs["Zepp-Uhr 1"]["model"] == "" and devs["Zepp-Uhr 1"]["until"] == "2024-02-29"
    assert devs["Meine Uhr"]["zsrc"] == "watch.99.huami.com"
    r = c.post("/api/devices/zepp-apply", json={"devices": [{"zsrc": "run.46.huami.com", "name": "Nochmal"}]}).json()
    assert r["created"] == [] and r["skipped"] == ["run.46.huami.com"] and len(c.get("/api/my-devices").json()["devices"]) == 2
    assert c.post("/api/devices/zepp-apply", json={"devices": []}).status_code == 400
    assert c.post("/api/devices/zepp-apply", json={"devices": [{"zsrc": "x", "name": " "}]}).status_code == 400
    assert c.post("/api/devices/zepp-apply", json={"devices": [{"zsrc": "y", "attach_to": 999}]}).status_code == 404


# ---------------------------------------------------------------- Zuordnung über die Kennung
def test_assignment_prefers_matching_zsrc_then_date(monkeypatch):
    from app import sync
    c = _client()
    a = _dev(c, name="Alt", until="2025-03-31", zsrc="old.huami.com")
    b = _dev(c, name="Neu", since="2025-04-01", zsrc="new.huami.com")
    _tour(f"z{T0}", 1735689600, "zepp")                 # 2025-01-01: nach Datum Gerät „Alt“
    _tour("z777", 1735689600, "zepp")
    assert mydevices.device_of(f"z{T0}")["name"] == "Alt"
    monkeypatch.setattr(sync, "_zepp_api", lambda: type("A", (), {"history": lambda s: [
        {"trackid": str(T0), "type": "6", "source": "new.huami.com"}, {"trackid": "777", "type": "6", "source": "old.huami.com"}, {"trackid": "888", "source": "old.huami.com"}]})())
    c.post("/api/devices/zepp-probe")                    # merkt die Kennung nur für vorhandene Touren
    assert db.query("SELECT tour_id FROM tour_zsrc ORDER BY tour_id") == [{"tour_id": f"z{T0}"}, {"tour_id": "z777"}]
    assert mydevices.device_of(f"z{T0}")["name"] == "Neu"           # Kennung schlägt das Datum
    assert mydevices.device_of("z777")["name"] == "Alt"
    assert mydevices.assignments()[f"z{T0}"][0]["id"] == b and mydevices.assignments()["z777"][0]["id"] == a
    c.post(f"/api/tours/z{T0}/device", json={"device_id": a})                # ausdrückliche Wahl hat immer Vorrang
    assert mydevices.device_of(f"z{T0}")["id"] == a and mydevices.device_of(f"z{T0}")["manual"]


def test_zsrc_only_used_for_same_kind_and_without_zsrc_unchanged():
    c = _client()
    g = _dev(c, name="Garmin", kind="garmin", zsrc="run.1")
    z = _dev(c, name="Zepp")
    _tour("t1", T0, "zepp")
    db.execute("INSERT INTO tour_zsrc(tour_id,zsrc) VALUES('t1','run.1')")
    assert mydevices.device_of("t1")["id"] == z                      # gleiche Kennung, aber andere Art -> nicht bevorzugt
    assert mydevices.device_of("t1")["model"] == ""


def test_delete_local_forgets_zsrc():
    from app import metrics
    _tour("t2", T0, "zepp")
    db.execute("INSERT INTO tour_zsrc(tour_id,zsrc) VALUES('t2','a')")
    metrics.forget("t2")
    assert db.one("SELECT 1 FROM tour_zsrc WHERE tour_id='t2'") is None


# ---------------------------------------------------------------- Migration
def test_migration_adds_zsrc_idempotently_and_keeps_data(tmp_path):
    p = tmp_path / "alt.sqlite"
    con = sqlite3.connect(p)
    con.execute("CREATE TABLE devices (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, kind TEXT, model TEXT, since TEXT, until TEXT, active INTEGER DEFAULT 1, note TEXT)")
    con.execute("INSERT INTO devices(name,kind,model,note) VALUES('Alt','zepp','Balance 2','Notiz')")
    con.commit(); con.close()
    for _ in range(2):                                              # zweimal öffnen: kein Fehler
        db.close_all()
        c = db._open(p)
        cols = {r["name"] for r in c.execute("PRAGMA table_info(devices)")}
        assert {"zsrc", "model", "note"} <= cols
        r = c.execute("SELECT name, model, note, zsrc FROM devices").fetchone()
        assert (r["name"], r["model"], r["note"], r["zsrc"]) == ("Alt", "Balance 2", "Notiz", None)
    assert c.execute("SELECT 1 FROM sqlite_master WHERE name='tour_zsrc'").fetchone()
    db.close_all()
