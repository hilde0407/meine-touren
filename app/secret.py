"""Verschlüsselte Ablage von Zugangsdaten (Komoot-Passwort, Strava-/Zepp-Token …) in der Datenbank.

AES-256-GCM. Der Schlüssel kommt aus der Umgebungsvariable MT_SECRET_KEY (beliebiger Text) oder – falls nicht gesetzt –
aus der Datei <DATA_DIR>/secret.key, die beim ersten Start angelegt wird (nur für den Dienstbenutzer lesbar).
Die Schlüsseldatei steht NICHT in den Sicherungen: Eine gestohlene Sicherung verrät damit keine Passwörter.
Bei einer Wiederherstellung auf einem neuen Rechner ohne die alte Schlüsseldatei müssen die Zugangsdaten neu eingegeben werden.
"""
import base64
import hashlib
import os
import threading

from Crypto.Cipher import AES

from . import config

PREFIX = "enc1:"
_k = {"key": None, "src": None}
_lock = threading.Lock()


def _key():
    env = os.environ.get("MT_SECRET_KEY", "")
    src = ("env", env) if env else ("file", str(config.DATA_DIR))
    with _lock:
        if _k["key"] is not None and _k["src"] == src:
            if env or (config.DATA_DIR / "secret.key").exists():
                return _k["key"]
            _write(_k["key"])                      # Schlüsseldatei verschwunden: wieder anlegen, sonst wäre nach einem Neustart alles unlesbar
            return _k["key"]
        if env:
            key = hashlib.sha256(env.encode()).digest()
        else:
            f = config.DATA_DIR / "secret.key"
            if f.exists():
                key = bytes.fromhex(f.read_text().strip())
            else:
                key = os.urandom(32)
                _write(key)
        _k.update(key=key, src=src)
        return key


def _write(key):
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(config.DATA_DIR / "secret.key"), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as h:
        h.write(key.hex())


def encrypt(text):
    if not text:
        return ""
    nonce = os.urandom(12)
    c = AES.new(_key(), AES.MODE_GCM, nonce=nonce)
    ct, tag = c.encrypt_and_digest(str(text).encode("utf-8"))
    return PREFIX + base64.urlsafe_b64encode(nonce + tag + ct).decode()


def decrypt(value):
    """Gibt (Klartext, ok) zurück. Klartext aus älteren Versionen wird unverändert geliefert (ok=None → neu verschlüsseln)."""
    if not value or not value.startswith(PREFIX):
        return value, None
    try:
        raw = base64.urlsafe_b64decode(value[len(PREFIX):])
        c = AES.new(_key(), AES.MODE_GCM, nonce=raw[:12])
        return c.decrypt_and_verify(raw[28:], raw[12:28]).decode("utf-8"), True
    except Exception:  # noqa  (falscher Schlüssel, z. B. Sicherung von einem anderen Rechner)
        return "", False


def reset_cache():
    with _lock:
        _k.update(key=None, src=None)
