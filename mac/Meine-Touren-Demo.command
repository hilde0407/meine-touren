#!/bin/bash
# Meine Touren mit Beispieldaten ausprobieren (Doppelklick) – ohne eigene Daten, ohne Konto, ohne Netzwerk.
# Die Demo-Daten liegen in ~/Meine-Touren-Demo und sind unabhängig von deinen echten Daten.
cd "$(dirname "$0")"
export MT_DEMO=1 MT_DATA="${MT_DATA:-$HOME/Meine-Touren-Demo}"
mkdir -p "$MT_DATA/quelle"; export MT_FOTOS="$MT_DATA/quelle"   # nie die echten Fotos einlesen
exec ./Meine-Touren-lokal.command "${1:-8090}"
