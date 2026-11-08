"""Konsistenz der Übersetzungstabelle (00-i18n-neu.js): vier Spalten, keine leeren Felder, gleiche Platzhalter."""
import re
from pathlib import Path

SRC = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "00-i18n-neu.js"


def _rows():
    txt = SRC.read_text(encoding="utf8")
    body = txt.split("window.I18N_NEU = `", 1)[1].rsplit("`", 1)[0]
    return [r for r in body.split("\n") if r.strip()]


def test_vier_spalten_und_platzhalter():
    bad = []
    for r in _rows():
        cols = [c.strip() for c in r.split(" || ")]
        if len(cols) != 4 or not all(cols):
            bad.append(("Spalten", r[:80]))
            continue
        key = cols[0].split(" @@ ")[-1] if " @@ " in cols[0] else cols[0]
        n = key.count("{}")
        if any(c.count("{}") != n for c in cols[1:]):
            bad.append(("Platzhalter", r[:80]))
    assert not bad, bad[:10]


def test_keine_doppelten_schluessel_mit_abweichung_im_tabellenende():
    seen = {}
    for r in _rows():
        k = r.split(" || ")[0].strip()
        seen[k] = r
    assert len(seen) > 400


def test_gone_page_sprachen():
    from app import more2

    class R:
        def __init__(self, a): self.headers = {"accept-language": a}
    for lang, word in (("de", "(mehr) gültig"), ("en", "no longer valid"), ("fr", "plus valable"), ("es", "ya no es válido")):
        r = more2.gone_page(None, R(lang))
        assert word in r.body.decode() and f'lang="{lang}"' in r.body.decode()
