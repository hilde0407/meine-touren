"""Benutzer, Anmeldung (Sitzungs-Cookie) und Freigaben. Eigene Datenbank: system.sqlite."""
import hashlib
import hmac
import os
import re
import secrets
import shutil
import sqlite3
import threading
import time
import unicodedata

from . import config, ctx, db

_lock = threading.RLock()
_conn = None
_conn_path = None
SESSION_DAYS = 30
COOKIE = "kh_session"
SCHEMA = """
CREATE TABLE IF NOT EXISTS users (uid TEXT PRIMARY KEY, name TEXT, pw TEXT, role TEXT, active INTEGER DEFAULT 1, created INTEGER);
CREATE TABLE IF NOT EXISTS sessions (th TEXT PRIMARY KEY, uid TEXT, created INTEGER, exp INTEGER);
CREATE TABLE IF NOT EXISTS grants (id INTEGER PRIMARY KEY AUTOINCREMENT, owner TEXT, grantee TEXT, scope TEXT, ref TEXT, ts INTEGER);
CREATE TABLE IF NOT EXISTS share_index (token TEXT PRIMARY KEY, uid TEXT);
"""


def _c():
    global _conn, _conn_path
    with _lock:
        if _conn is None or _conn_path != str(config.SYSTEM_DB):
            config.SYSTEM_DB.parent.mkdir(parents=True, exist_ok=True)
            _conn = sqlite3.connect(str(config.SYSTEM_DB), check_same_thread=False)
            _conn_path = str(config.SYSTEM_DB)
            _conn.row_factory = sqlite3.Row
            _conn.executescript(SCHEMA)
            _conn.commit()
        return _conn


def q(sql, args=()):
    with _lock:
        c = _c(); cur = c.execute(sql, args); rows = [dict(r) for r in cur.fetchall()]; c.commit(); return rows


def q1(sql, args=()):
    r = q(sql, args)
    return r[0] if r else None


def reset():
    """Nur für Tests: Verbindung verwerfen."""
    global _conn
    with _lock:
        if _conn is not None:
            _conn.close(); _conn = None
    ctx.first_uid = None


# ---------- Passwörter ----------
def hash_pw(pw):
    salt = os.urandom(16)
    h = hashlib.scrypt(pw.encode(), salt=salt, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${salt.hex()}${h.hex()}"


def check_pw(pw, stored):
    try:
        _, salt, h = stored.split("$")
        calc = hashlib.scrypt(pw.encode(), salt=bytes.fromhex(salt), n=2 ** 14, r=8, p=1, dklen=32)
        return hmac.compare_digest(calc.hex(), h)
    except Exception:  # noqa
        return False


# ---------- Benutzer ----------
def slug(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[^a-z0-9_-]+", "-", s).strip("-")[:30]
    return s or "benutzer"


def users_exist():
    return bool(q1("SELECT 1 x FROM users LIMIT 1"))


def load_first():
    r = q1("SELECT uid FROM users ORDER BY created, uid LIMIT 1")
    ctx.first_uid = r["uid"] if r else None


def list_users():
    return q("SELECT uid,name,role,active,created FROM users ORDER BY created, uid")


def active_uids():
    return [u["uid"] for u in q("SELECT uid FROM users WHERE active=1 ORDER BY created, uid")] if users_exist() else [None]


def create_user(name, pw, role="user"):
    name = (name or "").strip()
    if len(name) < 2 or len(name) > 40:
        raise ValueError("Der Name muss 2 bis 40 Zeichen lang sein")
    if len(pw or "") < 8:
        raise ValueError("Das Passwort muss mindestens 8 Zeichen lang sein")
    base, uid, n = slug(name), None, 1
    uid = base
    while q1("SELECT 1 x FROM users WHERE uid=?", (uid,)) or uid in ("shared", "users", "legacy"):
        n += 1; uid = f"{base}-{n}"
    if q1("SELECT 1 x FROM users WHERE lower(name)=lower(?)", (name,)):
        raise ValueError("Diesen Namen gibt es schon")
    q("INSERT INTO users(uid,name,pw,role,active,created) VALUES(?,?,?,?,1,?)", (uid, name, hash_pw(pw), "admin" if role == "admin" else "user", int(time.time())))
    load_first()
    d = config.user_dir(uid)
    for sub in ("cache", "export", "inbox", "photos"):
        (d / sub).mkdir(parents=True, exist_ok=True)
    with ctx.as_user(uid):
        db.init()
    return uid


def set_password(uid, pw):
    if len(pw or "") < 8:
        raise ValueError("Das Passwort muss mindestens 8 Zeichen lang sein")
    q("UPDATE users SET pw=? WHERE uid=?", (hash_pw(pw), uid))
    q("DELETE FROM sessions WHERE uid=?", (uid,))


def delete_user(uid, with_data=False):
    q("DELETE FROM users WHERE uid=?", (uid,)); q("DELETE FROM sessions WHERE uid=?", (uid,))
    q("DELETE FROM grants WHERE owner=? OR grantee=?", (uid, uid)); q("DELETE FROM share_index WHERE uid=?", (uid,))
    load_first()
    if with_data:
        db.close_all()
        shutil.rmtree(config.user_dir(uid), ignore_errors=True)


# ---------- Anmeldung ----------
_fail = {}


def login(name, pw, ip=""):
    key = (name or "").strip().lower() + "|" + ip
    now = time.time(); f = [t for t in _fail.get(key, []) if now - t < 300]
    if len(f) >= 6:
        raise PermissionError("Zu viele Versuche – bitte in ein paar Minuten erneut versuchen")
    u = q1("SELECT * FROM users WHERE (lower(name)=lower(?) OR uid=?) AND active=1", (name.strip(), slug(name)))
    ok = bool(u and check_pw(pw, u["pw"]))
    if not u:
        hash_pw("x")          # gleiche Rechenzeit, damit man unbekannte Namen nicht erkennt
    if not ok:
        _fail[key] = f + [now]
        raise PermissionError("Name oder Passwort stimmt nicht")
    _fail.pop(key, None)
    tok = secrets.token_urlsafe(32)
    q("INSERT INTO sessions(th,uid,created,exp) VALUES(?,?,?,?)", (hashlib.sha256(tok.encode()).hexdigest(), u["uid"], int(now), int(now + SESSION_DAYS * 86400)))
    q("DELETE FROM sessions WHERE exp<?", (int(now),))
    return tok, u


def session_user(tok):
    if not tok:
        return None
    return q1("SELECT u.uid,u.name,u.role FROM sessions s JOIN users u ON u.uid=s.uid WHERE s.th=? AND s.exp>? AND u.active=1", (hashlib.sha256(tok.encode()).hexdigest(), int(time.time())))


def logout(tok):
    if tok:
        q("DELETE FROM sessions WHERE th=?", (hashlib.sha256(tok.encode()).hexdigest(),))


# ---------- Altdaten übernehmen ----------
def adopt_legacy(uid):
    """Daten des bisherigen Ein-Benutzer-Betriebs in den Ordner des ersten Benutzers verschieben."""
    old_db = config.DATA_DIR / "komoot_hub.sqlite"
    if not old_db.exists():
        return False
    db.close_all()
    dst = config.user_dir(uid)
    dst.mkdir(parents=True, exist_ok=True)
    moves = {"komoot_hub.sqlite": "komoot_hub.sqlite", "komoot_hub.sqlite-wal": "komoot_hub.sqlite-wal", "komoot_hub.sqlite-shm": "komoot_hub.sqlite-shm",
             "cache": "cache", "export": "export", "inbox": "inbox", "photos": "photos"}
    for a, b in moves.items():
        s = config.DATA_DIR / a
        if s.exists():
            t = dst / b
            if t.is_dir():
                shutil.rmtree(t, ignore_errors=True)
            elif t.exists():
                t.unlink()
            shutil.move(str(s), str(t))
    for sub in ("cache", "export", "inbox", "photos"):
        (dst / sub).mkdir(exist_ok=True)
    for sub in ("tiles", "dem"):      # Kartenkacheln und Geländedaten sind für alle Benutzer gemeinsam
        s = dst / "cache" / sub
        if s.is_dir():
            config.TILE_CACHE.mkdir(parents=True, exist_ok=True)
            if sub == "tiles":
                for style in s.iterdir():
                    shutil.move(str(style), str(config.TILE_CACHE / style.name)) if not (config.TILE_CACHE / style.name).exists() else None
                shutil.rmtree(s, ignore_errors=True)
            else:
                shutil.move(str(s), str(config.TILE_CACHE / "dem")) if not (config.TILE_CACHE / "dem").exists() else shutil.rmtree(s, ignore_errors=True)
    with ctx.as_user(uid):
        db.init()
        for table, col, old, new in (("photos", "path", config.DATA_DIR / "photos", dst / "photos"), ("workouts", "gpx_path", config.DATA_DIR / "export", dst / "export")):
            db.execute(f"UPDATE {table} SET {col}=? || substr({col}, ?) WHERE {col} LIKE ?", (str(new), len(str(old)) + 1, str(old) + "%"))
        for s in db.query("SELECT token FROM shares"):
            q("INSERT OR REPLACE INTO share_index(token,uid) VALUES(?,?)", (s["token"], uid))
    return True


# ---------- Freigaben ----------
def grants_to(viewer):
    """Freigaben an `viewer` (oder an alle): [{owner, scope, ref}]"""
    return q("SELECT owner,scope,ref FROM grants WHERE (grantee=? OR grantee='*') AND owner!=?", (viewer, viewer))


def can_see_photo(viewer, owner, tour_id):
    for g in grants_to(viewer):
        if g["owner"] == owner and (g["scope"] == "all" or (g["scope"] == "tour" and tour_id and g["ref"] == str(tour_id))):
            return True
    return False
