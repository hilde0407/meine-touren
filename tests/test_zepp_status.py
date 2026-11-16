"""3.30.0 – Zepp-Import auf der Übersicht, Server: Ergebnis des letzten Laufs (zepp_last_run), Fehlercodes, GET /api/zepp-status, Rechte. Zepp wird nie kontaktiert (export_zepp ersetzt)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401


def test_lauf_merkt_ergebnis_und_fehler(monkeypatch):
    from app import db, sync
    assert sync.zepp_letzter_lauf() is None and not sync.zepp_konfiguriert()
    monkeypatch.setattr(sync, "export_zepp", lambda limit=None: {"gesamt": 5, "neu": 2, "gps": 2, "ohne_gps": 0, "uebernommen": 1, "fehler": 0})
    assert sync.export_zepp_lauf()["neu"] == 2
    d = sync.zepp_letzter_lauf()
    assert d["ok"] is True and d["neu"] == 2 and d["uebernommen"] == 1 and d["ts"] >= d["start"] > 0

    def boom(limit=None):
        raise RuntimeError("Zepp-Zugangsdaten fehlen (Einstellungen)")
    monkeypatch.setattr(sync, "export_zepp", boom)
    with pytest.raises(RuntimeError):
        sync.export_zepp_lauf()
    d = sync.zepp_letzter_lauf()
    assert d["ok"] is False and d["code"] == "kein_zugang" and "fehlen" in d["fehler"]
    db.put("zepp_token", "GEHEIMTOKEN123456")
    monkeypatch.setattr(sync, "export_zepp", lambda limit=None: (_ for _ in ()).throw(RuntimeError("401 Unauthorized GEHEIMTOKEN123456")))
    with pytest.raises(RuntimeError):
        sync.export_zepp_lauf()
    d = sync.zepp_letzter_lauf()
    assert d["code"] == "anmeldung" and "GEHEIMTOKEN" not in d["fehler"]            # Zugangsdaten nie in der Anzeige
    assert sync.zepp_konfiguriert()


@pytest.mark.parametrize("msg,code", [("Zepp-Zugangsdaten fehlen", "kein_zugang"), ("HTTP 403", "anmeldung"), ("Connection timed out", "netz"), ("kaputt", "sonst"), ("", "sonst")])
def test_fehlercodes(msg, code):
    from app import sync
    assert sync.zepp_fehlercode(msg) == code


def test_status_endpoint_und_job_zaehlt_das_ergebnis(monkeypatch):
    from fastapi.testclient import TestClient
    from app import db, main, sync
    monkeypatch.setattr(sync, "export_zepp", lambda limit=None: {"gesamt": 1, "neu": 0, "gps": 0, "ohne_gps": 0, "uebernommen": 0, "fehler": 0})
    with TestClient(main.app) as c:
        s = c.get("/api/zepp-status").json()
        assert s == {"konfiguriert": False, "letzter": None} and "token" not in str(s).lower()
        db.put("zepp_email", "a@b.de"); db.put("zepp_password", "pw")
        assert c.get("/api/zepp-status").json()["konfiguriert"] is True
        assert c.post("/api/jobs/export").status_code == 200
        import time
        for _ in range(100):
            if not c.get("/api/jobs").json()["running"]:
                break
            time.sleep(0.05)
        j = c.get("/api/jobs").json()
        assert j["ok"] is True
        assert c.get("/api/zepp-status").json()["letzter"]["ok"] is True
