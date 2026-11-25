"""Rückblick pro Tour „Wie ist es gelaufen?“ (3.48.0): Einordnung einer gelaufenen Tour OHNE verknüpften Plan.

Kein eigener Baustein (Modul tourrueckblick, weil app/rueckblick.py der teilbare Jahresrückblick ist): die Daten gehören zum bestehenden Tour-Baustein „Planung und Ergebnis“ (51-bausteine-tour.js). Hat die Tour einen verknüpften Plan, bleibt allein Planung und Ergebnis
maßgeblich (status "hat_plan", nichts wird doppelt gezeigt). Sonst werden Dauer, Strecke, Aufstieg und Tempo der Tour eingeordnet gegenüber

* den eigenen Touren derselben Sportgruppe in den 12 Monaten vor dieser Tour (ohne sie selbst), und
* den ähnlichen Touren (dieselbe Strecke, Erkennung wie „Ähnliche Touren im Vergleich“, app/aehnliche.py), auch mit mindestens MIN_N Vergleichstouren,

jeweils über planhilfe._metrik (Median-Verhältnis: unter 80 % kürzer/weniger/langsamer, über 125 % länger/mehr/schneller, dazwischen ähnlich; dazu Perzentil). Unter MIN_N
Vergleichstouren gibt es keine Einordnung ("zu_wenig"), nie einen Platzhalterwert oder eine 0. Dazu: „dein n-ter Besuch dieser Strecke“ aus der Wiederholungserkennung.
Nur lesend."""
from datetime import datetime

from fastapi import APIRouter, HTTPException

from . import aehnliche, db, planhilfe, wiederholungen
from .gpxtools import TZ

router = APIRouter()

MIN_N = planhilfe.MIN_N
MONATE = planhilfe.MONATE
MIN_DUR_S = aehnliche.MIN_DUR_S
MIN_DIST_M = aehnliche.MIN_DIST_M
KEYS = ("dauer", "strecke", "auf", "tempo")


def _werte(r):
    """Dauer (h), Strecke (km), Aufstieg (m), Tempo (km/h) einer Zeile; fehlende Werte None (nie 0)."""
    dist, dur, up = aehnliche._num(r.get("dist_m")), aehnliche._num(r.get("dur_s")), aehnliche._num(r.get("up_m"))
    ok = bool(dist and dur and dist >= MIN_DIST_M and dur >= MIN_DUR_S)
    return {"dauer": dur / 3600.0 if dur and dur >= MIN_DUR_S else None, "strecke": dist / 1000.0 if dist and dist > 0 else None, "auf": up if up is not None and up >= 0 else None,
            "tempo": dist / dur * 3.6 if ok else None}


def einordnen(cur, rows):
    """cur: Werte der Tour, rows: Zeilen der Vergleichstouren. Je Kennzahl die Einordnung aus planhilfe._metrik oder None (fehlt der Wert der Tour oder gibt es unter MIN_N Vergleichswerte)."""
    vs = [_werte(r) for r in rows]
    out = {}
    for k in KEYS:
        vals = [v[k] for v in vs if v[k] is not None]
        m = planhilfe._metrik(cur[k], vals) if cur[k] is not None else None
        out[k] = None if m is None else {"wert": round(cur[k], 3), "median": round(m["median"], 3), "n": m["n"], "verhaeltnis_median_pct": m["verhaeltnis_median_pct"],
                                         "einordnung": m["einordnung"], "perzentil": m["perzentil"]}
    return out


def _block(cur, rows):
    """{"n": Anzahl Vergleichstouren, "kennzahlen": …} oder None bei weniger als MIN_N Touren."""
    if len(rows) < MIN_N:
        return None
    k = einordnen(cur, rows)
    return {"n": len(rows), "kennzahlen": k} if any(k.values()) else None


def rueckblick(tour_id, now=None):
    t = db.one("SELECT id,name,sport,start_ts,dist_m,dur_s,up_m FROM tours WHERE id=?", (str(tour_id),))
    if not t:
        raise HTTPException(404, "Tour nicht gefunden")
    if db.one("SELECT 1 x FROM plans WHERE tour_id=? LIMIT 1", (t["id"],)):
        return {"status": "hat_plan"}                                                      # Planung und Ergebnis ist maßgeblich
    if not t["start_ts"]:
        return {"status": "zu_wenig", "min_n": MIN_N}
    lo = t["start_ts"] - MONATE * 30.4375 * 86400
    grp = planhilfe._grp(t["sport"])
    eigene = [r for r in db.query("SELECT id,sport,start_ts,dist_m,dur_s,up_m FROM tours WHERE start_ts>=? AND start_ts<? AND id<>?", (lo, t["start_ts"], t["id"]))
              if ((planhilfe._grp(r["sport"]) == grp) if grp else r["sport"] == t["sport"])]
    cur = _werte(t)
    out = {"status": "zu_wenig", "min_n": MIN_N, "monate": MONATE, "sport_n": len(eigene), "eigene": None, "aehnliche": None, "besuch": None}
    out["eigene"] = _block(cur, eigene)
    entry = (wiederholungen.api_repeats() or {}).get(t["id"])
    if entry and entry.get("with"):
        ids = [w["id"] for w in entry["with"]]
        sim = db.query("SELECT id,start_ts,dist_m,dur_s,up_m FROM tours WHERE id IN (%s) AND start_ts IS NOT NULL" % ",".join("?" * len(ids)), ids)
        # n-ter Besuch: Anzahl der Läufe dieser Strecke bis einschließlich dieser Tour (nur Besuche mit Zeitstempel, sonst ließe sich die Reihenfolge nicht angeben)
        out["besuch"] = {"nr": 1 + sum(1 for r in sim if r["start_ts"] < t["start_ts"]), "von": 1 + len(sim)}
        out["aehnliche"] = _block(cur, sim)
    if out["eigene"] or out["aehnliche"]:
        out["status"] = "ok"
    return out


@router.get("/api/tours/{tour_id}/rueckblick")
def api_rueckblick(tour_id: str):
    return rueckblick(tour_id)
