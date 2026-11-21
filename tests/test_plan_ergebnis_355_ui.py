"""3.55.0 Tourseite, Baustein „Plan und Ergebnis“: Karte mit beiden Strecken (Plan gestrichelt in Indigo, gelaufen durchgezogen in der Sportfarbe, Start/Ziel, Ansicht passt auf beide),
Spalten „Geplant“ / „Gelaufen“ mit Farbmarkierung wie in Karte und Legende, Abstieg dazu, Knöpfe „Zum Plan“ und „Verknüpfung lösen“ gleich hoch mit Text auf einer Höhe;
hell/dunkel, 390 px und Desktop, en/fr/es. In der Testumgebung gibt es keine Kacheln – die Linien liegen trotzdem in der Karte. Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.helpers_ui import T, settled, toggle_details  # noqa: E402
from tests.test_seitenlayout_ui import _browser, pw  # noqa: E402,F401
from tests.test_reise_seiten_ui import app  # noqa: E402,F401
from tests.test_tourseite_ui import _shot  # noqa: E402
from tests.test_plan_ergebnis_339_ui import CARD, _plan, _tour, clean  # noqa: E402,F401

GEO = """() => {
  const c = document.querySelector('#tlw-planist'), q = s => c.querySelector(s), R = e => e.getBoundingClientRect(), cs = e => getComputedStyle(e);
  const m = R(q('.pemap')), pl = R(q('.pemap path.pepl')), is = R(q('.pemap path.peis'));
  const btn = [...c.querySelectorAll('.pebtns .btn')].map(b => { const r = R(b), g = document.createRange(); g.selectNodeContents(b); const t = g.getBoundingClientRect();
    return {cls: b.className, top: r.top, h: r.height, w: r.width, mid: (r.top + r.bottom) / 2, tmid: (t.top + t.bottom) / 2, tb: t.bottom, th: t.height, fs: cs(b).fontSize, fw: cs(b).fontWeight, lh: cs(b).lineHeight}; });
  return {
    map: [m.left, m.top, m.right, m.bottom], pl: [pl.left, pl.top, pl.right, pl.bottom, pl.width, pl.height], is: [is.left, is.top, is.right, is.bottom, is.width, is.height],
    dPl: q('.pemap path.pepl').getAttribute('d').length, dIs: q('.pemap path.peis').getAttribute('d').length,
    dash: q('.pemap path.pepl').getAttribute('stroke-dasharray'), dashIs: q('.pemap path.peis').getAttribute('stroke-dasharray'),
    strokePl: cs(q('.pemap path.pepl')).stroke, strokeIs: cs(q('.pemap path.peis')).stroke,
    swPl: cs(q('.peleg .pesw-pl')).stroke, swIs: cs(q('.peleg .pesw-is')).stroke, tagPl: cs(q('.pe-plan .pesw-pl')).stroke, tagIs: cs(q('.pe-ist .pesw-is')).stroke,
    edgePl: cs(q('.pe-plan')).borderLeftColor, edgeIs: cs(q('.pe-ist')).borderLeftColor,
    colPl: [R(q('.pe-plan')).top, R(q('.pe-plan')).bottom, R(q('.pe-plan')).left], colIs: [R(q('.pe-ist')).top, R(q('.pe-ist')).bottom, R(q('.pe-ist')).left],
    start: !!q('.pemap path.pestart'), ziel: !!q('.pemap path.peziel'), btn,
    over: Math.max(0, document.documentElement.scrollWidth - document.documentElement.clientWidth),
  };
}"""


def _open(pw, app, **kw):
    pid = _plan(app, "h0", km=8.0, up=150, est_h=3.0)
    pg = _tour(pw, app, **kw)
    c = pg.locator(CARD)
    expect(c.locator(".pemap path.pepl")).to_have_count(1, timeout=T)
    expect(c.locator(".pemap path.peis")).to_have_count(1, timeout=T)
    c.scroll_into_view_if_needed()
    settled(pg)
    return pg, c, pid


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("width,height", [(390, 844), (1280, 900)])
def test_karte_spalten_knoepfe(pw, app, scheme, width, height):
    pg, c, pid = _open(pw, app, width=width, height=height, scheme=scheme)
    try:
        g = pg.evaluate(GEO)
        # Karte: beide Linien vorhanden (auch ohne Kacheln), Plan gestrichelt, gelaufen durchgezogen, Start und Ziel; die Ansicht passt auf beide Strecken
        assert g["dPl"] > 20 and g["dIs"] > 20 and g["dash"] and g["dashIs"] in (None, "", "none"), g
        assert g["start"] and g["ziel"]
        for k in ("pl", "is"):
            L, Tp, Rt, B, W, H = g[k]
            assert W > 40 and H > 40, (k, g[k])
            assert L >= g["map"][0] - 1 and Rt <= g["map"][2] + 1 and Tp >= g["map"][1] - 1 and B <= g["map"][3] + 1, (k, g[k], g["map"])
        # gleiche Farben in Karte, Legende, Etikett und Randmarkierung der Spalte; Plan und gelaufen unterscheiden sich
        assert g["strokePl"] == g["swPl"] == g["tagPl"] == g["edgePl"], g
        assert g["strokeIs"] == g["swIs"] == g["tagIs"] == g["edgeIs"] == "rgb(47, 143, 95)", g          # Wandern: Sportfarbe --hike
        assert g["strokePl"] != g["strokeIs"]
        # Beschriftung der Spalten und Legende
        assert c.locator(".pe-plan .peh").text_content().strip() == "Geplant" and c.locator(".pe-ist .peh").text_content().strip() == "Gelaufen"
        assert c.locator(".pe-plan .pename a").get_attribute("href") == f"#/plan/{pid}" and "Rund um den See" in c.locator(".pe-plan .pename").inner_text()
        assert "Geplant am" in c.locator(".pe-plan .pedt").inner_text() and "Gelaufen am" in c.locator(".pe-ist .pedt").inner_text()
        assert c.locator(".pe-ist .pename").inner_text().strip()
        leg = [x.inner_text().strip() for x in c.locator(".peleg li").all()]
        assert leg == ["Geplant (gestrichelt)", "Gelaufen (durchgezogen)", "Start", "Ziel"], leg
        assert [x.inner_text() for x in c.locator(".pe-plan dt").all()] == ["Strecke", "Aufstieg", "Abstieg", "Dauer"]
        # Die Abweichung steht nur sichtbar beim gelaufenen Wert
        assert "länger als geplant" in c.locator(".pe-ist .pek-km").inner_text() and "länger" not in c.locator(".pe-plan .pek-km").inner_text()
        # Spalten: mobil untereinander, am Desktop nebeneinander
        if width < 600:
            assert g["colIs"][0] >= g["colPl"][1] - 1 and abs(g["colIs"][2] - g["colPl"][2]) < 1, g
        else:
            assert abs(g["colIs"][0] - g["colPl"][0]) < 1 and g["colIs"][2] > g["colPl"][2] + 100, g
        # Knöpfe: gleiche Klasse, Schrift, Höhe, Breite; Text vertikal mittig und auf derselben Grundlinie
        a, b = g["btn"]
        assert a["cls"] == b["cls"] and a["fs"] == b["fs"] and a["fw"] == b["fw"] and a["lh"] == b["lh"], g["btn"]
        assert abs(a["h"] - b["h"]) <= 0.5 and a["h"] >= 44 - 0.5 and abs(a["top"] - b["top"]) <= 0.5 and abs(a["w"] - b["w"]) <= 1, g["btn"]
        assert abs(a["tmid"] - b["tmid"]) <= 1 and abs(a["tb"] - b["tb"]) <= 1 and abs(a["th"] - b["th"]) <= 0.5, g["btn"]
        for x in (a, b):
            assert abs(x["tmid"] - x["mid"]) <= 1.5, x
        assert g["over"] == 0
        assert pg.evaluate("() => { const c = document.querySelector('#tlw-planist'); return c.scrollWidth <= c.clientWidth + 1; }")
        _shot(pg, f"tour-plan-ergebnis-355-{width}-{scheme}.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_karte_passt_nach_aufklappen(pw, app):
    """Ohne Breite gebaut (z. B. zugeklappt in Browsern, die den Inhalt ausblenden): sobald die Karte Platz hat, wird sie neu vermessen und auf beide Strecken eingepasst.
    Danach Ein- und Ausklappen per Klick: die Linien bleiben in der Karte."""
    pg, c, _ = _open(pw, app)
    try:
        pg.evaluate("() => { const c = document.querySelector('#tlw-planist'), b = c.querySelector('.pewrap').parentElement; b.hidden = true; return SL_WT.planergebnis.render(c, b, {}, {t: BY['h0']}); }")
        assert pg.evaluate("() => document.querySelector('#tlw-planist .pemap').clientWidth") == 0
        pg.evaluate("() => { document.querySelector('#tlw-planist .pewrap').parentElement.hidden = false; }")
        fit = "() => { const m = document.querySelector('#tlw-planist .pemap'), p = m && m.querySelector('path.pepl'); if (!p) return false; const a = m.getBoundingClientRect(), r = p.getBoundingClientRect(); return r.width > 40 && r.height > 40 && r.left >= a.left - 1 && r.right <= a.right + 1 && r.top >= a.top - 1 && r.bottom <= a.bottom + 1; }"
        pg.wait_for_function(fit, timeout=T)
        toggle_details(pg, CARD + " details.tls", False)
        toggle_details(pg, CARD + " details.tls", True)
        pg.wait_for_function(fit, timeout=T)
        assert pg.locator(CARD + " .pemap .leaflet-container, " + CARD + " .pemap.leaflet-container").count() == 1        # keine zweite Karte nach dem Neuaufbau
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


ERW = {
    "en": (["Planned", "Walked", "Planned on", "Walked on", "Descent", "Duration", "Planned (dashed)", "Walked (solid)", "To the plan", "Remove link", "longer than planned"], "en-GB"),
    "fr": (["Prévu", "Parcouru", "Prévu le", "Parcouru le", "Dénivelé négatif", "Durée", "Prévu (en pointillés)", "Parcouru (trait plein)", "Vers le plan", "Supprimer le lien", "plus long que prévu"], "fr-FR"),
    "es": (["Planificado", "Recorrido", "Planificado el", "Recorrido el", "Desnivel negativo", "Duración", "Planificado (discontinuo)", "Recorrido (continuo)", "Al plan", "Quitar el vínculo", "más largo de lo planificado"], "es-ES"),
}


@pytest.mark.parametrize("lang", sorted(ERW))
def test_sprachen(pw, app, lang):
    words, loc = ERW[lang]
    _plan(app, "h0", km=8.0, up=150, est_h=3.0)
    pg = _browser(pw, app, devs=None, locale=loc)
    pg.context.add_init_script(f"try {{ localStorage.setItem('lang', '{lang}'); }} catch (e) {{}}")
    pg.goto(f"{app}/#/tour/h0")
    try:
        c = pg.locator(CARD)
        expect(c.locator(".pemap path.pepl")).to_have_count(1, timeout=30000)
        expect(c.locator(".peleg")).to_contain_text(words[6], timeout=T)
        t = c.text_content()
        for w in words:
            assert w in t, (lang, w)
        for de in ("Geplant", "Gelaufen", "Abstieg", "Dauer", "gestrichelt", "durchgezogen", "Zum Plan", "Verknüpfung lösen", "einschließlich Pausen", " am "):
            assert de not in t, (lang, de)
        assert "Pausen" not in c.locator(".slcap").inner_text()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
