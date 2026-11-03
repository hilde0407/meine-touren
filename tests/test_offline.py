"""Offline-PWA: Service Worker liefert zuletzt gesehene Daten ohne Verbindung."""
from tests.test_browser import app_url  # noqa: F401


def test_offline_reload_shows_cached_tour(app_url):
    from playwright.sync_api import sync_playwright
    base = app_url.replace("127.0.0.1", "localhost")
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        ctx = b.new_context(locale="de-DE")
        pg = ctx.new_page()
        pg.route("**/tiles/**", lambda r: r.abort())
        pg.goto(base + "/#/tours"); pg.wait_for_timeout(2500)
        pg.evaluate("navigator.serviceWorker.ready.then(() => 1)")
        pg.reload(); pg.wait_for_timeout(1500)        # ab jetzt steuert der Service Worker die Seite
        tid = pg.evaluate("TOURS[0].id")
        pg.goto(base + "/#/tour/" + tid); pg.wait_for_timeout(2000)
        name = pg.evaluate("BY[TOURS[0].id].name")
        ctx.set_offline(True)
        pg.reload(); pg.wait_for_timeout(2500)
        assert pg.evaluate("document.querySelector('#offbar').style.display") == "block"
        assert name in pg.inner_text("main"), pg.inner_text("main")[:300]
        ctx.set_offline(False)
        b.close()
