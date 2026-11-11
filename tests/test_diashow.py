"""Diashow: Vollbild, Bedienelemente und Wischen auch auf Touchgeräten."""
from tests.test_browser import app_url  # noqa: F401


def test_slideshow_fullscreen_controls_and_swipe(app_url):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(locale="de-DE", viewport={"width": 820, "height": 1180}, has_touch=True, is_mobile=True)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/pic/**", lambda r: r.abort())          # Bilddateien fehlen im Test; es geht um die Bedienung
        pg.goto(app_url + "/slideshow.html"); pg.wait_for_timeout(1500)
        cap = lambda: pg.inner_text("#cap")
        assert "(1/" in cap()
        assert pg.evaluate("document.querySelector('#ctl').classList.contains('off')") is False      # Bedienleiste anfangs sichtbar
        pg.wait_for_timeout(3500)
        assert pg.evaluate("document.querySelector('#ctl').classList.contains('off')")               # blendet sich aus
        pg.touchscreen.tap(410, 600)                                                                  # Mitte: Leiste zeigen
        pg.wait_for_timeout(300)
        assert pg.evaluate("!document.querySelector('#ctl').classList.contains('off')")
        pg.touchscreen.tap(700, 600); pg.wait_for_timeout(300)                                       # rechts: weiter
        assert "(2/" in cap(), cap()
        pg.evaluate("""() => { const t = (type, x) => document.dispatchEvent(new TouchEvent(type, {bubbles: true, touches: type === 'touchend' ? [] : [new Touch({identifier: 1, target: document.body, clientX: x, clientY: 500})], changedTouches: [new Touch({identifier: 1, target: document.body, clientX: x, clientY: 500})]})); window.dispatchEvent(new TouchEvent('touchstart', {touches: [new Touch({identifier: 1, target: document.body, clientX: 600, clientY: 500})]})); window.dispatchEvent(new TouchEvent('touchend', {changedTouches: [new Touch({identifier: 1, target: document.body, clientX: 300, clientY: 500})]})); }""")
        pg.wait_for_timeout(300)
        assert "(3/" in cap(), cap()                                                                  # Wischen nach links = nächstes Foto
        pg.tap("#bfs"); pg.wait_for_timeout(500)
        assert pg.evaluate("!!(document.fullscreenElement || document.webkitFullscreenElement)")      # Vollbild per Knopf (Touch)
        pg.tap("#bfs"); pg.wait_for_timeout(500)
        assert pg.evaluate("!(document.fullscreenElement || document.webkitFullscreenElement)")
        assert not errs, errs
        b.close()


def test_nebenseiten_laufen_unter_csp(app_url):
    """Freigabe-Seite und Diashow funktionieren ohne Inline-Skripte; die Richtlinie blockiert nichts."""
    import json, urllib.request
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(locale="de-DE", viewport={"width": 1280, "height": 900})
        bad = []
        pg.on("pageerror", lambda e: bad.append(str(e)))
        pg.on("console", lambda m: bad.append(m.text) if "Content Security Policy" in m.text else None)
        pg.route("**/*", lambda r: r.abort() if not r.request.url.startswith(app_url) else r.continue_())
        tid = json.loads(urllib.request.urlopen(app_url + "/api/tours").read())[0]["id"]
        rq = urllib.request.Request(app_url + f"/api/tours/{tid}/share", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
        tok = json.loads(urllib.request.urlopen(rq).read())["token"]
        r = pg.goto(app_url + "/s/" + tok); pg.wait_for_timeout(1500)
        assert "script-src 'self'" in r.headers.get("content-security-policy", "")
        assert pg.evaluate("document.body.innerText.length") > 40 and pg.evaluate("!!document.querySelector('.leaflet-container')")
        rq = urllib.request.Request(app_url + f"/api/tours/{tid}/share", data=b'{"show": true}', headers={"Content-Type": "application/json"}, method="POST")
        r = pg.goto(app_url + "/s/" + json.loads(urllib.request.urlopen(rq).read())["token"]); pg.wait_for_timeout(1500)
        assert "script-src 'self'" in r.headers.get("content-security-policy", "") and pg.evaluate("document.body.innerText.length") > 10
        r = pg.goto(app_url + "/reset/gibtsnicht"); pg.wait_for_timeout(800)
        assert "script-src 'self'" in r.headers.get("content-security-policy", "") and pg.evaluate("document.body.innerText.length") > 20
        r = pg.goto(app_url + "/slideshow.html"); pg.wait_for_timeout(1200)
        assert "script-src 'self'" in r.headers.get("content-security-policy", "") and "(1/" in pg.inner_text("#cap")
        assert not bad, bad
        b.close()
