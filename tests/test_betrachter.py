"""Betrachter-Zugang (nur ansehen) und Live-Standort."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401
from tests.test_teilen import _gpx


def test_viewer_and_live():
    from fastapi.testclient import TestClient
    from app import main, tracks
    tracks.adopt(_gpx(), "g.gpx", name="Gipfeltour", ident="g1")
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "password": "geheim1234"})
        r = c.post("/api/users", json={"name": "Oma", "password": "omas-pass12", "role": "viewer"})
        assert r.status_code == 200, r.text
        users = {u["name"].lower(): u for u in c.get("/api/users").json()}
        assert users["oma"]["role"] == "viewer" and users["oma"]["owner"] == users["max"]["uid"]
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert v.get("/api/me").json()["user"]["role"] == "viewer"
        tours = v.get("/api/tours").json()                              # sieht Maxens Touren
        tours = [t for t in tours if t["name"] == "Gipfeltour"]
        assert len(tours) == 1
        assert v.get(f"/api/tours/{tours[0]['id']}/coords").status_code == 200
        assert v.get("/api/photos").status_code == 200
        # nichts ändern, nichts Privates
        assert v.post("/api/settings", json={"live_mode": "on"}).status_code == 403
        assert v.delete(f"/api/tours/{tours[0]['id']}").status_code == 403
        assert v.get("/api/users").status_code in (401, 403)
        assert v.get("/api/jobs").status_code == 403
        tid = tours[0]["id"]
        for bad in (f"/api/tours/{tid}/pdf", f"/api/tours/{tid}/trackfix", f"/api/tours/{tid}/shares", "/api/trips/x/pdf", "/api/recap/2026/pdf", "/api/photo-library"):
            assert v.get(bad).status_code == 403, bad
        for bad in ("/api/photo-delete", "/api/photo-upload", f"/api/tours/{tid}/rename", f"/api/tours/{tid}/note", f"/api/tours/{tid}/share"):
            assert v.post(bad, json={}).status_code == 403, bad
        assert v.get(f"/api/tours/{tid}/gpx").status_code == 200
        s = v.get("/api/settings").json()
        assert "notify_url" not in s and "live_mode" not in s
        # Live-Standort
        assert c.post("/api/live", json={"lat": 47.1, "lon": 11.2}).status_code == 403     # aus
        assert v.get("/api/live").json() == {}
        assert c.post("/api/settings", json={"live_mode": "rec"}).status_code == 200
        assert c.post("/api/live", json={"lat": 47.1, "lon": 11.2, "acc": 12, "source": "rec"}).status_code == 200
        assert c.post("/api/live", json={"lat": 999, "lon": 11.2}).status_code == 400
        p = v.get("/api/live").json()
        assert p["lat"] == 47.1 and p["lon"] == 11.2 and p["age_s"] < 60
        assert v.post("/api/live", json={"lat": 1, "lon": 1}).status_code == 403          # Betrachter sendet nicht
        c.post("/api/settings", json={"live_mode": "off"})
        assert v.get("/api/live").json() == {}


def test_record_upload_lands_in_users_account():
    """App-Aufzeichnung muss im Konto des angemeldeten Benutzers landen (nicht im Altbestand) – und die Rettung holt Altlasten."""
    from fastapi.testclient import TestClient
    from app import main, config
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "password": "geheim1234"})
        r = c.post("/api/record/upload", json={"gpx": _gpx(), "name": "", "sport": "hike"})
        assert r.status_code == 200, r.text
        tid = r.json()["id"]
        assert any(t["id"] == tid for t in c.get("/api/tours").json())
        # Altlast im Altbestand nachstellen und retten
        legacy = config.user_dir(None) / "tracks"
        legacy.mkdir(parents=True, exist_ok=True)
        (legacy / "g1700000001.gpx").write_text(_gpx().replace("2023", "2026"), encoding="utf-8")
        rr = c.post("/api/record/rescue").json()
        assert rr["found"] == 1 and rr["imported"][0]["id"] == "g1700000001", rr
        assert any(t["id"] == "g1700000001" for t in c.get("/api/tours").json())


def test_rec_photos_upload():
    """Fotos aus der App landen im Eingang des Benutzers; Betrachter darf nichts hochladen."""
    from fastapi.testclient import TestClient
    from app import main, config
    jpg = b"\xff\xd8\xff\xe0" + b"0" * 100
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "password": "geheim1234"})
        c.post("/api/users", json={"name": "Oma", "password": "omas-pass12", "role": "viewer"})
        r = c.post("/api/rec-photos", files=[("files", ("MT_1.jpg", jpg, "image/jpeg")), ("files", ("x.exe", b"zzz", "application/octet-stream"))])
        assert r.status_code == 200 and r.json()["saved"] == 1, r.text
        v = TestClient(main.app)
        v.post("/api/login", json={"name": "oma", "password": "omas-pass12"})
        assert v.post("/api/rec-photos", files=[("files", ("MT_2.jpg", jpg, "image/jpeg"))]).status_code == 403
