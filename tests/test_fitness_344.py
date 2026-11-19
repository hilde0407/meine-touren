"""3.44.0 Fitness-Einordnung: reine Funktionen (app/fitness.py) und Endpunkte GET /api/fitness, PUT/DELETE /api/fitness/geburtsjahr.
Grenzfälle, kein Alter, wenig Daten, Puls vorhanden/nicht, Alterseffekt, Trend; Geburtsjahr setzen/ändern/ungültig/entfernen, fremdes Konto, Betrachter, Anmeldung, kein Leck in Freigaben und Einstellungen.
Alle Testdaten sind erfunden und relativ zu „heute“ gebaut."""
import json
import time
from datetime import date, timedelta

import pytest

from tests.test_core import fresh  # noqa: F401

HEUTE = date.today()


def _tour(vor_tagen, dauer_s=3600, up_m=None, hist=None):
    return {"tag": HEUTE - timedelta(days=vor_tagen), "dauer_s": dauer_s, "up_m": up_m, "hist": hist}


def _jede_woche(n_je_woche=2, dauer_s=3600, ab=0, wochen=12, **kw):
    return [_tour(ab + 7 * w + k, dauer_s, **kw) for w in range(wochen) for k in range(n_je_woche)]


# ------------------------------------------------------------------------------------------------ Teilwerte
def test_umfang_grenzen():
    from app import fitness as f
    assert f.teilwert_umfang(0) == 0 and f.teilwert_umfang(150) == 70 and f.teilwert_umfang(300) == 100 and f.teilwert_umfang(900) == 100
    assert f.teilwert_umfang(75) == 35 and f.teilwert_umfang(225) == 85
    assert f.teilwert_umfang(None) is None and f.teilwert_umfang(-5) is None and f.teilwert_umfang(float("nan")) is None


def test_regelmaessigkeit():
    from app import fitness as f
    assert f.teilwert_regel([2] * 12) == 100
    assert f.teilwert_regel([0] * 12) is None and f.teilwert_regel([]) is None
    einmal = f.teilwert_regel([1] + [0] * 11)
    assert 0 <= einmal <= 10                                  # eine Tour in 12 Wochen: kaum regelmäßig
    jede = f.teilwert_regel([1] * 12)
    ungleich = f.teilwert_regel([3, 0, 3, 0, 3, 0, 3, 0, 3, 0, 3, 0])
    assert jede == 100 and ungleich == 35 and ungleich < jede


def test_geburtsjahr_pruefen():
    from app import fitness as f
    y = HEUTE.year
    assert f.pruefe_jahr(y - 10, HEUTE) == y - 10 and f.pruefe_jahr(str(y - 110), HEUTE) == y - 110 and f.pruefe_jahr(" 1980 ", HEUTE) == 1980
    for bad in (y - 9, y - 111, y, 0, -1980, "abc", "", None, True, 1980.5, [1980], {"a": 1}):
        with pytest.raises(ValueError):
            f.pruefe_jahr(bad, HEUTE)


def test_hfmax_tanaka_und_alter():
    from app import fitness as f
    assert f.hfmax(30) == pytest.approx(187.0) and f.hfmax(70) == pytest.approx(159.0)
    assert f.alter(HEUTE.year - 52, HEUTE) == 52


def test_puls_zu_wenig_daten_und_filter():
    from app import fitness as f
    assert f.teilwert_puls({}, 40) is None and f.teilwert_puls(None, 40) is None
    assert f.teilwert_puls({120: 599}, 40) is None                       # unter 10 Minuten
    assert f.teilwert_puls({5: 3600, 400: 3600}, 40) is None            # unplausible Werte zählen nicht
    p = f.teilwert_puls({120: 600}, 40)
    assert p and p["sekunden"] == 600 and p["mittel_bpm"] == 120


def test_aufstieg_nur_mit_aufstieg_und_zeit():
    from app import fitness as f
    assert f.teilwert_aufstieg(0, 7200, 40) is None and f.teilwert_aufstieg(None, 7200, 40) is None and f.teilwert_aufstieg(300, 1800, 40) is None
    r = f.teilwert_aufstieg(300, 3600, 30)
    assert r["m_h"] == 300 and r["ref_m_h"] == 400 and r["wert"] == 75
    assert f.faktor_alter(20) == 1 and f.faktor_alter(30) == 1 and f.faktor_alter(70) == pytest.approx(0.6) and f.faktor_alter(110) == 0.5


# ------------------------------------------------------------------------------------------------ Gesamteinordnung
def test_ohne_geburtsjahr_nie_platzhalter():
    from app import fitness as f
    r = f.berechne(_jede_woche(), None, HEUTE)
    assert r == {"status": "kein_geburtsjahr"}


def test_keine_touren_und_keine_aktuellen():
    from app import fitness as f
    a = f.berechne([], 1974, HEUTE)
    assert a["status"] == "keine_touren" and a["alter"] == HEUTE.year - 1974 and "gesamt" not in a and "umfang" not in a
    alt = [_tour(200), _tour(210)]
    b = f.berechne(alt, 1974, HEUTE)
    assert b["status"] == "keine_aktuellen" and "gesamt" not in b


def test_zu_wenig_daten_keine_nullen():
    from app import fitness as f
    t = [_tour(3 + 7 * w, dauer_s=None) for w in range(12)]               # Touren ohne Dauer, ohne Aufstieg, ohne Puls: nur die Regelmäßigkeit steht
    r = f.berechne(t, 1980, HEUTE)
    assert r["status"] == "zu_wenig" and "gesamt" not in r
    assert r["umfang"] == {"wert": None, "status": "keine_daten"} and r["intensitaet"] == {"wert": None, "status": "keine_daten"}
    assert r["regel"]["wert"] == 100 and r["regel"]["wochen_aktiv"] == 12


def test_gesamt_ist_mittel_der_vorhandenen_teile_und_klassen():
    from app import fitness as f
    t = _jede_woche(2, 3600 * 2, up_m=900)                                 # 2 x 2 h je Woche = 240 min, jede Woche, 450 m/h
    r = f.berechne(t, HEUTE.year - 30, HEUTE)
    assert r["status"] == "ok" and r["umfang"]["wert"] == 88 and r["regel"]["wert"] == 100 and r["intensitaet"]["quelle"] == "aufstieg" and r["intensitaet"]["wert"] == 100
    assert r["gesamt"] == round((88 + 100 + 100) / 3) and r["einordnung"] == "sehr_aktiv"
    assert r["von"] and r["bis"] == HEUTE.isoformat() and r["wochen"] == 12
    # nur zwei Teile (kein Aufstieg): Mittel aus zwei
    r2 = f.berechne(_jede_woche(2, 3600 * 2), 1980, HEUTE)
    assert r2["intensitaet"]["wert"] is None and r2["gesamt"] == round((88 + 100) / 2)
    for g, k in ((100, "sehr_aktiv"), (80, "sehr_aktiv"), (79, "gut"), (60, "gut"), (59, "solide"), (40, "solide"), (39, "ausbaufaehig"), (0, "ausbaufaehig")):
        assert f.klasse(g) == k


def test_alterseffekt_puls_gleiche_tour_30_gegen_70():
    """Gleicher Puls (110 bpm, eine Stunde je Tour): bei 30 Jahren (HFmax 187) 59 % = unter der 60-%-Grenze, bei 70 Jahren (HFmax 159) 69 % = im Bereich."""
    from app import fitness as f
    t = _jede_woche(1, 3600, hist={110: 3600})
    jung = f.berechne(t, HEUTE.year - 30, HEUTE)["intensitaet"]
    alt = f.berechne(t, HEUTE.year - 70, HEUTE)["intensitaet"]
    assert jung["quelle"] == alt["quelle"] == "puls"
    assert jung["hfmax"] == 187 and alt["hfmax"] == 159
    assert jung["mittel_pct"] == 59 and alt["mittel_pct"] == 69 and jung["mittel_bpm"] == alt["mittel_bpm"] == 110
    assert jung["wert"] == 0 and alt["wert"] == 100


def test_alterseffekt_aufstieg_gleiche_tour_30_gegen_70():
    """Ohne Puls: 300 m je Stunde sind bei 30 Jahren (Richtwert 400) 75, bei 70 Jahren (Richtwert 240) 100."""
    from app import fitness as f
    t = _jede_woche(1, 3600, up_m=300)
    jung = f.berechne(t, HEUTE.year - 30, HEUTE)["intensitaet"]
    alt = f.berechne(t, HEUTE.year - 70, HEUTE)["intensitaet"]
    assert jung["quelle"] == alt["quelle"] == "aufstieg" and jung["wert"] == 75 and alt["wert"] == 100 and jung["ref_m_h"] == 400 and alt["ref_m_h"] == 240


def test_puls_gemischt_anteil_im_bereich():
    from app import fitness as f
    # 40 Jahre: HFmax 180 -> Bereich 108 bis 162 bpm; die Hälfte der Zeit im Bereich
    t = _jede_woche(1, 3600, hist={100: 1800, 140: 1800})
    p = f.berechne(t, HEUTE.year - 40, HEUTE)["intensitaet"]
    assert p["hfmax"] == 180 and p["wert"] == 50 and p["zone_pct"] == 50


def test_trend_pfeile_und_ohne_vorzeitraum():
    from app import fitness as f
    gut = _jede_woche(2, 3600 * 2)                                         # letzte 12 Wochen: stark
    schwach = _jede_woche(1, 1800, ab=84, wochen=6)                        # Vorzeitraum: wenig (nur jede Woche der ersten sechs)
    r = f.berechne(gut + schwach, 1980, HEUTE)
    assert r["status"] == "ok" and r["trend"] == "up" and r["vorher"] is not None and r["vorher"] < r["gesamt"] - 5
    r = f.berechne(schwach_jetzt := _jede_woche(1, 1800, wochen=6) + _jede_woche(2, 3600 * 2, ab=84), 1980, HEUTE)
    assert r["trend"] == "down" and schwach_jetzt
    r = f.berechne(_jede_woche(2, 3600 * 2) + _jede_woche(2, 3600 * 2, ab=84), 1980, HEUTE)
    assert r["trend"] == "flat"
    r = f.berechne(gut, 1980, HEUTE)
    assert r["trend"] is None and r["vorher"] is None                     # Vorzeitraum ohne Daten: kein Pfeil


def test_fenstergrenzen_84_tage():
    from app import fitness as f
    # Tour genau am 84. Tag (vor 83 Tagen) zählt, vor 84 Tagen nicht mehr
    assert f.berechne([_tour(83, 3600)], 1980, HEUTE)["touren"] == 1
    assert f.berechne([_tour(84, 3600)], 1980, HEUTE)["status"] == "keine_aktuellen"


# ------------------------------------------------------------------------------------------------ Endpunkte
def _c():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _setup(c):
    assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200


def _uid(c):
    return c.get("/api/me").json()["user"]["uid"]


def _tour_db(c, tid, tage, dur=7200, up=500):
    from app import ctx, db
    with ctx.as_user(_uid(c)):
        _tour_ins(db, tid, tage, dur, up)


def _tour_ins(db, tid, tage, dur, up):
    ts = int(time.time()) - tage * 86400
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,?,?,'t','local')", (tid, "Testrunde " + tid, "hike", ts, ts + dur, 9000, dur, up, up))


def test_geburtsjahr_setzen_aendern_ungueltig_entfernen(fresh):
    from app import db
    with _c() as c:
        _setup(c)
        assert c.get("/api/fitness").json() == {"status": "kein_geburtsjahr"}
        y = HEUTE.year
        for bad in ({"jahr": 1800}, {"jahr": y}, {"jahr": y - 9}, {"jahr": "abc"}, {"jahr": None}, {"jahr": 1980.5}, {"jahr": True}, {}, {"x": 1}):
            r = c.put("/api/fitness/geburtsjahr", json=bad)
            assert r.status_code == 400, bad
        assert c.put("/api/fitness/geburtsjahr", content=b"kaputt", headers={"content-type": "application/json"}).status_code == 400
        assert c.put("/api/fitness/geburtsjahr", json=[1980]).status_code == 400
        from app import ctx
        with ctx.as_user(_uid(c)):
            assert db.get("birth_year") == ""
        assert c.get("/api/fitness").json() == {"status": "kein_geburtsjahr"}        # nach Fehlern nichts gespeichert
        assert c.put("/api/fitness/geburtsjahr", json={"jahr": 1974}).status_code == 200
        d = c.get("/api/fitness").json()
        assert d["status"] == "keine_touren" and d["geburtsjahr"] == 1974 and d["alter"] == y - 1974
        assert c.put("/api/fitness/geburtsjahr", json={"jahr": str(y - 40)}).status_code == 200 and c.get("/api/fitness").json()["alter"] == 40
        assert c.put("/api/fitness/geburtsjahr", json={"jahr": y - 111}).status_code == 400 and c.get("/api/fitness").json()["alter"] == 40
        assert c.delete("/api/fitness/geburtsjahr").status_code == 200
        assert c.get("/api/fitness").json() == {"status": "kein_geburtsjahr"}


def test_einordnung_mit_touren_ueber_den_endpunkt(fresh):
    from app import db
    with _c() as c:
        _setup(c)
        for w in range(12):
            _tour_db(c, f"f{w}", 3 + 7 * w)
        c.put("/api/fitness/geburtsjahr", json={"jahr": HEUTE.year - 40})
        d = c.get("/api/fitness").json()
        assert d["status"] == "ok" and d["touren"] == 12 and d["regel"]["wert"] == 100 and d["umfang"]["min_woche"] == 120.0 and d["umfang"]["wert"] == 56
        assert d["intensitaet"]["quelle"] == "aufstieg" and d["intensitaet"]["m_h"] == 250
        assert d["einordnung"] in ("sehr_aktiv", "gut", "solide", "ausbaufaehig") and d["trend"] is None


def test_geburtsjahr_nicht_in_einstellungen_freigaben_und_fremdem_konto(fresh):
    from app import db
    with _c() as c:
        _setup(c)
        _tour_db(c, "s1", 5)
        assert c.put("/api/fitness/geburtsjahr", json={"jahr": 1961}).status_code == 200
        # nicht über die Einstellungen les- oder schreibbar
        s = c.get("/api/settings").json()
        assert "birth_year" not in s and "geburtsjahr" not in json.dumps(s).lower() and "1961" not in json.dumps(s)
        c.post("/api/settings", json={"birth_year": "1900"})
        from app import ctx
        with ctx.as_user(_uid(c)):
            assert db.get("birth_year") == "1961"
        # öffentliche Freigabe (Tour) enthält nichts davon
        r = c.post("/api/tours/s1/share", json={"blocks": ["karte"]})
        assert r.status_code == 200, r.text
        tok = r.json()["token"]
        anon = _c()
        p = anon.get(f"/api/public/{tok}")
        assert p.status_code == 200 and "1961" not in p.text and "geburt" not in p.text.lower() and "fitness" not in p.text.lower()
        assert anon.get("/api/fitness").status_code == 401 and anon.put("/api/fitness/geburtsjahr", json={"jahr": 1990}).status_code == 401
        # zweites Konto sieht es nicht und kann es unabhängig setzen
        assert c.post("/api/users", json={"name": "Eva", "email": "eva@example.com", "password": "evas-pass123", "role": "user"}).status_code == 200
        e = _c()
        assert e.post("/api/login", json={"name": "eva", "password": "evas-pass123"}).status_code == 200
        assert e.get("/api/fitness").json() == {"status": "kein_geburtsjahr"}
        assert e.put("/api/fitness/geburtsjahr", json={"jahr": 1999}).status_code == 200 and e.get("/api/fitness").json()["geburtsjahr"] == 1999
        assert c.get("/api/fitness").json()["geburtsjahr"] == 1961


def test_betrachter_darf_weder_lesen_noch_schreiben(fresh):
    from app import main
    assert not main.VIEWER_GET.match("/api/fitness") and not main.VIEWER_GET.match("/api/fitness/geburtsjahr")
    with _c() as c:
        _setup(c)
        c.put("/api/fitness/geburtsjahr", json={"jahr": 1961})
        assert c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"}).status_code == 200
        v = _c()
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert v.get("/api/fitness").status_code == 403
        assert v.put("/api/fitness/geburtsjahr", json={"jahr": 1990}).status_code == 403 and v.delete("/api/fitness/geburtsjahr").status_code == 403
        assert "1961" not in v.get("/api/settings").text
        assert c.get("/api/fitness").json()["geburtsjahr"] == 1961


def test_freigabe_praefixe_schliessen_fitness_nicht_ein():
    from app import more2
    assert not "/api/fitness".startswith(tuple(more2.PUBLIC_PREFIXES))
