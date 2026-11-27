"""3.60.1 – Statistik-Gruppen: kein Gruppenname wie eine Sportart (4 Sprachen, ohne Groß-/Kleinschreibung und Leerzeichen), bestehende Gruppen mit solchem Namen
bleiben und funktionieren weiter; Beschriftung „<Name> = A + B + …“ (Server: Jahresrückblick)."""
import json
import re
import sys
import time
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import config, db, gpxtools, stat_gruppen as sg  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
JS = ROOT / "app" / "static" / "js"
NOW = int(time.time())
BIKE4 = ["touringbicycle", "racebike", "mtb", "mtb_easy"]


def _client():
    from fastapi.testclient import TestClient
    from app import main
    return TestClient(main.app)


def _tour(tid, sport, km=10.0, tage=40):
    ts = NOW - tage * 86400
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
               (tid, f"Tour {tid}", sport, ts, ts + 3600, km * 1000, 3600, 100, 100, 48.0, 8.0, "tour_recorded"))


@pytest.mark.parametrize("name", ["Wandern", " wandern ", "WANDERN", "Hiking", "Randonnée", "Senderismo", "Kajak/Kanu", "kajak / kanu", "VTT", "Mountain bike",
                                  "Ski alpin", "Schneeschuh wandern", "Sonstiges", "Other"])
def test_name_wie_eine_aktivitaet_wird_abgelehnt(name):
    with pytest.raises(HTTPException) as e:
        sg.pruefen([{"name": name, "sports": ["hike", "mountaineering"]}], {"hike", "mountaineering"})
    assert e.value.status_code == 400 and "heißt schon eine Sportart" in e.value.detail and "Gruppe 1" in e.value.detail


@pytest.mark.parametrize("name", ["Rad fahren", "Ski (alle)", "Bergwandern", "Wandern und Bergsteigen", "Rad (alle)", "Wanderungen"])
def test_andere_namen_bleiben_erlaubt(name):
    assert sg.pruefen([{"name": name, "sports": ["hike", "mountaineering"]}], {"hike", "mountaineering"})[0]["name"] == name.strip()


def test_alle_29_namen_in_vier_sprachen_bekannt():
    n = sg.aktivitaetsnamen()
    assert all(sg._norm_name(x) in n for _, x, _, _ in gpxtools.CATALOG)
    for en in ("Walking", "Mountaineering", "Road bike", "Alpine skiing", "Snowshoe hiking", "Paragliding"):
        assert sg.namens_kollision(en), en
    assert not any(sg.namens_kollision(v["name"]) for v in sg.VORSCHLAEGE)               # die Vorschläge bleiben gültig
    # dieselbe Quelle wie die Oberfläche: jeder deutsche Name steht vierspaltig in 00-i18n-neu.js
    keys = {l.split(" || ")[0].strip() for l in (JS / "00-i18n-neu.js").read_text(encoding="utf-8").split("\n") if l.count(" || ") == 3}
    assert [x for _, x, _, _ in gpxtools.CATALOG if x not in keys] == []


def test_bestehende_gruppe_mit_aktivitaetsnamen_bleibt_und_zaehlt():
    _tour("w1", "hike", 10); _tour("b1", "mountaineering", 8, tage=41); _tour("r1", "touringbicycle", 30, tage=42)
    alt = [{"id": "wan", "name": "Wandern", "sports": ["hike", "mountaineering"]}, {"id": "rad", "name": "Rad fahren", "sports": BIKE4}]
    db.put(sg.KEY, json.dumps(alt))
    assert sg.load() == alt                                                                # nicht still umbenannt oder gelöscht
    assert sg.key("mountaineering") == "sgrp:wan" and sg.expand(["sgrp:wan"]) == {"hike", "mountaineering"}
    with _client() as c:
        assert c.get("/api/stats/gruppen").json()["gruppen"] == alt
        assert c.get("/api/bausteine/jahr", params={"zeitraum": "all", "sport": "sgrp:wan"}).json()["touren"] == 2
        r = c.put("/api/stats/gruppen", json={"gruppen": alt})                             # unverändert speichern verlangt einen anderen Namen
        assert r.status_code == 400 and "„Wandern“ heißt schon eine Sportart" in r.json()["detail"]
        assert json.loads(db.get(sg.KEY)) == alt                                             # nichts geändert
        alt[0]["name"] = "Wandern & Berg".replace("&", "und")
        assert c.put("/api/stats/gruppen", json={"gruppen": alt}).status_code == 200


def test_beschriftung_und_jahresrueckblick():
    from app import rueckblick
    gr = [{"id": "a", "name": "Berg", "sports": ["hike", "mountaineering"]}, {"id": "b", "name": "Rad fahren", "sports": BIKE4}]
    assert sg.label("sgrp:a", gr) == "Berg" and sg.titel("sgrp:a", gr) == "Berg = Wandern + Bergsteigen"      # 3.61.3: Anzeige nur der Name
    assert sg.label("sgrp:b", gr) == "Rad fahren" and sg.titel("sgrp:b", gr) == "Rad fahren = Radtour + Rennrad + Mountainbike + Gravelbike"
    assert sg.label("mtb", gr) == "Mountainbike" and sg.label("sgrp:weg", gr) == "sgrp:weg" and sg.name("sgrp:a", gr) == "Berg"
    _tour("w1", "hike", 10); _tour("m1", "mtb", 20, tage=41); _tour("x1", "kayak", 3, tage=42)
    sg.save(gr)
    ts = db.query("SELECT id,name,sport,start_ts,dist_m,dur_s,up_m FROM tours")
    rows = {s["sport"]: s for s in rueckblick._kennzahlen(ts, 2026, "")["sports"]}
    assert rows["sgrp:b"]["name"] == "Rad fahren" and rows["sgrp:b"]["gruppe"] == "Rad fahren"
    assert rows["sgrp:b"]["mitglieder"] == ["Radtour", "Rennrad", "Mountainbike", "Gravelbike"] and rows["kayak"] == {"sport": "kayak", "name": "Kajak / Kanu", "km": 3.0}


def test_oberflaeche_quelltext():
    g = (JS / "01-grundlagen.js").read_text(encoding="utf-8")
    assert "const sgLabel = k =>" in g and "const sgTitle = k =>" in g and "const sgNameClash = n =>" in g and "(zusammengefasst)" not in g
    assert "isSg(s) ? sgLabel(s)" in g                                                     # sName: überall dieselbe Beschriftung
    v = (JS / "05-verwaltung.js").read_text(encoding="utf-8")
    assert "Name wie eine Sportart – bitte umbenennen" in v and "sgNameClash(" in v
    i18n = (JS / "00-i18n-neu.js").read_text(encoding="utf-8")
    for k in ("Name wie eine Sportart – bitte umbenennen || ", "Statistik-Gruppe {}: „{}“ heißt schon eine Sportart – bitte einen anderen Gruppennamen wählen || "):
        assert k in i18n
    for f in ("56-statistik.js", "06-erweiterungen.js", "53-filter.js", "52-bausteine-uebersicht.js", "02-uebersicht.js"):
        src = (JS / f).read_text(encoding="utf-8")
        assert "sgTitle(" in src or "sportFilterHtml(" in src or "sportFilterOptions(" in src, f      # 3.61.0: Filter über sportFilterHtml (Tooltip aus sportAuswahl)


def test_version_texte_und_dateien():
    assert config.VERSION.startswith("3.61.5 · Meine Touren")
    notes = (ROOT / "docs" / "versionen" / "3.60.1.md").read_text(encoding="utf-8")
    assert notes.startswith("# 3.60.1") and "heißt schon eine Sportart" in notes and " = " in notes
    assert "3.60.1" in (ROOT / "docs" / "versionen" / "README.md").read_text(encoding="utf-8")
    assert "Version 3.60.1" in (ROOT / "docs" / "VERSIONSVERLAUF.md").read_text(encoding="utf-8")
    hb = (ROOT / "docs" / "HANDBUCH.md").read_text(encoding="utf-8")
    assert "(zusammengefasst)" not in hb and "Name = Sportart + Sportart" in hb
    assert 'const V = "mt-v149"' in (ROOT / "app" / "static" / "sw.js").read_text(encoding="utf-8")
    assert 'SL_APPV = "3.61.5"' in (JS / "54-ansichten.js").read_text(encoding="utf-8")
    assert re.search(r"Gruppenname.*Sportart", hb)


# ------------------------------------------------------------------------------------------------ Kartenfarben je Sportart (3.60.1)
def _lin(c):
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def _lum(h):
    r, g, b = map(_lin, _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _lab(h):
    r, g, b = map(_lin, _rgb(h))
    x, y, z = (0.4124 * r + 0.3576 * g + 0.1805 * b) / 0.95047, 0.2126 * r + 0.7152 * g + 0.0722 * b, (0.0193 * r + 0.1192 * g + 0.9505 * b) / 1.08883
    f = lambda t: t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116
    return 116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))


def test_eigene_kartenfarbe_je_sportart_deutlich_verschieden():
    import itertools
    import math
    css = (ROOT / "app" / "static" / "style.css").read_text(encoding="utf-8")
    col = dict(re.findall(r"--sp-(\w+):(#[0-9a-f]{6});", css))
    keys = [k for k, *_ in gpxtools.CATALOG]
    assert set(col) == set(keys) and len(set(col.values())) == 29                         # jede Sportart, keine doppelt
    bg = _lum("#f2efe9")                                                                    # heller Kartengrund
    low = [k for k in keys if (bg + 0.05) / (_lum(col[k]) + 0.05) < 3]
    assert low == [], low
    kat = {k: c for k, _, _, c in gpxtools.CATALOG}
    for (a, b) in itertools.combinations(keys, 2):
        d = math.dist(_lab(col[a]), _lab(col[b]))
        assert d >= (15 if kat[a] == kat[b] else 12), (a, b, round(d, 1))                  # z. B. Radtour, Mountainbike und E-Bike nicht mehr fast gleich
    g = (JS / "01-grundlagen.js").read_text(encoding="utf-8")
    assert 'cssv("--sp-" + k)' in g and "function sportAuswahl" in g and "const sportOrder" in g
    assert "function sportFilterHtml" in g and "sportAuswahl(keys, sel)" in g                    # 3.61.0: die gemeinsame Darstellung baut auf sportAuswahl auf
    for f, needle in (("02-uebersicht.js", "sportFilterHtml("), ("53-filter.js", "sportFilterHtml("), ("56-statistik.js", "sportOrder("), ("06-erweiterungen.js", "sportOrder("),
                      ("64-kartenseite.js", "sportOrder(")):
        assert needle in (JS / f).read_text(encoding="utf-8"), f
