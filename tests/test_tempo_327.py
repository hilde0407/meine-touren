"""3.27.0 – Geschwindigkeit bei vielen Touren: Neuland-Berechnung liefert dasselbe wie das bisherige Verfahren (und rechnet bei neuen Daten neu),
Startseite mit Versionsstempel (ETag/304, Programmdateien mit ?v= dürfen lange zwischengespeichert werden, ohne Stempel weiter nicht)."""
import math
import re
import sys
from math import cos, floor, radians
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401,E402
from app import db, extras, more2, routes  # noqa: E402


def _walk(seed, n=400, lat=48.0, lng=11.0):
    h, pts = seed * 1.3, []
    for i in range(n):
        h += math.sin(i / 17 + seed) * 0.12
        lat += math.cos(h) * 0.00015
        lng += math.sin(h) * 0.0002
        pts.append((lat, lng, 500.0, (1700000000 + i * 10) * 1000))
    return pts


def _reference(tours):
    """Das Verfahren vor 3.27.0 (Tupel-Zellen, Nachbarn bei jeder Prüfung)."""
    seen, res = set(), {}
    for t in tours:
        pts = [p for p in (routes.load(t["id"]) or []) if p and p[0] is not None]
        if len(pts) < 3:
            continue
        mine, total, new = set(), 0.0, 0.0
        for a, b in zip(pts, pts[1:]):
            d = extras._hav((a[0], a[1]), (b[0], b[1]))
            if d <= 0:
                continue
            n = max(1, int(d / 30)); seg = d / n
            for i in range(n):
                la, lo = a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n
                cy, cx = floor(la / 0.0004), floor(lo / (0.0004 / max(0.2, cos(radians(la)))))
                total += seg
                if not any((cy + dy, cx + dx) in seen for dy in (-1, 0, 1) for dx in (-1, 0, 1)):
                    new += seg
                mine.add((cy, cx))
        seen |= mine
        if total > 0:
            res[t["id"]] = {"new_km": round(new / 1000, 2), "km": round(total / 1000, 2), "pct": round(100 * new / total)}
    return res


def _mk(i, pts):
    ts = 1700000000 + i * 86400
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status,source) VALUES(?,?,?,?,?,?,?,?,?,?,?,'t','komoot')", (f"n{i}", f"N{i}", "hike", ts, ts + 4000, 5000, 4000, 10, 10, pts[0][0], pts[0][1], ))
    routes.store(f"n{i}", pts)


def test_neuland_wie_bisher_und_erneuert_sich():
    for i, (s, dl) in enumerate([(1, 0), (1, 0), (2, 0.0004), (3, 0.5), (1, 0.00005)]):          # gleiche Strecke zweimal, leicht versetzt, ganz woanders, fast gleich
        _mk(i, _walk(s, lat=48.0 + dl))
    got = more2.newground()["tours"]
    tours = db.query("SELECT id,start_ts,dist_m FROM tours WHERE start_ts IS NOT NULL ORDER BY start_ts")
    ref = _reference(tours)
    assert got == ref
    assert ref["n0"]["pct"] == 100 and ref["n1"]["pct"] == 0 and ref["n3"]["pct"] == 100          # erste Tour ganz neu, Wiederholung nicht, Tour weit weg wieder neu
    _mk(5, _walk(9, lat=49.0))                                                                      # neue Tour: Ergebnis wird neu berechnet (Zwischenspeicher veraltet nicht)
    assert more2.newground()["tours"]["n5"]["pct"] == 100


def test_startseite_stempel_etag_und_cache():
    from fastapi.testclient import TestClient
    from app import main
    with TestClient(main.app) as c:
        r = c.get("/")
        assert r.status_code == 200 and r.headers["cache-control"] == "no-cache" and "ETag" in r.headers and "content-security-policy" in r.headers
        refs = re.findall(r'(?:src|href)="((?:js|vendor)/[^"]+|style\.css[^"]*)"', r.text)
        assert len(refs) > 40 and all(re.search(r"\?v=[0-9a-f]{16}$", x) for x in refs if x.endswith((".js", ".css")) or "?v=" in x), refs[:3]
        assert r.text.count("?v=") == len(refs)
        assert c.get("/", headers={"If-None-Match": r.headers["ETag"]}).status_code == 304
        assert c.get("/index.html").text == r.text
        one = refs[0]
        a = c.get("/" + one)
        assert a.status_code == 200 and "immutable" in a.headers["cache-control"]
        b = c.get("/" + one.split("?")[0])
        assert b.status_code == 200 and b.headers["cache-control"] == "no-cache"                    # ohne Stempel prüft der Browser weiter bei jedem Aufruf
        assert c.get("/js/01-grundlagen.js?v=zzz").headers["cache-control"] == "no-cache"           # ungültiger Stempel: kein langes Zwischenspeichern
        assert "immutable" not in c.get("/api/version").headers.get("cache-control", "")
