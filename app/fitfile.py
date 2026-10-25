"""FIT-Dateien (Garmin, Suunto, Wahoo, Polar, Coros …) lesen und als GPX ausgeben – ohne Zusatzpaket.

Unterstützt: 12/14-Byte-Kopf, Definitions- und Datensätze, komprimierte Zeitstempel, Entwicklerfelder
(werden übersprungen), aneinandergehängte FIT-Dateien. Gelesen werden nur GPS-Punkte (record) sowie Sportart
(session/sport). Prüfsummen werden nicht erzwungen, damit leicht beschädigte Dateien noch brauchbar sind.
"""
import gzip
import io
import struct
import zipfile
from datetime import datetime, timezone
from xml.sax.saxutils import escape

FIT_EPOCH = 631065600            # 1989-12-31 00:00:00 UTC in Unix-Sekunden
MAX_ZIP_BYTES = 4 * 1024 ** 3    # Schutz gegen Zip-Bomben (entpackt, gesamt)
MAX_MEMBER = 200 * 1024 ** 2

# Basistypen: Nummer -> (struct-Zeichen, Größe, "ungültig"-Wert)
BASE = {
    0x00: ("B", 1, 0xFF), 0x01: ("b", 1, 0x7F), 0x02: ("B", 1, 0xFF), 0x83: ("h", 2, 0x7FFF),
    0x84: ("H", 2, 0xFFFF), 0x85: ("i", 4, 0x7FFFFFFF), 0x86: ("I", 4, 0xFFFFFFFF),
    0x07: ("s", 1, None), 0x88: ("f", 4, None), 0x89: ("d", 8, None), 0x0A: ("B", 1, 0x00),
    0x8B: ("H", 2, 0x0000), 0x8C: ("I", 4, 0x00000000), 0x0D: ("B", 1, 0xFF),
    0x8E: ("q", 8, 0x7FFFFFFFFFFFFFFF), 0x8F: ("Q", 8, 0xFFFFFFFFFFFFFFFF), 0x90: ("Q", 8, 0),
}

# FIT-Sportart (sport) -> Komoot-Sportart dieser App
SPORT = {
    1: "jogging", 2: "touringbicycle", 11: "hike", 12: "nordic", 13: "skialpin", 14: "skialpin",
    16: "mountaineering", 17: "hike", 21: "e_touringbicycle", 35: "snowshoe",
}
SUB_SPORT = {                     # (sport, sub_sport) -> genauer
    (2, 7): "racebike", (2, 8): "mtb", (2, 28): "e_touringbicycle", (2, 46): "e_touringbicycle", (2, 47): "e_touringbicycle",
    (13, 37): "skitour", (12, 37): "skitour", (14, 37): "skitour", (1, 3): "jogging", (11, 0): "hike", (11, 19): "nordicwalking",
}


class FitError(Exception):
    pass


def is_fit(data):
    return len(data) >= 12 and data[8:12] == b".FIT"


def _decode(data):
    """Gibt (punkte, sportart_tuple) zurück; punkte = [(unix_s, lat, lon, alt_or_None)]."""
    pos, n = 0, len(data)
    points, sport = [], None
    while pos + 12 <= n and data[pos + 8:pos + 12] == b".FIT":
        hsize = data[pos]
        dsize = struct.unpack_from("<I", data, pos + 4)[0]
        start, end = pos + hsize, min(pos + hsize + dsize, n)
        sport_box = []
        _records(data, start, end, points, sport_box)
        if sport_box:
            sport = sport or sport_box[0]
        pos = end + 2                               # 2 Byte Prüfsumme
    if pos == 0:
        raise FitError("Keine FIT-Datei")
    return points, sport


def _records(data, p, end, points, sport_box):
    defs = {}                                       # lokale Nachrichtennummer -> (global, endian, felder, dev_bytes)
    last_ts = 0
    session = {}
    while p < end:
        h = data[p]; p += 1
        if h & 0x80:                                # komprimierter Zeitstempel
            local, off = (h >> 5) & 3, h & 0x1F
            if last_ts:
                ts = (last_ts & ~0x1F) + off
                if off < (last_ts & 0x1F):
                    ts += 0x20
                last_ts = ts
            d = defs.get(local)
            if not d:
                raise FitError("Datensatz ohne Definition")
            vals, p = _read(data, p, d)
            vals[253] = last_ts
            _use(d[0], vals, points, session)
            continue
        local = h & 0x0F
        if h & 0x40:                                # Definition
            has_dev = bool(h & 0x20)
            p += 1                                  # reserviert
            arch = data[p]; p += 1
            endian = ">" if arch else "<"
            gnum = struct.unpack_from(endian + "H", data, p)[0]; p += 2
            nf = data[p]; p += 1
            fields = []
            for _ in range(nf):
                fields.append((data[p], data[p + 1], data[p + 2])); p += 3
            dev = 0
            if has_dev:
                nd = data[p]; p += 1
                for _ in range(nd):
                    dev += data[p + 1]; p += 3
            defs[local] = (gnum, endian, fields, dev)
            continue
        d = defs.get(local)
        if not d:
            raise FitError("Datensatz ohne Definition")
        vals, p = _read(data, p, d)
        if 253 in vals and isinstance(vals[253], int):
            last_ts = vals[253]
        _use(d[0], vals, points, session)
    if session:
        sport_box.append((session.get(5), session.get(6)))


def _read(data, p, d):
    gnum, endian, fields, dev = d
    vals = {}
    for num, size, btype in fields:
        info = BASE.get(btype) or BASE.get(btype | 0x80) or BASE.get(btype & 0x7F)
        raw = data[p:p + size]; p += size
        if info is None or len(raw) < size:
            continue
        ch, isz, invalid = info
        if ch == "s" or size % isz or size == 0:
            continue
        if size != isz:                              # Feld mit mehreren Werten (Array): nur erstes Element
            raw = raw[:isz]
        v = struct.unpack(endian + ch, raw)[0]
        if invalid is not None and v == invalid:
            continue
        vals[num] = v
    return vals, p + dev


def _use(gnum, v, points, session):
    if gnum == 20:                                   # record
        lat, lon, ts = v.get(0), v.get(1), v.get(253)
        if lat is None or lon is None or ts is None:
            return
        la, lo = lat * 180.0 / 2 ** 31, lon * 180.0 / 2 ** 31
        if abs(la) > 90 or abs(lo) > 180 or (la == 0 and lo == 0):
            return
        alt = v.get(78)
        alt = (alt / 5.0 - 500) if alt is not None else None
        if alt is None and v.get(2) is not None:
            alt = v[2] / 5.0 - 500
        points.append((ts + FIT_EPOCH, la, lo, alt))
    elif gnum == 18 and not session:                 # session (erste genügt)
        session.update({k: v[k] for k in (5, 6) if k in v})
    elif gnum == 12 and not session and 0 in v:      # sport
        session.update({5: v[0], 6: v.get(1)})


def sport_name(sport):
    if not sport or sport[0] is None:
        return ""
    s, sub = sport
    return SUB_SPORT.get((s, sub)) or SPORT.get(s, "")


def to_gpx(data, name=""):
    """FIT-Bytes -> (gpx_text, sport). Löst FitError / ValueError (keine GPS-Punkte) aus."""
    pts, sport = _decode(data)
    if not pts:
        raise ValueError("Keine GPS-Punkte")
    pts.sort(key=lambda x: x[0])
    sp = sport_name(sport)
    f = lambda t: datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    body = "".join(
        f'<trkpt lat="{la:.7f}" lon="{lo:.7f}">' + (f"<ele>{al:.1f}</ele>" if al is not None else "") + f"<time>{f(t)}</time></trkpt>\n"
        for t, la, lo, al in pts)
    nm = escape(name or "Aktivität")
    gpx = ('<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Meine Touren (FIT)" xmlns="http://www.topografix.com/GPX/1/1">\n'
           f"<metadata><name>{nm}</name><time>{f(pts[0][0])}</time></metadata>\n"
           f"<trk><name>{nm}</name>" + (f"<type>{sp}</type>" if sp else "") + f"<trkseg>\n{body}</trkseg></trk></gpx>\n")
    return gpx, sp


def iter_expand(name, data=None, depth=0, budget=None):
    """Datei (FIT/GPX/TCX, gzip oder ZIP – auch verschachtelt, z. B. Garmin-Gesamtexport) -> liefert (name, text, kind).
    data: Bytes, ein Dateipfad (Path) oder None (name ist dann der Pfad). text ist GPX/TCX-Text (FIT wird umgewandelt).
    kind: 'fit' | 'gpx' | 'nogps' (FIT ohne Strecke, z. B. Schlaf/Alltag) | 'bad' (defekt)."""
    from pathlib import Path
    budget = budget if budget is not None else [MAX_ZIP_BYTES]
    path = None
    if data is None:
        path, data = Path(name), None
    elif isinstance(data, Path):
        path, data = data, None
    low = name.lower()
    head = b""
    if path is not None:
        with open(path, "rb") as fh:
            head = fh.read(4)
    else:
        head = data[:4]
    if head[:2] == b"\x1f\x8b" or low.endswith(".gz"):
        try:
            raw = gzip.decompress(data if data is not None else path.read_bytes())
        except OSError:
            raw = None
        if raw is not None:
            yield from iter_expand(name[:-3] if low.endswith(".gz") else name, raw, depth + 1, budget)
            return
    if head == b"PK\x03\x04" or low.endswith(".zip"):
        if depth > 3:
            return
        try:
            z = zipfile.ZipFile(path if path is not None else io.BytesIO(data))
        except zipfile.BadZipFile:
            yield (name, "", "bad")
            return
        with z:
            for zi in z.infolist():
                if zi.is_dir() or zi.file_size > MAX_MEMBER:
                    continue
                ext = zi.filename.lower().rsplit(".", 1)[-1] if "." in zi.filename else ""
                if ext not in ("fit", "gpx", "tcx", "zip", "gz"):
                    continue
                budget[0] -= zi.file_size
                if budget[0] < 0:
                    raise ValueError("Archiv zu groß (Zip-Bombe?)")
                yield from iter_expand(zi.filename, z.read(zi), depth + 1, budget)
        return
    if data is None:
        data = path.read_bytes()
    if low.endswith(".fit") or is_fit(data):
        try:
            gpx, _ = to_gpx(data, name.rsplit("/", 1)[-1].rsplit(".", 1)[0])
            yield (name, gpx, "fit")
        except ValueError:
            yield (name, "", "nogps")
        except (FitError, struct.error, IndexError):
            yield (name, "", "bad")
    elif low.endswith((".gpx", ".tcx")):
        yield (name, data.decode("utf-8", "replace"), "gpx")


def expand(name, data=None):
    return list(iter_expand(name, data))
