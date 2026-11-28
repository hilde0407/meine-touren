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


# ---------- 3.74.0: gemeinsame Helfer (Namen, Ordner) ----------
MAX_BOOK, MAX_TITLE, MAX_FOLDER = 80, 200, 60
OHNE_ORDNER = "Ohne Ordner"


def _clean(s):
    return re.sub(r"\s+", " ", str(s if s is not None else "")).strip()


def _key(s):
    """Vergleichsschlüssel für Namen: ohne Groß-/Kleinschreibung und doppelte Leerzeichen (wie schluessel() im Tagebuch)."""
    return _clean(s).casefold()


def _natur(s):
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", _key(s))]


def _existing_book(name):
    """Gespeicherter Buchname, der zu `name` passt (ohne Rücksicht auf Groß-/Kleinschreibung), sonst None."""
    k = _key(name)
    for r in db.query("SELECT DISTINCT COALESCE(book,'') b FROM guide_tours"):
        if _key(r["b"]) == k:
            return r["b"]
    return None


@router.get("/api/guides")
def api_guides():
    return db.query("SELECT id,book,title FROM guide_tours ORDER BY book,title")


@router.post("/api/guides")
async def api_guides_add(request: Request):
    data = await request.json()
    book = _clean(data.get("book"))[:MAX_BOOK]
    ex_ = _existing_book(book)
    if ex_ is not None:
        book = ex_                                         # 3.74.0: ein vorhandenes Buch gilt ohne Rücksicht auf Groß-/Kleinschreibung (kein zweites Buch „rother taunus“)
    da = [(_key(r["title"]), r["km"]) for r in db.query("SELECT title,km FROM guide_tours WHERE COALESCE(book,'')=?", (book,))]
    ok, schon, bad = 0, 0, []
    for it in data.get("items") or []:
        try:
            title, pts = _guide_parse(it.get("gpx", ""), it.get("name", "Tour"))
            km, up = guide_stats(it.get("gpx", ""), pts)
            title = title[:MAX_TITLE]
            if any(k == _key(title) and t is not None and abs(t - km) < 0.05 for k, t in da):
                schon += 1                                 # 3.74.0: gleicher Titel und gleiche Länge (auf 50 m) zählt nicht doppelt (wie im Tagebuch)
                continue
            db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES(?,?,?,?,?)", (book, title, json.dumps([[round(a, 5), round(b, 5)] for a, b in pts]), km, up))
            da.append((_key(title), km))
            ok += 1
        except Exception as ex:  # noqa
            bad.append(f"{it.get('name', '?')}: {ex}")
    return {"added": ok, "schon": schon, "failed": bad}


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
    book = _clean(book)[:MAX_BOOK] or _clean(re.sub(r"(?i)\.zip$", "", (file.filename or "").replace("\\", "/").split("/")[-1]))[:MAX_BOOK]
    ex_ = _existing_book(book)
    if ex_ is not None:
        book = ex_                                         # 3.74.0: wie beim GPX-Upload: vorhandenes Buch ohne Rücksicht auf Groß-/Kleinschreibung
    have = [(_key(r["title"]), r["km"]) for r in db.query("SELECT title,km FROM guide_tours WHERE COALESCE(book,'')=?", (book,))]
    ok, schon, bad = 0, 0, []
    for i in sorted((i for i in infos if not i.is_dir() and i.filename.lower().endswith(".gpx") and not _zip_skip(i.filename)), key=lambda i: i.filename.lower()):
        try:
            if i.file_size > ZIP_MAX_GPX:
                raise ValueError("Datei zu groß")
            text = z.read(i).decode("utf-8", "replace")
            title, pts = _guide_parse(text, i.filename.replace("\\", "/").split("/")[-1])
            title = title[:MAX_TITLE]
            km, up = guide_stats(text, pts)
            if any(k == _key(title) and h is not None and abs(h - km) < 0.05 for k, h in have):
                schon += 1                                 # 3.74.0: gleiche Doppel-Prüfung wie beim GPX-Upload (Titel und Länge auf 50 m)
                continue
            db.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES(?,?,?,?,?)", (book, title, json.dumps([[round(a, 5), round(b, 5)] for a, b in pts]), km, up))
            have.append((_key(title), km))
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
    return {"book": book, "added": ok, "existing": schon, "schon": schon, "failed": bad, "cover": cover}


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
    ordner = book_folders()
    books = {}
    for g in db.query("SELECT id,book,title,pts,km,up FROM guide_tours ORDER BY book,id"):
        books.setdefault(g["book"] or "", []).append(g)
    out = {"format": EXPORT_FORMAT, "version": EXPORT_VERSION, "app": "Meine Touren " + config.VERSION.split(" ")[0],
           "erstellt": datetime.now(TZ).isoformat(timespec="seconds"), "buecher": []}
    for key, gs in books.items():
        e = {"id": _book_id(key), "key": key, "name": key or "(ohne Buch)", "cover_v": cv.get(key), "touren": []}
        if ordner.get(key):
            e["ordner"] = ordner[key]                      # 3.74.0: zusätzliches Feld (das Tagebuch ignoriert unbekannte Felder; ein Import in Meine Touren legt den Ordner für neue Bücher an)
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


# ---------- 3.74.0: Ordner für Bücher, Umbenennen, Verschieben ----------
# Wie „Geplante Touren“ im Tagebuch (js/calc-ordner.js, ab 2.25.0): Ordner enthalten Bücher; ein Buch liegt in höchstens einem Ordner (fehlt = „Ohne Ordner“).
# Namen sind ohne Rücksicht auf Groß-/Kleinschreibung und doppelte Leerzeichen eindeutig. Auch leere Ordner bleiben (Tabelle guide_folders); „Ordner löschen“ löscht nie ein
# Buch: die Bücher darin kommen zurück nach „Ohne Ordner“. Beides liegt in der Datenbank und damit in jeder Sicherung. Schreiben darf nur der Besitzer (Betrachter: nur GET).
def _fehler(code, text):
    raise HTTPException(code, text)


def _pruefe_name(name, was, maxlen):
    n = _clean(name)
    if not n:
        _fehler(400, "Der Name ist leer")
    if len(n) > maxlen:
        _fehler(400, f"Der Name ist zu lang (höchstens {maxlen} Zeichen)")
    return n


def _pruefe_ordner(name, selbst=None):
    n = _pruefe_name(name, "Ordner", MAX_FOLDER)
    if _key(n) == _key(OHNE_ORDNER):
        _fehler(400, f"„{OHNE_ORDNER}“ ist kein Ordnername")
    if any(k != (_key(selbst) if selbst is not None else None) and k == _key(n) for k in _folder_names()):
        _fehler(409, f"Einen Ordner „{n}“ gibt es schon")
    return n


def _folder_names():
    """{Schlüssel: Name} aller Ordner (Liste und Ordner, die ein Buch trägt)."""
    m = {r["k"]: r["name"] or r["k"] for r in db.query("SELECT k,name FROM guide_folders")}
    for r in db.query("SELECT DISTINCT fk FROM guide_book_folder"):
        m.setdefault(r["fk"], r["fk"])
    return m


def folder_list():
    """Alle Ordnernamen, natürlich sortiert (2 vor 10)."""
    return sorted(_folder_names().values(), key=_natur)


def book_folders():
    """{Buchname (gespeichert): Ordnername} für Bücher, die es noch gibt."""
    names = _folder_names()
    have = {r["b"] for r in db.query("SELECT DISTINCT COALESCE(book,'') b FROM guide_tours")}
    return {r["book"]: names.get(r["fk"], r["fk"]) for r in db.query("SELECT book,fk FROM guide_book_folder") if r["book"] in have}


def _tidy():
    """Verwaiste Reste entfernen: Titelbild und Ordnerzuordnung eines Buchs, das keine Buchtour mehr hat, und Wunschlisten-Einträge gelöschter Buchtouren."""
    db.execute("DELETE FROM guide_cover WHERE book NOT IN (SELECT DISTINCT COALESCE(book,'') FROM guide_tours)")
    db.execute("DELETE FROM guide_book_folder WHERE book NOT IN (SELECT DISTINCT COALESCE(book,'') FROM guide_tours)")
    db.execute("DELETE FROM wishlist WHERE gid NOT IN (SELECT id FROM guide_tours)")


@router.get("/api/guides/folders")
def api_guide_folders():
    return {"folders": folder_list()}


@router.post("/api/guides/folders")
def api_guide_folder_new(body: dict):
    n = _pruefe_ordner(body.get("name"))
    db.execute("INSERT INTO guide_folders(k,name) VALUES(?,?)", (_key(n), n))
    return {"ok": True, "name": n}


@router.post("/api/guides/folders/rename")
def api_guide_folder_rename(body: dict):
    alt = _clean(body.get("name"))
    names = _folder_names()
    if _key(alt) not in names:
        _fehler(404, "Ordner nicht gefunden")
    n = _pruefe_ordner(body.get("new"), selbst=alt)
    ka, kn = _key(alt), _key(n)
    with db.cur() as c:
        c.execute("DELETE FROM guide_folders WHERE k=?", (ka,))
        c.execute("INSERT OR REPLACE INTO guide_folders(k,name) VALUES(?,?)", (kn, n))
        if ka != kn:
            c.execute("UPDATE guide_book_folder SET fk=? WHERE fk=?", (kn, ka))
    return {"ok": True, "name": n}


@router.post("/api/guides/folders/move")
def api_guide_folder_move(body: dict):
    """Bücher in einen Ordner legen (`folder` = Name, ein neuer Name legt den Ordner an) oder aus dem Ordner nehmen (`folder` leer/null)."""
    books = body.get("books")
    if not isinstance(books, list) or not books:
        _fehler(400, "Kein Buch gewählt")
    have = {r["b"] for r in db.query("SELECT DISTINCT COALESCE(book,'') b FROM guide_tours")}
    books = [str(b) for b in books][:500]
    if any(b not in have for b in books):
        _fehler(404, "Buch nicht gefunden")
    f = body.get("folder")
    with db.cur() as c:
        if f in (None, ""):
            c.executemany("DELETE FROM guide_book_folder WHERE book=?", [(b,) for b in books])
        else:
            n = _pruefe_name(f, "Ordner", MAX_FOLDER)
            if _key(n) == _key(OHNE_ORDNER):
                _fehler(400, f"„{OHNE_ORDNER}“ ist kein Ordnername")
            k = _key(n)
            c.execute("INSERT OR IGNORE INTO guide_folders(k,name) VALUES(?,?)", (k, n))
            c.executemany("INSERT OR REPLACE INTO guide_book_folder(book,fk) VALUES(?,?)", [(b, k) for b in books])
    return {"ok": True, "moved": len(books)}


@router.delete("/api/guides/folders")
def api_guide_folder_del(name: str = ""):
    """Löscht nur den Ordner; seine Bücher bleiben und kommen zurück nach „Ohne Ordner“."""
    k = _key(name)
    if k not in _folder_names():
        _fehler(404, "Ordner nicht gefunden")
    with db.cur() as c:
        n = c.execute("SELECT COUNT(*) FROM guide_book_folder WHERE fk=?", (k,)).fetchone()[0]
        c.execute("DELETE FROM guide_book_folder WHERE fk=?", (k,))
        c.execute("DELETE FROM guide_folders WHERE k=?", (k,))
    return {"ok": True, "books": n}


@router.post("/api/guides/book/rename")
def api_guide_book_rename(body: dict):
    """Buch umbenennen. Ein Name, den ein anderes Buch schon trägt, wird nie zusammengeführt (dafür gibt es „Buchtour in ein anderes Buch verschieben“)."""
    alt = str(body.get("book") if body.get("book") is not None else "")
    if not db.one("SELECT 1 FROM guide_tours WHERE COALESCE(book,'')=? LIMIT 1", (alt,)):
        _fehler(404, "Buch nicht gefunden")
    n = _pruefe_name(body.get("name"), "Buch", MAX_BOOK)
    other = _existing_book(n)
    if other is not None and other != alt:
        _fehler(409, f"Ein Buch „{n}“ gibt es schon")
    if n != alt:
        with db.cur() as c:
            c.execute("UPDATE guide_tours SET book=? WHERE COALESCE(book,'')=?", (n, alt))
            c.execute("UPDATE guide_cover SET book=? WHERE book=?", (n, alt))
            c.execute("UPDATE guide_book_folder SET book=? WHERE book=?", (n, alt))
    return {"ok": True, "book": n}


@router.post("/api/guides/tour/{gid}")
def api_guide_tour_edit(gid: int, body: dict):
    """Buchtour umbenennen (`title`) und/oder in ein anderes Buch verschieben (`book`; ein neuer Name legt das Buch an). Nichts wird zusammengeführt oder überschrieben:
    gibt es dort dieselbe Buchtour (gleicher Titel, Länge auf 50 m), bleibt alles, wie es ist."""
    g = db.one("SELECT id,book,title,km FROM guide_tours WHERE id=?", (gid,))
    if not g:
        _fehler(404, "Buchtour nicht gefunden")
    title = _pruefe_name(body["title"], "Buchtour", MAX_TITLE) if "title" in body else g["title"]
    book = g["book"] or ""
    if "book" in body:
        n = _pruefe_name(body["book"], "Buch", MAX_BOOK)
        book = _existing_book(n)
        if book is None:
            book = n
    if book != (g["book"] or ""):
        for r in db.query("SELECT title,km FROM guide_tours WHERE COALESCE(book,'')=? AND id<>?", (book, gid)):
            if _key(r["title"]) == _key(title) and (r["km"] is None or g["km"] is None or abs(r["km"] - g["km"]) < 0.05):
                _fehler(409, f"„{title}“ gibt es in „{book or '(ohne Buch)'}“ schon")
    db.execute("UPDATE guide_tours SET title=?, book=? WHERE id=?", (title, book, gid))
    _tidy()
    return {"ok": True, "book": book, "title": title}


# ---------- 3.74.0: Wanderführer-Datei importieren (Gegenstück zu GET /api/guides/export und zu „Wanderführer exportieren“ im Tagebuch) ----------
# Dasselbe Verhalten wie im Tagebuch (js/calc-fuehrer-datei.js): erst eine Vorschau (nichts wird geschrieben), dann „Importieren“. Nichts wird überschrieben:
# neue Bücher kommen dazu, in vorhandenen Büchern (gleicher Name ohne Rücksicht auf Groß-/Kleinschreibung) nur neue Buchtouren; gleiche Buchtour (gleicher Titel, Länge auf 50 m)
# zählt als „schon da“; gleicher Titel mit anderer Länge bleibt draußen (Unterschied), ebenso ein zweites Titelbild und ein anderer Ordner. „Gewandert“ rechnet Meine Touren selbst neu.
IMPORT_MAX_BYTES = 80 * 1024 * 1024
IMPORT_MAX_BUECHER, IMPORT_MAX_TOUREN = 200, 500
IMPORT_COVER_MAX = 2_000_000             # Zeichen der Daten-Adresse (das Tagebuch schickt höchstens 200 000; hier großzügiger, das Bild wird ohnehin neu kodiert)


def _entpacke(p):
    """Strecke der Datei (gepackt {la, lo, e} in Einheiten von 1e-5 Grad als Unterschiede zum Vorgänger, oder eine Liste [[lat, lon, …]]) -> [(lat, lon)]; ungültige Punkte fallen weg."""
    out = []
    if isinstance(p, dict) and isinstance(p.get("la"), list) and isinstance(p.get("lo"), list) and len(p["la"]) == len(p["lo"]):
        a = b = 0
        try:
            for x, y in zip(p["la"], p["lo"]):
                a += x
                b += y
                out.append((a / 1e5, b / 1e5))
        except TypeError:
            return []
    elif isinstance(p, list):
        for q in p:
            try:
                out.append((float(q[0]), float(q[1])) if isinstance(q, (list, tuple)) else (float(q["lat"]), float(q["lon"])))
            except (TypeError, ValueError, KeyError, IndexError):
                continue
    return [(a, b) for a, b in out if abs(a) <= 90 and abs(b) <= 180]


def _gleich(a_title, a_km, b_title, b_km):
    return _key(a_title) == _key(b_title) and abs((a_km or 0) - (b_km or 0)) < 0.05


def _datei_lesen(d):
    """Datei prüfen. Wirft HTTPException(400) mit verständlicher Meldung; gibt (Bücher, Zahl nicht lesbarer Einträge) zurück."""
    if not isinstance(d, dict) or d.get("format") != EXPORT_FORMAT:
        _fehler(400, "Das ist keine Wanderführer-Datei.")
    v = d.get("version")
    if not isinstance(v, (int, float)) or v < 1:
        _fehler(400, "Das ist keine Wanderführer-Datei.")
    if v > EXPORT_VERSION:
        _fehler(400, "Die Datei stammt aus einer neueren Version. Bitte Meine Touren aktualisieren.")
    if not isinstance(d.get("buecher"), list):
        _fehler(400, "In der Datei stehen keine Bücher.")
    defekt, books = 0, []
    for b in d["buecher"][:IMPORT_MAX_BUECHER]:
        if not isinstance(b, dict) or not isinstance(b.get("name"), str) or not _clean(b["name"]) or not isinstance(b.get("touren"), list):
            defekt += 1
            continue
        name = _clean(b["name"])[:MAX_BOOK]
        if _key(name) == _key("(ohne Buch)"):
            name = ""                                       # so nennt der Export die Buchtouren ohne Buch
        touren = []
        for t in b["touren"][:IMPORT_MAX_TOUREN]:
            ok = isinstance(t, dict) and isinstance(t.get("title"), str) and _clean(t["title"]) and isinstance(t.get("km"), (int, float)) and not isinstance(t.get("km"), bool) \
                and t["km"] == t["km"] and 0 <= t["km"] < 100000
            pts = _entpacke(t.get("pts")) if ok else []
            if not ok or len(pts) < 3:
                defekt += 1
                continue
            up = t.get("up")
            touren.append({"title": _clean(t["title"])[:MAX_TITLE], "km": round(float(t["km"]), 3),
                           "up": round(up) if isinstance(up, (int, float)) and not isinstance(up, bool) and up == up and abs(up) < 100000 else None, "pts": pts})
        cover = b.get("cover") if isinstance(b.get("cover"), str) and re.match(r"^data:image/(jpeg|png|webp);base64,", b["cover"]) and len(b["cover"]) <= IMPORT_COVER_MAX else None
        ordner = _clean(b.get("ordner"))[:MAX_FOLDER] if isinstance(b.get("ordner"), str) else ""
        if _key(ordner) == _key(OHNE_ORDNER):
            ordner = ""
        books.append({"name": name, "touren": touren, "cover": cover, "ordner": ordner})
    return books, defekt


def _plane(books):
    """Was der Import täte (ohne etwas zu schreiben): Zahlen, Unterschiede und die Zeilen, die eingefügt würden."""
    local = {}
    for r in db.query("SELECT id,COALESCE(book,'') b,title,km,pts FROM guide_tours"):
        km = r["km"]
        if km is None:
            try:
                km = guide_stats("<x/>", [(float(p[0]), float(p[1])) for p in json.loads(r["pts"] or "[]")])[0]
            except (TypeError, ValueError, IndexError):
                km = 0
        local.setdefault(_key(r["b"]), {"name": r["b"], "touren": []})["touren"].append({"title": r["title"], "km": km})
    has_cover = {r["book"] for r in db.query("SELECT book FROM guide_cover")}
    out = {"nNeu": 0, "nTouren": 0, "nErgaenzt": 0, "schon": 0, "cover": 0, "konflikte": [], "buecher": [], "insert": [], "covers": [], "ordner": {}}
    seen_new = {}
    for fb in books:
        k = _key(fb["name"])
        lb = local.get(k) or seen_new.get(k)
        neu_buch = lb is None
        if neu_buch:
            lb = seen_new[k] = {"name": fb["name"], "touren": []}
            out["nNeu"] += 1
        add = []
        for t in fb["touren"]:
            da = lb["touren"] + add
            if any(_gleich(x["title"], x["km"], t["title"], t["km"]) for x in da):
                out["schon"] += 1
                continue
            same = next((x for x in da if _key(x["title"]) == _key(t["title"])), None)
            if same:
                out["konflikte"].append(("laenge", t["title"], lb["name"] or "(ohne Buch)", t["km"], same["km"]))
                continue
            add.append({"title": t["title"], "km": t["km"]})
            out["insert"].append((lb["name"], t))
        lb["touren"] += add
        if neu_buch:
            out["nTouren"] += len(add)
            if fb["ordner"]:
                out["ordner"][lb["name"]] = fb["ordner"]
        else:
            out["nErgaenzt"] += len(add)
        if fb["cover"]:
            if lb["name"] not in has_cover and lb["name"] not in {c[0] for c in out["covers"]}:
                out["covers"].append((lb["name"], fb["cover"]))
                out["cover"] += 1
            else:
                out["konflikte"].append(("cover", lb["name"] or "(ohne Buch)"))
        out["buecher"].append({"name": lb["name"] or "(ohne Buch)", "neu": neu_buch, "neueTouren": len(add)})
    return out


def _plan_antwort(pl, defekt):
    return {"neueBuecher": pl["nNeu"], "neueTourenInNeuenBuechern": pl["nTouren"], "neueTourenInVorhandenen": pl["nErgaenzt"], "schon": pl["schon"], "titelbilder": pl["cover"],
            "defekt": defekt, "buecher": pl["buecher"],
            "konflikte": [{"art": k[0], "titel": k[1], "buch": k[2], "km_datei": k[3], "km_hier": k[4]} if k[0] == "laenge" else {"art": "cover", "buch": k[1]} for k in pl["konflikte"]]}


async def _import_body(request):
    raw = await request.body()
    if len(raw) > IMPORT_MAX_BYTES:
        _fehler(413, f"Die Datei ist zu groß (höchstens {IMPORT_MAX_BYTES // 1048576} MB)")
    try:
        return json.loads(raw.decode("utf-8-sig"))
    except (ValueError, UnicodeDecodeError):
        _fehler(400, "Die Datei ist keine Wanderführer-Datei (kein JSON).")


@router.post("/api/guides/import/preview")
async def api_guides_import_preview(request: Request):
    books, defekt = _datei_lesen(await _import_body(request))
    return _plan_antwort(_plane(books), defekt)


@router.post("/api/guides/import")
async def api_guides_import(request: Request):
    books, defekt = _datei_lesen(await _import_body(request))
    pl = _plane(books)                                      # erst jetzt, auf dem aktuellen Stand: nie ein Plan vom Client
    covers = []
    for book, data in pl["covers"]:
        try:
            import base64
            covers.append((book, _cover_jpeg(base64.b64decode(data.split(",", 1)[1], validate=False))))
        except Exception:  # noqa
            pl["cover"] -= 1                                # unlesbares Bild: Buch und Buchtouren kommen trotzdem
    with db.cur() as c:
        for book, t in pl["insert"]:
            pts = _duenne([[round(a, 5), round(b, 5)] for a, b in t["pts"]])
            c.execute("INSERT INTO guide_tours(book,title,pts,km,up) VALUES(?,?,?,?,?)", (book, t["title"], json.dumps(pts), t["km"], t["up"]))
        now = int(time.time())
        for book, img in covers:
            c.execute("INSERT OR REPLACE INTO guide_cover(book,img,v,ts) VALUES(?,?,?,?)", (book, img, hashlib.sha1(img).hexdigest()[:12], now))
        for book, fname in pl["ordner"].items():
            n = _clean(fname)
            c.execute("INSERT OR IGNORE INTO guide_folders(k,name) VALUES(?,?)", (_key(n), n))
            c.execute("INSERT OR IGNORE INTO guide_book_folder(book,fk) VALUES(?,?)", (book, _key(n)))
    return _plan_antwort(pl, defekt)


# ---------- 3.74.0: Tournamen an die Buchtouren angleichen ----------
# Vorschlag aus dem „Gewandert“-Abgleich (more.api_guides_progress): Titel der Buchtour -> Name der eigenen Tour. Nichts geschieht ohne Bestätigung der Vorschau; jede Umbenennung
# steht im Protokoll (guide_rename_log: alter und neuer Name) und lässt sich rückgängig machen. Optional und nur auf ausdrücklichen Wunsch auch bei Komoot (sync.rename_tour,
# PATCH /v007/tours/<id>): der Client muss die Anzahl der betroffenen Komoot-Touren bestätigen. Ein Komoot-Fehler stoppt die lokale Umbenennung nicht und wird je Tour gemeldet.
def _komoot_moeglich():
    """(möglich, Grund): Komoot-Zugangsdaten sind eingetragen (der Schreibzugriff selbst klappt erst beim Versuch; Fehler kommen je Tour zurück)."""
    if not db.get("komoot_email") or not db.get("komoot_password"):
        return False, "Komoot ist nicht verbunden"
    return True, ""


def _sauber(msg):
    """Fehlertext für die Anzeige: ohne Zugangsdaten, höchstens 160 Zeichen."""
    t = str(msg or "")
    for k in ("komoot_email", "komoot_password"):
        v = db.get(k)
        if v:
            t = t.replace(v, "…")
    return t[:160]


@router.get("/api/guides/rename-suggestions")
def api_guides_rename_suggestions():
    from . import more
    tours = {}
    for b in more.api_guides_progress():
        for x in b["tours"]:
            if x.get("tour"):
                tours.setdefault(x["tour"], []).append({"gid": x["id"], "title": x["title"], "book": b["key"], "book_name": b["book"]})
    cur = {}
    ids = sorted(tours)
    for i in range(0, len(ids), 500):
        part = ids[i:i + 500]
        for r in db.query(f"SELECT id,name,source,start_ts FROM tours WHERE id IN ({','.join('?' * len(part))})", tuple(part)):
            cur[r["id"]] = r
    out = []
    for tid, gs in tours.items():
        t = cur.get(tid)
        if not t:
            continue
        g = gs[0]
        if _key(t["name"]) == _key(g["title"]):
            continue                                       # schon gleich (ohne Rücksicht auf Groß-/Kleinschreibung)
        out.append({"tour": tid, "name": t["name"] or "", "title": g["title"][:MAX_TITLE], "book": g["book_name"], "gid": g["gid"], "ts": t["start_ts"],
                    "komoot": t["source"] != "local", "mehrere": len({y["title"] for y in gs}) > 1})
    out.sort(key=lambda x: (-(x["ts"] or 0), x["tour"]))
    ok, why = _komoot_moeglich()
    return {"items": out, "komoot_moeglich": ok, "komoot_grund": why}


@router.post("/api/guides/rename-tours")
def api_guides_rename_tours(body: dict):
    """Gewählte Touren umbenennen: {"items": [{"tour", "name"}], "komoot": bool, "bestaetigt": Anzahl Komoot-Touren}. Gibt je Tour das Ergebnis zurück."""
    from . import sync
    items = body.get("items")
    if not isinstance(items, list) or not items:
        _fehler(400, "Keine Tour gewählt")
    items = items[:1000]
    rows = {}
    for r in db.query(f"SELECT id,name,source FROM tours WHERE id IN ({','.join('?' * len(items))})", tuple(str(i.get("tour")) for i in items if isinstance(i, dict))):
        rows[r["id"]] = r
    want_k = bool(body.get("komoot"))
    n_k = sum(1 for i in items if isinstance(i, dict) and rows.get(str(i.get("tour"))) and rows[str(i["tour"])]["source"] != "local")
    if want_k:
        ok, why = _komoot_moeglich()
        if not ok:
            _fehler(400, why)
        if body.get("bestaetigt") != n_k:
            _fehler(400, "Bei Komoot umbenennen braucht die ausdrückliche Bestätigung mit der Anzahl der betroffenen Touren")
    batch = hashlib.sha1(f"{time.time()}{len(items)}".encode()).hexdigest()[:12]
    res = []
    for i in items:
        tid = str(i.get("tour")) if isinstance(i, dict) else ""
        r = rows.get(tid)
        try:
            name = _pruefe_name(i.get("name"), "Tour", 120)
        except HTTPException as e:
            res.append({"tour": tid, "ok": False, "fehler": e.detail})
            continue
        if not r:
            res.append({"tour": tid, "ok": False, "fehler": "Tour nicht gefunden"})
            continue
        if _key(r["name"]) == _key(name) and r["name"] == name:
            res.append({"tour": tid, "ok": True, "komoot": None, "unveraendert": True})
            continue
        k_here = want_k and r["source"] != "local"
        try:
            k_ok, msg = sync.rename_tour(tid, name, k_here)
        except Exception as e:  # noqa
            res.append({"tour": tid, "ok": False, "fehler": _sauber(e)})
            continue
        db.execute("INSERT INTO guide_rename_log(batch,ts,tour_id,old,new,komoot) VALUES(?,?,?,?,?,?)", (batch, int(time.time()), tid, r["name"] or "", name, 1 if (k_here and k_ok) else 0))
        e = {"tour": tid, "ok": True, "komoot": (bool(k_ok) if k_here else None), "alt": r["name"] or "", "neu": name}
        if k_here and not k_ok:
            e["komoot_fehler"] = _sauber(msg) or "Komoot hat die Umbenennung nicht angenommen"
        res.append(e)
    return {"ok": True, "batch": batch, "ergebnisse": res, "umbenannt": sum(1 for x in res if x["ok"] and not x.get("unveraendert")),
            "bei_komoot": sum(1 for x in res if x.get("komoot") is True), "fehler": sum(1 for x in res if not x["ok"] or x.get("komoot_fehler"))}


@router.get("/api/guides/rename-log")
def api_guides_rename_log():
    """Protokoll: die letzten Umbenennungen (neueste zuerst) mit altem und neuem Namen und ob sie schon rückgängig gemacht wurden."""
    rows = db.query("SELECT id,batch,ts,tour_id,old,new,komoot,undone FROM guide_rename_log ORDER BY id DESC LIMIT 500")
    return {"items": rows}


@router.post("/api/guides/rename-undo")
def api_guides_rename_undo(body: dict):
    """Namen aus dem Protokoll zurücksetzen: {"ids": [Protokoll-IDs]} oder {"batch": …}; bei Komoot nur mit "komoot": true und "bestaetigt": Anzahl der Touren, die dort umbenannt wurden.
    Eine Tour, die inzwischen anders heißt als der protokollierte neue Name, bleibt unverändert."""
    from . import sync
    if body.get("batch"):
        rows = db.query("SELECT * FROM guide_rename_log WHERE batch=? AND undone=0 ORDER BY id DESC", (str(body["batch"]),))
    else:
        ids = [int(x) for x in (body.get("ids") or []) if str(x).lstrip("-").isdigit()][:1000]
        rows = db.query(f"SELECT * FROM guide_rename_log WHERE undone=0 AND id IN ({','.join('?' * len(ids))}) ORDER BY id DESC", tuple(ids)) if ids else []
    if not rows:
        _fehler(404, "Nichts zum Rückgängigmachen")
    want_k = bool(body.get("komoot"))
    n_k = sum(1 for r in rows if r["komoot"])
    if want_k:
        ok, why = _komoot_moeglich()
        if not ok:
            _fehler(400, why)
        if body.get("bestaetigt") != n_k:
            _fehler(400, "Bei Komoot rückgängig machen braucht die ausdrückliche Bestätigung mit der Anzahl der betroffenen Touren")
    res = []
    for r in rows:
        t = db.one("SELECT name,source FROM tours WHERE id=?", (r["tour_id"],))
        if not t:
            res.append({"id": r["id"], "tour": r["tour_id"], "ok": False, "fehler": "Tour nicht gefunden"})
            continue
        if (t["name"] or "") != r["new"]:
            res.append({"id": r["id"], "tour": r["tour_id"], "ok": False, "fehler": "Die Tour heißt inzwischen anders und bleibt, wie sie ist"})
            continue
        k_here = want_k and bool(r["komoot"]) and t["source"] != "local"
        try:
            k_ok, msg = sync.rename_tour(r["tour_id"], r["old"] or r["new"], k_here)
        except Exception as e:  # noqa
            res.append({"id": r["id"], "tour": r["tour_id"], "ok": False, "fehler": _sauber(e)})
            continue
        db.execute("UPDATE guide_rename_log SET undone=1 WHERE id=?", (r["id"],))
        e = {"id": r["id"], "tour": r["tour_id"], "ok": True, "name": r["old"], "komoot": (bool(k_ok) if k_here else None)}
        if k_here and not k_ok:
            e["komoot_fehler"] = _sauber(msg) or "Komoot hat die Umbenennung nicht angenommen"
        res.append(e)
    return {"ok": True, "ergebnisse": res, "zurueckgesetzt": sum(1 for x in res if x["ok"]), "fehler": sum(1 for x in res if not x["ok"] or x.get("komoot_fehler"))}


# nach den festen Pfaden (/api/guides/cover) registriert, sonst fängt {gid} sie ab
@router.delete("/api/guides/{gid}")
def api_guides_del(gid: str):
    if gid.startswith("book:"):
        db.execute("DELETE FROM guide_tours WHERE book=?", (gid[5:],))
    else:
        db.execute("DELETE FROM guide_tours WHERE id=?", (int(gid),))
    _tidy()                    # 3.53.0: Titelbild verschwindet mit dem Buch; 3.74.0: ebenso die Ordnerzuordnung und die Wunschlisten-Einträge gelöschter Buchtouren
    return {"ok": True}
