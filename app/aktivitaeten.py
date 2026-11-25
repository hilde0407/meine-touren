"""3.59.0/3.60.0 Aktivitäten: Katalog (app/gpxtools.py CATALOG) und Favoriten-Aktivitäten je Benutzer.

Favoriten: geordnete Liste (höchstens 12) in der Tabelle `settings` unter `fav_sports` (JSON) – damit in jeder Sicherung, Wiederherstellung und im Umzugspaket.
3.60.0: Katalog mit 29 Aktivitäten – entfernte Aktivitäten (gpxtools.RUECKFALL, z. B. „golf“ aus 3.59.0) fallen beim Lesen und Speichern still weg.
Ohne Einstellung gilt FAV_DEF (Wandern, Laufen, Radtour, Skitour, Mountainbike). Die Oberfläche bietet die Favoriten überall zuerst an, wo eine Tour
aufgenommen oder angelegt wird (Aufzeichnen, Planung), dazu „Mehr …“ mit allen Kategorien.
"""
import json

from fastapi import APIRouter, HTTPException, Request

from . import db, gpxtools

router = APIRouter()

KEY = "fav_sports"
MAX_FAV = 12
FAV_DEF = ["hike", "jogging", "touringbicycle", "skitour", "mtb"]


def katalog():
    return [{"id": k, "name": n, "sports": [s for s, _, _, c in gpxtools.CATALOG if c == k]} for k, n in gpxtools.KATEGORIEN]


def pruefen(raw):
    if not isinstance(raw, list) or not raw:
        raise HTTPException(400, "Bitte mindestens eine Favoriten-Aktivität wählen")
    out = []
    for s in raw:
        if isinstance(s, str) and s in gpxtools.RUECKFALL:               # 3.60.0: entfernte Aktivität (älterer Stand der Oberfläche): still weglassen
            continue
        if not isinstance(s, str) or s not in gpxtools.LABEL:
            raise HTTPException(400, "Unbekannte Aktivität")
        if s not in out:
            out.append(s)
    if not out:
        raise HTTPException(400, "Bitte mindestens eine Favoriten-Aktivität wählen")
    if len(out) > MAX_FAV:
        raise HTTPException(400, f"Höchstens {MAX_FAV} Favoriten")
    return out


def favoriten():
    v = db.get(KEY)
    try:
        raw = json.loads(v) if v else None
    except (ValueError, TypeError):
        raw = None
    if not isinstance(raw, list):
        return list(FAV_DEF)
    out = [s for s in dict.fromkeys(x for x in raw if isinstance(x, str)) if s in gpxtools.LABEL][:MAX_FAV]
    return out or list(FAV_DEF)


@router.get("/api/aktivitaeten/favoriten")
def api_favoriten():
    return {"favoriten": favoriten(), "standard": list(FAV_DEF), "max": MAX_FAV, "kategorien": katalog()}


@router.put("/api/aktivitaeten/favoriten")
async def api_favoriten_speichern(request: Request):
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, "Ungültige Anfrage")
    if not isinstance(body, dict) or "favoriten" not in body:
        raise HTTPException(400, "„favoriten“ fehlt")
    fav = pruefen(body["favoriten"])
    db.put(KEY, json.dumps(fav))
    return {"ok": True, "favoriten": fav}
