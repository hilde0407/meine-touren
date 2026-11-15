"""3.19.0 – Konfigurierbare Bausteine (Browser, Chromium): „Dein Jahr“ als Baustein, Standardlayout unverändert, Zahnrad und Einstellungs-Dialog, Aktivität filtern ändert die Werte
(gegen eine unabhängige Rechnung aus /api/tours), Konfiguration bleibt nach dem Neuladen, zwei Instanzen mit verschiedenen Filtern, andere Bausteine, Tourseite,
Tastatur, 390 px, Kontrast hell/dunkel, Englisch.
Wettlauf-Regel wie in test_seitenlayout_ui.py: nach jeder Aktion auf den Zustand warten (wait_for_function mit Pfeilfunktion / expect, 15 s), nie nur schlafen.
Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt (Chromium, dpr 2)."""
import json
import os
import re
import socket
import subprocess
import sys
import urllib.request
from datetime import date, datetime, timedelta

import pytest
from pathlib import Path

from tests.test_bausteine_ui import EXTRA, T, TEXTCONTRAST, _api, _edit, _reset, _shot, _tour  # noqa: F401
from tests.test_bausteine_ui import pw  # noqa: F401  (Fixture)
from tests.test_tourseite_ui import LAUNCH, SEED, _wait

# Zusätzliche Touren im laufenden Jahr, damit der Aktivitätsfilter die Zahlen wirklich verändert (Tage vor heute, Sportart, Strecke in m)
MORE = """
for i, (d, sp, dist) in enumerate([(5, "mtb", 40000), (30, "mtb", 35000), (12, "touringbicycle", 60000), (3, "jogging", 8000), (40, "jogging", 10000), (100, "jogging", 12000),
                                   (150, "jogging", 9000), (200, "hike", 14000), (250, "mtb", 52000), (2, "hike", 11000)]):
    add("k%%d" %% i, d, sp, dist, dist / 1.4, dist * 0.05)
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    tmp = tmp_path_factory.mktemp("bkf")
    data = tmp / "data"
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    for code in (SEED % {"root": str(ROOT), "data": str(data)}, (EXTRA + MORE) % {"root": str(ROOT), "data": str(data), "photos": str(tmp / "pics")}):
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT, env=env)
        assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / "launch.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    pr = subprocess.Popen([sys.executable, str(script)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    yield url
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)


OV = "() => [...document.querySelectorAll('main.home > section, main.home > .hcols > section, main.home > .tlw, main.home > .hcols > .tlw')].filter(e => !e.hidden && !e.classList.contains('sl-off')).map(e => e.dataset.wtype || e.id)"
GEAR = '.slit[data-sl="jahr"] [data-a="cfg"]'
NUMS = "(sel) => [...document.querySelectorAll(sel + ' .hyn b')].map(e => e.textContent.trim())"
SAVED = "() => { const s = document.getElementById('slsaved'); return !!s && s.textContent.trim() === 'Gespeichert'; }"
DOC = "() => JSON.stringify([document.getElementById('slsaved') && document.getElementById('slsaved').textContent, SL.docs.uebersicht])"
YEAR = datetime.now().year
ROOT = Path(__file__).resolve().parent.parent


def tours(url):
    with urllib.request.urlopen(url + "/api/tours", timeout=15) as r:
        return json.loads(r.read())


def calc(rows, sports=(), frm=None, to=None):
    """Touren, km, Höhenmeter, Stunden – unabhängig von der Oberfläche aus den Rohdaten gerechnet."""
    sel = [t for t in rows if (not sports or t["sport"] in sports) and (frm is None or t["date"][:10] >= frm) and (to is None or t["date"][:10] <= to)]
    return [len(sel), sum(t["dist_m"] for t in sel) / 1000, sum(t["up_m"] or 0 for t in sel), sum((t["dur_s"] or 0) for t in sel) / 3600]


def same(ui, exp):
    """Die Oberfläche rundet auf ganze Zahlen (de-DE mit Punkt als Tausendertrenner)."""
    got = [int(x.replace(".", "")) for x in ui]
    return all(abs(g - e) <= 0.5 + 1e-6 for g, e in zip(got, exp)), got


def wait_nums(pg, sel, exp):
    """Warten, bis die vier Kennzahlen dem Erwarteten entsprechen (Zustand, nicht Zeit)."""
    pg.wait_for_function("([sel, exp]) => { const v = [...document.querySelectorAll(sel + ' .hyn b')].map(e => parseInt(e.textContent.replace(/\\./g, ''), 10)); return v.length === exp.length && v.every((x, i) => Math.abs(x - exp[i]) <= 0.5 + 1e-6); }", arg=[sel, exp], timeout=T)


def click_gear(pg, sel=GEAR):
    """Auf schmalen Bausteinen (3.24.0) liegt „Einstellungen“ im „⋯“-Menü des Bausteinkopfs: zuerst das Menü öffnen."""
    if not pg.locator(sel).is_visible():
        pg.locator(sel.split(" [data-a")[0] + ' [data-a="more"]').click()
        pg.wait_for_function("(s) => { const e = document.querySelector(s); return !!e && e.offsetParent !== null; }", arg=sel, timeout=T)
    pg.locator(sel).click()


def open_gear(pg, sel=GEAR):
    click_gear(pg, sel)
    pg.wait_for_selector('.sldlg [role="dialog"] form', timeout=T)


def save_dialog(pg):
    pg.get_by_role("button", name="Speichern", exact=True).click()
    try:
        pg.wait_for_function("() => !document.querySelector('.sldlg')", timeout=T)
    except Exception:
        raise AssertionError(f"Dialog schließt nicht: {pg.errors} {pg.locator('.slerr').all_inner_texts()}")


def chip(pg, label):
    return pg.locator(".sldlg .flchip", has_text=re.compile(r"^%s$" % re.escape(label)))


def browser(pw, url, width=1280, height=1000, scheme="light", dpr=1, lang="de"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale="en-US" if lang == "en" else "de-DE", viewport={"width": width, "height": height}, color_scheme=scheme, device_scale_factor=dpr, reduced_motion="reduce")
    ctx.add_init_script("try { localStorage.setItem('lang', %r); } catch (e) {}" % lang)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(url) else r.continue_())
    pg.browser_ = b
    pg.goto(f"{url}/#/dash")
    pg.wait_for_selector("main.home #hlast", timeout=T)
    pg.wait_for_function("() => !!document.querySelector('#slopen')", timeout=T)
    return pg


# ------------------------------------------------------------------  Standard bleibt Standard  ------------------------------------------------------------------

def test_dein_jahr_default_block_is_the_old_block(pw, app):
    _reset(app)
    rows = tours(app)
    pg = browser(pw, app)
    try:
        assert pg.evaluate(OV)[:3] == ["hlast", "hyear", "hrecent"]                                            # an der alten Stelle
        assert pg.locator("main.home .slit").count() == 0 and pg.locator("#hyear .flk").count() == 0       # ohne Anpassung kein Kurztext, kein Rahmen
        assert pg.locator("#hyear h2").inner_text() == f"Dein Jahr {YEAR}"
        assert pg.locator("#hyear a.hmore").inner_text() == "Zur Statistik" and pg.locator("#hyear a.hmore").get_attribute("href") == "#/stats"
        assert pg.locator("#hyear .hyn span").all_inner_texts() == ["Touren", "Kilometer", "Höhenmeter", "Stunden unterwegs"]
        wait_nums(pg, "#hyear", calc(rows, frm=f"{YEAR}-01-01"))
        assert pg.locator("#hyear .hym > div").count() == 12 and pg.locator("#hyear .hym .cur").count() == 1
        assert pg.locator("#hyear .hym .cur span").inner_text() == "N"                                          # November: laufender Monat hervorgehoben
        assert pg.locator("#hyear .hcmp").count() == 1 and "gegenüber" in pg.locator("#hyear .hcmp").inner_text()
        assert _api(app, "uebersicht")["layout"] is None                                                       # nichts gespeichert
        assert not pg.errors, pg.errors
        _edit(pg)
        assert pg.locator(GEAR).count() == 1 and pg.locator('.slit[data-sl="jahr"] input[data-a="open"]').count() == 0 and pg.locator('.slit[data-sl="jahr"] [data-a="del"]').count() == 0
        assert pg.locator('.slit[data-sl="jahr"] [data-a="eye"]').count() == 1                                  # ausblendbar wie andere
        assert pg.locator(GEAR).get_attribute("aria-haspopup") == "dialog" and "Einstellungen" in pg.locator(GEAR).inner_text()
        assert pg.locator("#hyear").evaluate("e => e.closest('.slit').dataset.sl") == "jahr"
    finally:
        pg.browser_.close()


def test_dein_jahr_can_be_hidden_and_stays_hidden(pw, app):
    _reset(app)
    pg = browser(pw, app)
    try:
        _edit(pg)
        pg.locator('.slit[data-sl="jahr"] [data-a="eye"]').click()
        pg.wait_for_function("() => document.querySelector('.slit[data-sl=jahr]').classList.contains('sl-dim')", timeout=T)
        pg.locator("#slbar").get_by_role("button", name="Fertig").click()
        pg.wait_for_function("() => !document.querySelector('.slit') && !document.querySelector('#hyear:not(.sl-off)')", timeout=T)
        pg.wait_for_function(SAVED) if pg.locator("#slsaved").count() else None
        pg.wait_for_function("() => true")
        assert _api(app, "uebersicht")["layout"]["hidden"] == ["jahr"]
        pg.reload()
        pg.wait_for_selector("main.home #hlast", timeout=T)
        pg.wait_for_function("() => !!document.querySelector('#hyear.sl-off') && !!document.querySelector('#slopen')", timeout=T)
        assert pg.evaluate(OV)[:2] == ["hlast", "hrecent"]
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Zahnrad, Dialog, Filter  ------------------------------------------------------------------

def test_gear_opens_dialog_filter_by_activity_changes_values_and_survives_reload(pw, app):
    _reset(app)
    rows = tours(app)
    pg = browser(pw, app)
    try:
        wait_nums(pg, "#hyear", calc(rows, frm=f"{YEAR}-01-01"))
        _edit(pg)
        open_gear(pg)
        box = pg.locator('.sldlg [role="dialog"]')
        assert box.get_attribute("aria-modal") == "true" and "Einstellungen: Dein Jahr" in box.locator("h2").inner_text()
        assert pg.evaluate("() => !!document.activeElement.closest('[role=dialog]')")                          # Fokus im Dialog
        labels = pg.locator(".sldlg .flsp .flchip").all_inner_texts()
        assert labels[0] == "Alle" and {"Wandern", "MTB", "Radtour", "Laufen"} <= set(labels)                   # Sportarten des Nutzers
        assert chip(pg, "Alle").locator("input").is_checked() and not chip(pg, "Wandern").locator("input").is_checked()
        assert pg.locator(".sldlg select.flsel").input_value() == "year"                                        # Zeitraum: laufendes Jahr
        assert [o for o in pg.locator(".sldlg select.flsel option").all_inner_texts()][:4] == ["Laufendes Jahr", "Letzte 12 Monate", "Letzte 90 Tage", "Gesamte Zeit"]
        assert str(YEAR) in pg.locator(".sldlg select.flsel optgroup option").all_inner_texts()
        assert pg.locator('.sldlg input[type=checkbox][name]:not([data-all])').count() >= 4
        _shot(pg, "dialog-dein-jahr-hell.png", full=False)
        chip(pg, "Wandern").click()                                                                             # „Alle“ und Einzelauswahl schließen sich aus
        assert not chip(pg, "Alle").locator("input").is_checked() and chip(pg, "Wandern").locator("input").is_checked()
        chip(pg, "Wandern").click()
        assert chip(pg, "Alle").locator("input").is_checked()                                                   # ohne Auswahl gilt wieder „Alle“
        chip(pg, "Wandern").click()
        save_dialog(pg)
        exp = calc(rows, ["hike"], frm=f"{YEAR}-01-01")
        wait_nums(pg, "#hyear", exp)
        assert pg.locator("#hyear .flk").inner_text() == "Wandern" and pg.locator("#hyear h2").inner_text() == f"Dein Jahr {YEAR}"
        assert exp[0] < calc(rows, frm=f"{YEAR}-01-01")[0]                                                      # der Filter ändert die Zahlen wirklich
        assert pg.evaluate("() => document.activeElement && document.activeElement.dataset.a") == "cfg"        # Fokus kehrt zum Zahnrad zurück
        assert pg.locator('.slit[data-sl="jahr"] .slnm').inner_text().startswith("Dein Jahr") and "Wandern" in pg.locator('.slit[data-sl="jahr"] .slnm').inner_text()
        try:
            pg.wait_for_function(SAVED, timeout=T)
        except Exception:
            raise AssertionError(pg.evaluate(DOC))
        lay = _api(app, "uebersicht")["layout"]
        assert lay["cfg"] == {"jahr": {"sports": ["hike"]}} and "widgets" not in lay                           # nur die Abweichung wird gespeichert
        pg.locator("#slbar").get_by_role("button", name="Fertig").click()
        pg.wait_for_function("() => !document.querySelector('.slit')", timeout=T)
        pg.reload()
        pg.wait_for_selector("main.home #hyear .flk", timeout=T)
        assert pg.locator("#hyear .flk").inner_text() == "Wandern"
        wait_nums(pg, "#hyear", exp)
        # Zurück auf „Alle“: die Konfiguration entfällt ganz
        _edit(pg)
        open_gear(pg)
        chip(pg, "Alle").click()
        save_dialog(pg)
        pg.wait_for_function("() => !document.querySelector('#hyear .flk')", timeout=T)
        wait_nums(pg, "#hyear", calc(rows, frm=f"{YEAR}-01-01"))
        pg.wait_for_function(SAVED, timeout=T)
        assert "cfg" not in _api(app, "uebersicht")["layout"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_add_second_instance_via_catalog_configure_and_reload(pw, app):
    _reset(app)
    rows = tours(app)
    today = date.today()
    m = today.year * 12 + today.month - 12
    start12 = date(m // 12, m % 12 + 1, 1).isoformat()
    pg = browser(pw, app)
    try:
        _edit(pg)
        open_gear(pg)
        chip(pg, "Wandern").click()
        save_dialog(pg)
        pg.locator("#slbar [data-a=add]").click()
        pg.wait_for_selector('.slcat [data-add="jahr"]', timeout=T)
        assert pg.locator('.slcat [data-add="jahr"]').inner_text() == "Hinzufügen"                              # Standard-Instanz zählt nicht als „schon hinzugefügt“: mehrfach erlaubt
        pg.locator('.slcat [data-add="jahr"]').click()
        pg.wait_for_function("() => document.querySelectorAll('main.home section.hyear').length === 2", timeout=T)
        wid = pg.evaluate("() => SL.docs.uebersicht.widgets.slice(-1)[0].id")
        sel2 = f"#tlw-{wid}"
        wait_nums(pg, sel2, calc(rows, frm=f"{YEAR}-01-01"))                                                    # neue Instanz: Standardfilter, unabhängig von der ersten
        assert pg.locator(f"{sel2} .flk").count() == 0
        open_gear(pg, f'.slit[data-sl="{wid}"] [data-a="cfg"]')
        chip(pg, "MTB").click()
        pg.locator(".sldlg select.flsel").select_option(label="Letzte 12 Monate")
        save_dialog(pg)
        exp2 = calc(rows, ["mtb"], frm=start12)
        wait_nums(pg, sel2, exp2)
        assert pg.locator(f"{sel2} .flk").inner_text() == "MTB"
        assert pg.locator(f"{sel2} h2").inner_text() == "Deine letzten 12 Monate"
        assert pg.locator(f"{sel2} .hym > div").count() == 12
        wait_nums(pg, "#hyear", calc(rows, ["hike"], frm=f"{YEAR}-01-01"))                                      # die erste Instanz bleibt unberührt
        pg.wait_for_function(SAVED, timeout=T)
        lay = _api(app, "uebersicht")["layout"]
        w = lay["widgets"][0]
        assert lay["cfg"] == {"jahr": {"sports": ["hike"]}} and w["type"] == "jahr" and w["cfg"]["sports"] == ["mtb"] and w["cfg"]["range"] == "12m"
        # Gegenprobe: der Endpunkt liefert dieselben Zahlen wie die Oberfläche und die unabhängige Rechnung
        with urllib.request.urlopen(f"{app}/api/bausteine/jahr?sport=mtb&zeitraum=12m", timeout=15) as r:
            api = json.loads(r.read())
        assert api["touren"] == exp2[0] and abs(api["km"] - exp2[1]) < 0.01 and abs(api["hm"] - exp2[2]) < 0.1 and abs(api["stunden"] - exp2[3]) < 0.01 and api["von"] == start12
        pg.locator("#slbar").get_by_role("button", name="Fertig").click()
        pg.wait_for_function("() => !document.querySelector('.slit')", timeout=T)
        pg.reload()
        pg.wait_for_function("() => document.querySelectorAll('main.home section.hyear').length === 2", timeout=T)
        wait_nums(pg, sel2, exp2)
        wait_nums(pg, "#hyear", calc(rows, ["hike"], frm=f"{YEAR}-01-01"))
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


SEEDED = {"order": ["aufmacher", "jahr", "wj2", "wj3", "zuletzt"], "cfg": {"jahr": {"sports": ["hike"]}},
          "widgets": [{"id": "wj2", "type": "jahr", "cfg": {"sports": ["mtb", "touringbicycle"], "range": "12m", "metrics": ["km", "up"], "title": "Rad, letzte 12 Monate"}},
                      {"id": "wj3", "type": "jahr", "cfg": {"range": "y", "yr": YEAR - 1, "sports": ["hike"], "compare": False}}]}


def test_two_and_three_instances_values_ranges_titles(pw, app):
    _reset(app)
    _api(app, "uebersicht", "PUT", SEEDED)
    rows = tours(app)
    today = date.today()
    m = today.year * 12 + today.month - 12
    start12 = date(m // 12, m % 12 + 1, 1).isoformat()
    pg = browser(pw, app, dpr=2)
    try:
        pg.wait_for_function("() => document.querySelectorAll('main.home section.hyear').length === 3", timeout=T)
        assert pg.evaluate(OV)[:5] == ["hlast", "hyear", "jahr", "jahr", "hrecent"]
        wait_nums(pg, "#hyear", calc(rows, ["hike"], frm=f"{YEAR}-01-01"))
        # Instanz 2: zwei Kennzahlen (Kilometer, Höhenmeter), eigener Titel, Rad, letzte 12 Monate
        x = calc(rows, ["mtb", "touringbicycle"], frm=start12)
        wait_nums(pg, "#tlw-wj2", [x[1], x[2]])
        assert pg.locator("#tlw-wj2 h2").inner_text() == "Rad, letzte 12 Monate" and pg.locator("#tlw-wj2 .hyn span").all_inner_texts() == ["Kilometer", "Höhenmeter"]
        assert pg.locator("#tlw-wj2 .flk").inner_text() == "MTB, Radtour, Laufendes Jahr".replace("Laufendes Jahr", "Letzte 12 Monate")    # mit eigenem Titel steht der Zeitraum im Kurztext
        assert pg.locator("#tlw-wj2 .hyg").get_attribute("data-n") == "2"
        # Instanz 3: bestimmtes Jahr, ohne Vergleich
        y = calc(rows, ["hike"], frm=f"{YEAR - 1}-01-01", to=f"{YEAR - 1}-12-31")
        wait_nums(pg, "#tlw-wj3", y)
        assert pg.locator("#tlw-wj3 h2").inner_text() == f"Dein Jahr {YEAR - 1}" and pg.locator("#tlw-wj3 .flk").inner_text() == "Wandern"
        assert pg.locator("#tlw-wj3 .hcmp").count() == 0 and pg.locator("#hyear .hcmp").count() <= 1
        assert pg.locator("#tlw-wj3 .hym .cur").count() == 0                                                     # Vorjahr: kein „laufender“ Monat
        assert pg.locator("#hyear #hgoals").count() == 1 and pg.locator("#tlw-wj2 #hgoals").count() == 0         # Jahresziele nur in der Standard-Instanz
        _shot(pg, "uebersicht-zwei-dein-jahr-hell.png", full=False)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_all_time_and_90_days_ranges_and_empty_filter(pw, app):
    _reset(app)
    _api(app, "uebersicht", "PUT", {"widgets": [{"id": "wa", "type": "jahr", "cfg": {"range": "all", "sports": ["hike"]}}, {"id": "wb", "type": "jahr", "cfg": {"range": "90d"}},
                                                {"id": "wc", "type": "jahr", "cfg": {"sports": ["skialpin"]}}]})
    rows = tours(app)
    pg = browser(pw, app)
    try:
        pg.wait_for_function("() => document.querySelectorAll('main.home section.hyear').length === 4", timeout=T)
        wait_nums(pg, "#tlw-wa", calc(rows, ["hike"]))
        assert pg.locator("#tlw-wa h2").inner_text() == "Deine Touren insgesamt" and pg.locator("#tlw-wa .hym > div").count() <= 12
        frm = (date.today() - timedelta(days=89)).isoformat()
        wait_nums(pg, "#tlw-wb", calc(rows, frm=frm))
        assert pg.locator("#tlw-wb h2").inner_text() == "Deine letzten 90 Tage" and pg.locator("#tlw-wb .hym > div").count() == 13
        wait_nums(pg, "#tlw-wc", [0, 0, 0, 0])
        assert "Keine Touren mit diesem Filter" in pg.locator("#tlw-wc").inner_text()                             # leerer Filter: Hinweis statt leerer Fläche
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Andere Bausteine  ------------------------------------------------------------------

READY2 = "(ids) => ids.every(i => { const w = document.querySelector('#tlw-' + i + ' .tlsb'); return !!w && !/Wird geladen/.test(w.textContent); })"


def test_other_widgets_honour_activity_range_and_count(pw, app):
    _reset(app)
    rows = tours(app)
    jog = [t for t in rows if t["sport"] == "jogging"][:3]
    frm = (date.today() - timedelta(days=89)).isoformat()
    hike90 = [t for t in rows if t["sport"] == "hike" and t["date"][:10] >= frm]
    _api(app, "uebersicht", "PUT", {"widgets": [
        {"id": "wl", "type": "letzte", "cfg": {"n": 3, "sports": ["jogging"]}},
        {"id": "wr", "type": "rekorde", "cfg": {"sports": ["hike"], "range": "90d"}},
        {"id": "wp", "type": "periode", "cfg": {"period": "month", "sports": ["skialpin"], "title": "Ski im Monat"}},
        {"id": "ws", "type": "serie", "cfg": {"sports": ["skialpin"]}},
        {"id": "wh", "type": "heatmap", "cfg": {"metric": "up", "sports": ["hike"]}},
        {"id": "wm", "type": "meilensteine", "cfg": {"sports": ["hike"]}},
        {"id": "ww", "type": "wochentage", "cfg": {"sports": ["hike"], "range": "y", "yr": YEAR - 1, "metric": "h"}},
        {"id": "wg", "type": "sportarten", "cfg": {"range": "12m"}},
        {"id": "wk", "type": "rueckblick", "cfg": {"range": "y", "yr": YEAR - 1, "sports": ["hike"]}},
        {"id": "wo", "type": "rueckblick", "cfg": {"year": "last"}},
        {"id": "wz", "type": "jahresziel", "cfg": {"metric": "km", "goal": 500, "sports": ["hike"]}},
        {"id": "wv", "type": "jahresvergleich", "cfg": {"sports": ["hike"], "metrics": ["h", "count"]}},
    ]})
    pg = browser(pw, app)
    try:
        ids = ["wl", "wr", "wp", "ws", "wh", "wm", "ww", "wg", "wk", "wo", "wz", "wv"]
        pg.wait_for_function(READY2, arg=ids, timeout=T)
        # Letzte Touren: nur Laufen, höchstens 3, Kurztext in der Kopfzeile (auch zugeklappt sichtbar)
        names = pg.locator("#tlw-wl .sllist a").all_inner_texts()
        assert names == [t["name"] for t in jog] and len(names) == 3
        assert pg.locator("#tlw-wl .flk").inner_text() == "Laufen"
        # Rekorde: nur Wandern in den letzten 90 Tagen
        if hike90:
            best = max(hike90, key=lambda t: t["dist_m"])
            assert f"{best['dist_m'] / 1000:.1f}".replace(".", ",") in pg.locator("#tlw-wr .utile").first.inner_text()
        else:
            assert "Keine Touren mit diesem Filter" in pg.locator("#tlw-wr").inner_text()
        assert pg.locator("#tlw-wr .flk").inner_text() == "Wandern, Letzte 90 Tage"
        pg.locator("#tlw-wr summary").click()                                                                     # zugeklappt: Kurztext bleibt sichtbar
        pg.wait_for_function("() => !document.querySelector('#tlw-wr').open", timeout=T)
        assert pg.locator("#tlw-wr .flk").is_visible()
        # Eigener Titel, Aktivität ohne Touren
        assert pg.locator("#tlw-wp .tlt").inner_text() == "Ski im Monat" and pg.locator("#tlw-wp .flk").inner_text() == "Skifahren"
        assert "Keine Touren mit diesem Filter" in pg.locator("#tlw-ws").inner_text()
        km_all = sum(t["dist_m"] for t in rows if t["sport"] == "hike") / 1000
        mt = pg.locator("#tlw-wm").inner_text()
        assert abs(int(re.search(r"Kilometer gesamt\n([\d.]+) km", mt).group(1).replace(".", "")) - km_all) <= 0.5 + 1e-6 and f"Touren gesamt\n{sum(t['sport'] == 'hike' for t in rows)}\n" in mt
        assert pg.locator("#tlw-wh svg.slheat rect").count() >= 300 and pg.locator("#tlw-wh .flk").inner_text() == "Wandern"
        assert pg.locator("#tlw-ww .flk").inner_text() == f"Wandern, {YEAR - 1}"
        assert pg.locator("#tlw-wg .flk").inner_text() == "Letzte 12 Monate" and pg.locator("#tlw-wg circle.slsg").count() >= 1
        assert pg.locator("#tlw-wk .tlt").inner_text() == f"Rückblick {YEAR - 1}" and pg.locator("#tlw-wo .tlt").inner_text() == f"Rückblick {YEAR - 1}"      # neue und ältere Einstellung
        assert pg.locator("#tlw-wk .flk").inner_text() == f"Wandern, {YEAR - 1}" and pg.locator("#tlw-wo .flk").count() == 0
        km_hike = sum(t["dist_m"] for t in rows if t["sport"] == "hike" and t["date"][:4] == str(YEAR)) / 1000
        assert f"von 500 km" in pg.locator("#tlw-wz .slgt").inner_text() and pg.locator("#tlw-wz .flk").inner_text() == "Wandern"
        assert abs(int(re.search(r"([\d.]+) von 500", pg.locator("#tlw-wz .slgt").inner_text()).group(1).replace(".", "")) - km_hike) <= 0.5 + 1e-6
        assert pg.locator("#tlw-wv .utile").count() == 2 and pg.locator("#tlw-wv .utile span").all_inner_texts() == ["Stunden", "Touren"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_tour_average_comparison_basis(pw, app):
    _reset(app)
    _api(app, "tour-haupt", "PUT", {"widgets": [{"id": "wd1", "type": "durchschnitt", "cfg": {"values": ["km", "up"], "basis": "all"}},
                                                {"id": "wd2", "type": "durchschnitt", "cfg": {"values": ["km", "up"], "basis": "year"}},
                                                {"id": "wd3", "type": "durchschnitt", "cfg": {"values": ["km", "up"]}}]})
    pg = _tour(pw, app)
    try:
        pg.wait_for_function(READY2, arg=["wd1", "wd2", "wd3"], timeout=T)
        assert "alle Sportarten" in pg.locator("#tlw-wd1 .slcap").inner_text() and pg.locator("#tlw-wd1 .flk").inner_text() == "Alle Touren"
        assert "Jahr:" in pg.locator("#tlw-wd2 .slcap").inner_text() and pg.locator("#tlw-wd2 .flk").inner_text() == "Touren dieses Jahres"
        assert "Sportart:" in pg.locator("#tlw-wd3 .slcap").inner_text() and pg.locator("#tlw-wd3 .flk").count() == 0         # Standard wie bisher
        n = lambda i: int(re.search(r"deiner (\d+) anderen", pg.locator(f"#tlw-wd{i} .slcap").inner_text()).group(1))  # noqa: E731
        assert n(1) >= n(3) and n(1) >= n(2)
        _edit(pg)
        click_gear(pg, '.slit[data-sl="wd3"] [data-a="cfg"]')
        pg.wait_for_selector(".slform", timeout=T)
        assert pg.locator('.sldlg .flchip input[type=radio]').count() == 3 and pg.locator(".sldlg .flchip", has_text="Gleiche Sportart").locator("input").is_checked()
        pg.locator(".sldlg .flchip", has_text="Allen Touren").click()
        save_dialog(pg)
        pg.wait_for_function("() => /alle Sportarten/.test(document.querySelector('#tlw-wd3 .slcap')?.textContent || '')", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Tastatur, Touch, 390 px, Kontrast, Englisch  ------------------------------------------------------------------

def test_keyboard_flow_focus_trap_space_escape(pw, app):
    _reset(app)
    pg = browser(pw, app)
    try:
        _edit(pg)
        pg.locator(GEAR).focus()
        pg.keyboard.press("Enter")
        pg.wait_for_selector('.sldlg [role="dialog"] form', timeout=T)
        assert pg.evaluate("() => !!document.activeElement.closest('[role=dialog]')")
        for _ in range(40):                                                                                       # der Fokus verlässt den Dialog nie (Tab und Umschalt+Tab)
            pg.keyboard.press("Tab")
            assert pg.evaluate("() => !!document.activeElement.closest('[role=dialog]')")
        pg.keyboard.press("Shift+Tab")
        assert pg.evaluate("() => !!document.activeElement.closest('[role=dialog]')")
        for _ in range(15):                                                                                       # mit Tab zum Chip „Wandern“, Leertaste wählt
            if pg.evaluate("() => document.activeElement.value") == "hike":
                break
            pg.keyboard.press("Tab")
        assert pg.evaluate("() => document.activeElement.value") == "hike"
        assert pg.evaluate("() => { const l = document.activeElement.closest('.flchip'); const s = getComputedStyle(l); return s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) >= 2; }")      # sichtbarer Fokus
        pg.keyboard.press("Space")
        pg.wait_for_function("() => document.activeElement.checked === true && !document.querySelector('.sldlg [data-all]').checked", timeout=T)
        pg.keyboard.press("Escape")                                                                               # Esc schließt ohne Speichern; Fokus zurück zum Zahnrad
        pg.wait_for_function("() => !document.querySelector('.sldlg')", timeout=T)
        pg.wait_for_function("() => document.activeElement && document.activeElement.dataset.a === 'cfg'", timeout=T)
        assert pg.locator("#hyear .flk").count() == 0 and _api(app, "uebersicht")["layout"] is None
        # Enter im Textfeld speichert (Formular), Auswahl per Tastatur
        pg.keyboard.press("Enter")
        pg.wait_for_selector(".sldlg form", timeout=T)
        pg.locator('.sldlg input[type=text]').fill("Mein Jahr")
        pg.locator('.sldlg input[type=text]').press("Enter")
        pg.wait_for_function("() => !document.querySelector('.sldlg') && document.querySelector('#hyear h2').textContent === 'Mein Jahr'", timeout=T)
        assert pg.locator("#hyear .flk").count() == 0                                                              # Titel ohne Filter: kein Kurztext
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_phone_390px_dialog_fits_no_side_scroll_and_shots(pw, app):
    _reset(app)
    _api(app, "uebersicht", "PUT", SEEDED)
    pg = browser(pw, app, width=390, height=844, dpr=2)
    try:
        pg.wait_for_function("() => document.querySelectorAll('main.home section.hyear').length === 3", timeout=T)
        pg.wait_for_function("() => document.querySelector('#tlw-wj3 .hyn b')", timeout=T)
        o = pg.evaluate("() => ({page: document.documentElement.scrollWidth - window.innerWidth, wide: [...document.querySelectorAll('main.home .hyear')].filter(w => w.scrollWidth > w.clientWidth + 1).map(w => w.id)})")
        assert o["page"] <= 0 and o["wide"] == [], o
        _shot(pg, "uebersicht-390-zwei-dein-jahr-hell.png")
        _edit(pg)
        open_gear(pg)
        r = pg.evaluate("() => { const b = document.querySelector('.sldlg .slbox'), r = b.getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom, sw: b.scrollWidth, cw: b.clientWidth, vw: window.innerWidth, vh: window.innerHeight, page: document.documentElement.scrollWidth - window.innerWidth}; }")
        assert r["l"] >= 0 and r["r"] <= r["vw"] + 0.5 and r["sw"] <= r["cw"] and r["b"] <= r["vh"] + 0.5 and r["page"] <= 0, r
        assert pg.evaluate("() => [...document.querySelectorAll('.sldlg .flchip')].every(c => c.getBoundingClientRect().height >= 40 && c.getBoundingClientRect().right <= window.innerWidth)")      # Touch-Ziele
        pg.get_by_role("button", name="Speichern", exact=True).scroll_into_view_if_needed()
        assert pg.get_by_role("button", name="Speichern", exact=True).is_visible() and pg.get_by_role("button", name="Abbrechen").is_visible()
        _shot(pg, "dialog-dein-jahr-390-hell.png", full=False)
        pg.get_by_role("button", name="Abbrechen").click()
        pg.wait_for_function("() => !document.querySelector('.sldlg')", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme,width", [("light", 1280), ("dark", 1280), ("dark", 390)])
def test_contrast_of_blocks_and_dialog_light_and_dark(pw, app, scheme, width):
    _reset(app)
    _api(app, "uebersicht", "PUT", SEEDED)
    pg = browser(pw, app, width=width, height=900 if width > 500 else 844, scheme=scheme, dpr=2)
    try:
        pg.wait_for_function("() => document.querySelectorAll('main.home section.hyear').length === 3", timeout=T)
        pg.wait_for_function("() => [...document.querySelectorAll('.hyear .hyn b')].every(e => /\\d/.test(e.textContent))", timeout=T)
        r = pg.evaluate(TEXTCONTRAST, "main.home .hyear *")
        assert r["n"] > 15 and not r["low"], f"{scheme} {width}: Kontrast unter 4,5:1 {r['low']}"
        _shot(pg, f"uebersicht-{width}-{scheme}-zwei-dein-jahr.png", full=False)
        _edit(pg)
        click_gear(pg, '.slit[data-sl="wj2"] [data-a="cfg"]')
        pg.wait_for_selector('.sldlg [role="dialog"] form', timeout=T)
        r = pg.evaluate(TEXTCONTRAST, ".sldlg .slbox *")
        assert r["n"] > 15 and not r["low"], f"{scheme} {width}: Dialog, Kontrast unter 4,5:1 {r['low']}"
        # Gewählte Chips (Hell auf Dunkel und umgekehrt) und der Fokusrahmen
        pg.evaluate("() => document.querySelector('.sldlg .flchip input:checked').closest('.flchip').dataset.k = '1'")
        c = pg.evaluate("() => { const l = document.querySelector('.sldlg .flchip:has(input:checked)'), s = getComputedStyle(l); return [s.color, s.backgroundColor]; }")
        assert c[0] != c[1]
        _shot(pg, f"dialog-dein-jahr-{width}-{scheme}.png", full=False)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_english_labels_in_header_and_dialog(pw, app):
    _reset(app)
    _api(app, "uebersicht", "PUT", {"cfg": {"jahr": {"sports": ["hike"]}}, "widgets": [{"id": "wl", "type": "letzte", "cfg": {"n": 5, "sports": ["jogging"], "range": "all"}}]})
    pg = browser(pw, app, lang="en")
    try:
        pg.wait_for_function("() => /Your year/.test(document.querySelector('#hyear h2')?.textContent || '')", timeout=T)
        assert pg.locator("#hyear h2").inner_text() == f"Your year {YEAR}" and pg.locator("#hyear .flk").inner_text() == "Hiking"
        assert pg.locator("#hyear a.hmore").inner_text() == "Go to statistics"
        _edit(pg)
        click_gear(pg)
        pg.wait_for_selector('.sldlg [role="dialog"] form', timeout=T)
        pg.wait_for_function("() => /Activity/.test(document.querySelector('.sldlg legend')?.textContent || '')", timeout=T)
        txt = pg.locator(".sldlg").inner_text()
        for w in ("Activity", "Current year", "Last 12 months", "Last 90 days", "All time", "Compare with the previous year", "Custom title (optional)", "Save", "Cancel"):
            assert w in txt, (w, txt)
        assert "Laufendes" not in txt and "Aktivität" not in txt and "Letzte" not in txt
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
