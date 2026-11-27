"""3.53.0 – Wanderführer übersichtlich (Server): Titelbild je Buch (hochladen, ausliefern mit Version und privatem Cache, entfernen,
nur Bilder, Größenlimit, kein Pfad), Rechte (Besitzer ändert, Betrachter liest, fremde Benutzer und ohne Anmeldung nicht),
Titelbild verschwindet mit dem Buch und ist Teil der Sicherung; Fortschritt mit Länge, Aufstieg, Startpunkt und Bildversion; Antwortgröße bei 5 × 80 Touren."""
import io
import json
import time
import zipfile
import sqlite3
from pathlib import Path

from PIL import Image

from tests.test_core import fresh  # noqa: F401  (autouse: frische Datenbank je Test)
from app import db, routes

ROOT = Path(__file__).resolve().parent.parent


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _png(w=900, h=1300, color=(30, 90, 140)):
    """Fantasie-Titelbild (kein Verlagscover): Fläche mit Streifen."""
    im = Image.new("RGB", (w, h), color)
    for y in range(0, h, 60):
        im.paste((240, 200, 60), (0, y, w, y + 12))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def _book(book="Rother Testgebirge", n=3, lat=47.5, lon=11.0, ele=True):
    for i in range(n):
        pts = [[round(lat + i * 0.02 + j * 0.0005, 5), round(lon + j * 0.0004, 5)] for j in range(60)]
        db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES(?,?,?,?,?)", (book, f"{i + 1} Tour {i + 1}", json.dumps(pts), 3.0 + i, 200 + 10 * i if ele else None))
    return book


def _setup(c):
    assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200


def test_titelbild_hoch_runter_version_und_cache():
    b = _book()
    with _client() as c:
        assert c.get("/api/guides/progress").json()[0]["cover"] is None
        r = c.post("/api/guides/cover", params={"book": b}, files={"file": ("x.png", _png(), "image/png")})
        assert r.status_code == 200, r.text
        v = r.json()["v"]
        assert len(v) == 12 and r.json()["bytes"] < 80_000
        g = c.get("/api/guides/progress").json()[0]
        assert g["cover"] == v and g["key"] == b and g["book"] == b
        assert set(g["tours"][0]) >= {"id", "title", "tour", "ts", "km", "up", "s"} and "pts" not in g["tours"][0]
        assert g["tours"][0]["s"] == [47.5, 11.0] and g["tours"][1]["km"] == 4.0 and g["tours"][2]["up"] == 220
        img = c.get("/api/guides/cover", params={"book": b, "v": v})
        assert img.status_code == 200 and img.headers["content-type"] == "image/jpeg"
        assert img.headers["cache-control"] == "private, max-age=31536000, immutable"          # nie „public“
        im = Image.open(io.BytesIO(img.content))
        assert im.format == "JPEG" and max(im.size) <= 480 and im.size[1] > im.size[0]          # neu kodiert, verkleinert, Hochformat bleibt
        alt = c.get("/api/guides/cover", params={"book": b, "v": "veraltet"})
        assert alt.headers["cache-control"] == "private, no-cache"                              # falsche/alte Version: nachfragen
        assert c.get("/api/guides/cover", params={"book": b}, headers={"If-None-Match": img.headers["etag"]}).status_code == 304
        r2 = c.post("/api/guides/cover", params={"book": b}, files={"file": ("y.png", _png(color=(160, 40, 40)), "image/png")})
        assert r2.json()["v"] != v                                                              # neues Bild = neue Adresse
        assert c.delete("/api/guides/cover", params={"book": b}).json()["ok"]
        assert c.get("/api/guides/cover", params={"book": b}).status_code == 404
        assert c.get("/api/guides/progress").json()[0]["cover"] is None


def test_nur_bilder_groessenlimit_und_unbekanntes_buch():
    b = _book()
    with _client() as c:
        assert c.post("/api/guides/cover", params={"book": b}, files={"file": ("x.jpg", b"<svg onload=alert(1)>", "image/jpeg")}).status_code == 400
        assert c.post("/api/guides/cover", params={"book": b}, files={"file": ("x.html", b"<html>hallo</html>" * 10, "text/html")}).status_code == 400
        big = b"\xff\xd8\xff" + b"0" * (3 * 1024 * 1024 + 10)
        assert c.post("/api/guides/cover", params={"book": b}, files={"file": ("x.jpg", big, "image/jpeg")}).status_code == 413
        assert c.post("/api/guides/cover", params={"book": "Gibt es nicht"}, files={"file": ("x.png", _png(), "image/png")}).status_code == 404
        assert c.post("/api/guides/cover", params={"book": "../../etc/passwd"}, files={"file": ("x.png", _png(), "image/png")}).status_code == 404
        assert c.delete("/api/guides/cover", params={"book": "Gibt es nicht"}).status_code == 404
        assert db.one("SELECT COUNT(*) n FROM guide_cover")["n"] == 0
        # Bild mit Transparenz und GIF gehen; das Ergebnis ist immer JPEG ohne Metadaten
        im = Image.new("RGBA", (300, 400), (0, 0, 0, 0))
        buf = io.BytesIO()
        im.save(buf, "GIF")
        assert c.post("/api/guides/cover", params={"book": b}, files={"file": ("x.gif", buf.getvalue(), "image/gif")}).status_code == 200
    # Dateien legt das Titelbild keine an (nur die Datenbank): kein Pfad, den jemand verbiegen könnte
    from app import config
    assert not list(config.DATA_DIR.rglob("*cover*"))


def test_ohne_buchname():
    _book(book="")
    with _client() as c:
        g = c.get("/api/guides/progress").json()[0]
        assert g["book"] == "(ohne Buch)" and g["key"] == ""
        assert c.post("/api/guides/cover", params={"book": ""}, files={"file": ("x.png", _png(), "image/png")}).status_code == 200
        assert c.get("/api/guides/progress").json()[0]["cover"]


def test_titelbild_geht_mit_dem_buch():
    a = _book("Buch A")
    b = _book("Buch B", lat=46.0)
    with _client() as c:
        for k in (a, b):
            assert c.post("/api/guides/cover", params={"book": k}, files={"file": ("x.png", _png(), "image/png")}).status_code == 200
        assert c.delete("/api/guides/" + "book:" + a).json()["ok"]
        assert [r["book"] for r in db.query("SELECT book FROM guide_cover")] == [b]
        ids = [r["id"] for r in db.query("SELECT id FROM guide_tours WHERE book=?", (b,))]
        for i in ids[:-1]:
            c.delete(f"/api/guides/{i}")
        assert db.one("SELECT COUNT(*) n FROM guide_cover")["n"] == 1                 # Buch hat noch eine Tour
        c.delete(f"/api/guides/{ids[-1]}")
        assert db.one("SELECT COUNT(*) n FROM guide_cover")["n"] == 0                 # letzte Tour weg: Titelbild weg


def test_rechte_besitzer_betrachter_fremd():
    b = _book()
    with _client() as c:
        _setup(c)
        v = c.post("/api/guides/cover", params={"book": b}, files={"file": ("x.png", _png(), "image/png")}).json()["v"]
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        c.post("/api/users", json={"name": "Eva", "email": "eva@example.com", "password": "evas-pass123", "role": "user"})
        o = _client()
        assert o.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert o.get("/api/guides/progress").json()[0]["cover"] == v                   # Betrachter: liest Fortschritt und Titelbild
        assert o.get("/api/guides/cover", params={"book": b, "v": v}).status_code == 200
        assert o.post("/api/guides/cover", params={"book": b}, files={"file": ("x.png", _png(), "image/png")}).status_code == 403
        assert o.delete("/api/guides/cover", params={"book": b}).status_code == 403
        assert o.delete("/api/guides/book:" + b).status_code == 403
        anon = _client()
        assert anon.get("/api/guides/cover", params={"book": b, "v": v}).status_code == 401
        assert anon.get("/api/guides/progress").status_code == 401
        assert anon.post("/api/guides/cover", params={"book": b}, files={"file": ("x.png", _png(), "image/png")}).status_code == 401
        e = _client()
        assert e.post("/api/login", json={"name": "eva", "password": "evas-pass123"}).status_code == 200
        assert e.get("/api/guides/progress").json() == []                               # eigene Daten: keine fremden Bücher
        assert e.get("/api/guides/cover", params={"book": b, "v": v}).status_code == 404
        assert e.post("/api/guides/cover", params={"book": b}, files={"file": ("x.png", _png(), "image/png")}).status_code == 404
        assert c.get("/api/guides/cover", params={"book": b, "v": v}).status_code == 200   # Besitzer: unverändert


def test_titelbild_in_der_sicherung(tmp_path):
    from app import extras
    b = _book()
    with _client() as c:
        v = c.post("/api/guides/cover", params={"book": b}, files={"file": ("x.png", _png(), "image/png")}).json()["v"]
    p = extras.make_backup(tmp_path, keep=0)
    with zipfile.ZipFile(p) as z:
        z.extract("komoot_hub.sqlite", tmp_path / "x")
    con = sqlite3.connect(tmp_path / "x" / "komoot_hub.sqlite")
    row = con.execute("SELECT book, v, length(img) FROM guide_cover").fetchone()
    con.close()
    assert row[0] == b and row[1] == v and row[2] > 1000
    from app import backup_check
    assert backup_check.pruefe_zip(p, tief=True)["ok"]


def test_schema_idempotent():
    from app import db as d
    d.close_all()
    d.init()
    d.init()
    cols = {r["name"] for r in db.query("PRAGMA table_info(guide_cover)")}
    assert cols == {"book", "img", "v", "ts"}


def test_antwortgroesse_5_buecher_80_touren():
    for k in range(5):
        _book(f"Rother Band {k + 1}", n=80, lat=45.0 + k)
    now = int(time.time())
    for i in range(40):                                       # 40 eigene Touren, je eine auf einer Buchtour von Band 1
        tid = f"m{i}"
        db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,status) VALUES(?,?,?,?,?,?,?,?)", (tid, f"Tour {i}", "hike", now - i * 86400, now - i * 86400 + 3600, 3000, 3600, "x"))
        routes.store(tid, [(45.0 + i * 0.02 + j * 0.0005, 11.0 + j * 0.0004 + 0.0002, 500, j) for j in range(60)])
    with _client() as c:
        t0 = time.time()
        r = c.get("/api/guides/progress", headers={"Accept-Encoding": "gzip"})
        dt1 = time.time() - t0
        t0 = time.time()
        c.get("/api/guides/progress")
        dt2 = time.time() - t0
    g = r.json()
    raw = json.dumps(g, separators=(",", ":")).encode()
    import gzip
    print(f"\n[Messung 3.53.0] /api/guides/progress 5 × 80 Touren, 40 eigene: {len(raw)} B, gzip {len(gzip.compress(raw))} B, erster Aufruf {dt1 * 1000:.0f} ms, zweiter {dt2 * 1000:.0f} ms")
    assert len(g) == 5 and sum(b["total"] for b in g) == 400
    assert g[0]["done"] == 40 and g[1]["done"] == 0
    assert len(raw) < 60_000 and len(gzip.compress(raw)) < 15_000
    assert dt2 < 0.5


def test_oberflaeche_service_worker_und_rechte_liste():
    from app import main
    assert main.VIEWER_GET.match("/api/guides/progress") and main.VIEWER_GET.match("/api/guides/cover")
    assert not main.VIEWER_GET.match("/api/guides") and not main.VIEWER_GET.match("/api/guides/book:x")
    sw = (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    assert 'const V = "mt-v160"' in sw and 'p === "/api/guides/cover" && u.searchParams.get("v")' in sw
    js = (ROOT / "app" / "static" / "js" / "10-auswertung.js").read_text(encoding="utf-8")
    assert "const GF_BLOCK = 60" in js and "createImageBitmap" in js and "400 / Math.max" in js
    assert "https://" not in js.split("3.53.0 Wanderführer übersichtlich")[1]                # nichts aus dem Netz (Titelbilder wählt der Benutzer selbst)
    i18n = (ROOT / "app" / "static" / "js" / "00-i18n-neu.js").read_text(encoding="utf-8")
    for k in ("{} von {} gewandert || ", "Titelbild wählen || ", "Offene Touren auf der Karte || ", "Buchreihenfolge || "):
        assert k in i18n
