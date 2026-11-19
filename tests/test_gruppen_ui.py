"""3.36.0 – Bedienung der Seitenanpassung (Browser, Chromium): Duplizieren, Rückgängig/Wiederholen, Gruppen, Handy-Anordnung, Layoutcode.
Wettlauf-Regel: nach jeder Aktion auf den Zustand warten (wait_for_function/expect, 15 s), vor Prüfungen auf Netzwerk-Ruhe warten, keine festen Schlafzeiten als einzige Synchronisation;
auf-/zuklappbare Elemente werden explizit gesetzt statt angeklickt. Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt (Chromium, dpr 2)."""
import base64
import json
import os
import socket
import subprocess
import sys

import pytest

expect = pytest.importorskip("playwright.sync_api").expect
from tests.test_seitenlayout_ui import ROOT, T, _api, _browser, _dash, _edit, _saved, pw  # noqa: F401
from tests.test_tourseite_ui import CONTRAST, LAUNCH, SEED, _shot, _wait
from tests.helpers_ui import press_until_gone, quiet  # noqa: E402

KEYS = ("tour-haupt", "tour-auswertung", "uebersicht", "statistik")
W = lambda i, t="periode", **c: {"id": i, "type": t, "cfg": c}  # noqa: E731


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    tmp = tmp_path_factory.mktemp("gr")
    data = tmp / "data"
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data)}], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
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


def _page(pw, url, layout=None, **kw):
    if layout is not None:
        _api(url, "uebersicht", "PUT", layout)
    pg = _dash(pw, url, **kw)
    quiet(pg, 5000)
    return pg


def _srv(url, key="uebersicht"):
    return _api(url, key).get("layout") or {}


def _wait_srv(pg, url, pred, key="uebersicht"):
    """Auf den Stand beim Server warten (nicht mit time.sleep: Python schlafend bedient die Routen der Seite nicht)."""
    import time
    end = time.time() + 15
    while time.time() < end:
        d = _srv(url, key)
        if pred(d):
            return d
        pg.wait_for_timeout(200)
    raise AssertionError("Server-Stand nicht erreicht: " + json.dumps(_srv(url, key))[:300])


def _strips(pg):
    return pg.evaluate("() => [...document.querySelectorAll('#main .slit')].map(w => w.dataset.sl)")


def _order_is(pg, ids):
    pg.wait_for_function("(e) => JSON.stringify(SL.present.filter(i => e.includes(i))) === JSON.stringify(e)", arg=ids, timeout=T)


def _btn(pg, id_, a):
    loc = pg.locator(f'.slit[data-sl="{id_}"] [data-a="{a}"]')
    if a in ("dup", "grp", "ungrp") and loc.count() and not loc.first.is_visible():          # schmaler Baustein: Duplizieren und Gruppen stehen im Menü „⋯“
        more = pg.locator(f'.slit[data-sl="{id_}"] .slst .slmorebtn')
        if more.is_visible():
            more.click()
    return loc


def _live(pg):
    return pg.locator("#sllive")


def _done(pg):
    pg.locator("#slbar [data-a=done]").click()
    pg.wait_for_function("() => !document.getElementById('slbar')", timeout=T)


# ------------------------------------------------------------------  Duplizieren  ------------------------------------------------------------------

def test_duplicate_widget_copy_after_original_with_focus_and_limits(pw, app):
    pg = _page(pw, app, {"widgets": [W("wk1", title="Meine Woche", period="month"), W("wk2")], "order": ["wk1", "wk2"]})
    try:
        _edit(pg)
        assert _btn(pg, "zuletzt", "dup").count() == 0 and _btn(pg, "jahr", "dup").count() == 0          # feste Abschnitte: kein Duplizieren
        _btn(pg, "wk1", "dup").click()
        pg.wait_for_function("() => document.querySelectorAll('.slit').length === 8", timeout=T)
        ids = _strips(pg)
        i = ids.index("wk1")
        new = ids[i + 1]
        assert new not in ("wk2", "wk1") and ids[i + 2] == "wk2"                                       # direkt dahinter
        pg.wait_for_function("(n) => document.activeElement && document.activeElement.closest('.slit') && document.activeElement.closest('.slit').dataset.sl === n", arg=new, timeout=T)
        expect(pg.locator(f'.slit[data-sl="{new}"] .slnm')).to_contain_text("Meine Woche (Kopie)", timeout=T)
        _done(pg)
        d = _wait_srv(pg, app, lambda d: len(d.get("widgets", [])) == 3)
        cp = next(w for w in d["widgets"] if w["id"] == new)
        assert cp["type"] == "periode" and cp["cfg"] == {"title": "Meine Woche (Kopie)", "period": "month"}
        assert d["order"].index(new) == d["order"].index("wk1") + 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_duplicate_stops_at_the_widget_limit(pw, app):
    ws = [W("w%02d" % i) for i in range(40)]
    pg = _page(pw, app, {"widgets": ws})
    try:
        _edit(pg)
        _btn(pg, "w00", "dup").click()
        expect(pg.locator(".uibox")).to_contain_text("höchstens 40", timeout=T)
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('.uidlg')", timeout=T)
        assert pg.evaluate("SL.docs.uebersicht.widgets.length") == 40
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Rückgängig und Wiederholen  ------------------------------------------------------------------

def _undo(pg):
    return pg.locator('#slbar [data-a="undo"]')


def _redo(pg):
    return pg.locator('#slbar [data-a="redo"]')


def test_undo_redo_buttons_keyboard_and_announcements(pw, app):
    pg = _page(pw, app, {"widgets": [W("wk1"), W("wk2")], "order": ["zuletzt", "wk1", "wk2"]})
    try:
        _edit(pg)
        expect(_undo(pg)).to_have_attribute("aria-disabled", "true", timeout=T)
        expect(_redo(pg)).to_have_attribute("aria-disabled", "true", timeout=T)
        _btn(pg, "wk1", "down").click()                                                                  # verschieben
        _order_is(pg, ["zuletzt", "wk2", "wk1"])
        _btn(pg, "wk2", "eye").click()                                                                   # ausblenden
        pg.wait_for_function("() => SL.docs.uebersicht.hidden && SL.docs.uebersicht.hidden.includes('wk2')", timeout=T)
        expect(_undo(pg)).to_have_attribute("aria-disabled", "false", timeout=T)
        _undo(pg).click()                                                                                # Ausblenden zurück
        pg.wait_for_function("() => !(SL.docs.uebersicht.hidden || []).includes('wk2')", timeout=T)
        expect(_live(pg)).to_contain_text("Rückgängig:", timeout=T)
        expect(_redo(pg)).to_have_attribute("aria-disabled", "false", timeout=T)
        pg.keyboard.press("Control+Shift+Z")                                                             # wiederholen per Tastatur
        pg.wait_for_function("() => SL.docs.uebersicht.hidden.includes('wk2')", timeout=T)
        expect(_live(pg)).to_contain_text("Wiederholt:", timeout=T)
        pg.keyboard.press("Control+z")
        pg.keyboard.press("Control+z")
        _order_is(pg, ["zuletzt", "wk1", "wk2"])
        expect(_undo(pg)).to_have_attribute("aria-disabled", "true", timeout=T)
        pg.keyboard.press("Control+z")                                                                   # nichts mehr: Ansage, kein Fehler
        expect(_live(pg)).to_contain_text("Nichts zum Rückgängigmachen", timeout=T)
        # eine neue Änderung leert „Wiederholen“
        _btn(pg, "wk2", "up").click()
        _order_is(pg, ["zuletzt", "wk2", "wk1"])
        expect(_redo(pg)).to_have_attribute("aria-disabled", "true", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_undo_ignored_in_input_fields_and_dialogs_and_outside_edit_mode(pw, app):
    pg = _page(pw, app, {"widgets": [W("wk1"), W("wk2")], "order": ["zuletzt", "wk1", "wk2"]})
    try:
        pg.keyboard.press("Control+z")                                                                   # nicht im Bearbeitungsmodus: nichts
        _edit(pg)
        _btn(pg, "wk1", "down").click()
        _order_is(pg, ["zuletzt", "wk2", "wk1"])
        pg.locator("#slbar [data-a=add]").click()
        pg.wait_for_selector("#slq", timeout=T)
        pg.locator("#slq").focus()
        pg.keyboard.press("Control+z")                                                                   # Eingabefeld/Dialog: gilt nicht für die Seite
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('.uidlg')", timeout=T)
        assert pg.evaluate("SL.present.filter(i => i.startsWith('wk')).join()") == "wk2,wk1"
        _done(pg)
        _edit(pg)
        expect(_undo(pg)).to_have_attribute("aria-disabled", "true", timeout=T)                          # Fertig leert den Verlauf
        pg.keyboard.press("Control+z")
        assert pg.evaluate("SL.present.filter(i => i.startsWith('wk')).join()") == "wk2,wk1"
    finally:
        pg.browser_.close()


def test_history_is_limited_to_50_steps_and_discard_clears_it(pw, app):
    pg = _page(pw, app, {"widgets": [W("wk1")]})
    try:
        _edit(pg)
        for _ in range(55):
            _btn(pg, "wk1", "eye").click()
        pg.wait_for_function("() => SL.hist.undo.length === 50", timeout=T)
        for _ in range(60):
            if pg.evaluate("SL.hist.undo.length") == 0:
                break
            _undo(pg).click()
        assert pg.evaluate("SL.hist.undo.length") == 0 and pg.evaluate("SL.hist.redo.length") == 50
        pg.locator("#slbar [data-a=more]").click() if pg.locator("#slbar [data-a=more]").is_visible() else None
        _btn(pg, "wk1", "w").first.click()
        pg.wait_for_function("() => SL.hist.undo.length === 1 && SL.docs.uebersicht.w", timeout=T)
        pg.locator("#slbar [data-a=discard]").click()
        pg.locator(".uibox button:has-text('Verwerfen')").last.click()
        pg.wait_for_function("() => SL.hist.undo.length === 0 && SL.hist.redo.length === 0", timeout=T)
        expect(_undo(pg)).to_have_attribute("aria-disabled", "true", timeout=T)
    finally:
        pg.browser_.close()


def test_undo_covers_add_remove_reset_cfg_and_width(pw, app):
    pg = _page(pw, app, {"widgets": [W("wk1")]})
    try:
        _edit(pg)
        _btn(pg, "wk1", "w").first.click()                                                               # ganze Breite (Standard des Bausteins ist halb)
        pg.wait_for_function("() => (SL.docs.uebersicht.w || {}).wk1 === 'voll'", timeout=T)
        _undo(pg).click()
        pg.wait_for_function("() => !(SL.docs.uebersicht.w || {}).wk1", timeout=T)
        _btn(pg, "wk1", "del").click()
        pg.locator(".uibox button:has-text('Entfernen')").click()
        pg.wait_for_function("() => !(SL.docs.uebersicht.widgets || []).length", timeout=T)
        _undo(pg).click()
        pg.wait_for_function("() => (SL.docs.uebersicht.widgets || []).length === 1", timeout=T)
        pg.wait_for_selector('.slit[data-sl="wk1"]', timeout=T)
        pg.locator("#slbar [data-a=more]").click() if pg.locator("#slbar [data-a=more]").is_visible() else None
        pg.locator("#slbar [data-a=reset]").click()
        pg.locator(".uibox button:has-text('Standard wiederherstellen')").last.click()
        pg.wait_for_function("() => !(SL.docs.uebersicht || {}).widgets", timeout=T)
        _undo(pg).click()
        pg.wait_for_function("() => (SL.docs.uebersicht.widgets || []).length === 1", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Gruppen  ------------------------------------------------------------------

def _to_group(pg, id_, which):
    """Baustein über das Menü einer Gruppe zuweisen: which = 'new' oder Titel der Gruppe."""
    _btn(pg, id_, "grp").click()
    pg.wait_for_selector(".slgl", timeout=T)
    if which == "new":
        pg.locator(".slgl [data-g=new]").click()
    else:
        pg.locator(".slgl button", has_text=which).first.click()
    pg.wait_for_function("() => !document.querySelector('.sldlg')", timeout=T)


def _groups(pg):
    return pg.evaluate("() => (SL.docs.uebersicht.groups || []).map(g => [g.title, g.ids.join(), !!g.closed])")


def test_groups_create_assign_rename_default_state_and_server(pw, app):
    pg = _page(pw, app, {"widgets": [W("wk1"), W("wk2"), W("wk3")], "order": ["zuletzt", "wk1", "wk2", "wk3"]})
    try:
        _edit(pg)
        assert _btn(pg, "wk1", "ungrp").count() == 0
        _to_group(pg, "wk1", "new")
        pg.wait_for_function("() => document.querySelectorAll('#main .slgrp').length === 1", timeout=T)
        assert _groups(pg) == [["", "wk1", False]]
        expect(pg.locator(".slgrp .slgt")).to_have_text("Gruppe 1", timeout=T)
        _to_group(pg, "wk2", "Gruppe 1")
        pg.wait_for_function("() => document.querySelectorAll('#main .slgrp .slit').length === 2", timeout=T)
        assert _groups(pg) == [["", "wk1,wk2", False]]
        _order_is(pg, ["zuletzt", "wk1", "wk2", "wk3"])
        # umbenennen
        pg.locator('.slgst [data-a="gname"]').click()
        pg.fill("#slgname", "Mein Block")
        pg.keyboard.press("Enter")
        pg.wait_for_function("() => !document.querySelector('.sldlg')", timeout=T)
        expect(pg.locator(".slgrp .slgt")).to_have_text("Mein Block", timeout=T)
        expect(pg.locator(".slgrp .slgc")).to_have_text("2 Bausteine", timeout=T)
        # Standard „zu“
        pg.locator('.slgst [data-a="gopen"]').uncheck()
        pg.wait_for_function("() => SL.docs.uebersicht.groups[0].closed === true", timeout=T)
        assert pg.evaluate("document.querySelector('.slgd').open") is True                              # im Bearbeitungsmodus immer offen
        _done(pg)
        d = _wait_srv(pg, app, lambda d: d.get("groups"))
        assert d["groups"][0]["title"] == "Mein Block" and d["groups"][0]["ids"] == ["wk1", "wk2"] and d["groups"][0]["closed"] is True and d["groups"][0]["id"].startswith("grp")
        # Ansicht: Standard zu; Zustand explizit setzen (kein Klick) und je Benutzer merken
        pg.wait_for_function("() => { const d = document.querySelector('.slgd'); return !!d && d.open === false; }", timeout=T)
        pg.evaluate("() => { document.querySelector('.slgd').open = true; }")
        key = pg.evaluate("() => 'mt_slg_' + slUid() + '_' + SL.docs.uebersicht.groups[0].id")
        pg.wait_for_function("(k) => localStorage.getItem(k) === '1'", arg=key, timeout=T)
        pg.reload()
        pg.wait_for_selector("main.home .slgrp", timeout=T)
        pg.wait_for_function("() => document.querySelector('.slgd').open === true", timeout=T)
        pg.evaluate("() => { document.querySelector('.slgd').open = false; }")
        pg.wait_for_function("(k) => localStorage.getItem(k) === '0'", arg=key, timeout=T)
        assert pg.evaluate("document.querySelector('.slgd').open") is False
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_groups_ungroup_keyboard_dissolve_move_and_undo(pw, app):
    pg = _page(pw, app, {"widgets": [W("wk1"), W("wk2"), W("wk3")], "order": ["zuletzt", "wk1", "wk2", "wk3"],
                         "groups": [{"id": "grpaa1", "title": "Block", "ids": ["wk1", "wk2"]}]})
    try:
        _edit(pg)
        pg.wait_for_selector(".slgrp .slit", state="attached", timeout=T)
        # Pfeil runter am Rand der Gruppe: der Baustein verlässt sie
        _grip = lambda i: pg.locator(f'.slit[data-sl="{i}"] .slgrp-none, .slit[data-sl="{i}"] .slgrip')  # noqa: E731
        _grip("wk2").focus()
        pg.keyboard.press("ArrowDown")
        pg.wait_for_function("() => SL.docs.uebersicht.groups[0].ids.join() === 'wk1'", timeout=T)
        expect(_live(pg)).to_contain_text("aus der Gruppe", timeout=T)
        _order_is(pg, ["zuletzt", "wk1", "wk2", "wk3"])
        # Menü: wieder hinein, dann „Aus Gruppe lösen“
        _to_group(pg, "wk3", "Block")
        pg.wait_for_function("() => SL.docs.uebersicht.groups[0].ids.join() === 'wk1,wk3'", timeout=T)
        _btn(pg, "wk3", "ungrp").click()
        pg.wait_for_function("() => SL.docs.uebersicht.groups[0].ids.join() === 'wk1'", timeout=T)
        # Gruppe auflösen: Baustein bleiben, Gruppe weg; Rückgängig bringt sie zurück
        pg.locator('.slgst [data-a="gdel"]').click()
        pg.wait_for_function("() => !SL.docs.uebersicht.groups && !document.querySelector('.slgrp')", timeout=T)
        assert set(_strips(pg)) >= {"wk1", "wk2", "wk3"}
        pg.keyboard.press("Control+z")
        pg.wait_for_function("() => SL.docs.uebersicht.groups && SL.docs.uebersicht.groups[0].ids.join() === 'wk1' && !!document.querySelector('.slgrp')", timeout=T)
        # Mitglied entfernen: auch aus der Gruppe (die leere Gruppe verschwindet)
        _btn(pg, "wk1", "del").click()
        pg.locator(".uibox button:has-text('Entfernen')").click()
        pg.wait_for_function("() => !SL.docs.uebersicht.groups", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_groups_move_as_a_block_and_drag_into_and_out_of_a_group(pw, app):
    pg = _page(pw, app, {"widgets": [W("wk1"), W("wk2"), W("wk3")], "order": ["zuletzt", "wk1", "wk2", "wk3"],
                         "groups": [{"id": "grpaa1", "title": "Block", "ids": ["wk1", "wk2"]}]}, height=2600)           # hohes Fenster: alles im Bild, kein Scrollen beim Ziehen
    try:
        _edit(pg)
        pg.wait_for_selector(".slgrp .slit", state="attached", timeout=T)
        pg.locator('.slgst [data-a="gdown"]').click()                                                    # die Gruppe wandert als ein Block hinter wk3
        _order_is(pg, ["zuletzt", "wk3", "wk1", "wk2"])
        pg.locator('.slgst [data-a="gup"]').click()
        _order_is(pg, ["zuletzt", "wk1", "wk2", "wk3"])
        # wk3 per Zeiger in die Gruppe ziehen
        g = pg.locator('.slit[data-sl="wk3"] .slgrip').bounding_box()
        pg.locator('.slit[data-sl="wk3"]').scroll_into_view_if_needed()
        tgt = pg.locator('.slit[data-sl="wk2"]').bounding_box()
        g = pg.locator('.slit[data-sl="wk3"] .slgrip').bounding_box()
        pg.mouse.move(g["x"] + 20, g["y"] + 20)
        pg.mouse.down()
        pg.mouse.move(tgt["x"] + 60, tgt["y"] + tgt["height"] - 10, steps=8)
        pg.wait_for_function("() => !!document.querySelector('.slgrp.sl-into')", timeout=T)
        pg.mouse.up()
        pg.wait_for_function("() => SL.docs.uebersicht.groups && SL.docs.uebersicht.groups[0].ids.includes('wk3')", timeout=T)
        pg.wait_for_function("() => document.querySelectorAll('#main .slgrp .slit').length === 3", timeout=T)
        # und wieder hinaus (über die Gruppe)
        pg.locator('.slit[data-sl="zuletzt"]').scroll_into_view_if_needed()
        z = pg.locator('.slit[data-sl="zuletzt"]').bounding_box()
        g = pg.locator('.slit[data-sl="wk3"] .slgrip').bounding_box()
        pg.mouse.move(g["x"] + 20, g["y"] + 20)
        pg.mouse.down()
        pg.mouse.move(z["x"] + 60, z["y"] + 20, steps=8)
        pg.mouse.up()
        pg.wait_for_function("() => SL.docs.uebersicht.groups[0].ids.join() === 'wk1,wk2'", timeout=T)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_group_template_and_group_survives_export_and_import_of_a_view(pw, app):
    pg = _page(pw, app)
    try:
        _edit(pg)
        pg.locator("#slbar [data-a=views]").click()
        pg.wait_for_selector(".slvws .slvr", timeout=T)
        pg.locator(".slvws").get_by_role("button", name="Aus Vorlage …", exact=True).click()
        pg.get_by_role("button", name="Mit Gruppe: Als neue Ansicht übernehmen", exact=True).click()
        pg.wait_for_function("() => SL.docs.uebersicht && SL.docs.uebersicht.groups && SL.docs.uebersicht.groups[0].title === 'Rückblick' && SL.docs.uebersicht.groups[0].ids.length === 3", timeout=T)
        pg.wait_for_function("() => document.querySelectorAll('#main .slgrp .slit').length === 3", timeout=T)
        doc = pg.evaluate("() => slExportDoc('uebersicht', SL.view.uebersicht)")
        assert doc["layouts"]["uebersicht"]["groups"][0]["ids"] == ["t-rueckblick", "t-heutevor", "t-rekorde"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Handy-Anordnung  ------------------------------------------------------------------

def test_mobile_arrangement_edit_preview_server_and_effect(pw, app):
    pg = _page(pw, app, {"widgets": [W("wk1"), W("wk2")], "order": ["zuletzt", "wk1", "wk2"]})
    try:
        _edit(pg)
        expect(pg.locator('#slbar [data-a="dev"][data-d="desk"]')).to_have_attribute("aria-pressed", "true", timeout=T)
        pg.locator('#slbar [data-a="dev"][data-d="mob"]').click()
        pg.wait_for_function("() => document.body.classList.contains('sl-dev-mob')", timeout=T)
        w = pg.evaluate("document.getElementById('main').getBoundingClientRect().width")
        assert w <= 402.5, w                                                                               # schmaler Rahmen
        expect(pg.locator("#slbn")).to_contain_text("noch keine eigene Anordnung", timeout=T)
        _btn(pg, "wk2", "up").click()                                                                      # nur die Handy-Reihenfolge ändern
        _order_is(pg, ["zuletzt", "wk2", "wk1"])
        _btn(pg, "wk1", "eye").click()
        pg.wait_for_function("() => SL.docs.uebersicht.mob && SL.docs.uebersicht.mob.hidden.includes('wk1')", timeout=T)
        assert pg.evaluate("SL.docs.uebersicht.order.join()") == "zuletzt,wk1,wk2" and not pg.evaluate("SL.docs.uebersicht.hidden")
        pg.locator('#slbar [data-a="dev"][data-d="desk"]').click()                                         # Desktop: unverändert
        pg.wait_for_function("() => !document.body.classList.contains('sl-dev-mob')", timeout=T)
        _order_is(pg, ["zuletzt", "wk1", "wk2"])
        expect(_btn(pg, "wk1", "eye")).to_have_attribute("aria-pressed", "false", timeout=T)
        _undo(pg).click()                                                                                  # Rückgängig gilt auch für die Handy-Anordnung
        pg.wait_for_function("() => !((SL.docs.uebersicht.mob || {}).hidden || []).includes('wk1')", timeout=T)
        _redo(pg).click()
        pg.wait_for_function("() => ((SL.docs.uebersicht.mob || {}).hidden || []).includes('wk1')", timeout=T)
        _done(pg)
        d = _wait_srv(pg, app, lambda d: d.get("mob"))
        assert [i for i in d["mob"]["order"] if i in ("zuletzt", "wk1", "wk2")] == ["zuletzt", "wk2", "wk1"] and d["mob"]["hidden"] == ["wk1"] and d["order"] == ["zuletzt", "wk1", "wk2"]
        # Wirkung: Desktop unverändert
        pg.wait_for_selector("#tlw-wk1", timeout=T)
        assert pg.evaluate("[...document.querySelectorAll('#main > *')].map(e => e.id).filter(i => i.startsWith('tlw-w')).join()") == "tlw-wk1,tlw-wk2"
    finally:
        pg.browser_.close()
    m = _dash(pw, app, width=390, height=900)                                                              # schmal: die Handy-Anordnung gilt
    try:
        quiet(m, 5000)
        m.wait_for_selector("#tlw-wk2", timeout=T)
        assert m.evaluate("document.documentElement.classList.contains('mob')")
        assert m.evaluate("[...document.querySelectorAll('#main > *')].map(e => e.id).filter(i => i.startsWith('tlw-w')).filter(i => !document.getElementById(i).closest('.sl-off')).join()") == "tlw-wk2"
        assert m.evaluate("document.getElementById('tlw-wk1').classList.contains('sl-off')")
        # auf dem Handy startet der Umschalter bei „Handy“, „zurücksetzen“ entfernt die Anordnung
        m.locator("#slopen").click()
        m.wait_for_selector("#slbar", timeout=T)
        expect(m.locator('#slbar [data-a="dev"][data-d="mob"]')).to_have_attribute("aria-pressed", "true", timeout=T)
        m.locator('#slbar [data-a="mobreset"]').click()
        m.wait_for_function("() => !SL.docs.uebersicht.mob", timeout=T)
        assert not m.errors, m.errors
    finally:
        m.browser_.close()


def test_no_mobile_toggle_effect_without_own_arrangement_and_none_on_the_map(pw, app):
    pg = _page(pw, app, {"widgets": [W("wk1"), W("wk2")], "order": ["zuletzt", "wk2", "wk1"]}, width=390, height=900)
    try:
        pg.wait_for_selector("#tlw-wk2", timeout=T)
        assert pg.evaluate("[...document.querySelectorAll('#main > *')].map(e => e.id).filter(i => i.startsWith('tlw-w')).join()") == "tlw-wk2,tlw-wk1"          # Desktop-Reihenfolge
        pg.goto(app + "/#/map")
        pg.wait_for_selector("#slopen", timeout=T)
        quiet(pg, 5000)
        pg.locator("#slopen").click()
        pg.wait_for_selector("#slbar", timeout=T)
        assert pg.locator("#slbdv").is_hidden()
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Layoutcode  ------------------------------------------------------------------

def _open_views(pg):
    pg.locator("#slopenw #slviews").click() if pg.locator("#slopenw #slviews").is_visible() else pg.locator("#slbar [data-a=views]").click()
    pg.wait_for_selector(".slvws .slvr", timeout=T)


def _mk(layout, page="uebersicht", name="Fremd"):
    d = {"format": "meine-touren-ansicht", "format_version": 1, "page": page, "name": name, "layouts": {page: layout}}
    return "MTA1." + base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")


def test_share_dialog_copy_code_and_link(pw, app):
    pg = _page(pw, app, {"widgets": [W("wk1", title="Zähler ✓")], "groups": [{"id": "grpaa1", "title": "Block", "ids": ["wk1"]}]})
    try:
        pg.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=app)
        _open_views(pg)
        pg.get_by_role("button", name="Teilen …: Standard", exact=True).click()
        pg.wait_for_selector("#slcode", timeout=T)
        code = pg.input_value("#slcode")
        assert code.startswith("MTA1.") and "=" not in code and "+" not in code and "/" not in code
        raw = code[5:]
        doc = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        assert doc["format"] == "meine-touren-ansicht" and doc["page"] == "uebersicht" and doc["layouts"]["uebersicht"]["widgets"][0]["cfg"]["title"] == "Zähler ✓"
        assert "tours" not in json.dumps(doc) and "exported" not in doc
        pg.get_by_role("button", name="Code kopieren", exact=True).click()
        expect(pg.locator("#slcodeok")).to_have_text("Code kopiert", timeout=T)
        assert pg.evaluate("navigator.clipboard.readText()") == code
        pg.get_by_role("button", name="Link kopieren", exact=True).click()
        expect(pg.locator("#slcodeok")).to_have_text("Link kopiert", timeout=T)
        link = pg.evaluate("navigator.clipboard.readText()")
        assert link == f"{app}/#/layoutcode/{code}"
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_import_code_checked_by_server_and_bad_codes_rejected(pw, app):
    pg = _page(pw, app)
    try:
        _edit(pg)
        pg.locator("#slbar [data-a=views]").click()
        pg.wait_for_selector(".slvws .slvr", timeout=T)
        pg.locator(".slvws").get_by_role("button", name="Importieren …", exact=True).click()
        pg.wait_for_selector("#slimpcode", timeout=T)
        pg.get_by_role("button", name="Code prüfen", exact=True).click()                                   # leer
        expect(pg.locator(".slimpbad")).to_contain_text("Bitte zuerst einen Ansichtscode", timeout=T)
        for bad, txt in (("MTA1.@@@", "ungültige Zeichen"), ("hallo", "kein Ansichtscode"), (_mk({"groups": [{"id": "grpa1", "title": "", "ids": ["gibtsnicht"]}]}), "gibt")):
            pg.fill("#slimpcode", bad)
            pg.get_by_role("button", name="Code prüfen", exact=True).click()
            expect(pg.locator(".slimpbad")).to_contain_text(txt, timeout=T)
        assert pg.evaluate("slMaster('uebersicht').views.length") == 1                                       # nichts übernommen
        pg.fill("#slimpcode", "  https://x.example/#/layoutcode/" + _mk({"widgets": [W("wk1")], "groups": [{"id": "grpaa1", "title": "Fremd", "ids": ["wk1", "tag"]}], "mob": {"order": ["tag"]}}, name="Von Oma") + " ")
        pg.get_by_role("button", name="Code prüfen", exact=True).click()
        expect(pg.locator(".slimpok")).to_contain_text("1 Gruppe", timeout=T)
        expect(pg.locator(".slimpok")).to_contain_text("Eigene Handy-Anordnung", timeout=T)
        pg.get_by_role("button", name="Als neue Ansicht importieren", exact=True).click()
        pg.wait_for_function("() => slViewName('uebersicht', SL.view.uebersicht) === 'Von Oma'", timeout=T)
        pg.wait_for_function("() => SL.docs.uebersicht.groups[0].title === 'Fremd' && SL.docs.uebersicht.mob.order[0] === 'tag'", timeout=T)
        pg.keyboard.press("Escape")                                                                         # die Liste der Ansichten schließen
        pg.wait_for_function("() => !document.querySelector('.sldlg')", timeout=T)
        _done(pg)
        _wait_srv(pg, app, lambda d: True)
        c = _api(app, "uebersicht")["container"]
        assert [v["name"] for v in c["views"]] == ["Standard", "Von Oma"] and c["views"][1]["layout"]["groups"][0]["ids"] == ["wk1", "tag"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def _link_dialog(pg, app, name):
    pg.goto(f"{app}/#/layoutcode/" + _mk({"order": ["tag"]}, name=name))
    pg.wait_for_selector("#slimpres .slimpok", timeout=T)
    assert pg.evaluate("location.hash") == "#/dash"
    expect(pg.locator(".slimpok")).to_contain_text(name, timeout=T)
    quiet(pg, 3000)                                                                                     # Dialog fertig aufgebaut (Fokus), erst dann Escape
    press_until_gone(pg, "Escape", ".sldlg")


def test_link_opens_the_page_and_prepares_the_import(pw, app):
    """Link in der laufenden App (Adresszeile/Lesezeichen: nur der Hash ändert sich). Die App ist vorher fertig gestartet – sonst misst der Test den Kaltstart (eigener Test unten)."""
    pg = _browser(pw, app, devs=None)
    try:
        pg.goto(f"{app}/#/dash")
        pg.wait_for_selector("#slopen", timeout=T)
        quiet(pg, 3000)
        _link_dialog(pg, app, "Per Link")
        pg.goto(f"{app}/#/layoutcode/MTA1.kaputt")                                                          # kaputter Code: Fehlermeldung statt Import
        expect(pg.locator("#main")).to_contain_text("Dieser Code kann nicht geöffnet werden", timeout=T)      # nicht nur „irgendeine Karte“: die alte Übersicht hat auch welche
        assert pg.locator(".sldlg").count() == 0
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_link_as_first_page_load_opens_the_import_dialog(pw, app):
    """Kaltstart über den Link (neuer Tab): der Import-Dialog öffnet sich (seit 3.39.0 startet boot() erst nach dem letzten Skript)."""
    pg = _browser(pw, app, devs=None)
    try:
        _link_dialog(pg, app, "Per Link kalt")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_standard_sections_of_the_server_match_the_page_registry(pw, app):
    from app import layout
    pg = _page(pw, app)
    try:
        reg = pg.evaluate("() => Object.fromEntries(Object.entries(SL_REG).map(([k, v]) => [k, v.map(r => r.id)]))")
        assert set(reg["tour"]) == layout.STD_IDS["tour-haupt"]
        for k in ("uebersicht", "statistik", "reise", "reisen", "fotos"):
            assert set(reg[k]) == layout.STD_IDS[k], k
        assert layout.STD_IDS["karte"] == frozenset() and reg["karte"]
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Sprachen, Kontrast, 390 px, Screenshots  ------------------------------------------------------------------

GL = {"widgets": [W("wk1", title="Meine Woche"), W("wk2", period="month"), W("wk3")], "order": ["zuletzt", "wk1", "wk2", "wk3"],
      "groups": [{"id": "grpaa1", "title": "Rückblick", "ids": ["wk1", "wk2"]}]}


def test_new_strings_are_translated(pw, app):
    for loc, want in (("en-US", ["Undo", "Redo", "Arrangement for", "Phone", "Dissolve group", "Rename"]), ("fr-FR", ["Annuler", "Rétablir", "Disposition pour", "Téléphone"]),
                      ("es-ES", ["Deshacer", "Rehacer", "Disposición para", "Móvil"])):
        pg = _page(pw, app, GL, locale=loc)
        try:
            _edit(pg)
            pg.wait_for_function("(w) => w.every(x => document.body.innerText.includes(x))", arg=want[:4], timeout=T)
            if loc == "en-US":
                expect(pg.locator(".slgst [data-a=gdel]")).to_have_text("Dissolve group", timeout=T)
                expect(pg.locator("#slbar [data-a=undo]")).to_contain_text("Undo", timeout=T)
                pg.locator('.slit[data-sl="wk3"] [data-a=grp]').click()
                expect(pg.locator(".sldlg h2")).to_have_text("Choose group", timeout=T)
                expect(pg.locator(".slgl [data-g=new]")).to_have_text("Into a new group", timeout=T)
            assert not pg.errors, pg.errors
        finally:
            pg.browser_.close()


def test_layout_390px_no_overflow_and_contrast_light_and_dark(pw, app):
    for scheme in ("light", "dark"):
        for width in (390, 1280):
            pg = _page(pw, app, GL, width=width, height=900, scheme=scheme)
            try:
                _edit(pg)
                pg.locator('#slbar [data-a="dev"][data-d="mob"]').click()
                pg.wait_for_function("() => document.body.classList.contains('sl-dev-mob')", timeout=T)
                quiet(pg, 5000)
                over = pg.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth")
                assert over <= 1, (scheme, width, over)
                bar = pg.evaluate("(() => { const r = document.getElementById('slbar').getBoundingClientRect(); return [r.left, r.right, innerWidth]; })()")
                assert bar[0] >= 0 and bar[1] <= bar[2] + 1, bar
                small = pg.evaluate("[...document.querySelectorAll('#slbar button, .slgst button')].filter(b => b.offsetParent && (b.getBoundingClientRect().height < 38)).map(b => b.textContent.trim())")
                assert not small, (scheme, width, small)
                c = pg.evaluate(CONTRAST, ["#slbar [data-a=undo]", "#slbar [data-a=redo]", '#slbar [data-d="desk"]', '#slbar [data-d="mob"]', ".slgt", ".slgc", ".slgtag", "#slbn"])
                low = {k: v for k, v in c.items() if v < 4.5}
                assert len(c) >= 6 and not low, (scheme, width, low)
                pg.locator('#slbar [data-a="dev"][data-d="desk"]').click()
                assert not pg.errors, pg.errors
            finally:
                pg.browser_.close()


def _snap(pg, name, sel=None):
    """Bildschirmfoto des sichtbaren Bereichs (Leiste inklusive), optional mit einem Element im Bild."""
    d = os.environ.get("TS_SHOTS")
    if not d:
        return
    if sel:
        pg.locator(sel).first.scroll_into_view_if_needed()
    quiet(pg, 5000)
    os.makedirs(d, exist_ok=True)
    pg.screenshot(path=os.path.join(d, name), timeout=60000)


def test_screenshots_group_mobile_preview_and_code_dialog(pw, app):
    if not os.environ.get("TS_SHOTS"):
        pytest.skip("nur mit TS_SHOTS")
    for scheme in ("light", "dark"):
        for width, h in ((1280, 1000), (390, 900)):
            pg = _page(pw, app, GL, width=width, height=h, scheme=scheme, dpr=2)
            try:
                pg.wait_for_selector(".slgrp", timeout=T)
                pg.evaluate("() => { document.querySelector('.slgd').open = true; }")
                _snap(pg, f"gr-gruppe-{width}-{scheme}.png", ".slgrp")
                _edit(pg)
                _btn(pg, "wk1", "eye").click()
                _undo(pg).click()
                _snap(pg, f"gr-bearbeiten-{width}-{scheme}.png", ".slgrp")
                pg.locator('#slbar [data-a="dev"][data-d="mob"]').click()
                pg.wait_for_function("() => document.body.classList.contains('sl-dev-mob')", timeout=T)
                _btn(pg, "wk3", "up").click()
                quiet(pg, 5000)
                _snap(pg, f"gr-handy-{width}-{scheme}.png", ".slgrp")
                pg.locator('#slbar [data-a="dev"][data-d="desk"]').click()
                pg.locator("#slbar [data-a=views]").click()
                pg.wait_for_selector(".slvws .slvr", timeout=T)
                pg.get_by_role("button", name="Teilen …: Standard", exact=True).click()
                pg.wait_for_selector("#slcode", timeout=T)
                _snap(pg, f"gr-code-{width}-{scheme}.png")
            finally:
                pg.browser_.close()
