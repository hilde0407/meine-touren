#!/bin/sh
# Start im Container: Besitzrechte des Datenordners setzen, dann ohne Root-Rechte weiterlaufen.
set -e
PUID="${PUID:-1000}"
PGID="${PGID:-1000}"
if [ "$(id -u)" = "0" ]; then
  mkdir -p /data /fotos
  # nur wenn nötig (spart bei großen Datenordnern Zeit)
  if [ "$(stat -c %u:%g /data)" != "$PUID:$PGID" ]; then
    chown -R "$PUID:$PGID" /data 2>/dev/null || echo "Hinweis: Rechte von /data konnten nicht gesetzt werden (Dateisystem schreibgeschützt?)"
  fi
  export HOME=/tmp
  exec gosu "$PUID:$PGID" "$@"
fi
exec "$@"
