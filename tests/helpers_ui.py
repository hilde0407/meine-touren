"""Gemeinsame Hilfen für die Browsertests (Playwright, sync). Regeln und Beispiele: tests/README.md.

Grundsatz: nie auf eine feste Zeit warten, sondern auf einen Zustand. Wer nur „die Seite soll fertig aufgebaut sein“ meint, nimmt `quiet`/`settled`;
wer einen bestimmten Zustand erwartet, wartet darauf (`expect(...)`, `wait_for_function`, `wait_route`, `open_details`).
"""
import socket
import time
import urllib.request

T = 15000          # Standard-Wartezeit in ms (expect(..., timeout=T), wait_for_function(..., timeout=T))

# Wird von conftest.py in jeden Browser-Kontext eingehängt: zählt laufende fetch-/XHR-Anfragen und merkt sich den Zeitpunkt der letzten DOM-Änderung bzw. Anfrage.
# Danach kann `quiet` auf „es tut sich nichts mehr“ warten (statt eine feste Zeit zu schlafen). Der Wrapper gibt dasselbe Promise zurück (keine neuen unbehandelten Ablehnungen).
QUIET_INIT_JS = """() => {
  if (window.__mtq) return;
  const s = window.__mtq = {pend: 0, last: performance.now()};
  const touch = () => { s.last = performance.now(); };
  const f = window.fetch;
  if (f) window.fetch = function () {
    s.pend++; touch();
    const p = f.apply(this, arguments);
    const d = () => { s.pend--; touch(); };
    p.then(d, d);
    return p;
  };
  const send = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function () {
    s.pend++; touch();
    this.addEventListener('loadend', () => { s.pend--; touch(); }, {once: true});
    return send.apply(this, arguments);
  };
  new MutationObserver(touch).observe(document, {subtree: true, childList: true, attributes: true, characterData: true});
}"""

_QUIET_FN = "(q) => { const s = window.__mtq; return !s || (s.pend === 0 && performance.now() - Math.max(s.last, s.start || 0) >= q); }"


def quiet(pg, cap=2000, quiet_ms=300):
    """Wartet, bis seit `quiet_ms` keine Anfrage mehr läuft/endete und sich das DOM nicht mehr geändert hat – mindestens `quiet_ms` ab dem Aufruf (zwischen Klick und erster
    Änderung liegt oft eine Verzögerung), höchstens `cap` ms (nie länger als der alte feste Schlaf).
    Ersatz für `pg.wait_for_timeout(cap)` nach Navigation/Klick, wenn nur „fertig aufgebaut“ gemeint ist. Seiten, die ständig etwas ändern (Live-Ansicht), laufen bis `cap`.
    Lädt die Seite dabei neu (Sprachwechsel), wird nach dem Neuladen weitergewartet."""
    from playwright.sync_api import Error as PWError, TimeoutError as PWTimeout
    end = time.time() + cap / 1000
    for _ in range(4):
        left = max(100, int((end - time.time()) * 1000))
        try:
            if not pg.evaluate("() => { if (!window.__mtq) return false; window.__mtq.start = performance.now(); return true; }"):
                pg.wait_for_timeout(min(cap, 1000))                          # Kontext ohne Zähler (nicht über conftest angelegt): alte Wartezeit
                return
            pg.wait_for_function(_QUIET_FN, arg=quiet_ms, timeout=left, polling=50)
            return
        except PWTimeout:
            return
        except PWError as e:
            if "context was destroyed" not in str(e) and "navigation" not in str(e):
                raise
            pg.wait_for_load_state("load")                                    # Seite wurde neu geladen: danach noch einmal


def settled(pg, timeout=T):
    """Layout fertig: Schriften geladen, zwei Frames ohne Änderung der Seitenhöhe und keine laufenden Anfragen/DOM-Änderungen
    (Screenshots und Messungen nie mitten im Aufbau)."""
    pg.evaluate("() => document.fonts.ready.then(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))))")
    pg.wait_for_function("() => { const h = document.documentElement.scrollHeight, w = window.__hs = window.__hs || {h: 0, n: 0}; w.n = w.h === h ? w.n + 1 : 0; w.h = h; return w.n >= 3; }",
                         timeout=timeout, polling=100)
    quiet(pg, cap=timeout)


def open_details(pg, selector, open=True, timeout=T):
    """Auf-/Zuklappbare Elemente (<details>) explizit auf einen Zustand setzen statt anzuklicken (ein Klick kehrt den Zustand um, wenn er schon passt)
    und warten, bis die Seite den Zustand übernommen hat (toggle-Ereignis, danach Layout)."""
    want = bool(open)
    pg.wait_for_selector(selector, state="attached", timeout=timeout)
    pg.evaluate("([sel, want]) => document.querySelectorAll(sel).forEach(d => { d.open = want; })", [selector, want])
    pg.wait_for_function("([sel, want]) => [...document.querySelectorAll(sel)].every(d => d.open === want)", arg=[selector, want], timeout=timeout)
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def wait_route(pg, hash_prefix, timeout=T):
    """Warten, bis die Seite die Route erreicht hat (location.hash beginnt mit `hash_prefix`, z. B. '#/tour/')."""
    pg.wait_for_function("(h) => location.hash.startsWith(h)", arg=hash_prefix, timeout=timeout)


def set_lang(pg, lang, timeout=T):
    """Sprache über die Auswahl in der Kopfzeile umstellen und auf das Neuzeichnen warten (html[lang])."""
    pg.select_option("#langsw", lang)
    pg.wait_for_function("(l) => document.documentElement.lang === l || document.documentElement.lang.startsWith(l)", arg=lang, timeout=timeout)
    quiet(pg)


def eager_images(pg, timeout=T):
    """Bilder mit loading=lazy sofort laden lassen und warten, bis alle fertig (oder fehlgeschlagen) sind – für Messungen und Screenshots."""
    pg.evaluate("() => document.querySelectorAll('img[loading=lazy]').forEach(i => { i.loading = 'eager'; })")
    pg.wait_for_function("() => [...document.images].every(i => i.complete)", timeout=timeout)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def wait_http(url, tries=150, delay=0.2):
    """Wartet, bis der Server auf `url` antwortet; bricht mit klarer Meldung ab (statt später mit einem Verbindungsfehler im Test)."""
    last = None
    for _ in range(tries):
        try:
            urllib.request.urlopen(url, timeout=1)
            return
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(delay)
    raise RuntimeError(f"Server unter {url} nicht erreichbar: {last}")


def press_until_gone(pg, key, selector, timeout=T):
    """Taste drücken, bis das Element weg ist. Ein einzelner Tastendruck kann verpuffen, wenn der Dialog noch nicht fokussiert/angeschlossen ist (Fokus, Ereignisanmeldung nach dem Aufbau);
    mehrfaches Drücken ist harmlos, weil nach dem Schließen nichts mehr auf die Taste wartet."""
    end = time.time() + timeout / 1000
    while True:
        pg.keyboard.press(key)
        try:
            pg.wait_for_selector(selector, state="detached", timeout=600)
            return
        except Exception:  # noqa: BLE001 - Zeitüberschreitung: erneut drücken
            if time.time() > end:
                raise AssertionError(f"{selector} nach {key} nicht verschwunden")


def toggle_details(pg, selector, open=True, timeout=T):
    """Zustand eines <details> per KLICK auf die Zusammenfassung herstellen (für Tests, die das Klicken selbst prüfen) – ohne die Doppelklick-Falle:
    erst Ruhe abwarten (kein Neuaufbau mehr, der den Klick verschluckt oder den Zustand zurücksetzt), nur klicken, wenn der Zustand noch nicht passt, danach auf den Zustand warten."""
    from playwright.sync_api import TimeoutError as PWTimeout
    fn = "([s, w]) => { const d = document.querySelector(s); return !!d && d.open === w; }"
    quiet(pg, 3000)
    for _ in range(3):
        if pg.evaluate(fn, [selector, bool(open)]):
            break
        pg.locator(selector).locator("> summary").first.click()
        try:
            pg.wait_for_function(fn, arg=[selector, bool(open)], timeout=3000)
            break
        except PWTimeout:
            quiet(pg, 3000)
    pg.wait_for_function(fn, arg=[selector, bool(open)], timeout=timeout)
