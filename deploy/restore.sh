#!/usr/bin/env bash
# Stellt die Datenbank eines Benutzers aus einem Backup wieder her:  <name>-restore /var/backups/<name>/<benutzer>/meine-touren-....zip
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "Bitte als root ausführen"; exit 1; }
# Dienstname: eine bestehende Installation unter dem alten Namen "komoot-hub" bleibt unverändert
if [ -d /opt/komoot-hub ] && [ ! -d /opt/meine-touren ]; then NAME=komoot-hub; SVCUSER=komoot; else NAME=meine-touren; SVCUSER=touren; fi
APP=/opt/$NAME; DATA=/var/lib/$NAME; ENVF=/etc/$NAME.env; BACKUPS=/var/backups/$NAME
F="${1:-}"; [ -f "$F" ] || { echo "Aufruf: $0 <backup.zip>"; ls -1 "$BACKUPS" 2>/dev/null | tail -5; exit 1; }
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
python3 - "$F" "$T" <<'PY'
import sys, zipfile
z = zipfile.ZipFile(sys.argv[1]); z.extract("komoot_hub.sqlite", sys.argv[2])
for n in z.namelist():
    if n.startswith("tracks/"): z.extract(n, sys.argv[2])
open(sys.argv[2] + "/uid", "w").write(z.read("UID.txt").decode() if "UID.txt" in z.namelist() else "")
PY
U=$(cat "$T/uid")
[ -n "$U" ] && DATA="$DATA/users/$U" && mkdir -p "$DATA" && chown "$SVCUSER:$SVCUSER" "$DATA"
systemctl stop "$NAME"
[ -f "$DATA/komoot_hub.sqlite" ] && cp "$DATA/komoot_hub.sqlite" "$DATA/komoot_hub.sqlite.vor-restore"
cp "$T/komoot_hub.sqlite" "$DATA/komoot_hub.sqlite"; chown "$SVCUSER:$SVCUSER" "$DATA/komoot_hub.sqlite"
[ -d "$T/tracks" ] && mkdir -p "$DATA/tracks" && cp -n "$T"/tracks/*.gpx "$DATA/tracks/" && chown -R "$SVCUSER:$SVCUSER" "$DATA/tracks"
rm -f "$DATA/komoot_hub.sqlite-wal" "$DATA/komoot_hub.sqlite-shm"
systemctl start "$NAME"
echo "Wiederhergestellt aus $F${U:+ (Benutzer $U)} (vorheriger Stand: komoot_hub.sqlite.vor-restore)."
echo "Hinweis: Fotos und Strecken-Zwischenspeicher sind nicht im Backup (Fotos neu hochladen bzw. 'Strecken lokal sichern')."
