"""Tests für die Update-Funktion: Prüfung, Anforderung an den Hilfsdienst, lokale Installation (Mac)."""
import io, sys, tarfile, time
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from tests.test_core import fresh  # noqa: F401
from app import config, db, health, updater  # noqa


def _newer(monkeypatch, latest="9.9.9"):
    monkeypatch.setattr(health, "update_check", lambda: {"current": "1.0.36", "latest": latest, "newer": latest != "1.0.36", "url": "u", "notes": "n", "published": "", "ok": True})
    health._upd.update(ts=0, data=None)


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def test_mode_detection(tmp_path, monkeypatch):
    monkeypatch.setattr(updater, "unit_path", lambda: tmp_path / "gibt-es-nicht")
    monkeypatch.delenv("MT_SELF_UPDATE", raising=False)
    assert updater.mode() == "manual"
    monkeypatch.setenv("MT_SELF_UPDATE", "1")
    monkeypatch.setattr(updater, "APP_ROOT", tmp_path)
    assert updater.mode() == "local"
    (tmp_path / "u.path").write_text("x")
    monkeypatch.setattr(updater, "unit_path", lambda: tmp_path / "u.path")
    assert updater.mode() == "service"


def test_service_mode_writes_only_a_version_number(tmp_path, monkeypatch):
    _newer(monkeypatch)
    monkeypatch.setattr(updater, "mode", lambda: "service")
    monkeypatch.setattr(updater, "backup_all", lambda: 2)
    with _client() as c:
        r = c.post("/api/update/install", json={"version": "9.9.9"})
        assert r.status_code == 200 and r.json()["backups"] == 2
        assert (config.DATA_DIR / "update-request").read_text() == "9.9.9"
        assert updater.status()["state"] == "requested"
        # falsche/unsichere Angaben
        assert c.post("/api/update/install", json={"version": "9.9.9; rm -rf /"}).status_code == 400
        assert c.post("/api/update/install", json={"version": "../x"}).status_code == 400
        assert c.post("/api/update/install", json={"version": "8.0.0"}).status_code == 409


def test_manual_mode_gives_command(monkeypatch):
    _newer(monkeypatch)
    monkeypatch.setattr(updater, "mode", lambda: "manual")
    with _client() as c:
        r = c.post("/api/update/install", json={"version": "9.9.9"})
        assert r.status_code == 400 and "-update github" in r.json()["detail"]


def test_only_admin_may_install(monkeypatch):
    from app import auth
    _newer(monkeypatch)
    monkeypatch.setattr(updater, "mode", lambda: "service")
    monkeypatch.setattr(updater, "backup_all", lambda: 0)
    with _client() as c:
        c.post("/api/setup", json={"name": "chef", "password": "geheim123"})
        c.post("/api/login", json={"name": "chef", "password": "geheim123"})
        c.post("/api/users", json={"name": "gast", "password": "geheim456", "role": "user"})
        c.post("/api/logout")
        c.post("/api/login", json={"name": "gast", "password": "geheim456"})
        assert c.post("/api/update/install", json={"version": "9.9.9"}).status_code == 403
        c.post("/api/logout")
        c.post("/api/login", json={"name": "chef", "password": "geheim123"})
        assert c.post("/api/update/install", json={"version": "9.9.9"}).status_code == 200


def _tar(version="9.9.9", evil=False, root="meine-touren-9.9.9"):
    b = io.BytesIO()
    with tarfile.open(fileobj=b, mode="w:gz") as t:
        def add(name, data):
            ti = tarfile.TarInfo(name); ti.size = len(data); t.addfile(ti, io.BytesIO(data))
        add(f"{root}/app/main.py", b"# neu")
        add(f"{root}/app/config.py", f'VERSION = "{version} · Meine Touren (2030-01-01)"\n'.encode())
        add(f"{root}/mac/Meine-Touren-lokal.command", b"#!/bin/bash\n")
        add(f"{root}/requirements.txt", b"fastapi\n")
        if evil:
            add(f"{root}/../../ausserhalb.txt", b"boese")
    return b.getvalue()


class FakeGet:
    def __init__(self, data, code=200): self.data, self.status_code = data, code
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def iter_content(self, n): yield self.data


def _setup_root(tmp_path, monkeypatch):
    root = tmp_path / "prog"
    (root / "app").mkdir(parents=True); (root / "app" / "main.py").write_text("# alt"); (root / "app" / "config.py").write_text('VERSION = "1.0.36 · x"')
    (root / "mac").mkdir(); (root / "requirements.txt").write_text("alt")
    monkeypatch.setattr(updater, "APP_ROOT", root)
    return root


def test_install_local_replaces_files_and_keeps_old(tmp_path, monkeypatch):
    root = _setup_root(tmp_path, monkeypatch)
    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: FakeGet(_tar()))
    updater.install_local("9.9.9")
    assert (root / "app" / "main.py").read_text() == "# neu" and (root / "requirements.txt").read_text() == "fastapi\n"
    assert (root / "mac" / "Meine-Touren-lokal.command").exists()
    old = root / ".vorher" / config.VERSION.split(" ")[0]
    assert (old / "app" / "main.py").read_text() == "# alt"
    assert updater.status()["state"] == "restart"


def test_install_local_rejects_wrong_version_and_path_traversal(tmp_path, monkeypatch):
    root = _setup_root(tmp_path, monkeypatch)
    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: FakeGet(_tar(version="1.2.3")))
    with pytest.raises(RuntimeError, match="passt nicht"):
        updater.install_local("9.9.9")
    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: FakeGet(_tar(evil=True)))
    with pytest.raises(ValueError):
        updater.install_local("9.9.9")
    assert (root / "app" / "main.py").read_text() == "# alt"          # nichts verändert
    assert not (tmp_path / "ausserhalb.txt").exists()
    monkeypatch.setattr(updater.requests, "get", lambda *a, **k: FakeGet(b"", 404))
    with pytest.raises(RuntimeError, match="404"):
        updater.install_local("9.9.9")


def test_update_check_cache_and_failure_ttl(monkeypatch):
    calls = []
    def get(*a, **k):
        calls.append(1); raise OSError("offline")
    monkeypatch.setattr(health.requests, "get", get)
    health._upd.update(ts=0, data=None)
    u = health.update_check(); u2 = health.update_check()
    assert not u["ok"] and not u["newer"] and len(calls) == 1          # Fehler wird kurz zwischengespeichert
    assert health._upd["ttl"] == 30 * 60


def test_notify_mentions_new_version(monkeypatch):
    from app import more2
    _newer(monkeypatch)
    db.put("notify_url", "http://example.invalid/x")
    sent = []
    monkeypatch.setattr(more2, "notify_send", lambda t: sent.append(t))
    assert more2.notify_check() and "9.9.9" in sent[0]
    assert not more2.notify_check()                                    # nicht noch einmal für dieselbe Version
