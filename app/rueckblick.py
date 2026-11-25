"""3.26.0 „Jahresrückblick als teilbare Seite“: Was ein Rückblick-Link (Freigabe ohne Konto) zeigt – und wie der Server das durchsetzt.

Ein Rückblick-Link steht in derselben Tabelle wie Tourlinks (shares): tour_id = „rb:<Jahr>“ oder „rb:<Jahr>:<Sportart>“, blocks = gewählte Bausteine.
Bausteine: kennzahlen (Touren, Strecke, Aufstieg, Stunden, Tage, Monatssäulen), rekorde (Tourname, Datum, Wert), heatmap (Strecke je Kalendertag), fotos (die besten Fotos des Jahres).
Der Server liefert nur Gewähltes aus; Fotos sind nur abrufbar, wenn „fotos“ gewählt ist und das Foto zur ausgewählten Bestenliste gehört.

Datenschutz: Nie Teil des Links sind Notizen, Wegpunkte, Strecken und Koordinaten (auch keine Start- oder Heimatorte), Ortsnamen aus der Geokodierung, Uhr-Rohdaten, Puls, Gerät, Ausrüstung.
Die Heatmap ist ein Kalender (Tag → km), keine Karte. Bestwerte nennen nur Tourname und Datum der Tour.
"""
from datetime import date, datetime, timedelta

from fastapi import HTTPException

from . import db, gpxtools, photos, stats
from .gpxtools import TZ

BLOCKS = ("kennzahlen", "rekorde", "heatmap", "fotos")
PREFIX = "rb:"
LIFT = {"skialpin"}                     # Liftabfahrten sagen nichts über die Leistung (wie im Jahresrückblick der App)
N_PHOTOS = 12


def is_rb(tour_id):
    return isinstance(tour_id, str) and tour_id.startswith(PREFIX)


def ref(year, sport=""):
    return f"{PREFIX}{int(year)}" + (f":{sport}" if sport else "")


def parse(tour_id):
    """'rb:2025:hike' -> (2025, 'hike'); 'rb:2025' -> (2025, '')."""
    p = tour_id[len(PREFIX):].split(":", 1)
    y, sp = int(p[0]), (gpxtools.norm(p[1])[0] if len(p) > 1 else "")
    if sp == "snowshoe" and not tours(y, sp):              # Links von vor 3.50.0 („snowshoe“), deren Touren noch Wandern mit Schlagwort sind: wie bisher Wandern
        sp = "hike"
    return y, sp


def normalize(blocks):
    if not isinstance(blocks, list) or not all(isinstance(b, str) for b in blocks):
        raise HTTPException(400, "Ungültige Auswahl")
    bad = [b for b in blocks if b not in BLOCKS]
    if bad:
        raise HTTPException(400, "Unbekannter Inhalt: " + ", ".join(sorted(set(bad))[:5]))
    if not blocks:
        raise HTTPException(400, "Bitte mindestens einen Inhalt wählen")
    return [b for b in BLOCKS if b in blocks]


def effective(raw):
    """Gespeicherte Auswahl (kommagetrennt) als Liste in fester Reihenfolge; unbekannte Namen fallen weg."""
    have = (raw or "").split(",")
    return [b for b in BLOCKS if b in have]


def _range(year):
    return int(datetime(year, 1, 1, tzinfo=TZ).timestamp()), int(datetime(year + 1, 1, 1, tzinfo=TZ).timestamp())


def tours(year, sport=""):
    lo, hi = _range(year)
    sql = "SELECT id,name,sport,start_ts,dist_m,dur_s,up_m FROM tours WHERE start_ts>=? AND start_ts<?"
    args = [lo, hi]
    if sport:
        r = gpxtools.roh(sport)                    # 3.60.0: auch ältere Touren mit entferntem Schlüssel, der als diese Sportart zählt
        sql += f" AND sport IN ({','.join('?' * len(r))})"
        args += r
    return db.query(sql + " ORDER BY start_ts", tuple(args))


def check(year, sport):
    """Jahr und Sportart prüfen (es muss Touren geben). Gibt (Jahr, Sportart) zurück."""
    try:
        year = int(year)
    except (TypeError, ValueError):
        raise HTTPException(400, "Ungültiges Jahr")
    if not 1970 <= year <= 2100:
        raise HTTPException(400, "Ungültiges Jahr")
    sport = sport if isinstance(sport, str) else ""
    if len(sport) > 40 or ":" in sport:
        raise HTTPException(400, "Ungültige Sportart")
    sport = gpxtools.norm(sport)[0]           # 3.50.0: ältere Links „Schneeschuh“ zeigen Wandern
    if not tours(year, sport):
        raise HTTPException(400, "Keine Touren in diesem Zeitraum")
    return year, sport


def title(year, sport=""):
    return f"Jahresrückblick {year}" + (f" · {stats.SPORT_DE.get(sport, sport)}" if sport else "")


def _photo_rows(year, sport=""):
    """Kandidaten: nur Fotos von Touren des Jahres (und der Sportart)."""
    lo, hi = _range(year)
    sql = ("SELECT p.id,p.taken_ts,p.rating,p.sharp,p.path FROM photos p JOIN tours t ON t.id=p.tour_id "
           "WHERE t.start_ts>=? AND t.start_ts<? AND COALESCE(p.manual,0)!=2 AND p.taken_ts IS NOT NULL")
    args = [lo, hi]
    if sport:
        sql += " AND t.sport=?"
        args.append(sport)
    rows = db.query(sql + " ORDER BY p.taken_ts LIMIT 3000", tuple(args))
    return rows


def best_photos(year, sport="", n=N_PHOTOS, measure=False):
    """Die besten Fotos des Jahres (Bewertung, Schärfe, über das Jahr verteilt)."""
    rows = _photo_rows(year, sport)
    if measure:                                   # nur beim Anlegen/Ändern durch den Besitzer: fehlende Bewertung/Schärfe nachrechnen (begrenzt)
        photos.ensure_metrics(rows, budget_s=20)
    return [r["id"] for r in photos.pick_best(rows, n)]


def _kennzahlen(ts, year, sport):
    km = sum((t["dist_m"] or 0) for t in ts) / 1000
    months = [0.0] * 12
    for t in ts:
        months[datetime.fromtimestamp(t["start_ts"], tz=TZ).month - 1] += (t["dist_m"] or 0) / 1000
    out = {"count": len(ts), "km": round(km, 1), "up_m": round(sum((t["up_m"] or 0) for t in ts)), "h": round(sum((t["dur_s"] or 0) for t in ts) / 3600, 1),
           "days": len({datetime.fromtimestamp(t["start_ts"], tz=TZ).date() for t in ts}), "months": [round(m, 1) for m in months]}
    prev = tours(year - 1, sport)
    out["prev_km"] = round(sum((t["dist_m"] or 0) for t in prev) / 1000, 1) if prev else None
    if not sport:
        from . import stat_gruppen
        gr, by = stat_gruppen.load(), {}                                # 3.59.0: Sportarten einer Statistik-Gruppe zählen als eine Zeile mit dem Gruppennamen
        for t in ts:
            k = stat_gruppen.key(t["sport"], gr) if t["sport"] else "other"
            by[k] = by.get(k, 0) + (t["dist_m"] or 0) / 1000
        gid = {stat_gruppen.PREFIX + g["id"]: g for g in gr}
        out["sports"] = [dict({"sport": k, "name": stat_gruppen.label(k, gr), "km": round(v, 1)},              # 3.60.1: Gruppe als „<Name> = A + B + …“
                              **({"gruppe": gid[k]["name"], "mitglieder": [stats.SPORT_DE.get(s, s) for s in gid[k]["sports"]]} if k in gid else {}))
                         for k, v in sorted(by.items(), key=lambda kv: -kv[1])]
    return out


def _rekorde(ts):
    pool = [t for t in ts if (t["sport"] or "") not in LIFT] or ts
    day = lambda t: datetime.fromtimestamp(t["start_ts"], tz=TZ).date()
    rec = lambda k, t, v, u: {"k": k, "name": t["name"] or "Tour", "date": day(t).isoformat(), "v": v, "u": u}
    out = []
    for k, f, u, r in (("weit", "dist_m", "km", lambda v: round(v / 1000, 1)), ("hoch", "up_m", "m", lambda v: round(v)), ("lang", "dur_s", "h", lambda v: round(v / 3600, 1))):
        t = max(pool, key=lambda x: x[f] or 0)
        if (t[f] or 0) > 0:
            out.append(rec(k, t, r(t[f]), u))
    mk = {}
    for t in ts:
        mk[day(t).month] = mk.get(day(t).month, 0) + (t["dist_m"] or 0) / 1000
    if mk:
        m = max(mk, key=mk.get)
        out.append({"k": "monat", "month": m, "v": round(mk[m], 1), "u": "km"})
    days = sorted({day(t) for t in ts})
    best = run = 1
    for a, b in zip(days, days[1:]):
        run = run + 1 if b - a == timedelta(days=1) else 1
        best = max(best, run)
    if days:
        out.append({"k": "serie", "v": best, "u": "d"})
    return out


def _heatmap(ts, year):
    per = {}
    for t in ts:
        d = datetime.fromtimestamp(t["start_ts"], tz=TZ).date()
        per[d] = per.get(d, 0) + (t["dist_m"] or 0) / 1000
    first = date(year, 1, 1)
    return {"year": year, "wd0": first.weekday(), "n": (date(year + 1, 1, 1) - first).days,
            "days": [[(d - first).days + 1, round(v, 1)] for d, v in sorted(per.items())]}


def public(s):
    """Antwort von /api/public/<token> für einen Rückblick-Link."""
    year, sport = parse(s["tour_id"])
    bl = effective(s["blocks"])
    ts = tours(year, sport)
    out = {"kind": "rueckblick", "year": year, "sport": sport, "sport_name": stats.SPORT_DE.get(sport, sport) if sport else "", "blocks": bl}
    if "kennzahlen" in bl:
        out["kz"] = _kennzahlen(ts, year, sport)
    if "rekorde" in bl and ts:
        out["rek"] = _rekorde(ts)
    if "heatmap" in bl:
        out["heat"] = _heatmap(ts, year)
    if "fotos" in bl:
        out["photos"] = best_photos(year, sport)
    return out


def photo_allowed(s, pid):
    year, sport = parse(s["tour_id"])
    return "fotos" in effective(s["blocks"]) and pid in best_photos(year, sport)
