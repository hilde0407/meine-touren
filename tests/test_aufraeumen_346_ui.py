"""3.46.0 – „Seite anpassen“/„Ansichten“ (#slopenw) schließt auf dem Desktop bündig mit der Inhaltsspalte ab (nicht am Fensterrand), bei 1280 und 1512 px."""
import json

import pytest

from tests.test_freigabe_ansicht_ui import T, _get, _page, app, pw  # noqa: F401

pytest.importorskip("playwright.sync_api")

SEITEN = ["#/dash", "#/tour/r3", "#/stats", "#/trips", "#/photos", "#/tour/r3/auswertung", "#/map", "TRIP"]

MESS = """() => {
  const w = document.getElementById('slopenw'), m = w.parentElement;
  const r = w.getBoundingClientRect(), inn = document.querySelector('main .inner');
  let spalte;
  if (inn) { const ir = inn.getBoundingClientRect(), cs = getComputedStyle(inn); spalte = ir.right - parseFloat(cs.paddingRight); }
  else { const mr = m.getBoundingClientRect(), cs = getComputedStyle(m); spalte = mr.right - parseFloat(cs.paddingRight); }
  const ks = [...w.children].filter(c => c.getBoundingClientRect().width > 0);
  return {rechts: ks.length ? Math.max(...ks.map(c => c.getBoundingClientRect().right)) : r.right, spalte, main: m.tagName + '.' + m.className};
}"""


@pytest.mark.parametrize("breite", [1280, 1512])
@pytest.mark.parametrize("seite", [x for x in SEITEN if x != "#/map"])
def test_leiste_buendig(pw, app, seite, breite):
    if seite == "TRIP":
        t = _get(app, "/api/trips")
        if not t:
            pytest.skip("keine Reise")
        seite = "#/trip/" + str(t[0]["id"])
    pg = _page(pw, app, width=breite)
    try:
        pg.goto(f"{app}/{seite}")
        pg.wait_for_function("() => !!document.getElementById('slopenw')", timeout=T)
        pg.wait_for_function("() => document.getElementById('slopenw').getBoundingClientRect().width > 0", timeout=T)
        m = pg.evaluate(MESS)
        assert abs(m["rechts"] - m["spalte"]) <= 1, (seite, breite, m)
    finally:
        pg.browser_.close()
