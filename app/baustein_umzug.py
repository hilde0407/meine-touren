"""Umzug alter Bausteine (3.45.0 „Weniger Bausteine, klarere Namen“).

Aus mehreren Bausteinen wurde je einer mit einer Einstellung „Darstellung“ bzw. „Anzahl“. Gespeicherte Ansichten, Vorlagen, Export-Dateien und Ansichtscodes mit den alten
Typkennungen laden weiter: Beim Prüfen eines Layouts (layout.clean) wird jeder alte Typ auf den neuen Baustein mit passender Einstellung abgebildet. Dieselbe Tabelle steht in der
Oberfläche (static/js/49-seitenlayout.js, SL_ALIAS), damit auch Zwischenspeicher und ältere Antworten sofort richtig angezeigt werden.

  alter Typ     neuer Typ   Einstellung
  jahresziel    ziele       view ring,    zeit jahr   (eigenes Ziel → Ziel der Statistik, siehe unten)
  jahresziele   ziele       view balken,  zeit jahr   (year bleibt)
  hnziel        ziele       view warnung, zeit jahr   (schwelle, ausblenden, snoozes, sports, title bleiben)
  hnwoche       ziele       view balken,  zeit woche  (eigenes Wochenziel → Wochenziel der Statistik)
  rekorde       bestwerte   n 1, werte [km, hm, tempo]     (sports, range, yr, eigen, title bleiben)
  sttop         bestwerte   n wie bisher (8 → 10), werte [wert]
  holenknopf    zeppimport  view knopf   (3.48.0: „Touren holen (nur Knopf)“ ist die Darstellung „Nur Knopf“ von „Touren holen“; title bleibt)

Ziele werden nur noch an einer Stelle gepflegt (Tabelle „goals“, Statistik → Ziele). Hatte ein alter Baustein ein eigenes Ziel (Jahresziel: goal/metric, Wochenziel: ziel/einheit,
Sammel-Baustein „Hinweise“: woche_ziel/woche_einheit), wird es beim Umzug als Ziel der Statistik übernommen – aber nur, wenn es für denselben Zeitraum, dieselbe Sportart und
dieselbe Messgröße noch kein Ziel gibt (das vorhandene Ziel gilt). Wochenziele stehen in „goals“ mit period = "week" und year = 0.
Der Umzug läuft beim Öffnen einer Datenbank (db.migrate → migrate_rows) und beim Speichern eines Layouts (layout.put_layout). Beim Prüfen einer fremden Export-Datei oder eines
Ansichtscodes werden keine Ziele angelegt (es sind die Ziele eines anderen); die Prüfung meldet dann, dass das eigene Ziel nicht übernommen wurde.
"""
import json
import time
from datetime import date

ZIELE = "ziele"
BESTWERTE = "bestwerte"
HOLEN = "zeppimport"
ALT = ("jahresziel", "jahresziele", "hnziel", "hnwoche", "rekorde", "sttop", "holenknopf")
GOAL_METRICS = ("km", "up", "count", "hours")
PERIODS = ("year", "week")
BW_WERTE = ("km", "hm", "dauer", "tempo", "monat")
BW_N = (1, 3, 5, 10)
_KEEP = ("sports", "title")
_KEEP_FILTER = ("sports", "range", "yr", "eigen", "title")


def _sport1(cfg):
    s = cfg.get("sports")
    return s[0] if isinstance(s, list) and len(s) == 1 and isinstance(s[0], str) else ""


def _num(x):
    if isinstance(x, bool) or not isinstance(x, (int, float)) or x != x:
        return None
    return x


def _pick(cfg, keys):
    return {k: cfg[k] for k in keys if k in cfg}


def alias(typ, cfg):
    """Alter Typ → (neuer Typ, neue Konfiguration, Ziele [{period, year, sport, metric, target, quelle}]). Andere Typen bleiben unverändert (nur die Wochenziel-Felder
    des Sammel-Bausteins „hinweise“ ziehen in die Ziele um)."""
    cfg = cfg if isinstance(cfg, dict) else {}
    goals = []
    if typ == "hinweise":
        z = _num(cfg.get("woche_ziel"))
        out = {k: v for k, v in cfg.items() if k not in ("woche_ziel", "woche_einheit")}
        if z and z > 0:
            goals.append({"period": "week", "year": 0, "sport": _sport1(cfg), "metric": "count" if cfg.get("woche_einheit") == "touren" else "km", "target": float(z), "quelle": "hinweise"})
        return typ, out, goals
    if typ not in ALT:
        return typ, cfg, goals
    if typ == "jahresziel":
        hm = cfg.get("metric") == "hm"
        g = _num(cfg.get("goal"))
        target = float(g) if g and g > 0 else (20000.0 if hm else 1000.0)
        goals.append({"period": "year", "year": date.today().year, "sport": _sport1(cfg), "metric": "up" if hm else "km", "target": target, "quelle": typ})
        return ZIELE, {"view": "ring", "zeit": "jahr", **_pick(cfg, _KEEP)}, goals
    if typ == "jahresziele":
        out = {"view": "balken", "zeit": "jahr", **_pick(cfg, _KEEP)}
        if cfg.get("year") == "last":
            out["year"] = "last"
        return ZIELE, out, goals
    if typ == "hnziel":
        out = {"view": "warnung", "zeit": "jahr", **_pick(cfg, _KEEP + ("schwelle", "ausblenden"))}
        sn = [x for x in cfg.get("snoozes") or [] if isinstance(x, str) and x.startswith("ziel:")]
        if sn:
            out["snoozes"] = sn
        return ZIELE, out, goals
    if typ == "hnwoche":
        z = _num(cfg.get("ziel"))
        if z and z > 0:
            goals.append({"period": "week", "year": 0, "sport": _sport1(cfg), "metric": "count" if cfg.get("einheit") == "touren" else "km", "target": float(z), "quelle": typ})
        return ZIELE, {"view": "balken", "zeit": "woche", **_pick(cfg, _KEEP)}, goals
    if typ == "holenknopf":                                              # 3.48.0
        return HOLEN, {"view": "knopf", **_pick(cfg, ("title",))}, goals
    if typ == "rekorde":
        return BESTWERTE, {"n": 1, "werte": ["km", "hm", "tempo"], **_pick(cfg, _KEEP_FILTER)}, goals
    # sttop
    n = cfg.get("n")
    n = 10 if n == 8 else n if n in BW_N else 5
    w = cfg.get("wert") if cfg.get("wert") in ("km", "hm", "dauer", "tempo") else "km"
    return BESTWERTE, {"n": n, "werte": [w], **_pick(cfg, _KEEP_FILTER)}, goals


def has_alt(doc):
    """Steht im Dokument (Layout oder Behälter) noch ein alter Typ oder ein altes Wochenziel?"""
    s = json.dumps(doc, ensure_ascii=False) if not isinstance(doc, str) else doc
    return any(f'"type": "{t}"' in s or f'"type":"{t}"' in s for t in ALT) or '"woche_ziel"' in s


def _lay(lay, goals):
    if not isinstance(lay, dict):
        return lay
    out = dict(lay)
    if isinstance(lay.get("widgets"), list):
        ws = []
        for w in lay["widgets"]:
            if isinstance(w, dict) and isinstance(w.get("type"), str):
                t, c, g = alias(w["type"], w.get("cfg"))
                goals.extend(g)
                w = {**w, "type": t, "cfg": c}
            ws.append(w)
        out["widgets"] = ws
    return out


def migrate_doc(doc):
    """Ganzes gespeichertes Dokument (altes Format oder Behälter) → (neues Dokument, Ziele)."""
    goals = []
    if isinstance(doc, dict) and isinstance(doc.get("views"), list):
        return {**doc, "views": [{**v, "layout": _lay(v.get("layout"), goals)} if isinstance(v, dict) else v for v in doc["views"]]}, goals
    return _lay(doc, goals), goals


def add_goals(goals, execute, one):
    """Ziele übernehmen, wenn es für Zeitraum, Jahr, Sportart und Messgröße noch keines gibt. execute/one: Datenbankzugriff (db.execute/db.one oder eine Verbindung)."""
    n = 0
    for g in goals:
        if g["metric"] not in GOAL_METRICS or g["period"] not in PERIODS or not g["target"] or g["target"] <= 0:
            continue
        if one("SELECT 1 x FROM goals WHERE COALESCE(period,'year')=? AND year=? AND COALESCE(sport,'')=? AND metric=?", (g["period"], g["year"], g["sport"], g["metric"])):
            continue
        execute("INSERT INTO goals(year,sport,metric,target,period) VALUES(?,?,?,?,?)", (g["year"], g["sport"], g["metric"], g["target"], g["period"]))
        n += 1
    return n


def migrate_rows(conn):
    """Beim Öffnen einer Datenbank: alle gespeicherten Layouts mit alten Bausteinen umziehen, eigene Ziele übernehmen. Ändert nur Zeilen mit alten Inhalten (mehrfach aufrufbar)."""
    rows = conn.execute("SELECT page_key,json FROM user_layout").fetchall()
    one = lambda sql, a: conn.execute(sql, a).fetchone()                    # noqa: E731
    ex = lambda sql, a: conn.execute(sql, a)                                # noqa: E731
    changed = 0
    for r in rows:
        raw = r["json"] or ""
        if not has_alt(raw):
            continue
        try:
            doc = json.loads(raw)
        except ValueError:
            continue
        new, goals = migrate_doc(doc)
        add_goals(goals, ex, one)
        conn.execute("UPDATE user_layout SET json=?, ts=? WHERE page_key=?", (json.dumps(new, ensure_ascii=False, separators=(",", ":")), int(time.time()), r["page_key"]))
        changed += 1
    if changed:
        conn.commit()
    return changed


def goal_text(g):
    """Kurzer Text für Hinweise der Prüfung („1.000 km im Jahr“)."""
    u = {"km": "km", "up": "m Aufstieg", "count": "Touren", "hours": "Stunden"}[g["metric"]]
    v = f"{g['target']:,.0f}".replace(",", ".")
    return f"{v} {u} {'pro Woche' if g['period'] == 'week' else 'im Jahr'}"
