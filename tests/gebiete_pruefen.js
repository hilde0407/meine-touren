#!/usr/bin/env node
/* Prüfbericht der Gebietszuordnung (3.62.1) über echte Touren, ohne Oberfläche.
   Aufruf:  node tests/gebiete_pruefen.js tours.json [--json]
   tours.json = Antwort von /api/tours (Liste mit id, name, lat, lng, g_country, g_state, g_county, g_place). Im Browser geht es auch ohne Datei:  Gebiete.bericht(TOURS).text
   Zeigt je Gebiet die Zahl der Touren mit Beispielnamen, Touren in mehr als 3 Gebieten (Ausreißer der Näherungsgrenzen), Touren ohne Gebiet nach Land und Gebiete ohne Tour. */
const fs = require("fs"), path = require("path");
const G = require(path.join(__dirname, "..", "app", "static", "js", "gebiete-daten.js"));
const file = process.argv[2];
if (!file) { console.error("Aufruf: node tests/gebiete_pruefen.js tours.json [--json]"); process.exit(2); }
let t = JSON.parse(fs.readFileSync(file, "utf8"));
if (!Array.isArray(t)) t = t.tours || t.items || [];
const fehler = G.pruefen();
if (fehler.length) { console.error("Tabelle fehlerhaft:\n" + fehler.join("\n")); process.exit(1); }
const b = G.bericht(t);
console.log(process.argv.includes("--json") ? JSON.stringify(b, null, 1) : b.text);
