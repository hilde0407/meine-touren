"""3.13.0 – Höhe aus der Uhr-Zusammenfassung (grob), Sammel-Korrektur der Höhen (Vorschau, Job, Obergrenzen, Rückgängig), Fortschritt (done/total), Rechte, Backup/Umzug.
Alle Daten sind konstruiert: Gelände = Formel (kein Netz), Zepp-Verlauf/-Detail nachgebaut. Nichts davon belegt das Verhalten gegen eine echte Zepp-Antwort."""
import io
import json
import sqlite3
import sys
import time
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from tests.test_geraetequalitaet import dem, _line, _local, _komoot, _dev, _h, _summ, _Api, T0  # noqa: F401,E402
from tests.test_messwerte import _client  # noqa: E402
from app import config, db, devbatch, devquality as dq, elev, extras, jobs, routes, sync, umzug, uhrtraining  # noqa: E402


def _wait():
    for _ in range(600):
        if not jobs.get_state()["running"]:
            return
        time.sleep(0.05)
    raise AssertionError("Job läuft zu lange")


def _route(tid, pts):
    routes.store(tid, [(la, lo, el, (t - pts[0][3]) * 1000) for la, lo, el, t in pts])


def _uhr(tid, up, down, dis="3000"):
    """Zusatzdatei wie sie der Job „Uhr-Daten aller Touren laden“ schreibt (nur Zusammenfassung)."""
    uhrtraining.store(tid, {"v": 1, "geladen": T0, "summary": {"trackid": "1", "dis": dis, "run_time": "1500", "altitude_ascend": up, "altitude_descend": down},
                            "detail": False, "detail_offen": True, "kilo_pace": None})


def _ref(pts):
    """Auf-/Abstieg des (formelhaften) Geländes entlang der Punkte – so wie die Auswertung ihn rechnet."""
    st, h = dq.height_metrics([[la, lo, el, i * 5000] for i, (la, lo, el, _t) in enumerate(pts)], {"tiles": 500})
    assert st == "ok"
    return h


# ---------------------------------------------------------------- Höhe aus der Zusammenfassung
def test_summary_height_is_second_source_and_ignores_unusable_values(dem):
    c = _client()
    _dev(c)
    pts = _line(300, f=1.0)
    ref = _ref(pts)
    cases = {"k0": (ref["up_dem"] * 1.5, ref["down_dem"] * 1.5),        # brauchbar, Uhr meldet 50 % mehr
             "k1": (-1, -274), "k2": (0, 0), "k3": (0, 50), "k4": (5000, 5000),     # Platzhalter / beides 0 / nur Aufstieg 0 / über 300 m je km (3 km Strecke)
             "k5": ("abc", None), "k6": (-2004831, -2004831)}
    for i, (tid, (up, down)) in enumerate(cases.items()):
        _komoot(tid, T0 + i * 20000, 3000)
        _route(tid, pts)
        _uhr(tid, up, down)
    _komoot("k_ohne", T0 + 900000, 3000)                                # ohne Zusatzdatei: keine Höhe
    _route("k_ohne", pts)
    r = dq.run(tile_max=500)                                            # ohne Zepp-Zugang: die gespeicherte Zusammenfassung genügt
    rows = {x["tour_id"]: x for x in db.query("SELECT * FROM device_quality")}
    ok = rows["k0"]
    assert ok["h_src"] == "summary" and ok["h_state"] == "ok"
    assert ok["up_dev"] == round(ref["up_dem"] * 1.5) and ok["down_dev"] == round(ref["down_dem"] * 1.5) and abs(ok["up_dem"] - ref["up_dem"]) < 0.11
    for k in ("k1", "k2", "k3", "k4", "k5", "k6", "k_ohne"):
        assert rows[k]["h_src"] is None and rows[k]["h_state"] is None and rows[k]["up_dev"] is None, k
    assert r["height_summary"] == 1 and r["height"] == 0 and r["pending"] == 0
    assert any("grob aus der Zusammenfassung" in ln for ln in jobs.snapshot()["log"])


def test_summary_needs_route_points_and_waits_for_tiles(dem):
    c = _client()
    _dev(c)
    pts = _line(300)
    ref = _ref(pts)
    _komoot("a", T0, 3000); _uhr("a", ref["up_dem"] * 2, ref["down_dem"] * 2)               # keine Strecke gespeichert
    _komoot("b", T0 + 20000, 3000); _route("b", pts); _uhr("b", ref["up_dem"] * 2, ref["down_dem"] * 2)
    r = dq.run(tile_max=0)                                                                   # Kontingent 0: kein Netzabruf
    rows = {x["tour_id"]: x for x in db.query("SELECT * FROM device_quality")}
    assert rows["a"]["h_src"] is None and rows["b"]["h_src"] == "summary" and rows["b"]["h_state"] == "no_dem" and r["pending"] == 1
    r = dq.run(tile_max=50)
    assert db.one("SELECT h_state FROM device_quality WHERE tour_id='b'")["h_state"] == "ok" and r["pending"] == 0


def test_detail_has_priority_and_summary_tours_are_fetched_last(dem):
    c = _client()
    _dev(c)
    pts = _line(300)
    ref = _ref(pts)
    hist = []
    for i in range(6):                                                  # 6 Touren mit Zusammenfassung (Uhr meldet 50 % mehr) …
        tid, s = f"k{i}", T0 + i * 20000
        _komoot(tid, s, 3000); _route(tid, pts); _uhr(tid, ref["up_dem"] * 1.5, ref["down_dem"] * 1.5); hist.append(_summ(s, 3000))
    for i in range(2):                                                  # … und 2 ohne: für die ist das Detail der einzige Weg
        tid, s = f"n{i}", T0 + 500000 + i * 20000
        _komoot(tid, s, 3000); _route(tid, pts); hist.append(_summ(s, 3000))
    api = _Api(hist, f=1.3)
    r = dq.run(api=api, detail_max=2, tile_max=500)
    rows = {x["tour_id"]: x for x in db.query("SELECT * FROM device_quality")}
    assert api.details == 2 and {k for k, x in rows.items() if x["h_src"] == "zepp"} == {"n0", "n1"}      # Touren ohne Höhenwert zuerst
    assert all(rows[f"k{i}"]["h_src"] == "summary" for i in range(6))
    assert r["height_summary"] == 6 and r["height"] == 2 and r["pending"] == 0
    r = dq.run(api=api, detail_max=0, tile_max=500)                    # 0 Abrufe: trotzdem eine (grobe) Höhe, nichts wird abgerufen
    assert api.details == 2 and dq.assess_height(list(db.query("SELECT * FROM device_quality")))["n_summary"] == 6
    r = dq.run(api=api, detail_max=6, tile_max=500)                    # Detail für die Zusammenfassungs-Touren: das Detail ersetzt die grobe Zahl
    rows = {x["tour_id"]: x for x in db.query("SELECT * FROM device_quality")}
    assert api.details == 8 and all(x["h_src"] == "zepp" and x["h_state"] == "ok" for x in rows.values())
    assert all(abs(x["up_dev"] / x["up_dem"] - 1.3) < 0.12 for x in rows.values())
    r = dq.run(api=None, detail_max=6, tile_max=500)                    # später ohne Zepp-Zugang: Detail bleibt Detail (wird nicht durch die Zusammenfassung ersetzt)
    assert api.details == 8 and {x["h_src"] for x in db.query("SELECT h_src FROM device_quality")} == {"zepp"}


def _hrow(src, up_dev, **kw):
    return dict({"tour_id": "x", "h_state": "ok", "h_src": src, "up_dem": 400.0, "up_dev": up_dev, "down_dem": 400.0, "down_dev": up_dev, "dist_plausible": None,
                 "dist_ratio": None, "gps_jumps": None, "gps_gap_pct": None, "hr_bad_pct": None, "hr_n": None}, **kw)


def test_assessment_keeps_exact_and_rough_apart_with_own_thresholds():
    rows = [_hrow("zepp", 520.0)] * 6 + [_hrow("summary", 520.0)] * 6               # beide 30 % zu hoch
    a = dq.assess_height(rows)
    assert a["level"] == "auffällig" and a["rough"] is False and a["n_detail"] == 6 and a["n_summary"] == 6 and a["n"] == 6      # genau: >25 % = auffällig
    assert a["summary"]["level"] == "mäßig" and a["summary"]["n"] == 6                                                          # grob: 15–35 % = mäßig
    only = dq.assess_height([_hrow("summary", 520.0)] * 6)
    assert only["rough"] is True and only["level"] == "mäßig" and only["text"].startswith("Grob, nur aus der Zusammenfassung der Uhr:") and only["n_detail"] == 0 and only["n_summary"] == 6
    assert dq.assess_height([_hrow("summary", 448.0)] * 6)["level"] == "gut"                                                    # 12 %: grob noch gut …
    assert dq.assess_height([_hrow("zepp", 448.0)] * 6)["level"] == "mäßig"                                                     # … genau schon mäßig
    few = dq.assess_height([_hrow("zepp", 400.0)] * 3 + [_hrow("summary", 400.0)] * 3)
    assert few["level"] is None and few["rough"] is False                                                                       # 3 + 3 werden NICHT zusammengezählt
    v = dq.verdict({"height": only})
    assert v["level"] == "mäßig" and "Grob" in v["findings"][0]


def test_flags_use_stricter_limits_for_rough_values():
    assert not [f for f in dq.tour_flags(_hrow("summary", 520.0)) if f["kind"] == "height"]            # 30 % / 120 m: grob nicht auffällig
    f = [f for f in dq.tour_flags(_hrow("summary", 600.0)) if f["kind"] == "height"]                   # 50 % / 200 m
    assert f and f[0]["rough"] is True
    g = [f for f in dq.tour_flags(_hrow("zepp", 520.0)) if f["kind"] == "height"]
    assert g and "rough" not in g[0]
    assert not [f for f in dq.tour_flags(_hrow("summary", 440.0, up_dem=400.0)) if f["kind"] == "height"]


# ---------------------------------------------------------------- Fortschritt
def test_job_reports_done_and_total_and_payload_keeps_the_state(dem):
    c = _client()
    d = _dev(c)
    for i in range(4):
        _local(f"z{T0 + i * 10000}", _line(300))
    jobs.start("t", lambda: dq.run(tile_max=0))                          # keine Kacheln: alle 4 bleiben offen
    _wait()
    st = jobs.snapshot()
    assert st["total"] == 4 and st["done"] == 0 and st["ok"] is True
    p = [x for x in c.get("/api/devices/quality").json()["devices"] if x["id"] == d][0]["progress"]
    assert p["total"] == 4 and p["done"] == 0 and p["open"] == 4
    jobs.start("t", lambda: dq.run(tile_max=100))                        # „Weiter auswerten“
    _wait()
    st = jobs.snapshot()
    assert st["total"] == 4 and st["done"] == 4
    _komoot("k_neu", T0 + 900000, 3000)                                   # neue Tour mit Zuordnung, noch ohne Zeile: offen
    j = c.get("/api/devices/quality").json()                              # (frischer Abruf = nach dem Neuladen der Seite)
    p = [x for x in j["devices"] if x["id"] == d][0]["progress"]
    assert (p["total"], p["done"], p["open"]) == (5, 4, 1) and j["progress"]["total"] == 5 and j["progress"]["open"] == 1 and j["computed_at"]
    assert p["n_detail"] == 4 and p["n_summary"] == 0


def test_legacy_progress_calls_keep_working_and_new_job_resets_numbers():
    jobs.start("a", lambda: jobs.progress("nur Text"))
    _wait()
    s = jobs.snapshot()
    assert s["progress"] == "nur Text" and s["done"] is None and s["total"] is None
    jobs.start("b", lambda: jobs.progress("x", 3, 10))
    _wait()
    assert (jobs.snapshot()["done"], jobs.snapshot()["total"]) == (3, 10)
    jobs.start("c", lambda: None)
    _wait()
    assert jobs.snapshot()["done"] is None


def test_summary_rows_count_as_checked_not_open(dem):
    c = _client()
    d = _dev(c)
    pts = _line(300)
    ref = _ref(pts)
    for i in range(3):
        _komoot(f"k{i}", T0 + i * 20000, 3000); _route(f"k{i}", pts); _uhr(f"k{i}", ref["up_dem"], ref["down_dem"])
    dq.run(tile_max=500)
    dv = [x for x in c.get("/api/devices/quality").json()["devices"] if x["id"] == d][0]
    assert dv["progress"] == {"total": 3, "done": 3, "open": 0, "n_detail": 0, "n_summary": 3}
    assert dv["height"]["n_summary"] == 3 and dv["height"]["n_detail"] == 0


# ---------------------------------------------------------------- Sammel-Korrektur
def _seed(dem, n=6, f=1.4):
    c = _client()
    d = _dev(c)
    for i in range(n):
        tid = f"z{T0 + i * 10000}"
        pts = _line(300, f=f)
        _local(tid, pts); _route(tid, pts)
    dq.run(tile_max=200)
    return c, d


def _fix(tid):
    """Einzelkorrektur wie der Knopf auf der Tourseite (elev.fix), mit der nachgebauten Geländefunktion statt Netz."""
    return elev.fix(tid, tile=dq._tile_factory({"tiles": 50}))


def _state():
    return ([(t["id"], t["up_m"], t["down_m"], t["dist_m"], t["dur_s"], t["start_ts"]) for t in db.query("SELECT * FROM tours ORDER BY id")],
            db.one("SELECT COUNT(*) n FROM elev_fix")["n"], db.one("SELECT COUNT(*) n FROM quality_batch")["n"])


def test_preview_changes_nothing_and_lists_only_open_height_tours(dem):
    c, d = _seed(dem)
    before, calls = _state(), len(dem)
    r = c.get(f"/api/devices/{d}/quality/fix-preview").json()
    assert r["total"] == 6 and [m["id"] for m in r["methods"]] == ["dem"] and r["cap"] == 100 and r["zepp_missing"] is True
    t = r["tours"][0]
    assert t["up_now"] == 100 and t["up_dev"] > t["up_dem"] * 1.3 and t["new"]["dem"] == t["up_dem"] and t["new"]["zepp"] == t["up_dev"] and t["rough"] is False
    assert _state() == before and len(dem) == calls                      # nichts geändert, kein Kachelabruf
    assert c.get("/api/devices/999/quality/fix-preview").status_code == 404
    db.put("zepp_token", "GEHEIM"); r2 = c.get(f"/api/devices/{d}/quality/fix-preview").json()
    assert [m["id"] for m in r2["methods"]] == ["dem", "zepp"] and r2["zepp_missing"] is False
    g = c.post("/api/devices", json={"name": "Garmin", "kind": "garmin"}).json()["id"]            # Art passt nicht: Uhr-Methode nur bei Zepp
    assert [m["id"] for m in c.get(f"/api/devices/{g}/quality/fix-preview").json()["methods"]] == ["dem"]
    assert "GEHEIM" not in json.dumps(r2)
    # eine bereits (einzeln) korrigierte Tour ist nicht mehr dabei
    _fix(t["id"])
    assert c.get(f"/api/devices/{d}/quality/fix-preview").json()["total"] == 5


def test_batch_dem_only_selected_tours_with_originals_log_and_no_route_change(dem):
    c, d = _seed(dem)
    ids = [t["id"] for t in c.get(f"/api/devices/{d}/quality/fix-preview").json()["tours"]]
    pick = ids[:3]
    before = {t["id"]: t for t in db.query("SELECT * FROM tours")}
    r = c.post(f"/api/devices/{d}/quality/fix", json={"method": "dem", "tours": pick + ["gibt-es-nicht"]})
    assert r.status_code == 200 and r.json()["n"] == 3 and r.json()["ignored"] == 1
    _wait()
    assert jobs.get_state()["ok"] is True
    assert {x["id"] for x in db.query("SELECT id FROM elev_fix")} == set(pick)
    prev = {t["id"]: t for t in c.get(f"/api/devices/{d}/quality/tours?limit=50").json()["tours"]}
    assert set(prev) == set(ids) - set(pick)                                                     # korrigierte Touren verschwinden aus „Auffällige Touren“
    for tid in pick:
        t = db.one("SELECT * FROM tours WHERE id=?", (tid,))
        q = db.one("SELECT up_dem FROM device_quality WHERE tour_id=?", (tid,))
        assert abs(t["up_m"] - q["up_dem"]) < 0.11 and t["up_m"] != 100                          # Höhe = Geländemodell
        assert elev.orig_path(tid).exists() and db.one("SELECT orig_up FROM elev_fix WHERE id=?", (tid,))["orig_up"] == 100       # Original bleibt
        assert (t["dist_m"], t["dur_s"], t["start_ts"]) == (before[tid]["dist_m"], before[tid]["dur_s"], before[tid]["start_ts"])  # Strecke/Zeit unberührt
    for tid in set(ids) - set(pick):
        assert db.one("SELECT up_m FROM tours WHERE id=?", (tid,))["up_m"] == 100
    b = db.query("SELECT * FROM quality_batch")
    assert len(b) == 3 and {x["state"] for x in b} == {"done"} and {x["method"] for x in b} == {"dem"} and {x["device_id"] for x in b} == {d} and len({x["batch_id"] for x in b}) == 1
    assert all(x["orig_up"] == 100 and x["new_up"] > 0 for x in b)
    log = "\n".join(jobs.snapshot()["log"])
    assert "Korrigiert: 3 Touren" in log and "Korrigiert: z" in log
    dv = [x for x in c.get("/api/devices/quality").json()["devices"] if x["id"] == d][0]
    assert dv["batch"]["n_done"] == 3 and dv["batch"]["method"] == "dem" and dv["flagged_height"] == 3
    st = jobs.snapshot()
    assert st["total"] == 3 and st["done"] == 3                                                  # Fortschritt der Sammel-Korrektur
    # idempotent: dieselbe Auswahl noch einmal ergibt nichts mehr zu tun
    assert c.post(f"/api/devices/{d}/quality/fix", json={"method": "dem", "tours": pick}).status_code == 400
    # die Rückmeldung für den Rest: erneuter Start nimmt nur noch die offenen
    r = c.post(f"/api/devices/{d}/quality/fix", json={"method": "dem", "tours": ids})
    assert r.json()["n"] == 3 and r.json()["ignored"] == 3
    _wait()
    assert db.one("SELECT COUNT(*) n FROM elev_fix")["n"] == 6 and len({x["batch_id"] for x in db.query("SELECT batch_id FROM quality_batch")}) == 2


def test_batch_caps_per_run_and_resumes(dem):
    c, d = _seed(dem)
    db.put("quality_batch_max", "2")
    ids = [t["id"] for t in c.get(f"/api/devices/{d}/quality/fix-preview").json()["tours"]]
    r = c.post(f"/api/devices/{d}/quality/fix", json={"method": "dem", "tours": ids}).json()
    assert r["n"] == 6 and r["will_run"] == 2 and r["cap"] == 2
    _wait()
    assert db.one("SELECT COUNT(*) n FROM elev_fix")["n"] == 2
    assert any("4 weitere folgen beim nächsten Start" in ln for ln in jobs.snapshot()["log"])
    c.post(f"/api/devices/{d}/quality/fix", json={"method": "dem", "tours": ids}); _wait()
    c.post(f"/api/devices/{d}/quality/fix", json={"method": "dem", "tours": ids}); _wait()
    assert db.one("SELECT COUNT(*) n FROM elev_fix")["n"] == 6                                    # nach drei Läufen alles erledigt, nichts doppelt
    assert c.get(f"/api/devices/{d}/quality/fix-preview").json()["total"] == 0


def test_batch_tile_budget_is_respected_and_resumes(dem):
    c, d = _seed(dem)
    ids = [t["id"] for t in c.get(f"/api/devices/{d}/quality/fix-preview").json()["tours"]]
    db.put("quality_tile_max", "0")
    n0 = len(dem)
    c.post(f"/api/devices/{d}/quality/fix", json={"method": "dem", "tours": ids}); _wait()
    assert len(dem) == n0 and jobs.get_state()["ok"] is True                                      # kein Kachelabruf
    assert db.one("SELECT COUNT(*) n FROM elev_fix")["n"] == 0 and db.one("SELECT COUNT(*) n FROM quality_batch")["n"] == 0
    assert any("Geländekacheln fehlen" in ln for ln in jobs.snapshot()["log"])
    db.put("quality_tile_max", "20")                                                              # wiederholbar: jetzt geht es
    c.post(f"/api/devices/{d}/quality/fix", json={"method": "dem", "tours": ids}); _wait()
    assert db.one("SELECT COUNT(*) n FROM elev_fix")["n"] == 6 and 1 <= len(set(dem[n0:])) <= 20


def test_batch_aborts_cleanly_after_repeated_failures_and_can_be_repeated(dem, monkeypatch):
    c, d = _seed(dem)
    ids = [t["id"] for t in c.get(f"/api/devices/{d}/quality/fix-preview").json()["tours"]]
    real = elev.fix
    monkeypatch.setattr(elev, "fix", lambda tid, tile=None: (_ for _ in ()).throw(RuntimeError("Netz weg")))
    c.post(f"/api/devices/{d}/quality/fix", json={"method": "dem", "tours": ids}); _wait()
    log = "\n".join(jobs.snapshot()["log"])
    assert jobs.get_state()["ok"] is True and "5 Fehler in Folge" in log and "sauber abgebrochen" in log
    assert db.one("SELECT COUNT(*) n FROM elev_fix")["n"] == 0 and db.one("SELECT COUNT(*) n FROM quality_batch")["n"] == 0
    monkeypatch.setattr(elev, "fix", real)
    c.post(f"/api/devices/{d}/quality/fix", json={"method": "dem", "tours": ids}); _wait()
    assert db.one("SELECT COUNT(*) n FROM elev_fix")["n"] == 6


def _zdetail(n=300, step=0.00009, dt=5, f=1.4):
    la0 = 48.0
    lats = [la0 + step * i for i in range(n)]
    ll = [f"{int(la0 * 1e8)},{int(8.0 * 1e8)}"] + [f"{int(step * 1e8)},0"] * (n - 1)
    return {"longitude_latitude": ";".join(ll), "time": ";".join(["0"] + [str(dt)] * (n - 1)), "altitude": ";".join(str(int(_h(la, 8.0, f) * 100)) for la in lats), "heart_rate": "", "gait": ""}


class _ZApi:
    def __init__(self, hist):
        self.hist, self.hist_calls, self.details = hist, 0, 0

    def history(self):
        self.hist_calls += 1
        return self.hist

    def detail(self, s):
        self.details += 1
        return _zdetail()


def test_batch_zepp_method_loads_history_once_and_never_logs_credentials(dem, monkeypatch):
    c, d = _seed(dem, n=4)
    db.put("zepp_token", "SUPERGEHEIMES-TOKEN")
    api = _ZApi([{"trackid": str(T0 + i * 10000), "type": "6", "dis": "3000", "run_time": "1500", "end_time": str(T0 + i * 10000 + 1500), "source": "run.46.huami.com"} for i in range(4)])
    monkeypatch.setattr(sync, "_zepp_api", lambda: api)
    ids = [t["id"] for t in c.get(f"/api/devices/{d}/quality/fix-preview").json()["tours"]]
    assert c.post(f"/api/devices/{d}/quality/fix", json={"method": "zepp", "tours": ids}).status_code == 200
    _wait()
    assert jobs.get_state()["ok"] is True and api.hist_calls == 1 and api.details == 4              # Verlauf nur einmal, je Tour ein Detail
    fx = db.query("SELECT * FROM elev_fix")
    assert len(fx) == 4 and {x["src"] for x in fx} == {"zepp"} and all(x["orig_up"] == 100 for x in fx)
    assert {x["method"] for x in db.query("SELECT method FROM quality_batch")} == {"zepp"}
    assert "SUPERGEHEIMES" not in "\n".join(jobs.snapshot()["log"])
    c.post(f"/api/devices/{d}/quality/fix-undo", json={"batch": db.one("SELECT batch_id b FROM quality_batch")["b"]})
    assert db.one("SELECT COUNT(*) n FROM elev_fix")["n"] == 0


def test_zepp_method_fails_cleanly_when_zepp_is_unreachable(dem, monkeypatch):
    c, d = _seed(dem, n=3)
    db.put("zepp_token", "x")

    def boom():
        raise RuntimeError("Anmeldung fehlgeschlagen")
    monkeypatch.setattr(sync, "_zepp_api", boom)
    ids = [t["id"] for t in c.get(f"/api/devices/{d}/quality/fix-preview").json()["tours"]]
    c.post(f"/api/devices/{d}/quality/fix", json={"method": "zepp", "tours": ids}); _wait()
    assert db.one("SELECT COUNT(*) n FROM elev_fix")["n"] == 0 and any("Zepp nicht erreichbar" in ln for ln in jobs.snapshot()["log"]) and jobs.get_state()["ok"] is True


def test_start_validation(dem):
    c, d = _seed(dem, n=3)
    assert c.post(f"/api/devices/{d}/quality/fix", json={"method": "zepp", "tours": ["x"]}).status_code == 400          # keine Zepp-Zugangsdaten
    assert c.post(f"/api/devices/{d}/quality/fix", json={"method": "dem", "tours": []}).status_code == 400
    assert c.post(f"/api/devices/{d}/quality/fix", json={"method": "irgendwas", "tours": ["x"]}).status_code == 400
    assert c.post("/api/devices/999/quality/fix", json={"method": "dem", "tours": ["x"]}).status_code == 404
    assert "dev-quality-fix" in __import__("app.main", fromlist=["JOBS"]).JOBS
    before = _state()
    assert c.post("/api/jobs/dev-quality-fix").status_code == 200; _wait()                                                  # von Hand ohne Anforderung: nichts
    assert _state() == before and any("keine Anforderung" in ln for ln in jobs.snapshot()["log"])


def test_undo_restores_only_this_batch_and_leaves_changed_tours_alone(dem, monkeypatch):
    c, d = _seed(dem)
    ids = [t["id"] for t in c.get(f"/api/devices/{d}/quality/fix-preview").json()["tours"]]
    manual = ids[5]
    _fix(manual)                                                                                       # Einzelkorrektur außerhalb des Laufs
    c.post(f"/api/devices/{d}/quality/fix", json={"method": "dem", "tours": ids[:3]}); _wait()
    bid = db.one("SELECT batch_id b FROM quality_batch")["b"]
    assert db.one("SELECT COUNT(*) n FROM elev_fix")["n"] == 4
    db.execute("UPDATE elev_fix SET up_m=12345 WHERE id=?", (ids[0],))                              # von Hand weitergeändert
    assert c.post(f"/api/tours/{ids[1]}/elev-restore").status_code == 200                            # von Hand zurückgenommen
    monkeypatch.setattr(jobs, "get_state", lambda: {"running": "irgendein Job"})
    assert c.post(f"/api/devices/{d}/quality/fix-undo", json={"batch": bid}).status_code == 409        # während eines Jobs nicht
    monkeypatch.undo()
    r = c.post(f"/api/devices/{d}/quality/fix-undo", json={"batch": bid})
    assert r.status_code == 200 and r.json() == {"restored": 1, "changed": 2}
    assert db.one("SELECT up_m FROM tours WHERE id=?", (ids[2],))["up_m"] == 100 and not db.one("SELECT 1 x FROM elev_fix WHERE id=?", (ids[2],)) and not elev.orig_path(ids[2]).exists()
    assert db.one("SELECT up_m FROM elev_fix WHERE id=?", (ids[0],))["up_m"] == 12345               # nicht angefasst
    assert db.one("SELECT 1 x FROM elev_fix WHERE id=?", (manual,))                                  # Korrektur außerhalb des Laufs bleibt
    assert {x["tour_id"]: x["state"] for x in db.query("SELECT * FROM quality_batch")} == {ids[0]: "gone", ids[1]: "gone", ids[2]: "undone"}
    assert c.post(f"/api/devices/{d}/quality/fix-undo", json={"batch": bid}).status_code == 404       # nichts mehr zu tun
    assert c.post(f"/api/devices/{d}/quality/fix-undo", json={"batch": "gibtsnicht"}).status_code == 404
    dv = [x for x in c.get("/api/devices/quality").json()["devices"] if x["id"] == d][0]
    assert dv["batch"]["n_done"] == 0 and dv["batch"]["n_undone"] == 3
    # zurückgenommene Tour erscheint wieder in der Liste
    assert ids[2] in [t["id"] for t in c.get(f"/api/devices/{d}/quality/tours?limit=50").json()["tours"]]


# ---------------------------------------------------------------- Rechte
def test_viewer_cannot_start_undo_or_preview(dem):
    from fastapi.testclient import TestClient
    from app import main
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        did = c.post("/api/devices", json={"name": "Uhr", "kind": "zepp"}).json()["id"]
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert v.get("/api/devices/quality").status_code == 200                                       # lesen (inkl. Fortschritt) ist erlaubt
        assert v.get(f"/api/devices/{did}/quality/fix-preview").status_code == 403
        assert v.post(f"/api/devices/{did}/quality/fix", json={"method": "dem", "tours": ["x"]}).status_code == 403
        assert v.post(f"/api/devices/{did}/quality/fix-undo", json={"batch": "x"}).status_code == 403
        assert v.post("/api/jobs/dev-quality-fix").status_code == 403
        assert TestClient(main.app).get(f"/api/devices/{did}/quality/fix-preview").status_code in (401, 403)
        assert c.get(f"/api/devices/{did}/quality/fix-preview").status_code == 200                    # Eigentümer


# ---------------------------------------------------------------- Backup und Umzug
def test_quality_batch_is_in_backup_and_umzug_and_never_dropped(dem, tmp_path):
    c, d = _seed(dem, n=4)
    ids = [t["id"] for t in c.get(f"/api/devices/{d}/quality/fix-preview").json()["tours"]]
    c.post(f"/api/devices/{d}/quality/fix", json={"method": "dem", "tours": ids}); _wait()
    assert db.one("SELECT COUNT(*) n FROM quality_batch")["n"] == 4
    name, data = extras.make_backup()
    p = tmp_path / "b.sqlite"
    p.write_bytes(zipfile.ZipFile(io.BytesIO(data)).read("komoot_hub.sqlite"))
    con = sqlite3.connect(p)
    assert con.execute("SELECT COUNT(*) FROM quality_batch WHERE state='done'").fetchone()[0] == 4
    assert con.execute("SELECT SUM(new_up) FROM quality_batch").fetchone()[0] > 0
    con.close()
    out = umzug.make(config.DATA_DIR, tmp_path / "out", "t")
    assert umzug.restore(out, tmp_path / "neu") > 0
    found = 0
    for f in (tmp_path / "neu").rglob("*.sqlite"):
        con = sqlite3.connect(f)
        try:
            found += con.execute("SELECT COUNT(*) FROM quality_batch").fetchone()[0]
        except sqlite3.Error:
            pass
        con.close()
    assert found == 4
    app = Path(__file__).resolve().parent.parent / "app"
    src = "".join((app / n).read_text(encoding="utf8") for n in ("devbatch.py", "devquality.py", "db.py"))
    assert "DROP TABLE" not in src.upper() and "CREATE TABLE IF NOT EXISTS quality_batch" in src
    db.close_all(); db.init()                                                                         # erneutes Öffnen (Migration) behält die Zeilen
    assert db.one("SELECT COUNT(*) n FROM quality_batch")["n"] == 4


def test_version_and_release_notes_and_dialog_script_is_loaded_first():
    from app import config as cfg
    root = Path(__file__).resolve().parent.parent
    assert cfg.VERSION == "3.15.0 · Meine Touren (2026-11-14)"
    notes = (root / "docs" / "versionen" / "3.13.0.md").read_text(encoding="utf-8")
    assert "Sammel-Korrektur" in notes or "Alle auffälligen Höhen korrigieren" in notes and "Fortschritt" in notes
    html = (root / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("js/00-i18n.js") < html.index("js/00-dialog.js") < html.index("js/01-grundlagen.js")
    assert (root / "app" / "static" / "js" / "00-dialog.js").exists()
