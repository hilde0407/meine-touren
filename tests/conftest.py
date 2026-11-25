"""Gemeinsame Testumgebung (siehe tests/README.md).

Browser: Statt in jedem Test (und jedem Modul) einen eigenen Chromium zu starten, gibt es je Prozess (bei pytest-xdist: je Worker) genau einen Playwright und
einen Chromium. `sync_playwright()` wird dafür ersetzt: die vorhandenen Tests (`with sync_playwright() as p: ... p.chromium.launch() ... b.close()`) laufen unverändert,
bekommen aber den gemeinsamen Browser. `b.close()` schließt nur die über diesen Handle geöffneten Kontexte; nach jedem Test werden außerdem alle noch offenen Kontexte
geschlossen, damit nichts in den nächsten Test hineinragt (Cookies, Speicher, Routen, Seiten gehören immer zu einem Kontext).
Stürzt der Chromium ab, wird beim nächsten `launch()` ein neuer gestartet.
Fehlersuche: MT_NO_SHARED=1 schaltet das gemeinsame Browser-Handling ab (jeder Test startet seinen eigenen Chromium), MT_NO_QUIET_INIT=1 lässt den Zähler für `quiet` weg.
"""
import inspect
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# 3.51.0: kein Vorab-Erzeugen der Foto-Streifen im Hintergrund (Threads würden in die Datenbank des nächsten Tests schreiben); test_fotostreifen_351*.py schaltet es gezielt ein.
os.environ.setdefault("MT_NO_WARM", "1")

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
        it = _STATE.get("item")
        if it is not None and not it.get_closest_marker("browser"):          # Prüfung der Einordnung (siehe unten „Kern und volle Suite“)
            pytest.fail(f"{it.nodeid} startet einen Browser, wurde aber nicht als Browsertest erkannt (sonst liefe er im schnellen Kern). "
                        "Bitte mit @pytest.mark.browser kennzeichnen (oder @pytest.mark.kern, wenn er als Stichprobe in den Kern gehört).", pytrace=False)
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


# ---------- Kern und volle Suite (tests/README.md, Abschnitt „Kern und volle Suite“) ----------
# Jeder Test landet automatisch in genau einem Topf:
#   * Server-, Unit-, Format- und Stiltests (alles ohne Browser) gehören immer zum Kern.
#   * Browsertests gehören zur vollen Suite (Marker „voll“, hier gesetzt) – außer sie tragen @pytest.mark.kern (Stichprobe je Hauptseite).
# Kern = -m "not voll", Rest = -m voll, volle Suite = ohne -m. Ein Browsertest wird an seinem Quelltext erkannt (Testfunktion, ihre Fixtures und die Hilfsfunktionen,
# die sie aufruft); @pytest.mark.browser erzwingt die Einordnung. Startet ein nicht erkannter Test trotzdem einen Browser, schlägt er mit einem klaren Hinweis fehl
# (_SharedSyncPlaywright.__enter__), statt den Kern unbemerkt langsam zu machen.
_BROWSER_RE = re.compile(r"\bplaywright\b|sync_playwright|\.goto\(|\.new_page\(|\bchromium\b")
_SRC_CACHE = {}


def _src(obj):
    k = id(obj)
    if k not in _SRC_CACHE:
        try:
            _SRC_CACHE[k] = inspect.getsource(obj)
        except (OSError, TypeError):
            _SRC_CACHE[k] = ""
    return _SRC_CACHE[k]


def _is_test_code(fn):
    mod = getattr(fn, "__module__", "") or ""
    return mod.startswith("tests.") and mod != "tests.conftest" or (mod.startswith("test_") and mod != "conftest")


def _uses_browser(fn, depth=3, seen=None):
    """Quelltext der Funktion und der Test-Hilfsfunktionen, die sie beim Namen aufruft (bis `depth` Ebenen), nennt den Browser."""
    seen = seen if seen is not None else set()
    fn = inspect.unwrap(fn)
    if id(fn) in seen or not callable(fn):
        return False
    seen.add(id(fn))
    if _BROWSER_RE.search(_src(fn)):
        return True
    if depth <= 0:
        return False
    g = getattr(fn, "__globals__", {})
    code = getattr(fn, "__code__", None)
    for name in (code.co_names if code else ()):
        f = g.get(name)
        if inspect.isfunction(f) and _is_test_code(f) and _uses_browser(f, depth - 1, seen):
            return True
    return False


def _browser_item(item):
    if item.get_closest_marker("browser"):
        return True
    fn = getattr(item, "function", None)
    if fn is not None and _uses_browser(fn):
        return True
    for defs in getattr(getattr(item, "_fixtureinfo", None), "name2fixturedefs", {}).values():
        for d in defs:
            f = getattr(d, "func", None)
            if f is not None and _is_test_code(f) and _uses_browser(f):
                return True
    return False


def pytest_configure(config):
    config.addinivalue_line("markers", "browser: Browsertest (wird meist automatisch erkannt; erzwingt die Einordnung)")
    config.addinivalue_line("markers", "kern: Browsertest, der als Stichprobe zum schnellen Kern gehört (jeder Push)")
    config.addinivalue_line("markers", "voll: automatisch gesetzt – Browsertest nur in der vollen Suite (vor dem Veröffentlichen, nachts, manuell)")


def pytest_collection_modifyitems(config, items):
    for it in items:
        if _browser_item(it):
            if not it.get_closest_marker("browser"):
                it.add_marker(pytest.mark.browser)
            if not it.get_closest_marker("kern"):
                it.add_marker(pytest.mark.voll)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_setup(item):
    _STATE["item"] = item


def pytest_runtest_teardown(item, nextitem):
    _STATE["item"] = None


# 3.61.3: Zahl und Einheit stehen mit geschütztem Leerzeichen (U+00A0, „756 km, 68 %“ bricht nie in der Mitte um). Die vielen Browser-Tests, die Texte mit normalem Leerzeichen
# vergleichen, sehen deshalb die gelesenen Texte (inner_text, text_content, Attribute, Ergebnisse von evaluate) mit normalem Leerzeichen; tests/test_zahl_einheit_3613_ui.py und
# tests/test_format_341.py prüfen das geschützte Leerzeichen selbst (dort ist die Umwandlung aus).
_RAW_MODULES = {"test_zahl_einheit_3613_ui", "test_format_341"}


def _nb(x, _seen=None):
    """Ersetzt U+00A0 in Texten (auch in Listen und Wörterbüchern); Zyklen (evaluate kann Objektgraphen liefern) werden unverändert durchgereicht."""
    if isinstance(x, str):
        return x.replace(chr(160), " ")
    if isinstance(x, (list, dict)):
        _seen = _seen if _seen is not None else set()
        if id(x) in _seen:
            return x
        _seen.add(id(x))
        if isinstance(x, list):
            return [_nb(i, _seen) for i in x]
        return {k: _nb(v, _seen) for k, v in x.items()}
    return x


@pytest.fixture(autouse=True)
def _nbsp_wie_leerzeichen(request):
    if request.module.__name__.split(".")[-1] in _RAW_MODULES:
        yield
        return
    try:
        from playwright.sync_api import ElementHandle, Frame, Locator, Page
    except Exception:
        yield
        return
    names = ["inner_text", "text_content", "all_inner_texts", "all_text_contents", "get_attribute", "input_value", "evaluate", "evaluate_all", "evaluate_handle_json"]
    saved = []
    for cls in (Locator, Page, Frame, ElementHandle):
        for n in names:
            f = getattr(cls, n, None)
            if f is None:
                continue

            def mk(f):
                def w(self, *a, **k):
                    return _nb(f(self, *a, **k))
                w.__name__ = f.__name__
                return w
            saved.append((cls, n, f))
            setattr(cls, n, mk(f))
    try:
        yield
    finally:
        for cls, n, f in saved:
            setattr(cls, n, f)
