"""3.29.0 – Diashow-Link für ein Jahr oder alle Jahre (Backend): Eingaben prüfen, 24 Stunden Standard, nur Fotos ausliefern (keine Orte, Notizen, Strecken, Tournamen),
Fotos nur aus der ausgelieferten Liste, keine Kommentare, Liste mit „Zeigt“-Angaben, Betrachter dürfen nichts anlegen, bestehende Links unverändert."""
import math
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401
from tests.test_browser import app_url  # noqa: F401
from tests.test_rueckblick import GEHEIM, JAHR, _client, _seed, _ts

SECRET_NAMES = ("Gipfelrunde", "Seetour", "Radltour", "GEHEIMNOTIZ", "GEHEIMWEG", "GEHEIMUHR")


def _mk(c, **kw):
    body = {"year": JAHR, "days": 1, **kw}
    r = c.post("/api/diashow/share", json=body)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_validierung(fresh):
    _seed()
    c = _client()
    for bad in ({"year": 1800}, {"year": "x"}, {"year": 2031}, {"year": 2019}, {"sport": "a:b"}, {"sport": "x" * 50}, {"sport": "sail"}, {"best": -1}, {"best": 301}, {"best": "viele"}, {"days": -1}, {"days": 99999}, {"days": "x"}):
        r = c.post("/api/diashow/share", json={"year": JAHR, **bad})
        assert r.status_code == 400, (bad, r.status_code)
    assert c.post("/api/diashow/share", json=[1]).status_code == 400
    assert c.post("/api/diashow/share", content=b"kein json").status_code == 400


def test_standard_24_stunden_und_nur_fotos(fresh):
    from app import db
    _seed()
    c = _client()
    r = c.post("/api/diashow/share", json={"year": JAHR})
    assert r.status_code == 200
    tok = r.json()["token"]
    assert r.json()["title"] == f"Diashow {JAHR}" and r.json()["url"] == f"/s/{tok}"
    row = db.one("SELECT * FROM shares WHERE token=?", (tok,))
    assert row["photos"] == 2 and row["tour_id"] == f"ds:{JAHR}" and row["comments"] == 0 and row["blocks"] is None
    assert abs(row["exp"] - row["ts"] - 86400) <= 2                                   # 24 Stunden Standard
    d = c.get(f"/api/public/{tok}").json()
    assert d["kind"] == "diashow" and d["name"] == f"Diashow {JAHR}" and len(d["photos"]) == 2 and d["coords"] == [] and d["show"] is True
    assert len(d["photo_t"]) == 2 and d["photo_t"][0].startswith("02.03.2025")
    raw = c.get(f"/api/public/{tok}").text
    assert not any(w in raw for w in GEHEIM + SECRET_NAMES), raw
    for k in ("lat", "lng", "km", "up_m", "note", "wps", "hr", "sport", "date", "tour"):
        assert f'"{k}"' not in raw, k
    assert db.one("SELECT views FROM shares WHERE token=?", (tok,))["views"] == 2


def test_seite_und_vorschau(fresh):
    _seed()
    c = _client()
    tok = _mk(c)
    page = c.get(f"/s/{tok}")
    assert page.status_code == 200 and f"Diashow {JAHR}" in page.text and "og:image" in page.text and "seite-show.js" in page.text
    assert "script-src 'self'" in page.headers["content-security-policy"] and "no-store" in page.headers["cache-control"]
    assert not any(w in page.text for w in SECRET_NAMES)


def test_fotos_nur_aus_der_liste(fresh):
    from app import db
    _seed()
    c = _client()
    tok = _mk(c)
    ids = c.get(f"/api/public/{tok}").json()["photos"]
    assert c.get(f"/pub/{tok}/photo/{ids[0]}?size=200").status_code == 200
    assert c.get(f"/pub/{tok}/photo/99999").status_code == 404
    nur_wandern = _mk(c, sport="hike")
    ph = c.get(f"/api/public/{nur_wandern}").json()["photos"]
    fremd = [i for i in ids if i not in ph]
    assert len(ph) == 1 and fremd and c.get(f"/pub/{nur_wandern}/photo/{fremd[0]}").status_code == 404      # Foto einer anderen Aktivität
    assert c.get(f"/api/public/{nur_wandern}").json()["name"].endswith("Wandern")
    # Foto ohne Tour, aus anderem Jahr, verborgenes Foto: nie ausgeliefert
    from PIL import Image
    from app import config, photos
    p = config.LIB_DIR / "x.jpg"
    Image.new("RGB", (40, 30), "red").save(p)
    photos._store([(str(p), p.stat().st_mtime, p.stat().st_size, _ts(5, 5), None, None)])
    photos.assign_all()
    neu = [r["id"] for r in db.query("SELECT id FROM photos WHERE path=?", (str(p),))][0]
    db.execute("UPDATE photos SET tour_id=NULL WHERE id=?", (neu,))
    assert c.get(f"/pub/{tok}/photo/{neu}").status_code == 404
    db.execute("UPDATE photos SET manual=2 WHERE id=?", (ids[0],))
    import app.diashow_link as dl
    dl._CACHE.clear()
    assert ids[0] not in c.get(f"/api/public/{tok}").json()["photos"] and c.get(f"/pub/{tok}/photo/{ids[0]}").status_code == 404
    # ein Tourlink erreicht keine Fotos eines anderen Jahres/Links (Rückwärtsverträglichkeit des Tourlinks)
    alt = c.post("/api/tours/a/share", json={"photos": 1}).json()["token"]
    assert c.get(f"/pub/{alt}/photo/{ids[1]}").status_code in (200, 404)


def test_beste_n_und_alle_jahre_und_leer(fresh):
    _seed()
    c = _client()
    d = c.get(f"/api/public/{_mk(c, best=1)}").json()
    assert len(d["photos"]) == 1
    alle = c.post("/api/diashow/share", json={}).json()
    assert alle["title"] == "Diashow alle Jahre"
    assert len(c.get(f"/api/public/{alle['token']}").json()["photos"]) == 2
    assert c.post("/api/diashow/share", json={"year": 2024}).status_code == 400            # Jahr ohne Fotos
    assert c.post("/api/diashow/share", json={"year": JAHR, "sport": "run"}).status_code == 400


def test_keine_kommentare(fresh):
    _seed()
    c = _client()
    tok = _mk(c, comments=True)
    pid = c.get(f"/api/public/{tok}").json()["photos"][0]
    assert c.get(f"/api/public/{tok}/comments").json() == {"enabled": False, "comments": {}}
    assert c.post(f"/api/public/{tok}/comments", json={"photo_id": pid, "text": "hallo"}).status_code == 403
    c.patch(f"/api/share/{tok}", json={"comments": True})                                       # auch nachträglich nicht erlaubbar
    assert c.post(f"/api/public/{tok}/comments", json={"photo_id": pid, "text": "hallo"}).status_code == 403
    assert c.patch(f"/api/share/{tok}", json={"blocks": ["fotos"]}).status_code == 400


def test_liste_laufzeit_widerruf_ablauf_und_alte_links(fresh):
    from app import db
    _seed()
    c = _client()
    alt = c.post("/api/tours/a/share", json={"show": True, "days": 1}).json()["token"]
    alt_vorher = c.get(f"/api/public/{alt}").json()
    tok = _mk(c, sport="hike", best=5)
    rows = {r["token"]: r for r in c.get("/api/shares").json()}
    r = rows[tok]
    assert r["kind"] == "diashow" and r["photos"] == 2 and r["year"] == JAHR and r["sport"] == "hike" and r["sport_name"] == "Wandern" and r["best"] == 5 and not r["tour_id"] and r["comments"] == 0
    assert r["name"] == f"Diashow {JAHR} · Wandern"
    assert rows[alt].get("kind") is None and rows[alt]["tour_id"] == "a"
    assert c.patch(f"/api/share/{tok}", json={"days": 7}).json()["exp"] > time.time() + 6 * 86400
    assert c.get(f"/api/public/{alt}").json() == alt_vorher
    db.execute("UPDATE shares SET exp=? WHERE token=?", (int(time.time()) - 10, tok))
    assert c.get(f"/api/public/{tok}").status_code == 410 and c.get(f"/s/{tok}").status_code == 410
    assert c.get(f"/pub/{tok}/photo/1").status_code == 410
    assert c.post("/api/shares/purge-expired").json()["removed"] == 1
    tok2 = _mk(c)
    c.delete(f"/api/share/{tok2}")
    assert c.get(f"/api/public/{tok2}").status_code == 404 and c.get(f"/s/{tok2}").status_code == 404


def test_betrachter_darf_nichts_anlegen():
    from fastapi.testclient import TestClient
    from app import main, tracks
    from tests.test_teilen import _gpx
    tracks.adopt(_gpx(), "g.gpx", name="Gipfeltour", ident="g1")
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        assert c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"}).status_code == 200
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert v.post("/api/diashow/share", json={"year": 2025}).status_code == 403
        assert TestClient(main.app).post("/api/diashow/share", json={"year": 2025}).status_code == 401


def test_browser_teilen_knopf_jahr_gesamt_und_oeffentliche_seite(app_url):
    """Slideshow-Seite: Teilen-Knopf bei Jahr und ohne Angabe (nicht bei Zufall); Klick legt einen 24-Stunden-Link an, die öffentliche Seite zeigt Titel und Fotoanzahl, keine Orte."""
    import json
    import urllib.request
    from playwright.sync_api import sync_playwright
    photos = json.loads(urllib.request.urlopen(app_url + "/api/photos?limit=1500").read())
    mit_tour = [p for p in photos if p.get("tour_id")]
    if not mit_tour:
        import pytest
        pytest.skip("keine Fotos mit Tour in den Browser-Testdaten")
    year = datetime.fromtimestamp(mit_tour[0]["taken_ts"]).year
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(locale="de-DE", viewport={"width": 390, "height": 800}, permissions=["clipboard-read", "clipboard-write"])
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/pic/**", lambda r: r.abort())
        pg.route("**/pub/**", lambda r: r.abort())
        pg.goto(f"{app_url}/slideshow.html?year={year}")
        pg.wait_for_function("() => document.getElementById('bshr').style.display !== 'none' && document.getElementById('cap').textContent.includes('(1/')", timeout=15000)
        pg.goto(f"{app_url}/slideshow.html?random=1")
        pg.wait_for_function("() => document.getElementById('cap').textContent.includes('(1/')", timeout=15000)
        assert pg.evaluate("() => getComputedStyle(document.getElementById('bshr')).display") == "none"       # Zufalls-Diashow: kein Teilen
        pg.goto(f"{app_url}/slideshow.html")
        pg.wait_for_function("() => document.getElementById('cap').textContent.includes('(1/')", timeout=15000)
        assert pg.evaluate("() => getComputedStyle(document.getElementById('bshr')).display") != "none"
        pg.goto(f"{app_url}/slideshow.html?year={year}")
        pg.wait_for_function("() => document.getElementById('cap').textContent.includes('(1/')", timeout=15000)
        pg.evaluate("() => document.getElementById('bshr').click()")
        pg.wait_for_function("() => document.getElementById('fsh').style.display === 'block'", timeout=15000)
        assert "Link kopiert" in pg.inner_text("#fsh") or "Link konnte nicht" not in pg.inner_text("#fsh"), pg.inner_text("#fsh")
        rows = [r for r in json.loads(urllib.request.urlopen(app_url + "/api/shares").read()) if r.get("kind") == "diashow"]
        assert len(rows) == 1 and rows[0]["year"] == year and abs(rows[0]["exp"] - rows[0]["ts"] - 86400) <= 2 and rows[0]["photos"] == 2
        pub = ctx.new_page()
        pub.route("**/pub/**", lambda r: r.abort())
        pub.goto(f"{app_url}/s/{rows[0]['token']}")
        pub.wait_for_function("() => /Fotos/.test(document.getElementById('sub').textContent)", timeout=15000)
        assert pub.inner_text("#h") == f"Diashow {year}" and pub.evaluate("() => getComputedStyle(document.getElementById('mp')).display") == "none"   # keine Karte
        assert not errs, errs
        b.close()
