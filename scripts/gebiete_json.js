#!/usr/bin/env node
/* Erzeugt app/gebiete.json aus app/static/js/gebiete-daten.js (3.64.0): dieselbe Gebietstabelle für den Server (app/gebiete.py), damit es nur EINE Quelle gibt.
   Aufruf:  node scripts/gebiete_json.js            schreibt app/gebiete.json
            node scripts/gebiete_json.js --stdout   gibt den Inhalt nur aus (tests/test_gebiete_364.py vergleicht ihn mit der Datei)
   Die Datei nie von Hand ändern: Gebiete in gebiete-daten.js ändern, dann dieses Skript ausführen. */
const fs = require("fs"), path = require("path");
const G = require(path.join(__dirname, "..", "app", "static", "js", "gebiete-daten.js"));
const rows = G.liste.map(x => ({id: x.id, name: x.name, typ: x.typ, eltern: x.eltern, boxen: x.boxen, poly: x.poly, alias: x.alias, county: x.county, nicht: x.nicht, nichtKreis: x.nichtKreis, in: x.in, prio: x.prio, anz: x.anz}));
const out = '{"quelle": "app/static/js/gebiete-daten.js (erzeugt mit node scripts/gebiete_json.js, nicht von Hand ändern)", "gebiete": [\n' + rows.map(r => JSON.stringify(r)).join(",\n") + "\n]}\n";
if (process.argv.includes("--stdout")) process.stdout.write(out);
else fs.writeFileSync(path.join(__dirname, "..", "app", "gebiete.json"), out);
