"""3.35.0 – Eigene Kennzahl weiterentwickelt, Server: Vergleichsart (Vorjahr/Vormonat), Differenz und Richtung, Ziel mit linearem Soll („im Plan“), Verlauf je Woche/Monat/Jahr,
strenge Prüfung der neuen Felder (vglart, plan, spark, touren), Betrachter und Version. Testdaten: seed() aus test_statistik.py (heute = 2026-11-15)."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from tests.test_statistik import HEUTE, client, mk, seed  # noqa: E402
from app import kennzahl as kz  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def cfg(**k):
    return {"title": "T", "mess": "km", "agg": "sum", "range": "all", **k}


def ausw(**k):
    return kz.auswerten(cfg(**k), HEUTE)


def test_vergleich_vorjahr_vormonat_differenz_und_richtung():
    seed()                                                  # 2026: 12 + 40 + 28 = 80 km; 2025: 5 (Mai) + 60 (Nov) = 65 km
    v = ausw(range="year", vgl=True, vglart="jahr")["vorher"]
    assert v["art"] == "jahr" and v["von"] == "2025-01-01" and v["bis"] == "2025-11-15" and v["wert"] == 65 and v["diff"] == 15 and v["pct"] == 23.1 and v["dir"] == "auf"
    d = ausw(range="year", vgl=True)["vorher"]                                          # Standard: unverändert wie vor 3.35.0
    assert d["art"] == "davor" and d["wert"] == 65 and d["pct"] == 23.1
    m = ausw(range="c", vgl=True, vglart="monat", **{"from": "2026-03-01", "to": "2026-03-31"})["vorher"]
    assert m["von"] == "2026-02-01" and m["bis"] == "2026-02-28" and m["wert"] == 0 and m["pct"] is None and m["diff"] == 52 and m["dir"] == "auf"      # Vormonat leer: Differenz statt Prozent
    mk("f", date(2025, 3, 3), "hike", 52.2)                                              # März 2025: 52,2 km gegen 52 km im März 2026
    g = ausw(range="c", vgl=True, vglart="jahr", **{"from": "2026-03-01", "to": "2026-03-31"})["vorher"]
    assert g["wert"] == 52.2 and g["pct"] == -0.4 and g["dir"] == "gleich" and g["diff"] == -0.2                  # unter ±0,5 %: „gleich“
    mk("g", date(2025, 3, 20), "hike", 100)
    ab = ausw(range="c", vgl=True, vglart="jahr", **{"from": "2026-03-01", "to": "2026-03-31"})["vorher"]
    assert ab["dir"] == "ab" and ab["pct"] < 0 and ab["diff"] < 0
    assert ausw(range="all", vgl=True, vglart="jahr")["vorher"] is None                  # gesamte Zeit: kein Vergleichszeitraum
    s = ausw(range="c", vgl=True, vglart="jahr", **{"from": "2024-02-29", "to": "2024-03-10"})["vorher"]
    assert s["von"] == "2023-02-28" and s["bis"] == "2023-03-10"                         # Schalttag wird angepasst


def test_ziel_mit_linearem_soll():
    seed()                                                  # 2026 bis 15.11.: 80 km, Tag 319 von 365 = 87,4 %
    z = ausw(range="year", ziel=100, plan=True)["ziel"]
    assert z["ziel"] == 100 and z["pct"] == 80 and z["soll_pct"] == 87.4 and z["soll"] == 87.3973 and z["plan"] == "zurueck"
    assert ausw(range="year", ziel=90, plan=True)["ziel"]["plan"] == "im_plan"          # Soll 78,7: innerhalb von 5 % darüber
    assert ausw(range="year", ziel=80, plan=True)["ziel"]["plan"] == "voraus"           # Soll 69,9
    assert "soll" not in ausw(range="year", ziel=100)["ziel"]                           # ohne plan: wie bisher
    assert ausw(range="year", ziel=100)["ziel"] == {"ziel": 100, "pct": 80.0}
    # Zeiträume: ganzes vergangenes Jahr = 100 %, laufender eigener Bereich anteilig, sonst kein Soll
    assert ausw(range="y", yr=2025, ziel=100, plan=True)["ziel"]["soll_pct"] == 100.0 and ausw(range="y", yr=2025, ziel=100, plan=True)["ziel"]["plan"] == "zurueck"
    assert ausw(range="c", ziel=100, plan=True, **{"from": "2026-11-01", "to": "2026-11-30"})["ziel"]["soll_pct"] == 50.0
    for k in ({"range": "y", "yr": 2027}, {"range": "c", "from": "2026-12-01", "to": "2026-12-31"}, {"range": "12m"}, {"range": "90d"}, {"range": "all"},
              {"range": "year", "agg": "avg"}, {"range": "year", "agg": "max"}, {"range": "year", "durch": {"mess": "touren", "agg": "sum"}}):
        assert "soll" not in ausw(ziel=100, plan=True, **k)["ziel"], k
    assert ausw(mess="touren", range="year", ziel=10, plan=True)["ziel"]["soll"] == round(10 * 319 / 365, 4)
    assert ausw(range="year", ziel=10, plan=True, sports=["jogging"])["ziel"]["plan"] == "zurueck"      # kein Wert: 0 gegen Soll


def test_verlauf_woche_monat_jahr_und_aus():
    seed()
    w = ausw(range="c", **{"from": "2026-03-01", "to": "2026-03-31"})["reihe"]
    assert w["art"] == "woche" and w["labels"][0] == "2026-02-23" and len(w["werte"]) == 6 and w["werte"][1] == 52 and sum(w["werte"]) == 52
    n = ausw(range="90d")["reihe"]
    assert n["art"] == "woche" and len(n["werte"]) <= 15 and sum(n["werte"]) == 28 and all(date.fromisoformat(x).weekday() == 0 for x in n["labels"])
    assert n == ausw(range="90d")["reihe"]                                                # deterministisch
    assert ausw(range="90d", agg="monat")["reihe"]["art"] == "monat"                        # „pro Monat“ bleibt monatlich
    assert ausw(range="year")["reihe"]["art"] == "monat" and len(ausw(range="year")["reihe"]["werte"]) == 11
    assert ausw(range="all")["reihe"]["art"] == "monat" and len(ausw(range="all")["reihe"]["werte"]) == 19
    mk("h", date(2010, 1, 5), "hike", 1)
    j = ausw(range="all")["reihe"]
    assert j["art"] == "jahr" and len(j["werte"]) == 12 and j["labels"][-1] == "2026"       # über 36 Monate: Jahre, höchstens die letzten 12
    a = ausw(range="c", agg="avg", **{"from": "2026-03-01", "to": "2026-03-31"})["reihe"]["werte"]
    assert a[0] is None and a[1] == 26 and a[2:] == [None] * 4                              # ohne Tour keine Angabe (nie 0)
    assert ausw(range="year", spark="aus")["reihe"] is None and ausw(range="year", spark="linie")["reihe"]["art"] == "monat"
    assert "spark" not in kz.clean_cfg(cfg(spark="saeulen")) and kz.clean_cfg(cfg(spark="linie"))["spark"] == "linie"


def _bad(c, body):
    return c.post("/api/bausteine/eigen", json=body).status_code


def test_neue_felder_streng_geprueft():
    bad = [cfg(vglart="jahr"), cfg(vgl=False, vglart="jahr"), cfg(vgl=True, vglart="woche"), cfg(vgl=True, vglart=None), cfg(vgl=True, vglart=1), cfg(plan=True), cfg(ziel=10, plan="ja"), cfg(ziel=10, plan=1),
           cfg(spark="kreis"), cfg(spark=True), cfg(spark=None), cfg(touren="ja"), cfg(touren=1), cfg(touren=None), cfg(vgl=True, vglart="jahr", extra=1)]
    with client() as c:
        for b in bad:
            assert _bad(c, b) == 400, b
        ok = cfg(range="year", vgl=True, vglart="monat", ziel=1000, plan=True, spark="linie", touren=True, sports=["hike"], tag="Alpen", minkm=5)
        r = c.post("/api/bausteine/eigen", json=ok)
        assert r.status_code == 200 and r.json()["ziel"]["plan"] and r.json()["vorher"]["art"] == "monat"
        assert c.post("/api/bausteine/eigen", json=cfg(plan=False, touren=False, spark="saeulen")).status_code == 200
    out = kz.clean_cfg(cfg(vgl=True, vglart="davor", ziel=5, plan=False, touren=False))
    assert "vglart" not in out and "plan" not in out and "touren" not in out                  # Standardwerte werden nicht gespeichert
    assert kz.clean_cfg(cfg(vgl=True, vglart="jahr", ziel=5, plan=True, touren=True)) == {"title": "T", "mess": "km", "agg": "sum", "range": "all", "vgl": True, "vglart": "jahr", "ziel": 5, "plan": True, "touren": True}


def test_layout_speichert_neue_felder_und_betrachter():
    from fastapi.testclient import TestClient
    from app import main
    w = {"id": "w1", "type": "eigenkz", "cfg": cfg(range="year", vgl=True, vglart="jahr", ziel=100, plan=True, spark="linie", touren=True)}
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        assert c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"}).status_code == 200
        assert c.put("/api/layout/uebersicht", json={"widgets": [w]}).status_code == 200
        assert c.get("/api/layout/uebersicht").json()["layout"]["widgets"][0]["cfg"]["vglart"] == "jahr"
        w2 = {"id": "w1", "type": "eigenkz", "cfg": cfg(plan=True)}                       # Soll ohne Ziel wird schon beim Speichern abgelehnt
        assert c.put("/api/layout/uebersicht", json={"widgets": [w2]}).status_code == 400
        assert c.get("/api/layout/uebersicht").json()["layout"]["widgets"][0]["cfg"]["plan"] is True
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert v.put("/api/layout/uebersicht", json={"widgets": [w]}).status_code == 403
        assert v.post("/api/bausteine/eigen", json=w["cfg"]).status_code == 403                # keine neuen Rechte: Betrachter sehen den Standard, schreiben nichts
        assert v.get("/api/layout/uebersicht").json()["layout"] is None


def test_version_and_notes():
    from app import config
    assert config.VERSION.startswith("3.45.0 · Meine Touren")
    notes = (ROOT / "docs" / "versionen" / "3.35.0.md").read_text(encoding="utf-8")
    assert "Fortschrittsbalken" in notes and "Sparkline" in notes and "Trend" in notes and "Antippen" in notes
    assert 'const V = "mt-v127"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    assert 'SL_APPV = "3.45.0"' in (ROOT / "app" / "static" / "js" / "54-ansichten.js").read_text(encoding="utf-8")
    hist = (ROOT / "docs" / "VERSIONSVERLAUF.md").read_text(encoding="utf-8")
    assert hist.index("## Version 3.35.0") < hist.index("## Version 3.34.0")
    assert "3.35.0.md" in (ROOT / "docs" / "versionen" / "README.md").read_text(encoding="utf-8")
    assert "Eigene Kennzahlen weiterentwickeln" in hist
