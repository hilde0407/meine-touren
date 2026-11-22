"""3.21.0 – Ansichten, Vorlagen, Export (Browser, Chromium).
Ansichten anlegen, umschalten, umbenennen, duplizieren, löschen, Standard festlegen, Vorlagen, Regel Sportart → Ansicht, Export-Datei, Import (gültig, ungültig, Überschreiben nur nach Rückfrage),
Neuladen, 390 px, Kontrast hell/dunkel, Tastatur. Wettlauf-Regel: nach jeder Aktion auf den Zustand warten (wait_for_function/expect, 15 s).
Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt (Chromium, dpr 2)."""
import json
import os
import socket
import subprocess
import sys

import pytest

expect = pytest.importorskip("playwright.sync_api").expect
from tests.test_seitenlayout_ui import (ROOT, T, _api, _browser, _dash, _edit, _saved, pw)  # noqa: F401
from tests.test_tourseite_ui import CONTRAST, LAUNCH, SEED, _shot, _wait

KEYS = ("tour-haupt", "tour-auswertung", "uebersicht")
SEED2 = SEED + "\ndb.execute(\"UPDATE tours SET sport='bike' WHERE id='s0'\")\n"          # zweite Sportart für die Regel „Sportart → Ansicht“


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    tmp = tmp_path_factory.mktemp("av")
    data = tmp / "data"
    out = subprocess.run([sys.executable, "-c", SEED2 % {"root": str(ROOT), "data": str(data)}], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / "launch.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    pr = subprocess.Popen([sys.executable, str(script)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    yield url
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)


@pytest.fixture(autouse=True)
def clean(app):
    for k in KEYS:
        _api(app, k, "DELETE")
    yield


def _box(views, active=None, rules=None):
    """views: [(id, name, {layout})]"""
    d = {"v": 2, "views": [{"id": i, "name": n, "layout": l} for i, n, l in views], "active": active or views[0][0]}
    if rules is not None:
        d["rules"] = rules
    return d


def _put_both(url, views, **kw):
    """Ansichten der Tourseite: beide Dokumente führen dieselben Ansichten (der Inhalt je Schlüssel eigen)."""
    _api(url, "tour-haupt", "PUT", _box([(i, n, l) for i, n, l in views], **kw))
    _api(url, "tour-auswertung", "PUT", _box([(i, n, {"v": 1}) for i, n, l in views], **kw))


def _cont(url, key):
    return _api(url, key).get("container")


def _tour_page(pw, url, tour="r3", **kw):
    pg = _browser(pw, url, devs="one" if tour == "r3" else None, tour=tour, **kw)
    pg.goto(f"{url}/#/tour/{tour}")
    pg.wait_for_selector("#tl #tls-photos", state="attached", timeout=T)
    pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen') && !!SL.view.tour", timeout=T)
    return pg


def _goto_tour(pg, url, tid):
    """Hash-Navigation zu einer anderen Tour: erst warten, bis der Router die Seite NEU gezeichnet hat (die alte Tourseite trägt data-old und zählt nicht)."""
    pg.evaluate("() => { const t = document.getElementById('tl'); if (t) t.dataset.old = '1'; }")
    pg.goto(f"{url}/#/tour/{tid}")
    pg.wait_for_selector("#tl:not([data-old]) #tls-photos", state="attached", timeout=T)
    pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen') && !!SL.view.tour", timeout=T)


def _view_is(pg, name, fam="tour"):
    pg.wait_for_function("([f, n]) => { try { return slViewName(f, SL.view[f]) === n; } catch (e) { return false; } }", arg=[fam, name], timeout=T)


def _open_views(pg):
    pg.locator("#slbar [data-a=views]").click()
    pg.wait_for_selector(".slvws .slvr", timeout=T)


def _rows(pg):
    return pg.locator(".slvws .slvnm").all_inner_texts()


def _btn(pg, label):
    return pg.locator(".slvws").get_by_role("button", name=label, exact=True)


def _server_names(url, key="tour-haupt"):
    return [v["name"] for v in (_cont(url, key) or {"views": []})["views"]]


def _wait_server(pg, url, pred, key="tour-haupt"):
    """Wartet auf den Stand beim Server. Nicht mit time.sleep: während Python schläft, bedient er die Routen der Seite (pg.route) nicht, und das Speichern bliebe hängen."""
    import time
    end = time.time() + 15
    while time.time() < end:
        c = _cont(url, key)
        if c and pred(c):
            return c
        pg.wait_for_timeout(200)
    raise AssertionError("Server hat den erwarteten Stand nicht erreicht: " + json.dumps(_cont(url, key))[:300])


def _dlg_open(pg):
    return "() => !document.querySelector('.uidlg')"


def test_standard_view_alone_looks_as_before_and_old_documents_are_migrated(pw, app):
    _api(app, "tour-haupt", "PUT", {"order": ["photos", "map", "prof", "puls", "wp"], "hidden": ["wp"]})          # altes Format
    pg = _tour_page(pw, app)
    try:
        assert pg.locator("#slview").count() == 0                                        # eine Ansicht: keine Auswahl, alles wie bisher
        assert pg.evaluate("slViewName('tour', SL.view.tour)") == "Standard" and pg.evaluate("SL.docs['tour-haupt'].order[0]") == "photos"
        assert pg.evaluate("() => [...document.querySelectorAll('#tl details.tls')].filter(d => !d.closest('.sl-off')).map(d => d.dataset.tls)")[0] == "photos"
        _edit(pg)
        pg.locator("#slbar [data-a=done]").click()
        pg.wait_for_function("() => !document.querySelector('.slit')", timeout=T)
        assert _api(app, "tour-haupt")["layout"].get("views") is None                    # unverändert im alten Format gespeichert
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_create_switch_rename_duplicate_default_delete_and_reload(pw, app):
    pg = _tour_page(pw, app)
    try:
        _edit(pg)
        _open_views(pg)
        assert _rows(pg) == ["Standard"]
        assert _btn(pg, "Löschen: Standard").count() == 0                                # die letzte Ansicht lässt sich nicht löschen
        # neue Ansicht (Standard-Anordnung), mit Namenskontrolle
        pg.locator(".slvws [data-a=new]").click()
        pg.wait_for_selector("#slvname", timeout=T)
        pg.fill("#slvname", "")
        pg.keyboard.press("Enter")
        pg.wait_for_function("() => document.getElementById('slverr').textContent.length > 0", timeout=T)
        pg.fill("#slvname", "standard")
        pg.keyboard.press("Enter")
        pg.wait_for_function("() => /gibt es schon/.test(document.getElementById('slverr').textContent)", timeout=T)
        pg.fill("#slvname", "Wandern")
        pg.locator("input[name=slvsrc][value=empty]").check()
        pg.keyboard.press("Enter")
        pg.wait_for_function("() => !document.querySelector('#slvname')", timeout=T)
        _view_is(pg, "Wandern")
        pg.wait_for_function("() => document.querySelectorAll('.slvws .slvr').length === 2", timeout=T)
        assert _rows(pg) == ["Standard", "Wandern"]
        c = _wait_server(pg, app, lambda c: len(c["views"]) == 2)
        assert [v["name"] for v in c["views"]] == ["Standard", "Wandern"] and c["active"] == "standard"
        assert _wait_server(pg, app, lambda x: len(x["views"]) == 2, "tour-auswertung")["views"][1]["id"] == c["views"][1]["id"]           # beide Dokumente führen dieselben Ansichten
        pg.keyboard.press("Escape")
        pg.wait_for_function(_dlg_open(pg), timeout=T)
        # in „Wandern“ den Abschnitt Fotos ausblenden; „Standard“ bleibt unberührt
        pg.locator('.slit[data-sl="photos"] [data-a=eye]').click()
        pg.wait_for_function("() => !!document.querySelector('.slit[data-sl=photos].sl-dim')", timeout=T)
        pg.locator("#slview").select_option(label="Standard")
        _view_is(pg, "Standard")
        pg.wait_for_function("() => !document.querySelector('.slit[data-sl=photos].sl-dim')", timeout=T)
        pg.locator("#slview").select_option(label="Wandern")
        pg.wait_for_function("() => !!document.querySelector('.slit[data-sl=photos].sl-dim')", timeout=T)
        c = _wait_server(pg, app, lambda c: "photos" in (c["views"][1]["layout"].get("hidden") or []))
        assert not c["views"][0]["layout"].get("hidden")
        # umbenennen
        _open_views(pg)
        _btn(pg, "Umbenennen: Wandern").click()
        pg.wait_for_selector("#slvname", timeout=T)
        pg.fill("#slvname", "Rad")
        pg.keyboard.press("Enter")
        pg.wait_for_function("() => !document.querySelector('#slvname')", timeout=T)
        pg.wait_for_function("() => [...document.querySelectorAll('.slvws .slvnm')].some(e => e.textContent === 'Rad')", timeout=T)
        _view_is(pg, "Rad")
        # duplizieren: Kopie mit gleichem Inhalt, wird angezeigt
        _btn(pg, "Duplizieren: Rad").click()
        _view_is(pg, "Rad (Kopie)")
        pg.wait_for_function("() => document.querySelectorAll('.slvws .slvr').length === 3", timeout=T)
        c = _wait_server(pg, app, lambda c: len(c["views"]) == 3)
        assert "photos" in c["views"][2]["layout"]["hidden"] and c["views"][2]["name"] == "Rad (Kopie)"
        # Standard festlegen
        _btn(pg, "Als Standard festlegen: Rad").click()
        pg.wait_for_function("() => { const r = document.querySelector('.slvr[data-id]:nth-child(2) .slvbd'); return !!r && r.textContent === 'Standardansicht'; }", timeout=T)
        _wait_server(pg, app, lambda c: c["active"] == c["views"][1]["id"])
        # löschen: erst abbrechen, dann bestätigen
        _btn(pg, "Löschen: Rad (Kopie)").click()
        pg.wait_for_selector(".uidlg .uibox.danger", timeout=T)
        pg.get_by_role("button", name="Abbrechen").click()
        pg.wait_for_function("() => !document.querySelector('.uidlg .uibox.danger')", timeout=T)
        assert len(_rows(pg)) == 3
        _btn(pg, "Löschen: Rad (Kopie)").click()
        pg.wait_for_selector(".uidlg .uibox.danger", timeout=T)
        pg.locator(".uidlg .uidanger").click()
        pg.wait_for_function("() => document.querySelectorAll('.slvws .slvr').length === 2", timeout=T)
        _wait_server(pg, app, lambda c: len(c["views"]) == 2)
        _view_is(pg, "Rad") if pg.evaluate("slViewName('tour', SL.view.tour)") == "Rad" else _view_is(pg, "Standard")
        pg.keyboard.press("Escape")
        pg.wait_for_function(_dlg_open(pg), timeout=T)
        pg.locator("#slbar [data-a=done]").click()
        # Neuladen: Ansichten, Standard und die von Hand gewählte Ansicht (Sitzung) bleiben
        pg.locator("#slview").select_option(label="Standard")
        _view_is(pg, "Standard")
        pg.reload()
        pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slview')", timeout=T)
        _view_is(pg, "Standard")
        assert pg.locator("#slview option").all_inner_texts() == ["Standard", "Rad"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    pg = _tour_page(pw, app)                                                             # neue Sitzung: es gilt die Standardansicht „Rad“
    try:
        _view_is(pg, "Rad")
        assert pg.locator("#slview").input_value() == _cont(app, "tour-haupt")["active"]
        pg.goto(f"{app}/#/tour/r3/auswertung")                                           # die Auswertungsseite folgt derselben Ansicht
        pg.wait_for_function("() => { const l = document.querySelector('#tlload'); return !!l && l.hidden; }", timeout=T)
        _view_is(pg, "Rad")
        assert pg.locator("#slview").input_value() == _cont(app, "tour-haupt")["active"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_templates_dialog_adopts_a_template_as_new_editable_view(pw, app):
    pg = _tour_page(pw, app)
    try:
        _edit(pg)
        _open_views(pg)
        _btn(pg, "Aus Vorlage …").click()
        pg.wait_for_selector(".slvt .slcard", timeout=T)
        assert pg.locator(".slvt .slcard h3").all_inner_texts() == ["Wandern", "Radtour / Training", "Kompakt"]
        assert pg.locator(".slvt .slcard svg.slvpv").count() == 3 and "Höchster Punkt" in pg.locator(".slvt .slcard").first.inner_text()
        pg.get_by_role("button", name="Kompakt: Als neue Ansicht übernehmen", exact=True).click()
        pg.wait_for_function("() => !document.querySelector('.slvt')", timeout=T)
        _view_is(pg, "Kompakt")
        pg.wait_for_function("() => !!document.querySelector('#tlw-t-kennzahlen') && !!document.querySelector('.slit[data-sl=photos].sl-dim')", timeout=T)
        c = _wait_server(pg, app, lambda c: len(c["views"]) == 2)
        lay = c["views"][1]["layout"]
        assert [w["type"] for w in lay["widgets"]] == ["kennzahlen"] and set(lay["hidden"]) == {"puls", "wp", "photos", "planist"} and lay["w"]["map"] == "halb"
        assert _wait_server(pg, app, lambda x: len(x["views"]) == 2, "tour-auswertung")["views"][1]["layout"] == {"v": 1}
        assert pg.locator(".slvws .slvnm").all_inner_texts() == ["Standard", "Kompakt"]
        # und danach änderbar; dieselbe Vorlage noch einmal: eindeutiger Name
        pg.keyboard.press("Escape")
        pg.wait_for_function(_dlg_open(pg), timeout=T)
        pg.locator('.slit[data-sl="map"] [data-a=eye]').click()
        _wait_server(pg, app, lambda c: "map" in (c["views"][1]["layout"].get("hidden") or []))
        _open_views(pg)
        _btn(pg, "Aus Vorlage …").click()
        pg.wait_for_selector(".slvt .slcard", timeout=T)
        pg.get_by_role("button", name="Kompakt: Als neue Ansicht übernehmen", exact=True).click()
        _view_is(pg, "Kompakt 2")
        _wait_server(pg, app, lambda c: len(c["views"]) == 3)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    pg = _dash(pw, app)
    try:
        _edit(pg)
        _open_views(pg)
        _btn(pg, "Aus Vorlage …").click()
        pg.wait_for_selector(".slvt .slcard", timeout=T)
        assert pg.locator(".slvt .slcard h3").all_inner_texts() == ["Wanderer", "Training", "Rückblick", "Kompakt", "Mit Hinweisen", "Mit Gruppe"]
        pg.get_by_role("button", name="Wanderer: Als neue Ansicht übernehmen", exact=True).click()
        _view_is(pg, "Wanderer", "uebersicht")
        pg.wait_for_function("() => ['t-ziele','t-meilensteine','t-heatmap','t-letzte','t-bestwerte'].every(i => !!document.getElementById('tlw-' + i))", timeout=T)
        assert pg.evaluate("document.querySelector('#hlast').closest('.sl-dim') !== null")        # nicht aufgeführte Standard-Abschnitte sind ausgeblendet
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_every_template_passes_the_server_validation(pw, app):
    pg = _dash(pw, app)
    try:
        res = pg.evaluate("""async () => {
          const out = [];
          for (const t of SL_TPL) {
            const docs = slTplDocs(t), bad = [];
            for (const i of t.items) { const it = slTplItem(t.fam, i); if (it.type && !slFits(window.SL_WT[it.type], t.fam)) bad.push('Typ ' + it.type); if (!it.type && !SL_REG[t.fam].some(r => r.id === it.id)) bad.push('Abschnitt ' + it.id); }
            for (const [k, d] of Object.entries(docs)) {
              const r = await fetch('/api/layout/' + k, {method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(d)});
              if (!r.ok) bad.push(k + ': ' + r.status + ' ' + await r.text());
              const x = await fetch('/api/layout/check', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(slExportDocLike(t, docs))});
              if (!(await x.json()).ok) bad.push('check ' + k);
            }
            out.push([t.id, t.name, t.desc.length > 40, slTplPreview(t).includes('<rect'), bad]);
          }
          return out;
          function slExportDocLike(t, docs) { return {format: 'meine-touren-ansicht', format_version: 1, page: t.fam, name: t.name, layouts: docs}; }
        }""")
        assert len(res) == 23, res
        for tid, name, desc, prev, bad in res:
            assert desc and prev and not bad, (tid, bad)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_rule_sport_selects_the_view_and_manual_choice_wins_for_the_session(pw, app):
    _put_both(app, [("standard", "Standard", {"v": 1}), ("vw", "Wandern", {"v": 1, "hidden": ["photos"]}), ("vr", "Rad", {"v": 1, "hidden": ["puls"]})])
    pg = _tour_page(pw, app)
    try:
        _view_is(pg, "Standard")
        _edit(pg)
        _open_views(pg)
        assert pg.locator(".slvws select[data-rule]").count() == 2                       # hike und bike: die Sportarten dieses Nutzers
        pg.locator('.slvws select[data-rule="hike"]').select_option(label="Wandern")
        _view_is(pg, "Wandern")                                                          # die Regel gilt sofort für die geöffnete Tour
        pg.locator('.slvws select[data-rule="bike"]').select_option(label="Rad")
        c = _wait_server(pg, app, lambda c: c.get("rules") == {"hike": "vw", "bike": "vr"})
        _wait_server(pg, app, lambda x: x.get("rules") == c["rules"], "tour-auswertung")
        pg.keyboard.press("Escape")
        pg.wait_for_function(_dlg_open(pg), timeout=T)
        pg.locator("#slbar [data-a=done]").click()
        expect(pg.locator("#slview option").first).to_have_text("Automatisch (Wandern)", timeout=T)
        _goto_tour(pg, app, "s0")                                                         # Radtour → „Rad“
        _view_is(pg, "Rad")
        expect(pg.locator("#slview option").first).to_have_text("Automatisch (Rad)", timeout=T)
        expect(pg.locator("#slview")).to_have_value("", timeout=T)
        _goto_tour(pg, app, "r3")
        _view_is(pg, "Wandern")
        # von Hand gewählt: bleibt für die Sitzung, auch bei einer anderen Tour; „Automatisch“ schaltet zurück
        pg.locator("#slview").select_option(label="Standard")
        _view_is(pg, "Standard")
        _goto_tour(pg, app, "s0")
        pg.wait_for_function("() => document.querySelector('#slview').value === 'standard'", timeout=T)
        _view_is(pg, "Standard")
        pg.locator("#slview").select_option(index=0)
        _view_is(pg, "Rad")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    pg = _tour_page(pw, app, tour="s0")                                                  # neue Sitzung: Regel gilt wieder
    try:
        _view_is(pg, "Rad")
    finally:
        pg.browser_.close()
    # Regeln verschwinden mit ihrer Ansicht, die Standardansicht ist der Rückfall
    pg = _tour_page(pw, app)
    try:
        _edit(pg)
        _open_views(pg)
        _btn(pg, "Löschen: Wandern").click()
        pg.locator(".uidlg .uidanger").click()
        c = _wait_server(pg, app, lambda c: len(c["views"]) == 2)
        assert c["rules"] == {"bike": "vr"}
        _view_is(pg, "Standard")
    finally:
        pg.browser_.close()


def _write(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return str(p)


def test_export_file_and_import_valid_invalid_and_replace_only_after_confirmation(pw, app, tmp_path):
    lay = {"v": 1, "order": ["w1", "jahr"], "widgets": [{"id": "w1", "type": "periode", "cfg": {"period": "week"}}], "hidden": ["tag"]}
    _api(app, "uebersicht", "PUT", _box([("standard", "Standard", {"v": 1}), ("vt", "Training-Test", lay)]))
    pg = _dash(pw, app)
    try:
        pg.wait_for_function("() => !!document.querySelector('#slview')", timeout=T)
        _edit(pg)
        _open_views(pg)
        with pg.expect_download(timeout=T) as dl:
            _btn(pg, "Exportieren: Training-Test").click()
        d = dl.value
        assert d.suggested_filename == "ansicht-uebersicht-training-test.json"
        doc = json.loads(open(d.path(), encoding="utf-8").read())
        assert doc["format"] == "meine-touren-ansicht" and doc["format_version"] == 1 and doc["app_version"] == "3.58.0" and doc["page"] == "uebersicht" and doc["name"] == "Training-Test"
        assert list(doc["layouts"]) == ["uebersicht"] and doc["layouts"]["uebersicht"]["widgets"][0]["type"] == "periode" and doc["layouts"]["uebersicht"]["hidden"] == ["tag"]
        # Import gültig: Vorschau, dann als NEUE Ansicht (Name vergeben → nummeriert)
        f = _write(tmp_path, "gut.json", {**doc, "zukunft": 1})
        _btn(pg, "Importieren …").click()
        pg.wait_for_selector("#slimpin", state="attached", timeout=T)
        pg.set_input_files("#slimpin", f)
        pg.wait_for_selector(".slimpok", timeout=T)
        txt = pg.locator(".slimpres").inner_text()
        assert "Training-Test" in txt and "1 Baustein" in txt and "Unbekanntes Feld „zukunft“" in txt and pg.locator("#slimpname").input_value() == "Training-Test"
        assert pg.locator('.slimpres [data-a=repl]').is_visible()                        # gleicher Name vorhanden: ersetzen wird angeboten
        assert len(_cont(app, "uebersicht")["views"]) == 2                                # bis hierher nichts verändert
        pg.locator('.slimpres [data-a=new]').click()
        pg.wait_for_function("() => !document.querySelector('.slimp')", timeout=T)
        _view_is(pg, "Training-Test 2", "uebersicht")
        c = _wait_server(pg, app, lambda c: len(c["views"]) == 3, "uebersicht")
        assert c["views"][2]["layout"]["widgets"][0]["type"] == "periode" and c["views"][1]["layout"] == c["views"][2]["layout"]
        # Ungültiges wird mit klarer Meldung abgelehnt, nichts verändert
        bad = [
            ("kein.json", "{kaputt", "kein gültiges JSON"), ("fremd.json", {"hallo": 1}, "keine Datei mit einer exportierten Ansicht"),
            ("neu.json", {**doc, "format_version": 2}, "neueren Version"), ("tour.json", {**doc, "page": "tour", "layouts": {"tour-haupt": lay}}, "gehört zur Tourseite"),
            ("breite.json", {**doc, "layouts": {"uebersicht": {"w": {"jahr": "riesig"}}}}, "Breite"), ("feld.json", {**doc, "layouts": {"uebersicht": {"evil": 1}}}, "Unbekannte Felder"),
            ("tourbaustein.json", {**doc, "layouts": {"uebersicht": {"widgets": [{"id": "w1", "type": "kennzahlen"}]}}}, "Tour"),
        ]
        _btn(pg, "Importieren …").click()
        pg.wait_for_selector("#slimpin", state="attached", timeout=T)
        for name, content, word in bad:
            pg.set_input_files("#slimpin", _write(tmp_path, name, content))
            pg.wait_for_selector(".slimpbad", timeout=T)
            m = pg.locator(".slimpbad").inner_text()
            assert word in m and "nichts verändert" in m and pg.locator(".slimpok").count() == 0, (name, m)
            pg.wait_for_function("(n) => document.getElementById('slimpf').textContent === n", arg=name, timeout=T)
        assert len(_cont(app, "uebersicht")["views"]) == 3
        # Ersetzen: erst nach Rückfrage
        new = {**doc, "layouts": {"uebersicht": {"v": 1, "order": ["jahr"]}}}
        pg.set_input_files("#slimpin", _write(tmp_path, "ersatz.json", new))
        pg.wait_for_selector(".slimpok", timeout=T)
        pg.locator('.slimpres [data-a=repl]').click()
        pg.wait_for_selector(".uidlg .uibox.danger", timeout=T)
        assert "überschrieben" in pg.locator(".uidlg .uibox.danger").inner_text()
        pg.get_by_role("button", name="Abbrechen").click()
        pg.wait_for_function("() => !document.querySelector('.uidlg .uibox.danger')", timeout=T)
        assert _cont(app, "uebersicht")["views"][1]["layout"] == c["views"][1]["layout"]    # abgebrochen: unverändert
        pg.locator('.slimpres [data-a=repl]').click()
        pg.wait_for_selector(".uidlg .uibox.danger", timeout=T)
        pg.locator(".uidlg .uidanger").click()
        pg.wait_for_function("() => !document.querySelector('.slimp')", timeout=T)
        c2 = _wait_server(pg, app, lambda c: c["views"][1]["layout"].get("order") == ["jahr"], "uebersicht")
        assert len(c2["views"]) == 3 and "widgets" not in c2["views"][1]["layout"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    # Tourseite: eine Tour-Datei lässt sich dort importieren (beide Dokumente), exportiert wird der Inhalt beider
    _put_both(app, [("standard", "Standard", {"v": 1}), ("vw", "Wandern", {"v": 1, "hidden": ["photos"]})])
    _api(app, "tour-auswertung", "PUT", _box([("standard", "Standard", {"v": 1}), ("vw", "Wandern", {"v": 1, "order": ["ana"]})]))
    pg = _tour_page(pw, app)
    try:
        _edit(pg)
        _open_views(pg)
        with pg.expect_download(timeout=T) as dl:
            _btn(pg, "Exportieren: Wandern").click()
        doc = json.loads(open(dl.value.path(), encoding="utf-8").read())
        assert doc["page"] == "tour" and doc["layouts"]["tour-haupt"]["hidden"] == ["photos"] and doc["layouts"]["tour-auswertung"]["order"] == ["ana"]
        _btn(pg, "Importieren …").click()
        pg.wait_for_selector("#slimpin", state="attached", timeout=T)
        doc["name"] = "Aus Datei"
        pg.set_input_files("#slimpin", _write(tmp_path, "tour-ok.json", doc))
        pg.wait_for_selector(".slimpok", timeout=T)
        pg.locator('.slimpres [data-a=new]').click()
        _view_is(pg, "Aus Datei")
        c = _wait_server(pg, app, lambda c: len(c["views"]) == 3)
        assert c["views"][2]["layout"]["hidden"] == ["photos"] and _wait_server(pg, app, lambda x: len(x["views"]) == 3, "tour-auswertung")["views"][2]["layout"]["order"] == ["ana"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_keyboard_and_dialog_focus(pw, app):
    _put_both(app, [("standard", "Standard", {"v": 1}), ("vw", "Wandern", {"v": 1, "hidden": ["photos"]})])
    pg = _tour_page(pw, app)
    try:
        pg.focus("#slview")
        pg.keyboard.press("ArrowDown")                                                   # eine Auswahl per Tastatur schaltet um
        _view_is(pg, "Wandern")
        _edit(pg)
        pg.locator("#slbar [data-a=views]").focus()
        pg.keyboard.press("Enter")
        pg.wait_for_selector(".slvws .slvr", timeout=T)
        assert pg.evaluate("document.activeElement.closest('.slvws') !== null")          # Fokus im Dialog
        for _ in range(40):                                                              # Tab bleibt im Dialog
            pg.keyboard.press("Tab")
            assert pg.evaluate("document.activeElement.closest('.slvws') !== null")
        _btn(pg, "Umbenennen: Wandern").focus()
        pg.keyboard.press("Enter")
        pg.wait_for_selector("#slvname", timeout=T)
        assert pg.evaluate("document.activeElement.id") == "slvname"
        pg.keyboard.press("Escape")                                                      # Esc schließt nur den obersten Dialog, der Fokus kehrt zurück
        pg.wait_for_function("() => !document.querySelector('#slvname')", timeout=T)
        assert pg.locator(".slvws .slvr").count() == 2
        pg.wait_for_function("() => document.activeElement && document.activeElement.dataset.a === 'rename'", timeout=T)
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('.slvws')", timeout=T)
        pg.wait_for_function("() => document.activeElement && document.activeElement.dataset.a === 'views'", timeout=T)
        assert pg.evaluate("getComputedStyle(document.activeElement).outlineStyle") != "none"       # sichtbarer Fokus
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_mobile_390_selector_and_dialogs(pw, app):
    _put_both(app, [("standard", "Standard", {"v": 1}), ("vw", "Sehr lange Bezeichnung für Berg und Tal", {"v": 1, "hidden": ["photos"]})])
    pg = _tour_page(pw, app, width=390, height=844, dpr=2)
    try:
        pg.wait_for_function("() => !!document.querySelector('#slview')", timeout=T)
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert pg.evaluate("document.querySelector('#slview').getBoundingClientRect().height") == 0              # 3.37.1: auf dem Handy statt der Auswahlliste der Knopf „Ansichten“ mit Menü
        pg.locator("#slviews").click()
        pg.wait_for_selector("#slvmenu", timeout=T)
        assert pg.evaluate("() => { const m = document.getElementById('slvmenu'), r = m.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth && [...m.querySelectorAll('[role=menuitemradio]')].length === 2 && [...m.querySelectorAll('button')].every(b => b.getBoundingClientRect().height >= 44); }")
        _shot(pg, "ansichten-390-auswahl.png", full=False)
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.getElementById('slvmenu')", timeout=T)
        _edit(pg)
        _open_views(pg)
        assert pg.evaluate("() => { const b = document.querySelector('.slvws'); return b.scrollWidth <= b.clientWidth + 1 && b.getBoundingClientRect().right <= innerWidth + 1; }")
        assert min(pg.evaluate("() => [...document.querySelectorAll('.slvws .slvbt .slb, .slvws .slvadd .btn')].map(b => b.getBoundingClientRect().height)")) >= 40
        _shot(pg, "ansichten-390-verwalten.png", full=False)
        _btn(pg, "Aus Vorlage …").click()
        pg.wait_for_selector(".slvt .slcard", timeout=T)
        assert pg.evaluate("() => { const b = document.querySelector('.slcat'); return b.scrollWidth <= b.clientWidth + 1; }")
        _shot(pg, "ansichten-390-vorlagen.png", full=False)
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('.slvt')", timeout=T)
        _btn(pg, "Importieren …").click()
        pg.wait_for_selector("#slimpin", state="attached", timeout=T)
        _shot(pg, "ansichten-390-import.png", full=False)
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


VIEW_SELS = [".slvl", ".slvs", ".slvn", ".slvws h2", ".slvin", ".slvr .slvnm", ".slvr .slb", ".slvbd", ".slvbd.on", ".slvadd .btn", ".slvadd .btn.ghost", ".slvrl", ".slvrg select", ".slvws .uifoot .btn"]
TPL_SELS = [".slcat h2", ".slvt .slcard h3", ".slvt .slcard p", ".slvcont", ".slvt .slcard .btn", ".slcatin"]
IMP_SELS = [".slimp h2", ".slimpf", ".slimpres h3", ".slimpres p", ".slimpok .slfs label", ".slimpgo .btn", ".slimphint", ".slimpbad", ".slimpbad li", ".slimp .slcatin"]


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_contrast_and_screenshots_light_and_dark(pw, app, scheme, tmp_path):
    _put_both(app, [("standard", "Standard", {"v": 1}), ("vw", "Wandern", {"v": 1, "hidden": ["photos"]}), ("vr", "Rad", {"v": 1})], rules={"hike": "vw"})
    pg = _tour_page(pw, app, scheme=scheme, dpr=2)
    try:
        pg.wait_for_function("() => !!document.querySelector('#slview')", timeout=T)
        c = pg.evaluate(CONTRAST, [".slvl", ".slvs", "#slopen"])
        assert len(c) >= 3 and not {k: v for k, v in c.items() if v < 4.5}, c
        _shot(pg, f"ansichten-auswahl-{scheme}.png", full=False)
        _edit(pg)
        _open_views(pg)
        c = pg.evaluate(CONTRAST, VIEW_SELS)
        low = {k: round(v, 2) for k, v in c.items() if v < 4.5}
        assert len(c) >= 12 and not low, f"{scheme}: Kontrast unter 4,5:1 (Verwaltung): {low}"
        _shot(pg, f"ansichten-verwalten-{scheme}.png", full=False)
        _btn(pg, "Aus Vorlage …").click()
        pg.wait_for_selector(".slvt .slcard", timeout=T)
        c = pg.evaluate(CONTRAST, TPL_SELS)
        low = {k: round(v, 2) for k, v in c.items() if v < 4.5}
        assert len(c) >= 6 and not low, f"{scheme}: Kontrast unter 4,5:1 (Vorlagen): {low}"
        _shot(pg, f"ansichten-vorlagen-{scheme}.png", full=False)
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('.slvt')", timeout=T)
        _btn(pg, "Importieren …").click()
        pg.wait_for_selector("#slimpin", state="attached", timeout=T)
        doc = {"format": "meine-touren-ansicht", "format_version": 1, "page": "tour", "name": "Wandern", "layouts": {"tour-haupt": {"hidden": ["photos"]}}}
        p = tmp_path / "e.json"
        p.write_text(json.dumps({**doc, "zukunft": 1}), encoding="utf-8")
        pg.set_input_files("#slimpin", str(p))
        pg.wait_for_selector(".slimpok", timeout=T)
        c = pg.evaluate(CONTRAST, IMP_SELS)
        low = {k: round(v, 2) for k, v in c.items() if v < 4.5}
        assert not low, f"{scheme}: Kontrast unter 4,5:1 (Import): {low}"
        _shot(pg, f"ansichten-import-{scheme}.png", full=False)
        p2 = tmp_path / "f.json"
        p2.write_text(json.dumps({**doc, "format_version": 3}), encoding="utf-8")
        pg.set_input_files("#slimpin", str(p2))
        pg.wait_for_selector(".slimpbad", timeout=T)
        c = pg.evaluate(CONTRAST, IMP_SELS)
        low = {k: round(v, 2) for k, v in c.items() if v < 4.5}
        assert not low, f"{scheme}: Kontrast unter 4,5:1 (Import, Fehler): {low}"
        _shot(pg, f"ansichten-import-fehler-{scheme}.png", full=False)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
