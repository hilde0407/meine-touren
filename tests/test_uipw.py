"""Oberflächenpasswort in der Oberfläche setzen."""
import base64, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401


def _basic(pw):
    return {"Authorization": "Basic " + base64.b64encode(f"x:{pw}".encode()).decode()}


def test_set_change_and_remove_password():
    from fastapi.testclient import TestClient
    from app import main, uipw
    c = TestClient(main.app)
    assert c.get("/api/status").status_code == 200 and c.get("/api/status").json()["protected"] is False
    assert c.post("/api/ui-password", json={"password": "abc"}).status_code == 400          # zu kurz
    assert c.post("/api/ui-password", json={"password": "geheim123"}).status_code == 200
    assert uipw.is_set() and "geheim123" not in uipw._f().read_text()                       # nur Hash gespeichert
    assert c.get("/api/status").status_code == 401
    assert c.get("/api/status", headers=_basic("falsch")).status_code == 401
    r = c.get("/api/status", headers=_basic("geheim123"))
    assert r.status_code == 200 and r.json()["protected"] is True
    assert c.post("/api/ui-password", json={"password": "neuesPasswort"}, headers=_basic("geheim123")).status_code == 200
    assert c.get("/api/status", headers=_basic("geheim123")).status_code == 401
    assert c.post("/api/ui-password", json={"password": ""}, headers=_basic("neuesPasswort")).status_code == 200
    assert c.get("/api/status").status_code == 200


def test_env_password_cannot_be_changed(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main, config
    monkeypatch.setattr(config, "UI_PASSWORD", "ausEnv")
    c = TestClient(main.app)
    assert c.post("/api/ui-password", json={"password": "anderes123"}, headers=_basic("ausEnv")).status_code == 409
    assert c.get("/api/status", headers=_basic("ausEnv")).json()["ui_pw_env"] is True
