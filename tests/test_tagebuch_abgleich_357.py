"""3.57.0 – Abgleich von Notizen, Fotos und Videos mit „Mein Tourentagebuch“ (Server-Seite, app/tagebuch_abgleich.py).
Geprüft: Lesen (Notiz mit Stempel, Foto- und Videoliste ohne Pfade, verkleinertes Foto mit Cache-Kopf, Video nur mit video=1 und mit Range),
Notiz zusammenführen (alle Fälle der Regel, nichts geht verloren, Stempel ändert sich auch über die Oberfläche), Foto hochladen (EXIF-Zeit/-Ort,
Angaben des Tagebuchs gewinnen, PNG, Verkleinerung, Doppelte per SHA-1, Kennung, Bildinhalt und Name+Zeit, gelöschte Fotos), Video nur mit
bestaetigt=1 und Obergrenzen, Rechte (Betrachter liest, schreibt nie; ohne Anmeldung 401; ein anderer Benutzer sieht nur eigene Daten)."""
import io

import pytest
from PIL import Image

from tests.test_core import fresh  # noqa: F401  (autouse: frische Datenbank je Test)
from tests.test_teilen import _gpx
from app import db, tagebuch_abgleich as tb


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _setup(c):
    assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200


def _one(c, sql, args=()):
    """Abfrage in der Datenbank des angemeldeten Benutzers (jeder Benutzer hat seine eigene)."""
    from app import ctx
    with ctx.as_user(c.get("/api/me").json()["user"]["uid"]):
        return db.one(sql, args)


def _videodir(c):
    from app import config, ctx
    with ctx.as_user(c.get("/api/me").json()["user"]["uid"]):
        return config.LIB_DIR.parent / "videos"


def _tour(c):
    r = c.post("/api/record/upload", json={"gpx": _gpx(), "name": "Gipfeltour", "sport": "hike"})
    assert r.status_code == 200, r.text
    return r.json()["id"]


def _jpeg(w=3000, h=2000, color=(30, 90, 140), exif_time=None, gps=None, fmt="JPEG", quer=False):
    im = Image.new("RGB", (w, h), color)
    for y in range(0, h, 97):
        im.paste((240, 200, 60), (0, y, w // 2, y + 20))
    if quer:                                                  # anderes Bild (anderer Bildinhalt-Abdruck)
        im = Image.radial_gradient("L").resize((w, h)).convert("RGB")
    ex = Image.Exif()
    if exif_time:
        ex.get_ifd(0x8769)[0x9003] = exif_time
        ex.get_ifd(0x8769)[0x9011] = "+02:00"
    if gps:
        g = ex.get_ifd(0x8825)
        g[1], g[2], g[3], g[4] = "N", (47.0, 30.0, 0.0), "E", (11.0, 15.0, 0.0)
    b = io.BytesIO()
    im.save(b, fmt, **({"exif": ex.tobytes()} if fmt == "JPEG" else {}))
    return b.getvalue()


MP4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom" + b"\x00" * 5000


# ---------------------------------------------------------------- Notiz ----------------------------------------------------------------
def test_notiz_regel():
    m = tb.notiz_merge
    assert m("", None, "", None) == ("leer", None)
    assert m("Alt", 5, "  ", 5) == ("leer", None)                       # leer löscht nie
    assert m("Alt", 5, "Alt\r\n", None) == ("gleich", None)
    assert m("", None, "Neu", None) == ("uebernommen", "Neu")
    assert m("Alt", 5, "Neu", 5) == ("uebernommen", "Neu")              # Server seit dem Stand unverändert
    assert m("Alt", 6, "Alt und mehr", 5) == ("uebernommen", "Alt und mehr")    # enthält den Servertext ganz
    assert m("Alt und Neu", 6, "Neu", 5) == ("schon_enthalten", None)
    st, txt = m("Server", 6, "Handy", 5, when=1782900000)
    assert st == "zusammengefuehrt" and txt.startswith("Server\n\n——— Aus Mein Tourentagebuch, ") and txt.endswith("———\nHandy")
    st, txt = m("Server", None, "Handy", None)                           # alte Notiz ohne Stempel: auch zusammenführen
    assert st == "zusammengefuehrt" and "Server" in txt and "Handy" in txt


def test_notiz_endpunkt_und_stempel():
    with _client() as c:
        _setup(c)
        tid = _tour(c)
        d = c.get(f"/api/tours/{tid}/tagebuch").json()
        assert d["notiz"] == {"text": "", "geaendert": None} and d["fotos"] == [] and d["videos"] == [] and d["darf_schreiben"] is True
        assert d["tour"]["id"] == tid and d["grenzen"]["video_mb"] == 200
        r = c.post(f"/api/tours/{tid}/notiz", json={"text": "Vom Handy", "basis": None}).json()
        assert r["status"] == "uebernommen" and not r["konflikt"] and r["notiz"]["text"] == "Vom Handy"
        s1 = r["notiz"]["geaendert"]
        assert isinstance(s1, int) and s1 > 1_700_000_000_000
        # am Server (Oberfläche) geändert → Stempel neu
        assert c.post(f"/api/tours/{tid}/note", json={"note": "Im Browser ergänzt"}).status_code == 200
        n = c.get(f"/api/tours/{tid}/tagebuch").json()["notiz"]
        assert n["text"] == "Im Browser ergänzt" and n["geaendert"] > s1
        # Tagebuch mit altem Stand → beides bleibt
        r = c.post(f"/api/tours/{tid}/notiz", json={"text": "Vom Handy, später", "basis": s1}).json()
        assert r["status"] == "zusammengefuehrt" and r["konflikt"]
        assert r["notiz"]["text"].startswith("Im Browser ergänzt\n\n——— Aus Mein Tourentagebuch") and r["notiz"]["text"].endswith("Vom Handy, später")
        # mit aktuellem Stand → ersetzt
        s2 = r["notiz"]["geaendert"]
        r = c.post(f"/api/tours/{tid}/notiz", json={"text": "Aufgeräumt", "basis": s2}).json()
        assert r["status"] == "uebernommen" and r["notiz"]["text"] == "Aufgeräumt"
        assert c.get("/api/tours").json()[0]["note"] == "Aufgeräumt"            # dieselbe Notiz wie überall
        # gleich, leer, Fehler
        assert c.post(f"/api/tours/{tid}/notiz", json={"text": "Aufgeräumt", "basis": 1}).json()["status"] == "gleich"
        assert c.post(f"/api/tours/{tid}/notiz", json={"text": "", "basis": r["notiz"]["geaendert"]}).json()["notiz"]["text"] == "Aufgeräumt"
        assert c.post(f"/api/tours/{tid}/notiz", json={"text": "x", "basis": "gestern"}).status_code == 400
        assert c.post(f"/api/tours/{tid}/notiz", json={"text": "x" * (tb.NOTIZ_MAX + 1)}).status_code == 413
        assert c.post("/api/tours/gibtsnicht/notiz", json={"text": "x"}).status_code == 404
        # lange Notiz über die Oberfläche wird nicht mehr bei 5000 Zeichen gekürzt
        c.post(f"/api/tours/{tid}/note", json={"note": "y" * 8000})
        assert len(c.get(f"/api/tours/{tid}/tagebuch").json()["notiz"]["text"]) == 8000


# ---------------------------------------------------------------- Fotos ----------------------------------------------------------------
def test_foto_hochladen_lesen_doppelte():
    with _client() as c:
        _setup(c)
        tid = _tour(c)
        start = _one(c, "SELECT start_ts FROM tours WHERE id=?", (tid,))["start_ts"]
        raw = _jpeg(exif_time="2026:07:01 10:00:30", gps=True)        # 08:00:30 UTC = Tourstart + 30 s
        r = c.post(f"/api/tours/{tid}/photo", files={"file": ("IMG_1.jpg", raw, "image/jpeg")}, data={"ref": "abc123def456abc123de"})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["status"] == "neu" and isinstance(j["id"], int) and j["taken_ts"] == start + 30
        assert abs(j["lat"] - 47.5) < 1e-3 and abs(j["lng"] - 11.25) < 1e-3
        pid = j["id"]
        row = _one(c, "SELECT * FROM photos WHERE id=?", (pid,))
        assert row["tour_id"] == tid and row["manual"] == 1 and row["dated"] == 1 and row["fp"]
        with Image.open(row["path"]) as im:                               # verkleinert wie die Foto-Pipeline, EXIF-Zeit erhalten
            assert max(im.size) == 2200
            assert im.getexif().get_ifd(0x8769).get(0x9003) == "2026:07:01 10:00:30"
        # Liste
        d = c.get(f"/api/tours/{tid}/tagebuch").json()
        f = d["fotos"][0]
        assert f["id"] == pid and f["ref"] == "abc123def456abc123de" and f["name"] == "IMG_1.jpg" and f["video"] is False and f["v"] == j["v"]
        assert "path" not in f and all("/" not in str(v) for v in f.values() if isinstance(v, str))
        # Doppelte: gleicher Inhalt, gleiche Kennung, gleiches Bild anders verkleinert, gleicher Name + Zeit
        assert c.post(f"/api/tours/{tid}/photo", files={"file": ("x.jpg", raw, "image/jpeg")}).json() | {"v": 0} == {"status": "vorhanden", "id": pid, "wie": "inhalt", "v": 0, "tour_id": tid}
        assert c.post(f"/api/tours/{tid}/photo", files={"file": ("x.jpg", _jpeg(color=(1, 2, 3)), "image/jpeg")}, data={"ref": "abc123def456abc123de"}).json()["wie"] == "kennung"
        small = _jpeg(1500, 1000, exif_time="2026:07:01 10:00:30")
        assert c.post(f"/api/tours/{tid}/photo", files={"file": ("y.jpg", small, "image/jpeg")}).json()["wie"] == "bild"
        other = _jpeg(color=(200, 10, 10), quer=True)
        assert c.post(f"/api/tours/{tid}/photo", files={"file": ("IMG_1.jpg", other, "image/jpeg")}, data={"taken": str((start + 31) * 1000)}).json()["wie"] == "name_zeit"
        assert len(c.get(f"/api/tours/{tid}/tagebuch").json()["fotos"]) == 1
        # Foto abrufen: verkleinert, mit Cache wie bei Titelbildern
        r = c.get(f"/api/tours/{tid}/tagebuch/photo/{pid}?w=800&v={j['v']}")
        assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and "immutable" in r.headers["cache-control"]
        with Image.open(io.BytesIO(r.content)) as im:
            assert max(im.size) == 800
        r2 = c.get(f"/api/tours/{tid}/tagebuch/photo/{pid}?w=99999", headers={"if-none-match": r.headers["etag"]})
        assert r2.status_code in (200, 304)
        assert "no-cache" in c.get(f"/api/tours/{tid}/tagebuch/photo/{pid}").headers["cache-control"]      # ohne Version: nachfragen
        assert c.get(f"/api/tours/{tid}/tagebuch/photo/999999").status_code == 404
        # Angaben des Tagebuchs gewinnen; PNG ohne EXIF
        png = _jpeg(800, 600, color=(9, 200, 90), fmt="PNG")
        j2 = c.post(f"/api/tours/{tid}/photo", files={"file": ("p.png", png, "image/png")},
                    data={"taken": str((start + 600) * 1000), "offset": "+02:00", "lat": "47.25", "lng": "11.5"}).json()
        assert j2["status"] == "neu" and j2["taken_ts"] == start + 600 and j2["lat"] == 47.25
        row = _one(c, "SELECT * FROM photos WHERE id=?", (j2["id"],))
        assert row["taken_ts"] == start + 600 and abs(row["lat"] - 47.25) < 1e-6
        with Image.open(row["path"]) as im:
            assert im.getexif().get_ifd(0x8769).get(0x9011) == "+02:00"
        # falsche Dateien, Grenzen
        assert c.post(f"/api/tours/{tid}/photo", files={"file": ("x.jpg", b"kein bild", "image/jpeg")}).status_code == 415
        assert c.post(f"/api/tours/{tid}/photo", files={"file": ("x.jpg", b"", "image/jpeg")}).status_code == 400
        assert c.post("/api/tours/nix/photo", files={"file": ("x.jpg", raw, "image/jpeg")}).status_code == 404
        # in Meine Touren gelöscht → nicht still wieder aufnehmen, mit force=1 schon
        assert c.post("/api/photo-delete", json={"ids": [j2["id"]]}).status_code == 200
        assert c.post(f"/api/tours/{tid}/photo", files={"file": ("p.png", png, "image/png")}, data={"taken": str((start + 600) * 1000)}).json()["status"] == "geloescht"
        assert c.post(f"/api/tours/{tid}/photo", files={"file": ("p.png", png, "image/png")}, data={"taken": str((start + 600) * 1000), "force": "1"}).json()["status"] == "neu"
        # Übersicht für die Vorschau
        u = c.get(f"/api/tagebuch/uebersicht?ids={tid},gibtsnicht").json()
        assert list(u) == [tid] and u[tid]["fotos"] == 2 and u[tid]["videos"] == 0 and len(u[tid]["stand"]) == 12
        s0 = u[tid]["stand"]
        c.post(f"/api/tours/{tid}/notiz", json={"text": "neu"})
        assert c.get(f"/api/tagebuch/uebersicht?ids={tid}").json()[tid]["stand"] != s0


def test_foto_zu_gross(monkeypatch):
    monkeypatch.setattr(tb, "FOTO_MAX", 10_000)
    with _client() as c:
        _setup(c)
        tid = _tour(c)
        r = c.post(f"/api/tours/{tid}/photo", files={"file": ("x.jpg", _jpeg(), "image/jpeg")})
        assert r.status_code == 413 and "MB" in r.json()["detail"]


# ---------------------------------------------------------------- Videos ----------------------------------------------------------------
def test_video_nur_bestaetigt_mit_grenzen(monkeypatch):
    with _client() as c:
        _setup(c)
        tid = _tour(c)
        assert c.post(f"/api/tours/{tid}/video", files={"file": ("v.mp4", MP4, "video/mp4")}).status_code == 400          # ohne bestaetigt=1
        r = c.post(f"/api/tours/{tid}/video", files={"file": ("v.mp4", MP4, "video/mp4")}, data={"bestaetigt": "1", "ref": "abcdefabcdefabcdefav", "taken": "1782892800000", "dur_ms": "4200"})
        assert r.status_code == 200, r.text
        vid = r.json()["id"]
        assert r.json()["status"] == "neu"
        assert c.post(f"/api/tours/{tid}/video", files={"file": ("v.mp4", MP4, "video/mp4")}, data={"bestaetigt": "1"}).json() == {"status": "vorhanden", "id": vid, "wie": "inhalt"}
        assert c.post(f"/api/tours/{tid}/video", files={"file": ("w.mp4", MP4 + b"1", "video/mp4")}, data={"bestaetigt": "1", "ref": "abcdefabcdefabcdefav"}).json()["wie"] == "kennung"
        assert c.post(f"/api/tours/{tid}/video", files={"file": ("x.mp4", b"nur text" * 10, "video/mp4")}, data={"bestaetigt": "1"}).status_code == 415
        v = c.get(f"/api/tours/{tid}/tagebuch").json()["videos"]
        assert len(v) == 1 and v[0]["video"] is True and v[0]["size"] == len(MP4) and v[0]["dur_ms"] == 4200 and v[0]["taken_ts"] == 1782892800
        # lesen nur mit video=1, mit Range
        assert c.get(f"/api/tours/{tid}/tagebuch/video/{vid}").status_code == 400
        r = c.get(f"/api/tours/{tid}/tagebuch/video/{vid}?video=1")
        assert r.status_code == 200 and r.content == MP4 and r.headers["content-type"] == "video/mp4"
        r = c.get(f"/api/tours/{tid}/tagebuch/video/{vid}?video=1", headers={"Range": "bytes=0-9"})
        assert r.status_code == 206 and r.content == MP4[:10]
        # Obergrenzen je Video und je Tour
        monkeypatch.setattr(tb, "VIDEO_MAX", 3000)
        r = c.post(f"/api/tours/{tid}/video", files={"file": ("big.mp4", MP4 + b"2", "video/mp4")}, data={"bestaetigt": "1"})
        assert r.status_code == 413 and "höchstens" in r.json()["detail"]
        monkeypatch.setattr(tb, "VIDEO_MAX", 10 ** 6)
        monkeypatch.setattr(tb, "VIDEO_TOUR_MAX", len(MP4) + 100)
        r = c.post(f"/api/tours/{tid}/video", files={"file": ("b.mp4", MP4 + b"3", "video/mp4")}, data={"bestaetigt": "1"})
        assert r.status_code == 413 and "je Tour" in r.json()["detail"]
        assert len(c.get(f"/api/tours/{tid}/tagebuch").json()["videos"]) == 1
        assert _videodir(c).is_dir() and not list(_videodir(c).rglob("*.part"))           # keine Reste abgebrochener Uploads


# ---------------------------------------------------------------- Rechte ----------------------------------------------------------------
def test_rechte_betrachter_fremde_anonym():
    with _client() as c:
        _setup(c)
        tid = _tour(c)
        pid = c.post(f"/api/tours/{tid}/photo", files={"file": ("a.jpg", _jpeg(exif_time="2026:07:01 10:00:10"), "image/jpeg")}).json()["id"]
        vid = c.post(f"/api/tours/{tid}/video", files={"file": ("v.mp4", MP4, "video/mp4")}, data={"bestaetigt": "1"}).json()["id"]
        c.post(f"/api/tours/{tid}/notiz", json={"text": "Notiz von Max"})
        assert c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"}).status_code == 200
        assert c.post("/api/users", json={"name": "Anna", "email": "anna@example.com", "password": "annas-pass1", "role": "user"}).status_code == 200
        # Betrachter: liest wie Tour, Fotos und Notiz ohnehin – schreibt nie
        v = _client()
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        d = v.get(f"/api/tours/{tid}/tagebuch")
        assert d.status_code == 200 and d.json()["notiz"]["text"] == "Notiz von Max" and d.json()["darf_schreiben"] is False and len(d.json()["fotos"]) == 1
        assert v.get(f"/api/tours/{tid}/tagebuch/photo/{pid}?w=300").status_code == 200
        assert v.get(f"/api/tours/{tid}/tagebuch/video/{vid}?video=1").status_code == 200
        assert v.get(f"/api/tagebuch/uebersicht?ids={tid}").status_code == 200
        assert v.post(f"/api/tours/{tid}/notiz", json={"text": "Oma war hier"}).status_code == 403
        assert v.post(f"/api/tours/{tid}/photo", files={"file": ("b.jpg", _jpeg(color=(5, 5, 5)), "image/jpeg")}).status_code == 403
        assert v.post(f"/api/tours/{tid}/video", files={"file": ("v.mp4", MP4 + b"x", "video/mp4")}, data={"bestaetigt": "1"}).status_code == 403
        assert c.get(f"/api/tours/{tid}/tagebuch").json()["notiz"]["text"] == "Notiz von Max"
        # anderer Benutzer: nur eigene Daten (die Tour gibt es in seinem Konto nicht)
        a = _client()
        assert a.post("/api/login", json={"name": "anna", "password": "annas-pass1"}).status_code == 200
        assert a.get(f"/api/tours/{tid}/tagebuch").status_code == 404
        assert a.get(f"/api/tours/{tid}/tagebuch/photo/{pid}").status_code == 404
        assert a.post(f"/api/tours/{tid}/notiz", json={"text": "x"}).status_code == 404
        assert a.get(f"/api/tagebuch/uebersicht?ids={tid}").json() == {}
        # ohne Anmeldung
        n = _client()
        assert n.get(f"/api/tours/{tid}/tagebuch").status_code == 401
        assert n.post(f"/api/tours/{tid}/notiz", json={"text": "x"}).status_code == 401
        assert n.get(f"/api/tours/{tid}/tagebuch/video/{vid}?video=1").status_code == 401


@pytest.mark.parametrize("path,ok", [("/api/tours/g1/tagebuch", True), ("/api/tours/g1/tagebuch/photo/12", True), ("/api/tours/g1/tagebuch/video/3", True),
                                     ("/api/tagebuch/uebersicht", True), ("/api/tours/g1/notiz", False), ("/api/tours/g1/photo", False), ("/api/tours/g1/video", False),
                                     ("/api/tours/g1/tagebuch/photo/x/y", False)])
def test_viewer_get_liste(path, ok):
    from app import main
    assert bool(main.VIEWER_GET.match(path)) is ok
