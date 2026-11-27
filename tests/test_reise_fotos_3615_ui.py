"""3.61.5 – Reise-Fotos: Foto-Flächen nutzen die ganze Breite der Kachel, die Diashow einer Reise lässt sich teilen.
API (Diashow-Freigabe mit Zeitraum ds:<von>..<bis>): anlegen, abrufen, Fotos nur aus dem Zeitraum, ungültige Zeiträume 400, Freigabenliste, bestehende Links unverändert.
Browser (Chromium): Breite von Raster / Streifen / Show in der vollen Kachel >= 95 % bei 1440 px, Handy 390 px ohne Überlauf, Erinnerungen der Übersicht, Knopf „Diashow teilen“ im Baustein,
Teilen-Knopf der Diashow-Seite bei Zeitraum sichtbar, bei Sportart / Tag / neueste / nur einem Datum weiter verborgen."""
import json
import urllib.request

import pytest

from tests.test_core import fresh  # noqa: F401
from tests.test_rueckblick import JAHR, _client, _seed
from tests.test_seitenlayout_ui import T, _api, pw  # noqa: F401
from tests.test_reise_seiten_ui import TL, _tid, _trip, _trips, app, clean  # noqa: F401

BEREICH = (f"{JAHR}-03-01", f"{JAHR}-03-31")


def _mk(c, **kw):
    r = c.post("/api/diashow/share", json={"from": BEREICH[0], "to": BEREICH[1], "days": 1, **kw})
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------  API  ------------------------------------------------------------------
def test_zeitraum_anlegen_abrufen_und_liste(fresh):
    from app import db, diashow_link
    _seed()
    c = _client()
    j = _mk(c)
    tok = j["token"]
    assert j["title"] == f"Diashow 01.03.{JAHR} – 31.03.{JAHR}" and j["url"] == f"/s/{tok}"
    row = db.one("SELECT * FROM shares WHERE token=?", (tok,))
    assert row["tour_id"] == f"ds:{JAHR}-03-01..{JAHR}-03-31" and row["photos"] == 2 and row["comments"] == 0 and row["names"] == 1
    assert abs(row["exp"] - row["ts"] - 86400) <= 2
    d = c.get(f"/api/public/{tok}").json()
    assert d["kind"] == "diashow" and d["name"] == j["title"] and len(d["photos"]) == 1 and d["coords"] == [] and d["photo_names"] == ["Gipfelrunde"]
    assert d["photo_t"][0].startswith(f"02.03.{JAHR}")
    # nur Fotos aus dem Zeitraum (das Juli-Foto gehört nicht dazu)
    alle = {p["id"] for p in db.query("SELECT id FROM photos")}
    assert len(alle) == 2
    pid = d["photos"][0]
    assert diashow_link.photo_allowed(row, pid) and not any(diashow_link.photo_allowed(row, o) for o in alle - {pid})
    assert c.get(f"/pub/{tok}/photo/{pid}?size=200").status_code == 200
    assert c.get(f"/pub/{tok}/photo/{(alle - {pid}).pop()}?size=200").status_code == 404
    page = c.get(f"/s/{tok}")
    assert page.status_code == 200 and f"Diashow 01.03.{JAHR}" in page.text
    # Liste
    rows = [r for r in c.get("/api/shares").json() if r.get("kind") == "diashow"]
    assert len(rows) == 1 and rows[0]["range_from"] == BEREICH[0] and rows[0]["range_to"] == BEREICH[1] and rows[0]["name"] == j["title"] and rows[0]["year"] == 0 and rows[0]["names"] == 1
    # Kommentare gibt es nicht
    assert c.post(f"/api/public/{tok}/comments", json={"name": "x", "text": "y"}).status_code in (400, 403, 404, 405)


def test_zeitraum_ungueltig(fresh):
    _seed()
    c = _client()
    ok = {"from": BEREICH[0], "to": BEREICH[1]}
    for bad in ({"from": "2025-03-31", "to": "2025-03-01"}, {"from": "2025-3-1", "to": "2025-03-31"}, {"from": "2025-02-30", "to": "2025-03-31"}, {"from": "1969-12-31", "to": "1970-01-02"},
                {"from": "2025-01-01", "to": "2026-01-02"}, {"from": "2025-03-01"}, {"to": "2025-03-31"}, {"from": 5, "to": 6}, {"from": "x", "to": "y"}, {**ok, "year": JAHR}, {**ok, "sport": "hike"},
                {**ok, "best": 301}, {**ok, "days": -1}, {"from": "2025-04-01", "to": "2025-04-30"}, {"from": "2101-01-01", "to": "2101-01-02"}):
        r = c.post("/api/diashow/share", json=bad)
        assert r.status_code == 400, (bad, r.status_code)
    assert c.post("/api/diashow/share", json={"from": "2025-01-01", "to": "2025-12-31", "days": 1}).status_code == 200      # genau 365 Tage
    assert c.post("/api/diashow/share", json={"from": "2024-01-01", "to": "2024-12-31", "days": 1}).status_code == 400      # 366 Tage (Schaltjahr) erlaubt, aber ohne Fotos


def test_bestehende_links_unveraendert(fresh):
    from app import db
    _seed()
    c = _client()
    for body, ref in (({"year": JAHR}, f"ds:{JAHR}"), ({}, "ds:all"), ({"year": JAHR, "sport": "hike"}, f"ds:{JAHR}:hike")):
        r = c.post("/api/diashow/share", json={**body, "days": 1})
        assert r.status_code == 200, r.text
        assert db.one("SELECT tour_id FROM shares WHERE token=?", (r.json()["token"],))["tour_id"] == ref
    rows = [r for r in c.get("/api/shares").json() if r.get("kind") == "diashow"]
    assert len(rows) == 3 and all(r["range_from"] == "" for r in rows)


# ------------------------------------------------------------------  Browser  ------------------------------------------------------------------
def _reise_widgets(app_url, **cfg):
    _api(app_url, "reise", "PUT", {"widgets": [{"id": "wd1", "type": "rdiashow", "cfg": {"mode": "best", "view": "grid", "n": 12, **cfg}}]})


def _breiten(pg, view):
    sel = {"grid": ".erg", "strip": ".ers", "show": ".erp"}[view]
    pg.wait_for_function("(s) => document.querySelector('#tlw-wd1 ' + s) && document.querySelectorAll('#tlw-wd1 .erb img').length >= 1", arg=sel, timeout=TL)
    return pg.evaluate("""(s) => { const f = document.querySelector('#tlw-wd1 ' + s), b = document.querySelector('#tlw-wd1 .erb'), body = b.parentElement;
      const cs = getComputedStyle(body), pad = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
      return {flaeche: f.getBoundingClientRect().width, body: body.clientWidth - pad, erb: b.getBoundingClientRect().width, doc: document.documentElement.scrollWidth, vw: innerWidth}; }""", sel)


@pytest.mark.parametrize("view", ["grid", "strip", "show"])
def test_fotoflaeche_nutzt_die_ganze_breite(pw, app, view):
    _reise_widgets(app, view=view)
    pg = _trip(pw, app, width=1440)
    try:
        m = _breiten(pg, view)
        assert m["body"] > 1000, m
        assert m["flaeche"] >= 0.95 * m["body"], (view, m)
        assert m["erb"] > 860, m                                                   # früher durch .slwb>* auf 860 px begrenzt
        if view == "grid":
            cols = pg.evaluate("() => getComputedStyle(document.querySelector('#tlw-wd1 .erg')).gridTemplateColumns.split(' ').length")
            assert cols >= 7, cols                                                  # bei 1130 px Breite mehr als die früheren 6 Spalten
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_lesbare_textbloecke_bleiben_bei_860(pw, app):
    _reise_widgets(app)
    pg = _trip(pw, app, width=1440)
    try:
        pg.wait_for_selector("#tlw-wd1 .erb img", timeout=TL)
        css = open("app/static/style.css", encoding="utf-8").read()
        assert ".slwb>*:not(.utiles):not(.slfotos):not(.slsign):not(.erb):not(.rsdh){max-width:860px}" in css
        assert pg.evaluate("() => getComputedStyle(document.querySelector('#tlw-wd1 .erb')).maxWidth") == "none"
    finally:
        pg.browser_.close()


@pytest.mark.parametrize("view", ["grid", "strip", "show"])
def test_handy_ohne_ueberlauf(pw, app, view):
    _reise_widgets(app, view=view)
    pg = _trip(pw, app, width=390, height=800)
    try:
        m = _breiten(pg, view)
        assert m["doc"] <= m["vw"], m
        assert m["flaeche"] <= m["body"] + 1 and m["flaeche"] >= 0.9 * m["body"], m
        r = pg.evaluate("() => { const b = document.querySelector('#tlw-wd1 .erdsh').getBoundingClientRect(); return [b.left, b.right, b.height]; }")
        assert r[0] >= 0 and r[1] <= 390 and r[2] >= 44, r
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()


def test_erinnerungen_der_uebersicht_nutzen_die_breite(pw, app):
    from tests.test_seitenlayout_ui import _browser
    pg = _browser(pw, app, width=1440, devs=None)
    try:
        pg.goto(f"{app}/#/dash")
        pg.wait_for_function("() => document.querySelectorAll('#hmemsec .erb img').length >= 1", timeout=TL)
        m = pg.evaluate("() => { const s = document.querySelector('#hmemsec'), f = s.querySelector('.erg, .ers, .erp'); return [f.getBoundingClientRect().width, s.getBoundingClientRect().width]; }")
        assert m[0] >= 0.95 * m[1], m
    finally:
        pg.browser_.close()


def test_knopf_diashow_teilen_im_baustein(pw, app):
    _reise_widgets(app, view="grid")
    pg = _trip(pw, app)
    try:
        pg.wait_for_selector("#tlw-wd1 .erdsh", timeout=TL)
        assert pg.locator("#tlw-wd1 .erdsh").inner_text() == "Diashow teilen"
        pg.evaluate("() => { window.__shared = null; Object.defineProperty(navigator, 'share', {configurable: true, value: async d => { window.__shared = d; }}); }")
        pg.click("#tlw-wd1 .erdsh")
        pg.wait_for_function("() => !!window.__shared", timeout=TL)
        sh = pg.evaluate("() => window.__shared")
        assert sh["url"].startswith(app + "/s/") and sh["title"].startswith("Diashow"), sh
        assert "Tournamen sind im Link sichtbar" in pg.inner_text("#tlw-wd1 .erdsn")
        t = _trips(app)["La Gomera"]
        rows = [r for r in json.loads(urllib.request.urlopen(app + "/api/shares").read()) if r.get("kind") == "diashow"]
        assert len(rows) == 1 and rows[0]["range_from"] == t["start"] and rows[0]["range_to"] == t["end"] and rows[0]["photos"] == 2
        assert abs(rows[0]["exp"] - rows[0]["ts"] - 86400) <= 2
        pub = json.loads(urllib.request.urlopen(f"{app}/api/public/{rows[0]['token']}").read())
        assert len(pub["photos"]) == 6 and pub["kind"] == "diashow" and pub["coords"] == []                  # die sechs Fotos der Reise
        # Freigabenliste: Typ „Diashow“ und Zeitraum
        pg.goto(f"{app}/#/links")
        pg.wait_for_function("() => /Fotos vom \\d\\d\\.\\d\\d\\.\\d{4} bis \\d\\d\\.\\d\\d\\.\\d{4}/.test(document.getElementById('lkb').textContent)", timeout=TL)
        assert "Diashow" in pg.inner_text("#lkb")
        assert not pg.errors, pg.errors
    finally:
        pg.browser_.close()
        for r in json.loads(urllib.request.urlopen(app + "/api/shares").read()):
            urllib.request.urlopen(urllib.request.Request(f"{app}/api/share/{r['token']}", method="DELETE"))


def test_knopf_fehlt_ohne_link_einstellung(pw, app):
    _reise_widgets(app, link=False)
    pg = _trip(pw, app)
    try:
        pg.wait_for_selector("#tlw-wd1 .erb img", timeout=TL)
        assert pg.locator("#tlw-wd1 .erdsh").count() == 0
    finally:
        pg.browser_.close()


def test_diashow_seite_teilen_knopf_je_filter(pw, app):
    t = _trips(app)["La Gomera"]
    b = pw.chromium.launch()
    try:
        for q, sichtbar in ((f"from={t['start']}&to={t['end']}", True), (f"from={t['start']}&to={t['end']}&best=60", True), (f"from={t['start']}&to={t['end']}&sport=hike", False),
                            (f"from={t['start']}&to={t['end']}&recent=1", False), (f"from={t['start']}", False), (f"to={t['end']}", False), ("sport=hike", False), ("recent=1", False)):
            pg = b.new_page()
            pg.route("**/pic/**", lambda r: r.abort())
            pg.goto(f"{app}/slideshow.html?{q}")
            pg.wait_for_function("() => document.getElementById('cap').textContent.includes('(1/') || getComputedStyle(document.getElementById('msg')).display !== 'none'", timeout=TL)
            shown = pg.evaluate("() => getComputedStyle(document.getElementById('bshr')).display") != "none"
            assert shown == sichtbar, (q, shown)
            pg.close()
    finally:
        b.close()
