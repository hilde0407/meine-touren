"""Kern und volle Suite (tests/README.md): jeder Test liegt in genau einem Topf, Kern + Rest = alle gesammelten Tests (keine Lücke, keine Doppelung);
jede Hauptseite hat mindestens eine Browser-Stichprobe im Kern; scripts/test.py und die Workflows benutzen die Töpfe wie beschrieben."""
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WF = ROOT / ".github" / "workflows"


def _ids(*args):
    out = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:randomly", "-p", "no:cacheprovider", *args, "tests"],
                         capture_output=True, text=True, cwd=ROOT, timeout=300)
    ids = [x for x in out.stdout.splitlines() if "::" in x]
    assert ids, out.stdout[-2000:] + out.stderr[-2000:]
    return ids


def test_kern_plus_rest_gleich_alle():
    alle, kern, rest = _ids(), _ids("-m", "not voll"), _ids("-m", "voll")
    assert len(alle) == len(set(alle))
    assert set(kern) | set(rest) == set(alle) and not set(kern) & set(rest)
    assert len(kern) + len(rest) == len(alle)
    browser_kern = _ids("-m", "kern")
    assert set(browser_kern) <= set(kern) and set(browser_kern) <= set(_ids("-m", "browser"))      # „kern“ nur an Browsertests (Server-Tests sind ohnehin im Kern)
    assert 15 <= len(browser_kern) <= 60, len(browser_kern)                                        # Stichprobe, nicht die halbe Suite
    files = {i.split("::")[0] for i in rest}
    assert "tests/test_uebersicht_bilder_354.py" not in files and "tests/test_stil.py" not in files   # Server- und Stiltests immer im Kern


def test_jede_hauptseite_hat_eine_stichprobe_im_kern():
    kern = _ids("-m", "kern")
    need = {
        "Übersicht, Karte, Tourenliste, Statistik, Rückblick, Reisen, Wanderführer, Fotos, Prüfen, Verwaltung, Konto, Suche, Tourseite, Vergleich": "tests/test_browser.py::test_view_loads_without_errors",
        "Tourseite (Haupt- und Unterseite)": "tests/test_tourseite_ui.py::",
        "Statistik": "tests/test_statistik_ui.py::",
        "Tourenliste mit Fotos": "tests/test_titelfotos_352_ui.py::",
        "Foto-Streifen": "tests/test_fotostreifen_351_ui.py::",
        "Wanderführer": "tests/test_wanderfuehrer_353_ui.py::",
        "Aufzeichnen-Seite der App": "tests/test_app_aufzeichnen_349_ui.py::",
        "Aufzeichnen im Browser": "tests/test_browser.py::test_record_view_app",
        "Verwaltung (Reiter)": "tests/test_browser.py::test_admin_tabs",
        "Übersicht (Bilder, Bausteine)": "tests/test_uebersicht_bilder_354_ui.py::",
        "Seite anpassen": "tests/test_seitenlayout_ui.py::",
        "Karte": "tests/test_karte_343_ui.py::",
    }
    missing = [k for k, p in need.items() if not any(i.startswith(p) for i in kern)]
    assert not missing, missing
    src = (ROOT / "tests" / "test_browser.py").read_text(encoding="utf-8")
    views = re.search(r"^VIEWS = \[(.*?)\]", src, re.M | re.S).group(1)
    for v in ("dash", "map", "tours", "records", "trips", "places", "photos", "check", "admin", "account", "tour/"):
        assert f'"{v}' in views, v


def _build():
    spec = importlib.util.spec_from_file_location("mt_test_script", ROOT / "scripts" / "test.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m.build


def test_skript_modi():
    build = _build()
    cmd, mode = build([])
    assert mode == "--kern" and cmd[cmd.index("-m", 3) + 1] == "not voll" and cmd[-1] == "tests"
    cmd, mode = build(["--voll"])
    assert mode == "--voll" and "-m" not in cmd[3:] and cmd[-1] == "tests"
    cmd, mode = build(["--rest"])
    assert cmd[cmd.index("-m", 3) + 1] == "voll"
    cmd, mode = build(["tests/test_stil.py", "-k", "x"])                     # genannte Dateien: alles darin, kein Kern-Filter
    assert mode == "--voll" and "-m" not in cmd[3:] and cmd[-3:] == ["tests/test_stil.py", "-k", "x"] and "tests" not in cmd
    cmd, mode = build(["--kern", "tests/test_browser.py"])
    assert cmd[cmd.index("-m", 3) + 1] == "not voll"


def test_workflows():
    t = (WF / "tests.yml").read_text(encoding="utf-8")
    v = (WF / "tests-voll.yml").read_text(encoding="utf-8")
    r = (WF / "release.yml").read_text(encoding="utf-8")
    assert "python scripts/test.py --kern" in t and "uses: ./.github/workflows/tests-voll.yml" in t and "[voll]" in t
    assert "python scripts/test.py --voll" in v and "workflow_call:" in v and "workflow_dispatch:" in v
    # Windows wie bisher: wöchentlich (nur der Montags-Termin, nicht der nächtliche), manuell oder „[windows]“, volle Suite
    win = t[t.index("  windows:"):]
    assert "github.event.schedule == '17 4 * * 1'" in win and "workflow_dispatch" in win and "[windows]" in win and "scripts/test.py --voll" in win
    # Veröffentlichen: erst die volle Suite, dann die Veröffentlichung; Image und APK hängen an der Veröffentlichung
    jobs = r[r.index("jobs:"):]
    assert re.search(r"\n  tests:\n    uses: \./\.github/workflows/tests-voll\.yml", jobs)
    rel = jobs[jobs.index("\n  release:"):jobs.index("\n  docker:")]
    assert "\n    needs: tests\n" in rel and "gh release create" in rel
    assert jobs.index("\n  tests:") < jobs.index("\n  release:")
    assert "\n  docker:\n    needs: release\n" in jobs and "\n  android:\n    needs: release\n" in jobs
