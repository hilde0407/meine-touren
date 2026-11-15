"""Seite anpassen (3.17.0): gespeicherte Anordnung der Abschnitte und Bausteine je Seite.

Schlüssel: „tour-haupt“ (Tourseite), „tour-auswertung“ (Unterseite Auswertung), „uebersicht“ (Übersicht).
Jeder Benutzer hat eine eigene Datenbank (app/ctx.py); die Tabelle `user_layout` ist daher je Benutzer getrennt, eine Spalte „user“ ist nicht nötig.
Dokument (JSON-Objekt, alle Felder optional):
  order    [id]            Reihenfolge der Abschnitte dieser Seite
  hidden   [id]            ausgeblendete Abschnitte
  closed   [id] / open [id] Abschnitte, die standardmäßig zu bzw. (abweichend vom Standard) offen sind
  page     {id: "haupt"|"auswertung"}  Abschnitte, die auf der anderen Seite der Tour liegen
  widgets  [{id, type, cfg}]  hinzugefügte Bausteine mit ihrer Konfiguration
  cfg      {id: {…}}       Konfiguration der Standard-Bausteine, die nicht als „widgets“ gespeichert sind (3.19.0: der Baustein „Dein Jahr“ der Übersicht, Kennung „jahr“)
  w        {id: Breite}    Breite im Raster (3.20.0): "voll" | "zweidrittel" | "halb" | "drittel"; gespeichert werden nur Abweichungen vom Standard des Abschnitts (den kennt die Oberfläche)
Seiteneignung (3.20.0): Bausteine der Übersicht dürfen auch auf der Tourseite stehen (Dokument „tour-haupt“); tour-bezogene Bausteine (TOUR_ONLY) nur auf Tourseiten,
das Dokument „uebersicht“ lehnt sie ab. Unbekannte Typen (neuere Version) bleiben überall erlaubt.
Gemeinsame Filterfelder in der Konfiguration (3.19.0, streng geprüft; unbekannte Schlüssel einer neueren Version bleiben erlaubt, wenn sie einfache Werte haben):
  sports   [Sportart]      leer = alle Aktivitäten      range  year | y | 12m | 90d | all      yr  Jahr (bei range = y)
  metrics  [count|km|up|h] angezeigte Kennzahlen         compare  Vorjahresvergleich an/aus    title  eigener Titel (höchstens 60 Zeichen)
  n        1…10 (Anzahl Einträge)                        basis  sport | all | year (Vergleichsbasis der Tourseite)
Der Server speichert nur, was er prüfen kann (erlaubte Felder, Kennungen, Größe); welche Abschnitte es gibt, weiß die Oberfläche.
Betrachter dürfen lesen, bekommen aber immer den Standard (das Layout des Besitzers wird nicht übernommen) und dürfen nichts schreiben.
"""
import json
import re
import time

from fastapi import APIRouter, HTTPException, Request

from . import db

router = APIRouter()

KEYS = ("tour-haupt", "tour-auswertung", "uebersicht")
FIELDS = {"v", "order", "hidden", "closed", "open", "page", "widgets", "cfg", "w"}
WIDTHS = ("voll", "zweidrittel", "halb", "drittel")
# Bausteine, die eine Tour brauchen (Typkennungen wie in static/js/50-bausteine.js und 51-bausteine-tour.js, fam "tour"): nicht in der Übersicht
TOUR_ONLY = frozenset(("kennzahlen", "tempo", "vergleich", "pulszonen", "wetter", "fotostreifen", "notiz", "splits", "steigung", "bewegung", "durchschnitt", "jahresrang",
                       "tageslicht", "gipfel", "vergleiche", "stimmung", "fotohighlights", "miniprofil", "steckbrief"))
ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,40}$")
MAX_IDS = 120
MAX_WIDGETS = 40
MAX_TEXT = 600                    # längster Text in der Konfiguration eines Bausteins (die Oberfläche begrenzt eigene Notizen auf 500)
MAX_BYTES = 24000
MAX_SPORTS = 20
SPORT_RE = re.compile(r"^[A-Za-z0-9_]{1,40}$")
RANGES = ("year", "y", "12m", "90d", "all")
METRICS = ("count", "km", "up", "h")
BASES = ("sport", "all", "year")
MAX_TITLE = 60


def _ids(v, name):
    if not isinstance(v, list) or len(v) > MAX_IDS:
        raise HTTPException(400, f"„{name}“ muss eine Liste mit höchstens {MAX_IDS} Einträgen sein")
    out = []
    for x in v:
        if not isinstance(x, str) or not ID_RE.match(x):
            raise HTTPException(400, f"Ungültige Kennung in „{name}“")
        if x not in out:
            out.append(x)
    return out


KNOWN = ("sports", "range", "yr", "metrics", "compare", "title", "n", "basis")


def _known(k, x):
    """Strenge Prüfung der gemeinsamen Filterfelder (3.19.0); gibt den bereinigten Wert zurück."""
    bad = HTTPException(400, f"Ungültiger Wert für „{k}“ in der Konfiguration")
    if k == "sports":
        if not isinstance(x, list) or len(x) > MAX_SPORTS or not all(isinstance(i, str) and SPORT_RE.match(i) for i in x):
            raise bad
        return list(dict.fromkeys(x))
    if k == "range":
        if x not in RANGES:
            raise bad
        return x
    if k == "yr":
        if isinstance(x, bool) or not isinstance(x, int) or not 1970 <= x <= 2100:
            raise bad
        return x
    if k == "metrics":
        if not isinstance(x, list) or not x or not all(i in METRICS for i in x):
            raise bad
        return list(dict.fromkeys(x))
    if k == "compare":
        if not isinstance(x, bool):
            raise bad
        return x
    if k == "title":
        if not isinstance(x, str) or len(x) > MAX_TITLE:
            raise bad
        return x.strip()
    if k == "n":
        if isinstance(x, bool) or not isinstance(x, int) or not 1 <= x <= 10:
            raise bad
        return x
    if k == "basis":
        if x not in BASES:
            raise bad
        return x
    return None


def _cfg(v):
    if not isinstance(v, dict) or len(v) > 20:
        raise HTTPException(400, "Ungültige Konfiguration eines Bausteins")
    out = {}
    for k, x in v.items():
        if not isinstance(k, str) or not ID_RE.match(k):
            raise HTTPException(400, "Ungültiger Schlüssel in der Konfiguration")
        if k in KNOWN:
            out[k] = _known(k, x)
            continue
        if isinstance(x, str):
            if len(x) > MAX_TEXT:
                raise HTTPException(400, "Text zu lang")
            out[k] = x
        elif isinstance(x, (bool, int, float)) or x is None:
            out[k] = x
        elif isinstance(x, list) and len(x) <= 20 and all(isinstance(i, str) and len(i) <= 40 for i in x):
            out[k] = x
        else:
            raise HTTPException(400, "Ungültiger Wert in der Konfiguration")
    return out


def clean(doc, key=None):
    """Prüft ein Layout-Dokument und gibt die bereinigte Fassung zurück (HTTPException 400 bei Fehlern)."""
    if not isinstance(doc, dict):
        raise HTTPException(400, "Das Layout muss ein JSON-Objekt sein")
    extra = set(doc) - FIELDS
    if extra:
        raise HTTPException(400, "Unbekannte Felder: " + ", ".join(sorted(map(str, extra))))
    out = {"v": 1}
    for k in ("order", "hidden", "closed", "open"):
        if k in doc:
            out[k] = _ids(doc[k], k)
    if "page" in doc:
        p = doc["page"]
        if not isinstance(p, dict) or len(p) > MAX_IDS:
            raise HTTPException(400, "„page“ muss ein Objekt sein")
        for k, x in p.items():
            if not ID_RE.match(str(k)) or x not in ("haupt", "auswertung"):
                raise HTTPException(400, "Ungültige Seite in „page“")
        out["page"] = dict(p)
    if "w" in doc:
        b = doc["w"]
        if not isinstance(b, dict) or len(b) > MAX_IDS or not all(isinstance(k, str) and ID_RE.match(k) for k in b):
            raise HTTPException(400, "„w“ muss ein Objekt mit Kennungen sein")
        if any(x not in WIDTHS for x in b.values()):
            raise HTTPException(400, "Ungültige Breite in „w“ (erlaubt: " + ", ".join(WIDTHS) + ")")
        out["w"] = dict(b)
    if "widgets" in doc:
        w = doc["widgets"]
        if not isinstance(w, list) or len(w) > MAX_WIDGETS:
            raise HTTPException(400, f"Höchstens {MAX_WIDGETS} Bausteine je Seite")
        seen, ws = set(), []
        for x in w:
            if not isinstance(x, dict) or set(x) - {"id", "type", "cfg"}:
                raise HTTPException(400, "Ungültiger Baustein")
            if not isinstance(x.get("id"), str) or not ID_RE.match(x["id"]) or not isinstance(x.get("type"), str) or not ID_RE.match(x["type"]):
                raise HTTPException(400, "Ungültige Kennung eines Bausteins")
            if x["id"] in seen:
                raise HTTPException(400, "Doppelte Kennung eines Bausteins")
            if key == "uebersicht" and x["type"] in TOUR_ONLY:
                raise HTTPException(400, "Dieser Baustein gehört zu einer Tour und kann nicht in der Übersicht stehen")
            seen.add(x["id"])
            ws.append({"id": x["id"], "type": x["type"], "cfg": _cfg(x.get("cfg") or {})})
        out["widgets"] = ws
    if "cfg" in doc:
        c = doc["cfg"]
        if not isinstance(c, dict) or len(c) > 10 or not all(isinstance(k, str) and ID_RE.match(k) for k in c):
            raise HTTPException(400, "„cfg“ muss ein Objekt mit höchstens 10 Einträgen sein")
        out["cfg"] = {k: _cfg(x) for k, x in c.items()}
    if len(json.dumps(out, ensure_ascii=False)) > MAX_BYTES:
        raise HTTPException(400, "Das Layout ist zu groß")
    return out


def _key(k):
    if k not in KEYS:
        raise HTTPException(404, "Unbekannte Seite")
    return k


def _viewer(request: Request):
    u = getattr(request.state, "user", None)
    return bool(u and u.get("role") == "viewer")


@router.get("/api/layout/{page_key}")
def get_layout(page_key: str, request: Request):
    _key(page_key)
    if _viewer(request):
        return {"key": page_key, "layout": None, "ts": None, "default": True}
    r = db.one("SELECT json,ts FROM user_layout WHERE page_key=?", (page_key,))
    if not r:
        return {"key": page_key, "layout": None, "ts": None}
    try:
        lay = json.loads(r["json"])
    except ValueError:
        lay = None
    return {"key": page_key, "layout": lay, "ts": r["ts"]}


@router.put("/api/layout/{page_key}")
async def put_layout(page_key: str, request: Request):
    _key(page_key)
    if _viewer(request):
        raise HTTPException(403, "Dieser Zugang darf nur ansehen")
    raw = await request.body()
    if len(raw) > MAX_BYTES * 2:
        raise HTTPException(413, "Das Layout ist zu groß")
    try:
        body = json.loads(raw or b"null")
    except ValueError:
        raise HTTPException(400, "Kein gültiges JSON")
    if isinstance(body, dict) and isinstance(body.get("layout"), dict) and set(body) <= {"layout", "key", "ts"}:
        body = body["layout"]                          # {"layout": {...}} wird wie das Dokument selbst angenommen
    lay = clean(body, page_key)
    ts = int(time.time())
    db.execute("INSERT INTO user_layout(page_key,json,ts) VALUES(?,?,?) ON CONFLICT(page_key) DO UPDATE SET json=excluded.json, ts=excluded.ts",
               (page_key, json.dumps(lay, ensure_ascii=False, separators=(",", ":")), ts))
    return {"ok": True, "key": page_key, "layout": lay, "ts": ts}


@router.delete("/api/layout/{page_key}")
def delete_layout(page_key: str, request: Request):
    _key(page_key)
    if _viewer(request):
        raise HTTPException(403, "Dieser Zugang darf nur ansehen")
    db.execute("DELETE FROM user_layout WHERE page_key=?", (page_key,))
    return {"ok": True, "key": page_key}
