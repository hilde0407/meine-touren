"""3.25.0 „Teilen mit Ansicht“: Welche Inhalte ein Freigabelink der öffentlichen Tourseite zeigt – und wie der Server das durchsetzt.

Je Link wird eine Auswahl fester Bausteine gespeichert (Spalte shares.blocks, kommagetrennt). Der Server liefert nur Gewähltes aus:
Was nicht gewählt ist, steht weder im JSON von /api/public/<token> noch ist das Foto abrufbar (kein bloßes Ausblenden im Browser).
Links ohne Eintrag (NULL, alle Links aus älteren Versionen) verhalten sich unverändert: Karte und Kennzahlen, Fotos nur wenn photos=1.

Datenschutz: Nie Teil eines Freigabelinks sind Uhr-Daten, Auswertung, Vergleiche, Gerät, Ausrüstung, Sicherheit und Standortverlauf außerhalb der Strecke.
Notiztexte der Wegpunkte erscheinen nur, wenn zusätzlich „Notiz“ gewählt ist. Mit „Anfang und Ende ausblenden“ (trim) fehlen auch Wegpunkte in der Nähe von Start und Ziel."""
import json
from datetime import datetime

from fastapi import HTTPException

from . import db, extras
from .gpxtools import TZ

BLOCKS = ("karte", "hoehe", "zahlen", "fotos", "notiz", "wege", "puls", "wetter")
LEGACY = ("karte", "zahlen")                       # bisheriger Umfang eines Tourlinks; dazu Fotos, wenn photos=1


def normalize(blocks):
    """Auswahl prüfen: Liste bekannter Bausteine, mindestens einer, Wegpunkte brauchen die Karte. Ergebnis in fester Reihenfolge."""
    if not isinstance(blocks, list) or not all(isinstance(b, str) for b in blocks):
        raise HTTPException(400, "Ungültige Auswahl")
    bad = [b for b in blocks if b not in BLOCKS]
    if bad:
        raise HTTPException(400, "Unbekannter Inhalt: " + ", ".join(sorted(set(bad))[:5]))
    if not blocks:
        raise HTTPException(400, "Bitte mindestens einen Inhalt wählen")
    if "wege" in blocks and "karte" not in blocks:
        raise HTTPException(400, "Wegpunkte brauchen die Karte")
    return [b for b in BLOCKS if b in blocks]


def effective(s):
    """Bausteine eines Links (Zeile aus shares). Diashows (photos=2) haben feste Inhalte: None."""
    if s["photos"] == 2:
        return None
    raw = s["blocks"] if "blocks" in s.keys() else None
    if raw is None:
        return [b for b in BLOCKS if b in LEGACY or (b == "fotos" and s["photos"] == 1)]
    return [b for b in BLOCKS if b in raw.split(",")]


def _clock(ts):
    try:
        return datetime.fromtimestamp(ts, tz=TZ).strftime("%H:%M")
    except Exception:  # noqa
        return ""


def _near_ends(pts, la, lo, meters):
    return any(extras._hav((p[0], p[1]), (la, lo)) <= meters for p in (pts[0], pts[-1]))


def _down(seq, n):
    return seq[::max(1, len(seq) // n)]


def public(s, t, pts, all_pts, photo_rows):
    """Antwort von /api/public/<token> für einen Link mit gespeicherter Auswahl. pts = ggf. gekürzte Strecke, all_pts = volle Strecke."""
    bl = effective(s)
    out = {"name": t["name"], "sport": t["sport"], "date": datetime.fromtimestamp(t["start_ts"], tz=TZ).isoformat(), "blocks": bl, "show": False}
    if "zahlen" in bl:
        out.update(km=round((t["dist_m"] or 0) / 1000, 1), up_m=round(t["up_m"] or 0), down_m=round(t["down_m"] or 0), h=round((t["dur_s"] or 0) / 3600, 1))
    if "karte" in bl:
        out["coords"] = [[round(p[0], 5), round(p[1], 5)] for p in _down(pts, 800)]
    if "hoehe" in bl:
        prof, d, prev = [], 0.0, None
        for p in pts:
            if prev is not None:
                d += extras._hav((prev[0], prev[1]), (p[0], p[1]))
            prev = p
            if p[2] is not None:
                prof.append([round(d / 1000, 3), round(p[2])])
        out["prof"] = _down(prof, 300) if len(prof) > 1 else []
    if "fotos" in bl:
        out["photos"] = [p["id"] for p in photo_rows]
        out["photo_t"] = [_clock(p["taken_ts"]) if p["taken_ts"] else "" for p in photo_rows]
    if "notiz" in bl:
        n = db.one("SELECT note FROM tour_notes WHERE id=?", (t["id"],))
        if n and (n["note"] or "").strip():
            out["note"] = n["note"]
    if "wege" in bl:
        rows = db.query("SELECT ts,lat,lng,note FROM tour_wps WHERE tour_id=? ORDER BY ts,id LIMIT 200", (t["id"],))
        keep = [r for r in rows if r["lat"] is not None and r["lng"] is not None and not (s["trim"] and all_pts and _near_ends(all_pts, r["lat"], r["lng"], 300))]
        out["wps"] = [dict({"lat": round(r["lat"], 5), "lng": round(r["lng"], 5), "t": _clock(r["ts"]) if r["ts"] else ""},
                           **({"note": (r["note"] or "")[:300]} if "notiz" in bl and r["note"] else {})) for r in keep]
    if "puls" in bl:
        from . import puls
        series, _ = puls._series(t["id"])
        if len(series) >= 5:
            v = [p[1] for p in series]
            out["hr"] = {"pts": [[p[0], p[1]] for p in _down(series, 300)], "avg": round(sum(v) / len(v)), "max": max(v), "min": min(v)}
    if "wetter" in bl:
        c = db.one("SELECT js FROM weather WHERE id=?", (t["id"],))                       # nur Zwischengespeichertes: der öffentliche Aufruf fragt keinen Wetterdienst an
        try:
            w = json.loads(c["js"]) if c else None
        except ValueError:
            w = None
        if w:
            out["wx"] = {k: w[k] for k in ("text", "tmin", "tmax", "precip", "wind") if k in w}
    return out
