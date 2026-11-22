"""3.54.0 – Bilder der Übersicht mit Zwischenspeicher (Server): die Fotolisten, aus denen Übersicht, Statistik und Diashow ihre Bilder holen, tragen die Bildversion „v“
(nie den Dateipfad) – auch „beste Fotos“, die besten Fotos einer Tour, die Titelfotos der Reisen und Schlagwörter. Das große Bild des Kopfbereichs wird vorab erzeugt.
Oberfläche: keine unversionierte Bildadresse mehr in den Bausteinen der Übersicht; Service Worker mt-v139 mit Grenze 2000; Freigaben (/spic, /sphoto) unverändert."""
import re
from pathlib import Path

from tests.test_core import fresh  # noqa: F401  (autouse: frische Datenbank je Test)
from tests.test_fotostreifen_351 import BASE, _client, _tour
from app import db, photos

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "app" / "static" / "js"
NOPATH = ("path", "mtime", "size")


def test_beste_fotos_und_zufall_mit_version_ohne_pfad():
    _tour("t1", n=12, rated=(2, 7))
    with _client() as c:
        for q in ("best=true&limit=6", "random=true&limit=6", "recent=1&limit=8"):
            ph = c.get("/api/photos?" + q).json()
            assert ph and all(p["v"] == photos.ver_of(p["id"]) for p in ph), q
            assert not any(k in p for p in ph for k in NOPATH + ("rating", "sharp")), q
        b = c.get("/api/tours/t1/best-photos?n=4").json()["photos"]
        assert b and all(p["v"] == photos.ver_of(p["id"]) and not any(k in p for k in NOPATH) for p in b)
        r = c.get(f"/pic/{b[0]['id']}?size=300&v={b[0]['v']}")
        assert r.status_code == 200 and "immutable" in r.headers["cache-control"] and r.headers["cache-control"].startswith("private")


def test_reisen_und_schlagwoerter_mit_titelfoto_version():
    for k in range(3):                                         # drei Tage hintereinander: eine Reise
        _tour(f"r{k}", n=3, base=BASE + k * 86400)
    db.execute("INSERT INTO tour_tags(id,tag) VALUES('r0','Alpen'),('r1','Alpen')")
    with _client() as c:
        db.put("trip_min_days", "2")
        tags = c.get("/api/tags").json()
        trips = c.get("/api/trips").json()
    a = next(t for t in tags if t["tag"] == "Alpen")
    assert a["photo"] and a["photo_v"] == photos.ver_of(a["photo"])
    for t in trips:
        assert t["photo_v"] == (photos.ver_of(t["photo"]) if t["photo"] else None)
    assert not any(k in x for x in tags + trips for k in NOPATH)


def test_kopfbild_vorab_neueste_touren(monkeypatch):
    _tour("alt", n=3, base=BASE)
    _tour("neu", n=3, base=BASE + 86400)
    seen = []
    real = photos.thumb
    monkeypatch.setattr(photos, "thumb", lambda i, s: (seen.append((i, s)), real(i, s))[1])
    assert photos.warm_home() == 2
    first = lambda t: db.one("SELECT id FROM photos WHERE tour_id=? ORDER BY taken_ts LIMIT 1", (t,))["id"]
    assert seen == [(first("neu"), 1200), (first("alt"), 1200)]                    # erstes Foto der Tour (wie der Kopfbereich), neueste zuerst
    assert photos.HOME_SIZE == 1200 and photos.HOME_TOURS == 8
    seen.clear()
    photos.warm_thumbs(sizes=(photos.STRIP_SIZE,))
    big = [x for x in seen if x[1] == 1200]
    assert big and seen.index(big[0]) < len(seen) and all(s == 300 for _, s in seen[:seen.index(big[0])])   # nach den Titelfotos, vor dem Rest
    assert photos.warm_home(stop=lambda: True) is None


def test_oberflaeche_ohne_unversionierte_bilder():
    """Übersicht (Kopfbereich, Bausteine, Erinnerungen), Statistik, Rückblick, Diashow: jede /pic/-Adresse kommt aus picSrc (mit Version) oder trägt &v=."""
    files = ["41-startseite.js", "50-bausteine.js", "52-bausteine-uebersicht.js", "60-bausteine-erinnerungen.js", "02-uebersicht.js", "06-erweiterungen.js",
             "08-analyse.js", "10-auswertung.js", "17-tourblatt.js", "21-bestefotos.js", "28-reisen.js", "07-flug.js", "20-offline.js", "seite-slideshow.js"]
    bad = []
    for f in files:
        for n, line in enumerate((JS / f).read_text(encoding="utf-8").splitlines(), 1):
            for m in re.finditer(r"/pic/\$\{[^}]*\}\?size=[^`\"']*", line):
                if "&v=" not in m.group(0) and "p.v ?" not in line and "?size=2000${p.v" not in line and 'class="br3" style="width:220px' not in line:   # Karten-Popup (siehe unten)
                    bad.append(f"{f}:{n}: {m.group(0)}")
    assert not bad, bad
    # bewusst ohne Version: Karten-Popup aller Fotos mit Ort (bis 60.000 Fotos, ohne Version), Stichprobe der nicht zugeordneten Fotos (zufällig), Freigaben
    assert '<img src="/pic/${p.id}?size=300" class="br3"' in (JS / "06-erweiterungen.js").read_text(encoding="utf-8")
    assert "/pic/${i}?size=200" in (JS / "23-aufraeumen.js").read_text(encoding="utf-8")
    er = (JS / "60-bausteine-erinnerungen.js").read_text(encoding="utf-8")
    assert "const ER_PX = {s: 400, m: 400, l: 500}" in er and 'sessionStorage.setItem(ER_HOLD' in er and "fresh: true" in er
    assert 'loading="lazy" decoding="async"' in er
    st = (JS / "41-startseite.js").read_text(encoding="utf-8")
    assert "picSrc(ph[0], HL_PX)" in st and "const HL_PX = 1200" in st and 'width="84" height="60"' in st
    ub = (JS / "52-bausteine-uebersicht.js").read_text(encoding="utf-8")
    assert "homeCovers()" in ub and "/api/photos?tour_id=${slEnc(t.id)}&limit=1" not in ub
    off = (JS / "20-offline.js").read_text(encoding="utf-8")
    assert '"mt_erhold", "mt_wied"' in off                                            # Abmelden vergisst die gemerkte Zufallsauswahl
    for f in ("seite-show.js", "seite-share.js", "seite-rueckblick.js"):
        assert "&v=" not in (JS / f).read_text(encoding="utf-8")                      # Freigaben bleiben unversioniert


def test_service_worker():
    sw = (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    assert 'const V = "mt-v142"' in sw and 'PICS = "mt-pics-v2"' in sw and "const PICMAX = 2000" in sw
    assert "trim(PICS, 1200)" not in sw and sw.count("trim(PICS, PICMAX)") == 2
    assert 'p.startsWith("/pic/") && u.searchParams.get("v")' in sw and "s <= 600" in sw
