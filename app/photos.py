"""Fotoindex (EXIF), Zuordnung zu Touren, Vorschaubilder."""
import hashlib
import os
import time
from datetime import datetime, timedelta, timezone

from PIL import Image, ImageOps

from . import config, db, jobs
from .gpxtools import TZ
from .jobs import log

EXTS = {".jpg", ".jpeg", ".png", ".webp"}
try:
    import pillow_heif  # optional
    pillow_heif.register_heif_opener()
    EXTS |= {".heic", ".heif"}
except Exception:  # noqa
    pass


def _gps(exif):
    try:
        g = exif.get_ifd(0x8825)
        if not g or 2 not in g or 4 not in g:
            return None, None
        f = lambda v: float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
        la, lo = f(g[2]), f(g[4])
        if g.get(1) == "S": la = -la
        if g.get(3) == "W": lo = -lo
        return la, lo
    except Exception:  # noqa
        return None, None


def read_meta(path):
    """(taken_ts_utc oder None, lat, lng)"""
    try:
        with Image.open(path) as im:
            ex = im.getexif()
            raw = None
            try:
                raw = ex.get_ifd(0x8769).get(36867) or ex.get_ifd(0x8769).get(36868)
            except Exception:  # noqa
                pass
            raw = raw or ex.get(306)
            lat, lng = _gps(ex)
            offs = ex.get_ifd(0x8769).get(36880) if raw else None
    except Exception:  # noqa
        return None, None, None
    return _raw_ts(raw, offs), lat, lng


def _raw_ts(raw, offs=None):
    ts = None
    if raw:
        try:
            d = datetime.strptime(str(raw).strip()[:19], "%Y:%m:%d %H:%M:%S")
            off_cfg = db.get("camera_utc_offset_h")
            if offs and len(str(offs)) >= 6:
                s = str(offs)
                sign = -1 if s[0] == "-" else 1
                d = d.replace(tzinfo=timezone(sign * timedelta(hours=int(s[1:3]), minutes=int(s[4:6]))))
            elif off_cfg not in ("", None):
                d = d.replace(tzinfo=timezone(timedelta(hours=float(off_cfg))))
            else:
                d = d.replace(tzinfo=TZ)
            ts = int(d.timestamp())
        except ValueError:
            pass
    return ts


def fingerprint(src):
    """64-Bit-dHash des Bildinhalts (Pfad oder Bytes) als Hex – gleiche Bilder in anderer Größe/Datei ergeben (fast) denselben Wert."""
    import io
    try:
        with Image.open(io.BytesIO(src) if isinstance(src, (bytes, bytearray)) else src) as im:
            try:
                im.draft("L", (128, 128))
            except Exception:  # noqa
                pass
            im = ImageOps.exif_transpose(im).convert("L").resize((9, 8), Image.BILINEAR)
        px = im.tobytes()
        bits = 0
        for y in range(8):
            for x in range(8):
                bits = (bits << 1) | (px[y * 9 + x] > px[y * 9 + x + 1])
        return "%016x" % bits
    except Exception:  # noqa
        return None


def similar(a, b, tol=6):
    return bool(a and b) and bin(int(a, 16) ^ int(b, 16)).count("1") <= tol


def find_duplicate(ts, fp, own_path=None):
    """Gibt den Pfad eines bereits vorhandenen Fotos mit gleicher Aufnahmezeit und gleichem Bildinhalt zurück."""
    if ts is None or not fp:
        return None
    for r in db.query("SELECT path,fp FROM photos WHERE taken_ts BETWEEN ? AND ? AND fp IS NOT NULL AND COALESCE(dated,1)=1", (ts - 2, ts + 2)):
        if r["path"] != own_path and similar(fp, r["fp"]):
            return r["path"]
    return None


def _fill_fp():
    rows = db.query("SELECT id,path FROM photos WHERE fp IS NULL")
    upd = []
    for i, r in enumerate(rows, 1):
        upd.append((fingerprint(r["path"]) or "", r["id"]))      # "" = nicht lesbar, nicht erneut versuchen
        if i % 300 == 0:
            jobs.progress(f"Bildvergleich {i}/{len(rows)}")
            db.executemany("UPDATE photos SET fp=? WHERE id=?", upd); upd = []
    db.executemany("UPDATE photos SET fp=? WHERE id=?", upd)


def dedupe():
    """Entfernt doppelte Fotos (gleiche Aufnahmezeit + gleicher Bildinhalt); das ältere/zugeordnete bleibt."""
    rows = db.query("SELECT id,path,taken_ts,fp,COALESCE(manual,0) m,tour_id FROM photos WHERE COALESCE(dated,1)=1 AND fp IS NOT NULL AND fp!='' ORDER BY taken_ts,id")
    drop, keep = set(), []
    for r in rows:
        keep = [k for k in keep if r["taken_ts"] - k["taken_ts"] <= 2]
        twin = next((k for k in keep if similar(r["fp"], k["fp"])), None)
        if twin is None:
            keep.append(r); continue
        a, b = (twin, r) if (twin["m"], twin["id"] * -1) >= (r["m"], r["id"] * -1) else (r, twin)
        drop.add(b["id"]); paths = b["path"]
        if b is twin:
            keep = [k for k in keep if k["id"] != twin["id"]] + [r]
        try:
            lib = config.LIB_DIR.resolve()
            p = os.path.realpath(paths)
            if lib in __import__("pathlib").Path(p).parents and os.path.exists(p):
                os.remove(p)
        except Exception:  # noqa
            pass
    for i in range(0, len(drop), 500):
        db.executemany("DELETE FROM photos WHERE id=?", [(x,) for x in list(drop)[i:i + 500]])
    if drop:
        log(f"Fotos: {len(drop)} doppelte (gleiche Zeit und gleicher Bildinhalt) entfernt")
    return len(drop)


def only_tracked():
    return db.get("photo_only_tracked") not in ("0", "false", "nein")


def track_windows():
    """Zeitfenster aller Touren (mit Toleranz) – nur Fotos darin lassen sich einer Strecke zuordnen."""
    margin = db.get_int("photo_margin_min", 30) * 60
    return [(t["start_ts"] - margin, (t["end_ts"] or t["start_ts"]) + margin)
            for t in db.query("SELECT start_ts,end_ts FROM tours WHERE start_ts IS NOT NULL ORDER BY start_ts")]


def in_track(ts, wins):
    return ts is not None and any(a <= ts <= b for a, b in wins)


def scan(root=None):
    root = root or config.LIB_DIR
    if not root.exists():
        log(f"Fotoordner {root} nicht gefunden")
        return 0
    known = {r["path"]: (r["mtime"], r["size"]) for r in db.query("SELECT path,mtime,size FROM photos")}
    seen, n_new = set(), 0
    batch = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if not d.startswith(".")]
        for f in fn:
            if f.startswith(".") or os.path.splitext(f)[1].lower() not in EXTS:
                continue
            p = os.path.join(dp, f)
            seen.add(p)
            try:
                st = os.stat(p)
            except OSError:
                continue
            if known.get(p) == (st.st_mtime, st.st_size):
                continue
            ts, la, lo = read_meta(p)
            dated = 1 if ts is not None else 0
            if ts is None:  # Rückfall: Änderungsdatum (unsicher – wird nicht automatisch einer Tour zugeordnet)
                ts = int(st.st_mtime)
            batch.append((p, st.st_mtime, st.st_size, ts, la, lo, dated))
            n_new += 1
            if len(batch) >= 200:
                _store(batch); batch = []
                jobs.progress(f"{len(seen)} Fotos gesichtet")
    _store(batch)
    _check_dated()
    _fill_fp()
    gone = [p for p in known if p not in seen]
    for i in range(0, len(gone), 500):
        db.executemany("DELETE FROM photos WHERE path=?", [(p,) for p in gone[i:i + 500]])
    log(f"Fotos: {len(seen)} im Ordner, {n_new} neu/geändert, {len(gone)} entfernt")
    dedupe()
    assign_all()
    return n_new


def _check_dated():
    """Einmalig für bereits eingelesene Fotos feststellen, ob die Aufnahmezeit aus den Bilddaten stammt."""
    rows = db.query("SELECT id,path FROM photos WHERE dated IS NULL")
    if not rows:
        return
    log(f"Fotos: prüfe bei {len(rows)} Fotos, ob eine Aufnahmezeit im Bild steht")
    upd = []
    for i, r in enumerate(rows, 1):
        ts = read_meta(r["path"])[0] if os.path.exists(r["path"]) else 1
        upd.append((1 if ts is not None else 0, r["id"]))
        if i % 500 == 0:
            jobs.progress(f"Aufnahmezeit prüfen {i}/{len(rows)}")
            db.executemany("UPDATE photos SET dated=? WHERE id=?", upd); upd = []
    db.executemany("UPDATE photos SET dated=? WHERE id=?", upd)


def _store(batch):
    batch = [b if len(b) > 6 else (*b, 1) for b in batch]
    if batch:
        db.executemany(
            "INSERT INTO photos(path,mtime,size,taken_ts,lat,lng,dated) VALUES(?,?,?,?,?,?,?) "
            "ON CONFLICT(path) DO UPDATE SET mtime=excluded.mtime,size=excluded.size,dated=excluded.dated,"
            "fp=NULL,taken_ts=excluded.taken_ts+COALESCE(offset_s,0),lat=excluded.lat,lng=excluded.lng,tour_id=CASE WHEN manual=1 THEN tour_id ELSE NULL END", batch)


ASSIGN_VERSION = "v2"
FAR_KM = 10.0                 # Foto mit GPS weiter als das von der Strecke entfernt: gehört nicht zu dieser Tour
_PC = {}


def track_pts(tid):
    """Streckenpunkte [(lat, lng, sekunden_seit_start oder None)] aus dem Cache der Touren (None = keine Strecke vorhanden)."""
    from . import routes
    f = routes.path_full(tid)
    try:
        m = f.stat().st_mtime
    except OSError:
        return None
    key = str(f)
    c = _PC.get(key)
    if c and c[0] == m:
        return c[1]
    pts = [(p[0], p[1], (p[3] / 1000.0) if len(p) > 3 and p[3] is not None else None) for p in (routes.load(tid) or [])]
    if len(_PC) > 500:
        _PC.clear()
    _PC[key] = (m, pts)
    return pts


def dist_to_track(la, lo, pts):
    """Kürzester Abstand (km) eines Punktes zur Strecke (Näherung über die gespeicherten Streckenpunkte)."""
    from math import cos, radians
    if not pts:
        return None
    k = cos(radians(la))
    best = min((p[0] - la) ** 2 + ((p[1] - lo) * k) ** 2 for p in pts)
    return best ** 0.5 * 111.32


def _assign_sig(margin, tours):
    import hashlib
    h = hashlib.md5(repr((ASSIGN_VERSION, margin, [(t["id"], t["start_ts"], t["end_ts"]) for t in tours])).encode()).hexdigest()
    r = db.one("SELECT COUNT(*) n, COALESCE(SUM(taken_ts),0) s, COALESCE(SUM(COALESCE(manual,0)),0) m, COALESCE(SUM(COALESCE(dated,1)),0) d, "
               "COALESCE(SUM(tour_id IS NOT NULL),0) a FROM photos")
    pr = db.one("SELECT COUNT(*) n FROM photo_pref")["n"]
    return f"{h}|{r['n']}|{r['s']}|{r['m']}|{r['d']}|{r['a']}|{pr}"


def pick_tour(ts, la, lo, cands):
    """Wählt aus mehreren in Frage kommenden Touren die passendste: zuerst nach Aufnahmeort (Abstand zur Strecke, falls das Foto
    GPS hat), dann nach Zeit (innerhalb der Aufzeichnung vor Toleranzbereich, kleinster Abstand, kürzere Tour).
    cands: [dict(id,start,end,dur)]. Gibt (tour_id oder None, abstand_km oder None) zurück."""
    sc = []
    for w in cands:
        gap = 0 if w["start"] <= ts <= w["end"] else min(abs(ts - w["start"]), abs(ts - w["end"]))
        d = None
        if la is not None and lo is not None:
            d = dist_to_track(la, lo, track_pts(w["id"]))
        sc.append((w, gap, d))
    known = [x for x in sc if x[2] is not None]
    pool = sc
    if len(known) >= 2:
        dm = min(x[2] for x in known)
        pool = [x for x in known if x[2] <= dm + 1.0]
    w, gap, d = min(pool, key=lambda x: (x[1], x[0]["dur"], x[0]["start"]))
    if d is not None and d > FAR_KM:
        return None, d
    return w["id"], d


def assign_all(force=False):
    """Fotos den Touren zuordnen: nach Aufnahmezeit (mit Toleranz vor/nach der Tour); bei mehreren möglichen Touren und
    Foto-GPS entscheidet der Abstand zur Strecke, ein Foto weit weg von der Strecke wird nicht zugeordnet. Ändert sich nichts
    (gleiche Touren, Fotos, Einstellungen), wird die teure Neuberechnung übersprungen."""
    margin = db.get_int("photo_margin_min", 30) * 60
    tours = db.query("SELECT id,start_ts,end_ts FROM tours WHERE start_ts IS NOT NULL ORDER BY start_ts")
    sig = _assign_sig(margin, tours)
    if not force and db.get("assign_sig") == sig:
        return
    wins = sorted(({"id": t["id"], "start": t["start_ts"], "end": (t["end_ts"] or t["start_ts"]),
                    "a": t["start_ts"] - margin, "b": (t["end_ts"] or t["start_ts"]) + margin,
                    "dur": (t["end_ts"] or t["start_ts"]) - t["start_ts"]} for t in tours), key=lambda w: w["a"])
    ph = db.query("SELECT id,taken_ts,lat,lng FROM photos WHERE COALESCE(manual,0)=0 AND COALESCE(dated,1)=1 ORDER BY taken_ts")
    upd, active, i, far = [], [], 0, 0
    for p in ph:
        ts = p["taken_ts"]
        while i < len(wins) and wins[i]["a"] <= ts:
            active.append(wins[i]); i += 1
        active = [w for w in active if w["b"] >= ts]
        if not active:
            continue
        tid, d = pick_tour(ts, p["lat"], p["lng"], active)
        if tid is None:
            far += 1
            continue
        upd.append((tid, p["id"]))
    with db.cur() as c:       # alles in einer Transaktion: andere Anfragen sehen nie den Zwischenstand „nichts zugeordnet“
        c.execute("UPDATE photos SET tour_id=NULL WHERE COALESCE(manual,0)=0")
        c.executemany("UPDATE photos SET tour_id=? WHERE id=?", upd)
        c.execute("UPDATE photos SET tour_id=(SELECT tour_id FROM photo_pref WHERE photo_pref.path=photos.path) "
                  "WHERE COALESCE(manual,0)=0 AND path IN (SELECT path FROM photo_pref) AND (SELECT tour_id FROM photo_pref WHERE photo_pref.path=photos.path) IN (SELECT id FROM tours)")
    r = db.one("SELECT COUNT(*) n FROM photos WHERE tour_id IS NOT NULL")
    db.put("assign_sig", _assign_sig(margin, tours))
    log(f"Fotos: {r['n']} einer Tour zugeordnet" + (f", {far} wegen großer Entfernung zur Strecke nicht" if far else ""))


def gps_offset(points, pts, start, radius_km=0.25, max_h=14):
    """Zeitversatz zwischen Kamerauhr und Strecke aus dem Aufnahmeort bestimmen.
    points: [(taken_ts, lat, lng)] von Fotos mit GPS; pts: Streckenpunkte mit Zeit; start: Starttime der Tour (UTC-Sekunden).
    Jedes Foto 'stimmt' für alle Zeitpunkte, zu denen die Strecke in radius_km an seinem Ort vorbeikam; der Versatz mit den meisten
    Stimmen (Minutenraster) gewinnt. Gibt (delta_s, stimmen, fotos_mit_treffer) oder None zurück."""
    from math import cos, radians
    tp = [p for p in (pts or []) if p[2] is not None]
    if not tp or not points:
        return None
    if len(points) > 150:
        step = len(points) / 150
        points = [points[int(k * step)] for k in range(150)]
    votes, hit = {}, 0
    r2 = (radius_km / 111.32) ** 2
    for ts, la, lo in points:
        k = cos(radians(la)); mine = set()
        for p in tp:
            if (p[0] - la) ** 2 + ((p[1] - lo) * k) ** 2 <= r2:
                dl = (start + p[2]) - ts
                if abs(dl) <= max_h * 3600:
                    mine.add(int(round(dl / 60.0)))
        if mine:
            hit += 1
            for m in mine:
                votes[m] = votes.get(m, 0) + 1
    if not votes:
        return None
    sm = {m: sum(votes.get(m + j, 0) for j in range(-2, 3)) for m in votes}
    best = max(sm, key=lambda m: (sm[m], -abs(m)))
    near = [m for m in votes if abs(m - best) <= 2]
    centre = sum(m * votes[m] for m in near) / max(1, sum(votes[m] for m in near))
    return int(round(centre * 60)), min(sm[best], hit), hit


def suggest_offset(tour_id):
    """Passt die Kamerazeit der Fotos zu dieser Strecke? Vergleicht den Aufnahmeort der Fotos mit der Position der Strecke zur
    Aufnahmezeit. Ergebnis: {ok, delta_s, n, of, ids}."""
    t = db.one("SELECT id,start_ts,end_ts FROM tours WHERE id=?", (str(tour_id),))
    if not t:
        raise KeyError(tour_id)
    pts = track_pts(t["id"])
    if not pts or all(p[2] is None for p in pts):
        return {"ok": False, "reason": "Zu dieser Tour gibt es keine Strecke mit Zeitangaben."}
    end = t["end_ts"] or t["start_ts"]
    rows = db.query("SELECT id,taken_ts,lat,lng,tour_id,COALESCE(manual,0) m FROM photos WHERE lat IS NOT NULL AND lng IS NOT NULL AND COALESCE(dated,1)=1 "
                    "AND taken_ts BETWEEN ? AND ? AND (tour_id IS NULL OR tour_id=?) ORDER BY taken_ts", (t["start_ts"] - 14 * 3600, end + 14 * 3600, t["id"]))
    rows = [r for r in rows if not (r["m"] == 2)]
    if len(rows) < 3:
        return {"ok": False, "reason": "Zu wenige Fotos mit Aufnahmeort (mindestens 3) in der Nähe dieser Tour."}
    res = gps_offset([(r["taken_ts"], r["lat"], r["lng"]) for r in rows], pts, t["start_ts"])
    if not res:
        return {"ok": False, "reason": "Die Fotos wurden nicht in der Nähe der Strecke aufgenommen."}
    delta, n, hit = res
    if n < 3 or n < 0.5 * hit:
        return {"ok": False, "reason": "Kein eindeutiger Zeitversatz zu finden (die Fotos passen zu mehreren Zeitpunkten der Strecke)."}
    return {"ok": True, "delta_s": delta, "aligned": abs(delta) <= 120, "n": n, "of": len(rows), "ids": [r["id"] for r in rows]}


def apply_offset(tour_id, delta_s, ids):
    """Zeitversatz auf die Fotos anwenden, die für den Abgleich genutzt wurden, plus Fotos dazwischen/daneben (Zeitraum ±30 Min.),
    und diese fest der Tour zuordnen."""
    t = db.one("SELECT id FROM tours WHERE id=?", (str(tour_id),))
    if not t:
        raise KeyError(tour_id)
    delta_s = int(delta_s)
    if abs(delta_s) > 14 * 3600 + 600:
        raise ValueError("Zeitversatz unplausibel groß")
    ids = [int(i) for i in ids or []]
    if not ids:
        raise ValueError("Keine Fotos")
    q = ",".join("?" * len(ids))
    r = db.one(f"SELECT MIN(taken_ts) a, MAX(taken_ts) b FROM photos WHERE id IN ({q})", ids)
    rows = db.query("SELECT id FROM photos WHERE taken_ts BETWEEN ? AND ? AND (tour_id IS NULL OR tour_id=? OR id IN (%s)) AND COALESCE(manual,0)!=2" % q,
                    (r["a"] - 1800, r["b"] + 1800, str(tour_id), *ids))
    tgt = sorted({x["id"] for x in rows} | set(ids))
    for i in range(0, len(tgt), 500):
        part = tgt[i:i + 500]
        db.execute(f"UPDATE photos SET taken_ts=taken_ts+?, offset_s=COALESCE(offset_s,0)+?, tour_id=?, manual=1 WHERE id IN ({','.join('?' * len(part))})",
                   (delta_s, delta_s, str(tour_id), *part))
    assign_all()
    return {"shifted": len(tgt), "delta_s": delta_s}


def delete_photos(ids):
    """Löscht Fotos aus der Bibliothek (nur die App-Kopie im Fotoordner – nie Originale) und merkt sie, damit sie beim nächsten
    Import nicht wieder auftauchen."""
    ids = [int(i) for i in ids]
    lib = config.LIB_DIR.resolve()
    n = files = 0
    for i in range(0, len(ids), 400):
        chunk = ids[i:i + 400]
        rows = db.query("SELECT id,path FROM photos WHERE id IN (%s)" % ",".join("?" * len(chunk)), tuple(chunk))
        for r in rows:
            try:
                f = os.path.realpath(r["path"])
                if lib in __import__("pathlib").Path(f).parents:
                    rel = os.path.splitext(os.path.relpath(f, lib))[0].replace(os.sep, "/")
                    db.execute("INSERT OR REPLACE INTO photo_deleted(rel,ts) VALUES(?,?)", (rel, int(time.time())))
                    if os.path.exists(f):
                        os.remove(f); files += 1
            except OSError:
                pass
            db.execute("DELETE FROM photo_pref WHERE path=?", (r["path"],))
            db.execute("DELETE FROM photos WHERE id=?", (r["id"],))
            n += 1
    log(f"Fotos: {n} gelöscht")
    return n


def assign_manual(ids, tour_id, shift=False, minutes_after_start=0, scope="selected"):
    """Fotos fest einer Tour zuordnen. Optional: Zeitversatz aus dem ersten (frühesten) gewählten Foto bestimmen
    (Foto = Tourstart + Minuten) und auf selected / day (gleicher Aufnahmetag) / unassigned anwenden."""
    ids = [int(i) for i in ids]
    if not ids:
        raise ValueError("Keine Fotos gewählt")
    t = db.one("SELECT id,start_ts FROM tours WHERE id=?", (str(tour_id),))
    if not t:
        raise KeyError(tour_id)
    q = ",".join("?" * len(ids))
    first = db.one(f"SELECT id,taken_ts FROM photos WHERE id IN ({q}) ORDER BY taken_ts LIMIT 1", ids)
    if not first:
        raise KeyError("photo")
    offset, n_shift = 0, 0
    if shift:
        offset = int(t["start_ts"] + float(minutes_after_start) * 60 - first["taken_ts"])
        if scope == "day":
            from .gpxtools import TZ
            from datetime import datetime
            d = datetime.fromtimestamp(first["taken_ts"], tz=TZ).replace(hour=0, minute=0, second=0, microsecond=0)
            a = int(d.timestamp()); b = a + 86400
            rows = db.query("SELECT id FROM photos WHERE taken_ts>=? AND taken_ts<?", (a, b))
        elif scope == "unassigned":
            rows = db.query("SELECT id FROM photos WHERE tour_id IS NULL AND COALESCE(manual,0)=0")
        else:
            rows = []
        tgt = sorted({r["id"] for r in rows} | set(ids))
        n_shift = len(tgt)
        for i in range(0, len(tgt), 500):
            part = tgt[i:i + 500]
            db.execute(f"UPDATE photos SET taken_ts=taken_ts+?, offset_s=COALESCE(offset_s,0)+? WHERE id IN ({','.join('?' * len(part))})",
                       (offset, offset, *part))
    db.execute(f"UPDATE photos SET tour_id=?, manual=1 WHERE id IN ({q})", (str(tour_id), *ids))
    assign_all()
    return {"offset_s": offset, "shifted": n_shift, "assigned": len(ids)}


def shift_photos(tour_id, delta_s, scope="tour", reset=False):
    """Zeitverschiebung für die Fotos einer Tour („Perlenkette“): alle Fotos der Tour wandern um denselben Betrag,
    ihre Abstände zueinander bleiben. scope='day': zusätzlich alle anderen Fotos desselben Aufnahmetags
    (Kamerauhr ging für den ganzen Tag falsch). reset=True nimmt jede frühere Verschiebung dieser Fotos zurück."""
    t = db.one("SELECT id FROM tours WHERE id=?", (str(tour_id),))
    if not t:
        raise KeyError(tour_id)
    delta_s = int(delta_s)
    if abs(delta_s) > 400 * 86400:
        raise ValueError("Zeitversatz unplausibel groß")
    own = [r["id"] for r in db.query("SELECT id FROM photos WHERE tour_id=?", (str(tour_id),))]
    if not own:
        raise ValueError("Diese Tour hat keine Fotos")
    ids = set(own)
    if scope == "day":
        from datetime import datetime
        from .gpxtools import TZ
        q = ",".join("?" * len(own))
        for r in db.query(f"SELECT DISTINCT taken_ts FROM photos WHERE id IN ({q})", own):
            d = datetime.fromtimestamp(r["taken_ts"], tz=TZ).replace(hour=0, minute=0, second=0, microsecond=0)
            a = int(d.timestamp())
            ids |= {x["id"] for x in db.query("SELECT id FROM photos WHERE taken_ts>=? AND taken_ts<? AND (tour_id IS NULL OR tour_id=?)", (a, a + 86400, str(tour_id)))}
    ids = sorted(ids)
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        q = ",".join("?" * len(part))
        if reset:
            db.execute(f"UPDATE photos SET taken_ts=taken_ts-COALESCE(offset_s,0), offset_s=0 WHERE id IN ({q})", part)
        else:
            db.execute(f"UPDATE photos SET taken_ts=taken_ts+?, offset_s=COALESCE(offset_s,0)+? WHERE id IN ({q})", (delta_s, delta_s, *part))
    q = ",".join("?" * len(own))
    db.execute(f"UPDATE photos SET tour_id=?, manual=1 WHERE id IN ({q})", (str(tour_id), *own))
    assign_all()
    return {"shifted": len(ids), "delta_s": 0 if reset else delta_s}


def unassign_manual(ids, reset_time=False, exclude=False):
    ids = [int(i) for i in ids]
    q = ",".join("?" * len(ids))
    if reset_time:
        db.execute(f"UPDATE photos SET taken_ts=taken_ts-COALESCE(offset_s,0), offset_s=0 WHERE id IN ({q})", ids)
    db.execute(f"UPDATE photos SET manual=?, tour_id=NULL WHERE id IN ({q})", (2 if exclude else 0, *ids))
    assign_all()


def thumb(photo_id, size):
    r = db.one("SELECT path,mtime FROM photos WHERE id=?", (photo_id,))
    if not r or not os.path.exists(r["path"]):
        return None
    key = hashlib.sha1(f"{r['path']}|{r['mtime']}|{size}".encode()).hexdigest()
    out = config.CACHE_DIR / "thumb" / key[:2] / f"{key}.jpg"
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(r["path"]) as im:
            try:
                im.draft("RGB", (size * 2, size * 2))  # JPEG: schnelles Verkleinern beim Dekodieren
            except Exception:  # noqa
                pass
            im = ImageOps.exif_transpose(im).convert("RGB")
            im.thumbnail((size, size), Image.LANCZOS)
            tmp = out.with_suffix(".tmp")
            im.save(tmp, "JPEG", quality=82)
            tmp.replace(out)
    return out


def respond(request, path):
    """Bilddatei mit ETag ausliefern; der Browser fragt jedes Mal nach (304, wenn unverändert)."""
    from fastapi.responses import FileResponse, Response
    st = os.stat(path)
    etag = f'"{st.st_mtime_ns:x}-{st.st_size:x}"'
    h = {"Cache-Control": "private, no-cache", "ETag": etag}
    if etag in (request.headers.get("if-none-match") or ""):
        return Response(status_code=304, headers=h)
    return FileResponse(path, media_type="image/jpeg", headers=h)


def compress(src, dst, max_side=None, quality=None):
    """Verkleinert ein Foto für die Bildschirmdarstellung (EXIF-Zeit/GPS bleiben erhalten)."""
    max_side = max_side or db.get_int("photo_max_side", 2200)
    quality = quality or db.get_int("photo_quality", 82)
    with Image.open(src) as im:
        try:
            im.draft("RGB", (max_side * 2, max_side * 2))
        except Exception:  # noqa
            pass
        ex = im.getexif()
        try:
            ex.get_ifd(0x8769); ex.get_ifd(0x8825)
        except Exception:  # noqa
            pass
        im = ImageOps.exif_transpose(im)
        ex[0x0112] = 1
        im = im.convert("RGB")
        im.thumbnail((max_side, max_side), Image.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_suffix(".tmp")
        im.save(tmp, "JPEG", quality=quality, optimize=True, exif=ex.tobytes())
        os.utime(tmp, (os.stat(src).st_atime, os.stat(src).st_mtime))
        tmp.replace(dst)


def import_from(root=None, dst_root=None):
    """Kopiert Fotos aus dem Originalordner komprimiert in die App-Bibliothek (nur neue/geänderte)."""
    root = root or config.PHOTOS_DIR
    dst_root = dst_root or config.LIB_DIR
    if not root.exists():
        raise RuntimeError(f"Quellordner {root} nicht gefunden. Server: SMB-Freigabe eingebunden? Mac-Version: Ordner mit der Umgebungsvariable MT_FOTOS angeben, oder in der Verwaltung „Ordner auswählen und hochladen …“ benutzen.")
    done = skipped = failed = notrack = 0
    wins = track_windows() if only_tracked() else None
    gone = {r["rel"] for r in db.query("SELECT rel FROM photo_deleted")}
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if not d.startswith(".")]
        for f in sorted(fn):
            if f.startswith(".") or os.path.splitext(f)[1].lower() not in EXTS:
                continue
            src = os.path.join(dp, f)
            rel = os.path.relpath(src, root)
            dst = dst_root / (os.path.splitext(rel)[0] + ".jpg")
            if os.path.splitext(rel)[0].replace(os.sep, "/") in gone:
                skipped += 1; continue
            try:
                if dst.exists() and dst.stat().st_mtime >= os.stat(src).st_mtime - 2:
                    skipped += 1; continue
                if wins is not None and not in_track(read_meta(src)[0], wins):
                    notrack += 1; continue      # keine GPS-Strecke zu diesem Foto -> nicht übernehmen
                compress(src, dst)
                done += 1
            except Exception as e:  # noqa
                failed += 1
                if failed <= 5:
                    log(f"  {rel}: {e}")
            if (done + skipped + failed) % 50 == 0:
                jobs.progress(f"{done} übernommen, {skipped} vorhanden, {failed} Fehler")
    log(f"Fotos übernommen: {done} neu, {skipped} schon vorhanden, {notrack} ohne passende Strecke übersprungen, {failed} Fehler")
    return done


def _hav(a, b, c, d):
    from math import asin, cos, radians, sin, sqrt
    p = radians(c - a); q = radians(d - b)
    h = sin(p / 2) ** 2 + cos(radians(a)) * cos(radians(c)) * sin(q / 2) ** 2
    return 12742 * asin(sqrt(h))


def plan(items, only_tour=None):
    """Prüft vor dem Import je Aufnahmetag, welche Tour zu den Fotos passt.
    items: [{k, t:'JJJJ:MM:TT hh:mm:ss', lat?, lng?}] -> Tage mit Status 'ok' (eindeutig) oder 'ask' (nicht eindeutig) und Vorschlägen.
    Vorschläge: nach Uhrzeit, mit ganzstündiger Zeitverschiebung (Kamera nicht auf Ortszeit) und mit minutengenauer Verschiebung,
    die aus dem Aufnahmeort der Fotos berechnet wird (Kamerauhr falsch gestellt). only_tour: alle Fotos zu genau dieser Tour."""
    from datetime import datetime
    m = db.get_int("photo_margin_min", 30) * 60
    tours = db.query("SELECT id,name,start_ts,end_ts,lat,lng,dist_m FROM tours WHERE start_ts IS NOT NULL")
    if only_tour:
        tours = [t for t in tours if t["id"] == str(only_tour)]
    days = {}
    for it in items:
        ts = _raw_ts(it.get("t"))
        if ts is not None:
            days.setdefault(it["t"][:10].replace(":", "-"), []).append((it, ts))
    by_id = {t["id"]: t for t in tours}
    out = []
    for day, lst in sorted(days.items()):
        gps = [(ts, i["lat"], i["lng"]) for i, ts in lst if i.get("lat") is not None and i.get("lng") is not None]
        sample = gps[::max(1, len(gps) // 30)] if gps else []

        def dist(t, _c={}):
            if t["id"] in _c:
                return _c[t["id"]]
            d = None
            pts = track_pts(t["id"]) if sample else None
            if pts:
                ds = sorted(dist_to_track(la, lo, pts) for _, la, lo in sample)
                d = ds[len(ds) // 2]
            elif sample and t["lat"] is not None and t["lng"] is not None:
                ds = sorted(_hav(la, lo, t["lat"], t["lng"]) for _, la, lo in sample)
                d = ds[len(ds) // 2]
            _c[t["id"]] = d
            return d

        def match(shift):
            cnt, overlap = {}, 0
            for _, ts in lst:
                hit = [t for t in tours if t["start_ts"] - m <= ts + shift <= (t["end_ts"] or t["start_ts"]) + m]
                overlap += len(hit) > 1
                for t in hit:
                    cnt[t["id"]] = cnt.get(t["id"], 0) + 1
            return cnt, overlap
        base, overlap = match(0)
        far = bool(base) and bool(sample) and all((dist(by_id[i]) or 0) > FAR_KM for i in base)
        row = {"day": day, "n": len(lst), "keys": [i["k"] for i, _ in lst], "matched": sum(base.values()), "status": "ok", "options": [], "gps": len(gps),
               "names": [by_id[i]["name"] for i in base]}
        row["single"] = len(base) == 1
        if not only_tour and base and not overlap and not far and row["matched"] >= max(1, 0.6 * len(lst)):
            out.append(row); continue
        row["status"] = "ask"
        row["reason"] = ("alle Fotos dieses Tages zu dieser Tour" if only_tour else
                         "überlappende Touren" if overlap else "Aufnahmeort passt nicht zur Tour" if far else
                         f"{len(lst) - row['matched']} von {len(lst)} Fotos liegen außerhalb der Aufzeichnung" if base else "keine Tour zur Aufnahmezeit")
        cands = {}

        def add(t, shift_s, n, extra=None, score=0.0):
            dk = dist(t)
            if dk is not None and dk > 300:
                score -= 5
            o = {"tour": t["id"], "name": t["name"], "start": datetime.fromtimestamp(t["start_ts"], TZ).strftime("%d.%m.%Y %H:%M"),
                 "km": round((t["dist_m"] or 0) / 1000, 1), "shift_s": int(shift_s), "shift_h": round(shift_s / 3600, 2) if shift_s % 3600 else int(shift_s // 3600),
                 "matched": n, "dist_km": round(dk, 1) if dk is not None else None, "score": score - (dk / 50 if dk is not None else 0)}
            o.update(extra or {})
            cands[(t["id"], int(shift_s))] = o
        for h in range(-12, 13):
            cnt, _ = match(h * 3600)
            for tid, n in cnt.items():
                add(by_id[tid], h * 3600, n, score=n / len(lst) * 10 - abs(h) * 0.05)
        d0 = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=TZ).timestamp()
        for t in tours:
            near_day = only_tour or d0 - 3 * 3600 <= t["start_ts"] < d0 + 27 * 3600
            if near_day and (t["id"], 0) not in cands:      # Tour am selben Tag, Fotos aber vor Start/nach Ende (Uhr zu spät gestartet o. ä.)
                gaps = [max(t["start_ts"] - ts, ts - (t["end_ts"] or t["start_ts"]), 0) for _, ts in lst]
                add(t, 0, sum(g == 0 for g in gaps), {"gap_min": round(min(gaps) / 60)}, 4 - min(gaps) / 3600)
            if gps and (only_tour or d0 - 14 * 3600 <= t["start_ts"] < d0 + 38 * 3600):      # Kamerauhr falsch: Zeitversatz aus dem Aufnahmeort
                res = gps_offset(gps, track_pts(t["id"]), t["start_ts"])
                if res and res[1] >= max(2, 0.5 * res[2]) and abs(res[0]) > 120:
                    dl = res[0]
                    n = sum(t["start_ts"] - m <= ts + dl <= (t["end_ts"] or t["start_ts"]) + m for _, ts in lst)
                    add(t, dl, n, {"by_gps": True, "gps_n": res[1]}, 12 + res[1] / max(1, res[2]))
        opts = sorted(cands.values(), key=lambda x: -x["score"])
        row["options"] = opts[:4]
        if not any(o["shift_s"] == 0 for o in row["options"]):          # ohne Zeitverschiebung immer mindestens eine Möglichkeit anbieten
            z = next((o for o in opts if o["shift_s"] == 0), None)
            if z:
                row["options"].append(z)
        out.append(row)
    return out


def with_exif_time(jpeg, taken, lat=None, lng=None):
    """Fügt einem (vom Browser erzeugten) JPEG die Aufnahmezeit 'JJJJ:MM:TT hh:mm:ss' als EXIF hinzu."""
    import io
    import re
    import struct
    if not re.match(r"^\d{4}:\d\d:\d\d \d\d:\d\d:\d\d$", taken or "") or jpeg[:2] != b"\xff\xd8":
        return jpeg
    ex = Image.Exif()
    ex[0x0132] = taken                     # DateTime
    ex.get_ifd(0x8769)[0x9003] = taken     # DateTimeOriginal
    if lat is not None and lng is not None:
        def dms(v):
            v = abs(v); d = int(v); mi = int((v - d) * 60)
            return (float(d), float(mi), round(((v - d) * 60 - mi) * 60, 3))
        g = ex.get_ifd(0x8825)
        g[1] = "N" if lat >= 0 else "S"; g[2] = dms(lat); g[3] = "E" if lng >= 0 else "W"; g[4] = dms(lng)
    payload = ex.tobytes()
    if not payload.startswith(b"Exif\x00\x00"):
        payload = b"Exif\x00\x00" + payload
    return jpeg[:2] + b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload + jpeg[2:]
