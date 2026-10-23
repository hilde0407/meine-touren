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


def assign_all():
    margin = db.get_int("photo_margin_min", 30) * 60
    tours = db.query("SELECT id,start_ts,end_ts FROM tours WHERE start_ts IS NOT NULL ORDER BY start_ts")
    db.execute("UPDATE photos SET tour_id=NULL WHERE COALESCE(manual,0)=0")
    rows = []
    for t in tours:
        end = t["end_ts"] or t["start_ts"]
        rows.append((t["id"], t["start_ts"] - margin, end + margin))
    with db.cur() as c:
        c.executemany("UPDATE photos SET tour_id=? WHERE taken_ts BETWEEN ? AND ? AND tour_id IS NULL AND COALESCE(manual,0)=0 AND COALESCE(dated,1)=1", rows)
    db.execute("UPDATE photos SET tour_id=(SELECT tour_id FROM photo_pref WHERE photo_pref.path=photos.path) "
               "WHERE COALESCE(manual,0)=0 AND path IN (SELECT path FROM photo_pref) AND (SELECT tour_id FROM photo_pref WHERE photo_pref.path=photos.path) IN (SELECT id FROM tours)")
    r = db.one("SELECT COUNT(*) n FROM photos WHERE tour_id IS NOT NULL")
    log(f"Fotos: {r['n']} einer Tour zugeordnet")


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
        raise RuntimeError(f"Quellordner {root} nicht gefunden (SMB-Freigabe eingebunden?)")
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


def plan(items):
    """Prüft vor dem Import je Aufnahmetag, welche Tour zu den Fotos passt.
    items: [{k, t:'JJJJ:MM:TT hh:mm:ss', lat?, lng?}] -> Tage mit Status 'ok' (eindeutig) oder 'ask' (Rückfrage nötig) mit Vorschlägen.
    Vorschläge berücksichtigen Zeitverschiebungen in ganzen Stunden (Kamera nicht auf Ortszeit) und den Aufnahmeort."""
    from datetime import datetime
    m = db.get_int("photo_margin_min", 30) * 60
    tours = db.query("SELECT id,name,start_ts,end_ts,lat,lng,dist_m FROM tours WHERE start_ts IS NOT NULL")
    days = {}
    for it in items:
        ts = _raw_ts(it.get("t"))
        if ts is not None:
            days.setdefault(it["t"][:10].replace(":", "-"), []).append((it, ts))
    out = []
    for day, lst in sorted(days.items()):
        gl = [(i["lat"], i["lng"]) for i, _ in lst if i.get("lat") is not None and i.get("lng") is not None]
        g = (sorted(x[0] for x in gl)[len(gl) // 2], sorted(x[1] for x in gl)[len(gl) // 2]) if gl else None

        def dist(t):
            return _hav(g[0], g[1], t["lat"], t["lng"]) if g and t["lat"] is not None and t["lng"] is not None else None

        def match(shift):
            cnt, overlap = {}, 0
            for _, ts in lst:
                hit = [t for t in tours if t["start_ts"] - m <= ts + shift <= (t["end_ts"] or t["start_ts"]) + m]
                overlap += len(hit) > 1
                for t in hit:
                    cnt[t["id"]] = cnt.get(t["id"], 0) + 1
            return cnt, overlap
        by_id = {t["id"]: t for t in tours}
        base, overlap = match(0)
        far = bool(base) and g is not None and all((dist(by_id[i]) or 0) > 150 for i in base)
        row = {"day": day, "n": len(lst), "keys": [i["k"] for i, _ in lst], "matched": sum(base.values()), "status": "ok", "options": []}
        if base and not overlap and not far:
            out.append(row); continue
        row["status"] = "ask"
        row["reason"] = ("überlappende Touren" if overlap else "Aufnahmeort passt nicht zur Tour" if far else "keine Tour zur Aufnahmezeit")
        cands = {}
        for h in range(-12, 13):
            cnt, _ = match(h * 3600)
            for tid, n in cnt.items():
                t = by_id[tid]; dk = dist(t)
                score = n / len(lst) * 10 - (dk / 50 if dk is not None else 0) - abs(h) * 0.05
                if dk is not None and dk > 300:
                    score -= 5
                k = (tid, h)
                cands[k] = {"tour": tid, "name": t["name"], "start": datetime.fromtimestamp(t["start_ts"], TZ).strftime("%d.%m.%Y %H:%M"),
                            "km": round((t["dist_m"] or 0) / 1000, 1), "shift_h": h, "matched": n, "dist_km": round(dk) if dk is not None else None, "score": score}
        # Tour am selben Tag, aber Fotos vor Start/nach Ende der Aufzeichnung (Uhr zu spät gestartet o. ä.)
        d0 = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=TZ).timestamp()
        for t in tours:
            if d0 - 3 * 3600 <= t["start_ts"] < d0 + 27 * 3600 and (t["id"], 0) not in cands:
                gaps = [max(t["start_ts"] - ts, ts - (t["end_ts"] or t["start_ts"]), 0) for _, ts in lst]
                dk = dist(t)
                cands[(t["id"], 0)] = {"tour": t["id"], "name": t["name"], "start": datetime.fromtimestamp(t["start_ts"], TZ).strftime("%d.%m.%Y %H:%M"),
                                       "km": round((t["dist_m"] or 0) / 1000, 1), "shift_h": 0, "matched": sum(g == 0 for g in gaps),
                                       "gap_min": round(min(gaps) / 60), "dist_km": round(dk) if dk is not None else None,
                                       "score": 4 - min(gaps) / 3600 - (dk / 50 if dk is not None else 0)}
        opts = sorted(cands.values(), key=lambda x: -x["score"])
        row["options"] = opts[:4]
        if not any(o["shift_h"] == 0 for o in row["options"]):          # ohne Zeitverschiebung immer mindestens eine Möglichkeit anbieten
            z = next((o for o in opts if o["shift_h"] == 0), None)
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
