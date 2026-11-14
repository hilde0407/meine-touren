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
