#!/usr/bin/env bash
# Eigenen BRouter-Server (Routenplanung für „Meine Touren“) installieren.
# Debian/Ubuntu, als root:   bash install-brouter.sh [Kacheln ...]
# Beispiel:                  bash install-brouter.sh E5_N45 E10_N45 E5_N50 E10_N50
# Ohne Angabe werden Deutschland/Alpenraum-Kacheln geladen. Weitere später mit:
#   bash install-brouter.sh --nur-kacheln E5_N40 W20_N25
set -euo pipefail
VER="${BROUTER_VERSION:-1.7.7}"
DIR=/opt/brouter
PORT="${BROUTER_PORT:-17777}"
SEG_URL="https://brouter.de/brouter/segments4"
# 5°×5°-Kacheln: Name = untere linke Ecke (E5_N45 = 5–10° O, 45–50° N)
DEFAULT_TILES=(E5_N45 E10_N45 E5_N50 E10_N50 W5_N45 E0_N45 E15_N45 E15_N50)

[ "$(id -u)" = 0 ] || { echo "Bitte als root ausführen."; exit 1; }
ONLY=0; [ "${1:-}" = "--nur-kacheln" ] && { ONLY=1; shift; }
TILES=("$@"); [ ${#TILES[@]} -eq 0 ] && TILES=("${DEFAULT_TILES[@]}")

if [ $ONLY -eq 0 ]; then
  apt-get update -qq
  apt-get install -y -qq default-jre-headless curl unzip ca-certificates
  id brouter >/dev/null 2>&1 || useradd --system --home "$DIR" --shell /usr/sbin/nologin brouter
  mkdir -p "$DIR/segments4" "$DIR/customprofiles"
  if [ ! -f "$DIR/brouter.jar" ]; then
    tmp=$(mktemp -d); cd "$tmp"
    curl -fL -o b.zip "https://github.com/abrensch/brouter/releases/download/v${VER}/brouter-${VER}.zip"
    unzip -q b.zip
    cp "brouter-${VER}/brouter-${VER}-all.jar" "$DIR/brouter.jar"
    rm -rf "$DIR/profiles2"; cp -r "brouter-${VER}/profiles2" "$DIR/profiles2"
    cd /; rm -rf "$tmp"
  fi
fi

for t in "${TILES[@]}"; do
  f="$DIR/segments4/$t.rd5"
  if [ -s "$f" ]; then echo "$t vorhanden"; continue; fi
  echo "Lade $t (100–400 MB) …"
  curl -fL --retry 3 -o "$f.part" "$SEG_URL/$t.rd5" && mv "$f.part" "$f" || { rm -f "$f.part"; echo "  $t nicht ladbar – übersprungen"; }
done
chown -R brouter:brouter "$DIR"

if [ $ONLY -eq 0 ]; then
cat > /etc/systemd/system/brouter.service <<UNIT
[Unit]
Description=BRouter (Routenplanung)
After=network.target

[Service]
User=brouter
WorkingDirectory=$DIR
ExecStart=/usr/bin/java -Xmx256M -Xms128M -Xss1024k -DmaxRunningTime=60 -cp $DIR/brouter.jar btools.server.RouteServer $DIR/segments4 $DIR/profiles2 $DIR/customprofiles $PORT 2
Restart=on-failure

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable --now brouter
  sleep 2
fi
systemctl restart brouter 2>/dev/null || true
IP=$(hostname -I | awk '{print $1}')
echo
echo "Fertig. In Meine Touren unter Verwaltung → Routenplanung eintragen:"
echo "  http://$IP:$PORT/brouter"
echo "Test:  curl 'http://127.0.0.1:$PORT/brouter?lonlats=8.40,49.00|8.45,49.02&profile=trekking&alternativeidx=0&format=geojson' | head -c 300"
