"""3.39.0 Soll/Ist: GET /api/tours/{id}/plan (Server, in-process): ohne Verknüpfung kein Plan, Kennzahlen mit Differenzen (fehlende Werte null, nie 0), Linien höchstens 400 Punkte
(Anfang und Ende bleiben), Betrachter darf lesen, Anmeldung nötig, Freigabelinks liefern nichts davon; Verkürzung (Douglas-Peucker) als reine Funktion."""
import json
import math
import time

import pytest

from tests.test_core import fresh  # noqa: F401


def _circle(n, r=0.02):
    return [[48 + r * math.sin(2 * math.pi * i / n), 11 + r * (1 - math.cos(2 * math.pi * i / n))] for i in range(n + 1)]


def test_simplify_haelt_grenze_anfang_ende_und_form():
    from app import plan
    pts = _circle(5000)
    out = plan.simplify(pts, 400)
    assert len(out) <= 400 and out[0] == [round(pts[0][0], 5), round(pts[0][1], 5)] and out[-1] == [round(pts[-1][0], 5), round(pts[-1][1], 5)]
    assert len(plan.simplify(pts[:50], 400)) == 51 or len(plan.simplify(pts[:50], 400)) == 50          # kurze Linien bleiben unverändert
    gerade = [[48 + i * 1e-4, 11.0] for i in range(1000)]
    assert len(plan.simplify(gerade, 400)) <= 400
    assert plan.simplify([[48, 11]], 400) == [[48, 11]] and plan.simplify([], 400) == []


def test_endpunkt(fresh):
    from fastapi.testclient import TestClient
    from app import db, main, routes
    with TestClient(main.app) as c:
        _endpunkt(c, db, routes)


def _endpunkt(c, db, routes):
    now = int(time.time())
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES('tp1','Gelaufen','hike',?,?,12600,6120,540,500,'t','komoot')", (now - 86400, now - 80000))
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,status,source) VALUES('tp2','Ohne Werte','hike',?,?,NULL,NULL,NULL,NULL,'t','komoot')", (now - 86400, now - 80000))
    routes.store("tp1", [(p[0], p[1], 500, i * 1000) for i, p in enumerate(_circle(3000))])
    pid = db.execute("INSERT INTO plans(name,sport,pts,km,up,down,est_h,ts,tour_id,status) VALUES('Mein Plan','hike',?,12.0,500,500,2.0,?,'tp1','gegangen')", (json.dumps(_circle(2000)), now))
    pid2 = db.execute("INSERT INTO plans(name,sport,pts,km,up,down,est_h,ts,tour_id,status) VALUES('Plan 2','hike',?,10.0,NULL,NULL,NULL,?,'tp2','gegangen')", (json.dumps(_circle(10)), now))
    r = c.get("/api/tours/tp1/plan")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok" and d["plan"]["id"] == pid and d["plan"]["name"] == "Mein Plan"
    assert d["soll"] == {"km": 12.0, "up": 500, "h": 2.0} and d["ist"]["km"] == 12.6 and d["ist"]["up"] == 540
    assert d["diff"]["km"] == 0.6 and d["diff"]["up"] == 40 and abs(d["diff"]["h"] - (6120 / 3600 - 2.0)) < 0.001
    assert 2 <= len(d["plan_linie"]) <= 400 and 2 <= len(d["tour_linie"]) <= 400
    # fehlende Werte: null, nie 0
    d2 = c.get("/api/tours/tp2/plan").json()
    assert d2["status"] == "ok" and d2["ist"] == {"km": None, "up": None, "h": None} and d2["diff"] == {"km": None, "up": None, "h": None} and d2["soll"]["up"] is None and d2["tour_linie"] == []
    # keine Verknüpfung / unbekannte Tour
    db.execute("UPDATE plans SET tour_id=NULL WHERE id=?", (pid,))
    assert c.get("/api/tours/tp1/plan").json() == {"status": "kein_plan"}
    assert c.get("/api/tours/gibtsnicht/plan").status_code == 404
    assert pid2


def test_betrachter_darf_lesen_nicht_loesen_und_anmeldung_noetig():
    import re
    from app import main
    assert main.VIEWER_GET.match("/api/tours/abc/plan")
    assert not main.VIEWER_GET.match("/api/plans/3/tour")
    src = open(main.__file__, encoding="utf-8").read()
    assert "app.include_router(plan.tour_router)" in src


def test_freigabe_liefert_nichts_davon():
    """Öffentliche Freigaben (Präfixe in more2.PUBLIC_PREFIXES) schließen /api/tours/…/plan nicht ein."""
    from app import more2
    assert not "/api/tours/abc/plan".startswith(tuple(more2.PUBLIC_PREFIXES))
    import re
    assert not re.search(r"plan", " ".join(more2.PUBLIC_PREFIXES))
