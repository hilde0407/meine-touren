/* Sprache / Language – Übersetzungsschicht (Beta).
   Die Oberfläche ist deutsch geschrieben. Für Englisch werden Texte zur Laufzeit über ein Wörterbuch ersetzt
   (Textknoten, Platzhalter, Tooltips) und Datums-/Zahlenformate umgestellt. Was nicht im Wörterbuch steht, bleibt deutsch.
   Umschalten: Knopf „DE / EN“ oben rechts; Standard nach Browsersprache. Ergänzen: Zeile „deutsch|english“ in D unten. */
(function () {
  let lang = "de";
  try { lang = localStorage.getItem("lang") || ((navigator.language || "de").toLowerCase().startsWith("de") ? "de" : "en"); } catch (e) {}
  window.LANG = lang;
  document.documentElement.lang = lang;
  window.setLang = l => { try { localStorage.setItem("lang", l); } catch (e) {} location.reload(); };
  const mkBtn = () => {
    const b = document.createElement("button");
    b.id = "langsw"; b.className = "btn ghost sm"; b.title = "Sprache / Language";
    b.textContent = lang === "de" ? "DE → EN" : "EN → DE";
    b.style.cssText = "margin-left:8px;color:#fff;border:1px solid rgba(255,255,255,.5);background:transparent;white-space:nowrap;font-size:12px;padding:4px 8px;border-radius:6px;cursor:pointer";
    b.onclick = () => window.setLang(lang === "de" ? "en" : "de");
    const top = document.querySelector("header.top");
    if (top) top.appendChild(b);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mkBtn); else mkBtn();
  if (lang !== "en") return;

  const D = {};
  `Übersicht|Overview
Karte|Map
Touren|Tours
Reisen|Trips
Auswertung|Statistics
Fotos|Photos
Prüfen|Check
Verwaltung|Admin
Abbrechen|Cancel
Schließen|Close
Diashow|Slideshow
Wird geladen …|Loading …
Speichern|Save
Stunden|Hours
Alle Sportarten|All sports
Strecke|Distance
Aufstieg|Ascent
Abstieg|Descent
Std.|h
Min.|min
Trennen|Disconnect
Konto & Freigaben|Account & sharing
Tempo|Pace
Noch keine Touren|No tours yet
Kilometer|Kilometres
Meter aufwärts|Metres up
Unterwegs|On the road
Sportarten|Sports
Meiste Höhenmeter|Most elevation
Längste Dauer|Longest duration
Alle Jahre|All years
Alle Regionen|All regions
Höhenprofil|Elevation profile
Löschen …|Delete …
Löschen|Delete
Zurück|Back
‹ Zurück|‹ Back
Importieren|Import
Zustand|Status
(optional)|(optional)
nichts|nothing
Probelauf|Dry run
Jetzt importieren|Import now
Tage|Days
Jetzt sichern|Back up now
Entfernen|Remove
Mögliche Duplikate|Possible duplicates
Auffällige Höhenmeter|Unusual elevation
lokal löschen|delete locally
Unplausible Touren|Implausible tours
Mehr|More
Ansicht|View
Benutzer|Users
Geteilte Fotos|Shared photos
Alle Benutzer|All users
Freigeben|Share
Streckenfarbe|Track colour
je Sportart|by sport
einheitlich|uniform
Einfärben nach|Colour by
einfarbig|single colour
Steigung|Gradient
Breite|Width
Gesamt|Total
pro Tour im Schnitt|per tour on average
Stärkster Monat|Strongest month
stärkster Monat|strongest month
Ein Klick auf einen Balken öffnet das Jahr.|Click a bar to open that year.
Kilometer im Jahresverlauf|Kilometres over the years
Längste Tour|Longest tour
Keine Touren|No tours
An diesem Tag|On this day
in früheren Jahren|in earlier years
Erinnerungen|Memories
Zufalls-Diashow starten|Start random slideshow
Alle Touren|All tours
Alle Tags|All tags
Neueste zuerst|Newest first
Älteste zuerst|Oldest first
Längste Strecke|Longest distance
Mehr anzeigen|Show more
Keine Treffer|No results
Tour hochladen|Upload tour
Hochladen|Upload
Vorherige|Previous
Nächste|Next
✎ Umbenennen|✎ Rename
Umbenennen|Rename
lokal gespeichert|stored locally
⟳ Mit Komoot abgleichen|⟳ Sync with Komoot
⬆ Hochladen|⬆ Upload
🗑 Löschen|🗑 Delete
🏷 Tags|🏷 Tags
🔗 Teilen|🔗 Share
🎨 Streckenfarbe|🎨 Track colour
🎨 Strecken|🎨 Tracks
Dauer|Duration
Tempo im Schnitt|Average pace
Höchster Punkt|Highest point
Fotos hinzufügen …|Add photos …
Zeit per GPS prüfen|Check time via GPS
In Komoot öffnen|Open in Komoot
Tour umbenennen|Rename tour
Vorschläge aus den Kartendaten|Suggestions from map data
Suche Orte und Gipfel …|Search places and peaks …
Noch keine Fotos|No photos yet
Zufall|Random
Aus dieser Tour entfernen|Remove from this tour
Zuordnung lösen|Unassign
Zeit verschieben …|Shift time …
Fertig|Done
Verschieben|Shift
später (+)|later (+)
früher (−)|earlier (−)
−1 Std.|−1 h
+1 Std.|+1 h
−2 Std.|−2 h
+2 Std.|+2 h
Tour (nächstgelegene zuerst)|Tour (nearest first)
Zeitversatz anwenden auf|Apply time shift to
nur die gewählten Fotos|only the selected photos
alle Fotos desselben Aufnahmetags|all photos of the same day
alle noch nicht zugeordneten Fotos|all photos not yet assigned
Zuordnen|Assign
Ordner oder Fotos hierher ziehen|Drag folders or photos here
Ordner wählen …|Choose folder …
Einzelne Fotos wählen …|Choose individual photos …
Fotos werden geprüft …|Checking photos …
Nichts zu importieren:|Nothing to import:
Anderen Ordner wählen|Choose another folder
Auf der Karte ansehen|View on map
Fotos ansehen|View photos
Komoot aktualisieren|Update Komoot
Nur Touren|Tours only
Strecken lokal sichern|Save tracks locally
Regionen bestimmen|Determine regions
Bibliothek neu einlesen|Rescan library
Fotos aus Ordner übernehmen|Import photos from folder
Fotos importieren …|Import photos …
Bildeinstellungen|Image settings
Code einlösen|Redeem code
Zepp-Import starten|Start Zepp import
Höhenmeter neu berechnen|Recalculate elevation
Token testen|Test token
Datum|Date
Sport|Sport
Alle wählen|Select all
Lokal übernehmen|Add locally
Übernehmen und hochladen|Add and upload
Dateien importieren|Import files
Verbinden|Connect
✓ verbunden|✓ connected
Automatik|Automation
Täglich aktualisieren (Komoot, Routen, Fotos)|Update daily (Komoot, routes, photos)
Protokoll|Log
Einstellungen speichern|Save settings
Token funktioniert ✓|Token works ✓
Ziel hinzufügen|Add goal
alle Sportarten|all sports
Alle Aktivitäten|All activities
Rekorde|Records
Tage mit Touren|Days with tours
Wochen|Weeks
Bestwerte gesamt|Overall bests
Höchste Punkte|Highest points
Nach Wochentag|By weekday
Je Sportart|By sport
‹ Übersicht|‹ Overview
Drucken / als PDF speichern|Print / save as PDF
Mein Tourenjahr|My year in tours
Höhenmeter|Elevation gain
Tage unterwegs|Days out
Kilometer pro Monat|Kilometres per month
Die fünf längsten Touren|The five longest tours
Fotos des Jahres|Photos of the year
🛰 3D-Flug|🛰 3D flight
🔗 Diashow-Link|🔗 Slideshow link
Updates|Updates
Installiert:|Installed:
✓ aktuell|✓ up to date
Was ist neu?|What's new?
Jetzt prüfen|Check now
Auf GitHub ansehen|View on GitHub
Sicherung|Backup
Backup jetzt herunterladen|Download backup now
Zugriffsschutz|Access protection
✓ Passwortschutz ist aktiv.|✓ Password protection is active.
Heatmap|Heatmap
Touren im Ausschnitt|Tours in view
Im Kartenausschnitt|In map view
⏸ Pause|⏸ Pause
Kamera folgt|Camera follows
Kamera frei|Camera free
nah|near
mittel|medium
weit|far
flach|flat
schräg|tilted
sehr schräg|very tilted
Straßenkarte|Street map
Topografisch|Topographic
Satellit|Satellite
⏺ Video|⏺ Video
Lade Strecke …|Loading track …
Analyse|Analysis
Bewegungszeit|Moving time
Ø-Tempo in Bewegung|Avg. pace while moving
Steigung auf der Karte zeigen|Show gradient on map
Pausen auf der Karte zeigen|Show pauses on map
Mit anderer Tour vergleichen …|Compare with another tour …
Tourvergleich|Tour comparison
Zeit über Strecke|Time over distance
Foto-Eingang|Photo inbox
Selbsttest|Self-test
Selbsttest starten|Start self-test
Prüfen & Aufräumen|Check & tidy up
Wird geprüft …|Checking …
Überblick|Overview
Touren insgesamt|Tours in total
Noch mit Standardname|Still with default name
✓ Keine Duplikate gefunden.|✓ No duplicates found.
Korrigieren|Correct
✓ Keine auffälligen Höhen.|✓ No unusual elevation.
Namen vergeben|Assign names
✓ Alle Touren haben einen eigenen Namen.|✓ All tours have their own name.
Sportart ändern|Change sport
Ausblenden|Hide
✓ Keine auffälligen Touren.|✓ No unusual tours.
Wieder einblenden|Show again
Tour löschen?|Delete tour?
Suche …|Search …
Keine Vorschläge.|No suggestions.
Orte, Gipfel, Leistung, Wetter, Neuland|Places, peaks, performance, weather, new ground
Häufigste Startorte|Most frequent start locations
Gipfel & Pässe|Peaks & passes
Noch keine Gipfel bestimmt.|No peaks determined yet.
Wanderführer-Fortschritt|Guidebook progress
offen|open
Tags & Alben|Tags & albums
Noch keine Tags|No tags yet
Tour teilen|Share tour
Fotos mitsenden|Include photos
Link erstellen|Create link
Kopieren|Copy
Widerrufen|Revoke
Noch kein Link.|No link yet.
3D-Flug über alles|3D flight over everything
Karte offline speichern|Save map offline
Keine Fotos.|No photos.
Alben & Tags|Albums & tags
Noch keine Tags vergeben.|No tags assigned yet.
Leistung über die Jahre|Performance over the years
Höhenmeter pro Stunde|Elevation gain per hour
Wetter|Weather
Extreme & Regen|Extremes & rain
Wärmste Tour|Warmest tour
Kälteste Tour|Coldest tour
Nasseste Tour|Wettest tour
Noch keine Wetterdaten.|No weather data yet.
Neuland|New ground
Je Jahr|By year
Größte Entdeckungen|Biggest discoveries
Umbenennen nach Regeln|Rename by rules
Vorsilbe hinzufügen|Add prefix
Nachsilbe hinzufügen|Add suffix
Januar|January
Februar|February
März|March
Mai|May
Juni|June
Juli|July
Oktober|October
Dezember|December
Mär|Mar
Okt|Oct
Dez|Dec
Montag|Monday
Dienstag|Tuesday
Mittwoch|Wednesday
Donnerstag|Thursday
Freitag|Friday
Samstag|Saturday
Sonntag|Sunday
Mo|Mon
Di|Tue
Mi|Wed
Do|Thu
Fr|Fri
Sa|Sat
So|Sun
Wandern|Hiking
Radfahren|Cycling
Laufen|Running
Rennrad|Road bike
Mountainbike|Mountain bike
Spazieren|Walking
Ohne Tour|No tour
Weiter|Next
Ja|Yes
Nein|No
Ändern|Change
Aktualisieren|Refresh
Suchen|Search
Suche|Search
Name|Name
Hinzufügen|Add
Anmelden|Sign in
Abmelden|Sign out
Passwort|Password
Benutzername|Username
Einstellungen|Settings
Fehler|Error
Fertig.|Done.
Jetzt installieren|Install now
Die Datensicherung ist älter als einen Tag.|The backup is more than a day old.
Demo-Modus: Alle Touren und Fotos hier sind Beispieldaten.|Demo mode: all tours and photos here are sample data.
Foto-Import|Photo import
Zeit der Fotos anpassen|Adjust photo time
Fotos übernehmen|Import photos
Zuordnung|Assignment
Ohne Zuordnung|Unassigned
Zeitzone der Kamera|Camera time zone
Alles in Ordnung|All good
Bitte anmelden|Please sign in
Tour ansehen|View tour
Radtour|Bike ride
Wanderung|Hike
Jahresrückblick|Year in review
Suchen …  ( / )|Search …  ( / )
Letzte Tour|Latest tour
Uhr|
Wandern, Radfahren|Hiking, cycling
Komoot-Zugang|Komoot access
Letztes Backup|Last backup
Datenbank|Database
Freier Speicher|Free space
Tours ohne Strecke|Tours without track
Touren ohne Strecke|Tours without track
Fotos ohne Tour|Photos without tour
bitte prüfen|please check
Status|Status
Regelmäßig (alle 6 Stunden) auf neue Versionen prüfen|Check for new versions regularly (every 6 hours)
neueste Version auf GitHub:|latest version on GitHub:
frei|free
noch keines|none yet
fehlt|missing
🧹 Track korrigieren|🧹 Fix track
GPS-Track korrigieren|Fix GPS track
Track wird untersucht …|Analysing track …
Einblenden & Track korrigieren|Show & fix track
Korrigieren|Fix
Original wiederherstellen|Restore original
Erneut anwenden|Apply again
Schnelle Abschnitte|Fast sections
✓ Im Track wurde nichts Auffälliges gefunden.|✓ Nothing unusual found in the track.`.split("\n").forEach(l => { const i = l.indexOf("|"); if (i > 0) D[l.slice(0, i)] = l.slice(i + 1); });

  const decode = s => s.replace(/&amp;/g, "&");
  const P = [   // dynamische Texte
    [/^(\d+) Fotos?$/, (m, n) => `${n} photo${n === "1" ? "" : "s"}`],
    [/^(\d+) Touren?$/, (m, n) => `${n} tour${n === "1" ? "" : "s"}`],
    [/^(\d+) Tage?$/, (m, n) => `${n} day${n === "1" ? "" : "s"}`],
    [/^(\d+)\. (Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember) (\d{4})$/, (m, d, mo, y) => `${D[mo] || mo} ${d}, ${y}`],
    [/^(.*), (\d+) Fotos$/, (m, a, n) => `${a}, ${n} photos`],
    [/^(\d+) von (\d+)$/, (m, a, b) => `${a} of ${b}`],
    [/^(\d+(?:[.,]\d+)?) Uhr$/, (m, t) => t],
  ];
  const S = [   // Ersetzungen innerhalb längerer Texte
    [/(\d+)\. (Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember) (\d{4})/g, (m, d, mo, y) => `${D[mo] || mo} ${d}, ${y}`],
    [/(\d+) Bilder, (\d+) einer Tour zugeordnet/g, "$1 images, $2 assigned to a tour"],
    [/Es gibt noch kein Backup – das erste wird automatisch angelegt \(nachts\), oder jetzt sofort:/g, "There is no backup yet – the first one is created automatically (at night), or right now:"],
    [/Letzte Tour, Wandern/g, "Latest tour, hiking"],
    [/Letzte Tour, Radtour/g, "Latest tour, cycling"],
    [/Letzte Tour/g, "Latest tour"],
    [/Jahresrückblick (\d{4})/g, "Year in review $1"],
    [/ Uhr\b/g, ""],
    [/(\d+) Fotos in der Bibliothek, (\d+) einer Tour zugeordnet/g, "$1 photos in the library, $2 assigned to a tour"],
    [/(\d+) von (\d+)/g, "$1 of $2"],
    [/ in der Bibliothek/g, " in the library"],
    [/neueste Version auf GitHub/g, "latest version on GitHub"],
    [/Bibliothek:/g, "Library:"],
    [/(\d+(?:[.,]\d+)?) GB frei/g, "$1 GB free"],
    [/Verwaltung → /g, "Admin → "],
    [/fehlt – /g, "missing – "],
    [/noch keines – /g, "none yet – "],
    [/Verwaltung öffnen/g, "Open admin"],
    [/Fotos zuordnen/g, "Assign photos"],
    [/Diashow (\d{4})/g, "Slideshow $1"],
    [/(\d+) Fotos/g, "$1 photos"],
    [/(\d+) Touren/g, "$1 tours"],
    [/(\d+) Aktivitäten/g, "$1 activities"],
    [/\bTouren\b/g, "Tours"],
    [/\bFotos\b/g, "Photos"],
  ];
  const long = Object.keys(D).filter(k => k.length >= 16).sort((a, b) => b.length - a.length);
  const tr = s => {
    const t = decode(s).trim();
    if (!t) return s;
    let r = D[t];
    if (r === undefined) for (const [re, f] of P) { const m = re.exec(t); if (m) { r = f(...m); break; } }
    if (r === undefined && t.length > 16) { let u = t; for (const k of long) if (u.includes(k)) u = u.split(k).join(D[k]); if (u !== t) r = u; }
    if (r === undefined) { let u = t; for (const [re, f] of S) u = u.replace(re, f); if (u !== t) r = u; }
    if (r === undefined) return s;
    return s.replace(s.trim(), () => r);
  };
  window.TL = x => (typeof x === "string" ? tr(x) : x);

  const ATTR = ["placeholder", "title", "aria-label", "alt"];
  let busy = false;
  const doNode = n => {
    if (n.nodeType === 3) { const v = n.nodeValue; const r = tr(v); if (r !== v) n.nodeValue = r; return; }
    if (n.nodeType !== 1) return;
    if (/^(SCRIPT|STYLE|TEXTAREA|CODE|PRE)$/.test(n.tagName)) return;
    for (const a of ATTR) if (n.hasAttribute && n.hasAttribute(a)) { const v = n.getAttribute(a), r = tr(v); if (r !== v) n.setAttribute(a, r); }
    if (n.tagName === "INPUT" && /^(button|submit)$/.test(n.type) && n.value) { const r = tr(n.value); if (r !== n.value) n.value = r; }
    n.childNodes.forEach(doNode);
  };
  const run = fn => { if (busy) return; busy = true; try { fn(); } finally { busy = false; } };
  const mo = new MutationObserver(ms => run(() => ms.forEach(m => {
    if (m.type === "childList") m.addedNodes.forEach(doNode);
    else if (m.type === "characterData") doNode(m.target);
    else if (m.type === "attributes") { const v = m.target.getAttribute(m.attributeName), r = tr(v || ""); if (r !== v) m.target.setAttribute(m.attributeName, r); }
  })));
  const start = () => { run(() => doNode(document.body)); document.title = tr(document.title); mo.observe(document.body, {childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTR}); };
  if (document.body) start(); else document.addEventListener("DOMContentLoaded", start);

  // Datum und Zahlen
  const loc = a => (a === "de-DE" || a === "de" || a === undefined ? "en-GB" : a);
  ["toLocaleString", "toLocaleDateString", "toLocaleTimeString"].forEach(k => {
    const o = Date.prototype[k];
    Date.prototype[k] = function (a, b) { return o.call(this, loc(a), b); };
  });
  const on = Number.prototype.toLocaleString;
  Number.prototype.toLocaleString = function (a, b) { return on.call(this, a === "de-DE" ? "en-US" : a, b); };

  // Meldungsfenster
  const al = window.alert, cf = window.confirm, pr = window.prompt;
  window.alert = m => al(tr(String(m)));
  window.confirm = m => cf(tr(String(m)));
  window.prompt = (m, d) => pr(tr(String(m)), d);
})();
