"""Belastung und Erholung: die Trainingsbelastung laut Uhr (exercise_load aus den Zusatzdateien <Tour>.uhr.json) je Woche und Monat.

Rein lesend: Es werden nur Zusatzdateien gelesen, die schon vorhanden sind (beim Öffnen einer Tour oder durch den Job „Uhr-Daten aller Touren laden“ gespeichert).
Kein Zepp-Abruf.

Grundsatz „ohne Angabe“: Eine Tour ohne Uhr-Wert zählt NIE als 0. Eine Woche/ein Monat mit Touren, aber ohne einen einzigen Uhr-Wert hat keine Belastung (None).
Eine Woche ganz ohne Tour ist dagegen bekannt ruhig (0 Touren, keine Balken) – sie zählt im Vergleich „Aktuell“ als Woche mit Belastung 0.
"""
import re
from datetime import datetime, timedelta
from statistics import mean

from fastapi import APIRouter, HTTPException

from . import db, mydevices, uhrtraining
from .gpxtools import TZ

router = APIRouter()

# --- Schwellen für „Aktuell im Vergleich“ (Belastung der letzten 4 Wochen gegen den Wochenschnitt der 12 Wochen davor) ---
# WILLKÜRLICH gewählt, nicht wissenschaftlich begründet: Die Wochenbelastung eines Freizeitsportlers schwankt von Woche zu Woche von sich aus um
# gut ein Zehntel bis ein Fünftel (Wetter, Termine). Unter ±15 % ist ein Unterschied daher kein Unterschied („ähnlich wie sonst“);
# ab ±40 % ist er eindeutig außerhalb dieser üblichen Schwankung („deutlich“). Dazwischen: „etwas“.
ETWAS = 0.15
DEUTLICH = 0.40
RECENT_WEEKS, BASE_WEEKS, MIN_BASE_WEEKS = 4, 12, 8        # Vergleichsfenster; Mindestzahl Wochen mit Uhr-Daten in den 12 Vergleichswochen
MAX_BUCKETS = 1500
DATE_RE = re.compile(r"^\d{4}-\d\d-\d\d$")

_CACHE = {}                                                 # Zusatzdatei -> (Änderungszeit, Größe, Belastung oder None)


def _load_value(tid):
    """Belastung (plausibler Wert laut uhrtraining.kennzahlen) aus der Zusatzdatei einer Tour, sonst None. Mit Zwischenspeicher nach Änderungszeit."""
    p = uhrtraining.sidecar(tid)
    try:
        st = p.stat()
    except OSError:
        return None
    key = str(p)
    c = _CACHE.get(key)
    if c and c[0] == st.st_mtime_ns and c[1] == st.st_size:
        return c[2]
    d = uhrtraining.load(tid)
    v = None
    if d:
        w = uhrtraining.kennzahlen(d["summary"]).get("last")
        v = w["wert"] if w else None
    if len(_CACHE) > 20000:
        _CACHE.clear()
    _CACHE[key] = (st.st_mtime_ns, st.st_size, v)
    return v


def _day(ts):
    return datetime.fromtimestamp(ts, tz=TZ).date()


def _monday(d):
    return d - timedelta(days=d.weekday())


def _bounds(von, bis):
    """Datum (JJJJ-MM-TT, Ortszeit, beide inklusive) -> (Start-ts, Ende-ts) oder None je Seite."""
    out = []
    for v, end in ((von, False), (bis, True)):
        if not v:
            out.append(None)
            continue
        if not DATE_RE.match(v):
            raise HTTPException(400, "Datum bitte als JJJJ-MM-TT angeben")
        try:
            d = datetime.strptime(v, "%Y-%m-%d").replace(tzinfo=TZ)
        except ValueError:
            raise HTTPException(400, "Datum bitte als JJJJ-MM-TT angeben")
        out.append(int((d + timedelta(days=1)).timestamp()) - 1 if end else int(d.timestamp()))
    if out[0] is not None and out[1] is not None and out[0] > out[1]:
        raise HTTPException(400, "„von“ liegt nach „bis“")
    return out[0], out[1]


def _bucket(key, label, von, bis):
    return {"key": key, "label": label, "von": von.isoformat(), "bis": bis.isoformat(), "touren": 0, "mit_daten": 0, "ohne_angabe": 0, "belastung": None}


def _add(b, v):
    b["touren"] += 1
    if v is None:
        b["ohne_angabe"] += 1
    else:
        b["mit_daten"] += 1
        b["belastung"] = (b["belastung"] or 0) + v


def _weeks(tours, lo, hi):
    """Wochen (Montag bis Sonntag) lückenlos von lo bis hi (Datum); leere Wochen haben 0 Touren."""
    out, d = {}, _monday(lo)
    while d <= hi:
        iso = d.isocalendar()
        out[d] = _bucket(d.isoformat(), f"KW {iso[1]}/{iso[0]}", d, d + timedelta(days=6))
        d += timedelta(days=7)
    for t in tours:
        _add(out[_monday(t["day"])], t["v"])
    return list(out.values())


def _months(tours, lo, hi):
    out, y, m = {}, lo.year, lo.month
    while (y, m) <= (hi.year, hi.month):
        first = datetime(y, m, 1).date()
        last = (datetime(y + (m == 12), m % 12 + 1, 1).date() - timedelta(days=1))
        out[(y, m)] = _bucket(f"{y}-{m:02d}", f"{m:02d}/{y}", first, last)
        y, m = y + (m == 12), m % 12 + 1
    for t in tours:
        _add(out[(t["day"].year, t["day"].month)], t["v"])
    return list(out.values())


def _round(v):
    return None if v is None else round(v)


def aktuell(rows, now):
    """„Aktuell im Vergleich“: Belastung der letzten 4 Wochen (28 Tage bis jetzt) gegen den Wochenschnitt der 12 Wochen davor.
    rows = [{"ts", "v"}] aller Touren (v = Belastung oder None). Wochen sind 7-Tage-Blöcke, vom Jetzt aus rückwärts gezählt.
    Ein Block gilt als bekannt, wenn er mindestens einen Uhr-Wert hat oder gar keine Tour (ruhig = 0); Blöcke mit Touren, aber ohne Uhr-Wert, bleiben außen vor."""
    t_now = now.timestamp()
    blocks = []
    for i in range(RECENT_WEEKS + BASE_WEEKS):
        hi, lo = t_now - i * 7 * 86400, t_now - (i + 1) * 7 * 86400
        inside = [r for r in rows if lo < r["ts"] <= hi]
        vals = [r["v"] for r in inside if r["v"] is not None]
        blocks.append({"touren": len(inside), "mit_daten": len(vals), "summe": sum(vals)})
    recent, base = blocks[:RECENT_WEEKS], blocks[RECENT_WEEKS:]

    def known(bl):
        return [b["summe"] for b in bl if b["mit_daten"] > 0 or b["touren"] == 0]
    base_data = sum(1 for b in base if b["mit_daten"] > 0)
    rec_data = sum(1 for b in recent if b["mit_daten"] > 0)
    out = {"status": "ok", "wochen_mit_daten_basis": base_data, "wochen_mit_daten_aktuell": rec_data, "mindestens": MIN_BASE_WEEKS,
           "aktuell_schnitt": None, "basis_schnitt": None, "abweichung_pct": None, "stufe": None}
    if base_data < MIN_BASE_WEEKS:
        out["status"] = "zu_wenig_daten"
        return out
    if rec_data == 0:
        out["status"] = "keine_aktuellen_daten"
        return out
    a, b = mean(known(recent)), mean(known(base))
    if b <= 0:
        out["status"] = "zu_wenig_daten"
        return out
    r = round(a / b - 1, 6)                                  # gerundet, damit genau 15 % bzw. 40 % nicht an Gleitkomma-Rauschen scheitern
    out.update(aktuell_schnitt=round(a), basis_schnitt=round(b), abweichung_pct=round(r * 100),
               stufe="deutlich_mehr" if r >= DEUTLICH else "mehr" if r >= ETWAS else "deutlich_weniger" if r <= -DEUTLICH else "weniger" if r <= -ETWAS else "aehnlich")
    return out


def compute(von="", bis="", now=None):
    now = now or datetime.now(TZ)
    t_lo, t_hi = _bounds(von, bis)
    allrows = db.query("SELECT id,name,start_ts,dist_m FROM tours WHERE start_ts IS NOT NULL ORDER BY start_ts")
    for t in allrows:
        t["v"] = _load_value(t["id"])
        t["ts"] = t["start_ts"]
        t["day"] = _day(t["start_ts"])
    rows = [t for t in allrows if (t_lo is None or t["ts"] >= t_lo) and (t_hi is None or t["ts"] <= t_hi)]
    res = {"von": von or None, "bis": bis or None, "wochen": [], "monate": [], "haertest_wochen": [], "haertest_touren": [],
           "gesamt": {"touren": len(rows), "mit_daten": 0, "anteil_pct": None, "belastung": None}}
    if rows:
        lo = _day(t_lo) if t_lo is not None else rows[0]["day"]
        hi = _day(t_hi) if t_hi is not None else rows[-1]["day"]
        if (hi - lo).days / 7 > MAX_BUCKETS:
            raise HTTPException(400, "Zeitraum zu groß")
        res["wochen"] = _weeks(rows, lo, hi)
        res["monate"] = _months(rows, lo, hi)
        data = [t for t in rows if t["v"] is not None]
        g = res["gesamt"]
        g["mit_daten"] = len(data)
        g["anteil_pct"] = round(100 * len(data) / len(rows))
        g["belastung"] = _round(sum(t["v"] for t in data)) if data else None
        for b in res["wochen"] + res["monate"]:
            b["belastung"] = _round(b["belastung"])
        wk = [b for b in res["wochen"] if b["belastung"] is not None]
        res["haertest_wochen"] = sorted(wk, key=lambda b: (-b["belastung"], b["von"]))[:5]
        res["haertest_touren"] = [{"id": t["id"], "name": t["name"], "datum": t["day"].isoformat(), "km": round((t["dist_m"] or 0) / 1000, 1), "belastung": _round(t["v"])}
                                  for t in sorted(data, key=lambda t: (-t["v"], t["ts"]))[:5]]
    res["daten_insgesamt"] = sum(1 for t in allrows if t["v"] is not None)          # Touren mit Uhr-Wert überhaupt (unabhängig vom Zeitraum): entscheidet, ob die Oberfläche den Abschnitt zeigt
    res["aktuell"] = aktuell(allrows, now)
    res["offen"] = {"zepp_ohne_werte": _pending(allrows), "job": "uhr-alle"}
    res["hinweis"] = "Zepp-Werte werden beim ersten Öffnen einer Tour gespeichert."
    return res


def _pending(allrows):
    """Anzahl Touren mit Zepp-Uhr, zu denen noch keine Zusatzdatei vorliegt."""
    srcs = {r["tour_id"]: r["src"] for r in db.query("SELECT tour_id, src FROM tour_source")}
    n = 0
    for t in allrows:
        if mydevices.tour_kind(t["id"], srcs.get(t["id"], "")) == "zepp" and not uhrtraining.sidecar(t["id"]).exists():
            n += 1
    return n


@router.get("/api/stats/belastung")
def api_belastung(von: str = "", bis: str = ""):
    return compute(von, bis)
