"""Echte PDF-Berichte (reportlab)."""
import json
import sys
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401


def _seed(db, routes):
    from app.gpxtools import TZ
    ts = lambda d: int(datetime.fromisoformat(d + "T09:00:00").replace(tzinfo=TZ).timestamp())
    for i, d in enumerate(["2026-05-01", "2026-05-02", "2026-05-03"]):
        db.execute("INSERT INTO tours(id,name,sport,start_ts,dist_m,up_m,down_m,dur_s,lat,lng) VALUES(?,?,?,?,?,?,?,?,?,?)", (f"p{i}", f"Tour Ä{i} – Gipfel", "hike" if i < 2 else "bicycle", ts(d), 12000 + i * 1000, 600, 580, 14400, 28.1, -16.6))
        pts = [[28.1 + k * 0.001, -16.6 + k * 0.0012 + i * 0.01, 1000 + 15 * k - (k > 30) * 40 * (k - 30) / 3, k * 60000] for k in range(60)]
        routes.path_full(f"p{i}").parent.mkdir(parents=True, exist_ok=True)
        routes.path_full(f"p{i}").write_text(json.dumps(pts))


def test_pdfs(monkeypatch):
    from app import db, routes, pdfgen, more2
    _seed(db, routes)
    monkeypatch.setattr(pdfgen, "_tile", lambda *a: None)            # kein Netz im Test
    r = pdfgen.api_tour_pdf("p0", 1, 6)
    assert r.body[:5] == b"%PDF-" and len(r.body) > 3000 and "attachment" in r.headers["content-disposition"]
    trip = {"id": "p0", "region": "Teneriffa", "country": "Spanien", "start": "2026-05-01", "end": "2026-05-03", "days": 3, "tours": ["p0", "p1", "p2"], "km": 39, "up_m": 1800, "h": 12}
    monkeypatch.setattr(more2, "build_trips", lambda: [dict(trip)])
    r = pdfgen.api_trip_pdf("p0", 0, 0)
    assert r.body[:5] == b"%PDF-"
    r = pdfgen.api_recap_pdf(2026, 1, 3)
    assert r.body[:5] == b"%PDF-"
    from fastapi import HTTPException
    import pytest
    with pytest.raises(HTTPException):
        pdfgen.api_tour_pdf("nix")
    with pytest.raises(HTTPException):
        pdfgen.api_recap_pdf(1999)


def test_pdf_http(monkeypatch):
    from app import db, routes, pdfgen, main
    from fastapi.testclient import TestClient
    _seed(db, routes)
    monkeypatch.setattr(pdfgen, "_tile", lambda *a: None)
    r = TestClient(main.app).get("/api/tours/p1/pdf?photos_on=0&n=3")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf" and r.content[:5] == b"%PDF-"
