"""3.73.0 – Versionsstellen und Versionsnotizen."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_version_3730():
    from app import config
    assert config.VERSION.startswith("3.73.0 · Meine Touren")
    assert 'SL_APPV = "3.73.0"' in (ROOT / "app" / "static" / "js" / "54-ansichten.js").read_text(encoding="utf-8")
    assert 'const V = "mt-v165"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    notes = (ROOT / "docs" / "versionen" / "3.73.0.md").read_text(encoding="utf-8")
    assert notes.startswith("# 3.73.0") and "Komoot" in notes and "Ordner" in notes
    assert "3.73.0" in (ROOT / "docs" / "VERSIONSVERLAUF.md").read_text(encoding="utf-8")
    hb = (ROOT / "docs" / "HANDBUCH.md").read_text(encoding="utf-8")
    assert "Version 3.73.0" in hb and "Tournamen angleichen" in hb
    assert "3.73.0" in (ROOT / "docs" / "LEITFADEN-BEGRIFFE.md").read_text(encoding="utf-8")
