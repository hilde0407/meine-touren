"""Update-Prüfung (GitHub) und Installation aus der Oberfläche.

Zwei Wege, je nach Installation:
* „service“ (Proxmox-Container / Server mit systemd): Die App läuft ohne Root-Rechte. Sie legt nur eine Anforderung
  (Versionsnummer) in <Datenordner>/update-request ab. Ein kleiner Systemdienst mit Root-Rechten (<name>-update.path)
  nimmt sie auf, lädt die Version selbst von GitHub, sichert die Daten und installiert (deploy/update.sh auto).
  Die App kann also keinen eigenen Programmcode einschleusen – sie nennt nur eine Versionsnummer.
* „local“ (Mac-Testversion, gestartet mit mac/Meine-Touren-lokal.command): Die App ersetzt ihre eigenen Programmdateien
  und lässt sich vom Startskript neu starten.
* „manual“: sonst bleibt der Hinweis mit dem Befehl für die Konsole.
"""
import json
import os
import re
import shutil
import signal
import tarfile
import tempfile
import threading
import time
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException, Request

from . import auth, config, ctx, extras, health

router = APIRouter()
APP_ROOT = Path(__file__).resolve().parent.parent
VERSION_RE = re.compile(r"^\d+\.\d+\.\d+$")
KEEP = ("app", "mac", "deploy", "install", "ct", "requirements.txt", "README.md", "LICENSE")
MAX_DOWNLOAD = 150 * 1024 ** 2


def unit_path():
    return Path(f"/etc/systemd/system/{config.APP_NAME}-update.path")


def mode():
    if unit_path().exists() and os.access(config.DATA_DIR, os.W_OK):
        return "service"
    if os.environ.get("MT_SELF_UPDATE") == "1" and os.access(APP_ROOT, os.W_OK):
        return "local"
    return "manual"


def status_file():
    return config.DATA_DIR / "update-status"


def status():
    try:
        return json.loads(status_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _set_status(state, version, message=""):
    try:
        status_file().write_text(json.dumps({"state": state, "version": version, "message": message, "ts": int(time.time())}), encoding="utf-8")
    except OSError:
        pass


def info(force=False):
    if force:
        health._upd.update(ts=0, data=None)
    u = dict(health.update_check())
    m = mode()
    u.update(mode=m, can_install=bool(u.get("newer")) and m in ("service", "local"),
             command=f"{config.APP_NAME}-update github", status=status(), enabled=(db_get("update_check") != "0"))
    return u


def db_get(k):
    from . import db
    return db.get(k)


def backup_all():
    """Vor dem Update für jeden aktiven Benutzer eine frische Sicherung anlegen."""
    n = 0
    for u in auth.active_uids():
        with ctx.as_user(u):
            try:
                if extras.auto_backup(max_age_s=0):
                    n += 1
            except Exception:  # noqa
                pass
    return n


def _safe_extract(tf, dest):
    base = Path(dest).resolve()
    for m in tf.getmembers():
        target = (base / m.name).resolve()
        if base not in target.parents and target != base:
            raise ValueError("Unsicherer Pfad im Archiv")
        if m.issym() or m.islnk() or m.isdev():
            raise ValueError("Unerlaubter Eintrag im Archiv")
    try:
        tf.extractall(dest, filter="data")
    except TypeError:                        # ältere Python-Fassungen ohne filter=; die Prüfung oben hat bereits alles Unsichere abgelehnt
        tf.extractall(dest)


def install_local(version):
    """Programmdateien durch die Version aus GitHub ersetzen; Neustart übernimmt das Startskript."""
    url = f"https://github.com/{health.REPO}/archive/refs/tags/v{version}.tar.gz"
    _set_status("running", version, "Lade Version von GitHub …")
    with tempfile.TemporaryDirectory() as td:
        arc = Path(td) / "x.tar.gz"
        with requests.get(url, stream=True, timeout=60) as r:
            if r.status_code != 200:
                raise RuntimeError(f"Download fehlgeschlagen (HTTP {r.status_code})")
            size = 0
            with open(arc, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    size += len(chunk)
                    if size > MAX_DOWNLOAD:
                        raise RuntimeError("Download zu groß")
                    f.write(chunk)
        src = Path(td) / "src"
        src.mkdir()
        with tarfile.open(arc) as tf:
            _safe_extract(tf, src)
        roots = [p for p in src.iterdir() if p.is_dir()]
        root = roots[0] if len(roots) == 1 else src
        cfg = root / "app" / "config.py"
        if not (root / "app" / "main.py").exists() or not cfg.exists():
            raise RuntimeError("Das Archiv enthält keine Meine-Touren-Version")
        m = re.search(r'VERSION = "([^"]*)"', cfg.read_text(encoding="utf-8"))
        if not m or m.group(1).split(" ")[0] != version:
            raise RuntimeError("Die Versionsnummer im Archiv passt nicht zur angeforderten Version")
        old = APP_ROOT / ".vorher" / config.VERSION.split(" ")[0]
        shutil.rmtree(old, ignore_errors=True)
        old.mkdir(parents=True)
        for name in KEEP:
            cur, new = APP_ROOT / name, root / name
            if not new.exists():
                continue
            if cur.exists():
                shutil.move(str(cur), str(old / name))
            if new.is_dir():
                shutil.copytree(new, cur, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy2(new, cur)
    _set_status("restart", version, "Neustart …")


def restart_soon():
    (config.DATA_DIR / ".neustart").write_text("1")
    threading.Timer(1.5, lambda: os.kill(os.getpid(), signal.SIGTERM)).start()


@router.get("/api/update-check")
def api_update(force: bool = False, request: Request = None):
    return info(force)


@router.get("/api/update/status")
def api_update_status():
    return {"status": status(), "version": config.VERSION}


@router.post("/api/update/install")
def api_update_install(body: dict, request: Request):
    u = getattr(request.state, "user", None)
    if auth.users_exist() and (not u or u["role"] != "admin"):
        raise HTTPException(403, "Nur für Administratoren")
    ver = str(body.get("version") or "").lstrip("v")
    if not VERSION_RE.match(ver):
        raise HTTPException(400, "Ungültige Versionsnummer")
    cur = info(force=True)
    if not cur.get("newer") or cur.get("latest") != ver:
        raise HTTPException(409, "Diese Version ist nicht die neueste auf GitHub – bitte die Seite neu laden.")
    m = cur["mode"]
    if m == "manual":
        raise HTTPException(400, f"Automatische Installation ist hier nicht eingerichtet. Im Container ausführen: {cur['command']}")
    n = backup_all()
    if m == "service":
        _set_status("requested", ver, "Update angefordert …")
        (config.DATA_DIR / "update-request").write_text(ver, encoding="utf-8")
        return {"ok": True, "mode": m, "backups": n}
    try:
        install_local(ver)
    except Exception as e:  # noqa
        _set_status("error", ver, str(e)[:300])
        raise HTTPException(502, f"Update fehlgeschlagen: {e}")
    restart_soon()
    return {"ok": True, "mode": m, "backups": n}
