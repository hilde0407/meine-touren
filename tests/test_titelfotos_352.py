"""3.52.0 – Titelfoto je Tour in den Tourenlisten (Server): ein Aufruf /api/tour-covers für alle Touren mit Foto, Anzahl und Bildversion (kein Pfad),
stabile Wahl (Sterne, sonst Tourmitte ohne abgelehnte/unscharfe/ausgeschlossene Fotos), Bild mit Version darf im Browser bleiben, Betrachter lesen
wie bisher, fremde Benutzer nicht; Titelfotos werden vorab erzeugt (neueste Touren zuerst, vor den Foto-Streifen); fehlende Werte im Hintergrund;
kleine Antwort auch bei 800 Touren."""
import gzip
import json
import time
from pathlib import Path

from tests.test_core import fresh  # noqa: F401  (autouse: frische Datenbank je Test)
from tests.test_fotostreifen_351 import BASE, _client, _tour
from app import db, photos

ROOT = Path(__file__).resolve().parent.parent


def test_ein_aufruf_mit_version_ohne_pfad():
    a = _tour("t1", n=9)
    b = _tour("t2", n=4, base=BASE + 86400)
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,status) VALUES('t3','Ohne Fotos','hike',?,?,1000,600,'x')", (BASE + 2 * 86400, BASE + 2 * 86400 + 600))
    with _client() as c:
        cv = c.get("/api/tour-covers").json()
    assert set(cv) == {"t1", "t2"}                                                   # Touren ohne Fotos fehlen (die Liste zeigt die Strecke)
    assert cv["t1"] == {"id": a[4], "n": 9, "v": photos.ver_of(a[4])}                # Tourmitte, mit Bildversion
    assert cv["t2"]["id"] in (b[1], b[2]) and cv["t2"]["n"] == 4
    assert not any(k in x for x in cv.values() for k in ("path", "mtime", "size"))


def test_wahl_sterne_mitte_abgelehnt_unscharf_ausgeschlossen():
    ids = _tour("t1", n=11)
    assert photos.cover_of("t1") == ids[5]                                           # keine Sterne: Mitte
    db.execute("UPDATE photos SET rating=-1 WHERE id=?", (ids[5],))
    assert photos.cover_of("t1") in (ids[4], ids[6])                                 # abgelehnt: das nächste zur Mitte
    assert photos.cover_of("t1") == ids[4]                                           # Gleichstand: das frühere
    db.execute("UPDATE photos SET sharp=0.5 WHERE id=?", (ids[4],))
    assert photos.cover_of("t1") == ids[6]                                           # bekannt unscharf: nicht
    db.execute("UPDATE photos SET rating=3 WHERE id=?", (ids[9],))
    db.execute("UPDATE photos SET rating=2 WHERE id=?", (ids[1],))
    assert photos.cover_of("t1") == ids[9]                                           # eigene Bewertung zuerst
    db.execute("UPDATE photos SET manual=2, tour_id=NULL WHERE id=?", (ids[9],))       # ausgeschlossen (wie „Aus dieser Tour entfernen“ + ausschließen)
    db.execute("UPDATE photos SET manual=2 WHERE id=?", (ids[1],))                    # auch mit Tour-Kennung nie
    assert photos.cover_of("t1") not in (ids[9], ids[1])
    with _client() as c:
        cv = c.get("/api/tour-covers").json()["t1"]
    assert cv["id"] == photos.cover_of("t1") and cv["n"] == 9


def test_wahl_stabil_und_ohne_werte():
    ids = _tour("t1", n=20)
    db.execute("UPDATE photos SET rating=NULL, sharp=NULL")
    first = [photos.covers()["t1"] for _ in range(3)]
    assert first[0] == first[1] == first[2] and first[0]["id"] in (ids[9], ids[10])  # unbekannte Werte: Mitte, jedes Mal dasselbe
    assert db.one("SELECT COUNT(*) n FROM photos WHERE sharp IS NULL")["n"] == 20      # nichts im Aufruf berechnet (MT_NO_WARM=1 in den Tests)
    rows = db.query("SELECT id,rating,sharp FROM photos WHERE tour_id='t1' ORDER BY taken_ts,id")
    assert photos.cover_pick(rows)["id"] == photos.cover_pick([dict(r) for r in rows])["id"]
    assert photos.cover_pick([]) is None
    only_bad = [{"id": 1, "rating": -1, "sharp": 1.0}, {"id": 2, "rating": -1, "sharp": 1.0}]
    assert photos.cover_pick(only_bad)["id"] == 1                                     # nur abgelehnte: lieber eins zeigen (die Tour hat ja Fotos)


def test_fehlende_werte_im_hintergrund_einmal(monkeypatch):
    _tour("t1", n=6)
    _tour("t2", n=6, base=BASE + 86400)
    db.execute("UPDATE photos SET rating=NULL, sharp=NULL WHERE tour_id='t1'")
    got = []
    monkeypatch.setenv("MT_NO_WARM", "0")
    monkeypatch.setattr(photos, "warm_strip_bg", lambda tids, metrics=False: got.append((list(tids), metrics)))
    monkeypatch.setattr(photos, "_COVER_ASKED", set())
    t0 = time.time()
    photos.covers()
    assert time.time() - t0 < 1.0 and got == [(["t1"], True)]                        # nur die Tour mit fehlenden Werten, nicht abwarten
    photos.covers()
    assert len(got) == 1                                                              # nicht bei jedem Aufruf erneut


def test_bild_mit_version_bleibt_privat_und_betrachter():
    ids = _tour("t1", n=3)
    with _client() as c:
        assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200
        cv = c.get("/api/tour-covers").json()["t1"]
        r = c.get(f"/pic/{cv['id']}?size=300&v={cv['v']}")
        assert r.status_code == 200 and r.headers["cache-control"] == "private, max-age=31536000, immutable"
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        c.post("/api/users", json={"name": "Eva", "email": "eva@example.com", "password": "evas-pass123", "role": "user"})
        o = _client()
        assert o.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert o.get("/api/tour-covers").json()["t1"] == cv                                # Betrachter: dieselben Adressen
        anon = _client()
        assert anon.get("/api/tour-covers").status_code == 401
        e = _client()
        assert e.post("/api/login", json={"name": "eva", "password": "evas-pass123"}).status_code == 200
        assert e.get("/api/tour-covers").json() == {}                                       # eigene Daten: keine fremden Titelfotos
        assert e.get(f"/pic/{ids[1]}?size=300&v={cv['v']}").status_code == 404


def test_vorab_titelfotos_zuerst_neueste_zuerst(monkeypatch):
    _tour("alt", n=5, base=BASE)
    _tour("neu", n=5, base=BASE + 5 * 86400)
    seen = []
    real = photos.thumb
    monkeypatch.setattr(photos, "thumb", lambda i, s: (seen.append((db.one("SELECT tour_id FROM photos WHERE id=?", (i,))["tour_id"], i, s)), real(i, s))[1])
    photos.warm_thumbs(sizes=(photos.STRIP_SIZE,))
    assert seen[:2] == [("neu", photos.cover_of("neu"), 300), ("alt", photos.cover_of("alt"), 300)]   # zuerst die Titelfotos, neueste Tour zuerst
    assert photos.COVER_SIZE == photos.STRIP_SIZE == 300                                   # keine neue Bildgröße
    assert photos.thumb(photos.cover_of("neu"), 300).exists()
    seen.clear()
    photos.warm_strip("neu")
    assert seen[0] == ("neu", photos.cover_of("neu"), 300)                                  # nach Import/Zuordnung: das Titelfoto zuerst


def test_antwort_klein_bei_800_touren():
    rows, tours = [], []
    for k in range(800):
        tid = str(1000000000 + k * 7919)                                                    # Komoot-artige Kennung
        tours.append((tid, f"T{k}", BASE - k * 86400, BASE - k * 86400 + 9000))
        rows += [(f"/mnt/fotos/max/2025/{tid}/IMG_{j:05d}.jpg", 1.7e9 + j, 3000000, BASE - k * 86400 + 60 * j, tid) for j in range(1 + k % 60)]
    db.executemany("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,status) VALUES(?,?,'hike',?,?,10000,9000,'x')", tours)
    db.executemany("INSERT INTO photos(path,mtime,size,taken_ts,tour_id,rating,sharp) VALUES(?,?,?,?,?,0,10)", rows)
    with _client() as c:
        t0 = time.time()
        r = c.get("/api/tour-covers", headers={"Accept-Encoding": "gzip"})
        dt = time.time() - t0
    raw = json.dumps(r.json(), separators=(",", ":")).encode()
    print(f"\n[Messung 3.52.0] /api/tour-covers bei 800 Touren, {len(rows)} Fotos: {len(raw)} B, gzip {len(gzip.compress(raw))} B, {dt * 1000:.0f} ms")
    assert len(r.json()) == 800 and r.headers.get("content-encoding") == "gzip"
    assert len(raw) < 48000 and len(gzip.compress(raw)) < 20000
    assert dt < 3.0


def test_oberflaeche_und_service_worker():
    sw = (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    assert 'const V = "mt-v150"' in sw and "trim(PICS, PICMAX)" in sw and "netFirst(e.request, PICS, PICMAX)" in sw and "const PICMAX = 2000" in sw     # 3.54.0: Grenze 2000 (vorher 1200)
    js = (ROOT / "app" / "static" / "js" / "02-uebersicht.js").read_text(encoding="utf-8")
    assert 'loading="lazy" decoding="async"' in js and "size=${TR_PIC}&v=" in js and "const TR_PIC = 300" in js
    assert "/api/photos?tour_id=${t.id}&limit=1" not in (ROOT / "app" / "static" / "js" / "41-startseite.js").read_text(encoding="utf-8")   # keine Anfrage je Karte mehr
    i18n = (ROOT / "app" / "static" / "js" / "00-i18n-neu.js").read_text(encoding="utf-8")
    assert "Fotos in der Tourenliste || Photos in the tour list || Photos dans la liste des parcours || Fotos en la lista de rutas" in i18n
