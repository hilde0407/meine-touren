#!/usr/bin/env python3
"""foto_zeit_katalog.py – ergänzt fehlende Aufnahmezeiten in exportierten JPEGs aus dem Lightroom-Katalog.

Hintergrund: Lightroom-Exporte mit „nur Copyright“ enthalten keine Aufnahmezeit; Programme nehmen dann das Exportdatum.
Der Lightroom-Katalog kennt die richtige Aufnahmezeit jedes Originals. Zuordnung: Dateiname (ohne Zusätze wie -Pano,
-SharpenAI …) plus Datum im Ordnernamen (TT.MM.JJJJ) bzw. Jahr/Monat des Ordners; es wird nur geschrieben, wenn genau ein
Katalogeintrag passt. Der Katalog und die Festplatte werden nur GELESEN. Geändert werden nur JPEGs ohne Aufnahmezeit
(nur EXIF-Kopf, das Bild selbst bleibt byte-identisch). Rückgängig: --undo.

  python3 foto_zeit_katalog.py --katalog "/Volumes/Daten 2022"            # Probelauf (nur Bericht)
  python3 foto_zeit_katalog.py --katalog "/Volumes/Daten 2022" --anwenden
  python3 foto_zeit_katalog.py --undo                                      # letzten Lauf zurücknehmen
"""
import argparse, base64, collections, glob, io, json, os, re, sqlite3, struct, sys, time
from datetime import datetime

try:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
except ImportError:
    sys.exit("Pillow fehlt:  pip3 install pillow")

LOG = os.path.expanduser("~/.foto_zeit_katalog_log.jsonl")


def katalog_zeiten(platte):
    kats = [k for k in glob.glob(os.path.join(platte, "**", "*.lrcat"), recursive=True)
            if "/Backups/" not in k and not os.path.basename(k).startswith("._")]
    if not kats:
        sys.exit("Kein Lightroom-Katalog unter %s gefunden." % platte)
    out = collections.defaultdict(set)
    for k in kats:
        c = sqlite3.connect("file:%s?mode=ro&immutable=1" % os.path.abspath(k), uri=True)
        for b, ct in c.execute("select f.baseName,a.captureTime from Adobe_images a join AgLibraryFile f on f.id_local=a.rootFile "
                               "where a.masterImage is null and a.fileFormat!='VIDEO' and a.captureTime is not null"):
            out[b.lower()].add(ct[:19])
        c.close()
        print("Katalog:", k)
    return out


def segmente(b):
    """Liefert [(marker, start, ende)] der Kopfsegmente bis SOS."""
    segs, o = [], 2
    while o + 4 <= len(b) and b[o] == 0xFF:
        m = b[o + 1]
        if m == 0xDA or m == 0xD9:
            break
        ln = struct.unpack(">H", b[o + 2:o + 4])[0]
        segs.append((m, o, o + 2 + ln))
        o += 2 + ln
    return segs


def hat_zeit(payload):
    try:
        ex = Image.Exif(); ex.load(payload)
        e = ex.get_ifd(0x8769)
        return bool(e.get(36867) or e.get(36868))
    except Exception:
        return False


def kandidat(pfad, zeiten):
    name = os.path.splitext(os.path.basename(pfad))[0].lower()
    base = re.split(r"[-~ ]", name)[0]
    cs = zeiten.get(base)
    if not cs:
        return None, "Name nicht im Katalog"
    m = re.search(r"(\d\d)\.(\d\d)\.(\d{4})", pfad)
    if m:
        d = "%s-%s-%s" % (m.group(3), m.group(2), m.group(1))
        sel = [c for c in cs if c.startswith(d)]
    else:
        y = re.search(r"/(20\d\d)/", pfad)
        mo = re.search(r"/(\d\d) ?[-.] ", pfad)
        sel = [c for c in cs if (not y or c.startswith(y.group(1))) and (not mo or c[5:7] == mo.group(1))]
    if len(sel) == 1:
        return sel[0], None
    return None, "mehrdeutig" if sel else "kein Treffer mit Ordnerdatum"


def schreibe(pfad, zeit):
    b = open(pfad, "rb").read()
    if b[:2] != b"\xff\xd8":
        raise ValueError("kein JPEG")
    segs = segmente(b)
    ex_seg = next(((m, s, e) for m, s, e in segs if m == 0xE1 and b[s + 4:s + 10] == b"Exif\x00\x00"), None)
    ex = Image.Exif()
    if ex_seg:
        ex.load(b[ex_seg[1] + 4:ex_seg[2]])
    t = zeit[:10].replace("-", ":") + " " + zeit[11:19]
    ex[0x0132] = t
    e = ex.get_ifd(0x8769)
    e[0x9003] = t
    e[0x9004] = t
    payload = ex.tobytes()
    if not payload.startswith(b"Exif\x00\x00"):
        payload = b"Exif\x00\x00" + payload
    seg = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    if ex_seg:
        off, alt = ex_seg[1], b[ex_seg[1]:ex_seg[2]]
    else:
        app0 = next(((m, s, e2) for m, s, e2 in segs if m == 0xE0), None)
        off, alt = (app0[2] if app0 else 2), b""
    neu = b[:off] + seg + b[off + len(alt):]
    tmp = pfad + ".tmp"
    with open(tmp, "wb") as f:
        f.write(neu)
    os.replace(tmp, pfad)
    return {"offset": off, "eingefuegt": len(seg), "entfernt": base64.b64encode(alt).decode()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--katalog", help="Festplatte (Mountpunkt) mit dem Lightroom-Katalog, z. B. /Volumes/Daten 2022")
    ap.add_argument("--fotos", default=os.path.expanduser("~/Pictures/fertige Fotos"))
    ap.add_argument("--anwenden", action="store_true", help="wirklich schreiben (sonst nur Bericht)")
    ap.add_argument("--undo", action="store_true", help="letzten Lauf zurücknehmen")
    a = ap.parse_args()
    if a.undo:
        if not os.path.exists(LOG):
            sys.exit("Kein Protokoll vorhanden.")
        rows = [json.loads(l) for l in open(LOG)]
        lauf = rows[-1]["lauf"]
        n = 0
        for r in reversed([x for x in rows if x["lauf"] == lauf]):
            try:
                b = open(r["pfad"], "rb").read()
                o, n_ein = r["offset"], r["eingefuegt"]
                b = b[:o] + base64.b64decode(r["entfernt"]) + b[o + n_ein:]
                open(r["pfad"], "wb").write(b)
                os.utime(r["pfad"], (r["mtime"], r["mtime"]))
                n += 1
            except Exception as e:
                print("Fehler", r["pfad"], e)
        os.rename(LOG, LOG + ".%s" % lauf)
        print("%d Dateien zurückgesetzt." % n)
        return
    if not a.katalog:
        sys.exit("--katalog angeben")
    zeiten = katalog_zeiten(a.katalog)
    lauf = time.strftime("%Y%m%d-%H%M%S")
    stat = collections.Counter(); offen = []
    log = open(LOG, "a", encoding="utf-8") if a.anwenden else None
    for dp, dn, fn in os.walk(a.fotos):
        dn[:] = [d for d in dn if not d.startswith(".")]
        for f in sorted(fn):
            if f.startswith(".") or not f.lower().endswith((".jpg", ".jpeg")):
                continue
            p = os.path.join(dp, f)
            try:
                b = open(p, "rb").read(262144)
                segs = segmente(b)
                ex = next(((s, e) for m, s, e in segs if m == 0xE1 and b[s + 4:s + 10] == b"Exif\x00\x00"), None)
                if ex and hat_zeit(b[ex[0] + 4:ex[1]]):
                    stat["hat schon Aufnahmezeit"] += 1; continue
            except Exception as e:
                stat["nicht lesbar"] += 1; continue
            z, grund = kandidat(p, zeiten)
            if not z:
                stat["offen: " + grund] += 1; offen.append("%s  (%s)" % (p, grund)); continue
            stat["Zeit aus Katalog ergänzbar"] += 1
            if a.anwenden:
                try:
                    mt = os.path.getmtime(p)
                    info = schreibe(p, z)
                    ts = time.mktime(datetime.strptime(z, "%Y-%m-%dT%H:%M:%S").timetuple())
                    os.utime(p, (ts, ts))
                    log.write(json.dumps({"lauf": lauf, "pfad": p, "mtime": mt, **info}) + "\n"); log.flush()
                except Exception as e:
                    stat["Fehler beim Schreiben"] += 1; print("Fehler", p, e)
    for k, v in sorted(stat.items()):
        print("%6d  %s" % (v, k))
    if offen:
        ziel = os.path.expanduser("~/Desktop/foto_zeit_katalog_offen.txt")
        if not os.path.isdir(os.path.dirname(ziel)):
            ziel = os.path.expanduser("~/foto_zeit_katalog_offen.txt")
        with open(ziel, "w", encoding="utf-8") as f:
            f.write("\n".join(offen) + "\n")
        print("Nicht zuordenbar: %d (Liste: %s)" % (len(offen), ziel))
    if not a.anwenden:
        print("\nProbelauf – nichts geändert. Mit --anwenden schreiben.")


if __name__ == "__main__":
    main()
