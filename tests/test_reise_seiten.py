"""3.33.0 – Reisen als anpassbare Seiten, Server: neue Layout-Schlüssel „reise“ und „reisen“, streng geprüfte Bausteine (Reise-Kennzahlen, Strecke je Tag, Reise-Diashow, Reisen-Kennzahlen, Reisen je Jahr),
keine Bausteine fremder Seiten, keine Regeln, Export-Prüfung, Betrachter, Version, Hinweise und Dienstskript."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _w(wid, typ, cfg=None):
    d = {"id": wid, "type": typ}
    if cfg is not None:
        d["cfg"] = cfg
    return d


def test_keys_roundtrip_and_default():
    with _client() as c:
        for key, order in (("reise", ["kopf", "karte", "touren"]), ("reisen", ["reisen", "serien"])):
            g = c.get(f"/api/layout/{key}").json()
            assert g["layout"] is None
            doc = {"v": 1, "order": order, "hidden": [], "closed": ["touren"] if key == "reise" else [], "w": {order[-1]: "halb"}}
            assert c.put(f"/api/layout/{key}", json=doc).status_code == 200
            got = c.get(f"/api/layout/{key}").json()
            assert got["layout"]["order"] == order
            assert c.delete(f"/api/layout/{key}").status_code == 200
            assert c.get(f"/api/layout/{key}").json()["layout"] is None
        assert c.get("/api/layout/reisen-xx").status_code in (400, 404, 422)
        assert c.put("/api/layout/reisen-xx", json={"v": 1}).status_code in (400, 404, 422)


def test_new_blocks_are_accepted_with_strict_config():
    with _client() as c:
        ok = {"widgets": [_w("wrk1", "rkennzahl", {"values": ["km", "tage", "laender"], "title": "Zahlen"}), _w("wrt1", "rkmtag", {"metric": "up"}),
                          _w("wrd1", "rdiashow", {"mode": "best", "view": "show", "n": 6, "link": False})]}
        assert c.put("/api/layout/reise", json=ok).status_code == 200
        w = c.get("/api/layout/reise").json()["layout"]["widgets"]
        assert [x["type"] for x in w] == ["rkennzahl", "rkmtag", "rdiashow"]
        assert w[0]["cfg"]["values"] == ["tage", "km", "laender"]                               # kanonische Reihenfolge
        ok2 = {"widgets": [_w("wrn1", "rnzahlen", {"values": ["reisen", "km"]}), _w("wrj1", "rnjahre", {"metric": "days"}), _w("wrj2", "rnjahre")]}
        assert c.put("/api/layout/reisen", json=ok2).status_code == 200
        assert [x["type"] for x in c.get("/api/layout/reisen").json()["layout"]["widgets"]] == ["rnzahlen", "rnjahre", "rnjahre"]


def test_bad_config_is_rejected():
    bad = [("reise", _w("a1", "rkennzahl", {"values": []})), ("reise", _w("a1", "rkennzahl", {"values": ["km", "x"]})), ("reise", _w("a1", "rkennzahl", {"values": "km"})),
           ("reise", _w("a1", "rkennzahl", {"metric": "km"})), ("reise", _w("a1", "rkmtag", {"metric": "tage"})), ("reise", _w("a1", "rkmtag", {"metric": ["km"]})),
           ("reise", _w("a1", "rkmtag", {"sports": ["hike"]})), ("reise", _w("a1", "rkmtag", {"fremd": 1})),
           ("reise", _w("a1", "rdiashow", {"sports": ["hike"]})), ("reise", _w("a1", "rdiashow", {"range": "y"})), ("reise", _w("a1", "rdiashow", {"yr": 2024})),
           ("reise", _w("a1", "rdiashow", {"mode": "day"})), ("reise", _w("a1", "rdiashow", {"mode": "nix"})), ("reise", _w("a1", "rdiashow", {"n": 5})),
           ("reisen", _w("a1", "rnzahlen", {"values": ["down"]})), ("reisen", _w("a1", "rnjahre", {"metric": "up"})), ("reisen", _w("a1", "rnjahre", {"metric": 3}))]
    with _client() as c:
        for key, w in bad:
            r = c.put(f"/api/layout/{key}", json={"widgets": [w]})
            assert r.status_code == 400, (key, w, r.status_code)
        assert c.get("/api/layout/reise").json()["layout"] is None and c.get("/api/layout/reisen").json()["layout"] is None


def test_blocks_stay_on_their_own_pages():
    with _client() as c:
        for key, typ in (("reise", "rnzahlen"), ("reise", "rnjahre"), ("reisen", "rkennzahl"), ("reisen", "rkmtag"), ("reisen", "rdiashow"),
                         ("uebersicht", "rkennzahl"), ("statistik", "rkmtag"), ("tour-haupt", "rdiashow"), ("tour-auswertung", "rnjahre"), ("uebersicht", "rnzahlen")):
            assert c.put(f"/api/layout/{key}", json={"widgets": [_w("x1", typ)]}).status_code == 400, (key, typ)
        # und die Bausteine anderer Seiten nicht auf den Reisen-Seiten
        for key in ("reise", "reisen"):
            for typ in ("kennzahlen", "erinn", "eigenkz", "stentwicklung", "bewegung"):
                assert c.put(f"/api/layout/{key}", json={"widgets": [_w("x1", typ)]}).status_code == 400, (key, typ)


def test_rules_exist_only_for_the_tour_page():
    box = {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1}}], "active": "standard", "rules": [{"id": "r1", "view": "standard", "when": {}}]}
    with _client() as c:
        for key in ("reise", "reisen"):
            assert c.put(f"/api/layout/{key}", json=box).status_code == 400
            ok = {k: v for k, v in box.items() if k != "rules"}
            assert c.put(f"/api/layout/{key}", json=ok).status_code == 200
            assert c.get(f"/api/layout/{key}").json()["container"]["active"] == "standard"


def test_export_check_accepts_the_new_pages():
    with _client() as c:
        for page, key, typ in (("reise", "reise", "rkmtag"), ("reisen", "reisen", "rnjahre")):
            doc = {"format": "meine-touren-ansicht", "format_version": 1, "app_version": "3.33.0", "page": page, "name": "Meine", "layouts": {key: {"widgets": [_w("w1", typ)]}}}
            r = c.post("/api/layout/check", json=doc).json()
            assert r["ok"] and r["page"] == page and r["layouts"][key]["widgets"][0]["type"] == typ and r["stats"][key]["widgets"] == 1, r
        bad = {"format": "meine-touren-ansicht", "format_version": 1, "page": "reise", "name": "X", "layouts": {"reise": {"widgets": [_w("w1", "rnjahre")]}}}
        assert c.post("/api/layout/check", json=bad).json()["ok"] is False
        assert c.post("/api/layout/check", json={**bad, "page": "irgendwas"}).json()["ok"] is False


def test_viewer_sees_default_and_cannot_write():
    with _client() as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        assert c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"}).status_code == 200
        assert c.put("/api/layout/reise", json={"v": 1, "order": ["karte", "kopf"]}).status_code == 200
        v = _client()
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        for key in ("reise", "reisen"):
            assert v.get(f"/api/layout/{key}").json()["default"] is True
            assert v.put(f"/api/layout/{key}", json={"v": 1, "order": ["karte"]}).status_code == 403
            assert v.delete(f"/api/layout/{key}").status_code == 403
        assert c.get("/api/layout/reise").json()["layout"]["order"] == ["karte", "kopf"]


def test_version_notes_and_assets():
    from app import config
    assert config.VERSION.startswith("3.61.5 · Meine Touren")
    notes = (ROOT / "docs" / "versionen" / "3.33.0.md").read_text(encoding="utf-8")
    assert "Reisen als anpassbare Seiten" in notes and "reise" in notes and "reisen" in notes
    assert 'const V = "mt-v149"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    js = ROOT / "app" / "static" / "js"
    assert 'SL_APPV = "3.61.5"' in (js / "54-ansichten.js").read_text(encoding="utf-8")
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("60-bausteine-erinnerungen.js") < html.index("61-bausteine-reise.js") < html.index("62-reiseseiten.js")
    assert (js / "61-bausteine-reise.js").exists() and (js / "62-reiseseiten.js").exists()
