"""Android-Hülle: Aufzeichnungslogik (reines Java) und Server-Endpunkt für hochgeladene Aufzeichnungen."""
import shutil
import subprocess
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not shutil.which("javac"), reason="kein JDK")
def test_trackstore_java(tmp_path):
    src = ROOT / "android/app/src/main/java/de/meinetouren/app/TrackStore.java"
    subprocess.run(["javac", "-d", str(tmp_path), str(src), str(ROOT / "tests/android/TrackStoreCheck.java")], check=True)
    r = subprocess.run(["java", "-cp", str(tmp_path), "TrackStoreCheck"], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr


@pytest.mark.skipif(not shutil.which("javac"), reason="kein JDK")
def test_guide_java(tmp_path):
    """Wegführung: Abbiegungen erkennen, Ansagen, Abkommen und Rückkehr, Rundweg, Rauschen."""
    d = ROOT / "android/app/src/main/java/de/meinetouren/app"
    subprocess.run(["javac", "-d", str(tmp_path), str(d / "GuideText.java"), str(d / "Guide.java"), str(ROOT / "tests/android/GuideCheck.java"),
                    str(ROOT / "tests/android/GuideTextCheck.java")], check=True)
    for k in ("GuideCheck", "GuideTextCheck"):
        r = subprocess.run(["java", "-cp", str(tmp_path), k], capture_output=True, text=True, cwd=tmp_path)
        assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr


def _gpx():
    pts = "".join(f'<trkpt lat="{47+i*0.0005}" lon="11.0"><ele>{1000+i*3}</ele><time>2026-07-01T08:{i//60:02d}:{i%60:02d}Z</time></trkpt>' for i in range(60))
    return f'<?xml version="1.0"?><gpx version="1.1"><trk><name>x</name><type>skitour</type><trkseg>{pts}</trkseg></trk></gpx>'


def test_record_upload():
    from fastapi.testclient import TestClient
    from app import main, db
    c = TestClient(main.app)
    r = c.post("/api/record/upload", json={"gpx": _gpx(), "name": "Morgenrunde", "sport": "skitour"})
    assert r.status_code == 200 and not r.json()["dup"]
    tid = r.json()["id"]
    t = db.one("SELECT name,sport FROM tours WHERE id=?", (tid,))
    assert t["name"] == "Morgenrunde" and t["sport"] == "skitour"
    assert c.post("/api/record/upload", json={"gpx": _gpx(), "name": "nochmal"}).json()["dup"] is True
    assert c.post("/api/record/upload", json={"gpx": "<gpx/>"}).status_code == 400


def test_record_upload_notifies(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main, db, more2
    sent = []
    monkeypatch.setattr(more2, "notify_send", lambda t, title="x": sent.append((t, title)))
    c = TestClient(main.app)
    db.put("notify_url", "")
    c.post("/api/record/upload", json={"gpx": _gpx().replace("2026-07-01", "2026-07-02"), "name": "A"})
    import time; time.sleep(0.2)
    assert sent == []                                                  # ohne Webhook keine Meldung
    db.put("notify_url", "https://ntfy.sh/test")
    c.post("/api/record/upload", json={"gpx": _gpx().replace("2026-07-01", "2026-07-03"), "name": "Abendrunde"})
    time.sleep(0.3)
    assert len(sent) == 1 and "Abendrunde" in sent[0][0]
    db.put("notify_events", "0")
    c.post("/api/record/upload", json={"gpx": _gpx().replace("2026-07-01", "2026-07-04"), "name": "B"})
    time.sleep(0.3)
    assert len(sent) == 1                                              # abgeschaltet


def test_offline_cache_wired():
    """Offline-Speicher der App: Klasse vorhanden, im WebViewClient eingehängt, Anmelde-/Live-Pfade ausgenommen."""
    d = ROOT / "android/app/src/main/java/de/meinetouren/app"
    oc = (d / "OfflineCache.java").read_text(encoding="utf8")
    ma = (d / "MainActivity.java").read_text(encoding="utf8")
    assert "shouldInterceptRequest" in ma and "OfflineCache.serve" in ma and "OfflineCache.wanted" in ma
    for pfad in ("login", "logout", "live", "backup", "photo/"):
        assert pfad in oc.split("SKIP", 1)[1].split(";", 1)[0], pfad
    assert "offlineServed" in ma and "clearOffline" in ma


def test_record_upload_waypoints():
    """Wegpunkte aus der App-GPX werden mit der Tour gespeichert, lassen sich ändern und löschen."""
    from fastapi.testclient import TestClient
    from app import main, db
    c = TestClient(main.app)
    wpt = ('<wpt lat="47.0100" lon="11.0"><time>2026-07-01T08:10:00Z</time><name>Rast am Bach</name></wpt>'
           '<wpt lat="47.0200" lon="11.0"><time>2026-07-01T08:20:00Z</time><name>Wegpunkt</name></wpt>')
    g = _gpx().replace("<trk>", wpt + "<trk>", 1).replace("2026-07-01", "2026-07-02")
    r = c.post("/api/record/upload", json={"gpx": g, "name": "Mit Wegpunkten"})
    assert r.status_code == 200
    tid = r.json()["id"]
    w = c.get(f"/api/tours/{tid}/wps").json()
    assert [x["note"] for x in w] == ["Rast am Bach", "Wegpunkt"] and w[0]["ts"] < w[1]["ts"] and abs(w[0]["lat"] - 47.01) < 1e-6
    assert c.put(f"/api/tours/{tid}/wps/{w[0]['id']}", json={"note": "  Pause   am Wasser "}).json()["ok"]
    assert c.get(f"/api/tours/{tid}/wps").json()[0]["note"] == "Pause am Wasser"
    assert c.put(f"/api/tours/{tid}/wps/99999", json={"note": "x"}).status_code == 404
    c.delete(f"/api/tours/{tid}/wps/{w[1]['id']}")
    assert len(c.get(f"/api/tours/{tid}/wps").json()) == 1
    # Tour ohne Wegpunkte: leere Liste
    assert c.get("/api/tours/gibtsnicht/wps").json() == []


def test_photo_comments_api():
    """Kommentare zu Fotos: anlegen, je Tour auflisten, löschen; leere Texte werden abgelehnt; mit dem Foto verschwinden sie."""
    from fastapi.testclient import TestClient
    from app import main, db, photos
    c = TestClient(main.app)
    db.execute("INSERT INTO photos(path,taken_ts,tour_id) VALUES('/x/kommentar.jpg',1,'kt1')")
    pid = db.one("SELECT id FROM photos WHERE path='/x/kommentar.jpg'")["id"]
    assert c.post(f"/api/photos/{pid}/comments", json={"text": "   "}).status_code == 400
    assert c.post("/api/photos/987654/comments", json={"text": "x"}).status_code == 404
    r = c.post(f"/api/photos/{pid}/comments", json={"text": "Schöner Blick!"})
    assert r.status_code == 200 and r.json()["text"] == "Schöner Blick!"
    c.post(f"/api/photos/{pid}/comments", json={"text": "Zweiter"})
    m = c.get("/api/tours/kt1/comments").json()
    assert [x["text"] for x in m[str(pid)]] == ["Schöner Blick!", "Zweiter"]
    assert len(c.get(f"/api/photos/{pid}/comments").json()) == 2
    c.delete(f"/api/comments/{r.json()['id']}")
    assert [x["text"] for x in c.get("/api/tours/kt1/comments").json()[str(pid)]] == ["Zweiter"]
    photos.delete_photos([pid])
    assert c.get("/api/tours/kt1/comments").json() == {}


def test_story_place_name(monkeypatch):
    """Ortsname zu einer Koordinate für die Erzählung; Fehler ergeben einen leeren Namen statt eines Absturzes."""
    from fastapi.testclient import TestClient
    from app import main, extras
    c = TestClient(main.app)
    monkeypatch.setattr(extras, "place_name", lambda la, ln: "Garmisch")
    assert c.get("/api/place?lat=47.5&lng=11.1").json() == {"name": "Garmisch"}
    monkeypatch.setattr(extras, "place_name", lambda la, ln: (_ for _ in ()).throw(RuntimeError("offline")))
    assert c.get("/api/place?lat=47.5&lng=11.1").json() == {"name": None}
    assert c.get("/api/place?lat=95&lng=11.1").status_code == 400
