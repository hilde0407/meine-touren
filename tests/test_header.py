"""Schutz-Header und Content-Security-Policy der Hauptoberfläche."""
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402

ST = Path(__file__).resolve().parent.parent / "app" / "static"


def test_security_headers():
    from fastapi.testclient import TestClient
    from app import main
    c = TestClient(main.app)
    r = c.get("/")
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-frame-options"] == "SAMEORIGIN"
    csp = r.headers["content-security-policy"]
    assert "script-src 'self' blob:;" in csp and "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0] and "object-src 'none'" in csp
    assert c.get("/api/version").headers["x-content-type-options"] == "nosniff"


def test_app_has_no_inline_script():
    """Die CSP verbietet Inline-JavaScript: index.html und die JS-Dateien dürfen keines enthalten."""
    html = (ST / "index.html").read_text(encoding="utf-8")
    assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html)
    for f in sorted((ST / "js").glob("*.js")):
        t = f.read_text(encoding="utf-8")
        assert not re.search(r'\son(click|change|input|error|load|submit)="', t), f.name
        assert 'href="javascript:' not in t and 'javascript:history' not in t, f.name


def test_nebenseiten_csp_und_kein_inline_script():
    """Auch Freigabe-, Diashow- und Rücksetz-Seite laufen unter der CSP und enthalten kein Inline-JavaScript."""
    from fastapi.testclient import TestClient
    from app import main
    c = TestClient(main.app)
    for n in ("reset", "share", "show", "slideshow"):
        html = (ST / f"{n}.html").read_text(encoding="utf-8")
        assert not re.search(r"<script(?![^>]*\bsrc=)[^>]*>", html), n
        assert not re.search(r'\son(click|change|input|error|load|submit)="', html), n
        assert (ST / "js" / f"seite-{n}.js").exists()
    for p in ("/slideshow.html", "/share.html", "/s/gibtsnicht", "/reset/gibtsnicht"):
        assert "script-src 'self' blob:;" in c.get(p).headers.get("content-security-policy", ""), p
