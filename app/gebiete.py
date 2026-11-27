"""Gebiete (3.64.0): dieselbe Gebietstabelle wie im Browser (app/static/js/gebiete-daten.js) für den Server.
3.65.0: dazu eigene Gebiete (Tabelle gebiet_custom: Name, Typ, ein Rechteck), gesucht über Nominatim (Ortssuche) und frei bearbeitbar; sie rechnen wie eingebaute Gebiete (gleiche Funktion `von`,
im Browser `Gebiete.setEigene`), erscheinen in Filter, Suche, Reisenamen und Übersicht und haben die Quelle „eigen“.

Quelle ist allein gebiete-daten.js; app/gebiete.json wird daraus erzeugt (node scripts/gebiete_json.js) und tests/test_gebiete_364.py stellt sicher, dass die Datei aktuell ist und
`von()` hier dieselben Gebiete liefert wie `Gebiete.von()` im Browser – es gibt keine zweite Wahrheit.

Verwendet wird sie für den automatischen Namen erkannter Reisen (`trip_gebiet`, more2.build_trips). Alle Grenzen sind Näherungen (Rechtecke, einfache Vielecke; siehe Kopf von gebiete-daten.js)."""
import json
import re
import secrets
import time
import unicodedata
from collections import Counter
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException

from . import db

router = APIRouter()

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


TYPEN = ("gebirge", "tal", "insel", "kueste", "region")
EIGEN_PREFIX = "eigen-"
MAX_EIGENE = 200
EIGEN_TIEFE = 99                # eigene Gebiete gehen bei Anzeige und Reisename vor (wie eigene Reisen und eigene Namen); Tiefe sonst = Länge der Eltern-Kette
MAX_SPANNE = (30.0, 60.0)       # größtes Rechteck eines eigenen Gebiets (Grad Breite, Grad Länge): „Alpen“ ist 5° × 13°, ein Land wie Norwegen 13° × 30°


def _ableiten(x):
    alle = [list(b) for b in x["boxen"]] + [[min(p[0] for p in r), min(p[1] for p in r), max(p[0] for p in r), max(p[1] for p in r)] for r in x["poly"]]
    x["hull"] = [min(b[0] for b in alle), min(b[1] for b in alle), max(b[2] for b in alle), max(b[3] for b in alle)] if alle else None
    x["flaeche"] = sum((b[2] - b[0]) * (b[3] - b[1]) for b in alle) or 1e9
    x["eigen"] = bool(x["boxen"] or x["poly"] or x["county"])        # „hat eine Fläche“ (reine Oberbegriffe gelten nur über ihre Kinder), nicht „eigenes Gebiet“ – das ist quelle == "eigen"
    return x


@lru_cache(maxsize=1)
def _basis():
    daten = json.loads(DATEI.read_text(encoding="utf-8"))["gebiete"]
    by = {}
    for x in daten:
        x["kreise"] = [_kreis(c) for c in x["county"]]
        x["quelle"] = "eingebaut"
        _ableiten(x)
        by[x["id"]] = x
    for x in daten:
        n, e = 0, by.get(x["eltern"])
        while e and n < 10:
            n += 1
            e = by.get(e["eltern"])
        x["tiefe"] = n
    return daten, by


def _eigen_zeile(e):
    """Ein eigenes Gebiet (id, name, typ, süd, west, nord, ost) als Eintrag der Tabelle: ein Rechteck, kein Elternteil, kein Bezirk, Tiefe 99 – so rechnet auch Gebiete.setEigene im Browser."""
    gid, name, typ, s, w, n, o = e
    return _ableiten({"id": gid, "name": name, "typ": typ, "eltern": None, "boxen": [[s, w, n, o]], "poly": [], "alias": [], "county": [], "nicht": [], "in": None, "prio": 0, "anz": True,
                      "kreise": [], "quelle": "eigen", "tiefe": EIGEN_TIEFE})


@lru_cache(maxsize=16)
def _tabelle(eig=()):
    """(Liste, nach Kennung): die eingebauten Gebiete und die übergebenen eigenen (Tupel von (id, name, typ, süd, west, nord, ost), siehe `eigene_laden`)."""
    daten, by = _basis()
    if not eig:
        return daten, by
    extra = [_eigen_zeile(e) for e in eig]
    return daten + extra, {**by, **{x["id"]: x for x in extra}}


def eigene_laden():
    """Eigene Gebiete der Datenbank als hashbares Tupel (leer, wenn es keine gibt oder keine Datenbank erreichbar ist)."""
    try:
        rows = db.query("SELECT id,name,typ,box FROM gebiet_custom ORDER BY created, id")
    except Exception:  # noqa
        return ()
    out = []
    for r in rows:
        try:
            s, w, n, o = (float(v) for v in json.loads(r["box"]))
        except (TypeError, ValueError):
            continue
        if r["typ"] in TYPEN and s < n and w < o:
            out.append((r["id"], r["name"], r["typ"], s, w, n, o))
    return tuple(out)


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
def _von(la, ln, kr, eig=()):
    daten, by = _tabelle(eig)
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


def von(lat, lng, county=None, eigene=None):
    """Kennungen der Gebiete einer Koordinate, spezifischste zuerst (wie Gebiete.von im Browser; Eltern sind enthalten).
    eigene: die eigenen Gebiete (Tupel wie `eigene_laden`); ohne Angabe werden sie aus der Datenbank gelesen."""
    ll = _ok_ll(lat, lng)
    eig = eigene_laden() if eigene is None else tuple(eigene)
    return list(_von(ll[0] if ll else None, ll[1] if ll else None, _kreis(county) if county else "", eig))


def name(gid):
    return _tabelle(eigene_laden())[1][gid]["name"]


def _rang(by, gid):
    x = by[gid]
    return (x["tiefe"], x["prio"], -x["flaeche"])


def trip_gebiet(tours, eigene=None):
    """Das Gebiet, das eine Reise am besten benennt, oder None (dann gilt der Name aus Bundesland/Land).

    Je Tour zählen alle Gebiete, in denen sie startet (inklusive der übergeordneten). Genommen wird das spezifischste Gebiet (am tiefsten in der Eltern-Kette, dann das kleinere), in dem
    mindestens 60 % der Touren starten: eine Reise nur auf La Gomera heißt „La Gomera“, eine Rundreise über mehrere Kanareninseln „Kanaren“ (der Oberbegriff, in dem alle liegen),
    eine Reise mit Touren in Lungau, Pongau und Pinzgau bleibt „Salzburg“ (kein Gebiet erreicht 60 %, „Alpen“ ist als Name zu grob). Touren ohne Koordinate oder ohne Gebiet zählen mit."""
    eig = eigene_laden() if eigene is None else tuple(eigene)
    _, by = _tabelle(eig)
    n = len(tours)
    if not n:
        return None
    cnt = Counter()
    for t in tours:
        cnt.update(set(von(t.get("lat"), t.get("lng"), t.get("g_county"), eig)))
    ok = [g for g, c in cnt.items() if c / n >= ANTEIL and g not in ZU_GROB]
    if not ok:
        return None
    best = max(ok, key=lambda g: (_rang(by, g), cnt[g], g))
    return {"id": best, "name": by[best]["name"], "typ": by[best]["typ"], "anteil": round(cnt[best] / n, 2)}


# ---------- Eigene Gebiete (3.65.0) ----------
def tour_ids(gid, eigene=None):
    """Kennungen aller Touren, deren Startpunkt im Gebiet liegt (wie `inGebiet` im Browser)."""
    eig = eigene_laden() if eigene is None else tuple(eigene)
    return [r["id"] for r in db.query("SELECT t.id, t.lat, t.lng, g.county FROM tours t LEFT JOIN tour_geo g ON g.id=t.id WHERE t.start_ts IS NOT NULL ORDER BY t.start_ts")
            if gid in von(r["lat"], r["lng"], r["county"], eig)]


def _box(v):
    """Rechteck [Süd, West, Nord, Ost] prüfen: Zahlen, gültige Grade, Süd < Nord, West < Ost (nicht über den 180. Längengrad), nicht größer als MAX_SPANNE."""
    if not isinstance(v, (list, tuple)) or len(v) != 4:
        raise HTTPException(400, "Das Rechteck braucht vier Werte: Süd, West, Nord, Ost")
    try:
        s, w, n, o = (float(x) for x in v)
    except (TypeError, ValueError):
        raise HTTPException(400, "Die Grenzen des Rechtecks müssen Zahlen sein")
    if any(x != x or abs(x) == float("inf") for x in (s, w, n, o)) or abs(s) > 90 or abs(n) > 90 or abs(w) > 180 or abs(o) > 180:
        raise HTTPException(400, "Breite muss zwischen −90 und 90 liegen, Länge zwischen −180 und 180")
    if not s < n:
        raise HTTPException(400, "Süd muss kleiner sein als Nord")
    if not w < o:
        raise HTTPException(400, "West muss kleiner sein als Ost (Gebiete über den 180. Längengrad hinweg sind nicht möglich)")
    if n - s > MAX_SPANNE[0] or o - w > MAX_SPANNE[1]:
        raise HTTPException(400, f"Das Rechteck ist zu groß (höchstens {MAX_SPANNE[0]:.0f}° Breite und {MAX_SPANNE[1]:.0f}° Länge)")
    return [round(s, 5), round(w, 5), round(n, 5), round(o, 5)]


def _clean(body, own=None):
    name = re.sub(r"\s+", " ", str(body.get("name") or "")).strip()
    if not name:
        raise HTTPException(400, "Bitte einen Namen eingeben")
    if len(name) > 80 or re.search(r"[<>\x00-\x1f\x7f]", name):
        raise HTTPException(400, "Der Name darf höchstens 80 Zeichen lang sein (ohne Spitzklammern und Steuerzeichen)")
    typ = body.get("typ")
    if typ not in TYPEN:
        raise HTTPException(400, "Typ bitte wählen: Gebirge, Tal, Insel, Küste oder Landschaft")
    box = _box(body.get("box"))
    land = re.sub(r"\s+", " ", str(body.get("land") or "")).strip()[:60]
    quelle = re.sub(r"\s+", " ", str(body.get("quelle") or "")).strip()[:200]
    f = fold(name)
    for x in _tabelle(eigene_laden())[0]:
        if x["id"] != own and fold(x["name"]) == f:
            raise HTTPException(400, f"Ein Gebiet „{x['name']}“ gibt es schon" + (" (eingebaut). Mit einem anderen Namen, z. B. „" + name + " (eigene Grenzen)“, geht es." if x["quelle"] == "eingebaut" else ""))
    return name, typ, box, land, quelle


def _out(r):
    return {"id": r["id"], "name": r["name"], "typ": r["typ"], "box": json.loads(r["box"]), "land": r["land"] or "", "quelle": r["quelle"] or "", "created": r["created"]}


@router.get("/api/gebiete/eigene")
def api_eigene():
    """Eigene Gebiete (Name, Typ, Rechteck [Süd, West, Nord, Ost], Land); der Browser rechnet damit wie mit den eingebauten Gebieten."""
    return [_out(r) for r in db.query("SELECT * FROM gebiet_custom ORDER BY created, id")]


@router.post("/api/gebiete/eigene")
def api_eigene_neu(body: dict):
    if db.one("SELECT COUNT(*) n FROM gebiet_custom")["n"] >= MAX_EIGENE:
        raise HTTPException(400, f"Höchstens {MAX_EIGENE} eigene Gebiete")
    name, typ, box, land, quelle = _clean(body)
    gid = EIGEN_PREFIX + secrets.token_hex(4)
    db.execute("INSERT INTO gebiet_custom(id,name,typ,box,land,quelle,created) VALUES(?,?,?,?,?,?,?)", (gid, name, typ, json.dumps(box), land, quelle, int(time.time())))
    return {"ok": True, "id": gid}


@router.post("/api/gebiete/eigene/{gid}")
def api_eigene_aendern(gid: str, body: dict):
    if not db.one("SELECT 1 x FROM gebiet_custom WHERE id=?", (gid,)):
        raise HTTPException(404, "Eigenes Gebiet nicht gefunden")
    name, typ, box, land, quelle = _clean(body, gid)
    db.execute("UPDATE gebiet_custom SET name=?, typ=?, box=?, land=?, quelle=? WHERE id=?", (name, typ, json.dumps(box), land, quelle, gid))
    return {"ok": True}


@router.delete("/api/gebiete/eigene/{gid}")
def api_eigene_loeschen(gid: str):
    """Eigenes Gebiet löschen. Touren, Reisen und Fotos bleiben unverändert (die Zuordnung zum Gebiet entfällt nur); Reisen, die danach hießen, bekommen wieder ihren bisherigen automatischen Namen."""
    if not db.one("SELECT 1 x FROM gebiet_custom WHERE id=?", (gid,)):
        raise HTTPException(404, "Eigenes Gebiet nicht gefunden")
    db.execute("DELETE FROM gebiet_custom WHERE id=?", (gid,))
    return {"ok": True}


# ---------- Suche über Nominatim (OpenStreetMap) ----------
# Nutzungsbedingungen (operations.osmfoundation.org/policies/nominatim): höchstens 1 Anfrage pro Sekunde (gemeinsame Sperre mit den übrigen Ortsabfragen, extras._geo_lock), eigener User-Agent mit
# Kontakt (extras.UA), Ergebnisse zwischenspeichern (Tabelle geocache, 30 Tage), keine Suche während des Tippens (der Browser sucht erst auf Enter/Knopf). Nur Rechteck und Namen werden übernommen.
SUCHE_TTL = 30 * 86400
_ART = {"island": ("Insel", "insel"), "islet": ("Insel", "insel"), "archipelago": ("Inselgruppe", "insel"), "mountain_range": ("Gebirge", "gebirge"), "massif": ("Gebirgsmassiv", "gebirge"),
        "peak": ("Berg", "gebirge"), "mountain": ("Berg", "gebirge"), "hill": ("Hügel", "gebirge"), "ridge": ("Bergkamm", "gebirge"), "volcano": ("Vulkan", "gebirge"), "valley": ("Tal", "tal"),
        "river": ("Fluss", "tal"), "coastline": ("Küste", "kueste"), "coast": ("Küste", "kueste"), "bay": ("Bucht", "kueste"), "beach": ("Strand", "kueste"), "cape": ("Kap", "kueste"),
        "national_park": ("Nationalpark", "region"), "nature_reserve": ("Naturschutzgebiet", "region"), "protected_area": ("Schutzgebiet", "region"), "region": ("Region", "region"),
        "state": ("Bundesland", "region"), "county": ("Landkreis", "region"), "country": ("Land", "region"), "administrative": ("Verwaltungsgebiet", "region"), "forest": ("Wald", "region"),
        "wood": ("Wald", "region"), "park": ("Park", "region"), "city": ("Stadt", "region"), "town": ("Stadt", "region"), "village": ("Ort", "region"), "lake": ("See", "region"),
        "water": ("Gewässer", "region"), "glacier": ("Gletscher", "gebirge")}


def _nominatim(q):
    """Rohantwort der Nominatim-Suche (Liste); RuntimeError bei Netz- oder HTTP-Fehler. Tests ersetzen diese Funktion."""
    import requests
    from . import extras
    with extras._geo_lock:                                       # höchstens 1 Anfrage pro Sekunde, auch bei parallelen Aufrufen
        wait = 1.1 - (time.time() - extras._last_geo[0])
        if wait > 0:
            time.sleep(wait)
        extras._last_geo[0] = time.time()
        try:
            r = requests.get("https://nominatim.openstreetmap.org/search", headers=extras.UA, timeout=10,
                             params={"q": q, "format": "jsonv2", "limit": 8, "accept-language": "de", "addressdetails": 1, "dedupe": 1})
        except Exception as e:  # noqa
            raise RuntimeError(f"nicht erreichbar ({type(e).__name__})")
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    return r.json()


def _treffer(roh):
    """Nominatim-Treffer -> [{name, art, typ, land, box:[S,W,N,O], quelle}] (nur mit gültigem Rechteck; „boundingbox“ steht bei Nominatim als [Süd, Nord, West, Ost])."""
    out, seen = [], set()
    for e in roh if isinstance(roh, list) else []:
        try:
            s, n, w, o = (float(v) for v in e["boundingbox"])
            box = [round(s, 5), round(w, 5), round(n, 5), round(o, 5)]
            if not (s < n and w < o and abs(s) <= 90 and abs(n) <= 90 and abs(w) <= 180 and abs(o) <= 180):
                continue
        except (KeyError, TypeError, ValueError):
            continue
        k = e.get("addresstype") or e.get("type") or ""
        art, typ = _ART.get(k) or _ART.get(e.get("type") or "") or ((k or e.get("category") or "").replace("_", " ").capitalize() or "Ort", "region")
        a = e.get("address") or {}
        name = (e.get("name") or (e.get("display_name") or "").split(",")[0] or "").strip()
        if not name:
            continue
        key = (fold(name), typ, round(s, 1), round(w, 1))
        if key in seen:
            continue
        seen.add(key)
        gross = n - s > MAX_SPANNE[0] or o - w > MAX_SPANNE[1]
        out.append({"name": name, "art": art, "typ": typ, "land": a.get("country") or "", "box": box, "gross": gross, "quelle": (e.get("display_name") or "")[:200]})
    return out


def suche(q):
    """Gebiete zu einem Namen (OpenStreetMap-Suche, 30 Tage zwischengespeichert). RuntimeError, wenn die Suche nicht möglich ist und nichts Zwischengespeichertes vorliegt."""
    q = " ".join(str(q or "").split())[:120]
    key = "gsuche:" + fold(q)
    c = db.one("SELECT name,ts FROM geocache WHERE k=?", (key,))
    if c and time.time() - (c["ts"] or 0) < SUCHE_TTL:
        try:
            return json.loads(c["name"])
        except ValueError:
            pass
    try:
        res = _treffer(_nominatim(q))
    except RuntimeError:
        if c:                                                    # veraltete Treffer sind besser als keine, wenn der Dienst nicht antwortet
            try:
                return json.loads(c["name"])
            except ValueError:
                pass
        raise
    db.execute("INSERT OR REPLACE INTO geocache(k,name,ts) VALUES(?,?,?)", (key, json.dumps(res, ensure_ascii=False), int(time.time())))
    return res


@router.get("/api/gebiete/suche")
def api_suche(q: str = ""):
    """Gebiet per Namen suchen (OpenStreetMap/Nominatim): bis zu 8 Treffer mit Name, Art, Land, Typ-Vorschlag und Rechteck [Süd, West, Nord, Ost]."""
    q = " ".join(q.split())
    if len(q) < 2:
        raise HTTPException(400, "Bitte mindestens zwei Zeichen eingeben")
    try:
        return suche(q)
    except RuntimeError as e:
        raise HTTPException(502, f"Gebietssuche nicht möglich: {e}")
