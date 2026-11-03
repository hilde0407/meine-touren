"""Automatische Fotoauswahl: Sterne (XMP), Schärfe, Verteilung."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tests.test_core import fresh  # noqa: F401


def _img(path, sharp=True, seed=0):
    from PIL import Image, ImageDraw, ImageFilter
    im = Image.new("RGB", (640, 480), "white")
    d = ImageDraw.Draw(im)
    for i in range(0, 640, 16):
        d.rectangle([i, 0, i + 8, 480], fill=(30 + seed * 7 % 200, 60, 90))
    if not sharp:
        im = im.filter(ImageFilter.GaussianBlur(9))
    im.save(path, "JPEG", quality=92)


def test_rating_sharpness_and_best_selection():
    from app import db, config, photos
    config.LIB_DIR.mkdir(parents=True, exist_ok=True)
    base = 1700000000
    db.execute("INSERT INTO tours(id,name,sport,start_ts,end_ts,dist_m,dur_s,up_m,down_m,lat,lng,status) VALUES('t1','Runde','hike',?,?,8000,7200,300,300,50.1,8.0,'x')", (base, base + 7200))
    rows = []
    for i in range(12):
        p = config.LIB_DIR / f"b{i}.jpg"
        _img(p, sharp=(i != 3), seed=i)           # Foto 3 ist unscharf
        if i == 7:
            (config.LIB_DIR / "b7.xmp").write_text('<x:xmpmeta><rdf:Description xmp:Rating="5"/></x:xmpmeta>')
        if i == 5:
            (config.LIB_DIR / "b5.xmp").write_text('<x:xmpmeta><rdf:Description xmp:Rating="-1"/></x:xmpmeta>')
        rows.append((str(p), p.stat().st_mtime, p.stat().st_size, base + 600 * i, None, None))
    photos._store(rows); photos.assign_all()
    assert photos.read_rating(str(config.LIB_DIR / "b7.jpg")) == 5
    assert photos.read_rating(str(config.LIB_DIR / "b0.jpg")) is None
    assert photos.sharpness(str(config.LIB_DIR / "b0.jpg")) > 3 * photos.sharpness(str(config.LIB_DIR / "b3.jpg"))
    best, total = photos.best_of_tour("t1", 4)
    ids = {p["id"]: p for p in best}
    paths = {r["id"]: Path(r["path"]).name for r in db.query("SELECT id,path FROM photos")}
    names = [paths[i] for i in ids]
    assert total == 12 and len(best) == 4
    assert "b7.jpg" in names and "b5.jpg" not in names and "b3.jpg" not in names
    ts = [p["taken_ts"] for p in best]
    assert ts == sorted(ts) and max(ts) - min(ts) > 3000          # über die Tour verteilt
    from app import more
    r = more.api_best_photos("t1", 6)
    assert len(r["photos"]) == 6 and r["rated"] >= 1
