"""3.38.1 Baustein „Geplante Touren“ (Server): nur offene Pläne, optional gegangene mit Tour-Daten, verworfene nie; cfg „gegangen“ streng geprüft, alte Layouts ohne Feld bleiben gültig."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import db  # noqa: E402


def client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _plan(name, ts, status="geplant", tour=None, km=10.0, est=3.0):
    db.execute("INSERT INTO plans(name,sport,pts,km,up,down,max_alt,est_h,note,ts,status,tour_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", (name, "hike", "[]", km, 300, 300, 800, est, "", ts, status, tour))


def _seed():
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES('t1','Gelaufen','hike',1700000000,1700006000,11000,6120,320,320,48.0,8.0,'t','komoot')")
    _plan("Offen A", 100)
    _plan("Gegangen mit Tour", 200, "gegangen", "t1")
    _plan("Gegangen ohne Tour", 150, "gegangen", None)
    _plan("Gegangen Tour gelöscht", 140, "gegangen", "weg")
    _plan("Verworfen", 300, "verworfen")
    _plan("Offen B", 250)


def test_standard_nur_offene():
    _seed()
    with client() as c:
        r = c.get("/api/bausteine/geplant").json()
        assert [x["name"] for x in r] == ["Offen B", "Offen A"] and {x["status"] for x in r} == {"geplant"}
        assert all("tour" not in x and "pts" not in x for x in r)
        assert c.get("/api/bausteine/geplant?gegangen=0").json() == r


def test_gegangen_mit_tourdaten_und_verworfen_nie():
    _seed()
    with client() as c:
        r = c.get("/api/bausteine/geplant?gegangen=1").json()
        assert [x["name"] for x in r] == ["Offen B", "Gegangen mit Tour", "Gegangen ohne Tour", "Gegangen Tour gelöscht", "Offen A"]      # nach Zeit (neueste zuerst); das Frontend stellt offene voran
        assert "Verworfen" not in [x["name"] for x in r]
        by = {x["name"]: x for x in r}
        t = by["Gegangen mit Tour"]["tour"]
        assert t == {"id": "t1", "start_ts": 1700000000, "km": 11.0, "h": 1.7, "up": 320}
        assert by["Gegangen ohne Tour"]["tour"] is None and by["Gegangen Tour gelöscht"]["tour"] is None       # kein Vergleich ohne vorhandene Tour
        assert "tour" not in by["Offen A"]


def test_parameter_streng():
    with client() as c:
        for v in ("2", "ja", "true", "-1", ""):
            assert c.get("/api/bausteine/geplant", params={"gegangen": v}).status_code == 400, v


def test_status_wechsel_wirkt_sofort():
    _seed()
    with client() as c:
        pid = [x["id"] for x in c.get("/api/bausteine/geplant").json() if x["name"] == "Offen A"][0]
        assert c.post(f"/api/plans/{pid}/status", json={"status": "verworfen"}).status_code == 200
        assert [x["name"] for x in c.get("/api/bausteine/geplant?gegangen=1").json() if x["name"].startswith("Offen")] == ["Offen B"]


def test_cfg_validierung_und_alte_layouts():
    with client() as c:
        put = lambda cfg: c.put("/api/layout/uebersicht", json={"widgets": [{"id": "w1", "type": "geplant", "cfg": cfg}]})  # noqa: E731
        assert put({}).status_code == 200                                                    # altes Layout ohne Feld
        assert c.get("/api/layout/uebersicht").json()["layout"]["widgets"][0]["cfg"] == {}
        r = put({"gegangen": True})
        assert r.status_code == 200 and r.json()["layout"]["widgets"][0]["cfg"] == {"gegangen": True}
        assert put({"gegangen": False}).json()["layout"]["widgets"][0]["cfg"] == {"gegangen": False}
        for bad in ("ja", 1, 0, None, [], {"a": 1}, "true"):
            assert put({"gegangen": bad}).status_code == 400, bad
        assert c.get("/api/layout/uebersicht").json()["layout"]["widgets"][0]["cfg"] == {"gegangen": False}   # Fehlversuche ändern nichts
        assert put({"gegangen": True, "title": "Meine Pläne"}).status_code == 200
