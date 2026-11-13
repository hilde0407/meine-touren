"""Komplettsicherung für den Umzug auf einen neuen Server.

Anders als die tägliche Datenbanksicherung (klein, nur Datenbanken + lokale GPX) enthält das Umzugspaket den GESAMTEN Datenordner:
alle Datenbanken (Benutzer, Freigabelinks, Touren, Notizen, Kommentare …), Fotobibliotheken, Strecken-Zwischenspeicher (inkl. Original-Höhen),
lokale GPX/Pulsdateien, Exporte, Eingang, Schlüsseldatei der verschlüsselten Zugangsdaten und Passwortdatei der Oberfläche.
Weggelassen wird nur, was sich von selbst neu aufbaut (Vorschaubilder, Kartenkacheln, Sicherungen, Update-Merker).

Das Paket enthält die Schlüsseldatei und damit alle Zugangsdaten im Klartext-Zugriff: wie ein Passwort behandeln (Rechte 0600).
Wiederherstellen:  python3 umzug.py restore <paket.zip> <Datenordner>   (nur Standardbibliothek, läuft auch auf einem leeren Server).
"""
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import zipfile
from datetime import datetime
from pathlib import Path

MARK = "UMZUG.txt"
TOP_SKIP = {"backups", "backups-system", "tilecache", "update-status", "update-request", ".neustart"}
STORED = {".jpg", ".jpeg", ".png", ".heic", ".webp", ".zip", ".gz", ".mp4"}


def _skip(rel: Path) -> bool:
    p = rel.parts
    if p[0] in TOP_SKIP:
        return True
    if "thumb" in p and "cache" in p:                     # Vorschaubilder: baut sich neu auf
        return True
    n = rel.name
    return n.endswith(("-wal", "-shm", ".vor-restore", ".part", ".tmp"))


def _files(root: Path):
    for dp, dn, fn in os.walk(root):
        d = Path(dp)
        dn[:] = [x for x in dn if not _skip((d / x).relative_to(root))]
        for f in fn:
            r = (d / f).relative_to(root)
            if not _skip(r):
                yield d / f, r


def estimate(root: Path) -> int:
    return sum(f.stat().st_size for f, _ in _files(root) if f.exists())


def make(data_dir: Path, dest_dir: Path, version: str = "", keep: int = 2) -> Path:
    data_dir, dest_dir = Path(data_dir), Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    need = estimate(data_dir)
    free = shutil.disk_usage(dest_dir).free
    if free < need * 1.05 + 50 * 1024 * 1024:
        raise RuntimeError(f"Zu wenig freier Speicher für das Umzugspaket: {need // 1048576} MB nötig, {free // 1048576} MB frei in {dest_dir}")
    name = f"meine-touren-umzug-{datetime.now():%Y-%m-%d_%H%M}.zip"
    out, part = dest_dir / name, dest_dir / (name + ".part")
    n = 0
    with tempfile.TemporaryDirectory() as td, zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for f, rel in _files(data_dir):
            try:
                if f.suffix == ".sqlite":                 # laufende Datenbank: konsistente Kopie statt Rohdatei
                    tmp = Path(td) / "db.sqlite"
                    src = sqlite3.connect(str(f)); dst = sqlite3.connect(str(tmp))
                    with dst:
                        src.backup(dst)
                    src.close(); dst.close()
                    z.write(tmp, "data/" + rel.as_posix()); tmp.unlink()
                else:
                    z.write(f, "data/" + rel.as_posix(), compress_type=zipfile.ZIP_STORED if f.suffix.lower() in STORED else zipfile.ZIP_DEFLATED)
                n += 1
            except FileNotFoundError:
                continue                                   # während der Sicherung gelöscht (z. B. Zwischendatei)
        z.writestr(MARK, f"Meine Touren Umzugspaket\nVersion: {version}\nErstellt: {datetime.now().isoformat(timespec='seconds')}\nDateien: {n}\n"
                         "Wiederherstellen: deploy/restore.sh <datei.zip>   (Umzugspakete werden automatisch erkannt)\n"
                         "Nicht enthalten: /etc/meine-touren.env (Einstellungen des Dienstes) – bitte von Hand übernehmen.\n")
    os.chmod(part, 0o600)
    part.replace(out)
    for old in sorted(dest_dir.glob("meine-touren-umzug-*.zip"), key=lambda f: f.stat().st_mtime)[:-keep]:
        old.unlink()
    return out


def is_package(path) -> bool:
    try:
        with zipfile.ZipFile(path) as z:
            return MARK in z.namelist()
    except Exception:
        return False


def restore(pkg, target) -> int:
    """Packt das Umzugspaket nach <target>. Bestehende Dateien werden ersetzt; Pfade außerhalb von <target> werden abgelehnt."""
    target = Path(target).resolve()
    target.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(pkg) as z:
        if MARK not in z.namelist():
            raise RuntimeError("Das ist kein Umzugspaket")
        for m in z.infolist():
            if not m.filename.startswith("data/") or m.is_dir():
                continue
            dest = (target / m.filename[5:]).resolve()
            if target not in dest.parents:
                raise RuntimeError("Unzulässiger Pfad im Paket: " + m.filename)
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(m) as s, open(dest, "wb") as d:
                shutil.copyfileobj(s, d, 1 << 20)
            if dest.suffix == ".sqlite" or dest.name == "secret.key" or dest.name.endswith(".json") and dest.parent == target:
                os.chmod(dest, 0o600)
            n += 1
    for wal in list(target.rglob("*.sqlite-wal")) + list(target.rglob("*.sqlite-shm")):
        wal.unlink()
    return n


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "restore":
        print(f"{restore(sys.argv[2], sys.argv[3])} Dateien wiederhergestellt")
    else:
        sys.exit("Aufruf: umzug.py restore <paket.zip> <datenordner>")
