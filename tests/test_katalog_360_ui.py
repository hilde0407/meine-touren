"""3.60.0 Aktivitäten (Oberfläche, Chromium): Verwaltung → Reiter „Aktivitäten“ mit drei gleich gestalteten Abschnitten (Katalog nur lesen, Favoriten, Statistik-Gruppen),
Altdaten aus 3.59.0 (Touren mit entfernten Aktivitäten, Favoriten und Gruppen mit entfernten Schlüsseln): Anzeige als Rückfall, Statistik ohne doppelte Einträge,
Favoriten und Gruppen still bereinigt, „Sportart ändern“ wählt den Rückfall vor; Englisch ohne deutsche Reste, 390 px ohne Querrollen."""
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest
from tests.helpers_ui import free_port, quiet

ROOT = Path(__file__).resolve().parent.parent
pw_api = pytest.importorskip("playwright.sync_api")
expect = pw_api.expect
TL = 15000

# Stand wie nach 3.59.0: Touren und Einstellungen mit Schlüsseln, die es seit 3.60.0 nicht mehr gibt
SEED = """
import sys, os, time, json; sys.path.insert(0, {root!r}); os.environ['DATA_DIR'] = {data!r}
from app import db
db.init()
now = int(time.time())
for i, (tid, sp, km) in enumerate([("w1", "hike", 10), ("d1", "dogwalk", 4), ("g1", "golf", 3), ("s1", "sup", 6), ("c1", "commute", 20), ("r1", "touringbicycle", 30), ("o1", "other", 2)]):
    ts = now - (20 + i * 2) * 86400
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (tid, "Tour " + tid, sp, ts, ts + 3600, km * 1000, 3600, 100 + i, 100, 48.0, 8.0, "tour_recorded", "local"))
db.put("fav_sports", json.dumps(["golf", "hike", "sup", "rafting"]))
db.put("stat_gruppen", json.dumps([{{"id": "geh", "name": "Gehen", "sports": ["hike", "dogwalk", "walk"]}}, {{"id": "nass", "name": "Nass", "sports": ["sup", "golf"]}}]))
"""
DE = r"\\b(der|die|das|und|nicht|ist|wird|werden|für|mit|auf|noch|oder|kein|keine|Aktivitäten|Aktivität|Sportarten|Touren|Frühere|Sonstiges|Wandern|Favoriten|Gruppe|Gruppen|speichern)\\b"
SCAN = """([sel, re]) => { const R = new RegExp(re, 'i'), out = [];
  document.querySelectorAll(sel).forEach(root => { const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); let n;
    while (n = w.nextNode()) { const p = n.parentElement; if (!p || p.closest('code,pre,script,style,option,.sgn')) continue; const t = n.nodeValue.trim(); if (t.length > 2 && R.test(t)) out.push(t.slice(0, 120)); } });
  return [...new Set(out)]; }"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    d = tmp_path_factory.mktemp("kat360")
    data = d / "data"
    out = subprocess.run([sys.executable, "-c", SEED.format(root=str(ROOT), data=str(data))], capture_output=True, text=True, cwd=ROOT, env=dict(os.environ, DATA_DIR=str(data)))
    assert out.returncode == 0, out.stderr
    port = free_port()
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(d / "p"), BACKUP_DIR=str(d / "bak"), MT_NO_SCHEDULER="1")
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


def _tours(url):
    return {t["id"]: t["sport"] for t in json.loads(urllib.request.urlopen(url + "/api/tours", timeout=10).read())}


def _page(pw, url, w=1280, lang="de"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale={"de": "de-DE", "en": "en-GB"}[lang], viewport={"width": w, "height": 900}, service_workers="block")
    ctx.add_init_script(f"try {{ localStorage.setItem('lang', '{lang}'); localStorage.removeItem('admtab'); }} catch (e) {{}}")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    return b, pg, errs


def _aktivitaeten(pg, url, tab="sportarten"):
    pg.goto(url + "/#/admin?tab=" + tab)
    pg.wait_for_selector("#katp .katit", timeout=TL)
    pg.wait_for_selector("#favp .favlist li", timeout=TL)
    pg.wait_for_selector("#sgp .sgg, #sgp .sgnone", timeout=TL)
    quiet(pg, 4000)


def test_reiter_aktivitaeten_drei_abschnitte_und_altdaten(pw, app):
    vorher = _tours(app)
    b, pg, errs = _page(pw, app)
    try:
        _aktivitaeten(pg, app, "aktivitaeten")                                     # alte Adresse aus 3.60.0: Alias auf „sportarten“
        assert "tab=sportarten" in pg.url
        tab = pg.locator('.atab[data-t="sportarten"]')
        expect(tab).to_be_visible()
        expect(pg.locator('#atabs [data-t="sportarten"]')).to_have_attribute("aria-selected", "true")
        assert tab.locator(":scope > .gbody > *").evaluate_all("l => l.map(e => e.id)") == ["katp", "favp", "sgp"]
        assert tab.locator(".gbody > * > h2").all_inner_texts() == ["Sportarten-Katalog", "Favoriten-Sportarten", "Statistik-Gruppen"]
        # einheitliche Optik: gleiche Kartenränder und Überschriftengröße, gleiche Kategorie-Beschriftung in allen drei Abschnitten
        st = pg.evaluate("""() => [...document.querySelectorAll('.atab[data-t=sportarten] .gbody > *')].map(c => [getComputedStyle(c).borderTopWidth, getComputedStyle(c).borderRadius,
            getComputedStyle(c.querySelector(':scope > h2')).fontSize])""")
        assert len({tuple(x) for x in st}) == 1, st
        kat = ["Zu Fuß", "Rad", "Winter", "Wasser", "Outdoor und Sonstige"]
        assert pg.locator("#katp .sgcl").all_inner_texts() == kat and pg.locator("#favp .sgcl").all_inner_texts() == kat
        # Katalog: 29 Aktivitäten mit Symbol und Farbe, nur lesen
        assert pg.locator("#katp .katit").count() == 29 and pg.locator("#katp button, #katp input").count() == 0
        assert pg.locator('#katp .katit[data-k="snowshoe"]').evaluate("e => e.closest('.sgcat').querySelector('.sgcl').textContent") == "Winter"
        assert pg.locator('#katp .katit[data-k="mtb"] .katn').inner_text() == "Mountainbike" and pg.locator('#katp .katit[data-k="mountaineering"] .katn').inner_text() == "Bergsteigen"
        assert pg.evaluate("() => getComputedStyle(document.querySelector('#katp .katit[data-k=kayak] .katdot')).backgroundColor !== 'rgba(0, 0, 0, 0)'")
        # 3.67.0: kein Abschnitt „Frühere Sportarten“ mehr; der Rückfall bleibt (Zählung im Katalog über sport_alt)
        assert pg.locator('#katp details, #katp .katfr').count() == 0
        # Favoriten: entfernte Schlüssel still weg, Reihenfolge bleibt
        assert pg.locator("#favp .favn").all_inner_texts() == ["Wandern", "Rafting"]
        assert pg.locator("#favp .favst").count() == 29
        pg.locator("#favstd").click()                                                       # 3.61.0: „Standard wiederherstellen“ fragt nach und speichert gleich
        pg.locator(".uidlg .uifoot button", has_text="Standard wiederherstellen").click()
        expect(pg.locator("#favok")).to_have_text("Standard wiederhergestellt", timeout=TL)
        assert pg.locator("#favp .favn").all_inner_texts() == ["Wandern", "Laufen", "Radtour", "Skitour", "Mountainbike"]
        rq = urllib.request.Request(app + "/api/aktivitaeten/favoriten", data=json.dumps({"favoriten": ["hike", "rafting"]}).encode(), method="PUT",
                                    headers={"content-type": "application/json"})                    # Ausgangszustand für die folgenden Tests (gespeichert ist jetzt der Standard)
        urllib.request.urlopen(rq, timeout=10).read()
        # Statistik-Gruppen: „Gehen“ ohne Gassigehen, „Nass“ (nur entfernte) entfällt
        assert pg.locator("#sgp .sgg").count() == 1 and pg.locator("#sgn0").input_value() == "Gehen"
        assert pg.locator("#sgc0_hike").is_checked() and pg.locator("#sgc0_walk").is_checked() and pg.locator("#sgc0_dogwalk").count() == 0
        # die Abschnitte speichern selbst: keine zweite Speichern-Leiste auf diesem Reiter, auf den anderen schon
        assert not pg.locator("#save").is_visible()
        pg.click('#atabs [data-t="allgemein"]')
        assert pg.locator("#save").is_visible() and pg.locator('.atab[data-t="allgemein"] #homep').count() == 1
        assert not errs, errs
    finally:
        b.close()
    assert _tours(app) == vorher                                                     # die Touren bleiben unverändert


def test_anzeige_statistik_und_sportart_aendern_mit_rueckfall(pw, app):
    b, pg, errs = _page(pw, app)
    try:
        pg.goto(app + "/#/dash")
        pg.wait_for_function("() => typeof TOURS !== 'undefined' && TOURS.length === 7 && !!BY.g1 && !!BY.d1", timeout=TL)      # 3.71.1: BY wird erst nach TOURS gefüllt (Wettlauf)
        r = pg.evaluate("""() => ({g: [BY.g1.sport, BY.g1.sport_alt, sName('golf'), sIcon('golf')], d: [BY.d1.sport, sName('dogwalk')], s: sName('sup'),
            key: sgKey('dogwalk'), fav: FAV, grp: SGRP.map(g => g.sports), fam: sportGrp('commute'), opts: flSportOptions().map(o => o[0])})""")
        assert r["g"] == ["other", "golf", "Sonstiges", "📍"] and r["d"] == ["walk", "Spazieren / Gehen"] and r["s"] == "Kajak / Kanu"
        assert r["key"] == "sgrp:geh" and r["fav"] == ["hike", "rafting"] and r["grp"] == [["hike", "walk"]] and r["fam"] == "bike"
        assert len(r["opts"]) == len(set(r["opts"])) and "golf" not in r["opts"] and "dogwalk" not in r["opts"] and "other" in r["opts"]
        # Statistik: Sportarten-Chips ohne entfernte Schlüssel und ohne doppeltes „Sonstiges“
        pg.goto(app + "/#/stats")
        pg.wait_for_selector("#sch [data-s]", timeout=TL)
        quiet(pg, 3000)
        chips = pg.eval_on_selector_all("#sch [data-s]", "l => l.map(x => x.dataset.s)")
        names = pg.eval_on_selector_all("#sch [data-s]", "l => l.map(x => x.textContent.trim())")
        assert "golf" not in chips and "sup" not in chips and "commute" not in chips and names.count("Sonstiges") == 1, (chips, names)
        # Sportart ändern: bei „Golf“ ist der Rückfall „Sonstiges“ vorgewählt; Übernehmen speichert einen Schlüssel des Katalogs
        pg.goto(app + "/#/tour/g1")
        pg.wait_for_selector("#esport", state="attached", timeout=TL)
        quiet(pg, 3000)
        pg.locator('.tact-bar [data-g="edit"]').click()
        pg.locator('.tactl [data-e="esport"]').click()
        pg.wait_for_selector("#espsel", state="attached", timeout=TL)                 # 3.61.0: Muster „Zuweisen“ – verstecktes Feld, Knöpfe für alle 29 Sportarten
        assert pg.input_value("#espsel") == "other" and pg.locator(".spwahl [data-sp]").count() == 29
        assert pg.locator('.spwahl [data-sp="other"]').get_attribute("aria-checked") == "true"
        pg.locator("#espx").click()
        assert _tours(app)["g1"] == "golf"
        assert not errs, errs
    finally:
        b.close()


def test_englisch_ohne_deutsche_reste_und_390px(pw, app):
    b, pg, errs = _page(pw, app, w=390, lang="en")
    try:
        _aktivitaeten(pg, app)
        expect(pg.locator('#atabs [data-t="sportarten"]')).to_have_text("Sports")
        assert pg.locator(".atab[data-t=sportarten] .gbody > * > h2").all_inner_texts() == ["Sports catalogue", "Favourite sports", "Statistics groups"]
        assert pg.locator('#katp .katit[data-k="mountaineering"] .katn').inner_text() == "Mountaineering"
        assert pg.locator("#katp .sgcl").all_inner_texts()[-1] == "Outdoor and other"
        rest = pg.evaluate(SCAN, ['.atab[data-t="sportarten"]', DE])
        assert rest == [], rest
        assert pg.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth + 1")
        for sel in ("#katp", "#favp", "#sgp"):
            bb = pg.locator(sel).bounding_box()
            assert bb["x"] >= 0 and bb["x"] + bb["width"] <= 391, sel
        assert not errs, errs
    finally:
        b.close()
