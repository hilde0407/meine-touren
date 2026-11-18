#!/usr/bin/env python3
"""Testlauf mit denselben Standardoptionen wie die CI (siehe tests/README.md).

    python scripts/test.py                      # alles, parallel (falls pytest-xdist da ist), Wiederholung fehlgeschlagener Tests (falls pytest-rerunfailures da ist)
    python scripts/test.py tests/test_gruppen_ui.py -k link      # weitere Argumente gehen an pytest
    MT_TEST_WORKERS=1 python scripts/test.py    # seriell (Fehlersuche); MT_TEST_WORKERS=4 für feste Anzahl
    MT_TEST_RERUNS=0 python scripts/test.py     # ohne Wiederholung (Flakes sichtbar machen)

Worker: Standard = Zahl der Prozessoren, mindestens 2 und höchstens 4 (die Browsertests warten viel und belasten die CPU nur zur Hälfte).
Je Worker laufen ganze Dateien nacheinander (--dist loadfile): die Server der Browsertests werden je Datei einmal gestartet.
"""
import importlib.util
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _has(mod):
    return importlib.util.find_spec(mod) is not None


def main(argv):
    cmd = [sys.executable, "-m", "pytest", "-q", "-rfER"]            # -rR: Tests, die erst beim Wiederholen bestanden, am Ende auflisten
    reruns = os.environ.get("MT_TEST_RERUNS", "2")
    if reruns != "0" and _has("pytest_rerunfailures"):
        cmd += ["--reruns", reruns]
    workers = os.environ.get("MT_TEST_WORKERS") or str(min(4, max(2, os.cpu_count() or 2)))
    if workers != "1" and _has("xdist"):
        cmd += ["-n", workers, "--dist", "loadfile"]
    elif workers != "1":
        print("Hinweis: pytest-xdist fehlt (pip install -r requirements-dev.txt) – der Lauf ist seriell und dauert deutlich länger.", file=sys.stderr)
    if not any(not a.startswith("-") and (ROOT / a.split("::")[0]).exists() for a in argv):
        cmd.append("tests")
    return subprocess.call(cmd + argv, cwd=ROOT)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
