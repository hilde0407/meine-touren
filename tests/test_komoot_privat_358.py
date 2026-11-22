"""3.58.0 – Komoot: Upload immer privat (PATCH + Nachlesen), Notiz und Pins in der gesendeten GPX-Kopie, robusterer Upload (401, User-Agent),
Rückprüfung der Sichtbarkeit schon hochgeladener Touren, Komoot-Paket als ZIP, Rechte. Komoot wird nie wirklich angefragt (alles gestubbt)."""
import io
import json
import re
import zipfile

import pytest
from PIL import Image

from tests.test_core import fresh  # noqa: F401  (autouse: frische Datenbank je Test)
from app import db, gpxtools, komoot, portals, sync, tracks


def _gpx(t0="2026-07-01T08", wpt=True):
    pts = "".join(f'<trkpt lat="{47 + i * 0.001}" lon="11"><ele>{1000 + i}</ele><time>{t0}:{i // 60:02d}:{i % 60:02d}Z</time></trkpt>' for i in range(59))
    w = (f'<wpt lat="47.01" lon="11"><time>{t0}:00:20Z</time><name>Rast &lt;am&gt; See &amp; Brotzeit</name></wpt>'
         f'<wpt lat="47.03" lon="11"><time>{t0}:00:40Z</time><name>Kreuzung</name></wpt>') if wpt else ""
    return f'<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">{w}<trk><name>Gipfel</name><trkseg>{pts}</trkseg></trk></gpx>'


class FakeK:
    """Komoot-Stub: merkt sich, was gesendet wurde; Sichtbarkeit wie ein Konto mit Vorgabe „öffentlich“."""

    def __init__(self, default="public", patch_fails=False, read_fails=False, upload=("created", "555"), patch_ignored=False):
        self.default, self.patch_fails, self.read_fails, self.res, self.patch_ignored = default, patch_fails, read_fails, upload, patch_ignored
        self.sent, self.patches, self.reads, self.vis = [], [], [], {}

    def upload(self, gpx, sport, name, time_in_motion=None, info=None):
        self.sent.append({"gpx": gpx, "sport": sport, "name": name})
        st, rid = self.res
        if rid and rid not in self.vis:
            self.vis[rid] = self.default
        if info is not None:
            info["vis"] = None                  # Antwort ohne Sichtbarkeit: muss nachgelesen werden
        return st, rid

    def tour_raw(self, rid):
        self.reads.append(rid)
        if self.read_fails:
            raise komoot.KomootError("Tour laden: HTTP 503")
        if rid not in self.vis:
            raise komoot.KomootNotFound("Tour bei Komoot nicht gefunden (gelöscht?)")
        return {"id": rid, "type": "tour_recorded", "status": self.vis[rid], "name": "x"}

    def visibility(self, rid):
        return komoot._vis(self.tour_raw(rid))

    def set_visibility(self, rid, status="private"):
        self.patches.append((rid, status))
        if self.patch_fails:
            raise komoot.KomootError("Sichtbarkeit bei Komoot ändern fehlgeschlagen (HTTP 500)")
        if not self.patch_ignored:
            self.vis[rid] = status


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _local(tid="g1", wpt=True, note="Schöner Tag\nmit Sonne & <Wolken>\x07", t0="2026-07-01T08"):
    t, _ = tracks.adopt(_gpx(t0, wpt=wpt), "g.gpx", name="Gipfeltour", ident=tid)
    from app import wps
    wps.save(tid, wps.from_gpx(_gpx(t0, wpt=wpt)))
    if note:
        db.execute("INSERT OR REPLACE INTO tour_notes(id,note) VALUES(?,?)", (tid, note))
    db.execute("INSERT OR REPLACE INTO tour_peak(id,name,alt,lat,lng) VALUES(?,?,?,?,?)", (tid, "Hochkopf", 1058.0, 47.058, 11.0))
    return t


def _stub(monkeypatch, k):
    monkeypatch.setattr(sync, "_komoot", lambda *a, **kw: k)
    monkeypatch.setattr(portals, "CHECK_PAUSE_S", 0)
    return k


# ---------------------------------------------------------------- GPX-Kopie ----------------------------------------------------------------
def test_wegpunkte_und_notiz_nur_in_der_upload_kopie(monkeypatch):
    _local()
    stored = tracks.gpx_for("g1")
    assert "<wpt" not in stored and "<desc>" not in stored                       # gespeicherte Datei: wie bisher ohne Wegpunkte
    k = _stub(monkeypatch, FakeK())
    st, rid, _ = portals.upload_tour("g1", "komoot")
    assert (st, rid) == ("uploaded", "555")
    g = k.sent[0]["gpx"]
    assert g.count("<wpt ") == 3                                                  # zwei Pins + Gipfel
    assert "<name>Rast &lt;am&gt; See &amp; Brotzeit</name>" in g and "<name>Gipfel: Hochkopf</name>" in g and "<sym>Summit</sym>" in g
    assert "<desc>Schöner Tag\nmit Sonne &amp; &lt;Wolken&gt;</desc>" in g and "\x07" not in g
    assert g.index("</metadata>") < g.index("<wpt ") < g.index("<trk>")         # Reihenfolge nach GPX-1.1-Schema
    import xml.etree.ElementTree as ET
    ET.fromstring(g.encode())                                                     # wohlgeformt
    assert tracks.gpx_for("g1") == stored                                          # lokale Datei unverändert
    assert "<wpt" not in tracks.gpx_file("g1").read_text(encoding="utf-8")


def test_schalter_ohne_notiz_und_pins(monkeypatch):
    _local()
    k = _stub(monkeypatch, FakeK())
    db.put("komoot_with_notes", "0")
    portals.upload_tour("g1", "komoot")
    assert "<wpt" not in k.sent[0]["gpx"] and "<desc>" not in k.sent[0]["gpx"]
    db.put("komoot_with_notes", "1")
    portals.upload_tour("g1", "komoot", force=True, with_notes=False)              # Dialog-Häkchen gewinnt über die Einstellung
    assert "<wpt" not in k.sent[1]["gpx"]


def test_clean_text_und_laengen():
    assert gpxtools.clean_text("a\x00b\x1fc\r\nd\x7f", 50) == "abc\nd"
    s = gpxtools.clean_text("x" * 5000, gpxtools.DESC_MAX)
    assert len(s) == gpxtools.DESC_MAX and s.endswith("…")
    g = gpxtools.with_waypoints(_gpx(wpt=False), [{"lat": 47.0, "lng": 11.0, "name": "n" * 300, "desc": "d" * 900}], "")
    m = re.search(r"<name>(n+…)</name><desc>(d+…)</desc>", g)
    assert m and len(m.group(1)) == gpxtools.WPT_NAME_MAX and len(m.group(2)) == gpxtools.WPT_DESC_MAX
    assert "<metadata>" not in _gpx(wpt=False) and "<wpt" in g                    # ohne <metadata>: Wegpunkt direkt nach <gpx>
    # vorhandene Wegpunkte der Vorlage werden ersetzt, nicht verdoppelt
    g2 = gpxtools.with_waypoints(_gpx(), [{"lat": 47.0, "lng": 11.0, "name": "neu"}], "D")
    assert g2.count("<wpt ") == 1 and "<desc>D</desc>" in g2
    # convert ohne Wegpunkte bleibt wie bisher; mit Wegpunkten (nur für Kopien) enthält sie sie
    assert "<wpt" not in gpxtools.convert(_gpx(), "a.gpx")["gpx"]
    assert "<wpt" in gpxtools.convert(_gpx(), "a.gpx", wpts=[{"lat": 47.0, "lng": 11.0, "name": "x"}])["gpx"]


# ---------------------------------------------------------------- Sichtbarkeit beim Upload ----------------------------------------------------------------
def test_upload_setzt_privat_und_prueft(monkeypatch):
    _local()
    k = _stub(monkeypatch, FakeK(default="public"))
    info = {}
    portals.upload_tour("g1", "komoot", info=info)
    assert k.patches == [("555", "private")] and k.reads.count("555") >= 2        # vorher lesen, PATCH, nachlesen
    assert info["vis"] == "private" and info["vorher"] == "public" and "warnung" not in info
    s = portals.status_of("g1")["komoot"]
    assert s["vis"] == "private" and s["vis_ts"] and "privat (bestätigt)" in s["msg"] and "3 Wegpunkte" in s["msg"] and "mit Notiz" in s["msg"]


def test_upload_schon_privat_kein_patch(monkeypatch):
    _local()
    k = _stub(monkeypatch, FakeK(default="private"))
    portals.upload_tour("g1", "komoot")
    assert k.patches == [] and portals.status_of("g1")["komoot"]["vis"] == "private"


def test_patch_scheitert_bei_oeffentlicher_vorgabe_warnt_laut(monkeypatch):
    _local()
    k = _stub(monkeypatch, FakeK(default="public", patch_fails=True))
    with _client() as c:
        r = c.post("/api/tours/g1/upload", json={"portals": ["komoot"]}).json()["komoot"]
    assert r["status"] == "uploaded" and r["vis"] == "public" and "öffentlich" in r["warnung"] and "sofort" in r["warnung"]
    assert portals.status_of("g1")["komoot"]["vis"] == "public" and "ACHTUNG" in portals.status_of("g1")["komoot"]["msg"]
    assert k.patches == [("555", "private")]


def test_patch_ohne_wirkung_und_lesefehler_unbestaetigt(monkeypatch):
    _local()
    _stub(monkeypatch, FakeK(default="friends", patch_ignored=True))
    info = {}
    portals.upload_tour("g1", "komoot", info=info)
    assert info["vis"] == "friends" and "prüfen" in info["warnung"]
    _local("g2")
    _stub(monkeypatch, FakeK(read_fails=True))
    info = {}
    portals.upload_tour("g2", "komoot", info=info)
    assert info["vis"] == "unbekannt" and "nicht bestätigt" in info["warnung"]
    assert portals.status_of("g2")["komoot"]["vis_text"] == "Sichtbarkeit nicht bestätigt, bitte in Komoot prüfen"


def test_duplikat_wird_nur_gelesen(monkeypatch):
    _local()
    k = FakeK(upload=("duplicate", "777"))
    k.vis["777"] = "public"
    _stub(monkeypatch, k)
    info = {}
    st, rid, _ = portals.upload_tour("g1", "komoot", info=info)
    assert (st, rid) == ("duplicate", "777") and k.patches == [] and info["vis"] == "public" and "ÖFFENTLICH" in info["warnung"]
    assert portals.status_of("g1")["komoot"]["vis"] == "public"


# ---------------------------------------------------------------- echter Client, HTTP gestubbt ----------------------------------------------------------------
class _R:
    def __init__(self, status, j=None):
        self.status_code, self._j = status, j
        self.content = b"" if j is None else json.dumps(j).encode()
        self.text = self.content.decode()

    def json(self):
        if self._j is None:
            raise ValueError("leer")
        return self._j


def test_client_upload_401_meldet_neu_an_user_agent_und_patch(monkeypatch):
    k = komoot.Komoot("a@b.de", "pw-geheim"); k.user_id, k.token = "1", "alt"
    monkeypatch.setattr(komoot.time, "sleep", lambda s: None)
    monkeypatch.setattr(k, "login", lambda: setattr(k, "token", "neu") or "1")
    calls = []

    def fake(method, answers):
        def f(url, auth=None, headers=None, **kw):
            calls.append((method, url, auth[1], headers, kw)); return answers.pop(0)
        return f
    monkeypatch.setattr(komoot.requests, "post", fake("POST", [_R(401), _R(201, {"id": 42, "status": "public"})]))
    info = {}
    assert k.upload("<gpx/>", "hike", "T", info=info) == ("created", "42") and info["vis"] == "public"
    assert [c[2] for c in calls] == ["alt", "neu"]                                 # einmal neu angemeldet, dann wiederholt
    assert calls[0][3]["User-Agent"].startswith("MeineTouren/3.") and calls[0][3]["Content-Type"] == "application/octet-stream"
    assert calls[0][4]["params"]["status"] == "private" and "time_in_motion" not in calls[0][4]["params"]
    monkeypatch.setattr(komoot.requests, "patch", fake("PATCH", [_R(200, {"status": "private"})]))
    assert k.set_visibility("42") == "private"
    assert calls[-1][0] == "PATCH" and calls[-1][1].endswith("/v007/tours/42") and calls[-1][4]["json"] == {"status": "private"}
    monkeypatch.setattr(komoot.requests, "get", fake("GET", [_R(200, {"id": 42, "status": "private", "type": "tour_recorded"})]))
    assert k.visibility("42") == "private"
    # Fehlermeldungen nennen nie das Passwort
    monkeypatch.setattr(komoot.requests, "post", fake("POST", [_R(500), _R(500)]))
    with pytest.raises(komoot.KomootError) as e:
        k.upload("<gpx/>", "hike", "T")
    assert "pw-geheim" not in str(e.value) and "HTTP 500" in str(e.value)
    monkeypatch.setattr(komoot.requests, "post", fake("POST", [_R(401), _R(401)]))
    with pytest.raises(komoot.KomootError) as e:
        k.upload("<gpx/>", "hike", "T")
    assert "Anmeldung" in str(e.value) and "pw-geheim" not in str(e.value)
    monkeypatch.setattr(komoot.requests, "patch", fake("PATCH", [_R(403)]))
    with pytest.raises(komoot.KomootError):
        k.set_visibility("42")


def test_client_duplikat_mit_kennung(monkeypatch):
    k = komoot.Komoot("a@b.de", "pw"); k.user_id, k.token = "1", "t"
    monkeypatch.setattr(komoot.requests, "post", lambda url, **kw: _R(202, {"id": 9}))
    assert k.upload("<gpx/>", "hike", "T") == ("duplicate", "9")


# ---------------------------------------------------------------- Rückprüfung ----------------------------------------------------------------
def test_rueckpruefung_gesammelt_und_privat_per_klick(monkeypatch):
    for i, v in enumerate(["public", "private", "friends", None]):
        _local(f"g{i}", wpt=False, note="", t0=f"2026-07-0{i + 1}T08")
        portals.record(f"g{i}", "komoot", "uploaded", f"r{i}", "")
    portals.record("gx", "komoot", "error", "", "kaputt")                           # Fehler-Vermerke zählen nicht
    k = FakeK()
    k.vis.update({"r0": "public", "r1": "private", "r2": "friends"})                # r3 gibt es bei Komoot nicht mehr
    _stub(monkeypatch, k)
    with _client() as c:
        h = c.get("/api/komoot/hochgeladen").json()
        assert sorted(x["id"] for x in h["touren"]) == ["g0", "g1", "g2", "g3"] and h["zaehler"]["unbekannt"] == 4
        r = c.post("/api/komoot/sichtbarkeit", json={"ids": ["g0", "g1", "g2", "g3"]}).json()
        assert r["zaehler"] == {"oeffentlich": 1, "freunde": 1, "privat": 1, "unbekannt": 0, "fehlt": 1}
        assert k.patches == []                                                     # Prüfen ändert nie etwas
        assert c.get("/api/komoot/hochgeladen").json()["zaehler"]["oeffentlich"] == 1
        assert c.get("/api/tours/g0/uploads").json()["komoot"]["vis"] == "public"
        p = c.post("/api/tours/g0/komoot-privat").json()
        assert p["ok"] and p["vis"] == "private" and k.patches == [("r0", "private")]
        assert c.post("/api/tours/g3/komoot-privat").status_code == 400            # unbekannte Tour (Vermerk nach „fehlt“ gelöscht)
        many = c.post("/api/komoot/sichtbarkeit", json={"ids": [f"x{i}" for i in range(30)]}).json()
        assert len(many["ergebnis"]) == portals.CHECK_MAX                            # gedrosselt: höchstens 10 je Aufruf


def test_rueckpruefung_lesefehler_unbekannt(monkeypatch):
    _local(wpt=False, note="")
    portals.record("g1", "komoot", "uploaded", "r1", "")
    _stub(monkeypatch, FakeK(read_fails=True))
    with _client() as c:
        r = c.post("/api/komoot/sichtbarkeit", json={"ids": ["g1"]}).json()
    assert r["zaehler"]["unbekannt"] == 1 and portals.status_of("g1")["komoot"]["status"] == "uploaded"


# ---------------------------------------------------------------- Komoot-Paket ----------------------------------------------------------------
def _photo(tid, name="a.jpg"):
    from app import config, photos
    config.LIB_DIR.mkdir(parents=True, exist_ok=True)
    p = config.LIB_DIR / name
    im = Image.new("RGB", (3200, 2400), (30, 90, 140))
    ex = Image.Exif()
    g = ex.get_ifd(0x8825)
    g[1], g[2], g[3], g[4] = "N", (47.0, 1.0, 0.0), "E", (11.0, 0.0, 0.0)
    im.save(p, "JPEG", exif=ex.tobytes())
    t = db.one("SELECT start_ts FROM tours WHERE id=?", (tid,))
    photos._store([(str(p), p.stat().st_mtime, p.stat().st_size, t["start_ts"] + 20, 47.0167, 11.0)])
    photos.assign_all()
    return db.one("SELECT id FROM photos WHERE path=?", (str(p),))["id"]


def _zip(r):
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/zip" and "Komoot-Paket" in r.headers["content-disposition"]
    return zipfile.ZipFile(io.BytesIO(r.content))


def test_paket_inhalt_ohne_fotos():
    _local()
    _photo("g1")
    with _client() as c:
        z = _zip(c.get("/api/tours/g1/komoot-paket"))
    names = z.namelist()
    assert "Gipfeltour.gpx" in names and "README.txt" in names and "manifest.json" in names and "notiz.txt" in names
    assert not [n for n in names if n.startswith("fotos/")]                       # Vorgabe: keine Fotos
    g = z.read("Gipfeltour.gpx").decode()
    assert g.count("<wpt ") == 3 and "<desc>Schöner Tag" in g
    m = json.loads(z.read("manifest.json"))
    assert m["format"] == "meine-touren-komoot-paket" and m["wegpunkte"] == 3 and m["fotos"] == [] and m["notiz"] is True
    rd = z.read("README.txt").decode()
    assert "Sichtbarkeit".upper() in rd.upper() and "Nur ich" in rd and "keine Gesichter" in rd and "nicht zuverlässig zurückholen" in rd
    with _client() as c:
        z2 = _zip(c.get("/api/tours/g1/komoot-paket?notiz=0"))
    assert "notiz.txt" not in z2.namelist() and "<wpt" not in z2.read("Gipfeltour.gpx").decode()


def test_paket_fotos_verkleinert_ort_entfernt():
    _local()
    pid = _photo("g1")
    with _client() as c:
        z = _zip(c.get(f"/api/tours/g1/komoot-paket?fotos={pid}"))
        fn = [n for n in z.namelist() if n.startswith("fotos/")]
        assert len(fn) == 1
        im = Image.open(io.BytesIO(z.read(fn[0])))
        assert max(im.size) <= 2000
        ex = im.getexif()
        assert not ex.get_ifd(0x8825) and ex.get_ifd(0x8769).get(0x9003)          # kein GPS, Aufnahmezeit vorhanden
        assert json.loads(z.read("manifest.json"))["ort_entfernt"] is True
        z = _zip(c.get(f"/api/tours/g1/komoot-paket?fotos={pid}&ohne_ort=0"))
        im = Image.open(io.BytesIO(z.read([n for n in z.namelist() if n.startswith("fotos/")][0])))
        assert im.getexif().get_ifd(0x8825).get(2)                                 # Ort auf Wunsch enthalten
        # fremde/ungültige Fotos
        _local("g2", wpt=False, note="", t0="2026-07-05T08")
        other = _photo("g2", "b.jpg")
        assert c.get(f"/api/tours/g1/komoot-paket?fotos={other}").status_code == 400
        assert c.get("/api/tours/g1/komoot-paket?fotos=abc").status_code == 400
        assert c.get("/api/tours/nix/komoot-paket").status_code == 404


def test_rechte_betrachter_liest_paket_aber_setzt_nichts(monkeypatch):
    k = _stub(monkeypatch, FakeK())
    with _client() as c:
        assert c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"}).status_code == 200
        tid = c.post("/api/record/upload", json={"gpx": _gpx(), "name": "Gipfeltour", "sport": "hike"}).json()["id"]
        from app import ctx
        with ctx.as_user(c.get("/api/me").json()["user"]["uid"]):
            portals.record(tid, "komoot", "uploaded", "r1", "")
        k.vis["r1"] = "public"
        assert c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"}).status_code == 200
        v = _client()
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        r = v.get(f"/api/tours/{tid}/komoot-paket")
        assert r.status_code == 200 and zipfile.ZipFile(io.BytesIO(r.content)).read("README.txt")
        assert v.post(f"/api/tours/{tid}/komoot-privat").status_code == 403
        assert v.post(f"/api/tours/{tid}/upload", json={"portals": ["komoot"]}).status_code == 403
        assert v.post("/api/komoot/sichtbarkeit", json={"ids": [tid]}).status_code == 403
        assert v.get("/api/komoot/hochgeladen").status_code == 403
        assert k.patches == [] and k.sent == []
        assert _client().get(f"/api/tours/{tid}/komoot-paket").status_code == 401


@pytest.mark.parametrize("path,ok", [("/api/tours/g1/komoot-paket", True), ("/api/tours/g1/komoot-privat", False),
                                     ("/api/komoot/hochgeladen", False), ("/api/komoot/sichtbarkeit", False)])
def test_viewer_get_liste(path, ok):
    from app import main
    assert bool(main.VIEWER_GET.match(path)) is ok
