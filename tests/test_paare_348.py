"""3.48.0 – Darstellungs-Paare: „Touren holen (nur Knopf)“ (holenknopf) ist die Darstellung „Nur Knopf“ von „Touren holen“ (zeppimport). Alias beim Speichern, beim Öffnen der Datenbank,
in Ansichten, Export-Dateien und Ansichtscodes; die Tabelle der Oberfläche (SL_ALIAS) enthält denselben Eintrag. Nicht zusammengelegt (Standard-Abschnitte): siehe docs/versionen/3.48.0.md."""
import base64
import json
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import baustein_umzug as umzug, db  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
ALT = [{"id": "hk1", "type": "holenknopf", "cfg": {}}, {"id": "hk2", "type": "holenknopf", "cfg": {"title": "Holen", "x": 1}}, {"id": "zi", "type": "zeppimport", "cfg": {}}]


def client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _check(lay):
    by = {w["id"]: w for w in lay["widgets"]}
    assert by["hk1"] == {"id": "hk1", "type": "zeppimport", "cfg": {"view": "knopf"}}
    assert by["hk2"] == {"id": "hk2", "type": "zeppimport", "cfg": {"view": "knopf", "title": "Holen"}}
    assert by["zi"]["type"] == "zeppimport" and by["zi"]["cfg"] == {}                       # der Baustein „Touren holen“ bleibt unverändert (Darstellung Karte ist der Standard)
    assert "holenknopf" not in {w["type"] for w in lay["widgets"]}


def test_alias_tabelle():
    assert umzug.alias("holenknopf", {}) == ("zeppimport", {"view": "knopf"}, [])
    assert umzug.has_alt({"widgets": [{"type": "holenknopf"}]})
    assert "holenknopf" in umzug.ALT


def test_put_und_ansichten_behaelter():
    with client() as c:
        r = c.put("/api/layout/uebersicht", json={"widgets": ALT, "w": {"hk1": "drittel"}, "order": ["hk1"]})
        assert r.status_code == 200, r.text
        lay = c.get("/api/layout/uebersicht").json()["layout"]
        _check(lay)
        assert lay["w"] == {"hk1": "drittel"} and lay["order"] == ["hk1"]                  # Breite und Reihenfolge bleiben
        r = c.put("/api/layout/uebersicht", json={"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"widgets": ALT}}, {"id": "zwei", "name": "Zwei", "layout": {"widgets": ALT[:1]}}],
                                                 "active": "standard", "rules": {}})
        assert r.status_code == 200, r.text
        st = c.get("/api/layout/uebersicht").json()["layout"]
        _check(st["views"][0]["layout"])
        assert st["views"][1]["layout"]["widgets"][0]["type"] == "zeppimport"


def test_umzug_beim_oeffnen_der_datenbank():
    raw = {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"widgets": ALT}}], "active": "standard", "rules": {}}
    db.execute("INSERT INTO user_layout(page_key,json,ts) VALUES('uebersicht',?,1)", (json.dumps(raw),))
    path = db.pfad()
    db.close_all()
    db.init()
    _check(json.loads(db.one("SELECT json FROM user_layout WHERE page_key='uebersicht'")["json"])["views"][0]["layout"])
    with sqlite3.connect(str(path)) as con:
        con.row_factory = sqlite3.Row
        assert umzug.migrate_rows(con) == 0


def test_export_datei_und_ansichtscode():
    doc = {"format": "meine-touren-ansicht", "format_version": 1, "app_version": "3.47.1", "page": "uebersicht", "name": "Alt", "exported": "2026-11-01T10:00:00Z", "layouts": {"uebersicht": {"widgets": ALT}}}
    with client() as c:
        r = c.post("/api/layout/check", json=doc).json()
        assert r["ok"] is True, r
        _check(r["layouts"]["uebersicht"])
        code = "MTA1." + base64.urlsafe_b64encode(json.dumps(doc).encode()).decode().rstrip("=")
        r2 = c.post("/api/layout/code", json={"code": code}).json()
        assert r2["ok"] is True and r2["layouts"] == r["layouts"]


def test_oberflaeche_tabelle_und_vorlagen():
    js = (ROOT / "app" / "static" / "js" / "49-seitenlayout.js").read_text(encoding="utf-8")
    assert '  holenknopf: c => ["zeppimport", {view: "knopf"' in js
    allejs = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "app" / "static" / "js").glob("5*.js"))
    assert "  holenknopf: {" not in allejs
    tpl = (ROOT / "app" / "static" / "js" / "55-vorlagen.js").read_text(encoding="utf-8")
    assert "holenknopf" not in tpl
