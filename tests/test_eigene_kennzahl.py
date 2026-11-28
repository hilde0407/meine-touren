"""3.28.0 – Eigene Kennzahl, Backend: Whitelist-Prüfung, Berechnung gegen bekannte Daten, Layout-Speicherung, Grenze je Benutzer, Benutzertrennung, Betrachter, Version."""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from tests.test_statistik import HEUTE, client, mk, seed  # noqa: E402
from app import db, kennzahl as kz  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def cfg(**k):
    return {"title": "T", "mess": "km", "agg": "sum", "range": "all", **k}


def ausw(**k):
    return kz.auswerten(cfg(**k), HEUTE)


def test_values_against_known_data():
    seed()                                                  # a 12 km/4 h/400 m, b 40 km/2 h/300 m, c 28 km/8 h/900 m (2026), d 5 km/1 h/50 m, e 60 km/3 h/20 m (2025)
    assert ausw()["wert"] == 145 and ausw()["einheit"] == {"z": "km", "n": None} and ausw()["n"] == 5
    assert ausw(agg="avg")["wert"] == 29 and ausw(agg="max")["wert"] == 60 and ausw(agg="min")["wert"] == 5 and ausw(agg="count")["wert"] == 5
    r = ausw(agg="record", sports=["hike"])
    assert r["wert"] == 28 and r["rekord"]["id"] == "c" and r["rekord"]["datum"] == "2026-09-20"
    assert ausw(mess="hm")["wert"] == 1670 and ausw(mess="dauer")["wert"] == 18 and ausw(mess="touren", agg="sum")["wert"] == 5
    assert ausw(mess="tempo", agg="avg")["wert"] == round(145 / 18, 4)                       # gewichtet: Summe ÷ Summe
    assert ausw(mess="tempo", agg="max")["wert"] == 20 and ausw(mess="tempo", agg="record")["rekord"]["id"] == "e"      # b und e je 20 km/h: früheste Tour (e, 2025)
    f = ausw(mess="hm", durch={"mess": "km", "agg": "sum"})
    assert f["wert"] == round(1670 / 145, 4) and f["einheit"] == {"z": "m", "n": "km"}
    assert ausw(mess="hm", durch={"mess": "km", "agg": "sum"}, op="pct")["einheit"] == {"z": "pct", "n": None}
    assert ausw(mess="km", durch={"mess": "km", "agg": "max"})["einheit"] == {"z": None, "n": None}
    m = kz.auswerten(cfg(mess="touren", agg="monat", range="12m", vgl=True, ziel=10), HEUTE)    # 2025-12-01 bis 2026-11-15 = 12 Monate, 3 Touren
    assert m["wert"] == 0.25 and m["vorher"]["wert"] == round(2 / 12, 4) and m["vorher"]["pct"] == 50.0 and m["ziel"] == {"ziel": 10, "pct": 2.5}
    assert ausw(range="y", yr=2026)["wert"] == 80 and ausw(range="c", **{"from": "2026-03-01", "to": "2026-03-31"})["wert"] == 52
    assert ausw(sports=["jogging"], range="y", yr=2024)["wert"] == 0 and ausw(sports=["jogging"], range="y", yr=2024, agg="avg")["wert"] is None
    assert ausw(minkm=10)["wert"] == 140 and ausw(minkm=10)["n"] == 4
    assert ausw()["reihe"]["art"] == "monat" and len(ausw()["reihe"]["werte"]) == 19 and ausw()["reihe"]["werte"][0] == 5
    db.execute("INSERT INTO tour_tags(id,tag) VALUES('a','Alpen'),('c','alpen')")
    assert ausw(tag="ALPEN")["wert"] == 40 and ausw(tag="x'; DROP TABLE tours; --")["wert"] == 0 and db.one("SELECT COUNT(*) n FROM tours")["n"] == 5


def test_whitelist_and_limits():
    bad = [cfg(mess="sql"), cfg(agg="eval"), cfg(mess="tempo", agg="sum"), cfg(mess="touren", agg="max"), cfg(range="x"), cfg(range="y"), cfg(range="y", yr=1800), cfg(range="c"), cfg(**{"from": "2026-01-01", "to": "2026-02-01"}),
           cfg(range="c", **{"from": "2026-02-01", "to": "2026-01-01"}), cfg(range="c", **{"from": "2026-02-30", "to": "2026-03-01"}), cfg(sports=["a b"]), cfg(sports="hike"), cfg(minkm=-1), cfg(minkm=1001), cfg(minkm=True),
           cfg(ziel=0.0, extra=1), cfg(ziel=-5), cfg(ziel=1e12), cfg(ziel="9"), cfg(title=""), cfg(title="a" * 61), cfg(title="<b>"), cfg(symbol="x" * 9), cfg(tag="a" * 41), cfg(vgl="ja"), cfg(op="div"),
           cfg(durch={"mess": "km", "agg": "record"}), cfg(durch={"mess": "km", "agg": "sum", "x": 1}), cfg(durch={"mess": "zz", "agg": "sum"}), cfg(agg="record", durch={"mess": "km", "agg": "sum"}),
           cfg(agg="monat", durch={"mess": "km", "agg": "sum"}), cfg(durch={"mess": "km", "agg": "sum"}, op="mul"), {"title": "T"}, "kaputt", None]
    with client() as c:
        for b in bad:
            assert c.post("/api/bausteine/eigen", json=b).status_code == 400, b
        assert c.post("/api/bausteine/eigen", content=b"{kaputt").status_code == 400
        assert c.post("/api/bausteine/eigen", content=b"x" * 5000).status_code == 413
        ok = c.post("/api/bausteine/eigen", json=cfg(sports=["hike"], symbol="🥾", ziel=1000, vgl=True, tag="Alpen", minkm=2.5))
        assert ok.status_code == 200 and ok.json()["wert"] == 0
        assert c.post("/api/bausteine/eigen", json={"cfg": cfg()}).status_code == 200
        assert c.get("/api/bausteine/eigen").status_code in (404, 405)


def _w(i, **k):
    return {"id": f"w{i}", "type": "eigenkz", "cfg": cfg(**k)}


def test_layout_validation_persistence_pages_and_limit():
    with client() as c:
        d = {"v": 1, "widgets": [_w(1), _w(2, agg="avg")]}
        assert c.put("/api/layout/uebersicht", json=d).status_code == 200
        got = c.get("/api/layout/uebersicht").json()["layout"]["widgets"]
        assert [x["cfg"]["agg"] for x in got] == ["sum", "avg"]
        for k in ("tour-haupt", "tour-auswertung"):
            assert c.put(f"/api/layout/{k}", json={"widgets": [_w(1)]}).status_code == 400
        assert c.put("/api/layout/uebersicht", json={"widgets": [{"id": "w1", "type": "eigenkz", "cfg": {"mess": "km", "agg": "sum", "title": "T", "x": 1}}]}).status_code == 400
        assert c.get("/api/layout/uebersicht").json()["layout"]["widgets"][0]["cfg"]["agg"] == "sum"       # abgelehntes Speichern ändert nichts
        # Ansichten-Behälter: gleiche Prüfung
        cont = {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1, "widgets": [_w(1)]}}], "active": "standard"}
        assert c.put("/api/layout/statistik", json=cont).status_code == 200
        cont["views"][0]["layout"]["widgets"][0]["cfg"]["mess"] = "evil"
        assert c.put("/api/layout/statistik", json=cont).status_code == 400
        # Grenze: 24 je Benutzer über alle Seiten
        assert c.put("/api/layout/uebersicht", json={"widgets": [_w(i) for i in range(12)]}).status_code == 200
        assert c.put("/api/layout/statistik", json={"widgets": [_w(100 + i) for i in range(12)]}).status_code == 200
        r = c.put("/api/layout/statistik", json={"widgets": [_w(100 + i) for i in range(13)]})
        assert r.status_code == 400 and "24" in r.json()["detail"]
        assert c.put("/api/layout/uebersicht", json={"widgets": [_w(i) for i in range(13)]}).status_code == 400
        assert c.put("/api/layout/uebersicht", json={"widgets": [_w(i) for i in range(11)]}).status_code == 200       # Löschen schafft wieder Platz
        # „Standard wiederherstellen“ = DELETE
        assert c.delete("/api/layout/uebersicht").status_code == 200 and c.get("/api/layout/uebersicht").json()["layout"] is None
        # Export-Prüfung nutzt dieselben Regeln
        ex = {"format": "meine-touren-ansicht", "format_version": 1, "page": "uebersicht", "name": "X", "layouts": {"uebersicht": {"widgets": [_w(1, mess="evil")]}}}
        assert c.post("/api/layout/check", json=ex).json()["ok"] is False
        ex["layouts"]["uebersicht"]["widgets"] = [_w(1)]
        assert c.post("/api/layout/check", json=ex).json()["ok"] is True


def test_isolation_and_viewer():
    from fastapi.testclient import TestClient
    from app import main
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        assert c.post("/api/users", json={"name": "Anna", "email": "anna@example.com", "password": "annas-pass12", "role": "user"}).status_code == 200
        assert c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"}).status_code == 200
        from app import ctx
        with ctx.as_user("max"):                                     # Max' eigene Datenbank
            seed()
        assert c.post("/api/bausteine/eigen", json=cfg()).json()["wert"] == 145
        assert c.put("/api/layout/statistik", json={"widgets": [_w(1)]}).status_code == 200
        a = TestClient(main.app)
        assert a.post("/api/login", json={"name": "anna", "password": "annas-pass12"}).status_code == 200
        assert a.post("/api/bausteine/eigen", json=cfg()).json()["wert"] == 0                        # Annas Datenbank ist leer
        assert a.get("/api/layout/statistik").json()["layout"] is None
        assert a.put("/api/layout/statistik", json={"widgets": [_w(1)] * 1}).status_code == 200 and len(a.get("/api/layout/statistik").json()["layout"]["widgets"]) == 1
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert v.put("/api/layout/statistik", json={"widgets": [_w(1)]}).status_code == 403
        assert v.post("/api/bausteine/eigen", json=cfg()).status_code == 403
        assert v.get("/api/layout/statistik").json()["layout"] is None                                # Betrachter sieht den Standard, nicht die Bausteine des Besitzers
        assert TestClient(main.app).post("/api/bausteine/eigen", json=cfg()).status_code == 401


def test_version_and_notes():
    from app import config
    assert config.VERSION.startswith("3.73.0 · Meine Touren")
    assert (ROOT / "docs" / "versionen" / "3.31.0.md").exists()
    assert 'const V = "mt-v165"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    assert 'SL_APPV = "3.73.0"' in (ROOT / "app" / "static" / "js" / "54-ansichten.js").read_text(encoding="utf-8")
    assert "59-bausteine-eigen.js" in (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")


def _hr_sidecar(tid, bpms):
    import json
    from app import config
    config.TRACK_DIR.mkdir(parents=True, exist_ok=True)
    (config.TRACK_DIR / f"{tid}.hr.json").write_text(json.dumps([[i * 10, b] for i, b in enumerate(bpms)]), encoding="utf-8")


def test_puls_und_gehzeit_als_messgroesse():
    """3.29.0: Durchschnitts-/Höchstpuls je Tour (Pulsdatei) und Gehzeit (Bewegungszeit aus dem Tempo-Zwischenspeicher) – nur Touren mit Angabe zählen, Summe von Puls ist nicht möglich."""
    from app import config, routes, steigung
    seed()                                                  # a 12 km/4 h, b 40 km/2 h, c 28 km/8 h (2026), d 5 km/1 h, e 60 km/3 h (2025)
    _hr_sidecar("a", [100, 120, 140, 160, 180, 120])          # Ø 137 (gerundet), Max 180
    _hr_sidecar("c", [90, 100, 110, 120, 130, 100])           # Ø 108 (gerundet), Max 130
    p = ausw(mess="puls", agg="avg")
    assert p["einheit"] == {"z": "bpm", "n": None} and p["wert"] == round((137 + 108) / 2, 4) and p["n"] == 5
    assert ausw(mess="pulsmax", agg="max")["wert"] == 180 and ausw(mess="pulsmax", agg="min")["wert"] == 130 and ausw(mess="puls", agg="count")["wert"] == 2
    r = ausw(mess="puls", agg="record")
    assert r["rekord"]["id"] == "a" and r["rekord"]["wert"] == 137
    assert ausw(mess="pulsmax", agg="avg", range="y", yr=2025)["wert"] is None                     # 2025: keine Pulsdaten -> kein Wert (nie 0)
    for bad in (cfg(mess="puls", agg="sum"), cfg(mess="pulsmax", agg="monat"), cfg(mess="puls", agg="avg", durch={"mess": "puls", "agg": "sum"})):
        try:
            kz.clean_cfg(bad)
        except Exception as e:  # noqa
            assert getattr(e, "status_code", 0) == 400
        else:
            raise AssertionError(bad)
    # Gehzeit: Bewegungszeit aus den Streckenpunkten (50 m je 10 s, danach 20 Minuten Pause)
    import math
    pts = [(48.0 + i * 0.00045, 11.0, 500 + 5 * math.sin(i / 20), (1_700_000_000 + i * 10) * 1000) for i in range(300)]       # etwa 18 km/h, 400 Punkte
    pts += [(pts[-1][0], 11.0, 500, pts[-1][3] + 1_200_000)] + [(pts[-1][0] + (i + 1) * 0.00045, 11.0, 500, pts[-1][3] + 1_200_000 + (i + 1) * 10_000) for i in range(100)]
    routes.store("a", pts)
    g = ausw(mess="gehzeit", agg="sum")
    res = steigung.tempo_of("a", allow_compute=False)
    assert res and res["status"] == "ok"
    assert g["einheit"] == {"z": "h", "n": None} and g["wert"] == round(res["zeit_s"] / 3600, 4) and 0 < g["wert"] < (400 * 10 + 1200) / 3600 - 0.2 and g["n"] == 5
    assert "offen" not in g                                                                          # b–e haben keine Strecke: zählen nicht (und sind nicht „offen“)
    assert ausw(mess="gehzeit", agg="record")["rekord"]["id"] == "a"
    assert (config.CACHE_DIR / "tempo" / "a.json").exists()                                           # gecacht: nächster Aufruf liest nur die Datei
    kz.GEHZEIT_BUDGET_S = 0.0                                                                       # Budget aufgebraucht: ohne Zwischenspeicher-Treffer „offen“
    try:
        routes.store("b", pts)
        r2 = ausw(mess="gehzeit", agg="sum")
        assert r2["offen"] == 1 and r2["wert"] == g["wert"]
    finally:
        kz.GEHZEIT_BUDGET_S = 5.0
    assert ausw(mess="gehzeit", agg="sum")["wert"] > g["wert"] and "offen" not in ausw(mess="gehzeit", agg="sum")
