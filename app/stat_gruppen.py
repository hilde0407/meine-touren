"""3.59.0 Statistik-Gruppen: mehrere Aktivitäten in der Auswertung zusammenfassen (z. B. Wandern + Bergtour + Schneeschuh als „Bergwandern“).

Jeder Benutzer entscheidet selbst: Ohne eigene Gruppen (Standard, auch für alle bestehenden und neuen Benutzer und ältere Sicherungen) zählt die Statistik jede
Aktivität einzeln – in Filtern, Aufteilungen, Bestwerten, Rückblick und Zielen. Feste Zusammenfassungen gibt es nicht mehr; die früheren festen Gruppen sind nur
noch Vorschläge (VORSCHLAEGE), die man mit einem Klick als eigene Gruppe übernehmen kann – nie automatisch.
Rein eine Auswertungs-Gruppierung: Touren, ihre Sportart, Abgleich, Export, Tourenliste und Einzelansichten bleiben unverändert.
Gespeichert je Benutzer in der Tabelle `settings` unter `stat_gruppen` (JSON-Liste [{id, name, sports}]); damit in jeder Sicherung, Wiederherstellung und im Umzugspaket.

Ältere Ziele „grp:foot/bike/ski/run“ („Alle Rad-Sportarten“ …) funktionieren weiter: Gibt es eine eigene Gruppe mit dieser Kennung (die Vorschläge tragen sie),
zählt deren Inhalt, sonst die Aktivitäten-Familie (gpxtools.FAMILIE). Familien sind intern (Tempo-Schätzung, Planung, Steilheit) und keine Statistik-Gruppen.

Eine zentrale Stelle für alle Auswertungen (Server; die Oberfläche hat dieselben Regeln in 01-grundlagen.js, sgKey/sgExpand/sgMatch):
    load()             die Gruppen des Benutzers ([] = jede Aktivität einzeln)
    key(sport)         Sportart -> Schlüssel der Auswertung („sgrp:<id>“ für Mitglieder einer Gruppe, sonst die Sportart)
    name(key)          Anzeigename eines Schlüssels (Gruppenname bzw. deutscher Sportname)
    label(key)         3.60.1 Beschriftung einer Gruppe in Aufteilungen: „<Name> = A + B + C“ (ab 4 Mitgliedern „… + …“), sonst wie name()
    namens_kollision(n)  3.60.1: Gruppenname gleich dem Namen einer Aktivität (4 Sprachen, ohne Groß-/Kleinschreibung und Leerzeichen)? Neue Namen werden abgelehnt,
                       bestehende Gruppen bleiben (die Verwaltung zeigt einen Hinweis und verlangt beim Speichern einen anderen Namen).
    expand(liste)      Filterliste (Sportarten und/oder „sgrp:<id>“) -> Menge der Sportarten; None = alle (leer, oder nur gelöschte Gruppen)
    passt(sport, menge)  Filter passt (menge aus expand)
    ziel_sportarten(s) Sportarten eines Ziels (auch grp:… und sgrp:…); None = alle
Filtereinträge: eine Sportart ([A-Za-z0-9_]{1,40}) oder „sgrp:<id>“ (FILTER_RE).
Gespeicherte Filter oder Ziele mit einer inzwischen gelöschten Gruppe zählen wie „alle Sportarten“ – nie ein Fehler.
"""
import functools
import json
import re
import secrets
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from . import db, gpxtools

router = APIRouter()

KEY = "stat_gruppen"
PREFIX = "sgrp:"
MAX_GRUPPEN = 8
NAME_MAX = 30
MIN_SPORTS = 2
ID_RE = re.compile(r"^[a-z0-9]{1,12}$")
BAD_CHARS = re.compile(r'[<>&"\x00-\x1f]')                                    # Namen erscheinen in der Oberfläche wie Sportnamen (ohne Maskierung): solche Zeichen nicht zulassen
SPORT_RE = re.compile(r"^[A-Za-z0-9_]{1,40}$")
FILTER_RE = re.compile(r"^(?:sgrp:[a-z0-9]{1,12}|[A-Za-z0-9_]{1,40})$")       # ein Eintrag eines Sportartfilters (Layout, Bausteine, Hinweise)
# Ein-Klick-Vorschläge in der Verwaltung (nie automatisch). Kennungen wie die älteren Ziele „grp:<id>“, damit ein solches Ziel der übernommenen Gruppe folgt.
VORSCHLAEGE = [
    {"id": "foot", "name": "Wandern und Bergsteigen", "sports": ["hike", "mountaineering", "snowshoe"]},
    {"id": "bike", "name": "Rad (alle)", "sports": [k for k, _, _, c in gpxtools.CATALOG if c == "rad"]},
    {"id": "ski", "name": "Ski (alle)", "sports": ["skialpin", "skitour", "nordic"]},
]


I18N_NEU = Path(__file__).resolve().parent / "static" / "js" / "00-i18n-neu.js"


def _norm_name(n):
    return re.sub(r"\s+", "", str(n or "")).casefold()


@functools.lru_cache(maxsize=1)
def aktivitaetsnamen():
    """Namen der Katalog-Aktivitäten in allen vier Sprachen (normalisiert). Quelle der Übersetzungen ist dieselbe Tabelle wie in der Oberfläche (00-i18n-neu.js)."""
    de = {n for _, n, _, _ in gpxtools.CATALOG}
    out = {_norm_name(n) for n in de}
    try:
        for line in I18N_NEU.read_text(encoding="utf-8").split("\n"):
            c = line.split(" || ")
            if len(c) == 4 and c[0].strip() in de:
                out.update(_norm_name(x) for x in c)
    except OSError:
        pass
    out.discard("")
    return frozenset(out)


def namens_kollision(name):
    return _norm_name(name) in aktivitaetsnamen()


def known_sports():
    """Sportarten, die eine Gruppe enthalten darf: alle Sportarten der App und jede, die in den eigenen Touren vorkommt (auch fremde Kennungen von Komoot)."""
    out = set(gpxtools.LABEL)
    for r in db.query("SELECT DISTINCT sport FROM tours WHERE sport IS NOT NULL AND sport<>''"):
        s = gpxtools.norm(r["sport"])[0]
        if SPORT_RE.match(s):
            out.add(s)
    return out


def _neue_id(used):
    while True:
        i = secrets.token_hex(3)
        if i not in used:
            return i


def bereinigen(raw, known=None):
    """Nachsichtige Bereinigung gespeicherter Daten (Lesen): Unbekanntes fällt weg, nie ein Fehler.
    Unbekannte, doppelte oder entfernte Sportarten (3.60.0, gpxtools.RUECKFALL), Gruppen mit weniger als zwei Sportarten, ungültige Namen und alles über acht Gruppen werden verworfen."""
    if not isinstance(raw, list):
        return []
    known = known_sports() if known is None else known
    out, used_sp, used_id = [], set(), set()
    for g in raw:
        if len(out) >= MAX_GRUPPEN:
            break
        if not isinstance(g, dict):
            continue
        name = g.get("name")
        name = name.strip() if isinstance(name, str) else ""
        if not 1 <= len(name) <= NAME_MAX or BAD_CHARS.search(name):
            continue
        sp = []
        for s in g.get("sports") if isinstance(g.get("sports"), list) else []:
            if not isinstance(s, str) or s in gpxtools.RUECKFALL:          # 3.60.0: entfernte Aktivitäten (älterer Stand) fallen beim Laden still weg
                continue
            s = gpxtools.norm(s)[0]
            if s in known and s not in used_sp and s not in sp:
                sp.append(s)
        if len(sp) < MIN_SPORTS:
            continue
        gid = g.get("id") if isinstance(g.get("id"), str) and ID_RE.match(g.get("id")) and g.get("id") not in used_id else _neue_id(used_id)
        used_id.add(gid)
        used_sp.update(sp)
        out.append({"id": gid, "name": name, "sports": sp})
    return out


def pruefen(raw, known=None):
    """Strenge Prüfung beim Speichern: Fehler -> HTTPException 400 mit einer verständlichen Meldung. Gibt die bereinigte Liste zurück
    (Namen ohne Leerraum am Rand, Sportarten ohne Doppelte, „snowshoe“ als Wandern, fehlende oder ungültige Kennungen neu vergeben)."""
    if not isinstance(raw, list):
        raise HTTPException(400, "„gruppen“ muss eine Liste sein")
    if len(raw) > MAX_GRUPPEN:
        raise HTTPException(400, f"Höchstens {MAX_GRUPPEN} Gruppen")
    known = known_sports() if known is None else known
    out, used_sp, used_id, names = [], {}, set(), set()
    for n, g in enumerate(raw, 1):
        if not isinstance(g, dict):
            raise HTTPException(400, f"Gruppe {n}: ungültiger Eintrag")
        name = g.get("name")
        name = re.sub(r"\s+", " ", name).strip() if isinstance(name, str) else ""
        if not 1 <= len(name) <= NAME_MAX:
            raise HTTPException(400, f"Gruppe {n}: Der Name muss 1 bis {NAME_MAX} Zeichen lang sein")
        if BAD_CHARS.search(name):
            raise HTTPException(400, f"Gruppe {n}: Der Name darf die Zeichen < > & \" nicht enthalten")
        if namens_kollision(name):                                           # 3.60.1: „Wandern = Wandern + …“ neben „Wandern“ wäre verwirrend
            raise HTTPException(400, f"Gruppe {n}: „{name}“ heißt schon eine Sportart – bitte einen anderen Gruppennamen wählen")
        if name.casefold() in names:
            raise HTTPException(400, f"Zwei Gruppen heißen „{name}“")
        names.add(name.casefold())
        sports = g.get("sports")
        if not isinstance(sports, list) or len(sports) > 40:
            raise HTTPException(400, f"„{name}“: ungültige Liste der Sportarten")
        sp = []
        for s in sports:
            if not isinstance(s, str) or not SPORT_RE.match(s):
                raise HTTPException(400, f"„{name}“: ungültige Sportart")
            if s in gpxtools.RUECKFALL:                                   # 3.60.0: entfernte Aktivität (älterer Stand der Oberfläche): still weglassen
                continue
            s = gpxtools.norm(s)[0]
            if s not in known:
                raise HTTPException(400, f"„{name}“: unbekannte Sportart „{s}“")
            if s in sp:
                continue
            if s in used_sp:
                raise HTTPException(400, f"Eine Sportart kann nur in einer Gruppe sein („{s}“ ist schon in „{used_sp[s]}“)")
            sp.append(s)
        if len(sp) < MIN_SPORTS:
            raise HTTPException(400, f"„{name}“: Eine Gruppe braucht mindestens {MIN_SPORTS} Sportarten")
        gid = g.get("id")
        if not (isinstance(gid, str) and ID_RE.match(gid)) or gid in used_id:
            gid = _neue_id(used_id)
        used_id.add(gid)
        for s in sp:
            used_sp[s] = name
        out.append({"id": gid, "name": name, "sports": sp})
    return out


def load():
    """Die Gruppen des Benutzers (bereinigt); ohne Einstellung: [] – jede Aktivität einzeln."""
    v = db.get(KEY)
    if not v:
        return []
    try:
        raw = json.loads(v)
    except (ValueError, TypeError):
        return []
    return bereinigen(raw)


def save(gruppen):
    gruppen = pruefen(gruppen)
    db.put(KEY, json.dumps(gruppen, ensure_ascii=False, separators=(",", ":")) if gruppen else "")
    return gruppen


def ziel_sportarten(s):
    """Sportarten, die ein Ziel betrifft (Sportart, grp:<id> oder sgrp:<id>); None = alle."""
    if not s:
        return None
    if s.startswith("grp:") or s.startswith(PREFIX):
        gid = s.split(":", 1)[1]
        g = next((g for g in load() if g["id"] == gid), None)
        if g:
            return set(g["sports"])
        if s.startswith("grp:"):                                    # älteres Ziel ohne gleichnamige eigene Gruppe: die Aktivitäten-Familie (wie bis 3.58.0)
            fam = gpxtools.FAMILIE.get(gid)
            return set(fam) if fam else None
        return None                                                 # gelöschte Statistik-Gruppe: alle
    return {gpxtools.norm(s)[0]}


# ------------------------------------------------------------------------------------------------ die zentralen Regeln
def key(sport, gruppen=None):
    """Sportart -> Schlüssel der Auswertung: „sgrp:<id>“, wenn die Sportart in einer Gruppe ist, sonst die Sportart selbst."""
    s = gpxtools.norm(sport or "")[0]
    for g in load() if gruppen is None else gruppen:
        if s in g["sports"]:
            return PREFIX + g["id"]
    return s


def name(k, gruppen=None):
    """Anzeigename eines Schlüssels (Gruppenname oder deutscher Sportname, wie stats.SPORT_DE)."""
    from .stats import SPORT_DE
    if isinstance(k, str) and k.startswith(PREFIX):
        g = next((g for g in (load() if gruppen is None else gruppen) if PREFIX + g["id"] == k), None)
        return g["name"] if g else k
    return SPORT_DE.get(k, k)


def label(k, gruppen=None):
    """3.60.1: Beschriftung eines Schlüssels in Aufteilungen: Gruppe „<Name> = A + B + C“ (mehr als drei Mitglieder: „<Name> = A + B + C + …“), sonst der Sportname."""
    from .stats import SPORT_DE
    if isinstance(k, str) and k.startswith(PREFIX):
        g = next((g for g in (load() if gruppen is None else gruppen) if PREFIX + g["id"] == k), None)
        if not g:
            return k
        m = [SPORT_DE.get(s, s) for s in g["sports"]]
        return f"{g['name']} = " + " + ".join(m[:3] + (["…"] if len(m) > 3 else []))
    return SPORT_DE.get(k, k)


def expand(liste, gruppen=None):
    """Filterliste -> Menge der Sportarten; None = alle Sportarten (leere Liste oder nur Gruppen, die es nicht mehr gibt)."""
    liste = [x for x in (liste or []) if isinstance(x, str) and x]
    if not liste:
        return None
    gs = {PREFIX + g["id"]: g["sports"] for g in (load() if gruppen is None else gruppen)} if any(x.startswith(PREFIX) for x in liste) else {}
    out = set()
    for x in liste:
        if x.startswith(PREFIX):
            out.update(gs.get(x, ()))
        else:
            out.add(gpxtools.norm(x)[0])
    return out or None


def passt(sport, menge):
    """Passt eine Tour mit dieser Sportart zum Filter (menge aus expand; None = alle)?"""
    return menge is None or gpxtools.norm(sport or "")[0] in menge


def filter_liste(text, max_n=20):
    """Gemeinsame Prüfung eines Sportart-Parameters „a,b,sgrp:x“ (Bausteine, Hinweise) -> Liste der Einträge oder HTTPException 400."""
    sp = [x for x in (text or "").split(",") if x != ""]
    if len(sp) > max_n or not all(FILTER_RE.match(x) for x in sp):
        raise HTTPException(400, "Ungültige Sportart")
    return list(dict.fromkeys(sp))


def plain(liste, gruppen=None):
    """Filterliste -> Liste einzelner Sportarten (Gruppen aufgelöst); leer = alle."""
    liste = [x for x in (liste or []) if isinstance(x, str) and x]
    if not any(x.startswith(PREFIX) for x in liste):
        return list(dict.fromkeys(liste))                               # ohne Gruppe: unverändert (Reihenfolge bleibt)
    gs = {PREFIX + g["id"]: g["sports"] for g in (load() if gruppen is None else gruppen)}
    out = []
    for x in liste:
        for s in gs.get(x, ()) if x.startswith(PREFIX) else (x,):
            if s not in out:
                out.append(s)
    return out


# ------------------------------------------------------------------------------------------------ Schnittstelle
@router.get("/api/stats/gruppen")
def api_gruppen():
    """Die Gruppen und die wählbaren Sportarten (auch für Betrachter: sie sehen dieselbe Statistik)."""
    return {"gruppen": load(), "vorschlaege": VORSCHLAEGE, "sportarten": sorted(known_sports()), "max": MAX_GRUPPEN, "name_max": NAME_MAX}


@router.put("/api/stats/gruppen")
async def api_gruppen_speichern(request: Request):
    try:
        body = await request.json()
    except ValueError:
        raise HTTPException(400, "Ungültige Anfrage")
    if not isinstance(body, dict) or "gruppen" not in body:
        raise HTTPException(400, "„gruppen“ fehlt")
    return {"ok": True, "gruppen": save(body["gruppen"])}
