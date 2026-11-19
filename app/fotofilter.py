"""3.32.0 Filter für GET /api/photos (Kachel „Erinnerungen“ und Diashow): Sportart, Zeitraum, Kalendertag, „beste Fotos“.

Alle Parameter sind Whitelist-geprüft (Fehler = 400), nichts davon landet ungeprüft im SQL (nur Platzhalter ?):
  sport      kommagetrennte Sportarten (Buchstaben, Ziffern, Unterstrich; höchstens 20)  -> nur Fotos von Touren dieser Sportarten
  date_from / date_to   JJJJ-MM-TT (echtes Datum, von <= bis)  -> Aufnahmezeit in der Zeitzone der App
  day        MM-TT (echter Kalendertag, 02-29 erlaubt) und before (Jahr 1970–2100, optional) -> Fotos von Touren, die an diesem Kalendertag in einem Jahr < before gestartet sind
  best       true -> die besten Fotos (Sterne, Schärfe, über die Zeit verteilt wie „beste Fotos“ einer Tour, photos.pick_best); abgelehnte Fotos (manual = 2) nie
Rechte und Datenbank bleiben die des Aufrufers (je Benutzer eine Datenbank, Betrachter dürfen lesen wie bisher); es werden dieselben Felder geliefert wie sonst, nie der Dateipfad.
"""
import re
from datetime import date, datetime

from fastapi import HTTPException

from . import db, photos
from .gpxtools import TZ

SPORT_RE = re.compile(r"^[A-Za-z0-9_]{1,40}$")
MAX_SPORTS = 20
MAX_LIMIT = 60000
MAX_DAY_TOURS = 800
BEST_POOL = 6000


def _bad(msg):
    raise HTTPException(400, msg)


def clean_sports(s):
    if not s:
        return []
    parts = [x for x in s.split(",") if x != ""]
    if len(parts) > MAX_SPORTS or not all(SPORT_RE.match(x) for x in parts):
        _bad("Ungültige Sportart")
    return list(dict.fromkeys(parts))


def _iso(s, name):
    try:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            raise ValueError
        d = date.fromisoformat(s)
        if not 1970 <= d.year <= 2100:
            raise ValueError
        return d
    except ValueError:
        _bad(f"Ungültiges Datum für „{name}“")


def _day_ok(s):
    m = re.fullmatch(r"(\d{2})-(\d{2})", s or "")
    if not m:
        _bad("Ungültiger Kalendertag („day“ = MM-TT)")
    try:
        date(2000, int(m.group(1)), int(m.group(2)))                    # 2000 ist ein Schaltjahr: 02-29 ist erlaubt
    except ValueError:
        _bad("Ungültiger Kalendertag („day“ = MM-TT)")
    return s


def tours_on_day(md, before=0):
    """Kennungen der Touren, die an diesem Kalendertag (Ortszeit der App) gestartet sind, in einem Jahr vor „before“ (0 = jedes Jahr)."""
    out = []
    for t in db.query("SELECT id,start_ts FROM tours WHERE start_ts IS NOT NULL ORDER BY start_ts DESC"):
        d = datetime.fromtimestamp(t["start_ts"], tz=TZ)
        if d.strftime("%m-%d") == md and (not before or d.year < before):
            out.append(t["id"])
            if len(out) >= MAX_DAY_TOURS:
                break
    return out


def build(sport="", date_from="", date_to="", day="", before=0):
    """Zusätzliche WHERE-Bedingungen (Spalten von photos p und tours t) und ihre Werte; None = nichts kann passen (leeres Ergebnis)."""
    where, args = [], []
    sp = clean_sports(sport)
    if sp:
        where.append(f"t.sport IN ({','.join('?' * len(sp))})")
        args += sp
    a = _iso(date_from, "date_from") if date_from else None
    b = _iso(date_to, "date_to") if date_to else None
    if a and b and a > b:
        _bad("„date_from“ liegt nach „date_to“")
    if a:
        where.append("p.taken_ts>=?")
        args.append(int(datetime(a.year, a.month, a.day, tzinfo=TZ).timestamp()))
    if b:
        where.append("p.taken_ts<?")
        args.append(int(datetime(b.year, b.month, b.day, 23, 59, 59, tzinfo=TZ).timestamp()) + 1)
    if before and not 1970 <= before <= 2100:
        _bad("Ungültiges Jahr („before“)")
    if day:
        ids = tours_on_day(_day_ok(day), before)
        if not ids:
            return None
        where.append(f"p.tour_id IN ({','.join('?' * len(ids))})")
        args += ids
    elif before:
        _bad("„before“ gehört zu „day“")
    return where, args


def best(where, args, n):
    """Die besten n Fotos zu den Bedingungen (zeitlich sortiert, ohne Dateipfad)."""
    rows = db.query("SELECT p.id,p.taken_ts,p.tour_id,p.lat,p.lng,p.manual,p.offset_s,p.path,p.rating,p.sharp,t.name AS tour_name FROM photos p LEFT JOIN tours t ON t.id=p.tour_id "
                    f"WHERE {' AND '.join(where)} AND COALESCE(p.manual,0)!=2 AND p.taken_ts IS NOT NULL ORDER BY p.taken_ts LIMIT {BEST_POOL}", tuple(args))
    photos.ensure_metrics([r for r in rows if r.get("rating") is None or r.get("sharp") is None][:300], budget_s=4)         # fehlende Bewertung nachrechnen, begrenzt
    return [{k: v for k, v in r.items() if k not in ("path", "rating", "sharp")} for r in photos.pick_best(rows, n)]
