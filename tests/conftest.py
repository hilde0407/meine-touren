"""Gemeinsame Testumgebung (siehe tests/README.md).

Browser: Statt in jedem Test (und jedem Modul) einen eigenen Chromium zu starten, gibt es je Prozess (bei pytest-xdist: je Worker) genau einen Playwright und
einen Chromium. `sync_playwright()` wird dafür ersetzt: die vorhandenen Tests (`with sync_playwright() as p: ... p.chromium.launch() ... b.close()`) laufen unverändert,
bekommen aber den gemeinsamen Browser. `b.close()` schließt nur die über diesen Handle geöffneten Kontexte; nach jedem Test werden außerdem alle noch offenen Kontexte
geschlossen, damit nichts in den nächsten Test hineinragt (Cookies, Speicher, Routen, Seiten gehören immer zu einem Kontext).
Stürzt der Chromium ab, wird beim nächsten `launch()` ein neuer gestartet.
Fehlersuche: MT_NO_SHARED=1 schaltet das gemeinsame Browser-Handling ab (jeder Test startet seinen eigenen Chromium), MT_NO_QUIET_INIT=1 lässt den Zähler für `quiet` weg.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.helpers_ui import QUIET_INIT_JS  # noqa: E402


# Stresstest für Wettläufe: MT_CPU_THROTTLE=4 bremst die CPU jeder Seite im Browser um den Faktor 4 (Chromium-DevTools-Protokoll) – Flakes zeigen sich dann auch auf einem schnellen Rechner.
_THROTTLE = float(os.environ.get("MT_CPU_THROTTLE") or 0)


def _throttle(ctx, page):
    try:
        ctx.new_cdp_session(page).send("Emulation.setCPUThrottlingRate", {"rate": _THROTTLE})
    except Exception:
        pass


_STATE = {"pw": None, "browsers": {}, "ctxs": [], "seq": 0}          # ctxs: (laufende Nummer, Handle, Kontext) in Anlegereihenfolge


class _Handle:
    """Was ein Test als „Browser“ bekommt: legt Kontexte im gemeinsamen Chromium an und räumt nur diese wieder auf."""

    def __init__(self, real):
        self._real = real

    def new_context(self, **kw):
        c = self._real.new_context(**kw)
        if not os.environ.get("MT_NO_QUIET_INIT"):
            c.add_init_script("(" + QUIET_INIT_JS + ")()")          # Zähler für helpers_ui.quiet()
        if _THROTTLE > 1:
            c.on("page", lambda p, c=c: _throttle(c, p))
        _STATE["seq"] += 1
        _STATE["ctxs"].append((_STATE["seq"], self, c))
        return c

    def new_page(self, **kw):
        return self.new_context(**kw).new_page()

    @property
    def contexts(self):
        return [c for _, h, c in _STATE["ctxs"] if h is self and c in self._real.contexts]

    def close(self):
        _close_contexts(handle=self)

    def __getattr__(self, name):
        return getattr(self._real, name)


class _Chromium:
    def __init__(self, real):
        self._real = real

    def launch(self, **kw):
        key = repr(sorted(kw.items()))
        b = _STATE["browsers"].get(key)
        if b is None or not b.is_connected():
            b = self._real.launch(**kw)
            _STATE["browsers"][key] = b
        return _Handle(b)

    def __getattr__(self, name):
        return getattr(self._real, name)


class _Playwright:
    def __init__(self, real):
        self._real = real

    @property
    def chromium(self):
        return _Chromium(self._real.chromium)

    def __getattr__(self, name):
        return getattr(self._real, name)


class _SharedSyncPlaywright:
    def __enter__(self):
        self._mark = _STATE["seq"]
        if _STATE["pw"] is None:
            _STATE["pw"] = _REAL_SYNC_PLAYWRIGHT().start()
        return _Playwright(_STATE["pw"])

    def __exit__(self, *a):
        _close_contexts(since=self._mark)          # nur, was innerhalb dieses `with` angelegt wurde (Kontexte von Modul-Fixtures bleiben)
        return False


def _close_contexts(since=0, handle=None):
    """Kontexte schließen: alle mit Nummer > since (und, falls angegeben, nur die eines Handles)."""
    keep = []
    for n, h, c in _STATE["ctxs"]:
        if n > since and (handle is None or h is handle):
            try:
                c.close()
            except Exception:
                pass
        else:
            keep.append((n, h, c))
    _STATE["ctxs"] = keep


def _shutdown():
    _close_contexts()
    for b in list(_STATE["browsers"].values()):
        try:
            b.close()
        except Exception:
            pass
    _STATE["browsers"].clear()
    if _STATE["pw"] is not None:
        try:
            _STATE["pw"].stop()
        except Exception:
            pass
        _STATE["pw"] = None


try:
    import playwright.sync_api as _sa
    _REAL_SYNC_PLAYWRIGHT = _sa.sync_playwright
    if not os.environ.get("MT_NO_SHARED"):
        _sa.sync_playwright = _SharedSyncPlaywright          # die Tests importieren den Namen erst in der Funktion bzw. Fixture
except ImportError:                                      # ohne Playwright werden die Browsertests per importorskip übersprungen
    pass


@pytest.fixture(autouse=True)
def _browser_aufraeumen():
    """Nach jedem Test die in ihm (und seinen Funktions-Fixtures) angelegten Kontexte schließen; Kontexte aus Modul-Fixtures (z. B. `app_url` in test_browser.py) bleiben bis zum Modulende."""
    mark = _STATE["seq"]
    yield
    _close_contexts(since=mark)


def pytest_sessionfinish(session, exitstatus):
    _shutdown()
