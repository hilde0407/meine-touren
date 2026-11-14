"""3.12.0 – Belastung und Erholung, Job „Uhr-Daten aller Touren laden“, Ermüdungsverlauf, Tempo nach Steigung, Zeitschätzung.
ALLE Daten sind konstruiert (Zusatzdateien und Strecken mit bekannten Werten); es gibt hier keine echten Zepp-Antworten oder echten Strecken.
Die Deutung von exercise_load und kilo_pace ist eine ANNAHME aus 3.11.0 (siehe app/uhrtraining.py)."""
import io
import json
import math
import sys
import time
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from tests.test_messwerte import _client  # noqa: E402
from tests.test_uhrtraining import Api, T0, summary, tour, use, kilo, _reset  # noqa: F401,E402
from app import belastung as B, config, db, extras, routes, steigung as S, umzug, uhrtraining as ut, sync  # noqa: E402
from app.gpxtools import TZ  # noqa: E402

SECRET = "GEHEIMES-ZEPP-TOKEN-4711"
M = 111194.9                                  # Meter je Breitengrad (zur Haversine-Formel passend)


def lt(y, m, d, h=12, mi=0):
    base = datetime(y, m, 1, h, mi, tzinfo=TZ)
    return int((base + timedelta(days=d - 1)).timestamp())          # d darf über das Monatsende hinausgehen


def mk(tid, ts, kind="zepp", dist=5000, dur=3600, sport="hike", name=None):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,100,100,'t','komoot')",
               (tid, name or f"Tour {tid}", sport, ts, ts + dur, dist, dur))
    db.execute("INSERT OR REPLACE INTO tour_source(tour_id,src,name) VALUES(?,?,'')", (tid, kind))


def side(tid, load, detail=True, **kw):
    s = {"trackid": tid.lstrip("z"), "dis": "5000", "run_time": "3600", "exercise_load": str(load)}
    s.update(kw)
    ut.store(tid, {"v": 1, "geladen": 1, "summary": s, "detail": detail, "kilo_pace": None})


def wk(res, key):
    return next(b for b in res["wochen"] if b["key"] == key)


# ============================================================================================ A) Belastung
def test_weeks_and_months_boundaries_and_missing_not_zero():
    # Mo 2026-03-02 .. So 2026-03-08 ist eine Woche (Ortszeit). So 23:30 gehört noch zur alten, Mo 00:30 zur neuen Woche.
    mk("a1", lt(2026, 3, 1, 23, 30), "zepp"); side("a1", 50)               # Sonntag davor (KW 9)
    mk("a2", lt(2026, 3, 2, 0, 30), "zepp"); side("a2", 80)                # Montag (KW 10)
    mk("a3", lt(2026, 3, 8, 23, 59), "zepp"); side("a3", 20)               # Sonntag (KW 10)
    mk("a4", lt(2026, 3, 5), "garmin")                                     # ohne Uhr-Daten
    mk("a5", lt(2026, 3, 9, 8), "zepp"); side("a5", 30)                    # KW 11
    mk("a6", lt(2026, 3, 11), "garmin")                                    # KW 11, nur ohne Angabe
    mk("a7", lt(2026, 3, 31, 23, 50), "zepp"); side("a7", 40)              # März
    mk("a8", lt(2026, 4, 1, 0, 10), "zepp"); side("a8", 60)                # April
    r = B.compute("2026-02-23", "2026-04-12", now=datetime(2026, 4, 12, tzinfo=TZ))
    keys = [b["key"] for b in r["wochen"]]
    assert keys[0] == "2026-02-23" and keys[-1] == "2026-04-06" and len(keys) == 7                   # lückenlos, Montage
    assert wk(r, "2026-02-23")["belastung"] == 50 and wk(r, "2026-02-23")["touren"] == 1
    w = wk(r, "2026-03-02")
    assert w["belastung"] == 100 and w["touren"] == 3 and w["mit_daten"] == 2 and w["ohne_angabe"] == 1 and w["von"] == "2026-03-02" and w["bis"] == "2026-03-08"
    w = wk(r, "2026-03-09")
    assert w["belastung"] == 30 and w["touren"] == 2 and w["ohne_angabe"] == 1                       # Tour ohne Uhr-Wert zählt nicht als 0
    assert wk(r, "2026-03-16")["touren"] == 0 and wk(r, "2026-03-16")["belastung"] is None            # keine Tour: nichts
    m = {b["key"]: b for b in r["monate"]}
    assert m["2026-03"]["belastung"] == 50 + 80 + 20 + 30 + 40 and m["2026-03"]["touren"] == 7 and m["2026-04"]["belastung"] == 60
    assert m["2026-02"]["touren"] == 0 or m["2026-02"]["belastung"] is None
    g = r["gesamt"]
    assert g["touren"] == 8 and g["mit_daten"] == 6 and g["anteil_pct"] == 75 and g["belastung"] == 280
    assert wk(r, "2026-03-30")["belastung"] == 40 + 60                                                  # 31.3. (Di) und 1.4. (Mi) liegen in derselben Woche


def test_week_without_any_value_is_none_not_zero_and_placeholders_ignored():
    mk("b1", lt(2026, 5, 4), "garmin")
    mk("b2", lt(2026, 5, 5), "zepp"); side("b2", -1)                          # Platzhalter
    mk("b3", lt(2026, 5, 6), "zepp"); side("b3", 0)                           # 0 = keine Angabe
    mk("b4", lt(2026, 5, 7), "zepp"); side("b4", "abc")
    r = B.compute()
    assert len(r["wochen"]) == 1 and r["wochen"][0]["belastung"] is None and r["wochen"][0]["touren"] == 4 and r["wochen"][0]["ohne_angabe"] == 4
    assert r["gesamt"]["mit_daten"] == 0 and r["gesamt"]["anteil_pct"] == 0 and r["gesamt"]["belastung"] is None
    assert r["haertest_wochen"] == [] and r["haertest_touren"] == [] and "null" not in json.dumps(r["haertest_touren"])


def test_top_five_weeks_and_tours_and_range_filter():
    for i in range(7):
        mk(f"c{i}", lt(2026, 1, 5 + 7 * i), "zepp", name=f"Runde {i}"); side(f"c{i}", 100 + i * 10)
    mk("c9", lt(2026, 1, 6), "zepp", name="Zweite"); side("c9", 100)
    r = B.compute()
    assert [t["belastung"] for t in r["haertest_touren"]] == [160, 150, 140, 130, 120] and r["haertest_touren"][0]["name"] == "Runde 6"
    assert [b["belastung"] for b in r["haertest_wochen"]] == [200, 160, 150, 140, 130] and r["haertest_wochen"][0]["von"] == "2026-01-05"      # Woche mit zwei Touren ist die härteste
    assert wk(r, "2026-01-05")["belastung"] == 200                                                      # Woche mit zwei Touren
    r2 = B.compute("2026-01-12", "2026-01-25")
    assert [b["key"] for b in r2["wochen"]] == ["2026-01-12", "2026-01-19"] and r2["gesamt"]["touren"] == 2
    assert B.compute("2030-01-01", "2030-02-01")["wochen"] == []                                        # leerer Zeitraum: keine Balken


def _rows(now, base, recent):
    """Eine Tour je 7-Tage-Block: base = Werte der 12 Blöcke davor (None = Tour ohne Wert, "-" = keine Tour), recent = Werte der letzten 4 Blöcke."""
    rows = []
    for i, v in enumerate(recent):
        if v != "-":
            rows.append({"ts": now.timestamp() - (i * 7 + 3) * 86400, "v": v})
    for i, v in enumerate(base):
        if v != "-":
            rows.append({"ts": now.timestamp() - ((i + 4) * 7 + 3) * 86400, "v": v})
    return rows


NOW = datetime(2026, 11, 14, 12, tzinfo=TZ)


@pytest.mark.parametrize("recent,stufe", [(100, "aehnlich"), (114, "aehnlich"), (115, "mehr"), (139, "mehr"), (140, "deutlich_mehr"), (200, "deutlich_mehr"),
                                          (86, "aehnlich"), (85, "weniger"), (61, "weniger"), (60, "deutlich_weniger"), (10, "deutlich_weniger")])
def test_current_comparison_thresholds_15_and_40_percent(recent, stufe):
    a = B.aktuell(_rows(NOW, [100] * 12, [recent] * 4), NOW)
    assert a["status"] == "ok" and a["stufe"] == stufe and a["basis_schnitt"] == 100 and a["aktuell_schnitt"] == recent and a["abweichung_pct"] == recent - 100


def test_current_comparison_needs_eight_weeks_with_data():
    assert B.aktuell(_rows(NOW, [100] * 7 + [None] * 5, [100] * 4), NOW)["status"] == "zu_wenig_daten"
    assert B.aktuell(_rows(NOW, [100] * 7 + ["-"] * 5, [100] * 4), NOW)["status"] == "zu_wenig_daten"
    a = B.aktuell(_rows(NOW, [100] * 8 + [None] * 4, [100] * 4), NOW)
    assert a["status"] == "ok" and a["basis_schnitt"] == 100 and a["stufe"] == "aehnlich"            # Wochen mit Touren ohne Uhr-Wert verwässern nicht (ohne Angabe, nicht 0)
    a = B.aktuell(_rows(NOW, [100] * 8 + ["-"] * 4, [100] * 4), NOW)                                    # Wochen ganz ohne Tour sind ruhig = 0 (so dokumentiert)
    assert a["basis_schnitt"] == round(800 / 12)
    a = B.aktuell(_rows(NOW, [100] * 12, [None, None, None, None]), NOW)
    assert a["status"] == "keine_aktuellen_daten" and a["stufe"] is None
    a = B.aktuell(_rows(NOW, [100] * 12, [None, 120, None, None]), NOW)
    assert a["status"] == "ok" and a["aktuell_schnitt"] == 120 and a["wochen_mit_daten_aktuell"] == 1
    assert B.aktuell([], NOW)["status"] == "zu_wenig_daten"


def test_api_belastung_end_to_end_and_hint(monkeypatch):
    c = _client()
    r = c.get("/api/stats/belastung").json()
    assert r["wochen"] == [] and r["gesamt"]["touren"] == 0 and r["gesamt"]["anteil_pct"] is None and r["aktuell"]["status"] == "zu_wenig_daten"
    assert r["hinweis"] == "Zepp-Werte werden beim ersten Öffnen einer Tour gespeichert." and r["offen"] == {"zepp_ohne_werte": 0, "job": "uhr-alle"}
    mk("z1", lt(2026, 6, 1), "zepp"); mk("z2", lt(2026, 6, 2), "zepp"); side("z2", 33)
    r = c.get("/api/stats/belastung").json()
    assert r["offen"]["zepp_ohne_werte"] == 1 and r["gesamt"]["mit_daten"] == 1
    assert c.get("/api/stats/belastung?von=2026-13-45").status_code == 400
    assert c.get("/api/stats/belastung?von=morgen").status_code == 400
    assert c.get("/api/stats/belastung?von=2026-06-10&bis=2026-06-01").status_code == 400
    assert not any(ut.sidecar(t).exists() for t in ("z1",))                                   # rein lesend: keine Zusatzdatei entstanden
    assert c.get("/api/stats/belastung?von=2026-06-01&bis=2026-06-30").status_code == 200


def test_belastung_never_calls_zepp(monkeypatch):
    called = []
    monkeypatch.setattr(sync, "_zepp_api", lambda: called.append(1) or (_ for _ in ()).throw(RuntimeError("x")))
    mk("z1", lt(2026, 6, 1), "zepp")
    assert _client().get("/api/stats/belastung").status_code == 200 and not called


# ============================================================================================ A) Job
def world_job(monkeypatch, n=3, skip=(), **kw):
    hist = []
    for i in range(n):
        st = T0 + i * 86400 + 10
        tour(f"z{st}", st)
        if i not in skip:
            hist.append(summary(st, exercise_load=str(90 + i), **kw))
    api = use(monkeypatch, Api(hist))
    return _client(), api, [f"z{T0 + i * 86400 + 10}" for i in range(n)]


def test_job_writes_summary_sidecars_without_detail_calls_and_is_idempotent(monkeypatch):
    c, api, ids = world_job(monkeypatch)
    r = ut.load_all()
    assert r["status"] == "ok" and r["neu"] == 3 and api.h_calls == 1 and api.d_calls == 0                 # ein Verlauf, KEIN Detail
    for i, t in enumerate(ids):
        d = ut.load(t)
        assert d["detail"] is False and d["detail_offen"] is True and d["kilo_pace"] is None and d["summary"]["exercise_load"] == str(90 + i)
        assert "source" not in d["summary"] and "lat_start" not in d["summary"]                         # wie sonst: nur ausgewählte Felder
    before = {t: ut.sidecar(t).read_bytes() for t in ids}
    r2 = ut.load_all()
    assert r2["neu"] == 0 and r2["schon_da"] == 3 and {t: ut.sidecar(t).read_bytes() for t in ids} == before and api.d_calls == 0


def test_job_never_overwrites_sidecar_that_has_detail(monkeypatch):
    c, api, ids = world_job(monkeypatch, n=2)
    ut.store(ids[0], {"v": 1, "geladen": 5, "summary": summary(T0 + 10, calorie="111"), "detail": True, "kilo_pace": kilo()})
    keep = ut.sidecar(ids[0]).read_bytes()
    r = ut.load_all()
    assert r["neu"] == 1 and ut.sidecar(ids[0]).read_bytes() == keep                                       # vorhandene (mit Kilometerwerten) bleibt Byte für Byte
    assert ut.load(ids[0])["detail"] is True and ut.load(ids[0])["kilo_pace"] == kilo()


def test_job_detail_is_fetched_on_open_and_failed_reload_keeps_splits(monkeypatch):
    c, api, ids = world_job(monkeypatch, n=1)
    ut.load_all()
    t = ids[0]
    ut.reset_cache()
    d = c.get(f"/api/tours/{t}/uhr-training").json()                                                       # Öffnen holt die Kilometerwerte nach
    assert api.d_calls == 1 and d["splits"] and len(d["splits"]) == 6 and ut.load(t)["detail"] is True and ut.load(t)["detail_offen"] is False
    api.fail_detail = True
    d2 = c.post(f"/api/tours/{t}/uhr-training/neu").json()                                                 # Detail schlägt fehl: vorhandene Splits bleiben
    assert d2["status"] == "ok" and d2["splits"] and len(d2["splits"]) == 6
    assert ut.load(t)["detail"] is True and ut.load(t)["kilo_pace"] == kilo() and SECRET not in json.dumps(ut.load(t))


def test_job_failed_detail_on_open_is_not_retried_on_every_view(monkeypatch):
    c, api, ids = world_job(monkeypatch, n=1)
    ut.load_all()
    api.fail_detail = True
    c.get(f"/api/tours/{ids[0]}/uhr-training")
    n = api.d_calls
    d = c.get(f"/api/tours/{ids[0]}/uhr-training").json()
    c.get(f"/api/tours/{ids[0]}/uhr-training")
    assert api.d_calls == n == 1 and d["splits"] is None and any("Kilometerwerte" in h for h in d["hinweise"])     # einmal versucht, danach nur „Von Zepp neu laden“


def run_job(c, name="uhr-alle"):
    from app import jobs
    assert c.post("/api/jobs/" + name).status_code == 200
    for _ in range(200):
        if not jobs.get_state()["running"] and jobs.get_state()["finished"]:
            break
        time.sleep(0.05)
    time.sleep(0.1)


def test_job_hint_for_open_detail_and_viewer_does_not_fetch(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    st = T0 + 10
    tour(f"z{st}", st)
    api = use(monkeypatch, Api([summary(st)]))
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        run_job(c)
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        j = v.get(f"/api/tours/z{st}/uhr-training").json()
        assert j["status"] == "ok" and j["werte"]["last"]["wert"] == 96 and api.d_calls == 0 and j["splits"] is None
        assert "Die Kilometerwerte werden beim ersten Öffnen der Tour von Zepp geladen." in j["hinweise"]
        assert v.post("/api/jobs/uhr-alle").status_code == 403 and v.get("/api/stats/belastung").status_code == 200
        assert c.post("/api/jobs/uhr-alle").status_code == 200


def test_job_cap_dry_run_ambiguous_and_non_zepp(monkeypatch):
    c, api, ids = world_job(monkeypatch, n=4, skip=(3,))
    tour("g1", T0 + 99 * 86400, kind="garmin")
    assert ut.load_all(dry=True)["neu"] == 3 and not any(ut.sidecar(t).exists() for t in ids)               # Probelauf schreibt nichts
    r = ut.load_all(max_new=2)
    assert r["neu"] == 2 and r["obergrenze"] is True and sum(ut.sidecar(t).exists() for t in ids) == 2
    r = ut.load_all(max_new=2)
    assert r["neu"] == 1 and r["obergrenze"] is False and not ut.sidecar("g1").exists() and not ut.sidecar(ids[3]).exists()    # Garmin und „kein Training“: nichts
    assert r["ohne_training"] == 1
    st = T0 + 500 * 86400 + 10                                                                              # zwei Trainings passen zu einer Tour: nichts speichern
    tour(f"x{st}", st)
    db.execute("INSERT OR REPLACE INTO tour_source(tour_id,src,name) VALUES(?,?,'')", (f"x{st}", "zepp"))
    api.hist += [summary(st + 5), summary(st + 9)]
    ut.reset_cache()
    r = ut.load_all()
    assert r["mehrdeutig"] == 1 and not ut.sidecar(f"x{st}").exists()


def test_job_via_api_logs_without_secrets(monkeypatch):
    c, api, ids = world_job(monkeypatch, n=2)
    from app import jobs
    assert c.post("/api/jobs/uhr-alle").status_code == 200
    for _ in range(100):
        if not jobs.get_state()["running"]:
            break
        time.sleep(0.05)
    log = "\n".join(jobs.snapshot()["log"])
    assert "Uhr-Daten aller Touren laden" in log and "2 Touren wurden gespeichert" in log and all(ut.sidecar(t).exists() for t in ids)
    assert SECRET not in log


def test_job_error_message_has_no_credentials(monkeypatch):
    tour("z1", T0 + 10)

    def boom():
        raise ValueError("Antwort mit " + SECRET)
    monkeypatch.setattr(sync, "_zepp_api", boom)
    from app import jobs
    c = _client()
    assert c.post("/api/jobs/uhr-alle").status_code == 200
    for _ in range(100):
        if not jobs.get_state()["running"]:
            break
        time.sleep(0.05)
    log = "\n".join(jobs.snapshot()["log"])
    assert SECRET not in log and "Zepp ist gerade nicht erreichbar" in log


def test_job_sidecars_in_backup_and_umzug(tmp_path, monkeypatch):
    c, api, ids = world_job(monkeypatch, n=2)
    ut.load_all()
    z = zipfile.ZipFile(io.BytesIO(extras.make_backup()[1]))
    assert all(f"tracks/{t}.uhr.json" in z.namelist() for t in ids)
    out = umzug.make(config.DATA_DIR, tmp_path / "out", "t")
    names = zipfile.ZipFile(out).namelist()
    assert all(any(n.endswith(f"tracks/{t}.uhr.json") for n in names) for t in ids)
    umzug.restore(out, tmp_path / "neu")
    assert all(json.loads((tmp_path / "neu" / "tracks" / f"{t}.uhr.json").read_text(encoding="utf-8"))["detail_offen"] is True for t in ids)


# ============================================================================================ B) Ermüdung
def sp(secs, puls=None, partial=None):
    out = [{"km": i + 1, "sek": s, "min_km": round(s / 60, 2), "puls": (puls[i] if puls else None), "schritte": None, "strecke_m": 1000} for i, s in enumerate(secs)]
    if partial:
        out.append({"km": len(secs) + 1, "sek": partial, "min_km": 9, "puls": None, "schritte": None, "strecke_m": 400})
    return out


def test_fatigue_known_splits_known_percent():
    r = ut.ermuedung(sp([600] * 4 + [630] * 4, puls=[120] * 4 + [130] * 4))
    assert r["status"] == "ok" and r["km"] == 8 and r["tempo_pct"] == 5 and r["puls_diff"] == 10 and r["stufe"] == "leicht_langsamer" and r["puls"] == "steigt"
    r = ut.ermuedung(sp([600] * 3 + [570] * 3))
    assert r["tempo_pct"] == -5 and r["stufe"] == "schneller" and r["puls_diff"] is None and r["puls"] is None                 # ohne Puls nur Tempo
    assert ut.ermuedung(sp([600] * 6))["stufe"] == "gleichmaessig" and ut.ermuedung(sp([600] * 6))["tempo_pct"] == 0
    assert ut.ermuedung(sp([600] * 4 + [660] * 4))["stufe"] == "spuerbar_langsamer"                                           # +10 %
    assert ut.ermuedung(sp([600] * 4 + [720] * 4))["stufe"] == "deutlich_langsamer"                                           # +20 %
    assert ut.ermuedung(sp([600] * 4 + [618] * 4))["stufe"] == "leicht_langsamer" and ut.ermuedung(sp([600] * 4 + [614] * 4))["stufe"] == "gleichmaessig"
    assert ut.ermuedung(sp([600] * 3 + [600] * 3, puls=[120] * 3 + [116] * 3))["puls"] == "gleich"


def test_fatigue_ignores_partial_km_and_odd_middle_and_needs_six_full_km():
    r = ut.ermuedung(sp([600] * 3 + [600] * 3, partial=1500))                                                                   # Teilkilometer langsam: ohne Einfluss
    assert r["tempo_pct"] == 0 and r["km"] == 6
    r = ut.ermuedung(sp([600, 600, 600, 9999 // 3, 600, 600, 660][:7]))                                                         # 7 km: Mittelstück (km 4) bleibt außen vor
    assert r["k"] == 3 and r["tempo_pct"] == round((((600 + 600 + 660) / 3) / 600 - 1) * 100)
    assert ut.ermuedung(sp([600] * 5, partial=500)) is None and ut.ermuedung(sp([600] * 5)) is None and ut.ermuedung(None) is None and ut.ermuedung([]) is None
    assert ut.ermuedung(sp([600] * 6)) is not None
    some = sp([600] * 4 + [630] * 4, puls=[120, None, None, None, 130, 130, 130, 130])                                          # erste Hälfte < 60 % Puls: nur Tempo
    assert ut.ermuedung(some)["puls_diff"] is None and ut.ermuedung(some)["tempo_pct"] == 5


def test_fatigue_slope_hint_instead_of_judgement():
    hs = {"erste": {"auf": 20, "ab": 20}, "zweite": {"auf": 25, "ab": 15}}
    r = ut.ermuedung(sp([600] * 4 + [700] * 4), hs)
    assert r["status"] == "ok" and r["hoehen_geprueft"] is True and r["tempo_pct"] == 17
    hs = {"erste": {"auf": 10, "ab": 250}, "zweite": {"auf": 260, "ab": 20}}
    r = ut.ermuedung(sp([600] * 4 + [700] * 4), hs)
    assert r["status"] == "nur_hinweis" and r["tempo_pct"] is None and r["stufe"] is None and r["puls_diff"] is None and r["hoehen"] == hs
    assert ut.ermuedung(sp([600] * 8), {"erste": {"auf": 100, "ab": 100}, "zweite": {"auf": 130, "ab": 90}})["status"] == "ok"      # Unterschied unter 2x bzw. 40 m
    assert ut.ermuedung(sp([600] * 8), {"erste": {"auf": 30, "ab": 0}, "zweite": {"auf": 60, "ab": 0}})["status"] == "ok"          # 2x, aber nur 30 m
    assert ut.ermuedung(sp([600] * 8), {"erste": {"auf": 0, "ab": 0}, "zweite": {"auf": 40, "ab": 0}})["status"] == "nur_hinweis"  # flach gegen 40 m
    assert ut.ermuedung(sp([600] * 8), None)["hoehen_geprueft"] is False                                                           # ohne Höhendaten: Werte, aber ungeprüft


def track(segs, step=5.0, pause_at=None, pause_s=0, alt0=1000.0, with_alt=True, with_time=True):
    """Streckenpunkte [lat, lng, Höhe, t_ms] nach Abschnitten (Länge m, Steigung, Tempo km/h) – nach Norden, 5-m-Takt."""
    y, alt, t = 0.0, alt0, 0.0
    pts = [[48.0, 11.0, alt if with_alt else None, 0 if with_time else None]]
    for L, sl, v in segs:
        for _ in range(int(L / step)):
            y += step; alt += sl * step; t += step / (v / 3.6)
            pts.append([48.0 + y / M, 11.0, alt if with_alt else None, int(t * 1000) if with_time else None])
        if pause_at == L and pause_s:
            for _k in range(10):
                t += pause_s / 10
                pts.append([48.0 + y / M, 11.0, alt if with_alt else None, int(t * 1000)])
    return pts


STD = [(2000, 0, 5), (1000, .10, 3), (1000, 0, 5), (1000, -.10, 6)]


def test_fatigue_integration_halves_from_track(monkeypatch):
    st = T0 + 10
    tid = f"z{st}"
    tour(tid, st, dist=8000, dur=5000)
    routes.store(tid, [tuple(p) for p in track([(4000, 0, 5), (4000, .10, 5)])])                                              # zweite Hälfte nur bergauf
    kp = ";".join(f"{i},{600 if i < 4 else 700},0,0,{120 if i < 4 else 135},0,0,300,0,56,0,0,0,40" for i in range(8))
    use(monkeypatch, Api([summary(st, dis="8000", run_time="5000", heart_range="")], kp=kp))
    d = _client().get(f"/api/tours/{tid}/uhr-training").json()
    e = d["ermuedung"]
    assert e["status"] == "nur_hinweis" and e["tempo_pct"] is None and e["hoehen"]["erste"]["auf"] < 15 and e["hoehen"]["zweite"]["auf"] > 300
    ut.reset_cache()
    routes.store(tid, [tuple(p) for p in track([(8000, 0, 5)])])                                                              # überall flach
    ut.forget(tid)
    e = _client().get(f"/api/tours/{tid}/uhr-training").json()["ermuedung"]
    assert e["status"] == "ok" and e["tempo_pct"] == 17 and e["puls_diff"] == 15 and e["hoehen_geprueft"] is True
    routes.store(tid, [(la, lo, None, t) for la, lo, _a, t in track([(8000, 0, 5)])])                                         # Strecke ohne Höhe
    ut.forget(tid); ut.reset_cache()
    e = _client().get(f"/api/tours/{tid}/uhr-training").json()["ermuedung"]
    assert e["status"] == "ok" and e["hoehen_geprueft"] is False and e["tempo_pct"] == 17
    ut.forget(tid); ut.reset_cache()
    use(monkeypatch, Api([summary(st, dis="8000", run_time="5000", heart_range="")], kp=";".join(kp.split(";")[:5])))
    assert _client().get(f"/api/tours/{tid}/uhr-training").json()["ermuedung"] is None                                       # unter 6 km: keine Wertung


# ============================================================================================ C) Tempo nach Steigung
def close(a, b, tol=0.04):
    return abs(a - b) <= tol * abs(b)


def test_slope_classes_known_speeds():
    r = S.compute(track(STD))
    assert r["status"] == "ok"
    k = r["klassen"]
    assert close(k["auf"]["kmh"], 3.0) and close(k["eben"]["kmh"], 5.0) and close(k["ab"]["kmh"], 6.0)
    assert close(k["auf"]["dist_m"], 1000, .06) and close(k["eben"]["dist_m"], 3000, .03) and close(k["ab"]["dist_m"], 1000, .06)
    assert close(r["vert_mh"], 0.10 * 3000, .05)                                                                              # 10 % bei 3 km/h = 300 m/h
    assert close(r["up_m"], 100, .06) and close(r["down_m"], 100, .06)
    assert close(r["e_up"], (1200 - 720) / 100, .08)                                                                           # (Zeit − Zeit eben) / Höhenmeter


def test_slope_threshold_five_percent():
    r = S.compute(track([(2000, 0.04, 4), (2000, 0.06, 4)]))                                                                  # 4 % = eben, 6 % = bergauf
    k = r["klassen"]
    assert close(k["eben"]["dist_m"], 2000, .05) and close(k["auf"]["dist_m"], 2000, .05) and k["ab"] is None
    assert close(r["vert_mh"], 0.06 * 4000, .05)
    r = S.compute(track([(2000, -0.04, 4), (2000, -0.06, 4)]))
    assert r["klassen"]["auf"] is None and close(r["klassen"]["ab"]["dist_m"], 2000, .05) and r["vert_mh"] is None


def test_slope_pauses_are_removed():
    a = S.compute(track(STD))
    b = S.compute(track(STD, pause_at=2000, pause_s=900))                                                                    # 15 min Pause auf der ebenen Strecke
    c = S.compute(track(STD, pause_at=1000, pause_s=1800))
    assert a["klassen"] == b["klassen"] and b["zeit_s"] == a["zeit_s"] and a["vert_mh"] == b["vert_mh"] and a["klassen"]["eben"]["kmh"] == c["klassen"]["eben"]["kmh"]
    slow = S.compute(track([(2000, 0, 5), (1000, 0, 0.35), (2000, 0, 5)]))                                                   # 0,35 km/h ist keine Pause
    assert slow["status"] == "ok" and slow["klassen"]["eben"]["kmh"] < 4.5
    gap = S.compute(track([(2000, 0, 5), (1000, 0, 0.25), (2000, 0, 5)]))                                                     # 0,25 km/h = Pause: zählt nicht
    assert close(gap["klassen"]["eben"]["kmh"], 5.0, .02)


def test_slope_small_classes_not_reported_and_missing_data():
    r = S.compute(track([(4000, 0, 5), (200, .10, 3)]))                                                                       # 200 m bergauf: zu wenig für eine Aussage
    assert r["klassen"]["auf"] is None and r["vert_mh"] is None and r["e_up"] is None and r["klassen"]["eben"]["kmh"] > 0
    assert S.compute(track([(1500, 0, 5)]))["status"] == "zu_kurz"
    assert S.compute(track(STD, with_alt=False))["status"] == "keine_hoehe"
    assert S.compute(track(STD, with_time=False))["status"] == "keine_hoehe"
    assert S.compute([])["status"] == "zu_kurz" and S.compute(None)["status"] == "zu_kurz"
    bad = track(STD)
    for p in bad[::2]:
        p[2] = -2004831                                                                                                       # Zepp-Platzhalter: keine Höhe
    assert S.compute(bad)["status"] == "keine_hoehe"
    for p in bad[1::3]:
        p[2] = 1000.0
    r = S.compute(track([(4000, 0, 5)]))
    assert r["klassen"]["auf"] is None and r["klassen"]["ab"] is None and r["vert_mh"] is None                                # nur eben: Rest ist „keine Angabe“, nie 0
    text = json.dumps(r)
    assert '"vert_mh": null' in json.dumps(r) or "null" in text


def test_slope_flat_noise_does_not_create_climbs():
    import random
    rnd = random.Random(4)
    pts = track([(4000, 0, 5)])
    for p in pts:
        p[2] += rnd.uniform(-1.5, 1.5)                                                                                        # GPS-Höhenrauschen ±1,5 m
    r = S.compute(pts)
    assert r["klassen"]["eben"]["dist_m"] > 3800 and (r["klassen"]["auf"] is None or r["klassen"]["auf"]["dist_m"] < 200)


def test_estimate_duration_basics_and_edge_cases():
    assert S.estimate_duration(0, 0, 0) == 0
    assert S.estimate_duration(10000, 600, 0) == pytest.approx(7200 + 3600)                                                    # Naismith: 5 km/h + 1 h je 600 m
    p = {"eben_kmh": 4.0, "e_up": 8.0, "e_down": 1.0}
    assert S.estimate_duration(8000, 500, 500, p) == pytest.approx(7200 + 4000 + 500)
    for bad in (-1, float("nan"), float("inf"), "x", None, 3_000_000):
        with pytest.raises(ValueError):
            S.estimate_duration(bad, 0, 0)
    with pytest.raises(ValueError):
        S.estimate_duration(1000, -5, 0)
    with pytest.raises(ValueError):
        S.estimate_duration(1000, 0, 200_000)
    assert S.estimate_duration(1000, 0, 0, {"eben_kmh": 0}) == pytest.approx(1000 / (1.0 / 3.6))                              # unsinniges Profil wird gekappt, nicht geteilt durch 0
    assert S.estimate_duration(1000, 100, 0, {"e_up": -5}) == S.estimate_duration(1000, 0, 0)                                  # Aufstieg macht nie schneller
    assert S.estimate_duration(1000, 100, 0, {"eben_kmh": "kaputt", "e_up": None}) == S.estimate_duration(1000, 100, 0)       # ungültige Einträge: Standard


def test_estimate_duration_is_monotonic():
    profiles = [None, {"eben_kmh": 3.5, "e_up": 9, "e_down": 0.5}, {"eben_kmh": 6, "e_up": 3, "e_down": 0}, {"eben_kmh": 5, "e_up": 4.8, "e_down": -1.2}]
    for p in profiles:
        prev = -1
        for d in range(0, 40001, 2000):
            v = S.estimate_duration(d, 300, 300, p); assert v >= prev; prev = v
        prev = -1
        for u in range(0, 2001, 100):
            v = S.estimate_duration(10000, u, 300, p); assert v >= prev; prev = v
        prev = -1
        for dn in range(0, 2001, 100):
            v = S.estimate_duration(10000, 300, dn, p); assert v >= prev; prev = v
        assert S.estimate_duration(10000, 800, 800, p) > S.estimate_duration(10000, 0, 0, p)


def test_estimate_reproduces_constructed_track():
    r = S.compute(track(STD))
    prof = {"eben_kmh": r["klassen"]["eben"]["kmh"], "e_up": r["e_up"], "e_down": r["e_down"]}
    est = S.estimate_duration(r["dist_m"], r["up_m"], r["down_m"], prof)
    assert close(est, r["zeit_s"], 0.10)                                                                                      # e_down < 0 wird auf 0 gekappt: etwas langsamer als gemessen, aber nah dran


def _tempo_tours(n, sport="hike", base="t", speeds=(5, 3, 6)):
    for i in range(n):
        tid = f"{base}{i}"
        mk(tid, lt(2025, 5, 1 + i), "garmin", dist=5000, sport=sport)
        routes.store(tid, [tuple(p) for p in track([(2000, 0, speeds[0] + i * .1), (1000, .10, speeds[1]), (1000, 0, speeds[0]), (1000, -.10, speeds[2])])])


def test_stats_median_by_sport_and_year_filter():
    _tempo_tours(5)                                                                                                           # Wandern, 2025
    _tempo_tours(3, sport="jogging", base="j", speeds=(10, 6, 12))
    mk("k1", lt(2024, 6, 1), "garmin", dist=5000, sport="hike")
    routes.store("k1", [tuple(p) for p in track([(2000, 0, 4), (1000, .10, 2), (1000, 0, 4), (1000, -.10, 5)])])              # 2024, langsamer
    mk("r1", lt(2025, 7, 1), "garmin", dist=5000, sport="touringbicycle")
    routes.store("r1", [tuple(p) for p in track(STD)])                                                                         # Radtour: nicht dabei
    mk("kurz", lt(2025, 7, 2), "garmin", dist=1500, sport="hike")
    routes.store("kurz", [tuple(p) for p in track([(1500, 0, 5)])])                                                            # unter 2 km: nicht dabei
    mk("oh", lt(2025, 7, 3), "garmin", dist=5000, sport="hike")                                                                # ohne Strecke
    c = _client()
    r = c.get("/api/stats/tempo").json()
    w, l = r["gruppen"]["wandern"], r["gruppen"]["laufen"]
    assert w["touren"] == 6 and l["touren"] == 3 and r["offen"] == 0 and r["jahre"] == [2025, 2024]
    assert close(l["eben_kmh"], 10.0, .05) and close(l["auf_kmh"], 6.0, .05) and close(l["ab_kmh"], 12.0, .05) and close(l["vert_mh"], 600, .06)
    r25 = c.get("/api/stats/tempo?jahr=2025").json()["gruppen"]["wandern"]
    r24 = c.get("/api/stats/tempo?jahr=2024").json()["gruppen"]["wandern"]
    assert r25["touren"] == 5 and close(r25["eben_kmh"], 5.2, .05) and r24["touren"] == 1 and close(r24["eben_kmh"], 4.0, .05)       # Median 5,2 bei 5,0/5,1/5,2/5,3/5,4
    assert r24["n_eben_kmh"] == 1 and c.get("/api/stats/tempo?jahr=3000").status_code == 400
    assert c.get("/api/stats/tempo?jahr=2023").json()["gruppen"]["wandern"] == {"touren": 0, **{k: None for k in ("auf_kmh", "eben_kmh", "ab_kmh", "vert_mh", "e_up", "e_down")},
                                                                               **{"n_" + k: 0 for k in ("auf_kmh", "eben_kmh", "ab_kmh", "vert_mh", "e_up", "e_down")}}


def test_gehzeit_api_own_values_or_standard():
    c = _client()
    r = c.get("/api/stats/gehzeit?km=10&auf=600&ab=600").json()
    assert r["quelle"] == "standard" and r["sekunden"] == round(10000 / (5 / 3.6) + 600 * 6) and r["touren"] == 0                    # Naismith, wenn nichts da ist
    _tempo_tours(4)
    r = c.get("/api/stats/gehzeit?km=10&auf=600&ab=600").json()
    assert r["quelle"] in ("eigene", "teilweise") and r["touren"] == 4 and r["profil"]["eben_kmh"] > 4.5 and r["sekunden"] > 0
    assert c.get("/api/stats/gehzeit?km=10&auf=800&ab=600").json()["sekunden"] > r["sekunden"]
    assert c.get("/api/stats/gehzeit?km=20&auf=600&ab=600").json()["sekunden"] > r["sekunden"]
    assert c.get("/api/stats/gehzeit?km=10&sport=laufen").json()["quelle"] == "standard"                                              # Laufen: keine eigenen Läufe
    for q in ("km=-1", "km=abc", "km=nan", "km=10&auf=-3", "km=10&sport=ski", "km=5000", "km=10&ab=1e9"):
        assert c.get("/api/stats/gehzeit?" + q).status_code in (400, 422), q
    assert c.get("/api/stats/gehzeit").status_code == 422


# ---------------------------------------------------------------- Zwischenspeicher
def test_cache_computes_once_and_invalidates_when_track_changes(monkeypatch):
    mk("t1", lt(2025, 5, 1), "garmin", sport="hike")
    routes.store("t1", [tuple(p) for p in track(STD)])
    n = []
    orig = S.compute
    monkeypatch.setattr(S, "compute", lambda pts: n.append(1) or orig(pts))
    a = S.tempo_of("t1")
    assert a["status"] == "ok" and len(n) == 1 and S.cache_path("t1").exists()
    for _ in range(3):
        assert S.tempo_of("t1") == a
    assert len(n) == 1                                                                                                          # aus dem Zwischenspeicher
    assert S.tempo_of("t1", allow_compute=False) == a
    time.sleep(0.02)
    routes.store("t1", [tuple(p) for p in track([(2000, 0, 4), (1000, .10, 2), (1000, 0, 4), (1000, -.10, 5)])])               # Strecke/Höhe korrigiert
    b = S.tempo_of("t1", allow_compute=False)
    assert b is None                                                                                                            # ungültig geworden
    b = S.tempo_of("t1")
    assert len(n) == 2 and b["klassen"]["eben"]["kmh"] < a["klassen"]["eben"]["kmh"]
    S.cache_path("t1").write_text("{kaputt", encoding="utf-8")
    assert S.tempo_of("t1")["status"] == "ok" and len(n) == 3                                                                   # beschädigter Zwischenspeicher: neu rechnen
    monkeypatch.setattr(S, "ALGO", S.ALGO + 1)
    assert S.tempo_of("t1", allow_compute=False) is None                                                                         # neue Rechenvorschrift: alles ungültig
    assert S.tempo_of("zzz") == {"status": "keine_strecke"}


def test_cache_invalidated_by_local_gpx_change(monkeypatch):
    from app import tracks
    mk("t2", lt(2025, 5, 1), "garmin", sport="hike")
    txt = lambda segs: tracks.gpx_for_points("t2", segs) if hasattr(tracks, "gpx_for_points") else None
    config.TRACK_DIR.mkdir(parents=True, exist_ok=True)

    def gpx(pts):
        body = "".join(f'<trkpt lat="{p[0]:.6f}" lon="{p[1]:.6f}"><ele>{p[2]:.1f}</ele><time>{datetime.fromtimestamp(1750000000 + p[3] / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}</time></trkpt>' for p in pts)
        return f'<?xml version="1.0"?><gpx version="1.1" creator="t"><trk><trkseg>{body}</trkseg></trk></gpx>'
    g = tracks.gpx_file("t2")
    g.write_text(gpx(track(STD)), encoding="utf-8")
    a = S.tempo_of("t2")
    assert a["status"] == "ok" and close(a["klassen"]["eben"]["kmh"], 5.0, .05)
    time.sleep(0.02)
    g.write_text(gpx(track([(2000, 0, 4), (1000, .10, 2), (1000, 0, 4), (1000, -.10, 5)])), encoding="utf-8")
    b = S.tempo_of("t2")
    assert close(b["klassen"]["eben"]["kmh"], 4.0, .06)


def test_tempo_cache_not_a_second_source_of_truth_for_backup(monkeypatch):
    mk("t3", lt(2025, 5, 1), "garmin", sport="hike")
    routes.store("t3", [tuple(p) for p in track(STD)])
    S.tempo_of("t3")
    z = zipfile.ZipFile(io.BytesIO(extras.make_backup()[1]))
    assert not any("tempo" in n for n in z.namelist())                                                                         # abgeleitet, baut sich neu auf: nicht in der Sicherung


def test_tour_tempo_endpoint_and_budget(monkeypatch):
    mk("t4", lt(2025, 5, 1), "garmin", sport="hike")
    routes.store("t4", [tuple(p) for p in track(STD)])
    mk("t5", lt(2025, 5, 2), "garmin", sport="hike")
    c = _client()
    j = c.get("/api/tours/t4/tempo").json()
    assert j["status"] == "ok" and close(j["klassen"]["auf"]["kmh"], 3.0) and close(j["vert_mh"], 300, .05)
    assert c.get("/api/tours/t5/tempo").json() == {"status": "keine_strecke"} and c.get("/api/tours/gibtsnicht/tempo").status_code == 404
    for i in range(4):
        mk(f"b{i}", lt(2025, 6, 1 + i), "garmin", sport="hike")
        routes.store(f"b{i}", [tuple(p) for p in track(STD)])
    r = S.stats(budget_s=0)                                                                                                    # Zeitbudget leer: nichts berechnet, Rest „offen“
    assert r["offen"] == 4 and r["gruppen"]["wandern"]["touren"] == 1                                                          # t4 war schon im Zwischenspeicher
    r = S.stats()
    assert r["offen"] == 0 and r["gruppen"]["wandern"]["touren"] == 5


def test_viewer_can_read_new_endpoints_but_not_start_job(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    st = T0 + 10
    tour(f"z{st}", st)
    use(monkeypatch, Api([summary(st, exercise_load="70")]))
    routes.store(f"z{st}", [tuple(p) for p in track(STD)])
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        run_job(c)
        v = TestClient(main.app)
        assert v.get("/api/stats/belastung").status_code in (401, 403)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert v.get("/api/stats/belastung").json()["gesamt"]["belastung"] == 70
        assert v.get("/api/stats/tempo").status_code == 200 and v.get("/api/stats/gehzeit?km=5&auf=100&ab=100").status_code == 200
        assert v.get(f"/api/tours/z{st}/tempo").json()["status"] == "ok"
        assert v.post("/api/jobs/uhr-alle").status_code == 403
        assert TestClient(main.app).get("/api/stats/tempo").status_code in (401, 403)


def test_new_scripts_and_version():
    from app import config as cfg
    assert cfg.VERSION == "3.15.0 · Meine Touren (2026-11-14)"           # 3.13.0 baut auf 3.12.0 auf: beide Versionshinweise müssen vorhanden sein
    for v in ("3.12.0", "3.13.0", "3.14.0", "3.15.0"):
        assert (Path(__file__).resolve().parent.parent / "docs" / "versionen" / f"{v}.md").exists()
