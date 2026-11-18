"""3.40.0 „Wiederherstellung in der Oberfläche“ (Chromium): Verwaltung → Sicherung & Zugang → „Sicherung zurückspielen“.
Kompletter Ablauf (Quelle wählen, Vorprüfung, Bestätigung, Ergebnis, Rückweg über die Sicherheitskopie), Upload, Fehlermeldung, 1280 und 390 px, hell und dunkel, Englisch.
Nur Wegwerf-Daten (eigener DATA_DIR/BACKUP_DIR unter tmp). Synchronisation über expect(..., timeout=15000) und wait_for_function mit Pfeilfunktionen; keine festen Pausen.
Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt."""
import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest
from tests.helpers_ui import free_port, press_until_gone, quiet, settled, toggle_details, wait_http

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
pw_api = pytest.importorskip("playwright.sync_api")
expect = pw_api.expect
TL = 15000

SEED = """
import sys, os; sys.path.insert(0, {root!r}); os.environ['DATA_DIR'] = {data!r}
import time
from app import db
db.init()
now = int(time.time())
for i in range(5):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
               ('h%d' % i, 'Wanderung %d' % i, 'hike', now - (10 + 7 * i) * 86400, now - (10 + 7 * i) * 86400 + 100, (10 + i) * 1000, 3.0 * 3600, 300, 300, 48.0, 8.0, 'tour_recorded', 'komoot'))
"""
# Wörter, die nur in einem deutschen Satz stehen (Dateinamen stehen in <code> und werden nicht geprüft)
DE = r"\b(der|die|das|und|nicht|ist|wird|werden|für|mit|auf|noch|oder|kein|keine|Sicherung|Sicherheitskopie|Heute|Vorher|Jetzt|Touren|Strecken|Reisen|Datei|Abbrechen|zurückspielen|Geprüft|bleibt|ersetzt)\b"
SCAN = """([sel, re]) => { const R = new RegExp(re, 'i'), out = [];
  document.querySelectorAll(sel).forEach(root => {
    const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); let n;
    while (n = w.nextNode()) { const p = n.parentElement; if (!p || p.closest('code,pre,script,style')) continue; const t = n.nodeValue.replace(/Meine Touren/g, '').trim(); if (t.length > 2 && R.test(t)) out.push(t.slice(0, 160)); }
  });
  return [...new Set(out)]; }"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    d = tmp_path_factory.mktemp("rs340")
    data, bak = d / "data", d / "bak"
    out = subprocess.run([sys.executable, "-c", SEED.format(root=str(ROOT), data=str(data))], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr
    port = free_port()
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(d / "p"), BACKUP_DIR=str(bak), MT_NO_SCHEDULER="1")
    pr = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    wait_http(url + "/api/version")
    yield {"url": url, "data": data, "bak": bak, "tmp": d}
    pr.terminate()
    try:
        pr.wait(10)
    except subprocess.TimeoutExpired:
        pr.kill(); pr.wait(5)


@pytest.fixture(scope="module")
def pw():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


def _req(app, path, method="GET", body=None):
    r = urllib.request.Request(app["url"] + path, method=method, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(r, timeout=30) as x:
        return json.loads(x.read() or b"{}")


def _plaene(app):
    return sorted(p["name"] for p in _req(app, "/api/plans"))


@pytest.fixture
def clean(app):
    """Ausgangszustand je Test: keine Pläne, keine Sicherungen, kein Upload; danach Stand A (ohne Pläne) als Sicherung und Stand B (zwei Pläne) als „heute“."""
    for p in _req(app, "/api/plans"):
        _req(app, f"/api/plans/{p['id']}", "DELETE")
    for f in app["bak"].glob("*.zip") if app["bak"].exists() else []:
        f.unlink()
    _req(app, "/api/restore/upload", "DELETE")
    name = _req(app, "/api/backup/now", "POST")["name"]
    for n in ("Plan eins", "Plan zwei"):
        _req(app, "/api/plans", "POST", {"name": n, "sport": "hike", "pts": [[48.0, 8.0], [48.01, 8.01]], "km": 2.0, "up": 100, "down": 100, "est_h": 1.0})
    assert _plaene(app) == ["Plan eins", "Plan zwei"]
    return app["bak"] / name


def _page(pw, app, width=1280, height=1000, scheme="light", lang="de"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale={"de": "de-DE", "en": "en-GB"}[lang], viewport={"width": width, "height": height}, color_scheme=scheme, reduced_motion="reduce")
    ctx.add_init_script("try { localStorage.setItem('lang', %r); localStorage.removeItem('admtab'); } catch (e) {}" % lang)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("dialog", lambda d: (pg.errors.append("window-Dialog: " + d.message), d.dismiss()))          # kein window.confirm/alert
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(app["url"]) else r.continue_())
    pg.browser_ = b
    return pg


def _bereich(pg, app):
    """Verwaltung, Reiter mit dem Bereich „Sicherung“; „Sicherung zurückspielen“ aufklappen und auf die geladene Liste warten."""
    pg.goto(app["url"] + "#/admin?tab=sicher")
    pg.wait_for_function("() => !!document.querySelector('#atabs [data-t=sicher]') && !!document.querySelector('#rsd')", timeout=TL)
    t = pg.evaluate("() => document.querySelector('#rsd').closest('.atab').dataset.t")
    pg.click(f"#atabs [data-t={t}]")
    expect(pg.locator("#rsd > summary")).to_be_visible(timeout=TL)
    toggle_details(pg, "#rsd", True)
    pg.wait_for_function("() => !document.querySelector('#rsls .mut') || document.querySelectorAll('#rsls .rsi').length > 0 || /\\S/.test(document.querySelector('#rsls').textContent.replace('Lade …', '').replace('Loading …', ''))", timeout=TL)
    expect(pg.locator("#rsgo")).to_be_visible(timeout=TL)


def _no_hscroll(pg):
    return pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")


def _im_fenster(pg, sel):
    """Element liegt waagerecht ganz im sichtbaren Fenster und sein Inhalt läuft nicht seitlich über."""
    return pg.evaluate("(s) => { const e = document.querySelector(s), r = e.getBoundingClientRect(); return r.left >= 0 && r.right <= window.innerWidth + 0.5 && e.scrollWidth <= e.clientWidth + 1; }", sel)


def _contrast(pg, sel):
    return pg.evaluate("""(sel) => {
      const el = document.querySelector(sel);
      const rgb = c => { const x = document.createElement('canvas').getContext('2d'); x.fillStyle = '#000'; x.fillStyle = c; x.fillRect(0, 0, 1, 1); return [...x.getImageData(0, 0, 1, 1).data]; };
      const lum = ([r, g, b]) => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b); };
      let bg = null;
      for (let e = el; e && !bg; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor); if (c[3] > 250) bg = c; }
      const a = lum(rgb(getComputedStyle(el).color)), b = lum(bg || [255, 255, 255, 255]);
      return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    }""", sel)


def _shot(pg, name):
    d = os.environ.get("TS_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        settled(pg)
        pg.screenshot(path=str(Path(d) / name), timeout=60000)


def _zeile(pg, kopf_zeile):
    """Zahlen einer Tabellenzeile im Dialog: [linke Spalte, rechte Spalte] der Zeile mit dem Index (0 = Touren … 3 = geplante Touren)."""
    return pg.evaluate("(i) => [...document.querySelectorAll('.rsbox .rstab')].filter(t => t.offsetParent !== null)[0].querySelectorAll('tbody tr')[i].innerText.trim().split(/\\s+/).slice(-2)", kopf_zeile)


def _pruefen(pg):
    pg.click("#rsgo")
    expect(pg.locator(".rsbox")).to_be_visible(timeout=TL)
    quiet(pg)


# ------------------------------------------------------------------ kompletter Ablauf, Desktop hell, deutsch ------------------------------------------------------------------
def test_kompletter_ablauf_mit_rueckweg_ueber_die_sicherheitskopie(pw, app, clean):
    pg = _page(pw, app)
    try:
        _bereich(pg, app)
        # Bereich ist einklappbar
        toggle_details(pg, "#rsd", False)
        expect(pg.locator("#rsgo")).to_be_hidden(timeout=TL)
        toggle_details(pg, "#rsd", True)
        zeilen = pg.locator("#rsls .rsi")
        expect(zeilen).to_have_count(1, timeout=TL)
        expect(zeilen.first).to_contain_text(clean.name)
        expect(zeilen.first).to_contain_text("kB")
        expect(pg.locator("#rsgo")).to_be_disabled()                                  # ohne Quelle keine Prüfung
        zeilen.first.locator("input").check()
        expect(pg.locator("#rsgo")).to_be_enabled(timeout=TL)
        _shot(pg, "quelle-1280-hell.png")

        # Vorprüfung
        _pruefen(pg)
        box = pg.locator(".rsbox")
        assert box.get_attribute("role") == "dialog" and box.get_attribute("aria-modal") == "true"
        assert pg.evaluate("() => document.getElementById(document.querySelector('.rsbox').getAttribute('aria-labelledby')).textContent") == "Sicherung zurückspielen"
        assert pg.evaluate("() => !!document.getElementById(document.querySelector('.rsbox').getAttribute('aria-describedby'))")
        assert pg.evaluate("() => document.querySelector('.rsbox').contains(document.activeElement)")                 # Fokus im Dialog, auf „Abbrechen“
        assert pg.evaluate("() => document.activeElement.id") == "rsno"
        assert pg.evaluate("() => [...document.body.children].filter(e => !e.classList.contains('uidlg')).every(e => e.inert)")
        expect(box).to_contain_text("Geprüft: Die Sicherung ist lesbar und vollständig.")
        expect(box).to_contain_text(clean.name)
        expect(box).to_contain_text("(weniger als eine Stunde alt)")
        assert _zeile(pg, 0) == ["5", "5"] and _zeile(pg, 3) == ["0", "2"]             # Touren gleich; geplante Touren: Sicherung 0, heute 2
        for t in ("Das wird ersetzt", "geht verloren", "Fotodateien – sie sind nicht in der Sicherung.", "Zwischenspeicher", "secret.key", "Vorher wird der heutige Stand automatisch gesichert."):
            expect(box).to_contain_text(t)
        expect(pg.locator("#rsyes")).to_be_disabled()                                 # destruktiver Knopf erst nach dem Häkchen
        assert pg.evaluate("() => document.querySelector('#rsok').closest('label').innerText.trim()") == "Ich habe verstanden, dass der heutige Stand ersetzt wird"
        _shot(pg, "vorpruefung-1280-hell.png")

        # Tab bleibt im Dialog
        for _ in range(4):
            pg.keyboard.press("Tab")
            assert pg.evaluate("() => document.querySelector('.rsbox').contains(document.activeElement)")
        # Escape schließt, nichts ist passiert, Fokus zurück auf den Auslöser
        press_until_gone(pg, "Escape", ".rsbox")
        assert pg.evaluate("() => document.activeElement.id") == "rsgo"
        assert pg.evaluate("() => [...document.body.children].every(e => !e.inert)")
        assert _plaene(app) == ["Plan eins", "Plan zwei"] and len(list(app["bak"].glob("*.zip"))) == 1

        # noch einmal: bestätigen
        _pruefen(pg)
        pg.locator("#rsok").check()
        expect(pg.locator("#rsyes")).to_be_enabled(timeout=TL)
        pg.locator("#rsok").uncheck()
        expect(pg.locator("#rsyes")).to_be_disabled(timeout=TL)
        pg.locator("#rsok").check()
        _shot(pg, "bestaetigung-1280-hell.png")
        pg.click("#rsyes")
        expect(pg.locator("#rsdone")).to_be_visible(timeout=TL)
        expect(pg.locator("#rsdone")).to_contain_text("Fertig: Die Sicherung wurde zurückgespielt.")
        assert _zeile(pg, 3) == ["2", "0"]                                            # vorher 2, jetzt 0
        kopie = [f.name for f in app["bak"].glob("*vor-wiederherstellung*.zip")]
        assert len(kopie) == 1
        expect(pg.locator("#rsr")).to_contain_text(kopie[0])
        expect(pg.locator("#rsyes")).to_be_hidden()
        expect(pg.locator("#rsno")).to_have_text("Seite neu laden")
        assert pg.evaluate("() => document.activeElement.id") == "rsno"
        assert _plaene(app) == []
        _shot(pg, "ergebnis-1280-hell.png")
        with pg.expect_navigation(timeout=TL):
            pg.click("#rsno")
        pg.wait_for_function("() => !document.querySelector('.rsbox') && !!document.querySelector('#rsd')", timeout=TL)

        # Rückweg: die Sicherheitskopie steht in derselben Liste, gekennzeichnet, ganz oben
        _bereich(pg, app)
        zeilen = pg.locator("#rsls .rsi")
        expect(zeilen).to_have_count(2, timeout=TL)
        expect(zeilen.first).to_contain_text("Sicherheitskopie vor einer Wiederherstellung")
        expect(zeilen.first).to_contain_text(kopie[0])
        zeilen.first.locator("input").check()
        _pruefen(pg)
        expect(pg.locator(".rsbox")).to_contain_text("Das ist eine Sicherheitskopie, die vor einer früheren Wiederherstellung angelegt wurde.")
        assert _zeile(pg, 3) == ["2", "0"]
        pg.locator("#rsok").check()
        pg.click("#rsyes")
        expect(pg.locator("#rsdone")).to_be_visible(timeout=TL)
        assert _plaene(app) == ["Plan eins", "Plan zwei"]
        assert not (app["data"] / "restore-tmp").exists()
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------ 390 px, dunkel, Englisch, Upload ------------------------------------------------------------------
@pytest.mark.parametrize("width,scheme,lang,tag", [(390, "dark", "de", "390-dunkel"), (390, "dark", "en", "390-dunkel-en"), (1280, "light", "en", "1280-hell-en"), (1280, "dark", "de", "1280-dunkel")])
def test_upload_ablauf_mobil_dunkel_und_englisch(pw, app, clean, width, scheme, lang, tag):
    en = lang == "en"
    hoch = app["tmp"] / "meine-sicherung-zum-hochladen.zip"
    hoch.write_bytes(clean.read_bytes())
    clean.unlink()                                                                    # nur der Upload-Weg: auf dem Server liegt keine Sicherung
    pg = _page(pw, app, width=width, height=844 if width == 390 else 1000, scheme=scheme, lang=lang)
    try:
        _bereich(pg, app)
        if width == 390:
            assert pg.evaluate("() => document.documentElement.classList.contains('mob')")
        expect(pg.locator("#rsls")).to_contain_text("There is no backup on this server yet." if en else "Auf diesem Server liegt noch keine Sicherung.", timeout=TL)
        expect(pg.locator("#rsd > summary")).to_have_text("Restore a backup" if en else "Sicherung zurückspielen")
        expect(pg.locator("#rsgo")).to_have_text("Check backup …" if en else "Sicherung prüfen …")
        expect(pg.locator("#rsgo")).to_be_disabled()
        settled(pg)
        assert _no_hscroll(pg) and _im_fenster(pg, "#rsd")
        assert _contrast(pg, "#rsd > summary") >= 4.5 and _contrast(pg, ".rsup label") >= 4.5
        pg.set_input_files("#rsf", str(hoch))
        expect(pg.locator("#rsgo")).to_be_enabled(timeout=TL)
        _shot(pg, f"quelle-{tag}.png")
        _pruefen(pg)
        box = pg.locator(".rsbox")
        expect(box.locator("h2")).to_have_text("Restore a backup" if en else "Sicherung zurückspielen")
        expect(box).to_contain_text("Checked: the backup is readable and complete." if en else "Geprüft: Die Sicherung ist lesbar und vollständig.")
        expect(box).to_contain_text("meine-sicherung-zum-hochladen.zip")
        expect(box).to_contain_text("(less than an hour old)" if en else "(weniger als eine Stunde alt)")
        expect(box).to_contain_text("In the backup" if en else "In der Sicherung")
        expect(box).to_contain_text("I understand that today’s state will be replaced" if en else "Ich habe verstanden, dass der heutige Stand ersetzt wird")
        expect(pg.locator("#rsyes")).to_have_text("Restore now" if en else "Jetzt zurückspielen")
        expect(pg.locator("#rsno")).to_have_text("Cancel" if en else "Abbrechen")
        expect(pg.locator("#rsyes")).to_be_disabled()
        assert _zeile(pg, 3) == ["0", "2"]
        if en:
            assert pg.evaluate(SCAN, [".rsbox, #rsd", DE]) == []
        settled(pg)
        # passt ins Fenster: kein Querscrollen, Dialog nicht breiter als der Bildschirm, Tabelle läuft nicht über; Kontraste in hell und dunkel
        assert _no_hscroll(pg) and _im_fenster(pg, ".rsbox") and _im_fenster(pg, ".rsbox .rstab")
        for sel in (".rsbox h2", ".rsbox .rsgut", ".rsbox .rshin", ".rsbox .rschk", ".rsbox .rstab tbody th", ".rsbox .rstab thead th", "#rsno"):
            assert _contrast(pg, sel) >= 4.5, (sel, _contrast(pg, sel))
        assert pg.evaluate("() => { const r = document.querySelector('#rsok').getBoundingClientRect(), l = document.querySelector('.rschk').getBoundingClientRect(); return r.width >= 20 && l.height >= 44; }")
        _shot(pg, f"vorpruefung-{tag}.png")
        pg.locator("#rsok").scroll_into_view_if_needed()
        pg.locator("#rsok").check()
        expect(pg.locator("#rsyes")).to_be_enabled(timeout=TL)
        assert pg.evaluate("() => document.querySelector('#rsyes').getBoundingClientRect().height >= 44")
        pg.locator("#rsyes").scroll_into_view_if_needed()
        settled(pg)
        assert _contrast(pg, "#rsyes") >= 4.5
        _shot(pg, f"bestaetigung-{tag}.png")
        pg.click("#rsyes")
        expect(pg.locator("#rsdone")).to_contain_text("Done: the backup has been restored." if en else "Fertig: Die Sicherung wurde zurückgespielt.", timeout=TL)
        expect(pg.locator("#rsno")).to_have_text("Reload page" if en else "Seite neu laden")
        assert _zeile(pg, 3) == ["2", "0"]
        if en:
            assert pg.evaluate(SCAN, [".rsbox", DE]) == []
        settled(pg)
        assert _no_hscroll(pg) and _im_fenster(pg, ".rsbox") and _contrast(pg, "#rsdone") >= 4.5
        _shot(pg, f"ergebnis-{tag}.png")
        assert _plaene(app) == [] and not (app["data"] / "restore-tmp").exists()      # hochgeladene Datei ist weg
        # Escape nach dem Erfolg lädt die Seite ebenfalls neu
        with pg.expect_navigation(timeout=TL):
            pg.keyboard.press("Escape")
        pg.wait_for_function("() => !document.querySelector('.rsbox') && !!document.querySelector('#main')", timeout=TL)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------ Fehlermeldungen ------------------------------------------------------------------
@pytest.mark.parametrize("lang", ["de", "en"])
def test_falsche_dateien_zeigen_verstaendliche_meldung_und_aendern_nichts(pw, app, clean, lang):
    import zipfile
    en = lang == "en"
    kein_zip = app["tmp"] / "urlaub.zip"; kein_zip.write_bytes(b"das ist kein zip" * 50)
    umzug = app["tmp"] / "meine-touren-umzug-2026-01-01_0300.zip"
    with zipfile.ZipFile(umzug, "w") as z:
        z.writestr("UMZUG.txt", "Meine Touren Umzugspaket"); z.writestr("data/system.sqlite", "x")
    pg = _page(pw, app, width=390, height=844, lang=lang)
    try:
        _bereich(pg, app)
        for datei, de, eng in ((kein_zip, "Die Datei ist kein lesbares ZIP (abgeschnitten oder beschädigt).", "The file is not a readable ZIP (truncated or damaged)."),
                               (umzug, "Das ist ein Umzugspaket", "This is a moving package")):
            pg.set_input_files("#rsf", str(datei))
            expect(pg.locator("#rsgo")).to_be_enabled(timeout=TL)
            pg.click("#rsgo")
            err = pg.locator("#rserr")
            expect(err).to_be_visible(timeout=TL)
            expect(err).to_contain_text(eng if en else de, timeout=TL)
            assert err.get_attribute("role") == "alert"
            expect(pg.locator(".rsbox")).to_have_count(0)                             # kein Dialog, also auch keine Bestätigung möglich
            expect(pg.locator("#rsgo")).to_be_disabled(timeout=TL)                    # Auswahl verworfen
            pg.wait_for_function("() => document.querySelector('#rsmsg').textContent === ''", timeout=TL)
            settled(pg)
            assert _no_hscroll(pg) and _im_fenster(pg, "#rserr")
            if en:
                assert pg.evaluate(SCAN, ["#rserr", DE]) == []
        pg.locator("#rserr").scroll_into_view_if_needed()
        _shot(pg, f"fehler-390-{lang}.png")
        # eine Zeile der Liste wählen blendet die Meldung wieder aus
        pg.locator("#rsls .rsi input").first.check()
        expect(pg.locator("#rserr")).to_be_hidden(timeout=TL)
        assert _plaene(app) == ["Plan eins", "Plan zwei"] and len(list(app["bak"].glob("*.zip"))) == 1
        pg.wait_for_function("() => true", timeout=TL)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
    assert not list((app["data"] / "restore-tmp").glob("*/upload-*")) if (app["data"] / "restore-tmp").exists() else True
