"""3.17.0 – Layout-API „Seite anpassen“: speichern, lesen, zurücksetzen, Validierung, Betrachter, Benutzertrennung."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401

DOC = {"order": ["prof", "map"], "hidden": ["wp"], "closed": ["ana"], "open": ["wx"], "page": {"ana": "haupt"},
       "widgets": [{"id": "wk1", "type": "kennzahlen", "cfg": {"values": ["km", "up"]}}, {"id": "wn1", "type": "notiz", "cfg": {"text": "Hallo <b>Welt</b>"}}]}


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def test_save_read_reset_without_users():
    with _client() as c:
        r = c.get("/api/layout/tour-haupt")
        assert r.status_code == 200 and r.json()["layout"] is None
        r = c.put("/api/layout/tour-haupt", json=DOC)
        assert r.status_code == 200, r.text
        assert r.json()["layout"]["order"] == ["prof", "map"] and r.json()["layout"]["v"] == 1
        got = c.get("/api/layout/tour-haupt").json()
        assert got["layout"]["widgets"][1]["cfg"]["text"] == "Hallo <b>Welt</b>" and got["layout"]["page"] == {"ana": "haupt"} and got["ts"]
        # andere Seiten bleiben unberührt
        assert c.get("/api/layout/uebersicht").json()["layout"] is None and c.get("/api/layout/tour-auswertung").json()["layout"] is None
        # überschreiben und die Form {"layout": …} akzeptieren
        assert c.put("/api/layout/tour-haupt", json={"layout": {"order": ["map"]}}).status_code == 200
        assert c.get("/api/layout/tour-haupt").json()["layout"] == {"v": 1, "order": ["map"]}
        assert c.delete("/api/layout/tour-haupt").status_code == 200
        assert c.get("/api/layout/tour-haupt").json()["layout"] is None
        assert c.delete("/api/layout/tour-haupt").status_code == 200            # mehrfaches Zurücksetzen schadet nicht


def test_validation():
    with _client() as c:
        assert c.get("/api/layout/gibtsnicht").status_code == 404
        assert c.put("/api/layout/gibtsnicht", json={}).status_code == 404
        assert c.delete("/api/layout/../settings").status_code in (404, 405)
        bad = [
            [], "text", 5, None, {"evil": 1}, {"order": "map"}, {"order": [1]}, {"order": ["a b"]}, {"order": ["<script>"]}, {"order": ["x"] * 121},
            {"hidden": [{"a": 1}]}, {"page": {"ana": "irgendwo"}}, {"page": {"a b": "haupt"}}, {"page": []},
            {"widgets": {}}, {"widgets": [{"id": "w1"}]}, {"widgets": [{"id": "w1", "type": "x", "cfg": [], "extra": 1}]}, {"widgets": [{"id": "w1", "type": "x y"}]},
            {"widgets": [{"id": "w1", "type": "t"}, {"id": "w1", "type": "t"}]}, {"widgets": [{"id": "w%d" % i, "type": "t"} for i in range(41)]},
            {"widgets": [{"id": "w1", "type": "notiz", "cfg": {"text": "x" * 601}}]}, {"widgets": [{"id": "w1", "type": "notiz", "cfg": {"a": {"b": 1}}}]},
            {"widgets": [{"id": "w1", "type": "notiz", "cfg": {"a b": "x"}}]}, {"widgets": [{"id": "w1", "type": "t", "cfg": {"v": ["x"] * 21}}]},
        ]
        for b in bad:
            r = c.put("/api/layout/tour-haupt", json=b)
            assert r.status_code == 400, (b if len(str(b)) < 80 else str(b)[:80], r.status_code)
        assert c.put("/api/layout/tour-haupt", content=b"{kaputt", headers={"Content-Type": "application/json"}).status_code == 400
        assert c.put("/api/layout/tour-haupt", content=b"x" * 60000, headers={"Content-Type": "application/json"}).status_code == 413
        assert c.get("/api/layout/tour-haupt").json()["layout"] is None            # nichts davon wurde gespeichert
        # Größe: viele Bausteine mit langen Texten ergeben mehr als 24 000 Zeichen
        big = {"widgets": [{"id": "w%d" % i, "type": "heatmap", "cfg": {"text": "a" * 600}} for i in range(40)]}
        assert c.put("/api/layout/uebersicht", json=big).status_code == 400
        # Doppelte Kennungen in Listen werden bereinigt, unbekannte Kennungen sind erlaubt (die Oberfläche ignoriert sie)
        r = c.put("/api/layout/tour-auswertung", json={"order": ["ana", "ana", "neu"], "hidden": []})
        assert r.status_code == 200 and r.json()["layout"]["order"] == ["ana", "neu"]


def test_viewer_reads_default_but_cannot_write_and_users_are_separated():
    from fastapi.testclient import TestClient
    from app import main
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        assert c.put("/api/layout/tour-haupt", json=DOC).status_code == 200
        r = c.post("/api/users", json={"name": "Anna", "email": "anna@example.com", "password": "annas-pass12", "role": "user"})
        assert r.status_code == 200, r.text
        r = c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        assert r.status_code == 200, r.text
        a = TestClient(main.app)
        assert a.post("/api/login", json={"name": "anna", "password": "annas-pass12"}).status_code == 200
        assert a.get("/api/layout/tour-haupt").json()["layout"] is None            # Benutzertrennung: Annas Seite ist unberührt
        assert a.put("/api/layout/tour-haupt", json={"order": ["photos"]}).status_code == 200
        assert a.get("/api/layout/tour-haupt").json()["layout"]["order"] == ["photos"]
        assert c.get("/api/layout/tour-haupt").json()["layout"]["order"] == ["prof", "map"]        # Maxens Layout bleibt
        assert a.delete("/api/layout/tour-haupt").status_code == 200
        assert c.get("/api/layout/tour-haupt").json()["layout"]["order"] == ["prof", "map"]
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        g = v.get("/api/layout/tour-haupt")                                         # lesen ja – aber nie das Layout des Besitzers
        assert g.status_code == 200 and g.json()["layout"] is None and g.json()["default"] is True
        assert v.put("/api/layout/tour-haupt", json={"order": ["map"]}).status_code == 403
        assert v.delete("/api/layout/tour-haupt").status_code == 403
        assert c.get("/api/layout/tour-haupt").json()["layout"]["order"] == ["prof", "map"]
        anon = TestClient(main.app)
        assert anon.get("/api/layout/tour-haupt").status_code == 401 and anon.put("/api/layout/tour-haupt", json={}).status_code == 401


def test_viewer_route_pattern_and_photos_recent():
    from app import main
    assert main.VIEWER_GET.match("/api/layout/tour-haupt") and main.VIEWER_GET.match("/api/layout/uebersicht")
    assert not main.VIEWER_GET.match("/api/layout/tour-haupt/x") and not main.VIEWER_GET.match("/api/layout/")
    with _client() as c:
        assert c.get("/api/photos?recent=1&limit=3").status_code == 200


def test_table_lives_in_the_users_database_and_version():
    from app import config, db
    assert db.one("SELECT name FROM sqlite_master WHERE name='user_layout'")
    assert config.VERSION.startswith("3.61.1 · Meine Touren")
    root = Path(__file__).resolve().parent.parent
    html = (root / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("js/48-tourlayout.js") < html.index("js/49-seitenlayout.js") < html.index("js/50-bausteine.js") < html.index("js/39-sw.js")
    notes = (root / "docs" / "versionen" / "3.17.0.md").read_text(encoding="utf-8")
    assert "Seite anpassen" in notes and "/api/layout/" in notes
