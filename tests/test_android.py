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
