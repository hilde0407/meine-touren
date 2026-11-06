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


# ---------- Bausteine ----------
def _styles():
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    ink = colors.HexColor(FOREST)
    return {
        "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=24, leading=28, textColor=ink, spaceAfter=4),
        "sub": ParagraphStyle("sub", fontName="Helvetica", fontSize=10.5, leading=14, textColor=colors.HexColor(MUT)),
        "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=ink, spaceBefore=14, spaceAfter=6),
        "p": ParagraphStyle("p", fontName="Helvetica", fontSize=9.5, leading=12.5, textColor=ink),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor(MUT)),
    }


def _figs(items, width):
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    v = ParagraphStyle("v", fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=colors.HexColor(FOREST), alignment=1)
    l = ParagraphStyle("l", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor(MUT), alignment=1)
    row1 = [Paragraph(_esc(a), v) for a, _ in items]
    row2 = [Paragraph(_esc(b), l) for _, b in items]
    t = Table([row1, row2], colWidths=[width / len(items)] * len(items))
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f1f4ee")), ("TOPPADDING", (0, 0), (-1, 0), 9), ("BOTTOMPADDING", (0, 1), (-1, 1), 8),
                           ("LINEAFTER", (0, 0), (-2, -1), 0.6, colors.white), ("ROUNDEDCORNERS", [6, 6, 6, 6])]))
    return t


def _table(head, rows, widths, align_left=(0,), foot=None, group_rows=()):
    from reportlab.platypus import Table, TableStyle, Paragraph
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib import colors
    cell = ParagraphStyle("c", fontName="Helvetica", fontSize=8.5, leading=10.5, textColor=colors.HexColor(FOREST))
    cellr = ParagraphStyle("cr", parent=cell, alignment=2)
    hd = ParagraphStyle("hd", fontName="Helvetica-Bold", fontSize=7.5, leading=9, textColor=colors.HexColor(MUT))
    hdr = ParagraphStyle("hdr", parent=hd, alignment=2)
    data = [[Paragraph(_esc(c), hd if i in align_left else hdr) for i, c in enumerate(head)]]
    for r in rows:
        data.append([Paragraph(_esc(c), cell if i in align_left else cellr) for i, c in enumerate(r)])
    if foot:
        b = ParagraphStyle("b", parent=cell, fontName="Helvetica-Bold")
        br = ParagraphStyle("br", parent=b, alignment=2)
        data.append([Paragraph(_esc(c), b if i in align_left else br) for i, c in enumerate(foot)])
    t = Table(data, colWidths=widths, repeatRows=1)
    st = [("LINEBELOW", (0, 0), (-1, 0), 0.8, colors.HexColor(FOREST)), ("LINEBELOW", (0, 1), (-1, -1), 0.3, colors.HexColor(RULE)),
          ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("VALIGN", (0, 0), (-1, -1), "MIDDLE")]
    if foot:
        st.append(("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.HexColor(FOREST)))
    for gi in group_rows:                      # Tageszeilen hervorheben
        st += [("BACKGROUND", (0, gi + 1), (-1, gi + 1), colors.HexColor("#f1f4ee")), ("SPAN", (0, gi + 1), (-1, gi + 1))]
    t.setStyle(TableStyle(st))
    return t


def _profile(pts, width, height=110):
    """Höhenprofil als Vektorgrafik; pts = Streckenpunkte mit Höhe an Index 2."""
    from reportlab.graphics.shapes import Drawing, Polygon, PolyLine, String, Line
    from reportlab.lib import colors
    ps = [p for p in pts if len(p) > 2 and p[2] is not None]
    if len(ps) < 3:
        return None
    dist = [0.0]
    for a, b in zip(ps, ps[1:]):
        dist.append(dist[-1] + extras._hav((a[0], a[1]), (b[0], b[1])))
    step = max(1, len(ps) // 400)
    xs, ys = dist[::step], [p[2] for p in ps][::step]
    lo, hi = min(ys), max(ys)
    if hi - lo < 10:
        hi = lo + 10
    L, B, T = 34, 16, 6
    W, H = width, height
    sx = lambda d: L + d / max(1, xs[-1]) * (W - L - 4)
    sy = lambda e: B + (e - lo) / (hi - lo) * (H - B - T)
    dr = Drawing(W, H)
    pts_xy = [c for x, y in zip(xs, ys) for c in (sx(x), sy(y))]
    dr.add(Polygon([sx(xs[0]), B] + pts_xy + [sx(xs[-1]), B], fillColor=colors.HexColor("#cfe3d6"), strokeColor=None))
    dr.add(PolyLine(pts_xy, strokeColor=colors.HexColor("#2f8f5f"), strokeWidth=1.4))
    for e in (lo, (lo + hi) / 2, hi):
        dr.add(Line(L, sy(e), W - 4, sy(e), strokeColor=colors.HexColor(RULE), strokeWidth=0.3))
        dr.add(String(L - 4, sy(e) - 3, f"{round(e)} m", fontName="Helvetica", fontSize=7, fillColor=colors.HexColor(MUT), textAnchor="end"))
    km = xs[-1] / 1000
    for i in range(5):
        dr.add(String(L + (W - L - 4) * i / 4, 3, f"{km * i / 4:.1f} km".replace(".", ","), fontName="Helvetica", fontSize=7, fillColor=colors.HexColor(MUT), textAnchor="middle"))
    return dr


def _photo_grid(ids, width, cols=3, gap=6):
    from reportlab.platypus import Table, TableStyle, Image
    from PIL import Image as PI
    cw = (width - gap * (cols - 1)) / cols
    ch = cw * 0.72
    cells = []
    for pid in ids:
        p = photos.thumb(pid, 700)
        if not p:
            continue
        try:
            with PI.open(p) as im:
                ratio = im.width / im.height
        except Exception:  # noqa
            continue
        w, h = (cw, cw / ratio) if cw / ratio <= ch else (ch * ratio, ch)
        cells.append(Image(str(p), width=w, height=h))
    if not cells:
        return None
    rows = [cells[i:i + cols] + [""] * (cols - len(cells[i:i + cols])) for i in range(0, len(cells), cols)]
    t = Table(rows, colWidths=[cw + gap] * cols, rowHeights=[ch + gap] * len(rows))
    t.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "CENTER"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0), ("RIGHTPADDING", (0, 0), (-1, -1), gap), ("TOPPADDING", (0, 0), (-1, -1), 0), ("BOTTOMPADDING", (0, 0), (-1, -1), gap)]))
    return t


def _build(story, title):
    from reportlab.platypus import SimpleDocTemplate
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    buf = io.BytesIO()

    def deco(c, doc):
        c.saveState()
        c.setStrokeColor(colors.HexColor(YELLOW)); c.setLineWidth(3); c.line(18 * mm, A4[1] - 12 * mm, 38 * mm, A4[1] - 12 * mm)
        c.setFont("Helvetica", 7.5); c.setFillColor(colors.HexColor(MUT))
        c.drawString(18 * mm, 10 * mm, _t(f"Meine Touren · {title}"))
        c.drawRightString(A4[0] - 18 * mm, 10 * mm, f"Seite {doc.page} · erstellt {datetime.now(TZ).strftime('%d.%m.%Y')}")
        c.restoreState()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=18 * mm, bottomMargin=16 * mm, title=_t(title), author="Meine Touren")
    doc.build(story, onFirstPage=deco, onLaterPages=deco)
    return buf.getvalue()


def _pdf_response(data, name):
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", name).strip("_") or "bericht"
    return Response(data, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{safe}.pdf"'})


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


# ---------- Tourblatt ----------
@router.get("/api/tours/{tour_id}/pdf")
def api_tour_pdf(tour_id: str, photos_on: int = 1, n: int = 6):
    _rl()
    from reportlab.platypus import Paragraph, Spacer, Image, KeepTogether
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    t = db.one("SELECT t.*, g.country AS g_country, g.state AS g_state, g.place AS g_place FROM tours t LEFT JOIN tour_geo g ON g.id=t.id WHERE t.id=?", (tour_id,))
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    W = A4[0] - 36 * mm
    S = _styles()
    pts = _pts(tour_id)
    km, h = (t["dist_m"] or 0) / 1000, (t["dur_s"] or 0) / 3600
    where = ", ".join(x for x in (t["g_place"], t["g_state"], t["g_country"]) if x)
    story = [Paragraph(_esc(f"{_sport(t['sport'])} · {_date(t['start_ts'])}" + (f" · {where}" if where else "")), S["sub"]), Spacer(1, 4), Paragraph(_esc(t["name"]), S["h1"]), Spacer(1, 6),
             _figs([(_nf(km, 2) + " km", "Strecke"), (_nf(t["up_m"]) + " m", "Aufstieg"), (_nf(t["down_m"]) + " m", "Abstieg"), (_hm(h), "Dauer"), ((_nf(km / h, 1) + " km/h") if h else "-", "Tempo")], W), Spacer(1, 10)]
    if pts:
        mi = map_image([([(p[0], p[1]) for p in pts], "#e11d74")], 1200, 640)
        story.append(Image(_img_reader(mi), width=W, height=W * 640 / 1200))
        prof = _profile(pts, W)
        if prof:
            story += [Paragraph("Höhenprofil", S["h2"]), prof]
    ids = _best_photos([tour_id], n, per=n) if photos_on else []
    grid = _photo_grid(ids, W) if ids else None
    if grid:
        story += [Paragraph("Fotos", S["h2"]), grid]
    return _pdf_response(_build(story, t["name"]), t["name"])


# ---------- Reisebericht ----------
def _trip(trip_id):
    from . import more2
    return next((x for x in more2._apply_trip_edits(more2.build_trips()) if x["id"] == trip_id), None)


@router.get("/api/trips/{trip_id}/pdf")
def api_trip_pdf(trip_id: str, photos_on: int = 1, n: int = 12):
    _rl()
    from reportlab.platypus import Paragraph, Spacer, Image
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    tr = _trip(trip_id)
    if not tr:
        raise HTTPException(404, "Reise nicht gefunden")
    ts = db.query("SELECT * FROM tours WHERE id IN (%s) ORDER BY start_ts" % ",".join("?" * len(tr["tours"])), tuple(tr["tours"]))
    W = A4[0] - 36 * mm
    S = _styles()
    day = lambda t: datetime.fromtimestamp(t["start_ts"], tz=TZ).date().isoformat()
    days = sorted({day(t) for t in ts})
    km = sum((t["dist_m"] or 0) for t in ts) / 1000
    title = tr["region"] + (f", {tr['country']}" if tr.get("country") and tr["country"] != tr["region"] else "")
    story = [Paragraph(_esc(_date(tr["start"]) + ("" if tr["end"] == tr["start"] else " - " + _date(tr["end"]))), S["sub"]), Spacer(1, 4), Paragraph(_esc(title), S["h1"]), Spacer(1, 6),
             _figs([(len(ts), "Touren"), (_nf(km, 1) + " km", "Strecke"), (_nf(sum(t["up_m"] or 0 for t in ts)) + " m", "Aufstieg"), (_nf(sum(t["down_m"] or 0 for t in ts)) + " m", "Abstieg"), (_nf(sum((t["dur_s"] or 0) for t in ts) / 3600, 1) + " h", "Unterwegs"), (len(days), "Tage")], W), Spacer(1, 10)]
    lines = [(  [(p[0], p[1]) for p in _pts(t["id"])], DAYC[days.index(day(t)) % len(DAYC)]) for t in ts]
    lines = [x for x in lines if len(x[0]) > 1]
    if lines:
        story.append(Image(_img_reader(map_image(lines, 1200, 700)), width=W, height=W * 700 / 1200))
        leg = "   ".join(f'<font color="{DAYC[i % len(DAYC)]}">&#9632;</font> {_date(d)[:5]}' for i, d in enumerate(days))
        story.append(Paragraph(leg, S["small"]))
    rows, foot = _activity_rows(ts)
    story += [Paragraph("Statistik nach Aktivität", S["h2"]), _table(["Aktivität", "Touren", "km", "Aufstieg m", "Abstieg m", "Stunden", "Ø km/h", "Längste km"], rows,
                                                                   [W * x for x in (0.22, 0.09, 0.10, 0.13, 0.13, 0.11, 0.10, 0.12)], foot=foot)]
    body, groups = [], []
    for d in days:
        a = [t for t in ts if day(t) == d]
        groups.append(len(body))
        body.append([f"{_date(d)}  -  {_nf(sum((t['dist_m'] or 0) for t in a) / 1000, 1)} km, Aufstieg {_nf(sum(t['up_m'] or 0 for t in a))} m, Abstieg {_nf(sum(t['down_m'] or 0 for t in a))} m", "", "", "", "", ""])
        for t in a:
            body.append([datetime.fromtimestamp(t["start_ts"], tz=TZ).strftime("%H:%M"), t["name"], _sport(t["sport"]), _nf((t["dist_m"] or 0) / 1000, 1), _nf(t["up_m"] or 0), _nf(t["down_m"] or 0)])
    story += [Paragraph("Tag für Tag", S["h2"]), _table(["Zeit", "Tour", "Aktivität", "km", "Auf m", "Ab m"], body, [W * x for x in (0.09, 0.43, 0.16, 0.1, 0.11, 0.11)], align_left=(0, 1, 2), group_rows=groups)]
    ids = _best_photos([t["id"] for t in ts], n, per=max(2, -(-24 // max(1, len(ts))))) if photos_on else []
    grid = _photo_grid(ids, W) if ids else None
    if grid:
        story += [Paragraph("Fotos", S["h2"]), grid]
    return _pdf_response(_build(story, title), "Reise_" + title)


# ---------- Jahresrückblick ----------
@router.get("/api/recap/{year}/pdf")
def api_recap_pdf(year: int, photos_on: int = 1, n: int = 6):
    _rl()
    from reportlab.platypus import Paragraph, Spacer
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.graphics.shapes import Drawing, Rect, String
    from reportlab.lib import colors
    ts = [t for t in db.query("SELECT * FROM tours WHERE start_ts IS NOT NULL ORDER BY start_ts") if datetime.fromtimestamp(t["start_ts"], tz=TZ).year == year]
    if not ts:
        raise HTTPException(404, "Keine Touren in diesem Jahr")
    W = A4[0] - 36 * mm
    S = _styles()
    mm_km = [0.0] * 12
    for t in ts:
        mm_km[datetime.fromtimestamp(t["start_ts"], tz=TZ).month - 1] += (t["dist_m"] or 0) / 1000
    km = sum(mm_km)
    days = len({datetime.fromtimestamp(t["start_ts"], tz=TZ).date() for t in ts})
    story = [Paragraph("Mein Tourenjahr", S["sub"]), Paragraph(str(year), S["h1"]), Spacer(1, 6),
             _figs([(len(ts), "Touren"), (_nf(km) + " km", "Strecke"), (_nf(sum(t["up_m"] or 0 for t in ts)) + " m", "Höhenmeter"), (_nf(sum((t["dur_s"] or 0) for t in ts) / 3600) + " h", "Stunden"), (days, "Tage unterwegs")], W), Spacer(1, 6)]
    H = 130
    dr = Drawing(W, H)
    mx = max(mm_km) or 1
    bw = W / 12
    for i, v in enumerate(mm_km):
        bh = v / mx * (H - 30)
        dr.add(Rect(i * bw + 4, 16, bw - 8, bh, fillColor=colors.HexColor("#2f8f5f" if v < mx else FOREST), strokeColor=None))
        dr.add(String(i * bw + bw / 2, 5, MONTHS[i], fontName="Helvetica", fontSize=7.5, fillColor=colors.HexColor(MUT), textAnchor="middle"))
        if v:
            dr.add(String(i * bw + bw / 2, 19 + bh, _nf(v), fontName="Helvetica", fontSize=7, fillColor=colors.HexColor(FOREST), textAnchor="middle"))
    story += [Paragraph("Kilometer pro Monat", S["h2"]), dr]
    rows, foot = _activity_rows(ts)
    story += [Paragraph("Statistik nach Aktivität", S["h2"]), _table(["Aktivität", "Touren", "km", "Aufstieg m", "Abstieg m", "Stunden", "Ø km/h", "Längste km"], rows, [W * x for x in (0.22, 0.09, 0.10, 0.13, 0.13, 0.11, 0.10, 0.12)], foot=foot)]
    top = sorted(ts, key=lambda t: -(t["dist_m"] or 0))[:5]
    story += [Paragraph("Die fünf längsten Touren", S["h2"]), _table(["Datum", "Tour", "Aktivität", "km", "Auf m"], [[_date(t["start_ts"]), t["name"], _sport(t["sport"]), _nf((t["dist_m"] or 0) / 1000, 1), _nf(t["up_m"] or 0)] for t in top], [W * x for x in (0.14, 0.50, 0.16, 0.10, 0.10)], align_left=(0, 1, 2))]
    ids = []
    if photos_on:
        ph = db.query("SELECT id FROM photos WHERE CAST(strftime('%Y', taken_ts, 'unixepoch') AS INT)=? ORDER BY taken_ts", (year,))
        ids = [p["id"] for p in ph]
        if len(ids) > n:
            ids = [ids[round(i * (len(ids) - 1) / max(1, n - 1))] for i in range(n)]
    grid = _photo_grid(ids, W) if ids else None
    if grid:
        story += [Paragraph("Fotos des Jahres", S["h2"]), grid]
    return _pdf_response(_build(story, f"Tourenjahr {year}"), f"Tourenjahr_{year}")
