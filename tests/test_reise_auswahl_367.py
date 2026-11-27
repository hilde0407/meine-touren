"""3.67.0 – Reise erstellen: Versionsstellen, Dokumentation und Quelltext-Prüfungen (ohne Browser)."""
from pathlib import Path

from app import config

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "app" / "static" / "js"


def test_version_und_doku():
    assert config.VERSION.startswith("3.68.0 · Meine Touren")
    assert 'const V = "mt-v158"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    assert 'SL_APPV = "3.68.0"' in (JS / "54-ansichten.js").read_text(encoding="utf-8")
    assert (ROOT / "docs" / "versionen" / "3.67.0.md").exists()
    assert "3.67.0" in (ROOT / "docs" / "VERSIONSVERLAUF.md").read_text(encoding="utf-8")
    assert "3.67.0" in (ROOT / "docs" / "versionen" / "README.md").read_text(encoding="utf-8")
    hb = (ROOT / "docs" / "HANDBUCH.md").read_text(encoding="utf-8")
    assert "Zeitraum markieren" in hb and "in Reise X" in hb and "Es ist nichts vorgewählt" in hb


def test_keine_automatische_vorauswahl_im_dialog():
    src = (JS / "28-reisen.js").read_text(encoding="utf-8")
    dlg = src[src.index("async function tripDialog"):src.index("/* Entfernte Reisen wiederherstellen")]
    assert "const take" not in dlg and "flDayAdd" not in dlg                       # keine Vorauswahl aus dem Zeitraum mehr
    assert 'querySelectorAll("input[type=date]").forEach' not in dlg              # Datumsfelder lösen keine Auswahl aus
    assert 'id="tcz"' in dlg and "tcz\").onclick" in dlg.replace("'", '"')
