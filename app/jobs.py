"""Hintergrundjobs: je Benutzer ein Job zur Zeit, mit Protokoll."""
import contextvars
import threading
import time
import traceback
from collections import deque

from . import ctx

_S = {}
_g = threading.Lock()


def _s():
    u = ctx.uid()
    with _g:
        if u not in _S:
            _S[u] = {"lock": threading.Lock(), "state": {"running": None, "started": None, "finished": None, "ok": None, "progress": ""}, "log": deque(maxlen=800)}
        return _S[u]


def get_state():
    return _s()["state"]


def log(msg):
    _s()["log"].append(time.strftime("%H:%M:%S ") + str(msg))


def progress(msg):
    _s()["state"]["progress"] = msg


def start(name, fn, *args, **kw):
    s = _s()
    if not s["lock"].acquire(blocking=False):
        return False
    state = s["state"]

    def run():
        state.update(running=name, started=time.time(), finished=None, ok=None, progress="")
        log(f"=== {name} gestartet ===")
        try:
            fn(*args, **kw)
            state["ok"] = True
            log(f"=== {name} beendet ===")
        except Exception as e:  # noqa
            state["ok"] = False
            log(f"FEHLER: {e}")
            log(traceback.format_exc(limit=3))
        finally:
            state.update(running=None, finished=time.time())
            s["lock"].release()

    c = contextvars.copy_context()
    threading.Thread(target=lambda: c.run(run), daemon=True).start()
    return True


def snapshot():
    s = _s()
    return {**s["state"], "log": list(s["log"])[-200:]}
