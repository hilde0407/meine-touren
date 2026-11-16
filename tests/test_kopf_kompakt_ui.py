"""3.29.0 – Kopf der Bausteine im Bearbeitungsmodus bei halber/drittel Breite und auf dem Handy: höchstens zwei Zeilen (vorher drei bis vier), Symbolknöpfe, alle Bedienelemente mindestens 32 px,
kein Überlauf, Menü „⋯“ bei schmalen Bausteinen, hell und dunkel. Wettlauf-Regel: auf den Zustand warten, nie nur schlafen. Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import pytest

from tests.test_statistik_ui import _api, _edit, _shot, _stats, app, clean, pw, T  # noqa: F401
from tests.test_tourseite_ui import _settled

expect = pytest.importorskip("playwright.sync_api").expect

WIDGETS = [{"id": "wa", "type": "stmonate", "cfg": {}}, {"id": "wb", "type": "sttop", "cfg": {}}, {"id": "wc", "type": "stlaengen", "cfg": {}}]
MEASURE = """() => [...document.querySelectorAll('.slit[data-sl^=w]')].map(w => {
  const s = w.querySelector('.slst'), r = s.getBoundingClientRect(), out = {id: w.dataset.sl, w: Math.round(w.getBoundingClientRect().width), head: Math.round(r.height), small: [], over: s.scrollWidth > s.clientWidth + 1};
  s.querySelectorAll('button, label.slsw').forEach(e => { const b = e.getBoundingClientRect(); if (b.width && b.height && (b.width < 32 || b.height < 32)) out.small.push(e.dataset.a || e.className); });
  return out; })"""


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width,breite", [(1280, "halb"), (1280, "drittel"), (390, "halb")])
def test_kopf_ist_kompakt_und_bedienbar(pw, app, scheme, width, breite):
    _api(app, "statistik", "PUT", {"v": 1, "widgets": WIDGETS, "w": {w["id"]: breite for w in WIDGETS}})
    pg = _stats(pw, app, width=width, height=900, scheme=scheme, dpr=2 if width == 390 else 1)
    try:
        _edit(pg)
        pg.wait_for_function("() => document.querySelectorAll('.slit[data-sl^=w] .slst').length === 3", timeout=T)
        _settled(pg)
        m = pg.evaluate(MEASURE)
        assert len(m) == 3, m
        for x in m:
            assert x["head"] <= 100, x                                         # vorher 136 bis 144 px
            assert not x["small"] and not x["over"], x
        assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
        # Ausblenden/Einblenden: Symbolknopf mit Namen und Hinweistext
        eye = pg.locator('.slit[data-sl="wa"] [data-a=eye]')
        assert eye.get_attribute("title") == "Ausblenden" and eye.get_attribute("aria-pressed") == "false"
        assert eye.evaluate("e => { const t = e.querySelector('span'); return !t || t.getBoundingClientRect().width <= 1; }")          # nur Symbol, der Name bleibt für Sprachausgabe
        _shot(pg, f"kopf-{width}-{breite}-{scheme}.png", full=False)
        eye.click()
        expect(eye).to_have_attribute("aria-pressed", "true", timeout=T)
        expect(pg.locator('.slit[data-sl="wa"] .slhid')).to_be_visible(timeout=T)
        eye.click()
        expect(eye).to_have_attribute("aria-pressed", "false", timeout=T)
        # Breite umschalten bleibt bedienbar
        pg.locator('.slit[data-sl="wb"] [data-a=w][data-w="voll"]').click()
        pg.wait_for_selector('.slit[data-sl="wb"].w-voll', timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_schmal_menue_mit_einstellungen_und_name_zweizeilig(pw, app):
    _api(app, "statistik", "PUT", {"v": 1, "widgets": WIDGETS, "w": {w["id"]: "drittel" for w in WIDGETS}})
    pg = _stats(pw, app, width=1280, height=900)
    try:
        _edit(pg)
        pg.wait_for_selector('.slit[data-sl="wa"] .slst', timeout=T)
        w = pg.evaluate("() => document.querySelector('.slit[data-sl=wa]').getBoundingClientRect().width")
        assert w < 480
        cfg, more = pg.locator('.slit[data-sl="wa"] [data-a=cfg]'), pg.locator('.slit[data-sl="wa"] [data-a=more]')
        expect(more).to_be_visible(timeout=T)
        assert not cfg.is_visible()
        more.click()
        expect(cfg).to_be_visible(timeout=T)
        assert pg.evaluate("() => { const e = document.querySelector('.slit[data-sl=wa] .slnm'); return getComputedStyle(e).webkitLineClamp === '2' && e.title.length > 0; }")
        cfg.click()
        pg.wait_for_selector(".slbox", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
