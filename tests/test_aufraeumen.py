"""Unbenutzte Fotos (ohne Tour) löschen."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import pytest
from tests.test_core import fresh  # noqa: F401


def test_delete_unused_photos_by_year_keeps_assigned():
    from PIL import Image
    from app import db, config, photos, more
    from fastapi import HTTPException
    config.LIB_DIR.mkdir(parents=True, exist_ok=True)
    base = 1700000000                    # Nov 2023
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES('t1','Runde','hike',?,?,8000,3600,300,300,50.1,8.0,'x')", (base, base + 3600))
    rows, files = [], []
    for i, ts in enumerate((base + 600, base + 86400 * 5, base + 86400 * 400, base + 86400 * 401)):   # 1 an Tour, 1 + 2 ohne Tour 2023/2024
        p = config.LIB_DIR / f"u{i}.jpg"; Image.new("RGB", (30, 20), "green").save(p); files.append(p)
        rows.append((str(p), p.stat().st_mtime, p.stat().st_size, ts, None, None))
    photos._store(rows); photos.assign_all()
    u = more.api_photos_unused()
    assert u["count"] == 3 and {y["y"] for y in u["years"]} == {2023, 2024}
    with pytest.raises(HTTPException):
        more.api_photos_unused_delete({})                       # ohne ausdrückliche Auswahl nichts löschen
    r = more.api_photos_unused_delete({"years": [2024]})
    assert r["deleted"] == 2
    assert not files[2].exists() and not files[3].exists() and files[0].exists() and files[1].exists()
    assert more.api_photos_unused()["count"] == 1
    assert db.one("SELECT COUNT(*) n FROM photo_deleted")["n"] == 2
