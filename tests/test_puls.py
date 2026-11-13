"""Puls: Zepp-Dekodierung, GPX-Roundtrip, API."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import zepp, tracks, gpxtools, db  # noqa: E402


def _pts(n=40, hr=True):
    s = {"trackid": "1700000000"}
    ll = ";".join(["5000000000,800000000"] + ["100,100"] * (n - 1))
    d = {"longitude_latitude": ll, "time": ";".join(["0"] + ["10"] * (n - 1)), "altitude": ";".join(["10000"] * n),
         "heart_rate": ";".join(("0,100" if i == 0 else "10,1") for i in range(n)) if hr else "", "gait": ""}
    return s, zepp.decode_points(s, d)


def test_decode_has_hr():
    s, pts = _pts()
    assert all(len(p) == 5 for p in pts)
    assert pts[0][4] == 100 and pts[10][4] == 110
    s, pts = _pts(hr=False)
    assert all(p[4] is None for p in pts)


def test_hr_roundtrip_and_api():
    from fastapi.testclient import TestClient
    from app import main
    s, pts = _pts()
    g = zepp.points_to_gpx(s, pts, "hike")
    assert "gpxtpx:hr" in g
    tour, c = tracks.adopt(g, "z.gpx", ident="zt1")
    assert "gpxtpx:hr" in tracks.gpx_file("zt1").read_text()
    r = TestClient(main.app).get("/api/tours/zt1/hr").json()
    assert r["n"] >= 30 and r["max"] >= 130 and 100 <= r["avg"] <= 140 and sum(r["zones"]) > 0
    # Tour ohne Puls
    s, p2 = _pts(hr=False)
    tracks.adopt(zepp.points_to_gpx(s, p2, "hike"), "n.gpx", ident="zt2")
    assert TestClient(main.app).get("/api/tours/zt2/hr").json() == {"n": 0}


def test_merge_hr_backfill():
    s, pts = _pts(hr=False)
    tracks.adopt(zepp.points_to_gpx(s, pts, "hike"), "m.gpx", ident="zt3")
    f = tracks.gpx_file("zt3")
    assert "gpxtpx:hr" not in f.read_text()
    s2, pts2 = _pts()
    txt, n = tracks.merge_hr(f.read_text(), [(p[0], p[4]) for p in pts2 if p[4]])
    assert n >= 30 and "xmlns:gpxtpx" in txt
    f.write_text(txt)
    from fastapi.testclient import TestClient
    from app import main
    assert TestClient(main.app).get("/api/tours/zt3/hr").json()["n"] >= 30
    assert tracks.merge_hr(txt, [(p[0], 99) for p in pts2])[1] == 0         # vorhandener Puls bleibt


def test_backfill_matches_existing_tour_without_gpx(monkeypatch):
    """Eine Komoot-Tour (ohne lokales GPX) bekommt den Puls über das passende Zepp-Training."""
    from fastapi.testclient import TestClient
    from app import main, puls
    s, pts = _pts()
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,status,source) VALUES(?,?,?,?,?,?,?,?,?)",
               ("k99", "Komoot-Tour", "hike", 1700000030, 1700000400, 500.0, 370, "tour_recorded", "komoot"))
    det = {"longitude_latitude": ";".join(["5000000000,800000000"] + ["100,100"] * 39), "time": ";".join(["0"] + ["10"] * 39),
           "altitude": ";".join(["10000"] * 40), "heart_rate": ";".join(("0,100" if i == 0 else "10,1") for i in range(40)), "gait": ""}

    class Api:
        def history(self): return [{"trackid": "1700000000", "dis": "500", "run_time": "390"}]
        def detail(self, sm): return det
    puls.backfill_hr(Api())
    r = TestClient(main.app).get("/api/tours/k99/hr").json()
    assert r["n"] >= 30 and r["max"] > 120
    puls.backfill_hr(Api())                                   # zweiter Lauf: nichts mehr zu tun


def test_tour_list_flags_hr():
    from fastapi.testclient import TestClient
    from app import main
    s, pts = _pts()
    tracks.adopt(zepp.points_to_gpx(s, pts, "hike"), "h.gpx", ident="zt8")
    s2, p2 = _pts(hr=False)
    tracks.adopt(zepp.points_to_gpx(s2, p2, "hike"), "h2.gpx", ident="zt9")
    r = {t["id"]: t["has_hr"] for t in TestClient(main.app).get("/api/tours").json()}
    assert r["zt8"] is True and r["zt9"] is False


def test_hr_survives_trackfix_export_backup():
    import io, zipfile
    from fastapi.testclient import TestClient
    from app import main, trackfix, extras, sync
    c = TestClient(main.app)
    s, pts = _pts()
    tracks.adopt(zepp.points_to_gpx(s, pts, "hike"), "t.gpx", ident="zt20")
    # Spur-Korrektur schreibt das GPX neu – der Puls bleibt
    trackfix.apply("zt20", remove_spikes=True, smooth=True)
    assert "gpxtpx:hr" in tracks.gpx_file("zt20").read_text()
    assert c.get("/api/tours/zt20/hr").json()["n"] >= 30
    # Export enthält Zeit und Puls
    g = c.get("/api/tours/zt20/gpx").text
    assert "<time>" in g and "gpxtpx:hr" in g and "xmlns:gpxtpx" in g
    # Puls-Zusatzdatei (Komoot-Tour) kommt ins Backup und in den Export
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,status,source) VALUES(?,?,?,?,?,?,?,?,?)",
               ("k77", "K", "hike", 1700000000, 1700000400, 500.0, 400, "tour_recorded", "komoot"))
    from app import routes
    routes.store("k77", [(50 + i * 1e-5, 8 + i * 1e-5, 100.0, i * 10000) for i in range(40)])
    import json
    tracks.hr_sidecar("k77").write_text(json.dumps([[i * 10, 100 + i] for i in range(40)]))
    assert "gpxtpx:hr" in c.get("/api/tours/k77/gpx").text
    z = zipfile.ZipFile(io.BytesIO(extras.make_backup()[1]))
    assert "tracks/k77.hr.json" in z.namelist() and "tracks/zt20.gpx" in z.namelist()


def test_viewer_may_read_hr():
    from app import main
    assert main.VIEWER_GET.match("/api/tours/abc/hr") and not main.VIEWER_GET.match("/api/tours/abc/elev-fix")


def test_hr_stats_all_tours():
    from fastapi.testclient import TestClient
    from app import main
    c = TestClient(main.app)
    s, pts = _pts()
    tracks.adopt(zepp.points_to_gpx(s, pts, "hike"), "a.gpx", ident="zs1")
    s2, p2 = _pts(hr=False)
    tracks.adopt(zepp.points_to_gpx(s2, p2, "hike"), "b.gpx", ident="zs2")
    r = c.get("/api/hr/stats").json()
    ids = {t["id"]: t for t in r["tours"]}
    assert "zs1" in ids and "zs2" not in ids and r["hrmax"] >= 185
    assert sum(ids["zs1"]["zones"]) > 300 and 100 <= ids["zs1"]["avg"] <= 140
    assert c.get("/api/hr/stats").json() == r                      # zweiter Aufruf aus dem Zwischenspeicher
    assert main.VIEWER_GET.match("/api/hr/stats")


def test_tour_pdf_with_hr():
    import pytest
    pytest.importorskip("reportlab")
    from fastapi.testclient import TestClient
    from app import main
    s, pts = _pts()
    tracks.adopt(zepp.points_to_gpx(s, pts, "hike"), "p.gpx", ident="zp1")
    r = TestClient(main.app).get("/api/tours/zp1/pdf?photos_on=0")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"


# ---------- Höhe aus der Uhr abgleichen (Zepp) ----------
def _zp(n=60, f=lambda i: 1000 + i, t0=1700000000):
    return [(t0 + i * 10, f(i)) for i in range(n)]


def test_align_zepp_keeps_level_takes_shape():
    from app import elev
    n = 60
    items = [(50.0, 8.0, 500 + (i % 3), i * 10000) for i in range(n)]           # Original flach auf ≈ 500 m, Zeit in ms seit Start
    zp = _zp(n)                                                                  # Uhr steigt 1 m je Punkt, absolut um ≈ 500 m daneben
    out = elev.align_zepp(items, zp, 1700000000)
    assert out is not None and len(out) == n
    assert abs(out[n - 1] - out[0] - (n - 1)) < 0.2                              # Verlauf der Uhr
    assert 495 < sorted(out)[n // 2] < 535                                       # Niveau der Originalhöhen (Median)
    assert elev.align_zepp([(50.0, 8.0, None, i * 10000) for i in range(n)], zp, 1700000000)[0] == 1000   # ohne Original: Zepp unverändert


def test_align_zepp_rejects_poor_data():
    from app import elev
    n = 60
    items = [(50.0, 8.0, 500.0, i * 10000) for i in range(n)]
    assert elev.align_zepp(items, _zp(30), 1700000000) is None                   # deckt nur die Hälfte ab (< 80 %)
    assert elev.align_zepp(items, _zp(n, f=lambda i: -20000), 1700000000) is None   # nur Platzhalter
    assert elev.align_zepp(items, _zp(n, f=lambda i: 800), 1700000000) is None       # konstant = keine Messung
    out = elev.align_zepp(items, _zp(n, f=lambda i: -20000 if i % 10 == 0 else 1000 + i), 1700000000)
    assert out is not None and max(out) < 1000                                   # Platzhalter ignoriert, Niveau 500 erhalten


def _zepp_tour(tid="k55", start=1700000000):
    from app import routes
    db.execute("INSERT OR REPLACE INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
               (tid, "Komoot-Tour", "hike", start, start + 590, 800.0, 590, 900.0, 880.0, "tour_recorded", "komoot"))
    routes.store(tid, [(50 + i * 1e-4, 8 + i * 1e-4, 500 + (40 if i % 2 else -40), i * 10000) for i in range(60)])   # verrauschtes GPS


class _ZApi:
    """Zepp-Training mit 60 Punkten, Höhe steigt gleichmäßig um 1 m je Punkt (= 59 m Aufstieg)."""
    def __init__(self, alt=lambda i: 123400 + i * 100): self.alt = alt
    def history(self): return [{"trackid": "1700000000", "dis": "800", "run_time": "590"}]
    def detail(self, sm):
        n = 60
        return {"longitude_latitude": ";".join(["5000000000,800000000"] + ["10000,10000"] * (n - 1)), "time": ";".join(["0"] + ["10"] * (n - 1)),
                "altitude": ";".join(str(self.alt(i)) for i in range(n)), "heart_rate": "", "gait": ""}


def test_zepp_fix_and_restore():
    from app import elev, routes
    _zepp_tour()
    r = elev.zepp_fix("k55", _ZApi())
    assert r["orig_up"] == 900.0 and 50 <= r["up"] <= 65 and r["down"] < 5
    t = db.one("SELECT * FROM tours WHERE id='k55'")
    assert abs(t["up_m"] - r["up"]) < 0.01 and db.one("SELECT src FROM elev_fix WHERE id='k55'")["src"] == "zepp"
    assert elev.orig_path("k55").exists()
    alts = [p[2] for p in routes.load("k55")]
    assert abs((alts[-1] - alts[0]) - 59) < 0.2 and 440 < alts[0] < 560           # Niveau bleibt bei ≈ 500 m
    elev.zepp_fix("k55", _ZApi())                                                 # erneut: Original bleibt das ursprüngliche
    assert db.one("SELECT orig_up FROM elev_fix WHERE id='k55'")["orig_up"] == 900.0
    assert elev.restore("k55")
    t = db.one("SELECT * FROM tours WHERE id='k55'")
    assert t["up_m"] == 900.0 and t["down_m"] == 880.0 and not elev.orig_path("k55").exists()
    assert routes.load("k55")[1][2] == 540 and db.one("SELECT 1 FROM elev_fix WHERE id='k55'") is None


def test_zepp_fix_errors_and_api(monkeypatch):
    import pytest
    from app import elev, main
    from fastapi.testclient import TestClient
    _zepp_tour("k56", 1600000000)                                                 # anderer Start, andere Strecke → kein Training
    with pytest.raises(elev.ZeppFixError, match="Kein passendes Zepp-Training"):
        elev.zepp_fix("k56", _ZApi())
    _zepp_tour("k57")
    with pytest.raises(elev.ZeppFixError, match="keine brauchbaren Höhendaten"):
        elev.zepp_fix("k57", _ZApi(alt=lambda i: -2000000))
    assert db.one("SELECT 1 FROM elev_fix WHERE id='k57'") is None and not elev.orig_path("k57").exists()
    with pytest.raises(KeyError):
        elev.zepp_fix("gibtsnicht", _ZApi())
    from app import sync
    monkeypatch.setattr(sync, "_zepp_api", lambda: (_ for _ in ()).throw(RuntimeError("Zepp-Zugangsdaten fehlen (Einstellungen)")))
    with pytest.raises(elev.ZeppFixError, match="Kein Zepp-Zugang"):
        elev.zepp_fix("k57")
    c = TestClient(main.app)
    r = c.post("/api/tours/k57/elev-zepp")
    assert r.status_code == 422 and "Zepp-Zugang" in r.json()["detail"]
    assert c.post("/api/tours/gibtsnicht/elev-zepp").status_code == 404


def test_zepp_fix_all_job():
    from app import elev
    _zepp_tour("k58")
    assert elev.zepp_fix_all(_ZApi()) == 1
    assert elev.zepp_fix_all(_ZApi()) == 0                                         # bereits abgeglichen → übersprungen
    elev.restore("k58")
