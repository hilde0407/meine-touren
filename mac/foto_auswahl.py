#!/usr/bin/env python3
"""foto_auswahl.py – wählt aus einem Lightroom-Katalog die besten Fotos aus und exportiert sie.

WICHTIG: Die externe Festplatte wird ausschließlich GELESEN (Katalog nur mit mode=ro&immutable=1,
Fotos nur geöffnet zum Lesen). Alle Ergebnisse landen im Zielordner (--ziel).

Stufen (jede ist fortsetzbar, mit --zeit N werden sie nach N Sekunden sauber beendet):
  scan     Katalog lesen -> <ziel>/_Arbeit/<platte>/katalog.json
  score    Bewertung (Schärfe, Belichtung, Bildaufbau) der Vorschaubilder -> scores2.jsonl
  select   je Tag beste ~10 %, 5-Sterne immer, Doppelte (gleiches Motiv) raus -> auswahl.json + Kontaktbögen
  export   entwickeln (Kamera-WB, milde Tonwerte, Schärfen) und als JPEG nach <ziel>/Jahr/Monat/Tag
  status   Fortschritt anzeigen
Aufruf:  python3 foto_auswahl.py <stufe> --platte "/Volumes/Daten 2022" --ziel ~/Desktop/Aktivitäten
"""
import argparse, io, json, math, os, sqlite3, sys, time, glob
import multiprocessing as mp

def Pool(n):
    return mp.get_context('spawn').Pool(n)


try:
    import numpy as np
    import cv2
    from PIL import Image, ImageFilter, ImageDraw, ImageOps, ImageCms
except ImportError as e:  # pragma: no cover
    sys.exit("Benötigt numpy, opencv-python, pillow (und rawpy): %s" % e)
try:
    import rawpy
except ImportError:
    rawpy = None

from PIL import ImageFile
ImageFile.MAXBLOCK = 1 << 28
Image.MAX_IMAGE_PIXELS = None
RAWEXT = {"ARW", "DNG", "NEF", "CR2", "CR3", "RAF", "ORF", "RW2"}
JPGEXT = {"JPG", "JPEG", "TIF", "TIFF", "PNG"}


# ---------------------------------------------------------------- Hilfen
def arbeit(a):
    name = os.path.basename(a.platte.rstrip("/")) or "platte"
    d = os.path.join(a.ziel, "_Arbeit", name)
    os.makedirs(d, exist_ok=True)
    return d


def jload(p, default=None):
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def jsave(p, obj):
    t = p + ".tmp"
    with open(t, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    os.replace(t, p)


def lies_jsonl(p):
    out = {}
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            for line in f:
                try:
                    r = json.loads(line)
                    out[r["id"]] = r
                except Exception:
                    pass
    return out


# ---------------------------------------------------------------- scan
def cmd_scan(a):
    w = arbeit(a)
    kat = glob.glob(os.path.join(a.platte, "**", "*.lrcat"), recursive=True)
    kat = [k for k in kat if "/Backups/" not in k and not os.path.basename(k).startswith("._")]
    if not kat:
        sys.exit("Kein Lightroom-Katalog (*.lrcat) gefunden.")
    kat = max(kat, key=os.path.getsize)
    print("Katalog:", kat)
    c = sqlite3.connect("file:%s?mode=ro&immutable=1" % os.path.abspath(kat), uri=True)
    roots = {r[0]: r[1] for r in c.execute("select id_local,absolutePath from AgLibraryRootFolder")}
    q = """select a.id_local,a.captureTime,a.rating,a.pick,a.fileFormat,a.copyName,a.masterImage,a.colorLabels,
                  f.baseName,f.extension,fo.pathFromRoot,fo.rootFolder
           from Adobe_images a join AgLibraryFile f on f.id_local=a.rootFile
           join AgLibraryFolder fo on fo.id_local=f.folder
           where a.fileFormat!='VIDEO'"""
    vol = "/Volumes/" + os.path.basename(a.platte.rstrip("/")) + "/"
    items, fehlt, andere = [], 0, 0
    for (i, ct, rating, pick, fmt, copy, master, lab, base, ext, pf, rf) in c.execute(q):
        if master is not None or copy:      # virtuelle Kopien = gleiche Datei
            continue
        if (pick or 0) < 0:                 # abgelehnt
            continue
        root = roots.get(rf, "")
        if not root.startswith(vol):
            andere += 1
            continue
        p = os.path.join(a.platte, root[len(vol):], pf, base + "." + ext)
        if not os.path.exists(p):
            fehlt += 1
            continue
        if not ct:
            continue
        items.append({"id": i, "t": ct, "r": int(rating or 0), "fmt": fmt, "ext": ext.upper(), "p": p, "n": base})
    items.sort(key=lambda x: x["t"])
    jsave(os.path.join(w, "katalog.json"), {"katalog": kat, "items": items})
    tage = len({x["t"][:10] for x in items})
    print("%d Fotos in %d Tagen, davon %d mit 5 Sternen. Fehlende Dateien: %d, außerhalb der Platte: %d"
          % (len(items), tage, sum(x["r"] == 5 for x in items), fehlt, andere))


# ---------------------------------------------------------------- Vorschau laden
def lade_vorschau(p, ext, maxd=1024):
    """Gibt (PIL-Bild RGB, exif-Bytes|None) zurück – schnell über das eingebettete Vorschaubild."""
    ext = ext.upper()
    if ext in RAWEXT and rawpy is not None:
        with rawpy.imread(p) as r:
            try:
                th = r.extract_thumb()
                if th.format == rawpy.ThumbFormat.JPEG:
                    im = Image.open(io.BytesIO(th.data))
                    im.draft("RGB", (maxd, maxd))
                    im = ImageOps.exif_transpose(im).convert("RGB")
                else:
                    im = Image.fromarray(th.data)
            except Exception:
                rgb = r.postprocess(use_camera_wb=True, half_size=True, output_bps=8)
                im = Image.fromarray(rgb)
    else:
        im = Image.open(p)
        im.draft("RGB", (maxd, maxd))
        im = ImageOps.exif_transpose(im).convert("RGB")
    im.thumbnail((maxd, maxd))
    return im


def bewerte(im):
    g = np.asarray(im.convert("L"), dtype=np.float32)
    h, w = g.shape
    # Schärfe: Laplace-Varianz je Kachel, 90.-Perzentil (scharfes Motiv, unscharfer Hintergrund erlaubt)
    lap = cv2.Laplacian(g, cv2.CV_32F)
    vs = []
    for ty in range(4):
        for tx in range(4):
            t = lap[ty * h // 4:(ty + 1) * h // 4, tx * w // 4:(tx + 1) * w // 4]
            vs.append(float(t.var()))
    vs.sort()
    sharp = vs[int(len(vs) * 0.85)]
    s_sharp = min(1.0, math.log1p(sharp) / math.log1p(400))
    # Belichtung
    m = g.mean() / 255.0
    hi = float((g > 250).mean())
    lo = float((g < 5).mean())
    s_exp = 1.0 - min(1.0, abs(m - 0.42) * 2.0) * 0.6 - min(0.4, hi * 4) - min(0.3, lo * 2)
    s_exp = max(0.0, s_exp)
    contrast = min(1.0, float(g.std()) / 70.0)
    # Bildaufbau (grob): Kantenenergie nahe den Drittelpunkten / Mitte, Horizont-Neigung
    e = cv2.GaussianBlur(np.abs(cv2.Sobel(g, cv2.CV_32F, 1, 0)) + np.abs(cv2.Sobel(g, cv2.CV_32F, 0, 1)), (0, 0), 6)
    tot = float(e.sum()) + 1e-6
    ys, xs = np.mgrid[0:h, 0:w]
    cx = float((e * xs).sum() / tot) / w
    cy = float((e * ys).sum() / tot) / h
    pts = [(a, b) for a in (1 / 3, 0.5, 2 / 3) for b in (1 / 3, 0.5, 2 / 3)]
    dmin = min(math.hypot(cx - a, cy - b) for a, b in pts)
    s_comp = max(0.0, 1.0 - dmin * 3.0)
    # Farbigkeit
    hsv = cv2.cvtColor(np.asarray(im.resize((256, int(256 * h / w) or 1))), cv2.COLOR_RGB2HSV)
    s_col = min(1.0, float(hsv[..., 1].mean()) / 110.0)
    score = 0.45 * s_sharp + 0.25 * s_exp + 0.1 * contrast + 0.12 * s_comp + 0.08 * s_col
    # dHash 16x16 (256 Bit) für Doppelte
    d = cv2.resize(g, (17, 16), interpolation=cv2.INTER_AREA)
    bits = (d[:, 1:] > d[:, :-1]).flatten()
    hs = "".join("1" if b else "0" for b in bits)
    sm = np.asarray(im.resize((160, max(1, int(160 * h / w)))), dtype=np.uint8)
    q = (sm // 64).astype(np.int32)
    hist = np.bincount((q[..., 0] * 16 + q[..., 1] * 4 + q[..., 2]).ravel(), minlength=64).astype(np.float32)
    hist = (hist / hist.sum() * 1000).round().astype(int).tolist()
    return {"hist": hist, "score": round(float(score), 4), "sharp": round(float(s_sharp), 3), "exp": round(float(s_exp), 3), "comp": round(float(s_comp), 3),
            "col": round(float(s_col), 3), "hash": "%064x" % int(hs, 2)}


def _score_worker(it):
    try:
        im = lade_vorschau(it["p"], it["ext"], 800)
        r = bewerte(im)
        r["id"] = it["id"]
        return r
    except Exception as e:
        return {"id": it["id"], "fehler": str(e)[:120]}


def cmd_score(a):
    w = arbeit(a)
    kat = jload(os.path.join(w, "katalog.json"))
    if not kat:
        sys.exit("Erst 'scan' ausführen.")
    pf = os.path.join(w, "scores2.jsonl")
    fertig = lies_jsonl(pf)
    todo = [x for x in kat["items"] if x["id"] not in fertig]
    t0 = time.time()
    print("noch zu bewerten: %d von %d" % (len(todo), len(kat["items"])))
    n = 0
    chunk = 48
    pool = Pool(a.prozesse)
    with open(pf, "a", encoding="utf-8") as out:
        for k in range(0, len(todo), chunk):
            if time.time() - t0 > a.zeit:
                break
            jobs = [(it, pool.apply_async(_score_worker, (it,))) for it in todo[k:k + chunk]]
            kaputt = False
            for it, j in jobs:
                try:
                    r = j.get(timeout=1 if kaputt else 45)
                except Exception as e:      # Absturz/Hänger in einer Datei -> überspringen
                    if kaputt:
                        continue            # nicht abgeschlossen -> beim nächsten Lauf erneut
                    r = {"id": it["id"], "fehler": "hängt/abgestürzt: " + type(e).__name__}
                    kaputt = True
                out.write(json.dumps(r) + "\n")
                n += 1
            out.flush()
            if kaputt:
                pool.terminate()
                pool = Pool(a.prozesse)
    pool.terminate()
    print("bewertet: %d in %.0f s, offen: %d" % (n, time.time() - t0, len(todo) - n))


# ---------------------------------------------------------------- select
def hamming(a, b):
    return bin(int(a, 16) ^ int(b, 16)).count("1")


def cmd_select(a):
    w = arbeit(a)
    kat = jload(os.path.join(w, "katalog.json"))
    sc = lies_jsonl(os.path.join(w, "scores2.jsonl"))
    items = [x for x in kat["items"]]
    offen = [x for x in items if x["r"] < 5 and x["id"] not in sc]
    if offen:
        print("Warnung: %d Fotos noch ohne Bewertung (Stufe score fortsetzen)" % len(offen))
    tage = {}
    for x in items:
        s = sc.get(x["id"], {})
        x["score"] = s.get("score", 0.0)
        x["hash"] = s.get("hash")
        x["hist"] = s.get("hist")
        x["fehler"] = s.get("fehler")
        tage.setdefault(x["t"][:10], []).append(x)
    auswahl, kandidaten = [], []
    for tag, lst in sorted(tages_items(tage)):
        lst.sort(key=lambda x: x["t"])
        n = len(lst)
        fav = [x for x in lst if x["r"] == 5]
        rest = [x for x in lst if x["r"] < 5 and x.get("hash") and not x["fehler"] and x["score"] >= a.minscore]
        # Doppelte: Serien (zeitlich nah + ähnlicher Hash) -> nur das beste behalten; Serien mit 5-Stern: Rest raus
        def aehnlich(x, y):
            if not (x.get("hash") and y.get("hash")):
                return False
            dt = abs(_sek(x["t"]) - _sek(y["t"]))
            if dt > a.fenster:
                return False
            if hamming(x["hash"], y["hash"]) <= a.hamming:
                return True
            hx, hy = x.get("hist"), y.get("hist")      # Farbverteilung (Panorama-Serien, Serienbilder)
            if hx and hy:
                ov = sum(min(p, q) for p, q in zip(hx, hy)) / 1000.0
                return ov >= a.histo
            return False
        rest.sort(key=lambda x: -x["score"])
        beh = []
        for x in rest:
            if any(aehnlich(x, y) for y in beh) or any(aehnlich(x, y) for y in fav):
                continue
            beh.append(x)
        ziel_n = max(len(fav), math.ceil(n * a.anteil))
        plus = max(0, ziel_n - len(fav))
        auto = beh[:plus]
        # Kandidaten für die Sichtung: die nächsten besten über das Soll hinaus
        extra = beh[plus:plus + max(2, plus)]
        for x in fav:
            auswahl.append({**_kurz(x), "grund": "5 Sterne"})
        for x in auto:
            auswahl.append({**_kurz(x), "grund": "Auto"})
        for x in extra:
            kandidaten.append({**_kurz(x), "grund": "Kandidat"})
    jsave(os.path.join(w, "auswahl.json"), {"auswahl": auswahl, "kandidaten": kandidaten})
    print("Auswahl: %d Fotos (davon %d mit 5 Sternen, %d automatisch), %d weitere Kandidaten, %d Tage"
          % (len(auswahl), sum(x["grund"] == "5 Sterne" for x in auswahl),
             sum(x["grund"] == "Auto" for x in auswahl), len(kandidaten), len(tage)))
    if a.sheets:
        kontaktboegen(a, w, auswahl, kandidaten)


def tages_items(d):
    return list(d.items())


def _sek(t):
    return time.mktime(time.strptime(t[:19], "%Y-%m-%dT%H:%M:%S"))


def _kurz(x):
    return {k: x[k] for k in ("id", "t", "r", "p", "ext", "n", "score") if k in x}


def kontaktboegen(a, w, auswahl, kandidaten):
    d = os.path.join(w, "kontakt")
    os.makedirs(d, exist_ok=True)
    tage = {}
    for x in auswahl:
        if x["grund"] == "Auto":
            tage.setdefault(x["t"][:10], []).append(x)
    for x in kandidaten:
        tage.setdefault(x["t"][:10], []).append(x)
    TH, COLS = 330, 5
    n = 0
    for tag, lst in sorted(tages_items(tage)):
        out = os.path.join(d, tag + ".jpg")
        if os.path.exists(out):
            continue
        lst = sorted(lst, key=lambda x: x["t"])[:25]
        rows = math.ceil(len(lst) / COLS)
        sheet = Image.new("RGB", (COLS * TH, rows * (TH + 22)), (30, 30, 30))
        dr = ImageDraw.Draw(sheet)
        for i, x in enumerate(lst):
            try:
                im = lade_vorschau(x["p"], x["ext"], TH)
                im = ImageOps.contain(im, (TH - 6, TH - 6))
                px, py = (i % COLS) * TH, (i // COLS) * (TH + 22)
                sheet.paste(im, (px + 3, py + 3))
                dr.text((px + 4, py + TH), "%d %s %s %.2f" % (x["id"], x["t"][11:16], "A" if x["grund"] == "Auto" else "K", x["score"]),
                        fill=(255, 255, 0) if x["grund"] == "Auto" else (140, 220, 255))
            except Exception:
                pass
        sheet.save(out, quality=82)
        n += 1
    print("Kontaktbögen neu: %d (%s)" % (n, d))


# ---------------------------------------------------------------- export
def srgb_icc():
    return ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()


def entwickle(p, ext):
    ext = ext.upper()
    if ext in RAWEXT and rawpy is not None:
        with rawpy.imread(p) as r:
            rgb = r.postprocess(use_camera_wb=True, output_bps=8, no_auto_bright=False, auto_bright_thr=0.005,
                                highlight_mode=rawpy.HighlightMode.Blend, user_flip=None)
            try:
                th = r.extract_thumb()
                ex = Image.open(io.BytesIO(th.data)).getexif() if th.format == rawpy.ThumbFormat.JPEG else None
            except Exception:
                ex = None
        im = Image.fromarray(rgb)
    else:
        im = Image.open(p)
        ex = im.getexif()
        im = ImageOps.exif_transpose(im).convert("RGB")
    # milder Kontrast + Schärfen
    xs = np.arange(256, dtype=np.float32) / 255.0
    lut = (np.clip(xs + 0.12 * (xs - 0.5) * (1 - np.abs(2 * xs - 1)), 0, 1) * 255 + 0.5).astype(np.uint8)   # sanfte S-Kurve
    arr = lut[np.asarray(im)]
    del im
    im = Image.fromarray(arr)
    im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))
    return im, ex


def baue_exif(ex, t, size, gps=None):
    out = Image.Exif()
    if ex is not None:
        for k in (0x010F, 0x0110, 0x0131):
            v = ex.get(k)
            if v:
                out[k] = v
        ifd = ex.get_ifd(0x8769)
        for k in (0x829A, 0x829D, 0x8827, 0x920A, 0xA434, 0x9204, 0x9207, 0x9209, 0x8822):
            if k in ifd:
                out.get_ifd(0x8769)[k] = ifd[k]
    d = t[:10].replace("-", ":") + " " + t[11:19]
    out[0x0132] = d
    e = out.get_ifd(0x8769)
    e[0x9003] = d
    e[0x9004] = d
    e[0xA002], e[0xA003] = size
    out[0x0112] = 1
    if gps:
        lat, lon, alt = gps
        g = out.get_ifd(0x8825)
        g[1] = "N" if lat >= 0 else "S"
        g[2] = _dms(abs(lat))
        g[3] = "E" if lon >= 0 else "W"
        g[4] = _dms(abs(lon))
        if alt is not None:
            g[5] = 0 if alt >= 0 else 1
            g[6] = abs(alt)
    return out


def _dms(v):
    d = int(v)
    m = int((v - d) * 60)
    s = ((v - d) * 60 - m) * 60
    return (float(d), float(m), round(s, 4))


def _export_worker(args):
    x, ziel, q, gps = args
    t = x["t"]
    d = os.path.join(ziel, t[0:4], t[5:7], t[8:10])
    out = os.path.join(d, x["n"] + ".jpg")
    if os.path.exists(out):
        return x["id"], "vorhanden"
    try:
        os.makedirs(d, exist_ok=True)
        im, ex = entwickle(x["p"], x["ext"])
        exif = baue_exif(ex, t, im.size, gps)
        tmp = out + ".part"
        im.save(tmp, "JPEG", quality=q, subsampling=0, optimize=True, dpi=(300, 300), exif=exif.tobytes(), icc_profile=srgb_icc())
        os.replace(tmp, out)
        ts = _sek(t)
        os.utime(out, (ts, ts))
        return x["id"], "ok"
    except Exception as e:
        return x["id"], "fehler: %s" % str(e)[:100]


def cmd_export(a):
    w = arbeit(a)
    sel = jload(os.path.join(w, "auswahl.json"))
    if not sel:
        sys.exit("Erst 'select' ausführen.")
    ids = None
    if a.nur:
        ids = {int(i) for i in a.nur.split(",")}
    gpsf = jload(os.path.join(w, "gps.json"), {})
    lst = list(sel["auswahl"])
    extra = jload(os.path.join(w, "sichtung.json"), {"nimm": []})
    nimm = set(extra.get("nimm", []))
    lst += [k for k in sel["kandidaten"] if k["id"] in nimm]
    drop = set(extra.get("raus", []))
    lst = [x for x in lst if x["id"] not in drop and (ids is None or x["id"] in ids)]
    ziel = a.ziel
    jobs = [(x, ziel, a.qualitaet, tuple(gpsf[str(x["id"])]) if str(x["id"]) in gpsf else None) for x in lst]
    t0 = time.time()
    ok = fehl = vor = 0
    chunk = 16
    with Pool(a.prozesse) as pool:
        for k in range(0, len(jobs), chunk):
            if time.time() - t0 > a.zeit:
                break
            for i, st in pool.map(_export_worker, jobs[k:k + chunk]):
                if st == "ok":
                    ok += 1
                elif st == "vorhanden":
                    vor += 1
                else:
                    fehl += 1
                    print(i, st)
    print("exportiert: %d, schon vorhanden: %d, Fehler: %d (von %d, %.0f s)" % (ok, vor, fehl, len(jobs), time.time() - t0))


def cmd_status(a):
    w = arbeit(a)
    kat = jload(os.path.join(w, "katalog.json"))
    sc = lies_jsonl(os.path.join(w, "scores2.jsonl"))
    print("Fotos im Katalog:", len(kat["items"]) if kat else "-", "| bewertet:", len(sc))
    sel = jload(os.path.join(w, "auswahl.json"))
    if sel:
        print("Auswahl:", len(sel["auswahl"]), "| Kandidaten:", len(sel["kandidaten"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("stufe", choices=["scan", "score", "select", "export", "status"])
    ap.add_argument("--platte", required=True, help='Mountpunkt der Festplatte, z. B. "/Volumes/Daten 2022"')
    ap.add_argument("--ziel", default=os.path.expanduser("~/Desktop/Aktivitäten"))
    ap.add_argument("--zeit", type=int, default=150, help="max. Laufzeit in Sekunden")
    ap.add_argument("--prozesse", type=int, default=2, help="parallele Prozesse (Export braucht ~1 GB RAM je Prozess)")
    ap.add_argument("--anteil", type=float, default=0.10)
    ap.add_argument("--minscore", type=float, default=0.38)
    ap.add_argument("--hamming", type=int, default=70, help="max. Hash-Abstand (von 256) für 'gleiches Motiv'")
    ap.add_argument("--histo", type=float, default=0.86, help="Überlappung der Farbhistogramme (0-1) für Serien")
    ap.add_argument("--fenster", type=int, default=1800, help="Sekunden, in denen ähnliche Bilder als Serie gelten")
    ap.add_argument("--sheets", action="store_true", help="Kontaktbögen erzeugen (select)")
    ap.add_argument("--qualitaet", type=int, default=92)
    ap.add_argument("--nur", help="export: nur diese Katalog-IDs (kommagetrennt)")
    a = ap.parse_args()
    {"scan": cmd_scan, "score": cmd_score, "select": cmd_select, "export": cmd_export, "status": cmd_status}[a.stufe](a)


if __name__ == "__main__":
    main()
