"""Selbsttest: prüft Datenbank, Dateien, Dienste und Zugänge – und ändert dabei nichts.

Die Antwort ist eine Liste aus Name, „läuft“ und einer kurzen Erklärung. In der Oberfläche
steht sie unter Verwaltung → Prüfen & Aufräumen.
"""
import os
import time
import shutil
from pathlib import Path

import requests
from fastapi import APIRouter

from . import config, ctx, db
from .extras import TILE_UP, UA

router = APIRouter()


@router.post("/api/selftest")
def api_selftest():
    from . import sync as _sync
    res = []

    def chk(name, fn):
        try:
            d = fn(); res.append({"name": name, "ok": True, "detail": d or ""})
        except Exception as e:  # noqa
            res.append({"name": name, "ok": False, "detail": str(e)[:200]})

    chk("Datenbank schreibbar", lambda: (db.execute("INSERT OR REPLACE INTO settings(k,v) VALUES('selftest','1')") and "") or "ok")

    def disk():
        u = shutil.disk_usage(config.DATA_DIR); free = u.free / 1e9
        if free < 1:
            raise RuntimeError(f"nur noch {free:.1f} GB frei")
        return f"{free:.1f} GB frei"
    chk("Speicherplatz", disk)
    kc = {}

    def kl():
        kc["k"] = _sync._komoot(True); return f"angemeldet als {kc['k'].user_id}"
    chk("Komoot-Anmeldung", kl)
    if "k" in kc:
        def tl():
            n = len(kc["k"].tours()); return f"{n} Touren bei Komoot"
        chk("Komoot-Tourenliste", tl)

        def co():
            t = db.one("SELECT id,name FROM tours ORDER BY start_ts DESC LIMIT 1")
            if not t:
                raise RuntimeError("keine Tour geladen")
            p = kc["k"].coordinates(t["id"])
            if not p:
                raise RuntimeError("keine Streckenpunkte")
            return f"{len(p)} Punkte für „{t['name']}“"
        chk("Komoot-Strecke abrufen", co)
    if db.get("zepp_token"):
        def zp():
            st = _sync.check_zepp()
            if st != "ok":
                raise RuntimeError(st.replace("fail:", ""))
            return "Token gültig"
        chk("Zepp-Token", zp)
    chk("Kartenkacheln (Internet)", lambda: (requests.get(TILE_UP["osm"].format(z=1, x=0, y=0), headers=UA, timeout=8).raise_for_status() or "erreichbar"))
    chk("Wetterdienst (Internet)", lambda: (requests.get("https://api.open-meteo.com/v1/forecast?latitude=50&longitude=8&hourly=temperature_2m&forecast_days=1", headers=UA, timeout=8).raise_for_status() or "erreichbar"))
    chk("Höhendaten für 3D (Internet)", lambda: (requests.get("https://s3.amazonaws.com/elevation-tiles-prod/terrarium/0/0/0.png", headers=UA, timeout=8).raise_for_status() or "erreichbar"))

    def bk():
        d = config.backup_dirs(ctx.uid())[0]; fs = sorted(list(d.glob("meine-touren-*.zip")) + list(d.glob("komoot-hub-*.zip")), key=lambda f: f.stat().st_mtime) if d.exists() else []
        if not fs:
            raise RuntimeError("noch kein automatisches Backup vorhanden (läuft nachts um 03:40)")
        age = (time.time() - fs[-1].stat().st_mtime) / 3600
        return f"{len(fs)} Backups, letztes vor {age:.0f} Std."
    chk("Automatisches Backup", bk)
    def integ():
        r = db.one("PRAGMA integrity_check")
        v = list(r.values())[0] if r else "?"
        if v != "ok":
            raise RuntimeError(f"Datenbank meldet: {v}")
        return "Datenbank in Ordnung"
    chk("Datenbank-Integrität", integ)

    def dirs():
        bad = []
        for n, d in (("Fotobibliothek", config.LIB_DIR), ("Eingang", config.INBOX_DIR), ("Backup", config.backup_dirs(ctx.uid())[0]), ("Strecken", config.TRACK_DIR)):
            try:
                d.mkdir(parents=True, exist_ok=True)
                probe = d / ".schreibtest"
                probe.write_text("ok"); probe.unlink()
            except Exception as e:  # noqa
                bad.append(f"{n}: {str(e)[:60]}")
        if bad:
            raise RuntimeError("; ".join(bad))
        return "Foto-, Eingangs-, Backup- und Streckenordner beschreibbar"
    chk("Schreibrechte der Ordner", dirs)

    def phfiles():
        rows = db.query("SELECT path FROM photos ORDER BY RANDOM() LIMIT 40")
        if not rows:
            return "noch keine Fotos"
        miss = sum(1 for r in rows if not Path(r["path"]).exists())
        if miss > len(rows) * 0.2:
            raise RuntimeError(f"{miss} von {len(rows)} geprüften Foto-Dateien fehlen (Quellordner nicht verbunden?)")
        return f"{len(rows) - miss} von {len(rows)} Stichproben vorhanden"
    chk("Foto-Dateien erreichbar", phfiles)

    def heic():
        from . import photos
        return "HEIC/HEIF wird unterstützt" if photos.heic_supported() else "HEIC/HEIF nicht installiert (optional: pip install pillow-heif)"
    chk("HEIC-Unterstützung", heic)

    def imp():
        from . import more
        n = len(more.implausible([dict(t) for t in db.query("SELECT * FROM tours")]))
        return f"{n} Touren unter „Prüfen“ auffällig" if n else "keine auffälligen Touren"
    chk("Auffällige Touren", imp)

    def upd():
        r = requests.get("https://api.github.com/repos/hilde0407/meine-touren/releases/latest", headers=UA, timeout=8)
        r.raise_for_status()
        return f"GitHub erreichbar, neueste Version {r.json().get('tag_name', '?')}"
    chk("Update-Prüfung (GitHub)", upd)

    def upsvc():
        mode = (os.environ.get("MT_SELF_UPDATE") == "1" and "lokal") or ("Dienst" if Path("/etc/systemd/system").exists() else "manuell")
        if mode == "Dienst" and not os.access(config.DATA_DIR, os.W_OK):
            raise RuntimeError("Datenordner nicht beschreibbar – Update-Anforderung nicht möglich")
        return f"Update-Weg: {mode}"
    chk("Update-Weg", upsvc)
    chk("Fotobibliothek", lambda: f"{db.one('SELECT COUNT(*) n FROM photos')['n']} Fotos, Eingang: {config.INBOX_DIR}")
    return res
