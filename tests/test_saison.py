"""3.37.0 – Serverdaten der neuen Bausteine: „Jahreszeiten und Wetter“ (GET /api/bausteine/saison), Anteil am Limit der Ausrüstung,
Kilometer und aktive Tage je Woche für die Wochenansicht von „Belastung und Erholung“. Alle Daten sind konstruiert; Leer- und Randfälle, Filter, Rechte."""
import json
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import belastung as B, bausteine_daten as bd, db  # noqa: E402
from app.gpxtools import TZ  # noqa: E402


def ts(y, m, d, h=12):
    return int(datetime(y, m, d, h, 0, tzinfo=TZ).timestamp())


def mk(tid, when, km=10.0, sport="hike", wx=None, name=None):
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,100,100,52.5,13.4,'t','komoot')",
               (tid, name or tid, sport, when, when + 3600, km * 1000, 3600))
    if wx is not None:
        db.execute("INSERT OR REPLACE INTO weather(id,js,ts) VALUES(?,?,?)", (tid, wx if isinstance(wx, str) else json.dumps(wx), when))


def client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def get(c, **q):
    r = c.get("/api/bausteine/saison", params=q)
    assert r.status_code == 200, r.text
    return r.json()


def season(d, key):
    return next(z for z in d["jahreszeiten"] if z["key"] == key)


def test_leer_ohne_touren_und_ohne_wetter():
    with client() as c:
        d = get(c)
        assert d["touren"] == 0 and d["km"] == 0 and len(d["monate"]) == 12 and [z["key"] for z in d["jahreszeiten"]] == ["fruehling", "sommer", "herbst", "winter"]
        assert all(m["touren"] == 0 and m["t_mittel"] is None and m["mit_wetter"] == 0 for m in d["monate"])
        assert d["wetter"] == {"mit": 0, "ohne": 0, "t_mittel": None, "t_min": None, "t_max": None, "klassen": []}


def test_monats_und_jahreszeitgrenzen_ueber_mehrere_jahre():
    for i, (y, m, dd, km) in enumerate([(2025, 2, 28, 1), (2026, 2, 1, 2), (2025, 3, 1, 4), (2025, 5, 31, 8), (2025, 6, 1, 16), (2025, 8, 31, 32), (2025, 9, 1, 64), (2025, 11, 30, 128), (2025, 12, 1, 256), (2024, 12, 31, 512)]):
        mk(f"t{i}", ts(y, m, dd), km=km)
    with client() as c:
        d = get(c)
        assert d["touren"] == 10 and d["km"] == 1023
        assert d["monate"][1]["touren"] == 2 and d["monate"][1]["km"] == 3                          # Februar beider Jahre zusammen
        assert d["monate"][11]["touren"] == 2 and d["monate"][11]["km"] == 768
        assert (season(d, "winter")["touren"], season(d, "winter")["km"]) == (4, 771) and season(d, "winter")["monate"] == [12, 1, 2]
        assert (season(d, "fruehling")["touren"], season(d, "fruehling")["km"]) == (2, 12)          # 1. März bis 31. Mai
        assert (season(d, "sommer")["touren"], season(d, "sommer")["km"]) == (2, 48)                # 1. Juni bis 31. August
        assert (season(d, "herbst")["touren"], season(d, "herbst")["km"]) == (2, 192)               # 1. September bis 30. November
        assert sum(z["touren"] for z in d["jahreszeiten"]) == d["touren"] and sum(z["km"] for z in d["jahreszeiten"]) == d["km"]


def test_temperaturen_nur_aus_lokalen_daten_und_nie_null_als_platzhalter():
    mk("a", ts(2025, 7, 1), km=10, wx={"tmin": 10, "tmax": 20})                                       # Mittel 15
    mk("b", ts(2025, 7, 2), km=20, wx={"tmin": 20, "tmax": 30})                                       # Mittel 25
    mk("c", ts(2025, 7, 3), km=30)                                                                    # ohne Wetterdaten
    mk("w", ts(2025, 1, 5), km=5, wx={"tmin": -8, "tmax": -2})                                        # Mittel -5
    for k, wx in enumerate(["kaputt", {"tmin": None, "tmax": 5}, {"tmin": "x", "tmax": 5}, {"tmin": 9, "tmax": 1}, {"tmin": -99, "tmax": 5}, {"tmin": True, "tmax": 5}, {"tmin": 5}, {}]):
        mk(f"x{k}", ts(2025, 4, 1 + k), km=1, wx=wx)                                                  # unbrauchbar: gelten als ohne Angabe
    with client() as c:
        d = get(c)
        jul = d["monate"][6]
        assert jul["touren"] == 3 and jul["mit_wetter"] == 2 and jul["t_mittel"] == 20.0 and jul["t_min"] == 10.0 and jul["t_max"] == 30.0   # die Tour ohne Wetter zählt nicht als 0 °C
        assert d["monate"][0]["t_mittel"] == -5.0 and d["monate"][3]["t_mittel"] is None and d["monate"][3]["mit_wetter"] == 0 and d["monate"][3]["touren"] == 8
        s = season(d, "sommer")
        assert s["t_mittel"] == 20.0 and s["mit_wetter"] == 2 and season(d, "fruehling")["t_mittel"] is None and season(d, "winter")["t_mittel"] == -5.0
        w = d["wetter"]
        assert w["mit"] == 3 and w["ohne"] == 9 and w["t_min"] == -8.0 and w["t_max"] == 30.0 and w["t_mittel"] == 11.7
        k = {x["key"]: x for x in w["klassen"]}
        assert [x["key"] for x in w["klassen"]] == ["kalt", "kuehl", "mild", "warm"]
        assert (k["kalt"]["touren"], k["kalt"]["km"]) == (1, 5) and (k["mild"]["touren"], k["mild"]["km"]) == (1, 10) and (k["warm"]["touren"], k["warm"]["km"]) == (1, 20) and k["kuehl"]["touren"] == 0


def test_klassengrenzen():
    for i, (lo, hi) in enumerate([(-1, 1), (-1, 0), (0, 0), (9, 11), (10, 10), (19, 21), (20, 20), (-20, -1)]):          # Mittel 0, -0,5, 0, 10, 10, 20, 20, -10,5
        mk(f"g{i}", ts(2025, 5, 1 + i), wx={"tmin": lo, "tmax": hi})
    with client() as c:
        k = {x["key"]: x["touren"] for x in get(c)["wetter"]["klassen"]}
        assert k == {"kalt": 2, "kuehl": 2, "mild": 2, "warm": 2}


def test_kein_abruf_beim_anzeigen(monkeypatch):
    import requests
    from app import extras

    def boom(*a, **k):
        raise AssertionError("Beim Anzeigen darf kein Wetterdienst gefragt werden")
    monkeypatch.setattr(requests, "get", boom)
    monkeypatch.setattr(extras, "fetch_weather", boom)
    mk("a", ts(2025, 7, 1))
    mk("b", ts(2025, 7, 2), wx={"tmin": 1, "tmax": 3})
    with client() as c:
        d = get(c)
        assert d["wetter"]["mit"] == 1 and d["wetter"]["ohne"] == 1
        assert c.get("/api/bausteine/saison").status_code == 200


def test_filter_aktivitaet_zeitraum_und_fehler():
    mk("h1", ts(2025, 7, 1), km=10, sport="hike")
    mk("m1", ts(2025, 7, 2), km=40, sport="mtb")
    mk("h2", ts(2024, 7, 2), km=7, sport="hike")
    mk("c1", ts(2025, 1, 15), km=3, sport="hike")
    with client() as c:
        assert get(c, sport="mtb")["touren"] == 1 and get(c, sport="mtb")["km"] == 40
        assert get(c, sport="hike,mtb")["touren"] == 4
        d = get(c, zeitraum="y", jahr=2025)
        assert d["touren"] == 3 and d["von"] == "2025-01-01" and d["bis"] == "2025-12-31"
        d = get(c, zeitraum="c", von="2025-07-01", bis="2025-07-01")
        assert d["touren"] == 1 and d["monate"][6]["touren"] == 1
        assert get(c, zeitraum="c", von="2030-01-01", bis="2030-02-01")["touren"] == 0                # leerer Zeitraum: alles 0, keine Fehler
        for q in ({"zeitraum": "x"}, {"sport": "a b"}, {"zeitraum": "c"}, {"zeitraum": "c", "von": "2025-02-01", "bis": "2025-01-01"}, {"zeitraum": "y", "jahr": 1800}, {"zeitraum": "c", "von": "kaputt", "bis": "2025-01-01"}):
            assert c.get("/api/bausteine/saison", params=q).status_code == 400, q


def test_antwort_enthaelt_keine_orte_namen_oder_notizen():
    mk("a", ts(2025, 7, 1), name="Geheimer Gipfel", wx={"tmin": 1, "tmax": 3})
    db.execute("INSERT INTO tour_notes(id,note) VALUES(?,?)", ("a", "Privat"))
    with client() as c:
        txt = c.get("/api/bausteine/saison").text
        assert "Geheimer" not in txt and "Privat" not in txt and "52.5" not in txt and "13.4" not in txt and "lat" not in txt


def test_rechte_betrachter_liest_anonym_nicht_und_benutzer_getrennt():
    from fastapi.testclient import TestClient
    from app import main
    mk("a", ts(2025, 7, 1), km=12)
    with TestClient(main.app) as c:
        assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200
        assert get(c)["touren"] == 1
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        c.post("/api/users", json={"name": "Eva", "email": "eva@example.com", "password": "evas-pass123", "role": "user"})
        assert TestClient(main.app).get("/api/bausteine/saison").status_code in (401, 403)
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert v.get("/api/bausteine/saison").json()["touren"] == 1                                   # Betrachter darf lesen
        assert v.post("/api/bausteine/saison", json={}).status_code in (403, 405)
        e = TestClient(main.app)
        assert e.post("/api/login", json={"name": "eva", "password": "evas-pass123"}).status_code == 200
        assert e.get("/api/bausteine/saison").json()["touren"] == 0                                   # eigene, leere Datenbank
    assert main.VIEWER_GET.match("/api/bausteine/saison")


def test_ausruestung_anteil_am_limit():
    mk("a", ts(2025, 7, 1), km=60)
    db.execute("INSERT INTO gear(name,kind,sports,since,until,limit_km,note) VALUES('Neu','Schuhe','hike','','',600,'')")
    db.execute("INSERT INTO gear(name,kind,sports,since,until,limit_km,note) VALUES('Knapp','Schuhe','hike','','',65,'')")
    db.execute("INSERT INTO gear(name,kind,sports,since,until,limit_km,note) VALUES('Durch','Schuhe','hike','','',50,'')")
    db.execute("INSERT INTO gear(name,kind,sports,since,until,limit_km,note) VALUES('Ohne','Rad','hike','','',0,'')")
    with client() as c:
        g = {x["name"]: x for x in c.get("/api/bausteine/ausruestung").json()}
        assert g["Neu"]["anteil_pct"] == 10 and g["Neu"]["status"] == "ok"
        assert g["Knapp"]["anteil_pct"] == 92 and g["Knapp"]["status"] == "soon"                    # ab 90 % „bald fällig“
        assert g["Durch"]["anteil_pct"] == 120 and g["Durch"]["status"] == "over"                   # über 100 möglich
        assert g["Ohne"]["anteil_pct"] is None and g["Ohne"]["limit_km"] is None


def test_wochen_mit_km_und_aktiven_tagen():
    from tests.test_belastung_tempo import mk as bmk, side, lt
    bmk("w1", lt(2026, 3, 2), "zepp", dist=5000); side("w1", 40)                                     # Montag
    bmk("w2", lt(2026, 3, 4), "zepp", dist=7500); side("w2", 60)                                     # Mittwoch
    bmk("w3", lt(2026, 3, 4, 18), "garmin", dist=2500)                                               # Mittwoch, ohne Uhr-Wert
    r = B.compute("2026-03-02", "2026-03-15", now=datetime(2026, 3, 15, 20, tzinfo=TZ))
    w = {x["key"]: x for x in r["wochen"]}
    assert w["2026-03-02"]["tage"] == "1010000" and w["2026-03-02"]["km"] == 15.0 and w["2026-03-02"]["touren"] == 3 and w["2026-03-02"]["belastung"] == 100
    assert w["2026-03-09"]["tage"] == "0000000" and w["2026-03-09"]["km"] == 0 and w["2026-03-09"]["touren"] == 0 and w["2026-03-09"]["belastung"] is None
    assert len(r["wochen"]) == 2
    bmk("w4", lt(2026, 3, 22), "garmin", dist=12000)                                                 # Sonntag, ohne Uhr-Wert
    r = B.compute("2026-03-02", "2026-03-23", now=datetime(2026, 3, 23, 20, tzinfo=TZ))
    w = {x["key"]: x for x in r["wochen"]}
    assert w["2026-03-16"]["tage"] == "0000001" and w["2026-03-16"]["km"] == 12.0 and w["2026-03-16"]["belastung"] is None and w["2026-03-16"]["ohne_angabe"] == 1   # nie als 0
    assert w["2026-03-09"]["tage"] == "0000000" and w["2026-03-09"]["belastung"] is None


def test_keine_touren_belastung_leer():
    r = B.compute("2026-03-02", "2026-03-15")
    assert r["wochen"] == [] and r["daten_insgesamt"] == 0
