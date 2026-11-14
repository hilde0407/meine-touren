"""3.10.0 – Genauigkeit der Uhren: Kennzahlen, Schwellen/Einschätzung, Job (idempotent, mit Obergrenzen), API, Rechte, Backup/Umzug.
Alle Daten sind konstruiert (bekannte Verhältnisse); echte Zepp-Antworten gibt es hier nicht: Verlauf und Detail sind nachgebaut
(Felder wie im Code verwendet: trackid, dis, run_time, source bzw. time, longitude_latitude, altitude)."""
import io
import json
import math
import sqlite3
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import config, db, devquality as dq, elev, extras, jobs, metrics, tracks, umzug  # noqa: E402
from tests.test_messwerte import _client  # noqa: E402

T0 = 1750000000
AMP = 40.0


# ---------------------------------------------------------------- Gelände (nachgebaut)
class _Px:
    def __init__(self, ty):
        self.ty = ty

    def __getitem__(self, k):
        h = 800 + AMP * math.sin((self.ty * 256 + k[1]) / 6.0)
        v = h + 32768
        return int(v // 256), int(v % 256), int((v - int(v)) * 256)


@pytest.fixture
def dem(monkeypatch):
    """Geländemodell als Formel: Höhe hängt nur von der Pixelzeile (Breitengrad) ab; keine Netzabrufe."""
    calls = []
    monkeypatch.setattr(elev, "_tile", lambda x, y: (calls.append((x, y)), _Px(y))[1])
    return calls


def _h(lat, lng, f=1.0):
    return 800 + f * AMP * math.sin(elev._px(lat, lng)[1] * 256 / 6.0)


def _line(n=300, step=0.00009, t=5, f=1.0, jump_at=None, gap_at=None):
    """Gerader Weg nach Norden (ca. 10 m je Punkt, Tempo 2 m/s), Höhe = f * Gelände."""
    pts, lat, ts = [], 48.0, T0
    for i in range(n):
        lat += step
        if jump_at is not None and i == jump_at:
            pts.append((lat + 0.05, 8.0, 900.0, ts))                      # Ausreißer (5,5 km daneben), nächster Punkt wieder auf dem Weg
        else:
            pts.append((lat, 8.0, round(_h(lat, 8.0, f), 1), ts))
        ts += t + (400 if gap_at is not None and i == gap_at else 0)
    return pts


def _gpx_text(pts):
    from datetime import datetime, timezone
    body = "".join(f'<trkpt lat="{la:.6f}" lon="{lo:.6f}"><ele>{el}</ele><time>{datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}</time></trkpt>'
                   for la, lo, el, t in pts)
    return f'<?xml version="1.0"?><gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1"><trk><type>hiking</type><trkseg>{body}</trkseg></trk></gpx>'


def _local(tid, pts, dist=3000, sport="hike", start=None):
    start = start or pts[0][3]
    config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
    tracks.gpx_file(tid).write_text(_gpx_text(pts), encoding="utf-8")
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,100,100,'t','local')",
               (tid, f"Tour {tid}", sport, start, start + 1500, dist, 1500))


def _komoot(tid, start, dist, sport="hike"):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,100,100,'t','komoot')",
               (tid, f"Komoot {tid}", sport, start, start + 3000, dist, 3000))
    db.execute("INSERT OR REPLACE INTO tour_source(tour_id,src,name) VALUES(?,'zepp','')", (tid,))


def _dev(c, **kw):
    return c.post("/api/devices", json=dict({"name": "Balance 2", "kind": "zepp"}, **kw)).json()["id"]


def _detail(f=1.3, n=120):
    """Zepp-Detail (Spaltenformat wie zepp.decode_points): Breite/Länge als Änderungen in 1e-8 Grad, Zeit als Abstände, Höhe in cm absolut."""
    la0 = 48.0
    steps = [0.0002] * (n - 1)
    lats = [la0 + sum(steps[:i]) for i in range(n)]
    ll = [f"{int(la0 * 1e8)},{int(8.0 * 1e8)}"] + [f"{int(0.0002 * 1e8)},0"] * (n - 1)
    return {"longitude_latitude": ";".join(ll), "time": ";".join(["0"] + ["10"] * (n - 1)),
            "altitude": ";".join(str(int(_h(la, 8.0, f) * 100)) for la in lats), "heart_rate": "", "gait": ""}


class _Api:
    def __init__(self, hist, f=1.3):
        self.hist, self.f, self.details = hist, f, 0

    def history(self):
        return self.hist

    def detail(self, s):
        self.details += 1
        return _detail(self.f)


def _summ(start, dis, rt=3000, src="run.46.huami.com"):
    return {"trackid": str(start + 10), "type": "6", "dis": str(dis), "run_time": str(rt), "end_time": str(start + rt), "source": src}


# ---------------------------------------------------------------- reine Kennzahlen
def test_percentile_and_ratio_with_known_values():
    assert dq.percentile([1, 2, 3, 4, 5], 50) == 3 and dq.percentile([1, 2, 3, 4, 5], 25) == 2 and dq.percentile([1, 2, 3, 4, 5], 75) == 4
    assert dq.percentile([0, 10], 25) == 2.5 and dq.percentile([], 50) is None
    assert dq.dist_ratio(9500, 10000) == (0.95, True)
    assert dq.dist_ratio(30000, 10000) == (3.0, False)                      # unplausibel
    assert dq.dist_ratio(4000, 10000)[1] is False and dq.dist_ratio(5000, 10000)[1] is True and dq.dist_ratio(20000, 10000)[1] is True
    assert dq.dist_ratio(0, 10000) == (None, None) and dq.dist_ratio(100, None) == (None, None)


def test_gps_quality_counts_jump_once_gap_share_and_density():
    g = dq.gps_quality([list(p[:3]) + [(p[3] - T0) * 1000] for p in _line(300, jump_at=100)], "hike")
    assert g["gps_jumps"] == 1                                              # Hin- und Rücksprung = ein Ereignis
    assert g["gps_gap_pct"] == 0.0 and g["gps_med_dt"] == 5.0
    assert 90 < dq.gps_quality([list(p[:3]) + [(p[3] - T0) * 1000] for p in _line(300)], "hike")["gps_pts_km"] < 110     # 300 Punkte auf ca. 3 km
    g = dq.gps_quality([list(p[:3]) + [(p[3] - T0) * 1000] for p in _line(300, gap_at=150)], "hike")
    assert g["gps_jumps"] == 0 and 20 < g["gps_gap_pct"] < 30               # 400 s Lücke bei 1900 s Gesamtdauer
    # Sportart-Grenze: 20 m/s zu Fuß = Sprung, mit dem Rad nicht
    fast = [[48 + i * 0.00036, 8.0, 0, i * 2000] for i in range(40)]      # 40 m alle 2 s = 20 m/s
    assert dq.gps_quality(fast, "hike")["gps_jumps"] >= 1 and dq.gps_quality(fast, "touringbicycle")["gps_jumps"] == 0
    assert dq.gps_quality([[48, 8, 0, None]] * 10, "hike")["gps_jumps"] is None   # ohne Zeit kein Tempo
    assert dq.gps_quality([[48, 8, 0, 0]] * 3, "hike") is None


def test_hr_quality_out_of_range_and_flat_runs():
    ok = [[i * 5, 100 + (i % 7)] for i in range(100)]
    assert dq.hr_quality(ok) == (100, 0.0)
    bad = [[i * 5, 100 + (i % 7)] for i in range(100)]
    for i in range(10):
        bad[i][1] = 250                                                      # 10 % außerhalb 30–220
    for i in range(40, 60):
        bad[i][1] = 90                                                       # 20 Messwerte (100 s) konstant ... unter 120 s: noch kein Aussetzer
    assert dq.hr_quality(bad) == (100, 10.0)
    for i in range(40, 70):
        bad[i][1] = 90                                                       # 30 Messwerte = 145 s konstant
    assert dq.hr_quality(bad) == (100, 40.0)
    assert dq.hr_quality(ok[:10]) is None


def test_height_metrics_against_formula_terrain(dem):
    pts = [[la, lo, h, i * 5000] for i, (la, lo, h, _t) in enumerate(_line(300, f=1.3))]
    st, h = dq.height_metrics(pts, {"tiles": 50})
    assert st == "ok" and h["up_dem"] > 200
    assert abs(h["up_dev"] / h["up_dem"] - 1.3) < 0.04 and abs(h["down_dev"] / h["down_dem"] - 1.3) < 0.04     # Uhr misst 30 % mehr Höhe
    st, h = dq.height_metrics([[la, lo, 1000.0, 0] for la, lo, _h_, _t in _line(300)], {"tiles": 50})
    assert st == "no_alt" and h == {}                                        # konstante Höhe = nicht gemessen
    assert dq.height_metrics(_line(10), {"tiles": 50})[0] == "no_pts"
    dem.clear()
    assert dq.height_metrics(pts, {"tiles": 0})[0] == "no_dem" and dem == []   # Kontingent 0: kein Netzabruf


# ---------------------------------------------------------------- Einschätzung
def _rows(ratios, **kw):
    return [dict({"tour_id": f"t{i}", "dist_ratio": r, "dist_plausible": int(0.5 <= r <= 2.0), "h_state": None, "gps_jumps": None, "hr_n": None}, **kw) for i, r in enumerate(ratios)]


@pytest.mark.parametrize("ratios,level,word", [
    ([1.01, 0.99, 1.02, 1.0, 0.98, 1.01], "gut", "passt zur Komoot-Strecke"),
    ([0.95, 0.96, 0.95, 0.94, 0.96, 0.95], "mäßig", "5,0 % kürzer als die Komoot-Strecke"),         # Median 0,95 = 5 %: zwischen 3 und 8
    ([0.88, 0.9, 0.9, 0.91, 0.89], "auffällig", "10,0 % kürzer"),
    ([1.12, 1.1, 1.09, 1.11, 1.1], "auffällig", "10,0 % länger"),
])
def test_dist_thresholds_and_text(ratios, level, word):
    a = dq.assess_dist(_rows(ratios), "komoot")
    assert a["level"] == level and word in a["text"] and a["n"] == len(ratios)


def test_dist_boundaries_and_min_n_and_outliers_counted_apart():
    assert dq.assess_dist(_rows([1.03] * 5), "komoot")["level"] == "gut"                  # genau 3 % noch gut
    assert dq.assess_dist(_rows([1.08] * 5), "komoot")["level"] == "mäßig"                # genau 8 % noch mäßig
    assert dq.assess_dist(_rows([1.081] * 5), "komoot")["level"] == "auffällig"
    a = dq.assess_dist(_rows([1.0, 1.0, 1.0, 1.0]), "komoot")
    assert a["n"] == 4 and a["level"] is None and a["text"] is None                       # zu wenige Touren: keine Einschätzung
    a = dq.assess_dist(_rows([1.0] * 5 + [3.0, 0.2]), "tour")
    assert a["n"] == 5 and a["n_implausible"] == 2 and a["level"] == "gut" and "gespeicherten Strecke" in a["text"]   # Ausreißer verfälschen den Median nicht
    assert dq.assess_dist(_rows([1.0, 1.0, 1.0, 1.0, 1.0, 1.2, 0.85]), "komoot").get("spread") is None
    s = dq.assess_dist(_rows([0.8, 0.8, 1.0, 1.2, 1.2, 1.0]), "komoot")
    assert "schwankt" in s["spread"]


def test_height_gps_hr_assessment_and_verdict():
    rows = [{"h_state": "ok", "up_dem": 400.0, "up_dev": 400.0 * 1.3, "down_dem": 400.0, "down_dev": 520.0} for _ in range(6)]
    h = dq.assess_height(rows)
    assert h["level"] == "auffällig" and "30,0 % höher" in h["text"] and h["up_err_m"]["median"] == 120.0
    rows = [{"h_state": "ok", "up_dem": 400.0, "up_dev": 404.0, "down_dem": 400.0, "down_dev": 396.0} for _ in range(6)]
    assert dq.assess_height(rows)["level"] == "gut"
    assert dq.assess_height([{"h_state": "ok", "up_dem": 20.0, "up_dev": 80.0, "down_dem": 20.0, "down_dev": 80.0}] * 8)["level"] is None   # unter 50 m kein Prozentwert
    g = [{"gps_jumps": 0, "gps_gap_pct": 1.0, "gps_med_dt": 5.0, "gps_src": "track", "gps_dec": 0} for _ in range(19)] + [{"gps_jumps": 2, "gps_gap_pct": 1.0, "gps_med_dt": 5.0, "gps_src": "track", "gps_dec": 0}]
    assert dq.assess_gps(g)["level"] == "gut" and dq.assess_gps(g)["jump_tours_pct"] == 5.0        # genau 5 % noch gut
    g[1]["gps_jumps"] = 1
    assert dq.assess_gps(g)["level"] == "mäßig"
    hr = [{"hr_n": 100, "hr_bad_pct": 0.0}] * 7 + [{"hr_n": 100, "hr_bad_pct": 30.0}] * 3
    assert dq.assess_hr(hr)["level"] == "auffällig" and "30 %" in dq.assess_hr(hr)["text"]
    v = dq.verdict({"dist": {"level": "gut", "text": "A."}, "height": {"level": "mäßig", "text": "B."}, "gps": {"level": None}})
    assert v["level"] == "mäßig" and v["findings"] == ["B."] and "Einschränkungen" in v["label"]
    assert dq.verdict({"dist": {"level": "gut", "text": "A."}})["label"] == "Zuverlässig"
    assert dq.verdict({"dist": {"level": None}})["level"] is None


# ---------------------------------------------------------------- Job
def _tour_state():
    return db.query("SELECT id,name,dist_m,up_m,down_m,start_ts,dur_s FROM tours ORDER BY id")


def test_job_own_tracks_measures_and_is_idempotent(dem):
    c = _client()
    d = _dev(c)
    for i in range(6):
        _local(f"z{T0 + i * 10000}", _line(300, f=1.3, jump_at=100 if i == 0 else None, gap_at=150 if i == 1 else None), dist=3000)
    before = _tour_state()
    r = dq.run(tile_max=100)
    assert r["tours"] == 6 and r["height"] == 6 and r["gps"] == 6 and r["dist"] == 0          # z-Touren: Strecke der Uhr = Tourstrecke, kein Vergleich
    rows = {x["tour_id"]: x for x in db.query("SELECT * FROM device_quality")}
    x = rows[f"z{T0}"]
    assert x["device_id"] == d and x["h_state"] == "ok" and abs(x["up_dev"] / x["up_dem"] - 1.3) < 0.04
    assert x["gps_jumps"] == 1 and rows[f"z{T0 + 10000}"]["gps_jumps"] == 0 and rows[f"z{T0 + 10000}"]["gps_gap_pct"] > 15
    assert x["gps_src"] == "track" and x["gps_dec"] == 0
    assert _tour_state() == before                                                           # Touren, Strecke und Höhe bleiben unberührt
    snap = [{k: v for k, v in y.items() if k != "berechnet_am"} for y in db.query("SELECT * FROM device_quality ORDER BY tour_id")]
    dq.run(tile_max=100)
    dq.run(tile_max=100)
    assert [{k: v for k, v in y.items() if k != "berechnet_am"} for y in db.query("SELECT * FROM device_quality ORDER BY tour_id")] == snap      # wiederholbar
    assert db.one("SELECT COUNT(*) n FROM device_quality")["n"] == 6
    assert _tour_state() == before


def test_job_removes_rows_of_deleted_tours_and_ignores_tours_without_device(dem):
    c = _client()
    _dev(c, kind="garmin", name="Garmin")                                                    # Art passt nicht zu Zepp-Touren
    _local("z1", _line(100)); _local("z2", _line(100))
    dq.run(tile_max=100)
    assert db.one("SELECT COUNT(*) n FROM device_quality")["n"] == 0                          # kein Gerät für Quelle zepp
    _dev(c)
    dq.run(tile_max=100)
    assert db.one("SELECT COUNT(*) n FROM device_quality")["n"] == 2
    db.execute("DELETE FROM tours WHERE id='z2'")
    dq.run(tile_max=100)
    assert [x["tour_id"] for x in db.query("SELECT tour_id FROM device_quality")] == ["z1"]


def test_job_zepp_distance_ratio_outliers_ambiguity_and_caps(dem):
    c = _client()
    d = _dev(c)
    hist, starts = [], []
    for i in range(8):                                                                       # Komoot-Touren mit Zepp-Training, Uhr misst 5 % weniger
        s = T0 + i * 20000
        _komoot(f"k{i}", s, 10000)
        hist.append(_summ(s, 9500))
        starts.append(s)
    _komoot("kx", T0 + 300000, 10000); hist.append(_summ(T0 + 300000, 30000))                # Verhältnis 3,0: unplausibel
    _komoot("kd", T0 + 400000, 10000); hist += [_summ(T0 + 400000, 9900), _summ(T0 + 400100, 9800)]   # zwei Trainings: mehrdeutig
    _local(f"z{T0 + 500010}", _line(200)); hist.append(_summ(T0 + 500000, 3000))             # z-Tour: nicht vergleichen
    api = _Api(hist)
    r = dq.run(api=api, detail_max=5, tile_max=500)
    assert api.details == 5                                                                  # Obergrenze für Zepp-Details
    assert r["dist"] == 8 and r["dist_implausible"] == 1 and r["zepp_ambiguous"] == 1
    rows = {x["tour_id"]: x for x in db.query("SELECT * FROM device_quality")}
    assert all(abs(rows[f"k{i}"]["dist_ratio"] - 0.95) < 1e-6 for i in range(8))
    assert rows["kx"]["dist_plausible"] == 0 and rows["kx"]["dist_ratio"] == 3.0
    assert rows["kd"]["dist_ratio"] is None and rows["kd"]["zepp_n"] == 2
    assert rows[f"z{T0 + 500010}"]["dist_ratio"] is None
    done = [x for x in rows.values() if x["h_src"] == "zepp" and x["h_state"] == "ok"]
    assert len(done) == 5 and all(abs(x["up_dev"] / x["up_dem"] - 1.3) < 0.12 and x["gps_src"] == "zepp" and x["gps_jumps"] == 0 and x["gps_med_dt"] is None for x in done)
    assert r["pending"] == 4
    r = dq.run(api=api, detail_max=5, tile_max=500)                                          # zweiter Lauf: bereits berechnete nicht erneut abrufen
    assert api.details == 5 + 4 and r["pending"] == 0
    r = dq.run(api=api, detail_max=5, tile_max=500)
    assert api.details == 9 and r["height"] == 9 + 1                                         # dritter Lauf ruft nichts mehr ab (9 Zepp-Details + 1 eigene Spur)
    a = dq.assess_dist(list(db.query("SELECT * FROM device_quality")), "komoot")
    assert a["n"] == 8 and a["n_implausible"] == 1 and a["level"] == "mäßig" and "5,0 % kürzer als die Komoot-Strecke" in a["text"]


def test_job_without_zepp_access_still_measures_local(dem):
    c = _client()
    _dev(c)
    _komoot("k1", T0, 10000)
    _local(f"z{T0 + 9000}", _line(120))
    r = dq.run(tile_max=100)                                                                 # kein api, keine Zugangsdaten
    assert r["tours"] == 2 and r["height"] == 1 and r["dist"] == 0
    assert any("Kein Zepp-Zugang" in ln for ln in jobs.snapshot()["log"])


def test_job_tile_budget_is_capped_and_resumes(dem):
    c = _client()
    _dev(c)
    for i in range(3):
        _local(f"z{T0 + i * 10000}", _line(300))
    r = dq.run(tile_max=0)
    assert dem == [] and r["height"] == 0 and r["pending"] == 3                              # nichts geladen, offen gemeldet
    assert db.one("SELECT h_state FROM device_quality")["h_state"] == "no_dem"
    r = dq.run(tile_max=10)
    assert r["height"] == 3 and 1 <= len(set(dem)) <= 10


def test_job_zepp_failure_does_not_write_secrets(dem, monkeypatch):
    c = _client()
    _dev(c)
    db.put("zepp_token", "SUPERGEHEIM-TOKEN")
    from app import sync

    def boom():
        raise RuntimeError("Anmeldung fehlgeschlagen")
    monkeypatch.setattr(sync, "_zepp_api", boom)
    _komoot("k1", T0, 10000)
    jobs.start("t", dq.run)
    import time
    for _ in range(100):
        if not jobs.get_state()["running"]:
            break
        time.sleep(0.05)
    log = "\n".join(jobs.snapshot()["log"])
    assert "SUPERGEHEIM" not in log and "nur lokale Messgrößen" in log and jobs.get_state()["ok"] is True


# ---------------------------------------------------------------- API
def _seed_api(dem):
    c = _client()
    d = _dev(c)
    for i in range(7):
        _local(f"z{T0 + i * 10000}", _line(300, f=1.4 if i < 6 else 1.0, jump_at=100 if i in (0, 1, 2) else None))
    dq.run(tile_max=200)
    return c, d


def test_api_quality_per_device_with_words_thresholds_and_channels(dem):
    c, d = _seed_api(dem)
    for i in range(3):                                                                       # Kanäle: Tempo bei 3 von 7 (43 %), Temperatur bei 1 von 7 (14 % = zu selten)
        metrics.store(f"z{T0 + i * 10000}", {"v": 1, "src": "zepp", "device": "x", "t0": T0, "t": [0, 1, 2, 3, 4, 5], "series": {"speed": [1.0] * 6, "temp": [5.0] * 6 if i == 0 else [None] * 6}})
    r = c.get("/api/devices/quality")
    assert r.status_code == 200
    j = r.json()
    dv = [x for x in j["devices"] if x["id"] == d][0]
    assert dv["n_tours"] == 7 and dv["n_eval"] == 7 and dv["period"]["from"] <= dv["period"]["to"]
    assert dv["height"]["level"] == "auffällig" and "höher als im Geländemodell" in dv["height"]["text"] and dv["height"]["n"] == 7
    assert dv["gps"]["level"] == "auffällig" and dv["gps"]["jump_tours_pct"] == round(300 / 7, 1)
    assert dv["dist"]["level"] is None and dv["dist"]["n"] == 0
    assert dv["verdict"]["level"] == "auffällig" and dv["verdict"]["label"] == "Auffällige Abweichungen" and len(dv["verdict"]["findings"]) == 2
    assert [t["kind"] for t in dv["tips"]] == ["height", "gps"]
    assert dv["flagged"] == 6
    assert [x["key"] for x in dv["channels"]] == ["speed"] and dv["channels"][0]["share"] == 43
    assert j["thresholds"]["dist"] == [3.0, 8.0] and j["min_n"] == 5 and j["zepp_configured"] is False
    assert "token" not in json.dumps(j).lower() and "passwor" not in json.dumps(j).lower()


def test_api_quality_empty_and_unknown_device():
    c = _client()
    assert c.get("/api/devices/quality").json()["devices"] == []
    d = _dev(c)
    dv = c.get("/api/devices/quality").json()["devices"][0]
    assert dv["n_eval"] == 0 and dv["verdict"]["level"] is None and dv["channels"] == [] and dv["period"] is None
    assert c.get(f"/api/devices/{d}/quality/tours").json()["tours"] == []
    assert c.get("/api/devices/999/quality/tours").status_code == 404


def test_api_flagged_tours_with_suggestions_and_existing_actions(dem):
    c, d = _seed_api(dem)
    r = c.get(f"/api/devices/{d}/quality/tours").json()
    assert r["total"] == 6 and r["device"]["id"] == d                                         # 7. Tour (f=1,0, ohne Sprung) ist unauffällig
    first = r["tours"][0]
    assert first["name"].startswith("Tour z") and first["day"]
    kinds = {f["kind"] for f in first["flags"]}
    assert kinds == {"height", "gps_jumps"} or kinds == {"height"}
    acts = {s["action"]: s for s in first["suggest"]}
    assert acts["elev-dem"]["url"] == f"/api/tours/{first['id']}/elev-fix" and acts["elev-dem"]["undo"].endswith("/elev-restore")
    assert acts["elev-zepp"]["url"].endswith("/elev-zepp") and (("trackfix" in acts) == ("gps_jumps" in kinds))
    assert all(s["method"] == "POST" for s in first["suggest"] if "url" in s)
    # Vorschläge ändern nichts: Höhe der Tour bleibt, es gibt keine Korrektur
    assert db.one("SELECT up_m FROM tours WHERE id=?", (first["id"],))["up_m"] == 100 and db.one("SELECT COUNT(*) n FROM elev_fix")["n"] == 0
    assert c.get(f"/api/devices/{d}/quality/tours?limit=2").json()["tours"].__len__() == 2
    # Mehrdeutige/unplausible Strecke wird gemeldet, Strecke nicht verändert
    t = db.one("SELECT * FROM device_quality LIMIT 1")
    db.execute("UPDATE device_quality SET dist_ratio=3.0, dist_plausible=0, dist_dev_m=30000, dist_tour_m=10000 WHERE tour_id=?", (t["tour_id"],))
    fl = [x for x in c.get(f"/api/devices/{d}/quality/tours").json()["tours"] if x["id"] == t["tour_id"]][0]
    assert fl["flags"][0]["kind"] == "dist_implausible" and any(s["action"] == "info" for s in fl["suggest"])
    assert db.one("SELECT dist_m FROM tours WHERE id=?", (t["tour_id"],))["dist_m"] == 3000


def test_corrected_tours_disappear_from_the_list_and_return_after_undo(dem):
    c, d = _seed_api(dem)
    tid = f"z{T0}"
    vorher = c.get(f"/api/devices/{d}/quality/tours").json()
    assert any(x["id"] == tid and any(f["kind"] == "height" for f in x["flags"]) for x in vorher["tours"])
    flagged0 = [x for x in c.get("/api/devices/quality").json()["devices"] if x["id"] == d][0]["flagged"]
    # Höhenkorrektur durchgeführt: die Höhen-Auffälligkeit gilt als erledigt, ohne neue Auswertung
    db.execute("INSERT INTO elev_fix(id,orig_up,orig_down,up_m,down_m,ts,src) VALUES(?,?,?,?,?,1,NULL)", (tid, 100, 100, 50, 50))
    nach = c.get(f"/api/devices/{d}/quality/tours").json()
    mine = [x for x in nach["tours"] if x["id"] == tid]
    assert not mine or all(f["kind"] != "height" for f in mine[0]["flags"])
    # GPS-Track bereinigt: Sprünge/Lücken ebenfalls erledigt -> die Tour ist (bis auf Strecke/Puls) nicht mehr aufgelistet
    db.execute("INSERT INTO track_fix(id,orig_dist,orig_dur,dist,dur,removed,excluded,ts) VALUES(?,?,?,?,?,1,0,1)", (tid, 3000, 100, 3000, 100))
    nach2 = c.get(f"/api/devices/{d}/quality/tours").json()
    mine2 = [x for x in nach2["tours"] if x["id"] == tid]
    assert not mine2 or all(f["kind"] not in ("height", "gps_jumps", "gps_gaps") for f in mine2[0]["flags"])
    assert nach2["total"] < vorher["total"] or not mine2
    flagged1 = [x for x in c.get("/api/devices/quality").json()["devices"] if x["id"] == d][0]["flagged"]
    assert flagged1 < flagged0
    # Korrektur zurückgenommen: die Tour erscheint wieder
    db.execute("DELETE FROM elev_fix WHERE id=?", (tid,)); db.execute("DELETE FROM track_fix WHERE id=?", (tid,))
    wieder = c.get(f"/api/devices/{d}/quality/tours").json()
    assert any(x["id"] == tid for x in wieder["tours"]) and wieder["total"] == vorher["total"]


def test_reassigning_tours_moves_them_to_the_new_device(dem):
    c, d = _seed_api(dem)
    d2 = _dev(c, name="Zweite", kind="zepp", since="2099-01-01")
    for i in range(7):
        c.post(f"/api/tours/z{T0 + i * 10000}/device", json={"device_id": d2})
    j = {x["id"]: x for x in c.get("/api/devices/quality").json()["devices"]}
    assert j[d]["n_eval"] == 0 and j[d2]["n_eval"] == 7                                       # ohne neuen Lauf zählt die aktuelle Zuordnung


# ---------------------------------------------------------------- Rechte
def test_viewer_may_read_but_not_start(dem):
    from fastapi.testclient import TestClient
    from app import main
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        did = c.post("/api/devices", json={"name": "Uhr", "kind": "zepp"}).json()["id"]
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert v.get("/api/devices/quality").status_code == 200
        assert v.get(f"/api/devices/{did}/quality/tours").status_code == 200
        assert v.post("/api/jobs/dev-quality").status_code == 403
        assert v.post(f"/api/tours/x/elev-fix").status_code == 403 and v.post("/api/tours/x/elev-zepp").status_code == 403
        assert TestClient(main.app).get("/api/devices/quality").status_code in (401, 403)      # ohne Anmeldung nicht
        assert c.post("/api/jobs/dev-quality").status_code == 200                              # Eigentümer darf starten
        import time
        for _ in range(100):
            if not jobs.get_state()["running"]:
                break
            time.sleep(0.05)


# ---------------------------------------------------------------- Backup und Umzug
def test_device_quality_in_backup_and_umzug_package(dem, tmp_path):
    c, d = _seed_api(dem)
    name, data = extras.make_backup()
    z = zipfile.ZipFile(io.BytesIO(data))
    p = tmp_path / "b.sqlite"
    p.write_bytes(z.read("komoot_hub.sqlite"))
    con = sqlite3.connect(p)
    assert con.execute("SELECT COUNT(*) FROM device_quality").fetchone()[0] == 7
    assert con.execute("SELECT up_dev FROM device_quality WHERE tour_id=?", (f"z{T0}",)).fetchone()[0] > 0
    con.close()
    out = umzug.make(config.DATA_DIR, tmp_path / "out", "t")
    n = umzug.restore(out, tmp_path / "neu")
    assert n > 0
    dbs = list((tmp_path / "neu").rglob("*.sqlite"))
    assert dbs
    found = 0
    for f in dbs:
        con = sqlite3.connect(f)
        try:
            found += con.execute("SELECT COUNT(*) FROM device_quality").fetchone()[0]
        except sqlite3.Error:
            pass
        con.close()
    assert found == 7


def test_table_creation_is_additive_and_never_dropped():
    src = (Path(__file__).resolve().parent.parent / "app" / "devquality.py").read_text(encoding="utf8") + (Path(__file__).resolve().parent.parent / "app" / "db.py").read_text(encoding="utf8")
    assert "DROP TABLE" not in src.upper()
    db.execute("INSERT INTO device_quality(tour_id,device_id) VALUES('a',1)")
    db.close_all(); db.init()                                                                 # erneutes Öffnen (Migration) behält Zeilen
    assert db.one("SELECT COUNT(*) n FROM device_quality")["n"] == 1
