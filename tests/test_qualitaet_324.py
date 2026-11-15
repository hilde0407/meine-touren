"""3.24.0 – Service Worker und Skriptliste: jede JS-Datei der App ist in der Startseite eingebunden, die Cache-Version ist erhöht, Hinweise zur Version sind da."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ST = ROOT / "app" / "static"
EINZEL = {"seite-reset.js", "seite-share.js", "seite-show.js", "seite-slideshow.js"}      # gehören zu eigenen Seiten (reset/share/show/slideshow.html)


def test_alle_skripte_in_der_startseite_und_im_cache_der_app():
    html = (ST / "index.html").read_text(encoding="utf-8")
    inc = re.findall(r'<script src="(js/[^"]+\.js)"', html)
    assert len(inc) == len(set(inc))
    for f in sorted((ST / "js").glob("*.js")):
        if f.name not in EINZEL:
            assert f"js/{f.name}" in inc, f"{f.name} fehlt in index.html (und damit im Cache des Service Workers)"
    for i in inc:
        assert (ST / i).is_file(), i
    for n in range(40, 59):
        assert any(x.startswith(f"js/{n}-") for x in inc), n
    for f in EINZEL:
        assert any(f in (ST / h).read_text(encoding="utf-8") for h in ("reset.html", "share.html", "show.html", "slideshow.html") if (ST / h).exists()), f


def test_service_worker_version_und_hinweise():
    sw = (ST / "sw.js").read_text(encoding="utf-8")
    assert 'const V = "mt-v103"' in sw
    from app import config
    assert config.VERSION.startswith("3.25.0 · Meine Touren")
    notes = (ROOT / "docs" / "versionen" / "3.24.1.md").read_text(encoding="utf-8")
    assert notes.startswith("# 3.24.1") and "2:60" in notes
