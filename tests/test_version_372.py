"""3.72.0 – Versionsstellen (Version, Cache, Ansichtsformat) und Versionsnotizen."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_version_3720():
    from app import config
    assert config.VERSION.startswith("3.74.0 · Meine Touren")
    assert 'SL_APPV = "3.74.0"' in (ROOT / "app" / "static" / "js" / "54-ansichten.js").read_text(encoding="utf-8")
    assert 'const V = "mt-v166"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    notes = (ROOT / "docs" / "versionen" / "3.72.0.md").read_text(encoding="utf-8")
    assert notes.startswith("# 3.72.0") and "N-05" in notes and "N-07" in notes and "M-10" in notes
    assert "3.72.0" in (ROOT / "docs" / "VERSIONSVERLAUF.md").read_text(encoding="utf-8")
    assert "Version 3.74.0" in (ROOT / "docs" / "HANDBUCH.md").read_text(encoding="utf-8")
