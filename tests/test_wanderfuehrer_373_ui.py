"""3.74.0 – Wanderführer in der Oberfläche (Browser, Chromium): Ordner anlegen/umbenennen/löschen/Bücher verschieben, Buch und Buchtour umbenennen/verschieben/löschen,
Export als Datei und Import mit Vorschau, Tournamen angleichen (Vorschau Alt → Neu, nichts vorgewählt, Komoot-Schalter mit Bestätigung, Fehler je Tour, Rückgängig),
Handy 390 px (Touch-Ziele, kein Seitwärtsscrollen, klebende Fußzeile), Englisch. Komoot wird nie angerufen: die Zugangsdaten sind Platzhalter, der Server-Aufruf wird im Browser abgefangen."""
import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import pytest

expect = pytest.importorskip("playwright.sync_api").expect

from tests.helpers_ui import T, quiet, settled  # noqa: E402
from tests.test_tourseite_ui import _wait  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent

SEED = r"""
import sys, os, time, json; sys.path.insert(0, %(root)r); os.environ['DATA_DIR'] = %(data)r
from app import db, routes
db.init()
now = int(time.time())
def line(lat, lon, n=60):
    return [[round(lat + j * 0.0005, 5), round(lon + j * 0.0004, 5)] for j in range(n)]
for book, n, lat, lon in (("Rother Allgäu", 6, 47.5, 11.0), ("Rother Harz", 3, 51.7, 10.6), ("Rother Eifel", 3, 50.3, 6.7)):
    for i in range(n):
        db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES(?,?,?,?,?)", (book, "%%d %%s Tour %%d" %% (i + 1, book.split()[-1], i + 1), json.dumps(line(lat + i * 0.02, lon)), 3.0 + i, 200 + 10 * i))
for tid, name, lat, lon, k in (("k1", "Mittwochsrunde", 47.5, 11.0, 3), ("k2", "Seeumrundung", 47.52, 11.0, 2)):
    ts = now - 86400 * k
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,status) VALUES(?,?,?,?,?,?,?,?)", (tid, name, "hike", ts, ts + 3600, 3000, 3600, "x"))
    routes.store(tid, [(lat + j * 0.0005, lon + j * 0.0004 + 0.0002, 500, j) for j in range(60)])
db.put("komoot_email", "platzhalter@example.invalid"); db.put("komoot_password", "platzhalter-passwort")
"""

LAUNCH = r"""
import sys, os; sys.path.insert(0, %(root)r)
import uvicorn
from app.main import app
uvicorn.run(app, host="127.0.0.1", port=%(port)d, log_level="warning")
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("wf373")
    data = tmp / "data"
    env = dict(os.environ, DATA_DIR=str(data), PHOTOS_DIR=str(tmp / "p"), BACKUP_DIR=str(tmp / "b"), MT_NO_SCHEDULER="1", MT_NO_WARM="1")
    out = subprocess.run([sys.executable, "-c", SEED % {"root": str(ROOT), "data": str(data)}], capture_output=True, text=True, cwd=ROOT, env=env)
    assert out.returncode == 0, out.stderr
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    script = tmp / "launch.py"
    script.write_text(LAUNCH % {"root": str(ROOT), "port": port})
    pr = subprocess.Popen([sys.executable, "-u", str(script)], cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    _wait(url)
    yield {"url": url, "tmp": tmp}
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


def _page(pw, app, width=1280, lang="de", scheme="light"):
    b = pw.chromium.launch()
    ctx = b.new_context(locale="de-DE", viewport={"width": width, "height": 900 if width > 500 else 844}, color_scheme=scheme, device_scale_factor=1, reduced_motion="reduce",
                        service_workers="block", accept_downloads=True)
    ctx.add_init_script("try { localStorage.setItem('lang', %r); %s } catch (e) {}" % (lang, "localStorage.setItem('viewmode', 'mobile');" if width < 500 else ""))
    pg = ctx.new_page()
    pg.errors = []
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.b_ = b
    pg.goto(app["url"] + "/#/places")
    pg.wait_for_selector("#gfl details.gfb, #gfempty", timeout=T)
    quiet(pg, 3000)
    return pg


def _card(pg, book):
    return pg.locator("details.gfb", has=pg.locator(".gfname", has_text=book))


def _msg(pg, text):
    expect(pg.locator("#gfmsg")).to_have_text(text, timeout=T)


def _dlg(pg):
    return pg.locator(".uibox")


def _btn(pg, label):
    return pg.locator(".uibox .uifoot button", has_text=label).last


def _open_card(pg, book):
    c = _card(pg, book)
    if c.get_attribute("open") is None:
        c.locator("summary").click()
    expect(c.locator(".gfbody .gfacts")).to_be_visible(timeout=T)
    return c


def _reload_wait(pg):
    quiet(pg, 3000)


def test_ordner_anlegen_umbenennen_verschieben_loeschen(pw, app):
    pg = _page(pw, app)
    assert pg.locator(".gfsec").count() == 0                                                  # ohne Ordner: flache Liste wie bisher
    pg.click("#gffold")
    expect(_dlg(pg).locator("h2")).to_have_text("Neuer Ordner")
    _dlg(pg).locator(".uipin").fill("Süddeutschland")
    _btn(pg, "Anlegen").click()
    _msg(pg, "Ordner „Süddeutschland“ gespeichert")
    expect(pg.locator(".gfsec")).to_have_count(2)                                              # der neue (leere) Ordner und „Ohne Ordner“
    expect(pg.locator('.gfsec[data-fi="0"] .gfleer')).to_contain_text("Leer.")
    expect(pg.locator('.gfsec[data-fi="-1"] details.gfb')).to_have_count(3)
    # gleicher Name (andere Schreibweise): Fehlerdialog „<Vorgang> nicht möglich“, nichts ändert sich
    pg.click("#gffold")
    _dlg(pg).locator(".uipin").fill("süddeutschland")
    _btn(pg, "Anlegen").click()
    expect(_dlg(pg).locator("h2")).to_have_text("Ordner anlegen nicht möglich")
    expect(_dlg(pg)).to_contain_text("Einen Ordner „süddeutschland“ gibt es schon")
    _btn(pg, "Schließen").click()
    # Buch in den Ordner verschieben
    c = _open_card(pg, "Rother Harz")
    c.locator(".gfact").click()
    expect(_dlg(pg).locator("h2")).to_have_text("Rother Harz")
    _dlg(pg).locator("[data-m=mv]").click()
    expect(_dlg(pg).locator("h2")).to_have_text("In Ordner verschieben")
    expect(_dlg(pg).locator("#gfsel")).to_have_value("Süddeutschland")
    _btn(pg, "Verschieben").click()
    _msg(pg, "„Rother Harz“ in „Süddeutschland“ verschoben")
    assert pg.locator('.gfsec[data-fi="0"] details.gfb').count() == 1 and pg.locator('.gfsec[data-fi="-1"] details.gfb').count() == 2
    # neuer Ordner beim Verschieben
    c = _open_card(pg, "Rother Eifel")
    c.locator(".gfact").click()
    _dlg(pg).locator("[data-m=mv]").click()
    _dlg(pg).locator("#gfsel").select_option("\u0001")
    expect(_btn(pg, "Verschieben")).to_be_disabled()
    _dlg(pg).locator("#gfnn").fill("Mittelgebirge")
    _btn(pg, "Verschieben").click()
    _msg(pg, "„Rother Eifel“ in „Mittelgebirge“ verschoben")
    expect(pg.locator(".gfsec")).to_have_count(3)
    # Ordner umbenennen (Bücher folgen)
    pg.locator('.gfsec[data-fi="0"] .gfoi[data-a=ren]').click()
    expect(_dlg(pg).locator(".uipin")).to_have_value("Mittelgebirge")
    _dlg(pg).locator(".uipin").fill("Mittelgebirge Ost")
    _btn(pg, "Speichern").click()
    _msg(pg, "Ordner „Mittelgebirge Ost“ gespeichert")
    assert pg.locator(".gfsec .gfot b").all_inner_texts() == ["Mittelgebirge Ost", "Süddeutschland", "Ohne Ordner"]
    assert pg.locator('.gfsec[data-fi="0"] .gfname').inner_text() == "Rother Eifel"
    # Bücher aus dem Ordner nehmen
    c = _open_card(pg, "Rother Harz")
    c.locator(".gfact").click()
    _dlg(pg).locator("[data-m=un]").click()
    _msg(pg, "„Rother Harz“ aus dem Ordner entfernt")
    # Ordner löschen: nur der Ordner, nie Bücher
    pg.locator('.gfsec[data-fi="0"] .gfoi[data-a=del]').click()
    expect(_dlg(pg).locator("h2")).to_have_text("Ordner „Mittelgebirge Ost“ löschen?")
    expect(_dlg(pg)).to_contain_text("Das Buch darin bleibt erhalten und kommt zurück nach „Ohne Ordner“.")
    expect(_btn(pg, "Löschen")).to_be_visible()
    _btn(pg, "Abbrechen").click()
    expect(pg.locator("details.gfb")).to_have_count(3)
    pg.locator('.gfsec[data-fi="0"] .gfoi[data-a=del]').click()
    _btn(pg, "Löschen").click()
    _msg(pg, "Ordner gelöscht")
    expect(pg.locator("details.gfb")).to_have_count(3)                                            # alle drei Bücher noch da
    pg.locator('.gfsec[data-fi="0"] .gfoi[data-a=del]').click()
    _btn(pg, "Löschen").click()
    _msg(pg, "Ordner gelöscht")
    expect(pg.locator(".gfsec")).to_have_count(0)                                              # keine Ordner mehr: flache Liste
    expect(pg.locator("details.gfb")).to_have_count(3)
    assert not pg.errors, pg.errors
    pg.b_.close()


def test_buch_und_buchtour_umbenennen_verschieben_loeschen(pw, app):
    pg = _page(pw, app)
    c = _open_card(pg, "Rother Eifel")
    c.locator(".gfact").click()
    _dlg(pg).locator("[data-m=ren]").click()
    expect(_dlg(pg).locator("h2")).to_have_text("Buch umbenennen")
    _dlg(pg).locator(".uipin").fill("Rother Harz")                                           # gibt es schon
    _btn(pg, "Speichern").click()
    expect(_dlg(pg).locator("h2")).to_have_text("Umbenennen nicht möglich")
    expect(_dlg(pg)).to_contain_text("Ein Buch „Rother Harz“ gibt es schon")
    _btn(pg, "Schließen").click()
    c = _open_card(pg, "Rother Eifel")
    c.locator(".gfact").click()
    _dlg(pg).locator("[data-m=ren]").click()
    _dlg(pg).locator(".uipin").fill("Rother Eifel Nord")
    _btn(pg, "Speichern").click()
    _msg(pg, "Name gespeichert")
    c = _open_card(pg, "Rother Eifel Nord")
    # Buchtour umbenennen
    c.locator(".gfrm").first.click()
    expect(_dlg(pg).locator("h2")).to_have_text("1 Eifel Tour 1")
    _dlg(pg).locator("[data-m=ren]").click()
    _dlg(pg).locator(".uipin").fill("1 Eifel Maarrunde")
    _btn(pg, "Speichern").click()
    _msg(pg, "Name gespeichert")
    c = _open_card(pg, "Rother Eifel Nord")
    assert "1 Eifel Maarrunde" in c.locator(".gfrows .r").all_inner_texts()[0]
    # Buchtour in ein anderes Buch verschieben (Zielbuch aus der Liste), dann ins neue Buch
    c.locator(".gfrm").first.click()
    _dlg(pg).locator("[data-m=mv]").click()
    expect(_dlg(pg).locator("h2")).to_have_text("Buchtour verschieben")
    assert "Rother Eifel Nord" not in _dlg(pg).locator("#gfsel").inner_text()                # nicht das eigene Buch
    _dlg(pg).locator("#gfsel").select_option("Rother Harz")
    _btn(pg, "Verschieben").click()
    _msg(pg, "„1 Eifel Maarrunde“ in „Rother Harz“ verschoben")
    expect(_card(pg, "Rother Eifel Nord").locator(".gfn")).to_have_text("0 von 2 gewandert")
    expect(_card(pg, "Rother Harz").locator(".gfn")).to_have_text("0 von 4 gewandert")
    c = _open_card(pg, "Rother Eifel Nord")
    c.locator(".gfrm").first.click()
    _dlg(pg).locator("[data-m=mv]").click()
    _dlg(pg).locator("#gfsel").select_option("\u0001")
    _dlg(pg).locator("#gfnn").fill("Sammelbuch")
    _btn(pg, "Verschieben").click()
    _msg(pg, "„2 Eifel Tour 2“ in „Sammelbuch“ verschoben")
    expect(_card(pg, "Sammelbuch")).to_have_count(1)
    # Buchtour löschen (Rückfrage mit Namen, Knopf „Löschen“), Buch löschen
    c = _open_card(pg, "Rother Eifel Nord")
    c.locator(".gfrm").first.click()
    _dlg(pg).locator("[data-m=del]").click()
    expect(_dlg(pg).locator("h2")).to_have_text("Buchtour „3 Eifel Tour 3“ löschen?")
    _btn(pg, "Löschen").click()
    _msg(pg, "Buchtour gelöscht")
    expect(_card(pg, "Rother Eifel Nord")).to_have_count(0)                                  # letzte Buchtour weg = Buch weg
    c = _open_card(pg, "Sammelbuch")
    c.locator(".gfact").click()
    _dlg(pg).locator("[data-m=del]").click()
    expect(_dlg(pg).locator("h2")).to_have_text("Buch „Sammelbuch“ löschen?")
    expect(_dlg(pg)).to_contain_text("Das Buch mit 1 Buchtour wird gelöscht")
    _btn(pg, "Löschen").click()
    _msg(pg, "Buch gelöscht")
    expect(_card(pg, "Sammelbuch")).to_have_count(0)
    assert not pg.errors, pg.errors
    pg.b_.close()


def test_buch_anlegen_mit_gpx_dateien_und_doppelte_nicht_doppelt(pw, app):
    gpx = '<?xml version="1.0"?><gpx version="1.1" creator="t"><trk><name>%s</name><trkseg>%s</trkseg></trk></gpx>'
    pts = "".join('<trkpt lat="%.5f" lon="9.00000"><ele>%d</ele></trkpt>' % (46 + i * 0.001, 500 + i) for i in range(30))
    pg = _page(pw, app)
    pg.click("#gfadd")
    expect(_dlg(pg).locator("h2")).to_have_text("Buch anlegen")
    expect(_btn(pg, "Anlegen")).to_be_disabled()
    _dlg(pg).locator("#gfbn").fill("Rother Neubuch")
    _dlg(pg).locator("#gfbf").set_input_files([{"name": "a.gpx", "mimeType": "application/gpx+xml", "buffer": (gpx % ("Gipfelrunde", pts)).encode()},
                                                {"name": "b.gpx", "mimeType": "application/gpx+xml", "buffer": (gpx % ("Gipfelrunde", pts)).encode()}])
    _btn(pg, "Anlegen").click()
    _msg(pg, "1 Buchtour angelegt · 1 schon vorhanden")
    assert _card(pg, "Rother Neubuch").locator(".gfn").inner_text() == "0 von 1 gewandert"
    pg.b_.close()


def test_buch_anlegen_mit_zip_titelbild_und_doppel_pruefung(pw, app):
    import io
    import zipfile
    from PIL import Image
    pts = "".join(f'<trkpt lat="{47.3 + j * 0.0005:.5f}" lon="{9.0 + j * 0.0004:.5f}"><ele>{500 + j}</ele></trkpt>' for j in range(60))
    g = lambda n: f'<?xml version="1.0"?><gpx version="1.1"><trk><name>{n}</name><trkseg>{pts}</trkseg></trk></gpx>'
    im = io.BytesIO()
    Image.new("RGB", (400, 300), (30, 90, 140)).save(im, "PNG")
    zb = io.BytesIO()
    with zipfile.ZipFile(zb, "w") as z:
        z.writestr("a.gpx", g("ZIP-Runde"))
        z.writestr("titel.png", im.getvalue())
    zdata = zb.getvalue()
    pg = _page(pw, app)
    pg.click("#gfadd")
    # Bei reiner ZIP-Auswahl ist der Buchname frei (Name der Datei)
    _dlg(pg).locator("#gfbf").set_input_files([{"name": "Zipbuch.zip", "mimeType": "application/zip", "buffer": zdata}])
    expect(_btn(pg, "Anlegen")).to_be_enabled()
    _dlg(pg).locator("#gfbn").fill("Zip Buch")
    _btn(pg, "Anlegen").click()
    _msg(pg, "1 Buchtour angelegt · Titelbild übernommen")
    assert _card(pg, "Zip Buch").locator(".gfn").inner_text() == "0 von 1 gewandert"
    # nochmal (andere Schreibweise des Buchnamens): nichts doppelt, kein zweites Buch
    pg.click("#gfadd")
    _dlg(pg).locator("#gfbn").fill("zip buch")
    _dlg(pg).locator("#gfbf").set_input_files([{"name": "Zipbuch.zip", "mimeType": "application/zip", "buffer": zdata}])
    _btn(pg, "Anlegen").click()
    _msg(pg, "0 Buchtouren angelegt · 1 schon vorhanden")
    assert pg.locator("details.gfb", has=pg.locator(".gfname", has_text="Zip Buch")).count() == 1
    pg.b_.close()


def test_export_und_import_mit_vorschau(pw, app, tmp_path):
    pg = _page(pw, app)
    pg.click("#gfexp")
    expect(_dlg(pg).locator("h2")).to_have_text("Wanderführer exportieren")
    with pg.expect_download() as dl:
        _btn(pg, "Exportieren").click()
    d = json.loads(Path(dl.value.path()).read_text(encoding="utf-8"))
    assert dl.value.suggested_filename.startswith("Meine-Touren-Wanderfuehrer-") and dl.value.suggested_filename.endswith(".json")
    assert d["format"] == "tourentagebuch-wanderfuehrer" and d["version"] == 1 and "Rother Allgäu" in [b["name"] for b in d["buecher"]]
    _msg(pg, "Wanderführer exportiert: %d %s" % (len(d["buecher"]), "Buch" if len(d["buecher"]) == 1 else "Bücher"))
    # Import: erst Vorschau, dann Importieren; Unterschiede werden genannt, Vorhandenes bleibt
    def pk(lat):
        la = [round((lat + j * 0.0005) * 1e5) for j in range(60)]
        lo = [round((8.0 + j * 0.0004) * 1e5) for j in range(60)]
        f = lambda a: [v - a[i - 1] if i else v for i, v in enumerate(a)]
        return {"la": f(la), "lo": f(lo)}
    datei = {"format": "tourentagebuch-wanderfuehrer", "version": 1, "buecher": [
        {"id": "x1", "name": "Rother Importbuch", "touren": [{"id": "t0", "ord": 0, "title": "Importrunde", "km": 6.0, "up": 100, "pts": pk(44.0)}, {"id": "t1", "ord": 1, "title": "Zweite Runde", "km": 7.0, "up": None, "pts": pk(44.1)}]},
        {"id": "x2", "name": "rother allgäu", "touren": [{"id": "t0", "ord": 0, "title": "1 Allgäu Tour 1", "km": 3.0, "up": 200, "pts": pk(47.5)}, {"id": "t1", "ord": 1, "title": "2 Allgäu Tour 2", "km": 9.5, "up": 1, "pts": pk(47.6)}]},
        {"name": "", "touren": []}]}
    pg.click("#gfimp")
    expect(_dlg(pg).locator("h2")).to_have_text("Wanderführer importieren")
    expect(_btn(pg, "Importieren")).to_be_disabled()
    (tmp_path / "w.json").write_text(json.dumps(datei), encoding="utf-8")
    _dlg(pg).locator("#gfif").set_input_files(str(tmp_path / "w.json"))
    expect(_dlg(pg).locator("#gfisum")).to_have_text("1 neues Buch · 1 Buchtour ist schon da.", timeout=T)
    expect(_dlg(pg).locator("#gfidef")).to_have_text("1 Eintrag ist nicht lesbar und bleibt draußen.")
    expect(_dlg(pg).locator(".gfkonf li")).to_have_text("„2 Allgäu Tour 2“ in „Rother Allgäu“: in der Datei 9,5 km, bei dir 4,0 km – nicht übernommen.")
    expect(_btn(pg, "Importieren")).to_be_enabled()
    assert _card(pg, "Rother Importbuch").count() == 0                                       # Vorschau ändert nichts
    _btn(pg, "Importieren").click()
    _msg(pg, "Importiert: 1 neues Buch · 1 Buchtour ist schon da")
    expect(_card(pg, "Rother Importbuch").locator(".gfn")).to_have_text("0 von 2 gewandert")
    expect(_card(pg, "Rother Allgäu").locator(".gfn")).to_have_text("2 von 6 gewandert")
    # fremde Datei: klare Meldung, Knopf bleibt aus
    pg.click("#gfimp")
    (tmp_path / "x.json").write_text('{"a": 1}', encoding="utf-8")
    _dlg(pg).locator("#gfif").set_input_files(str(tmp_path / "x.json"))
    expect(_dlg(pg).locator("#gfip .bad")).to_have_text("Import nicht möglich: Das ist keine Wanderführer-Datei.", timeout=T)
    expect(_btn(pg, "Importieren")).to_be_disabled()
    _btn(pg, "Abbrechen").click()
    assert not pg.errors, pg.errors
    pg.b_.close()


def test_tournamen_angleichen_vorschau_komoot_bestaetigung_fehler_und_rueckgaengig(pw, app):
    pg = _page(pw, app)
    calls = []
    pg.route("**/api/guides/rename-tours", lambda r: (calls.append(json.loads(r.request.post_data)), r.continue_())[1])
    pg.click("#gfnames")
    expect(_dlg(pg).locator("h2")).to_have_text("Tournamen angleichen")
    rows = _dlg(pg).locator(".gfnr")
    expect(rows).to_have_count(2, timeout=T)
    assert rows.nth(0).inner_text().replace("\n", " ").startswith("Seeumrundung → 2 Allgäu Tour 2")      # neueste Tour zuerst, Alt → Neu
    assert pg.locator(".gfnr input:checked").count() == 0                                    # nichts vorgewählt
    expect(_btn(pg, "Umbenennen")).to_be_disabled()
    expect(_dlg(pg).locator("#gfncnt")).to_have_text("0 von 2 gewählt")
    expect(_dlg(pg).locator("#gfnkom")).not_to_be_checked()                                  # Vorgabe: aus
    expect(_dlg(pg).locator("#gfnkh")).to_have_text("Ändert die Namen nur hier. Bei Komoot bleiben sie, wie sie sind.")
    _dlg(pg).locator("[data-all]").click()
    expect(_dlg(pg).locator("#gfncnt")).to_have_text("2 von 2 gewählt")
    # Komoot-Schalter an: Hinweis mit Anzahl; ohne Bestätigung ruft nichts den Server auf
    _dlg(pg).locator("#gfnkom").check()
    expect(_dlg(pg).locator("#gfnkh")).to_contain_text("2 Touren liegen bei Komoot und werden dort umbenannt")
    _btn(pg, "Umbenennen").click()
    expect(_dlg(pg).last.locator("h2")).to_have_text("Bei Komoot umbenennen?")
    expect(_dlg(pg).last).to_contain_text("2 Touren werden auch bei Komoot umbenannt.")
    _btn(pg, "Abbrechen").click()
    quiet(pg, 800)
    assert calls == []
    # Bestätigen, Antwort des Servers ersetzt (Komoot nie echt): Fehler je Tour sichtbar
    pg.unroute("**/api/guides/rename-tours")
    pg.route("**/api/guides/rename-tours", lambda r: (calls.append(json.loads(r.request.post_data)), r.fulfill(status=200, content_type="application/json", body=json.dumps({
        "ok": True, "batch": "b1", "umbenannt": 2, "bei_komoot": 1, "fehler": 1, "ergebnisse": [
            {"tour": "k2", "ok": True, "komoot": True, "alt": "Seeumrundung", "neu": "2 Allgäu Tour 2"},
            {"tour": "k1", "ok": True, "komoot": False, "alt": "Mittwochsrunde", "neu": "1 Allgäu Tour 1", "komoot_fehler": "Umbenennen bei Komoot fehlgeschlagen (HTTP 403)"}]})))[1])
    _btn(pg, "Umbenennen").click()
    _btn(pg, "Bei Komoot umbenennen").click()
    expect(_dlg(pg).locator("#gfnres")).to_have_text("2 Touren umbenannt", timeout=T)
    expect(_dlg(pg).locator("#gfnkres")).to_have_text("Bei Komoot umbenannt: 1")
    expect(_dlg(pg).locator("#gfnerr li")).to_have_text("„Mittwochsrunde“: Bei Komoot umbenennen nicht möglich: Umbenennen bei Komoot fehlgeschlagen (HTTP 403)")
    assert len(calls) == 1 and calls[0]["komoot"] is True and calls[0]["bestaetigt"] == 2 and sorted(i["tour"] for i in calls[0]["items"]) == ["k1", "k2"]
    assert {i["name"] for i in calls[0]["items"]} == {"1 Allgäu Tour 1", "2 Allgäu Tour 2"}
    _btn(pg, "Schließen").click()
    pg.unroute("**/api/guides/rename-tours")
    # echter Ablauf nur lokal: umbenennen, Protokoll, Rückgängig
    pg.click("#gfnames")
    expect(_dlg(pg).locator(".gfnr")).to_have_count(2, timeout=T)
    _dlg(pg).locator("[data-all]").click()
    _btn(pg, "Umbenennen").click()
    expect(_dlg(pg).locator("#gfnres")).to_have_text("2 Touren umbenannt", timeout=T)
    assert pg.locator("#gfnkres").count() == 0 and pg.locator("#gfnerr").count() == 0
    _btn(pg, "Schließen").click()
    _msg(pg, "Namen gespeichert")
    assert pg.evaluate("() => fetch('/api/tours').then(r => r.json()).then(l => l.filter(t => ['k1','k2'].includes(t.id)).map(t => t.name).sort())") == ["1 Allgäu Tour 1", "2 Allgäu Tour 2"]
    pg.click("#gfnames")
    expect(_dlg(pg).locator("#gfnone")).to_be_visible(timeout=T)                             # nichts mehr anzugleichen
    _dlg(pg).locator("[data-log]").click()
    expect(pg.locator("#gflb .gflb")).to_have_count(1, timeout=T)
    assert "Seeumrundung → 2 Allgäu Tour 2" in pg.locator("#gflb").inner_text() and "Mittwochsrunde → 1 Allgäu Tour 1" in pg.locator("#gflb").inner_text()
    pg.locator("#gflb [data-undo]").click()
    expect(pg.locator(".uibox").last.locator("h2")).to_have_text("Umbenennung rückgängig machen?")
    expect(pg.locator(".uibox").last).not_to_contain_text("Komoot")                         # lokal umbenannt: keine Frage nach Komoot
    pg.locator(".uibox .uifoot button", has_text="Rückgängig machen").last.click()
    _msg(pg, "Alte Namen wiederhergestellt")
    assert pg.evaluate("() => fetch('/api/tours').then(r => r.json()).then(l => l.filter(t => ['k1','k2'].includes(t.id)).map(t => t.name).sort())") == ["Mittwochsrunde", "Seeumrundung"]
    assert not pg.errors, pg.errors
    pg.b_.close()


def test_handy_touchziele_kein_seitwaerts_scrollen_klebende_fusszeile(pw, app):
    pg = _page(pw, app, width=390)
    settled(pg)
    assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
    for sel in ("#gfadd", "#gffold", "#gfnames", "#gfexp", "#gfimp"):
        assert pg.locator(sel).bounding_box()["height"] >= 43.5, sel
    c = _open_card(pg, "Rother Allgäu")
    for sel in (".gfact", ".gfrm"):
        assert c.locator(sel).first.bounding_box()["height"] >= 43.5, sel
    assert c.locator(".gfrm").first.bounding_box()["width"] >= 43.5
    pg.click("#gfnames")
    expect(_dlg(pg).locator(".gfnr").first).to_be_visible(timeout=T)
    _dlg(pg).locator("[data-all]").click()
    box = _dlg(pg).bounding_box()
    assert box["x"] >= -1 and box["x"] + box["width"] <= 391
    foot = pg.locator(".uibox .uifoot").bounding_box()
    assert foot["y"] + foot["height"] <= 845 and pg.evaluate("() => getComputedStyle(document.querySelector('.uibox .uifoot')).position") == "sticky"
    assert pg.evaluate("() => [...document.querySelectorAll('.uibox .uifoot .btn')].every(b => b.getBoundingClientRect().height >= 43.5)")
    assert pg.evaluate("() => document.documentElement.scrollWidth <= innerWidth + 1")
    _btn(pg, "Abbrechen").click()
    assert not pg.errors, pg.errors
    pg.b_.close()


def test_englisch_und_dunkel_ohne_emoji(pw, app):
    pg = _page(pw, app, lang="en", scheme="dark")
    expect(pg.locator("#gfadd")).to_contain_text("Add book …")
    expect(pg.locator("#gffold")).to_contain_text("New folder …")
    expect(pg.locator("#gfnames")).to_contain_text("Match tour names …")
    pg.click("#gfnames")
    expect(_dlg(pg).locator("h2")).to_have_text("Match tour names")
    expect(_dlg(pg).locator(".gfnr").first).to_be_visible(timeout=T)
    expect(_dlg(pg)).to_contain_text("Also rename on Komoot")
    assert "Alle" not in _dlg(pg).inner_text() and "Umbenennen" not in _dlg(pg).inner_text()
    _btn(pg, "Cancel").click()
    pg.click("#gfexp")
    expect(_dlg(pg)).to_contain_text("Include cover images")
    _btn(pg, "Cancel").click()
    # keine Emoji in der Oberfläche der Seite (Liniensymbole statt Zeichen)
    txt = pg.locator("#gfx").inner_text()
    assert not any(ord(ch) >= 0x1F000 or ch in "✓✗✕⚠ℹ⋯" for ch in txt), txt
    assert not pg.errors, pg.errors
    pg.b_.close()
