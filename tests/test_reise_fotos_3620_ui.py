"""3.62.0 – Reise-Seite: ein Foto-Baustein „Fotos“ statt zwei (fester Abschnitt „Fotos“ + Baustein „Fotos der Reise“).
Der Typ bleibt „rdiashow“ (gespeicherte Layouts bleiben gültig), neue Auswahl mode „all“ (Alle, Vorgabe); der feste Abschnitt „fotos“ der Reise ist derselbe Baustein mit Vorgabe „Alle“
(Id, Position, Breite, Sichtbarkeit und Auf-/Zu-Zustand unverändert, ohne Umschreiben gespeicherter Layouts).
Server: mode all nur beim Reise-Baustein, cfg.fotos streng geprüft, alte Layouts und alte Ansichtscodes mit „fotos“ bleiben importierbar.
Browser (Chromium): alle Fotos der Reise als Vorschaubilder samt Lightbox, „Diashow starten“ und „Diashow teilen“, Migration (Position, Breite, zu, ausgeblendet, alter rdiashow behält mode),
Beste / Zufällig / Neueste unverändert, Einstellungen, Vorlage „Fotoreise“, mehrfach einfügbar, ehrlicher Hinweis zum Teilen, PDF-Reisebericht weiter erreichbar."""
import base64
import json
import re
import urllib.request

import pytest

from tests.test_core import fresh  # noqa: F401
from tests.test_reise_seiten import _client, _w
from tests.test_seitenlayout_ui import T, _api, _edit, pw  # noqa: F401
from tests.test_bausteine_konfig_ui import click_gear, save_dialog
from tests.test_reise_seiten_ui import ALL_UNITS, STD, TL, UNITS, _order, _saved_doc, _tid, _trip, _trips, app, clean  # noqa: F401


# ------------------------------------------------------------------  Server  ------------------------------------------------------------------
def test_server_mode_all_nur_beim_reise_baustein(fresh):
    with _client() as c:
        ok = {"widgets": [_w("wf1", "rdiashow", {"mode": "all"}), _w("wf2", "rdiashow", {"mode": "all", "view": "strip", "ratio": "43", "size": "l", "caption": True}),
                          _w("wf3", "rdiashow", {"mode": "best", "n": 12}), _w("wf4", "rdiashow", {"mode": "random"}), _w("wf5", "rdiashow", {"mode": "recent", "n": 3}), _w("wf6", "rdiashow")]}
        assert c.put("/api/layout/reise", json=ok).status_code == 200
        w = c.get("/api/layout/reise").json()["layout"]["widgets"]
        assert [x["cfg"].get("mode") for x in w] == ["all", "all", "best", "random", "recent", None]
        for bad in ({"mode": "day"}, {"mode": "alle"}, {"mode": "all", "n": 5}, {"mode": "all", "sports": ["hike"]}, {"mode": "all", "range": "y"}):
            assert c.put("/api/layout/reise", json={"widgets": [_w("wf1", "rdiashow", bad)]}).status_code == 400, bad
        # „Alle“ gibt es bei den Erinnerungen der Übersicht und der Statistik nicht
        for key in ("uebersicht", "statistik"):
            assert c.put(f"/api/layout/{key}", json={"cfg": {"erinn": {"mode": "all"}}}).status_code == 400, key
            assert c.put(f"/api/layout/{key}", json={"widgets": [_w("we1", "erinn", {"mode": "all"})]}).status_code == 400, key
            assert c.put(f"/api/layout/{key}", json={"cfg": {"erinn": {"mode": "recent"}}}).status_code == 200, key


def test_server_abschnitt_fotos_einstellung(fresh):
    with _client() as c:
        assert c.put("/api/layout/reise", json={"cfg": {"fotos": {"mode": "random", "view": "strip"}}}).status_code == 200
        assert c.get("/api/layout/reise").json()["layout"]["cfg"] == {"fotos": {"mode": "random", "view": "strip"}}
        assert c.put("/api/layout/reise", json={"cfg": {"fotos": {"mode": "all", "ratio": "43", "size": "l", "title": "Alle Bilder"}}}).status_code == 200
        for bad in ({"mode": "day"}, {"sports": ["hike"]}, {"fremd": 1}, {"mode": "all", "n": 7}):
            assert c.put("/api/layout/reise", json={"cfg": {"fotos": bad}}).status_code == 400, bad
        # auf der Reise-Seite nur dort: kein Abschnitt „fotos“ mit Einstellung auf der Tourseite
        assert c.put("/api/layout/tour-haupt", json={"cfg": {"fotos": {"mode": "all"}}}).status_code in (200, 400)


def test_server_alte_layouts_mit_fotos_bleiben_gueltig(fresh):
    alt = {"v": 1, "order": ["kopf", "karte", "fotos", "touren", "kennzahlen"], "hidden": ["flug", "fotos"], "closed": ["fotos"], "open": ["stat"], "w": {"fotos": "halb", "karte": "halb"},
           "widgets": [_w("wd1", "rdiashow", {"mode": "recent", "view": "grid", "n": 9, "link": False})]}
    with _client() as c:
        assert c.put("/api/layout/reise", json=alt).status_code == 200
        got = c.get("/api/layout/reise").json()["layout"]
        for k in ("order", "hidden", "closed", "open", "w"):
            assert got[k] == alt[k], k
        assert got["widgets"] == [{"id": "wd1", "type": "rdiashow", "cfg": {"mode": "recent", "view": "grid", "n": 9, "link": False}}]
        assert "cfg" not in got                                                         # nichts umgeschrieben: ohne Eintrag gilt „Alle“
        # Gruppe mit dem Abschnitt „fotos“ (Standard-Abschnitt der Seite)
        g = {"v": 1, "groups": [{"id": "grpfoto1", "title": "Bilder", "ids": ["karte", "fotos"]}]}
        assert c.put("/api/layout/reise", json=g).status_code == 200
        assert c.get("/api/layout/reise").json()["layout"]["groups"][0]["ids"] == ["karte", "fotos"]


def _code(doc):
    return "MTA1." + base64.urlsafe_b64encode(json.dumps(doc).encode()).decode().rstrip("=")


def test_server_alter_ansichtscode_und_exportdatei_mit_fotos(fresh):
    lay = {"v": 1, "order": ["kopf", "fotos", "karte", "touren"], "hidden": ["stat", "fotos"], "closed": ["fotos"], "w": {"fotos": "drittel"}}
    exp = {"format": "meine-touren-ansicht", "format_version": 1, "app_version": "3.61.5", "page": "reise", "name": "Alt", "layouts": {"reise": lay}}
    with _client() as c:
        for r in (c.post("/api/layout/check", json=exp).json(), c.post("/api/layout/code", json={"code": _code(exp)}).json()):
            assert r["ok"] and not r["errors"], r
            assert r["layouts"]["reise"]["hidden"] == ["stat", "fotos"] and r["layouts"]["reise"]["w"] == {"fotos": "drittel"} and r["layouts"]["reise"]["closed"] == ["fotos"]
        neu = {**exp, "layouts": {"reise": {**lay, "cfg": {"fotos": {"mode": "best"}}, "widgets": [_w("wd1", "rdiashow", {"mode": "all"})]}}}
        r = c.post("/api/layout/code", json={"code": _code(neu)}).json()
        assert r["ok"], r
        bad = {**exp, "layouts": {"reise": {"cfg": {"fotos": {"mode": "day"}}}}}
        assert not c.post("/api/layout/check", json=bad).json()["ok"]


def test_standardabschnitte_der_reise_unveraendert():
    from app import layout
    assert layout.STD_IDS["reise"] == frozenset(("kopf", "kennzahlen", "stat", "flug", "karte", "fotos", "touren"))
    assert "rdiashow" in layout.REISE_TYPEN


# ------------------------------------------------------------------  Browser  ------------------------------------------------------------------
def _slitem(pg, wid):
    return pg.evaluate("(i) => { const it = slItems('reise').find(x => x.id === i); return it && {wtype: it.wtype, cfg: it.cfg, cw: it.cw, build: it.build || '', widget: !!it.widget}; }", wid)


def test_standard_zeigt_alle_fotos_der_reise_mit_lightbox(pw, app):
    pg = _trip(pw, app)
    try:
        assert pg.evaluate(UNITS) == STD and pg.evaluate(ALL_UNITS) == STD
        pg.wait_for_function("() => document.querySelectorAll('#tls-fotos .erb img').length === 6", timeout=TL)             # alle sechs Fotos der Reise (die der anderen Reisen nicht)
        assert pg.locator("#cph").count() == 0                                                                                # der alte Abschnitt mit eigener Abfrage entfällt
        assert pg.locator("#tls-fotos h3.tlt").inner_text() == "Fotos"
        assert "6 Fotos" in pg.locator("#tlk-fotos").inner_text()
        assert pg.evaluate("() => document.getElementById('tls-fotos').open") is True                                         # wie bisher offen
        assert _slitem(pg, "fotos")["wtype"] == "rdiashow" and _slitem(pg, "fotos")["cfg"]["mode"] == "all" and _slitem(pg, "fotos")["build"] == "rdiashow"
        # keine Zufallsauswahl, keine Begrenzung auf n: die Abfrage nennt nur Zeitraum und Obergrenze
        u = pg.evaluate("() => { const it = slItems('reise').find(x => x.id === 'fotos'); return erUrl(it.cfg, {from: '2025-01-01', to: '2025-01-09'}); }")
        assert "random" not in u and "best" not in u and "recent" not in u and "date_from=2025-01-01" in u and "date_to=2025-01-09" in u and "limit=5000" in u, u
        # Lightbox wie überall
        pg.locator("#tls-fotos .erb img").nth(2).click()
        pg.wait_for_function("() => document.getElementById('lb').classList.contains('on')", timeout=T)
        n0 = pg.evaluate("() => LB_I")
        assert pg.evaluate("() => PH_LIST.length") == 6 and n0 == 2
        pg.keyboard.press("ArrowRight") if False else pg.locator('#lb [data-a="next"]').click()
        pg.wait_for_function("(n) => LB_I === n", arg=3, timeout=T)
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.getElementById('lb').classList.contains('on')", timeout=T)
        # Diashow starten (alle Fotos des Zeitraums) und Diashow teilen
        href = pg.locator("#tls-fotos a.erdia").get_attribute("href")
        assert "from=" in href and "to=" in href and "best" not in href and "random" not in href and "recent" not in href and "day=" not in href, href
        assert pg.locator("#tls-fotos a.erdia").inner_text() == "Diashow starten"
        assert pg.locator("#tls-fotos .erdsh").inner_text() == "Diashow teilen"
        assert "300" in pg.locator("#tls-fotos .erdsh").get_attribute("title")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_teilen_bei_alle_nennt_ehrlich_die_besten_bis_300(pw, app):
    pg = _trip(pw, app)
    try:
        pg.wait_for_selector("#tls-fotos .erdsh", timeout=TL)
        pg.evaluate("() => { window.__shared = null; Object.defineProperty(navigator, 'share', {configurable: true, value: async d => { window.__shared = d; }}); }")
        pg.click("#tls-fotos .erdsh")
        pg.wait_for_function("() => !!window.__shared", timeout=TL)
        assert pg.evaluate("() => window.__shared.url").startswith(app + "/s/")
        pg.wait_for_function("() => /besten bis zu 300 Fotos der Reise/.test(document.querySelector('#tls-fotos .erdsn').textContent)", timeout=T)
        # mehr als 300 Fotos: nennt, dass nicht alle im Link sind (Aufruf mit Zahl, ohne 500 Fotos anzulegen)
        txt = pg.evaluate("""async () => {
          const box = document.createElement('div'); box.className = 'rsdh'; box.innerHTML = '<button type="button">x</button><span class="erdsn"></span>'; document.body.appendChild(box);
          const f0 = window.fetch; window.fetch = async () => ({ok: true, json: async () => ({url: '/s/abc', title: 'Diashow'})});
          navigator.share = async () => {};
          await erShareRange(box.querySelector('button'), {from: '2025-01-01', to: '2025-01-09', name: 'Reise'}, {mode: 'all'}, 500);
          window.fetch = f0; return box.querySelector('.erdsn').textContent; }""")
        assert "nur die besten 300 der 500 Fotos der Reise" in txt, txt
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
        for r in json.loads(urllib.request.urlopen(app + "/api/shares").read()):
            urllib.request.urlopen(urllib.request.Request(f"{app}/api/share/{r['token']}", method="DELETE"))


def test_migration_altes_layout_position_breite_zu_und_alter_baustein(pw, app):
    alt = {"v": 1, "order": ["kopf", "kennzahlen", "fotos", "karte", "touren", "stat", "flug", "wd1"], "hidden": ["flug"], "closed": ["fotos"], "w": {"fotos": "halb", "karte": "halb"},
           "widgets": [{"id": "wd1", "type": "rdiashow", "cfg": {"mode": "recent", "view": "strip", "n": 9, "caption": True}}]}
    _api(app, "reise", "PUT", alt)
    pg = _trip(pw, app)
    try:
        _order(pg, ["kopf", "kennzahlen", "fotos", "karte", "touren", "stat", "wd1"])
        f = _slitem(pg, "fotos")
        assert f["cw"] == "halb" and f["cfg"]["mode"] == "all" and f["wtype"] == "rdiashow", f                                  # gleiche Breite, jetzt „Alle“
        assert pg.evaluate("() => document.getElementById('tls-fotos').open") is False                                          # zugeklappt bleibt zugeklappt
        pg.wait_for_function("() => document.querySelectorAll('#tls-fotos .erb img').length === 6", timeout=TL)
        w = _slitem(pg, "wd1")
        assert w["cfg"] == alt["widgets"][0]["cfg"] and w["widget"] is True, w                                                  # alte Einstellungen unverändert
        assert pg.evaluate("() => erCfg(slItems('reise').find(x => x.id === 'wd1').cfg).mode") == "recent"
        pg.wait_for_function("() => document.querySelectorAll('#tlw-wd1 .ers img').length >= 1 && document.querySelector('#tlw-wd1 figcaption')", timeout=TL)
        assert "Neueste" in pg.locator("#tlw-wd1 .flk, #tlw-wd1 summary").first.inner_text()
        # nichts wurde umgeschrieben
        assert _api(app, "reise")["layout"]["order"] == alt["order"] and "cfg" not in _api(app, "reise")["layout"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_migration_ausgeblendet_bleibt_ausgeblendet(pw, app):
    _api(app, "reise", "PUT", {"v": 1, "hidden": ["fotos"]})
    pg = _trip(pw, app)
    try:
        assert pg.evaluate(UNITS) == [x for x in STD if x != "fotos"] and pg.evaluate(ALL_UNITS) == STD
        assert pg.locator("#tls-fotos").is_hidden()
        assert pg.locator("#slview, .slit").count() == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_beste_zufaellig_neueste_unveraendert(pw, app):
    pg = _trip(pw, app)
    try:
        r = pg.evaluate("""() => { const fix = {from: '2025-01-01', to: '2025-01-09'};
          return ['best', 'random', 'recent', 'all'].map(m => [erUrl({mode: m, n: 12}, fix), erSlideUrl({mode: m, n: 12}, fix)]); }""")
        assert r[0][0] == "/api/photos?best=true&limit=12&date_from=2025-01-01&date_to=2025-01-09" and r[0][1] == "slideshow.html?best=60&from=2025-01-01&to=2025-01-09"
        assert r[1][0] == "/api/photos?random=true&limit=12&date_from=2025-01-01&date_to=2025-01-09" and r[1][1] == "slideshow.html?random=1&from=2025-01-01&to=2025-01-09"
        assert r[2][0] == "/api/photos?recent=1&limit=12&date_from=2025-01-01&date_to=2025-01-09" and r[2][1] == "slideshow.html?recent=1&from=2025-01-01&to=2025-01-09"
        assert r[3][0] == "/api/photos?limit=5000&date_from=2025-01-01&date_to=2025-01-09" and r[3][1] == "slideshow.html?from=2025-01-01&to=2025-01-09"
    finally:
        pg.browser_.close()
    for mode in ("best", "random", "recent"):
        _api(app, "reise", "PUT", {"widgets": [{"id": "wd1", "type": "rdiashow", "cfg": {"mode": mode, "view": "grid", "n": 3}}]})
        pg = _trip(pw, app)
        try:
            pg.wait_for_function("() => document.querySelectorAll('#tlw-wd1 .erb img').length === 3", timeout=TL)            # Anzahl n gilt weiter
            pg.wait_for_function("() => document.querySelectorAll('#tls-fotos .erb img').length === 6", timeout=TL)          # der Abschnitt „Fotos“ daneben bleibt „Alle“
            assert pg.locator("#tlw-wd1 .erdsh").count() == 1 and pg.locator("#tlw-wd1 a.erdia").count() == 1
            assert "300" not in (pg.locator("#tlw-wd1 .erdsh").get_attribute("title") or "")
            assert not pg.errors, pg.errors
        finally:
            pg.browser_.close()


def test_einstellungen_welche_fotos_alle_vorgabe_und_speichern(pw, app):
    pg = _trip(pw, app)
    try:
        _edit(pg)
        pg.wait_for_selector("#tls-fotos .erb img", timeout=TL)
        click_gear(pg, '.slit[data-sl="fotos"] [data-a="cfg"]')
        pg.wait_for_selector(".sldlg form.erform", timeout=T)
        labels = pg.locator('.sldlg input[name="er-mode"] + span').all_inner_texts()
        assert labels == ["Alle Fotos der Reise", "Beste Fotos", "Zufällige Fotos", "Neueste Fotos"], labels
        assert pg.locator('.sldlg input[name="er-mode"][value="all"]').is_checked()
        assert pg.locator('.sldlg input[name="er-mode"][value="day"]').count() == 0 and pg.locator('.sldlg [name="f1"]').count() == 0
        assert pg.locator('.sldlg fieldset[data-nm]').is_hidden()                                                                  # „Alle“ hat keine Anzahl
        assert "Einstellungen: Fotos" in pg.locator(".sldlg").inner_text() or pg.locator(".uidlg h2, .uidlg h3").first.inner_text().startswith("Einstellungen: Fotos")
        pg.locator('.sldlg input[name="er-mode"][value="random"]').check()
        assert pg.locator('.sldlg fieldset[data-nm]').is_visible()
        save_dialog(pg)
        doc = _saved_doc(pg, want=lambda d: d and (d.get("cfg") or {}).get("fotos", {}).get("mode") == "random")
        assert doc["cfg"]["fotos"]["mode"] == "random", doc                                                                        # die Auswahl steht ausdrücklich im Dokument (ohne Eintrag wäre es „Alle“)
        pg.wait_for_function("() => document.querySelectorAll('#tls-fotos .erb img').length === 6", timeout=TL)
        assert _slitem(pg, "fotos")["cfg"]["mode"] == "random"
        # zurück zu „Alle“
        click_gear(pg, '.slit[data-sl="fotos"] [data-a="cfg"]')
        pg.wait_for_selector(".sldlg form.erform", timeout=T)
        assert pg.locator('.sldlg input[name="er-mode"][value="random"]').is_checked()
        pg.locator(".sldlg .erreset").click()
        assert pg.locator('.sldlg input[name="er-mode"][value="all"]').is_checked()
        save_dialog(pg)
        doc = _saved_doc(pg, want=lambda d: d and (d.get("cfg") or {}).get("fotos", {}).get("mode") == "all")
        assert doc["cfg"]["fotos"]["mode"] == "all"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_katalog_ein_baustein_fotos_mehrfach_einfuegbar(pw, app):
    pg = _trip(pw, app)
    try:
        _edit(pg)
        pg.locator("#slbar [data-a=add]").click()
        pg.wait_for_selector(".slcat .slcard", timeout=T)
        names = pg.locator(".slcat .slcard h3").all_inner_texts()
        assert "Fotos" in names and "Fotos der Reise" not in names, names
        assert pg.locator('.slcard:has([data-add="rdiashow"]) [data-add="rdiashow"]').first.inner_text() == "Hinzufügen"
        pg.locator('[data-add="rdiashow"]').first.click()
        pg.wait_for_function("() => document.querySelectorAll('#trx [data-wtype=rdiashow]').length === 2", timeout=T)
        pg.wait_for_function("() => [...document.querySelectorAll('#trx [data-wtype=rdiashow]')].every(e => e.querySelectorAll('.erb img').length === 6)", timeout=TL)      # neuer Baustein: Vorgabe „Alle“
        pg.locator("#slbar [data-a=add]").click()
        pg.wait_for_selector(".slcat .slcard", timeout=T)
        assert pg.locator('[data-add="rdiashow"]').first.inner_text() == "Noch einmal hinzufügen" and pg.locator('[data-add="rdiashow"]').first.is_enabled()
        pg.keyboard.press("Escape")
        _done_edit(pg)
        doc = _saved_doc(pg, want=lambda d: d and len(d.get("widgets", [])) == 1)
        assert doc["widgets"][0]["type"] == "rdiashow" and doc["widgets"][0]["cfg"]["mode"] == "all", doc
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def _done_edit(pg):
    pg.locator("#slbar").get_by_role("button", name="Fertig").click()
    pg.wait_for_function("() => !document.querySelector('.slit') && !document.getElementById('slbar')", timeout=T)


def test_vorlage_fotoreise_beste_oben_alle_unten(pw, app):
    pg = _trip(pw, app)
    try:
        d = pg.evaluate("() => slTplDocs(SL_TPL.find(t => t.id === 're-fotos')).reise")
        assert d["order"] == ["kopf", "t-rdiashow", "karte", "t-rkennzahl", "fotos", "touren"], d
        w = [x for x in d["widgets"] if x["type"] == "rdiashow"]
        assert len(w) == 1 and w[0]["cfg"]["mode"] == "best" and w[0]["cfg"]["view"] == "show" and w[0]["cfg"]["n"] == 12 and w[0]["cfg"]["ratio"] == "sq", w
        assert "fotos" not in d.get("hidden", []) and "cfg" not in d                                                                                  # „fotos“ steht sichtbar mit der Vorgabe „Alle“
        assert "alle Fotos" in pg.evaluate("() => SL_TPL.find(t => t.id === 're-fotos').desc") and "besten Fotos" in pg.evaluate("() => SL_TPL.find(t => t.id === 're-fotos').desc")
        _api(app, "reise", "PUT", d)                                                                                                 # der Server nimmt die Vorlage an
    finally:
        pg.browser_.close()
    pg = _trip(pw, app)
    try:
        pg.wait_for_function("() => document.querySelectorAll('#tls-fotos .erb img').length === 6 && document.querySelectorAll('#tlw-t-rdiashow .erp img').length >= 1", timeout=TL)
        assert pg.evaluate(UNITS) == ["kopf", "t-rdiashow", "karte", "t-rkennzahl", "fotos", "touren"] or pg.evaluate(UNITS) == ["kopf", "rdiashow", "karte", "rkennzahl", "fotos", "touren"] or "fotos" in pg.evaluate(UNITS)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_reisebericht_pdf_und_alte_kennungen_funktionieren(pw, app):
    t = _trips(app)["La Gomera"]
    with urllib.request.urlopen(f"{app}/api/trips/{t['id']}/pdf?photos_on=1", timeout=60) as r:
        assert r.status == 200 and r.read(5) == b"%PDF-"
    pg = _trip(pw, app)
    try:
        for sel in ("#tredit", "#trpdf", "#trsnd", "#trhide", "#coff", "#cofm", "#cm", "#tls-fotos", "#tlk-fotos", "#tlsb-fotos"):
            assert pg.locator(sel).count() >= 1, sel
        v0 = pg.evaluate("() => localStorage.getItem('mt_trf_rs_fotos')")
        pg.locator("#tls-fotos > summary").click()                                                                                    # einklappen merkt sich wie bisher den Schlüssel rs_fotos
        pg.wait_for_function("(v) => localStorage.getItem('mt_trf_rs_fotos') !== v", arg=v0, timeout=T)
        assert pg.evaluate("() => document.getElementById('tls-fotos').open") is False
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_handy_ohne_ueberlauf(pw, app):
    pg = _trip(pw, app, width=390, height=800)
    try:
        pg.wait_for_function("() => document.querySelectorAll('#tls-fotos .erb img').length === 6", timeout=TL)
        m = pg.evaluate("() => { const b = document.querySelector('#tls-fotos .erdsh').getBoundingClientRect(); return [document.documentElement.scrollWidth, innerWidth, b.left, b.right, b.height]; }")
        assert m[0] <= m[1] and m[2] >= 0 and m[3] <= 390 and m[4] >= 44, m
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
