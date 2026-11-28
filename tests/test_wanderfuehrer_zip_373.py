"""3.73.0 – Wanderführer als ZIP-Datei hochladen: alle GPX darin, ein Bild darin wird das Titelbild (nur wenn das Buch noch keins hat),
Auswahl des Bilds, Schutz vor kaputten und zu großen ZIP-Dateien, doppelte Touren, Buchname aus dem Dateinamen."""
import io
import zipfile

from PIL import Image

from tests.test_core import fresh  # noqa: F401  (autouse: frische Datenbank je Test)
from app import db, wanderfuehrer as wf


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _gpx(name, lat=47.5, n=30):
    pts = "".join(f'<trkpt lat="{lat + j * 0.0005:.5f}" lon="{11.0 + j * 0.0004:.5f}"><ele>{500 + j}</ele></trkpt>' for j in range(n))
    return f'<?xml version="1.0"?><gpx version="1.1"><trk><name>{name}</name><trkseg>{pts}</trkseg></trk></gpx>'


def _png(color=(30, 90, 140)):
    b = io.BytesIO()
    Image.new("RGB", (900, 600), color).save(b, "PNG")
    return b.getvalue()


def _zip(files):
    b = io.BytesIO()
    with zipfile.ZipFile(b, "w") as z:
        for n, d in files.items():
            z.writestr(n, d)
    return b.getvalue()


def _post(c, data, book="", name="Testbuch.zip"):
    return c.post("/api/guides/zip", params={"book": book}, files={"file": (name, data, "application/zip")})


def test_bildwahl():
    assert wf._zip_bild_wahl(["a.gpx"]) is None
    assert wf._zip_bild_wahl(["x/foto.png", "Titelbild.jpg"]) == "Titelbild.jpg"
    assert wf._zip_bild_wahl(["sub/b.jpg", "a.jpeg"]) == "a.jpeg"
    assert wf._zip_bild_wahl(["__MACOSX/._Titelbild.jpg", ".h.png", "x/y/cover.WEBP"]) == "x/y/cover.WEBP"
    assert wf._zip_bild_wahl(["karte.pdf", "text.txt"]) is None


def test_zip_import_mit_titelbild(fresh):
    c = _client()
    z = _zip({"01 - Eins.gpx": _gpx("01 – Eins"), "ordner/02 - Zwei.gpx": _gpx("02 – Zwei", 47.6), "__MACOSX/._01.gpx": "x", "Titelbild.png": _png()})
    r = _post(c, z, book="Region A")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["added"] == 2 and j["failed"] == [] and j["cover"] is True and j["book"] == "Region A"
    assert {t["title"] for t in db.query("SELECT title FROM guide_tours WHERE book='Region A'")} == {"01 – Eins", "02 – Zwei"}
    g = c.get("/api/guides/cover", params={"book": "Region A"})
    assert g.status_code == 200 and g.headers["content-type"] == "image/jpeg"
    im = Image.open(io.BytesIO(g.content))
    assert max(im.size) <= wf.COVER_SIDE


def test_vorhandenes_titelbild_bleibt_und_doppelte_touren(fresh):
    c = _client()
    z = _zip({"a.gpx": _gpx("Alpha"), "Titelbild.png": _png((200, 0, 0))})
    assert _post(c, z, book="B").json()["cover"] is True
    v1 = db.one("SELECT v FROM guide_cover WHERE book='B'")["v"]
    z2 = _zip({"a.gpx": _gpx("Alpha"), "b.gpx": _gpx("Beta", 47.7), "Titelbild.png": _png((0, 200, 0))})
    j = _post(c, z2, book="B").json()
    assert j["added"] == 1 and j["existing"] == 1 and j["cover"] == "vorhanden"
    assert db.one("SELECT v FROM guide_cover WHERE book='B'")["v"] == v1


def test_buchname_aus_dateiname_und_ohne_bild(fresh):
    c = _client()
    j = _post(c, _zip({"a.gpx": _gpx("Alpha")}), name="Mein Buch.zip").json()
    assert j["book"] == "Mein Buch" and j["cover"] is None and j["added"] == 1
    assert db.one("SELECT 1 FROM guide_cover WHERE book='Mein Buch'") is None


def test_kaputte_und_unlesbare_dateien(fresh):
    c = _client()
    assert _post(c, b"das ist keine zip").status_code == 400
    j = _post(c, _zip({"a.gpx": _gpx("Alpha"), "kaputt.gpx": "<gpx>", "Titelbild.jpg": b"kein bild"}), book="K").json()
    assert j["added"] == 1 and len(j["failed"]) == 1 and j["cover"] is False
    assert db.one("SELECT 1 FROM guide_cover WHERE book='K'") is None


def test_zip_ohne_gpx_legt_kein_titelbild_an(fresh):
    c = _client()
    j = _post(c, _zip({"Titelbild.png": _png()}), book="Leer").json()
    assert j["added"] == 0 and j["cover"] is None
    assert db.one("SELECT 1 FROM guide_cover WHERE book='Leer'") is None


def test_zu_viele_eintraege(fresh, monkeypatch):
    c = _client()
    monkeypatch.setattr(wf, "ZIP_MAX_ENTRIES", 2)
    r = _post(c, _zip({"a.gpx": _gpx("A"), "b.gpx": _gpx("B"), "c.gpx": _gpx("C")}), book="Z")
    assert r.status_code == 413
