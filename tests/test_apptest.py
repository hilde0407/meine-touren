"""App-Ablauf: Foto wird WÄHREND der Aufzeichnung hochgeladen, der Track erst am Ende."""
import io, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401
from tests.test_android import _gpx


def _jpeg(dt):
    from PIL import Image
    ex = Image.Exif(); ex[0x8769] = {0x9003: dt, 0x9011: "+00:00"}
    b = io.BytesIO(); Image.effect_noise((400, 300), 60).convert("RGB").save(b, "JPEG", exif=ex.tobytes()); return b.getvalue()


def _wait(secs=10):
    from app import jobs
    t = time.time()
    while time.time() - t < secs:
        if not jobs._s()["state"].get("running"):
            return
        time.sleep(0.1)


def test_photo_before_track():
    from fastapi.testclient import TestClient
    from app import main, db
    c = TestClient(main.app)
    # Foto um 08:00:30 (Track 08:00:00-08:00:59 UTC), EXIF ohne Zeitzone
    r = c.post("/api/rec-photos", files=[("files", ("MT_1.jpg", _jpeg("2026:07:01 08:00:30"), "image/jpeg"))])
    assert r.json()["saved"] == 1
    _wait()
    r = c.post("/api/record/upload", json={"gpx": _gpx(), "name": "Runde", "sport": "hike"})
    assert r.status_code == 200
    _wait()
    time.sleep(0.5); _wait()
    n = db.one("SELECT COUNT(*) n FROM photos")["n"]
    t = db.one("SELECT COUNT(*) n FROM photos WHERE tour_id IS NOT NULL")["n"]
    assert n == 1 and t == 1, (n, t)


def test_photo_other_timezone():
    """Telefon in UTC+0, Server in Mitteleuropa, Kamera ohne Zeitzonen-Angabe: Foto muss trotzdem zur Tour passen."""
    from fastapi.testclient import TestClient
    from PIL import Image
    from app import main, db
    ex = Image.Exif(); ex[0x8769] = {0x9003: "2026:07:01 08:00:30"}
    b = io.BytesIO(); Image.effect_noise((400, 300), 60).convert("RGB").save(b, "JPEG", exif=ex.tobytes())
    c = TestClient(main.app)
    c.post("/api/rec-photos", files=[("files", ("MT_2.jpg", b.getvalue(), "image/jpeg"))], headers={"X-UTC-Offset": "+00:00"})
    _wait()
    c.post("/api/record/upload", json={"gpx": _gpx().replace("2026-07-01", "2026-07-05"), "name": "Runde2", "sport": "hike"})
    _wait()
    assert db.one("SELECT COUNT(*) n FROM photos")["n"] == 0                 # anderer Tag: nicht zuordenbar
    c.post("/api/rec-photos", files=[("files", ("MT_3.jpg", b.getvalue().replace(b"2026:07:01", b"2026:07:05"), "image/jpeg"))], headers={"X-UTC-Offset": "+00:00"})
    _wait()
    assert db.one("SELECT COUNT(*) n FROM photos WHERE tour_id IS NOT NULL")["n"] == 1
