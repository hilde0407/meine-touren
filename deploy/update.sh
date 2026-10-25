#!/usr/bin/env bash
# Aktualisiert Meine Touren.
#   <name>-update                 neueste ZIP in /root, /tmp oder /home; sonst die neueste Version von GitHub
#   <name>-update github          neueste Version von GitHub (Hauptzweig bzw. letztes Release)
#   <name>-update /pfad/x.zip     bestimmte ZIP      <name>-update /pfad/ordner   entpackter Projektordner
#   <name>-update release 1.2.3   genau diese Version (Tag v1.2.3 von GitHub)
#   <name>-update auto            von der Oberfläche angefordertes Update (vom Systemdienst <name>-update.path gestartet)
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Bitte als root ausführen"; exit 1; }
# Dienstname: eine bestehende Installation unter dem alten Namen "komoot-hub" bleibt unverändert
if [ -d /opt/komoot-hub ] && [ ! -d /opt/meine-touren ]; then NAME=komoot-hub; SVCUSER=komoot; else NAME=meine-touren; SVCUSER=touren; fi
APP=/opt/$NAME; DATA=/var/lib/$NAME; ENVF=/etc/$NAME.env; BACKUPS=/var/backups/$NAME
REPO="${MEINE_TOUREN_REPO:-hilde0407/meine-touren}"
A="${1:-}"
T=$(mktemp -d)
WANT=""
status() {   # Zustand für die Oberfläche: <Datenordner>/update-status
  local m; m=$(printf '%s' "$3" | tr -d '"\\\n\r' | cut -c1-300)
  printf '{"state":"%s","version":"%s","message":"%s","ts":%s}\n' "$1" "$2" "$m" "$(date +%s)" > "$DATA/update-status" 2>/dev/null || true
  chown "$SVCUSER" "$DATA/update-status" 2>/dev/null || true
}
if [ "$A" = auto ]; then
  REQ="$DATA/update-request"
  [ -f "$REQ" ] || exit 0
  WANT=$(tr -dc '0-9.' < "$REQ" | head -c 20); rm -f "$REQ"      # nur eine Versionsnummer wird akzeptiert, nie ein Pfad oder Programmcode
  [[ "$WANT" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { status error "" "Ungültige Versionsangabe"; exit 1; }
  A="release:$WANT"
elif [ "$A" = release ]; then
  WANT="${2:-}"; [[ "$WANT" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "Aufruf: $0 release 1.2.3"; exit 1; }
  A="release:$WANT"
fi
trap 'rc=$?; rm -rf "$T"; if [ $rc -ne 0 ] && [ -n "$WANT" ]; then status error "$WANT" "Update fehlgeschlagen – Einzelheiten: journalctl -u $NAME-update"; fi' EXIT
[ -n "$WANT" ] && status running "$WANT" "Lade und installiere Version $WANT …"
SRC=""
if [ -d "$A" ]; then
  SRC="$A"
else
  if [ -z "$A" ]; then
    A=$(ls -t /root/meine-touren*.zip /root/komoot-hub*.zip /root/*/meine-touren*.zip /tmp/meine-touren*.zip /tmp/komoot-hub*.zip /home/*/meine-touren*.zip /home/*/komoot-hub*.zip 2>/dev/null | head -1 || true)
    [ -n "$A" ] || A=github
  fi
  if [[ "$A" == release:* ]]; then
    echo "Lade Version $WANT von github.com/$REPO …"
    curl -fsSL "https://github.com/$REPO/archive/refs/tags/v$WANT.tar.gz" | tar -xz -C "$T"
  elif [ "$A" = github ]; then
    echo "Lade neueste Version von github.com/$REPO …"
    curl -fsSL "https://github.com/$REPO/archive/refs/heads/main.tar.gz" | tar -xz -C "$T"
  else
    [ -f "$A" ] || { echo "Datei $A nicht gefunden."; exit 1; }
    echo "Verwende: $A ($(du -h "$A" | cut -f1), $(date -r "$A" '+%d.%m.%Y %H:%M'))"
    unzip -l "$A" | grep "app/main.py" >/dev/null || { echo "Das ist keine Meine-Touren-ZIP (app/main.py fehlt)."; exit 1; }
    unzip -q "$A" -d "$T"
  fi
  SRC=$(dirname "$(dirname "$(find "$T" -path '*/deploy/install.sh' | head -1)")")
fi
[ -f "$SRC/deploy/install.sh" ] || { echo "install.sh nicht gefunden."; exit 1; }
NEW=$(grep -o 'VERSION = "[^"]*"' "$SRC/app/config.py" | cut -d'"' -f2)
OLD=$(curl -s localhost:8080/api/version 2>/dev/null | python3 -c 'import sys,json; print(json.load(sys.stdin).get("version","unbekannt"))' 2>/dev/null || echo "unbekannt")
echo "Installiert: $OLD"
echo "Neu:         $NEW"
if [ -n "$WANT" ]; then
  [ "${NEW%% *}" = "$WANT" ] || { echo "Die Version im Archiv ($NEW) passt nicht zur angeforderten ($WANT) – abgebrochen."; exit 1; }
  [ "$(printf '%s\n%s\n' "${OLD%% *}" "$WANT" | sort -V | tail -1)" = "$WANT" ] && [ "${OLD%% *}" != "$WANT" ] || { echo "Keine neuere Version – abgebrochen."; exit 1; }
fi
[ "$OLD" = "$NEW" ] && echo "Hinweis: gleiche Version – schon aktuell."
if [ -x "$APP/venv/bin/python" ]; then
  (cd "$APP" && set -a && . "$ENVF" && set +a && sudo -u "$SVCUSER" env DATA_DIR="$DATA_DIR" "$APP/venv/bin/python" -m app.backup "$BACKUPS" 14) >/dev/null 2>&1 && echo "Sicherung vor dem Update erstellt." || echo "(Sicherung vor dem Update übersprungen)"
fi
bash "$SRC/deploy/install.sh"
sleep 2
NOW=$(curl -s localhost:8080/api/version | python3 -c 'import sys,json; print(json.load(sys.stdin).get("version"))' 2>/dev/null || echo "")
echo "Läuft jetzt: $NOW"
[ -z "$WANT" ] || { [ "${NOW%% *}" = "$WANT" ] && status ok "$WANT" "Version $WANT ist installiert" || { status error "$WANT" "Dienst meldet nach dem Update: ${NOW:-keine Antwort}"; exit 1; }; }
echo "Im Browser: Strg+Shift+R (Mac: Cmd+Shift+R)."
