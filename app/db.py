import sqlite3
import threading
from contextlib import contextmanager

from . import config

_lock = threading.RLock()          # nur zum Öffnen/Schließen von Verbindungen
_conns = {}
_plocks = {}                       # je Datenbank (= je Benutzer) eigene Sperre: Benutzer bremsen sich nicht gegenseitig aus


def _plock(path):
    with _lock:
        return _plocks.setdefault(path, threading.RLock())

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (k TEXT PRIMARY KEY, v TEXT);
CREATE TABLE IF NOT EXISTS workouts (
  trackid INTEGER PRIMARY KEY, start_ts INTEGER, end_ts INTEGER, ztype INTEGER, sport TEXT,
  dist_m REAL, dur_s INTEGER, gpx_path TEXT, status TEXT, komoot_id TEXT, message TEXT, updated INTEGER);
CREATE TABLE IF NOT EXISTS tours (
  id TEXT PRIMARY KEY, name TEXT, sport TEXT, start_ts INTEGER, end_ts INTEGER,
  dist_m REAL, dur_s REAL, up_m REAL, down_m REAL, lat REAL, lng REAL, status TEXT);
CREATE TABLE IF NOT EXISTS photos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, path TEXT UNIQUE, mtime REAL, size INTEGER,
  taken_ts INTEGER, lat REAL, lng REAL, tour_id TEXT);
CREATE TABLE IF NOT EXISTS elev_fix (id TEXT PRIMARY KEY, orig_up REAL, orig_down REAL, up_m REAL, down_m REAL, ts INTEGER);
CREATE TABLE IF NOT EXISTS tour_geo (id TEXT PRIMARY KEY, country TEXT, state TEXT, county TEXT, place TEXT, ts INTEGER);
CREATE TABLE IF NOT EXISTS guide_tours (id INTEGER PRIMARY KEY AUTOINCREMENT, book TEXT, title TEXT, pts TEXT);
CREATE TABLE IF NOT EXISTS tour_peak (id TEXT PRIMARY KEY, name TEXT, alt REAL, lat REAL, lng REAL);
CREATE TABLE IF NOT EXISTS tour_tags (id TEXT, tag TEXT, PRIMARY KEY(id,tag));
CREATE TABLE IF NOT EXISTS shares (token TEXT PRIMARY KEY, tour_id TEXT, photos INTEGER, trim INTEGER, ts INTEGER);
CREATE TABLE IF NOT EXISTS geocache (k TEXT PRIMARY KEY, name TEXT, ts INTEGER);
CREATE TABLE IF NOT EXISTS weather (id TEXT PRIMARY KEY, js TEXT, ts INTEGER);
CREATE TABLE IF NOT EXISTS tour_notes (id TEXT PRIMARY KEY, note TEXT);
CREATE TABLE IF NOT EXISTS goals (id INTEGER PRIMARY KEY AUTOINCREMENT, year INTEGER, sport TEXT, metric TEXT, target REAL);
CREATE TABLE IF NOT EXISTS tour_uploads (tour_id TEXT, portal TEXT, remote_id TEXT, status TEXT, msg TEXT, ts INTEGER, PRIMARY KEY(tour_id,portal));
CREATE TABLE IF NOT EXISTS tour_names (id TEXT PRIMARY KEY, name TEXT, orig TEXT);
CREATE INDEX IF NOT EXISTS photos_taken ON photos(taken_ts);
CREATE INDEX IF NOT EXISTS photos_tour ON photos(tour_id);
CREATE INDEX IF NOT EXISTS tours_start ON tours(start_ts);
"""


def _open(path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with _lock:
        if path in _conns:
            return _conns[path]
        conn = sqlite3.connect(str(path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:   # WAL + NORMAL: viele kleine Schreibvorgänge warten nicht mehr jeweils auf die Festplatte (deutlich schneller, auch auf Proxmox/Netzspeicher)
            conn.execute("PRAGMA journal_mode=WAL"); conn.execute("PRAGMA synchronous=NORMAL"); conn.execute("PRAGMA busy_timeout=15000")
        except sqlite3.Error:
            pass
        conn.executescript(SCHEMA)
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(photos)")}
        if "offset_s" not in cols:
            conn.execute("ALTER TABLE photos ADD COLUMN offset_s INTEGER DEFAULT 0")
        tcols = {r["name"] for r in conn.execute("PRAGMA table_info(tours)")}
        if "source" not in tcols:
            conn.execute("ALTER TABLE tours ADD COLUMN source TEXT DEFAULT 'komoot'")
        if "manual" not in cols:
            conn.execute("ALTER TABLE photos ADD COLUMN manual INTEGER DEFAULT 0")
        if "fp" not in cols:
            conn.execute("ALTER TABLE photos ADD COLUMN fp TEXT")            # Bild-Fingerabdruck (dHash) gegen Doppelte
        if "dated" not in cols:
            conn.execute("ALTER TABLE photos ADD COLUMN dated INTEGER")      # 1 = Aufnahmezeit aus EXIF, 0 = nur Dateidatum, NULL = noch nicht geprüft
        conn.execute("CREATE TABLE IF NOT EXISTS photo_pref (path TEXT PRIMARY KEY, tour_id TEXT)")   # beim Import gewählte Tour
        conn.execute("CREATE TABLE IF NOT EXISTS tour_sport (id TEXT PRIMARY KEY, sport TEXT)")        # eigene Sportart (bleibt beim Komoot-Abgleich)
        conn.execute("CREATE TABLE IF NOT EXISTS tour_hidden (id TEXT PRIMARY KEY, js TEXT, ts INTEGER)")  # ausgeblendete Touren (z. B. Fehlaufzeichnungen)
        conn.execute("CREATE TABLE IF NOT EXISTS photo_deleted (rel TEXT PRIMARY KEY, ts INTEGER)")   # gelöschte Fotos: nicht erneut importieren
        conn.commit()
        _conns[path] = conn
        return conn


def init(path=None):
    """Datenbank des aktuellen Benutzers (bzw. des Altbetriebs) öffnen."""
    return _open(path or config.DB_PATH)


def close_all():
    with _lock:
        items = list(_conns.items())
    for path, c in items:
        with _plock(path):            # nicht schließen, solange ein anderer Thread die Verbindung benutzt (sonst Absturz in SQLite)
            try:
                c.close()
            except Exception:  # noqa
                pass
            with _lock:
                _conns.pop(path, None)


@contextmanager
def cur():
    path = config.DB_PATH
    with _plock(path):
        conn = _open(path)
        c = conn.cursor()
        try:
            yield c
            conn.commit()
        finally:
            c.close()


def query(sql, args=()):
    with cur() as c:
        c.execute(sql, args)
        return [dict(r) for r in c.fetchall()]


def one(sql, args=()):
    r = query(sql, args)
    return r[0] if r else None


def execute(sql, args=()):
    with cur() as c:
        c.execute(sql, args)
        return c.lastrowid


def executemany(sql, rows):
    with cur() as c:
        c.executemany(sql, rows)


def get(key):
    r = one("SELECT v FROM settings WHERE k=?", (key,))
    if r is not None:
        return r["v"]
    return config.DEFAULTS.get(key, "")


def put(key, value):
    execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (key, str(value)))


def get_int(key, default=0):
    try:
        return int(float(get(key)))
    except (TypeError, ValueError):
        return default
