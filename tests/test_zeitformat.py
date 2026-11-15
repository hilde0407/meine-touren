"""3.24.1 – Dauer in h:mm: zuerst auf ganze Minuten runden, dann teilen (nie „2:60“ oder „0:60“). Browser (Chromium) für die JS-Hilfen, Python für das PDF."""
import pytest

from app import pdfgen

CASES = [(10799, "3:00"), (3599, "1:00"), (3600, "1:00"), (0, "0:00"), (59.6 * 60, "1:00"), (3569, "0:59"), (3570, "1:00"), (9000, "2:30"), (7199, "2:00")]


@pytest.mark.parametrize("h,exp", [(s / 3600, e) for s, e in CASES])
def test_pdf_hm(h, exp):
    assert pdfgen._hm(h) == exp + " h"


def test_pdf_splits_round_seconds():
    import inspect
    src = inspect.getsource(pdfgen)
    assert "round(s) // 60" in src and "int(s % 60)" not in src


@pytest.fixture(scope="module")
def pw():
    pytest.importorskip("playwright.sync_api")
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


def _helpers(pw):
    """Die Hilfen aus 01-grundlagen.js ohne die ganze App laden."""
    import re
    from pathlib import Path
    src = (Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "01-grundlagen.js").read_text(encoding="utf-8")
    code = "const pad2 = n => String(n).padStart(2, '0');\n" + re.search(r"const hmParts = .*?\nconst fmtMS = .*?\n};\n", src, re.S).group(0)
    b = pw.chromium.launch()
    pg = b.new_page()
    pg.set_content("<html><body></body></html>")
    pg.evaluate("(c) => { window.__h = new Function(c + '; return {hmParts, fmtHM, fmtMS};')(); }", code)
    return b, pg


def test_js_fmt_hm_and_ms(pw):
    b, pg = _helpers(pw)
    try:
        for s, exp in CASES:
            assert pg.evaluate("s => window.__h.fmtHM(s)", s) == exp, s
        assert pg.evaluate("() => window.__h.hmParts(10799)") == [3, 0]
        assert pg.evaluate("() => window.__h.fmtMS(59.6)") == "1:00"            # Pace: 59,6 s → 1:00 statt 0:60
        assert pg.evaluate("() => window.__h.fmtMS(0)") == "0:00"
        assert pg.evaluate("() => window.__h.fmtMS(3599.6)") == "60:00"
        assert pg.evaluate("() => window.__h.fmtHM(NaN)") == "0:00"
    finally:
        b.close()


def test_no_old_pattern_left():
    """Kein Zerlegen mehr nach dem Muster Stunden = floor, Minuten = round(Rest) in den App-Skripten."""
    import re
    from pathlib import Path
    bad = []
    for f in sorted((Path(__file__).resolve().parent.parent / "app" / "static" / "js").glob("*.js")):
        if f.name.startswith("00-i18n"):
            continue
        t = f.read_text(encoding="utf-8")
        if re.search(r"Math\.round\(\(\w+ % 3600\) / 60\)|Math\.round\(\(\w+(\.\w+)? % 1\) \* 60\)", t):
            bad.append(f.name)
    assert not bad, bad
