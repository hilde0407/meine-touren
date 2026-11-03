#!/bin/bash
# Meine Touren auf dem Mac auf die neueste Version von GitHub aktualisieren (Doppelklick) – ohne die Oberfläche.
# Ersetzt nur die Programmdateien (app, mac, windows, deploy, …). Deine Daten (~/Meine-Touren-Daten) bleiben unberührt;
# die bisherige Version liegt anschließend in .vorher/<Version>.
# Danach Meine Touren neu starten (Fenster schließen, Meine-Touren-lokal.command erneut öffnen).
set -e
cd "$(dirname "$0")"
APP="$(cd .. && pwd)"
[ -f "$APP/app/main.py" ] || { echo "app/main.py nicht gefunden – bitte das Skript im Ordner 'mac' des entpackten meine-touren belassen."; exit 1; }
DATA="${MT_DATA:-$HOME/Meine-Touren-Daten}"
VENV="${VENV:-$HOME/.meine-touren-venv}"
[ -x "$VENV/bin/python" ] || { echo "Die Python-Umgebung $VENV fehlt – bitte zuerst einmal Meine-Touren-lokal.command starten."; read -p "Enter zum Beenden"; exit 1; }
cd "$APP"
export DATA_DIR="$DATA" BACKUP_DIR="$DATA/backups-system" TZ="${TZ:-Europe/Berlin}" APP_NAME="meine-touren-lokal" MT_SELF_UPDATE=1
"$VENV/bin/python" - <<'PY'
import sys
from app import config, health, updater
cur = config.VERSION.split(" ")[0]
u = health.update_check()
if not u.get("ok") or not u.get("latest"):
    sys.exit("GitHub ist gerade nicht erreichbar – bitte später erneut versuchen.")
print(f"Installiert: {cur} · neueste Version auf GitHub: {u['latest']}")
if not u.get("newer"):
    print("Du hast bereits die neueste Version.")
    sys.exit(0)
print(f"Lade Version {u['latest']} …")
try:
    updater.install_local(u["latest"])
except Exception as e:  # noqa
    sys.exit(f"Update fehlgeschlagen: {e}")
print(f"✓ Version {u['latest']} installiert (die alte liegt in .vorher/{cur}).")
print("Bitte Meine Touren jetzt neu starten: Fenster schließen und Meine-Touren-lokal.command erneut öffnen.")
PY
rc=$?
read -p "Enter zum Beenden" _ || true
exit $rc
