"""3.26.0 – Jahresrückblick als teilbare Seite (Backend): Auswahl prüfen, nur Gewähltes ausliefern, Fotos gesperrt, Datenschutz, Liste, alte Links unverändert."""
import json
import math
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401

GEHEIM = ("GEHEIMNOTIZ", "GEHEIMWEG", "GEHEIMUHR", "48.0", "11.0")
JAHR = 2025


def _ts(m, d):
    from app.gpxtools import TZ
    return int(datetime(JAHR, m, d, 9, tzinfo=TZ).timestamp())


def _seed():
    from PIL import Image
    from app import config, db, photos, routes
    config.LIB_DIR.mkdir(parents=True, exist_ok=True)
    config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
    for tid, name, sport, m, d, km, h, up in (("a", "Gipfelrunde", "hike", 3, 2, 12000, 4, 600), ("b", "Seetour", "hike", 3, 3, 8000, 2, 100), ("c", "Radltour", "bike", 7, 9, 60000, 3, 800)):
        t0 = _ts(m, d)
        db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,48,11,'t','komoot')", (tid, name, sport, t0, t0 + h * 3600, km, h * 3600, up, up))
        routes.store(tid, [(48 + 0.01 * math.sin(i / 9), 11 + i * 0.0004, 500, (t0 + i * 30) * 1000) for i in range(50)])
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES('v','Vorjahr','hike',?,?,10000,3600,100,100,'t','komoot')", (int(datetime(JAHR - 1, 5, 1, tzinfo=__import__('app.gpxtools', fromlist=['TZ']).TZ).timestamp()),) * 2)
    db.execute("INSERT INTO tour_notes(id,note) VALUES('a','GEHEIMNOTIZ privat')")
    db.execute("INSERT INTO tour_wps(tour_id,ts,lat,lng,note) VALUES('a',?,48.0,11.0,'GEHEIMWEG')", (_ts(3, 2),))
    db.execute("INSERT INTO devices(id,name,kind,model,active) VALUES(1,'GEHEIMUHR','zepp','X',1)")
    for k, tid in enumerate(("a", "c")):
        p = config.LIB_DIR / f"p{k}.jpg"
        Image.new("RGB", (40, 30), "blue").save(p)
        photos._store([(str(p), p.stat().st_mtime, p.stat().st_size, _ts(3 if tid == "a" else 7, 2 if tid == "a" else 9) + 60, None, None)])
    photos.assign_all()


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _mk(c, **kw):
    body = {"year": JAHR, "sport": "", "blocks": ["kennzahlen", "rekorde", "heatmap", "fotos"], "days": 30}
    body.update(kw)
    r = c.post("/api/rueckblick/share", json=body)
    assert r.status_code == 200, r.text
    return r.json()["token"]


def test_validierung(fresh):
    _seed()
    c = _client()
    for bad in ({"blocks": []}, {"blocks": ["karte"]}, {"blocks": "kennzahlen"}, {"year": 1800}, {"year": "x"}, {"year": 2031}, {"sport": "sail"}, {"sport": "a:b"}, {"days": -1}, {"days": 99999}):
        r = c.post("/api/rueckblick/share", json={"year": JAHR, "sport": "", "blocks": ["kennzahlen"], **bad})
        assert r.status_code == 400, (bad, r.status_code)


def test_nur_gewaehlte_bausteine(fresh):
    _seed()
    c = _client()
    tok = _mk(c, blocks=["rekorde"])
    d = c.get(f"/api/public/{tok}").json()
    assert d["kind"] == "rueckblick" and d["year"] == JAHR and d["blocks"] == ["rekorde"]
    assert "rek" in d and not {"kz", "heat", "photos"} & d.keys()
    d = c.get(f"/api/public/{_mk(c, blocks=['heatmap', 'kennzahlen'])}").json()
    assert d["blocks"] == ["kennzahlen", "heatmap"] and "kz" in d and "heat" in d and "rek" not in d and "photos" not in d
    kz = d["kz"]
    assert kz["count"] == 3 and kz["km"] == 80.0 and kz["up_m"] == 1500 and kz["days"] == 3 and kz["prev_km"] == 10.0 and len(kz["months"]) == 12
    assert [s["sport"] for s in kz["sports"]] == ["bike", "hike"]
    assert d["heat"]["n"] == 365 and {x[1] for x in d["heat"]["days"]} == {12.0, 8.0, 60.0}


def test_aktivitaetsfilter_rekorde(fresh):
    _seed()
    c = _client()
    d = c.get(f"/api/public/{_mk(c, sport='hike')}").json()
    assert d["sport"] == "hike" and d["kz"]["count"] == 2 and "sports" not in d["kz"] and d["kz"]["km"] == 20.0
    rek = {r["k"]: r for r in d["rek"]}
    assert rek["weit"]["name"] == "Gipfelrunde" and rek["weit"]["v"] == 12.0 and rek["serie"]["v"] == 2 and rek["monat"]["month"] == 3
    assert c.get(f"/api/public/{_mk(c, sport='bike', blocks=['rekorde'])}").json()["rek"][0]["name"] == "Radltour"


def test_fotos_nur_wenn_gewaehlt_und_nur_bestenliste(fresh):
    _seed()
    c = _client()
    ohne = _mk(c, blocks=["kennzahlen"])
    mit = _mk(c, blocks=["fotos"])
    ids = c.get(f"/api/public/{mit}").json()["photos"]
    assert len(ids) == 2
    assert c.get(f"/pub/{mit}/photo/{ids[0]}?size=200").status_code == 200
    assert c.get(f"/pub/{ohne}/photo/{ids[0]}").status_code == 404                    # Baustein nicht gewählt: Foto gesperrt
    nur_wandern = _mk(c, sport="hike", blocks=["fotos"])
    ph = c.get(f"/api/public/{nur_wandern}").json()["photos"]
    fremd = [i for i in ids if i not in ph]
    assert len(ph) == 1 and fremd and c.get(f"/pub/{nur_wandern}/photo/{fremd[0]}").status_code == 404   # Foto einer anderen Aktivität: gesperrt
    assert c.get(f"/pub/{mit}/photo/99999").status_code == 404


def test_nichts_privates_und_seite(fresh):
    _seed()
    c = _client()
    tok = _mk(c)
    raw = c.get(f"/api/public/{tok}").text
    assert not any(w in raw for w in GEHEIM), raw[:300]
    for k in ("coords", "lat", "lng", "note", "wps", "hr", "wx", "prof"):
        assert f'"{k}"' not in raw
    page = c.get(f"/s/{tok}")
    assert page.status_code == 200 and "rueckblick.html" not in page.text and "seite-rueckblick.js" in page.text and "no-store" in page.headers["cache-control"]
    assert "script-src 'self'" in page.headers["content-security-policy"]
    assert c.get("/s/gibtsnicht").status_code == 404


def test_liste_patch_widerruf_und_alte_links(fresh):
    _seed()
    c = _client()
    alt = c.post("/api/tours/a/share", json={"photos": 1}).json()["token"]
    alt_vorher = c.get(f"/api/public/{alt}").json()
    tok = _mk(c, blocks=["kennzahlen", "fotos"])
    rows = {r["token"]: r for r in c.get("/api/shares").json()}
    r = rows[tok]
    assert r["kind"] == "rueckblick" and r["year"] == JAHR and r["blocks"] == ["kennzahlen", "fotos"] and r["name"] == f"Jahresrückblick {JAHR}" and not r["tour_id"]
    assert rows[alt].get("kind") is None and rows[alt]["blocks"] == ["karte", "zahlen", "fotos"]
    r = c.patch(f"/api/share/{tok}", json={"blocks": ["heatmap"], "days": 7}).json()
    assert r["blocks"] == ["heatmap"] and r["kind"] == "rueckblick" and r["exp"]
    assert c.patch(f"/api/share/{tok}", json={"blocks": ["karte"]}).status_code == 400            # Tour-Bausteine gelten hier nicht
    assert c.patch(f"/api/share/{alt}", json={"blocks": ["heatmap"]}).status_code == 400          # und umgekehrt
    assert c.get(f"/api/public/{tok}").json()["blocks"] == ["heatmap"]
    assert c.get(f"/pub/{tok}/photo/1").status_code == 404                                        # Fotos nach „Auswahl ändern“ gesperrt
    assert c.get(f"/api/public/{alt}").json() == alt_vorher                                       # bestehender Link unverändert
    c.delete(f"/api/share/{tok}")
    assert c.get(f"/api/public/{tok}").status_code == 404
    assert c.get(f"/s/{tok}").status_code == 404


def test_abgelaufen_und_rechte(fresh):
    from app import db
    _seed()
    c = _client()
    tok = _mk(c, blocks=["kennzahlen"])
    db.execute("UPDATE shares SET exp=? WHERE token=?", (int(time.time()) - 10, tok))
    assert c.get(f"/api/public/{tok}").status_code == 410 and c.get(f"/s/{tok}").status_code == 410
