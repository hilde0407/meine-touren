"""3.72.0 – Großarl (13.168 E) liegt im Großarltal, nicht im Gasteinertal; neue Gebiete Rheingau, Nahetal, Soonwald, Hochwald, Mullerthal; Nordvogesen reicht bis 49.10 N. Nur Ortslagen (synthetische Punkte)."""
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


def test_grossarl_ist_grossarltal():
    i = _ids(47.2286, 13.1684)
    assert i[0] == "grossarltal" and "pongau" in i and "gastein" not in i, i


def test_gastein_orte_bleiben():
    for la, ln in [(47.17, 13.10), (47.27, 13.12), (47.13, 13.14), (47.18, 13.06), (47.11, 13.13)]:   # Bad Hofgastein, Dorfgastein, Klammstein, Heißingfelding, Bad Gastein
        i = _ids(la, ln)
        assert "gastein" in i and "pongau" in i and "pinzgau" not in i and "grossarltal" not in i, (la, ln, i)


def test_neue_gebiete_ortslagen():
    soll = {"rheingau": [(50.00, 8.00), (50.04, 8.10), (50.02, 8.08), (50.04, 8.12), (50.07, 8.19), (50.08, 8.24)],
            "nahetal": [(49.85, 7.87), (49.80, 7.80), (49.82, 7.83)],
            "soonwald": [(49.94, 7.77), (49.90, 7.72)],
            "hochwald": [(49.51, 6.75), (49.53, 6.80)],
            "mullerthal": [(49.71, 6.47), (49.73, 6.43), (49.81, 6.42)],
            "vogesen": [(49.05, 7.62)]}
    for gid, pts in soll.items():
        for la, ln in pts:
            assert gid in _ids(la, ln), (gid, la, ln, _ids(la, ln))
    assert "hunsrueck" in _ids(49.51, 6.75) and "hunsrueck" in _ids(49.94, 7.77)   # Hochwald und Soonwald gehören zum Hunsrück


def test_bestehende_zuordnung_bleibt():
    """Taunus, Mittelrheintal, Rheinhessen behalten ihre Punkte; der neue Rheingau ergänzt nur."""
    for gid, la, ln in [("taunus", 50.20, 8.45), ("taunus", 50.15, 8.30), ("mittelrhein", 50.15, 7.70), ("mittelrhein", 50.00, 7.78), ("rheinhessen", 49.80, 8.10), ("moseltal", 49.75, 6.65)]:
        assert gid in _ids(la, ln), (gid, la, ln)
    for la, ln in [(50.00, 8.00), (50.04, 8.10)]:
        assert "rheingau" in _ids(la, ln)


def test_neue_gebiete_nicht_zu_weit():
    for gid, la, ln in [("rheingau", 49.99, 8.27), ("rheingau", 50.22, 8.27), ("mullerthal", 49.61, 6.13), ("hochwald", 49.75, 6.64), ("nahetal", 49.97, 8.20)]:
        assert gid not in _ids(la, ln), (gid, la, ln)


@node
def test_json_aktuell():
    neu = subprocess.run(["node", str(ROOT / "scripts" / "gebiete_json.js"), "--stdout"], capture_output=True, text=True, check=True).stdout
    assert (ROOT / "app" / "gebiete.json").read_text(encoding="utf-8") == neu
