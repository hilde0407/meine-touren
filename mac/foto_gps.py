#!/usr/bin/env python3
"""foto_gps.py – ergänzt GPS-Koordinaten in den ausgewählten Fotos (Ordner Aktivitäten/Jahr/Monat/Tag) aus den Touren von „Meine Touren“.

Die Aufnahmezeit jedes Fotos wird mit den Tourzeiten verglichen; liegt sie in einer Tour (± Toleranz), wird die Position zu diesem
Zeitpunkt aus der gespeicherten Strecke interpoliert und als GPS in den EXIF-Kopf geschrieben. Fotos, die schon GPS haben, bleiben
unberührt. Nur der EXIF-Kopf wird geändert, das Bild selbst bleibt byte-identisch. Rückgängig: --undo.

  python3 foto_gps.py                       # Probelauf: nur Bericht
  python3 foto_gps.py --anwenden
  python3 foto_gps.py --undo

Optionen: --fotos ORDNER (Standard ~/Desktop/Aktivitäten)  --daten ORDNER (Standard ~/Meine-Touren-Daten/users/<Benutzer>)
          --benutzer volker  --toleranz 600 (Sekunden vor/nach der Tour)  --zeitzone Europe/Berlin
"""
import argparse, base64, bisect, collections, glob, json, os, sqlite3, struct, sys, time
from datetime import datetime
try:
    from zoneinfo import ZoneInfo
except ImportError:
    sys.exit("Python 3.9 oder neuer nötig")
try:
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
except ImportError:
    sys.exit("Pillow fehlt:  pip3 install pillow")

LOG = os.path.expanduser("~/.foto_gps_log.jsonl")


def segmente(b):
    segs, o = [], 2
    while o + 4 <= len(b) and b[o] == 0xFF:
        m = b[o + 1]
        if m in (0xDA, 0xD9):
            break
        ln = struct.unpack(">H", b[o + 2:o + 4])[0]
        segs.append((m, o, o + 2 + ln))
        o += 2 + ln
    return segs


def lade_touren(daten):
    c = sqlite3.connect("file:%s?mode=ro&immutable=1" % os.path.join(daten, "komoot_hub.sqlite"), uri=True)
    rows = c.execute("select id,start_ts,end_ts from tours where start_ts is not null").fetchall()
    c.close()
    tours = sorted((s, e or s, str(i)) for i, s, e in rows)
    return tours, os.path.join(daten, "cache", "coords")


_cache = {}


def strecke(coords, tid):
    if tid in _cache:
        return _cache[tid]
    f = os.path.join(coords, tid + ".json")
    pts = None
    if os.path.exists(f):
        try:
            pts = [p for p in json.load(open(f)) if len(p) >= 4 and p[0] is not None and p[1] is not None and p[3] is not None]
        except Exception:
            pts = None
    if len(_cache) > 40:
        _cache.clear()
    _cache[tid] = pts
    return pts


def position(pts, start, ts):
    """Interpolierte (lat, lng) zum Zeitpunkt ts (Unix); außerhalb der Aufzeichnung der nächste Endpunkt."""
    ms = (ts - start) * 1000
    ts_list = [p[3] for p in pts]
    i = bisect.bisect_left(ts_list, ms)
    if i <= 0:
        return pts[0][0], pts[0][1]
    if i >= len(pts):
        return pts[-1][0], pts[-1][1]
    a, b = pts[i - 1], pts[i]
    d = (b[3] - a[3]) or 1
    f = (ms - a[3]) / d
    return a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f


def tour_fuer(tours, starts, ts, tol):
    best = None
    i = bisect.bisect_right(starts, ts + tol)
    for s, e, tid in tours[max(0, i - 30):i]:
        if s - tol <= ts <= e + tol:
            innen = s <= ts <= e
            abst = 0 if innen else min(abs(ts - s), abs(ts - e))
            if best is None or abst < best[0]:
                best = (abst, s, e, tid)
    return best


def dms(v):
    v = abs(v)
    d = int(v); m = int((v - d) * 60); s = ((v - d) * 60 - m) * 60
    return (float(d), float(m), round(s, 4))


def lies(pfad):
    b = open(pfad, "rb").read(262144)
    if b[:2] != b"\xff\xd8":
        return None, None
    segs = segmente(b)
    ex_seg = next(((s, e) for m, s, e in segs if m == 0xE1 and b[s + 4:s + 10] == b"Exif\x00\x00"), None)
    if not ex_seg:
        return None, None
    ex = Image.Exif(); ex.load(b[ex_seg[0] + 4:ex_seg[1]])
    t = ex.get_ifd(0x8769).get(36867) or ex.get(0x0132)
    gps = ex.get_ifd(0x8825)
    return t, bool(gps.get(2) and gps.get(4))


def gps_von(pfad):
    b = open(pfad, "rb").read(262144)
    segs = segmente(b)
    ex_seg = next(((s, e) for m, s, e in segs if m == 0xE1 and b[s + 4:s + 10] == b"Exif\x00\x00"), None)
    if not ex_seg:
        return None
    ex = Image.Exif(); ex.load(b[ex_seg[0] + 4:ex_seg[1]])
    g = ex.get_ifd(0x8825)
    try:
        la = sum(float(x) / 60 ** i for i, x in enumerate(g[2])) * (1 if g[1] == "N" else -1)
        lo = sum(float(x) / 60 ** i for i, x in enumerate(g[4])) * (1 if g[3] == "E" else -1)
        return la, lo
    except Exception:
        return None


def orte_lesen(datei):
    """Zeilen 'JJJJ-MM-TT;Breite;Länge' (oder 'JJJJ-MM;…' für einen ganzen Monat bzw. 'JJJJ;…')."""
    out = {}
    if datei and os.path.exists(datei):
        for z in open(datei, encoding="utf-8"):
            t = [x.strip().replace(",", ".") for x in z.replace("\t", ";").split(";")]
            if len(t) >= 3 and t[0][:1].isdigit():
                try:
                    out[t[0]] = (float(t[1]), float(t[2]))
                except ValueError:
                    pass
    return out


def schreibe(pfad, lat, lng):
    b = open(pfad, "rb").read()
    segs = segmente(b)
    ex_seg = next(((m, s, e) for m, s, e in segs if m == 0xE1 and b[s + 4:s + 10] == b"Exif\x00\x00"), None)
    ex = Image.Exif()
    if ex_seg:
        ex.load(b[ex_seg[1] + 4:ex_seg[2]])
    g = ex.get_ifd(0x8825)
    g[1] = "N" if lat >= 0 else "S"; g[2] = dms(lat)
    g[3] = "E" if lng >= 0 else "W"; g[4] = dms(lng)
    g[0] = b"\x02\x03\x00\x00"
    payload = ex.tobytes()
    if not payload.startswith(b"Exif\x00\x00"):
        payload = b"Exif\x00\x00" + payload
    seg = b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload
    if ex_seg:
        off, alt = ex_seg[1], b[ex_seg[1]:ex_seg[2]]
    else:
        app0 = next(((m, s, e2) for m, s, e2 in segs if m == 0xE0), None)
        off, alt = (app0[2] if app0 else 2), b""
    tmp = pfad + ".tmp"
    with open(tmp, "wb") as f:
        f.write(b[:off] + seg + b[off + len(alt):])
    os.replace(tmp, pfad)
    return {"offset": off, "eingefuegt": len(seg), "entfernt": base64.b64encode(alt).decode()}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fotos", default=os.path.expanduser("~/Desktop/Aktivitäten"))
    ap.add_argument("--daten")
    ap.add_argument("--benutzer", default="volker")
    ap.add_argument("--toleranz", type=int, default=600)
    ap.add_argument("--zeitzone", default="Europe/Berlin")
    ap.add_argument("--orte", help="Datei mit Zeilen JJJJ-MM-TT;Breite;Länge für Tage ohne Tour (auch JJJJ-MM oder JJJJ)")
    ap.add_argument("--tagesort", action="store_true", help="Fotos ohne Tour bekommen die mittlere Position der Fotos desselben Tagesordners, die GPS haben")
    ap.add_argument("--anwenden", action="store_true")
    ap.add_argument("--zeit", type=int, default=0, help="nach N Sekunden sauber beenden (erneut starten setzt fort)")
    ap.add_argument("--log")
    ap.add_argument("--undo", action="store_true")
    a = ap.parse_args()
    global LOG
    if a.log:
        LOG = a.log
    if a.undo:
        rows = [json.loads(l) for l in open(LOG)]
        lauf = rows[-1]["lauf"]; n = 0
        for r in reversed([x for x in rows if x["lauf"] == lauf]):
            b = open(r["pfad"], "rb").read()
            o = r["offset"]
            open(r["pfad"], "wb").write(b[:o] + base64.b64decode(r["entfernt"]) + b[o + r["eingefuegt"]:])
            os.utime(r["pfad"], (r["mtime"], r["mtime"])); n += 1
        os.rename(LOG, LOG + "." + lauf)
        print("%d Dateien zurückgesetzt." % n)
        return
    daten = a.daten or os.path.expanduser("~/Meine-Touren-Daten/users/" + a.benutzer)
    tours, coords = lade_touren(daten)
    starts = [t[0] for t in tours]
    tz = ZoneInfo(a.zeitzone)
    lauf = time.strftime("%Y%m%d-%H%M%S")
    st = collections.Counter(); keine = []
    log = open(LOG, "a", encoding="utf-8") if a.anwenden else None
    t0 = time.time()
    orte = orte_lesen(a.orte)
    offen = []                                   # (Pfad, Ordner, Tag) ohne Tour
    for dp, dn, fn in os.walk(a.fotos):
        dn[:] = [d for d in dn if not d.startswith(".") and d not in ("_Arbeit", "Lightroom")]
        for f in sorted(fn):
            if f.startswith(".") or not f.lower().endswith((".jpg", ".jpeg")):
                continue
            if a.zeit and time.time() - t0 > a.zeit:
                st["zeitlimit erreicht – bitte erneut starten"] += 1; break
            p = os.path.join(dp, f)
            try:
                t, hat = lies(p)
            except Exception:
                st["nicht lesbar"] += 1; continue
            if hat:
                st["hat schon GPS"] += 1; continue
            if not t:
                st["ohne Aufnahmezeit"] += 1; continue
            try:
                ts = int(datetime.strptime(t.strip()[:19], "%Y:%m:%d %H:%M:%S").replace(tzinfo=tz).timestamp())
            except ValueError:
                st["Zeit nicht lesbar"] += 1; continue
            b = tour_fuer(tours, starts, ts, a.toleranz)
            if not b:
                offen.append((p, dp, datetime.fromtimestamp(ts, tz).strftime("%Y-%m-%d"))); continue
            pts = strecke(coords, b[3])
            if not pts or len(pts) < 2:
                st["Tour ohne gespeicherte Strecke"] += 1; keine.append(p + "  (Tour %s ohne Strecke)" % b[3]); continue
            lat, lng = position(pts, b[1], ts)
            st["GPS ergänzbar"] += 1
            if a.anwenden:
                try:
                    mt = os.path.getmtime(p)
                    info = schreibe(p, lat, lng)
                    os.utime(p, (mt, mt))
                    log.write(json.dumps({"lauf": lauf, "pfad": p, "mtime": mt, **info}) + "\n"); log.flush()
                except Exception as e:
                    st["Fehler beim Schreiben"] += 1; print("Fehler", p, e)
    if offen:      # Ersatzposition: Tagesliste (--orte) bzw. Mittel der GPS-Fotos des Tagesordners (--tagesort)
        mitte = {}
        if a.tagesort:
            for ordner in {o[1] for o in offen}:
                pts = []
                for f in os.listdir(ordner):
                    if f.lower().endswith((".jpg", ".jpeg")) and not f.startswith("."):
                        try:
                            g = gps_von(os.path.join(ordner, f))
                        except Exception:
                            g = None
                        if g:
                            pts.append(g)
                if pts:
                    pts.sort()
                    mitte[ordner] = (sorted(x[0] for x in pts)[len(pts) // 2], sorted(x[1] for x in pts)[len(pts) // 2])
        for p, ordner, tag in offen:
            pos = orte.get(tag) or orte.get(tag[:7]) or orte.get(tag[:4]) or mitte.get(ordner)
            if not pos:
                st["keine Tour zur Aufnahmezeit"] += 1; keine.append(p); continue
            st["GPS aus Tagesort/Liste ergänzbar"] += 1
            if a.anwenden:
                try:
                    mt = os.path.getmtime(p)
                    info = schreibe(p, pos[0], pos[1])
                    os.utime(p, (mt, mt))
                    log.write(json.dumps({"lauf": lauf, "pfad": p, "mtime": mt, **info}) + "\n"); log.flush()
                except Exception as e:
                    st["Fehler beim Schreiben"] += 1; print("Fehler", p, e)
    for k, v in sorted(st.items()):
        print("%6d  %s" % (v, k))
    if keine:
        z = os.path.join(a.fotos, "ohne_gps.txt")
        try:
            open(z, "w", encoding="utf-8").write("\n".join(keine) + "\n")
            print("Liste der Fotos ohne GPS:", z)
        except OSError:
            pass
    if not a.anwenden:
        print("\nProbelauf – nichts geändert. Mit --anwenden schreiben.")


if __name__ == "__main__":
    main()
