"""Ausrüstung (Kilometerstand, Standard-Zuordnung) und Jahreszeit der Wunschliste."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401
from tests.test_wiederholung import _loop


def _tours():
    from app import tracks, db
    for i, day in enumerate(("03-01", "05-10", "08-02")):
        tracks.adopt(_loop(day), f"g{i}.gpx", name=f"G{i}", ident=f"g{i}")
    db.execute("UPDATE tours SET sport='racebike' WHERE id IN ('g0','g1')")
    db.execute("UPDATE tours SET sport='hike' WHERE id='g2'")


def test_gear_auto_assignment_and_totals():
    from app import gear
    _tours()
    gid = gear.api_gear_save({"name": "Rennrad", "kind": "Rad", "sports": ["racebike"], "limit_km": 1})["id"]
    shoes = gear.api_gear_save({"name": "Schuhe", "kind": "Schuhe", "sports": ["hike"], "since": "2026-06-01"})["id"]
    g = {x["id"]: x for x in gear.api_gear()}
    assert g[gid]["n"] == 2 and g[gid]["km"] > 0 and g[gid]["status"] == "over"
    assert g[shoes]["n"] == 1
    # ausdrückliche Wahl hat Vorrang vor der Standard-Regel
    gear.api_tour_gear_set("g0", {"ids": [shoes]})
    g = {x["id"]: x for x in gear.api_gear()}
    assert g[gid]["n"] == 1 and g[shoes]["n"] == 2
    r = gear.api_tour_gear("g0")
    assert r["ids"] == [shoes] and r["auto"] is False
    gear.api_tour_gear_set("g1", {"ids": []})                     # ausdrücklich keine Ausrüstung
    assert gear.api_tour_gear("g1")["ids"] == []
    gear.api_tour_gear_set("g0", {"auto": True}); gear.api_tour_gear_set("g1", {"auto": True})
    g = {x["id"]: x for x in gear.api_gear()}
    assert g[gid]["n"] == 2
    gear.api_gear_delete(gid)
    assert [x["id"] for x in gear.api_gear()] == [shoes]


def test_gear_period_and_validation():
    from app import gear
    import pytest
    from fastapi import HTTPException
    _tours()
    old = gear.api_gear_save({"name": "Alt", "sports": ["racebike"], "until": "2026-04-01"})["id"]
    assert {x["id"]: x for x in gear.api_gear()}[old]["n"] == 1            # nur die Tour vom 1. März
    with pytest.raises(HTTPException):
        gear.api_gear_save({"name": "  "})


def test_wishlist_season():
    from app import db, more
    import json
    gid = db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES('B','T',?,5,100)", (json.dumps([[48, 8], [48.01, 8.01]]),))
    more.api_wishlist_set({"id": gid, "on": True, "season": "winter"})
    assert [x for x in more.api_wishlist() if x["id"] == gid][0]["season"] == "winter"
    more.api_wishlist_set({"id": gid, "season": "sommer"})
    assert [x for x in more.api_wishlist() if x["id"] == gid][0]["season"] == "sommer"
    more.api_wishlist_set({"id": gid, "on": False})
    assert [x for x in more.api_wishlist() if x["id"] == gid][0]["wish"] == 0
