"""3.20.0 – Raster und seitenübergreifende Bausteine, Backend: Breite im Layout-Dokument, Seiteneignung, Registry, Version und Hinweise."""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "app" / "static" / "js"


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def test_width_field_is_validated_and_saved():
    with _client() as c:
        doc = {"order": ["map"], "w": {"map": "halb", "wk1": "drittel", "ana": "zweidrittel", "prof": "voll"}}
        r = c.put("/api/layout/tour-haupt", json=doc)
        assert r.status_code == 200, r.text
        assert c.get("/api/layout/tour-haupt").json()["layout"]["w"] == doc["w"]
        bad = [{"w": []}, {"w": "halb"}, {"w": {"map": "dreiviertel"}}, {"w": {"map": 6}}, {"w": {"map": None}}, {"w": {"a b": "halb"}}, {"w": {"x%d" % i: "halb" for i in range(121)}}]
        for b in bad:
            assert c.put("/api/layout/tour-haupt", json=b).status_code == 400, b
        assert c.get("/api/layout/tour-haupt").json()["layout"]["w"] == doc["w"]          # abgelehnte Dokumente ändern nichts
        assert c.put("/api/layout/uebersicht", json={"w": {"jahr": "halb"}}).status_code == 200


def test_tour_widgets_are_refused_in_the_overview_but_overview_widgets_may_be_on_the_tour_page():
    from app import layout
    with _client() as c:
        for t in sorted(layout.TOUR_ONLY):
            assert c.put("/api/layout/uebersicht", json={"widgets": [{"id": "w1", "type": t}]}).status_code == 400, t
            assert c.put("/api/layout/tour-haupt", json={"widgets": [{"id": "w1", "type": t}]}).status_code == 200, t
        for t in ("jahr", "periode", "heatmap", "rekorde", "serie", "auffaellig"):
            assert c.put("/api/layout/uebersicht", json={"widgets": [{"id": "w1", "type": t}]}).status_code == 200, t
            assert c.put("/api/layout/tour-haupt", json={"widgets": [{"id": "w1", "type": t, "cfg": {"title": "Jahr"}}]}).status_code == 200, t
        assert c.put("/api/layout/uebersicht", json={"widgets": [{"id": "w1", "type": "neuer_typ_einer_neueren_version"}]}).status_code == 200


def test_server_list_matches_the_registry_in_the_scripts():
    """TOUR_ONLY (Python) = alle Typen mit fam „tour“ in 50/51; jeder Typ hat in 52 Breite und Eignung."""
    from app import layout
    src = "".join((JS / f).read_text(encoding="utf-8") for f in ("50-bausteine.js", "51-bausteine-tour.js", "52-bausteine-uebersicht.js"))
    types = dict(re.findall(r'^  (\w+): \{\n    fam: "(\w+)"', src, re.M))
    assert len(types) >= 40, types
    assert {k for k, f in types.items() if f == "tour"} == set(layout.TOUR_ONLY)
    meta = re.search(r"const META = \{(.*?)\n  \};", src, re.S).group(1)
    widths = dict(re.findall(r'(\w+): "(voll|zweidrittel|halb|drittel)"', meta))
    assert set(widths) == set(types), set(types) ^ set(widths)
    assert all(widths[k] in ("voll", "halb", "drittel") for k in widths)
    assert widths["heatmap"] == "voll" and widths["rueckblick"] == "voll" and widths["kennzahlen"] == "halb"


def test_version_notes_and_service_worker():
    from app import config
    assert config.VERSION.startswith("3.61.1 · Meine Touren")
    notes = (ROOT / "docs" / "versionen" / "3.20.0.md").read_text(encoding="utf-8")
    assert "Raster" in notes and "Breite" in notes and "Tourseite" in notes
    assert 'const V = "mt-v147"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    css = (ROOT / "app" / "static" / "style.css").read_text(encoding="utf-8")
    assert "grid-auto-flow" not in css.split("3.20.0: Raster")[-1] and ".w-halb" in css            # kein grid-auto-flow: dense (Tab-Reihenfolge = sichtbare Reihenfolge)
