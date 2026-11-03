"""Demo-Modus: Beispieltouren und -fotos zum Ausprobieren, ohne eigene Daten und ohne Netzwerk.

Start:  MT_DEMO=1 (Umgebungsvariable) – oder  python -m app.demo [Port]   (Daten in einem temporären Ordner)
Beim Start werden Beispieldaten angelegt, wenn die Datenbank noch leer ist. Echte Daten werden nie angefasst oder ergänzt."""
import io
import math
import os
import sys
from datetime import datetime, timedelta, timezone

from . import config, db


def active():
    return os.environ.get("MT_DEMO") == "1"


# (Datum, Name, Breite, Länge, Radius, Punkte, Typ, Drehung, Sekunden je Punkt)
TOURS = [
    ("2025-03-08--09-10-00", "Frühlingsrunde Kandel", 48.06, 8.01, .02, 500, "hiking", 0, 9),
    ("2025-04-19--08-30-00", "Schauinsland Aufstieg", 47.92, 7.90, .03, 700, "hiking", 1, 10),
    ("2025-05-24--10-00-00", "Rheinradweg Etappe", 48.40, 7.85, .06, 900, "cycling", 2, 14),
    ("2025-06-14--07-45-00", "Feldberg Gipfeltour", 47.87, 8.00, .04, 800, "hiking", 3, 11),
    ("2025-07-05--09-00-00", "Schluchtensteig Teil 1", 47.80, 8.20, .05, 800, "hiking", 4, 12),
    ("2025-07-26--08-00-00", "Morgenlauf Dreisam", 47.99, 7.88, .012, 400, "running", 5, 5),
    ("2025-08-16--11-00-00", "Titisee Rundweg", 47.90, 8.15, .025, 600, "hiking", 6, 10),
    ("2025-09-06--09-30-00", "Kaiserstuhl Radrunde", 48.10, 7.65, .05, 900, "cycling", 7, 12),
    ("2025-09-27--08-45-00", "Belchen Überschreitung", 47.82, 7.83, .035, 800, "hiking", 8, 11),
    ("2025-10-11--10-15-00", "Herbstwanderung Münstertal", 47.85, 7.77, .03, 700, "hiking", 9, 11),
    ("2026-03-14--09-00-00", "Rosskopf Frühjahr", 48.03, 7.89, .025, 600, "hiking", 10, 10),
    ("2026-05-09--08-20-00", "Hotzenwald Runde", 47.65, 8.10, .04, 800, "hiking", 11, 11),
    ("2026-06-20--07-30-00", "Schwarzwald Radmarathon", 48.20, 8.20, .09, 1100, "cycling", 12, 13),
    ("2026-09-12--09-40-00", "Kandelhöhenweg", 48.07, 8.02, .03, 700, "hiking", 13, 11),
]


def _gpx(dt, lat, lon, r, n, typ, rot, spd):
    from .gpxtools import TZ
    t0 = datetime.strptime(dt, "%Y-%m-%d--%H-%M-%S").replace(tzinfo=TZ).astimezone(timezone.utc)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / (n - 1)
        rr = r * (1 + 0.35 * math.sin(3 * a + rot) + 0.15 * math.sin(5 * a))
        t = (t0 + timedelta(seconds=spd * i)).strftime("%Y-%m-%dT%H:%M:%SZ")
        pts.append(f'<trkpt lat="{lat + rr * math.sin(a + rot) * 0.6:.6f}" lon="{lon + rr * (1 - math.cos(a)) * 0.9:.6f}">'
                   f'<ele>{600 + 250 * math.sin(2 * a + rot) + 40 * math.sin(9 * a):.1f}</ele><time>{t}</time></trkpt>')
    return ('<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1"><trk><type>' + typ +
            "</type><trkseg>" + "".join(pts) + "</trkseg></trk></gpx>")


def _photo(i, label):
    from PIL import Image, ImageDraw
    w, h = 1200, 800
    im = Image.new("RGB", (w, h))
    dr = ImageDraw.Draw(im)
    top, bot = [(110, 170, 230), (240, 190, 110), (150, 200, 140), (200, 150, 200)][i % 4], (40 + 20 * (i % 3), 70, 60)
    for y in range(h):
        k = y / h
        dr.line([(0, y), (w, y)], fill=tuple(int(top[c] * (1 - k) + bot[c] * k) for c in range(3)))
    dr.polygon([(0, h), (w * .3, h * .55), (w * .55, h * .8), (w * .8, h * .5), (w, h)], fill=(30, 60, 50))
    dr.text((24, 20), label, fill=(255, 255, 255))
    b = io.BytesIO()
    im.save(b, "JPEG", quality=80)
    return b.getvalue()


def seed():
    """Beispieldaten anlegen, falls noch keine Tour vorhanden ist. Gibt die Zahl der angelegten Touren zurück."""
    from . import photos, routes, tracks
    from .gpxtools import TZ
    if db.one("SELECT 1 x FROM tours LIMIT 1"):
        return 0
    for dt, name, la, lo, r, n, typ, rot, spd in TOURS:
        tracks.adopt(_gpx(dt, la, lo, r, n, typ, rot, spd), name + ".gpx", name=name)
    # Fotos entlang einiger Touren (Zeit und Aufnahmeort stimmen mit der Strecke überein)
    lib = config.LIB_DIR / "demo"
    lib.mkdir(parents=True, exist_ok=True)
    k = 0
    for t in db.query("SELECT id,name,start_ts,end_ts FROM tours WHERE source='local' ORDER BY start_ts"):
        if t["name"] not in ("Feldberg Gipfeltour", "Kandelhöhenweg", "Titisee Rundweg"):
            continue
        pts = routes.load(t["id"]) or []
        if len(pts) < 10:
            continue
        for j in range(1, 6):
            fr = j / 6
            p = pts[int(fr * (len(pts) - 1))]
            ts = int(t["start_ts"] + (t["end_ts"] - t["start_ts"]) * fr)
            when = datetime.fromtimestamp(ts, TZ).strftime("%Y:%m:%d %H:%M:%S")
            data = photos.with_exif_time(_photo(k, f"Beispielfoto {k + 1} · {t['name']}"), when, p[0], p[1])
            (lib / f"demo_{k + 1:02d}.jpg").write_bytes(data)
            k += 1
    photos.scan()
    db.put("auto_sync", "0")
    db.put("update_check", "0")
    db.put("photo_only_tracked", "0")
    return len(TOURS)


def main(argv=None):
    import tempfile
    import threading
    import time
    import webbrowser
    argv = list(sys.argv[1:] if argv is None else argv)
    port = int(argv[0]) if argv and argv[0].isdigit() else 8090
    data = os.environ.get("DATA_DIR") or tempfile.mkdtemp(prefix="meine-touren-demo-")
    os.environ.update(MT_DEMO="1", DATA_DIR=data, MT_NO_SCHEDULER="1", PHOTOS_DIR=os.path.join(data, "quelle"),
                      BACKUP_DIR=os.path.join(data, "backups"))
    os.makedirs(os.environ["PHOTOS_DIR"], exist_ok=True)
    print(f"Demo-Modus: Beispieldaten in {data}\nMeine Touren läuft auf http://127.0.0.1:{port}  (Beenden: Strg+C)")
    threading.Thread(target=lambda: (time.sleep(2.5), webbrowser.open(f"http://127.0.0.1:{port}")), daemon=True).start()
    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
