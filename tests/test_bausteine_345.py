"""3.45.0 „Weniger Bausteine, klarere Namen“ – Server: Umzug alter Bausteine (Alias-Tabelle app/baustein_umzug.py) beim Speichern, beim Öffnen der Datenbank, in Ansichten,
Export-Dateien und Ansichtscodes; eigene Ziele alter Bausteine bleiben als Ziele der Statistik erhalten (keine Dubletten); strenge Prüfung der neuen Bausteine „Ziele“ und „Bestwerte“;
Wochenziele in den Zielen (period = week) und im Hinweis „woche“. Nur erfundene Testdaten."""
import base64
import json
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import baustein_umzug as umzug, db, hinweise  # noqa: E402
from app.gpxtools import TZ  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
YEAR = date.today().year
ALT = [
    {"id": "w1", "type": "jahresziel", "cfg": {"metric": "km", "goal": 1200, "sports": ["hike"], "title": "Mein Ring"}},
    {"id": "w2", "type": "jahresziele", "cfg": {"year": "last"}},
    {"id": "w3", "type": "hnziel", "cfg": {"schwelle": 15, "ausblenden": 3, "snoozes": ["ziel:%d" % (int(datetime.now().timestamp()) + 3600)]}},
    {"id": "w4", "type": "hnwoche", "cfg": {"einheit": "touren", "ziel": 3}},
    {"id": "w5", "type": "rekorde", "cfg": {"sports": ["hike"], "range": "y", "yr": 2025}},
    {"id": "w6", "type": "sttop", "cfg": {"wert": "tempo", "n": 8, "range": "12m"}},
    {"id": "w7", "type": "hinweise", "cfg": {"arten": ["pause", "woche"], "woche_ziel": 40, "woche_einheit": "km"}},
]
NEU = {
    "w1": ("ziele", {"view": "ring", "zeit": "jahr", "sports": ["hike"], "title": "Mein Ring"}),
    "w2": ("ziele", {"view": "balken", "zeit": "jahr", "year": "last"}),
    "w4": ("ziele", {"view": "balken", "zeit": "woche"}),
    "w5": ("bestwerte", {"n": 1, "werte": ["km", "hm", "tempo"], "sports": ["hike"], "range": "y", "yr": 2025}),
    "w6": ("bestwerte", {"n": 10, "werte": ["tempo"], "range": "12m"}),
    "w7": ("hinweise", {"arten": ["pause", "woche"]}),
}


def client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def goals():
    return sorted((g["period"], g["year"], g["sport"], g["metric"], g["target"]) for g in client().get("/api/goals").json())


def _check(lay):
    by = {w["id"]: w for w in lay["widgets"]}
    for i, (t, c) in NEU.items():
        assert by[i]["type"] == t and by[i]["cfg"] == c, (i, by[i])
    assert by["w3"]["type"] == "ziele" and by["w3"]["cfg"]["view"] == "warnung" and by["w3"]["cfg"]["schwelle"] == 15 and by["w3"]["cfg"]["ausblenden"] == 3
    assert len(by["w3"]["cfg"]["snoozes"]) == 1
    assert not set(umzug.ALT) & {w["type"] for w in lay["widgets"]}


# ------------------------------------------------------------------------------------------------ Alias beim Speichern
def test_put_mit_allen_alten_kennungen_bildet_ab_und_uebernimmt_ziele():
    with client() as c:
        r = c.put("/api/layout/uebersicht", json={"order": ["w5", "jahr"], "widgets": ALT, "w": {"w1": "halb"}, "groups": [{"id": "grpaa", "title": "Ziele", "ids": ["w1", "w3"]}]})
        assert r.status_code == 200, r.text
        lay = c.get("/api/layout/uebersicht").json()["layout"]
        _check(lay)
        assert lay["order"] == ["w5", "jahr"] and lay["w"] == {"w1": "halb"} and lay["groups"][0]["ids"] == ["w1", "w3"]     # Kennungen, Breiten und Gruppen bleiben
    assert goals() == [("week", 0, "", "count", 3.0), ("week", 0, "", "km", 40.0), ("year", YEAR, "hike", "km", 1200.0)]


def test_vorhandenes_ziel_gilt_und_es_entstehen_keine_dubletten():
    with client() as c:
        c.post("/api/goals", json={"year": YEAR, "metric": "km", "sport": "hike", "target": 800})
        for _ in range(2):
            assert c.put("/api/layout/uebersicht", json={"widgets": [ALT[0], ALT[3]]}).status_code == 200
        assert c.put("/api/layout/tour-haupt", json={"widgets": [dict(ALT[0], id="x1")]}).status_code == 200
    assert goals() == [("week", 0, "", "count", 3.0), ("year", YEAR, "hike", "km", 800.0)]


def test_jahresziel_ohne_eigenes_ziel_und_mit_aufstieg():
    with client() as c:
        assert c.put("/api/layout/statistik", json={"widgets": [{"id": "a", "type": "jahresziel", "cfg": {}}, {"id": "b", "type": "jahresziel", "cfg": {"metric": "hm", "sports": ["hike", "mtb"]}}]}).status_code == 200
        lay = c.get("/api/layout/statistik").json()["layout"]
    assert [w["cfg"] for w in lay["widgets"]] == [{"view": "ring", "zeit": "jahr"}, {"view": "ring", "zeit": "jahr", "sports": ["hike", "mtb"]}]
    assert goals() == [("year", YEAR, "", "km", 1000.0), ("year", YEAR, "", "up", 20000.0)]        # Standardziele wie bisher angezeigt; mehrere Sportarten: Ziel für alle


def test_ansichten_behaelter_und_tourseite():
    box = {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"widgets": [ALT[1]]}}, {"id": "v2", "name": "Alt", "layout": {"widgets": [ALT[0], ALT[4], ALT[5]]}}], "active": "v2", "rules": {}}
    with client() as c:
        assert c.put("/api/layout/statistik", json=box).status_code == 200
        st = c.get("/api/layout/statistik").json()["container"]
        assert [w["type"] for w in st["views"][1]["layout"]["widgets"]] == ["ziele", "bestwerte", "bestwerte"] and st["active"] == "v2"
        assert c.put("/api/layout/tour-haupt", json={"widgets": [ALT[0], ALT[4]]}).status_code == 200                 # früher auch auf der Tourseite erlaubt: bleibt erlaubt
        assert [w["type"] for w in c.get("/api/layout/tour-haupt").json()["layout"]["widgets"]] == ["ziele", "bestwerte"]


def test_bestwerte_ist_nicht_mehr_nur_statistik_und_hinweise_nicht_auf_der_tourseite():
    with client() as c:
        assert c.put("/api/layout/uebersicht", json={"widgets": [ALT[5]]}).status_code == 200          # „Top-Touren“ ist jetzt „Bestwerte“ und darf auch auf die Übersicht
        assert c.put("/api/layout/tour-haupt", json={"widgets": [{"id": "h", "type": "hnrekord", "cfg": {}}]}).status_code == 400


def test_strenge_pruefung_ziele_und_bestwerte():
    with client() as c:
        ok = [{"view": "warnung", "zeit": "alle", "schwelle": 20, "ausblenden": 0, "sports": ["hike"], "title": "X"}, {"view": "ring", "year": "last"}, {}]
        for cfg in ok:
            assert c.put("/api/layout/uebersicht", json={"widgets": [{"id": "z", "type": "ziele", "cfg": cfg}]}).status_code == 200, cfg
        bad = [{"view": "torte"}, {"zeit": "monat"}, {"schwelle": 0}, {"goal": 1000}, {"snoozes": ["pause:1"]}, {"year": 2025}]
        for cfg in bad:
            assert c.put("/api/layout/uebersicht", json={"widgets": [{"id": "z", "type": "ziele", "cfg": cfg}]}).status_code == 400, cfg
        for cfg in ({"n": 3, "werte": ["monat", "km"]}, {"n": 10, "range": "all", "eigen": True}):
            assert c.put("/api/layout/statistik", json={"widgets": [{"id": "b", "type": "bestwerte", "cfg": cfg}]}).status_code == 200, cfg
        assert c.get("/api/layout/statistik").json()["layout"]["widgets"][0]["cfg"]["n"] == 10
        for cfg in ({"n": 8}, {"n": 2}, {"werte": []}, {"werte": ["puls"]}, {"wert": "km"}, {"range": "c"}):
            assert c.put("/api/layout/statistik", json={"widgets": [{"id": "b", "type": "bestwerte", "cfg": cfg}]}).status_code == 400, cfg
        # Abschnitte „Ziele“ und „Bestwerte“ der Statistik sind Bausteine: ihre Einstellung steht unter cfg und wird genauso geprüft
        assert c.put("/api/layout/statistik", json={"cfg": {"ziele": {"zeit": "jahr"}, "bestwerte": {"n": 3}}}).status_code == 200
        assert c.put("/api/layout/statistik", json={"cfg": {"bestwerte": {"n": 7}}}).status_code == 400


# ------------------------------------------------------------------------------------------------ Umzug beim Öffnen der Datenbank
def test_umzug_beim_oeffnen_der_datenbank():
    raw = {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"widgets": ALT}}], "active": "standard", "rules": {}}
    db.execute("INSERT INTO user_layout(page_key,json,ts) VALUES('uebersicht',?,1)", (json.dumps(raw),))
    db.execute("INSERT INTO user_layout(page_key,json,ts) VALUES('karte',?,1)", (json.dumps({"order": ["a"]}),))
    path = db.pfad()
    db.close_all()
    con = sqlite3.connect(str(path))
    assert '"jahresziel"' in con.execute("SELECT json FROM user_layout WHERE page_key='uebersicht'").fetchone()[0]           # noch alt in der Datei
    con.close()
    db.init()
    row = db.one("SELECT json,ts FROM user_layout WHERE page_key='uebersicht'")
    _check(json.loads(row["json"])["views"][0]["layout"])
    assert row["ts"] > 1
    assert db.one("SELECT ts FROM user_layout WHERE page_key='karte'")["ts"] == 1                 # ohne alte Bausteine unverändert
    assert goals() == [("week", 0, "", "count", 3.0), ("week", 0, "", "km", 40.0), ("year", YEAR, "hike", "km", 1200.0)]
    with sqlite3.connect(str(path)) as con:                                                      # mehrfach aufrufbar: nichts Neues
        con.row_factory = sqlite3.Row
        assert umzug.migrate_rows(con) == 0


def test_defektes_layout_verhindert_das_oeffnen_nicht():
    db.execute("INSERT INTO user_layout(page_key,json,ts) VALUES('uebersicht',?,1)", ('{"widgets":[{"type":"rekorde"', ))
    db.close_all()
    db.init()
    assert db.one("SELECT json FROM user_layout WHERE page_key='uebersicht'")["json"].startswith('{"widgets"')


# ------------------------------------------------------------------------------------------------ Export-Datei und Ansichtscode
def _export(page, lays):
    return {"format": "meine-touren-ansicht", "format_version": 1, "app_version": "3.44.0", "page": page, "name": "Alt", "exported": "2026-11-01T10:00:00Z", "layouts": lays}


def test_export_datei_und_ansichtscode_mit_alten_kennungen():
    doc = _export("uebersicht", {"uebersicht": {"widgets": ALT}})
    with client() as c:
        r = c.post("/api/layout/check", json=doc).json()
        assert r["ok"] is True, r
        _check(r["layouts"]["uebersicht"])
        assert r["stats"]["uebersicht"]["types"] == ["bestwerte", "hinweise", "ziele"]
        notes = " ".join(r["ignored"])
        assert "1.200 km im Jahr" in notes and "3 Touren pro Woche" in notes and "40 km pro Woche" in notes and "nicht übernommen" in notes
        code = "MTA1." + base64.urlsafe_b64encode(json.dumps(doc).encode()).decode().rstrip("=")
        r2 = c.post("/api/layout/code", json={"code": code}).json()
        assert r2["ok"] is True and r2["layouts"] == r["layouts"] and r2["ignored"] == r["ignored"]
        tour = c.post("/api/layout/check", json=_export("tour", {"tour-haupt": {"widgets": [ALT[0], ALT[4]]}, "tour-auswertung": {}})).json()
        assert tour["ok"] and [w["type"] for w in tour["layouts"]["tour-haupt"]["widgets"]] == ["ziele", "bestwerte"]
        st = c.post("/api/layout/check", json=_export("statistik", {"statistik": {"order": ["kpi", "t-sttop"], "widgets": [{"id": "t-sttop", "type": "sttop", "cfg": {"wert": "tempo"}}]}})).json()
        assert st["ok"] and st["layouts"]["statistik"]["widgets"][0] == {"id": "t-sttop", "type": "bestwerte", "cfg": {"n": 5, "werte": ["tempo"]}}
    assert goals() == []                                                                           # Prüfen legt keine Ziele an (es sind die eines anderen)


# ------------------------------------------------------------------------------------------------ Ziele: Wochenziele
def test_goals_api_mit_wochenzielen():
    with client() as c:
        assert c.post("/api/goals", json={"period": "week", "metric": "count", "target": 3}).status_code == 200
        assert c.post("/api/goals", json={"year": YEAR, "metric": "km", "target": 500}).status_code == 200
        for bad in ({"period": "monat", "metric": "km", "target": 3}, {"period": "week", "metric": "km", "target": 0}, {"period": "week", "metric": "puls", "target": 3}):
            assert c.post("/api/goals", json=bad).status_code == 400, bad
        gs = c.get("/api/goals").json()
    assert sorted((g["period"], g["year"]) for g in gs) == [("week", 0), ("year", YEAR)]


def _tour(tid, d, km=10, sport="hike"):
    ts = int(datetime(d.year, d.month, d.day, 9, 0, tzinfo=TZ).timestamp())
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES(?,?,?,?,?,?,?,?,?,'t','komoot')", (tid, tid, sport, ts, ts + 3600, km * 1000, 3600, 100, 100))


def test_hinweis_woche_liest_die_wochenziele():
    heute = date(2026, 6, 20)                                                                     # Samstag
    mo = heute - timedelta(days=heute.weekday())
    _tour("a", mo, 12)
    _tour("b", mo + timedelta(days=2), 5, "mtb")
    p = hinweise.check("woche")
    assert hinweise.auswertung(p, heute)["hinweise"] == []                                         # ohne Wochenziel nichts
    db.execute("INSERT INTO goals(year,sport,metric,target,period) VALUES(0,'hike','km',50,'week')")
    db.execute("INSERT INTO goals(year,sport,metric,target,period) VALUES(0,'','count',2,'week')")
    h = hinweise.auswertung(p, heute)["hinweise"][0]
    assert h["art"] == "woche" and h["stufe"] == "hinweis"                                         # Samstag, ein Ziel offen
    z = h["daten"]["ziele"]
    assert [(x["einheit"], x["ist"], x["erreicht"]) for x in z] == [("km", 12.0, False), ("touren", 2.0, True)]
    assert h["daten"]["einheit"] == "km" and h["daten"]["ziel"] == 50
    assert [x["einheit"] for x in hinweise.auswertung(hinweise.check("woche", sport="mtb"), heute)["hinweise"][0]["daten"]["ziele"]] == ["touren"]   # Sportart wählt Ziele aus
    # der Parameter woche_ziel (älterer Aufruf) hat Vorrang und liefert das bisherige Format
    d = hinweise.auswertung(hinweise.check("woche", woche_ziel="10"), heute)["hinweise"][0]["daten"]
    assert "ziele" not in d and d["ziel"] == 10 and d["erreicht"] is True
    # Jahresziel-Hinweis sieht keine Wochenziele
    assert hinweise.auswertung(hinweise.check("ziel"), date(2026, 6, 20))["hinweise"] == []


# ------------------------------------------------------------------------------------------------ Oberfläche: gleiche Tabelle, keine alten Typen mehr im Katalog
def test_alias_tabelle_in_der_oberflaeche_und_vorlagen():
    js = (ROOT / "app" / "static" / "js" / "49-seitenlayout.js").read_text(encoding="utf-8")
    for t in umzug.ALT:
        assert f"  {t}: c => [" in js or f"  {t}: c => {{" in js, t
    tpl = (ROOT / "app" / "static" / "js" / "55-vorlagen.js").read_text(encoding="utf-8")
    for t in umzug.ALT:
        assert f'"w:{t}"' not in tpl, t
    assert '"w:ziele"' in tpl and '"w:bestwerte"' in tpl
    allejs = "".join(p.read_text(encoding="utf-8") for p in (ROOT / "app" / "static" / "js").glob("5*.js"))
    for t in ("jahresziel: {", "jahresziele: {", "rekorde: {", "sttop: {", 'wtype: "hnziel"', 'wtype: "hnwoche"'):
        assert t not in allejs, t
