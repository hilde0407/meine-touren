#!/bin/bash
# Meine Touren lokal auf dem Mac starten (Doppelklick). Beim ersten Start wird alles eingerichtet.
# Daten:  ~/Meine-Touren-Daten   (Touren, Fotos-Index, Einstellungen – unabhängig vom Server)
# Aufruf: Meine-Touren-lokal.command [Port]      (Standard 8080)  – Beenden: Fenster schließen oder Strg+C
set -e
cd "$(dirname "$0")"
# Skript liegt im Ordner mac/ des entpackten Archivs -> App-Ordner ist eine Ebene höher
APP="$(cd .. && pwd)"
[ -f "$APP/app/main.py" ] || { echo "app/main.py nicht gefunden – bitte das Skript im Ordner 'mac' des entpackten meine-touren belassen."; exit 1; }
PORT="${1:-8080}"
DATA="${MT_DATA:-$HOME/Meine-Touren-Daten}"
VENV="$HOME/.meine-touren-venv"

PY=""
for c in python3.13 python3.12 python3.11 python3.10 /opt/homebrew/bin/python3 /usr/local/bin/python3 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info>=(3,10) else 1)' 2>/dev/null; then PY="$c"; break; fi
done
[ -n "$PY" ] || { echo "Python 3.10 oder neuer fehlt. Installation: brew install python   (oder https://www.python.org/downloads/)"; read -p "Enter zum Beenden"; exit 1; }

einrichten() {
  if [ ! -x "$VENV/bin/uvicorn" ] || [ "$APP/requirements.txt" -nt "$VENV/.fertig" ]; then
    echo "Einrichtung (einmalig, 1–2 Minuten) …"
    "$PY" -m venv "$VENV"
    "$VENV/bin/pip" install -q --upgrade pip
    "$VENV/bin/pip" install -q -r "$APP/requirements.txt"
    touch "$VENV/.fertig"
  fi
  # Garmin-Konto-Anbindung (optional, braucht Python 3.12+; ohne sie geht der Datei-Import trotzdem)
  [ -f "$VENV/.garmin" ] || { "$VENV/bin/pip" install -q -r "$APP/requirements-optional.txt" >/dev/null 2>&1; touch "$VENV/.garmin"; }
}
einrichten
mkdir -p "$DATA"
# Quelle für "Fotos aus Ordner übernehmen" (Verwaltung): Standard ~/Pictures/fertige Fotos, sonst ~/Pictures; anderer Ordner: MT_FOTOS
FOTOS="${MT_FOTOS:-$HOME/Pictures/fertige Fotos}"; [ -d "$FOTOS" ] || FOTOS="$HOME/Pictures"
export PHOTOS_DIR="$FOTOS"
export DATA_DIR="$DATA" BACKUP_DIR="$DATA/backups-system" TZ="${TZ:-Europe/Berlin}" APP_NAME="meine-touren-lokal" TILE_FETCH=1
echo "Foto-Quelle: $FOTOS"
echo "Meine Touren läuft auf http://127.0.0.1:$PORT   (Daten: $DATA)"
( sleep 3; open "http://127.0.0.1:$PORT" ) &
cd "$APP"
export MT_SELF_UPDATE=1                    # erlaubt "Jetzt installieren" in der Oberfläche; Neustart übernimmt diese Schleife
while true; do
  rm -f "$DATA/.neustart"
  "$VENV/bin/uvicorn" app.main:app --host 127.0.0.1 --port "$PORT" || true
  if [ -f "$DATA/.neustart" ]; then
    echo "Neustart nach Update …"; rm -f "$DATA/.neustart"; rm -f "$VENV/.garmin"; einrichten; continue
  fi
  break
done
