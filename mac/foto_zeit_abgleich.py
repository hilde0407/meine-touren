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

    info = {"model": g(i0, 0x0110), "exp": g(ex, 0x829A), "f": g(ex, 0x829D), "iso": g(ex, 0x8827), "fl": g(ex, 0x920A),
            "uid": g(ex, 0xA420) or None, "dt": g(ex, 0x9003), "patch": {}}
    for name, tag in (("dto", 0x9003), ("cd", 0x9004)):          # Positionen der 19-Byte-Zeitstempel für die Korrektur
        if tag in ex and ex[tag][0] == 2 and ex[tag][1] >= 20:
            f.seek(ex[tag][2]); raw = f.read(19)
            if DT_RE.match(raw):
                info["patch"][name] = (ex[tag][2], raw.decode())
    if not info["dt"] and "dto" in info["patch"]:
        info["dt"] = info["patch"]["dto"][1]
    return info


def jpeg_info(path):
    with open(path, "rb") as f:
        if f.read(2) != b"\xff\xd8":
            raise ValueError("kein JPEG")
        while True:
            b = f.read(4)
            if len(b) < 4 or b[0] != 0xFF:
                raise ValueError("kein EXIF")
            mk, ln = b[1], struct.unpack(">H", b[2:4])[0]
            if mk == 0xDA:
                raise ValueError("kein EXIF")
            if mk == 0xE1:
                start = f.tell()
                if f.read(6) == b"Exif\0\0":
                    return tiff_info(f, start + 6)
                f.seek(start)
            f.seek(ln - 2, 1)


def raw_info(path):
    with open(path, "rb") as f:
        return tiff_info(f, 0)


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
        old = d["files"]; new = {}; n = reused = bad = 0
        print(f"Lese {root} (Platte „{label}“) …")
        for dp, dns, fns in os.walk(root):
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
                if o and o["size"] == st.st_size and o["mtime"] == int(st.st_mtime):
                    new[rel] = o; reused += 1; continue
                try:
                    i = raw_info(p)
                except Exception:  # noqa
                    bad += 1; continue
                if not i["dt"]:
                    bad += 1; continue
                new[rel] = {"stem": p.stem.upper(), "size": st.st_size, "mtime": int(st.st_mtime), "dt": i["dt"], "model": i["model"],
                            "exp": i["exp"], "f": i["f"], "iso": i["iso"], "fl": i["fl"], "uid": i["uid"]}
                n += 1
                if n % 200 == 0:
                    print(f"  {n} neu gelesen …")
        d["files"] = new; d["root"] = str(root); d["scanned"] = int(time.time())
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


def find_original(j, stem, stems):
    cands = []
    for s in stem_candidates(stem, stems):
        cands = [r for r in stems[s] if compatible(j, r)]
        if cands:
            break
    if not cands:
        return None, "nicht gefunden"
    if len({c["dt"] for c in cands}) > 1:
        return None, "mehrdeutig (%d Originale mit gleichem Namen und gleichen Einstellungen)" % len(cands)
    return cands[0], ""


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
    for k, p in enumerate(files, 1):
        try:
            j = jpeg_info(p)
        except Exception as e:  # noqa
            st, rel, note, delta, newdt, disk = "kein EXIF", "", str(e), "", "", ""
            rows.append((str(p), st, "", "", "", "", note)); cnt[st] = cnt.get(st, 0) + 1; continue
        r, why = find_original(j, p.stem, stems)
        if not r:
            st = "mehrdeutig" if why.startswith("mehrdeutig") else "nicht gefunden"
            rows.append((str(p), st, j["dt"] or "", "", "", "", why)); cnt[st] = cnt.get(st, 0) + 1; continue
        orig = r["dt"]
        try:
            diff = (parse(j["dt"]) - parse(orig)).total_seconds() if j["dt"] else None
        except ValueError:
            diff = None
        if diff is not None and abs(diff) <= a.toleranz:
            st = "ok"
        elif not j["patch"]:
            st = "nicht änderbar"
        else:
            st = "korrigiert" if apply else "zu korrigieren"
            if apply:
                try:
                    done = patch_file(p, j["patch"], orig)
                    logf.write(json.dumps({"run": run, "file": str(p), "new": orig, "fields": done}) + "\n"); logf.flush()
                except Exception as e:  # noqa
                    st = "Fehler"; rows.append((str(p), st, j["dt"] or "", orig, "", f'{r["disk"]}:{r["rel"]}', str(e))); cnt[st] = cnt.get(st, 0) + 1; continue
        rows.append((str(p), st, j["dt"] or "", orig, fmt_delta(diff) if diff is not None else "", f'{r["disk"]}:{r["rel"]}', ""))
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
    shown = [r for r in rows if r[1] in ("zu korrigieren", "korrigiert")][:8]
    for r in shown:
        print(f"    {Path(r[0]).name}: {r[2]} → {r[3]}  ({r[4]})")
    print(f"Bericht: {rep}")
    if apply and cnt.get("korrigiert"):
        print(f"{cnt['korrigiert']} Dateien korrigiert (Lauf {run}). Rückgängig: python3 {Path(sys.argv[0]).name} undo")
    elif not apply and cnt.get("zu korrigieren"):
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
    s.add_argument("--name", help="Bezeichnung der Platte (Standard: Volume-Name)"); s.add_argument("--ext", default="arw", help="Dateiendungen, Standard: arw (z. B. arw,dng)")
    sub.add_parser("status", help="eingelesene Festplatten anzeigen")
    for nm, h in (("check", "nur prüfen und Bericht erstellen"), ("fix", "Zeiten korrigieren")):
        s = sub.add_parser(nm, help=h); s.add_argument("ordner"); s.add_argument("--toleranz", type=int, default=1, help="Abweichung in Sekunden, die noch als gleich gilt (Standard 1)")
        s.add_argument("--bericht", help="Pfad der CSV-Berichtsdatei")
    s = sub.add_parser("undo", help="letzte Korrektur rückgängig machen"); s.add_argument("--lauf", help="bestimmter Lauf (Standard: der letzte)")
    a = ap.parse_args()
    return {"index": lambda: cmd_index(a), "status": lambda: cmd_status(a), "check": lambda: run_check(a, False), "fix": lambda: run_check(a, True), "undo": lambda: cmd_undo(a)}[a.cmd]()


if __name__ == "__main__":
    sys.exit(main() or 0)
