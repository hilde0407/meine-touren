"""3.29.0 „Diashow-Link für ein Jahr oder die ganze Sammlung“: Link ohne Konto mit Fotos und (seit 3.31.1) dem Tournamen je Foto, ohne alles andere.

Ein solcher Link steht in derselben Tabelle wie Tour- und Rückblick-Links (shares): tour_id = „ds:<Jahr>“, „ds:<Jahr>:<Sportart>“ oder „ds:all“ (alle Jahre), photos = 2 (Diashow),
best = Höchstzahl der Fotos (0 = Standard, höchstens MAX_PHOTOS). Standard-Laufzeit 24 Stunden; Kommentare gibt es hier nicht.

Datenschutz: Ausgeliefert werden nur Foto-Nummern, eine Aufnahmezeit je Foto, ein Titel (Jahr, Sportart) und seit 3.31.1 der Tourname je Foto (photo_names; ein Name kann einen Ort verraten, darum weist der Teilen-Knopf darauf hin).
Nie Teil des Links: Tour-Nummern, Koordinaten, Orte, Notizen, Tourdatum, Strecken, Uhr-Daten.
Bestehende Links (shares.names = 0) bekommen die Namen NICHT nachträglich: wer sie vor 3.31.1 verschickt hat, hat ohne Namen geteilt. Nur ab 3.31.1 angelegte Links (names = 1) liefern sie.
3.61.5: tour_id = „ds:<von>..<bis>“ (JJJJ-MM-TT, z. B. die Reise-Diashow): die Fotos, die in diesem Zeitraum aufgenommen wurden (wie die Reise-Diashow, GET /api/photos mit date_from/date_to),
höchstens MAX_RANGE_DAYS Tage, von <= bis; ohne Sportart. Der Titel nennt nur den Zeitraum, nie den Reisenamen.
Ein Foto ist nur abrufbar, wenn es zur ausgelieferten Liste gehört (wie beim Rückblick); verborgene und abgelehnte Fotos gehören nie dazu. Die Liste wird immer serverseitig aus Jahr, Sportart und Höchstzahl berechnet.
"""
import re
import time
from datetime import date, datetime

from fastapi import HTTPException

from . import db, gpxtools, photos, stats
from .gpxtools import TZ
from .rueckblick import _range

PREFIX = "ds:"
MAX_PHOTOS = 300
MAX_RANGE_DAYS = 366
_RANGE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})\.\.(\d{4}-\d{2}-\d{2})")
_CACHE = {}


def is_ds(tour_id):
    return isinstance(tour_id, str) and tour_id.startswith(PREFIX)


def ref(year, sport=""):
    return PREFIX + (str(int(year)) if year else "all") + (f":{sport}" if sport else "")


def range_ref(von, bis):
    return f"{PREFIX}{von}..{bis}"


def range_check(von, bis):
    """Zeitraum prüfen (JJJJ-MM-TT, echtes Datum, 1970–2100, von <= bis, höchstens MAX_RANGE_DAYS Tage). Gibt (von, bis) als Text zurück."""
    out = []
    for v in (von, bis):
        if not isinstance(v, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            raise HTTPException(400, "Ungültiger Zeitraum")
        try:
            d = date.fromisoformat(v)
        except ValueError:
            raise HTTPException(400, "Ungültiger Zeitraum")
        if not 1970 <= d.year <= 2100:
            raise HTTPException(400, "Ungültiger Zeitraum")
        out.append(d)
    if out[0] > out[1]:
        raise HTTPException(400, "Der Zeitraum beginnt nach seinem Ende")
    if (out[1] - out[0]).days + 1 > MAX_RANGE_DAYS:
        raise HTTPException(400, f"Der Zeitraum darf höchstens {MAX_RANGE_DAYS} Tage lang sein")
    return von, bis


def spec(tour_id):
    """'ds:2025:hike' -> (2025, 'hike', None); 'ds:all' -> (0, '', None); 'ds:2025-03-01..2025-03-07' -> (0, '', ('2025-03-01', '2025-03-07'))."""
    m = _RANGE_RE.fullmatch(tour_id[len(PREFIX):])
    if m:
        return 0, "", (m.group(1), m.group(2))
    return (*parse(tour_id), None)


def parse(tour_id):
    """'ds:2025:hike' -> (2025, 'hike'); 'ds:all' -> (0, '')."""
    p = tour_id[len(PREFIX):].split(":", 1)
    y, sp = (0 if p[0] == "all" else int(p[0])), (gpxtools.norm(p[1])[0] if len(p) > 1 else "")
    if sp == "snowshoe" and not db.one("SELECT 1 x FROM tours WHERE sport='snowshoe' LIMIT 1"):    # Links von vor 3.50.0, Touren noch Wandern mit Schlagwort: wie bisher Wandern
        sp = "hike"
    return y, sp


def _de(iso):
    return f"{iso[8:10]}.{iso[5:7]}.{iso[:4]}"


def title(year, sport="", rng=None):
    if rng:
        return f"Diashow {_de(rng[0])} – {_de(rng[1])}"
    return ("Diashow " + (str(year) if year else "alle Jahre")) + (f" · {stats.SPORT_DE.get(sport, sport)}" if sport else "")


def _rows(year, sport, rng=None):
    if rng:                                       # Zeitraum: Aufnahmezeit in der Ortszeit der App, wie GET /api/photos (fotofilter.build); auch Fotos ohne Tour
        a, b = date.fromisoformat(rng[0]), date.fromisoformat(rng[1])
        lo, hi = int(datetime(a.year, a.month, a.day, tzinfo=TZ).timestamp()), int(datetime(b.year, b.month, b.day, 23, 59, 59, tzinfo=TZ).timestamp()) + 1
        return db.query("SELECT p.id,p.taken_ts,p.rating,p.sharp,p.path,t.name AS tour_name FROM photos p LEFT JOIN tours t ON t.id=p.tour_id "
                        "WHERE COALESCE(p.manual,0)!=2 AND p.taken_ts IS NOT NULL AND p.taken_ts>=? AND p.taken_ts<? ORDER BY p.taken_ts LIMIT 5000", (lo, hi))
    sql = ("SELECT p.id,p.taken_ts,p.rating,p.sharp,p.path,t.name AS tour_name FROM photos p JOIN tours t ON t.id=p.tour_id WHERE COALESCE(p.manual,0)!=2 AND p.taken_ts IS NOT NULL")
    args = []
    if year:
        lo, hi = _range(year)
        sql += " AND t.start_ts>=? AND t.start_ts<?"
        args += [lo, hi]
    if sport:
        r = gpxtools.roh(sport)                    # 3.60.0: auch ältere Touren mit entferntem Schlüssel, der als diese Sportart zählt
        sql += f" AND t.sport IN ({','.join('?' * len(r))})"
        args += r
    return db.query(sql + " ORDER BY p.taken_ts LIMIT 5000", tuple(args))


def check(year, sport, best):
    """Eingaben prüfen. Gibt (Jahr, Sportart, Höchstzahl) zurück; Jahr 0 = alle Jahre. Es muss mindestens ein Foto geben."""
    if year in (None, "", 0, "0", "all"):
        year = 0
    else:
        try:
            year = int(year)
        except (TypeError, ValueError):
            raise HTTPException(400, "Ungültiges Jahr")
        if not 1970 <= year <= 2100:
            raise HTTPException(400, "Ungültiges Jahr")
    sport = sport if isinstance(sport, str) else ""
    if len(sport) > 40 or ":" in sport:
        raise HTTPException(400, "Ungültige Sportart")
    sport = gpxtools.norm(sport)[0]
    try:
        best = int(best or 0)
    except (TypeError, ValueError):
        raise HTTPException(400, "Ungültige Anzahl")
    if best < 0 or best > MAX_PHOTOS:
        raise HTTPException(400, "Ungültige Anzahl")
    if not _rows(year, sport):
        raise HTTPException(400, "Keine Fotos in diesem Zeitraum")
    return year, sport, best


def check_range(von, bis, best):
    """Eingaben für eine Diashow mit Zeitraum prüfen. Gibt (von, bis, Höchstzahl) zurück. Es muss mindestens ein Foto im Zeitraum geben."""
    von, bis = range_check(von, bis)
    try:
        best = int(best or 0)
    except (TypeError, ValueError):
        raise HTTPException(400, "Ungültige Anzahl")
    if best < 0 or best > MAX_PHOTOS:
        raise HTTPException(400, "Ungültige Anzahl")
    if not _rows(0, "", (von, bis)):
        raise HTTPException(400, "Keine Fotos in diesem Zeitraum")
    return von, bis, best


def photo_list(year, sport, best, measure=False, rng=None):
    """Die ausgelieferten Fotos (zeitlich sortiert, dicts mit id und taken_ts): die besten höchstens best (0 = MAX_PHOTOS), gleichmäßig verteilt."""
    key = (year, sport, best, rng)
    hit = _CACHE.get(key)
    if hit and not measure and time.time() - hit[0] < 30:
        return hit[1]
    rows = _rows(year, sport, rng)
    if measure:                                   # nur beim Anlegen durch den Besitzer: fehlende Bewertung/Schärfe nachrechnen (begrenzt)
        photos.ensure_metrics(rows, budget_s=20)
    out = [{"id": r["id"], "taken_ts": r["taken_ts"], "tour_name": (r["tour_name"] or "")[:200]} for r in photos.pick_best(rows, best or MAX_PHOTOS)]
    _CACHE[key] = (time.time(), out)
    if len(_CACHE) > 50:
        _CACHE.pop(next(iter(_CACHE)))
    return out


def public(s):
    """Antwort von /api/public/<token>: Titel, Fotos und bei neuen Links der Tourname je Foto (kein Datum der Tour, keine Strecke, kein Ort)."""
    year, sport, rng = spec(s["tour_id"])
    ph = photo_list(year, sport, s["best"] or 0, rng=rng)
    out = {"kind": "diashow", "name": title(year, sport, rng), "photos": [p["id"] for p in ph],
           "photo_t": [datetime.fromtimestamp(p["taken_ts"], tz=TZ).strftime("%d.%m.%Y %H:%M") for p in ph], "coords": [], "show": True}
    if s.get("names"):                            # nur Links ab 3.31.1: Tourname je Foto (sonst nichts von der Tour)
        out["photo_names"] = [p["tour_name"] for p in ph]
    return out


def photo_allowed(s, pid):
    year, sport, rng = spec(s["tour_id"])
    return any(p["id"] == pid for p in photo_list(year, sport, s["best"] or 0, rng=rng))
