"""E-Mail-Pflicht, Passwort zurücksetzen per E-Mail und Zwei-Faktor-Anmeldung (TOTP)."""
import re, time
import pytest
from fastapi.testclient import TestClient
from tests.test_core import fresh      # noqa: F401  (Fixture)


def test_totp_rfc6238_vector():
    from app import security
    sec = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"          # ASCII „12345678901234567890“
    assert security.totp_now(sec, t=59, digits=8) == "94287082"
    assert security.totp_now(sec, t=1111111109, digits=8) == "07081804"
    assert security.totp_verify(sec, security.totp_now(sec, t=1000), 0, t=1000) == 1000 // 30
    assert security.totp_verify(sec, security.totp_now(sec, t=1000), 1000 // 30, t=1000) is None      # ein Code gilt nur einmal


@pytest.fixture
def app(fresh, monkeypatch):                    # noqa: F811
    from app import main, security
    sent = []
    monkeypatch.setattr(security, "send_mail", lambda to, subj, body: sent.append((to, subj, body)))
    monkeypatch.setattr(security, "send_async", lambda to, subj, body: to and sent.append((to, subj, body)))
    c = TestClient(main.app)
    return c, sent, main, security


def _setup(c):
    assert c.post("/api/setup", json={"name": "Max", "password": "geheim1234"}).status_code == 400          # E-Mail fehlt
    assert c.post("/api/setup", json={"name": "Max", "password": "geheim1234", "email": "kaputt"}).status_code == 400
    assert c.post("/api/setup", json={"name": "Max", "password": "geheim1234", "email": "max@example.com"}).status_code == 200


def test_email_required_and_reset_flow(app):
    c, sent, main, security = app
    _setup(c)
    assert c.post("/api/users", json={"name": "Anna", "password": "annas-pass1"}).status_code == 400
    assert c.post("/api/users", json={"name": "Anna", "password": "annas-pass1", "email": "anna@example.com"}).status_code == 200
    assert c.get("/api/me").json()["user"]["email"] == "max@example.com"
    anon = TestClient(main.app)
    # ohne Mail-Einrichtung: klare Meldung
    assert anon.post("/api/forgot", json={"who": "anna@example.com"}).status_code == 503
    for k, v in {"smtp_host": "smtp.example.com", "smtp_from": "touren@example.com", "public_url": "https://touren.example.net"}.items():
        security.conf_set(k, v)
    assert anon.post("/api/forgot", json={"who": "unbekannt@example.com"}).json() == {"ok": True} and not sent      # keine Auskunft, ob bekannt
    assert anon.post("/api/forgot", json={"who": "ANNA@example.com"}).json() == {"ok": True}
    to, subj, body = sent[-1]
    assert to == "anna@example.com" and "Passwort" in subj
    tok = re.search(r"https://touren\.example\.net/reset/([\w-]+)", body).group(1)
    assert anon.get("/reset/" + tok).status_code == 200 and anon.get("/api/reset/" + tok).json()["name"] == "Anna"
    assert anon.post("/api/reset", json={"token": tok, "password": "kurz"}).status_code == 400
    assert anon.post("/api/reset", json={"token": tok, "password": "neues-pass-99"}).json()["ok"] is True
    assert anon.post("/api/reset", json={"token": tok, "password": "nochmal-123"}).status_code == 404        # nur einmal benutzbar
    assert anon.post("/api/login", json={"name": "anna", "password": "annas-pass1"}).status_code == 401
    assert anon.post("/api/login", json={"name": "anna", "password": "neues-pass-99"}).status_code == 200
    # Abgelaufen
    anon.post("/api/forgot", json={"who": "anna"}); tok2 = re.search(r"/reset/([\w-]+)", sent[-2][2] if len(sent) > 1 else sent[-1][2])
    security.auth.q("UPDATE resets SET exp=1")
    assert anon.get("/api/reset/" + (tok2.group(1) if tok2 else "x")).status_code == 404


def test_two_factor_login_and_recovery(app):
    c, sent, main, security = app
    _setup(c)
    st = c.get("/api/me/2fa").json(); assert st["on"] is False
    s = c.post("/api/me/2fa/setup").json()
    assert s["uri"].startswith("otpauth://totp/") and s["secret"] in s["uri"]
    assert c.post("/api/me/2fa/enable", json={"code": "000000"}).status_code == 400
    t0 = time.time()
    r = c.post("/api/me/2fa/enable", json={"code": security.totp_now(s["secret"], t0)}).json()
    assert len(r["codes"]) == 8 and c.get("/api/me/2fa").json()["on"] is True
    # Anmeldung: Passwort allein reicht nicht
    a = TestClient(main.app)
    j = a.post("/api/login", json={"name": "max", "password": "geheim1234"}).json()
    assert j.get("need_2fa") and "ticket" in j and a.get("/api/tours").status_code == 401
    assert a.post("/api/login/2fa", json={"ticket": j["ticket"], "code": "123456"}).status_code == 401
    # derselbe Zeitschritt wie beim Einschalten darf nicht noch einmal benutzt werden → nächster Schritt
    code = security.totp_now(s["secret"], t0 + 30)
    ok = a.post("/api/login/2fa", json={"ticket": j["ticket"], "code": code})
    assert ok.status_code == 200 and a.get("/api/tours").status_code == 200
    # Wiederherstellungscode: einmal gültig
    b = TestClient(main.app)
    j = b.post("/api/login", json={"name": "max", "password": "geheim1234"}).json()
    assert b.post("/api/login/2fa", json={"ticket": j["ticket"], "code": r["codes"][0]}).status_code == 200
    j = TestClient(main.app).post("/api/login", json={"name": "max", "password": "geheim1234"}).json()
    assert TestClient(main.app).post("/api/login/2fa", json={"ticket": j["ticket"], "code": r["codes"][0]}).status_code == 401
    # Ticket wird nach 5 Fehlversuchen ungültig
    j = TestClient(main.app).post("/api/login", json={"name": "max", "password": "geheim1234"}).json()
    d = TestClient(main.app)
    for _ in range(5):
        d.post("/api/login/2fa", json={"ticket": j["ticket"], "code": "111111"})
    assert d.post("/api/login/2fa", json={"ticket": j["ticket"], "code": r["codes"][1]}).status_code == 401
    # Ausschalten braucht Passwort und Code
    assert c.post("/api/me/2fa/disable", json={"password": "falsch", "code": "x"}).status_code == 400
    assert c.post("/api/me/2fa/disable", json={"password": "geheim1234", "code": r["codes"][2]}).status_code == 200
    assert c.get("/api/me/2fa").json()["on"] is False
    assert TestClient(main.app).post("/api/login", json={"name": "max", "password": "geheim1234"}).json().get("ok") is True


def test_admin_resets_two_factor_and_mail_settings(app):
    c, sent, main, security = app
    _setup(c)
    c.post("/api/users", json={"name": "Anna", "password": "annas-pass1", "email": "anna@example.com"})
    a = TestClient(main.app); a.post("/api/login", json={"name": "anna", "password": "annas-pass1"})
    s = a.post("/api/me/2fa/setup").json(); a.post("/api/me/2fa/enable", json={"code": security.totp_now(s["secret"])})
    assert {u["uid"]: u["totp_on"] for u in c.get("/api/users").json()}["anna"] == 1
    assert a.get("/api/mail/settings").status_code == 403                       # nur Administratoren
    assert c.patch("/api/users/anna", json={"reset_2fa": True, "email": "neu@example.com"}).status_code == 200
    u = {u["uid"]: u for u in c.get("/api/users").json()}["anna"]
    assert u["totp_on"] == 0 and u["email"] == "neu@example.com"
    assert c.post("/api/mail/settings", json={"smtp_host": "h.example", "smtp_port": "x"}).status_code == 400
    assert c.post("/api/mail/settings", json={"smtp_host": "h.example", "smtp_from": "a@b.de", "smtp_pw": "geheimes", "public_url": "https://x.net"}).status_code == 200
    g = c.get("/api/mail/settings").json()
    assert g["smtp_host"] == "h.example" and g["pw_set"] is True and "geheimes" not in str(g) and g["ready"] is True
    assert a.get("/api/tours").status_code == 401                               # Sitzungen des Benutzers wurden beendet
    a.post("/api/login", json={"name": "anna", "password": "annas-pass1"})
    # E-Mail ändern braucht das Passwort
    assert a.post("/api/me/email", json={"email": "x@example.com", "password": "falsch"}).status_code == 400
    assert a.post("/api/me/email", json={"email": "x@example.com", "password": "annas-pass1"}).status_code == 200


def test_viewer_cannot_use_security_endpoints(app):
    c, sent, main, security = app
    _setup(c)
    c.post("/api/users", json={"name": "Oma", "password": "omas-pass12", "role": "viewer", "email": "oma@example.com"})
    v = TestClient(main.app); v.post("/api/login", json={"name": "oma", "password": "omas-pass12"})
    assert v.post("/api/me/2fa/setup").status_code == 403 and v.post("/api/me/email", json={}).status_code == 403


def test_trip_names_are_unique(fresh, monkeypatch):       # noqa: F811
    """Mehrere Reisen im selben Bundesland heißen nicht alle gleich; kurze gelten als Kurzreise."""
    from app import more2
    trips = [{"id": "a", "region": "Hessen", "start": "2024-05-03", "days": 2, "tours": ["a"]},
             {"id": "b", "region": "Hessen", "start": "2024-07-10", "days": 5, "tours": ["b"]},
             {"id": "c", "region": "Hessen", "start": "2024-08-01", "days": 2, "tours": ["c"]},
             {"id": "d", "region": "Bayern", "start": "2024-09-01", "days": 4, "tours": ["d"]}]
    geo = {"a": {"g_place": "Rhön"}, "b": {"g_place": "Rhön"}, "c": {"g_place": "Taunus"}, "d": {}}
    more2._unique_names(trips, geo)
    names = [t["region"] for t in trips]
    assert len(set(names)) == 4 and names[3] == "Bayern" and "Taunus" in names[2] and "Mai 2024" in names[0] and "Juli 2024" in names[1]
    assert [t["short"] for t in trips] == [True, False, True, False]


def test_home_places_exclude_regular_areas(fresh):        # noqa: F811
    """Zuhause und Stammgebiete (viele Touren über viele Monate) zählen nie als Reise; ein Urlaubsort schon."""
    from app import more2
    from app.gpxtools import TZ
    from datetime import datetime
    ts = lambda y, m, d: int(datetime(y, m, d, 9, tzinfo=TZ).timestamp())
    tours = [{"lat": 50.1 + i * 0.001, "lng": 8.6, "start_ts": ts(2023 + i // 12, i % 12 + 1, 5)} for i in range(24)]              # Zuhause: 24 Monate
    tours += [{"lat": 28.1, "lng": -15.4, "start_ts": ts(2024, i % 9 + 1, 12)} for i in range(14)]                                    # zweiter Wohnort
    tours += [{"lat": 46.5, "lng": 10.0, "start_ts": ts(2024, 7, 1 + d)} for d in range(7)]                                           # Urlaub
    homes = more2.home_places(tours)
    near = lambda p, q: more2.extras._hav(p, q) < 20000
    assert len(homes) == 2 and any(near(h, (50.1, 8.6)) for h in homes) and any(near(h, (28.1, -15.4)) for h in homes)
    assert not any(near(h, (46.5, 10.0)) for h in homes)


def test_photo_positions_from_track_time(fresh):          # noqa: F811
    """Fotos ohne GPS bekommen ihre Position aus der Uhrzeit auf dem Track der Tour (est=1); Fotos mit GPS bleiben unverändert."""
    from app import db, routes, main
    base = 1700000000
    with TestClient(main.app) as c:
        db.execute("INSERT OR REPLACE INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES('e1','Estour','hike',?,?,1000,100,1,1,48,8,'x')", (base, base + 100))
        routes.store("e1", [(48 + j * 0.001, 8.0, 300, j * 1000) for j in range(101)])          # Minute für Minute: 1 s = 0,001°
        db.execute("INSERT INTO photos(path,mtime,size,taken_ts,tour_id) VALUES('/x/e1.jpg',1,1,?,?)", (base + 50, "e1"))
        db.execute("INSERT INTO photos(path,mtime,size,taken_ts,lat,lng,tour_id) VALUES('/x/e2.jpg',1,1,?,?,?,?)", (base + 60, 10.5, 20.5, "e1"))
        assert len(c.get("/api/photos?gps=true").json()) == 1                                    # ohne est: nur das Foto mit GPS
        r = {p["taken_ts"]: p for p in c.get("/api/photos?gps=true&est=true").json()}
        assert r[base + 50]["est"] == 1 and abs(r[base + 50]["lat"] - 48.05) < 0.002 and r[base + 60]["est"] == 0 and r[base + 60]["lat"] == 10.5
