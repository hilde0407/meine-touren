"""Gebiete (3.64.0): dieselbe Gebietstabelle wie im Browser (app/static/js/gebiete-daten.js) für den Server.

Quelle ist allein gebiete-daten.js; app/gebiete.json wird daraus erzeugt (node scripts/gebiete_json.js) und tests/test_gebiete_364.py stellt sicher, dass die Datei aktuell ist und
`von()` hier dieselben Gebiete liefert wie `Gebiete.von()` im Browser – es gibt keine zweite Wahrheit.

Verwendet wird sie für den automatischen Namen erkannter Reisen (`trip_gebiet`, more2.build_trips). Alle Grenzen sind Näherungen (Rechtecke, einfache Vielecke; siehe Kopf von gebiete-daten.js)."""
import json
import re
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

DATEI = Path(__file__).with_name("gebiete.json")
REG = "region"
# Oberbegriffe, die als Reisename zu grob wären („Alpen“ für eine Reise durch Tirol und Südtirol): dann bleibt es beim Bundesland bzw. Land
ZU_GROB = {"alpen", "skandinavien", "karpaten"}
ANTEIL = 0.6        # ein Gebiet benennt eine Reise, wenn mindestens dieser Anteil ihrer Touren darin startet (sonst das nächstgrößere Gebiet, zuletzt Bundesland/Land)

_ERSATZ = (("ß", "ss"), ("æ", "ae"), ("œ", "oe"), ("ø", "o"), ("ð", "o"), ("đ", "d"), ("ł", "l"), ("ŀ", "l"), ("ı", "i"), ("þ", "th"))


def fold(s):
    """Wie `fold` in gebiete-daten.js: klein, ohne Akzente und Sonderzeichen."""
    s = "" if s is None else str(s).lower()
    for a, b in _ERSATZ:
        s = s.replace(a, b)
    s = "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.category(c).startswith("M"))
    return re.sub(r"[^a-z0-9]+", "", s)


def _kreis(s):
    return re.sub(r"^(landkreis|bezirk|kreis|provinz|provincia|stadt|kreisfreie|region)(di|von|de)?", "", fold(s))


def _in_box(b, la, ln):
    return b[0] <= la <= b[2] and b[1] <= ln <= b[3]


def _in_poly(ring, la, ln):
    c = False
    j = len(ring) - 1
    for i in range(len(ring)):
        yi, xi = ring[i]
        yj, xj = ring[j]
        if (yi > la) != (yj > la) and ln < (xj - xi) * (la - yi) / (yj - yi) + xi:
            c = not c
        j = i
    return c


@lru_cache(maxsize=1)
def _tabelle():
    daten = json.loads(DATEI.read_text(encoding="utf-8"))["gebiete"]
    by = {}
    for x in daten:
        x["kreise"] = [_kreis(c) for c in x["county"]]
        alle = [list(b) for b in x["boxen"]] + [[min(p[0] for p in r), min(p[1] for p in r), max(p[0] for p in r), max(p[1] for p in r)] for r in x["poly"]]
        x["hull"] = [min(b[0] for b in alle), min(b[1] for b in alle), max(b[2] for b in alle), max(b[3] for b in alle)] if alle else None
        x["flaeche"] = sum((b[2] - b[0]) * (b[3] - b[1]) for b in alle) or 1e9
        x["eigen"] = bool(x["boxen"] or x["poly"] or x["county"])
        by[x["id"]] = x
    for x in daten:
        n, e = 0, by.get(x["eltern"])
        while e and n < 10:
            n += 1
            e = by.get(e["eltern"])
        x["tiefe"] = n
    return daten, by


def _flaeche(x, la, ln):
    if la is None or not x["hull"] or not _in_box(x["hull"], la, ln):
        return False
    return any(_in_box(b, la, ln) for b in x["boxen"]) or any(_in_poly(r, la, ln) for r in x["poly"])


def _trifft(by, x, la, ln, kr):
    ok = False
    if la is not None and x["hull"]:
        ok = _flaeche(x, la, ln) and (not x["in"] or _flaeche(by[x["in"]], la, ln))
    if not ok and kr and kr in x["kreise"]:
        ok = True
    if not ok:
        return False
    for n in x["nicht"]:
        if isinstance(n, str):
            if _flaeche(by[n], la, ln):
                return False
        elif la is not None and _in_box(n, la, ln):
            return False
    return True


def _ok_ll(la, ln):
    try:
        la, ln = float(la), float(ln)
    except (TypeError, ValueError):
        return None
    if not (abs(la) <= 90 and abs(ln) <= 180) or (la == 0 and ln == 0) or la != la or ln != ln:
        return None
    return la, ln


@lru_cache(maxsize=20000)
def _von(la, ln, kr):
    daten, by = _tabelle()
    ids = set()
    for x in daten:
        if x["eigen"] and _trifft(by, x, la, ln, kr):
            ids.add(x["id"])
            n, e = 0, by.get(x["eltern"])
            while e and n < 10:
                ids.add(e["id"])
                n += 1
                e = by.get(e["eltern"])
    return tuple(i for i in sorted(ids, key=lambda i: (-by[i]["tiefe"], -by[i]["prio"], by[i]["flaeche"], i)))


def von(lat, lng, county=None):
    """Kennungen der Gebiete einer Koordinate, spezifischste zuerst (wie Gebiete.von im Browser; Eltern sind enthalten)."""
    ll = _ok_ll(lat, lng)
    return list(_von(ll[0] if ll else None, ll[1] if ll else None, _kreis(county) if county else ""))


def name(gid):
    return _tabelle()[1][gid]["name"]


def _rang(by, gid):
    x = by[gid]
    return (x["tiefe"], x["prio"], -x["flaeche"])


def trip_gebiet(tours):
    """Das Gebiet, das eine Reise am besten benennt, oder None (dann gilt der Name aus Bundesland/Land).

    Je Tour zählen alle Gebiete, in denen sie startet (inklusive der übergeordneten). Genommen wird das spezifischste Gebiet (am tiefsten in der Eltern-Kette, dann das kleinere), in dem
    mindestens 60 % der Touren starten: eine Reise nur auf La Gomera heißt „La Gomera“, eine Rundreise über mehrere Kanareninseln „Kanaren“ (der Oberbegriff, in dem alle liegen),
    eine Reise mit Touren in Lungau, Pongau und Pinzgau bleibt „Salzburg“ (kein Gebiet erreicht 60 %, „Alpen“ ist als Name zu grob). Touren ohne Koordinate oder ohne Gebiet zählen mit."""
    _, by = _tabelle()
    n = len(tours)
    if not n:
        return None
    cnt = Counter()
    for t in tours:
        cnt.update(set(von(t.get("lat"), t.get("lng"), t.get("g_county"))))
    ok = [g for g, c in cnt.items() if c / n >= ANTEIL and g not in ZU_GROB]
    if not ok:
        return None
    best = max(ok, key=lambda g: (_rang(by, g), cnt[g], g))
    return {"id": best, "name": by[best]["name"], "typ": by[best]["typ"], "anteil": round(cnt[best] / n, 2)}
