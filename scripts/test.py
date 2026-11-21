#!/usr/bin/env python3
"""Testlauf mit denselben Standardoptionen wie die CI (siehe tests/README.md, Abschnitt „Kern und volle Suite“).

    python scripts/test.py                      # schneller Kern (Standard): alle Server-/Unit-/Format-/Stiltests + Browser-Stichproben (@pytest.mark.kern)
    python scripts/test.py --voll               # volle Suite: alles (= Kern + übrige Browsertests) – vor dem Veröffentlichen
    python scripts/test.py --rest               # nur die Tests, die nicht zum Kern gehören (Kontrolle: Kern + Rest = voll)
    python scripts/test.py tests/test_gruppen_ui.py -k link      # mit Dateien/Tests: alle genannten Tests (kein Kern-Filter, außer mit --kern)
    MT_TEST_WORKERS=1 python scripts/test.py    # seriell (Fehlersuche); MT_TEST_WORKERS=4 für feste Anzahl
    MT_TEST_RERUNS=0 python scripts/test.py     # ohne Wiederholung (Flakes sichtbar machen)
    MT_TEST_TIMEOUT=0 python scripts/test.py    # ohne Zeitgrenze je Test (Standard 600 s, pytest-timeout; ein hängender Test scheitert dann und wird wiederholt)

Worker: Standard = Zahl der Prozessoren, mindestens 2 und höchstens 4 (die Browsertests warten viel und belasten die CPU nur zur Hälfte).
Je Worker laufen ganze Dateien nacheinander (--dist loadfile): die Server der Browsertests werden je Datei einmal gestartet.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MODES = {"--kern": "not voll", "--voll": None, "--rest": "voll"}


def _has(mod):
    return importlib.util.find_spec(mod) is not None


def build(argv):
    """Befehlszeile für pytest (ohne Ausführung; getestet in tests/test_testsuite_kern.py)."""
    modes = [a for a in argv if a in MODES]
    argv = [a for a in argv if a not in MODES]
    if len(modes) > 1:
        raise SystemExit("Bitte nur einen Modus angeben: --kern, --voll oder --rest.")
    paths = any(not a.startswith("-") and (ROOT / a.split("::")[0]).exists() for a in argv)
    mode = modes[0] if modes else ("--voll" if paths else "--kern")    # genannte Dateien laufen ganz; ohne Angabe der Kern
    cmd = [sys.executable, "-m", "pytest", "-q", "-rfER"]            # -rR: Tests, die erst beim Wiederholen bestanden, am Ende auflisten
    reruns = os.environ.get("MT_TEST_RERUNS", "2")
    if reruns != "0" and _has("pytest_rerunfailures"):
        cmd += ["--reruns", reruns]
    timeout = os.environ.get("MT_TEST_TIMEOUT", "600")                # je Test höchstens 10 min (der längste braucht rund 1 min); 0 = aus
    if timeout != "0" and _has("pytest_timeout") and os.name != "nt":    # Windows kennt kein SIGALRM: dort beendet pytest-timeout den ganzen Worker – lieber ohne
        cmd += ["--timeout", timeout]
    workers = os.environ.get("MT_TEST_WORKERS") or str(min(4, max(2, os.cpu_count() or 2)))
    if workers != "1" and _has("xdist"):
        cmd += ["-n", workers, "--dist", "loadfile"]
    elif workers != "1":
        print("Hinweis: pytest-xdist fehlt (pip install -r requirements-dev.txt) – der Lauf ist seriell und dauert deutlich länger.", file=sys.stderr)
    if MODES[mode]:
        cmd += ["-m", MODES[mode]]
    if not paths:
        cmd.append("tests")
    return cmd + argv, mode


def main(argv):
    cmd, mode = build(argv)
    print(f"Testlauf: {'schneller Kern' if mode == '--kern' else 'volle Suite' if mode == '--voll' else 'nur der Rest (ohne Kern)'}", file=sys.stderr)
    return subprocess.call(cmd, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
