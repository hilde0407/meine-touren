"""FIT-Dateien (Garmin, Suunto, Wahoo, Polar, Coros …) lesen und als GPX ausgeben – ohne Zusatzpaket.

Unterstützt: 12/14-Byte-Kopf, Definitions- und Datensätze, komprimierte Zeitstempel, Entwicklerfelder
(werden übersprungen), aneinandergehängte FIT-Dateien. Gelesen werden nur GPS-Punkte (record) sowie Sportart
(session/sport). Zusätzlich werden – soweit die Datei sie enthält – Geschwindigkeit, Kadenz, Leistung, Temperatur, Atemfrequenz,
Schrittlänge, Bodenkontaktzeit, vertikale Oszillation und Luftdruck je Punkt gelesen (landen als GPX-Erweiterung, siehe metrics.py),
dazu Hersteller/Produkt (file_id, device_info) und Zusammenfassung (Kalorien, Trainingseffekt).
Prüfsummen werden nicht erzwungen, damit leicht beschädigte Dateien noch brauchbar sind.
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


def _decode(data, meta=None):
    """Gibt (punkte, sportart_tuple) zurück; punkte = [(unix_s, lat, lon, alt_or_None, hr, extra_dict)].
    meta (dict, optional) bekommt 'dev' (Hersteller/Produkt) und 'sum' (Zusammenfassung der Aktivität)."""
    pos, n = 0, len(data)
    points, sport = [], None
    while pos + 12 <= n and data[pos + 8:pos + 12] == b".FIT":
        hsize = data[pos]
        dsize = struct.unpack_from("<I", data, pos + 4)[0]
        start, end = pos + hsize, min(pos + hsize + dsize, n)
        sport_box = []
        _records(data, start, end, points, sport_box, meta)
        if sport_box:
            sport = sport or sport_box[0]
        pos = end + 2                               # 2 Byte Prüfsumme
    if pos == 0:
        raise FitError("Keine FIT-Datei")
    return points, sport


def _records(data, p, end, points, sport_box, meta=None):
    defs = {}                                       # lokale Nachrichtennummer -> (global, endian, felder, dev_bytes)
    last_ts = 0
    session = {}
    tap = meta.get("_tap") if meta else None        # Diagnose (scan): bekommt jeden Datensatz samt unbekannter Felder
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
            if tap:
                tap(d[0], vals)
            _use(d[0], vals, points, session, meta)
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
        if tap:
            tap(d[0], vals)
        _use(d[0], vals, points, session, meta)
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
        if ch == "s" and size > 0:                   # Text (z. B. Produktname)
            txt = raw.split(b"\0")[0].decode("utf-8", "replace").strip()
            if txt:
                vals[num] = txt
            continue
        if size % isz or size == 0:
            continue
        if size != isz:                              # Feld mit mehreren Werten (Array): nur erstes Element
            raw = raw[:isz]
        v = struct.unpack(endian + ch, raw)[0]
        if invalid is not None and v == invalid:
            continue
        vals[num] = v
    return vals, p + dev


def _use(gnum, v, points, session, meta=None):
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
        hr = v.get(3)                                # Herzfrequenz (uint8, bpm)
        points.append((ts + FIT_EPOCH, la, lo, alt, hr if hr is not None and 30 <= hr <= 240 else None, _extra(v)))
    elif gnum == 18 and not session:                 # session (erste genügt)
        session.update({k: v[k] for k in (5, 6) if k in v})
        if meta is not None:
            _summary(v, meta)
    elif gnum == 0 and meta is not None:             # file_id: Hersteller/Produkt
        d = meta.setdefault("dev", {})
        for k, key in ((1, "manu"), (2, "prod"), (8, "name")):
            if k in v and key not in d:
                d[key] = v[k]
    elif gnum == 23 and meta is not None and v.get(0, 0) == 0:   # device_info der Aufzeichnung (Index 0 = Aufzeichnungsgerät)
        d = meta.setdefault("dev", {})
        for k, key in ((2, "manu"), (4, "prod"), (27, "name")):
            if k in v and key not in d:
                d[key] = v[k]
    elif gnum == 12 and not session and 0 in v:      # sport
        session.update({5: v[0], 6: v.get(1)})


def _extra(v):
    """Zusatzmesswerte eines record-Satzes (SI-Einheiten); fehlende Felder fehlen im Ergebnis."""
    ex = {}

    def put(key, num, scale, lo, hi):
        x = v.get(num)
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            x = x / scale
            if lo <= x <= hi:
                ex[key] = x
    put("speed", 73, 1000.0, 0, 90)                  # m/s (enhanced), sonst 6
    if "speed" not in ex:
        put("speed", 6, 1000.0, 0, 90)
    put("pow", 7, 1.0, 0, 5000)
    put("temp", 13, 1.0, -60, 70)
    put("resp", 108, 100.0, 1, 120)
    if "resp" not in ex:
        put("resp", 99, 1.0, 1, 120)
    put("stride", 85, 10000.0, 0.1, 4)               # mm (Faktor 10) -> m
    put("gct", 41, 10.0, 50, 2000)                   # ms
    put("vosc", 39, 10.0, 5, 400)                    # mm
    put("press", 91, 100.0, 300, 1100)               # Pa -> hPa
    c = v.get(4)
    if isinstance(c, (int, float)) and 0 < c < 255:
        ex["cad"] = c + (v.get(53, 0) or 0) / 128.0  # volle Umdrehungen/Schritte (Hälfte) + Bruchteil
    return ex


def _summary(v, meta):
    sm = meta.setdefault("sum", {})
    for k, key, scale, lo, hi in ((11, "kcal", 1, 1, 30000), (24, "te", 10.0, 0, 5.5), (137, "ate", 10.0, 0, 5.5)):
        x = v.get(k)
        if isinstance(x, (int, float)) and lo <= x / scale <= hi and key not in sm:
            sm[key] = round(x / scale, 1) if scale != 1 else int(x)


SCAN_CAP = 20000                                     # je Feld höchstens so viele Zahlenwerte für Kennzahlen merken


def scan(data):
    """Diagnose: ALLE Nachrichten- und Feldnummern einer FIT-Datei (auch unbekannte, nicht ausgewertete) mit Anzahl und Zahlenwerten (roh, unskaliert).
    Rückgabe {"fields": {(nachricht, feld): {"n": Anzahl, "vals": [Zahlen …], "text": Anzahl Textwerte}}, "starts": [Unix-s …], "bad": bool}.
    Felder mit mehreren Werten (Arrays) zählen nur ihr erstes Element (wie beim normalen Lesen); beschädigte Dateien liefern, was bis dahin gelesen wurde."""
    fields, starts, rec_seen = {}, [], []

    def tap(g, vals):
        for f, v in vals.items():
            e = fields.setdefault((g, f), {"n": 0, "vals": [], "text": 0})
            e["n"] += 1
            if isinstance(v, str):
                e["text"] += 1
            elif isinstance(v, (int, float)) and not isinstance(v, bool) and len(e["vals"]) < SCAN_CAP:
                e["vals"].append(v)
        ts = vals.get(253) if g == 20 else vals.get(2) if g == 18 else None
        if isinstance(ts, int) and ts > 0 and (g == 18 or not rec_seen):
            if g == 20:
                rec_seen.append(1)                       # nur der erste Punkt
            starts.append(ts + FIT_EPOCH)                # Start der Sitzung und erster Punkt
    bad = False
    try:
        _decode(data, {"_tap": tap})
    except (FitError, struct.error, IndexError):
        bad = True
    return {"fields": fields, "starts": starts, "bad": bad}


MANUFACTURER = {1: "garmin", 13: "garmin", 15: "garmin", 23: "suunto", 123: "polar", 258: "zepp"}
BRAND = {"garmin": "Garmin", "suunto": "Suunto", "polar": "Polar", "zepp": "Amazfit/Zepp"}
FOOT_SPORTS = {1, 11, 17, 35}                        # Laufen, Gehen, Wandern, Schneeschuhwandern: Kadenz = Schritte/min (beide Beine)


def device_info(meta):
    """(art, anzeigename) aus Hersteller/Produkt der FIT-Datei; ('', '') wenn nichts bekannt."""
    d = (meta or {}).get("dev") or {}
    src = MANUFACTURER.get(d.get("manu"), "other" if d.get("manu") not in (None, 0) else "")
    name = str(d.get("name") or "").strip()
    if not name and src in BRAND:
        name = BRAND[src]
    return src, name[:80]


def sport_name(sport):
    if not sport or sport[0] is None:
        return ""
    s, sub = sport
    return SUB_SPORT.get((s, sub)) or SPORT.get(s, "")


def _ext_xml(hr, ex):
    parts = []
    if hr:
        parts.append(f"<gpxtpx:hr>{hr}</gpxtpx:hr>")
    for k, tag, fmt in (("cad", "gpxtpx:cad", "{:.0f}"), ("temp", "gpxtpx:atemp", "{:.0f}"), ("speed", "mt:speed", "{:.2f}"), ("pow", "mt:power", "{:.0f}"),
                        ("resp", "mt:resp", "{:.1f}"), ("stride", "mt:stride", "{:.3f}"), ("gct", "mt:gct", "{:.0f}"), ("vosc", "mt:vosc", "{:.1f}"), ("press", "mt:press", "{:.1f}")):
        if k in ex:
            parts.append(f"<{tag}>{fmt.format(ex[k])}</{tag}>")
    return "<extensions><gpxtpx:TrackPointExtension>" + "".join(parts) + "</gpxtpx:TrackPointExtension></extensions>" if parts else ""


def to_gpx(data, name=""):
    """FIT-Bytes -> (gpx_text, sport). Löst FitError / ValueError (keine GPS-Punkte) aus."""
    meta = {}
    pts, sport = _decode(data, meta)
    if not pts:
        raise ValueError("Keine GPS-Punkte")
    pts.sort(key=lambda x: x[0])
    sp = sport_name(sport)
    foot = bool(sport and sport[0] in FOOT_SPORTS)
    f = lambda t: datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def ex_of(p):
        ex = dict(p[5]) if len(p) > 5 else {}
        if foot and "cad" in ex:
            ex["cad"] *= 2                                   # FIT zählt beim Gehen/Laufen Schritte je Bein
        return ex
    body = "".join(
        f'<trkpt lat="{la:.7f}" lon="{lo:.7f}">' + (f"<ele>{al:.1f}</ele>" if al is not None else "") + f"<time>{f(t)}</time>"
        + _ext_xml(hr, ex_of((t, la, lo, al, hr) + tuple(rest))) + "</trkpt>\n"
        for t, la, lo, al, hr, *rest in pts)
    nm = escape(name or "Aktivität")
    src, dev = device_info(meta)
    mx = ""
    if src or meta.get("sum"):
        mx = "<extensions>" + (f'<mt:device src="{src}">{escape(dev)}</mt:device>' if src else "") \
             + ("<mt:sum " + " ".join(f'{k}="{v}"' for k, v in meta["sum"].items()) + "/>" if meta.get("sum") else "") + "</extensions>"
    gpx = ('<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Meine Touren (FIT)" xmlns="http://www.topografix.com/GPX/1/1" '
           'xmlns:gpxtpx="http://www.garmin.com/xmlschemas/TrackPointExtension/v1" xmlns:mt="https://meine-touren.invalid/ns/1">\n'
           f"<metadata><name>{nm}</name><time>{f(pts[0][0])}</time>{mx}</metadata>\n"
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
