"""Gemeinsames Oberflächenpasswort (Altbetrieb ohne Benutzerverwaltung).

Es kann wie bisher per Umgebungsvariable UI_PASSWORD gesetzt werden oder in der Oberfläche (Verwaltung → Sicherung & Zugang).
Das in der Oberfläche gesetzte Passwort liegt nur als gesalzener Hash im Datenordner."""
import hashlib
import hmac
import json
import os

from . import config


def _f():
    return config.DATA_DIR / "ui_password.json"


def _hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 120_000).hex()


def env_set():
    return bool(config.UI_PASSWORD)


def file_set():
    try:
        d = json.loads(_f().read_text())
        return bool(d.get("hash"))
    except (OSError, ValueError):
        return False


def is_set():
    return env_set() or file_set()


def check(pw):
    if env_set():
        return hmac.compare_digest(pw, config.UI_PASSWORD)
    try:
        d = json.loads(_f().read_text())
        return hmac.compare_digest(_hash(pw, d["salt"]), d["hash"])
    except (OSError, ValueError, KeyError):
        return False


def set_password(pw):
    """pw leer = Schutz aufheben."""
    if env_set():
        raise PermissionError("Das Passwort ist über die Umgebungsvariable UI_PASSWORD festgelegt und lässt sich hier nicht ändern.")
    f = _f()
    if not pw:
        f.unlink(missing_ok=True)
        return
    salt = os.urandom(16).hex()
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(".tmp")
    tmp.write_text(json.dumps({"salt": salt, "hash": _hash(pw, salt)}))
    os.chmod(tmp, 0o600)
    tmp.replace(f)
