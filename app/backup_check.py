"""Sicherungen prüfen: ZIP lesbar, enthaltene Datenbank öffnet und besteht die Integritätsprüfung, Zähler, Alter.
Arbeitet nur lesend auf der Sicherungsdatei und in einem temporären Verzeichnis (wird danach gelöscht) – nie auf den Live-Daten."""
import sqlite3
import tempfile
import time
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from . import config, ctx, db, extras

router = APIRouter()

WARN_S = config.BACKUP_WARN_S   # eine einzige Schwelle (36 h) für Zustand und Warnleiste; der Hinweis-Baustein hat seine eigene Einstellung in Tagen


def pruefe_zip(path, tief=True):
    """Prüft eine Sicherungsdatei. tief=True: PRAGMA integrity_check, sonst die schnellere quick_check.
    Gibt {ok, fehler, touren, tracks, layouts, db_pruefung, groesse} zurück (touren/layouts None, wenn die Tabelle in alten Sicherungen fehlt)."""
    p = Path(path)
    out = {"ok": False, "fehler": "", "touren": None, "tracks": 0, "layouts": None, "db_pruefung": "", "groesse": 0}
    try:
        out["groesse"] = p.stat().st_size
        if out["groesse"] == 0:
            out["fehler"] = "Die Datei ist leer."
            return out
        with zipfile.ZipFile(p) as z:
            bad = z.testzip()
            if bad:
                out["fehler"] = f"Beschädigter Eintrag im ZIP: {bad}"
                return out
            names = z.namelist()
            if "komoot_hub.sqlite" not in names:
                out["fehler"] = "Die Datenbank (komoot_hub.sqlite) fehlt in der Sicherung."
                return out
            out["tracks"] = sum(1 for n in names if n.startswith("tracks/") and n.endswith(".gpx"))
            with tempfile.TemporaryDirectory() as td:
                dbf = Path(td) / "komoot_hub.sqlite"
                with z.open("komoot_hub.sqlite") as src, open(dbf, "wb") as dst:
                    while True:
                        b = src.read(1 << 20)
                        if not b:
                            break
                        dst.write(b)
                c = sqlite3.connect(f"file:{dbf}?mode=ro", uri=True)
                try:
                    r = c.execute("PRAGMA integrity_check" if tief else "PRAGMA quick_check").fetchall()
                    v = "; ".join(str(x[0]) for x in r[:3]) if r else "?"
                    out["db_pruefung"] = v
                    if v != "ok":
                        out["fehler"] = f"Die Datenbank in der Sicherung ist beschädigt: {v[:200]}"
                        return out
                    tabs = {x[0] for x in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                    if "tours" in tabs:
                        out["touren"] = c.execute("SELECT COUNT(*) FROM tours").fetchone()[0]
                    if "user_layout" in tabs:
                        out["layouts"] = c.execute("SELECT COUNT(*) FROM user_layout").fetchone()[0]
                finally:
                    c.close()
        out["ok"] = True
    except zipfile.BadZipFile:
        out["fehler"] = "Die Datei ist kein lesbares ZIP (abgeschnitten oder beschädigt)."
    except (OSError, sqlite3.Error, EOFError, RuntimeError, ValueError) as e:
        out["fehler"] = f"{e.__class__.__name__}: {str(e)[:160]}"
    return out


def status():
    """Zustand der Sicherung für die Verwaltung: neueste Datei, Alter, letzter Fehler, letzte Prüfung."""
    nb = extras.newest_backup()
    out = {"neueste": None, "fehler": (db.get("backup_err") or "").strip(), "fehler_ts": _int(db.get("backup_err_ts")), "geprueft": None, "ueberfaellig": False,
           "warn_h": WARN_S // 3600}
    if nb:
        st = nb.stat()
        out["neueste"] = {"name": nb.name, "ts": int(st.st_mtime), "groesse": st.st_size, "alter_h": round((time.time() - st.st_mtime) / 3600, 1)}
        out["ueberfaellig"] = time.time() - st.st_mtime > WARN_S
    else:
        out["ueberfaellig"] = bool(db.one("SELECT 1 x FROM tours LIMIT 1"))
    g = db.get("backup_check")
    if g:
        try:
            import json
            out["geprueft"] = json.loads(g)
        except ValueError:
            pass
    return out


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


@router.get("/api/backup/status")
def api_status(request: Request):
    extras._admin_only(request)
    return status()


def waechter(tage=None):
    """Sicherungs-Wächter (3.48.0, Warnleiste unter der Kopfzeile). Keine zweite Berechnung: das Alter und die Schwelle kommen aus der Hinweis-Regel „sicherung“
    (hinweise._sicherung, Schwelle sicherung_tage, Standard 7), der Fehlerfall aus status() (Anlegen fehlgeschlagen) und der letzten Prüfung (nur, wenn sie genau die neueste Datei betrifft).
    Gibt {zeige, art, ...} zurück; art: keine (noch nie eine Sicherung, obwohl es Touren gibt) | fehler (grund: angelegt | pruefung) | alt (alter_tage ≥ schwelle)."""
    from . import hinweise
    t = hinweise.DEFAULTS["sicherung_tage"] if tage in (None, "") else max(1, min(365, int(tage)))
    out = {"zeige": False, "art": "", "grund": "", "alter_tage": None, "datum": None, "schwelle": t, "ausblendbar": True}
    if not db.one("SELECT 1 x FROM tours LIMIT 1"):
        return out                                                    # nichts zu sichern
    st = status()
    r = hinweise._sicherung({"sicherung_tage": t}, None, None)
    d = r[1] if r else {}
    g = st.get("geprueft") or {}
    nb = st.get("neueste")
    pruef_bad = bool(g) and g.get("ok") is False and nb is not None and g.get("name") == nb["name"]
    if nb is not None and not r:                                      # Alter in Ordnung: Tage trotzdem für den Fehlertext berechnen
        d = {"alter_tage": max(0, int((time.time() - nb["ts"]) // 86400)), "datum": time.strftime("%Y-%m-%d", time.localtime(nb["ts"]))}
    if st["fehler"] or pruef_bad:
        out.update(zeige=True, art="fehler", grund="angelegt" if st["fehler"] else "pruefung", ausblendbar=False)
    elif nb is None:
        out.update(zeige=True, art="keine")
    elif r:
        out.update(zeige=True, art="alt")
    if out["zeige"]:
        out["alter_tage"] = d.get("alter_tage")
        out["datum"] = d.get("datum")
    return out


@router.get("/api/backup/waechter")
def api_waechter(request: Request, tage: str = ""):
    extras._admin_only(request)
    try:
        return waechter(tage)
    except ValueError:
        raise HTTPException(400, "„tage“ muss eine Zahl sein")


@router.post("/api/backup/check")
def api_check(request: Request):
    """Admin: neueste Sicherung prüfen (Probelauf im Temp-Verzeichnis, ändert nichts an den Live-Daten) und das Ergebnis merken."""
    extras._admin_only(request)
    import json
    nb = extras.newest_backup()
    now = int(time.time())
    if nb is None:
        res = {"ts": now, "ok": False, "fehler": "Es gibt noch keine Sicherung, die geprüft werden könnte.", "name": None}
    else:
        r = pruefe_zip(nb, tief=True)
        res = {"ts": now, "ok": r["ok"], "fehler": r["fehler"], "name": nb.name, "touren": r["touren"], "tracks": r["tracks"], "layouts": r["layouts"],
               "alter_h": round((now - nb.stat().st_mtime) / 3600, 1), "groesse": r["groesse"]}
    db.put("backup_check", json.dumps(res))
    return res
