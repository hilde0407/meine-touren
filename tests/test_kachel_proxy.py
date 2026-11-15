"""3.24.0 – Kachel-Proxy /tiles/…: Rate-Limit je Benutzer bzw. Adresse (429 mit Retry-After), saubere Fehler beim Anbieter ohne Dauerfehler im Zwischenspeicher."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401


def _setup(monkeypatch, tmp_path):
    from app import extras
    extras._TILE_HITS.clear(); extras._TILE_DOWN.clear()
    monkeypatch.setattr(extras, "TILE_DIR", tmp_path / "tiles")
    monkeypatch.setattr(extras.config, "TILE_FETCH", True)
    return extras


class _R:
    def __init__(self, code=200, content=b"PNG"):
        self.status_code, self.content = code, content


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def test_rate_limit_429_mit_retry_after(monkeypatch, tmp_path):
    extras = _setup(monkeypatch, tmp_path)
    monkeypatch.setattr(extras, "TILE_RATE", 5)
    monkeypatch.setattr(extras.requests, "get", lambda *a, **k: _R())
    with _client() as c:
        codes = [c.get(f"/tiles/osm/5/{i}/3").status_code for i in range(8)]
        assert codes[:5] == [200] * 5 and codes[5:] == [429] * 3
        r = c.get("/tiles/osm/5/9/3")
        assert r.status_code == 429 and 1 <= int(r.headers["retry-after"]) <= 61 and r.headers["cache-control"] == "no-store"
    assert extras._tile_limit("x", now=1000.0) == 0                                   # eigenes Fenster je Schlüssel
    monkeypatch.setattr(extras, "TILE_RATE", 2)
    assert extras._tile_limit("y", now=1000.0) == 0 and extras._tile_limit("y", now=1001.0) == 0
    assert extras._tile_limit("y", now=1002.0) == 59 and extras._tile_limit("y", now=1061.5) == 0    # nach 60 s wieder frei


def test_anbieter_fehler_kein_dauerfehler_und_kurze_pause(monkeypatch, tmp_path):
    extras = _setup(monkeypatch, tmp_path)
    calls = []

    def get(url, **k):
        calls.append(url)
        return _R(503, b"")
    monkeypatch.setattr(extras.requests, "get", get)
    with _client() as c:
        r = c.get("/tiles/osm/4/2/2", follow_redirects=False)
        assert r.status_code == 307 and r.headers["cache-control"] == "no-store" and "openstreetmap" in r.headers["location"]
        c.get("/tiles/osm/4/3/2", follow_redirects=False)
        assert len(calls) == 1                                                          # Anbieter wird in der Pause nicht bedrängt
        assert 0 < extras.TILE_DOWN_S <= 60                                             # Fehler sind nie länger als 60 s „gemerkt“
        extras._TILE_DOWN.clear()                                                       # Pause vorbei: Anbieter wieder da, Kachel kommt normal
        monkeypatch.setattr(extras.requests, "get", lambda *a, **k: _R())
        ok = c.get("/tiles/osm/4/2/2")
        assert ok.status_code == 200 and ok.content == b"PNG" and "max-age=86400" in ok.headers["cache-control"]
        assert not list((tmp_path / "tiles").rglob("*.tmp"))                            # keine Reste


def test_verbindungsfehler_liefert_alte_kachel_kurz_gemerkt(monkeypatch, tmp_path):
    import os, time
    extras = _setup(monkeypatch, tmp_path)
    f = tmp_path / "tiles" / "osm" / "4" / "2" / "2.png"
    f.parent.mkdir(parents=True); f.write_bytes(b"ALT")
    old = time.time() - 30 * 86400
    os.utime(f, (old, old))

    def boom(*a, **k):
        raise extras.requests.ConnectionError("offline")
    monkeypatch.setattr(extras.requests, "get", boom)
    with _client() as c:
        r = c.get("/tiles/osm/4/2/2")
        assert r.status_code == 200 and r.content == b"ALT" and "max-age=60" in r.headers["cache-control"]
