"""Wetterwarnung (Auswertung der Vorhersage) und Live-Standort-Links."""
from app import begleiter


def _h(**k):
    base = {"temperature_2m": [15] * 7, "precipitation": [0] * 7, "weather_code": [1] * 7, "wind_gusts_10m": [20] * 7}
    base.update(k)
    return base


def test_analyze_ruhig_und_gewitter():
    assert begleiter.analyze(_h()) == {"level": "ok", "events": []}
    r = begleiter.analyze(_h(weather_code=[1, 1, 95, 95, 1, 1, 1]))
    assert r["level"] == "danger" and r["events"][0] == {"kind": "thunder", "in_h": 2, "val": None}
    assert begleiter.analyze(_h(weather_code=[1, 1, 1, 1, 1, 95, 95]))["level"] == "ok"        # zu weit weg


def test_analyze_regen_wind_kaelte_schnee():
    r = begleiter.analyze(_h(precipitation=[0, 5.2, 1, 0, 0, 0, 0]))
    assert r["level"] == "warn" and r["events"][0]["kind"] == "rain" and r["events"][0]["in_h"] == 1 and r["events"][0]["val"] == 5.2
    r = begleiter.analyze(_h(wind_gusts_10m=[20, 20, 65, 20, 20, 20, 20]))
    assert r["level"] == "warn" and r["events"][0]["kind"] == "wind"
    assert begleiter.analyze(_h(wind_gusts_10m=[20, 85, 20, 20, 20, 20, 20]))["level"] == "danger"
    r = begleiter.analyze(_h(temperature_2m=[18, 14, 9, 8, 8, 8, 8]))
    assert [e["kind"] for e in r["events"]] == ["cold"] and r["events"][0]["val"] == 10
    r = begleiter.analyze(_h(weather_code=[1, 73, 1, 1, 1, 1, 1]))
    assert r["events"][0]["kind"] == "snow"
    assert begleiter.analyze({})["level"] == "ok"                                                # fehlende Daten


def test_wetter_endpoint(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main
    n = []
    monkeypatch.setattr(begleiter, "_forecast", lambda la, lo: (n.append(1), _h(weather_code=[1, 95, 1, 1, 1, 1, 1]))[1])
    c = TestClient(main.app)
    r = c.get("/api/weather/alert?lat=47.41&lon=11.02").json()
    assert r["level"] == "danger" and r["events"][0]["kind"] == "thunder"
    c.get("/api/weather/alert?lat=47.42&lon=11.03")                                              # gleiche 0,1°-Zelle: aus dem Zwischenspeicher
    assert len(n) == 1
    assert c.get("/api/weather/alert?lat=95&lon=0").status_code == 400

    def boom(la, lo):
        raise RuntimeError("x")
    monkeypatch.setattr(begleiter, "_forecast", boom)
    assert c.get("/api/weather/alert?lat=10&lon=10").status_code == 502


def test_live_link():
    import time
    from fastapi.testclient import TestClient
    from app import main
    c = TestClient(main.app)
    c.post("/api/settings", json={"live_mode": "off"})
    assert c.post("/api/live/link", json={}).status_code == 403
    c.post("/api/settings", json={"live_mode": "on"})
    r = c.post("/api/live/link", json={"hours": 2}).json()
    tok = r["token"]
    assert r["url"].endswith(f"/pub/live/{tok}") and 7000 < r["exp"] - time.time() <= 7200
    assert c.get(f"/api/public/live/{tok}").json().get("lat") is None                           # noch keine Position
    c.post("/api/live", json={"lat": 47.5, "lon": 11.25, "acc": 8, "source": "rec"})
    j = c.get(f"/api/public/live/{tok}").json()
    assert abs(j["lat"] - 47.5) < 1e-9 and j["age_s"] < 5 and "exp" in j
    page = c.get(f"/pub/live/{tok}", headers={"accept-language": "fr"})
    assert page.status_code == 200 and 'lang="fr"' in page.text and "Position en direct" in page.text
    assert any(x["token"] == tok for x in c.get("/api/live/links").json())
    c.delete(f"/api/live/link/{tok}")
    assert c.get(f"/api/public/live/{tok}").status_code == 410
    assert c.get("/api/public/live/unbekannt").status_code == 410
