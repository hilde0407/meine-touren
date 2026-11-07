"""Touren mit anderen Benutzern teilen (Strecke + Fotos übernehmen)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401


def _gpx(t0="2026-07-01T08"):
    pts = "".join(f'<trkpt lat="{47+i*0.001}" lon="11"><ele>{1000+i}</ele><time>{t0}:{i//60:02d}:{i%60:02d}Z</time></trkpt>' for i in range(59))
    return f'<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><name>Gipfel</name><trkseg>{pts}</trkseg></trk></gpx>'


def test_share_tour_copy():
    from fastapi.testclient import TestClient
    from PIL import Image
    from app import main, db, config, tracks, photos
    config.LIB_DIR.mkdir(parents=True, exist_ok=True)
    t, c0 = tracks.adopt(_gpx(), "g.gpx", name="Gipfeltour", ident="g1")
    p1 = config.LIB_DIR / "b.jpg"; Image.new("RGB", (40, 30), "blue").save(p1)
    photos._store([(str(p1), p1.stat().st_mtime, p1.stat().st_size, t["start_ts"] + 20, None, None)]); photos.assign_all()
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        c.post("/api/users", json={"name": "Anna", "email": "anna@example.com", "password": "annas-pass1", "role": "user"})
        a = TestClient(main.app); a.post("/api/login", json={"name": "anna", "password": "annas-pass1"})
        assert a.get("/api/shared/tours").json() == []
        assert c.post("/api/grants", json={"grantee": "anna", "scope": "tour", "ref": "g1"}).status_code == 200
        lst = a.get("/api/shared/tours").json()
        assert len(lst) == 1 and lst[0]["name"] == "Gipfeltour" and not lst[0]["imported"]
        r = a.post("/api/shared/tours-import", json={"owner": "max", "ids": ["g1", "nicht-freigegeben"]}).json()
        assert r["imported"] == 1 and r["photos"] == 1 and not r["failed"]
        tours = a.get("/api/tours").json()
        assert [x["name"] for x in tours] == ["Gipfeltour"]
        assert [p["tour_id"] for p in a.get("/api/photos").json()] == [tours[0]["id"]]
        assert a.get("/api/shared/tours").json()[0]["imported"] is True
        assert [x["name"] for x in c.get("/api/tours").json()] == ["Gipfeltour"]     # Maxens Tour bleibt unverändert
