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
    gone = [p for p in known if p not in seen]
    for i in range(0, len(gone), 500):
        db.executemany("DELETE FROM photos WHERE path=?", [(p,) for p in gone[i:i + 500]])
    log(f"Fotos: {len(seen)} im Ordner, {n_new} neu/geändert, {len(gone)} entfernt")
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
            "taken_ts=excluded.taken_ts+COALESCE(offset_s,0),lat=excluded.lat,lng=excluded.lng,tour_id=CASE WHEN manual=1 THEN tour_id ELSE NULL END", batch)


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
    r = db.one("SELECT COUNT(*) n FROM photos WHERE tour_id IS NOT NULL")
    log(f"Fotos: {r['n']} einer Tour zugeordnet")


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
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if not d.startswith(".")]
        for f in sorted(fn):
            if f.startswith(".") or os.path.splitext(f)[1].lower() not in EXTS:
                continue
            src = os.path.join(dp, f)
            rel = os.path.relpath(src, root)
            dst = dst_root / (os.path.splitext(rel)[0] + ".jpg")
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


def with_exif_time(jpeg, taken):
    """Fügt einem (vom Browser erzeugten) JPEG die Aufnahmezeit 'JJJJ:MM:TT hh:mm:ss' als EXIF hinzu."""
    import io
    import re
    import struct
    if not re.match(r"^\d{4}:\d\d:\d\d \d\d:\d\d:\d\d$", taken or "") or jpeg[:2] != b"\xff\xd8":
        return jpeg
    ex = Image.Exif()
    ex[0x0132] = taken                     # DateTime
    ex.get_ifd(0x8769)[0x9003] = taken     # DateTimeOriginal
    payload = ex.tobytes()
    if not payload.startswith(b"Exif\x00\x00"):
        payload = b"Exif\x00\x00" + payload
    return jpeg[:2] + b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload + jpeg[2:]
