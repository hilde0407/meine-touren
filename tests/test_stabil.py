"""3.7.7: Rollback in cur(), Zepp-Token-Formular, offene API-Pfade, Kachel-Cache, Komoot-Wiederholungen, Login-Zähler."""
import threading
import pytest
from fastapi.testclient import TestClient
from tests.test_core import fresh      # noqa: F401  (Fixture)

from app import config, db


def test_cur_rollback_laesst_keine_halbtransaktion(fresh):      # noqa: F811
    db.execute("CREATE TABLE IF NOT EXISTS rb_t(x TEXT)")
    with pytest.raises(RuntimeError):
        with db.cur() as c:
            c.execute("INSERT INTO rb_t(x) VALUES('halb')")
            raise RuntimeError("Abbruch mitten in der Transaktion")
    with db.cur() as c:                                          # nächster Benutzer der geteilten Verbindung
        c.execute("INSERT INTO rb_t(x) VALUES('ganz')")
    assert [r["x"] for r in db.query("SELECT x FROM rb_t")] == ["ganz"]


@pytest.fixture
def app(fresh):                                                  # noqa: F811
    from app import main
    c = TestClient(main.app)
    assert c.post("/api/setup", json={"name": "Max", "password": "geheim1234", "email": "max@example.com"}).status_code == 200
    return c, main


def _tree():
    return sorted(str(p.relative_to(config.DATA_DIR.parent)) for p in config.DATA_DIR.parent.rglob("*") if "pycache" not in str(p))


def test_zepp_token_ungueltiger_benutzer_legt_nichts_an(app):
    c, main = app
    key = c.get("/api/zepp-key").json()
    anon = TestClient(main.app)
    falsch = anon.post("/api/zepp-token", data={"u": key["u"], "k": "falsch", "token": "x" * 50})
    vorher, conns = _tree(), len(db._conns)
    for u in ("../x", "..", "nobody", "a/b", "X" * 80, ""):
        r = anon.post("/api/zepp-token", data={"u": u, "k": key["k"], "token": "x" * 50})
        assert r.status_code == falsch.status_code and r.text == falsch.text, u          # keine Benutzer-Enumeration
    assert _tree() == vorher and len(db._conns) == conns
    ok = anon.post("/api/zepp-token", data={"u": key["u"], "k": key["k"], "token": "kurz"})      # richtiger Schlüssel kommt durch die Prüfung
    assert "Kein gültiges Token" in ok.text


def test_token_page_escaped(app):
    from app import main
    assert "<script>" not in main._token_page("<script>alert(1)</script>", False).body.decode()


def test_offene_pfade_exakt(app):
    c, main = app
    anon = TestClient(main.app)
    assert anon.post("/api/zepp-token/test").status_code == 401
    assert anon.get("/api/me/2fa").status_code == 401
    assert anon.get("/api/me").status_code == 200 and anon.get("/api/version").status_code == 200
    assert anon.get("/api/reset/unbekannt").status_code != 401          # Passwort-Link bleibt offen


def test_kachel_gleichzeitig_ohne_fehler(fresh, tmp_path, monkeypatch):      # noqa: F811
    from app import extras
    monkeypatch.setattr(extras, "TILE_DIR", tmp_path); monkeypatch.setattr(config, "TILE_FETCH", True)
    bar = threading.Barrier(2, timeout=5)

    class R:
        status_code, content = 200, b"\x89PNG-test"

    def fake_get(*a, **k):
        bar.wait()                                   # beide Threads sind gleichzeitig beim Schreiben
        return R()
    monkeypatch.setattr(extras.requests, "get", fake_get)
    errs = []

    def run():
        try:
            extras.api_tile("osm", 5, 3, 4)
        except Exception as e:  # noqa
            errs.append(e)
    ts = [threading.Thread(target=run) for _ in range(2)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errs
    assert (tmp_path / "osm" / "5" / "3" / "4.png").read_bytes() == R.content
    assert not list(tmp_path.rglob("*.tmp"))


class _Resp:
    def __init__(self, status, j=None):
        self.status_code, self._j, self.text = status, j or {}, ""

    def json(self):
        return self._j


def _komoot(monkeypatch, antworten):
    from app import komoot
    k = komoot.Komoot("a@b.de", "pw"); k.user_id, k.token = "1", "alt"
    calls = []
    monkeypatch.setattr(komoot.time, "sleep", lambda s: None)
    monkeypatch.setattr(k, "login", lambda: setattr(k, "token", "neu") or "1")

    def fake_get(url, params=None, auth=None, timeout=0):
        calls.append((url, auth[1])); return antworten.pop(0)
    monkeypatch.setattr(komoot.requests, "get", fake_get)
    return k, calls


def test_komoot_coordinates_401_meldet_neu_an(monkeypatch):
    items = {"items": [{"lat": 1.0, "lng": 2.0, "alt": 3.0, "t": 0}]}
    k, calls = _komoot(monkeypatch, [_Resp(401), _Resp(200, items)])
    assert k.coordinates("7") == [(1.0, 2.0, 3.0, 0)]
    assert [c[1] for c in calls] == ["alt", "neu"]


def test_komoot_coordinates_dauerfehler_ist_exception(monkeypatch):
    from app import komoot
    k, calls = _komoot(monkeypatch, [_Resp(500)] * 6)
    with pytest.raises(komoot.KomootError):
        k.coordinates("7")
    assert len(calls) == 6                          # je Variante 3 Versuche


def test_komoot_coordinates_429_dann_ok_und_leer_bleibt_leer(monkeypatch):
    k, _ = _komoot(monkeypatch, [_Resp(429), _Resp(200, {"items": []}), _Resp(200, {})])
    assert k.coordinates("7") == []                 # echte leere Strecke ist kein Fehler


def test_login_zaehler_wird_bereinigt(fresh, monkeypatch):      # noqa: F811
    from app import auth
    auth._fail.clear(); auth._fail_prune = 0.0
    auth._fail["alt|1.2.3.4"] = [1.0]
    with pytest.raises(PermissionError):
        auth.check_login("irgendwer", "x", "9.9.9.9")
    assert "alt|1.2.3.4" not in auth._fail


def test_ip_nur_mit_trust_proxy(monkeypatch):
    from app import users_api

    class Rq:
        client = type("C", (), {"host": "10.0.0.1"})()
        headers = {"x-forwarded-for": "6.6.6.6, 5.5.5.5"}
    monkeypatch.delenv("TRUST_PROXY", raising=False)
    assert users_api._ip(Rq()) == "10.0.0.1"
    monkeypatch.setenv("TRUST_PROXY", "1")
    assert users_api._ip(Rq()) == "5.5.5.5"


def test_freigaben_uebersicht_verwalten(fresh):
    """Alle Links an einem Ort: Liste mit Tourname, Laufzeit ändern, Kommentare, Abgelaufene entfernen, Widerruf."""
    import time
    from app import db
    from fastapi.testclient import TestClient
    from app import main
    from tests.test_core import gpx
    c = TestClient(main.app)
    c.post("/api/share-target", files=[("files", ("Runde.gpx", gpx("Workout--2025-06-01--08-00-00.gpx").encode(), "application/octet-stream"))], follow_redirects=False)
    tid = db.one("SELECT id FROM tours")["id"]
    a = c.post(f"/api/tours/{tid}/share", json={"days": 7}).json()["token"]
    b = c.post(f"/api/tours/{tid}/share", json={"show": True, "comments": True}).json()["token"]
    lst = c.get("/api/shares").json()
    assert {x["token"] for x in lst} == {a, b} and all(x["name"] for x in lst)
    assert next(x for x in lst if x["token"] == b)["comments"] == 1
    r = c.patch(f"/api/share/{b}", json={"days": 30, "comments": False}).json()
    assert r["comments"] == 0 and r["exp"] > time.time() + 29 * 86400
    assert c.patch(f"/api/share/{b}", json={"days": 0}).json()["exp"] is None
    assert c.patch(f"/api/share/{a}", json={"comments": True}).json()["comments"] == 0       # nur Diashows haben Kommentare
    assert c.patch(f"/api/share/{b}", json={"days": -1}).status_code == 400 and c.patch("/api/share/gibtsnicht", json={}).status_code == 404
    db.execute("UPDATE shares SET exp=? WHERE token=?", (int(time.time()) - 5, a))
    assert c.get(f"/api/public/{a}").status_code in (404, 410)
    assert c.post("/api/shares/purge-expired").json() == {"removed": 1}
    assert [x["token"] for x in c.get("/api/shares").json()] == [b]
    assert c.delete(f"/api/share/{b}").status_code == 200 and c.get("/api/shares").json() == []


def test_umzugspaket_komplett(tmp_path):
    """Umzugspaket: Datenbanken, Fotos, Strecken, Schlüssel sind drin, Vorschaubilder/Kacheln nicht; Wiederherstellen ergibt identische Daten."""
    import sqlite3
    import zipfile
    import pytest
    from app import umzug
    src = tmp_path / "alt"
    (src / "users/u1/photos/2025").mkdir(parents=True); (src / "users/u1/cache/coords").mkdir(parents=True); (src / "users/u1/cache/thumb/ab").mkdir(parents=True)
    (src / "tilecache").mkdir(); (src / "backups").mkdir()
    for n in ("users/u1/komoot_hub.sqlite", "system.sqlite"):
        c = sqlite3.connect(src / n); c.execute("CREATE TABLE tour_notes(id TEXT, note TEXT)"); c.execute("INSERT INTO tour_notes VALUES('a','Notiz äöü')"); c.commit(); c.close()
    (src / "users/u1/photos/2025/f.jpg").write_bytes(b"\xff\xd8JPEGDATA")
    (src / "users/u1/cache/coords/a.orig.json").write_text("[1,2]")
    (src / "users/u1/cache/thumb/ab/t.jpg").write_bytes(b"thumb")
    (src / "tilecache/k.png").write_bytes(b"tile"); (src / "backups/x.zip").write_bytes(b"old")
    (src / "secret.key").write_text("geheim"); (src / "ui_password.json").write_text("{}")
    pkg = umzug.make(src, tmp_path / "out", "t", keep=2)
    names = set(zipfile.ZipFile(pkg).namelist())
    assert {"UMZUG.txt", "data/secret.key", "data/system.sqlite", "data/users/u1/komoot_hub.sqlite", "data/users/u1/photos/2025/f.jpg",
            "data/users/u1/cache/coords/a.orig.json", "data/ui_password.json"} <= names
    assert not any("thumb" in n or "tilecache" in n or "backups" in n for n in names) and umzug.is_package(pkg)
    neu = tmp_path / "neu"
    assert umzug.restore(pkg, neu) == 6
    assert (neu / "users/u1/photos/2025/f.jpg").read_bytes() == b"\xff\xd8JPEGDATA" and (neu / "secret.key").read_text() == "geheim"
    assert sqlite3.connect(neu / "users/u1/komoot_hub.sqlite").execute("SELECT note FROM tour_notes").fetchone()[0] == "Notiz äöü"
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as z:
        z.writestr("UMZUG.txt", "x"); z.writestr("data/../../evil.txt", "x")
    with pytest.raises(RuntimeError):
        umzug.restore(bad, tmp_path / "ziel")
    assert not (tmp_path / "evil.txt").exists()


def test_umzugspaket_api(fresh, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app import main, extras
    import time
    from app import config
    monkeypatch.setattr(config, "BACKUP_ROOT", tmp_path / "bk")
    c = TestClient(main.app)
    assert c.post("/api/backup/full").json() == {"started": True}
    l = []
    for _ in range(100):                                 # Job läuft im Hintergrund: warten, bis das Paket in der Liste steht
        l = c.get("/api/backup/full").json()
        if l:
            break
        time.sleep(0.1)
    assert l and l[0]["name"].startswith("meine-touren-umzug-")
    r = c.get("/api/backup/full/" + l[0]["name"]); assert r.status_code == 200 and r.content[:2] == b"PK"
    assert c.get("/api/backup/full/..%2Fetc%2Fpasswd").status_code == 404
