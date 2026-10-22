#!/bin/bash
# Verkleinert Fotos auf dem Mac (nur Bilder, keine Videos) und überträgt sie in die Fotobibliothek des Containers.
# Aufruf:  bash fotos_senden.sh "$HOME/Pictures/Wanderfotos" root@192.168.1.50 [benutzername]
# Mit Benutzerverwaltung: Benutzername (Kennung, siehe Konto-Seite) angeben, dann landen die Fotos im privaten Ordner dieses Benutzers.
# Es werden nur neue/geänderte Fotos übertragen; Originale bleiben unverändert. Beliebig oft wiederholbar.
set -euo pipefail
QUELLE="${1:-$HOME/Pictures/Wanderfotos}"
ZIEL="${2:?Ziel angeben, z. B. root@192.168.1.50}"
BENUTZER="${3:-}"
MAXSEITE="${MAXSEITE:-2200}"     # längste Bildseite in Pixel
QUALITAET="${QUALITAET:-82}"
ARBEIT="$HOME/.fotos_senden_cache"
mkdir -p "$ARBEIT"
echo "Verkleinere Fotos aus: $QUELLE"
n=0
while IFS= read -r -d '' f; do
  rel="${f#"$QUELLE"/}"; rel="${rel%.*}.jpg"
  out="$ARBEIT/$rel"
  if [ -f "$out" ] && [ "$out" -nt "$f" ]; then continue; fi
  mkdir -p "$(dirname "$out")"
  # sips behält EXIF (Aufnahmezeit, GPS) bei und dreht nach der Ausrichtung
  sips -s format jpeg -s formatOptions "$QUALITAET" -Z "$MAXSEITE" "$f" --out "$out" >/dev/null 2>&1 || { echo "  übersprungen: $rel"; continue; }
  touch -r "$f" "$out"
  n=$((n+1)); [ $((n % 100)) -eq 0 ] && echo "  $n Fotos verkleinert …"
done < <(find "$QUELLE" -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' -o -iname '*.heic' -o -iname '*.tif' -o -iname '*.tiff' \) ! -name '.*' -print0)
echo "$n neue Fotos verkleinert. Übertrage zum Container …"
rsync -a --chmod=D755,F644 --info=progress2 -e ssh "$ARBEIT"/ "$ZIEL":"${DATENORDNER:-/var/lib/meine-touren}/${BENUTZER:+users/$BENUTZER/}photos/"
echo "Fertig. In der App: Verwaltung → Fotos → „Bibliothek neu einlesen“."
