"""Umgebungsvariablen und Standardwerte."""
import os
from pathlib import Path

DATA_DIR = Path(os.environ.get("DATA_DIR", "/data"))
PHOTOS_ROOT = Path(os.environ.get("PHOTOS_DIR", "/mnt/fotos"))   # optionale Quelle (Originale, z. B. SMB); je Benutzer: <Ordner>/<Benutzername>
TILE_FETCH = os.environ.get("TILE_FETCH", "1") == "1"            # 0 = Kacheln nur aus dem Zwischenspeicher liefern
UI_PASSWORD = os.environ.get("UI_PASSWORD", "")
APP_NAME = os.environ.get("APP_NAME", "meine-touren")      # Dienstname (für Hinweise in der Oberfläche)
UI_USER = os.environ.get("UI_USER", "admin")
TZ_NAME = os.environ.get("TZ", "Europe/Berlin")

DEFAULTS = {
    "zepp_email": "",
    "zepp_password": "",
    "zepp_token": "",            # Notlösung: apptoken aus dem Browser
    "zepp_host": "",             # leer = automatisch probieren
    "komoot_email": "",
    "komoot_password": "",
    "strava_client_id": "",
    "strava_client_secret": "",
    "strava_redirect": "",      # leer = Adresse der Seite selbst
    "zepp_auto_adopt": "1",      # 1 = Zepp-Trainings automatisch als lokale Tour übernehmen (kein Upload)
    "default_sport": "hike",
    "dup_tolerance_s": "300",
    "upload_pause_s": "2",
    "auto_sync": "1",            # 1 = täglich Komoot-Touren, Routen, Fotos aktualisieren (lädt NIE zu Komoot hoch)
    "auto_sync_hour": "3",
    "photo_margin_min": "30",
    "photo_only_tracked": "1",
    "camera_utc_offset_h": "",   # leer = Kamera-Zeit ist lokale Zeit (Europa/Berlin)
    "slideshow_seconds": "6",
    "photo_max_side": "2200",
    "photo_quality": "82",
    "notify_url": "",            # optionaler Webhook (ntfy, Gotify, eigener Dienst …) für Warnungen; leer = aus
    "garmin_email": "",          # nur zur Anzeige; gespeichert werden nur die Anmelde-Token (verschlüsselt), nie das Passwort
    "garmin_since": "",          # leer = alle Aktivitäten, sonst ab diesem Datum (JJJJ-MM-TT)
    "garmin_auto": "0",          # 1 = neue Garmin-Aktivitäten täglich automatisch als lokale Tour übernehmen
    "suunto_client_id": "",
    "suunto_client_secret": "",
    "suunto_key": "",            # Ocp-Apim-Subscription-Key (Suunto API Zone)
    "suunto_since": "",
    "suunto_auto": "0",
    "update_check": "1",         # 1 = regelmäßig auf GitHub nach einer neuen Version sehen
    "ui_prefs": "",              # JSON: Streckenfarbe, Kartenstil (geräteübergreifend)
}
SECRET_KEYS = {"zepp_password", "zepp_token", "komoot_password", "strava_client_secret", "strava_tokens", "suunto_client_secret", "suunto_key", "suunto_tokens", "garmin_tokens"}
ENCRYPTED_KEYS = SECRET_KEYS | {"zepp_key"}     # werden verschlüsselt in der Datenbank abgelegt (app/secret.py)

VERSION = "1.1.2 · Meine Touren (2026-10-25)"


SYSTEM_DB = DATA_DIR / "system.sqlite"          # Benutzer, Sitzungen, Freigaben
TILE_CACHE = DATA_DIR / "tilecache"             # Kartenkacheln und Geländedaten: für alle Benutzer gemeinsam
def _backup_root():
    if os.environ.get("BACKUP_DIR"):
        return Path(os.environ["BACKUP_DIR"])
    if os.name == "nt":                  # Windows: kein /var/backups
        return DATA_DIR / "backups-system"
    try:
        return Path("/var/backups/komoot-hub" if Path("/var/backups/komoot-hub").exists() else "/var/backups/meine-touren")
    except OSError:                      # z. B. macOS ohne Zugriff
        return DATA_DIR / "backups-system"


BACKUP_ROOT = _backup_root()


def user_dir(uid):
    return DATA_DIR / "users" / uid if uid else DATA_DIR


def backup_dirs(uid=None):
    sub = (lambda p: p / uid) if uid else (lambda p: p)
    return [sub(BACKUP_ROOT), sub(DATA_DIR / "backups")]


def __getattr__(name):          # pro Benutzer wechselnde Pfade
    from . import ctx
    u = ctx.uid(); base = user_dir(u)
    m = {"INBOX_DIR": base / "inbox", "LIB_DIR": base / "photos", "EXPORT_DIR": base / "export", "CACHE_DIR": base / "cache", "DB_PATH": base / "komoot_hub.sqlite", "TRACK_DIR": base / "tracks"}
    if name in m:
        return m[name]
    if name == "PHOTOS_DIR":
        if u and (PHOTOS_ROOT / u).is_dir():
            return PHOTOS_ROOT / u
        return PHOTOS_ROOT if (not u or u == ctx.first_uid) else PHOTOS_ROOT / u
    raise AttributeError(name)
