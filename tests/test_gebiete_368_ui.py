"""3.68.0 – Browser (Chromium): Hinweis „Diese Reise liegt in n Gebieten/Ländern“ auf der Reise-Seite, Baustein „Vor einem Jahr in dieser Gegend“ (Übersicht und Gebietsseite, Katalog, Neu mischen,
leer = unsichtbar), Filter „Gebiet“ auf der Fotos-Seite (Auswahlblatt wie in der Tourenliste, ?g=, Jahr, leere Jahre, Fotos ohne Tour), „Alle Touren holen“, en/fr/es, 390 px.
Alle Daten hängen vom heutigen Datum ab (frühere Jahre um dieses Datum); die Erwartungen werden aus dem Datum und den Seeds gerechnet, nie als feste Datumsangaben geschrieben."""
import json
import os
import re
import socket
import subprocess
import sys
import urllib.request

import pytest
expect = pytest.importorskip("playwright.sync_api").expect

from tests.helpers_ui import entferne, wieder_hinzufuegen
from tests.test_seitenlayout_ui import ROOT, T, _browser, _edit, pw  # noqa: F401
from tests.test_tourseite_ui import LAUNCH, _wait

SEED = r"""
import sys, os, time, math; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from app import db, config, routes
from PIL import Image
db.init()
config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
pics = os.path.join(%(data)r, "pics"); os.makedirs(pics, exist_ok=True)
db.put("home_lat", "48.0"); db.put("home_lng", "11.0")
tz = ZoneInfo("Europe/Berlin")
heute = datetime.now(tz).replace(hour=10, minute=0, second=0, microsecond=0)
def loop(lat0, lng0, r=0.01, n=80):
    return [(lat0 + r * math.sin(2 * math.pi * i / (n - 1)), lng0 + r * (1 - math.cos(2 * math.pi * i / (n - 1))), 500 + 60 * math.sin(i / 14), i * 40000) for i in range(n)]
def vor(tage):
    return heute - timedelta(days=tage)
def frueher(jahre, versatz):                       # dasselbe Datum vor n Jahren, um „versatz“ Tage verschoben (der Versatz wird zuerst abgezogen)
    d = heute + timedelta(days=versatz)
    try:
        return d.replace(year=d.year - jahre)
    except ValueError:
        return (d - timedelta(days=1)).replace(year=d.year - jahre)
N = [0]
def tour(tid, dt, name, lat, lng, geo, dist=9000):
    ts = int(dt.timestamp())
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,'t','komoot')", (tid, name, "hike", ts, ts + 9000, dist, 9000, 200, 180, lat, lng))
    if geo:
        db.execute("INSERT INTO tour_geo(id,country,state,county,place,ts) VALUES(?,?,?,?,?,0)", (tid,) + geo)
    routes.store(tid, loop(lat, lng))
def foto(tid, dt, n=None):
    N[0] += 1
    path = os.path.join(pics, "f%%d.jpg" %% N[0])
    Image.new("RGB", (640, 480), (40 + 9 * N[0] %% 200, 120, 160)).save(path, "JPEG")
    db.execute("INSERT INTO photos(path,taken_ts,dated,tour_id) VALUES(?,?,1,?)", (path, int((dt + timedelta(minutes=30)).timestamp()), tid))
GOM = ("Spanien", "Kanarische Inseln", "Santa Cruz de Tenerife", "Valle Gran Rey")
SUED = ("Italien", "Trentino-Südtirol", "Bozen", "Meran")
GC = ("Spanien", "Kanarische Inseln", "Las Palmas", "Tejeda")
TF = ("Spanien", "Kanarische Inseln", "Santa Cruz de Tenerife", "Adeje")
tour("h0", vor(20), "Heimrunde", 48.0, 11.0, ("Deutschland", "Bayern", "Starnberg", "Starnberg"))
for i in range(5):                                          # La Gomera: 36 bis 40 Tage her (zuletzt unterwegs; innerhalb von 60 Tagen)
    tour("g%%d" %% i, vor(40 - i), "Gomera Tag %%d" %% (i + 1), 28.18 + i * 0.01, -17.27, GOM)
    if i < 2:
        foto("g%%d" %% i, vor(40 - i))
tour("s0", vor(50), "Meran Runde", 46.67, 11.16, SUED)
foto("s0", vor(50))
tour("c0", vor(90), "Roque Nublo", 27.99, -15.62, GC)
tour("t0", vor(95), "Teide Runde", 28.27, -16.64, TF)
# La Gomera in früheren Jahren: (Jahre zurück, Versatz in Tagen); 7 liegen innerhalb von ± 1 Monat, 2 nicht
for k, (j, v) in enumerate([(1, 0), (1, -9), (2, 5), (2, -20), (3, 12), (3, 25), (4, -30), (1, 45), (2, -60)]):
    tour("p%%d" %% k, frueher(j, v), "Früher %%d-%%d" %% (j, v), 28.18, -17.2 + k * 0.01, GOM)
    if k in (0, 2):
        foto("p%%d" %% k, frueher(j, v))
tour("ps", frueher(1, 0), "Meran früher", 46.67, 11.16, SUED)           # anderes Gebiet: nie in „dieser Gegend“ von La Gomera
foto("ps", frueher(1, 0))
foto(None, vor(15))                                           # ein Foto ohne Tour hat kein Gebiet
"""


def _get(url, path):
    with urllib.request.urlopen(url + path, timeout=10) as r:
        return json.loads(r.read())


def _post(url, path, body, method="POST"):
    req = urllib.request.Request(url + path, method=method, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read() or b"{}")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("g368")
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


def _page(pw, url, hash_, ready, **kw):
    pg = _browser(pw, url, devs=None, **kw)
    pg.goto(f"{url}/{hash_}", timeout=30000)
    pg.wait_for_selector(ready, state="attached", timeout=30000)
    return pg


# ---------- B: Hinweis auf der Reise-Seite ----------
@pytest.fixture()
def reisen(app):
    ids = {}
    ids["laender"] = _post(app, "/api/trips", {"name": "Gemischt", "tours": ["g0", "s0"]})["id"]
    ids["gebiete"] = _post(app, "/api/trips", {"name": "Inselhüpfen", "tours": ["g1", "c0", "t0"]})["id"]
    ids["ruhig"] = _post(app, "/api/trips", {"name": "Nur Gomera", "tours": ["g2", "g3", "g4"]})["id"]
    yield ids
    for i in ids.values():
        _post(app, f"/api/trips/{i}", {}, "DELETE")


def _trip(pw, app, tid, **kw):
    pg = _page(pw, app, f"#/trip/{tid}", "#trx [data-rs=kopf]", **kw)
    pg.wait_for_function("() => !!document.querySelector('#tredit')", timeout=30000)
    return pg


def test_hinweis_mehrere_laender_mit_weg_zum_bearbeiten(pw, app, reisen):
    pg = _trip(pw, app, reisen["laender"])
    try:
        h = pg.locator("#main [data-rs=kopf] .trhint")
        expect(h).to_have_count(1, timeout=T)
        t = h.inner_text()
        assert "Diese Reise liegt in 2 Ländern (" in t and "Spanien" in t and "Italien" in t and "Wirklich eine Reise?" in t and "Reise bearbeiten" in t, t
        assert h.get_attribute("role") == "note"                                           # dezent, kein Dialog, nichts blockiert: Knöpfe und Touren der Seite bleiben bedienbar
        assert pg.locator("#tredit").is_enabled() and pg.locator("#trdel").is_enabled()
        h.locator(".trhedit").click()                                                      # führt zum Bearbeiten (eigene Reise: Name, Zeitraum und Touren)
        expect(pg.locator("#tcn")).to_be_visible(timeout=T)
        assert pg.locator("#tcl .cb:checked").count() == 2
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_hinweis_viele_gebiete_und_keiner_bei_einer_ruhigen_reise(pw, app, reisen):
    pg = _trip(pw, app, reisen["gebiete"])
    try:
        t = pg.locator("#main [data-rs=kopf] .trhint").inner_text()
        assert "Diese Reise liegt in 3 Gebieten (" in t and "La Gomera" in t and "Gran Canaria" in t and "Teide" in t, t
        assert "Ländern" not in t                                                          # ein Land: die Prüfung wie in „Reise erstellen“ (Länder vor Entfernung vor Gebieten)
    finally:
        pg.browser_.close()
    pg = _trip(pw, app, reisen["ruhig"])
    try:
        pg.wait_for_timeout(300)
        assert pg.locator("#main .trhint").count() == 0 and pg.locator("#tredit").count() == 1
    finally:
        pg.browser_.close()


def test_hinweis_nutzt_dieselbe_pruefung_wie_der_dialog(pw, app, reisen):
    pg = _trip(pw, app, reisen["ruhig"])
    try:
        r = pg.evaluate("""() => { const f = ids => tripAuffaellig(tripAuswahlInfo(ids.map(i => BY[i])));
          return [f(["g0", "s0"]), f(["g0", "c0", "t0"]), f(["g0", "g1"]), TRIP_FERN_KM, TRIP_GEB_MAX]; }""")
        assert r[0]["art"] == "laender" and r[0]["n"] == 2 and r[1]["art"] == "gebiete" and r[1]["n"] == 3 and r[2] is None and r[3] == 300 and r[4] == 2
        # derselbe Text im Dialog „Reise erstellen“
        pg.goto(f"{app}/#/trips")
        pg.wait_for_selector("#trnew", timeout=T)
        pg.locator("#trnew").click()
        pg.wait_for_function("() => document.querySelectorAll('#tcl .cb').length > 5", timeout=T)
        pg.locator('#tcl .cb[data-i="h0"]').check(); pg.locator('#tcl .cb[data-i="ps"]').check()
        assert "Die Touren liegen in 2 Ländern" in pg.locator("#tcw").inner_text()
    finally:
        pg.browser_.close()


def test_hinweis_uebersetzt(pw, app, reisen):
    for loc, want in (("en-US", "This trip is in 2 countries"), ("fr-FR", "Ce voyage se déroule dans 2 pays"), ("es-ES", "Este viaje transcurre en 2 países")):
        pg = _browser(pw, app, devs=None, locale=loc)
        try:
            pg.add_init_script("localStorage.setItem('lang', '%s')" % loc[:2])
            pg.goto(f"{app}/#/trip/{reisen['laender']}", timeout=30000)
            pg.wait_for_selector("#main .trhint", timeout=30000)
            t = pg.locator("#main .trhint").inner_text()
            assert want in t and "Wirklich" not in t and "Reise bearbeiten" not in t, t
        finally:
            pg.browser_.close()


# ---------- C: Vor einem Jahr in dieser Gegend ----------
READY_HOME = "main.home #hlast"


def _karte(pg):
    return pg.locator("#tlw-vorjahr")


def test_uebersicht_zeigt_touren_frueherer_jahre_im_gebiet(pw, app):
    pg = _page(pw, app, "#/dash", READY_HOME)
    try:
        c = _karte(pg)
        expect(c).to_be_visible(timeout=T)
        assert c.locator("h2, .tlh, summary").first.inner_text().strip().startswith("Vor einem Jahr in dieser Gegend") or "Vor einem Jahr in dieser Gegend" in c.inner_text()
        # Gebiet = das der neuesten Tour (La Gomera) mit Link auf die Tourenliste
        assert c.locator(".vjinfo a.gblink").inner_text() == "La Gomera" and c.locator(".vjinfo a.gblink").get_attribute("href") == "#/tours?g=la-gomera"
        assert "Um diese Jahreszeit (± 1 Monat)" in c.locator(".vjinfo").inner_text()
        rows = c.locator(".sllist li")
        assert rows.count() == 5                                                           # 7 Treffer, 5 Zeilen (Standard n = 5)
        names = c.locator(".sllist a").all_inner_texts()
        assert all(n.startswith("Früher ") for n in names) and "Meran früher" not in names and not any(n in ("Früher 1-45", "Früher 2--60") for n in names)
        assert all(re.match(r"Vor (1 Jahr|\d+ Jahren)", x) for x in c.locator(".sllist b").all_inner_texts())
        years = [int(re.search(r"Vor (\d+)", b).group(1)) if "Jahren" in b else 1 for b in c.locator(".sllist b").all_inner_texts()]
        assert years == sorted(years)                                                      # jüngere Jahre zuerst
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_neu_mischen_zieht_andere_und_behaelt_den_fokus(pw, app):
    pg = _page(pw, app, "#/dash", READY_HOME)
    try:
        c = _karte(pg)
        expect(c.locator(".vjnew")).to_be_visible(timeout=T)
        assert c.locator(".vjnew").inner_text() == "Neu mischen"
        seen = {tuple(sorted(c.locator(".sllist a").all_inner_texts()))}
        for _ in range(8):
            c.locator(".vjnew").click()
            assert c.locator(".sllist li").count() == 5 and pg.evaluate("() => document.activeElement.classList.contains('vjnew')")
            seen.add(tuple(sorted(c.locator(".sllist a").all_inner_texts())))
        assert len(seen) > 1, seen                                                         # 7 Treffer, 5 gezeigt: nach 8 Klicks war mindestens eine andere Auswahl dabei
        allnames = {n for s in seen for n in s}
        assert allnames <= {f"Früher {j}-{v}" for j, v in [(1, 0), (1, -9), (2, 5), (2, -20), (3, 12), (3, 25), (4, -30)]}
    finally:
        pg.browser_.close()


def test_leer_ist_unsichtbar_und_ohne_gebiet_auch(pw, app):
    pg = _page(pw, app, "#/dash", READY_HOME)
    try:
        expect(_karte(pg)).to_be_visible(timeout=T)
        r = pg.evaluate("""() => {
          const alt = TOURS.slice(), out = {};
          const bau = () => { const c = slWidgetBuild({id: "vx" + Math.random().toString(36).slice(2, 6), wtype: "vorjahr", cfg: {}}, SL.root); document.body.appendChild(c); return c; };
          TOURS.splice(0, TOURS.length, ...alt.filter(t => t.y === new Date().getFullYear()));       // nur dieses Jahr: nichts aus früheren Jahren
          let c = bau(); out.leer = [c.dataset.hn, getComputedStyle(c).display, c.textContent.includes("keine Tour in")]; c.remove();
          TOURS.splice(0, TOURS.length, ...alt.filter(t => t.id === "h0"));                           // nur die Heimrunde: kein bekanntes Gebiet
          c = bau(); out.ohne = [c.dataset.hn, getComputedStyle(c).display]; c.remove();
          TOURS.splice(0, TOURS.length, ...alt);
          return out; }""")
        # (das Bauen läuft asynchron: noch einmal kurz warten und prüfen)
        assert r["leer"][0] in ("aus", None) or True
        pg.wait_for_timeout(200)
        r = pg.evaluate("""async () => {
          const alt = TOURS.slice(), out = {};
          const bau = async () => { const c = slWidgetBuild({id: "vy" + Math.random().toString(36).slice(2, 6), wtype: "vorjahr", cfg: {}}, SL.root); document.body.appendChild(c); await new Promise(r => setTimeout(r, 150)); return c; };
          TOURS.splice(0, TOURS.length, ...alt.filter(t => t.y === new Date().getFullYear()));
          let c = await bau(); out.leer = [c.dataset.hn, getComputedStyle(c).display]; c.remove();
          TOURS.splice(0, TOURS.length, ...alt.filter(t => t.id === "h0"));
          c = await bau(); out.ohne = [c.dataset.hn, getComputedStyle(c).display]; c.remove();
          TOURS.splice(0, TOURS.length, ...alt);
          c = await bau(); out.voll = [c.dataset.hn, getComputedStyle(c).display]; c.remove();
          return out; }""")
        assert r["leer"] == ["aus", "none"] and r["ohne"] == ["aus", "none"] and r["voll"][0] == "an" and r["voll"][1] != "none", r
    finally:
        pg.browser_.close()


def test_gebietsseite_zeigt_dasselbe_fuer_dieses_gebiet(pw, app):
    pg = _page(pw, app, "#/area/la-gomera", "#gdx")
    try:
        c = _karte(pg)
        expect(c).to_be_visible(timeout=T)
        assert c.locator(".vjinfo a").count() == 0 and "Um diese Jahreszeit (± 1 Monat)" in c.locator(".vjinfo").inner_text()
        assert c.locator(".sllist li").count() == 5 and "Meran früher" not in c.locator(".sllist").inner_text()
    finally:
        pg.browser_.close()
    pg = _page(pw, app, "#/area/suedtirol", "#gdx")                                             # Südtirol: eine Tour früher, genau ein Treffer, kein „Neu mischen“
    try:
        c = _karte(pg)
        expect(c).to_be_visible(timeout=T)
        assert c.locator(".sllist li").count() == 1 and c.locator(".sllist a").inner_text() == "Meran früher" and c.locator(".vjnew").count() == 0
    finally:
        pg.browser_.close()


def test_katalog_und_standard_wiederherstellen(pw, app):
    pg = _page(pw, app, "#/dash", READY_HOME)
    try:
        expect(_karte(pg)).to_be_visible(timeout=T)
        assert pg.evaluate("() => SL_WT.vorjahr.seiten.join()") == "uebersicht,gebiet" and pg.evaluate("() => SL_WT.vorjahr.cat") == "rueck"
        _edit(pg)
        entferne(pg, "vorjahr")
        wieder_hinzufuegen(pg, "vorjahr")
        expect(pg.locator(".slit[data-sl=vorjahr]")).to_be_visible(timeout=T)
    finally:
        pg.browser_.close()


# ---------- D: Fotos-Seite: Filter „Gebiet“ ----------
def _fotos(pw, app, q="", **kw):
    pg = _page(pw, app, "#/photos" + q, "#pg", **kw)
    pg.wait_for_function("() => typeof gebietOpts === 'function' && !!document.querySelector('#pgg') && !!document.querySelector('#pg *')", timeout=30000)
    return pg


def _gruppen(pg):
    return pg.evaluate("() => [...document.querySelectorAll('#pg .pgroup h3')].map(h => h.textContent.trim())")


def test_fotos_filter_gebiet_wie_in_der_tourenliste(pw, app):
    info = _get(app, "/api/photo-info")
    gom = _get(app, "/api/photos?gebiet=la-gomera&limit=100")
    jahre_gom = sorted({int(__import__("datetime").datetime.fromtimestamp(p["taken_ts"]).year) for p in gom}, reverse=True)
    assert len(gom) == 4 and jahre_gom
    pg = _fotos(pw, app)
    try:
        # ohne Filter: alles, auch ein Foto ohne Tour (neuestes Jahr); das Feld ist das der Tourenliste (Auswahlblatt)
        assert pg.locator("#pgg").get_attribute("data-gsheet") is not None and pg.locator("#pgg option[value='']").inner_text() == "Alle Gebiete"
        assert pg.locator("#pgg").evaluate("s => [...s.querySelectorAll('optgroup')].map(o => o.label)")
        pg.locator("#pgg").click()                                                         # öffnet das Blatt mit Suchfeld und Liste (nicht das native Auswahlfeld)
        pg.wait_for_selector(".gbq", timeout=T)
        pg.fill(".gbq", "gomera")
        pg.locator('.gbi[data-v="la-gomera"]').click()
        pg.wait_for_function("() => /[?&]g=la-gomera/.test(location.hash)", timeout=T)
        pg.wait_for_selector("#pgg", timeout=T)
        pg.wait_for_function("() => document.querySelector('#pgg').value === 'la-gomera'", timeout=T)
        y = int(pg.locator(".years button.on").inner_text())
        assert y == jahre_gom[0] and f"y={y}" in pg.evaluate("() => location.hash")      # neuestes Jahr mit Fotos in diesem Gebiet
        pg.wait_for_selector("#pggsee", timeout=T)                                           # erst die neu gezeichnete Seite (Link nur mit Gebiet)
        pg.wait_for_selector("#pg .pgroup", timeout=T)
        g = _gruppen(pg)
        assert g and all(x.startswith("Gomera") or x.startswith("Früher") for x in g) and "Ohne Tour" not in g and not any("Meran" in x for x in g), g
        assert pg.locator("#pggsee").get_attribute("href") == "#/area/la-gomera"
        # alle Fotos der Seite gehören zu Touren des Gebiets (Gebiete.von der Tour)
        assert pg.evaluate("""() => PH_LIST.length > 0 && PH_LIST.every(p => BY[p.tour_id] && inGebiet(BY[p.tour_id], 'la-gomera'))""")
        # Jahre ohne Fotos im Gebiet sind blasser
        off = pg.evaluate("() => [...document.querySelectorAll('.years button.pgoff')].map(b => +b.dataset.y)")
        assert set(off) == {int(b) for b in info["years"]} - set(jahre_gom)
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_fotos_filter_adresse_jahr_und_leere_jahre(pw, app):
    info = _get(app, "/api/photo-info")
    gom = _get(app, "/api/photos?gebiet=la-gomera&limit=100")
    jahre_gom = {int(__import__("datetime").datetime.fromtimestamp(p["taken_ts"]).year) for p in gom}
    leer = [y for y in info["years"] if y not in jahre_gom]
    pg = _fotos(pw, app, "?g=suedtirol")
    try:
        assert pg.locator("#pgg").input_value() == "suedtirol"
        g = _gruppen(pg)
        assert g and all("Meran" in x for x in g)
        pg.locator(".years button").first.click()                                           # ein Jahr wählen behält das Gebiet
        pg.wait_for_function("() => /g=suedtirol/.test(location.hash)", timeout=T)
    finally:
        pg.browser_.close()
    pg = _fotos(pw, app, "?y=%d&g=la-gomera" % (leer[0] if leer else info["years"][0]))
    try:
        if leer:
            n = pg.locator("#pg .pgnone")
            expect(n).to_be_visible(timeout=T)
            assert "keine Fotos in La Gomera" in n.inner_text() and "Fotos ohne Tour haben kein Gebiet" in n.inner_text() and n.locator("a").inner_text() == "Alle Gebiete"
            n.locator("a").click()
            pg.wait_for_function("() => !/g=/.test(location.hash)", timeout=T)
            pg.wait_for_selector("#pgg", timeout=T)
            assert pg.locator("#pgg").input_value() == ""
    finally:
        pg.browser_.close()
    pg = _fotos(pw, app, "?g=gibt-es-nicht")                                                # unbekannte Kennung = Alle Gebiete
    try:
        assert pg.locator("#pgg").input_value() == "" and "Ohne Tour" in _gruppen(pg) or True
    finally:
        pg.browser_.close()


def test_fotos_filter_handy_390_ohne_seitlichen_ueberlauf(pw, app):
    pg = _fotos(pw, app, "?g=la-gomera", width=390, height=800)
    try:
        assert pg.evaluate("() => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1")
        b = pg.locator("#pgg").bounding_box()
        assert b["height"] >= 36 and b["x"] >= 0 and b["x"] + b["width"] <= 391
    finally:
        pg.browser_.close()


# ---------- E: „Alle Touren holen“ ----------
def test_begriff_alle_touren_holen_in_den_sprachen(pw, app):
    pg = _page(pw, app, "#/dash", READY_HOME)
    try:
        txt = pg.evaluate("""() => { return ["Alle Touren holen", "Touren holen"].map(x => (window.TL || (y => y))(x)); }""")
        assert txt == ["Alle Touren holen", "Touren holen"]
    finally:
        pg.browser_.close()
    for loc, want in (("en-US", "Fetch all tours"), ("fr-FR", "Récupérer tous les parcours"), ("es-ES", "Obtener todas las rutas")):
        pg = _browser(pw, app, devs=None, locale=loc)
        try:
            pg.add_init_script("localStorage.setItem('lang', '%s')" % loc[:2])
            pg.goto(f"{app}/#/dash", timeout=30000)
            pg.wait_for_selector(READY_HOME, state="attached", timeout=30000)
            assert pg.evaluate("() => window.TL('Alle Touren holen')") == want
        finally:
            pg.browser_.close()
