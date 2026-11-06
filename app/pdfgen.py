"""Echte PDF-Berichte (Vektor-Text, Karte, Höhenprofil, Fotos): Tour, Reise, Jahresrückblick. Erzeugt mit reportlab."""
import io
import math
import re
import time
from datetime import datetime

import requests
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response

from . import config, db, extras, photos, routes, stats, tracks
from .gpxtools import TZ

router = APIRouter()
FOREST, YELLOW, MUT, RULE = "#0e2a2b", "#f2c230", "#5b6f6c", "#c9d3cc"
DAYC = ["#e11d74", "#f2c230", "#00a6d6", "#7cc43a", "#ff6a1a", "#8e5bd6", "#16a085", "#c0392b"]
MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def _rl():
    import reportlab  # noqa: F401  (Fehlermeldung, falls nicht installiert)


def _t(s):
    """Text für die eingebaute Schrift (WinAnsi): nicht darstellbare Zeichen werden ersetzt."""
    s = "" if s is None else str(s)
    return s.encode("cp1252", "replace").decode("cp1252")


def _esc(s):
    return _t(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _nf(v, d=0):
    s = f"{(v or 0):,.{d}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def _hm(h):
    m = round((h or 0) * 60)
    return f"{m // 60}:{m % 60:02d} h"


def _date(ts_or_iso, long=False):
    d = datetime.fromtimestamp(ts_or_iso, tz=TZ) if isinstance(ts_or_iso, (int, float)) else datetime.fromisoformat(ts_or_iso)
    return d.strftime("%d.%m.%Y")


def _sport(s):
    return stats.SPORT_DE.get(s, s or "Sonstiges")


def _pts(tid):
    data = routes.load(tid)
    if data is None:
        gf = tracks.gpx_file(tid)
        data = tracks.points_from_gpx(gf.read_text(encoding="utf-8")) if gf.exists() else []
    return [p for p in data if p and p[0] is not None and p[1] is not None]


# ---------- Karte aus (zwischengespeicherten) Kacheln ----------
def _merc(lat, lng, z):
    n = 256 * 2 ** z
    x = (lng + 180) / 360 * n
    lat = max(-85.0511, min(85.0511, lat))
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y


def _tile(z, x, y):
    f = extras.TILE_DIR / "topo" / str(z) / str(x) / f"{y}.png"
    from PIL import Image
    try:
        if not f.exists() and config.TILE_FETCH:
            r = requests.get(extras.TILE_UP["topo"].format(z=z, x=x, y=y), headers=extras.UA, timeout=6)
            if r.status_code == 200 and r.content:
                f.parent.mkdir(parents=True, exist_ok=True)
                tmp = f.with_suffix(".tmp"); tmp.write_bytes(r.content); tmp.replace(f)
        if f.exists():
            return Image.open(f).convert("RGB")
    except Exception:  # noqa
        pass
    return None


def map_image(lines, w=1200, h=700):
    """lines = [(Punkte, Farbe)]; liefert ein PIL-Bild (Karte + Strecke) oder eine schlichte Fläche, wenn keine Kacheln erreichbar sind."""
    from PIL import Image, ImageDraw
    allp = [p for ln, _ in lines for p in ln]
    img = Image.new("RGB", (w, h), "#e9ede7")
    if not allp:
        return img
    la0, la1 = min(p[0] for p in allp), max(p[0] for p in allp)
    lo0, lo1 = min(p[1] for p in allp), max(p[1] for p in allp)
    z = 15
    while z > 3:
        x0, y1 = _merc(la0, lo0, z)
        x1, y0 = _merc(la1, lo1, z)
        if (x1 - x0) * 1.15 <= w and (y1 - y0) * 1.15 <= h:
            break
        z -= 1
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    ox, oy = cx - w / 2, cy - h / 2                      # Pixelposition der linken oberen Ecke
    got = 0
    for tx in range(int(ox // 256), int((ox + w) // 256) + 1):
        for ty in range(int(oy // 256), int((oy + h) // 256) + 1):
            if 0 <= tx < 2 ** z and 0 <= ty < 2 ** z:
                t = _tile(z, tx, ty)
                if t:
                    img.paste(t, (int(tx * 256 - ox), int(ty * 256 - oy)))
                    got += 1
    d = ImageDraw.Draw(img)
    proj = lambda p: tuple(v - o for v, o in zip(_merc(p[0], p[1], z), (ox, oy)))
    for ln, col in lines:
        xy = [proj(p) for p in ln]
        if len(xy) > 1:
            d.line(xy, fill="#ffffff", width=9, joint="curve")
            d.line(xy, fill=col, width=5, joint="curve")
    if lines and lines[0][0]:
        for p, c in ((lines[0][0][0], "#2f8f5f"), (lines[-1][0][-1], "#c0504d")):
            x, y = proj(p)
            d.ellipse([x - 9, y - 9, x + 9, y + 9], fill=c, outline="#ffffff", width=3)
    if got:
        d.rectangle([w - 330, h - 24, w, h], fill="#ffffffcc")
        d.text((w - 324, h - 19), "Karte: OpenStreetMap, OpenTopoMap (CC-BY-SA)", fill="#333333")
    return img


def _img_reader(img, fmt="JPEG"):
    b = io.BytesIO()
    img.save(b, fmt, quality=85)
    b.seek(0)
    return b


# ---------- Gestaltung ----------
SPORT_COL = {"hike": "#2f8f5f", "mountaineering": "#2f8f5f", "nordicwalking": "#2f8f5f", "touringbicycle": "#d0792a", "racebike": "#d0792a", "mtb": "#d0792a",
             "e_touringbicycle": "#c9a21c", "jogging": "#c0504d", "skialpin": "#3b7fb0", "skitour": "#3b7fb0", "nordic": "#3b7fb0", "snowshoe": "#7a5fb0"}
PAGE_W, PAGE_H = 595.27, 841.89           # A4 in Punkten
MARGIN = 51                                # 18 mm
HERO_H = 150


def _c(h):
    from reportlab.lib import colors
    return colors.HexColor(h)


def _styles():
    from reportlab.lib.styles import ParagraphStyle
    ink = _c(FOREST)
    return {
        "p": ParagraphStyle("p", fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=ink),
        "note": ParagraphStyle("note", fontName="Helvetica-Oblique", fontSize=10, leading=14.5, textColor=ink, leftIndent=10, borderPadding=(2, 0, 2, 0)),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8, leading=10.5, textColor=_c(MUT)),
        "cap": ParagraphStyle("cap", fontName="Helvetica", fontSize=7, leading=9, textColor=_c(MUT)),
    }


def _flowables():
    from reportlab.platypus import Flowable

    class Section(Flowable):
        """Abschnittsüberschrift: gelber Balken, Text, feine Linie."""
        def __init__(self, text, width):
            super().__init__()
            self.text, self.w = text, width
            self.height = 30
            self.keepWithNext = True

        def wrap(self, aw, ah):
            return self.w, self.height

        def draw(self):
            c = self.canv
            c.setFillColor(_c(YELLOW)); c.roundRect(0, 6, 4, 15, 2, stroke=0, fill=1)
            c.setFillColor(_c(FOREST)); c.setFont("Helvetica-Bold", 13); c.drawString(12, 9, _t(self.text))
            c.setStrokeColor(_c(RULE)); c.setLineWidth(0.6); c.line(12 + c.stringWidth(_t(self.text), "Helvetica-Bold", 13) + 10, 14.5, self.w, 14.5)

    class Cards(Flowable):
        """Kennzahlen als Karten: großer Wert, kleine Einheit, Beschriftung."""
        def __init__(self, items, width):
            super().__init__()
            self.items, self.w = items, width
            self.height = 58

        def wrap(self, aw, ah):
            return self.w, self.height

        def draw(self):
            c = self.canv
            n = len(self.items)
            gap = 7
            cw = (self.w - gap * (n - 1)) / n
            for i, (val, unit, label) in enumerate(self.items):
                x = i * (cw + gap)
                c.setFillColor(_c("#f4f6f1")); c.setStrokeColor(_c(RULE)); c.setLineWidth(0.6)
                c.roundRect(x, 0, cw, self.height, 7, stroke=1, fill=1)
                c.setFillColor(_c(YELLOW)); c.roundRect(x + 10, self.height - 5, 22, 3, 1.5, stroke=0, fill=1)
                v = _t(val)
                fs = 19 if len(v) <= 7 else 15
                c.setFillColor(_c(FOREST)); c.setFont("Helvetica-Bold", fs)
                c.drawString(x + 10, 24, v)
                if unit:
                    c.setFont("Helvetica", 9); c.setFillColor(_c(MUT)); c.drawString(x + 12 + c.stringWidth(v, "Helvetica-Bold", fs), 24, _t(unit))
                c.setFont("Helvetica", 7.5); c.setFillColor(_c(MUT)); c.drawString(x + 10, 10, _t(label).upper())

    class Framed(Flowable):
        """Bild mit feinem Rahmen und abgerundeten Ecken."""
        def __init__(self, reader, width, height):
            super().__init__()
            from reportlab.lib.utils import ImageReader
            self.r, self.w, self.height = ImageReader(reader), width, height

        def wrap(self, aw, ah):
            return self.w, self.height

        def draw(self):
            c = self.canv
            c.saveState()
            p = c.beginPath(); p.roundRect(0, 0, self.w, self.height, 8)
            c.clipPath(p, stroke=0, fill=0)
            c.drawImage(self.r, 0, 0, self.w, self.height)
            c.restoreState()
            c.setStrokeColor(_c(RULE)); c.setLineWidth(0.8); c.roundRect(0, 0, self.w, self.height, 8, stroke=1, fill=0)

    class Quote(Flowable):
        def __init__(self, text, width, style):
            super().__init__()
            from reportlab.platypus import Paragraph
            self.par, self.w = Paragraph(_esc(text).replace("\n", "<br/>"), style), width

        def wrap(self, aw, ah):
            w, h = self.par.wrap(self.w - 22, ah)
            self.height = h + 14
            return self.w, self.height

        def draw(self):
            c = self.canv
            c.setFillColor(_c("#fbf7e8")); c.roundRect(0, 0, self.w, self.height, 6, stroke=0, fill=1)
            c.setFillColor(_c(YELLOW)); c.rect(0, 0, 4, self.height, stroke=0, fill=1)
            self.par.drawOn(c, 14, 7)

    return Section, Cards, Framed, Quote


def _hero_reader(photo_id, w=1500, h=int(1500 * HERO_H / PAGE_W)):
    """Titelbild für den Kopf: Foto, zugeschnitten und nach links dunkel verlaufend (Text bleibt lesbar)."""
    from PIL import Image
    p = photos.thumb(photo_id, 1600) if photo_id else None
    if not p:
        return None
    try:
        im = Image.open(p).convert("RGB")
    except Exception:  # noqa
        return None
    r = w / h
    if im.width / im.height > r:
        nw = int(im.height * r); im = im.crop(((im.width - nw) // 2, 0, (im.width + nw) // 2, im.height))
    else:
        nh = int(im.width / r); top = max(0, int((im.height - nh) * 0.4)); im = im.crop((0, top, im.width, top + nh))
    im = im.resize((w, h), Image.LANCZOS)
    ov = Image.new("RGBA", (w, h))
    px = ov.load()
    f = tuple(int(FOREST[i:i + 2], 16) for i in (1, 3, 5))
    for x in range(w):
        a = int(235 - 150 * (x / w) ** 0.8)
        for y in range(h):
            px[x, y] = (*f, a)
    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    return _img_reader(im)


def _build(story, title, hero):
    """hero = dict(kicker, title, meta, photo) – wird als farbiger Kopf auf Seite 1 gezeichnet."""
    from reportlab.platypus import SimpleDocTemplate, Spacer
    from reportlab.pdfgen import canvas as cv
    from reportlab.lib.utils import simpleSplit, ImageReader
    buf = io.BytesIO()
    rd = _hero_reader(hero.get("photo"))
    if rd:
        rd = ImageReader(rd)

    class Numbered(cv.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._saved = []

        def showPage(self):
            self._saved.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._saved)
            for st in self._saved:
                self.__dict__.update(st)
                self.setStrokeColor(_c(RULE)); self.setLineWidth(0.5); self.line(MARGIN, 34, PAGE_W - MARGIN, 34)
                self.setFont("Helvetica-Bold", 7.5); self.setFillColor(_c(FOREST)); self.drawString(MARGIN, 22, "Meine Touren")
                self.setFont("Helvetica", 7.5); self.setFillColor(_c(MUT))
                self.drawString(MARGIN + 58, 22, _t(title)[:70])
                self.drawRightString(PAGE_W - MARGIN, 22, f"Seite {self._pageNumber} von {total}  ·  erstellt {datetime.now(TZ).strftime('%d.%m.%Y')}")
                super().showPage()
            super().save()

    def first(c, doc):
        c.saveState()
        c.setFillColor(_c(FOREST)); c.rect(0, PAGE_H - HERO_H, PAGE_W, HERO_H, stroke=0, fill=1)
        if rd:
            c.drawImage(rd, 0, PAGE_H - HERO_H, PAGE_W, HERO_H)
        c.setFillColor(_c(YELLOW)); c.rect(0, PAGE_H - HERO_H - 4, PAGE_W, 4, stroke=0, fill=1)
        y = PAGE_H - 46
        c.setFont("Helvetica-Bold", 9); c.setFillColor(_c(YELLOW))
        c.drawString(MARGIN, y, _t(hero.get("kicker", "")).upper())
        t = _t(hero["title"])
        fs = 28 if len(t) < 34 else 22
        lines = simpleSplit(t, "Helvetica-Bold", fs, PAGE_W - 2 * MARGIN)[:2]
        c.setFillColor(_c("#ffffff")); c.setFont("Helvetica-Bold", fs)
        y -= fs + 6
        for ln in lines:
            c.drawString(MARGIN, y, ln); y -= fs + 3
        c.setFont("Helvetica", 10.5); c.setFillColor(_c("#dfe8e3"))
        c.drawString(MARGIN, PAGE_H - HERO_H + 16, _t(hero.get("meta", ""))[:110])
        c.restoreState()

    def later(c, doc):
        c.saveState()
        c.setFillColor(_c(YELLOW)); c.rect(MARGIN, PAGE_H - 30, 26, 3, stroke=0, fill=1)
        c.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=(PAGE_W, PAGE_H), leftMargin=MARGIN, rightMargin=MARGIN, topMargin=44, bottomMargin=50, title=_t(title), author="Meine Touren")
    doc.build([Spacer(1, HERO_H - 44 + 16)] + story, onFirstPage=first, onLaterPages=later, canvasmaker=Numbered)
    return buf.getvalue()


def _pdf_response(data, name):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "bericht"
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{safe}.pdf"'})


def _table(head, rows, widths, align_left=(0,), foot=None, group_rows=(), sport_col=None):
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    cell = ParagraphStyle("c", fontName="Helvetica", fontSize=8.5, leading=10.5, textColor=_c(FOREST))
    cellr = ParagraphStyle("cr", parent=cell, alignment=2)
    hd = ParagraphStyle("hd", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=_c("#ffffff"))
    hdr = ParagraphStyle("hdr", parent=hd, alignment=2)
    day = ParagraphStyle("day", parent=cell, fontName="Helvetica-Bold", textColor=_c(FOREST))
    data = [[Paragraph(_esc(c), hd if i in align_left else hdr) for i, c in enumerate(head)]]
    for ri, r in enumerate(rows):
        st_l, st_r = (day, day) if ri in group_rows else (cell, cellr)
        data.append([Paragraph(_esc(c), st_l if i in align_left else st_r) for i, c in enumerate(r)])
    if foot:
        b = ParagraphStyle("b", parent=cell, fontName="Helvetica-Bold")
        data.append([Paragraph(_esc(c), b if i in align_left else ParagraphStyle("br", parent=b, alignment=2)) for i, c in enumerate(foot)])
    t = Table(data, colWidths=widths, repeatRows=1)
    st = [("BACKGROUND", (0, 0), (-1, 0), _c(FOREST)), ("TOPPADDING", (0, 0), (-1, -1), 4.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5),
          ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
          ("LINEBELOW", (0, 1), (-1, -1), 0.3, _c(RULE)), ("ROUNDEDCORNERS", [5, 5, 0, 0])]
    body_i = 0
    for ri in range(len(rows)):
        if ri in group_rows:
            st += [("BACKGROUND", (0, ri + 1), (-1, ri + 1), _c("#fbf1c9")), ("SPAN", (0, ri + 1), (-1, ri + 1))]
            body_i = 0
        else:
            if body_i % 2:
                st.append(("BACKGROUND", (0, ri + 1), (-1, ri + 1), _c("#f6f8f3")))
            body_i += 1
    if foot:
        st += [("BACKGROUND", (0, -1), (-1, -1), _c("#e7ede4")), ("LINEABOVE", (0, -1), (-1, -1), 0.8, _c(FOREST))]
    t.setStyle(TableStyle(st))
    return t


def _profile(pts, width, height=120):
    """Höhenprofil als Vektorgrafik; pts = Streckenpunkte mit Höhe an Index 2."""
    from reportlab.graphics.shapes import Drawing, Polygon, PolyLine, String, Line, Circle
    ps = [p for p in pts if len(p) > 2 and p[2] is not None]
    if len(ps) < 3:
        return None, None
    dist = [0.0]
    for a, b in zip(ps, ps[1:]):
        dist.append(dist[-1] + extras._hav((a[0], a[1]), (b[0], b[1])))
    step = max(1, len(ps) // 400)
    xs, ys = dist[::step], [p[2] for p in ps][::step]
    lo, hi = min(ys), max(ys)
    span = max(hi - lo, 10)
    lo_a, hi_a = lo - span * 0.08, hi + span * 0.12
    L, B, T = 40, 18, 8
    W, H = width, height
    sx = lambda d: L + d / max(1, xs[-1]) * (W - L - 6)
    sy = lambda e: B + (e - lo_a) / (hi_a - lo_a) * (H - B - T)
    dr = Drawing(W, H)
    for e in (lo, (lo + hi) / 2, hi):
        dr.add(Line(L, sy(e), W - 6, sy(e), strokeColor=_c("#e2e8e0"), strokeWidth=0.5))
        dr.add(String(L - 5, sy(e) - 2.5, f"{round(e)} m", fontName="Helvetica", fontSize=7, fillColor=_c(MUT), textAnchor="end"))
    pxy = [c for x, y in zip(xs, ys) for c in (sx(x), sy(y))]
    dr.add(Polygon([sx(xs[0]), B] + pxy + [sx(xs[-1]), B], fillColor=_c("#d6e8dc"), strokeColor=None))
    dr.add(PolyLine(pxy, strokeColor=_c("#2f8f5f"), strokeWidth=1.8, strokeLineJoin=1))
    i_hi = ys.index(hi)
    dr.add(Circle(sx(xs[i_hi]), sy(hi), 3, fillColor=_c(YELLOW), strokeColor=_c(FOREST), strokeWidth=1))
    km = xs[-1] / 1000
    for i in range(6):
        dr.add(String(L + (W - L - 6) * i / 5, 4, f"{km * i / 5:.1f}".replace(".", ",") + (" km" if i == 5 else ""), fontName="Helvetica", fontSize=7, fillColor=_c(MUT), textAnchor="middle"))
    return dr, (lo, hi)


def _round_photo(path, w_px=640, radius=22):
    from PIL import Image, ImageDraw
    im = Image.open(path).convert("RGB")
    im.thumbnail((w_px, w_px), Image.LANCZOS)
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, im.width - 1, im.height - 1], radius=radius, fill=255)
    out = Image.new("RGBA", im.size, (255, 255, 255, 0))
    out.paste(im, (0, 0), m)
    b = io.BytesIO(); out.save(b, "PNG"); b.seek(0)
    return b, im.width / im.height


def _photo_grid(ids, width, cols=3, gap=8):
    from reportlab.platypus import Table, TableStyle, Image, Paragraph, KeepTogether
    cw = (width - gap * (cols - 1)) / cols
    ch = cw * 0.72
    S = _styles()
    cells = []
    for pid in ids:
        p = photos.thumb(pid, 700)
        if not p:
            continue
        try:
            buf, ratio = _round_photo(p)
        except Exception:  # noqa
            continue
        w, h = (cw, cw / ratio) if cw / ratio <= ch else (ch * ratio, ch)
        row = db.one("SELECT taken_ts FROM photos WHERE id=?", (pid,))
        cap = datetime.fromtimestamp(row["taken_ts"], tz=TZ).strftime("%d.%m.%Y %H:%M") if row and row["taken_ts"] else ""
        cells.append([Image(buf, width=w, height=h), Paragraph(cap, S["cap"])])
    if not cells:
        return None
    rows, heights = [], []
    for i in range(0, len(cells), cols):
        part = cells[i:i + cols]
        rows.append([[c[0], c[1]] for c in part] + [""] * (cols - len(part)))
        heights.append(ch + 16)
    t = Table(rows, colWidths=[cw + gap] * cols, rowHeights=heights)
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "LEFT"), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), gap),
                           ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    return t


def _best_photos(tour_ids, n, per=3):
    if n <= 0:
        return []
    out = []
    for tid in tour_ids:
        try:
            best, _ = photos.best_of_tour(tid, per)
        except Exception:  # noqa
            best = []
        out += [b["id"] for b in best]
    if len(out) > n:
        out = [out[round(i * (len(out) - 1) / max(1, n - 1))] for i in range(n)]
    return list(dict.fromkeys(out))


def _hero_photo(ids):
    return ids[len(ids) // 2] if ids else None


def _activity_rows(ts):
    g = {}
    for t in ts:
        g.setdefault(t["sport"] or "other", []).append(t)
    rows = []
    for k in sorted(g, key=lambda k: -sum((t["dist_m"] or 0) for t in g[k])):
        a = g[k]
        km = sum((t["dist_m"] or 0) for t in a) / 1000
        h = sum((t["dur_s"] or 0) for t in a) / 3600
        rows.append([_sport(k), len(a), _nf(km, 1), _nf(sum(t["up_m"] or 0 for t in a)), _nf(sum(t["down_m"] or 0 for t in a)), _nf(h, 1), _nf(km / h, 1) if h else "-", _nf(max((t["dist_m"] or 0) for t in a) / 1000, 1)])
    km = sum((t["dist_m"] or 0) for t in ts) / 1000
    h = sum((t["dur_s"] or 0) for t in ts) / 3600
    foot = ["Gesamt", len(ts), _nf(km, 1), _nf(sum(t["up_m"] or 0 for t in ts)), _nf(sum(t["down_m"] or 0 for t in ts)), _nf(h, 1), _nf(km / h, 1) if h else "-", _nf(max((t["dist_m"] or 0) for t in ts) / 1000, 1)] if len(rows) > 1 else None
    return rows, foot


ACT_HEAD = ["Aktivität", "Touren", "km", "Aufstieg m", "Abstieg m", "Stunden", "Ø km/h", "Längste km"]
ACT_W = (0.22, 0.09, 0.10, 0.13, 0.13, 0.11, 0.10, 0.12)


# ---------- Tourblatt ----------
@router.get("/api/tours/{tour_id}/pdf")
def api_tour_pdf(tour_id: str, photos_on: int = 1, n: int = 6):
    _rl()
    from reportlab.platypus import Spacer
    t = db.one("SELECT t.*, g.country AS g_country, g.state AS g_state, g.place AS g_place FROM tours t LEFT JOIN tour_geo g ON g.id=t.id WHERE t.id=?", (tour_id,))
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    Section, Cards, Framed, Quote = _flowables()
    W = PAGE_W - 2 * MARGIN
    S = _styles()
    pts = _pts(tour_id)
    km, h = (t["dist_m"] or 0) / 1000, (t["dur_s"] or 0) / 3600
    where = ", ".join(x for x in (t["g_place"], t["g_state"], t["g_country"]) if x)
    st = datetime.fromtimestamp(t["start_ts"], tz=TZ)
    ids = _best_photos([tour_id], max(n, 1), per=max(n, 1)) if photos_on else []
    stars = db.one("SELECT stars FROM tour_rating WHERE id=?", (tour_id,))
    note = db.one("SELECT note FROM tour_notes WHERE id=?", (tour_id,))
    prof, hl = _profile(pts, W)
    cards = [(_nf(km, 1), "km", "Strecke"), (_nf(t["up_m"]), "m", "Aufstieg"), (_nf(t["down_m"]), "m", "Abstieg"), (_hm(h).replace(" h", ""), "h", "Dauer"), ((_nf(km / h, 1) if h else "-"), "km/h", "Tempo")]
    story = [Cards(cards, W), Spacer(1, 12)]
    if pts:
        story += [Framed(_img_reader(map_image([([(p[0], p[1]) for p in pts], "#e11d74")], 1500, 800)), W, W * 800 / 1500), Spacer(1, 4)]
    if prof:
        story += [Section("Höhenprofil", W), prof, Paragraph_small(f"Höchster Punkt {_nf(hl[1])} m  ·  tiefster Punkt {_nf(hl[0])} m  ·  Start {st.strftime('%H:%M')} Uhr", S)]
    if note and (note["note"] or "").strip():
        story += [Section("Notiz", W), Quote(note["note"].strip()[:1500], W, S["note"])]
    grid = _photo_grid(ids[:max(n, 1)], W) if ids else None
    if grid:
        story += [Section("Fotos", W), grid]
    star_txt = (f"  ·  Bewertung {int(stars['stars'])} von 5") if stars and stars["stars"] else ""
    hero = {"kicker": f"{_sport(t['sport'])}{star_txt}", "title": t["name"], "meta": f"{st.strftime('%d.%m.%Y')}" + (f"  ·  {where}" if where else ""), "photo": _hero_photo(ids)}
    return _pdf_response(_build(story, t["name"], hero), t["name"])


def Paragraph_small(text, S):
    from reportlab.platypus import Paragraph
    return Paragraph(_esc(text), S["small"])


# ---------- Reisebericht ----------
def _trip(trip_id):
    from . import more2
    return next((x for x in more2._apply_trip_edits(more2.build_trips()) if x["id"] == trip_id), None)


@router.get("/api/trips/{trip_id}/pdf")
def api_trip_pdf(trip_id: str, photos_on: int = 1, n: int = 12):
    _rl()
    from reportlab.platypus import Paragraph, Spacer
    tr = _trip(trip_id)
    if not tr:
        raise HTTPException(404, "Reise nicht gefunden")
    ts = db.query("SELECT * FROM tours WHERE id IN (%s) ORDER BY start_ts" % ",".join("?" * len(tr["tours"])), tuple(tr["tours"]))
    Section, Cards, Framed, Quote = _flowables()
    W = PAGE_W - 2 * MARGIN
    S = _styles()
    day = lambda t: datetime.fromtimestamp(t["start_ts"], tz=TZ).date().isoformat()
    days = sorted({day(t) for t in ts})
    km = sum((t["dist_m"] or 0) for t in ts) / 1000
    title = tr["region"] + (f", {tr['country']}" if tr.get("country") and tr["country"] != tr["region"] else "")
    ids = _best_photos([t["id"] for t in ts], max(n, 1), per=max(2, -(-24 // max(1, len(ts))))) if photos_on else []
    cards = [(str(len(ts)), "", "Touren"), (_nf(km, 1), "km", "Strecke"), (_nf(sum(t["up_m"] or 0 for t in ts)), "m", "Aufstieg"), (_nf(sum(t["down_m"] or 0 for t in ts)), "m", "Abstieg"),
             (_nf(sum((t["dur_s"] or 0) for t in ts) / 3600, 1), "h", "Unterwegs"), (str(len(days)), "", "Tage")]
    story = [Cards(cards, W), Spacer(1, 12)]
    lines = [([(p[0], p[1]) for p in _pts(t["id"])], DAYC[days.index(day(t)) % len(DAYC)]) for t in ts]
    lines = [x for x in lines if len(x[0]) > 1]
    if lines:
        story.append(Framed(_img_reader(map_image(lines, 1500, 860)), W, W * 860 / 1500))
        leg = "&nbsp;&nbsp;&nbsp;".join(f'<font color="{DAYC[i % len(DAYC)]}">&#9632;</font> {_date(d)[:5]}' for i, d in enumerate(days))
        story += [Spacer(1, 3), Paragraph(leg, S["small"])]
    rows, foot = _activity_rows(ts)
    story += [Section("Statistik nach Aktivität", W), _table(ACT_HEAD, rows, [W * x for x in ACT_W], foot=foot)]
    body, groups = [], []
    for d in days:
        a = [t for t in ts if day(t) == d]
        groups.append(len(body))
        body.append([f"{_date(d)}   -   {_nf(sum((t['dist_m'] or 0) for t in a) / 1000, 1)} km  ·  Aufstieg {_nf(sum(t['up_m'] or 0 for t in a))} m  ·  Abstieg {_nf(sum(t['down_m'] or 0 for t in a))} m", "", "", "", "", ""])
        for t in a:
            body.append([datetime.fromtimestamp(t["start_ts"], tz=TZ).strftime("%H:%M"), t["name"], _sport(t["sport"]), _nf((t["dist_m"] or 0) / 1000, 1), _nf(t["up_m"] or 0), _nf(t["down_m"] or 0)])
    story += [Section("Tag für Tag", W), _table(["Zeit", "Tour", "Aktivität", "km", "Auf m", "Ab m"], body, [W * x for x in (0.09, 0.43, 0.16, 0.1, 0.11, 0.11)], align_left=(0, 1, 2), group_rows=groups)]
    grid = _photo_grid(ids[:max(n, 1)], W) if ids else None
    if grid:
        story += [Section("Fotos", W), grid]
    d0, d1 = tr["start"], tr["end"]
    hero = {"kicker": "Reisebericht", "title": title, "meta": _date(d0) + ("" if d1 == d0 else " - " + _date(d1)) + f"  ·  {len(days)} Tag{'e' if len(days) != 1 else ''}  ·  {len(ts)} Touren", "photo": _hero_photo(ids)}
    return _pdf_response(_build(story, title, hero), "Reise_" + title)


# ---------- Jahresrückblick ----------
@router.get("/api/recap/{year}/pdf")
def api_recap_pdf(year: int, photos_on: int = 1, n: int = 6):
    _rl()
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.graphics.shapes import Drawing, Line, Rect, String
    ts = [t for t in db.query("SELECT * FROM tours WHERE start_ts IS NOT NULL ORDER BY start_ts") if datetime.fromtimestamp(t["start_ts"], tz=TZ).year == year]
    if not ts:
        raise HTTPException(404, "Keine Touren in diesem Jahr")
    Section, Cards, Framed, Quote = _flowables()
    W = PAGE_W - 2 * MARGIN
    mm_km = [0.0] * 12
    for t in ts:
        mm_km[datetime.fromtimestamp(t["start_ts"], tz=TZ).month - 1] += (t["dist_m"] or 0) / 1000
    km = sum(mm_km)
    days = len({datetime.fromtimestamp(t["start_ts"], tz=TZ).date() for t in ts})
    cards = [(str(len(ts)), "", "Touren"), (_nf(km), "km", "Strecke"), (_nf(sum(t["up_m"] or 0 for t in ts)), "m", "Höhenmeter"), (_nf(sum((t["dur_s"] or 0) for t in ts) / 3600), "h", "Stunden"), (str(days), "", "Tage unterwegs")]
    story = [Cards(cards, W), Spacer(1, 6), Section("Kilometer pro Monat", W)]
    H = 140
    dr = Drawing(W, H)
    mx = max(mm_km) or 1
    bw = W / 12
    for i, v in enumerate(mm_km):
        bh = v / mx * (H - 34)
        best = v == mx
        if v:
            dr.add(Rect(i * bw + 5, 18, bw - 10, max(bh, 1.5), fillColor=_c(YELLOW if best else "#2f8f5f"), strokeColor=None, rx=3, ry=3))
        dr.add(String(i * bw + bw / 2, 6, MONTHS[i], fontName="Helvetica", fontSize=7.5, fillColor=_c(MUT), textAnchor="middle"))
        if v:
            dr.add(String(i * bw + bw / 2, 22 + bh, _nf(v), fontName="Helvetica-Bold" if best else "Helvetica", fontSize=7, fillColor=_c(FOREST), textAnchor="middle"))
    dr.add(Line(0, 17.5, W, 17.5, strokeColor=_c(RULE), strokeWidth=0.6))
    story.append(dr)
    bm = mm_km.index(mx)
    story.append(Paragraph_small(f"Stärkster Monat: {MONTHS[bm]} mit {_nf(mx)} km", _styles()))
    # Anteile der Sportarten als gestapelter Balken
    rows, foot = _activity_rows(ts)
    share = {}
    for t in ts:
        share[t["sport"] or "other"] = share.get(t["sport"] or "other", 0) + (t["dist_m"] or 0) / 1000
    bar = Drawing(W, 22)
    x = 0
    for k, v in sorted(share.items(), key=lambda kv: -kv[1]):
        w = v / (km or 1) * W
        bar.add(Rect(x, 6, max(w - 1, 0.5), 12, fillColor=_c(SPORT_COL.get(k, "#78857f")), strokeColor=None))
        x += w
    leg = "&nbsp;&nbsp;&nbsp;".join(f'<font color="{SPORT_COL.get(k, "#78857f")}">&#9632;</font> {_esc(_sport(k))} {_nf(v / (km or 1) * 100)} %' for k, v in sorted(share.items(), key=lambda kv: -kv[1]))
    story += [Section("Statistik nach Aktivität", W), bar, Paragraph(leg, _styles()["small"]), Spacer(1, 8), _table(ACT_HEAD, rows, [W * x for x in ACT_W], foot=foot)]
    top = sorted(ts, key=lambda t: -(t["dist_m"] or 0))[:5]
    story += [Section("Die fünf längsten Touren", W), _table(["Datum", "Tour", "Aktivität", "km", "Auf m"], [[_date(t["start_ts"]), t["name"], _sport(t["sport"]), _nf((t["dist_m"] or 0) / 1000, 1), _nf(t["up_m"] or 0)] for t in top], [W * x for x in (0.14, 0.50, 0.16, 0.10, 0.10)], align_left=(0, 1, 2))]
    ids = []
    if photos_on:
        ph = db.query("SELECT id FROM photos WHERE CAST(strftime('%Y', taken_ts, 'unixepoch') AS INT)=? ORDER BY taken_ts", (year,))
        ids = [p["id"] for p in ph]
        if len(ids) > max(n, 1):
            ids = [ids[round(i * (len(ids) - 1) / max(1, max(n, 1) - 1))] for i in range(max(n, 1))]
    grid = _photo_grid(ids, W) if ids else None
    if grid:
        story += [Section("Fotos des Jahres", W), grid]
    hero = {"kicker": "Mein Tourenjahr", "title": str(year), "meta": f"{len(ts)} Touren  ·  {_nf(km)} km  ·  {_nf(sum(t['up_m'] or 0 for t in ts))} Höhenmeter", "photo": ids[len(ids) // 2] if ids else None}
    return _pdf_response(_build(story, f"Tourenjahr {year}", hero), f"Tourenjahr_{year}")
