"""3.36.0 – Layout-Server: Gruppen, Handy-Anordnung, Layoutcode (Validierung, Grenzen, Fehlerfälle, Rückwärtskompatibilität, Rechte)."""
import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _g(i="grpa1", ids=("jahr", "tag"), **kw):
    return {"id": i, "title": kw.pop("title", "Mein Abschnitt"), "ids": list(ids), **kw}


def _code(doc):
    return "MTA1." + base64.urlsafe_b64encode(json.dumps(doc).encode()).decode().rstrip("=")


def _export(layout, page="uebersicht", name="Test"):
    return {"format": "meine-touren-ansicht", "format_version": 1, "page": page, "name": name, "layouts": {page: layout}}


def test_old_layouts_stay_valid_and_groups_roundtrip():
    with _client() as c:
        old = {"order": ["tag", "jahr"], "hidden": ["zuletzt"], "w": {"tag": "halb"}}
        r = c.put("/api/layout/uebersicht", json=old)
        assert r.status_code == 200 and "groups" not in r.json()["layout"] and "mob" not in r.json()["layout"]
        doc = dict(old, widgets=[{"id": "wk1", "type": "periode", "cfg": {}}], groups=[_g("grpa1", ["jahr", "wk1"], closed=True), _g("grpb2", ["tag"], title="  Zweite   Gruppe ")],
                   mob={"order": ["wk1", "tag"], "hidden": ["jahr"]})
        r = c.put("/api/layout/uebersicht", json=doc)
        assert r.status_code == 200, r.text
        lay = c.get("/api/layout/uebersicht").json()["layout"]
        assert lay["groups"] == [{"id": "grpa1", "title": "Mein Abschnitt", "ids": ["jahr", "wk1"], "closed": True}, {"id": "grpb2", "title": "Zweite Gruppe", "ids": ["tag"]}]
        assert lay["mob"] == {"order": ["wk1", "tag"], "hidden": ["jahr"]}
        # leere Listen: nichts gespeichert; closed=false wird nicht gespeichert
        r = c.put("/api/layout/uebersicht", json={"groups": [_g(closed=False)], "mob": {}})
        assert r.json()["layout"]["groups"] == [{"id": "grpa1", "title": "Mein Abschnitt", "ids": ["jahr", "tag"]}] and "mob" not in r.json()["layout"]
        assert "groups" not in c.put("/api/layout/uebersicht", json={"groups": []}).json()["layout"]
        # leere Handy-Sichtbarkeit ist eine echte Aussage („nichts ausgeblendet“) und bleibt erhalten
        assert c.put("/api/layout/uebersicht", json={"mob": {"hidden": []}}).json()["layout"]["mob"] == {"hidden": []}
        # Ansichten-Behälter tragen Gruppen und Handy-Anordnung mit
        box = {"v": 2, "views": [{"id": "standard", "name": "Standard", "layout": {"v": 1}}, {"id": "v1", "name": "Gruppiert", "layout": {"groups": [_g()], "mob": {"order": ["tag"]}}}], "active": "standard"}
        assert c.put("/api/layout/uebersicht", json=box).status_code == 200
        got = c.get("/api/layout/uebersicht").json()["container"]["views"][1]["layout"]
        assert got["groups"][0]["ids"] == ["jahr", "tag"] and got["mob"] == {"order": ["tag"]}
        c.delete("/api/layout/uebersicht")


def test_group_validation_and_limits():
    with _client() as c:
        def put(doc, key="uebersicht"):
            return c.put("/api/layout/" + key, json=doc)

        w1 = [{"id": "wk1", "type": "periode", "cfg": {}}]
        bad = {
            "kein Liste": {"groups": {}}, "zu viele Gruppen": {"groups": [_g("grp%02d" % i, ["tag"]) for i in range(11)]},
            "Gruppe kein Objekt": {"groups": ["x"]}, "fremdes Feld": {"groups": [dict(_g(), extra=1)]},
            "Kennung ohne grp": {"groups": [_g("abc12")]}, "Kennung zu lang": {"groups": [_g("grp" + "a" * 13)]}, "Kennung Großbuchstaben": {"groups": [_g("grpAB")]},
            "doppelte Kennung": {"groups": [_g("grpa1", ["jahr"]), _g("grpa1", ["tag"])]},
            "Titel zu lang": {"groups": [_g(title="x" * 61)]}, "Titel mit Spitzklammer": {"groups": [_g(title="<b>")]}, "Titel Zahl": {"groups": [_g(title=5)]},
            "Titel Steuerzeichen": {"groups": [_g(title="a\nb")]},
            "ids fehlt": {"groups": [{"id": "grpa1"}]}, "ids leer": {"groups": [_g(ids=[])]}, "ids zu viele": {"groups": [_g(ids=["w%d" % i for i in range(31)])], "widgets": [{"id": "w%d" % i, "type": "periode", "cfg": {}} for i in range(31)]},
            "ids kein Text": {"groups": [_g(ids=[5])]}, "ids ungültig": {"groups": [_g(ids=["a b"])]},
            "Mitglied in zwei Gruppen": {"groups": [_g("grpa1", ["jahr"]), _g("grpb2", ["jahr", "tag"])]},
            "doppelt in einer Gruppe": {"groups": [_g(ids=["jahr", "jahr"])]},
            "Verschachtelung": {"groups": [_g("grpa1", ["jahr"]), _g("grpb2", ["grpa1"])]},
            "Mitglied unbekannt": {"groups": [_g(ids=["gibtsnicht"])]}, "Baustein unbekannt": {"groups": [_g(ids=["wxx"])], "widgets": w1},
            "closed kein Bool": {"groups": [_g(closed="ja")]},
        }
        for name, doc in bad.items():
            r = put(doc)
            assert r.status_code == 400, (name, r.status_code, r.text)
        assert c.get("/api/layout/uebersicht").json()["layout"] is None                     # nichts davon wurde gespeichert
        # Grenzen sind erreichbar: 10 Gruppen, 30 Mitglieder
        ok10 = {"groups": [_g("grp%02d" % i, [x]) for i, x in enumerate(["aufmacher", "jahr", "zepp", "zuletzt", "tag", "erinn"])]}
        assert put(ok10).status_code == 200
        ws = [{"id": "w%d" % i, "type": "periode", "cfg": {}} for i in range(30)]
        assert put({"widgets": ws, "groups": [_g(ids=[w["id"] for w in ws])]}).status_code == 200
        # Pflicht-Abschnitte lassen sich nicht gruppieren (Einstieg „sum“, Kopf „kopf“), Karte hat keine Gruppen
        assert put({"groups": [_g(ids=["map", "sum"])]}, "tour-haupt").status_code == 400
        assert put({"groups": [_g(ids=["kopf"])]}, "reise").status_code == 400 and put({"groups": [_g(ids=["kopf"])]}, "fotos").status_code == 400
        assert put({"groups": [_g(ids=["map", "prof"])]}, "tour-haupt").status_code == 200
        assert put({"groups": [_g(ids=["serien", "alben"])]}, "reisen").status_code == 200
        assert put({"groups": [_g(ids=["karte"])]}, "karte").status_code == 400 and put({"groups": []}, "karte").status_code == 200
        assert put({"groups": [_g(ids=["kpi", "ziele"])]}, "statistik").status_code == 200 and put({"groups": [_g(ids=["kpi"])]}, "uebersicht").status_code == 400
        # Dokument „tour-auswertung“: Bausteine liegen im Dokument „tour-haupt“, dort genügt eine gültige Kennung
        assert put({"groups": [_g(ids=["wx", "wabc12"])]}, "tour-auswertung").status_code == 200
        for k in ("uebersicht", "tour-haupt", "tour-auswertung", "reisen", "statistik", "karte"):
            c.delete("/api/layout/" + k)


def test_mobile_validation():
    with _client() as c:
        put = lambda d, k="uebersicht": c.put("/api/layout/" + k, json=d)  # noqa: E731
        for b in ({"mob": []}, {"mob": "x"}, {"mob": {"extra": []}}, {"mob": {"order": "tag"}}, {"mob": {"order": [1]}}, {"mob": {"hidden": ["a b"]}}, {"mob": {"order": ["x"] * 121}}):
            assert put(b).status_code == 400, b
        assert put({"mob": {"order": ["tag", "tag", "jahr"]}}).json()["layout"]["mob"] == {"order": ["tag", "jahr"]}       # doppelte Kennungen werden bereinigt
        assert put({"mob": {"order": ["map"]}}, "karte").status_code == 400
        assert put({"mob": {}}, "karte").status_code == 200
        c.delete("/api/layout/uebersicht")
        c.delete("/api/layout/karte")


def test_export_check_reports_groups_and_mob():
    with _client() as c:
        r = c.post("/api/layout/check", json=_export({"groups": [_g()], "mob": {"order": ["tag"]}}, name="Mit Gruppe")).json()
        assert r["ok"] and r["stats"]["uebersicht"]["groups"] == 1 and r["stats"]["uebersicht"]["mob"] is True
        assert r["layouts"]["uebersicht"]["groups"][0]["ids"] == ["jahr", "tag"]
        r = c.post("/api/layout/check", json=_export({"groups": [_g(ids=["jahr", "grpa1"])]})).json()
        assert not r["ok"] and "verschachteln" in " ".join(r["errors"])
        old = c.post("/api/layout/check", json=_export({"order": ["tag"]})).json()
        assert old["ok"] and old["stats"]["uebersicht"]["groups"] == 0 and old["stats"]["uebersicht"]["mob"] is False


def test_layout_code_check():
    with _client() as c:
        post = lambda body: c.post("/api/layout/code", json=body)  # noqa: E731
        doc = _export({"groups": [_g()], "mob": {"order": ["tag"]}, "widgets": [{"id": "wk1", "type": "periode", "cfg": {"title": "Ünïcode ✓"}}]}, name="Für Oma")
        r = post({"code": _code(doc)}).json()
        assert r["ok"] and r["name"] == "Für Oma" and r["page"] == "uebersicht" and r["layouts"]["uebersicht"]["widgets"][0]["cfg"]["title"] == "Ünïcode ✓"
        assert r["layouts"]["uebersicht"]["groups"][0]["id"] == "grpa1"
        # Link, Leerraum und Zeilenumbrüche im Code sind erlaubt; Padding auch
        code = _code(doc)
        assert post({"code": "  https://beispiel.example/app/#/layoutcode/" + code + "\n"}).json()["ok"]
        assert post({"code": code[:20] + "\n " + code[20:]}).json()["ok"]
        assert post({"code": code + "=="}).json()["ok"]
        fehler = {
            "fehlt": {}, "Zahl": {"code": 5}, "leer": {"code": ""}, "Vorsilbe fehlt": {"code": code[5:]}, "falsche Vorsilbe": {"code": "MTA2." + code[5:]}, "nur Vorsilbe": {"code": "MTA1."},
            "Sonderzeichen": {"code": "MTA1.abc$%&"}, "kein base64": {"code": "MTA1.A"}, "kein JSON": {"code": "MTA1." + base64.urlsafe_b64encode(b"hallo").decode()},
            "kein UTF-8": {"code": "MTA1." + base64.urlsafe_b64encode(b"\xff\xfe\xfa").decode()}, "JSON-Liste": {"code": _code([1, 2])},
            "andere Datei": {"code": _code({"format": "etwas-anderes"})}, "zu lang": {"code": "MTA1." + "A" * 100001},
            "neuere Version": {"code": _code(dict(doc, format_version=2))}, "ungültiges Layout": {"code": _code(_export({"groups": [_g(ids=["gibtsnicht"])]}))},
            "unbekannter Typ ist erlaubt aber Seite falsch": {"code": _code(dict(doc, page="gibtsnicht"))},
        }
        for name, body in fehler.items():
            r = post(body).json()
            assert r["ok"] is False and r["errors"] and r["layouts"] == {}, (name, r)
        # Größe: sehr lange Eingabe wird abgewiesen, ohne dass etwas gelesen wird
        assert post({"code": "MTA1." + "A" * 200000}).json()["ok"] is False
        assert c.post("/api/layout/code", content=b"{kaputt", headers={"Content-Type": "application/json"}).json()["ok"] is False
        # Ein Code speichert nichts und liefert keine Tourdaten
        assert c.get("/api/layout/uebersicht").json()["layout"] is None
        assert set(r) >= {"ok", "errors", "ignored", "name", "page", "layouts", "stats"} and "tours" not in json.dumps(post({"code": code}).json())


def test_layout_code_rights():
    from fastapi.testclient import TestClient
    from app import main
    with TestClient(main.app) as c:
        c.post("/api/setup", json={"name": "Max", "email": "max@example.com", "password": "geheim1234"})
        assert c.post("/api/users", json={"name": "Oma", "email": "oma@example.com", "password": "omas-pass12", "role": "viewer"}).status_code == 200
        code = _code(_export({"order": ["tag"]}))
        assert c.post("/api/layout/code", json={"code": code}).json()["ok"]
        v = TestClient(main.app)
        assert v.post("/api/login", json={"name": "oma", "password": "omas-pass12"}).status_code == 200
        assert v.post("/api/layout/code", json={"code": code}).status_code == 403
        assert v.put("/api/layout/uebersicht", json={"groups": [_g()]}).status_code == 403                  # Betrachter schreiben keine Gruppen
        assert TestClient(main.app).post("/api/layout/code", json={"code": code}).status_code == 401


def test_standard_sections_match_the_user_interface():
    """STD_IDS im Server = Registry der Oberfläche (49-seitenlayout.js, 62/63/64) – sonst ließen sich Gruppen mit gültigen Abschnitten ablehnen."""
    import re
    from app import layout
    js = ROOT / "app" / "static" / "js"
    src = {f: (js / f).read_text(encoding="utf-8") for f in ("49-seitenlayout.js", "62-reiseseiten.js", "63-fotoseiten.js", "64-kartenseite.js")}
    allsrc = "\n".join(src.values())

    def ids(block):
        return set(re.findall(r'\{id: "([a-z]+)"', block))

    reg = src["49-seitenlayout.js"]
    tour = ids(reg[reg.index("  tour: ["):reg.index("  uebersicht: [")])
    ueb = ids(reg[reg.index("  uebersicht: ["):reg.index("  statistik: [")])
    sta = ids(reg[reg.index("  statistik: ["):reg.index("/* 3.33.0 Reisen")])
    assert tour == layout.STD_IDS["tour-haupt"] == layout.STD_IDS["tour-auswertung"]
    assert ueb == layout.STD_IDS["uebersicht"] and sta == layout.STD_IDS["statistik"]
    for key, name in (("reise", "SL_REG.reise"), ("reisen", "SL_REG.reisen"), ("fotos", "SL_REG.fotos")):
        i = allsrc.index(name + " = [")
        assert ids(allsrc[i:allsrc.index("];", i)]) == layout.STD_IDS[key], key
    i = allsrc.index("SL_REG.karte = [")
    assert ids(allsrc[i:allsrc.index("];", i)]) and layout.STD_IDS["karte"] == frozenset()          # die Karte nimmt keine Gruppen an


def test_version_and_files_360():
    from app import config
    assert config.VERSION.startswith("3.55.1 · Meine Touren")
    html = (ROOT / "app" / "static" / "index.html").read_text(encoding="utf-8")
    assert html.index("js/65-zeitraum.js") < html.index("js/66-gruppen.js") < html.index("js/67-verlauf.js") < html.index("js/68-layoutcode.js") < html.index("js/39-sw.js")
    assert 'const V = "mt-v140"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    assert 'SL_APPV = "3.55.1"' in (ROOT / "app" / "static" / "js" / "54-ansichten.js").read_text(encoding="utf-8")
    notes = (ROOT / "docs" / "versionen" / "3.36.0.md").read_text(encoding="utf-8")
    assert notes.startswith("# 3.36.0") and "Rückgängig" in notes and "Gruppen" in notes and "Layoutcode" in notes and "Handy" in notes
    assert "3.36.0" in (ROOT / "docs" / "versionen" / "README.md").read_text(encoding="utf-8")
    assert (ROOT / "docs" / "VERSIONSVERLAUF.md").read_text(encoding="utf-8").index("## Version 3.36.0") < (ROOT / "docs" / "VERSIONSVERLAUF.md").read_text(encoding="utf-8").index("## Version 3.35.0")
    hb = (ROOT / "docs" / "HANDBUCH.md").read_text(encoding="utf-8")
    assert "Rückgängig" in hb and "Layoutcode" in hb and "Gruppe" in hb
