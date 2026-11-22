"""3.58.0 Komoot (Oberfläche, Chromium): Upload-Dialog mit „Notiz und Pins mitsenden“ und Hinweis „wird privat gesetzt“, laute Warnung bei unbestätigter
Sichtbarkeit (Dialog bleibt offen), Sichtbarkeits-Hinweis auf der Tourseite mit „Bei Komoot auf privat setzen“ (nur nach Klick und Rückfrage), Komoot-Paket-Dialog
(keine Fotos vorausgewählt, Ort entfernen an, Download-Adresse, ZIP vom Server), Rückprüfung in der Verwaltung („N öffentlich, M privat, K unbekannt“).
Alle Komoot-Antworten sind per page.route nachgebildet – es gibt keinen Netzaufruf zu Komoot. 390 px, hell und dunkel, Englisch."""
import io
import json
import os
import subprocess
import sys
import time
import urllib.request
import zipfile
from pathlib import Path

import pytest
from tests.helpers_ui import free_port, quiet, set_lang

ROOT = Path(__file__).resolve().parent.parent
pw_api = pytest.importorskip("playwright.sync_api")
expect = pw_api.expect
TL = 15000

SEED = """
import sys, os; sys.path.insert(0, {root!r}); os.environ['DATA_DIR'] = {data!r}
from app import db, tracks
db.init()
pts = "".join('<trkpt lat="%s" lon="11"><ele>%d</ele><time>2026-07-01T08:%02d:%02dZ</time></trkpt>' % (47 + i * 0.001, 1000 + i, i // 60, i % 60) for i in range(59))
g = '<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><name>G</name><trkseg>' + pts + '</trkseg></trk></gpx>'
tracks.adopt(g, "g.gpx", name="Gipfeltour", ident="g1")
db.execute("INSERT OR REPLACE INTO tour_notes(id,note) VALUES('g1','Schöner Tag')")
db.execute("INSERT INTO tour_wps(tour_id,ts,lat,lng,note) VALUES('g1',1782893000,47.01,11,'Rast')")
"""


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    d = tmp_path_factory.mktemp("kp358")
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


def _page(pw, url, w=1280, dark=False, lang="de"):
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={"width": w, "height": 860}, color_scheme="dark" if dark else "light", service_workers="block")
    ctx.add_init_script(f"try {{ localStorage.setItem('lang', '{lang}'); }} catch (e) {{}}")
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    return b, pg, errs


def _json(route, data):
    route.fulfill(status=200, content_type="application/json", body=json.dumps(data))


def _fake(pg, uploads, check=None, calls=None):
    """Komoot-Antworten nachbilden: Portale, Upload-Vermerk, Prüfung, Upload, privat setzen."""
    calls = calls if calls is not None else []
    st = {"u": uploads}
    pg.route("**/api/portals", lambda r: _json(r, {"portals": [{"id": "komoot", "name": "Komoot", "configured": True, "connected": True, "account": "a@b.de", "with_notes": True},
                                                               {"id": "strava", "name": "Strava", "configured": False, "connected": False, "account": ""}], "redirect": ""}))
    pg.route("**/api/tours/g1/uploads", lambda r: _json(r, st["u"]))
    pg.route("**/api/tours/g1/komoot-check", lambda r: (calls.append(("check", None)),
                                                         _json(r, {**check, "vis": st["u"]["komoot"]["vis"]} if check else {"checked": False})))

    def up(r):
        calls.append(("upload", json.loads(r.request.post_data or "{}")))
        _json(r, {"komoot": {"status": "uploaded", "remote_id": "555", "msg": "", "url": "https://www.komoot.com/tour/555", "vis": "public",
                             "vis_text": "ACHTUNG: bei Komoot öffentlich – bitte in Komoot prüfen",
                             "warnung": "Deine Komoot-Vorgabe für neue Aktivitäten ist „öffentlich“, und das Zurücksetzen auf „privat“ hat nicht geklappt. Bitte sofort in Komoot auf „Nur ich“ stellen oder die Tour dort löschen."}})
    pg.route("**/api/tours/g1/upload", up)

    def priv(r):
        calls.append(("privat", None))
        st["u"] = {"komoot": {**st["u"]["komoot"], "vis": "private"}}
        _json(r, {"vis": "private", "vis_text": "bei Komoot privat (bestätigt)", "ok": True, "msg": ""})
    pg.route("**/api/tours/g1/komoot-privat", priv)
    return calls


def _open_tour(pg, url):
    pg.goto(url + "/#/tour/g1")
    pg.wait_for_selector("#eup", state="attached", timeout=TL)
    quiet(pg)


def test_upload_dialog_privat_und_warnung(pw, app):
    b, pg, errs = _page(pw, app)
    calls = _fake(pg, {})
    _open_tour(pg, app)
    pg.evaluate("() => document.querySelector('#eup').click()")
    dlg = pg.locator(".uidlg.uimod")
    expect(dlg.locator("#kwn")).to_be_checked(timeout=TL)
    expect(dlg.locator(".kvnote")).to_contain_text("„privat“", timeout=TL)
    dlg.locator('.pp[value="komoot"]').check()
    dlg.locator("#uok").click()
    expect(dlg.locator(".kvwarn")).to_contain_text("sofort in Komoot", timeout=TL)
    expect(dlg.locator(".kvis.bad")).to_be_visible()
    assert [c for c in calls if c[0] == "upload"][0][1]["with_notes"] is True
    expect(dlg).to_be_visible()                                       # bleibt offen, solange „privat“ nicht bestätigt ist
    # Häkchen aus: with_notes=false wird gesendet
    dlg.locator("#kwn").uncheck()
    dlg.locator("#uok").click()
    pg.wait_for_function("() => document.querySelectorAll('.kvwarn').length >= 1", timeout=TL)
    quiet(pg)
    assert [c for c in calls if c[0] == "upload"][-1][1]["with_notes"] is False
    assert not errs, errs
    b.close()


def test_tourseite_hinweis_und_privat_nur_per_klick(pw, app):
    b, pg, errs = _page(pw, app)
    calls = _fake(pg, {"komoot": {"status": "uploaded", "remote_id": "555", "msg": "", "ts": 1, "url": "https://www.komoot.com/tour/555", "vis": "public"}},
                  check={"checked": True, "exists": True, "type": "tour_recorded", "vis": "public"})
    _open_tour(pg, app)
    expect(pg.locator("#upst .kvis.bad")).to_contain_text("öffentlich", timeout=TL)
    assert not [c for c in calls if c[0] == "privat"]                # nichts von selbst
    pg.locator("#kpriv").click()
    conf = pg.locator(".uidlg:not(.uimod)")
    expect(conf).to_contain_text("privat", timeout=TL)
    conf.locator(".uifoot .btn:not(.ghost)").click()
    expect(pg.locator("#upst .kvis.ok")).to_contain_text("privat bestätigt", timeout=TL)
    assert [c[0] for c in calls].count("privat") == 1
    expect(pg.locator("#kpriv")).to_have_count(0)
    assert not errs, errs
    b.close()


@pytest.mark.parametrize("w,dark,lang", [(1280, False, "de"), (390, True, "de"), (390, False, "en")])
def test_komoot_paket_dialog(pw, app, w, dark, lang):
    b, pg, errs = _page(pw, app, w=w, dark=dark, lang=lang)
    _fake(pg, {})
    pg.route("**/api/photos?tour_id=g1*", lambda r: _json(r, [{"id": 11, "taken_ts": 1782893100, "v": "a"}, {"id": 12, "taken_ts": 1782893200, "v": "b"},
                                                             {"id": 13, "taken_ts": 1782893300, "v": "c"}]))
    pg.route("**/pic/1[123]*", lambda r: r.fulfill(status=404, body=""))
    _open_tour(pg, app)
    pg.evaluate("() => document.querySelector('#ekpk').click()")
    dlg = pg.locator(".uidlg.uimod")
    expect(dlg.locator(".kpcb")).to_have_count(3, timeout=TL)
    assert dlg.locator(".kpcb:checked").count() == 0                  # Vorgabe: kein Foto
    expect(dlg.locator("#kpo")).to_be_checked()
    expect(dlg.locator("#kpn")).to_be_checked()
    href = dlg.locator("#kpd").get_attribute("href")
    assert href.startswith("/api/tours/g1/komoot-paket?") and "fotos" not in href and "ohne_ort=1" in href and "notiz=1" in href
    dlg.locator(".kpf").nth(0).click()
    dlg.locator(".kpf").nth(2).click()
    dlg.locator("#kpo").uncheck()
    href = dlg.locator("#kpd").get_attribute("href")
    assert "fotos=11%2C13" in href and "ohne_ort=0" in href
    if lang == "de":
        expect(dlg.locator("#kpc")).to_have_text("2 Fotos ausgewählt")
        expect(dlg.locator(".kpwarn")).to_contain_text("erkennt keine Gesichter")
    else:
        expect(dlg.locator("h2")).to_contain_text("Komoot package", timeout=TL)
        expect(dlg.locator("#kpc")).to_have_text("2 photos selected", timeout=TL)
        expect(dlg.locator(".kpwarn")).to_contain_text("does not detect faces")
    over = pg.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    assert over <= 1, over
    box = dlg.locator(".uibox").bounding_box()
    assert box["x"] >= 0 and box["x"] + box["width"] <= w + 1
    # Kontrast des Warnkastens (Text gegen Hintergrund) mindestens 4,5:1
    ratio = pg.evaluate("""() => {
      const el = document.querySelector('.kpwarn'), cs = getComputedStyle(el);
      const rgb = s => { const c = document.createElement('canvas').getContext('2d'); c.fillStyle = s; c.fillRect(0, 0, 1, 1); return [...c.getImageData(0, 0, 1, 1).data].slice(0, 3); };
      const L = a => { const v = a.map(x => { x /= 255; return x <= .03928 ? x / 12.92 : ((x + .055) / 1.055) ** 2.4; }); return .2126 * v[0] + .7152 * v[1] + .0722 * v[2]; };
      const a = L(rgb(cs.color)), bg = L(rgb(cs.backgroundColor));
      return (Math.max(a, bg) + .05) / (Math.min(a, bg) + .05);
    }""")
    assert ratio >= 4.5, ratio
    # Der Server liefert das Paket (ohne Fotos, die es hier nicht gibt)
    r = pg.request.get(app + "/api/tours/g1/komoot-paket?notiz=1&ohne_ort=1")
    assert r.status == 200
    z = zipfile.ZipFile(io.BytesIO(r.body()))
    assert "README.txt" in z.namelist() and "<wpt" in z.read("Gipfeltour.gpx").decode()
    assert not errs, errs
    b.close()


def test_tourmenue_hat_komoot_paket(pw, app):
    b, pg, errs = _page(pw, app, w=390)
    _fake(pg, {})
    pg.route("**/api/photos?tour_id=g1*", lambda r: _json(r, []))
    _open_tour(pg, app)
    pg.locator('.tact-bar button[data-g="share"]').click()
    pg.locator('[data-e="ekpk"]').click()
    expect(pg.locator(".uidlg.uimod h2")).to_contain_text("Komoot-Paket", timeout=TL)
    expect(pg.locator(".uidlg.uimod")).to_contain_text("keine Fotos")
    assert not errs, errs
    b.close()


def test_verwaltung_rueckpruefung(pw, app):
    b, pg, errs = _page(pw, app, w=390, dark=True)
    touren = [{"id": "g1", "name": "Gipfeltour", "start_ts": 1782892800, "remote_id": "1", "status": "uploaded", "vis": None, "url": "https://www.komoot.com/tour/1"},
              {"id": "g2", "name": "Seerunde", "start_ts": 1782800000, "remote_id": "2", "status": "uploaded", "vis": None, "url": "https://www.komoot.com/tour/2"},
              {"id": "g3", "name": "Talweg", "start_ts": 1782700000, "remote_id": "3", "status": "linked", "vis": None, "url": "https://www.komoot.com/tour/3"}]
    calls = []
    pg.route("**/api/komoot/hochgeladen", lambda r: _json(r, {"touren": touren, "zaehler": {}}))

    def chk(r):
        ids = json.loads(r.request.post_data)["ids"]
        calls.append(("check", ids))
        res = {"g1": {"vis": "public"}, "g2": {"vis": "private"}, "g3": {"vis": "unbekannt"}}
        _json(r, {"ergebnis": {i: res[i] for i in ids}, "zaehler": {}})
    pg.route("**/api/komoot/sichtbarkeit", chk)
    pg.route("**/api/tours/g1/komoot-privat", lambda r: (calls.append(("privat", "g1")), _json(r, {"vis": "private", "ok": True})))
    pg.goto(app + "/#/admin?tab=weitergabe")
    pg.wait_for_selector("#kvchk", timeout=TL)
    quiet(pg)
    pg.locator("#kvchk").click()
    dlg = pg.locator(".uidlg.uimod")
    expect(dlg.locator(".kvlist li")).to_have_count(3, timeout=TL)
    assert not calls                                                   # Öffnen fragt Komoot nicht
    dlg.locator("#kvgo").click()
    expect(dlg.locator("#kvsum")).to_contain_text("1 öffentlich, 1 privat, 1 unbekannt", timeout=TL)
    assert [c for c in calls if c[0] == "check"] == [("check", ["g1", "g2", "g3"])] and not [c for c in calls if c[0] == "privat"]
    dlg.locator('[data-kp="g1"]').click()
    expect(dlg.locator("#kvsum")).to_contain_text("0 öffentlich, 2 privat, 1 unbekannt", timeout=TL)
    over = pg.evaluate("() => document.documentElement.scrollWidth - window.innerWidth")
    assert over <= 1, over
    assert not errs, errs
    b.close()
