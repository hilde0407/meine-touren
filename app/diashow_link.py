"""3.29.0 „Diashow-Link für ein Jahr oder die ganze Sammlung“: Link ohne Konto mit Fotos und (seit 3.31.1) dem Tournamen je Foto, ohne alles andere.

Ein solcher Link steht in derselben Tabelle wie Tour- und Rückblick-Links (shares): tour_id = „ds:<Jahr>“, „ds:<Jahr>:<Sportart>“ oder „ds:all“ (alle Jahre), photos = 2 (Diashow),
best = Höchstzahl der Fotos (0 = Standard, höchstens MAX_PHOTOS). Standard-Laufzeit 24 Stunden; Kommentare gibt es hier nicht.

Datenschutz: Ausgeliefert werden nur Foto-Nummern, eine Aufnahmezeit je Foto, ein Titel (Jahr, Sportart) und seit 3.31.1 der Tourname je Foto (photo_names; ein Name kann einen Ort verraten, darum weist der Teilen-Knopf darauf hin).
Nie Teil des Links: Tour-Nummern, Koordinaten, Orte, Notizen, Tourdatum, Strecken, Uhr-Daten.
Bestehende Links (shares.names = 0) bekommen die Namen NICHT nachträglich: wer sie vor 3.31.1 verschickt hat, hat ohne Namen geteilt. Nur ab 3.31.1 angelegte Links (names = 1) liefern sie.
Ein Foto ist nur abrufbar, wenn es zur ausgelieferten Liste gehört (wie beim Rückblick); verborgene und abgelehnte Fotos gehören nie dazu. Die Liste wird immer serverseitig aus Jahr, Sportart und Höchstzahl berechnet.
"""
import time
from datetime import datetime

from fastapi import HTTPException

from . import db, gpxtools, photos, stats
from .gpxtools import TZ
from .rueckblick import _range

PREFIX = "ds:"
MAX_PHOTOS = 300
_CACHE = {}


def is_ds(tour_id):
    return isinstance(tour_id, str) and tour_id.startswith(PREFIX)


def ref(year, sport=""):
    return PREFIX + (str(int(year)) if year else "all") + (f":{sport}" if sport else "")


def parse(tour_id):
    """'ds:2025:hike' -> (2025, 'hike'); 'ds:all' -> (0, '')."""
    p = tour_id[len(PREFIX):].split(":", 1)
    y, sp = (0 if p[0] == "all" else int(p[0])), (gpxtools.norm(p[1])[0] if len(p) > 1 else "")
    if sp == "snowshoe" and not db.one("SELECT 1 x FROM tours WHERE sport='snowshoe' LIMIT 1"):    # Links von vor 3.50.0, Touren noch Wandern mit Schlagwort: wie bisher Wandern
        sp = "hike"
    return y, sp


def title(year, sport=""):
    return ("Diashow " + (str(year) if year else "alle Jahre")) + (f" · {stats.SPORT_DE.get(sport, sport)}" if sport else "")


def _rows(year, sport):
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


def photo_list(year, sport, best, measure=False):
    """Die ausgelieferten Fotos (zeitlich sortiert, dicts mit id und taken_ts): die besten höchstens best (0 = MAX_PHOTOS), gleichmäßig verteilt."""
    key = (year, sport, best)
    hit = _CACHE.get(key)
    if hit and not measure and time.time() - hit[0] < 30:
        return hit[1]
    rows = _rows(year, sport)
    if measure:                                   # nur beim Anlegen durch den Besitzer: fehlende Bewertung/Schärfe nachrechnen (begrenzt)
        photos.ensure_metrics(rows, budget_s=20)
    out = [{"id": r["id"], "taken_ts": r["taken_ts"], "tour_name": (r["tour_name"] or "")[:200]} for r in photos.pick_best(rows, best or MAX_PHOTOS)]
    _CACHE[key] = (time.time(), out)
    if len(_CACHE) > 50:
        _CACHE.pop(next(iter(_CACHE)))
    return out


def public(s):
    """Antwort von /api/public/<token>: Titel, Fotos und bei neuen Links der Tourname je Foto (kein Datum der Tour, keine Strecke, kein Ort)."""
    year, sport = parse(s["tour_id"])
    ph = photo_list(year, sport, s["best"] or 0)
    out = {"kind": "diashow", "name": title(year, sport), "photos": [p["id"] for p in ph],
           "photo_t": [datetime.fromtimestamp(p["taken_ts"], tz=TZ).strftime("%d.%m.%Y %H:%M") for p in ph], "coords": [], "show": True}
    if s.get("names"):                            # nur Links ab 3.31.1: Tourname je Foto (sonst nichts von der Tour)
        out["photo_names"] = [p["tour_name"] for p in ph]
    return out


def photo_allowed(s, pid):
    year, sport = parse(s["tour_id"])
    return any(p["id"] == pid for p in photo_list(year, sport, s["best"] or 0))
