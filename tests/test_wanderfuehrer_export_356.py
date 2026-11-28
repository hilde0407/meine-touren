"""3.56.0 – Wanderführer für „Mein Tourentagebuch“: GET /api/guides/export liefert Bücher und Buchtouren mit Strecke genau im Dateiformat
des Tagebuchs („tourentagebuch-wanderfuehrer“, Version 1; js/calc-fuehrer-datei.js ab Tagebuch 2.13.0). Geprüft: Format und Packung der Strecke,
Rechte (Besitzer, Betrachter liest, ohne Anmeldung 401, fremder Benutzer nur eigene Daten), „gewandert“ aus dem vorhandenen Abgleich,
Titelbilder nur mit cover=1, höchstens 400 Punkte je Buchtour, keine anderen Daten, und dass die Prüfung des Tagebuchs (FuehrerDatei.lies) die Antwort annimmt –
gespiegelt in Python und, wenn Node und das Tagebuch-Repo daneben liegen, mit dem echten Modul."""
import io
import json
import os
import re
from datetime import datetime
from app.gpxtools import TZ
import shutil
import subprocess
import time
from pathlib import Path

import pytest
from PIL import Image

from tests.test_core import fresh  # noqa: F401  (autouse: frische Datenbank je Test)
from app import db, routes

ROOT = Path(__file__).resolve().parent.parent
TAGEBUCH_JS = Path(os.environ.get("MT_TAGEBUCH_REPO", ROOT.parent / "mein-tourentagebuch")) / "android/app/src/main/assets/www/js"


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _png(w=900, h=1300):
    im = Image.new("RGB", (w, h), (30, 90, 140))
    for y in range(0, h, 60):
        im.paste((240, 200, 60), (0, y, w, y + 12))
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def _line(lat, lon, n=60):
    return [[round(lat + j * 0.0005, 5), round(lon + j * 0.0004, 5)] for j in range(n)]


def _book(book="Rother Testgebirge", n=3, lat=47.5, lon=11.0, npts=60):
    for i in range(n):
        db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES(?,?,?,?,?)",
                   (book, f"{i + 1} Tour {i + 1}", json.dumps(_line(lat + i * 0.02, lon, npts)), 3.0 + i, 200 + 10 * i))
    return book


def _walk(tid, name, lat, lon, ts):
    """Eigene Tour auf der Buchstrecke ab (lat, lon)."""
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,status) VALUES(?,?,?,?,?,?,?,?)", (tid, name, "hike", ts, ts + 3600, 3000, 3600, "x"))
    routes.store(tid, [(lat + j * 0.0005, lon + j * 0.0004 + 0.0002, 500, j) for j in range(60)])
    db.execute("INSERT OR REPLACE INTO tour_notes(id,note) VALUES(?,?)", (tid, "geheime Notiz"))


def _setup(c):
    assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200


def _entpacke(o):
    """Fuehrer.entpacke aus dem Tagebuch (calc-fuehrer.js), gespiegelt."""
    if not isinstance(o, dict) or not isinstance(o.get("la"), list) or not isinstance(o.get("lo"), list) or len(o["la"]) != len(o["lo"]):
        return []
    la, lo, s1, s2, out = o["la"], o["lo"], 0, 0, []
    for a, b in zip(la, lo):
        s1 += a; s2 += b
        out.append((s1 / 1e5, s2 / 1e5))
    return out


def _lies(d):
    """FuehrerDatei.lies aus dem Tagebuch (calc-fuehrer-datei.js), gespiegelt: gibt die angenommenen Bücher und die Zahl der verworfenen zurück."""
    assert d.get("format") == "tourentagebuch-wanderfuehrer"
    assert d.get("version", 0) >= 1 and d["version"] <= 1
    assert isinstance(d.get("buecher"), list)
    defekt, buecher = 0, []
    for b in d["buecher"][:200]:
        if not isinstance(b, dict) or not isinstance(b.get("name"), str) or not b["name"].strip() or not isinstance(b.get("touren"), list):
            defekt += 1; continue
        touren = []
        for t in b["touren"][:500]:
            ok = isinstance(t, dict) and isinstance(t.get("title"), str) and t["title"].strip() and isinstance(t.get("km"), (int, float)) and not isinstance(t.get("km"), bool) and t["km"] >= 0
            punkte = [p for p in _entpacke(t.get("pts")) if abs(p[0]) <= 90 and abs(p[1]) <= 180] if ok else []
            if not ok or len(punkte) < 3:
                defekt += 1; continue
            touren.append({"title": t["title"], "km": t["km"], "up": t.get("up"), "punkte": punkte})
        cov = b.get("cover")
        buecher.append({"id": b["id"] if isinstance(b.get("id"), str) and re.fullmatch(r"[\w-]{1,40}", b["id"], re.A) else None, "name": b["name"],
                        "cover": cov if isinstance(cov, str) and cov.startswith("data:image/jpeg;base64,") and len(cov) <= 200000 else None, "touren": touren})
    return buecher, defekt


def test_format_wie_tagebuch_und_gewandert():
    b = _book()
    now = int(time.time())
    _walk("m1", "Meine Runde am See", 47.52, 11.0, now - 86400 * 3)        # passt auf Buchtour 2
    with _client() as c:
        r = c.get("/api/guides/export")
    assert r.status_code == 200 and r.headers["content-type"].startswith("application/json")
    d = r.json()
    assert d["format"] == "tourentagebuch-wanderfuehrer" and d["version"] == 1 and d["app"].startswith("Meine Touren 3.74.0")
    assert re.match(r"\d{4}-\d\d-\d\dT", d["erstellt"])
    (bk,) = d["buecher"]
    assert bk["name"] == b and bk["key"] == b and re.fullmatch(r"mt-[0-9a-f]{12}", bk["id"]) and bk["cover_v"] is None and "cover" not in bk
    assert [t["id"] for t in bk["touren"]] == ["t0", "t1", "t2"] and [t["ord"] for t in bk["touren"]] == [0, 1, 2]
    t1 = bk["touren"][1]
    assert set(t1) == {"id", "ord", "mt_id", "title", "km", "up", "f", "pts", "gewandert"}
    assert t1["title"] == "2 Tour 2" and t1["km"] == 4.0 and t1["up"] == 210 and t1["f"] == ""
    assert t1["gewandert"] == [{"datum": datetime.fromtimestamp(now - 86400 * 3, tz=TZ).strftime("%Y-%m-%d"), "name": "Meine Runde am See"}]
    assert "gewandert" not in bk["touren"][0] and "gewandert" not in bk["touren"][2]
    # Strecke: gepackt wie Fuehrer.packe (Deltas in 1e-5 Grad, Reihenfolge der GPX-Datei), ohne Höhen; entpackt = gespeicherte Punkte
    assert set(t1["pts"]) == {"la", "lo"} and all(isinstance(v, int) for v in t1["pts"]["la"] + t1["pts"]["lo"])
    assert t1["pts"]["la"][0] == 4752000 and t1["pts"]["la"][1] == 50 and t1["pts"]["lo"][1] == 40
    stored = json.loads(db.one("SELECT pts FROM guide_tours WHERE id=?", (t1["mt_id"],))["pts"])
    assert [(round(a, 5), round(o, 5)) for a, o in _entpacke(t1["pts"])] == [tuple(p) for p in stored]
    # die Prüfung des Tagebuchs nimmt alles an
    buecher, defekt = _lies(d)
    assert defekt == 0 and len(buecher) == 1 and buecher[0]["id"] == bk["id"] and len(buecher[0]["touren"]) == 3
    # keine anderen Daten: keine Notizen, keine Spur der eigenen Tour, keine Foto-/Tour-IDs
    raw = r.text
    assert "geheime Notiz" not in raw and '"m1"' not in raw and "4752020" not in raw
    ids = {bk["id"]}
    with _client() as c:
        ids.add(c.get("/api/guides/export").json()["buecher"][0]["id"])
    assert len(ids) == 1                                                       # Kennung bleibt gleich (wiederholter Import erkennt das Buch)


def test_ohne_buchname_und_defekte_strecke():
    _book(book="", n=2)
    db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES(?,?,?,?,?)", ("", "kaputt", json.dumps([[47.0, 11.0]]), 1.0, None))
    db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES(?,?,?,?,?)", ("", "ohne Länge", json.dumps(_line(46.0, 10.0, 20)), None, None))
    with _client() as c:
        d = c.get("/api/guides/export").json()
    (bk,) = d["buecher"]
    assert bk["name"] == "(ohne Buch)" and bk["key"] == ""
    assert [t["title"] for t in bk["touren"]] == ["1 Tour 1", "2 Tour 2", "ohne Länge"]      # zu kurze Strecke fällt weg (das Tagebuch verwürfe sie)
    assert bk["touren"][2]["km"] > 0 and bk["touren"][2]["up"] is None
    assert _lies(d)[1] == 0


def test_leer():
    with _client() as c:
        d = c.get("/api/guides/export").json()
    assert d["buecher"] == [] and _lies(d) == ([], 0)


def test_rechte_betrachter_anonym_fremd():
    b = _book()
    _walk("m1", "Max wandert", 47.5, 11.0, int(time.time()) - 86400)
    with _client() as c:
        _setup(c)
        mine = c.get("/api/guides/export").json()
        assert mine["buecher"][0]["touren"][0]["gewandert"][0]["name"] == "Max wandert"
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        c.post("/api/users", json={"name": "Eva", "email": "eva@example.com", "password": "evas-pass123", "role": "user"})
        o = _client()
        assert o.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        ov = o.get("/api/guides/export")
        assert ov.status_code == 200
        assert ov.json()["buecher"] == mine["buecher"]                     # Betrachter: dieselben Bücher seines Besitzers
        assert o.get(f"/api/plan/guide/{mine['buecher'][0]['touren'][0]['mt_id']}").status_code == 403   # Einzelstrecke bleibt gesperrt
        assert o.post("/api/guides/export").status_code in (403, 405)
        assert _client().get("/api/guides/export").status_code == 401
        assert _client().get("/api/guides/export", params={"cover": 1}).status_code == 401
        e = _client()
        assert e.post("/api/login", json={"name": "eva", "password": "evas-pass123"}).status_code == 200
        assert e.get("/api/guides/export").json()["buecher"] == []          # fremder Benutzer: nur eigene (keine) Bücher
    # Eva legt dasselbe Buch an und wandert eine andere Tour: sie sieht nur ihr eigenes „gewandert“
        from app import ctx
        uid = e.get("/api/me").json()["user"]["uid"]
        with ctx.as_user(uid):
            _book(b)
            _walk("e1", "Eva unterwegs", 47.54, 11.0, int(time.time()) - 7200)
        name = lambda ts: [t.get("gewandert", [{}])[0].get("name") for t in ts]
        assert name(e.get("/api/guides/export").json()["buecher"][0]["touren"]) == [None, None, "Eva unterwegs"]
        assert name(c.get("/api/guides/export").json()["buecher"][0]["touren"]) == ["Max wandert", None, None]
        assert name(o.get("/api/guides/export").json()["buecher"][0]["touren"]) == ["Max wandert", None, None]   # Betrachter: die des Besitzers


def test_titelbild_nur_mit_cover():
    b = _book()
    with _client() as c:
        v = c.post("/api/guides/cover", params={"book": b}, files={"file": ("x.png", _png(), "image/png")}).json()["v"]
        ohne = c.get("/api/guides/export").json()["buecher"][0]
        mit = c.get("/api/guides/export", params={"cover": 1}).json()
    assert ohne["cover_v"] == v and "cover" not in ohne
    bk = mit["buecher"][0]
    assert bk["cover_v"] == v and bk["cover"].startswith("data:image/jpeg;base64,") and len(bk["cover"]) <= 200_000
    import base64
    im = Image.open(io.BytesIO(base64.b64decode(bk["cover"].split(",", 1)[1])))
    assert im.format == "JPEG" and max(im.size) <= 480
    assert _lies(mit)[0][0]["cover"] == bk["cover"]


def test_zu_grosses_titelbild_wird_kleiner():
    from app import wanderfuehrer
    im = Image.frombytes("RGB", (480, 480), os.urandom(480 * 480 * 3))        # Rauschen: als JPEG q100 weit über 150 kB
    b = io.BytesIO()
    im.save(b, "JPEG", quality=100)
    assert len(b.getvalue()) * 4 // 3 > 200_000
    s = wanderfuehrer._cover_data(b.getvalue())
    assert s is None or (s.startswith("data:image/jpeg;base64,") and len(s) <= 200_000)


def test_hoechstens_400_punkte_und_groesse():
    for k in range(5):
        for i in range(80):
            db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES(?,?,?,?,?)",
                       (f"Rother Band {k + 1}", f"{i + 1} Tour", json.dumps(_line(45.0 + k + i * 0.02, 11.0, 401)), 12.0, 800))
    db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES(?,?,?,?,?)", ("Lang", "Riesig", json.dumps(_line(44.0, 9.0, 2000)), 50.0, 3000))
    with _client() as c:
        t0 = time.time()
        r = c.get("/api/guides/export")
        dt = time.time() - t0
        rz = c.get("/api/guides/export", headers={"Accept-Encoding": "gzip"})
    d = r.json()
    riesig = next(b for b in d["buecher"] if b["name"] == "Lang")["touren"][0]
    p = _entpacke(riesig["pts"])
    assert len(p) <= 401 and p[0] == (44.0, 9.0) and (round(p[-1][0], 5), round(p[-1][1], 5)) == (round(44.0 + 1999 * 0.0005, 5), round(9.0 + 1999 * 0.0004, 5))
    assert all(len(_entpacke(t["pts"])) <= 401 for b in d["buecher"] for t in b["touren"])
    raw = len(r.content)
    import gzip
    gz = len(gzip.compress(r.content))
    print(f"\n[Messung 3.56.0] /api/guides/export 5 × 80 Buchtouren à 401 Punkte + 1 × 2000: {raw} B, gzip {gz} B, {dt * 1000:.0f} ms")
    assert sum(len(b["touren"]) for b in d["buecher"]) == 401 and _lies(d)[1] == 0
    assert raw < 2_000_000 and gz < 500_000
    assert rz.status_code == 200


def test_rechte_liste():
    from app import main
    assert main.VIEWER_GET.match("/api/guides/export")
    assert not main.VIEWER_GET.match("/api/plan/guide/1") and not main.VIEWER_GET.match("/api/guides/export/x")
    assert not main.VIEWER_GET.match("/api/guides")


@pytest.mark.skipif(not shutil.which("node") or not (TAGEBUCH_JS / "calc-fuehrer-datei.js").exists(), reason="Node oder Tagebuch-Repo nicht vorhanden")
def test_echtes_tagebuch_modul_liest_die_antwort(tmp_path):
    b = _book()
    _book("Zweites Buch mit Leerzeichen", n=2, lat=46.0)
    _walk("m1", "Runde", 47.5, 11.0, int(time.time()) - 86400)
    with _client() as c:
        c.post("/api/guides/cover", params={"book": b}, files={"file": ("x.png", _png(), "image/png")})
        text = c.get("/api/guides/export", params={"cover": 1}).text
    f = tmp_path / "export.json"
    f.write_text(text, encoding="utf-8")
    code = (f"const D = require({json.dumps(str(TAGEBUCH_JS / 'calc-fuehrer-datei.js'))}); const fs = require('fs');"
            f"const r = D.lies(fs.readFileSync({json.dumps(str(f))}, 'utf8'));"
            "const pl = D.plane([], r, {}, (() => { let i = 0; return () => 'neu' + (i++); })());"
            "console.log(JSON.stringify({defekt: r.defekt, b: r.buecher.map(x => ({id: x.id, name: x.name, cover: !!x.cover, n: x.touren.length, p: x.touren.map(t => t.punkte.length)})),"
            " text: D.zusammenfassung(pl), nNeu: pl.nNeu, nTouren: pl.nTouren}));")
    out = json.loads(subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True).stdout)
    assert out["defekt"] == 0 and out["nNeu"] == 2 and out["nTouren"] == 5
    assert [x["n"] for x in out["b"]] == [3, 2] and out["b"][0]["cover"] and not out["b"][1]["cover"]
    assert all(x["id"] and x["id"].startswith("mt-") for x in out["b"]) and all(n == 60 for x in out["b"] for n in x["p"])
    assert out["text"] == "2 neue Bücher · 1 Titelbild"
