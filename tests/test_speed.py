"""Übersicht: Routen mit ETag, Wiederholungs-Auswertung wird zwischengespeichert."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401
from tests.test_wiederholung import _loop


def test_routes_etag_and_repeats_cache():
    from fastapi.testclient import TestClient
    from app import tracks, db, more, main
    for i, day in enumerate(("03-01", "05-10", "08-02")):
        tracks.adopt(_loop(day), f"s{i}.gpx", name=f"S{i}", ident=f"s{i}")
    c = TestClient(main.app)
    r = c.get("/api/routes")
    assert r.status_code == 200 and len(r.json()) == 3 and r.headers["etag"]
    assert c.get("/api/routes", headers={"If-None-Match": r.headers["etag"]}).status_code == 304
    more.api_repeats()
    t = time.time(); more.api_repeats(); assert time.time() - t < 0.05
    db.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('irgendwas','1')")        # fremde DB-Änderung rechnet nicht neu
    t = time.time(); more.api_repeats(); assert time.time() - t < 0.05
    tracks.adopt(_loop("09-09"), "s3.gpx", name="S3", ident="s3")                    # neue Tour: neu berechnen
    assert more.api_repeats()["s0"]["n"] == 4
    assert len(c.get("/api/routes").json()) == 4


def test_warm_thumbs_runs_without_photos():
    from app import photos
    assert photos.warm_thumbs() == 0
