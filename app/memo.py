"""Zwischenspeicher für rechenintensive Auswertungen.

Das Ergebnis wird im Arbeitsspeicher gehalten und nur neu berechnet, wenn sich die Daten des Benutzers
(Datenbank oder lokale Strecken) geändert haben."""
import functools
import threading

from . import config

_C = {}
_L = threading.Lock()


def _sig():
    p = config.DB_PATH
    parts = []
    for f in (p, p.with_name(p.name + "-wal")):
        try:
            s = f.stat(); parts.append((s.st_mtime_ns, s.st_size))
        except OSError:
            parts.append(None)
    try:
        parts.append((config.CACHE_DIR / "coords").stat().st_mtime_ns)
    except OSError:
        parts.append(None)
    return tuple(parts)


def cached(fn):
    @functools.wraps(fn)
    def wrap(*a, **k):
        key = (str(config.DB_PATH), fn.__name__, repr((a, sorted(k.items()))))
        sig = _sig()
        with _L:
            hit = _C.get(key)
        if hit and hit[0] == sig:
            return hit[1]
        val = fn(*a, **k)
        with _L:
            _C[key] = (sig, val)
        return val
    return wrap
