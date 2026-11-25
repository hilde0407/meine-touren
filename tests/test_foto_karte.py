"""3.34.0 – Fotos-Seite und Karte als anpassbare Seiten, Server: Schlüssel „fotos“ und „karte“, streng geprüfte Bausteine (Foto-Kennzahlen, Fotos je Jahr, Karten-Kennzahlen,
Touren im Kartenausschnitt, Legende), keine Bausteine fremder Seiten, Export-Prüfung, Betrachter, Feld „eigen“ der Eigenen Kennzahl, Fotozahlen je Jahr."""
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
        for key, order in (("fotos", ["kopf", "raster", "jahre"]), ("karte", ["karte", "ka_jahr", "ka_sport"])):
            assert c.get(f"/api/layout/{key}").json()["layout"] is None
            doc = {"v": 1, "order": order, "hidden": [order[-1]], "closed": [], "w": {order[0]: "voll"}}
            assert c.put(f"/api/layout/{key}", json=doc).status_code == 200
            got = c.get(f"/api/layout/{key}").json()
            assert got["layout"]["order"] == order and got["layout"]["hidden"] == [order[-1]]
            assert c.delete(f"/api/layout/{key}").status_code == 200
            assert c.get(f"/api/layout/{key}").json()["layout"] is None


def test_new_blocks_are_accepted_with_strict_config():
    with _client() as c:
        ok = {"widgets": [_w("f1", "fkennzahl", {"values": ["jahre", "fotos"], "title": "Zahlen"}), _w("f2", "fjahre", {"n": 12})]}
        assert c.put("/api/layout/fotos", json=ok).status_code == 200
        w = c.get("/api/layout/fotos").json()["layout"]["widgets"]
        assert [x["type"] for x in w] == ["fkennzahl", "fjahre"] and w[0]["cfg"]["values"] == ["fotos", "jahre"]        # kanonische Reihenfolge
        ok2 = {"widgets": [_w("k1", "kzahlen", {"values": ["touren", "km"], "basis": "ausschnitt"}), _w("k2", "kliste", {"sort": "km", "n": 20}), _w("k3", "klegende", {"metric": "km"})]}
        assert c.put("/api/layout/karte", json=ok2).status_code == 200
        assert [x["type"] for x in c.get("/api/layout/karte").json()["layout"]["widgets"]] == ["kzahlen", "kliste", "klegende"]


def test_bad_config_is_rejected():
    bad = [("fotos", _w("a1", "fkennzahl", {"values": []})), ("fotos", _w("a1", "fkennzahl", {"values": ["km"]})), ("fotos", _w("a1", "fkennzahl", {"values": "fotos"})),
           ("fotos", _w("a1", "fkennzahl", {"sports": ["hike"]})), ("fotos", _w("a1", "fjahre", {"n": 7})), ("fotos", _w("a1", "fjahre", {"n": "8"})), ("fotos", _w("a1", "fjahre", {"n": True})),
           ("fotos", _w("a1", "fjahre", {"fremd": 1})),
           ("karte", _w("a1", "kzahlen", {"values": ["x"]})), ("karte", _w("a1", "kzahlen", {"basis": "alle"})), ("karte", _w("a1", "kliste", {"sort": "name"})),
           ("karte", _w("a1", "kliste", {"n": 3})), ("karte", _w("a1", "klegende", {"metric": "up"})), ("karte", _w("a1", "klegende", {"range": "y"}))]
    with _client() as c:
        for key, w in bad:
            r = c.put(f"/api/layout/{key}", json={"widgets": [w]})
            assert r.status_code == 400, (key, w, r.status_code)
        assert c.get("/api/layout/fotos").json()["layout"] is None and c.get("/api/layout/karte").json()["layout"] is None


def test_blocks_stay_on_their_own_pages():
    with _client() as c:
        for key, typ in (("fotos", "kzahlen"), ("fotos", "kliste"), ("karte", "fkennzahl"), ("karte", "fjahre"), ("fotos", "rkennzahl"), ("karte", "rnzahlen"),
                         ("uebersicht", "fkennzahl"), ("statistik", "kzahlen"), ("tour-haupt", "klegende"), ("reise", "fjahre"), ("reisen", "kliste")):
            assert c.put(f"/api/layout/{key}", json={"widgets": [_w("x1", typ)]}).status_code == 400, (key, typ)
        for key in ("fotos", "karte"):
            for typ in ("kennzahlen", "erinn", "eigenkz", "stentwicklung", "bewegung"):
                assert c.put(f"/api/layout/{key}", json={"widgets": [_w("x1", typ)]}).status_code == 400, (key, typ)


def test_rules_exist_only_for_the_tour_page_and_export_check():
    box = {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1}}], "active": "standard", "rules": [{"id": "r1", "view": "standard", "when": {}}]}
    with _client() as c:
        for key in ("fotos", "karte"):
            assert c.put(f"/api/layout/{key}", json=box).status_code == 400
            ok = {k: v for k, v in box.items() if k != "rules"}
            assert c.put(f"/api/layout/{key}", json=ok).status_code == 200
        for page, key, typ in (("fotos", "fotos", "fjahre"), ("karte", "karte", "klegende")):
            doc = {"format": "meine-touren-ansicht", "format_version": 1, "app_version": "3.34.0", "page": page, "name": "Meine", "layouts": {key: {"widgets": [_w("w1", typ)]}}}
            r = c.post("/api/layout/check", json=doc).json()
            assert r["ok"] and r["page"] == page and r["layouts"][key]["widgets"][0]["type"] == typ, r
        bad = {"format": "meine-touren-ansicht", "format_version": 1, "page": "fotos", "name": "X", "layouts": {"fotos": {"widgets": [_w("w1", "kzahlen")]}}}
        assert c.post("/api/layout/check", json=bad).json()["ok"] is False


def test_viewer_sees_default_and_cannot_write():
    with _client() as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        assert c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"}).status_code == 200
        assert c.put("/api/layout/karte", json={"v": 1, "order": ["karte", "ka_jahr"]}).status_code == 200
        v = _client()
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        for key in ("fotos", "karte"):
            assert v.get(f"/api/layout/{key}").json()["default"] is True
            assert v.put(f"/api/layout/{key}", json={"v": 1, "order": ["karte"]}).status_code == 403
            assert v.delete(f"/api/layout/{key}").status_code == 403
        assert c.get("/api/layout/karte").json()["layout"]["order"] == ["karte", "ka_jahr"]


def test_period_override_flag_of_blocks():
    """3.34.0: „eigen“ (true = eigener Zeitraum statt Zeitraum der Seite) ist ein bool-Feld der Bausteine der Übersicht und der Eigenen Kennzahl."""
    with _client() as c:
        ok = {"widgets": [_w("j1", "jahr", {"range": "12m", "eigen": True}), _w("j2", "rekorde", {"range": "all"})]}
        assert c.put("/api/layout/uebersicht", json=ok).status_code == 200
        w = c.get("/api/layout/uebersicht").json()["layout"]["widgets"]
        assert w[0]["cfg"].get("eigen") is True
        for v in ("ja", 1, None, [True]):
            assert c.put("/api/layout/uebersicht", json={"widgets": [_w("j1", "jahr", {"eigen": v})]}).status_code == 400, v
        kz = {"title": "Meine", "symbol": "hike", "mess": "km", "agg": "sum", "range": "y", "yr": 2025, "eigen": True}
        r = c.post("/api/bausteine/eigen", json=kz)
        assert r.status_code == 200, r.text
        assert c.post("/api/bausteine/eigen", json={**kz, "eigen": "x"}).status_code == 400


def test_photo_info_has_year_counts():
    with _client() as c:
        r = c.get("/api/photo-info").json()
        assert r["year_counts"] == {} and r["count"] == 0
        assert "year_counts" in r


def test_version_notes_and_assets():
    from app import config
    assert config.VERSION.startswith("3.61.0 · Meine Touren")
    notes = (ROOT / "docs" / "versionen" / "3.34.0.md").read_text(encoding="utf-8")
    assert "Fotos-Seite" in notes and "Zeitraum der Seite" in notes and "Live-Vorschau" in notes and "Alben" in notes
    assert 'const V = "mt-v147"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    js = ROOT / "app" / "static" / "js"
    assert 'SL_APPV = "3.61.0"' in (js / "54-ansichten.js").read_text(encoding="utf-8")
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("62-reiseseiten.js") < html.index("63-fotoseiten.js") < html.index("64-kartenseite.js") < html.index("65-zeitraum.js")
    hist = (ROOT / "docs" / "VERSIONSVERLAUF.md").read_text(encoding="utf-8")
    assert hist.index("## Version 3.34.0") < hist.index("## Version 3.33.0")
    assert "3.34.0.md" in (ROOT / "docs" / "versionen" / "README.md").read_text(encoding="utf-8")
