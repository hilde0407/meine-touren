"""Stil-Regeln: feste Schriftgrößen-Skala, kaum Inline-Stile, Hilfsklassen sind definiert."""
import re
from pathlib import Path

ST = Path(__file__).resolve().parent.parent / "app" / "static"
SCALE = {12, 13, 14, 15, 16, 18, 20, 22, 24, 26, 30, 34, 44}
JS = [f for f in sorted((ST / "js").glob("*.js")) if "i18n" not in f.name]


def _sizes(text):
    out = [float(x) for x in re.findall(r"font-size:\s*(\d+(?:\.\d+)?)px", text)]
    out += [float(m[1]) for m in re.findall(r"font:\s*((?:(?:italic|normal|bold|[1-9]00)\s+)*)(\d+(?:\.\d+)?)px", text)]
    return out


def test_font_sizes_on_scale():
    for f in [ST / "style.css"] + JS:
        bad = sorted({s for s in _sizes(f.read_text(encoding="utf-8")) if s not in SCALE})
        assert not bad, f"{f.name}: Schriftgrößen außerhalb der Skala: {bad}"


def test_inline_styles_stay_rare():
    """Statische Abstände/Schriftgrößen gehören in Klassen; inline bleiben nur berechnete oder per JS geschaltete Werte."""
    n = sum(len(re.findall(r'style="', f.read_text(encoding="utf-8"))) for f in JS)
    assert n <= 190, f"{n} Inline-Stile (Grenze 190) – bitte Hilfsklassen aus style.css verwenden"


def test_helper_classes_defined():
    css = (ST / "style.css").read_text(encoding="utf-8")
    defined = set(re.findall(r":where\(\.([\w-]+)\)", css))
    used = set()
    for f in JS:
        for m in re.finditer(r'class="([^"]*)"', f.read_text(encoding="utf-8")):
            used |= {t for t in re.split(r"[\s${}?:\"'`]+", m.group(1)) if re.fullmatch(r"(m[tblr]?|p[tblr]?|g|fs|mw|mnw|br)\d[\dn_-]*", t)}
    used -= {"g2", "g3", "g4"}                     # Rasterklassen (.grid.g2 …), keine Hilfsklassen
    assert used <= defined, f"nicht definierte Hilfsklassen: {sorted(used - defined)}"
