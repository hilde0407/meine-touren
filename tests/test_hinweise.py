"""3.23.0 – Hinweis-Bausteine, Backend: GET /api/bausteine/hinweise (app/hinweise.py) und Layout-Validierung der Hinweis-Typen (app/layout.py).
Alle Daten sind konstruiert, „heute“ ist fest (auswertung(heute=…)); erwartet wird von Hand gerechnet, nicht mit derselben Funktion."""
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import db, hinweise as hw  # noqa: E402
from app.gpxtools import TZ  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
HEUTE = date(2026, 6, 15)                    # ein Montag; das Jahr ist zu 166/365 vorbei


def tag(n, h=12, base=HEUTE):
    d = base - timedelta(days=n)
    return int(datetime(d.year, d.month, d.day, h, 0, tzinfo=TZ).timestamp())


def mk(tid, days_ago, sport="hike", km=10.0, hm=100.0, dur=3600.0, name=None, base=HEUTE):
    ts = tag(days_ago, base=base)
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,?,?,'t','komoot')",
               (tid, name or tid, sport, ts, ts + int(dur), km * 1000, dur, hm, hm))


def run(arten="", heute=HEUTE, **kw):
    p = hw.check(arten, **kw)
    return {h["art"]: h for h in hw.auswertung(p, heute)["hinweise"]}


def client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def goal(year, sport, metric, target):
    db.execute("INSERT INTO goals(year,sport,metric,target) VALUES(?,?,?,?)", (year, sport, metric, target))


# ------------------------------------------------------------------  1. Jahresziel in Gefahr
def test_ziel_forecast_and_threshold():
    mk("a", 100, km=100)                                          # 100 km in den ersten 166 Tagen → Prognose 100 / (166/365) = 219,88 km
    prog = 100 / (166 / 365)
    goal(2026, "", "km", prog / 0.89)                             # Prognose 11 % unter dem Ziel
    h = run("ziel")
    assert h["ziel"]["stufe"] == "hinweis"                        # 11 % >= 10 %, aber unter der doppelten Schwelle (20 %)
    z = h["ziel"]["daten"]["ziele"][0]
    assert z["metrik"] == "km" and abs(z["prognose"] - prog) < 0.01 and abs(z["abweichung_pct"] - 11.0) < 0.1 and z["ist"] == 100
    assert run("ziel", ziel_schwelle="15") == {}                  # Schwelle 15 %: nicht „um mehr als“ 15 % darunter
    assert run("ziel", ziel_schwelle="10.5")["ziel"]["daten"]["schwelle"] == 10.5
    db.execute("DELETE FROM goals")
    goal(2026, "", "km", prog / 0.91)                             # nur 9 % darunter: bei 10 % kein Hinweis
    assert run("ziel") == {}
    db.execute("DELETE FROM goals")
    goal(2026, "", "km", prog / 0.70)                             # 30 % darunter: Warnung (ab dem Doppelten der Schwelle)
    assert run("ziel")["ziel"]["stufe"] == "warnung"


def test_ziel_reached_early_year_other_year_and_metrics():
    mk("a", 100, km=100, hm=500, dur=7200)
    goal(2026, "", "km", 90)                                      # schon erreicht
    assert run("ziel") == {}
    db.execute("DELETE FROM goals")
    goal(2025, "", "km", 100000)                                  # Ziel des Vorjahres zählt nicht
    assert run("ziel") == {}
    goal(2026, "", "km", 100000)
    assert run("ziel", heute=date(2026, 1, 10)) == {}             # vor dem 14. Tag des Jahres keine Prognose
    assert run("ziel", heute=date(2026, 1, 14))["ziel"]["stufe"] == "warnung"
    db.execute("DELETE FROM goals")
    goal(2026, "", "up", 100000)
    goal(2026, "", "count", 100000)
    goal(2026, "", "hours", 100000)
    z = run("ziel")["ziel"]["daten"]["ziele"]
    by = {x["metrik"]: x for x in z}
    assert by["up"]["ist"] == 500 and by["count"]["ist"] == 1 and by["hours"]["ist"] == 2.0
    db.execute("UPDATE goals SET target=0 WHERE metric='hours'")  # unbrauchbares Ziel wird übergangen
    assert "hours" not in {x["metrik"] for x in run("ziel")["ziel"]["daten"]["ziele"]}


def test_ziel_sport_selects_which_goals_apply():
    mk("a", 100, "hike", km=100)
    mk("b", 90, "mtb", km=300)
    goal(2026, "hike", "km", 100000)                              # Ziel Wandern
    goal(2026, "grp:bike", "km", 100000)                          # Ziel Rad-Gruppe
    goal(2026, "", "km", 100000)                                  # Ziel ohne Aktivität: betrifft alle
    sp = lambda **kw: sorted(x["sport"] for x in run("ziel", **kw)["ziel"]["daten"]["ziele"])  # noqa: E731
    assert sp() == ["", "grp:bike", "hike"]
    assert sp(sport="hike") == ["", "hike"]
    assert sp(sport="mtb") == ["", "grp:bike"]                    # mtb gehört zur Rad-Gruppe
    assert sp(sport="skitour") == [""]
    by = {x["sport"]: x["ist"] for x in run("ziel")["ziel"]["daten"]["ziele"]}
    assert by == {"hike": 100, "grp:bike": 300, "": 400}          # jedes Ziel zählt seine eigenen Touren, auch wenn „sport“ nur auswählt


# ------------------------------------------------------------------  2. Meilenstein erreicht
def test_meilenstein_km_window_and_highest_mark():
    mk("a", 60, km=90)
    mk("b", 3, km=20)                                             # 90 → 110 km: überschreitet 100 km (vor 3 Tagen)
    m = run("meilenstein")["meilenstein"]
    assert m["stufe"] == "info" and m["daten"]["marken"] == [{"typ": "km", "wert": 100, "datum": (HEUTE - timedelta(days=3)).isoformat(), "tour": "b", "name": "b"}]
    assert run("meilenstein", meilenstein_tage="3")["meilenstein"]                   # genau 3 Tage her: noch im Fenster
    assert run("meilenstein", meilenstein_tage="2") == {}                            # 2 Tage: zu alt
    assert run("meilenstein", sport="mtb") == {}                                     # nur Touren der Aktivität zählen
    mk("c", 1, km=2000)                                                              # springt über 250, 500, 1000 und 2000 (110 → 2110): die höchste Marke zählt
    assert [x["wert"] for x in run("meilenstein")["meilenstein"]["daten"]["marken"] if x["typ"] == "km"] == [2000]


def test_meilenstein_hm_and_tours_counts():
    for i in range(24):
        mk("t%d" % i, 100 + i, km=1, hm=100)                                         # 24 Touren, 2400 hm vor mehr als 7 Tagen
    assert run("meilenstein") == {}
    mk("n", 2, km=1, hm=7700)                                                        # 25. Tour: 25 Touren und 2400 → 10100 hm (10 000 überschritten)
    marken = {x["typ"]: x["wert"] for x in run("meilenstein")["meilenstein"]["daten"]["marken"]}
    assert marken == {"touren": 25, "hm": 10000}
    assert run("meilenstein", sport="mtb") == {}
    for i in range(24, 49):
        mk("u%d" % i, 150 - i + 24, km=1, hm=0)                                      # weitere 25 Touren (alle älter als die Meilenstein-Tour) → 50 Touren
    # Die Reihenfolge nach Zeit entscheidet: die Touren u* liegen vor „n“, die 50. Tour ist nun n (heute − 2): 50 statt 25
    assert {x["typ"]: x["wert"] for x in run("meilenstein")["meilenstein"]["daten"]["marken"]}["touren"] == 50


def test_marks_function():
    assert hw._marken("km", 90, 110) == [100] and hw._marken("km", 0, 600) == [100, 250, 500] and hw._marken("km", 990, 3100) == [1000, 2000, 3000]
    assert hw._marken("hm", 9999, 10000) == [10000] and hw._marken("hm", 10000, 19999.9) == [] and hw._marken("touren", 24, 25) == [25] and hw._marken("touren", 49, 101) == [50, 100]


# ------------------------------------------------------------------  3. Neue Auffälligkeiten
def _flagged_tour(tid, n_jumps=9):
    mk(tid, 5)
    if not db.one("SELECT 1 x FROM devices WHERE id=1"):
        db.execute("INSERT INTO devices(id,name,kind,model,active) VALUES(1,'Uhr','zepp','X',1)")
    db.execute("INSERT OR REPLACE INTO tour_device(tour_id,device_id) VALUES(?,1)", (tid,))
    from app import devquality
    devquality.ensure_table()
    db.execute("INSERT INTO device_quality(tour_id,device_id,berechnet_am,day,gps_jumps,gps_gap_pct,hr_bad_pct) VALUES(?,1,1,'2026-06-10',?,0,0)", (tid, n_jumps))


def test_auffaellig_counts_unacked_flags_and_minimum():
    assert run("auffaellig") == {}
    _flagged_tour("a")
    _flagged_tour("b")
    h = run("auffaellig")["auffaellig"]
    assert h["stufe"] == "hinweis" and h["daten"] == {"anzahl": 2, "min": 1}
    assert run("auffaellig", auffaellig_min="3") == {}
    assert run("auffaellig", auffaellig_min="2")["auffaellig"]["daten"]["anzahl"] == 2
    db.execute("INSERT INTO quality_ack(tour_id,kinds,ts) VALUES('a','gps_jumps',1)")           # quittiert: zählt nicht mehr
    assert run("auffaellig")["auffaellig"]["daten"]["anzahl"] == 1
    db.execute("INSERT INTO quality_ack(tour_id,kinds,ts) VALUES('b','gps_jumps',1)")
    assert run("auffaellig") == {}
    db.execute("UPDATE device_quality SET gps_jumps=0")                                         # und wer unauffällig ist, zählt nie
    db.execute("DELETE FROM quality_ack")
    assert run("auffaellig") == {}


# ------------------------------------------------------------------  4. Lange Pause
def test_pause_days_threshold_and_activity():
    assert run("pause") == {}                                                                    # ohne Touren keine Pause
    mk("a", 20, "hike")
    mk("b", 5, "mtb")
    assert run("pause") == {}                                                                    # zuletzt vor 5 Tagen
    h = run("pause", sport="hike")["pause"]                                                      # beim Wandern: seit 20 Tagen
    assert h["stufe"] == "info" and h["daten"]["tage"] == 20 and h["daten"]["tour"] == "a" and h["daten"]["letzte"] == (HEUTE - timedelta(days=20)).isoformat()
    assert run("pause", sport="hike", pause_tage="21") == {} and run("pause", sport="hike", pause_tage="20")["pause"]
    assert run("pause", sport="hike", pause_tage="10")["pause"]["stufe"] == "hinweis"           # ab dem Doppelten der Schwelle
    assert run("pause", sport="skitour") == {}


# ------------------------------------------------------------------  5. Rekord-Tour
def test_rekord_in_window_ties_and_minimum():
    for i, (d, km, hm, dur) in enumerate([(100, 10, 100, 7200), (90, 12, 200, 7200), (80, 14, 150, 7200), (70, 9, 100, 3600)]):
        mk("o%d" % i, d, km=km, hm=hm, dur=dur)
    mk("n", 2, km=20, hm=50, dur=14400)
    r = run("rekord")["rekord"]["daten"]["rekorde"]                                              # 5 Touren: n ist die längste, o3 (9 km/h) das schnellste
    assert [x["metrik"] for x in r] == ["km"] and r[0]["tour"] == "n" and r[0]["wert"] == 20
    mk("m", 1, km=10, hm=900, dur=3600)                                                          # 10 km/h und die meisten Höhenmeter
    r = {x["metrik"]: x for x in run("rekord")["rekord"]["daten"]["rekorde"]}
    assert set(r) == {"km", "hm", "tempo"} and r["hm"]["tour"] == "m" and r["tempo"]["tour"] == "m" and abs(r["tempo"]["wert"] - 10.0) < 1e-6
    assert run("rekord", rekord_tage="1")["rekord"]["daten"]["rekorde"][0]["tour"] == "m" and {x["metrik"] for x in run("rekord", rekord_tage="1")["rekord"]["daten"]["rekorde"]} == {"hm", "tempo"}
    assert run("rekord", sport="mtb") == {}                                                      # unter 5 Touren dieser Aktivität: keine Rekorde
    mk("g", 1, km=20, hm=0, dur=7200)                                                            # Gleichstand mit n (20 km): die frühere Tour behält den Rekord
    assert [x["tour"] for x in run("rekord")["rekord"]["daten"]["rekorde"] if x["metrik"] == "km"] == ["n"]


def test_rekord_tempo_needs_3km_and_30min_and_few_tours_none():
    for i in range(4):
        mk("o%d" % i, 100 + i, km=10, hm=100, dur=7200)
    mk("kurz", 1, km=2.0, hm=0, dur=900)                                                         # 8 km/h, aber unter 3 km und 30 Minuten: kein Tempo-Rekord, sondern keine Rekordtour
    assert run("rekord") == {}
    db.execute("DELETE FROM tours WHERE id='kurz'")
    assert run("rekord") == {}                                                                   # nur 4 Touren: zu wenig für Rekorde


# ------------------------------------------------------------------  6. Wochenziel
def test_woche_goal_progress_units_and_levels():
    assert run("woche") == {}                                                                    # ohne Ziel nichts
    mk("v", 8, km=30)                                                                            # Vorwoche: zählt nicht
    mk("a", 0, km=12)                                                                            # Montag (heute)
    h = run("woche", woche_ziel="50")["woche"]
    assert h["stufe"] == "info" and h["daten"] == {"einheit": "km", "ziel": 50, "ist": 12, "rest": 38, "erreicht": False, "tage_rest": 6, "von": "2026-06-15", "bis": "2026-06-21"}
    assert run("woche", woche_ziel="12")["woche"]["daten"]["erreicht"] is True and run("woche", woche_ziel="12")["woche"]["daten"]["rest"] == 0
    t = run("woche", woche_ziel="3", woche_einheit="touren")["woche"]["daten"]
    assert t["einheit"] == "touren" and t["ist"] == 1 and t["rest"] == 2
    assert run("woche", woche_ziel="0") == {}
    assert run("woche", woche_ziel="50", sport="mtb")["woche"]["daten"]["ist"] == 0              # nur die gewählte Aktivität
    sa = run("woche", heute=date(2026, 6, 20), woche_ziel="50")["woche"]                         # Samstag: nur noch ein Tag danach → Hinweis
    assert sa["stufe"] == "hinweis" and sa["daten"]["tage_rest"] == 1 and sa["daten"]["ist"] == 12
    assert run("woche", heute=date(2026, 6, 20), woche_ziel="10")["woche"]["stufe"] == "info"    # erreicht: Info
    so = run("woche", heute=date(2026, 6, 21), woche_ziel="50")["woche"]
    assert so["daten"]["tage_rest"] == 0 and so["daten"]["von"] == "2026-06-15"
    assert run("woche", heute=date(2026, 6, 22), woche_ziel="50")["woche"]["daten"]["ist"] == 0   # neue Woche beginnt am Montag


# ------------------------------------------------------------------  7. Erholung
def _load_series(monkeypatch, recent=300.0, base=100.0, gap_recent=False):
    """12 Basiswochen und 4 Wochen aktuell, je eine Tour pro Woche (Belastung laut Uhr)."""
    from app import belastung
    db.execute("DELETE FROM tours")
    vals = {}
    for i in range(16):
        tid = "l%d" % i
        mk(tid, 7 * i + 2)
        vals[tid] = recent if i < 4 else base
    if gap_recent:
        vals["l0"] = None
    monkeypatch.setattr(belastung, "_load_value", lambda tid: vals.get(tid))
    return vals


def test_erholung_levels_data_and_recent_load(monkeypatch):
    assert run("erholung") == {}
    _load_series(monkeypatch)                                                                    # aktuell 300 gegen 100: +200 %
    h = run("erholung")["erholung"]
    assert h["stufe"] == "warnung" and h["daten"]["stufe"] == "deutlich_mehr" and h["daten"]["abweichung_pct"] == 200 and h["daten"]["basis_schnitt"] == 100
    _load_series(monkeypatch, recent=120.0)                                                      # +20 %: „etwas mehr“
    assert run("erholung") == {}                                                                 # Standard verlangt „deutlich mehr“
    h = run("erholung", erholung_stufe="mehr")["erholung"]
    assert h["stufe"] == "hinweis" and h["daten"]["stufe"] == "mehr"
    _load_series(monkeypatch, recent=100.0)
    assert run("erholung", erholung_stufe="mehr") == {}                                          # ähnlich wie sonst
    _load_series(monkeypatch, recent=300.0, gap_recent=True)                                     # in den letzten 7 Tagen keine Tour mit Uhr-Wert: schon erholt
    assert run("erholung") == {}


def test_erholung_without_watch_data_and_too_few_weeks(monkeypatch):
    from app import belastung
    for i in range(16):
        mk("l%d" % i, 7 * i + 2)
    monkeypatch.setattr(belastung, "_load_value", lambda tid: None)
    assert run("erholung") == {}                                                                 # keine Uhr-Daten
    vals = {"l0": 500.0, "l1": 500.0, "l2": 500.0, "l3": 500.0, "l4": 100.0, "l5": 100.0}       # nur 2 Basiswochen mit Daten (mindestens 8 nötig)
    monkeypatch.setattr(belastung, "_load_value", lambda tid: vals.get(tid))
    assert run("erholung") == {}


# ------------------------------------------------------------------  8. Sicherung
def test_sicherung_age_missing_and_error(tmp_path, monkeypatch):
    from app import config
    monkeypatch.setattr(config, "backup_dirs", lambda uid=None: [tmp_path])
    assert run("sicherung") == {}                                                                # ohne Touren gibt es nichts zu sichern
    mk("a", 3)
    h = run("sicherung", heute=None)["sicherung"]
    assert h["stufe"] == "warnung" and h["daten"] == {"alter_tage": None, "datum": None, "fehler": False, "schwelle": 7}      # noch keine Sicherung

    def backup(age_days):
        f = tmp_path / "meine-touren-test.zip"
        f.write_bytes(b"x")
        t = time.time() - age_days * 86400 - 600
        os.utime(f, (t, t))
    p = hw.check("sicherung")
    backup(2)
    assert hw.auswertung(p)["hinweise"] == []                                                    # vor 2 Tagen: in Ordnung
    backup(8)
    r = hw.auswertung(p)["hinweise"][0]
    assert r["stufe"] == "hinweis" and r["daten"]["alter_tage"] == 8 and r["daten"]["schwelle"] == 7
    assert hw.auswertung(hw.check("sicherung", sicherung_tage="9"))["hinweise"] == []
    backup(22)
    assert hw.auswertung(p)["hinweise"][0]["stufe"] == "warnung"                                 # ab dem Dreifachen der Schwelle
    backup(1)
    db.put("backup_err", "Ordner nicht beschreibbar")
    r = hw.auswertung(p)["hinweise"][0]
    assert r["stufe"] == "warnung" and r["daten"]["fehler"] is True                               # fehlgeschlagen: auch wenn die letzte Sicherung neu ist
    db.put("backup_err", "")
    assert hw.auswertung(p)["hinweise"] == []


# ------------------------------------------------------------------  Zusammenspiel, Endpunkt, Zwischenspeicher
def test_all_kinds_order_geprueft_and_nothing_to_report():
    p = hw.check("")
    assert p["arten"] == list(hw.ARTEN)
    r = hw.auswertung(p, HEUTE)
    assert r["hinweise"] == [] and r["geprueft"] == list(hw.ARTEN) and r["heute"] == "2026-06-15" and r["stand"]
    assert hw.check("woche,ziel,ziel")["arten"] == ["ziel", "woche"]                              # feste Reihenfolge, ohne Doppelte


def test_endpoint_validation_defaults_and_cache(monkeypatch):
    with client() as c:
        assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200
        r = c.get("/api/bausteine/hinweise")
        assert r.status_code == 200 and set(r.json()) == {"stand", "heute", "hinweise", "geprueft"} and r.json()["geprueft"] == list(hw.ARTEN)
        for q in ({"arten": "foo"}, {"arten": "ziel,<b>"}, {"sport": "a b"}, {"sport": ",".join("s%d" % i for i in range(21))}, {"ziel_schwelle": "0"}, {"ziel_schwelle": "91"}, {"ziel_schwelle": "abc"},
                  {"ziel_schwelle": "nan"}, {"meilenstein_tage": "0"}, {"meilenstein_tage": "366"}, {"meilenstein_tage": "1.5"}, {"auffaellig_min": "0"}, {"pause_tage": "-1"},
                  {"rekord_tage": "400"}, {"woche_ziel": "-1"}, {"woche_ziel": "100001"}, {"woche_einheit": "meilen"}, {"erholung_stufe": "viel"}, {"sicherung_tage": "0"}):
            assert c.get("/api/bausteine/hinweise", params=q).status_code == 400, q
        assert c.get("/api/bausteine/hinweise", params={"arten": "pause,woche", "woche_ziel": "5,5", "sport": "hike,,mtb"}).json()["geprueft"] == ["pause", "woche"]
        n = []
        orig = hw.auswertung
        monkeypatch.setattr(hw, "auswertung", lambda p, heute=None: (n.append(1), orig(p, heute))[1])
        hw._CACHE.clear()
        a = c.get("/api/bausteine/hinweise", params={"arten": "pause"}).json()
        b = c.get("/api/bausteine/hinweise", params={"arten": "pause"}).json()
        assert a == b and len(n) == 1                                                               # zweiter Aufruf aus dem Zwischenspeicher
        c.get("/api/bausteine/hinweise", params={"arten": "pause", "pause_tage": "3"})
        assert len(n) == 2                                                                          # andere Parameter: neu gerechnet
        from app import ctx
        with ctx.as_user(ctx.first_uid):                                                            # Max' eigene Datenbank (der erste Benutzer erbt die Altdaten)
            mk("zz", 40, base=datetime.now(TZ).date())
        d = c.get("/api/bausteine/hinweise", params={"arten": "pause"}).json()
        assert len(n) == 3 and d["hinweise"][0]["daten"]["tage"] == 40                               # neue Tour: Zwischenspeicher ungültig
        monkeypatch.setattr(hw, "CACHE_S", -1)
        c.get("/api/bausteine/hinweise", params={"arten": "pause"})
        assert len(n) == 4                                                                          # abgelaufen: neu


def test_endpoint_viewer_reads_users_are_separate_and_anonymous_is_refused():
    from fastapi.testclient import TestClient
    from app import main
    mk("a", 30, base=datetime.now(TZ).date())                                                        # Altdaten, erbt der erste Benutzer (Max): letzte Tour vor 30 Tagen
    goal(datetime.now(TZ).year, "", "km", 100000)
    with client() as c:
        assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        c.post("/api/users", json={"name": "Eva", "email": "eva@example.com", "password": "evas-pass123", "role": "user"})
        assert TestClient(main.app).get("/api/bausteine/hinweise").status_code in (401, 403)
        hw._CACHE.clear()
        mine = c.get("/api/bausteine/hinweise", params={"arten": "pause"}).json()
        assert mine["hinweise"][0]["art"] == "pause" and mine["hinweise"][0]["daten"]["tage"] == 30
        assert c.get("/api/bausteine/hinweise", params={"arten": "ziel"}).json()["hinweise"][0]["art"] == "ziel"
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert v.get("/api/bausteine/hinweise", params={"arten": "pause"}).status_code == 200      # Betrachter darf lesen …
        assert v.post("/api/bausteine/hinweise", json={}).status_code in (403, 405)                 # … nicht schreiben
        e = TestClient(main.app)
        assert e.post("/api/login", json={"name": "eva", "password": "evas-pass123"}).status_code == 200
        assert e.get("/api/bausteine/hinweise", params={"arten": "pause"}).json()["hinweise"] == []   # Benutzertrennung (auch im Zwischenspeicher): Evas Datenbank ist leer
        assert e.get("/api/bausteine/hinweise", params={"arten": "ziel"}).json()["hinweise"] == []
    assert main.VIEWER_GET.match("/api/bausteine/hinweise")


# ------------------------------------------------------------------  Layout-Validierung
def _w(typ, cfg=None, i="w1"):
    return {"widgets": [{"id": i, "type": typ, "cfg": cfg or {}}]}


def test_layout_hint_types_pages_and_config():
    snooze = "ziel:%d" % int(time.time() + 3 * 86400)
    with client() as c:
        for typ in ("hnziel", "hnmeilenstein", "hnauffaellig", "hnpause", "hnrekord", "hnwoche", "hnerholung", "hnsicherung", "hinweise"):
            assert c.put("/api/layout/uebersicht", json=_w(typ, {"sports": ["hike"], "title": " Mein Hinweis "})).status_code == 200, typ
        for typ in ("hnziel", "hnmeilenstein", "hnrekord", "hnerholung", "hinweise"):
            assert c.put("/api/layout/statistik", json=_w(typ)).status_code == 200, typ
        for typ in ("hnauffaellig", "hnpause", "hnwoche", "hnsicherung"):
            assert c.put("/api/layout/statistik", json=_w(typ)).status_code == 400, typ              # nur auf der Übersicht
        for typ in ("hnziel", "hinweise"):
            for k in ("tour-haupt", "tour-auswertung"):
                assert c.put("/api/layout/" + k, json=_w(typ)).status_code == 400, (typ, k)         # nie auf der Tourseite
        good = {"schwelle": 12.5, "tage": 14, "min": 2, "ziel": 50, "ausblenden": 7, "einheit": "touren", "stufe": "mehr", "woche_ziel": 80.5, "woche_einheit": "km",
                "arten": ["pause", "ziel"], "snoozes": [snooze, "pause:5"], "sports": ["hike", "hike"], "title": "X"}
        r = c.put("/api/layout/uebersicht", json=_w("hinweise", good))
        assert r.status_code == 200, r.text
        cfg = r.json()["layout"]["widgets"][0]["cfg"]
        assert cfg["arten"] == ["ziel", "pause"] and cfg["sports"] == ["hike"] and cfg["snoozes"] == [snooze, "pause:5"] and cfg["schwelle"] == 12.5
        assert c.get("/api/layout/uebersicht").json()["layout"]["widgets"][0]["cfg"]["snoozes"] == [snooze, "pause:5"]            # Zeitstempel bleibt erhalten
        far = "ziel:%d" % int(time.time() + 400 * 86400)
        bads = [{"schwelle": 0}, {"schwelle": 91}, {"schwelle": "10"}, {"schwelle": True}, {"tage": 0}, {"tage": 366}, {"tage": 2.5}, {"min": 0}, {"min": 1001}, {"ziel": -1}, {"ziel": 100001},
                {"ausblenden": 91}, {"ausblenden": -1}, {"einheit": "meilen"}, {"stufe": "viel"}, {"woche_einheit": 1}, {"arten": []}, {"arten": ["foo"]}, {"arten": "ziel"},
                {"snoozes": [far]}, {"snoozes": ["foo:1"]}, {"snoozes": ["ziel:abc"]}, {"snoozes": ["ziel:1", "ziel:2"]}, {"snoozes": "ziel:1"}, {"snoozes": [5]}, {"snoozes": ["ziel:123456789012"]},
                {"unbekannt": 1}, {"range": "all"}, {"sports": "hike"}, {"title": "x" * 61}]
        for b in bads:
            assert c.put("/api/layout/uebersicht", json=_w("hnziel", b)).status_code == 400, b
        assert c.get("/api/layout/uebersicht").json()["layout"]["widgets"][0]["cfg"]["snoozes"] == [snooze, "pause:5"]            # fehlgeschlagene Versuche ändern nichts
        assert c.put("/api/layout/uebersicht", json=_w("hnziel", {"snoozes": []})).status_code == 200                                # leer = nicht ausgeblendet
        # in einer Ansicht (Behälter) gilt dieselbe Prüfung
        box = {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": _w("hnauffaellig")}, {"id": "b", "name": "B", "layout": _w("hnziel", {"schwelle": 5})}], "active": "standard"}
        assert c.put("/api/layout/uebersicht", json=box).status_code == 200
        box["views"][1]["layout"] = _w("hnziel", {"schwelle": 500})
        assert c.put("/api/layout/uebersicht", json=box).status_code == 400
        box["views"][1]["layout"] = _w("hnwoche")
        assert c.put("/api/layout/statistik", json=box).status_code == 400
        # Export-Datei einer Ansicht
        lay = {"v": 1, **_w("hnziel", {"schwelle": 15, "snoozes": [snooze]}), "order": ["w1"]}
        doc = {"format": "meine-touren-ansicht", "format_version": 1, "app_version": "3.23.0", "page": "uebersicht", "name": "Mit Hinweisen", "exported": "2026-11-15T10:00:00Z", "layouts": {"uebersicht": lay}}
        r = c.post("/api/layout/check", json=doc).json()
        assert r["ok"] and r["stats"]["uebersicht"]["types"] == ["hnziel"] and r["layouts"]["uebersicht"]["widgets"][0]["cfg"]["schwelle"] == 15
        doc["layouts"]["uebersicht"]["widgets"][0]["cfg"]["schwelle"] = 0
        assert not c.post("/api/layout/check", json=doc).json()["ok"]
        doc["page"] = "tour"
        doc["layouts"] = {"tour-haupt": lay}
        assert not c.post("/api/layout/check", json=doc).json()["ok"]                                                                 # auf der Tourseite abgelehnt


def test_layout_hint_viewer_cannot_write_and_users_are_separate():
    from fastapi.testclient import TestClient
    from app import main
    with client() as c:
        assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        c.post("/api/users", json={"name": "Eva", "email": "eva@example.com", "password": "evas-pass123", "role": "user"})
        assert c.put("/api/layout/uebersicht", json=_w("hnziel", {"snoozes": ["ziel:%d" % int(time.time() + 86400)]})).status_code == 200
        v = TestClient(main.app)
        v.post("/api/login", json={"name": "oma", "password": "omas-pass12"})
        assert v.put("/api/layout/uebersicht", json=_w("hnziel")).status_code == 403
        assert v.get("/api/layout/uebersicht").json()["layout"] is None                                                               # Betrachter: immer der Standard
        e = TestClient(main.app)
        e.post("/api/login", json={"name": "eva", "password": "evas-pass123"})
        assert e.get("/api/layout/uebersicht").json()["layout"] is None                                                               # Evas Ausblenden-Zeit ist ihre eigene


def test_version_notes_and_script_order():
    from app import config as cfg
    assert cfg.VERSION.startswith("3.41.0 · Meine Touren")
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("js/57-bausteine-statistik.js") < html.index("js/58-bausteine-hinweise.js") < html.index("js/39-sw.js")
    notes = (ROOT / "docs" / "versionen" / "3.23.0.md").read_text(encoding="utf-8")
    assert "Hinweis-Bausteine" in notes and "/api/bausteine/hinweise" in notes
    for name in ("Jahresziel in Gefahr", "Meilenstein erreicht", "Neue Auffälligkeiten", "Lange Pause", "Rekord-Tour", "Wochenziel", "Erholung", "Sicherung", "Mit Hinweisen"):
        assert name in notes, name
    assert "mt-v122" in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
