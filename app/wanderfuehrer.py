"""Wanderführer (z. B. Rother): Tourtitel aus eigenen GPX-Downloads erkennen.

Ein Buch liegt als ZIP mit GPX-Dateien vor. Daraus merkt sich die App Name, Strecke und
Streckenverlauf jeder Buchtour und erkennt später, welche eigene Tour dazu passt.
"""
import hashlib
import io
import re
import json
import time
import zipfile
from xml.etree import ElementTree as ET

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response

from . import db

router = APIRouter()


def _hav(a, b):
    from . import extras
    return extras._hav(a, b)


def _guide_parse(text, fallback):
    root = ET.fromstring(text)
    loc = lambda el: el.tag.split("}")[-1]
    pts, names = [], []
    for el in root.iter():
        n = loc(el)
        if n == "trkpt" or n == "rtept":
            try:
                pts.append((float(el.get("lat")), float(el.get("lon"))))
            except (TypeError, ValueError):
                pass
        elif n == "name" and (el.text or "").strip():
            names.append(el.text.strip())
    if len(pts) < 3:
        raise ValueError("keine Streckenpunkte")
    step = max(1, len(pts) // 400)
    title = next((x for x in names if not re.fullmatch(r"[\w\- ]*\.gpx", x, re.I)), None) or re.sub(r"\.gpx$", "", fallback, flags=re.I)
    return title, pts[::step] + ([pts[-1]] if step > 1 else [])


def guide_stats(text, pts):
    """Länge (km) aus den Punkten, Aufstieg (m) aus den Höhenangaben der GPX-Datei (None, falls keine vorhanden)."""
    import math
    km = 0.0
    for a, b in zip(pts, pts[1:]):
        dy = (b[0] - a[0]) * 111.2
        dx = (b[1] - a[1]) * 111.2 * math.cos(math.radians((a[0] + b[0]) / 2))
        km += (dx * dx + dy * dy) ** 0.5
    up = None
    try:
        els = []
        for el in ET.fromstring(text).iter():
            if el.tag.split("}")[-1] in ("trkpt", "rtept"):
                for ch in el:
                    if ch.tag.split("}")[-1] == "ele" and ch.text:
                        els.append(float(ch.text))
        if len(els) >= 3:
            sm = [sum(els[max(0, i - 2):i + 3]) / len(els[max(0, i - 2):i + 3]) for i in range(len(els))]
            up, ref = 0.0, sm[0]
            for v in sm[1:]:                       # Schwelle 3 m gegen Rauschen
                if v - ref >= 3:
                    up += v - ref; ref = v
                elif ref - v >= 3:
                    ref = v
    except Exception:  # noqa
        up = None
    return round(km, 2), (round(up) if up is not None else None)


def _seg_dist(p, a, b):
    k = 111000.0
    cx = 0.65  # cos(~50°)
    px, py, ax, ay, bx, by = p[1] * k * cx, p[0] * k, a[1] * k * cx, a[0] * k, b[1] * k * cx, b[0] * k
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    u = 0 if L == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / L))
    return ((px - ax - u * dx) ** 2 + (py - ay - u * dy) ** 2) ** 0.5


def _covered(samples, line, r):
    hit = 0
    for p in samples:
        for i in range(len(line) - 1):
            a = line[i]
            if abs(a[0] - p[0]) > 0.01 or abs(a[1] - p[1]) > 0.015:
                continue
            if _seg_dist(p, a, line[i + 1]) <= r:
                hit += 1; break
    return hit / max(1, len(samples))


def guide_matches(pts):
    gs = db.query("SELECT id,book,title,pts FROM guide_tours")
    if not gs or len(pts) < 5:
        return []
    n = min(40, len(pts))
    samp = [(pts[int(i * (len(pts) - 1) / max(1, n - 1))][0], pts[int(i * (len(pts) - 1) / max(1, n - 1))][1]) for i in range(n)]
    out = []
    for g in gs:
        line = json.loads(g["pts"])
        la, lo = [p[0] for p in line], [p[1] for p in line]
        if min(la) - 0.02 > max(s[0] for s in samp) or max(la) + 0.02 < min(s[0] for s in samp) or min(lo) - 0.03 > max(s[1] for s in samp) or max(lo) + 0.03 < min(s[1] for s in samp):
            continue
        c1 = _covered(samp, line, 80)                       # Anteil meiner Tour auf der Buchtour
        if c1 < 0.6:
            continue
        step = max(1, len(line) // 40)
        c2 = _covered(line[::step], [(p[0], p[1]) for p in pts], 120)   # Anteil der Buchtour, den ich gegangen bin
        if c2 >= 0.5:
            out.append((c1 * c2, g["book"], g["title"]))
    out.sort(reverse=True)
    return [(b, t) for _, b, t in out[:2]]


@router.get("/api/guides")
def api_guides():
    return db.query("SELECT id,book,title FROM guide_tours ORDER BY book,title")


@router.post("/api/guides")
async def api_guides_add(request: Request):
    data = await request.json()
    book = (data.get("book") or "").strip()[:80]
    ok, bad = 0, []
    for it in data.get("items") or []:
        try:
            title, pts = _guide_parse(it.get("gpx", ""), it.get("name", "Tour"))
            km, up = guide_stats(it.get("gpx", ""), pts)
            db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES(?,?,?,?,?)", (book, title[:200], json.dumps([[round(a, 5), round(b, 5)] for a, b in pts]), km, up))
            ok += 1
        except Exception as ex:  # noqa
            bad.append(f"{it.get('name', '?')}: {ex}")
    return {"added": ok, "failed": bad}


# ---------- 3.73.0: Wanderführer als ZIP-Datei hochladen (alle GPX darin, ein Bild darin wird das Titelbild) ----------
ZIP_MAX_BYTES = 60 * 1024 * 1024           # hochgeladene ZIP-Datei
ZIP_MAX_ENTRIES = 1000                     # Einträge in der ZIP
ZIP_MAX_GPX = 20 * 1024 * 1024             # entpackte Größe je GPX-Datei
ZIP_MAX_TOTAL = 400 * 1024 * 1024          # entpackt insgesamt (Schutz vor ZIP-Bomben)
_BILD_RX = re.compile(r"\.(jpe?g|png|webp)$", re.I)


def _zip_skip(name):
    return any(p.startswith(".") or p == "__MACOSX" for p in name.replace("\\", "/").split("/") if p)


def _zip_bild_wahl(namen):
    """Titelbild unter den Dateinamen einer ZIP: Namen mit titel/cover/bild zuerst, dann am wenigsten tief, dann alphabetisch. None ohne Bild."""
    l = [n for n in namen if _BILD_RX.search(n) and not _zip_skip(n)]
    if not l:
        return None
    key = lambda n: (0 if re.search(r"(titel|cover|bild)", n.replace("\\", "/").split("/")[-1], re.I) else 1, n.replace("\\", "/").count("/"), n.lower())
    return sorted(l, key=key)[0]


@router.post("/api/guides/zip")
async def api_guides_zip(book: str = "", file: UploadFile = File(...)):
    raw = await file.read(ZIP_MAX_BYTES + 1)
    if len(raw) > ZIP_MAX_BYTES:
        raise HTTPException(413, f"Die ZIP-Datei ist zu groß (höchstens {ZIP_MAX_BYTES // 1048576} MB)")
    try:
        z = zipfile.ZipFile(io.BytesIO(raw))
    except zipfile.BadZipFile:
        raise HTTPException(400, "Das ist keine ZIP-Datei, die ich lesen kann")
    infos = z.infolist()
    if len(infos) > ZIP_MAX_ENTRIES or sum(i.file_size for i in infos) > ZIP_MAX_TOTAL:
        raise HTTPException(413, "Die ZIP-Datei ist zu umfangreich")
    book = (book or "").strip()[:80] or re.sub(r"(?i)\.zip$", "", (file.filename or "").replace("\\", "/").split("/")[-1]).strip()[:80]
    have = {r["title"] for r in db.query("SELECT title FROM guide_tours WHERE COALESCE(book,'')=?", (book,))}
    ok, schon, bad = 0, 0, []
    for i in sorted((i for i in infos if not i.is_dir() and i.filename.lower().endswith(".gpx") and not _zip_skip(i.filename)), key=lambda i: i.filename.lower()):
        try:
            if i.file_size > ZIP_MAX_GPX:
                raise ValueError("Datei zu groß")
            text = z.read(i).decode("utf-8", "replace")
            title, pts = _guide_parse(text, i.filename.replace("\\", "/").split("/")[-1])
            title = title[:200]
            if title in have:
                schon += 1
                continue
            km, up = guide_stats(text, pts)
            db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES(?,?,?,?,?)", (book, title, json.dumps([[round(a, 5), round(b, 5)] for a, b in pts]), km, up))
            have.add(title)
            ok += 1
        except Exception as ex:  # noqa
            bad.append(f"{i.filename}: {ex}")
    cover = None      # None: kein Bild in der ZIP · True: übernommen · False: Bild nicht lesbar · "vorhanden": das Buch hat schon ein Titelbild
    bn = _zip_bild_wahl([i.filename for i in infos if not i.is_dir()])
    if bn and (ok or schon) and db.one("SELECT 1 FROM guide_tours WHERE COALESCE(book,'')=? LIMIT 1", (book,)):
        if db.one("SELECT 1 FROM guide_cover WHERE book=?", (book,)):
            cover = "vorhanden"
        else:
            try:
                info = z.getinfo(bn)
                if info.file_size > COVER_MAX_BYTES * 5:
                    raise ValueError("Bild zu groß")
                data = _cover_jpeg(z.read(info))
                db.execute("INSERT OR REPLACE INTO guide_cover(book, img, v, ts) VALUES(?,?,?,?)", (book, data, hashlib.sha1(data).hexdigest()[:12], int(time.time())))
                cover = True
            except Exception:  # noqa
                cover = False
    return {"book": book, "added": ok, "existing": schon, "failed": bad, "cover": cover}


# ---------- 3.53.0: Titelbild je Buch ----------
# Der Benutzer wählt das Bild selbst (nie ein Download aus dem Netz). Gespeichert wird ein kleines, vom Server neu kodiertes JPEG
# in der Datenbank (Tabelle guide_cover): kein Dateipfad, also keine Pfadangriffe; Sicherung, Wiederherstellung und Umzug nehmen es von selbst mit.
COVER_MAX_BYTES = 3 * 1024 * 1024          # hochgeladene Datei (die Oberfläche schickt ~400 px, typisch 20–60 kB)
COVER_MAX_PIXELS = 40_000_000
COVER_SIDE = 480                           # längste Seite nach dem Neukodieren (Oberfläche: 400 px; etwas Spielraum, nie größer)


def _book_or_404(book):
    book = (book or "")[:80]
    if not db.one("SELECT 1 FROM guide_tours WHERE COALESCE(book,'')=? LIMIT 1", (book,)):
        raise HTTPException(404, "Buch nicht gefunden")
    return book


def _cover_jpeg(raw):
    """Bild prüfen und neu kodieren: nur echte Bilder (JPEG, PNG, WebP, GIF), Metadaten fallen weg, längste Seite höchstens COVER_SIDE. ValueError sonst."""
    from PIL import Image, ImageOps
    try:
        im = Image.open(io.BytesIO(raw))
        if im.format not in ("JPEG", "PNG", "WEBP", "GIF", "MPO"):
            raise ValueError("Format nicht unterstützt")
        if im.width * im.height > COVER_MAX_PIXELS:
            raise ValueError("Bild zu groß")
        im.load()
    except ValueError:
        raise
    except Exception as e:  # noqa
        raise ValueError(str(e) or "kein Bild")
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    else:
        im = im.convert("RGB")
    im.thumbnail((COVER_SIDE, COVER_SIDE), Image.LANCZOS)
    out = io.BytesIO()
    im.save(out, "JPEG", quality=84, optimize=True)
    return out.getvalue()


def cover_versions():
    """{Buch: Version} für alle Bücher mit Titelbild (für /api/guides/progress und die Wunschliste)."""
    return {r["book"]: r["v"] for r in db.query("SELECT book, v FROM guide_cover")}


@router.get("/api/guides/cover")
def api_guide_cover_get(request: Request, book: str = "", v: str = ""):
    r = db.one("SELECT img, v FROM guide_cover WHERE book=?", ((book or "")[:80],))
    if not r:
        raise HTTPException(404, "Kein Titelbild")
    etag = f'"{r["v"]}"'
    # wie /pic (3.51.0): mit passender Version darf der Browser das Bild behalten, sonst fragt er nach; immer „private“, nie „public“
    h = {"Cache-Control": "private, max-age=31536000, immutable" if v and v == r["v"] else "private, no-cache", "ETag": etag, "X-Content-Type-Options": "nosniff"}
    if etag in (request.headers.get("if-none-match") or ""):
        return Response(status_code=304, headers=h)
    return Response(bytes(r["img"]), media_type="image/jpeg", headers=h)


@router.post("/api/guides/cover")
async def api_guide_cover_put(book: str = "", file: UploadFile = File(...)):
    book = _book_or_404(book)
    raw = await file.read(COVER_MAX_BYTES + 1)
    if len(raw) > COVER_MAX_BYTES:
        raise HTTPException(413, f"Das Bild ist zu groß (höchstens {COVER_MAX_BYTES // 1048576} MB)")
    try:
        data = _cover_jpeg(raw)
    except ValueError:
        raise HTTPException(400, "Das ist keine Bilddatei, die ich lesen kann (JPEG, PNG, WebP oder GIF)")
    v = hashlib.sha1(data).hexdigest()[:12]
    db.execute("INSERT OR REPLACE INTO guide_cover(book, img, v, ts) VALUES(?,?,?,?)", (book, data, v, int(time.time())))
    return {"ok": True, "v": v, "bytes": len(data)}


@router.delete("/api/guides/cover")
def api_guide_cover_del(book: str = ""):
    book = _book_or_404(book)
    db.execute("DELETE FROM guide_cover WHERE book=?", (book,))
    return {"ok": True}


# ---------- 3.56.0: Wanderführer für „Mein Tourentagebuch“ ----------
# Liefert alle Bücher mit Buchtouren genau im Dateiformat des Tagebuchs („Wanderführer exportieren/importieren“ ab Tagebuch 2.13.0,
# js/calc-fuehrer-datei.js): das Tagebuch kann die Antwort unverändert mit FuehrerDatei.lies() lesen. Nur lesend; für Betrachter freigegeben
# (main.VIEWER_GET). Enthält nur, was das Konto für Wanderführer ohnehin sieht: Buchname, Buchtouren (Titel, Länge, Aufstieg, Strecke) und
# je Buchtour die zugeordnete eigene Tour (Datum, Name) aus dem vorhandenen Abgleich (more.api_guides_progress). Keine Fotos, Notizen oder Spuren eigener Touren.
EXPORT_FORMAT, EXPORT_VERSION = "tourentagebuch-wanderfuehrer", 1
EXPORT_MAX_PTS = 400                       # Punkte je Buchtour (wie MAX_BUCH im Tagebuch und wie beim Hochladen gespeichert)
EXPORT_COVER_MAX = 200_000                 # Zeichen der Daten-Adresse (COVER_MAX in calc-fuehrer-datei.js)


def _duenne(pts, mx=EXPORT_MAX_PTS):
    """Höchstens `mx` Punkte: jeder step-te, der letzte bleibt (wie Fuehrer.duenne im Tagebuch)."""
    if len(pts) <= mx:
        return list(pts)
    step = -(-len(pts) // mx)
    out = pts[::step]
    if out[-1] is not pts[-1]:
        out.append(pts[-1])
    return out


def _packe(pts):
    """Strecke gepackt wie Fuehrer.packe im Tagebuch: Grad × 1e5 als ganze Zahlen, je Punkt der Unterschied zum Vorgänger, in Streckenreihenfolge.
    Höhen speichert Meine Touren für Buchtouren nicht – darum ohne „e“ (das Tagebuch kommt ohne Höhen aus)."""
    la = [round(p[0] * 1e5) for p in pts]
    lo = [round(p[1] * 1e5) for p in pts]
    d = lambda a: [v - a[i - 1] if i else v for i, v in enumerate(a)]
    return {"la": d(la), "lo": d(lo)}


def _cover_data(img):
    """Titelbild als Daten-Adresse (JPEG, Base64) innerhalb der Grenze des Tagebuchs; sonst kleiner neu kodiert, notfalls None."""
    import base64
    data = bytes(img)
    for side, q in ((None, None), (400, 80), (300, 70)):
        if side:
            from PIL import Image
            im = Image.open(io.BytesIO(bytes(img))).convert("RGB")
            im.thumbnail((side, side), Image.LANCZOS)
            out = io.BytesIO()
            im.save(out, "JPEG", quality=q, optimize=True)
            data = out.getvalue()
        s = "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
        if len(s) <= EXPORT_COVER_MAX:
            return s
    return None


def _book_id(key):
    """Stabile Kennung je Buch im Format, das das Tagebuch annimmt (^[\\w-]{1,40}$); ein Buchname mit Leerzeichen ginge dort verloren."""
    return "mt-" + hashlib.sha1(("guide-book:" + key).encode("utf-8")).hexdigest()[:12]


@router.get("/api/guides/export")
def api_guides_export(cover: int = 0):
    from datetime import datetime
    from . import config, more
    from .gpxtools import TZ
    done = {x["id"]: x for b in more.api_guides_progress() for x in b["tours"] if x.get("tour")}
    names = {}
    if done:
        ids = sorted({x["tour"] for x in done.values()})
        for i in range(0, len(ids), 500):
            part = ids[i:i + 500]
            for r in db.query(f"SELECT id,name FROM tours WHERE id IN ({','.join('?' * len(part))})", tuple(part)):
                names[r["id"]] = r["name"] or ""
    cv = cover_versions()
    imgs = {r["book"]: r["img"] for r in db.query("SELECT book, img FROM guide_cover")} if cover else {}
    books = {}
    for g in db.query("SELECT id,book,title,pts,km,up FROM guide_tours ORDER BY book,id"):
        books.setdefault(g["book"] or "", []).append(g)
    out = {"format": EXPORT_FORMAT, "version": EXPORT_VERSION, "app": "Meine Touren " + config.VERSION.split(" ")[0],
           "erstellt": datetime.now(TZ).isoformat(timespec="seconds"), "buecher": []}
    for key, gs in books.items():
        e = {"id": _book_id(key), "key": key, "name": key or "(ohne Buch)", "cover_v": cv.get(key), "touren": []}
        for ord_, g in enumerate(gs):
            try:
                line = [(float(p[0]), float(p[1])) for p in json.loads(g["pts"] or "[]")]
            except (TypeError, ValueError, IndexError):
                continue
            line = [p for p in line if abs(p[0]) <= 90 and abs(p[1]) <= 180]
            if len(line) < 3:
                continue                                   # ohne Strecke nicht übertragbar (das Tagebuch verwirft sie auch)
            km = g["km"] if g["km"] is not None else guide_stats("<x/>", line)[0]
            t = {"id": f"t{ord_}", "ord": ord_, "mt_id": g["id"], "title": (g["title"] or "Tour")[:200], "km": round(float(km), 3),
                 "up": round(g["up"]) if g["up"] is not None else None, "f": "", "pts": _packe(_duenne(line))}
            d = done.get(g["id"])
            if d and d.get("ts"):
                t["gewandert"] = [{"datum": datetime.fromtimestamp(d["ts"], tz=TZ).strftime("%Y-%m-%d"), "name": names.get(d["tour"], "")[:200]}]
            e["touren"].append(t)
        if cover and key in imgs:
            c = _cover_data(imgs[key])
            if c:
                e["cover"] = c
        out["buecher"].append(e)
    return out


# nach den festen Pfaden (/api/guides/cover) registriert, sonst fängt {gid} sie ab
@router.delete("/api/guides/{gid}")
def api_guides_del(gid: str):
    if gid.startswith("book:"):
        db.execute("DELETE FROM guide_tours WHERE book=?", (gid[5:],))
    else:
        db.execute("DELETE FROM guide_tours WHERE id=?", (int(gid),))
    db.execute("DELETE FROM guide_cover WHERE book NOT IN (SELECT DISTINCT COALESCE(book,'') FROM guide_tours)")   # 3.53.0: Titelbild verschwindet mit dem Buch
    return {"ok": True}
