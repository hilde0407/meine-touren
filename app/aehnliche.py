"""Ähnliche Touren im Vergleich (3.14.0): frühere und spätere Wiederholungen derselben Strecke mit Dauer, Strecke, Aufstieg und Tempo.

Welche Touren dieselbe Strecke gehen, entscheidet allein die vorhandene Wiederholungserkennung (app/wiederholungen.py, api_repeats) – hier wird nichts
neu erkannt. Dieses Modul liest nur die Kennzahlen der gefundenen Touren aus der Datenbank, rechnet das Durchschnittstempo (Strecke / Gesamtzeit),
die Abweichung jeder Wiederholung zur gewählten Tour und eine Kurzaussage („schneller als 4 von 6 früheren Läufen“, „bestes Tempo bisher“).

Fehlt bei einer Tour Zeit oder Strecke, bleibt ihr Tempo leer (None, nie 0): Sie wird aufgelistet, zählt aber im Vergleich nicht mit.
Verändert wird nichts; ohne Wiederholung gibt es nur {"status": "keine_wiederholung"}.
"""
from datetime import datetime

from fastapi import APIRouter, HTTPException

from . import db, mydevices, wiederholungen
from .gpxtools import TZ

router = APIRouter()

MIN_DUR_S = 60                 # kürzere Zeiten gelten als Platzhalter
MIN_DIST_M = 1000              # wie in der Wiederholungserkennung


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def _row(t, dev):
    dist, dur, up = _num(t.get("dist_m")), _num(t.get("dur_s")), _num(t.get("up_m"))
    ok = bool(dist and dur and dist >= MIN_DIST_M and dur >= MIN_DUR_S)
    ts = int(t["start_ts"])
    return {"id": t["id"], "name": t.get("name") or "", "start_ts": ts, "datum": datetime.fromtimestamp(ts, tz=TZ).strftime("%Y-%m-%d"),
            "dauer_s": round(dur) if dur and dur >= MIN_DUR_S else None, "strecke_m": round(dist) if dist else None, "auf_m": round(up) if up is not None else None,
            "tempo_kmh": round(dist / dur * 3.6, 2) if ok else None, "geraet": dev.get("name") if dev else None}


def _diff(r, cur):
    """Abweichung einer Wiederholung zur gewählten Tour (r minus aktuell; Tempo in Prozent der aktuellen Tour). Fehlt eine Seite: None."""
    d = {}
    for key, src in (("dauer_s", "dauer_s"), ("strecke_m", "strecke_m"), ("auf_m", "auf_m")):
        d[key] = r[src] - cur[src] if r[src] is not None and cur[src] is not None else None
    d["tempo_pct"] = round((r["tempo_kmh"] / cur["tempo_kmh"] - 1) * 100, 1) if r["tempo_kmh"] and cur["tempo_kmh"] else None
    return d


def _aussage(cur, others):
    """Kurzaussage als Schlüssel plus Zahlen; die Oberfläche formuliert den Text. None, wenn die gewählte Tour kein Tempo hat oder nichts vergleichbar ist."""
    if cur["tempo_kmh"] is None:
        return None
    frueher = [o for o in others if o["start_ts"] < cur["start_ts"] and o["tempo_kmh"] is not None]
    spaeter = [o for o in others if o["start_ts"] > cur["start_ts"] and o["tempo_kmh"] is not None]
    langsamer = sum(1 for o in frueher if o["tempo_kmh"] < cur["tempo_kmh"])
    out = {"frueher": len(frueher), "schneller_als": langsamer, "spaeter": len(spaeter), "spaeter_schneller": sum(1 for o in spaeter if o["tempo_kmh"] > cur["tempo_kmh"])}
    if frueher:
        out["art"] = "bestes_bisher" if langsamer == len(frueher) else "langsamer_als_alle" if langsamer == 0 else "schneller_als"
    elif spaeter:
        out["art"] = "erster"
    else:
        return None
    return out


def compare(tour_id):
    t = db.one("SELECT id,name,start_ts,dist_m,dur_s,up_m FROM tours WHERE id=?", (str(tour_id),))
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    entry = (wiederholungen.api_repeats() or {}).get(t["id"])
    if not entry or t.get("start_ts") is None:
        return {"status": "keine_wiederholung"}
    ids = [w["id"] for w in entry["with"]]
    found = {r["id"]: r for r in db.query("SELECT id,name,start_ts,dist_m,dur_s,up_m FROM tours WHERE id IN (%s) AND start_ts IS NOT NULL" % ",".join("?" * len(ids)), ids)} if ids else {}
    if not found:
        return {"status": "keine_wiederholung"}
    try:
        asg = mydevices.assignments()
    except Exception:  # noqa
        asg = {}
    dev = lambda i: (asg.get(i) or (None, False))[0]  # noqa: E731
    cur = _row(t, dev(t["id"]))
    others = [_row(r, dev(r["id"])) for r in found.values()]
    for o in others:
        o["abweichung"] = _diff(o, cur)
    rows = sorted(others + [dict(cur, aktuell=True)], key=lambda r: (r["start_ts"], r["id"]))
    for r in rows:
        r.setdefault("aktuell", False)
    best = max((r for r in rows if r["tempo_kmh"] is not None), key=lambda r: r["tempo_kmh"], default=None)
    return {"status": "ok", "touren": rows, "anzahl": len(rows), "aussage": _aussage(cur, others), "bestes_id": best["id"] if best else None,
            "mit_tempo": sum(1 for r in rows if r["tempo_kmh"] is not None)}


@router.get("/api/tours/{tour_id}/aehnliche")
def api_aehnliche(tour_id: str):
    return compare(tour_id)
