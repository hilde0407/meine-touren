"""3.59.0 – Statistik-Gruppen (app/stat_gruppen.py): Prüfen und Bereinigen, Speichern, ohne Einstellung jede Aktivität einzeln, Vorschläge, Sicherung und
Wiederherstellung, Auswertungen mit Gruppe gegenüber ohne (Bausteine, Hinweise, Ziele, Jahresrückblick, Eigene Kennzahl), Layout-Filter, Betrachter.
Dazu der Aktivitäten-Katalog, die Favoriten-Aktivitäten und „Schneeschuh-Touren als Schneeschuh führen“ (rückgängig machbar).
Alle Zeitpunkte relativ zu „jetzt“ und mit zeitraum=all bzw. dem Jahr der Tour – unabhängig von der Zeitzone (die CI läuft in UTC)."""
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import config, db, extras, stat_gruppen as sg  # noqa: E402
from app.gpxtools import TZ  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NOW = int(time.time())


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _tour(tid, sport, km=10.0, tage=40, up=100):
    ts = NOW - tage * 86400
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
               (tid, f"Tour {tid}", sport, ts, ts + 3600, km * 1000, 3600, up, up, 48.0, 8.0, "tour_recorded"))


def _daten():
    _tour("w1", "hike", 10); _tour("w2", "hike", 12, tage=50); _tour("b1", "mountaineering", 8, tage=60)
    _tour("r1", "touringbicycle", 40, tage=70); _tour("m1", "mtb", 30, tage=80); _tour("s1", "skitour", 9, tage=90)


GR = [{"name": "Bergwandern", "sports": ["hike", "mountaineering"]}]


# ------------------------------------------------------------------------------------------------ Prüfen, Bereinigen, Speichern
def test_pruefen_grenzen_und_bereinigung():
    k = {"hike", "mountaineering", "nordicwalking", "touringbicycle", "mtb", "skitour"}
    out = sg.pruefen([{"name": "  Berg   wandern ", "sports": ["hike", "mountaineering", "hike"]}], k)
    assert out[0]["name"] == "Berg wandern" and out[0]["sports"] == ["hike", "mountaineering"] and sg.ID_RE.match(out[0]["id"])
    bad = [
        [{"name": "", "sports": ["hike", "mtb"]}],
        [{"name": "x" * 31, "sports": ["hike", "mtb"]}],
        [{"name": "A<b>", "sports": ["hike", "mtb"]}],
        [{"name": "A", "sports": ["hike"]}],
        [{"name": "A", "sports": ["hike", "gibtsnicht"]}],
        [{"name": "A", "sports": ["hike", "mtb"]}, {"name": "B", "sports": ["hike", "skitour"]}],      # Sportart in zwei Gruppen
        [{"name": "A", "sports": ["hike", "mtb"]}, {"name": "a", "sports": ["skitour", "touringbicycle"]}],   # gleicher Name
        [{"name": f"G{i}", "sports": ["hike", "mtb"]} for i in range(9)],
        "keine Liste",
        [{"name": "A", "sports": ["hike", "sgrp:x"]}],
    ]
    for b in bad:
        with pytest.raises(HTTPException) as e:
            sg.pruefen(b, k)
        assert e.value.status_code == 400
    # doppelte oder ungültige Kennungen werden neu vergeben
    out = sg.pruefen([{"id": "abc", "name": "A", "sports": ["hike", "mtb"]}, {"id": "abc", "name": "B", "sports": ["skitour", "touringbicycle"]},
                      {"id": "NO!", "name": "C", "sports": ["mountaineering", "nordicwalking"]}], k)
    assert out[0]["id"] == "abc" and out[1]["id"] != "abc" and sg.ID_RE.match(out[2]["id"]) and len({g["id"] for g in out}) == 3


def test_bereinigen_ist_nachsichtig():
    k = {"hike", "mountaineering", "mtb", "racebike"}
    raw = [{"id": "a", "name": "Gut", "sports": ["hike", "mountaineering", "weg"]}, {"id": "b", "name": "Doppelt", "sports": ["hike", "mtb"]},
           {"name": "", "sports": ["mtb", "racebike"]}, "Müll", {"id": "c", "name": "Rad", "sports": ["mtb", "racebike"]}]
    assert sg.bereinigen(raw, k) == [{"id": "a", "name": "Gut", "sports": ["hike", "mountaineering"]}, {"id": "c", "name": "Rad", "sports": ["mtb", "racebike"]}]
    assert sg.bereinigen("x", k) == [] and len(sg.bereinigen([{"name": f"G{i}", "sports": ["hike", "mtb"]} for i in range(9)], {"hike", "mtb"})) == 1


def test_ohne_einstellung_jede_aktivitaet_einzeln():
    _daten()
    assert db.get(sg.KEY) == "" and sg.load() == [] and sg.key("mountaineering") == "mountaineering"
    assert sg.expand([]) is None and sg.expand(["hike"]) == {"hike"}
    with _client() as c:
        d = c.get("/api/stats/gruppen").json()
        assert d["gruppen"] == [] and [v["id"] for v in d["vorschlaege"]] == ["foot", "bike", "ski"]
        assert d["vorschlaege"][0]["sports"] == ["hike", "mountaineering", "snowshoe"] and "mtb_easy" in d["vorschlaege"][1]["sports"]
        assert {"hike", "skitour", "skialpin", "nordic", "snowshoe", "kayak", "mtb_easy"} <= set(d["sportarten"]) and d["max"] == 8 and d["name_max"] == 30
        assert c.get("/api/bausteine/jahr", params={"zeitraum": "all"}).json()["touren"] == 6
        # Vorschläge werden nie automatisch gespeichert
        assert c.get("/api/stats/gruppen").json()["gruppen"] == [] and db.get(sg.KEY) == ""


def test_speichern_lesen_und_leeren():
    _daten()
    with _client() as c:
        r = c.put("/api/stats/gruppen", json={"gruppen": GR})
        assert r.status_code == 200, r.text
        g = r.json()["gruppen"]
        assert g[0]["name"] == "Bergwandern" and g[0]["sports"] == ["hike", "mountaineering"]
        assert c.get("/api/stats/gruppen").json()["gruppen"] == g and json.loads(db.get(sg.KEY)) == g
        assert c.put("/api/stats/gruppen", json={"gruppen": [{"name": "X", "sports": ["hike"]}]}).status_code == 400
        assert c.get("/api/stats/gruppen").json()["gruppen"] == g                       # ein Fehler ändert nichts
        assert c.put("/api/stats/gruppen", json={}).status_code == 400
        # Vorschlag übernehmen: die Kennung „bike“ bleibt
        v = c.get("/api/stats/gruppen").json()["vorschlaege"][1]
        g2 = c.put("/api/stats/gruppen", json={"gruppen": g + [v]}).json()["gruppen"]
        assert g2[1]["id"] == "bike" and g2[1]["name"] == "Rad (alle)"
        assert c.put("/api/stats/gruppen", json={"gruppen": []}).json()["gruppen"] == []
        assert c.get("/api/stats/gruppen").json()["gruppen"] == [] and db.get(sg.KEY) == ""


def test_eigene_sportart_aus_den_touren_ist_bekannt():
    _tour("k1", "parkour"); _tour("w1", "hike")                                    # eine Kennung, die der Katalog nicht kennt (z. B. von Komoot)
    with _client() as c:
        assert "parkour" in c.get("/api/stats/gruppen").json()["sportarten"]
        assert c.put("/api/stats/gruppen", json={"gruppen": [{"name": "Berg", "sports": ["hike", "parkour"]}]}).status_code == 200
    db.execute("DELETE FROM tours WHERE id='k1'")                                       # Sportart verschwindet: die Gruppe fällt beim Lesen weg, kein Fehler
    assert sg.load() == []


def test_gespeicherter_unsinn_wird_beim_lesen_ignoriert():
    db.put(sg.KEY, "{kaputt")
    assert sg.load() == []
    db.put(sg.KEY, json.dumps([{"id": "x", "name": "Q", "sports": ["hike", "nix"]}]))
    assert sg.load() == []


# ------------------------------------------------------------------------------------------------ Auswertungen: mit Gruppe gegenüber ohne
def test_zentrale_regeln():
    gr = [{"id": "bw", "name": "Bergwandern", "sports": ["hike", "mountaineering"]}]
    assert sg.key("hike", gr) == "sgrp:bw" and sg.key("snowshoe", gr) == "snowshoe" and sg.key("mtb", gr) == "mtb"
    assert sg.name("sgrp:bw", gr) == "Bergwandern" and sg.name("mtb", gr) == "Mountainbike" and sg.name("sgrp:weg", gr) == "sgrp:weg"
    assert sg.expand(["sgrp:bw", "mtb"], gr) == {"hike", "mountaineering", "mtb"} and sg.expand(["sgrp:weg"], gr) is None
    assert sg.plain(["mtb", "sgrp:bw"], gr) == ["mtb", "hike", "mountaineering"] and sg.plain(["sgrp:weg"], gr) == []
    assert sg.passt("mountaineering", sg.expand(["sgrp:bw"], gr)) and not sg.passt("mtb", sg.expand(["sgrp:bw"], gr)) and sg.passt("mtb", None)
    with pytest.raises(HTTPException):
        sg.filter_liste("hike,<x>")
    assert sg.filter_liste("hike,sgrp:bw,hike") == ["hike", "sgrp:bw"]


def test_bausteine_auswertung_mit_gruppe_und_ohne():
    _daten()
    with _client() as c:
        gid = c.put("/api/stats/gruppen", json={"gruppen": GR}).json()["gruppen"][0]["id"]
        mit = c.get("/api/bausteine/jahr", params={"zeitraum": "all", "sport": f"sgrp:{gid}"}).json()
        ohne = c.get("/api/bausteine/jahr", params={"zeitraum": "all", "sport": "hike,mountaineering"}).json()
        nur = c.get("/api/bausteine/jahr", params={"zeitraum": "all", "sport": "hike"}).json()
        assert mit["touren"] == ohne["touren"] == 3 and nur["touren"] == 2 and abs(mit["km"] - 30) < 0.01
        st = c.get("/api/bausteine/statistik", params={"zeitraum": "all", "sport": f"sgrp:{gid}"}).json()
        assert st["touren"] == 3 and {t["sport"] for t in st["top"]} == {"hike", "mountaineering"}
        assert c.get("/api/bausteine/saison", params={"zeitraum": "all", "sport": f"sgrp:{gid},mtb"}).json()["touren"] == 4
        # gelöschte Gruppe in einem gespeicherten Filter: alle Sportarten, kein Fehler
        assert c.get("/api/bausteine/jahr", params={"zeitraum": "all", "sport": "sgrp:weg"}).json()["touren"] == 6
        assert c.get("/api/bausteine/jahr", params={"zeitraum": "all", "sport": "sgrp:<x>"}).status_code == 400
        h = c.get("/api/bausteine/hinweise", params={"sport": f"sgrp:{gid}"})
        assert h.status_code == 200, h.text


def test_ziele_mit_familie_eigener_und_geloeschter_gruppe():
    from app import hinweise
    _daten()
    zs = hinweise._ziel_sportarten
    # ohne Gruppen: ältere Ziele grp:… zählen die Aktivitäten-Familie (Schneeschuh gehört zu „Zu Fuß“), sgrp ohne Gruppe = alle
    assert zs("grp:bike") == {"touringbicycle", "e_touringbicycle", "racebike", "mtb", "mtb_easy", "e_mtb", "bikepacking"} and "snowshoe" in zs("grp:foot")   # 3.60.0: Katalog
    assert zs("sgrp:x") is None and zs("mtb") == {"mtb"} and zs("snowshoe") == {"snowshoe"} and zs("") is None
    with _client() as c:
        # Vorschlag „Rad (alle)“ ohne MTB übernehmen: das ältere Ziel „Alle Rad-Sportarten“ (grp:bike) folgt der Gruppe mit dieser Kennung
        rad = {"id": "bike", "name": "Rad", "sports": ["touringbicycle", "e_touringbicycle", "racebike"]}
        assert c.put("/api/stats/gruppen", json={"gruppen": [rad, {"name": "Gelände", "sports": ["mtb", "touringbicycle"]}]}).status_code == 400   # Radtour doppelt
        g = c.put("/api/stats/gruppen", json={"gruppen": [rad, {"name": "Gelände", "sports": ["mtb", "nordicwalking"]}]}).json()["gruppen"]
        neu = next(x for x in g if x["name"] == "Gelände")
        assert zs("grp:bike") == {"touringbicycle", "e_touringbicycle", "racebike"} and zs("sgrp:" + neu["id"]) == {"mtb", "nordicwalking"}
        y = datetime.fromtimestamp(NOW - 40 * 86400, tz=TZ).year
        assert c.post("/api/goals", json={"year": y, "target": 100, "metric": "km", "sport": "sgrp:" + neu["id"]}).status_code == 200
        assert c.post("/api/goals", json={"year": y, "target": 100, "metric": "km", "sport": "sgrp:gibtsnicht"}).status_code == 400
        assert [x["sport"] for x in c.get("/api/goals").json()] == ["sgrp:" + neu["id"]]
        # Gruppen löschen: grp:bike wieder die Familie, das Ziel der gelöschten Gruppe zählt alle Sportarten – kein Fehler
        c.put("/api/stats/gruppen", json={"gruppen": []})
        assert "mtb" in zs("grp:bike") and zs("sgrp:" + neu["id"]) is None
        assert c.get("/api/bausteine/hinweise").status_code == 200


def test_jahresrueckblick_fasst_zusammen():
    from app import rueckblick
    _daten()
    y = datetime.fromtimestamp(NOW - 40 * 86400, tz=TZ).year
    ts = db.query("SELECT id,name,sport,start_ts,dist_m,dur_s,up_m FROM tours WHERE id IN ('w1','w2','b1')")       # unabhängig davon, ob die Touren ins selbe Kalenderjahr fallen
    names = lambda: {s["name"]: s["km"] for s in rueckblick._kennzahlen(ts, y, "")["sports"]}
    assert names() == {"Wandern": 22.0, "Bergsteigen": 8.0}
    sg.save(GR)
    assert names() == {"Bergwandern": 30.0}


def test_layout_filter_und_eigene_kennzahl_nehmen_gruppen_an():
    from app import kennzahl, layout
    _daten()
    gid = sg.save(GR)[0]["id"]
    assert layout._known("sports", ["hike", f"sgrp:{gid}"]) == ["hike", f"sgrp:{gid}"]
    with pytest.raises(HTTPException):
        layout._known("sports", ["sgrp:A B"])
    rows = kennzahl._rows({"sports": [f"sgrp:{gid}"]})
    assert {r["id"] for r in rows} == {"w1", "w2", "b1"}
    assert len(kennzahl._rows({"sports": ["sgrp:weg"]})) == 6


def test_betrachter_darf_lesen_aber_nicht_schreiben():
    from app import main
    assert main.VIEWER_GET.match("/api/stats/gruppen") and not main.VIEWER_GET.match("/api/stats/gruppen/x")


# ------------------------------------------------------------------------------------------------ Sicherung und Wiederherstellung
def test_sicherung_enthaelt_die_gruppen_und_die_wiederherstellung_bringt_sie_zurueck(tmp_path, monkeypatch):
    import io
    import sqlite3
    import zipfile
    from app import wiederherstellung as wh
    _daten()
    g = sg.save(GR)
    name, data = extras.make_backup(strip_secrets=True)                                 # Download „Datensicherung“ (ohne Zugangsdaten)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        (tmp_path / "x.sqlite").write_bytes(z.read("komoot_hub.sqlite"))
    con = sqlite3.connect(str(tmp_path / "x.sqlite"))
    assert json.loads(con.execute("SELECT v FROM settings WHERE k=?", (sg.KEY,)).fetchone()[0]) == g
    con.close()
    root = tmp_path / "bak"
    monkeypatch.setattr(config, "backup_dirs", lambda uid=None: [root / uid if uid else root])
    wh._tokens.clear()
    p = extras.make_backup(str(root))
    db.put(sg.KEY, "")
    assert sg.load() == []
    with _client() as c:
        v = c.post("/api/restore/check", json={"id": f"s:0:{Path(p).name}"}).json()
        r = c.post("/api/restore/run", json={"id": v["id"], "token": v["token"], "bestaetigt": True})
        assert r.status_code == 200, r.text
        assert c.get("/api/stats/gruppen").json()["gruppen"] == g
    wh._tokens.clear()


def test_sicherung_ohne_schluessel_gibt_keine_gruppen(tmp_path, monkeypatch):
    from app import wiederherstellung as wh
    _daten()
    root = tmp_path / "bak"
    monkeypatch.setattr(config, "backup_dirs", lambda uid=None: [root / uid if uid else root])
    wh._tokens.clear()
    p = extras.make_backup(str(root))                                                   # wie eine Sicherung von 3.58.0: kein Schlüssel
    sg.save(GR)
    with _client() as c:
        v = c.post("/api/restore/check", json={"id": f"s:0:{Path(p).name}"}).json()
        assert c.post("/api/restore/run", json={"id": v["id"], "token": v["token"], "bestaetigt": True}).status_code == 200
        assert c.get("/api/stats/gruppen").json()["gruppen"] == []
    wh._tokens.clear()


# ------------------------------------------------------------------------------------------------ Version und Dateien
def test_version_texte_und_dateien():
    notes = (ROOT / "docs" / "versionen" / "3.59.0.md").read_text(encoding="utf-8")
    assert notes.startswith("# 3.59.0") and "Was ist neu" in notes and "Wie benutze ich es" in notes and "Schneeschuh" in notes and "Favoriten" in notes
    assert "3.59.0" in (ROOT / "docs" / "versionen" / "README.md").read_text(encoding="utf-8")
    assert "Version 3.59.0" in (ROOT / "docs" / "VERSIONSVERLAUF.md").read_text(encoding="utf-8")
    assert "Aktivitäten zusammenfassen" in (ROOT / "docs" / "HANDBUCH.md").read_text(encoding="utf-8")
    i18n = (ROOT / "app" / "static" / "js" / "00-i18n-neu.js").read_text(encoding="utf-8")
    for k in ("Statistik: Aktivitäten zusammenfassen || ", "{} (zusammengefasst) || ", "Gruppen speichern || ", "Zu Fuß || ", "Favoriten-Aktivitäten || ", "Kajak/Kanu || ", "Schneeschuh-Touren || "):
        assert k in i18n
    js = (ROOT / "app" / "static" / "js" / "01-grundlagen.js").read_text(encoding="utf-8")
    assert "const sgKey" in js and "function sgExpand" in js and "const sgMatch" in js


# ------------------------------------------------------------------------------------------------ Aktivitäten-Katalog
# 3.60.0: Der Katalog (29 Aktivitäten) und die Gleichheit beider Tabellen prüft tests/test_katalog_360.py.
def test_neue_aktivitaet_setzen_und_hochladen(monkeypatch):
    from app import portals, tracks
    _tour("k1", "hike")
    with _client() as c:
        for sp in ("kayak", "mtb_easy", "snowshoe", "trailrun"):
            r = c.post("/api/tours/k1/sport", json={"sport": sp})
            assert r.status_code == 200 and r.json()["sport"] == sp
        assert c.post("/api/tours/k1/sport", json={"sport": "fliegen"}).status_code == 400
    assert portals.STRAVA_SPORT["kayak"] == "Kayaking" and portals.KOMOOT_SPORT.get("mtb_easy") is None and portals.KOMOOT_SPORT["kayak"] == "hike"


# ------------------------------------------------------------------------------------------------ Favoriten
def test_favoriten_vorgabe_speichern_pruefen():
    from app import aktivitaeten as ak
    with _client() as c:
        d = c.get("/api/aktivitaeten/favoriten").json()
        assert d["favoriten"] == ["hike", "jogging", "touringbicycle", "skitour", "mtb"] == d["standard"] and d["max"] == 12
        assert [k["id"] for k in d["kategorien"]] == ["fuss", "rad", "winter", "wasser", "sonst"] and "kayak" in d["kategorien"][3]["sports"]
        r = c.put("/api/aktivitaeten/favoriten", json={"favoriten": ["kayak", "hike", "kayak", "snowshoe"]})
        assert r.status_code == 200 and r.json()["favoriten"] == ["kayak", "hike", "snowshoe"]
        assert c.get("/api/aktivitaeten/favoriten").json()["favoriten"] == ["kayak", "hike", "snowshoe"] and json.loads(db.get(ak.KEY)) == ["kayak", "hike", "snowshoe"]
        for bad in ([], ["fliegen"], [f"x{i}" for i in range(3)], list(ak.FAV_DEF) + ["walk", "climbing", "nordicwalking", "snowshoe", "trailrun", "racebike", "mtb_easy", "e_mtb"], "hike"):
            assert c.put("/api/aktivitaeten/favoriten", json={"favoriten": bad}).status_code == 400
        assert c.put("/api/aktivitaeten/favoriten", json={}).status_code == 400
    db.put(ak.KEY, "kaputt")
    assert ak.favoriten() == ak.FAV_DEF
    from app import main
    assert main.VIEWER_GET.match("/api/aktivitaeten/favoriten")


def test_favoriten_in_der_sicherung(tmp_path):
    import io
    import sqlite3
    import zipfile
    from app import aktivitaeten as ak
    db.put(ak.KEY, json.dumps(["kayak", "hike"]))
    _, data = extras.make_backup(strip_secrets=True)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        (tmp_path / "x.sqlite").write_bytes(z.read("komoot_hub.sqlite"))
    con = sqlite3.connect(str(tmp_path / "x.sqlite"))
    assert json.loads(con.execute("SELECT v FROM settings WHERE k=?", (ak.KEY,)).fetchone()[0]) == ["kayak", "hike"]
    con.close()


# ------------------------------------------------------------------------------------------------ Schneeschuh als eigene Sportart führen
def test_schneeschuh_touren_umstellen_und_zuruecknehmen():
    from app import sport_umzug
    _tour("s1", "hike"); _tour("s2", "hike", tage=41); _tour("w1", "hike", tage=42); _tour("s3", "hike", tage=43)
    for t in ("s1", "s2", "s3"):
        db.execute("INSERT INTO tour_tags(id,tag) VALUES(?, 'Schneeschuh')", (t,))
    db.execute("INSERT INTO tour_sport(id,sport) VALUES('s3','hike')")                  # früher von Hand gewählt
    with _client() as c:
        d = c.get("/api/schneeschuh").json()
        assert sorted(k["id"] for k in d["kandidaten"]) == ["s1", "s2", "s3"] and d["umgestellt"] == 0
        assert c.post("/api/schneeschuh/umstellen", json={"ids": ["s1", "w1"]}).json()["n"] == 1     # nur Kandidaten
        assert c.post("/api/schneeschuh/umstellen", json={}).json()["n"] == 2
        sp = {r["id"]: r["sport"] for r in db.query("SELECT id,sport FROM tours")}
        assert sp == {"s1": "snowshoe", "s2": "snowshoe", "s3": "snowshoe", "w1": "hike"}
        assert {r["id"] for r in db.query("SELECT id FROM tour_tags WHERE tag='Schneeschuh'")} == {"s1", "s2", "s3"}   # das Schlagwort bleibt
        assert c.get("/api/schneeschuh").json() == {"kandidaten": [], "umgestellt": 3}
        # der Neustart legt nichts wieder zusammen
        db.close_all(); db.init()
        assert db.one("SELECT sport FROM tours WHERE id='s1'")["sport"] == "snowshoe"
        # eine Tour danach von Hand geändert: bleibt beim Zurücknehmen
        c.post("/api/tours/s2/sport", json={"sport": "mountaineering"})
        assert c.post("/api/schneeschuh/zuruecknehmen").json()["n"] == 2
        sp = {r["id"]: r["sport"] for r in db.query("SELECT id,sport FROM tours")}
        assert sp == {"s1": "hike", "s2": "mountaineering", "s3": "hike", "w1": "hike"}
        assert db.one("SELECT sport FROM tour_sport WHERE id='s3'")["sport"] == "hike" and not db.one("SELECT 1 x FROM tour_sport WHERE id='s1'")
        assert c.get("/api/schneeschuh").json()["umgestellt"] == 0
    assert sport_umzug.FLAG_SNOW and db.get(sport_umzug.FLAG_SNOW)


def test_komoot_abgleich_stellt_umgestellte_nicht_zurueck():
    from app import sync
    _tour("k9", "hike")
    db.execute("INSERT INTO tour_tags(id,tag) VALUES('k9','Schneeschuh')")
    db.execute("INSERT INTO sport_merged(id,orig,ts) VALUES('k9','snowshoe',0)")
    t = {"id": "k9", "name": "Hörnle", "sport": "snowshoe", "start_ts": NOW - 40 * 86400, "end_ts": NOW - 40 * 86400 + 3600, "dist_m": 7000, "dur_s": 3600,
         "up_m": 300, "down_m": 300, "lat": 47.6, "lng": 11.0, "status": "tour_recorded"}

    class K:
        def tours(self):
            return [dict(t)]
    sync.refresh_tours(K())
    assert db.one("SELECT sport FROM tours WHERE id='k9'")["sport"] == "hike"            # nicht still umgestellt
    with _client() as c:
        c.post("/api/schneeschuh/umstellen", json={})
    sync.refresh_tours(K())
    assert db.one("SELECT sport FROM tours WHERE id='k9'")["sport"] == "snowshoe"
