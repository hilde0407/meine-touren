"""3.50.0: Laufen als eigene Sportart (Zepp-Typ 1/8), Umzug bestehender Daten.
3.59.0: Schneeschuh ist wieder eine eigene Sportart – nichts wird mehr zusammengelegt (auch nicht beim Öffnen älterer Datenbanken); die Tests sind darauf umgestellt."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.test_core import fresh, gpx  # noqa: F401  (setzt die Testumgebung und liefert die Fixture)
from app import config, db, gpxtools, sport_umzug, sync, tracks  # noqa

T0 = int(time.time()) - 40 * 86400


def _tour(i, sport="hike", ts=None, source="local", dist=8000, dur=7200):
    ts = ts or T0
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (i, "Tour " + i, sport, ts, ts + dur, dist, dur, 100, 100, 47.0, 11.0, "tour_recorded", source))


def _workout(trackid, ztype, sport="hike", komoot_id=None, status="local", dist=8000, dur=2700):
    db.execute("INSERT OR REPLACE INTO workouts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
               (trackid, trackid, trackid + dur, ztype, sport, dist, dur, None, status, komoot_id, "", int(time.time())))


def _tags(tid):
    return sorted(r["tag"] for r in db.query("SELECT tag FROM tour_tags WHERE id=?", (tid,)))


def _reopen():
    """Datenbank schließen und wieder öffnen: der Umzug läuft beim Öffnen (db.migrate)."""
    db.close_all()
    db.init()


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


# ---------- Zuordnung ----------
def test_zepp_zuordnung_und_alias():
    z = gpxtools.ZEPP_SPORT
    assert z[1] == "jogging" and z[8] == "jogging"
    assert all(z[k] == "hike" for k in (6, 7, 13, 15, 22))
    assert z[178] == "snowshoe" and gpxtools.norm("snowshoe") == ("snowshoe", None)
    assert gpxtools.ALIAS["running"] == "jogging" and gpxtools.ALIAS["type_1"] == "jogging" and gpxtools.ALIAS["walking"] == "hike"
    assert "snowshoe" in gpxtools.LABEL and gpxtools.known("snowshoe") and gpxtools.known("jogging")
    assert gpxtools.norm("jogging") == ("jogging", None) and gpxtools.norm("") == ("", None)


def test_convert_schneeschuh_und_laufen():
    g = gpx("Workout--2026-01-10--10-00-00.gpx")
    c = gpxtools.convert(g.replace("<type>hiking</type>", "<type>snowshoe</type>"), "a.gpx")
    assert c["sport"] == "snowshoe" and c["tags"] == [] and c["name"].startswith("Schneeschuhwanderung")
    c = gpxtools.convert(g.replace("<type>hiking</type>", "<type>running</type>"), "a.gpx")
    assert c["sport"] == "jogging" and c["tags"] == []
    c = gpxtools.convert(g, "a.gpx")
    assert c["sport"] == "hike" and c["tags"] == []


def test_adopt_schneeschuh_bleibt_schneeschuh(fresh):
    g = gpx("Workout--2026-01-11--10-00-00.gpx")
    t, _ = tracks.adopt(g, "a.gpx", sport="snowshoe")
    assert t["sport"] == "snowshoe" and _tags(t["id"]) == []
    tracks.add_tag(t["id"], "Schneeschuh")
    assert _tags(t["id"]) == ["Schneeschuh"]                              # nie doppelt


def test_aufzeichnung_schneeschuh(fresh):
    c = _client()
    g = gpx("Workout--2026-01-12--10-00-00.gpx")
    r = c.post("/api/record/upload", json={"gpx": g, "sport": "snowshoe", "name": "Winter"})
    assert r.status_code == 200, r.text
    tid = r.json()["id"]
    assert db.one("SELECT sport FROM tours WHERE id=?", (tid,))["sport"] == "snowshoe" and _tags(tid) == []
    r = c.post("/api/record/upload", json={"gpx": gpx("Workout--2026-01-13--10-00-00.gpx"), "sport": "jogging"})
    assert db.one("SELECT sport FROM tours WHERE id=?", (r.json()["id"],))["sport"] == "jogging"


def test_sportart_aendern_schneeschuh_alter_client(fresh):
    _tour("a")
    r = _client().post("/api/tours/a/sport", json={"sport": "snowshoe"})
    assert r.status_code == 200 and r.json()["sport"] == "snowshoe"
    assert db.one("SELECT sport FROM tours WHERE id='a'")["sport"] == "snowshoe" and db.one("SELECT sport FROM tour_sport WHERE id='a'")["sport"] == "snowshoe"
    assert _tags("a") == []


def test_ziel_plan_ausruestung_speichern_normalisiert(fresh):
    c = _client()
    assert c.post("/api/goals", json={"year": 2026, "sport": "snowshoe", "metric": "km", "target": 100}).status_code == 200
    assert db.one("SELECT sport FROM goals")["sport"] == "snowshoe"
    assert c.post("/api/gear", json={"name": "Schuhe", "kind": "Schuhe", "sports": ["snowshoe", "hike", "jogging"]}).status_code == 200
    assert db.one("SELECT sports FROM gear")["sports"] == "snowshoe,hike,jogging"


def test_zepp_uebernahme_alter_exportdatei_wird_lauf(fresh, tmp_path):
    g = gpx("Workout--2026-02-01--09-00-00.gpx")
    p = tmp_path / "w.gpx"
    p.write_text(g.replace("<type>hiking</type>", "<type>hike</type>"), encoding="utf-8")      # so schrieben Versionen bis 3.49.0 einen Lauf
    db.execute("INSERT INTO workouts VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (555, 555, 999, 1, "jogging", 3000, 900, str(p), "new", None, "", 0))
    tid = sync.adopt_workout(555)
    assert db.one("SELECT sport FROM tours WHERE id=?", (tid,))["sport"] == "jogging"


# ---------- Umzug bestehender Daten ----------
def _alter_stand():
    db.execute("DELETE FROM settings WHERE k=?", (sport_umzug.FLAG,))
    _tour("s1", "snowshoe", T0 + 1000)
    _tour("s2", "snowshoe", T0 + 2000)
    db.execute("INSERT INTO tour_tags(id,tag) VALUES('s2','Schneeschuh')")             # hat das Schlagwort schon
    _tour("s3", "hike", T0 + 3000)
    db.execute("INSERT INTO tour_sport(id,sport) VALUES('s3','snowshoe')")              # von Hand gewählt (Tabelle eigen)
    db.execute("INSERT INTO plans(name,sport,pts,ts) VALUES('Winterplan','snowshoe','[]',0)")
    db.execute("INSERT INTO goals(year,sport,metric,target,period) VALUES(2026,'snowshoe','km',50,'year')")
    db.execute("INSERT INTO goals(year,sport,metric,target,period) VALUES(2026,'snowshoe','up',9000,'year')")
    db.execute("INSERT INTO goals(year,sport,metric,target,period) VALUES(2026,'hike','up',30000,'year')")
    db.execute("INSERT INTO gear(name,kind,sports) VALUES('Schneeschuhe','Sonstiges','snowshoe,hike')")
    db.execute("INSERT INTO tour_hidden(id,js,ts) VALUES('h1',?,0)", (json.dumps({"id": "h1", "sport": "snowshoe", "name": "x"}),))
    # Zepp-Läufe
    _tour("z101", "hike", T0 + 86400)                                                  # sicher: lokale Übernahme dieses Trainings
    _workout(101, 1, komoot_id="z101")
    _tour("z102", "hike", T0 + 2 * 86400)                                              # von Hand auf Wandern gesetzt: bleibt
    db.execute("INSERT INTO tour_sport(id,sport) VALUES('z102','hike')")
    _workout(102, 1, komoot_id="z102")
    _tour("k103", "hike", T0 + 3 * 86400, source="komoot")                              # Komoot-Tour eines Laufs: nicht raten
    _workout(103, 1, komoot_id="k103", status="in_komoot")
    _tour("k104", "hike", T0 + 4 * 86400, source="komoot")                              # nur über die Startzeit: nicht raten
    _workout(T0 + 4 * 86400 + 30, 1, komoot_id=None, status="in_komoot")
    _tour("z105", "hike", T0 + 5 * 86400)                                              # Gehen (Typ 6): bleibt Wandern
    _workout(105, 6, komoot_id="z105")
    _workout(106, 8, status="no_gps")                                                  # Laufband ohne GPS: nur die Anzeige im Zepp-Verlauf
    _tour("z107", "touringbicycle", T0 + 6 * 86400)                                    # schon etwas anderes: bleibt
    _workout(107, 1, komoot_id="z107")


def test_umzug_legt_schneeschuh_nicht_mehr_zusammen_stellt_laeufe_um_und_ist_idempotent(fresh):
    """3.59.0: Eine Datenbank im Stand vor 3.50.0 (z. B. aus einer alten Sicherung): Schneeschuh bleibt Schneeschuh, nur die sicheren Läufe werden umgestellt."""
    _alter_stand()
    _reopen()
    sp = {r["id"]: r["sport"] for r in db.query("SELECT id,sport FROM tours")}
    assert sp["s1"] == sp["s2"] == "snowshoe" and sp["s3"] == "hike"
    assert db.one("SELECT sport FROM tour_sport WHERE id='s3'")["sport"] == "snowshoe"
    assert sp["z101"] == "jogging"
    assert sp["z102"] == "hike" and sp["k103"] == "hike" and sp["k104"] == "hike" and sp["z105"] == "hike" and sp["z107"] == "touringbicycle"
    assert _tags("s1") == [] and _tags("s2") == ["Schneeschuh"]
    assert db.one("SELECT sport FROM plans")["sport"] == "snowshoe"
    assert sorted(g["sport"] for g in db.query("SELECT * FROM goals")) == ["hike", "snowshoe", "snowshoe"]
    assert db.one("SELECT sports FROM gear")["sports"] == "snowshoe,hike"
    assert json.loads(db.one("SELECT js FROM tour_hidden")["js"])["sport"] == "snowshoe"
    assert db.one("SELECT sport FROM workouts WHERE trackid=106")["sport"] == "jogging"
    info = sport_umzug.info()
    assert info["laufen"] == 1 and info["schneeschuh"] == 0
    assert db.get(sport_umzug.FLAG_SNOW)                                                 # Schutz-Merker gesetzt
    n_log = db.one("SELECT COUNT(*) n FROM sport_log")["n"]
    _reopen()                                                                            # zweiter Lauf: nichts mehr zu tun
    assert db.one("SELECT COUNT(*) n FROM sport_log")["n"] == n_log and sport_umzug.info() == info
    assert {r["id"]: r["sport"] for r in db.query("SELECT id,sport FROM tours")} == sp


def test_umzug_laufen_nur_einmal(fresh):
    db.execute("DELETE FROM settings WHERE k=?", (sport_umzug.FLAG,))
    _reopen()
    assert sport_umzug.info().get("laufen") == 0                                     # Merker gesetzt, obwohl nichts umzustellen war
    _tour("z201", "hike")
    _workout(201, 1, komoot_id="z201")
    _reopen()
    assert db.one("SELECT sport FROM tours WHERE id='z201'")["sport"] == "hike"        # nach dem Umzug nichts mehr nachträglich ändern
    assert [k["id"] for k in sport_umzug.kandidaten()] == ["z201"]                     # wird aber unter Prüfen angeboten


def test_kandidaten_und_sammelumstellung(fresh):
    _alter_stand()
    _reopen()
    c = _client()
    r = c.get("/api/sport-umzug").json()
    ids = [k["id"] for k in r["kandidaten"]]
    assert sorted(ids) == ["k103", "k104"]
    wie = {k["id"]: k["wie"] for k in r["kandidaten"]}
    assert wie == {"k103": "verknuepft", "k104": "zeit"}
    assert r["umzug"]["laufen"] == 1 and "kopie" not in r["umzug"]                    # kein Pfad nach außen
    x = c.post("/api/sport-umzug/laufen", json={"ids": ["k103", "z105", "s1"]}).json()  # nur Kandidaten werden umgestellt
    assert x["n"] == 1
    assert db.one("SELECT sport FROM tours WHERE id='k103'")["sport"] == "jogging"
    assert db.one("SELECT sport FROM tour_sport WHERE id='k103'")["sport"] == "jogging"  # gilt als eigene Wahl (bleibt beim Komoot-Abgleich)
    assert db.one("SELECT sport FROM tours WHERE id='z105'")["sport"] == "hike"
    assert [k["id"] for k in c.get("/api/sport-umzug").json()["kandidaten"]] == ["k104"]
    assert c.post("/api/sport-umzug/laufen", json={"ids": []}).status_code == 400


class _K:
    def __init__(self, tours):
        self._t = tours

    def tours(self):
        return [dict(t) for t in self._t]


def test_komoot_abgleich_schneeschuh(fresh):
    """3.59.0: Neue Komoot-Schneeschuhtouren bleiben Schneeschuh; eine von 3.50.0 zusammengelegte Tour bleibt still Wandern (bis „als Schneeschuh führen“)."""
    t = {"id": "777", "name": "Schneeschuh Hörnle", "sport": "snowshoe", "start_ts": T0, "end_ts": T0 + 7200, "dist_m": 7000, "dur_s": 7200,
         "up_m": 400, "down_m": 400, "lat": 47.6, "lng": 11.0, "status": "tour_recorded"}
    alt = dict(t, id="778", start_ts=T0 + 86400, end_ts=T0 + 86400 + 7200)
    db.execute("INSERT INTO sport_merged(id,orig,ts) VALUES('778','snowshoe',0)")
    sync.refresh_tours(_K([t, alt]))
    assert db.one("SELECT sport FROM tours WHERE id='777'")["sport"] == "snowshoe" and _tags("777") == []
    assert db.one("SELECT sport FROM tours WHERE id='778'")["sport"] == "hike"


def test_tourenliste_fuer_das_tagebuch(fresh):
    """Das Tagebuch liest GET /api/tours: dieselben Felder wie bisher; 3.59.0: Schneeschuh kommt wieder als „snowshoe“."""
    _tour("s1", "snowshoe")
    _tour("r1", "jogging", T0 + 5000)
    db.execute("DELETE FROM settings WHERE k=?", (sport_umzug.FLAG,))
    _reopen()
    rows = {t["id"]: t for t in _client().get("/api/tours").json()}
    for k in ("id", "name", "sport", "start_ts", "end_ts", "dist_m", "dur_s", "up_m", "down_m", "source", "note", "stars", "tags", "date", "sport_de"):
        assert k in rows["s1"], k
    assert rows["s1"]["sport"] == "snowshoe" and rows["s1"]["sport_de"] == "Schneeschuh"
    assert rows["r1"]["sport"] == "jogging" and rows["r1"]["sport_de"] == "Laufen"


def test_wanderstatistik_ohne_schneeschuh_und_laeufe(fresh):
    """3.59.0: Wandern zählt nur Wandern (Schneeschuh ist eigene Sportart), ohne die Läufe der Uhr."""
    db.execute("DELETE FROM settings WHERE k=?", (sport_umzug.FLAG,))
    for i in range(3):
        _tour(f"h{i}", "hike", T0 + i * 86400, dist=10000)
    _tour("s1", "snowshoe", T0 + 4 * 86400, dist=6000)
    _tour("z301", "hike", T0 + 5 * 86400, dist=8000)
    _workout(301, 1, komoot_id="z301")
    _reopen()
    hike = db.query("SELECT dist_m FROM tours WHERE sport='hike'")
    assert len(hike) == 3 and sum(t["dist_m"] for t in hike) == 30000 and db.one("SELECT COUNT(*) n FROM tours WHERE sport='snowshoe'")["n"] == 1
    assert db.one("SELECT COUNT(*) n FROM tours WHERE sport='jogging'")["n"] == 1


def test_hochladen_wandern_mit_schneeschuh_geht_als_schneeschuh(fresh, monkeypatch):
    from app import portals
    t, _ = tracks.adopt(gpx("Workout--2026-01-20--10-00-00.gpx"), "a.gpx")
    tracks.add_tag(t["id"], "Schneeschuh")                                           # Wandern mit Schlagwort (von 3.50.0 zusammengelegt)
    u, _ = tracks.adopt(gpx("Workout--2026-01-21--10-00-00.gpx"), "b.gpx")
    seen = []
    monkeypatch.setattr(portals, "komoot_upload", lambda g, sport, name, **kw: (seen.append(sport), ("created", "1"))[1])
    portals.upload_tour(t["id"], "komoot")
    portals.upload_tour(u["id"], "komoot")
    assert seen == ["snowshoe", "hike"]


def test_alte_rueckblick_und_diashow_links_zeigen_wandern(fresh):
    from app import diashow_link, rueckblick
    assert rueckblick.parse("rb:2026:snowshoe") == (2026, "hike") and rueckblick.parse("rb:2026:jogging") == (2026, "jogging")
    assert diashow_link.parse("ds:2026:snowshoe") == (2026, "hike") and diashow_link.parse("ds:all") == (0, "")
