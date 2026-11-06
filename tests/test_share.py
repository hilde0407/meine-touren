"""Teilen-Ziel (Android-Teilen-Menü) und Manifest."""
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh, gpx  # noqa: F401


def test_manifest_valid():
    m = json.loads((Path(__file__).resolve().parent.parent / "app/static/manifest.webmanifest").read_text())
    st = m["share_target"]
    assert st["method"] == "POST" and st["enctype"] == "multipart/form-data" and st["params"]["files"][0]["name"] == "files"
    assert ".gpx" in st["params"]["files"][0]["accept"] and "image/jpeg" in st["params"]["files"][0]["accept"]
    assert {i["purpose"] for i in m["icons"]} == {"any", "maskable"} and m["scope"] == "./" and len(m["shortcuts"]) >= 3


def test_share_target_imports_gpx_and_photos(fresh):
    from app import config, db
    from fastapi.testclient import TestClient
    from app import main
    c = TestClient(main.app)
    g = gpx("Workout--2025-06-01--08-00-00.gpx")
    files = [("files", ("Meine Runde.gpx", g.encode(), "application/octet-stream")),
             ("files", ("foto.jpg", b"\xff\xd8\xff\xe0not-really-a-jpeg", "image/jpeg")),
             ("files", ("virus.exe", b"MZ", "application/octet-stream"))]
    r = c.post("/api/share-target", files=files, follow_redirects=False)
    assert r.status_code == 303
    loc = r.headers["location"]
    assert loc.startswith("/#/shared?") and "t=1" in loc and "a=1" in loc and "p=1" in loc and "x=1" in loc
    assert db.one("SELECT COUNT(*) n FROM tours")["n"] == 1
    assert (config.INBOX_DIR / "teilen" / "foto.jpg").exists() and not (config.INBOX_DIR / "teilen" / "virus.exe").exists()
    assert (config.INBOX_DIR / "touren" / "erledigt" / "Meine Runde.gpx").exists()
    # dieselbe Datei noch einmal: kein Duplikat
    r = c.post("/api/share-target", files=[("files", ("Meine Runde.gpx", g.encode(), "application/octet-stream"))], follow_redirects=False)
    assert "t=0" in r.headers["location"] and db.one("SELECT COUNT(*) n FROM tours")["n"] == 1
