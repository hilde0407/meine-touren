"""3.60.0 – Aktivitäten-Katalog: die endgültige Auswahl (29 Aktivitäten, 5 Kategorien; docs/versionen/3.60.0.md), eine Tabelle je Seite (gpxtools.CATALOG und
SPORT_TABLE in 01-grundlagen.js, gleich), Rückfall entfernter Schlüssel (gpxtools.RUECKFALL = SPORT_ALIAS) beim Import, Senden, in Anzeige, Filtern, Statistik und Zielen.
Altdaten aus 3.59.0: Touren bleiben unverändert, Favoriten und Statistik-Gruppen lassen entfernte Schlüssel beim Laden still weg."""
import json
import re
import sys
import time
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import config, db, gpxtools  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "app" / "static" / "js"
NOW = int(time.time())

# Volkers endgültige Auswahl (Reihenfolge und Gruppierung wie in der Vorgabe)
ERWARTET = [
    ("fuss", ["hike", "walk", "mountaineering", "climbing", "nordicwalking", "jogging", "trailrun"]),
    ("rad", ["touringbicycle", "racebike", "mtb", "mtb_easy", "e_touringbicycle", "e_mtb", "bikepacking"]),
    ("winter", ["skialpin", "skitour", "nordic", "snowboard", "snowshoe"]),
    ("wasser", ["kayak", "rowing", "dragonboat", "rafting", "boat"]),
    ("sonst", ["skateboard", "skaten", "horse", "paraglide", "other"]),
]
ENTFERNT_359 = ["dogwalk", "orienteering", "commute", "cyclocross", "bmx", "sled", "iceskate", "snowmobile", "swim", "snorkel", "sup", "sailing", "waterski",
                "surf", "kitesurf", "wakesurf", "fishing", "hunting", "archery", "golf", "atv", "motorbike"]


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _tour(tid, sport, km=10.0, tage=40):
    ts = NOW - tage * 86400
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
               (tid, f"Tour {tid}", sport, ts, ts + 3600, km * 1000, 3600, 100, 100, 48.0, 8.0, "tour_recorded"))


def _js_table():
    js = (JS / "01-grundlagen.js").read_text(encoding="utf-8")
    table = js.split("const SPORT_TABLE = [", 1)[1].split("];", 1)[0]
    rows = re.findall(r'^  \["(\w+)", "(\w+)", "([^"]+)", "(--\w+)", "([^"]+)"\],$', table, re.M)
    kat = re.findall(r'\["(\w+)", "([^"]+)"\]', js.split("const SPORT_KAT = [", 1)[1].split("];", 1)[0])
    alias = dict(re.findall(r'(\w+): "(\w+)"', js.split("const SPORT_ALIAS = {", 1)[1].split("};", 1)[0]))
    return rows, kat, alias


# ------------------------------------------------------------------------------------------------ Katalog
def test_genau_die_29_aktivitaeten_in_fuenf_kategorien():
    keys = [k for k, *_ in gpxtools.CATALOG]
    assert len(keys) == len(set(keys)) == 29
    assert [(c, [k for k, _, _, kc in gpxtools.CATALOG if kc == c]) for c, _ in gpxtools.KATEGORIEN] == ERWARTET
    assert gpxtools.KATEGORIEN == [("fuss", "Zu Fuß"), ("rad", "Rad"), ("winter", "Winter"), ("wasser", "Wasser"), ("sonst", "Outdoor und Sonstige")]
    n = gpxtools.SPORT_NAME
    assert (n["mountaineering"], n["mtb"], n["snowshoe"], n["skialpin"], n["walk"], n["climbing"], n["kayak"], n["skaten"], n["paraglide"]) == (
        "Bergsteigen", "Mountainbike", "Schneeschuhwandern", "Ski alpin", "Spazieren / Gehen", "Klettern / Klettersteig", "Kajak / Kanu", "Inlineskaten / Rollschuh", "Gleitschirm")
    assert not set(ENTFERNT_359) & set(keys)


def test_eine_tabelle_je_seite_und_beide_gleich():
    rows, kat, alias = _js_table()
    assert [(k, c, nm) for k, c, nm, _, _ in rows] == [(k, c, nm) for k, nm, _, c in gpxtools.CATALOG]
    assert kat == gpxtools.KATEGORIEN
    assert alias == gpxtools.RUECKFALL                                                       # Rückfall: dieselbe Tabelle auf beiden Seiten
    css = (ROOT / "app" / "static" / "style.css").read_text(encoding="utf-8")
    assert all(f"{col}:" in css for col in {r[3] for r in rows})                             # jede Kartenfarbe ist definiert
    assert all(r[4].strip() for r in rows)                                                   # jede Aktivität hat ein Symbol
    i18n = (JS / "00-i18n-neu.js").read_text(encoding="utf-8") + (JS / "00-i18n.js").read_text(encoding="utf-8")
    names = [nm for _, nm, _, _ in gpxtools.CATALOG] + [nm for _, nm in gpxtools.KATEGORIEN]
    assert [nm for nm in names if f"\n{nm} || " not in i18n and f"\n{nm}|" not in i18n] == []   # jeder Name ist übersetzt


def test_rueckfall_zielt_in_den_katalog_und_deckt_3590_ab():
    keys = set(gpxtools.LABEL)
    assert set(gpxtools.RUECKFALL.values()) <= keys and not set(gpxtools.RUECKFALL) & keys
    assert set(ENTFERNT_359) <= set(gpxtools.RUECKFALL)
    r = gpxtools.RUECKFALL
    assert (r["dogwalk"], r["orienteering"], r["commute"], r["cyclocross"], r["bmx"], r["splitboard"], r["sup"], r["sled"], r["golf"], r["sailing"]) == (
        "walk", "jogging", "touringbicycle", "racebike", "other", "skitour", "kayak", "other", "other", "other")
    fam = [s for v in gpxtools.FAMILIE.values() for s in v]
    assert len(fam) == len(set(fam)) and set(fam) <= keys
    assert gpxtools.roh("other")[0] == "other" and "golf" in gpxtools.roh("golf") and "dogwalk" in gpxtools.roh("walk")


def test_zuordnung_strava_komoot_fit_zepp():
    from app import fitfile, portals
    keys = set(gpxtools.LABEL)
    assert set(portals.STRAVA_SPORT) == keys
    assert set(portals.KOMOOT_SPORT) <= keys and portals.KOMOOT_SPORT["bikepacking"] == "touringbicycle" and portals.KOMOOT_SPORT["rafting"] == "hike"
    assert portals.sende_sport("sup") == "kayak" and portals.sende_sport("dogwalk") == "walk" and portals.sende_sport("golf") == "other" and portals.sende_sport("") == "hike"
    assert portals.STRAVA_SPORT[portals.sende_sport("commute")] == "Ride"
    # FIT: alles landet im Katalog oder über den Rückfall
    assert set(fitfile.SPORT.values()) | set(fitfile.SUB_SPORT.values()) <= keys
    assert fitfile.sport_name((42, 0)) == "rafting" and fitfile.sport_name((26, 0)) == "paraglide" and fitfile.sport_name((14, 37)) == "skitour"
    assert fitfile.sport_name((1, 3)) == "trailrun" and fitfile.sport_name((2, 11)) == "racebike"
    # Zepp: unverändert (1 Laufen, 8 Laufband, 6/7 Gehen = Wandern, 13/22/15 Wandern, 9 Rad, 43/105 Ski alpin, 178 Schneeschuh, 206 E-Bike)
    assert gpxtools.ZEPP_SPORT == {1: "jogging", 6: "hike", 7: "hike", 8: "jogging", 9: "touringbicycle", 13: "hike", 15: "hike", 22: "hike",
                                   43: "skialpin", 105: "skialpin", 178: "snowshoe", 206: "e_touringbicycle"}


GPX = """<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><type>{t}</type><trkseg>
<trkpt lat="47.5" lon="11.0"><ele>800</ele><time>2026-05-01T08:00:00Z</time></trkpt><trkpt lat="47.51" lon="11.01"><ele>820</ele><time>2026-05-01T08:30:00Z</time></trkpt>
</trkseg></trk></gpx>"""


@pytest.mark.parametrize("typ, sport", [("dogwalk", "walk"), ("sup", "kayak"), ("golf", "other"), ("splitboard", "skitour"), ("orienteering", "jogging"),
                                        ("rafting", "rafting"), ("paragliding", "paraglide"), ("bikepacking", "bikepacking"), ("gibtsnicht", "hike")])
def test_import_setzt_den_rueckfall(typ, sport):
    c = gpxtools.convert(GPX.format(t=typ), "x.gpx", "hike")
    assert c["sport"] == sport and f"<type>{sport}</type>" in c["gpx"] and c["tags"] == []


# ------------------------------------------------------------------------------------------------ Altdaten aus 3.59.0
def _alt():
    _tour("d1", "dogwalk", 4); _tour("w1", "walk", 6, tage=41); _tour("g1", "golf", 3, tage=42); _tour("c1", "commute", 20, tage=43)
    _tour("r1", "touringbicycle", 30, tage=44); _tour("s1", "sup", 5, tage=45); _tour("o1", "other", 2, tage=46)


def _sports():
    return {r["id"]: r["sport"] for r in db.query("SELECT id,sport FROM tours")}


def test_touren_bleiben_unveraendert_und_zaehlen_unter_ihrem_rueckfall():
    from app import bausteine_daten as bd, rueckblick, stats
    _alt()
    vorher = _sports()
    with _client() as c:
        assert c.get("/api/bausteine/jahr", params={"zeitraum": "all", "sport": "walk"}).json()["touren"] == 2
        assert c.get("/api/bausteine/jahr", params={"zeitraum": "all", "sport": "other"}).json()["touren"] == 2
        assert c.get("/api/bausteine/jahr", params={"zeitraum": "all", "sport": "kayak"}).json()["touren"] == 1
        assert c.get("/api/bausteine/jahr", params={"zeitraum": "all", "sport": "dogwalk"}).json()["touren"] == 2        # älterer Filter: wie sein Rückfall
        st = c.get("/api/bausteine/statistik", params={"zeitraum": "all", "sport": "touringbicycle"}).json()
        assert st["touren"] == 2 and {t["sport"] for t in st["top"]} == {"touringbicycle"}
        tours = {t["id"]: t for t in c.get("/api/tours").json()}
        assert tours["g1"]["sport"] == "golf"                                                    # die Tour selbst bleibt, wie sie ist
    assert stats.SPORT_DE["golf"] == "Sonstiges" and stats.SPORT_DE["dogwalk"] == "Spazieren / Gehen" and stats.SPORT_DE["sup"] == "Kajak / Kanu"
    ts = db.query("SELECT id,name,sport,start_ts,dist_m,dur_s,up_m FROM tours")
    y = rueckblick._kennzahlen(ts, 2026, "")["sports"]
    assert {s["sport"]: s["km"] for s in y} == {"walk": 10.0, "other": 5.0, "touringbicycle": 50.0, "kayak": 5.0}
    yr = lambda tid: __import__("datetime").datetime.fromtimestamp(db.one("SELECT start_ts FROM tours WHERE id=?", (tid,))["start_ts"], tz=gpxtools.TZ).year
    ids = {t["id"] for t in rueckblick.tours(yr("g1"), "other")}
    assert "g1" in ids and ("o1" in ids) == (yr("o1") == yr("g1")) and rueckblick.check(yr("g1"), "golf")[1] == "other"
    assert bd._rows(["walk"]) and all(r["sport"] == "walk" for r in bd._rows(["walk"]))
    assert _sports() == vorher                                                                   # nichts wurde umgeschrieben


def test_ziele_mit_entferntem_schluessel_zaehlen_ueber_den_rueckfall():
    from app import hinweise, stat_gruppen
    _alt()
    assert stat_gruppen.ziel_sportarten("commute") == {"touringbicycle"} and stat_gruppen.ziel_sportarten("golf") == {"other"}
    rows = hinweise._touren(None)
    jahr = rows[0]["d"].year
    g = {"metric": "km", "sport": "commute", "year": jahr}
    erwartet = sum(r["km"] for r in rows if r["d"].year == jahr and r["id"] in ("c1", "r1"))
    assert abs(hinweise._ziel_wert(g, rows) - erwartet) < 0.01 and erwartet > 0
    assert hinweise._ziel_wert({"metric": "count", "sport": "golf", "year": jahr}, rows) == sum(1 for r in rows if r["d"].year == jahr and r["id"] in ("g1", "o1"))
    with _client() as c:                                                                         # ein neues Ziel mit entferntem Schlüssel wird als Rückfall gespeichert
        assert c.post("/api/goals", json={"year": jahr, "target": 10, "metric": "km", "sport": "dogwalk"}).status_code == 200
        assert [x["sport"] for x in c.get("/api/goals").json()] == ["walk"]


def test_sportart_setzen_nur_aus_dem_katalog():
    _tour("k1", "golf")
    with _client() as c:
        for sp in ENTFERNT_359[:5] + ["golf"]:
            assert c.post("/api/tours/k1/sport", json={"sport": sp}).status_code == 400
        for sp in ("bikepacking", "rafting", "paraglide", "dragonboat", "boat"):
            r = c.post("/api/tours/k1/sport", json={"sport": sp})
            assert r.status_code == 200 and r.json()["sport"] == sp


def test_auswertungen_der_familien_und_pruefen():
    from app import more, trackfix
    assert trackfix.kind("dogwalk") == "walk" and trackfix.kind("orienteering") == "run" and trackfix.kind("commute") == "bike" and trackfix.kind("golf") == "other"
    assert trackfix.kind("bikepacking") == "bike" and trackfix.kind("climbing") == "walk"
    t = {"id": "x", "name": "x", "sport": "dogwalk", "start_ts": NOW, "dist_m": 20000, "dur_s": 3600, "source": "local"}
    imp = more.implausible([t])
    assert imp and imp[0]["suggest"] == "touringbicycle" and "km/h" in imp[0]["why"]


# ------------------------------------------------------------------------------------------------ Favoriten und Statistik-Gruppen
def test_favoriten_bereinigen_entfernte_still():
    from app import aktivitaeten as ak
    db.put(ak.KEY, json.dumps(["golf", "hike", "sup", "bikepacking"]))
    assert ak.favoriten() == ["hike", "bikepacking"]
    db.put(ak.KEY, json.dumps(["golf", "sup"]))
    assert ak.favoriten() == ak.FAV_DEF                                                          # nichts übrig: Vorgabe
    with _client() as c:
        r = c.put("/api/aktivitaeten/favoriten", json={"favoriten": ["dogwalk", "rafting", "hike"]})
        assert r.status_code == 200 and r.json()["favoriten"] == ["rafting", "hike"]
        assert c.put("/api/aktivitaeten/favoriten", json={"favoriten": ["golf"]}).status_code == 400
        assert c.put("/api/aktivitaeten/favoriten", json={"favoriten": ["parkour"]}).status_code == 400
        d = c.get("/api/aktivitaeten/favoriten").json()
        assert [k["name"] for k in d["kategorien"]][-1] == "Outdoor und Sonstige" and d["kategorien"][2]["sports"][-1] == "snowshoe"


def test_statistik_gruppen_bereinigen_entfernte_still():
    from app import stat_gruppen as sg
    _alt()
    db.put(sg.KEY, json.dumps([{"id": "a", "name": "Gehen", "sports": ["hike", "dogwalk", "walk"]}, {"id": "b", "name": "Wasser", "sports": ["sup", "golf"]},
                               {"id": "c", "name": "Rad", "sports": ["commute", "touringbicycle", "racebike"]}]))
    assert sg.load() == [{"id": "a", "name": "Gehen", "sports": ["hike", "walk"]}, {"id": "c", "name": "Rad", "sports": ["touringbicycle", "racebike"]}]
    assert sg.key("dogwalk") == "sgrp:a" and sg.key("commute") == "sgrp:c" and sg.key("golf") == "other"
    with _client() as c:
        r = c.put("/api/stats/gruppen", json={"gruppen": [{"name": "Berg", "sports": ["hike", "mountaineering", "orienteering"]}]})
        assert r.status_code == 200 and r.json()["gruppen"][0]["sports"] == ["hike", "mountaineering"]
        d = c.get("/api/stats/gruppen").json()
        assert not set(ENTFERNT_359) & set(d["sportarten"]) and {"walk", "other", "kayak"} <= set(d["sportarten"])
        assert d["vorschlaege"][0]["name"] == "Wandern und Bergsteigen" and "bikepacking" in d["vorschlaege"][1]["sports"]
    with pytest.raises(HTTPException):
        sg.pruefen([{"name": "X", "sports": ["hike", "golf"]}], {"hike", "other"})         # nach dem Weglassen nur noch eine Sportart


# ------------------------------------------------------------------------------------------------ Oberfläche (Quelltext) und Version
def test_oberflaeche_nutzt_den_rueckfall_an_einer_stelle():
    g = (JS / "01-grundlagen.js").read_text(encoding="utf-8")
    assert "const sNorm = s =>" in g and "t.sport_alt = t.sport" in g and "sNorm(s) === s" in g and "favoriten.filter(k => SPORT[k])" in g
    sp = (JS / "24-sport.js").read_text(encoding="utf-8")
    fam = dict((k, re.findall(r'"(\w+)"', v)) for k, v in re.findall(r"^  (\w+): \[([^\]]*)\]", sp.split("const SPORT_GRP = {", 1)[1].split("};", 1)[0], re.M))
    assert {k: tuple(v) for k, v in fam.items()} == gpxtools.FAMILIE
    v = (JS / "05-verwaltung.js").read_text(encoding="utf-8")
    assert 'id="katp"' in v and 'id="favp"' in v and 'id="sgp"' in v and "function katAdmin" in v
    assert [k for k, _ in re.findall(r'\["(\w+)", "([^"]+)"\]', v.split("const KAT_FRUEHER = [", 1)[1].split("];", 1)[0])] == ENTFERNT_359
    st = (JS / "13-start.js").read_text(encoding="utf-8")
    assert re.findall(r'^  \["(\w+)", "', st.split("const ADM_TABS = [", 1)[1].split("];", 1)[0], re.M) == [
        "uebersicht", "sportarten", "quellen", "weitergabe", "fotos", "auto", "handy", "sicher"]


def test_version_texte_und_dateien():
    notes = (ROOT / "docs" / "versionen" / "3.60.0.md").read_text(encoding="utf-8")
    assert notes.startswith("# 3.60.0") and "Was ist neu" in notes and "Bestand" in notes and "Verwaltung" in notes and "Bikepacking" in notes and "Gassigehen" in notes
    assert "3.60.0" in (ROOT / "docs" / "versionen" / "README.md").read_text(encoding="utf-8")
    assert "Version 3.60.0" in (ROOT / "docs" / "VERSIONSVERLAUF.md").read_text(encoding="utf-8")
    hb = (ROOT / "docs" / "HANDBUCH.md").read_text(encoding="utf-8")
    assert "Verwaltung → Sportarten" in hb and "Sportarten-Katalog" in hb and "Bergsteigen" in hb       # 3.60.1: Begriff „Sportart“
