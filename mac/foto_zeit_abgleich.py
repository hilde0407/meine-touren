#!/usr/bin/env python3
"""Foto-Zeit-Abgleich: korrigiert die Aufnahmezeit exportierter JPEGs anhand der Original-RAW-Dateien (Sony ARW).

Lightroom-Exporte tragen manchmal die falsche Uhrzeit (z. B. den Exportzeitpunkt). Dieses Programm liest die
echte Aufnahmezeit aus den RAW-Dateien und schreibt sie in die JPEGs zurück. Nur Python 3 nötig (auf dem Mac
vorhanden), keine weiteren Pakete.

Ablauf (die Festplatten werden nacheinander angeschlossen):
  1. Festplatte anschließen, einlesen:    python3 foto_zeit_abgleich.py index /Volumes/Platte1
  2. Prüfen (ändert nichts):               python3 foto_zeit_abgleich.py check "$HOME/Pictures/fertige Fotos"
  3. Korrigieren:                          python3 foto_zeit_abgleich.py fix   "$HOME/Pictures/fertige Fotos"
  4. Nächste Festplatte: wieder Schritt 1 bis 3. Bereits korrigierte Fotos bleiben unverändert, der Index sammelt
     alle Platten. Am Ende zeigt der Bericht, welche JPEGs zu keinem Original gefunden wurden.
Weitere Befehle:  status (eingelesene Platten)   undo (letzte Korrektur rückgängig machen)

Zuordnung: Dateiname (DSC01234.jpg, auch DSC01234-Bearbeitet.jpg / DSC01234-2.jpg) und zur Sicherheit Kamera-
modell, Belichtungszeit, Blende, ISO und Brennweite. Die Zähler der Sony-Kameras beginnen irgendwann wieder bei
vorn; Treffer, die sich nicht eindeutig zuordnen lassen, werden nur gemeldet, nie geändert.
Geändert werden die Felder „Aufnahmezeit“ (DateTimeOriginal) und „Digitalisierungszeit“ (CreateDate) direkt in der
Datei (je 19 Byte, sonst bleibt alles unberührt). Jede Änderung wird protokolliert und lässt sich mit undo zurücknehmen.
"""
import argparse
import csv
import json
import os
import re
import struct
import sys
import time
from datetime import datetime
from pathlib import Path

INDEX = Path(os.environ.get("FOTO_ZEIT_INDEX") or Path.home() / ".foto_zeit_index.json")
LOG = Path(os.environ.get("FOTO_ZEIT_LOG") or Path.home() / ".foto_zeit_log.jsonl")
DT_RE = re.compile(rb"^\d{4}:\d\d:\d\d \d\d:\d\d:\d\d$")
SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}


# ---------------------------------------------------------------- EXIF lesen (TIFF/ARW und JPEG)
class Tiff:
    def __init__(self, f, base=0):
        self.f, self.base = f, base
        f.seek(base)
        h = f.read(8)
        if h[:2] == b"II":
            self.e = "<"
        elif h[:2] == b"MM":
            self.e = ">"
        else:
            raise ValueError("kein TIFF")
        if struct.unpack(self.e + "H", h[2:4])[0] != 42:
            raise ValueError("kein TIFF")
        self.first = struct.unpack(self.e + "I", h[4:8])[0]

    def ifd(self, off):
        """{tag: (typ, anzahl, absolute Position der Werte)}"""
        e, f = self.e, self.f
        f.seek(self.base + off)
        n = struct.unpack(e + "H", f.read(2))[0]
        if n > 600:
            raise ValueError("IFD unplausibel")
        raw = f.read(12 * n)
        out = {}
        for i in range(n):
            tag, typ, cnt = struct.unpack(e + "HHI", raw[i * 12:i * 12 + 8])
            size = SIZES.get(typ, 1) * cnt
            here = self.base + off + 2 + i * 12 + 8
            out[tag] = (typ, cnt, here if size <= 4 else self.base + struct.unpack(e + "I", raw[i * 12 + 8:i * 12 + 12])[0])
        return out

    def val(self, ent):
        typ, cnt, pos = ent
        e, f = self.e, self.f
        f.seek(pos)
        if typ == 2:
            return f.read(cnt).split(b"\0")[0].decode("latin-1").strip()
        if typ == 3:
            return list(struct.unpack(e + "%dH" % cnt, f.read(2 * cnt)))
        if typ == 4:
            return list(struct.unpack(e + "%dI" % cnt, f.read(4 * cnt)))
        if typ == 5:
            v = struct.unpack(e + "%dI" % (2 * cnt), f.read(8 * cnt))
            return [v[i] / v[i + 1] if v[i + 1] else 0.0 for i in range(0, len(v), 2)]
        return None


def tiff_info(f, base=0):
    t = Tiff(f, base)
    i0 = t.ifd(t.first)
    ex = {}
    if 0x8769 in i0:
        try:
            ex = t.ifd(t.val(i0[0x8769])[0])
        except Exception:  # noqa
            ex = {}

    def g(d, tag, first=True):
        if tag not in d:
            return None
        try:
            v = t.val(d[tag])
        except Exception:  # noqa
            return None
        return (v[0] if v else None) if first and isinstance(v, list) else v

    info = {"make": g(i0, 0x010F), "model": g(i0, 0x0110), "exp": g(ex, 0x829A), "f": g(ex, 0x829D), "iso": g(ex, 0x8827), "fl": g(ex, 0x920A),
            "uid": g(ex, 0xA420) or None, "dt": g(ex, 0x9003), "patch": {}}
    for name, tag in (("dto", 0x9003), ("cd", 0x9004)):          # Positionen der 19-Byte-Zeitstempel für die Korrektur
        if tag in ex and ex[tag][0] == 2 and ex[tag][1] >= 20:
            f.seek(ex[tag][2]); raw = f.read(19)
            if DT_RE.match(raw):
                info["patch"][name] = (ex[tag][2], raw.decode())
    if not info["dt"] and "dto" in info["patch"]:
        info["dt"] = info["patch"]["dto"][1]
    return info


class NoExif(ValueError):
    pass


def jpeg_info(path):
    with open(path, "rb") as f:
        if f.read(2) != b"\xff\xd8":
            raise ValueError("kein JPEG")
        while True:
            b = f.read(4)
            if len(b) < 4 or b[0] != 0xFF:
                raise NoExif()
            mk, ln = b[1], struct.unpack(">H", b[2:4])[0]
            if mk == 0xDA:
                raise NoExif()
            if mk == 0xE1:
                start = f.tell()
                if f.read(6) == b"Exif\0\0":
                    try:
                        info = tiff_info(f, start + 6)
                    except Exception:  # noqa
                        info = {"make": None, "model": None, "exp": None, "f": None, "iso": None, "fl": None, "uid": None, "dt": None, "patch": {}}
                    info["seg"] = (start - 4, ln + 2)                 # Position des 0xFF-Markers und Länge inkl. Marker
                    return info
                f.seek(start)
            f.seek(ln - 2, 1)


def raw_info(path):
    with open(path, "rb") as f:
        return tiff_info(f, 0)


# ---------------------------------------------------------------- EXIF-Block neu schreiben (wenn Felder fehlen)
def _entries(t, ifd):
    """Einträge als {tag: (typ, anzahl, bytes im Little-Endian-Format)}"""
    out = {}
    for tag, (typ, cnt, pos) in ifd.items():
        sz = SIZES.get(typ, 1) * cnt
        t.f.seek(pos); raw = t.f.read(sz)
        if len(raw) != sz:
            continue
        w = {3: "H", 8: "h", 4: "I", 9: "i", 11: "f", 5: "I", 10: "i", 12: "d"}.get(typ)
        if w and t.e == ">":
            n = sz // struct.calcsize(w)
            raw = struct.pack("<%d%s" % (n, w), *struct.unpack(">%d%s" % (n, w), raw))
        out[tag] = (typ, cnt, raw)
    return out


def _serialize(entries, off):
    items = sorted(entries.items())
    head = struct.pack("<H", len(items)); data = b""; base = off + 2 + 12 * len(items) + 4
    for tag, (typ, cnt, raw) in items:
        if len(raw) <= 4:
            head += struct.pack("<HHI", tag, typ, cnt) + raw.ljust(4, b"\0")
        else:
            head += struct.pack("<HHII", tag, typ, cnt, base + len(data)); data += raw + (b"\0" if len(raw) % 2 else b"")
    return head + struct.pack("<I", 0) + data


def _ascii(s):
    b = s.encode("latin-1", "replace") + b"\0"
    return (2, len(b), b)


def _rational(v):
    from fractions import Fraction
    fr = Fraction(v).limit_denominator(100000)
    return (5, 1, struct.pack("<II", fr.numerator, fr.denominator))


def build_exif(path, jinfo, add):
    """Neuer EXIF-Block (TIFF, Little-Endian) mit den vorhandenen Feldern plus den fehlenden aus `add`."""
    i0, ex = {}, {}
    if jinfo.get("seg"):
        with open(path, "rb") as f:
            t = Tiff(f, jinfo["seg"][0] + 10)
            d0 = t.ifd(t.first)
            if 0x8825 in d0:
                raise RuntimeError("GPS-Block vorhanden – wird nicht umgeschrieben")
            i0 = _entries(t, {k: v for k, v in d0.items() if k not in (0x8769, 0x0201, 0x0202)})
            if 0x8769 in d0:
                e0 = t.ifd(t.val(d0[0x8769])[0])
                if 0xA005 in e0:
                    raise RuntimeError("Interoperabilitäts-Block vorhanden – wird nicht umgeschrieben")
                ex = _entries(t, e0)
    ex.setdefault(0x9000, (7, 4, b"0231"))
    for tag, v in add.get("ifd0", {}).items():
        i0.setdefault(tag, v)
    for tag, v in add.get("exif", {}).items():
        ex.setdefault(tag, v)
    i0[0x8769] = (4, 1, struct.pack("<I", 0))
    ex_off = 8 + len(_serialize(i0, 8))
    i0[0x8769] = (4, 1, struct.pack("<I", ex_off))
    return b"II*\0" + struct.pack("<I", 8) + _serialize(i0, 8) + _serialize(ex, ex_off)


def new_fields(orig, jinfo):
    """Was dem JPEG fehlt und aus dem Original übernommen wird."""
    dt = orig["dt"]
    add = {"ifd0": {}, "exif": {0x9003: _ascii(dt), 0x9004: _ascii(dt)}}
    if orig.get("make") and not jinfo.get("make"):
        add["ifd0"][0x010F] = _ascii(orig["make"])
    if orig.get("model") and not jinfo.get("model"):
        add["ifd0"][0x0110] = _ascii(orig["model"])
    for key, tag in (("exp", 0x829A), ("f", 0x829D), ("fl", 0x920A)):
        if orig.get(key) and not jinfo.get(key):
            add["exif"][tag] = _rational(orig[key])
    if orig.get("iso") and not jinfo.get("iso"):
        add["exif"][0x8827] = (3, 1, struct.pack("<H", min(int(orig["iso"]), 65535)))
    return add


def rewrite_exif(path, jinfo, orig, backup_dir):
    """Schreibt einen neuen EXIF-Block ins JPEG. Der alte Block wird für „undo“ gesichert."""
    exif = build_exif(path, jinfo, new_fields(orig, jinfo))
    seg = b"Exif\0\0" + exif
    if len(seg) + 2 > 65535:
        raise RuntimeError("EXIF-Block zu groß")
    block = b"\xff\xe1" + struct.pack(">H", len(seg) + 2) + seg
    data = Path(path).read_bytes()
    if jinfo.get("seg"):
        a, n = jinfo["seg"]; old = data[a:a + n]
        if old[:2] != b"\xff\xe1":
            raise RuntimeError("Datei hat sich geändert")
    else:
        a, n, old = 2, 0, b""
        if data[2:4] == b"\xff\xe0":                                  # nach JFIF-Segment einfügen
            a = 4 + struct.unpack(">H", data[4:6])[0]
    bk = None
    if old:
        backup_dir.mkdir(parents=True, exist_ok=True)
        bk = backup_dir / (re.sub(r"[^A-Za-z0-9._-]", "_", str(path))[-150:] + f".{abs(hash(str(path))) % 10**8}.bak")
        bk.write_bytes(old)
    tmp = Path(str(path) + ".fza_tmp")
    tmp.write_bytes(data[:a] + block + data[a + n:])
    st = os.stat(path)
    os.replace(tmp, path)
    os.chmod(path, st.st_mode & 0o7777)
    return {"mode": "rewrite", "backup": str(bk) if bk else None, "newlen": len(block), "oldlen": n, "at": a}


# ---------------------------------------------------------------- Index der RAW-Dateien
def load_index():
    try:
        return json.loads(INDEX.read_text())
    except Exception:  # noqa
        return {"disks": {}}


def save_index(ix):
    INDEX.write_text(json.dumps(ix))


def disk_label(root, name=None):
    if name:
        return name
    parts = Path(root).resolve().parts
    return parts[2] if len(parts) > 2 and parts[1] == "Volumes" else str(Path(root).resolve())


def cmd_index(a):
    ix = load_index()
    exts = tuple("." + e.lower().lstrip(".") for e in a.ext.split(","))
    for root in a.pfade:
        root = Path(root).expanduser()
        if not root.is_dir():
            print(f"Ordner nicht gefunden: {root}"); continue
        label = disk_label(root, a.name if len(a.pfade) == 1 else None)
        d = ix["disks"].setdefault(label, {"files": {}})
        old = d["files"]; new = {}; n = reused = bad = 0; t0 = time.time(); cut = False
        print(f"Lese {root} (Platte „{label}“) …")
        for dp, dns, fns in os.walk(root):
            if a.zeitlimit and time.time() - t0 > a.zeitlimit:
                cut = True; break
            dns[:] = [x for x in dns if not x.startswith(".")]
            for fn in fns:
                if fn.startswith(".") or not fn.lower().endswith(exts):
                    continue
                p = Path(dp) / fn; rel = str(p.relative_to(root))
                try:
                    st = p.stat()
                except OSError:
                    continue
                o = old.get(rel)
                if o and o["size"] == st.st_size and o["mtime"] == int(st.st_mtime) and "make" in o:
                    new[rel] = o; reused += 1; continue
                try:
                    i = raw_info(p)
                except Exception:  # noqa
                    bad += 1; continue
                if not i["dt"]:
                    bad += 1; continue
                new[rel] = {"stem": p.stem.upper(), "size": st.st_size, "mtime": int(st.st_mtime), "dt": i["dt"], "make": i["make"], "model": i["model"],
                            "exp": i["exp"], "f": i["f"], "iso": i["iso"], "fl": i["fl"], "uid": i["uid"]}
                n += 1
                if n % 200 == 0:
                    print(f"  {n} neu gelesen …")
        d["files"] = {**old, **new} if cut else new; d["root"] = str(root); d["scanned"] = int(time.time())
        if cut:
            print("  Zeitlimit erreicht – denselben Befehl noch einmal ausführen, er macht dort weiter.")
        print(f"  {len(new)} Originale auf „{label}“ ({n} neu, {reused} unverändert, {bad} ohne lesbares Datum)")
    save_index(ix)
    print(f"Index gespeichert: {INDEX} – insgesamt {sum(len(d['files']) for d in ix['disks'].values())} Originale auf {len(ix['disks'])} Platte(n).")


def cmd_status(a):
    ix = load_index()
    if not ix["disks"]:
        print("Noch nichts eingelesen. Erst: index /Volumes/<Platte>"); return
    for k, d in ix["disks"].items():
        print(f"{k:30s} {len(d['files']):7d} Originale   eingelesen {time.strftime('%d.%m.%Y %H:%M', time.localtime(d.get('scanned', 0)))}   {d.get('root', '')}")


# ---------------------------------------------------------------- Zuordnung
def by_stem(ix):
    m = {}
    for label, d in ix["disks"].items():
        for rel, e in d["files"].items():
            m.setdefault(e["stem"], []).append(dict(e, disk=label, rel=rel))
    return m


def stem_candidates(stem, stems):
    u = stem.upper()
    out = []
    for n in range(len(u), 4, -1):
        if (n == len(u) or not u[n].isalnum()) and u[:n] in stems:
            out.append(u[:n])
    return out


def close(a, b, rel=0.02):
    return a is None or b is None or abs(a - b) <= rel * max(abs(a), abs(b), 1e-9)


def compatible(j, r):
    if j["model"] and r["model"] and j["model"].strip().lower() != r["model"].strip().lower():
        return False
    if j["uid"] and r["uid"] and j["uid"] != r["uid"]:
        return False
    return close(j["exp"], r["exp"]) and close(j["f"], r["f"]) and (j["iso"] is None or r["iso"] is None or j["iso"] == r["iso"]) and close(j["fl"], r["fl"])


def folder_hint(path):
    """Datum aus dem Ordnerpfad: ('tag', 'JJJJ:MM:TT') bei „TT.MM.JJJJ“, sonst ('monat', 'JJJJ:MM') bzw. ('jahr', 'JJJJ')."""
    parts = Path(path).parts[:-1]
    for p in reversed(parts):
        m = re.search(r"(\d{1,2})\.(\d{1,2})\.(20\d\d|19\d\d)", p)
        if m:
            return "tag", "%s:%02d:%02d" % (m.group(3), int(m.group(2)), int(m.group(1)))
    yr = next((p for p in parts if re.fullmatch(r"(19|20)\d\d", p)), None)
    if yr:
        i = parts.index(yr)
        m = re.match(r"(\d{2})\b", parts[i + 1]) if i + 1 < len(parts) else None
        if m and 1 <= int(m.group(1)) <= 12:
            return "monat", f"{yr}:{m.group(1)}"
        return "jahr", yr
    return None


def context_pick(cands, path, mtime):
    """Mehrere Originale gleichen Namens: anhand Ordnerdatum und Exportzeitpunkt (Original muss älter sein) auswählen."""
    dts = sorted({c["dt"] for c in cands})
    if mtime:
        lim = datetime.fromtimestamp(mtime + 86400).strftime("%Y:%m:%d %H:%M:%S")
        dts = [d for d in dts if d <= lim]
    h = folder_hint(path)
    if h and dts:
        kind, v = h
        sel = [d for d in dts if d.startswith(v)]
        if not sel and kind == "tag":
            from datetime import timedelta
            day = datetime.strptime(v, "%Y:%m:%d")
            near = {(day + timedelta(days=x)).strftime("%Y:%m:%d") for x in (-1, 1)}
            sel = [d for d in dts if d[:10] in near]
        if not sel and kind != "jahr":
            sel = [d for d in dts if d.startswith(v[:4])]
        dts = sel
    return dts[0] if len(dts) == 1 else None


def plausible(dt, path, mtime):
    """Passt die Originalzeit zum Ordner (Jahr/Monat/Tag im Pfad) und liegt sie vor dem Export (Dateizeit)?"""
    from datetime import timedelta
    t = parse(dt)
    if mtime and t > datetime.fromtimestamp(mtime) + timedelta(days=1):
        return False
    h = folder_hint(path)
    if not h:
        return True
    kind, v = h
    if kind == "tag":
        lo = datetime.strptime(v, "%Y:%m:%d") - timedelta(days=2); hi = lo + timedelta(days=5)
    elif kind == "monat":
        lo = datetime.strptime(v + ":01", "%Y:%m:%d") - timedelta(days=35); hi = lo + timedelta(days=100)
    else:
        lo = datetime.strptime(v + ":01:01", "%Y:%m:%d") - timedelta(days=35); hi = lo + timedelta(days=436)
    return lo <= t <= hi


def find_original(j, stem, stems, path=None, mtime=None):
    cands = []; relaxed = False
    for s in stem_candidates(stem, stems):
        cands = [r for r in stems[s] if compatible(j, r)]
        if cands:
            break
    if not cands and re.search(r"pano|hdr|stack|fokus|focus|merge", stem, re.I):          # zusammengesetzte Bilder: Belichtungswerte weichen ab
        for s in stem_candidates(stem, stems):
            cands = [r for r in stems[s] if not (j["model"] and r["model"] and j["model"].strip().lower() != r["model"].strip().lower())]
            if cands:
                relaxed = True; break
    if not cands:
        return None, "nicht gefunden"
    strong = not relaxed and all(j.get(k) is not None for k in ("exp", "f", "iso"))           # Aufnahmedaten im JPEG vorhanden und passend
    if not strong and path:                                                     # sonst: nur plausible Treffer (Ordnerdatum, vor dem Export)
        cands = [c for c in cands if plausible(c["dt"], path, mtime)]
        if not cands:
            return None, "nicht gefunden (Originaldatum passt nicht zum Ordner)"
    if len({c["dt"] for c in cands}) > 1:
        dt = context_pick(cands, path, mtime) if path else None
        if not dt:
            return None, "mehrdeutig (%d Originale mit gleichem Namen und gleichen Einstellungen)" % len(cands)
        return next(c for c in cands if c["dt"] == dt), "über Ordnerdatum gewählt"
    return cands[0], ("" if strong else "nur über Dateiname und Ordnerdatum zugeordnet")


def parse(dt):
    return datetime.strptime(dt, "%Y:%m:%d %H:%M:%S")


def fmt_delta(s):
    sign = "+" if s >= 0 else "-"; s = abs(int(s)); d, s = divmod(s, 86400); h, s = divmod(s, 3600); m, s = divmod(s, 60)
    return sign + (f"{d} T " if d else "") + f"{h:02d}:{m:02d}:{s:02d}"


# ---------------------------------------------------------------- Prüfen / Korrigieren
def patch_file(path, patch, new):
    nb = new.encode()
    done = []
    with open(path, "r+b") as f:
        for name in ("dto", "cd"):
            if name not in patch:
                continue
            pos, old = patch[name]
            f.seek(pos)
            if f.read(19) != old.encode():
                raise RuntimeError("Datei hat sich geändert")
            f.seek(pos); f.write(nb); done.append((name, pos, old))
    return done


def run_check(a, apply):
    ix = load_index()
    if not ix["disks"]:
        print("Der Index ist leer. Erst eine Festplatte einlesen: index /Volumes/<Platte>"); return 1
    stems = by_stem(ix)
    root = Path(a.ordner).expanduser()
    files = sorted(p for p in root.rglob("*") if p.is_file() and not p.name.startswith(".") and p.suffix.lower() in (".jpg", ".jpeg"))
    run = datetime.now().strftime("%Y%m%d-%H%M%S-%f"); rows = []; cnt = {}
    logf = open(LOG, "a") if apply else None
    bdir = Path(os.environ.get("FOTO_ZEIT_BACKUP") or Path.home() / ".foto_zeit_backup") / run
    for k, p in enumerate(files, 1):
        try:
            j = jpeg_info(p)
        except NoExif:
            j = {"make": None, "model": None, "exp": None, "f": None, "iso": None, "fl": None, "uid": None, "dt": None, "patch": {}, "seg": None}
        except Exception as e:  # noqa
            rows.append((str(p), "defekt", "", "", "", "", str(e))); cnt["defekt"] = cnt.get("defekt", 0) + 1; continue
        try:
            mt = p.stat().st_mtime
        except OSError:
            mt = None
        r, why = find_original(j, p.stem, stems, p, mt)
        if not r:
            st = "mehrdeutig" if why.startswith("mehrdeutig") else "nicht gefunden"
            rows.append((str(p), st, j["dt"] or "", "", "", "", why)); cnt[st] = cnt.get(st, 0) + 1; continue
        orig = r["dt"]
        try:
            diff = (parse(j["dt"]) - parse(orig)).total_seconds() if j["dt"] else None
        except ValueError:
            diff = None
        note = why
        if diff is not None and abs(diff) <= a.toleranz:
            st = "ok"
        else:
            st = ("korrigiert" if apply else "zu korrigieren") if "dto" in j["patch"] else ("ergänzt" if apply else "zu ergänzen")
            if apply:
                try:
                    if "dto" in j["patch"]:
                        done = patch_file(p, j["patch"], orig)
                        logf.write(json.dumps({"run": run, "file": str(p), "new": orig, "mode": "patch", "fields": done}) + "\n")
                    else:
                        res = rewrite_exif(p, j, dict(r, dt=orig), bdir)
                        logf.write(json.dumps(dict(res, run=run, file=str(p), new=orig)) + "\n")
                    logf.flush()
                except Exception as e:  # noqa
                    st = "Fehler"; rows.append((str(p), st, j["dt"] or "", orig, "", f'{r["disk"]}:{r["rel"]}', str(e))); cnt[st] = cnt.get(st, 0) + 1; continue
        rows.append((str(p), st, j["dt"] or "", orig, fmt_delta(diff) if diff is not None else "", f'{r["disk"]}:{r["rel"]}', note))
        cnt[st] = cnt.get(st, 0) + 1
        if k % 500 == 0:
            print(f"  {k}/{len(files)} geprüft …")
    if logf:
        logf.close()
    rep = Path(a.bericht or f"foto_zeit_bericht_{run}.csv")
    with open(rep, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";"); w.writerow(["Datei", "Status", "Zeit im JPEG", "Zeit im Original", "Abweichung", "Original", "Hinweis"]); w.writerows(rows)
    print(f"\n{len(files)} JPEG-Dateien in {root}:")
    for k2, v in sorted(cnt.items(), key=lambda x: -x[1]):
        print(f"  {k2:16s} {v}")
    shown = [r for r in rows if r[1] in ("zu korrigieren", "korrigiert", "zu ergänzen", "ergänzt")][:8]
    for r in shown:
        print(f"    {Path(r[0]).name}: {r[2] or 'keine Zeit'} → {r[3]}  {('(' + r[4] + ')') if r[4] else ''}")
    print(f"Bericht: {rep}")
    if apply and (cnt.get("korrigiert") or cnt.get("ergänzt")):
        print(f"{cnt.get('korrigiert', 0) + cnt.get('ergänzt', 0)} Dateien geändert (Lauf {run}). Rückgängig: python3 {Path(sys.argv[0]).name} undo")
    elif not apply and (cnt.get("zu korrigieren") or cnt.get("zu ergänzen")):
        print("Zum Anwenden denselben Befehl mit „fix“ statt „check“ ausführen.")
    return 0


def cmd_undo(a):
    if not LOG.exists():
        print("Kein Protokoll vorhanden."); return 1
    recs = [json.loads(x) for x in LOG.read_text().splitlines() if x.strip()]
    if not recs:
        print("Protokoll leer."); return 1
    run = a.lauf or recs[-1]["run"]; sel = [r for r in recs if r["run"] == run]
    n = skipped = 0
    for r in sel:
        try:
            if r.get("mode") == "rewrite":
                data = Path(r["file"]).read_bytes(); at, nl = r["at"], r["newlen"]
                if data[at:at + 2] != b"\xff\xe1" or struct.unpack(">H", data[at + 2:at + 4])[0] + 2 != nl:
                    skipped += 1; continue
                old = Path(r["backup"]).read_bytes() if r.get("backup") else b""
                tmp = Path(r["file"] + ".fza_tmp"); tmp.write_bytes(data[:at] + old + data[at + nl:]); os.replace(tmp, r["file"]); n += 1
                continue
            with open(r["file"], "r+b") as f:
                for name, pos, old in r["fields"]:
                    f.seek(pos)
                    if f.read(19) != r["new"].encode():
                        skipped += 1; break
                    f.seek(pos); f.write(old.encode())
                else:
                    n += 1
        except OSError:
            skipped += 1
    rest = [r for r in recs if r["run"] != run]
    LOG.write_text("".join(json.dumps(r) + "\n" for r in rest))
    print(f"Lauf {run}: {n} Dateien zurückgesetzt, {skipped} übersprungen (Datei fehlt oder wurde inzwischen geändert).")
    return 0


def main():
    ap = argparse.ArgumentParser(description="Aufnahmezeit exportierter JPEGs anhand der RAW-Originale korrigieren")
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("index", help="RAW-Dateien einer angeschlossenen Festplatte/eines Ordners einlesen"); s.add_argument("pfade", nargs="+")
    s.add_argument("--name", help="Bezeichnung der Platte (Standard: Volume-Name)"); s.add_argument("--zeitlimit", type=int, default=0, help=argparse.SUPPRESS); s.add_argument("--ext", default="arw", help="Dateiendungen, Standard: arw (z. B. arw,dng)")
    sub.add_parser("status", help="eingelesene Festplatten anzeigen")
    for nm, h in (("check", "nur prüfen und Bericht erstellen"), ("fix", "Zeiten korrigieren")):
        s = sub.add_parser(nm, help=h); s.add_argument("ordner"); s.add_argument("--toleranz", type=int, default=1, help="Abweichung in Sekunden, die noch als gleich gilt (Standard 1)")
        s.add_argument("--bericht", help="Pfad der CSV-Berichtsdatei")
    s = sub.add_parser("undo", help="letzte Korrektur rückgängig machen"); s.add_argument("--lauf", help="bestimmter Lauf (Standard: der letzte)")
    a = ap.parse_args()
    return {"index": lambda: cmd_index(a), "status": lambda: cmd_status(a), "check": lambda: run_check(a, False), "fix": lambda: run_check(a, True), "undo": lambda: cmd_undo(a)}[a.cmd]()


if __name__ == "__main__":
    sys.exit(main() or 0)
