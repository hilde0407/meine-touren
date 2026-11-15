"""Karten dürfen nicht direkt bei OpenStreetMap laden (ohne Herkunftsangabe sperrt OSM: „Access blocked“)."""
from pathlib import Path

JS = Path(__file__).resolve().parent.parent / "app" / "static" / "js"


def test_trackfix_karte_ueber_servercache():
    s = (JS / "14-trackfix.js").read_text(encoding="utf-8")
    assert "L.tileLayer(" not in s
    assert 'tileL("osm"' in s


def test_kachelausweichen_sendet_herkunft():
    s = (JS / "01-grundlagen.js").read_text(encoding="utf-8")
    assert "referrerPolicy" in s


def test_flug_3d_laedt_osm_und_topo_nur_ueber_den_servercache():
    """3.24.0: kein Direktabruf bei OpenStreetMap/OpenTopoMap im 3D-Flug (ohne Herkunftsangabe: „Access blocked“); alle drei Stile über /tiles/."""
    s = (JS / "07-flug.js").read_text(encoding="utf8")
    assert "tile.openstreetmap.org" not in s and "tile.opentopomap.org" not in s
    assert 'tp = k => TBASE + `tiles/${k}/{z}/{x}/{y}`' in s
    for k in ("osm", "topo", "sat"):
        assert f'ras([tp("{k}")]' in s
    assert "maplibregl" in s and "L.tileLayer(" not in s
