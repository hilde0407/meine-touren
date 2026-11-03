/* Sprache / Language – Übersetzungsschicht (Beta).
   Die Oberfläche ist deutsch geschrieben. Für Englisch werden Texte zur Laufzeit über ein Wörterbuch ersetzt
   (Textknoten, Platzhalter, Tooltips) und Datums-/Zahlenformate umgestellt. Was nicht im Wörterbuch steht, bleibt deutsch.
   Sprachen: Deutsch (Original), English, Français, Español – Auswahl oben rechts; Standard nach Browsersprache. Ergänzen: Zeile „deutsch|übersetzung“ (Englisch unten in EN, Französisch/Spanisch in 00-i18n-data.js). */
(function () {
  const SUP = ["de", "en", "fr", "es"];
  let lang = "de";
  try {
    lang = localStorage.getItem("lang");
    if (!SUP.includes(lang)) { const n = (navigator.language || "de").toLowerCase().slice(0, 2); lang = SUP.includes(n) ? n : "en"; }
  } catch (e) {}
  window.LANG = lang;
  document.documentElement.lang = lang;
  window.setLang = l => { try { localStorage.setItem("lang", l); } catch (e) {} location.reload(); };
  const mkBtn = () => {
    const b = document.createElement("select");
    b.id = "langsw"; b.title = "Sprache / Language / Langue / Idioma";
    b.innerHTML = SUP.map(x => `<option value="${x}"${x === lang ? " selected" : ""}>${x.toUpperCase()}</option>`).join("");
    b.style.cssText = "margin-left:8px;width:auto;color:#fff;border:1px solid rgba(255,255,255,.5);background:transparent;font-size:12px;padding:4px 6px;border-radius:6px;cursor:pointer";
    b.querySelectorAll("option").forEach(o => (o.style.color = "#000"));
    b.onchange = () => window.setLang(b.value);
    const top = document.querySelector("header.top");
    if (top) top.appendChild(b);
  };
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", mkBtn); else mkBtn();
  if (lang === "de") return;

  const D = {};
  const EN = `Noch kein Ziel für 2026. Setze dir eines, zum Beispiel 1000 km Wandern.|No goal for 2026 yet. Set one, for example 1000 km of hiking.
Aktivität im Jahr 2026|Activity in 2026
Neuere Tour (←)|Newer tour (←)
Ältere Tour (→)|Older tour (→)
Ältere Tour|Older tour
Farbe und Breite der Strecken ändern|Change colour and width of the tracks
Alle Strecken übereinander: häufig begangene Wege leuchten stärker|All tracks on top of each other: frequently walked paths glow brighter
Fotos mit GPS-Position anzeigen|Show photos with GPS position
Alle Touren auflisten, die den sichtbaren Kartenausschnitt berühren|List all tours touching the visible map area
um die Erde|around the Earth
Mount Everest bergauf|up Mount Everest
unterwegs|on the road
längste Serie|longest streak
Längste:|Longest:
· Meiste Höhenmeter:|· Most elevation:
Meiste Höhenmeter:|Most elevation:
gegenüber|compared with
Keine Reisen erkannt (es braucht mindestens zwei Touren am Stück, über 60 km von deinem üblichen Startort entfernt). Eigene Gruppen legst du mit Tags an.|No trips detected (at least two tours in a row, more than 60 km from your usual starting point, are needed). Create your own groups with tags.
in der Tour über „🏷 Tags“ vergeben|assign in the tour via “🏷 Tags”
Noch keine Regionen bestimmt: Verwaltung → „Regionen bestimmen“.|No regions determined yet: Admin → “Determine regions”.
Noch keine Wanderführer hinterlegt: Verwaltung → „Wanderführer“ (GPX-Dateien hochladen).|No hiking guides stored yet: Admin → “Hiking guides” (upload GPX files).
nur Jahre mit mindestens 2 Touren der Sportart|only years with at least 2 tours of the sport
Bei welcher Temperatur bist du unterwegs?|At what temperature do you go out?
unter 0 °|below 0 °
über 30 °|above 30 °
Anteil der Strecke, der auf keiner früheren Tour lag|Share of the route not covered by any earlier tour
Gruppe wählen|Choose group
ausgewählt|selected
Einer Tour zuordnen …|Assign to a tour …
Aufnahmezeit der gewählten Fotos verschieben, z. B. Zeitzone einer Reise korrigieren|Shift the capture time of the selected photos, e.g. to correct the time zone of a trip
Fehlende Strecken: Verwaltung → „Routen laden“. Fehlende Regionen: „Regionen bestimmen“.|Missing tracks: Admin → “Load routes”. Missing regions: “Determine regions”.
Mögliche Ursache:|Possible cause:
– „🧹 Track korrigieren“ hilft dabei.|– “🧹 Fix track” can help.
Der Track selbst ist unauffällig – wahrscheinlich ist nur die Sportart falsch.|The track itself looks fine – probably only the sport is wrong.
Zeitangaben nicht aufgezeichnet (überall gleiches Tempo) – Dauer korrigieren|Times not recorded (same pace everywhere) – correct the duration
Tour öffnen|Open tour
Name enthält …|Name contains …
Text ersetzen (Suchen → Ersetzen)|Replace text (search → replace)
Datum und Uhrzeit am Ende entfernen|Remove date and time at the end
Wähle Touren aus, lege eine Regel fest, prüfe die Vorschau und wende sie an.|Select tours, define a rule, check the preview and apply it.
Version:|Version:
Garmin, Suunto & andere Uhren|Garmin, Suunto & other watches
Touren und Fotos in die App holen|Bring tours and photos into the app
Weitere Wege (SMB-Ordner, Mac-Skript)|More ways (SMB folder, Mac script)
(Ordner nicht gefunden)|(folder not found)
Längste Bildseite (Pixel)|Longest image side (pixels)
JPEG-Qualität (1–95)|JPEG quality (1–95)
Zuordnung: Toleranz vor/nach der Tour (Min.)|Assignment: tolerance before/after the tour (min)
Automatik & Benachrichtigung|Automation & notification
Uhrzeit (Stunde)|Time of day (hour)
Benachrichtigung (optional)|Notification (optional)
Testnachricht senden (nach „Speichern“)|Send test message (after “Save”)
Wartung & Sicherheit|Maintenance & security
Sicherung, Zugriffsschutz, Selbsttest, Wanderführer|Backup, access protection, self-test, hiking guides
Die Oberfläche ist nicht passwortgeschützt.|The interface is not password-protected.
Wanderführer (z. B. Rother)|Hiking guides (e.g. Rother)
GPX-Dateien auswählen …|Choose GPX files …
Noch keine Wanderführer hinterlegt.|No hiking guides stored yet.
Einrichten …|Set up …
Touren zum Vergleichen nicht gefunden|Tours to compare not found
‹ Alle Touren|‹ All tours
⬇ GPX|⬇ GPX
⛰ Höhen korrigieren|⛰ Fix elevation
Steigung (Anteil der Strecke)|Gradient (share of the route)
📍 Fotos ausrichten|📍 Align photos
Andere Tour …|Other tour …
Diese Tour liegt nur lokal vor (Strecke als GPX im Datenordner)|This tour exists only locally (track as GPX in the data folder)
Zu Komoot, Strava … hochladen|Upload to Komoot, Strava …
Lokale Tour löschen|Delete local tour
Öffentlichen Link erzeugen|Create public link
Farbe und Breite der Strecke|Colour and width of the track
Höhen mit Geländemodell neu berechnen|Recalculate elevation with a terrain model
Ausreißer im GPS-Track entfernen, Seilbahn-/Autofahrten aus der Wertung nehmen|Remove outliers in the GPS track, exclude cable-car/car rides from the totals
Vergleicht den Aufnahmeort der Fotos mit der Strecke und korrigiert eine falsch gestellte Kamerauhr|Compares where the photos were taken with the track and corrects a wrongly set camera clock
Ein Foto auf die richtige Stelle der Strecke ziehen – die anderen wandern zeitlich mit|Drag a photo to the right spot on the track – the others move along in time
Aus den Fotos übernehmen|Take from the photos
Zeit aus den Foto-Positionen ableiten|Derive time from the photo positions
Nach der Korrektur:|After the correction:
Mit Schlagworten wie „Urlaub Réunion 2026“ oder „Rother Taunus“ entsteht ein Album mit eigener Seite (Karte, Summen, Fotos, 3D-Flug).|Tags such as “Holiday Réunion 2026” or “Rother Taunus” create an album with its own page (map, totals, photos, 3D flight).
Anfang und Ende (300 m) ausblenden – schützt deinen Wohnort|Hide start and end (300 m) – protects your home location
weiße Umrandung (besser sichtbar auf Satellit/Topo)|white outline (more visible on satellite/topo)
Zugang fehlt (Verwaltung)|Access missing (Admin)
nicht verbunden (Verwaltung → Portale)|not connected (Admin → Portals)
Mehrtagestouren|Multi-day tours
erkannt an Namen wie „… Tag 3“ oder „… Etappe 2“|detected from names like “… Day 3” or “… Stage 2”
Gesamtansicht|Overall view
Etappen|Stages
Meine Touren|Meine Touren
Name suchen|Search name
m auf|m up
m ab|m down
Übersicht|Overview
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
✓ Im Track wurde nichts Auffälliges gefunden.|✓ Nothing unusual found in the track.
📄 Tourblatt|📄 Tour sheet
Druckbares Tourblatt mit Karte, Höhenprofil und Fotos|Printable tour sheet with map, elevation profile and photos
‹ Zurück zur Tour|‹ Back to the tour
🖨 Drucken / als PDF speichern|🖨 Print / save as PDF
Gelbe Punkte = Fotos – anklicken zum Ansehen.|Yellow dots = photos – click to view.
＋ Mehrtagestour bilden …|＋ Create multi-day tour …
Mehrtagestour bilden|Create multi-day tour
✎ Reihe umbenennen|✎ Rename series
Mehrtagestour umbenennen|Rename multi-day tour
Benennen|Name
Bitte einen Namen eingeben und mindestens zwei Touren wählen.|Please enter a name and choose at least two tours.
Keine Touren in diesem Zeitraum.|No tours in this period.
Wunschliste|Wish list
Zur Wunschliste|Add to wish list
Noch keine Touren vorgemerkt.|No tours saved yet.
Von der Wunschliste entfernen|Remove from wish list
Offline-Nutzung|Offline use
Für Offline vorbereiten|Prepare for offline use
Offline – es werden die zuletzt geladenen Daten gezeigt (Änderungen sind nicht möglich).|Offline – showing the most recently loaded data (changes are not possible).
Ausgewählte Touren übernehmen|Import selected tours
Bitte Touren ankreuzen.|Please tick tours.
✓ übernommen|✓ imported
Wird übernommen …|Importing …
Ziel erreicht ✓|Goal reached ✓
noch kein Fortschritt – Ziel wird so verfehlt|no progress yet – goal will be missed
Kamerauhr|Camera clock
Wird geprüft …|Checking …
Ignorieren|Ignore
✓ Die Kamerauhr passt zu den Strecken der letzten Touren.|✓ The camera clock matches the tracks of the latest tours.
Bei diesen Touren passen die Foto-Zeiten nicht zum Aufnahmeort (Kamerauhr falsch gestellt, z. B. Zeitzone der Reise). Mit „Korrigieren“ werden die Fotos um den Unterschied verschoben und der Tour zugeordnet.|For these tours the photo times do not match where they were taken (camera clock wrong, e.g. the trip’s time zone). “Fix” shifts the photos by the difference and assigns them to the tour.
⭐ Beste Fotos|⭐ Best photos
Alle Fotos zeigen|Show all photos
Diashow der besten|Slideshow of the best
Wird ausgewählt …|Selecting …
Wählt aus den Fotos der Tour die besten aus: Sterne aus Lightroom (XMP), unscharfe und abgelehnte Fotos fallen heraus, verteilt über die ganze Tour|Picks the best photos of the tour: Lightroom stars (XMP), blurry and rejected photos are dropped, spread over the whole tour`;
  ((lang === "en" ? EN : (window.I18N || {})[lang]) || "").split("\n").forEach(l => { const i = l.indexOf("|"); if (i > 0) D[l.slice(0, i)] = l.slice(i + 1); });

  const decode = s => s.replace(/&amp;/g, "&");
  const MO = "Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember";
  const dt = (d, mo, y) => (lang === "en" ? `${D[mo] || mo} ${d}, ${y}` : lang === "fr" ? `${d === "1" ? "1er" : d} ${D[mo] || mo} ${y}` : `${d} de ${D[mo] || mo} de ${y}`);
  const pl = (n, one, many) => (n === "1" ? one : many);
  const U = {   // Einheiten und Satzteile je Sprache
    en: {photo: ["photo", "photos"], tour: ["tour", "tours"], day: ["day", "days"], of: "of", img: "images", asg: "assigned to a tour", lib: "in the library", libc: "Library:", free: "free", adm: "Admin → ", open: "Open admin", asgp: "Assign photos", show: "Slideshow", act: "activities", Tours: "Tours", Photos: "Photos", miss: "missing – ", none: "none yet – ", latest: "latest version on GitHub", ltour: "Latest tour", lh: "Latest tour, hiking", lc: "Latest tour, cycling", yr: "Year in review", stg: ["stage", "stages"], fast: ["section with vehicle pace (cable car, bus, car?)", "sections with vehicle pace (cable car, bus, car?)"], tfast: "too fast for hiking", nobk: "There is no backup yet – the first one is created automatically (at night), or right now:"},
    fr: {photo: ["photo", "photos"], tour: ["parcours", "parcours"], day: ["jour", "jours"], of: "sur", img: "images", asg: "associées à un parcours", lib: "dans la bibliothèque", libc: "Bibliothèque :", free: "libres", adm: "Administration → ", open: "Ouvrir l’administration", asgp: "Associer les photos", show: "Diaporama", act: "activités", Tours: "Parcours", Photos: "Photos", miss: "manquant – ", none: "aucune pour l’instant – ", latest: "dernière version sur GitHub", ltour: "Dernier parcours", lh: "Dernier parcours, randonnée", lc: "Dernier parcours, vélo", yr: "Bilan de l’année", stg: ["étape", "étapes"], fast: ["section à allure de véhicule (téléphérique, bus, voiture ?)", "sections à allure de véhicule (téléphérique, bus, voiture ?)"], tfast: "trop rapide pour la randonnée", nobk: "Il n’y a pas encore de sauvegarde – la première est créée automatiquement (la nuit), ou tout de suite :"},
    es: {photo: ["foto", "fotos"], tour: ["ruta", "rutas"], day: ["día", "días"], of: "de", img: "imágenes", asg: "asignadas a una ruta", lib: "en la biblioteca", libc: "Biblioteca:", free: "libres", adm: "Administración → ", open: "Abrir administración", asgp: "Asignar fotos", show: "Presentación", act: "actividades", Tours: "Rutas", Photos: "Fotos", miss: "falta – ", none: "ninguna aún – ", latest: "última versión en GitHub", ltour: "Última ruta", lh: "Última ruta, senderismo", lc: "Última ruta, ciclismo", yr: "Resumen del año", stg: ["etapa", "etapas"], fast: ["tramo a ritmo de vehículo (¿teleférico, autobús, coche?)", "tramos a ritmo de vehículo (¿teleférico, autobús, coche?)"], tfast: "demasiado rápido para senderismo", nobk: "Aún no hay copia de seguridad – la primera se crea automáticamente (por la noche), o ahora mismo:"},
  }[lang];
  const P = [   // dynamische Texte (ganzer Textknoten)
    [/^(\d+) Fotos?$/, (m, n) => `${n} ${pl(n, U.photo[0], U.photo[1])}`],
    [/^(\d+) Touren?$/, (m, n) => `${n} ${pl(n, U.tour[0], U.tour[1])}`],
    [/^(\d+) Tage?$/, (m, n) => `${n} ${pl(n, U.day[0], U.day[1])}`],
    [new RegExp(`^(\\d+)\\. (${MO}) (\\d{4})$`), (m, d, mo, y) => dt(d, mo, y)],
    [/^(.*), (\d+) Fotos$/, (m, a2, n) => `${a2}, ${n} ${pl(n, U.photo[0], U.photo[1])}`],
    [/^(\d+) von (\d+)$/, (m, a2, b2) => `${a2} ${U.of} ${b2}`],
    [/^(\d+(?:[.,]\d+)?) Uhr$/, (m, t) => t],
  ];
  const S = [   // Ersetzungen innerhalb längerer Texte
    [new RegExp(`(\\d+)\\. (${MO}) (\\d{4})`, "g"), (m, d, mo, y) => dt(d, mo, y)],
    [/(\d+) Bilder, (\d+) einer Tour zugeordnet/g, (m, a2, b2) => `${a2} ${U.img}, ${b2} ${U.asg}`],
    [/Es gibt noch kein Backup – das erste wird automatisch angelegt \(nachts\), oder jetzt sofort:/g, () => U.nobk],
    [/Letzte Tour, Wandern/g, () => U.lh],
    [/Letzte Tour, Radtour/g, () => U.lc],
    [/Letzte Tour/g, () => U.ltour],
    [/Jahresrückblick (\d{4})/g, (m, y) => `${U.yr} ${y}`],
    [/ Uhr\b/g, ""],
    [/(\d+) Fotos in der Bibliothek, (\d+) einer Tour zugeordnet/g, (m, a2, b2) => `${a2} ${U.photo[1]} ${U.lib}, ${b2} ${U.asg}`],
    [/(\d+) von (\d+)/g, (m, a2, b2) => `${a2} ${U.of} ${b2}`],
    [/ in der Bibliothek/g, () => " " + U.lib],
    [/neueste Version auf GitHub/g, () => U.latest],
    [/Bibliothek:/g, () => U.libc],
    [/(\d+(?:[.,]\d+)?) GB frei/g, (m, g) => `${g} GB ${U.free}`],
    [/Verwaltung → /g, () => U.adm],
    [/fehlt – /g, () => U.miss],
    [/noch keines – /g, () => U.none],
    [/Verwaltung öffnen/g, () => U.open],
    [/Fotos zuordnen/g, () => U.asgp],
    [/Diashow (\d{4})/g, (m, y) => `${U.show} ${y}`],
    [/(\d+) Fotos/g, (m, n) => `${n} ${pl(n, U.photo[0], U.photo[1])}`],
    [/(\d+) Touren/g, (m, n) => `${n} ${pl(n, U.tour[0], U.tour[1])}`],
    [/(\d+) Aktivitäten/g, (m, n) => `${n} ${U.act}`],
    [/(\d+) Etappen/g, (m, n) => `${n} ${pl(n, U.stg[0], U.stg[1])}`],
    [/(\d+) Abschnitte?  ?mit Fahrt-Tempo \(Seilbahn, Bus, Auto\?\)/g, (m, n) => `${n} ${pl(n, U.fast[0], U.fast[1])}`],
    [/zu schnell für Wandern/g, () => U.tfast],
    [/\bTouren\b/g, () => U.Tours],
    [/\bFotos\b/g, () => U.Photos],
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
  const LOC = {en: ["en-GB", "en-US"], fr: ["fr-FR", "fr-FR"], es: ["es-ES", "es-ES"]}[lang];
  const loc = a => (a === "de-DE" || a === "de" || a === undefined ? LOC[0] : a);
  ["toLocaleString", "toLocaleDateString", "toLocaleTimeString"].forEach(k => {
    const o = Date.prototype[k];
    Date.prototype[k] = function (a, b) { return o.call(this, loc(a), b); };
  });
  const on = Number.prototype.toLocaleString;
  Number.prototype.toLocaleString = function (a, b) { return on.call(this, a === "de-DE" ? LOC[1] : a, b); };

  // Meldungsfenster
  const al = window.alert, cf = window.confirm, pr = window.prompt;
  window.alert = m => al(tr(String(m)));
  window.confirm = m => cf(tr(String(m)));
  window.prompt = (m, d) => pr(tr(String(m)), d);
})();
