"""3.70.1 – Gasteinertal gehört zum Pongau (nicht Pinzgau), neues Gebiet Großarltal (Eltern Pongau), Rauris bleibt Pinzgau. Nur Ortslagen (synthetische Punkte)."""
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_core import fresh  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
node = pytest.mark.skipif(not shutil.which("node"), reason="Node nicht installiert")


def _ids(la, ln, county=None):
    from app import gebiete
    return gebiete.von(la, ln, county, ())


def test_bad_hofgastein_pongau_nicht_pinzgau():
    for la, ln in [(47.17, 13.10), (47.18, 13.06), (47.11, 13.13), (47.27, 13.10)]:   # Bad Hofgastein, Heißingfelding, Bad Gastein, Dorfgastein
        i = _ids(la, ln)
        assert "gastein" in i and "pongau" in i and "pinzgau" not in i and "grossarltal" not in i, (la, ln, i)
    assert _ids(47.17, 13.10)[0] == "gastein"


def test_grossarltal():
    for la, ln in [(47.22, 13.20), (47.14, 13.20), (47.19, 13.20)]:   # Großarl, Hüttschlag, Rattersberg
        i = _ids(la, ln)
        assert i[0] == "grossarltal" and "pongau" in i and "gastein" not in i and "pinzgau" not in i, (la, ln, i)
    assert "grossarltal" not in _ids(47.24, 13.30)   # Kleinarl


def test_echte_pinzgau_orte_bleiben():
    for la, ln in [(47.22, 13.00), (47.27, 12.76), (47.32, 12.80), (47.28, 12.48), (47.22, 12.18), (47.40, 12.90), (47.39, 12.64), (47.25, 13.07)]:   # Rauris, Kaprun, Zell, Mittersill, Krimml, Maria Alm, Saalbach, Lend
        i = _ids(la, ln)
        assert "pinzgau" in i and "gastein" not in i and "grossarltal" not in i, (la, ln, i)


@node
def test_json_aktuell():
    neu = subprocess.run(["node", str(ROOT / "scripts" / "gebiete_json.js"), "--stdout"], capture_output=True, text=True, check=True).stdout
    assert (ROOT / "app" / "gebiete.json").read_text(encoding="utf-8") == neu


def test_version_3701():
    from app import config
    assert config.VERSION.startswith("3.73.0 · Meine Touren")
    assert 'SL_APPV = "3.73.0"' in (ROOT / "app" / "static" / "js" / "54-ansichten.js").read_text(encoding="utf-8")
    assert 'const V = "mt-v164"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
