"""3.11.0 – „Training laut Uhr“: Auswertung der Zepp-Zusammenfassung/-Splits, Plausibilitätsprüfungen, Zwischenspeicher, Zusatzdatei, Rechte, Backup/Umzug.
ALLE Daten sind konstruiert, aber mit den Wertebereichen echter Diagnose-Dateien (Cheetah Pro / Balance). Echte Zepp-Antworten gibt es hier nicht;
die Deutung von te (Zehntel), heart_range, weatherInfo und kilo_pace ist eine ANNAHME (siehe app/uhrtraining.py)."""
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from tests.test_messwerte import _client  # noqa: E402
from app import config, db, extras, sync, tracks, umzug, uhrtraining as ut, zepp  # noqa: E402

T0 = 1750000000
SECRET = "GEHEIMES-ZEPP-TOKEN-4711"
KP = ["0,650,0,0,112,0,0,300,0,56,0,0,0,40", "1,640,0,0,118,0,0,310,0,57,0,0,0,41", "2,700,0,0,121,0,0,320,0,55,0,0,0,40",
      "3,655,0,0,125,0,0,330,0,56,0,0,0,39", "4,605,0,0,130,0,0,340,0,58,0,0,0,40"]


@pytest.fixture(autouse=True)
def _reset():
    ut.reset_cache()
    yield
    ut.reset_cache()


def summary(start, **kw):
    """Zusammenfassung im Stil der Balance (Werte aus den echten Bereichen): 5,4 km in 60 min."""
    s = {"trackid": str(start), "source": "run.46.huami.com", "type": "6", "dis": "5400", "run_time": "3600", "end_time": str(start + 3600), "calorie": "312",
         "te": "32", "anaerobic_te": "14", "exercise_load": "96", "rpe": "5", "total_step": "6800", "pause_time": "240", "pauseTimeWithMillis": "240000",
         "avg_heart_rate": "118", "max_heart_rate": "152", "min_heart_rate": "84", "avg_frequency": "112", "avg_pace": "1.2", "avg_slope": "3",
         "altitude_ascend": "310", "altitude_descend": "305", "max_altitude": "1240", "min_altitude": "905",
         "heart_range": "600,100;900,118;1200,135;600,150;240,160;60,168", "weatherInfo": "3,21,0,0,0,74", "VO2_max": "-1", "spo2": "0",
         "avg_stride_length": "0", "min_pace": "0", "city": "Berlin", "lat_start": "48.1234"}
    s.update(kw)
    return s


def kilo(last="5,260,0,0,128,0,0,350,0,57,0,0,0,40"):
    return ";".join(KP + ([last] if last else []))


class Api:
    def __init__(self, hist, kp=None, fail_detail=False):
        self.hist, self.kp, self.fail_detail = hist, kp if kp is not None else kilo(), fail_detail
        self.h_calls = self.d_calls = 0

    def history(self):
        self.h_calls += 1
        return self.hist

    def detail(self, s):
        self.d_calls += 1
        if self.fail_detail:
            raise RuntimeError("Detail kaputt " + SECRET)
        return {"kilo_pace": self.kp, "longitude_latitude": "4812340000,812340000", "altitude": "-2004831"}


def tour(tid, ts, kind="zepp", dist=5400, dur=3600):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,100,100,'t','komoot')",
               (tid, f"Tour {tid}", "hike", ts, ts + dur, dist, dur))
    db.execute("INSERT OR REPLACE INTO tour_source(tour_id,src,name) VALUES(?,?,'')", (tid, kind))


def use(monkeypatch, api):
    monkeypatch.setattr(sync, "_zepp_api", lambda: api)
    return api


def world(monkeypatch, n=1, _kp=None, **kw):
    hist = []
    for i in range(n):
        st = T0 + i * 86400 + 10
        tour(f"z{st}", st)
        hist.append(summary(st, **kw))
    return _client(), use(monkeypatch, Api(hist, kp=_kp)), [f"z{T0 + i * 86400 + 10}" for i in range(n)]


def get(c, tid):
    r = c.get(f"/api/tours/{tid}/uhr-training")
    assert r.status_code == 200, r.text
    return r.json()


# ---------------------------------------------------------------- Werte und Platzhalter
def test_values_from_real_ranges(monkeypatch):
    c, api, (tid,) = world(monkeypatch)
    d = get(c, tid)
    assert d["quelle"] == "zepp" and d["status"] == "ok" and d["device"]["name"] == "Amazfit/Zepp"
    w = {k: v["wert"] for k, v in d["werte"].items()}
    assert w == {"te": 3.2, "ate": 1.4, "last": 96, "rpe": 5, "kcal": 312, "schritte": 6800, "pause_s": 240, "puls_avg": 118, "puls_max": 152, "puls_min": 84,
                 "frequenz": 112, "aufstieg": 310, "abstieg": 305, "hoehe_max": 1240, "hoehe_min": 905}
    assert d["wetter"] == {"temp_c": 21, "feuchte_pct": 74}
    assert d["geladen"] and d["hinweise"] and any("nicht mit Garmin vergleichbar" in h for h in d["hinweise"])


def test_placeholders_are_never_shown(monkeypatch):
    ph = {k: "-1" for k in ("te", "anaerobic_te", "exercise_load", "rpe", "calorie", "total_step", "pause_time", "avg_heart_rate", "max_heart_rate", "min_heart_rate",
                            "avg_frequency", "altitude_ascend", "altitude_descend", "max_altitude", "min_altitude")}
    ph.update(heart_range="0,0;0,0;0,0;0,0;0,0;0,0", weatherInfo="-1,-274,-1,-1,-1,-361", max_altitude="-2004831", min_altitude="-2004831")
    c, api, (tid,) = world(monkeypatch, _kp="", **ph)
    d = get(c, tid)
    assert d["werte"] == {} and d["pulszonen"] is None and d["wetter"] is None and d["splits"] is None
    assert d["status"] == "leer"
    for k in ("-1", "-274", "-361", "2004831"):
        assert k not in json.dumps(d["werte"]) + json.dumps(d["wetter"])
    # 0 bei Höhe/Temperatur/Luftfeuchte/Schritten ist kein Wert
    ph2 = dict(altitude_ascend="0", altitude_descend="0", max_altitude="0", min_altitude="0", pause_time="0", total_step="0", weatherInfo="3,0,0,0,0,0",
               te="0", anaerobic_te="0", exercise_load="0", calorie="0", avg_frequency="0", avg_heart_rate="0", max_heart_rate="0", min_heart_rate="0", rpe="0",
               heart_range="")
    assert ut.kennzahlen(summary(1, **ph2)) == {} and ut.wetter(summary(1, **ph2)) is None and ut.pulszonen(summary(1, **ph2)) is None


def test_te_only_as_whole_tenths_and_avg_pace_never_shown(monkeypatch):
    c, api, (tid,) = world(monkeypatch, te="3.4", anaerobic_te="70")
    d = get(c, tid)
    assert "te" not in d["werte"] and "ate" not in d["werte"]                   # keine ganze Zahl bzw. außerhalb der Skala: nichts erraten
    s = json.dumps(d)
    assert "avg_pace" not in s and "avg_slope" not in s and "pauseTimeWithMillis" not in s
    ut.reset_cache()
    assert ut.kennzahlen(summary(1, te="26", anaerobic_te="1"))["te"]["wert"] == 2.6
    assert ut.kennzahlen(summary(1, te="50"))["te"]["wert"] == 5.0 and ut.kennzahlen(summary(1, te="6"))["te"]["wert"] == 0.6


def test_heart_values_must_be_consistent():
    w = ut.kennzahlen(summary(1, avg_heart_rate="160", max_heart_rate="150", min_heart_rate="84"))
    assert w["puls_avg"]["wert"] == 160 and "puls_max" not in w and "puls_min" not in w
    w = ut.kennzahlen(summary(1, min_heart_rate="130"))
    assert "puls_min" not in w and w["puls_avg"]["wert"] == 118
    w = ut.kennzahlen(summary(1, max_altitude="500", min_altitude="900"))
    assert "hoehe_max" not in w and "hoehe_min" not in w


def test_summary_without_source_or_coordinates_in_sidecar(monkeypatch):
    c, api, (tid,) = world(monkeypatch)
    get(c, tid)
    raw = ut.sidecar(tid).read_text(encoding="utf-8")
    d = json.loads(raw)
    assert d["summary"]["te"] == "32" and "source" not in d["summary"] and "city" not in raw and "48.1234" not in raw and "run.46.huami.com" not in raw
    assert "-2004831" not in raw and "longitude" not in raw and "avg_pace" not in raw
    assert d["kilo_pace"] and d["detail"] is True


# ---------------------------------------------------------------- Pulszonen
def test_zones_only_when_sum_matches_run_time(monkeypatch):
    s = summary(1)
    z = ut.pulszonen(s)
    assert [x["bis_bpm"] for x in z] == [100, 118, 135, 150, 160, 168] and sum(x["sekunden"] for x in z) == 3600 and abs(sum(x["anteil"] for x in z) - 1) < 0.01
    assert ut.pulszonen(dict(s, run_time="3150")) is not None                      # Summe 3600 = +14,3 % -> noch innerhalb ±15 %
    assert ut.pulszonen(dict(s, run_time="3100")) is None                          # +16 %
    assert ut.pulszonen(dict(s, run_time="4200")) is not None                      # 3600/4200 = 0,857: innerhalb
    assert ut.pulszonen(dict(s, run_time="4300")) is None                          # 0,837: außerhalb
    assert ut.pulszonen(dict(s, heart_range="600,100;900,118;1200,135;600,150;240,160;60,168;1,1")) is None           # siebtes Paar mit unmöglicher Grenze
    assert ut.pulszonen(dict(s, heart_range="600,168;900,150;1200,135;600,118;240,100;60,90")) is None                 # Grenzen fallen
    assert ut.pulszonen(dict(s, heart_range="10377,100;900,118")) is None                                              # zu wenige Zonen
    assert ut.pulszonen(dict(s, heart_range="600,10;900,118;1200,135;600,150;240,160;60,168")) is None                 # Grenze unplausibel
    assert ut.pulszonen(dict(s, heart_range="kaputt;x,y")) is None and ut.pulszonen(dict(s, heart_range=None)) is None
    assert ut.pulszonen(dict(s, heart_range=[[600, 100], [900, 118], [1200, 135], [600, 150], [240, 160], [60, 168]])) is not None     # auch als Liste
    assert ut.pulszonen({k: v for k, v in s.items() if k != "run_time"}) is None
    c, api, (tid,) = world(monkeypatch, run_time="9000", dis="5400")                # Summe der Zonen (3600) passt nicht zur Dauer: ganz weglassen
    d = get(c, tid)
    assert d["pulszonen"] is None and not any("Pulszonen" in h for h in d["hinweise"])


# ---------------------------------------------------------------- Wetter
def test_weather_only_when_plausible():
    assert ut.wetter(summary(1, weatherInfo="3,21,0,0,0,74")) == {"temp_c": 21, "feuchte_pct": 74}
    assert ut.wetter(summary(1, weatherInfo="3,17.5,0,0,0,68")) == {"temp_c": 17.5, "feuchte_pct": 68}
    assert ut.wetter(summary(1, weatherInfo="3,99,0,0,0,74")) == {"feuchte_pct": 74}                    # 99 °C: unmöglich, Feuchte bleibt
    assert ut.wetter(summary(1, weatherInfo="3,21,0,0,0,120")) == {"temp_c": 21}
    assert ut.wetter(summary(1, weatherInfo="3,-274,0,0,0,-1")) is None
    assert ut.wetter(summary(1, weatherInfo="3,0,0,0,0,0")) is None                                       # 0 = Platzhalter
    assert ut.wetter(summary(1, weatherInfo="3")) is None and ut.wetter(summary(1, weatherInfo=None)) is None and ut.wetter(summary(1, weatherInfo="")) is None
    assert ut.wetter(summary(1, weatherInfo=[3, 22, 0, 0, 0, 80])) == {"temp_c": 22, "feuchte_pct": 80}
    assert ut.wetter(summary(1, weatherInfo="[3,22,0,0,0,80]")) == {"temp_c": 22, "feuchte_pct": 80}
    assert ut.wetter(summary(1, weatherInfo=["a", "b"])) is None


# ---------------------------------------------------------------- Splits
def test_splits_with_partial_kilometre(monkeypatch):
    c, api, (tid,) = world(monkeypatch)
    sp = get(c, tid)["splits"]
    assert [s["km"] for s in sp] == [1, 2, 3, 4, 5, 6]
    assert sp[0]["sek"] == 650 and sp[0]["min_km"] == round(650 / 60, 2) and sp[0]["puls"] == 112 and sp[0]["schritte"] == 112     # 56 Zyklen = 112 Schritte/min (zur Zusammenfassung geprüft)
    last = sp[-1]
    assert last["strecke_m"] == 400 and last["sek"] == 260 and abs(last["min_km"] - 260 / 0.4 / 60) < 0.01 and all(s["strecke_m"] == 1000 for s in sp[:-1])


def test_partial_kilometre_dropped_when_time_does_not_fit():
    s = summary(1)
    full = ut.splits(s, kilo(last="5,650,0,0,128,0,0,350,0,57,0,0,0,40"), 112)         # Zeit eines vollen Kilometers für 400 m: passt nicht
    assert [x["km"] for x in full] == [1, 2, 3, 4, 5]
    assert ut.splits(s, kilo(last="5,10,0,0,128,0,0,350,0,57,0,0,0,40"), 112)[-1]["km"] == 5      # 10 s für 400 m: zu schnell
    assert ut.splits(dict(s, dis="5000"), kilo(), 112)[-1]["km"] == 5                       # Strecke hat nur 5 volle km, Rest 0 m: sechste Zeile wird nicht gezeigt
    assert ut.splits(dict(s, dis="5000"), kilo(last=None), 112) is not None
    assert ut.splits(dict(s, dis="5050"), kilo(), 112) [-1]["km"] == 5                      # Rest 50 m: zu kurz, weglassen


def test_splits_rejected_when_not_consistent():
    s = summary(1)
    cum = ";".join(f"{i},{650 * (i + 1)},0,0,110" for i in range(5))                       # kumulative Zeiten: Summe weit über der Dauer
    assert ut.splits(s, cum, None) is None
    assert ut.splits(s, ";".join(f"{i + 1},650,0,0,110" for i in range(5)), None) is None     # Nummern beginnen nicht bei 0
    assert ut.splits(s, ";".join(f"{i},65,0,0,110" for i in range(5)), None) is None          # 65 s je km: unplausibel
    assert ut.splits(s, ";".join(f"{i},650,0,0,110" for i in range(5)), None) is not None
    assert ut.splits(s, ";".join(f"{i},2400,0,0,110" for i in range(5)), None) is None        # Summe 12 000 s >> 3 600 s
    assert ut.splits(dict(s, dis="0"), kilo(), None) is None and ut.splits(s, "", None) is None and ut.splits(s, "x;y", None) is None
    assert ut.splits(dict(s, dis="900"), "0,650", None) is None                                 # unter einem Kilometer
    assert len(ut.splits(s, [[0, 650, 0, 0, 110], [1, 640, 0, 0, 110]], None)) == 2             # Uhr liefert nur 2 Zeilen: gezeigt wird, was da ist


def test_split_heart_rate_and_cadence_only_when_plausible():
    s = summary(1)
    nop = ";".join(f"{i},650,0,0,0,0,0,300,0,56" for i in range(5))                         # Puls 0 = kein Wert
    sp = ut.splits(s, nop, 112)
    assert sp and all(x["puls"] is None for x in sp) and all(x["schritte"] == 112 for x in sp)
    odd = ";".join(f"{i},650,0,0,300,0,0,300,0,75" for i in range(5))                       # Puls 300 unmöglich; 75 (bzw. 150) passt nicht zu 112 Schritte/min
    sp = ut.splits(s, odd, 112)
    assert all(x["puls"] is None and x["schritte"] is None for x in sp)
    assert all(x["schritte"] is None for x in ut.splits(s, nop, None))                       # ohne mittlere Schrittfrequenz keine Gegenprobe
    steps = ";".join(f"{i},650,0,0,110,0,0,300,0,110" for i in range(5))
    assert all(x["schritte"] == 110 for x in ut.splits(s, steps, 112))                       # Spalte schon in Schritten/min


# ---------------------------------------------------------------- Zepp-Fehler und Zwischenspeicher
def test_no_access_and_errors_give_a_message_not_a_crash(monkeypatch):
    tour("z1750000010", T0 + 10)
    c = _client()

    def nope():
        raise RuntimeError("Zepp-Zugangsdaten fehlen (Einstellungen)")
    monkeypatch.setattr(sync, "_zepp_api", nope)
    d = get(c, "z1750000010")
    assert d["status"] == "kein_zugang" and "Zepp-Zugang" in d["meldung"] and d["werte"] == {}
    assert not ut.sidecar("z1750000010").exists()
    ut.reset_cache()

    def boom():
        raise ValueError("Antwort mit " + SECRET)
    monkeypatch.setattr(sync, "_zepp_api", boom)
    r = c.get("/api/tours/z1750000010/uhr-training")
    assert r.status_code == 200 and r.json()["status"] == "fehler" and SECRET not in r.text
    calls = []
    monkeypatch.setattr(sync, "_zepp_api", lambda: calls.append(1) or (_ for _ in ()).throw(RuntimeError("x")))
    assert get(c, "z1750000010")["status"] == "fehler" and not calls                   # kurz gemerkt: kein erneuter Abruf bei jedem Seitenaufruf


def test_history_error_after_loading_keeps_old_values_on_reload(monkeypatch):
    c, api, (tid,) = world(monkeypatch)
    assert get(c, tid)["werte"]["kcal"]["wert"] == 312

    def boom():
        raise RuntimeError("Netzwerk " + SECRET)
    monkeypatch.setattr(sync, "_zepp_api", boom)
    r = c.post(f"/api/tours/{tid}/uhr-training/neu")
    assert r.status_code == 200 and SECRET not in r.text
    j = r.json()
    assert j["status"] == "fehler" and j["werte"]["kcal"]["wert"] == 312 and "Gespeicherte Werte" in j["meldung"]
    assert get(c, tid)["werte"]["kcal"]["wert"] == 312


def test_detail_failure_keeps_summary_and_says_so(monkeypatch):
    hist = [summary(T0 + 10)]
    tour(f"z{T0 + 10}", T0 + 10)
    api = use(monkeypatch, Api(hist, fail_detail=True))
    c = _client()
    d = get(c, f"z{T0 + 10}")
    assert d["status"] == "ok" and d["werte"]["kcal"]["wert"] == 312 and d["splits"] is None and any("Kilometerwerte konnten nicht geladen" in h for h in d["hinweise"])
    assert SECRET not in json.dumps(d) and SECRET not in ut.sidecar(f"z{T0 + 10}").read_text(encoding="utf-8")
    api.fail_detail = False
    j = c.post(f"/api/tours/z{T0 + 10}/uhr-training/neu").json()                          # Neu laden holt das Detail nach
    assert j["splits"] and not any("konnten nicht geladen" in h for h in j["hinweise"])


def test_sidecar_cache_second_call_needs_no_zepp(monkeypatch):
    c, api, (tid,) = world(monkeypatch)
    a = get(c, tid)
    assert (api.h_calls, api.d_calls) == (1, 1) and ut.sidecar(tid).exists()
    monkeypatch.setattr(sync, "_zepp_api", lambda: (_ for _ in ()).throw(AssertionError("Zepp darf nicht gefragt werden")))
    b = get(c, tid)
    assert b["werte"] == a["werte"] and b["splits"] == a["splits"] and (api.h_calls, api.d_calls) == (1, 1)
    ut.reset_cache()                                                                       # auch nach Neustart (Speicher leer) nur die Zusatzdatei
    assert get(c, tid)["werte"] == a["werte"]


def test_history_cached_for_ten_minutes_across_tours(monkeypatch):
    c, api, tids = world(monkeypatch, n=3)
    for t in tids:
        assert get(c, t)["status"] == "ok"
    assert api.h_calls == 1 and api.d_calls == 3                                           # Verlauf einmal, je Tour ein Detail
    ut.reset_cache()
    st = T0 + 9 * 86400 + 10
    tour(f"z{st}", st)
    api.hist.append(summary(st))
    assert get(c, f"z{st}")["status"] == "ok" and api.h_calls == 2
    u = ut.ctx.uid() or ""
    ut._HIST[u]["ts"] -= ut.TTL + 5                                                         # abgelaufen
    st2 = T0 + 10 * 86400 + 10
    tour(f"z{st2}", st2)
    api.hist.append(summary(st2))
    assert get(c, f"z{st2}")["status"] == "ok" and api.h_calls == 3


def test_reload_button_refreshes_history_and_detail(monkeypatch):
    c, api, (tid,) = world(monkeypatch)
    get(c, tid)
    api.hist[0] = summary(T0 + 10, calorie="400")
    api.kp = kilo(last=None)
    j = c.post(f"/api/tours/{tid}/uhr-training/neu").json()
    assert j["status"] == "ok" and j["werte"]["kcal"]["wert"] == 400 and api.h_calls == 2 and api.d_calls == 2
    assert [s["km"] for s in j["splits"]] == [1, 2, 3, 4, 5]
    assert get(c, tid)["werte"]["kcal"]["wert"] == 400 and api.h_calls == 2


def test_no_matching_training_and_ambiguous_and_not_zepp(monkeypatch):
    tour("z5", T0 + 5)
    c = _client()
    api = use(monkeypatch, Api([summary(T0 + 90000)]))
    assert get(c, "z5")["status"] == "kein_training" and not ut.sidecar("z5").exists()
    # mehrdeutig: zwei passende Trainings (Komoot-Tour ohne z-Kennung)
    ut.reset_cache()
    db.execute("DELETE FROM tours WHERE id='z5'")
    tour("k1", T0 + 100)
    api.hist = [summary(T0 + 100), summary(T0 + 130)]
    d = get(c, "k1")
    assert d["status"] == "mehrdeutig" and d["werte"] == {} and "mehrere" in d["meldung"]
    # eindeutig über die Zuordnung (anderer Start, gleiche Strecke/Dauer)
    ut.reset_cache()
    api.hist = [summary(T0 + 130)]
    assert get(c, "k1")["status"] == "ok"
    # Garmin-Tour: Zepp wird nicht einmal gefragt
    tour("g1", T0 + 5000, kind="garmin")
    n = api.h_calls
    assert get(c, "g1")["status"] == "nicht_zepp" and api.h_calls == n
    assert c.get("/api/tours/gibtsnicht/uhr-training").status_code == 404
    assert c.post("/api/tours/gibtsnicht/uhr-training/neu").status_code == 404


def test_tour_manually_assigned_to_other_device_is_not_zepp(monkeypatch):
    c, api, (tid,) = world(monkeypatch)
    g = c.post("/api/devices", json={"name": "Forerunner", "kind": "garmin"}).json()["id"]
    c.post(f"/api/tours/{tid}/device", json={"device_id": g})
    assert get(c, tid)["status"] == "nicht_zepp" and api.h_calls == 0


def test_device_name_from_my_devices(monkeypatch):
    c, api, (tid,) = world(monkeypatch)
    c.post("/api/devices", json={"name": "Amazfit Cheetah Pro", "kind": "zepp", "model": "Cheetah Pro"})
    d = get(c, tid)
    assert d["device"]["name"] == "Amazfit Cheetah Pro" and d["device"]["kind"] == "zepp"


# ---------------------------------------------------------------- Rechte, Backup, Umzug
def test_viewer_reads_stored_values_only_and_cannot_reload(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    st = T0 + 10
    tour(f"z{st}", st)
    tour(f"z{st + 86400}", st + 86400)
    api = use(monkeypatch, Api([summary(st), summary(st + 86400)]))
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        assert c.get(f"/api/tours/z{st}/uhr-training").json()["status"] == "ok"             # Eigentümer lädt
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        r = v.get(f"/api/tours/z{st}/uhr-training")
        assert r.status_code == 200 and r.json()["werte"]["kcal"]["wert"] == 312
        n = (api.h_calls, api.d_calls)
        r2 = v.get(f"/api/tours/z{st + 86400}/uhr-training")                                  # nicht gespeichert: Betrachter löst keinen Zepp-Abruf aus
        assert r2.status_code == 200 and r2.json()["status"] == "nicht_geladen" and (api.h_calls, api.d_calls) == n
        assert v.post(f"/api/tours/z{st}/uhr-training/neu").status_code == 403
        assert TestClient(main.app).get(f"/api/tours/z{st}/uhr-training").status_code in (401, 403)
        assert TestClient(main.app).post(f"/api/tours/z{st}/uhr-training/neu").status_code in (401, 403)
        assert c.post(f"/api/tours/z{st}/uhr-training/neu").status_code == 200


def test_sidecar_in_backup_and_umzug_and_deleted_with_tour(tmp_path, monkeypatch):
    c, api, (tid,) = world(monkeypatch)
    get(c, tid)
    z = zipfile.ZipFile(io.BytesIO(extras.make_backup()[1]))
    assert f"tracks/{tid}.uhr.json" in z.namelist()
    z2 = zipfile.ZipFile(io.BytesIO(extras.make_backup(strip_secrets=True)[1]))
    assert f"tracks/{tid}.uhr.json" not in z2.namelist()                                     # wie die übrigen Zusatzdateien: nicht im geteilten Export
    out = umzug.make(config.DATA_DIR, tmp_path / "out", "t")
    assert any(n.endswith(f"tracks/{tid}.uhr.json") for n in zipfile.ZipFile(out).namelist())
    n = umzug.restore(out, tmp_path / "neu")
    assert n > 0 and json.loads((tmp_path / "neu" / "tracks" / f"{tid}.uhr.json").read_text(encoding="utf-8"))["summary"]["te"] == "32"
    db.execute("UPDATE tours SET source='local' WHERE id=?", (tid,))
    tracks.delete_local(tid)
    assert not ut.sidecar(tid).exists()


def test_main_page_loads_script_and_version():
    from app import config as cfg
    assert cfg.VERSION.startswith("3.13.0 · Meine Touren")
    html = (Path(__file__).resolve().parent.parent / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("js/44-geraete.js") < html.index("js/45-uhrtraining.js")


# ---------------------------------------------------------------- Höhen-Platzhalter (zepp.decode_points)
def test_altitude_placeholder_is_not_interpolated_into_heights():
    n = 8
    ll = ";".join(["5000000000,800000000"] + ["20000,0"] * (n - 1))
    base = {"longitude_latitude": ll, "time": ";".join(["0"] + ["10"] * (n - 1)), "heart_rate": "", "gait": ""}
    s = {"trackid": str(T0)}
    det = dict(base, altitude="120000;-2004831;-2004831;120400;120500;-2004831;120700;120800")      # cm; −2 004 831 = Platzhalter der Uhr
    pts = zepp.decode_points(s, det)
    hs = [p[3] for p in pts]
    assert len(hs) == n and min(hs) >= 1190 and max(hs) <= 1208                          # nie unter −500 m und nie „dazwischen“ erfunden
    assert hs[1] == 1200 and hs[2] == 1200 and hs[5] == 1205                              # Platzhalter übernehmen den letzten echten Wert
    pts = zepp.decode_points(s, dict(base, altitude=";".join(["-2004831"] * n)))
    assert all(p[3] > -500 for p in pts)
    pts = zepp.decode_points(s, dict(base, altitude="-2004831;-2004831;120000;120100;120200;120300;120400;120500"))
    assert min(p[3] for p in pts) >= 1200                                                  # Platzhalter am Anfang: erster echter Wert
    # Zwischenpunkte (Puls-Zeitpunkte) kurz vor dem nächsten echten Wert: früher entstand hier eine erfundene Höhe zwischen −20 000 m und der echten Höhe
    det = {"longitude_latitude": ";".join(["5000000000,800000000"] + ["200000,0"] * 3), "time": "0;100;100;100", "altitude": "120000;-2004831;120400;120500",
           "heart_rate": "99,80;100,1;100,1;100,1", "gait": ""}
    hs = [p[3] for p in zepp.decode_points(s, det)]
    assert len(hs) >= 5 and min(hs) >= 1199.9 and max(hs) <= 1205.1, hs
