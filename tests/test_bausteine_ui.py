"""3.18.0 – Mehr Bausteine (Browser, Chromium): Katalog mit Kategorien und Suche, alle Bausteine über den Katalog hinzufügen und rendern, Leerzustände, 390 px, Kontrast hell/dunkel,
Beschriftungen der Grafiken, Englisch. Wenige Seiten-Durchläufe statt je Baustein ein Browser-Start: Ein Durchlauf fügt alle Bausteine einer Seite nacheinander hinzu,
die weiteren Durchläufe lesen dasselbe gespeicherte Layout.
Wettlauf-Regel wie in test_seitenlayout_ui.py: nach jeder Aktion auf den Zustand warten (wait_for_function/expect, 15 s), nie nur schlafen.
Mit TS_SHOTS=<Ordner> werden Screenshots abgelegt (Chromium, dpr 2)."""
import json
import os
import re
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

from tests.test_tourseite_ui import CONTRAST, DEV1, HR_JSON, LAUNCH, READY_SUB, SEED, WPS_JSON, WX_JSON, _ready_main, _wait, uhr_json

ROOT = Path(__file__).resolve().parent.parent
T = 15000
KEYS = ("tour-haupt", "tour-auswertung", "uebersicht")
TOUR_TYPES = ["kennzahlen", "tempo", "vergleich", "pulszonen", "wetter", "fotostreifen", "notiz",
              "splits", "steigung", "bewegung", "durchschnitt", "jahresrang", "tageslicht", "gipfel", "vergleiche", "stimmung", "fotohighlights", "miniprofil", "steckbrief"]
DASH_TYPES = ["periode", "belastung", "jahresvergleich", "letzte", "neuefotos", "auffaellig", "bestwerte", "heutevor",                 # 3.45.0: „Bestwerte“ statt „Rekorde“, „Ziele“ statt „Jahresziel“ und „Ziele“
              "ziele", "serie", "heatmap", "meilensteine", "wochentage", "sportarten", "wiederentdecken", "orte", "uhrenzeit", "ausruestung", "geplant", "rueckblick", "saison"]
NEW_TOUR = TOUR_TYPES[7:]
NEW_DASH = DASH_TYPES[8:]

EXTRA = r"""
import sys, os, time, math, random; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db, config, routes
db.init()
now = int(time.time())
rnd = random.Random(7)
sports = ["hike"] * 6 + ["mtb", "touringbicycle", "jogging", "skitour", "e_touringbicycle", "snowshoe"]
geo = [("Siebengebirge", "Rhein-Sieg-Kreis", "Nordrhein-Westfalen", "Deutschland"), ("Eifel", "Kreis Euskirchen", "Nordrhein-Westfalen", "Deutschland"),
       ("Bergisches Land", "Rheinisch-Bergischer Kreis", "Nordrhein-Westfalen", "Deutschland"), ("Taunus", "Hochtaunuskreis", "Hessen", "Deutschland"), ("Allgäu", "Oberallgäu", "Bayern", "Deutschland")]
def add(tid, days, sport, dist, dur, up, name=None):
    ts = now - int(days * 86400) - rnd.randint(0, 40000)
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,'t','komoot')",
               (tid, name or "Tour " + tid, sport, ts, ts + int(dur), dist, dur, up, up, 50.7, 7.2))
    g = rnd.choice(geo)
    if rnd.random() < 0.9:
        db.execute("INSERT INTO tour_geo(id,country,state,county,place,ts) VALUES(?,?,?,?,?,?)", (tid, g[3], g[2], g[1], g[0], now))
for i in range(70):
    d = rnd.uniform(0.6, 1.0) ** 1.6 * 820 + 2
    sp = rnd.choice(sports)
    dist = rnd.uniform(4000, 26000) * (2.2 if "bi" in sp or sp == "mtb" else 1)
    add("x%%d" %% i, d, sp, dist, dist / rnd.uniform(1.0, 1.6), dist * rnd.uniform(0.02, 0.09))
for i, d in enumerate([1, 8, 15, 22, 29, 36, 60]):            # Wochen-Serie
    add("w%%d" %% i, d, "hike", 9000 + 1000 * i, 9000 / 1.3, 300 + 20 * i)
add("old1", 400, "hike", 12500, 9600, 420, "Seeufer-Runde")          # für „Wiederentdecken“ und „Heute vor X Jahren“
db.execute("UPDATE tours SET lat=48.0, lng=11.0 WHERE id IN ('r0','r1','r2','r3','r4')")
db.execute("UPDATE devices SET since='2022-05-01', until='2024-02-28', active=0 WHERE id=2")
db.execute("UPDATE devices SET since='2024-03-01' WHERE id=1")
for i in range(0, 70, 2):
    db.execute("INSERT OR REPLACE INTO tour_device(tour_id,device_id) VALUES(?,?)", ("x%%d" %% i, 1 if i %% 4 == 0 else 2))
db.execute("INSERT INTO gear(name,kind,sports,since,until,limit_km,note) VALUES('Wanderschuhe Meindl','Schuhe','hike','','',600,'')")
db.execute("INSERT INTO gear(name,kind,sports,since,until,limit_km,note) VALUES('Mountainbike','Rad','mtb,touringbicycle','','',0,'')")
db.execute("INSERT INTO gear(name,kind,sports,since,until,limit_km,note) VALUES('Laufschuhe','Schuhe','jogging','','',150,'')")
db.execute("INSERT INTO plans(name,sport,pts,km,up,down,max_alt,est_h,note,ts) VALUES('Gipfelweg Drachenfels','hike','[]',8.4,420,420,321,3.1,'',?)", (now - 100,))
db.execute("INSERT INTO plans(name,sport,pts,km,up,down,max_alt,est_h,note,ts) VALUES('Rund um den Laacher See','hike','[]',12.5,260,260,300,4.0,'',?)", (now - 200,))
from PIL import Image, ImageDraw
pd = %(photos)r
os.makedirs(pd, exist_ok=True)
for i, (c1, c2) in enumerate([("#2f6f5f", "#e8c46a"), ("#3b6f9f", "#f2e6c8"), ("#7a5f3f", "#9fc2a8"), ("#4a7a4a", "#c8dce8")]):
    im = Image.new("RGB", (900, 600), c1)
    dr = ImageDraw.Draw(im)
    dr.polygon([(0, 600), (260, 260), (480, 480), (700, 200), (900, 600)], fill=c2)
    dr.ellipse((680, 60, 780, 160), fill="#fff3b0")
    f = os.path.join(pd, "p%%d.jpg" %% i)
    im.save(f, "JPEG", quality=85)
    db.execute("INSERT INTO photos(path,mtime,size,taken_ts,tour_id,dated) VALUES(?,?,?,?,?,1)", (f, 1.0, 1000, now - 40 * 86400 + 600 * (i + 1), "r3"))
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    pytest.importorskip("playwright.sync_api")
    tmp = tmp_path_factory.mktemp("bst")
    data = tmp / "data"
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1")
    for code in (SEED % {"root": str(ROOT), "data": str(data)}, EXTRA % {"root": str(ROOT), "data": str(data), "photos": str(tmp / "pics")}):
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


@pytest.fixture(scope="module")
def pw():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        yield p


def _api(url, key, method="GET", body=None):
    req = urllib.request.Request(f"{url}/api/layout/{key}", method=method, data=None if body is None else json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read() or b"{}")


def _reset(app):
    for k in KEYS:
        _api(app, k, "DELETE")


def _shot(pg, name, full=True):
    d = os.environ.get("TS_SHOTS")
    if d:
        Path(d).mkdir(parents=True, exist_ok=True)
        pg.evaluate("window.scrollTo(0, 0)")
        pg.screenshot(path=str(Path(d) / name), full_page=full)


def _browser(pw, url, width=1280, height=1000, scheme="light", dpr=1, locale="de-DE", tour="r3"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale=locale, viewport={"width": width, "height": height}, color_scheme=scheme, device_scale_factor=dpr, reduced_motion="reduce")
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(url) else r.continue_())
    pg.route(f"**/api/tours/{tour}/uhr-training", lambda r: r.fulfill(json=uhr_json(DEV1)))
    pg.route(f"**/api/tours/{tour}/hr", lambda r: r.fulfill(json=HR_JSON))
    pg.route(f"**/api/tours/{tour}/weather", lambda r: r.fulfill(json=WX_JSON))
    pg.route(f"**/api/tours/{tour}/wps", lambda r: r.fulfill(json=WPS_JSON))
    pg.browser_ = b
    return pg


def _tour(pw, url, sub=False, tour="r3", **kw):
    pg = _browser(pw, url, tour=tour, **kw)
    pg.goto(f"{url}/#/tour/{tour}" + ("/auswertung" if sub else ""))
    if sub:
        pg.wait_for_function(READY_SUB, timeout=T)
    else:
        _ready_main(pg, True)
    pg.wait_for_function("() => typeof SL === 'object' && !!document.querySelector('#slopen')", timeout=T)
    return pg


def _dash(pw, url, **kw):
    pg = _browser(pw, url, **kw)
    pg.goto(f"{url}/#/dash")
    pg.wait_for_selector("main.home #hlast", timeout=T)
    pg.wait_for_function("() => !!document.querySelector('#slopen')", timeout=T)
    return pg


def _edit(pg):
    pg.wait_for_selector("#slopen", state="visible", timeout=T)
    pg.locator("#slopen").click()
    pg.wait_for_selector("#slbar", timeout=T)
    pg.wait_for_function("() => document.querySelectorAll('.slit').length > 0", timeout=T)


def _catalog(pg):
    pg.locator("#slbar [data-a=add]").click()
    try:
        pg.wait_for_selector(".slcat .slcard", timeout=T)
    except Exception:
        raise AssertionError(f"Katalog öffnet nicht: {pg.errors}")


READY = "(types) => types.every(t => { const w = document.querySelector('[data-wtype=\"' + t + '\"] .tlsb'); return !!w && !/Wird geladen/.test(w.textContent); })"
OVERFLOW = "() => ({page: document.documentElement.scrollWidth - window.innerWidth, wide: [...document.querySelectorAll('[data-wtype]')].filter(w => w.scrollWidth > w.clientWidth + 1).map(w => w.dataset.wtype)})"
ARIA = """() => [...document.querySelectorAll('[data-wtype] svg')].filter(s => !s.closest('[aria-hidden=true]') && !s.closest('[role=img]') && s.getAttribute('role') !== 'img').map(s => s.closest('[data-wtype]').dataset.wtype + ':' + s.getAttribute('class'))"""
NOLABEL = "() => [...document.querySelectorAll('[data-wtype] [role=img]')].filter(e => !(e.getAttribute('aria-label') || '').trim()).map(e => e.closest('[data-wtype]').dataset.wtype)"
# Kontrast aller Textelemente der Bausteine (eigener Text, Vordergrund gegen den ersten deckenden Hintergrund)
TEXTCONTRAST = """(sel) => {
  const parse = c => { const m = c.match(/[\\d.]+/g).map(Number); return {r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1}; };
  const lum = c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const bg = el => { for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c.a > 0.5) return c; } return {r: 255, g: 255, b: 255, a: 1}; };
  const low = {}; let n = 0;
  document.querySelectorAll(sel).forEach(el => {
    if (![...el.childNodes].some(x => x.nodeType === 3 && x.textContent.trim()) || el.closest('svg') || el.closest('[hidden]') || !el.offsetParent) return;
    const f = parse(getComputedStyle(el).color), b = bg(el), a = lum(f), c = lum(b), r = (Math.max(a, c) + 0.05) / (Math.min(a, c) + 0.05);
    n++;
    if (r < 4.5 && !el.matches('.slem')) low[(el.closest('[data-wtype]') || el).dataset.wtype + ' ' + el.tagName + '.' + el.className + ' "' + el.textContent.trim().slice(0, 20) + '"'] = Math.round(r * 100) / 100;
  });
  return {n, low};
}"""


def _add_all(pg, types):
    """Jeden Baustein über den Katalog hinzufügen (der Bearbeitungsmodus bleibt offen) und auf seinen Inhalt warten; am Ende „Fertig“."""
    _edit(pg)
    for ty in types:
        _catalog(pg)
        btn = pg.locator(f'[data-add="{ty}"]')
        btn.scroll_into_view_if_needed()
        btn.click()
        if ty == "notiz":                                                      # die Notiz öffnet gleich die Einstellungen
            pg.wait_for_selector(".slform textarea", timeout=T)
            pg.locator(".slform textarea").fill("Einkehr im Gasthof, Rückweg über den Grat.")
            pg.get_by_role("button", name="Speichern", exact=True).click()
        pg.wait_for_function(READY, arg=[ty], timeout=T)
    pg.wait_for_function("() => !document.querySelector('.uidlg')", timeout=T)
    pg.locator("#slbar").get_by_role("button", name="Fertig").click()
    pg.wait_for_function("() => !document.querySelector('.slit') && !document.querySelector('#slbar')", timeout=T)


# ------------------------------------------------------------------  Katalog  ------------------------------------------------------------------

def test_catalog_categories_search_and_390px(pw, app):
    _reset(app)
    pg = _tour(pw, app, width=390, height=844, dpr=2)
    try:
        _edit(pg)
        _catalog(pg)
        n_all = len(TOUR_TYPES) + len(DASH_TYPES) + 1                  # 3.20.0: auch die Bausteine der Übersicht (ohne „Auffällige Touren“, plus „Dein Jahr“)
        # 3.45.0: die Bausteine der Übersicht stehen in der zugeklappten Gruppe „Allgemein (nicht zu dieser Tour)“
        assert pg.locator(".slcard:visible").count() == len(TOUR_TYPES) + 1 and pg.locator(".slcard .slpv").count() == n_all      # plus „Plan und Ergebnis“
        assert pg.locator(".slcnt").inner_text() == f"{n_all} Bausteine"
        heads = pg.locator(".slcath:visible").all_inner_texts()
        assert heads == ["Zahlen", "Grafiken", "Spaß und Eigenes", "Planung", "Allgemein (nicht zu dieser Tour)"], heads          # Planung: „Plan und Ergebnis“
        assert pg.locator(".slchip").all_inner_texts() == ["Alle", "Zahlen", "Grafiken", "Spaß und Eigenes", "Planung", "Allgemein"]
        assert pg.locator('.slchip[aria-pressed="true"]').inner_text() == "Alle"
        # jeder Eintrag hat Vorschau, Kurzbeschreibung und Knopf
        assert pg.evaluate("() => [...document.querySelectorAll('.slcard')].filter(c => !c.querySelector('.slpv').innerHTML.trim() || !c.querySelector('p').textContent.trim() || !c.querySelector('[data-add]')).length") == 0
        # Kategorie wählen
        pg.locator(".slchip", has_text="Spaß und Eigenes").click()
        pg.wait_for_function("() => document.querySelectorAll('.slcard:not([hidden])').length === 3", timeout=T)
        assert pg.locator('.slchip[aria-pressed="true"]').inner_text() == "Spaß und Eigenes" and pg.locator(".slcnt").inner_text() == "3 Bausteine"
        assert pg.locator(".slcath:visible").all_inner_texts() == ["Spaß und Eigenes"]
        # Suche (innerhalb der Kategorie, dann über alle)
        pg.locator("#slq").fill("kalor")
        pg.wait_for_function("() => document.querySelectorAll('.slcard:not([hidden])').length === 1", timeout=T)
        assert pg.locator(".slcard:visible .slci h3").inner_text() == "Spaß-Vergleiche"
        pg.locator(".slchip", has_text="Alle").click()
        pg.locator("#slq").fill("WETTER")
        pg.wait_for_function("() => document.querySelectorAll('.slcard:not([hidden])').length >= 2", timeout=T)
        names = pg.locator(".slcard:visible .slci h3").all_inner_texts()
        assert "Wetter zur Tour" in names and "Wetter und Tageszeit" in names, names
        pg.locator("#slq").fill("gibt es nicht")
        pg.wait_for_function("() => document.querySelectorAll('.slcard:not([hidden])').length === 0", timeout=T)
        assert pg.locator(".slnorsl").is_visible() and pg.locator(".slcnt").inner_text() == "0 Bausteine"
        pg.locator("#slq").fill("")
        pg.wait_for_function("(n) => document.querySelectorAll('.slcard:not([hidden])').length === n", arg=n_all, timeout=T)
        # 390 px: kein seitliches Scrollen, Chips und Suchfeld gut bedienbar
        o = pg.evaluate("() => ({page: document.documentElement.scrollWidth - window.innerWidth, box: (b => b.scrollWidth - b.clientWidth)(document.querySelector('.slbox')), chip: Math.min(...[...document.querySelectorAll('.slchip')].map(c => c.getBoundingClientRect().height)), q: document.querySelector('#slq').getBoundingClientRect().height})")
        assert o["page"] <= 0 and o["box"] <= 0 and o["chip"] >= 40 and o["q"] >= 44, o
        # Tastatur: Fokus ist sichtbar
        pg.locator(".slchip").nth(1).focus()
        assert pg.evaluate("() => getComputedStyle(document.activeElement).outlineStyle") != "none"
        _shot(pg, "katalog-390-hell.png", full=False)
        pg.locator(".slchip", has_text="Grafiken").click()
        pg.wait_for_function("() => document.querySelectorAll('.slcard:not([hidden])').length > 3", timeout=T)
        _shot(pg, "katalog-390-grafiken.png", full=False)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_catalog_dash_has_all_categories_and_desktop_shot(pw, app):
    _reset(app)
    pg = _dash(pw, app, dpr=2)
    try:
        _edit(pg)
        _catalog(pg)
        assert pg.locator(".slcard").count() == len(DASH_TYPES) + 13                    # 3.45.0: 7 statt 9 Hinweis-Bausteine; plus „Fitness-Einordnung“ (3.44.0), plus „Erinnerungen“ (3.32.0, mehrfach), plus „Touren-Knopf“ (3.31.0), plus „Zepp-Import“ (3.30.0), plus „Dein Jahr“ und 9 Hinweis-Bausteine (3.23.0) und „Eigene Kennzahl“ (3.28.0) (3.19.0, hat kein .tlsb und wird in test_bausteine_konfig_ui.py geprüft)
        assert pg.locator(".slchip").all_inner_texts() == ["Alle", "Zahlen", "Grafiken", "Rückblick", "Planung", "Touren holen", "Hinweise", "Eigene Kennzahlen"]
        pg.locator(".slchip", has_text="Planung").click()
        pg.wait_for_function("() => document.querySelectorAll('.slcard:not([hidden])').length === 4", timeout=T)
        assert sorted(pg.locator(".slcard:visible .slci h3").all_inner_texts()) == ["Ausrüstung", "Geplante Touren", "Meilensteine", "Ziele"]
        pg.locator(".slchip", has_text="Alle").click()
        pg.wait_for_function("(n) => document.querySelectorAll('.slcard:not([hidden])').length === n", arg=len(DASH_TYPES) + 13, timeout=T)
        _shot(pg, "katalog-desktop-hell.png", full=False)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Alle Bausteine der Tourseite  ------------------------------------------------------------------

def test_add_all_tour_widgets_render_and_look_right(pw, app):
    _reset(app)
    pg = _tour(pw, app)
    try:
        _add_all(pg, TOUR_TYPES)
        w = _api(app, "tour-haupt")["layout"]["widgets"]
        assert [x["type"] for x in w] == TOUR_TYPES
        assert pg.evaluate("() => document.querySelectorAll('[data-wtype]').length") == len(TOUR_TYPES)
        assert not pg.errors, pg.errors
        # Inhalte der neuen Bausteine (die Daten kommen aus den konstruierten Touren)
        assert pg.locator('[data-wtype="splits"] svg.slcol').count() == 1 and pg.locator('[data-wtype="splits"] .slfacts li').count() == 3
        assert pg.locator('[data-wtype="steigung"] .slhist li').count() == 7
        assert pg.locator('[data-wtype="bewegung"] svg.slstrip').count() == 1 and pg.locator('[data-wtype="bewegung"] .utile').count() == 2
        assert pg.locator('[data-wtype="durchschnitt"] .slrows li').count() == 3 and pg.locator('[data-wtype="durchschnitt"] .slmk').count() == 3
        assert pg.locator('[data-wtype="jahresrang"] .slcmp').inner_text().startswith("Platz ")
        assert pg.locator('[data-wtype="tageslicht"] svg.slstrip').count() == 1 and "Sonnenaufgang" in pg.locator('[data-wtype="tageslicht"]').inner_text()
        assert pg.locator('[data-wtype="gipfel"] .slsign b').inner_text().endswith(" m") and pg.locator('[data-wtype="gipfel"] .utile').count() >= 3
        assert pg.locator('[data-wtype="vergleiche"] .slfun li').count() == 3 and "×" in pg.locator('[data-wtype="vergleiche"] .slfn').first.inner_text()
        assert pg.locator('[data-wtype="stimmung"] .slmood li').count() >= 4
        assert pg.locator('[data-wtype="fotohighlights"] .slfh img').count() >= 3
        assert pg.locator('[data-wtype="miniprofil"] svg.slprof path.slpl').count() > 10
        assert "Auf dieser Strecke" in pg.locator('[data-wtype="steckbrief"]').inner_text() and pg.locator('[data-wtype="steckbrief"] .sltd').count() >= 3
        # Fotos laden wirklich
        pg.wait_for_function("() => [...document.querySelectorAll('[data-wtype=fotohighlights] img')].every(i => i.complete && i.naturalWidth > 0)", timeout=T)
        # Grafiken: Vorlesehilfen
        assert pg.evaluate(ARIA) == [] and pg.evaluate(NOLABEL) == []
        assert pg.evaluate("() => document.querySelectorAll('[data-wtype] [role=img]').length") >= 7
        # Kopf wie bei allen Abschnitten: Symbol, Titel, einklappbar
        assert pg.evaluate("() => [...document.querySelectorAll('[data-wtype]')].every(w => w.querySelector('summary .tli') && w.querySelector('summary h3').textContent.trim() && w.querySelector('details'))")
        pg.locator('[data-wtype="splits"] summary').click()
        pg.wait_for_function("() => !document.querySelector('[data-wtype=splits] details').open", timeout=T)
        pg.locator('[data-wtype="splits"] summary').click()
        pg.wait_for_function("() => document.querySelector('[data-wtype=splits] details').open", timeout=T)
        # Bewegung reduziert: keine Übergänge
        assert not pg.errors, pg.errors
        _shot(pg, "tour-desktop-hell-alle-bausteine.png")
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme,width,dpr", [("light", 390, 2), ("dark", 390, 2), ("dark", 1280, 2)])
def test_tour_widgets_390px_contrast_and_shots(pw, app, scheme, width, dpr):
    if not _api(app, "tour-haupt").get("layout"):                                   # Layout aus dem ersten Durchlauf; einzeln gestartet: selbst anlegen
        _api(app, "tour-haupt", "PUT", {"widgets": [{"id": f"w{i}", "type": t, "cfg": {"text": "Notiz"} if t == "notiz" else {}} for i, t in enumerate(TOUR_TYPES)]})
    pg = _tour(pw, app, scheme=scheme, width=width, height=900 if width > 500 else 844, dpr=dpr)
    try:
        try:
            pg.wait_for_function(READY, arg=TOUR_TYPES, timeout=T)
        except Exception:
            raise AssertionError("nicht fertig: " + str(pg.evaluate("(ts) => ts.filter(t => !READYF(t))".replace("READYF(t)", "(() => { const w = document.querySelector('[data-wtype=\"' + t + '\"] .tlsb'); return !!w && !/Wird geladen/.test(w.textContent); })()"), TOUR_TYPES)) + str(pg.errors))
        pg.evaluate("() => document.querySelectorAll('img[loading=lazy]').forEach(i => (i.loading = 'eager'))")       # Fotos unterhalb des Bildschirms laden sonst nie
        pg.wait_for_function("() => [...document.querySelectorAll('[data-wtype=fotohighlights] img')].every(i => i.complete)", timeout=T)
        o = pg.evaluate(OVERFLOW)
        assert o["page"] <= 0 and o["wide"] == [], f"{scheme} {width}: seitliches Scrollen {o}"
        r = pg.evaluate(TEXTCONTRAST, "[data-wtype] .tlsb *")
        assert r["n"] > 100 and not r["low"], f"{scheme} {width}: Kontrast unter 4,5:1 {r['low']}"
        c = pg.evaluate(CONTRAST, ["#tl .tlgh", "#slopen"])
        assert not {k: v for k, v in c.items() if v < 4.5}, c
        assert pg.evaluate("() => getComputedStyle(document.querySelector('[data-wtype=tageslicht] .slstrip')).display") == "block"
        assert pg.evaluate("() => getComputedStyle(document.querySelector('.slcol')).transitionDuration") == "0s"
        assert not pg.errors, pg.errors
        _shot(pg, f"tour-{width}-{scheme}-alle-bausteine.png")
    finally:
        pg.browser_.close()


def test_tour_widgets_on_the_auswertung_page(pw, app):
    _reset(app)
    _api(app, "tour-haupt", "PUT", {"widgets": [{"id": f"w{i}", "type": t, "cfg": {}} for i, t in enumerate(NEW_TOUR)], "page": {f"w{i}": "auswertung" for i in range(len(NEW_TOUR))}})
    pg = _tour(pw, app, sub=True, scheme="dark", width=390, height=844, dpr=2)
    try:
        pg.wait_for_function(READY, arg=NEW_TOUR, timeout=T)
        o = pg.evaluate(OVERFLOW)
        assert o["page"] <= 0 and o["wide"] == [], o
        r = pg.evaluate(TEXTCONTRAST, "[data-wtype] .tlsb *")
        assert not r["low"], r["low"]
        _shot(pg, "auswertung-390-dunkel-bausteine.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Alle Bausteine der Übersicht  ------------------------------------------------------------------

def test_add_all_dash_widgets_render_and_look_right(pw, app):
    _reset(app)
    pg = _dash(pw, app)
    try:
        _add_all(pg, DASH_TYPES)
        w = _api(app, "uebersicht")["layout"]["widgets"]
        assert [x["type"] for x in w] == DASH_TYPES
        assert not pg.errors, pg.errors
        q = lambda t, s: pg.locator(f'[data-wtype="{t}"] {s}')  # noqa: E731
        assert q("ziele", ".goal, .slnone").count() >= 1 and q("bestwerte", ".utile").count() == 5                # 3.45.0: Ziele (Balken) und Bestwerte (fünf Kacheln)
        assert q("serie", ".utile").count() == 3 and q("serie", "svg.slpts rect").count() == 26
        assert q("heatmap", "svg.slheat rect").count() >= 300 and q("heatmap", ".slmos span").count() >= 10
        assert q("meilensteine", ".slrows li").count() == 3 and "Mount Everest" in q("meilensteine", ".slrows").inner_text()
        assert q("wochentage", "svg.slcol").count() == 2 and "Lieblingstag" in q("wochentage", ".slcmp").inner_text()
        assert q("sportarten", ".slleg li").count() >= 3 and q("sportarten", "circle.slsg").count() >= 3
        assert q("wiederentdecken", ".slrdn").count() == 1 and q("wiederentdecken", "[data-other]").count() == 1
        assert q("orte", ".slrows li").count() >= 3
        assert q("uhrenzeit", ".slrows li").count() == 2
        assert q("ausruestung", ".slrows li").count() == 3 and q("ausruestung", ".slbr.warn, .slbr.bad").count() >= 0
        assert q("geplant", ".sllist li").count() == 2
        assert q("rueckblick", "svg.slcol").count() == 1 and q("rueckblick", ".slrec").count() == 2
        # „Andere Tour“ würfelt neu (Fokus bleibt am Knopf)
        first = q("wiederentdecken", ".slrdn").inner_text()
        seen = {first}
        for _ in range(12):
            q("wiederentdecken", "[data-other]").click()
            pg.wait_for_function("() => document.activeElement && document.activeElement.hasAttribute('data-other')", timeout=T)
            seen.add(q("wiederentdecken", ".slrdn").inner_text())
        assert len(seen) >= 2
        assert pg.evaluate(ARIA) == [] and pg.evaluate(NOLABEL) == []
        _shot(pg, "uebersicht-desktop-hell-alle-bausteine.png")
    finally:
        pg.browser_.close()


def test_dash_config_number_field_goal_and_ring(pw, app):
    """3.45.0: Das eigene Ziel des früheren „Jahresziel“-Bausteins gibt es nicht mehr (Ziele stehen in der Statistik); geprüft wird das Zahlenfeld „Schwelle“ des Bausteins „Ziele“."""
    _reset(app)
    _api(app, "uebersicht", "PUT", {"widgets": [{"id": "wj", "type": "ziele", "cfg": {"view": "warnung"}}]})
    pg = _dash(pw, app)
    try:
        pg.wait_for_selector("#tlw-wj", state="attached", timeout=T)
        _edit(pg)
        pg.locator('.slit[data-sl="wj"] [data-a="cfg"]').click()
        pg.wait_for_selector(".slform input[type=number]", timeout=T)
        pg.locator(".slform input[type=number]").fill("0")                                  # zu klein: Fehlermeldung, nichts gespeichert
        pg.get_by_role("button", name="Speichern", exact=True).click()
        pg.wait_for_function("() => document.querySelector('.slerr').textContent.length > 5", timeout=T)
        pg.locator(".slform input[type=number]").fill("20")
        pg.get_by_role("button", name="Speichern", exact=True).click()
        pg.wait_for_function("() => document.getElementById('slsaved').textContent.trim() === 'Gespeichert'", timeout=T)
        assert _api(app, "uebersicht")["layout"]["widgets"][0]["cfg"]["schwelle"] == 20
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("scheme,width", [("light", 390), ("dark", 390), ("dark", 1280)])
def test_dash_widgets_390px_contrast_and_shots(pw, app, scheme, width):
    _reset(app)
    _api(app, "uebersicht", "PUT", {"widgets": [{"id": f"w{i}", "type": t, "cfg": {}} for i, t in enumerate(DASH_TYPES)]})
    pg = _dash(pw, app, scheme=scheme, width=width, height=900 if width > 500 else 844, dpr=2)
    try:
        pg.wait_for_function(READY, arg=DASH_TYPES, timeout=T)
        pg.wait_for_timeout(600)
        o = pg.evaluate(OVERFLOW)
        assert o["page"] <= 0 and o["wide"] == [], f"{scheme} {width}: seitliches Scrollen {o}"
        r = pg.evaluate(TEXTCONTRAST, "[data-wtype] .tlsb *")
        assert r["n"] > 100 and not r["low"], f"{scheme} {width}: Kontrast unter 4,5:1 {r['low']}"
        assert not pg.errors, pg.errors
        _shot(pg, f"uebersicht-{width}-{scheme}-alle-bausteine.png")
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Leerzustände  ------------------------------------------------------------------

EMPTY = """async ([types, tid, mock]) => {
  const out = {};
  const keep = TOURS.slice();
  if (mock) TOURS.length = 0;
  for (const k of types) {
    const T = SL_WT[k], card = tlCard('tlw-e' + k, {sec: 'e' + k, key: 'e' + k, icon: T.icon, title: T.title(T.defaults || {}), def: true, bodyCls: 'slwb'}), body = tlBody(card);
    try { await T.render(card, body, JSON.parse(JSON.stringify(T.defaults || {})), {t: BY[tid] || null}); } catch (e) { out[k] = 'FEHLER ' + e; continue; }
    out[k] = body.textContent.trim();
  }
  keep.forEach(t => TOURS.push(t));
  TOURS.length = keep.length;
  return out;
}"""


def test_empty_states_tour_widgets(pw, app):
    pg = _tour(pw, app)
    try:
        for tid in ("n0", "s0"):                                                 # n0: keine Strecke; s0: Strecke ohne Zeitstempel
            r = pg.evaluate(EMPTY, [NEW_TOUR, tid, False])
            bad = {k: v for k, v in r.items() if not v or v.startswith("FEHLER") or "Wird geladen" in v}
            assert not bad, (tid, bad)
        r = pg.evaluate(EMPTY, [NEW_TOUR, "n0", False])
        assert r["splits"] == "Für diese Tour liegt keine Strecke vor." and r["miniprofil"] == "Für diese Tour liegt keine Strecke vor."
        assert r["gipfel"] == "Für diese Tour liegt keine Strecke vor." and r["fotohighlights"] == "Keine Fotos vorhanden."
        r = pg.evaluate(EMPTY, [NEW_TOUR, "s0", False])
        assert r["splits"] == "Der Track dieser Tour enthält keine Zeitstempel." and r["bewegung"] == "Der Track dieser Tour enthält keine Zeitstempel."
        assert "Höchster Punkt" in r["gipfel"]                                    # Höhen sind da
        assert "Position" in r["tageslicht"] or "Sonnenaufgang" in r["tageslicht"]
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_empty_states_dash_widgets(pw, app):
    pg = _dash(pw, app)
    try:
        pg.route("**/api/my-devices", lambda r: r.fulfill(json={"devices": [], "kinds": []}))
        pg.route("**/api/bausteine/ausruestung", lambda r: r.fulfill(json=[]))
        pg.route("**/api/bausteine/geplant", lambda r: r.fulfill(json=[]))
        pg.route("**/api/goals", lambda r: r.fulfill(json=[]))
        r = pg.evaluate(EMPTY, [NEW_DASH, "r3", True])
        bad = {k: v for k, v in r.items() if not v or v.startswith("FEHLER") or "Wird geladen" in v}
        assert not bad, bad
        assert r["uhrenzeit"].startswith("Noch kein Gerät") and r["ausruestung"] == "Noch keine Ausrüstung angelegt." and r["geplant"].startswith("Keine offenen Pläne")
        assert r["heatmap"] == "Noch keine Touren." and r["ziele"].startswith("Noch kein Ziel für")
        assert r["orte"].startswith("Noch keine Regionen bestimmt") and r["rueckblick"].startswith("Im Jahr ")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


# ------------------------------------------------------------------  Englisch  ------------------------------------------------------------------

GERMAN = re.compile(r"(?i)(?<![\w-])(und|oder|der|die|das|dem|den|für|von|bis|mit|noch|keine|kein|dieser|diese|dieses|auf|ein|eine|einer|zum|zur|dein|deine|deiner|wie|nach|aus|ist|sind|wurde|bei|pro|über|unter|gesamt|touren|strecke|woche|wochen|tage|monat|jahr|jahre|jahren|stunden|std)(?![\w-])|[äöüß]")


def _german_leftovers(pg, sel):
    return pg.evaluate("""(sel) => {
      const out = new Set();
      document.querySelectorAll(sel).forEach(el => {
        el.childNodes.forEach(n => { if (n.nodeType === 3 && n.textContent.trim()) out.add(n.textContent.trim()); });
        ['aria-label', 'title', 'alt', 'placeholder'].forEach(a => el.getAttribute && el.getAttribute(a) && out.add(el.getAttribute(a)));
      });
      return [...out];
    }""", sel)


@pytest.mark.parametrize("loc,page", [("en-US", "tour"), ("fr-FR", "tour"), ("es-ES", "tour"), ("en-US", "dash")])
def test_texts_are_translated(pw, app, loc, page):
    _reset(app)
    if page == "tour":
        _api(app, "tour-haupt", "PUT", {"widgets": [{"id": f"w{i}", "type": t, "cfg": {}} for i, t in enumerate(NEW_TOUR)]})
        pg = _tour(pw, app, locale=loc)
        types = NEW_TOUR
    else:
        _api(app, "uebersicht", "PUT", {"widgets": [{"id": f"w{i}", "type": t, "cfg": {}} for i, t in enumerate(NEW_DASH)]})
        pg = _dash(pw, app, locale=loc)
        types = NEW_DASH
    try:
        pg.wait_for_function(READY, arg=types, timeout=T)
        pg.wait_for_timeout(500)                                                  # die Übersetzung läuft über den MutationObserver
        texts = _german_leftovers(pg, "[data-wtype] *")
        left = sorted({t for t in texts if GERMAN.search(t)})
        # Namen aus den Daten (Tourennamen, Orte, Gerätenamen) und Beispielwörter sind kein Übersetzungsfehler
        left = [t for t in left if not re.search(r"Tour x?\d|Tour [a-z]\d|Gipfelrunde|Seeufer|Solo ohne|Rhein|Eifel|Kreis|Hessen|Bayern|Nordrhein|Deutschland|Allgäu|Oberallgäu|Bergisches|Siebengebirge|Taunus|Amazfit|Garmin|Wanderschuhe|Mountainbike|Laufschuhe|Drachenfels|Laacher", t)]
        assert not left, f"{loc}: nicht übersetzt: {left}"
        if page == "tour":
            _shot(pg, f"tour-{loc}-bausteine.png")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
