"""3.21.0 – Ansichten, Backend: Behälter mit mehreren Layouts je Seite, Migration des alten Formats, Validierung, Regeln, Limits, Export-Prüfung, Betrachter, Benutzertrennung, Hinweise."""
import copy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
OLD = {"order": ["prof", "map"], "hidden": ["wp"], "widgets": [{"id": "wk1", "type": "kennzahlen", "cfg": {"values": ["km"]}}]}


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _box(n=2, **kw):
    d = {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1}}] + [{"id": f"v{i}", "name": f"Ansicht {i}", "layout": {"order": ["map"]}} for i in range(1, n)], "active": "standard"}
    d.update(kw)
    return d


def test_old_format_is_read_as_one_view_and_stays_as_stored():
    with _client() as c:
        assert c.get("/api/layout/tour-haupt").json()["container"] is None
        assert c.put("/api/layout/tour-haupt", json=OLD).status_code == 200
        g = c.get("/api/layout/tour-haupt").json()
        assert g["layout"]["order"] == ["prof", "map"] and "views" not in g["layout"]           # wie gespeichert (rückwärtskompatibel)
        b = g["container"]
        assert [v["id"] for v in b["views"]] == ["standard"] and b["views"][0]["name"] == "Standard" and b["active"] == "standard" and b["rules"] == {}
        assert b["views"][0]["layout"]["widgets"][0]["id"] == "wk1"                            # nichts geht verloren


def test_container_roundtrip_and_validation():
    with _client() as c:
        box = _box(3, rules={"hike": "v1", "bike": "v2"})
        box["views"][1]["name"] = "  Wandern   Berg "
        r = c.put("/api/layout/tour-haupt", json=box)
        assert r.status_code == 200, r.text
        g = c.get("/api/layout/tour-haupt").json()
        assert g["container"]["views"][1]["name"] == "Wandern Berg" and g["container"]["rules"] == {"hike": "v1", "bike": "v2"} and g["layout"]["v"] == 2
        assert g["container"]["views"][1]["layout"] == {"v": 1, "order": ["map"]}
        # die Seitenschlüssel sind unabhängig: die Übersicht kennt keine Sportart-Regeln
        assert c.put("/api/layout/uebersicht", json=_box(2)).status_code == 200
        assert c.put("/api/layout/uebersicht", json=_box(2, rules={"hike": "v1"})).status_code == 400
        assert c.put("/api/layout/uebersicht", json=_box(2, rules={})).status_code == 200
        good = c.get("/api/layout/tour-haupt").json()["container"]
        bad = [
            _box(2, active="gibtsnicht"), _box(2, rules={"hike": "nope"}), _box(2, rules={"hi ke": "v1"}), _box(2, rules=[]), _box(2, extra=1),
            _box(13), {"v": 2, "views": [], "active": "x"}, {"views": "x"}, _box(1, views=[{"id": "a b", "name": "x", "layout": {}}]),
            {"v": 2, "views": [{"id": "a", "name": "x", "layout": {}}, {"id": "a", "name": "y", "layout": {}}], "active": "a"},
            {"v": 2, "views": [{"id": "a", "name": "", "layout": {}}], "active": "a"}, {"v": 2, "views": [{"id": "a", "name": "x" * 41, "layout": {}}], "active": "a"},
            {"v": 2, "views": [{"id": "a", "name": "<b>x</b>", "layout": {}}], "active": "a"}, {"v": 2, "views": [{"id": "a", "name": 5, "layout": {}}], "active": "a"},
            {"v": 2, "views": [{"id": "a", "name": "x", "layout": {"evil": 1}}], "active": "a"}, {"v": 2, "views": [{"id": "a", "name": "x", "layout": {"order": "map"}}], "active": "a"},
            {"v": 2, "views": [{"id": "a", "name": "x", "layout": {}, "extra": 1}], "active": "a"}, {"v": 2, "views": ["a"], "active": "a"},
            {"v": 2, "views": [{"id": "a", "name": "x", "layout": {"widgets": [{"id": "w1", "type": "kennzahlen"}]}}], "active": "a"} if False else {"v": 2, "views": [{"id": "a", "name": "x", "layout": {"w": {"map": "riesig"}}}], "active": "a"},
        ]
        for b in bad:
            r = c.put("/api/layout/tour-haupt", json=b)
            assert r.status_code == 400, (str(b)[:90], r.status_code)
        assert c.get("/api/layout/tour-haupt").json()["container"] == good                # nichts davon wurde gespeichert
        # genau 12 sind erlaubt; Standard fehlt „active“ → erste Ansicht
        assert c.put("/api/layout/tour-haupt", json=_box(12)).status_code == 200
        b = _box(2)
        del b["active"]
        assert c.put("/api/layout/tour-haupt", json=b).json()["layout"]["active"] == "standard"
        # Übersichts-Bausteine einer Tour sind auch in einer Ansicht der Übersicht abgelehnt
        tb = {"v": 2, "views": [{"id": "a", "name": "x", "layout": {"widgets": [{"id": "w1", "type": "kennzahlen"}]}}], "active": "a"}
        assert c.put("/api/layout/uebersicht", json=tb).status_code == 400 and c.put("/api/layout/tour-haupt", json=tb).status_code == 200


def test_size_limits():
    with _client() as c:
        wid = [{"id": "w%d" % i, "type": "heatmap", "cfg": {"text": "a" * 300}} for i in range(40)]          # ~14 000 Zeichen: je Layout erlaubt
        box = {"v": 2, "views": [{"id": "v%d" % i, "name": "A%d" % i, "layout": {"widgets": wid}} for i in range(11)], "active": "v0"}
        r = c.put("/api/layout/uebersicht", json=box)
        assert r.status_code == 400 and "zu groß" in r.json()["detail"]                                      # zusammen über der Grenze
        box["views"] = box["views"][:5]
        assert c.put("/api/layout/uebersicht", json=box).status_code == 200
        assert c.put("/api/layout/uebersicht", content=b'{"views":[' + b"x" * 200000 + b"]}", headers={"Content-Type": "application/json"}).status_code == 413
        huge = {"v": 2, "views": [{"id": "a", "name": "x", "layout": {"widgets": [{"id": "w1", "type": "t", "cfg": {"q": "a" * 590}}] * 1}}], "active": "a", "pad": "z" * 200000}
        assert c.put("/api/layout/uebersicht", json=huge).status_code == 413


def test_check_export_uses_the_server_rules():
    from app import layout
    ok = {"format": "meine-touren-ansicht", "format_version": 1, "app_version": "3.21.0", "page": "tour", "name": "Wandern", "exported": "2026-11-15T10:00:00Z",
          "layouts": {"tour-haupt": OLD, "tour-auswertung": {"order": ["ana"]}}}
    with _client() as c:
        r = c.post("/api/layout/check", json=ok).json()
        assert r["ok"] and r["page"] == "tour" and r["name"] == "Wandern" and r["layouts"]["tour-haupt"]["v"] == 1 and r["layouts"]["tour-auswertung"]["order"] == ["ana"]
        assert r["stats"]["tour-haupt"]["widgets"] == 1 and r["stats"]["tour-haupt"]["types"] == ["kennzahlen"] and r["errors"] == []
        # Unbekanntes auf oberster Ebene wird ignoriert und gemeldet
        x = copy.deepcopy(ok)
        x["zukunft"] = 1
        x["layouts"]["sonstwas"] = {}
        r = c.post("/api/layout/check", json=x).json()
        assert r["ok"] and len(r["ignored"]) == 2 and any("zukunft" in i for i in r["ignored"]) and "sonstwas" not in r["layouts"]
        # Ein fehlender Schlüssel gilt als leeres Layout
        y = copy.deepcopy(ok)
        del y["layouts"]["tour-auswertung"]
        assert c.post("/api/layout/check", json=y).json()["layouts"]["tour-auswertung"] == {"v": 1}
        # Fehler: gleiche Prüfung wie beim Speichern, klare Meldungen, nichts wird geliefert
        cases = [
            ([], "JSON-Objekt"), ({"format": "anders"}, "keine Datei"), ({**ok, "format_version": 2}, "neueren Version"), ({**ok, "format_version": "1"}, "Formatversion"),
            ({**ok, "page": "gibtesnicht"}, "keine gültige Seite"), ({**ok, "name": ""}, "Name"), ({**ok, "name": "x" * 41}, "Name"), ({**ok, "layouts": []}, "keine Ansichten"),
            ({**ok, "layouts": {"tour-haupt": {"evil": 1}}}, "Unbekannte Felder"), ({**ok, "layouts": {"tour-haupt": {"w": {"map": "riesig"}}}}, "Breite"),
            ({**ok, "page": "uebersicht", "layouts": {"uebersicht": {"widgets": [{"id": "w1", "type": "kennzahlen"}]}}}, "Tour"),
        ]
        for doc, word in cases:
            r = c.post("/api/layout/check", json=doc).json()
            assert not r["ok"] and r["layouts"] == {} and any(word in e for e in r["errors"]), (str(doc)[:80], r["errors"])
        r = c.post("/api/layout/check", content=b"{kaputt", headers={"Content-Type": "application/json"}).json()
        assert not r["ok"] and "JSON" in r["errors"][0]
        assert layout.check_export(ok)["ok"]
        assert c.post("/api/layout/check", json=ok).status_code == 200 and c.get("/api/layout/tour-haupt").json()["layout"] is None          # Prüfen speichert nichts


def test_viewer_and_users_are_separated():
    from fastapi.testclient import TestClient
    from app import main
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        assert c.put("/api/layout/tour-haupt", json=_box(2, rules={"hike": "v1"})).status_code == 200
        assert c.post("/api/users", json={"name": "Anna", "email": "anna@example.com", "password": "annas-pass12", "role": "user"}).status_code == 200
        assert c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"}).status_code == 200
        a = TestClient(main.app)
        assert a.post("/api/login", json={"name": "anna", "password": "annas-pass12"}).status_code == 200
        assert a.get("/api/layout/tour-haupt").json()["container"] is None                       # Benutzertrennung
        assert a.put("/api/layout/tour-haupt", json=_box(3)).status_code == 200
        assert len(a.get("/api/layout/tour-haupt").json()["container"]["views"]) == 3 and len(c.get("/api/layout/tour-haupt").json()["container"]["views"]) == 2
        assert c.get("/api/layout/tour-haupt").json()["container"]["rules"] == {"hike": "v1"}
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        g = v.get("/api/layout/tour-haupt").json()
        assert g["layout"] is None and g["container"] is None and g["default"] is True            # Betrachter: immer Standard
        assert v.put("/api/layout/tour-haupt", json=_box(2)).status_code == 403 and v.delete("/api/layout/tour-haupt").status_code == 403
        ok = {"format": "meine-touren-ansicht", "format_version": 1, "page": "tour", "name": "X", "layouts": {}}
        assert v.post("/api/layout/check", json=ok).status_code == 403
        assert a.post("/api/layout/check", json=ok).json()["ok"]
        assert TestClient(main.app).post("/api/layout/check", json=ok).status_code == 401
        assert c.delete("/api/layout/tour-haupt").status_code == 200 and c.get("/api/layout/tour-haupt").json()["container"] is None


def test_version_notes_and_files():
    from app import config
    assert config.VERSION.startswith("3.56.0 · Meine Touren")
    notes = (ROOT / "docs" / "versionen" / "3.21.0.md").read_text(encoding="utf-8")
    assert "Ansichten" in notes and "Vorlagen" in notes and "Export" in notes and "/api/layout/check" in notes and "54-ansichten.js" in notes
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("js/53-filter.js") < html.index("js/54-ansichten.js") < html.index("js/55-vorlagen.js") < html.index("js/39-sw.js")
    assert 'const V = "mt-v141"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
