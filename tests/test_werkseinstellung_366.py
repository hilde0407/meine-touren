"""3.66.0 – Werkseinstellung für alle Seiten (Server): POST /api/layout/werkseinstellung.
Mit und ohne „eigene Ansichten löschen“, alle Seitenschlüssel, Tourseite (zwei Dokumente), Regeln, fehlende Standardansicht, Grenze von 12 Ansichten, altes Format, Betrachter, Benutzertrennung,
und dass nichts außer den Layouts angefasst wird (Ziele, Touren, Einstellungen)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
KEYS = ("tour-haupt", "tour-auswertung", "uebersicht", "statistik", "reise", "serie", "reisen", "gebiete", "gebiet", "fotos", "karte")


def _box(own=1, std=True, active="standard", rules=None, hidden=("wp",)):
    views = ([{"id": "standard", "name": "Standard", "layout": {"v": 1, "hidden": list(hidden)}}] if std else [])
    views += [{"id": f"v{i}", "name": f"Eigene {i}", "layout": {"v": 1, "order": ["map"]}} for i in range(1, own + 1)]
    return {"v": 2, "views": views, "active": active, "rules": rules or {}}


def _fill(c, **kw):
    for k in KEYS:
        r = c.put("/api/layout/" + k, json=_box(rules=({"hike": "v1"} if k.startswith("tour") else {}), active="v1", **kw))
        assert r.status_code == 200, (k, r.text)


def _c():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def test_eigene_ansichten_bleiben_standard_wird_zurueckgesetzt():
    with _c() as c:
        _fill(c)
        r = c.post("/api/layout/werkseinstellung", json={"eigene_ansichten_loeschen": False})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["ok"] and j["geloescht"] is False and j["unvollstaendig"] == [] and j["eigene_ansichten"] == 10      # 9 Seiten + Tourseite (einmal gezählt), je 1 eigene Ansicht
        assert set(j["layouts"]) == set(KEYS)
        for k in KEYS:
            b = c.get("/api/layout/" + k).json()["container"]
            assert b == j["layouts"][k]
            std = next(v for v in b["views"] if v["id"] == "standard")
            assert std["layout"] == {"v": 1} and std["name"] == "Standard"                        # zurückgesetzt, „wp“ nicht mehr ausgeblendet
            assert b["active"] == "standard"                                                      # Festlegung auf die mitgelieferte
            own = next(v for v in b["views"] if v["id"] == "v1")
            assert own["layout"] == {"v": 1, "order": ["map"]} and own["name"] == "Eigene 1"      # eigene Ansicht unberührt
        assert c.get("/api/layout/tour-haupt").json()["container"]["rules"] == {"hike": "v1"}    # Regel nach Sportart bleibt
        assert c.get("/api/layout/statistik").json()["container"]["rules"] == {}


def test_eigene_ansichten_loeschen_entfernt_alle_dokumente():
    with _c() as c:
        _fill(c)
        j = c.post("/api/layout/werkseinstellung", json={"eigene_ansichten_loeschen": True}).json()
        assert j["ok"] and j["geloescht"] is True and all(v is None for v in j["layouts"].values()) and j["eigene_ansichten"] == 10
        for k in KEYS:
            g = c.get("/api/layout/" + k).json()
            assert g["layout"] is None and g["container"] is None, k


def test_nur_standardansicht_ohne_eigene_loescht_das_dokument():
    with _c() as c:
        for k in KEYS:
            assert c.put("/api/layout/" + k, json={"order": ["map"], "hidden": ["wp"]}).status_code == 200            # altes Format
        j = c.post("/api/layout/werkseinstellung", json={}).json()                                           # Standard: eigene behalten (hier gibt es keine)
        assert j["ok"] and j["eigene_ansichten"] == 0 and all(v is None for v in j["layouts"].values())
        assert all(c.get("/api/layout/" + k).json()["container"] is None for k in KEYS)


def test_fehlende_standardansicht_wird_neu_angelegt():
    with _c() as c:
        b = _box(2, std=False, active="v2")
        b["views"][0]["name"] = "Standard"                                                   # Namenskonflikt: die eigene Ansicht heißt schon so
        assert c.put("/api/layout/uebersicht", json=b).status_code == 200
        j = c.post("/api/layout/werkseinstellung", json={"eigene_ansichten_loeschen": False}).json()
        v = c.get("/api/layout/uebersicht").json()["container"]
        assert [x["id"] for x in v["views"]] == ["standard", "v1", "v2"] and v["active"] == "standard"
        assert v["views"][0]["name"] == "Standard (Werkseinstellung)" and v["views"][1]["name"] == "Standard"
        assert j["unvollstaendig"] == []


def test_zwoelf_ansichten_ohne_standard_bleiben_unveraendert_und_werden_gemeldet():
    with _c() as c:
        b = _box(12, std=False, active="v3")
        assert c.put("/api/layout/fotos", json=b).status_code == 200
        before = c.get("/api/layout/fotos").json()["container"]
        j = c.post("/api/layout/werkseinstellung", json={"eigene_ansichten_loeschen": False}).json()
        assert j["unvollstaendig"] == ["fotos"] and c.get("/api/layout/fotos").json()["container"] == before == j["layouts"]["fotos"]


def test_eingabe_wird_geprueft_betrachter_und_benutzertrennung():
    from fastapi.testclient import TestClient
    from app import main
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        _fill(c)
        for bad in ({"eigene_ansichten_loeschen": "ja"}, {"x": 1}, [1]):
            assert c.post("/api/layout/werkseinstellung", json=bad).status_code == 400, bad
        assert c.post("/api/layout/werkseinstellung", content=b"{kaputt", headers={"Content-Type": "application/json"}).status_code == 400
        assert c.post("/api/users", json={"name": "Anna", "email": "anna@example.com", "password": "annas-pass12", "role": "user"}).status_code == 200
        assert c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"}).status_code == 200
        a = TestClient(main.app)
        assert a.post("/api/login", json={"name": "anna", "password": "annas-pass12"}).status_code == 200
        assert a.put("/api/layout/uebersicht", json=_box(2)).status_code == 200
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert v.post("/api/layout/werkseinstellung", json={"eigene_ansichten_loeschen": True}).status_code == 403
        assert TestClient(main.app).post("/api/layout/werkseinstellung", json={}).status_code == 401
        assert c.get("/api/layout/uebersicht").json()["container"] is not None                   # nichts passiert
        # Annas Reset berührt Maxens Layouts nicht, Maxens nicht Annas
        assert a.post("/api/layout/werkseinstellung", json={"eigene_ansichten_loeschen": True}).status_code == 200
        assert a.get("/api/layout/uebersicht").json()["container"] is None and c.get("/api/layout/uebersicht").json()["container"] is not None
        assert c.post("/api/layout/werkseinstellung", json={"eigene_ansichten_loeschen": True}).status_code == 200


def test_ziele_und_andere_daten_bleiben_unberuehrt():
    from app import db
    with _c() as c:
        _fill(c)
        n_before = {t: db.one(f"SELECT COUNT(*) n FROM {t}")["n"] for t in ("tours", "goals", "user_layout")}
        c.post("/api/layout/werkseinstellung", json={"eigene_ansichten_loeschen": True})
        n_after = {t: db.one(f"SELECT COUNT(*) n FROM {t}")["n"] for t in ("tours", "goals", "user_layout")}
        assert n_after["tours"] == n_before["tours"] and n_after["goals"] == n_before["goals"] and n_after["user_layout"] == 0 < n_before["user_layout"]


def test_quelltext_und_versionshinweis():
    from app import config
    assert config.VERSION.startswith("3.70.1 · Meine Touren")
    js = (ROOT / "app" / "static" / "js")
    assert 'SL_APPV = "3.70.1"' in (js / "54-ansichten.js").read_text(encoding="utf-8")
    assert 'const V = "mt-v161"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    assert (ROOT / "docs" / "versionen" / "3.66.0.md").exists()
    assert "3.66.0" in (ROOT / "docs" / "VERSIONSVERLAUF.md").read_text(encoding="utf-8")
    assert "3.66.0" in (ROOT / "docs" / "versionen" / "README.md").read_text(encoding="utf-8")
