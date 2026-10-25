#!/usr/bin/env bash
# Installiert bzw. aktualisiert Meine Touren in einem Debian/Ubuntu-Container (ohne Docker).
# Aufruf als root im entpackten Projektordner:  bash deploy/install.sh
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Bitte als root ausführen"; exit 1; }
SRC="$(cd "$(dirname "$0")/.." && pwd)"
# Dienstname: eine bestehende Installation unter dem alten Namen "komoot-hub" bleibt unverändert
if [ -d /opt/komoot-hub ] && [ ! -d /opt/meine-touren ]; then NAME=komoot-hub; SVCUSER=komoot; else NAME=meine-touren; SVCUSER=touren; fi
APP=/opt/$NAME; DATA=/var/lib/$NAME; ENVF=/etc/$NAME.env; BACKUPS=/var/backups/$NAME

echo "== Pakete =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3 python3-venv python3-pip cifs-utils rsync nginx tzdata ca-certificates unzip curl sudo

echo "== Benutzer und Ordner =="
id "$SVCUSER" >/dev/null 2>&1 || useradd --system --home "$DATA" --shell /usr/sbin/nologin "$SVCUSER"
mkdir -p "$APP" "$DATA" "$DATA/photos" "$DATA/inbox" /mnt/fotos "$BACKUPS"
chmod 755 "$DATA" "$DATA/photos"
chown -R "$SVCUSER:$SVCUSER" "$DATA"
chown "$SVCUSER:$SVCUSER" "$BACKUPS"; chmod 700 "$BACKUPS"

echo "== Programm nach $APP =="
rm -rf "$APP/app"
cp -r "$SRC/app" "$SRC/requirements.txt" "$APP/"
find "$APP/app" -name __pycache__ -type d -prune -exec rm -rf {} +
python3 -m venv "$APP/venv"
"$APP/venv/bin/pip" install -q --upgrade pip
"$APP/venv/bin/pip" install -q -r "$APP/requirements.txt"
chown -R root:root "$APP"

echo "== Einstellungen =="
if [ ! -f "$ENVF" ]; then
  cat > "$ENVF" <<EOT
TZ=${TZ:-Europe/Berlin}
DATA_DIR=$DATA
PHOTOS_DIR=/mnt/fotos
# Beim ersten Aufruf der Oberfläche wird ein Administrator angelegt (Benutzerverwaltung).
# Nur im Altbetrieb ohne Benutzer: gemeinsames Passwort (Benutzername UI_USER). Leer = ohne Schutz.
UI_USER=admin
UI_PASSWORD=
EOT
  chmod 640 "$ENVF"; chgrp "$SVCUSER" "$ENVF"
fi
grep -q '^APP_NAME=' "$ENVF" || echo "APP_NAME=$NAME" >> "$ENVF"
grep -q '^BACKUP_DIR=' "$ENVF" || echo "BACKUP_DIR=$BACKUPS" >> "$ENVF"

echo "== Systemdienst =="
sed -e "s|@USER@|$SVCUSER|g" -e "s|@APP@|$APP|g" -e "s|@ENVF@|$ENVF|g" -e "s|@DATA@|$DATA|g" -e "s|@BACKUPS@|$BACKUPS|g" \
  "$SRC/deploy/meine-touren.service" > "/etc/systemd/system/$NAME.service"
systemctl daemon-reload
systemctl enable --now "$NAME"
systemctl restart "$NAME"

echo "== Tägliches Backup (03:40 Uhr, 14 Stück, $BACKUPS) =="
cat > "/etc/cron.d/$NAME-backup" <<EOT
40 3 * * * $SVCUSER cd $APP && set -a && . $ENVF && set +a && $APP/venv/bin/python -m app.backup $BACKUPS 14 >/dev/null 2>&1
EOT
chmod 644 "/etc/cron.d/$NAME-backup"
# atomar ersetzen (läuft gerade ein Skript aus dieser Datei, bleibt dessen alte Fassung unverändert)
for pair in restore update; do cp "$SRC/deploy/$pair.sh" "/usr/local/bin/$NAME-$pair.new" && chmod 755 "/usr/local/bin/$NAME-$pair.new" && mv -f "/usr/local/bin/$NAME-$pair.new" "/usr/local/bin/$NAME-$pair"; done

echo "== Update aus der Oberfläche (Hilfsdienst mit Root-Rechten, nimmt nur eine Versionsnummer entgegen) =="
sed -e "s|@NAME@|$NAME|g" -e "s|@DATA@|$DATA|g" "$SRC/deploy/meine-touren-update.path" > "/etc/systemd/system/$NAME-update.path"
sed -e "s|@NAME@|$NAME|g" -e "s|@DATA@|$DATA|g" "$SRC/deploy/meine-touren-update.service" > "/etc/systemd/system/$NAME-update.service"
systemctl daemon-reload
systemctl enable --now "$NAME-update.path" >/dev/null 2>&1 || echo "(Update-Hilfsdienst konnte nicht gestartet werden – Updates weiterhin per $NAME-update github)"

echo "== Optional: Garmin-Konto-Anbindung =="
"$APP/venv/bin/pip" install -q -r "$SRC/requirements-optional.txt" >/dev/null 2>&1 && echo "garminconnect installiert." || echo "(garminconnect nicht installierbar, z. B. Python < 3.12 – Garmin-Import per Datei funktioniert trotzdem)"

echo "== Webserver (nginx, Port 80) =="
cp "$SRC/deploy/nginx-meine-touren.conf" "/etc/nginx/sites-available/$NAME"
ln -sf "/etc/nginx/sites-available/$NAME" "/etc/nginx/sites-enabled/$NAME"
rm -f /etc/nginx/sites-enabled/default
if nginx -t >/dev/null 2>&1; then systemctl reload nginx; else echo "WARNUNG: nginx-Konfiguration fehlerhaft (nginx -t) – die Oberfläche ist weiter unter Port 8080 erreichbar."; fi

IP=$(hostname -I | awk '{print $1}')
echo
echo "Fertig. Oberfläche: http://$IP/   (direkt ohne nginx: http://$IP:8080/)"
echo "Beim ersten Aufruf legst du den Administrator an."
echo "Einstellungen: $ENVF  (danach: systemctl restart $NAME)   Protokoll: journalctl -u $NAME -f"
