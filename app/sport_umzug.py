"""Sportarten-Umzug 3.50.0: „Laufen“ von der Uhr und Schneeschuh als Wandern (wie im Schwesterprojekt „Mein Tourentagebuch“).

3.59.0: Schneeschuh ist wieder eine eigene Sportart. Das Zusammenlegen (Punkt 1 unten) läuft NICHT mehr – auch nicht für Datenbanken aus älteren Sicherungen
(Merker FLAG_SNOW in den Einstellungen, gesetzt beim ersten Öffnen mit 3.59.0). Touren, die 3.50.0 zusammengelegt hat (Wandern + Schlagwort „Schneeschuh“),
bleiben, wie sie sind, bis du sie unter Prüfen „als Schneeschuh führst“ (POST /api/schneeschuh/umstellen); das lässt sich zurücknehmen
(POST /api/schneeschuh/zuruecknehmen, Tabelle snow_convert merkt sich die vorherige eigene Wahl). Das Schlagwort bleibt in beiden Fällen. Der Komoot-Abgleich
stellt eine zusammengelegte Tour nicht still zurück auf Schneeschuh.

1. Schneeschuh zählt als Wandern. Die Sportart „snowshoe“ gibt es nicht mehr; Touren, Pläne, Ziele, Ausrüstung, eigene Sportarten (tour_sport), ausgeblendete Touren
   und Zepp-Trainings werden auf „hike“ umgestellt. Jede Tour bekommt dabei einmal das Schlagwort „Schneeschuh“ (nur wenn sie es noch nicht hat; die Tabelle
   sport_merged merkt sich, dass es schon geschehen ist – entfernt man das Schlagwort, kommt es beim nächsten Komoot-Abgleich nicht wieder).
   Läuft bei jedem Öffnen einer Datenbank (auch nach dem Zurückspielen einer älteren Sicherung) und beim Komoot-Abgleich (merge_komoot); ist nichts umzustellen,
   passiert nichts.
2. Zepp-Typ 1 (Laufen draußen) und 8 (Laufband) sind Laufen („jogging“). Bis 3.49.0 wurden sie als Wandern übernommen. Einmalig (Merker sport_umzug_350 in den
   Einstellungen) werden die Touren umgestellt, bei denen das sicher ist: die Tour ist die lokal übernommene Datei genau dieses Zepp-Trainings (workouts.ztype ist
   gespeichert, workouts.komoot_id bzw. die Kennung z<trackid> zeigt auf die Tour), sie heißt noch „hike“ und ihre Sportart wurde nie von Hand gewählt (tour_sport).
   Touren, die nur über Komoot kamen oder nur über Startzeit und Länge zu einem Zepp-Lauf passen, werden nicht geraten: sie stehen unter Prüfen → „Läufe von der Uhr“
   (GET /api/sport-umzug) und lassen sich dort gesammelt umstellen (POST /api/sport-umzug/laufen; gilt dann als eigene Wahl wie „Sportart ändern“).

Sicherheit: Bevor die Datenbank zum ersten Mal geändert wird, legt der Umzug neben ihr eine vollständige Kopie an („<datei>.vor-3.50.0.sqlite“, nur einmal). Jede
Änderung steht mit altem und neuem Wert in der Tabelle sport_log. Mehrfach aufrufbar: ein zweiter Lauf findet nichts mehr.
"""
import json
import sqlite3
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException

from . import db, gpxtools

router = APIRouter()

FLAG = "sport_umzug_350"
KOPIE = ".vor-3.50.0.sqlite"
ALT = "snowshoe"
NEU, TAG = "hike", gpxtools.SCHNEESCHUH_TAG
FLAG_SNOW = "schneeschuh_eigen_359"           # 3.59.0: Schneeschuh nicht mehr zusammenlegen (Schutz, auch für zurückgespielte Sicherungen)
LAUFEN = "jogging"
_ZT = ",".join(str(z) for z in gpxtools.ZEPP_LAUFEN)


def tables(conn):
    conn.execute("CREATE TABLE IF NOT EXISTS sport_merged (id TEXT PRIMARY KEY, orig TEXT, ts INTEGER)")   # Touren, deren Sportart zusammengelegt wurde (Schlagwort schon vergeben)
    conn.execute("CREATE TABLE IF NOT EXISTS sport_log (n INTEGER PRIMARY KEY AUTOINCREMENT, ts INTEGER, tab TEXT, id TEXT, alt TEXT, neu TEXT, grund TEXT)")   # Protokoll des Umzugs
    conn.execute("CREATE TABLE IF NOT EXISTS snow_convert (id TEXT PRIMARY KEY, prev TEXT, ts INTEGER)")   # 3.59.0: „als Schneeschuh geführt“ (prev = vorherige eigene Sportart oder NULL)


def _has(conn, tab, col="sport"):
    try:
        return {r[1] for r in conn.execute(f"PRAGMA table_info({tab})")} >= {col}
    except sqlite3.Error:
        return False


def _snow_pending(conn):
    for tab in ("tours", "tour_sport", "plans", "goals", "workouts", "device_quality"):
        if _has(conn, tab) and conn.execute(f"SELECT 1 FROM {tab} WHERE sport=? LIMIT 1", (ALT,)).fetchone():
            return True
    if _has(conn, "gear", "sports") and conn.execute("SELECT 1 FROM gear WHERE ','||sports||',' LIKE ? LIMIT 1", (f"%,{ALT},%",)).fetchone():
        return True
    if _has(conn, "tour_hidden", "js") and conn.execute("SELECT 1 FROM tour_hidden WHERE js LIKE ? LIMIT 1", (f'%"{ALT}"%',)).fetchone():
        return True
    return False


def zepp_sicher(conn):
    """Touren, die sicher ein Zepp-Lauf sind und automatisch umgestellt werden dürfen: [(tour_id, trackid)]."""
    if not _has(conn, "workouts", "ztype"):
        return []
    rows = conn.execute(
        f"SELECT t.id, w.trackid FROM workouts w JOIN tours t ON (t.id = w.komoot_id OR t.id = 'z' || w.trackid) "
        f"WHERE w.ztype IN ({_ZT}) AND t.sport='hike' AND COALESCE(t.source,'komoot')='local' "
        f"AND t.id NOT IN (SELECT id FROM tour_sport)").fetchall()
    seen, out = set(), []
    for r in rows:
        if r[0] not in seen:
            seen.add(r[0]); out.append((r[0], r[1]))
    return out


def _kopie(conn):
    """Vollständige Kopie der Datenbank neben der Datei (einmal je Datenbank). Gibt den Pfad zurück oder "" (Speicher-Datenbank, Fehler)."""
    try:
        f = next((r[2] for r in conn.execute("PRAGMA database_list") if r[1] == "main"), "")
        if not f:
            return ""
        ziel = Path(f).with_name(Path(f).name + KOPIE)
        if not ziel.exists():
            dst = sqlite3.connect(str(ziel))
            with dst:
                conn.backup(dst)
            dst.close()
        return str(ziel)
    except Exception:  # noqa
        return ""


def _log(conn, tab, ident, alt, neu, grund, now):
    conn.execute("INSERT INTO sport_log(ts,tab,id,alt,neu,grund) VALUES(?,?,?,?,?,?)", (now, tab, str(ident), alt, neu, grund))


def _tag(conn, tid, now, orig=ALT):
    """Schlagwort einmal vergeben (nicht, wenn die Tour schon zusammengelegt wurde oder es schon trägt)."""
    if conn.execute("SELECT 1 FROM sport_merged WHERE id=?", (tid,)).fetchone():
        return False
    conn.execute("INSERT OR IGNORE INTO sport_merged(id,orig,ts) VALUES(?,?,?)", (tid, orig, now))
    return conn.execute("INSERT OR IGNORE INTO tour_tags(id,tag) VALUES(?,?)", (tid, TAG)).rowcount > 0


def _snow(conn, now):
    n = {"touren": 0, "plaene": 0, "ziele": 0, "ausruestung": 0}
    ids = [r[0] for r in conn.execute("SELECT id FROM tours WHERE sport=?", (ALT,))]
    ids += [r[0] for r in conn.execute("SELECT id FROM tour_sport WHERE sport=?", (ALT,)) if r[0] not in ids]
    for tid in ids:
        _tag(conn, tid, now)
        _log(conn, "tours", tid, ALT, NEU, "Schneeschuh zählt als Wandern", now)
    conn.execute("UPDATE tours SET sport=? WHERE sport=?", (NEU, ALT))
    conn.execute("UPDATE tour_sport SET sport=? WHERE sport=?", (NEU, ALT))
    n["touren"] = len(ids)
    for r in conn.execute("SELECT id, js FROM tour_hidden WHERE js LIKE ?", (f'%"{ALT}"%',)).fetchall():
        try:
            d = json.loads(r[1] or "{}")
        except ValueError:
            continue
        if isinstance(d, dict) and d.get("sport") == ALT:
            d["sport"] = NEU
            conn.execute("UPDATE tour_hidden SET js=? WHERE id=?", (json.dumps(d), r[0]))
            _tag(conn, r[0], now)
            _log(conn, "tour_hidden", r[0], ALT, NEU, "Schneeschuh zählt als Wandern", now)
    if _has(conn, "plans"):
        for r in conn.execute("SELECT id FROM plans WHERE sport=?", (ALT,)).fetchall():
            _log(conn, "plans", r[0], ALT, NEU, "Schneeschuh zählt als Wandern", now)
            n["plaene"] += 1
        conn.execute("UPDATE plans SET sport=? WHERE sport=?", (NEU, ALT))
    if _has(conn, "goals"):
        per = _has(conn, "goals", "period")
        for g in conn.execute("SELECT * FROM goals WHERE sport=?", (ALT,)).fetchall():
            g = dict(g)
            same = conn.execute("SELECT 1 FROM goals WHERE sport=? AND year=? AND metric=?" + (" AND COALESCE(period,'year')=?" if per else ""),
                                (NEU, g["year"], g["metric"]) + ((g.get("period") or "year",) if per else ())).fetchone()
            if same:      # dasselbe Ziel gibt es für Wandern schon: das Wandern-Ziel gilt (zählt Schneeschuh jetzt mit)
                conn.execute("DELETE FROM goals WHERE id=?", (g["id"],))
                _log(conn, "goals", g["id"], ALT, "", f"Ziel entfernt, Wandern-Ziel gilt ({g['metric']} {g['target']})", now)
            else:
                conn.execute("UPDATE goals SET sport=? WHERE id=?", (NEU, g["id"]))
                _log(conn, "goals", g["id"], ALT, NEU, "Schneeschuh zählt als Wandern", now)
            n["ziele"] += 1
    if _has(conn, "gear", "sports"):
        for r in conn.execute("SELECT id, sports FROM gear WHERE ','||sports||',' LIKE ?", (f"%,{ALT},%",)).fetchall():
            sp = []
            for s in (r[1] or "").split(","):
                s = NEU if s == ALT else s
                if s and s not in sp:
                    sp.append(s)
            conn.execute("UPDATE gear SET sports=? WHERE id=?", (",".join(sp), r[0]))
            _log(conn, "gear", r[0], r[1], ",".join(sp), "Schneeschuh zählt als Wandern", now)
            n["ausruestung"] += 1
    for tab in ("workouts", "device_quality"):
        if _has(conn, tab):
            conn.execute(f"UPDATE {tab} SET sport=? WHERE sport=?", (NEU, ALT))
    return n


def migrate(conn):
    """Beim Öffnen einer Datenbank (db.migrate). Gibt die Zusammenfassung zurück oder None, wenn nichts zu tun war."""
    tables(conn)
    if not conn.execute("SELECT 1 FROM settings WHERE k=?", (FLAG_SNOW,)).fetchone():
        conn.execute("INSERT OR REPLACE INTO settings(k,v) VALUES(?,?)", (FLAG_SNOW, json.dumps({"ts": int(time.time())})))
        conn.commit()
    done = conn.execute("SELECT v FROM settings WHERE k=?", (FLAG,)).fetchone()
    snow = False                                      # 3.59.0: Schneeschuh wird nie mehr zusammengelegt (früher: _snow_pending(conn))
    lauf = [] if done else zepp_sicher(conn)
    if done and not snow:
        return None
    now = int(time.time())
    kopie = _kopie(conn) if (snow or lauf) else ""
    try:
        res = _snow(conn, now) if snow else {"touren": 0, "plaene": 0, "ziele": 0, "ausruestung": 0}
        for tid, trackid in lauf:
            conn.execute("UPDATE tours SET sport=? WHERE id=? AND sport='hike'", (LAUFEN, tid))
            _log(conn, "tours", tid, "hike", LAUFEN, f"Zepp-Training {trackid} ist ein Lauf (Typ 1/8)", now)
        if not done and _has(conn, "workouts", "ztype"):
            conn.execute(f"UPDATE workouts SET sport=? WHERE ztype IN ({_ZT}) AND sport='hike'", (LAUFEN,))
        alt = {}
        if done:
            try:
                alt = json.loads(done[0] or "{}")
            except ValueError:
                alt = {}
        info = {"ts": alt.get("ts") or now, "laufen": int(alt.get("laufen") or 0) + len(lauf),
                "schneeschuh": int(alt.get("schneeschuh") or 0) + res["touren"], "plaene": int(alt.get("plaene") or 0) + res["plaene"],
                "ziele": int(alt.get("ziele") or 0) + res["ziele"], "ausruestung": int(alt.get("ausruestung") or 0) + res["ausruestung"],
                "kopie": kopie or alt.get("kopie") or ""}
        conn.execute("INSERT OR REPLACE INTO settings(k,v) VALUES(?,?)", (FLAG, json.dumps(info)))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return info


def merge_komoot(tours):
    """Komoot-Abgleich (3.59.0): Schneeschuh bleibt Schneeschuh – außer bei Touren, die 3.50.0 zu Wandern zusammengelegt hat und die du noch nicht
    „als Schneeschuh führst“: die bleiben still Wandern (mit Schlagwort). Gibt die Kennungen zurück, die ein Schlagwort brauchen (keine mehr)."""
    try:
        alt = {r["id"] for r in db.query("SELECT id FROM sport_merged")} - {r["id"] for r in db.query("SELECT id FROM tour_sport")}
    except Exception:  # noqa
        alt = set()
    for t in tours:
        if t.get("sport") == ALT and str(t["id"]) in alt:
            t["sport"] = NEU
    return []


def tag_merged(ids):
    """Nach dem Speichern: Schlagwort „Schneeschuh“ einmal je Tour vergeben."""
    if not ids:
        return
    now = int(time.time())
    with db.cur() as c:
        conn = c.connection
        for tid in ids:
            _tag(conn, tid, now)


def set_sport(tour_id, sport):
    """Sportart einer Tour von Hand setzen (wie „Sportart ändern“): bleibt beim Komoot-Abgleich. Zusammengelegte Kennungen werden umgesetzt."""
    sp, tag = gpxtools.norm(sport)
    db.execute("INSERT OR REPLACE INTO tour_sport(id,sport) VALUES(?,?)", (tour_id, sp))
    db.execute("UPDATE tours SET sport=? WHERE id=?", (sp, tour_id))
    if tag:
        tag_merged([tour_id])
    return sp


def kandidaten():
    """Touren, die wahrscheinlich ein Lauf der Zepp-Uhr sind, aber noch „Wandern“ heißen und nicht automatisch umgestellt wurden:
    Komoot-Touren eines Zepp-Laufs und Touren, die nur über Startzeit und Länge zu einem Zepp-Lauf passen. Nie Touren mit von Hand gewählter Sportart."""
    from . import sync
    eigen = {r["id"] for r in db.query("SELECT id FROM tour_sport")}
    tours = db.query("SELECT id,name,sport,start_ts,dist_m,dur_s,source FROM tours WHERE start_ts IS NOT NULL")
    by = {t["id"]: t for t in tours}
    tol = db.get_int("dup_tolerance_s", 300)
    out, seen = [], set()
    for w in db.query(f"SELECT trackid, ztype, komoot_id, start_ts, dist_m, dur_s FROM workouts WHERE ztype IN ({_ZT})"):
        t = by.get(str(w["komoot_id"] or "")) or by.get(f"z{w['trackid']}")
        wie = "verknuepft"
        if not t and w["start_ts"]:
            t = sync.is_duplicate(w["start_ts"], w["dist_m"] or 0, w["dur_s"] or 0, tours, tol)
            wie = "zeit"
        if not t or t["id"] in seen or t["id"] in eigen or t["sport"] != "hike":
            continue
        seen.add(t["id"])
        out.append({"id": t["id"], "name": t["name"] or "", "start_ts": t["start_ts"], "km": round((t["dist_m"] or 0) / 1000, 2),
                    "kmh": round((t["dist_m"] or 0) / t["dur_s"] * 3.6, 1) if t["dur_s"] else None, "quelle": t["source"] or "komoot", "wie": wie,
                    "trackid": w["trackid"], "ztype": w["ztype"]})
    out.sort(key=lambda x: -(x["start_ts"] or 0))
    return out


def info():
    try:
        d = json.loads(db.get(FLAG) or "{}")
    except ValueError:
        d = {}
    return d if isinstance(d, dict) else {}


@router.get("/api/sport-umzug")
def api_status():
    """Ergebnis des Umzugs 3.50.0 und Läufe der Uhr, die noch „Wandern“ heißen (für Prüfen)."""
    d = info()
    return {"umzug": {k: d.get(k) for k in ("ts", "laufen", "schneeschuh", "plaene", "ziele", "ausruestung")} if d else None,
            "kandidaten": kandidaten()}


# ------------------------------------------------------------------------------------------------ 3.59.0 Schneeschuh-Touren als Schneeschuh führen
def schnee_kandidaten():
    """Touren „Wandern“ mit dem Schlagwort „Schneeschuh“ (meist von 3.50.0 zusammengelegt)."""
    return db.query("SELECT t.id, t.name, t.start_ts, t.dist_m FROM tours t WHERE t.sport=? AND EXISTS (SELECT 1 FROM tour_tags x WHERE x.id=t.id AND x.tag=?) "
                    "ORDER BY t.start_ts DESC", (NEU, TAG))


@router.get("/api/schneeschuh")
def api_schnee():
    k = schnee_kandidaten()
    return {"kandidaten": [{"id": r["id"], "name": r["name"] or "", "start_ts": r["start_ts"], "km": round((r["dist_m"] or 0) / 1000, 2)} for r in k],
            "umgestellt": db.one("SELECT COUNT(*) n FROM snow_convert")["n"]}


@router.post("/api/schneeschuh/umstellen")
def api_schnee_umstellen(body: dict = None):
    """Gewählte (oder alle) Kandidaten als Schneeschuh führen; gilt als eigene Wahl. Das Schlagwort bleibt."""
    ids = (body or {}).get("ids") if isinstance(body, dict) else None
    erlaubt = [r["id"] for r in schnee_kandidaten()]
    if ids is not None:
        if not isinstance(ids, list) or len(ids) > 5000:
            raise HTTPException(400, "Ungültige Auswahl")
        want = {str(x) for x in ids}
        erlaubt = [i for i in erlaubt if i in want]
    now, n = int(time.time()), 0
    for tid in erlaubt:
        prev = db.one("SELECT sport FROM tour_sport WHERE id=?", (tid,))
        db.execute("INSERT OR REPLACE INTO snow_convert(id,prev,ts) VALUES(?,?,?)", (tid, prev["sport"] if prev else None, now))
        set_sport(tid, ALT)
        db.execute("INSERT INTO sport_log(ts,tab,id,alt,neu,grund) VALUES(?,?,?,?,?,?)", (now, "tours", tid, NEU, ALT, "Prüfen: als Schneeschuh führen"))
        n += 1
    return {"ok": True, "n": n}


@router.post("/api/schneeschuh/zuruecknehmen")
def api_schnee_zurueck():
    """Alle mit „als Schneeschuh führen“ umgestellten Touren wieder wie vorher (Wandern bzw. die frühere eigene Wahl); Touren, deren Sportart seitdem von Hand
    geändert wurde, bleiben."""
    now, n = int(time.time()), 0
    for r in db.query("SELECT id, prev FROM snow_convert"):
        cur = db.one("SELECT sport FROM tour_sport WHERE id=?", (r["id"],))
        if cur and cur["sport"] == ALT:
            if r["prev"]:
                db.execute("UPDATE tour_sport SET sport=? WHERE id=?", (r["prev"], r["id"]))
            else:
                db.execute("DELETE FROM tour_sport WHERE id=?", (r["id"],))
            db.execute("UPDATE tours SET sport=? WHERE id=?", (r["prev"] or NEU, r["id"]))
            db.execute("INSERT INTO sport_log(ts,tab,id,alt,neu,grund) VALUES(?,?,?,?,?,?)", (now, "tours", r["id"], ALT, r["prev"] or NEU, "Prüfen: Schneeschuh zurückgenommen"))
            n += 1
        db.execute("DELETE FROM snow_convert WHERE id=?", (r["id"],))
    return {"ok": True, "n": n}


@router.post("/api/sport-umzug/laufen")
def api_laufen(body: dict):
    """Gewählte Touren auf Laufen umstellen (nur Kandidaten aus GET /api/sport-umzug; gilt als eigene Wahl)."""
    ids = body.get("ids") if isinstance(body, dict) else None
    if not isinstance(ids, list) or not ids or len(ids) > 2000:
        raise HTTPException(400, "Keine Touren gewählt")
    erlaubt = {k["id"] for k in kandidaten()}
    n = 0
    now = int(time.time())
    for tid in ids:
        tid = str(tid)
        if tid not in erlaubt:
            continue
        set_sport(tid, LAUFEN)
        db.execute("INSERT INTO sport_log(ts,tab,id,alt,neu,grund) VALUES(?,?,?,?,?,?)", (now, "tours", tid, "hike", LAUFEN, "Prüfen: Lauf von der Uhr"))
        n += 1
    return {"ok": True, "n": n}
