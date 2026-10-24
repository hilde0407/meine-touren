"""Zustand der Installation, doppelte Tournamen, Hinweis auf neue Version."""
import json
import shutil
import time
from datetime import datetime

import requests
from fastapi import APIRouter

from . import config, ctx, db, extras, routes

router = APIRouter()
_upd = {"ts": 0, "data": None}
REPO = "hilde0407/meine-touren"


def _ver(s):
    out = []
    for x in str(s).split(" ")[0].lstrip("v").split("."):
        try:
            out.append(int(x))
        except ValueError:
            out.append(0)
    return out


def duplicate_names():
    """Touren, die am selben Tag oder in derselben Woche exakt gleich heißen (z. B. zwei Mal „Tag 6“)."""
    rows = db.query("SELECT id,name,start_ts,source FROM tours WHERE name IS NOT NULL AND name!='' AND start_ts IS NOT NULL ORDER BY start_ts")
    by = {}
    for r in rows:
        by.setdefault(r["name"].strip().lower(), []).append(r)
    out = []
    for k, rs in by.items():
        grp = [r for r in rs if any(abs(r["start_ts"] - o["start_ts"]) < 7 * 86400 and r["id"] != o["id"] for o in rs)]
        if grp:
            out.append({"name": grp[0]["name"], "tours": [{"id": r["id"], "date": datetime.fromtimestamp(r["start_ts"]).strftime("%d.%m.%Y"), "source": r["source"]} for r in grp]})
    return out


def health():
    checks = []

    def add(name, ok, detail, hint=""):
        checks.append({"name": name, "ok": ok, "detail": detail, "hint": hint})

    em = db.get("komoot_email") and db.get("komoot_password")
    add("Komoot-Zugang", bool(em), "gespeichert" if em else "fehlt", "" if em else "Verwaltung → Komoot: E-Mail und Passwort eintragen")
    nb = extras.newest_backup()
    age = (time.time() - nb.stat().st_mtime) / 3600 if nb else None
    add("Letztes Backup", age is not None and age < 36, f"vor {age:.0f} h" if age is not None else "noch keines",
        "" if age is not None and age < 36 else "Verwaltung → Sicherung: jetzt sichern")
    p = config.DB_PATH
    size = p.stat().st_size / 1e6 if p.exists() else 0
    add("Datenbank", True, f"{size:.0f} MB")
    try:
        du = shutil.disk_usage(config.DATA_DIR if config.DATA_DIR.exists() else config.DATA_DIR.parent)
        free = du.free / 1e9
        add("Freier Speicher", free > 2, f"{free:.1f} GB frei", "" if free > 2 else "Weniger als 2 GB frei – Platz schaffen")
    except OSError:
        pass
    n = db.one("SELECT COUNT(*) n FROM tours")["n"]
    no_route = sum(1 for t in db.query("SELECT id FROM tours") if not routes.path_full(t["id"]).exists())
    add("Touren ohne Strecke", no_route == 0, f"{no_route} von {n}", "" if no_route == 0 else "Verwaltung → „Routen laden“")
    r = db.one("SELECT COUNT(*) n, SUM(tour_id IS NULL) o FROM photos")
    o = r["o"] or 0
    add("Fotos ohne Tour", True, f"{o} von {r['n'] or 0}", "")
    d = duplicate_names()
    add("Doppelte Tournamen", not d, f"{len(d)} Namen" if d else "keine", "" if not d else "Touren umbenennen (Tour öffnen → Umbenennen)")
    err = db.get("backup_err")
    if err:
        add("Backup-Fehler", False, err[:120], "Sicherungsordner prüfen")
    return {"checks": checks, "ok": all(c["ok"] for c in checks), "duplicates": d, "version": config.VERSION}


def update_check():
    if _upd["data"] is not None and time.time() - _upd["ts"] < 6 * 3600:
        return _upd["data"]
    res = {"current": config.VERSION.split(" ")[0], "latest": None, "url": f"https://github.com/{REPO}/releases/latest", "newer": False}
    try:
        r = requests.get(f"https://api.github.com/repos/{REPO}/releases/latest", timeout=8, headers={"Accept": "application/vnd.github+json"})
        if r.status_code == 200:
            j = r.json()
            res["latest"] = j.get("tag_name", "").lstrip("v")
            res["url"] = j.get("html_url") or res["url"]
            res["newer"] = _ver(res["latest"]) > _ver(res["current"])
    except Exception:  # noqa
        pass
    _upd.update(ts=time.time(), data=res)
    return res


@router.get("/api/zustand")
def api_health():
    return health()


@router.get("/api/update-check")
def api_update():
    return update_check()
