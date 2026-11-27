"""3.62.2 – „Neu mischen“ im Foto-Baustein der Reise wirkt: Zufällig zieht neue Fotos (nicht dieselben aus dem Tab-Gedächtnis), Alle/Beste/Neueste mischen die Reihenfolge sichtbar anders
(nie dieselbe Reihenfolge wie vorher), Raster, Streifen und Einzelbild-Show werden wirklich neu gezeichnet. Wiederholt geklickt, damit der Zufall keinen Fehler vortäuscht."""
import pytest

from tests.test_core import fresh  # noqa: F401
from tests.test_seitenlayout_ui import T, _api, pw  # noqa: F401
from tests.test_reise_seiten_ui import TL, _trip, app, clean  # noqa: F401

CLICKS = 4
MARK = "(s) => { const c = document.querySelector(s + ' .erb').firstElementChild; c._alt = 1; }"
FRESH = "(s) => { const c = document.querySelector(s + ' .erb').firstElementChild; return !!c && !c._alt; }"
GRID = "(s) => [...document.querySelectorAll(s + ' .erf img')].map(i => i.getAttribute('src'))"
# Einzelbild-Show: anhalten, dann alle Bilder der Reihe nach durchblättern und die Quellen sammeln (Bilder werden erst beim Blättern geladen)
SHOW = """(s) => { const r = document.querySelector(s + ' .erp'), pp = r.querySelector('.erpp'), out = [];
  if (pp.getAttribute('aria-pressed') === 'false') pp.click();
  const n = r.querySelectorAll('.erpv img').length;
  for (let k = 0; k < n; k++) { out.push(r.querySelector('.erpv img.on').getAttribute('src')); r.querySelector('.ernext').click(); }
  return out; }"""


def _setup(pw, app, mode, view, n):
    _api(app, "reise", "PUT", {"widgets": [{"id": "wd1", "type": "rdiashow", "cfg": {"mode": mode, "view": view, "n": n, "shuffle": True}}]})
    pg = _trip(pw, app)
    what = ".erpv img" if view == "show" else ".erb img"
    pg.wait_for_function("([w, n]) => document.querySelectorAll('#tlw-wd1 ' + w).length === n", arg=[what, n if mode != "all" else 6], timeout=TL)
    return pg


@pytest.mark.parametrize("mode,view,n", [("random", "grid", 3), ("random", "show", 3), ("best", "grid", 6), ("recent", "strip", 6), ("all", "grid", 6), ("all", "show", 6), ("recent", "show", 6)])
def test_neu_mischen_aendert_auswahl_oder_reihenfolge(pw, app, mode, view, n):
    pg = _setup(pw, app, mode, view, n)
    try:
        sel = "#tlw-wd1"
        read = SHOW if view == "show" else GRID
        n_all = 6 if mode == "all" else n
        cur = pg.evaluate(read, sel)
        assert len(cur) == n_all, cur
        for _ in range(CLICKS):
            pg.evaluate(MARK, sel)
            pg.click(sel + " .ernew")
            pg.wait_for_function(FRESH, arg=sel, timeout=T)                                       # Anzeige wirklich neu gezeichnet (auch bei Auswahl „Zufällig“ mit gemerkter Liste)
            pg.wait_for_function("(s) => document.querySelectorAll(s + ' .erb img').length > 0", arg=sel, timeout=T)
            new = pg.evaluate(read, sel)
            assert len(new) == n_all
            assert new != cur, (mode, view, cur)                                                  # Auswahl bzw. Reihenfolge sichtbar anders
            if mode != "random":
                assert sorted(new) == sorted(cur)                                                 # gleiche Fotos, nur gemischt
            cur = new
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_abschnitt_fotos_alle_mit_neu_mischen(pw, app):
    """Der feste Abschnitt „Fotos“ (Vorgabe Alle) mit Knopf „Neu mischen“: Reihenfolge wechselt."""
    _api(app, "reise", "PUT", {"cfg": {"fotos": {"mode": "all", "shuffle": True}}})
    pg = _trip(pw, app)
    try:
        pg.wait_for_function("() => document.querySelectorAll('#tls-fotos .erb img').length === 6", timeout=TL)
        a = pg.evaluate(GRID, "#tls-fotos")
        pg.click("#tls-fotos .ernew")
        pg.wait_for_function("([s, a]) => [...document.querySelectorAll(s + ' .erf img')].map(i => i.getAttribute('src')).join() !== a.join()", arg=["#tls-fotos", a], timeout=T)
        assert sorted(pg.evaluate(GRID, "#tls-fotos")) == sorted(a)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
