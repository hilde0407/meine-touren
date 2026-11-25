"""3.59.0 Aktivitäten (Oberfläche, Chromium): Verwaltung „Statistik: Aktivitäten zusammenfassen“ (ohne Gruppen jede Aktivität einzeln, Kategorien, ausgegraute
Aktivitäten, Tastatur, Vorschläge, Speichern mit Rückmeldung), „Favoriten-Aktivitäten“ (Stern, Reihenfolge, Speichern), Statistikfilter mit Eintrag „<Name> (zusammengefasst)“,
Abschnitt „Sportarten“ als eine Zeile, Rekorde je Sportart, gelöschte Gruppe in der Adresse ohne Fehler, Prüfen „Schneeschuh-Touren“, Englisch, 390 px."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from tests.helpers_ui import free_port, quiet, set_lang

ROOT = Path(__file__).resolve().parent.parent
pw_api = pytest.importorskip("playwright.sync_api")
expect = pw_api.expect
TL = 15000

SEED = """
import sys, os, time; sys.path.insert(0, {root!r}); os.environ['DATA_DIR'] = {data!r}
from app import db
db.init()
now = int(time.time())
for i, (tid, sp, km) in enumerate([("w1", "hike", 10), ("w2", "hike", 12), ("b1", "mountaineering", 8), ("r1", "touringbicycle", 40), ("m1", "mtb", 30), ("s1", "skitour", 9), ("n1", "hike", 5)]):
    ts = now - (20 + i * 3) * 86400
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
               (tid, "Tour " + tid, sp, ts, ts + 3600, km * 1000, 3600, 100 + i, 100, 48.0, 8.0, "tour_recorded"))
db.execute("INSERT INTO tour_tags(id,tag) VALUES('n1','Schneeschuh')")               # von 3.50.0 zusammengelegt: Wandern mit Schlagwort
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    d = tmp_path_factory.mktemp("sg359")
    data = d / "data"
    out = subprocess.run([sys.executable, "-c", SEED.format(root=str(ROOT), data=str(data))], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr
    port = free_port()
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(d / "p"), BACKUP_DIR=str(d / "bak"))
    pr = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)], cwd=ROOT, env=env,
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(150):
        try:
            urllib.request.urlopen(url + "/api/version", timeout=1)
            break
        except Exception:
            time.sleep(0.2)
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


def _put(url, body):
    rq = urllib.request.Request(url + "/api/stats/gruppen", data=json.dumps(body).encode(), method="PUT", headers={"content-type": "application/json"})
    return json.loads(urllib.request.urlopen(rq, timeout=10).read())


def _sport(url, tid):
    return next(t["sport"] for t in json.loads(urllib.request.urlopen(url + "/api/tours", timeout=10).read()) if t["id"] == tid)


def _get(url):
    return json.loads(urllib.request.urlopen(url + "/api/stats/gruppen", timeout=10).read())


@pytest.fixture
def clean(app):
    _put(app, {"gruppen": []})
    yield app
    _put(app, {"gruppen": []})


def _page(pw, url, w=1280, lang="de"):
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": w, "height": 900}, service_workers="block")
    ctx.add_init_script(f"try {{ localStorage.setItem('lang', '{lang}'); localStorage.setItem('admtab', 'uebersicht'); }} catch (e) {{}}")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    return b, pg, errs


def _admin(pg, url):
    pg.goto(url + "/#/admin?tab=uebersicht")
    pg.wait_for_selector("#sgp .sgg, #sgp .sgnone", timeout=TL)
    quiet(pg, 4000)


def test_verwaltung_gruppen_anlegen_vorschlaege_und_speichern(pw, clean):
    url = clean
    b, pg, errs = _page(pw, url)
    try:
        pg.goto(url + "/#/admin?tab=uebersicht")
        pg.wait_for_selector("#sgp .sgnone", timeout=TL)
        quiet(pg, 4000)
        sec = pg.locator("#sgp")
        expect(sec.locator("h2")).to_have_text("Statistik: Aktivitäten zusammenfassen")
        expect(sec.locator(".sgnone")).to_have_text("Keine Gruppen: Die Statistik zählt jede Aktivität einzeln.")
        assert sec.locator(".sgg").count() == 0
        assert sec.locator(".sgsug:visible").all_inner_texts() == ["Vorschlag: Wandern und Bergtouren", "Vorschlag: Rad (alle)", "Vorschlag: Ski (alle)"]
        # Vorschlag „Rad (alle)“: MTB herauslösen (per Tastatur), danach ist MTB in einer neuen Gruppe frei
        sec.locator('.sgsug[data-v="bike"]').click()
        expect(sec.locator(".sgg")).to_have_count(1)
        expect(sec.locator("#sgok")).to_contain_text("Vorschlag übernommen")
        assert sec.locator('.sgsug[data-v="bike"]').is_hidden()
        assert sec.locator("#sgn0").input_value() == "Rad (alle)" and sec.locator("#sgc0_mtb_easy").is_checked() and sec.locator("#sgc0_e_mtb").is_checked()
        assert sec.locator(".sgg").first.locator(".sgcl").all_inner_texts() == ["Zu Fuß", "Rad", "Winter", "Wasser", "Outdoor & Sonstige"]
        sec.locator("#sgc0_mtb").focus()
        pg.keyboard.press("Space")
        expect(sec.locator("#sgc0_mtb")).not_to_be_checked()
        sec.locator("#sgadd").click()
        expect(sec.locator(".sgg")).to_have_count(2)
        assert pg.evaluate("() => document.activeElement.id") == "sgn1"
        pg.keyboard.type("Gelände")
        assert sec.locator("#sgc1_touringbicycle").is_disabled() and "in „Rad (alle)“" in sec.locator('label[for="sgc1_touringbicycle"]').inner_text()
        sec.locator("#sgc1_mtb").check()
        # Umbenennen: der Hinweis „in …“ zieht mit, ohne Neuaufbau (Fokus bleibt im Feld)
        sec.locator("#sgn0").fill("Rad")
        expect(sec.locator('label[for="sgc1_touringbicycle"] .sgin')).to_have_text("in „Rad“")
        assert pg.evaluate("() => document.activeElement.id") == "sgn0"
        # Prüfung im Browser: zu wenige Sportarten
        sec.locator("#sgsave").click()
        expect(sec.locator("#sgerr")).to_have_text("„Gelände“: Eine Gruppe braucht mindestens 2 Sportarten.")
        sec.locator("#sgc1_climbing").check()
        sec.locator("#sgsave").click()
        expect(sec.locator("#sgok")).to_have_text("Gespeichert ✓ – gilt ab sofort in der Statistik.", timeout=TL)
        d = _get(url)
        assert [g["name"] for g in d["gruppen"]] == ["Rad", "Gelände"] and d["gruppen"][0]["id"] == "bike" and "mtb" not in d["gruppen"][0]["sports"]
        # Vorschlag „Wandern und Bergtouren“ und Löschen
        sec.locator('.sgsug[data-v="foot"]').click()
        expect(sec.locator(".sgg")).to_have_count(3)
        sec.locator(".sgdel").nth(2).click()
        expect(sec.locator(".sgg")).to_have_count(2)
        expect(sec.locator('.sgsug[data-v="foot"]')).to_be_visible()
        assert not errs, errs
    finally:
        b.close()


def test_verwaltung_favoriten(pw, clean):
    url = clean
    b, pg, errs = _page(pw, url)
    try:
        pg.goto(url + "/#/admin?tab=uebersicht")
        pg.wait_for_selector("#favp .favlist li", timeout=TL)
        quiet(pg, 4000)
        sec = pg.locator("#favp")
        assert sec.locator(".favn").all_inner_texts() == ["Wandern", "Laufen", "Radtour", "Skitour", "MTB"]
        expect(sec.locator('.favst[data-k="hike"]')).to_have_attribute("aria-pressed", "true")
        sec.locator('.favst[data-k="kayak"]').click()
        expect(sec.locator('.favst[data-k="kayak"]')).to_have_attribute("aria-pressed", "true")
        assert pg.evaluate("() => document.activeElement.dataset.k") == "kayak"            # Fokus bleibt auf dem Stern
        sec.locator('.favst[data-k="jogging"]').click()
        sec.locator('.favup[data-k="kayak"]').click()
        assert sec.locator(".favn").all_inner_texts() == ["Wandern", "Radtour", "Skitour", "Kajak/Kanu", "MTB"]
        sec.locator('.favup[data-k="kayak"]').focus()
        pg.keyboard.press("Enter")
        assert sec.locator(".favn").all_inner_texts() == ["Wandern", "Radtour", "Kajak/Kanu", "Skitour", "MTB"]
        sec.locator("#favsave").click()
        expect(sec.locator("#favok")).to_have_text("Gespeichert ✓", timeout=TL)
        fav = json.loads(urllib.request.urlopen(url + "/api/aktivitaeten/favoriten", timeout=10).read())["favoriten"]
        assert fav == ["hike", "touringbicycle", "kayak", "skitour", "mtb"]
        # Planung bietet die Favoriten zuerst an
        pg.goto(url + "/#/plan")
        pg.wait_for_selector("#ps", timeout=TL)
        assert pg.eval_on_selector_all("#ps optgroup", "l => l.map(x => x.label)") == ["Favoriten", "Zu Fuß", "Rad", "Winter", "Wasser", "Outdoor & Sonstige"]
        assert pg.eval_on_selector_all("#ps optgroup:first-child option", "l => l.map(x => x.value)") == fav and pg.input_value("#ps") == "hike"
        assert not errs, errs
    finally:
        rq = urllib.request.Request(url + "/api/aktivitaeten/favoriten", data=json.dumps({"favoriten": ["hike", "jogging", "touringbicycle", "skitour", "mtb"]}).encode(),
                                    method="PUT", headers={"content-type": "application/json"})
        urllib.request.urlopen(rq, timeout=10).read()
        b.close()


def test_pruefen_schneeschuh_touren_umstellen_und_zuruecknehmen(pw, clean):
    url = clean
    b, pg, errs = _page(pw, url)
    try:
        pg.goto(url + "/#/check")
        box = pg.locator("#schnee")
        expect(box).to_be_visible(timeout=TL)
        expect(box).to_contain_text("1 Tour heißt noch „Wandern“ und trägt das Schlagwort „Schneeschuh“.")
        box.locator("#snall").click()
        pg.wait_for_selector(".uidlg", timeout=TL)
        pg.locator(".uidlg").get_by_role("button", name="Als Schneeschuh führen").click()
        expect(pg.locator("#snback")).to_have_text("Zurücknehmen (1)", timeout=TL)
        assert pg.locator("#snall").count() == 0
        assert _sport(url, "n1") == "snowshoe"
        pg.locator("#snback").click()
        pg.wait_for_selector(".uidlg", timeout=TL)
        pg.locator(".uidlg").get_by_role("button", name="Zurücknehmen").click()
        expect(pg.locator("#snall")).to_be_visible(timeout=TL)
        assert _sport(url, "n1") == "hike"
        assert not errs, errs
    finally:
        b.close()


def test_statistik_filter_aufteilung_und_rekorde_mit_gruppe(pw, clean):
    url = clean
    gid = _put(url, {"gruppen": [{"name": "Bergwandern", "sports": ["hike", "mountaineering"]}]})["gruppen"][0]["id"]
    b, pg, errs = _page(pw, url)
    try:
        pg.goto(url + "/#/stats")
        chip = pg.locator(f'#sch [data-s="sgrp:{gid}"]')
        expect(chip).to_have_text("Bergwandern (zusammengefasst)", timeout=TL)
        expect(pg.locator('#sch [data-s="hike"]')).to_be_visible()                       # die einzelnen Sportarten bleiben wählbar
        rows = pg.locator('[data-st="sportarten"] .rows, #stc-sportarten .rows').first
        expect(rows).to_contain_text("Bergwandern")
        assert "Bergtour" not in rows.inner_text() and "Wandern\n" not in rows.inner_text()
        chip.click()
        pg.wait_for_function("() => location.hash.includes('sgrp')", timeout=TL)
        quiet(pg, 4000)
        expect(pg.locator(f'#sch [data-s="sgrp:{gid}"]')).to_have_attribute("aria-pressed", "true")
        expect(pg.locator("#stf .sub")).to_have_text("4 Touren")
        # Rekorde: Gruppe als Auswahl und als eine Zeile „Je Sportart“
        pg.goto(url + "/#/records?s=")
        quiet(pg, 4000)
        expect(pg.locator(f'a.chip[href="#/records?s=sgrp%3A{gid}"]')).to_contain_text("Bergwandern (zusammengefasst)")
        expect(pg.locator(".panel", has_text="Je Sportart")).to_contain_text("Bergwandern")
        # gelöschte Gruppe in der Adresse: alle Sportarten, kein Fehler
        _put(url, {"gruppen": []})
        pg.goto(url + "/#/dash")
        pg.goto(url + f"/#/stats?s=sgrp:{gid}")
        pg.reload()
        expect(pg.locator('#sch [data-s=""]')).to_have_attribute("aria-pressed", "true", timeout=TL)
        expect(pg.locator("#stf .sub")).to_have_text("7 Touren")
        assert not errs, errs
    finally:
        b.close()


def test_englisch_und_handy(pw, clean):
    url = clean
    gid = _put(url, {"gruppen": [{"name": "Bergwandern", "sports": ["hike", "mountaineering"]}]})["gruppen"][0]["id"]
    b, pg, errs = _page(pw, url, w=390, lang="en")
    try:
        _admin(pg, url)
        sec = pg.locator("#sgp")
        expect(sec.locator("h2")).to_have_text("Statistics: combine activities")
        expect(sec.locator("#sgsave")).to_have_text("Save groups")
        expect(sec.locator("#sgadd")).to_have_text("Add group")
        assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        box = sec.bounding_box()
        assert box["x"] >= 0 and box["x"] + box["width"] <= 391
        pg.goto(url + "/#/stats")
        expect(pg.locator(f'#sch [data-s="sgrp:{gid}"]')).to_have_text("Bergwandern (combined)", timeout=TL)
        assert not errs, errs
    finally:
        b.close()


def test_tour_sportart_aendern_alle_aktivitaeten(pw, clean):
    url = clean
    b, pg, errs = _page(pw, url)
    try:
        pg.goto(url + "/#/tour/r1")
        pg.wait_for_selector("#esport", state="attached", timeout=TL)
        quiet(pg, 3000)
        pg.locator('.tact-bar [data-g="edit"]').click()
        pg.locator('.tactl [data-e="esport"]').click()
        pg.wait_for_selector("#espsel", timeout=TL)
        assert pg.eval_on_selector_all("#espsel optgroup", "l => l.map(x => x.label)") == ["Favoriten", "Zu Fuß", "Rad", "Winter", "Wasser", "Outdoor & Sonstige"]
        assert pg.input_value("#espsel") == "touringbicycle" and pg.locator("#espsel option").count() == 48
        pg.select_option("#espsel", "mtb_easy")
        pg.locator("#espok").click()
        pg.wait_for_selector("#espsel", state="detached", timeout=TL)
        assert _sport(url, "r1") == "mtb_easy"
        assert not errs, errs
    finally:
        b.close()
        rq = urllib.request.Request(url + "/api/tours/r1/sport", data=json.dumps({"sport": "touringbicycle"}).encode(), method="POST", headers={"content-type": "application/json"})
        urllib.request.urlopen(rq, timeout=10).read()
