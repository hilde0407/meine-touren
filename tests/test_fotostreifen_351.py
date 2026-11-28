"""3.51.0 – Foto-Streifen der Tourseite (Server): Fotoliste mit Version („v“) und Streifen-Auswahl („s“), Bilder mit passender Version dürfen im Browser
bleiben (private, immutable), ohne/mit veralteter Version wie bisher (no-cache); Freigabe- und Betrachterwege bleiben privat; Streifenbilder werden vorab erzeugt."""
import os
import time
from pathlib import Path

from tests.test_core import fresh  # noqa: F401  (autouse: frische Datenbank je Test)
from app import config, ctx, db, photos

ROOT = Path(__file__).resolve().parent.parent
BASE = 1700000000


def _tour(tid="t1", n=30, base=BASE, rated=()):
    from PIL import Image
    lib = config.LIB_DIR / tid
    lib.mkdir(parents=True, exist_ok=True)
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES(?,?,'hike',?,?,8000,7200,300,300,50.1,8.0,'x')",
               (tid, "Tour " + tid, base, base + 7200))
    batch = []
    for i in range(n):
        p = lib / f"f{i:03d}.jpg"
        Image.new("RGB", (120, 80), (i * 7 % 255, 80, 160)).save(p)
        batch.append((str(p), p.stat().st_mtime, p.stat().st_size, base + 60 + i * 200, None, None))
    photos._store(batch)
    photos.assign_all()
    ids = [r["id"] for r in db.query("SELECT id FROM photos WHERE tour_id=? ORDER BY taken_ts", (tid,))]
    for k, i in enumerate(ids):                     # Bewertung/Schärfe bekannt: gleichmäßig, einzelne mit Sternen
        db.execute("UPDATE photos SET rating=?, sharp=? WHERE id=?", (5 if k in rated else 0, 10.0, i))
    return ids


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def test_fotoliste_mit_version_und_streifen():
    ids = _tour(n=30, rated=(3, 17, 29))
    with _client() as c:
        ph = c.get("/api/photos?tour_id=t1&limit=400&strip=12").json()
        assert [p["id"] for p in ph] == ids                                   # volle Liste in Aufnahmereihenfolge, ein Aufruf
        assert all(len(p["v"]) == 12 for p in ph) and len({p["v"] for p in ph}) == 30
        assert not any(k in p for p in ph for k in ("path", "mtime", "size"))   # kein Dateipfad nach außen
        s = [p["id"] for p in ph if p.get("s")]
        assert len(s) == 12 and {ids[3], ids[17], ids[29]} <= set(s)           # Sterne zuerst
        k = [ids.index(i) for i in s]
        assert max(b - a for a, b in zip(k, k[1:])) <= 8                        # über die Tour verteilt
        assert not any(p.get("s") for p in c.get("/api/photos?tour_id=t1&limit=400").json())     # ohne strip: keine Markierung
        assert len([p for p in c.get("/api/photos?tour_id=t1&strip=50").json() if p.get("s")]) == 24   # höchstens 24


def test_streifen_wenige_fotos_und_ohne_bewertung_schnell():
    ids = _tour(n=5)
    with _client() as c:
        assert [p["id"] for p in c.get("/api/photos?tour_id=t1&strip=12").json() if p.get("s")] == ids
    ids2 = _tour("t2", n=40, base=BASE + 86400)
    db.execute("UPDATE photos SET rating=NULL, sharp=NULL WHERE tour_id='t2'")
    t0 = time.time()
    s = photos.strip_ids("t2", 12, bg=False)
    assert time.time() - t0 < 1.0 and len(s) == 12                              # ohne Schärfe-Berechnung im Aufruf
    assert db.one("SELECT COUNT(*) n FROM photos WHERE tour_id='t2' AND sharp IS NULL")["n"] == 40
    k = sorted(ids2.index(i) for i in s)
    assert k[0] <= 3 and k[-1] >= 36                                            # gleichmäßig über die Tour


def test_bild_mit_version_darf_bleiben():
    ids = _tour(n=3)
    with _client() as c:
        v = {p["id"]: p["v"] for p in c.get("/api/photos?tour_id=t1").json()}
        i = ids[0]
        r = c.get(f"/pic/{i}?size=300&v={v[i]}")
        assert r.status_code == 200 and r.headers["cache-control"] == "private, max-age=31536000, immutable" and r.headers["etag"]
        assert c.get(f"/pic/{i}?size=300&v={v[i]}", headers={"If-None-Match": r.headers["etag"]}).status_code == 304
        assert c.get(f"/photo/{i}?size=300&v={v[i]}").headers["cache-control"].startswith("private, max-age")
        assert c.get(f"/pic/{i}?size=300").headers["cache-control"] == "private, no-cache"           # ohne Version wie bisher
        assert c.get(f"/pic/{i}?size=300&v=000000000000").headers["cache-control"] == "private, no-cache"   # veraltet/fremd: nachfragen
        assert c.get(f"/pic/{i}?size=300&v={v[ids[1]]}").headers["cache-control"] == "private, no-cache"   # Version eines anderen Fotos
        assert "public" not in r.headers["cache-control"]


def test_version_aendert_sich_mit_datei_pfad_und_benutzer():
    ids = _tour(n=2)
    r = db.one("SELECT path,mtime,size FROM photos WHERE id=?", (ids[0],))
    v0 = photos.ver_of(ids[0])
    assert v0 == photos.ver(r["path"], r["mtime"], r["size"])
    p = Path(r["path"])
    from PIL import Image
    Image.new("RGB", (120, 80), "white").save(p)                               # ersetzt / gedreht / neu exportiert
    os.utime(p, (r["mtime"] + 50, r["mtime"] + 50))
    photos._store([(str(p), p.stat().st_mtime, p.stat().st_size, BASE + 60, None, None)])
    v1 = photos.ver_of(ids[0])
    assert v1 != v0
    assert photos.ver(r["path"], p.stat().st_mtime, p.stat().st_size + 1) != v1        # nur die Größe anders
    assert photos.ver(r["path"] + "x", p.stat().st_mtime, p.stat().st_size) != v1      # andere Datei (Neuzuordnung der Kennung, Umzug)
    with ctx.as_user("anna"):
        assert photos.ver(r["path"], p.stat().st_mtime, p.stat().st_size) != v1         # anderer Benutzer: andere Adresse
    with _client() as c:                                                                # Thumbnail ist neu, die alte Adresse gilt als veraltet
        assert c.get(f"/pic/{ids[0]}?size=300&v={v0}").headers["cache-control"] == "private, no-cache"
        assert c.get(f"/pic/{ids[0]}?size=300&v={v1}").headers["cache-control"].endswith("immutable")


def test_betrachter_und_freigabe_bleiben_privat():
    ids = _tour(n=3)
    with _client() as c:
        assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200
        v = {p["id"]: p["v"] for p in c.get("/api/photos?tour_id=t1").json()}
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        c.post("/api/users", json={"name": "Eva", "email": "eva@example.com", "password": "evas-pass123", "role": "user"})
        o = _client()
        assert o.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert {p["id"]: p["v"] for p in o.get("/api/photos?tour_id=t1").json()} == v      # Betrachter: dieselben Adressen wie der Besitzer
        r = o.get(f"/pic/{ids[0]}?size=300&v={v[ids[0]]}")
        assert r.status_code == 200 and r.headers["cache-control"].startswith("private, ") and "public" not in r.headers["cache-control"]
        anon = _client()
        assert anon.get(f"/pic/{ids[0]}?size=300&v={v[ids[0]]}").status_code == 401           # ohne Anmeldung nichts
        e = _client()
        assert e.post("/api/login", json={"name": "eva", "password": "evas-pass123"}).status_code == 200
        assert e.get(f"/pic/{ids[0]}?size=300&v={v[ids[0]]}").status_code == 404              # eigene Daten: das Foto gibt es dort nicht
        assert e.get(f"/sphoto/max/{ids[0]}?size=300&v={v[ids[0]]}").status_code == 404       # ohne Freigabe kein Zugriff
        r = c.post("/api/logout")
        assert r.headers.get("clear-site-data") == '"cache"'


def test_freigabe_bild_ohne_dauer_cache():
    """/spic und /sphoto bleiben bei „nachfragen“ (eine Freigabe kann zurückgenommen werden)."""
    src = (ROOT / "app" / "users_api.py").read_text(encoding="utf-8")
    i = src.index("def api_shared_photo(")
    assert "return photos.respond(request, p)" in src[i:i + 900]


def _thumb_exists(i, size):
    import hashlib
    r = db.one("SELECT path,mtime FROM photos WHERE id=?", (i,))
    key = hashlib.sha1(f"{r['path']}|{r['mtime']}|{size}".encode()).hexdigest()
    return (config.CACHE_DIR / "thumb" / key[:2] / f"{key}.jpg").exists()


def test_streifen_vorab_erzeugen():
    _tour(n=20)
    s = photos.strip_ids("t1")
    assert not any(_thumb_exists(i, photos.STRIP_SIZE) for i in s)
    photos.warm_strip("t1")
    assert all(_thumb_exists(i, photos.STRIP_SIZE) for i in s)
    assert not list((config.CACHE_DIR / "thumb").rglob("*.tmp"))
    n = photos.warm_thumbs(sizes=(photos.STRIP_SIZE,))                          # Vorab-Lauf: Streifen zuerst, dann alle übrigen
    assert n == 20 and photos.STRIP_SIZE in photos.warm_thumbs.__defaults__[0]


def test_zuordnung_wärmt_betroffene_touren(monkeypatch):
    seen = []
    monkeypatch.setattr(photos, "warm_strip_bg", lambda tids, metrics=False: seen.append(({t for t in tids if t}, metrics)))
    ids = _tour(n=4)
    assert seen and "t1" in seen[-1][0] and seen[-1][1] is True                # neue Fotos der Tour t1
    _tour("t2", n=2, base=BASE + 86400)
    photos.assign_manual([ids[0]], "t2")
    assert {"t1", "t2"} <= seen[-1][0]                                          # Foto wandert: beide Streifen ändern sich
    photos.unassign_manual([ids[1]])
    assert "t1" in seen[-1][0]


def test_hintergrund_thread(monkeypatch):
    monkeypatch.setenv("MT_NO_WARM", "0")
    ids = _tour(n=15)
    db.execute("UPDATE photos SET rating=NULL, sharp=NULL WHERE tour_id='t1'")
    photos.warm_strip_bg(["t1"], metrics=True)
    for _ in range(300):
        if not photos._STRIP_RUN:
            break
        time.sleep(0.05)
    assert not photos._STRIP_RUN
    assert db.one("SELECT COUNT(*) n FROM photos WHERE tour_id='t1' AND sharp IS NULL")["n"] == 0     # Bewertung/Schärfe nachgerechnet
    monkeypatch.setenv("MT_NO_WARM", "1")
    photos.warm_strip_bg(["t1"])
    assert not photos._STRIP_RUN and len(ids) == 15


def test_service_worker_und_seite():
    sw = (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    assert 'const V = "mt-v162"' in sw and 'PICS = "mt-pics-v2"' in sw
    assert 'p.startsWith("/pic/") && u.searchParams.get("v")' in sw and "immutable" in sw     # nur bestätigt unveränderliche Bilder zuerst aus dem Speicher
    js = (ROOT / "app" / "static" / "js" / "03-tour.js").read_text(encoding="utf-8")
    assert "strip=${PH_STRIP_N}" in js and "IntersectionObserver" in js and 'width="104" height="104"' in js
