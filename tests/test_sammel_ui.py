"""3.13.0 – Oberfläche (Browser, Chromium): einheitlicher Dialog (uiConfirm/uiAlert), Fortschrittsbalken, Auswertungsstand nach dem Neuladen, einklappbare Abschnitte,
Sammel-Korrektur (Vorschau → Bestätigung → Job → Rückgängig). Der Datenbestand ist konstruiert; Hintergrundjobs und Korrektur-Endpunkte sind im Browser nachgebaut
(Antworten per Route), die Vorschau und die Auswertung kommen vom echten Server. Screenshots: Desktop hell/dunkel und 390 px nach MT_SHOTS (Standard: shots5 im Scratchpad)."""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHOTS = Path(os.environ.get("MT_SHOTS", "/tmp/claude-0/-home-claude/f54b925a-8de6-50e7-aa7b-7917dc966b86/scratchpad/shots5"))

SEED = r"""
import sys, os, json, random, time, datetime; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db, config
db.init()
rnd = random.Random(11)
now = int(time.time())
config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
D = {}
for name, model, since, until in (("Amazfit Balance 2", "Balance 2", "2025-01-01", ""), ("Amazfit GTR 4", "GTR 4", "2022-01-01", "2024-12-31")):
    D[name] = db.execute("INSERT INTO devices(name,kind,model,since,until,active,note,zsrc) VALUES(?,'zepp',?,?,?,1,'','')", (name, model, since, until))
def tour(tid, day, name):
    ts = int(datetime.datetime.strptime(day, "%%Y-%%m-%%d").replace(hour=9).timestamp())
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,'hike',?,?,10000,7200,500,500,'t','komoot')", (tid, name, ts, ts + 7200))
    db.execute("INSERT OR REPLACE INTO tour_source(tour_id,src,name) VALUES(?,'zepp','')", (tid,))
def row(tid, dev, day, src, f):
    dem = rnd.uniform(150, 900)
    db.execute("INSERT INTO device_quality(tour_id,device_id,berechnet_am,day,sport,zepp_n,dist_tour_m,dist_dev_m,dist_ratio,dist_plausible,h_src,h_state,up_dev,down_dev,up_dem,down_dem,gps_src,gps_n,gps_jumps,gps_gap_pct,gps_med_dt,gps_pts_km,gps_dec,hr_n,hr_bad_pct) "
               "VALUES(?,?,?,?,'hike',1,10000,9500,0.95,1,?,'ok',?,?,?,?,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL)", (tid, dev, now - 7200, day, src, dem * (1 + f), dem * (1 + f), dem, dem))
names = ["Rundweg am See", "Gipfelrunde Zugspitze", "Waldweg bei Kochel", "Höhenweg Karwendel", "Auf den Wank", "Isarauen Süd", "Herzogstand Überschreitung", "Kesselberg Nordseite"]
for i in range(40):
    day = "2025-%%02d-%%02d" %% (1 + i %% 11, 1 + i %% 27)
    tid = "k%%d" %% i
    tour(tid, day, "%%s %%d" %% (names[i %% len(names)], i))
    summ = i %% 3 == 0
    row(tid, D["Amazfit Balance 2"], day, "summary" if summ else "zepp", rnd.gauss(0.5 if summ else 0.3, 0.12))
for i in range(5):                                       # zugeordnet, aber noch nicht ausgewertet: „offen“
    day = "2025-12-%%02d" %% (1 + i)
    tour("o%%d" %% i, day, "Neue Tour %%d" %% i)
for i in range(30):
    day = "2023-%%02d-%%02d" %% (1 + i %% 11, 1 + i %% 27)
    tid = "g%%d" %% i
    tour(tid, day, "Gipfelrunde Nr. %%d" %% i)
    row(tid, D["Amazfit GTR 4"], day, "zepp", rnd.gauss(0.03, 0.04))
# ein früherer Sammel-Lauf (Tabelle quality_batch)
for i in (1, 2, 4):
    db.execute("INSERT INTO quality_batch(batch_id,tour_id,device_id,method,ts,orig_up,orig_down,new_up,new_down,state) VALUES('b1',?,?,'dem',?,500,500,350,350,'done')", ("k%%d" %% i, D["Amazfit Balance 2"], now - 86400))
"""


def _seed(data):
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data)}], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr


def _wait(url):
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/api/version", timeout=1)
            return
        except Exception:
            time.sleep(0.2)


@pytest.fixture(scope="module")
def app_url(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    d = tmp_path_factory.mktemp("sq")
    _seed(d / "data")
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    env = dict(os.environ, DATA_DIR=str(d / "data"), PHOTOS_DIR=str(d / "p"), BACKUP_DIR=str(d / "b"), MT_NO_SCHEDULER="1")
    pr = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    yield url
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


def _page(pw, app_url, width=1280, height=1000, scheme="light", dpr=1, lang="de", hash_="#/admin?tab=quellen", wait=True):
    b = pw.chromium.launch()
    ctx = b.new_context(locale="de-DE" if lang == "de" else "en-US", viewport={"width": width, "height": height}, color_scheme=scheme, device_scale_factor=dpr)
    ctx.add_init_script(f"try{{localStorage.setItem('lang','{lang}')}}catch(e){{}}")
    pg = ctx.new_page()
    pg.errors, pg.posts = [], []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("console", lambda m: pg.errors.append("CSP: " + m.text) if "Content Security Policy" in m.text else None)
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(app_url) else r.continue_())
    pg.on("request", lambda r: pg.posts.append((r.method, r.url)) if r.method != "GET" else None)
    pg.goto(app_url + hash_)
    if wait:
        pg.wait_for_selector("#devsec .dvcard", timeout=10000)
        pg.wait_for_timeout(300)
    pg.browser_ = b
    return pg


def _shot(pg, name):
    try:
        SHOTS.mkdir(parents=True, exist_ok=True)
        pg.screenshot(path=str(SHOTS / name))
    except OSError:
        pass


def _card(pg, name):
    return pg.locator("#devsec .dvcard", has_text=name)


def _open(pg, name="Balance 2"):
    c = _card(pg, name)
    c.locator("details.dvq > summary").click()
    pg.wait_for_selector("details.dvq[open] .dvqv", timeout=8000)
    return c


def _api(app_url, path):
    return json.loads(urllib.request.urlopen(app_url + path).read())


def _posts(pg, suffix):
    return [u for m, u in pg.posts if u.endswith(suffix)]


# ---------------------------------------------------------------- Dialog-Komponente
def _prep(pg):
    pg.evaluate("""() => { const b = document.createElement('button'); b.id = 'trig'; b.textContent = 'Auslöser'; b.style.cssText = 'position:fixed;left:8px;top:8px;z-index:5'; document.body.appendChild(b); b.focus(); window.R = []; }""")


def test_dialog_roles_focus_trap_keys_inert_and_return(pw, app_url):
    pg = _page(pw, app_url)
    try:
        _prep(pg)
        # einfach: Dialog, Fokus auf OK, Tab bleibt im Dialog, Enter = Ja, Fokus zurück an den Auslöser
        pg.evaluate("(() => { uiConfirm({title: 'Frage', text: 'Erste Zeile\\n\\nZweiter Absatz <b>kein HTML</b>', ok: 'Ja'}).then(v => R.push(v)); })()")
        box = pg.locator(".uidlg .uibox")
        box.wait_for()
        assert box.get_attribute("role") == "dialog" and box.get_attribute("aria-modal") == "true"
        assert pg.evaluate("document.getElementById(document.querySelector('.uibox').getAttribute('aria-labelledby')).textContent") == "Frage"
        assert "Zweiter Absatz" in pg.evaluate("document.getElementById(document.querySelector('.uibox').getAttribute('aria-describedby')).textContent")
        assert pg.locator(".uitext p").count() == 2 and "<b>kein HTML</b>" in pg.inner_text(".uitext") and pg.locator(".uitext b").count() == 0     # Text, kein HTML
        assert pg.evaluate("document.activeElement.textContent") == "Ja"
        # Hintergrund inert, Dialog selbst nicht
        assert pg.evaluate("[...document.body.children].filter(e => !e.classList.contains('uidlg')).every(e => e.inert)") is True
        assert pg.evaluate("document.querySelector('.uidlg').inert") is False
        for _ in range(4):                                                                  # Tab/Shift+Tab verlassen den Dialog nie
            pg.keyboard.press("Tab")
            assert pg.evaluate("!!document.activeElement.closest('.uibox')") is True
        pg.keyboard.press("Shift+Tab"); pg.keyboard.press("Shift+Tab")
        assert pg.evaluate("!!document.activeElement.closest('.uibox')") is True
        pg.evaluate("document.querySelector('.uifoot button:last-child').focus()")
        pg.keyboard.press("Tab")
        assert pg.evaluate("document.activeElement.textContent") == "Abbrechen"           # vom letzten Knopf wieder zum ersten
        pg.evaluate("document.querySelector('.uibox').focus()")                             # Fokus auf dem Rahmen: Enter bestätigt
        pg.keyboard.press("Enter")
        pg.wait_for_function("() => R.length === 1")
        assert pg.evaluate("R") == [True] and pg.locator(".uidlg").count() == 0
        assert pg.evaluate("document.activeElement.id") == "trig"                          # Fokus zurück an den Auslöser
        assert pg.evaluate("[...document.body.children].every(e => !e.inert)") is True     # Hintergrund wieder frei
        # Esc = Abbrechen
        pg.evaluate("(() => { uiConfirm('Noch eine Frage?').then(v => R.push(v)); })()")
        pg.wait_for_selector(".uidlg .uibox")
        assert "Bitte bestätigen" in pg.inner_text(".uibox h2")                             # Standardtitel
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => R.length === 2")
        assert pg.evaluate("R") == [True, False] and pg.evaluate("document.activeElement.id") == "trig"
        # Klick auf OK / Abbrechen / Hintergrund
        for action, want in (("button:last-child", True), ("button:first-child", False)):
            pg.evaluate("(() => { uiConfirm({text: 'x'}).then(v => R.push(v)); })()")
            pg.wait_for_selector(".uidlg .uibox")
            pg.locator(f".uifoot {action}").click()
            pg.wait_for_selector(".uidlg", state="detached")
            assert pg.evaluate("R[R.length - 1]") is want
        pg.evaluate("(() => { uiConfirm({text: 'x'}).then(v => R.push(v)); })()")
        pg.wait_for_selector(".uidlg .uibox")
        pg.mouse.click(5, 500)                                                              # neben den Dialog
        pg.wait_for_selector(".uidlg", state="detached")
        assert pg.evaluate("R[R.length - 1]") is False
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_dialog_danger_focuses_cancel_and_enter_never_confirms_by_itself(pw, app_url):
    pg = _page(pw, app_url)
    try:
        _prep(pg)
        pg.evaluate("(() => { uiConfirm({title: 'Löschen?', text: 'Das lässt sich nicht zurücknehmen.', ok: 'Löschen', danger: true}).then(v => R.push(v)); })()")
        pg.wait_for_selector(".uidlg .uibox")
        assert pg.locator(".uibox").get_attribute("role") == "alertdialog"
        assert pg.evaluate("document.activeElement.textContent") == "Abbrechen"             # Fokus auf der sicheren Wahl
        pg.evaluate("document.querySelector('.uibox').focus()")
        pg.keyboard.press("Enter")                                                          # Enter auf dem Rahmen: nichts passiert
        pg.wait_for_timeout(200)
        assert pg.evaluate("R") == [] and pg.locator(".uidlg").count() == 1
        pg.evaluate("document.querySelector('.uifoot button').focus()")
        pg.keyboard.press("Enter")                                                          # Enter auf „Abbrechen“ = Abbrechen
        pg.wait_for_function("() => R.length === 1")
        assert pg.evaluate("R") == [False]
        pg.evaluate("(() => { uiConfirm({text: 'x', ok: 'Löschen', danger: true}).then(v => R.push(v)); })()")
        pg.wait_for_selector(".uidlg .uibox")
        pg.keyboard.press("Tab")
        assert pg.evaluate("document.activeElement.textContent") == "Löschen"
        pg.keyboard.press("Enter")                                                          # bewusst auf „Löschen“ gewandert: bestätigt
        pg.wait_for_function("() => R.length === 2")
        assert pg.evaluate("R") == [False, True]
        # uiAlert und Warteschlange
        pg.evaluate("(() => { (async () => { await uiAlert({title: 'Fertig', text: 'Eins'}); R.push('a1'); })(); uiAlert('Zwei').then(() => R.push('a2')); })()")
        pg.wait_for_selector(".uidlg .uibox")
        assert pg.locator(".uidlg").count() == 1 and pg.locator(".uibox").get_attribute("role") == "alertdialog" and pg.locator(".uifoot button").count() == 1
        assert "Eins" in pg.inner_text(".uibox")
        pg.keyboard.press("Enter")
        pg.wait_for_function("() => R.includes('a1')")
        pg.wait_for_selector(".uidlg .uibox:has-text('Zwei')")                              # zweiter Dialog erst nach dem ersten
        pg.keyboard.press("Escape")
        pg.wait_for_function("() => R.includes('a2')")
        assert pg.locator(".uidlg").count() == 0 and not pg.errors
    finally:
        pg.browser_.close()


def test_dialog_is_translated_in_english(pw, app_url):
    pg = _page(pw, app_url, lang="en")
    try:
        pg.evaluate("(() => { uiConfirm({title: 'Gerät entfernen?', text: 'Alle Touren dieses Laufs bekommen ihre ursprünglichen Höhen und Höhenmeter zurück. Touren, die du inzwischen selbst geändert oder zurückgenommen hast, bleiben unberührt.', ok: 'Entfernen', danger: true}); })()")
        pg.wait_for_selector(".uidlg .uibox")
        t = pg.inner_text(".uibox")
        assert "Remove device?" in t and "Cancel" in t and "Remove" in t and "original elevations" in t, t
        assert "Gerät" not in t
    finally:
        pg.browser_.close()


# ---------------------------------------------------------------- Auswertungsstand, Abschnitte, Fortschritt
def test_stand_persisted_after_reload_with_bar_and_open_sentence(pw, app_url):
    q = _api(app_url, "/api/devices/quality")
    dv = [d for d in q["devices"] if d["name"] == "Amazfit Balance 2"][0]
    p = dv["progress"]
    assert p["total"] == 45 and p["done"] == 40 and p["open"] == 5 and p["n_summary"] == 14 and p["n_detail"] == 26
    gp = q["progress"]
    assert gp["total"] == 75 and gp["done"] == 70
    pg = _page(pw, app_url)
    try:
        st = pg.locator("#dvqstat")                                                          # Gesamtstand oben: auch nach dem Neuladen
        assert "Noch 5 Touren offen – erneut starten." in st.inner_text() and "70 von 75 Touren" in st.inner_text() and "Zuletzt ausgewertet am" in st.inner_text()
        bar = st.locator("[role=progressbar]")
        assert bar.get_attribute("aria-valuenow") == str(q["progress"]["done"]) and bar.get_attribute("aria-valuemax") == str(q["progress"]["total"]) and bar.get_attribute("aria-label")
        assert st.locator("button", has_text="Weiter auswerten").count() == 1
        c = _open(pg)
        sec = c.locator("details.dvsec[data-sec=stand]")
        assert sec.get_attribute("open") is not None and sec.locator("summary").get_attribute("aria-expanded") == "true"
        t = sec.inner_text()
        assert "Zuletzt ausgewertet am" in t and "40 von 45 Touren" in t and "Noch 5 Touren offen – erneut starten." in t
        assert sec.locator("[role=progressbar]").get_attribute("aria-valuenow") == "40" and sec.locator("button", has_text="Weiter auswerten").count() == 1
        assert c.locator(".dvsplit").inner_text().replace("\n", " ") .count("Touren") == 2
        sp = c.locator(".dvsplit").inner_text()
        assert "Mit Detail (genau)" in sp and "26 Touren" in sp and "Nur Zusammenfassung (grob)" in sp and "14 Touren" in sp
        assert "großzügigere Grenzen" in c.inner_text()
        _shot(pg, "karte-genauigkeit-desktop-hell.png")
        # die andere Karte hat nichts offen
        g = _card(pg, "GTR 4")
        g.locator("details.dvq > summary").click()
        pg.wait_for_selector("details.dvq[open] .dvk", timeout=5000)
        assert "vollständig" in g.locator("details.dvsec[data-sec=stand] summary").inner_text() and g.locator(".dvopen").count() == 0
        assert g.locator("button", has_text="Weiter auswerten").count() == 0 and g.locator("button", has_text="Genauigkeit auswerten").count() == 1
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_sections_toggle_by_keyboard_remember_state_and_show_focus(pw, app_url):
    pg = _page(pw, app_url)
    try:
        c = _open(pg)
        sec = c.locator("details.dvsec[data-sec=auff]")
        s = sec.locator("summary")
        assert sec.get_attribute("open") is not None and s.get_attribute("aria-expanded") == "true"
        s.focus(); pg.keyboard.press("Shift+Tab"); pg.keyboard.press("Tab")                 # per Tastatur auf den Abschnittskopf
        ring = pg.evaluate("(() => { const e = document.activeElement, c = getComputedStyle(e); return [e.tagName, c.outlineStyle, parseFloat(c.outlineWidth)]; })()")
        assert ring[0] == "SUMMARY" and ring[1] != "none" and ring[2] >= 2, ring            # sichtbarer Fokus
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(150)
        assert sec.get_attribute("open") is None and s.get_attribute("aria-expanded") == "false"
        assert pg.evaluate("localStorage.getItem('mt_dvsec_auff')") == "0"
        pg.keyboard.press("Space")
        pg.wait_for_timeout(150)
        assert sec.get_attribute("open") is not None and s.get_attribute("aria-expanded") == "true"
        pg.keyboard.press("Enter")                                                          # wieder zu und neu laden: bleibt zu
        pg.wait_for_timeout(150)
        pg.reload(); pg.wait_for_selector("#devsec .dvcard", timeout=10000)
        c = _card(pg, "Balance 2")
        assert c.locator("details.dvq").get_attribute("open") is not None                  # auch „Genauigkeit“ selbst bleibt aufgeklappt
        sec = c.locator("details.dvsec[data-sec=auff]")
        assert sec.get_attribute("open") is None and sec.locator("summary").get_attribute("aria-expanded") == "false"
        assert c.locator("details.dvsec[data-sec=stand]").get_attribute("open") is not None   # Wichtiges bleibt offen
        pg.evaluate("localStorage.removeItem('mt_dvsec_auff')")
        # Speicher gesperrt: die Seite funktioniert trotzdem
        pg.evaluate("Object.defineProperty(window, 'localStorage', {get() { throw new Error('gesperrt'); }})")
        assert pg.evaluate("dvSecOpen('auff', true)") is True
    finally:
        pg.browser_.close()


JOB_JS = """
window.__poll = 0;
window.__steps = %s;
"""


def _mock_jobs(pg, steps, step_s=2.5):
    """GET /api/jobs liefert nacheinander die gegebenen Stände, zeitgesteuert (der letzte bleibt stehen); state["arm"]() startet die Uhr."""
    state = {"t0": None, "armed": False}

    def arm():
        state["armed"] = True

    def jobs(route):
        req = route.request
        if req.method == "POST":
            route.fulfill(status=200, content_type="application/json", body='{"started":"x"}')
            return
        if state["armed"] and state["t0"] is None:
            state["t0"] = time.time()
        i = 0 if state["t0"] is None else min(int((time.time() - state["t0"]) / step_s), len(steps) - 1)
        route.fulfill(status=200, content_type="application/json", body=json.dumps(steps[i] if state["t0"] is not None else dict(steps[0], running=None, ok=True)))
    pg.route("**/api/jobs", jobs)
    state["arm"] = arm
    return state


def test_progress_bar_while_the_evaluation_runs(pw, app_url):
    pg = _page(pw, app_url, dpr=2)
    try:
        run = {"running": "Genauigkeit der Uhren auswerten", "ok": None, "log": [], "started": 1, "finished": None}
        steps = [dict(run, progress="Genauigkeit 25/700", done=142, total=700), dict(run, progress="Zepp-Details 3/10", done=300, total=700),
                 {"running": None, "ok": True, "progress": "", "done": 700, "total": 700, "log": ["12:00:00 Genauigkeit fertig: 700 Touren"]}]
        st = _mock_jobs(pg, steps)
        st["arm"]()
        pg.locator("#dvqall").click()
        bar = pg.locator("#dvqjob [role=progressbar]")
        bar.wait_for(timeout=5000)
        pg.wait_for_function("() => document.querySelector('#dvqjob .dvjobt') && /142 von 700 Touren geprüft/.test(document.querySelector('#dvqjob .dvjobt').textContent)", timeout=8000)
        assert bar.get_attribute("aria-valuenow") == "142" and bar.get_attribute("aria-valuemax") == "700" and bar.get_attribute("aria-valuetext") == "142 von 700 Touren geprüft"
        assert "Genauigkeit 25/700" in pg.inner_text("#dvqjob")
        assert pg.locator("#dvqjob .dvbar > span").evaluate("e => parseFloat(e.style.width)") == 20
        assert pg.locator("#dvqall").is_disabled()                                           # kein zweiter Start während des Laufs
        _shot(pg, "fortschritt-auswertung-desktop-hell.png")
        pg.wait_for_function("() => document.querySelector('#dvqjob [role=progressbar]')?.getAttribute('aria-valuenow') === '300'", timeout=8000)
        pg.wait_for_selector("#dvqjob", state="detached", timeout=10000)                     # nach dem Ende wird neu gezeichnet: Stand aus der Datenbank
        pg.wait_for_selector("#dvqstat")
        assert _posts(pg, "/api/jobs/dev-quality") and not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ---------------------------------------------------------------- Sammel-Korrektur
def test_batch_dialog_preview_selection_confirm_job_and_undo(pw, app_url):
    pg = _page(pw, app_url, dpr=2)
    try:
        c = _open(pg)
        n_flag = [d for d in _api(app_url, "/api/devices/quality")["devices"] if d["name"] == "Amazfit Balance 2"][0]["flagged_height"]
        before = [u for m, u in pg.posts]
        c.locator("button.dvbatch").click()
        pg.wait_for_selector(".dvbatchbox .bxt", timeout=8000)
        rows = pg.locator(".dvbatchbox .bxt")
        pv = _api(app_url, [d for d in _api(app_url, "/api/devices/quality")["devices"] if d["name"] == "Amazfit Balance 2"][0]["id"].__str__().join(["/api/devices/", "/quality/fix-preview"]))
        assert rows.count() == pv["total"] == n_flag and all(rows.nth(i).is_checked() for i in range(rows.count()))      # alle vorgewählt
        assert [x.strip() for x in pg.locator(".dvbmeth .dvpickrow b").all_inner_texts()] == ["Aus dem Geländemodell berechnen"]   # nur, was zutrifft
        assert "Es passiert nichts, bevor du unten auf" in pg.inner_text(".dvbatchbox") and [u for m, u in pg.posts] == before             # Vorschau ändert nichts
        first = pv["tours"][0]
        assert f"Uhr {first['up_dev']:.0f} m".replace(".", ",") in pg.locator(".dvbrow").first.inner_text().replace("\n", " ") or "Uhr" in pg.locator(".dvbrow").first.inner_text()
        s_all = pg.inner_text("#bxsum")
        assert f"{pv['total']} Touren, ändert den Aufstieg um insgesamt" in s_all and "Der genaue Wert wird beim Korrigieren neu berechnet." in s_all
        assert pg.inner_text("#bxcount") == f"{pv['total']} von {pv['total']} Touren ausgewählt"
        pg.click("#bxnone")
        assert pg.is_disabled("#bxgo") and "Keine Tour ausgewählt." in pg.inner_text("#bxsum") and pg.inner_text("#bxcount").startswith("0 von")
        pg.click("#bxall")
        pg.locator(".dvbatchbox .bxt").nth(0).uncheck(); pg.locator(".dvbatchbox .bxt").nth(1).uncheck()
        assert pg.inner_text("#bxcount") == f"{pv['total'] - 2} von {pv['total']} Touren ausgewählt" and f"{pv['total'] - 2} Touren, ändert" in pg.inner_text("#bxsum")
        want = [pv["tours"][i]["id"] for i in range(2, pv["total"])]
        _shot(pg, "sammel-dialog-desktop-hell.png")
        # Bestätigung im gemeinsamen Dialog; Abbrechen ändert nichts
        pg.click("#bxgo")
        pg.wait_for_selector(".uidlg .uibox")
        t = pg.inner_text(".uibox")
        assert f"{pv['total'] - 2} Touren korrigieren?" in t and "Methode: Aus dem Geländemodell berechnen." in t and "ändert den Aufstieg um insgesamt" in t and "rückgängig machen" in t
        _shot(pg, "sammel-bestaetigung-desktop-hell.png")
        pg.locator(".uidlg .uifoot button", has_text="Abbrechen").click()
        pg.wait_for_selector(".uidlg", state="detached")
        assert not _posts(pg, "/quality/fix") and pg.evaluate("document.activeElement.id") == "bxgo"             # Fokus zurück an den Auslöser
        # bestätigen: Start (nachgebaut) und Fortschritt
        started = {}
        did = pv["device"]["id"]

        def fix(route):
            started["body"] = json.loads(route.request.post_data)
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"started": "x", "n": len(started["body"]["tours"]), "ignored": 0, "cap": 100, "will_run": 7}))
        pg.route(f"**/api/devices/{did}/quality/fix", fix)
        run = {"running": "Auffällige Höhen korrigieren", "ok": None, "log": [], "started": 1, "finished": None}
        st = _mock_jobs(pg, [dict(run, progress="Höhe 2/7 korrigiert", done=2, total=7), dict(run, progress="Höhe 5/7 korrigiert", done=5, total=7),
                        {"running": None, "ok": True, "progress": "", "done": 7, "total": 7, "log": ["12:00:00 Korrigiert: 7 Touren, Aufstieg zusammen 3000 m → 2100 m (-900 m); 1 übersprungen"]}])
        st["arm"]()
        pg.click("#bxgo")
        pg.wait_for_selector(".uidlg .uibox")
        pg.locator(".uidlg .uifoot button", has_text="Korrigieren").click()
        pg.wait_for_selector("#bxjob [role=progressbar]", timeout=5000)
        assert started["body"]["method"] == "dem" and started["body"]["tours"] == want                               # genau die gewählten Touren
        pg.wait_for_function("() => document.querySelector('#bxjob [role=progressbar]')?.getAttribute('aria-valuenow') === '5'", timeout=8000)
        assert pg.locator("#bxjob [role=progressbar]").get_attribute("aria-valuemax") == "7" and "5 von 7 Touren korrigiert" in pg.inner_text("#bxjob")
        _shot(pg, "sammel-fortschritt-desktop-hell.png")
        pg.wait_for_selector("#bxres .dvbdone", timeout=10000)
        res = pg.inner_text("#bxres")
        assert "3 Touren korrigiert" in res and "Aufstieg zusammen −450 m" in res and "1 übersprungen" in res            # Stand aus quality_batch (vorab angelegt)
        assert pg.locator("#bxundo").count() == 1
        _shot(pg, "sammel-ergebnis-desktop-hell.png")
        # Rückgängig: gefährliche Aktion → Fokus auf „Abbrechen“, Esc bricht ab
        pg.click("#bxundo")
        pg.wait_for_selector(".uidlg [role=alertdialog]")
        assert pg.evaluate("document.activeElement.textContent") == "Abbrechen" and "Diesen Sammel-Lauf rückgängig machen?" in pg.inner_text(".uibox")
        pg.keyboard.press("Escape")
        pg.wait_for_selector(".uidlg", state="detached")
        assert not _posts(pg, "/quality/fix-undo")
        undo = {}

        def fixundo(route):
            undo["body"] = json.loads(route.request.post_data)
            route.fulfill(status=200, content_type="application/json", body='{"restored":3,"changed":0}')
        pg.route(f"**/api/devices/{did}/quality/fix-undo", fixundo)
        pg.click("#bxundo")
        pg.wait_for_selector(".uidlg [role=alertdialog]")
        pg.locator(".uidlg .uifoot button", has_text="Rückgängig machen").click()
        pg.wait_for_selector(".uidlg .uibox:has-text('3 Touren wiederhergestellt.')", timeout=5000)
        assert undo["body"] == {"batch": "b1"}
        pg.keyboard.press("Enter")
        pg.wait_for_selector(".uidlg", state="detached")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_card_shows_last_batch_with_undo_and_viewer_sees_no_buttons(pw, app_url):
    pg = _page(pw, app_url)
    try:
        c = _open(pg)
        sec = c.locator("details.dvsec[data-sec=batch]")
        assert sec.get_attribute("open") is not None and "Sammel-Korrektur" in sec.locator("summary").inner_text()
        t = sec.inner_text()
        assert "3 Touren korrigiert (Höhe aus dem Geländemodell), Aufstieg zusammen −450 m." in t and "Nur dieser Lauf wird zurückgenommen" in t
        assert sec.locator(".dvundo").get_attribute("data-batch") == "b1"
        assert c.locator("button.dvbatch").inner_text().strip() == "Alle auffälligen Höhen korrigieren …"
        # Betrachter: JS-Rolle simulieren – weder Sammel-Korrektur noch Auswerten noch Rückgängig
        pg.evaluate("ME.user = Object.assign({}, ME.user, {role: 'viewer'})")
        pg.evaluate("devPanel()")
        pg.wait_for_selector("#devsec .dvcard")
        pg.wait_for_timeout(300)
        c = _card(pg, "Balance 2")
        pg.wait_for_selector("details.dvq[open] .dvqv", timeout=8000)
        assert c.locator("button.dvbatch, .dvundo, .dvqrun, details.dvsec[data-sec=batch]").count() == 0 and "Zuletzt ausgewertet am" in c.inner_text()
        assert pg.locator("#dvqstat button").count() == 0
    finally:
        pg.browser_.close()


# ---------------------------------------------------------------- Handy, Kontrast, Bilder
def _contrast_js(sels):
    return """(sels) => {
      const parse = s => { const m = s.match(/[\\d.]+/g).map(Number); return (s.startsWith('color(') ? m.slice(0, 3).map(v => v * 255) : m.slice(0, 3)); };
      const lin = c => { c /= 255; return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
      const L = ([r, g, b]) => 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
      const lay = c => { const a = c.match(/[\\d.]+/g).map(Number), k = c.startsWith('color(') ? 255 : 1; return [a[0] * k, a[1] * k, a[2] * k, a.length > 3 ? a[3] : 1]; };
      const bg = el => { const ls = []; for (let e = el; e; e = e.parentElement) { const c = getComputedStyle(e).backgroundColor; const l = lay(c); if (l[3] > 0) ls.push(l); if (l[3] >= 1) break; }
        let base = [255, 255, 255]; if (!ls.length || ls[ls.length - 1][3] < 1) base = matchMedia('(prefers-color-scheme: dark)').matches ? [20, 20, 20] : [255, 255, 255];
        for (let i = ls.length - 1; i >= 0; i--) { const [r, g, b, a] = ls[i]; base = [r * a + base[0] * (1 - a), g * a + base[1] * (1 - a), b * a + base[2] * (1 - a)]; } return base; };
      const out = [];
      for (const sel of sels) document.querySelectorAll(sel).forEach((el, i) => { if (i > 1) return; const f = parse(getComputedStyle(el).color), b = bg(el); const l1 = L(f), l2 = L(b); out.push([sel, (Math.max(l1, l2) + .05) / (Math.min(l1, l2) + .05)]); });
      return out;
    }"""


CARD_SELS = [".dvsect", ".dvsec .dvqs.ok", ".dvsec .dvqs.warn", ".dvopen b", ".dvopen .dvh", ".dvqwhen", ".dvsl", ".dvsplit b", ".dvsplith", ".dvbatchl", ".dvbatchbar .dvh", ".dvstatt b", ".dvstatt .mut", ".dvundo", ".dvbatch", ".dvbad .mut"]
DLG_SELS = [".dvbintro", ".dvbmeth b", ".dvbmeth small", ".dvbcount", ".dvbname b", ".dvbname .mut", ".dvbnum", ".dvbnum b", ".dvbnew b", ".dvbsum b", ".dvbsum .dvh", "#bxgo", "#bxno"]
CONF_SELS = [".uibox h2", ".uitext p", ".uifoot .btn", ".uifoot .uidanger"]


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_contrast_at_least_4_5_for_new_parts(pw, app_url, scheme):
    pg = _page(pw, app_url, scheme=scheme, dpr=2)
    try:
        _open(pg)
        res = pg.evaluate(_contrast_js(CARD_SELS), CARD_SELS)
        assert len(res) > 14
        bad = [(s, round(c, 2)) for s, c in res if c < 4.5]
        assert not bad, bad
        _shot(pg, f"karte-genauigkeit-desktop-{'hell' if scheme == 'light' else 'dunkel'}.png")
        _card(pg, "Balance 2").locator("button.dvbatch").click()
        pg.wait_for_selector(".dvbatchbox .bxt")
        res = pg.evaluate(_contrast_js(DLG_SELS), DLG_SELS)
        bad = [(s, round(c, 2)) for s, c in res if c < 4.5]
        assert len(res) > 10 and not bad, bad
        _shot(pg, f"sammel-dialog-desktop-{'hell' if scheme == 'light' else 'dunkel'}.png")
        pg.click("#bxgo")
        pg.wait_for_selector(".uidlg .uibox")
        res = pg.evaluate(_contrast_js(CONF_SELS), CONF_SELS)
        bad = [(s, round(c, 2)) for s, c in res if c < 4.5]
        assert not bad, bad
        _shot(pg, f"bestaetigung-desktop-{'hell' if scheme == 'light' else 'dunkel'}.png")
        pg.keyboard.press("Escape")
        pg.evaluate("(() => { uiConfirm({title: 'Gerät entfernen?', text: 'Wirklich?', ok: 'Entfernen', danger: true}); })()")
        pg.wait_for_selector(".uidlg .uibox.danger")
        res = pg.evaluate(_contrast_js(CONF_SELS), CONF_SELS)
        bad = [(s, round(c, 2)) for s, c in res if c < 4.5]
        assert len(res) >= 4 and not bad, bad
        _shot(pg, f"gefahr-bestaetigung-desktop-{'hell' if scheme == 'light' else 'dunkel'}.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_mobile_390_no_horizontal_scroll_and_touch_targets(pw, app_url):
    pg = _page(pw, app_url, width=390, height=844, dpr=2)
    try:
        c = _open(pg)
        assert pg.evaluate("document.documentElement.scrollWidth") <= 391
        over = pg.evaluate("[...document.querySelectorAll('#devsec .dvq *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('svg')).map(e => e.className || e.tagName).slice(0, 5)")
        assert not over, over
        assert min(s.bounding_box()["height"] for s in c.locator("details.dvsec > summary").all()) >= 44
        _shot(pg, "karte-genauigkeit-390.png")
        c.locator("details.dvsec[data-sec=stand]").scroll_into_view_if_needed()
        _shot(pg, "karte-stand-390.png")
        c.locator("button.dvbatch").click()
        pg.wait_for_selector(".dvbatchbox .bxt")
        assert pg.evaluate("document.documentElement.scrollWidth") <= 391
        box = pg.locator(".dvbatchbox").bounding_box()
        assert box["x"] >= -1 and box["x"] + box["width"] <= 391
        over = pg.evaluate("[...document.querySelectorAll('.dvbatchbox *')].filter(e => e.getBoundingClientRect().right > innerWidth + 1 && !e.closest('.dvbul')).map(e => e.className || e.tagName).slice(0, 5)")
        assert not over, over
        assert min(r.bounding_box()["height"] for r in pg.locator(".dvbrow").all()[:5]) >= 44
        _shot(pg, "sammel-dialog-390.png")
        pg.click("#bxgo")
        pg.wait_for_selector(".uidlg .uibox")
        assert pg.evaluate("document.documentElement.scrollWidth") <= 391
        bb = pg.locator(".uibox").bounding_box()
        assert bb["x"] >= 0 and bb["x"] + bb["width"] <= 390 and all(b.bounding_box()["height"] >= 44 for b in pg.locator(".uifoot .btn").all())
        _shot(pg, "bestaetigung-390.png")
        pg.keyboard.press("Escape")
        pg.evaluate("(() => { uiConfirm({title: 'Diesen Sammel-Lauf rückgängig machen?', text: 'Alle Touren dieses Laufs bekommen ihre ursprünglichen Höhen und Höhenmeter zurück.', ok: 'Rückgängig machen', danger: true}); })()")
        pg.wait_for_selector(".uidlg .uibox.danger")
        _shot(pg, "gefahr-bestaetigung-390.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_mobile_progress_390_and_dark_card(pw, app_url):
    pg = _page(pw, app_url, width=390, height=844, dpr=2, scheme="dark")
    try:
        run = {"running": "Genauigkeit der Uhren auswerten", "ok": None, "log": [], "started": 1, "finished": None}
        _mock_jobs(pg, [dict(run, progress="Genauigkeit 25/700", done=142, total=700)])["arm"]()
        pg.locator("#dvqall").click()
        pg.wait_for_selector("#dvqjob [role=progressbar][aria-valuenow='142']", timeout=8000)
        assert pg.evaluate("document.documentElement.scrollWidth") <= 391
        pg.locator("#dvqjob").scroll_into_view_if_needed()
        _shot(pg, "fortschritt-auswertung-390-dunkel.png")
    finally:
        pg.browser_.close()
