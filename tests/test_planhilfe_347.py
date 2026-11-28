"""3.47.0 Planung ausbauen: Notizen/Links/Quellen am Plan und Entscheidungshilfe „Passt die Tour zu mir?“ (reine Funktionen, Endpunkte, Migration).
Alle Daten erfunden; Links werden nie abgerufen."""
import json
import sqlite3
import sys
import time
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401

BERLIN = ZoneInfo("Europe/Berlin")
KA = (49.0, 8.4)                                           # erfundener Startpunkt (Raum Karlsruhe)
NOW = datetime(2026, 11, 19, 12, 0, tzinfo=BERLIN).timestamp()


@pytest.fixture
def berlin(monkeypatch):
    from app import planhilfe
    monkeypatch.setattr(planhilfe, "TZ", BERLIN)
    return planhilfe


def _t(km, up=300, h=3.0, tage=30, sport="hike"):
    return {"sport": sport, "start_ts": NOW - tage * 86400, "dist_m": km * 1000, "dur_s": h * 3600, "up_m": up}


# ------------------------------------------------------------------------------------------------ Links
@pytest.mark.parametrize("u", ["javascript:alert(1)", "JavaScript:alert(1)", " javascript:alert(1)", "data:text/html,<b>x</b>", "file:///etc/passwd", "ftp://example.org/x", "//example.org/x",
                               "http:///nur-pfad", "https://", "example.org/ohne-schema", "vbscript:x", "https://exa mple.org", "https://a.example/\nx", "https://user:geheim@example.org/",
                               "https://" + "a" * 500 + ".example", "", "   ", None, 5])
def test_url_ungueltig(u):
    from app import planhilfe
    with pytest.raises(ValueError):
        planhilfe.pruefe_url(u)


def test_url_gueltig():
    from app import planhilfe
    assert planhilfe.pruefe_url("  https://www.example.org/tour?id=7#karte ") == "https://www.example.org/tour?id=7#karte"
    assert planhilfe.pruefe_url("HTTP://Example.org:8080/a") == "HTTP://Example.org:8080/a"
    assert planhilfe.pruefe_url("https://" + "a" * 480 + ".example")                       # unter dem Limit von 500


def test_links_pruefen_und_grenzen():
    from app import planhilfe
    out = planhilfe.pruefe_links([{"url": "https://wetter.example/a", "titel": "  Wetter   heute ", "art": "wetter"}, {"url": "https://karte.example/b"}])
    assert out == [{"titel": "Wetter heute", "url": "https://wetter.example/a", "art": "wetter"}, {"titel": "karte.example", "url": "https://karte.example/b", "art": "sonstiges"}]
    assert planhilfe.pruefe_links(None) == [] and planhilfe.pruefe_links([]) == []
    ok20 = [{"url": f"https://example.org/{i}", "titel": "t"} for i in range(20)]
    assert len(planhilfe.pruefe_links(ok20)) == 20
    for bad in (ok20 + [{"url": "https://example.org/21"}],                        # 21 Links
                [{"url": "https://example.org", "titel": "x" * 121}],               # Titel zu lang
                [{"url": "https://example.org", "art": "virus"}],                    # Art unbekannt
                [{"url": "javascript:alert(1)", "titel": "x"}],
                [{"url": "data:text/html;base64,AAAA"}],
                ["https://example.org"], "https://example.org", {"url": "https://example.org"}):
        with pytest.raises(ValueError):
            planhilfe.pruefe_links(bad)
    assert len(planhilfe.pruefe_links([{"url": "https://example.org", "titel": "x" * 120}])[0]["titel"]) == 120


def test_lade_links_filtert_manipuliertes():
    from app import planhilfe
    raw = json.dumps([{"titel": "ok", "url": "https://example.org/", "art": "karte"}, {"titel": "böse", "url": "javascript:alert(1)", "art": "karte"}, 5, {"titel": "x", "url": "https://a.example", "art": "nix"}])
    assert [x["titel"] for x in planhilfe.lade_links(raw)] == ["ok"]
    assert planhilfe.lade_links("kaputt{") == [] and planhilfe.lade_links(None) == [] and planhilfe.lade_links('{"a":1}') == []


def test_quelle_notiz_datum_start_puffer():
    from app import planhilfe as p
    assert p.pruefe_quelle("komoot", "  Tour   12 ") == ("komoot", "Tour 12") and p.pruefe_quelle("", "") == (None, None) and p.pruefe_quelle(None, None) == (None, None)
    for bad in (("raten", ""), ("komoot", "x" * 201), ("komoot", 5)):
        with pytest.raises(ValueError):
            p.pruefe_quelle(*bad)
    assert p.pruefe_notiz(None) == "" and len(p.pruefe_notiz("x" * 4000)) == 4000
    with pytest.raises(ValueError):
        p.pruefe_notiz("x" * 4001)
    assert p.pruefe_datum("2026-12-24") == "2026-12-24" and p.pruefe_datum("") is None
    for bad in ("24.12.2026", "2026-02-30", "2026-13-01", "1999-01-01", "2101-01-01", 5):
        with pytest.raises(ValueError):
            p.pruefe_datum(bad)
    assert p.pruefe_start("07:30") == "07:30" and p.pruefe_start(None) is None
    for bad in ("7:30", "24:00", "07:60", "0730"):
        with pytest.raises(ValueError):
            p.pruefe_start(bad)
    assert p.pruefe_puffer("20") == 20 and p.pruefe_puffer(0) == 0 and p.pruefe_puffer(100) == 100 and p.pruefe_puffer("") is None
    for bad in (-1, 101, "abc", 12.5, float("nan"), True):
        with pytest.raises(ValueError):
            p.pruefe_puffer(bad)


# ------------------------------------------------------------------------------------------------ Form
def test_form_zu_wenig_nie_platzhalter():
    from app import planhilfe
    f = planhilfe.form(12, 400, 4.0, "hike", [_t(10 + i) for i in range(4)], NOW)           # nur 4 Touren
    assert f["status"] == "zu_wenig" and f["n"] == 4 and f["min_n"] == 5 and f["km"] is None and f["up"] is None and f["dauer"] is None
    assert planhilfe.form(12, 400, 4.0, "hike", [], NOW)["n"] == 0


def test_form_filter_sportgruppe_und_zeitraum():
    from app import planhilfe
    tours = [_t(10 + i) for i in range(5)] + [_t(80, sport="racebike") for _ in range(10)] + [_t(60, tage=400) for _ in range(10)]   # Rad und >12 Monate zählen nicht
    f = planhilfe.form(12, 400, 4.0, "hike", tours, NOW)
    assert f["status"] == "ok" and f["n"] == 5
    assert planhilfe.form(12, 400, 4.0, "nordicwalking", tours, NOW)["n"] == 5               # gleiche Sportgruppe „foot“
    assert planhilfe.form(50, 400, 4.0, "racebike", tours, NOW)["n"] == 10
    assert planhilfe.form(12, 400, 4.0, "hike", [dict(t, dist_m=0) for t in tours], NOW)["n"] == 0


def test_form_einordnung_median_perzentil_max():
    from app import planhilfe
    tours = [_t(k, up=u, h=hh) for k, u, hh in ((8, 200, 2.0), (10, 300, 2.5), (12, 400, 3.0), (14, 500, 3.5), (16, 600, 4.0))]       # Median 12 km / 400 m / 3 h, Max 16 / 600 / 4
    f = planhilfe.form(12.0, 400, 3.0, "hike", tours, NOW)
    assert f["km"]["einordnung"] == "aehnlich" and f["km"]["median"] == 12 and f["km"]["perzentil"] == 50 and f["km"]["max_stufe"] == "unter" and f["km"]["vs_max_pct"] == 75
    f = planhilfe.form(9.0, 400, 3.0, "hike", tours, NOW)                                    # 9/12 = 0,75 < 0,8
    assert f["km"]["einordnung"] == "unter" and f["km"]["perzentil"] == 20
    f = planhilfe.form(15.0, 400, 3.0, "hike", tours, NOW)                                   # 15/12 = 1,25 ist noch „ähnlich“
    assert f["km"]["einordnung"] == "aehnlich" and f["km"]["max_stufe"] == "unter" and f["km"]["vs_max_pct"] == 94         # 15/16 = 93,75 % (unter 95 %)
    assert planhilfe.form(15.2, 400, 3.0, "hike", tours, NOW)["km"]["max_stufe"] == "etwa"                                  # 95 %
    f = planhilfe.form(15.1, 400, 3.0, "hike", tours, NOW)
    assert f["km"]["einordnung"] == "ueber"
    f = planhilfe.form(17.0, 650, 4.3, "hike", tours, NOW)                                   # über dem Maximum, aber unter 120 %
    assert f["km"]["max_stufe"] == "ueber" and f["up"]["max_stufe"] == "ueber" and f["dauer"]["max_stufe"] == "ueber" and f["deutlich_ueber"] == []
    f = planhilfe.form(19.3, 700, 5.0, "hike", tours, NOW)                                   # 19,3/16 = 120,6 %, 700/600 = 116 %, 5/4 = 125 %
    assert f["km"]["max_stufe"] == "deutlich_ueber" and f["up"]["max_stufe"] == "ueber" and f["dauer"]["max_stufe"] == "deutlich_ueber" and f["deutlich_ueber"] == ["km", "dauer"]
    f = planhilfe.form(19.2, 400, 3.0, "hike", tours, NOW)                                   # genau 120 % zählt noch nicht als „deutlich“
    assert f["km"]["max_stufe"] == "ueber" and f["deutlich_ueber"] == []
    f = planhilfe.form(16.0, 600, 4.0, "hike", tours, NOW)
    assert f["km"]["max_stufe"] == "etwa" and f["km"]["vs_max_pct"] == 100


def test_form_fehlende_werte_nie_null():
    from app import planhilfe
    tours = [_t(10 + i, up=None if i < 3 else 300 + i, h=0) for i in range(6)]               # nur 3 Touren mit Aufstieg, keine mit Dauer
    f = planhilfe.form(12, 400, 3.0, "hike", tours, NOW)
    assert f["status"] == "ok" and f["km"] and f["up"] is None and f["dauer"] is None            # zu wenig Vergleichswerte → weglassen, nie 0
    f = planhilfe.form(12, None, None, "hike", [_t(10 + i) for i in range(6)], NOW)
    assert f["up"] is None and f["dauer"] is None and f["km"]["wert"] == 12                      # Planwert fehlt → keine Einordnung
    assert planhilfe.form(None, 100, 1, "hike", [_t(10 + i) for i in range(6)], NOW)["km"] is None
    flach = [_t(10 + i, up=0) for i in range(6)]                                              # Median 0: kein Verhältnis, kein Teilen durch 0
    f = planhilfe.form(12, 0, 3.0, "hike", flach, NOW)
    assert f["up"]["einordnung"] == "aehnlich" and f["up"]["verhaeltnis_median_pct"] is None and f["up"]["vs_max_pct"] == 100
    f = planhilfe.form(12, 150, 3.0, "hike", flach, NOW)
    assert f["up"]["einordnung"] == "ueber" and f["up"]["vs_max_pct"] is None and f["up"]["max_stufe"] == "deutlich_ueber"


# ------------------------------------------------------------------------------------------------ Tageslicht
def test_tageslicht_sommer_winter_gegen_baustein(berlin):
    from app import bausteine_daten
    for tag, (a_lo, a_hi, u_lo, u_hi) in {date(2026, 6, 21): (318, 330, 1285, 1297), date(2026, 12, 21): (490, 505, 985, 997)}.items():        # Karlsruhe: 05:24/21:32 Uhr bzw. 08:17/16:31 Uhr, ±6 min
        t = berlin.tageslicht(*KA, tag.isoformat(), "09:00", 4.0, 20, date(2026, 11, 19))
        assert t["status"] == "ok" and a_lo <= t["aufgang_min"] <= a_hi and u_lo <= t["untergang_min"] <= u_hi, t
        ref = bausteine_daten.tageslicht(datetime(tag.year, tag.month, tag.day, 9, 0, tzinfo=BERLIN).timestamp(), None, *KA)        # derselbe Rechenkern wie der Baustein
        assert abs(ref["aufgang_min"] - t["aufgang_min"]) <= 1 and abs(ref["untergang_min"] - t["untergang_min"]) <= 1
        assert t["daemm_bis_min"] > t["untergang_min"] and t["zeitzone"] == "Europe/Berlin"


def test_tageslicht_zeitumstellung_ortszeit(berlin):
    t = berlin.tageslicht(*KA, "2026-03-29", "09:00", 4.0, 20, date(2026, 11, 19))             # Sommerzeit beginnt an diesem Tag um 02:00
    assert t["status"] == "ok" and 415 <= t["aufgang_min"] <= 440, t                              # ≈ 07:05 MESZ (nicht 06:05)
    assert 1170 <= t["untergang_min"] <= 1200                                                  # ≈ 19:40 MESZ
    # Dauer über die Umstellung: 00:00 + 4 h absolute Zeit = 05:00 Ortszeit (eine Stunde fehlt)
    u = berlin.tageslicht(*KA, "2026-03-29", "00:00", 4.0, 0, date(2026, 11, 19))
    assert u["rueckkehr_min"] == 5 * 60 and u["rueckkehr_tag_plus"] == 0
    h = berlin.tageslicht(*KA, "2026-10-25", "00:00", 4.0, 0, date(2026, 11, 19))             # Sommerzeit endet: 04:00 absolut = 03:00 Ortszeit
    assert h["rueckkehr_min"] == 3 * 60


def test_tageslicht_ampel_grenzen(berlin):
    d = "2026-06-21"
    ref = berlin.tageslicht(*KA, d, "09:00", 4.0, 20, date(2026, 11, 19))
    sunset = ref["untergang_min"]

    def mit_reserve(res):                                                                       # Dauer so wählen, dass die Rückkehr `res` Minuten vor Sonnenuntergang liegt (Puffer 20 %)
        return berlin.tageslicht(*KA, d, "09:00", ((sunset - res - 540) / 1.2) / 60.0, 20, date(2026, 11, 19))
    for res, ampel in ((90, "reserve"), (61, "reserve"), (59, "knapp"), (1, "knapp"), (-1, "nach_untergang"), (-45, "nach_untergang")):
        t = mit_reserve(res)
        assert t["ampel"] == ampel and abs(t["reserve_min"] - res) <= 1, (res, t)
    t = mit_reserve(90)
    assert t["start_vor_aufgang"] is False and t["start_nach_untergang"] is False
    assert berlin.tageslicht(*KA, d, "04:00", 4.0, 20, date(2026, 11, 19))["start_vor_aufgang"] is True
    assert berlin.tageslicht(*KA, d, "22:30", 1.0, 20, date(2026, 11, 19))["start_nach_untergang"] is True


def test_tageslicht_standardwerte_und_mitternacht(berlin):
    heute = date(2026, 6, 21)
    t = berlin.tageslicht(*KA, None, None, 5.0, None, heute)
    assert t["datum"] == "2026-06-21" and t["start"] == "09:00" and t["puffer_pct"] == 20 and not (t["datum_gewaehlt"] or t["start_gewaehlt"] or t["puffer_gewaehlt"])
    assert t["start_min"] == 540 and t["dauer_min"] == 300 and t["puffer_min"] == 60 and t["rueckkehr_min"] == 540 + 360 and t["rueckkehr_tag_plus"] == 0
    n = berlin.tageslicht(*KA, "2026-06-21", "20:00", 6.0, 0, heute)
    assert n["rueckkehr_min"] == 120 and n["rueckkehr_tag_plus"] == 1 and n["ampel"] == "nach_untergang"
    assert berlin.tageslicht(*KA, "2026-06-21", "09:00", 5.0, 0, heute)["puffer_min"] == 0


def test_tageslicht_polar_position_dauer(berlin):
    heute = date(2026, 11, 19)
    assert berlin.tageslicht(78.2, 15.6, "2026-06-21", "09:00", 4.0, 20, heute)["status"] == "polar_tag"
    assert berlin.tageslicht(78.2, 15.6, "2026-12-21", "09:00", 4.0, 20, heute)["status"] == "polar_nacht"
    assert berlin.tageslicht(-78.2, 15.6, "2026-12-21", "09:00", 4.0, 20, heute)["status"] == "polar_tag"            # Südhalbkugel: umgekehrt
    assert "rueckkehr_min" in berlin.tageslicht(78.2, 15.6, "2026-06-21", "09:00", 4.0, 20, heute)
    for lat, lng in ((None, 8.0), (49.0, None), (0, 0), (91, 8), (49, 181)):
        assert berlin.tageslicht(lat, lng, None, None, 4.0, None, heute) == {"status": "keine_position"}
    for dauer in (None, 0, -1):
        assert berlin.tageslicht(*KA, None, None, dauer, None, heute)["status"] == "keine_dauer"


# ------------------------------------------------------------------------------------------------ Endpunkte und Speichern
def _plan(**kw):
    from app import plan
    d = {"name": "Testrunde", "sport": "hike", "pts": [[49.0 + 0.001 * i, 8.4 + 0.001 * i] for i in range(10)], "km": 14.0, "up": 500, "down": 500, "est_h": 4.0, "note": "Anfahrt mit der Bahn"}
    d.update(kw)
    return plan.api_plan_save(d)["id"]


def test_speichern_links_quelle_und_lesen():
    from app import plan
    pid = _plan(links=[{"titel": "Lawinenbericht", "url": "https://lawine.example/bericht", "art": "wetter"}, {"url": "https://fuehrer.example/s12", "art": "fuehrer"}], quelle="outdooractive", quelle_text="Tour 4711",
                plan_datum="2026-12-24", plan_start="08:15", puffer_pct=30)
    p = plan.api_plan_get(pid)
    assert [x["art"] for x in p["links"]] == ["wetter", "fuehrer"] and p["quelle"] == "outdooractive" and p["quelle_text"] == "Tour 4711"
    assert (p["plan_datum"], p["plan_start"], p["puffer_pct"]) == ("2026-12-24", "08:15", 30) and p["note"] == "Anfahrt mit der Bahn"
    row = plan.api_plans()[0]
    assert row["n_links"] == 2 and row["has_note"] is True and "links" not in row                   # Liste: nur Anzahl und Marker
    plan.api_plan_save({"id": pid, "name": "Neu", "pts": [[49, 8.4], [49.1, 8.5]], "note": "  "})   # ältere Aufrufer ohne die neuen Felder: nichts geht verloren
    p = plan.api_plan_get(pid)
    assert len(p["links"]) == 2 and p["quelle"] == "outdooractive" and p["plan_datum"] == "2026-12-24" and p["puffer_pct"] == 30
    assert plan.api_plans()[0]["has_note"] is False
    plan.api_plan_save({"id": pid, "name": "Neu", "pts": [[49, 8.4], [49.1, 8.5]], "links": [], "quelle": "", "quelle_text": "", "plan_datum": "", "plan_start": "", "puffer_pct": ""})
    p = plan.api_plan_get(pid)
    assert p["links"] == [] and p["quelle"] is None and p["plan_datum"] is None and p["puffer_pct"] is None


def test_speichern_lehnt_boeses_ab():
    from fastapi import HTTPException
    from app import plan
    pid = _plan(links=[{"url": "https://ok.example/", "titel": "ok"}])
    for kw in ({"links": [{"url": "javascript:alert(1)", "titel": "x"}]}, {"links": [{"url": "data:text/html,x"}]}, {"links": [{"url": "https://e.example"}] * 21},
               {"links": [{"url": "https://e.example", "titel": "t" * 121}]}, {"note": "n" * 4001}, {"quelle": "böse"}, {"quelle_text": "q" * 201},
               {"plan_datum": "morgen"}, {"plan_start": "25:00"}, {"puffer_pct": 500}):
        with pytest.raises(HTTPException) as e:
            _plan(**kw)
        assert e.value.status_code == 400, kw
        with pytest.raises(HTTPException):
            plan.api_plan_save({"id": pid, "name": "x", "pts": [[49, 8.4], [49.1, 8.5]], **kw})
    assert len(plan.api_plan_get(pid)["links"]) == 1 and len(plan.api_plans()) == 1             # nichts Halbes gespeichert


def test_links_werden_nie_abgerufen(monkeypatch):
    import requests
    from app import plan, planhilfe

    def boom(*a, **k):
        raise AssertionError("Netzzugriff")
    monkeypatch.setattr(requests, "get", boom)
    monkeypatch.setattr(requests, "head", boom)
    monkeypatch.setattr(requests, "post", boom)
    pid = _plan(links=[{"url": "https://wetter.example/x", "art": "wetter"}])
    plan.api_plan_get(pid)
    plan.api_plans()
    plan.api_plan_hilfe(pid)
    assert "requests" not in planhilfe.__dict__ and "urlopen" not in open(planhilfe.__file__).read()


def test_hilfe_endpunkt(monkeypatch):
    from fastapi import HTTPException
    from app import db, plan, planhilfe
    monkeypatch.setattr(planhilfe, "TZ", BERLIN)
    now = time.time()
    for i in range(6):
        db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                   (f"x{i}", f"Runde {i}", "hike", now - (10 + 7 * i) * 86400, now - (10 + 7 * i) * 86400 + 100, (10 + i) * 1000, 3.0 * 3600, 300 + 50 * i, 300, 49.0, 8.4, "tour_recorded", "komoot"))
    pid = _plan(km=14.0, up=500, est_h=3.5, links=[{"titel": "Lawine", "url": "https://lawine.example/", "art": "wetter"}, {"titel": "Hütte", "url": "https://huette.example/", "art": "huette"}])
    h = plan.api_plan_hilfe(pid, datum="2026-06-21", start="09:00", puffer="20")
    assert h["plan"]["id"] == pid and h["form"]["status"] == "ok" and h["form"]["n"] == 6 and h["form"]["km"]["einordnung"] in ("aehnlich", "ueber", "unter")
    assert h["tageslicht"]["status"] == "ok" and h["tageslicht"]["ampel"] == "reserve" and h["tageslicht"]["dauer_quelle"] == "plan"
    assert [x["titel"] for x in h["wetter_links"]] == ["Lawine"]                                  # nur Quellen der Art Wetter/Lawinenbericht
    h2 = plan.api_plan_hilfe(pid, datum="", start="", puffer="")                                  # leer = Standard (heute, 09:00, 20 %)
    assert h2["tageslicht"]["datum_gewaehlt"] is False and h2["tageslicht"]["start"] == "09:00" and h2["tageslicht"]["puffer_pct"] == 20
    for kw in ({"datum": "x"}, {"start": "99:99"}, {"puffer": "-4"}):
        with pytest.raises(HTTPException) as e:
            plan.api_plan_hilfe(pid, **kw)
        assert e.value.status_code == 400
    with pytest.raises(HTTPException) as e:
        plan.api_plan_hilfe(9999)
    assert e.value.status_code == 404
    assert plan.api_plan_get(pid)["plan_datum"] is None                                           # Überschreiben speichert nichts
    plan.api_plan_save({"id": pid, "name": "x", "pts": [[49, 8.4], [49.1, 8.5]], "plan_datum": "2026-12-21", "plan_start": "07:00", "puffer_pct": 50})
    t = plan.api_plan_hilfe(pid)["tageslicht"]
    assert (t["datum"], t["start"], t["puffer_pct"]) == ("2026-12-21", "07:00", 50) and t["datum_gewaehlt"] and t["puffer_gewaehlt"]


def test_hilfe_dauer_fallback_und_ohne_dauer(monkeypatch):
    from app import plan, planhilfe
    monkeypatch.setattr(planhilfe, "TZ", BERLIN)
    pid = _plan(est_h=None, km=10.0, up=400, down=400)
    h = plan.api_plan_hilfe(pid, datum="2026-06-21")
    assert h["tageslicht"]["dauer_quelle"] == "gehzeit" and h["tageslicht"]["status"] == "ok" and h["form"]["status"] == "zu_wenig" and h["form"]["dauer"] is None
    pid2 = _plan(est_h=None, km=None, up=None, down=None, sport="racebike")                       # keine Dauer, nichts zu schätzen
    assert plan.api_plan_hilfe(pid2)["tageslicht"]["status"] == "keine_dauer"


def test_belastungskontext_nur_mit_daten():
    from app import planhilfe
    assert planhilfe.belastungskontext() is None                                                  # keine Touren/Uhr-Werte: weglassen


# ------------------------------------------------------------------------------------------------ Migration
def test_migration_alter_plaene(tmp_path):
    from app import db
    f = tmp_path / "alt.db"
    c = sqlite3.connect(f)
    c.execute("CREATE TABLE plans (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, sport TEXT, pts TEXT, km REAL, up REAL, down REAL, max_alt REAL, est_h REAL, note TEXT, ts INTEGER, wps TEXT, tour_id TEXT, status TEXT NOT NULL DEFAULT 'geplant')")
    c.execute("INSERT INTO plans(name,sport,pts,km,up,est_h,note,ts,status) VALUES('Alte Runde','hike','[[49,8.4],[49.1,8.5]]',9.5,300,3,'Alte Notiz',1700000000,'gegangen')")
    c.commit()
    c.close()
    c = sqlite3.connect(f)
    c.row_factory = sqlite3.Row
    db.migrate(c)
    db.migrate(c)                                                                                  # zweimal: idempotent
    cols = {r["name"] for r in c.execute("PRAGMA table_info(plans)")}
    assert {"links", "quelle", "quelle_text", "plan_datum", "plan_start", "puffer_pct"} <= cols
    r = dict(c.execute("SELECT * FROM plans").fetchone())
    assert r["name"] == "Alte Runde" and r["note"] == "Alte Notiz" and r["status"] == "gegangen" and r["km"] == 9.5
    assert all(r[k] is None for k in ("links", "quelle", "quelle_text", "plan_datum", "plan_start", "puffer_pct"))
    c.close()
    from app import planhilfe
    assert planhilfe.lade_links(r["links"]) == []
    h = planhilfe.hilfe(r, now_ts=NOW, tours=[])                                                    # alter Plan: Hilfe funktioniert mit Standardwerten
    assert h["tageslicht"]["start"] == "09:00" and h["form"]["status"] == "zu_wenig"


def test_version_und_cache():
    from app import config
    root = Path(__file__).resolve().parent.parent
    assert config.VERSION.startswith("3.71.1 · Meine Touren")
    assert 'const V = "mt-v163"' in (root / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    assert (root / "docs" / "versionen" / "3.47.0.md").exists()
    assert "## Version 3.47.0" in (root / "docs" / "VERSIONSVERLAUF.md").read_text(encoding="utf-8")
    assert 'const SL_APPV = "3.71.1"' in (root / "app" / "static" / "js" / "54-ansichten.js").read_text(encoding="utf-8")
