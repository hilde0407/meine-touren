"""Android-Hülle: Aufzeichnungslogik (reines Java) und Server-Endpunkt für hochgeladene Aufzeichnungen."""
import shutil
import subprocess
import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.skipif(not shutil.which("javac"), reason="kein JDK")
def test_trackstore_java(tmp_path):
    src = ROOT / "android/app/src/main/java/de/meinetouren/app/TrackStore.java"
    subprocess.run(["javac", "-d", str(tmp_path), str(src), str(ROOT / "tests/android/TrackStoreCheck.java")], check=True)
    r = subprocess.run(["java", "-cp", str(tmp_path), "TrackStoreCheck"], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr


@pytest.mark.skipif(not shutil.which("javac"), reason="kein JDK")
def test_guide_java(tmp_path):
    """Wegführung: Abbiegungen erkennen, Ansagen, Abkommen und Rückkehr, Rundweg, Rauschen."""
    d = ROOT / "android/app/src/main/java/de/meinetouren/app"
    subprocess.run(["javac", "-d", str(tmp_path), str(d / "GuideText.java"), str(d / "Guide.java"), str(ROOT / "tests/android/GuideCheck.java"),
                    str(ROOT / "tests/android/GuideTextCheck.java")], check=True)
    for k in ("GuideCheck", "GuideTextCheck"):
        r = subprocess.run(["java", "-cp", str(tmp_path), k], capture_output=True, text=True, cwd=tmp_path)
        assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr


@pytest.mark.skipif(not shutil.which("javac"), reason="kein JDK")
def test_deviceinfo_java(tmp_path):
    """3.49.0 – Geräteangaben der App (reines Java): gültiges JSON, Bereinigung, Längen, Kennung."""
    d = ROOT / "android/app/src/main/java/de/meinetouren/app"
    subprocess.run(["javac", "-d", str(tmp_path), str(d / "DeviceInfo.java"), str(ROOT / "tests/android/DeviceInfoCheck.java")], check=True)
    r = subprocess.run(["java", "-cp", str(tmp_path), "de.meinetouren.app.DeviceInfoCheck"], capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0 and "OK" in r.stdout, r.stdout + r.stderr


def test_bridge_device_info_wired():
    """3.49.0 – Brücke: deviceInfo() und die echte App-Version (kein fest eingetragener Stand); die Kennung ist eine zufällige UUID, keine Hardware-Kennung."""
    import re
    d = ROOT / "android/app/src/main/java/de/meinetouren/app"
    ma = (d / "MainActivity.java").read_text(encoding="utf8")
    assert "public String deviceInfo()" in ma and "DeviceInfo.json(installId(), Build.MANUFACTURER, Build.MODEL, Build.VERSION.RELEASE, appVersion())" in ma
    assert "getPackageInfo(getPackageName(), 0).versionName" in ma and "BuildConfig" not in ma
    assert 'public String version() { return appVersion(); }' in ma and 'o.put("version", appVersion())' in ma
    assert not re.search(r'"\d+\.\d+\.\d+"', ma) and not re.search(r'MeineTourenApp/\d', ma), "fest eingetragene Versionsnummer"
    assert "UUID.randomUUID()" in ma and '"install_id"' in ma
    for verboten in ("ANDROID_ID", "getImei", "getDeviceId", "getSerial", "Build.SERIAL", "getMacAddress", "AdvertisingId"):
        for f in d.glob("*.java"):
            assert verboten not in f.read_text(encoding="utf8"), (verboten, f.name)
    wf = (ROOT / ".github/workflows/android.yml").read_text(encoding="utf8")
    assert "DeviceInfoCheck" in wf                                     # die Prüfung läuft auch vor dem APK-Bau


def _gpx():
    pts = "".join(f'<trkpt lat="{47+i*0.0005}" lon="11.0"><ele>{1000+i*3}</ele><time>2026-07-01T08:{i//60:02d}:{i%60:02d}Z</time></trkpt>' for i in range(60))
    return f'<?xml version="1.0"?><gpx version="1.1"><trk><name>x</name><type>skitour</type><trkseg>{pts}</trkseg></trk></gpx>'


def test_record_upload():
    from fastapi.testclient import TestClient
    from app import main, db
    c = TestClient(main.app)
    r = c.post("/api/record/upload", json={"gpx": _gpx(), "name": "Morgenrunde", "sport": "skitour"})
    assert r.status_code == 200 and not r.json()["dup"]
    tid = r.json()["id"]
    t = db.one("SELECT name,sport FROM tours WHERE id=?", (tid,))
    assert t["name"] == "Morgenrunde" and t["sport"] == "skitour"
    assert c.post("/api/record/upload", json={"gpx": _gpx(), "name": "nochmal"}).json()["dup"] is True
    assert c.post("/api/record/upload", json={"gpx": "<gpx/>"}).status_code == 400


def test_record_upload_notifies(monkeypatch):
    from fastapi.testclient import TestClient
    from app import main, db, more2
    sent = []
    monkeypatch.setattr(more2, "notify_send", lambda t, title="x": sent.append((t, title)))
    c = TestClient(main.app)
    db.put("notify_url", "")
    c.post("/api/record/upload", json={"gpx": _gpx().replace("2026-07-01", "2026-07-02"), "name": "A"})
    import time; time.sleep(0.2)
    assert sent == []                                                  # ohne Webhook keine Meldung
    db.put("notify_url", "https://ntfy.sh/test")
    c.post("/api/record/upload", json={"gpx": _gpx().replace("2026-07-01", "2026-07-03"), "name": "Abendrunde"})
    time.sleep(0.3)
    assert len(sent) == 1 and "Abendrunde" in sent[0][0]
    db.put("notify_events", "0")
    c.post("/api/record/upload", json={"gpx": _gpx().replace("2026-07-01", "2026-07-04"), "name": "B"})
    time.sleep(0.3)
    assert len(sent) == 1                                              # abgeschaltet


def test_offline_cache_wired():
    """Offline-Speicher der App: Klasse vorhanden, im WebViewClient eingehängt, Anmelde-/Live-Pfade ausgenommen."""
    d = ROOT / "android/app/src/main/java/de/meinetouren/app"
    oc = (d / "OfflineCache.java").read_text(encoding="utf8")
    ma = (d / "MainActivity.java").read_text(encoding="utf8")
    assert "shouldInterceptRequest" in ma and "OfflineCache.serve" in ma and "OfflineCache.wanted" in ma
    for pfad in ("login", "logout", "live", "backup", "photo/"):
        assert pfad in oc.split("SKIP", 1)[1].split(";", 1)[0], pfad
    assert "offlineServed" in ma and "clearOffline" in ma


def test_record_upload_waypoints():
    """Wegpunkte aus der App-GPX werden mit der Tour gespeichert, lassen sich ändern und löschen."""
    from fastapi.testclient import TestClient
    from app import main, db
    c = TestClient(main.app)
    wpt = ('<wpt lat="47.0100" lon="11.0"><time>2026-07-01T08:10:00Z</time><name>Rast am Bach</name></wpt>'
           '<wpt lat="47.0200" lon="11.0"><time>2026-07-01T08:20:00Z</time><name>Wegpunkt</name></wpt>')
    g = _gpx().replace("<trk>", wpt + "<trk>", 1).replace("2026-07-01", "2026-07-02")
    r = c.post("/api/record/upload", json={"gpx": g, "name": "Mit Wegpunkten"})
    assert r.status_code == 200
    tid = r.json()["id"]
    w = c.get(f"/api/tours/{tid}/wps").json()
    assert [x["note"] for x in w] == ["Rast am Bach", "Wegpunkt"] and w[0]["ts"] < w[1]["ts"] and abs(w[0]["lat"] - 47.01) < 1e-6
    assert c.put(f"/api/tours/{tid}/wps/{w[0]['id']}", json={"note": "  Pause   am Wasser "}).json()["ok"]
    assert c.get(f"/api/tours/{tid}/wps").json()[0]["note"] == "Pause am Wasser"
    assert c.put(f"/api/tours/{tid}/wps/99999", json={"note": "x"}).status_code == 404
    c.delete(f"/api/tours/{tid}/wps/{w[1]['id']}")
    assert len(c.get(f"/api/tours/{tid}/wps").json()) == 1
    # Tour ohne Wegpunkte: leere Liste
    assert c.get("/api/tours/gibtsnicht/wps").json() == []


def test_photo_comments_api():
    """Kommentare zu Fotos: anlegen, je Tour auflisten, löschen; leere Texte werden abgelehnt; mit dem Foto verschwinden sie."""
    from fastapi.testclient import TestClient
    from app import main, db, photos
    c = TestClient(main.app)
    db.execute("INSERT INTO photos(path,taken_ts,tour_id) VALUES('/x/kommentar.jpg',1,'kt1')")
    pid = db.one("SELECT id FROM photos WHERE path='/x/kommentar.jpg'")["id"]
    assert c.post(f"/api/photos/{pid}/comments", json={"text": "   "}).status_code == 400
    assert c.post("/api/photos/987654/comments", json={"text": "x"}).status_code == 404
    r = c.post(f"/api/photos/{pid}/comments", json={"text": "Schöner Blick!"})
    assert r.status_code == 200 and r.json()["text"] == "Schöner Blick!"
    c.post(f"/api/photos/{pid}/comments", json={"text": "Zweiter"})
    m = c.get("/api/tours/kt1/comments").json()
    assert [x["text"] for x in m[str(pid)]] == ["Schöner Blick!", "Zweiter"]
    assert len(c.get(f"/api/photos/{pid}/comments").json()) == 2
    c.delete(f"/api/comments/{r.json()['id']}")
    assert [x["text"] for x in c.get("/api/tours/kt1/comments").json()[str(pid)]] == ["Zweiter"]
    photos.delete_photos([pid])
    assert c.get("/api/tours/kt1/comments").json() == {}


def test_story_place_name(monkeypatch):
    """Ortsname zu einer Koordinate für die Erzählung; Fehler ergeben einen leeren Namen statt eines Absturzes."""
    from fastapi.testclient import TestClient
    from app import main, extras
    c = TestClient(main.app)
    monkeypatch.setattr(extras, "place_name", lambda la, ln: "Garmisch")
    assert c.get("/api/place?lat=47.5&lng=11.1").json() == {"name": "Garmisch"}
    monkeypatch.setattr(extras, "place_name", lambda la, ln: (_ for _ in ()).throw(RuntimeError("offline")))
    assert c.get("/api/place?lat=47.5&lng=11.1").json() == {"name": None}
    assert c.get("/api/place?lat=95&lng=11.1").status_code == 400


def test_public_slideshow_comments():
    """Geteilte Diashow: Kommentare nur, wenn beim Teilen erlaubt; Gäste dürfen schreiben (Rate-Limit), Besitzer sieht sie in der Erzählung."""
    from fastapi.testclient import TestClient
    from app import main, db
    c = TestClient(main.app)
    db.execute("INSERT INTO photos(path,taken_ts,tour_id,manual) VALUES('/x/gast.jpg',1,'gt1',0)")
    pid = db.one("SELECT id FROM photos WHERE path='/x/gast.jpg'")["id"]
    db.execute("INSERT OR IGNORE INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES('gt1','Gast','hike',1,2,1000,60,0,0,48,8,'tour_recorded','komoot')")
    off = c.post("/api/tours/gt1/share", json={"show": True}).json()["token"]
    assert c.get(f"/api/public/{off}/comments").json()["enabled"] is False
    assert c.post(f"/api/public/{off}/comments", json={"photo_id": pid, "text": "x"}).status_code == 403
    tok = c.post("/api/tours/gt1/share", json={"show": True, "comments": True}).json()["token"]
    assert c.get(f"/api/public/{tok}/comments").json()["enabled"] is True
    r = c.post(f"/api/public/{tok}/comments", json={"photo_id": pid, "author": "Anna", "text": "  Toll <b>!</b> "})
    assert r.status_code == 200 and r.json()["author"] == "Anna (Gast)"
    assert c.post(f"/api/public/{tok}/comments", json={"photo_id": pid, "text": " "}).status_code == 400
    assert c.post(f"/api/public/{tok}/comments", json={"photo_id": 424242, "text": "x"}).status_code == 404
    got = c.get(f"/api/public/{tok}/comments").json()["comments"][str(pid)]
    assert got[0]["text"] == "Toll <b>!</b>" and got[0]["author"] == "Anna (Gast)"
    assert [x["text"] for x in c.get("/api/tours/gt1/comments").json()[str(pid)]] == ["Toll <b>!</b>"]
    for _ in range(6):
        last = c.post(f"/api/public/{tok}/comments", json={"photo_id": pid, "text": "spam"})
    assert last.status_code == 429
    assert c.get("/api/tours/gt1/shares").json()[0]["comments"] in (0, 1)


def test_trip_names_month_added_once():
    """Mehrere Reisen mit gleichem Namen und Monat: der Monat wird nur einmal angehängt (nicht pro doppeltem Namen erneut)."""
    from app import more2
    trips, by = [], {}
    for i, reg in enumerate(["Andalusien", "Andalusien", "Hessen", "Hessen", "Bayern", "Bayern"]):
        trips.append({"id": f"r{i}", "region": reg, "days": 5, "start": "2019-06-0%d" % (i + 1), "tours": [f"r{i}"]})
        by[f"r{i}"] = {"g_place": None, "g_county": None}
    more2._unique_names(trips, by)
    assert [t["region"] for t in trips] == ["Andalusien (Juni 2019)"] * 2 + ["Hessen (Juni 2019)"] * 2 + ["Bayern (Juni 2019)"] * 2


def test_manual_home_place(monkeypatch):
    """Heimatort aus der Verwaltung ersetzt die automatische Erkennung; die Ortssuche liefert Name und Koordinaten."""
    from fastapi.testclient import TestClient
    from app import main, more2, db
    c = TestClient(main.app)
    tours = [{"lat": 48.0 + i * 0.01, "lng": 11.0, "start_ts": 1_700_000_000 + i * 86400 * 40} for i in range(20)]
    c.post("/api/settings", json={"home_name": "", "home_lat": "", "home_lng": ""})
    auto = more2.home_places(tours)
    c.post("/api/settings", json={"home_name": "Hamburg", "home_lat": "53.55", "home_lng": "10.0"})
    assert more2.home_places(tours) == [(53.55, 10.0)] != auto
    s = c.get("/api/settings").json()
    assert s["home_name"] == "Hamburg" and s["home_lat"] == "53.55"
    c.post("/api/settings", json={"home_lat": "abc"})
    assert more2.home_places(tours) == auto            # ungültige Eingabe: zurück zur Erkennung
    c.post("/api/settings", json={"home_name": "", "home_lat": "", "home_lng": ""})

    class R:
        status_code = 200
        def json(self): return [{"display_name": "Garmisch-Partenkirchen, Bayern, Deutschland", "lat": "47.49", "lon": "11.09"}]
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: R())
    r = c.get("/api/geo/search?q=Garmisch").json()
    assert r[0]["lat"] == 47.49 and r[0]["name"].startswith("Garmisch")
    assert c.get("/api/geo/search?q=a").status_code == 400


# ---------------------------------------------------------------------------------------------- 3.49.0: die App als Aufzeichnungsgerät
IID = "5b0e7a52-3c1d-4b8e-9f10-2a6c7d8e9f01"
IID2 = "9a1b2c3d-4e5f-4a6b-8c7d-0e1f2a3b4c5d"


def _dev(iid=IID, **kw):
    return dict({"install_id": iid, "hersteller": "google", "modell": "Pixel 8", "android": "14", "app_version": "3.49.0"}, **kw)


def _up(c, day, device=None, name="Runde", **kw):
    body = dict({"gpx": _gpx().replace("2026-07-01", f"2026-07-{day:02d}").replace('<gpx version="1.1">', '<gpx version="1.1" creator="Meine Touren (Android)">'), "name": name}, **kw)
    if device is not None:
        body["device"] = device
    r = c.post("/api/record/upload", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def test_app_device_registered_and_recognised():
    """Erster Upload mit Geräteangaben legt das Handy als Gerät „phone“ an; der zweite findet es wieder, aktualisiert Version und „zuletzt gesehen“."""
    from fastapi.testclient import TestClient
    from app import main, db, mydevices
    c = TestClient(main.app)
    assert c.post("/api/my-devices/app", json={"device": _dev()}).json() == {"known": False}          # Nachfragen legt nichts an
    assert db.query("SELECT 1 FROM devices") == []
    a = _up(c, 1, _dev())
    assert a["device"]["new"] is True and a["device"]["name"] == "Meine Touren App · Pixel 8"
    d = db.one("SELECT * FROM devices")
    assert d["kind"] == "phone" and d["model"] == "Google Pixel 8" and d["app_id"] == IID and d["app_version"] == "3.49.0" and d["app_android"] == "14" and d["active"] == 1
    assert d["app_since"] and d["last_seen"] == d["app_since"]
    db.execute("UPDATE devices SET last_seen=1, app_since=1 WHERE id=?", (d["id"],))
    b = _up(c, 2, _dev(iid=IID.upper(), app_version="3.50.1", android="15"))                        # Kennung in Großbuchstaben: dasselbe Gerät
    assert b["device"] == {"id": d["id"], "name": d["name"], "new": False}
    d2 = db.one("SELECT * FROM devices")
    assert len(db.query("SELECT 1 FROM devices")) == 1 and d2["app_version"] == "3.50.1" and d2["app_android"] == "15" and d2["last_seen"] > 1 and d2["app_since"] == 1
    # Tour gehört dem Gerät (nicht „von Hand“), Quelle = Handy mit Gerätenamen
    dv = mydevices.device_of(b["id"])
    assert dv["id"] == d["id"] and dv["manual"] is False and dv["app"] is True
    assert db.one("SELECT src,name FROM tour_source WHERE tour_id=?", (b["id"],)) == {"src": "phone", "name": "Meine Touren App · Pixel 8"}
    assert c.get(f"/api/tours/{b['id']}/metrics").json()["device"]["name"] == "Meine Touren App · Pixel 8"
    assert [t["dev"] for t in c.get("/api/tours").json()] == ["Meine Touren App · Pixel 8"] * 2
    lst = c.get("/api/my-devices").json()["devices"]
    assert len(lst) == 1 and lst[0]["n"] == 2 and lst[0]["app"]["version"] == "3.50.1" and lst[0]["app"]["android"] == "15" and lst[0]["app"]["last_rec"]
    assert IID not in c.get("/api/my-devices").text and IID not in c.get("/api/devices").text         # die Kennung verlässt den Server nicht
    k = c.post("/api/my-devices/app", json={"device": _dev()}).json()
    assert k["known"] is True and k["name"] == d["name"] and k["since"] == 1
    # doppelter Upload: nichts wird angelegt oder umgeschrieben
    again = c.post("/api/record/upload", json={"gpx": _gpx().replace("2026-07-01", "2026-07-02"), "device": _dev(iid=IID2)}).json()
    assert again["dup"] is True and len(db.query("SELECT 1 FROM devices")) == 1


def test_app_device_rename_stays_and_two_phones():
    """Umbenennen bleibt bei späteren Uploads erhalten; ein zweites Handy ist ein zweites Gerät (gleiches Modell: eindeutiger Name)."""
    from fastapi.testclient import TestClient
    from app import main, db, mydevices
    c = TestClient(main.app)
    a = _up(c, 1, _dev())
    did = a["device"]["id"]
    assert c.patch(f"/api/devices/{did}", json={"name": "Volkers Pixel", "model": "Pixel 8 (privat)", "note": "immer dabei"}).status_code == 200
    b = _up(c, 2, _dev(app_version="3.49.1"))
    assert b["device"] == {"id": did, "name": "Volkers Pixel", "new": False}
    d = db.one("SELECT * FROM devices WHERE id=?", (did,))
    assert d["name"] == "Volkers Pixel" and d["model"] == "Pixel 8 (privat)" and d["note"] == "immer dabei" and d["app_version"] == "3.49.1"
    assert db.one("SELECT name FROM tour_source WHERE tour_id=?", (b["id"],))["name"] == "Volkers Pixel"
    e = _up(c, 3, _dev(iid=IID2))                                       # zweites Handy, gleiches Modell
    assert e["device"]["new"] is True and e["device"]["id"] != did and e["device"]["name"] == "Meine Touren App · Pixel 8"
    f = _up(c, 4, _dev(iid="11111111-2222-4333-8444-555555555555"))
    assert f["device"]["name"] == "Meine Touren App · Pixel 8 (2)"
    asg = mydevices.assignments()
    assert asg[a["id"]][0]["id"] == did and asg[b["id"]][0]["id"] == did and asg[e["id"]][0]["id"] == e["device"]["id"] and asg[f["id"]][0]["id"] == f["device"]["id"]
    assert sorted(x["n"] for x in c.get("/api/my-devices").json()["devices"]) == [1, 1, 2]
    # Gerät löschen: Touren müssen umgehängt werden; danach meldet sich dasselbe Handy beim nächsten Upload neu an
    assert c.delete(f"/api/devices/{did}").status_code == 409
    assert c.delete(f"/api/devices/{did}?move_to={e['device']['id']}").json()["moved"] == 2
    g = _up(c, 5, _dev())
    assert g["device"]["new"] is True and mydevices.assignments()[a["id"]][0]["id"] == e["device"]["id"]      # ausdrückliche Zuordnung der alten Touren bleibt


def test_app_device_invalid_or_missing_info():
    """Alter Client ohne Angaben, ungültige und überlange Angaben: Der Upload gelingt immer; ein Gerät entsteht nur bei gültiger Kennung, Texte werden bereinigt und gekürzt."""
    from fastapi.testclient import TestClient
    from app import main, db, mydevices
    c = TestClient(main.app)
    old = _up(c, 1)                                                     # alte APK: kein Feld „device“
    assert old.get("device") is None and db.query("SELECT 1 FROM devices") == []
    assert db.one("SELECT src,name FROM tour_source WHERE tour_id=?", (old["id"],)) == {"src": "phone", "name": "Handy"}      # wie bisher
    assert mydevices.device_of(old["id"]) is None
    bad = ["text", 5, [], {}, {"install_id": ""}, {"install_id": "abc"}, {"install_id": 12345}, {"install_id": None}, {"install_id": "x" * 5000},
           {"install_id": "00000000-0000-0000-0000-000000000000"}, {"install_id": IID + "'; DROP TABLE devices;--"}, {"install_id": ["a"]}, {"modell": "Pixel"}]
    for i, dev in enumerate(bad):
        r = _up(c, 2 + i, dev)
        assert r["dup"] is False and r["device"] is None, dev
    assert db.query("SELECT 1 FROM devices") == []
    assert c.post("/api/my-devices/app", json={"device": "x"}).json() == {"known": False} and c.post("/api/my-devices/app", json={}).json() == {"known": False}
    long = _up(c, 20, _dev(hersteller="<script>alert(1)</script>" + "H" * 500, modell="Mod\x00ell\n<b>" + "M" * 500, android="14; rm -rf /" + "9" * 300, app_version="3.49.0" + "0" * 300))
    d = db.one("SELECT * FROM devices WHERE id=?", (long["device"]["id"],))
    assert "<" not in d["name"] + d["model"] and "\x00" not in d["model"] and "\n" not in d["model"]
    assert len(d["name"]) <= 80 and len(d["model"]) <= 80 and len(d["app_android"]) <= 20 and d["app_version"] == "" and ";" not in d["app_android"]
    nn = _up(c, 21, _dev(iid=IID2, hersteller=None, modell=7, android=["x"], app_version={"a": 1}))
    d = db.one("SELECT * FROM devices WHERE id=?", (nn["device"]["id"],))
    assert d["name"] == "Meine Touren App · 7" and d["app_android"] == "" and d["app_version"] == ""
    assert mydevices.clean_app_info(_dev(hersteller="", modell=""))["model"] == "" and mydevices.clean_app_info(_dev(hersteller="samsung", modell="samsung SM-G991B"))["model"] == "samsung SM-G991B"


def test_app_device_does_not_disturb_automatic():
    """Das App-Gerät nimmt nicht an der Automatik nach Art/Datum teil: ältere Handy-Aufzeichnungen bleiben, wie sie sind; Uhr und Handy am selben Tag bleiben getrennt;
    eine ausdrückliche Wahl gewinnt und „Alle Handzuordnungen zurücksetzen“ nimmt dem App-Gerät nichts weg. Auf Wunsch übernimmt es die bisherigen Aufzeichnungen."""
    from fastapi.testclient import TestClient
    from app import main, db, mydevices
    c = TestClient(main.app)
    old = _up(c, 1)                                                     # frühere Handy-Aufzeichnung ohne Geräteangaben
    new = _up(c, 2, _dev())
    app_id = new["device"]["id"]
    assert mydevices.device_of(old["id"]) is None                       # keine Massen-Umschreibung
    assert c.get("/api/my-devices").json()["devices"][0]["app"]["orphans"] == 1
    sug = c.get("/api/devices/suggestions").json()
    assert [(s["kind"], s["n"]) for s in sug] == [("phone", 1)]          # die alte Aufzeichnung bleibt als „ohne Gerät“ sichtbar
    # Uhr am selben Tag wie die App-Aufzeichnung
    uhr = c.post("/api/devices", json={"name": "Balance", "kind": "zepp"}).json()["id"]
    ts = db.one("SELECT start_ts FROM tours WHERE id=?", (new["id"],))["start_ts"]
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
               (f"z{ts + 600}", "Uhr", "hike", ts + 600, ts + 4200, 5000, 3600, 100, 100, 47, 11, "tour_recorded", "local"))
    asg = mydevices.assignments()
    assert asg[f"z{ts + 600}"][0]["id"] == uhr and asg[new["id"]][0]["id"] == app_id and asg[old["id"]][0] is None
    r = mydevices.match_summaries([{"trackid": ts, "dis": 1600, "run_time": 59, "source": "run.46.huami.com"}])       # Zepp-Training zur selben Zeit: Handy-Tour bleibt Handy
    assert r["skipped_other"] == 1 and db.one("SELECT src FROM tour_source WHERE tour_id=?", (new["id"],))["src"] == "phone"
    assert mydevices.device_of(new["id"])["id"] == app_id
    # ausdrückliche Wahl gewinnt; „automatisch“ führt zurück zum App-Gerät; Zurücksetzen aller Handzuordnungen ebenfalls
    assert c.post(f"/api/tours/{new['id']}/device", json={"device_id": uhr}).json()["device"]["id"] == uhr
    assert c.get("/api/devices/manual-check").json()["total"] == 1
    assert c.post("/api/devices/reset-manual", json={"mode": "all"}).json()["reset"] == 1
    dv = mydevices.device_of(new["id"])
    assert dv["id"] == app_id and dv["manual"] is False
    assert c.get("/api/devices/manual-check").json() == {"total": 0, "outside": 0, "by_device": {}, "redundant": 0}
    # ein von Hand angelegtes Handy-Gerät bekommt weiter die Aufzeichnungen ohne Angaben – nicht das App-Gerät
    hand = c.post("/api/devices", json={"name": "Altes Handy", "kind": "phone"}).json()["id"]
    assert mydevices.device_of(old["id"])["id"] == hand and mydevices.device_of(new["id"])["id"] == app_id
    c.delete(f"/api/devices/{hand}?move_to={uhr}")
    c.post(f"/api/tours/{old['id']}/device", json={"auto": True})
    assert mydevices.device_of(old["id"]) is None
    # „Bisherige Handy-Aufzeichnungen diesem Gerät zuordnen“
    assert c.post(f"/api/devices/{uhr}/adopt-phone", json={}).status_code == 400 and c.post("/api/devices/9999/adopt-phone", json={}).status_code == 404
    assert c.post(f"/api/devices/{app_id}/adopt-phone", json={"dry": True}).json() == {"ok": True, "n": 1} and mydevices.device_of(old["id"]) is None
    assert c.post(f"/api/devices/{app_id}/adopt-phone", json={}).json()["n"] == 1
    assert mydevices.device_of(old["id"])["id"] == app_id and mydevices.device_of(f"z{ts + 600}")["id"] == uhr
    assert c.post(f"/api/devices/{app_id}/adopt-phone", json={}).json()["n"] == 0
    # Tour löschen räumt die Kennung mit auf
    assert c.delete(f"/api/tours/{old['id']}").status_code == 200 and db.one("SELECT 1 FROM tour_app WHERE tour_id=?", (old["id"],)) is None


def test_app_device_migration_keeps_existing_devices(tmp_path, monkeypatch):
    """Bestehende Datenbank (Geräte-Tabelle ohne die neuen Spalten): Die Spalten kommen per ALTER TABLE dazu, vorhandene Geräte bleiben unverändert und sind keine App-Geräte."""
    import sqlite3
    from app import db, config
    db.close_all()
    con = sqlite3.connect(config.DB_PATH)
    con.execute("DROP TABLE devices")
    con.execute("DROP TABLE tour_app")
    con.execute("CREATE TABLE devices (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT, kind TEXT, model TEXT, since TEXT, until TEXT, active INTEGER DEFAULT 1, note TEXT)")
    con.execute("INSERT INTO devices(name,kind,model,since,until,active,note) VALUES('Altes Handy','phone','S10','2020-01-01','',1,'x')")
    con.commit(); con.close()
    db.init()
    d = db.one("SELECT * FROM devices")
    assert d["name"] == "Altes Handy" and d["kind"] == "phone" and d["since"] == "2020-01-01" and d["app_id"] is None and d["last_seen"] is None
    from fastapi.testclient import TestClient
    from app import main
    row = TestClient(main.app).get("/api/my-devices").json()["devices"][0]
    assert row["app"] is None and row["name"] == "Altes Handy"


def test_app_device_viewer_and_public():
    """Betrachter können weder hochladen noch ein Gerät anlegen oder abfragen; in öffentlichen Freigaben steht nichts vom Gerät (Kennung, Modell, Name)."""
    import json
    from fastapi.testclient import TestClient
    from app import main
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"})
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        body = {"gpx": _gpx(), "name": "Fremd", "device": _dev(iid=IID2)}
        assert v.post("/api/record/upload", json=body).status_code == 403
        assert v.post("/api/my-devices/app", json={"device": _dev()}).status_code == 403
        assert v.post("/api/devices/1/adopt-phone", json={}).status_code == 403
        anon = TestClient(main.app)
        assert anon.post("/api/record/upload", json=body).status_code == 401                 # ohne Anmeldung gar nicht
        t = _up(c, 3, _dev(modell="Geheimphone X"), name="Freigabe-Tour")
        devs = c.get("/api/my-devices").json()["devices"]
        assert len(devs) == 1 and devs[0]["model"] == "Google Geheimphone X" and devs[0]["n"] == 1      # nur der Upload des Besitzers hat ein Gerät angelegt
        assert IID not in v.get("/api/my-devices").text                                       # Betrachter sehen die Geräteliste des Besitzers (wie bisher), nie die Kennung
        tok = c.post(f"/api/tours/{t['id']}/share", json={"show": True}).json()["token"]
        tok2 = c.post(f"/api/tours/{t['id']}/share", json={}).json()["token"]
        for k in (tok, tok2):
            for url in (f"/api/public/{k}", f"/s/{k}", f"/api/public/{k}/comments"):
                res = anon.get(url)
                assert res.status_code == 200, (url, res.status_code)
                txt = res.text
                assert IID not in txt and "Geheimphone" not in txt and "Meine Touren App" not in txt and "app_version" not in txt, url
        assert IID not in json.dumps(c.get("/api/tours").json()) and IID not in c.get(f"/api/tours/{t['id']}/metrics").text
        assert IID not in c.get(f"/api/tours/{t['id']}/gpx").text and "Geheimphone" not in c.get(f"/api/tours/{t['id']}/gpx").text       # GPX-Export ohne Geräteangaben
