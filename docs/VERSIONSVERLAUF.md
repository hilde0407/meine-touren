# Versionsverlauf

Alle Versionen von **neu nach alt**, nach Versionsnummer sortiert (nicht alphabetisch). Ausführliche Beschreibungen der Versionen ab 3.7.2 stehen in [docs/versionen/](versionen/README.md); die Einträge hier fassen kurz zusammen. Ältere Versionen sind hier ausführlicher beschrieben. Aktuelle Übersicht in der [README](../README.md).

## Version 3.38.0 – Sicher planen

- Sicherung robust: Platzprüfung, `.part`-Datei, ZIP- und Datenbankprüfung, atomares Umbenennen; Fehler sichtbar, gute Sicherungen bleiben; eine Warnschwelle (36 h); Fehler der Sicherung vor dem Update werden gemeldet.
- Verwaltung: Knopf „Letzte Sicherung prüfen“ (Probelauf im Temp-Ordner, Zahlen, Ergebnis gemerkt) und ehrlicher Hinweis, was nicht in der Sicherung ist.
- Planseite: Machbarkeits-Check gegen die eigenen Touren der letzten 12 Monate (drei Stufen mit Symbol, konkrete Zahlen, Gesamtzeit und reine Gehzeit beschriftet), aria-Beschriftungen.
- Pläne mit gelaufener Tour verknüpfen (Status, Vorschlag ab 80 % Überdeckung zum Bestätigen, Soll/Ist in der Planliste).

Einzelheiten: [docs/versionen/3.38.0.md](versionen/3.38.0.md)

## Version 3.37.2 – Zeitraum der Seite standardmäßig ausgeblendet, mit Erklärung

- Die Leiste „Zeitraum der Seite“ der Übersicht ist standardmäßig aus (Bausteine nutzen ihren eigenen Zeitraum); Schalter „Zeitraum der Seite anzeigen“ in „Seite anpassen“, je Ansicht gespeichert (Layout-Feld `zrbar`).
- Ein wirksamer Seitenzeitraum (Adresse `?z=…`, zuletzt gewählt, in der Ansicht gespeichert) blendet die Leiste immer ein.
- Erklärung in der App: „Was ist das?“ beim Schalter, „Hilfe“ in der Leiste, „Gerade gilt: …“ in den Baustein-Einstellungen; Handbuch ergänzt.

Einzelheiten: [docs/versionen/3.37.2.md](versionen/3.37.2.md)

## Version 3.37.1 – Mobilansicht: schlanke Werkzeugzeile, ruhige Karte

- Karte (Handy): Die Bedienfelder wurden nach dem Laden höher (Reihe von 54 auf 110 px), weil „Seite anpassen / Ansichten“ erst spät als zweizeiliger Kasten in die Reihe kam. Jetzt ein einzeiliger Kasten, kein Höhensprung mehr.
- Übersicht (Handy): eine Werkzeugzeile (Seite anpassen, Ansichten als Menü, Zeitraum als Chip „Zeitraum: 2025“ mit aufklappender Auswahl) statt rund 440 px hoher Zeilen; Tastatur und Sprachausgabe (aria-expanded, aria-controls, Escape).
- Andere Seiten mit Seitenanpassung: dieselbe einzeilige Werkzeugzeile. Desktop unverändert.

Einzelheiten: [docs/versionen/3.37.1.md](versionen/3.37.1.md)

## Version 3.37.0 – Neue Bausteine

- Lückenprüfung zuerst: „Heute vor X Jahren“ gab es schon (Baustein „heutevor“), „Belastung und Erholung“ und „Ausrüstung“ waren großteils vorhanden; gebaut wurden nur die echten Lücken.
- Neu: Baustein „Jahreszeiten und Wetter“ (Touren und Kilometer je Jahreszeit und Monat; Temperaturen nur aus lokal gespeicherten Wetterdaten, sonst ehrlicher Hinweis, nie ein Abruf).
- „Belastung und Erholung“: Wochenansicht (8 oder 12 Wochen) mit Belastung laut Uhr, Touren, Kilometern und Ruhetagen; „ohne Angabe“ zählt nie als 0.
- „Ausrüstung“: Prozent des Limits, Warnsymbole (! ab 90 %, × ab 100 %) zusätzlich zur Farbe, Warnungen zuerst.

Einzelheiten: [docs/versionen/3.37.0.md](versionen/3.37.0.md)

## Version 3.36.0 – Bedienung der Seitenanpassung

- Bausteine duplizieren (Kopie mit denselben Einstellungen direkt dahinter, nur bei mehrfach nutzbaren Bausteinen).
- Rückgängig und Wiederholen im Bearbeitungsmodus (Knöpfe, Strg/Cmd+Z, bis 50 Schritte, mit Ansage für Vorlesehilfen).
- Gruppen: mehrere Bausteine zu einem einklappbaren Abschnitt bündeln (Titel frei, Zustand je Benutzer gemerkt); Vorlage „Mit Gruppe“.
- Eigene Handy-Anordnung (Umschalter „Desktop | Handy“ mit Vorschau im schmalen Rahmen); ohne sie gilt die Desktop-Reihenfolge.
- Ansichten teilen per Layoutcode oder Link (nur Layout und Einstellungen, serverseitig geprüft); Server prüft Gruppen und Handy-Anordnung streng, alte Layouts bleiben gültig.

Einzelheiten: [docs/versionen/3.36.0.md](versionen/3.36.0.md)

## Version 3.35.0 – Eigene Kennzahlen weiterentwickeln

- Ziel mit barrierefreiem Fortschrittsbalken, Rest bis zum Ziel und „Im Plan?“ (gleichmäßiges Soll, nur als Text und Marke, ohne Warnfarbe).
- Trendpfeil ↑ ↓ → mit Prozent und Differenz, neutral; Vergleich wählbar mit Zeitraum davor, Vorjahr oder Vormonat.
- Sparkline als SVG-Linie (Wochen-, Monats- oder Jahreswerte vom Server, begrenzt), Säulen oder aus.
- Antippen öffnet die zugehörigen Touren mit den Filtern der Kennzahl (bei Rekorden die Rekordtour); Hinweis, wenn ein Filter nicht genau abbildbar ist.
- Dialog mit einklappbaren Gruppen Ziel, Vergleich, Verlauf, Antippen; Server prüft die neuen Felder streng.

Einzelheiten: [docs/versionen/3.35.0.md](versionen/3.35.0.md)

## Version 3.34.0 – Fotos und Karte anpassbar, Galerie mit Vorschau, Zeitraum der Seite

- Fotos-Seite und Karte bestehen aus Bausteinen (verschieben, ausblenden, einklappen, Breite); die Karte bleibt Hauptbaustein, ihre Bedienfelder sind einzeln anpassbar. Neue Bausteine: Foto-Kennzahlen, Fotos je Jahr, Karten-Kennzahlen, Touren im Kartenausschnitt, Legende; sechs neue Vorlagen.
- „Baustein hinzufügen“ zeigt Live-Vorschauen mit den echten Daten (lazy, nicht bedienbar, mit Rückfall auf Beispielwerte), Hinweis „Bereits auf dieser Seite“.
- Zeitraum der Seite: eine Leiste (Alle, Dieses Jahr, Letzte 12 Monate, Vorjahr, Jahr, Von–bis) für alle zeitbezogenen Bausteine der Übersicht, je Baustein überschreibbar, per Adresse teilbar; Statistik mit neuem Knopf „Vorjahr“.
- Behoben: „Alben & Tags“ auf der Reisen-Übersicht.

Einzelheiten: [docs/versionen/3.34.0.md](versionen/3.34.0.md)

## Version 3.33.0 – Reisen als anpassbare Seiten

- Reise-Seite und Reisen-Übersicht bestehen aus Bausteinen: verschieben, ausblenden, einklappen, Breite wählen; ein Layout für alle Reisen, je Benutzer gespeichert.
- Neue Bausteine: Reise-Kennzahlen, Kilometer je Tag, Reise-Diashow, Reisen-Kennzahlen, Reisen je Jahr.
- Ansichten, fünf neue Vorlagen, Export und Import wie bei den anderen anpassbaren Seiten.

Einzelheiten: [docs/versionen/3.33.0.md](versionen/3.33.0.md)

## Version 3.32.0 – Erinnerungen-Kachel einstellbar

- Die Kachel „Erinnerungen“ auf der Übersicht ist einstellbar und in der Größe änderbar.

Einzelheiten: [docs/versionen/3.32.0.md](versionen/3.32.0.md)

## Version 3.31.1 – Diashow-Link mit Tourname

- Der Tourname steht bei jedem Foto der geteilten Diashow, auch ohne Konto; beim Teilen erscheint ein Datenschutz-Hinweis.
- Ältere Links funktionieren unverändert, bekommen die Namen aber nicht nachträglich.

Einzelheiten: [docs/versionen/3.31.1.md](versionen/3.31.1.md)

## Version 3.31.0 – Import-Knopf je nach Uhr

- Beschriftung und Funktion des Import-Knopfs richten sich nach den verbundenen Konten (Zepp, Garmin, Suunto).
- Der Schnell-Knopf in der Kopfzeile ist abschaltbar; neuer Baustein „Touren-Knopf“ für das Raster.
- Suche ohne Akzente und Apostrophe: „reunion“ findet „Réunion“, „strasse“ findet „Straße“.

Einzelheiten: [docs/versionen/3.31.0.md](versionen/3.31.0.md)

## Version 3.30.0 – Zepp-Import auf der Übersicht

- Großer Import-Knopf als Baustein und Schnell-Knopf „⟳ Zepp“ in der Kopfzeile, auf dem Handy ohne Scrollen erreichbar.

Einzelheiten: [docs/versionen/3.30.0.md](versionen/3.30.0.md)

## Version 3.29.0 – Diashow-Link für Jahr und Sammlung, Baustein „Ziele“

- Diashow-Link für ein Jahr oder eine Sammlung; Baustein „Ziele“ auf der Übersicht.
- Puls und Gehzeit für eigene Kennzahlen; kompakterer Bausteinkopf im Bearbeitungsmodus; robustere Browser-Tests.

Einzelheiten: [docs/versionen/3.29.0.md](versionen/3.29.0.md)

## Version 3.28.0 – Eigene Kennzahlen

- Eine eigene Kennzahl ohne Programmierung zusammenstellen: „Seite anpassen“ → „Baustein hinzufügen“ → Eigene Kennzahlen → „Erstellen“ (Übersicht und Statistik).

Einzelheiten: [docs/versionen/3.28.0.md](versionen/3.28.0.md)

## Version 3.27.0 – Geschwindigkeit bei vielen Touren, Vollbild in der Android-App

- Gemessen mit 800 synthetischen Touren: Seiten bauen sich deutlich schneller auf (z. B. Übersicht beim zweiten Aufruf 1223 → 481 ms).
- Die Android-App zeigt Vollbild aus der Seite (z. B. Diashow und Video) wieder an.

Einzelheiten: [docs/versionen/3.27.0.md](versionen/3.27.0.md)

## Version 3.26.0 – Jahresrückblick als teilbare Seite

- Der Jahresrückblick wird zu einem Link, der ohne Konto geöffnet und sauber als PDF gedruckt werden kann.
- Was gezeigt wird, wählst du vorher; der Server liefert nur Gewähltes aus.

Einzelheiten: [docs/versionen/3.26.0.md](versionen/3.26.0.md)

## Version 3.25.0 – Teilen mit Ansicht

- Ein Freigabelink zeigt die Tour in einer gewählten Ansicht (z. B. nur Karte und Fotos, ohne Puls, Notizen oder Wetter).
- Die Auswahl gilt serverseitig: Nicht Gewähltes verlässt den Server nicht.

Einzelheiten: [docs/versionen/3.25.0.md](versionen/3.25.0.md)

## Version 3.24.1 – Zwei Fehler behoben

- Dauer „2:60 Std.“ statt „3:00 Std.“ korrigiert.
- Herzfrequenz stand bei einer älteren gespeicherten Reihenfolge hinter Fotos und Einstieg.

Einzelheiten: [docs/versionen/3.24.1.md](versionen/3.24.1.md)

## Version 3.24.0 – Qualität und Feinschliff

- Keine neuen großen Funktionen: Härtung, bessere Auffindbarkeit und ruhigeres Bearbeiten auf kleinen Schirmen.

Einzelheiten: [docs/versionen/3.24.0.md](versionen/3.24.0.md)

## Version 3.23.0 – Hinweis-Bausteine

- Bausteine, die sich nur zeigen, wenn es einen Anlass gibt; sonst belegen sie keinen Platz. Im Bearbeitungsmodus steht ein gestrichelter Platzhalter.

Einzelheiten: [docs/versionen/3.23.0.md](versionen/3.23.0.md)

## Version 3.22.0 – Statistik als anpassbare Seite

- Die Statistikseite lässt sich wie Tourseite und Übersicht gestalten (Bausteine, Ansichten, Vorlagen, Export/Import).
- Globaler Filter oben (Aktivität und Zeitraum) für alle Bausteine.

Einzelheiten: [docs/versionen/3.22.0.md](versionen/3.22.0.md)

## Version 3.21.0 – Ansichten, Vorlagen, Export

- Jede anpassbare Seite kann mehrere benannte Ansichten haben (z. B. „Wandern“, „Rad“, „Kompakt“).
- Fertige Vorlagen; eine Ansicht lässt sich als Datei sichern und auf ein anderes Gerät oder Konto übertragen.

Einzelheiten: [docs/versionen/3.21.0.md](versionen/3.21.0.md)

## Version 3.20.0 – Raster und seitenübergreifende Bausteine

- Auf breiten Bildschirmen stehen kleine Abschnitte nebeneinander.
- Bausteine sind nicht mehr an eine Seite gebunden, z. B. „Dein Jahr“ auch auf der Tourseite.

Einzelheiten: [docs/versionen/3.20.0.md](versionen/3.20.0.md)

## Version 3.19.0 – Konfigurierbare Bausteine

- Bausteine der Übersicht lassen sich nach Aktivität, Zeitraum, Kennzahlen und Titel einstellen.
- „Dein Jahr“ ist ein richtiger Baustein, den man mehrfach mit verschiedenen Filtern hinzufügen kann.

Einzelheiten: [docs/versionen/3.19.0.md](versionen/3.19.0.md)

## Version 3.18.0 – Mehr Bausteine

- 24 neue Bausteine (12 für die Tourseite, 12 für die Übersicht), im Katalog mit Kategorien und Suche.

Einzelheiten: [docs/versionen/3.18.0.md](versionen/3.18.0.md)

## Version 3.17.0 – Seite anpassen und Bausteine

- Tourseite und Übersicht selbst zusammenstellen: Abschnitte ziehen, ausblenden, auf- oder zuklappen, auf die andere Seite legen.
- Fertige Bausteine aus einem Katalog hinzufügen; ohne Anpassung bleibt alles wie bisher.

Einzelheiten: [docs/versionen/3.17.0.md](versionen/3.17.0.md)

## Version 3.16.1 – Fehlerkorrektur Genauigkeitseinschätzung

- Touren, die nur wegen Lücken oder Pausen auffallen, bleiben nicht mehr dauerhaft in „Auffällige Touren“: Sie lassen sich als geprüft markieren (und wieder zurücknehmen).

Einzelheiten: [docs/versionen/3.16.1.md](versionen/3.16.1.md)

## Version 3.16.0 – Tourseite schlanker

- Die Tourseite zeigt nur noch die Strecke; die ausführliche Auswertung steht auf einer eigenen Unterseite. Keine Daten gehen verloren.

Einzelheiten: [docs/versionen/3.16.0.md](versionen/3.16.0.md)

## Version 3.15.0 – Neue Tourseite

- Neu gegliederte Tourseite mit klaren Gruppen, einheitlichen einklappbaren Abschnitten und einer Sprung-Leiste.

Einzelheiten: [docs/versionen/3.15.0.md](versionen/3.15.0.md)

## Version 3.14.0 – Ähnliche Touren im Vergleich

- Neuer einklappbarer Abschnitt auf der Tourseite: dieselbe Strecke früher und später im Vergleich.

Einzelheiten: [docs/versionen/3.14.0.md](versionen/3.14.0.md)

## Version 3.13.0 – Genauigkeit der Uhren: Sammel-Korrektur

- Schneller und übersichtlicher; Sammel-Korrektur, jede Änderung nur nach deiner Bestätigung und rücknehmbar.

Einzelheiten: [docs/versionen/3.13.0.md](versionen/3.13.0.md)

## Version 3.12.0 – Belastung, Ermüdung, Tempo nach Steigung

- Neue Abschnitte, berechnet nur aus vorhandenen Daten; fehlt etwas, erscheint der Abschnitt nicht.

Einzelheiten: [docs/versionen/3.12.0.md](versionen/3.12.0.md)

## Version 3.11.0 – „Training laut Uhr“

- Neuer Abschnitt auf der Tourseite für Touren, die mit einer Zepp-Uhr aufgezeichnet wurden: nur, was die Uhr glaubwürdig geliefert hat.

Einzelheiten: [docs/versionen/3.11.0.md](versionen/3.11.0.md)

## Version 3.10.1 – „Was liefert diese Uhr?“

- Diagnose, welche Daten eine Uhr wirklich liefert und welche die App noch nicht nutzt; nur lesend.

Einzelheiten: [docs/versionen/3.10.1.md](versionen/3.10.1.md)

## Version 3.10.0 – „Genauigkeit“ je Uhr

- Unter Meine Geräte zeigt jede Geräte-Karte, was die Uhr liefert und wie genau sie misst; nur lesend.

Einzelheiten: [docs/versionen/3.10.0.md](versionen/3.10.0.md)

## Version 3.9.7 – Handzuordnungen aufräumen

- „Auf automatisch umstellen“ und „Alle Handzuordnungen zurücksetzen“ unter Meine Geräte.

Einzelheiten: [docs/versionen/3.9.7.md](versionen/3.9.7.md)

## Version 3.9.6 – Falsche Handzuordnungen erkennen

- Hinweis bei Zuordnungen, die dem Zeitraum ihres Geräts widersprechen, mit „Zurücksetzen“.

Einzelheiten: [docs/versionen/3.9.6.md](versionen/3.9.6.md)

## Version 3.9.5 – Zuordnung zu Uhren findet mehr Touren

- Auch Touren mit leicht abweichenden Zeiten werden erkannt (Überlappung mindestens 60 %, Länge ±35 %).

Einzelheiten: [docs/versionen/3.9.5.md](versionen/3.9.5.md)

## Version 3.9.4 – „Unbekanntes Gerät“ behoben

- Touren aus Komoot oder Dateien, die mit der Uhr aufgezeichnet wurden, erhalten das passende Gerät.

Einzelheiten: [docs/versionen/3.9.4.md](versionen/3.9.4.md)

## Version 3.9.3 – Ältere Amazfit-Uhren

- Modellvorschlag „Vermutlich …“ für Uhren vor Zepp OS (z. B. Amazfit Stratos, Verge, Pace).

Einzelheiten: [docs/versionen/3.9.3.md](versionen/3.9.3.md)

## Version 3.9.2 – Zepp-Uhren automatisch erkannt

- „Geräte aus Zepp ermitteln“ schlägt den echten Modellnamen aus der offiziellen Zepp-Geräteliste vor.

Einzelheiten: [docs/versionen/3.9.2.md](versionen/3.9.2.md)

## Version 3.9.1 – „Meine Geräte“ überarbeitet

- **Neue Oberfläche:** je Gerät eine Karte (Bild oder Symbol, Name, Art/Modell, Zeitraum „seit 03/2024 · aktuell“, Anzahl Touren, Status), Aktionen im Menü „⋮“, Anlegen/Bearbeiten und „Touren zuordnen“ in eigenen Dialogen mit Hilfetexten.
- **Gerätefoto:** eigenes Foto je Gerät (wird auf 512 px verkleinert, liegt in `<Datenordner>/devices/<id>.jpg`, in Sicherung und Umzugspaket enthalten). Schnittstelle: `POST/GET/DELETE /api/my-devices/{id}/photo`. Es werden keine Produktfotos aus dem Internet geladen.
- **Geräte aus Zepp ermitteln:** `POST /api/devices/zepp-probe` liest den Zepp-Verlauf und gruppiert nach der Quellenkennung (`source`); `POST /api/devices/zepp-apply` legt die bestätigten Geräte an. Die Kennung wird am Gerät gespeichert (Spalte `devices.zsrc`) und bevorzugt bei der Zuordnung.

Einzelheiten: [docs/versionen/3.9.1.md](versionen/3.9.1.md)

## Version 3.9.0 – Messwerte der Geräte und „Meine Geräte“

- **Messwerte:** Die Tourseite zeigt – zusätzlich zu Puls und Höhe – Geschwindigkeit/Pace, Schritt- oder Trittfrequenz, Schrittlänge, Leistung, Temperatur, Atemfrequenz, Bodenkontaktzeit, vertikale Oszillation und Luftdruck, Kalorien und Trainingseffekt. **Nur, was das Gerät wirklich geliefert hat** (FIT, GPX, TCX, Zepp); die Geschwindigkeit wird sonst aus GPS und Zeit berechnet und als „berechnet“ gekennzeichnet. Ablage je Tour in `tracks/<id>.met.json` (höchstens 600 Stützstellen), enthalten in Sicherung und Umzugspaket. Bestand: Verwaltung → Zepp-Import → „Messwerte nachladen“. Schnittstelle: `GET /api/tours/{id}/metrics`.
- **Meine Geräte** (Verwaltung → „Touren holen“): Aufnahmegeräte selbst anlegen und benennen, mit Art, Modell und Zeitraum. Die Zuordnung der Touren geschieht automatisch nach Art der Quelle und Datum (neue Uhr = altes Gerät „bis“, neues „ab“), je Tour oder für einen Zeitraum von Hand änderbar. Schnittstelle: `/api/my-devices`, `POST /api/devices`, `PATCH/DELETE /api/devices/{id}`, `POST /api/tours/{id}/device`.

Einzelheiten: [docs/versionen/3.9.0.md](versionen/3.9.0.md)

## Version 3.8.0 – Freigegebene Links

- Ein Platz für alle Tour- und Diashow-Links („Freigegebene Links verwalten“).

Einzelheiten: [docs/versionen/3.8.0.md](versionen/3.8.0.md)

## Version 3.7.8 – Höhe aus der Uhr abgleichen

- Der Höhenverlauf einer Uhr mit Luftdruck-Sensor (z. B. Amazfit Balance 2) kann die GPS-/Komoot-Höhe ersetzen.

Einzelheiten: [docs/versionen/3.7.8.md](versionen/3.7.8.md)

## Version 3.7.7 – Fehlerbehebungen und Härtung

- Nach einer Durchsicht des Programmcodes.

Einzelheiten: [docs/versionen/3.7.7.md](versionen/3.7.7.md)

## Version 3.7.6 – Tour löschen überall

- „Tour löschen“ gibt es auf jeder Tourseite, auch bei Komoot-Touren (nur hier oder auch bei Komoot).

Einzelheiten: [docs/versionen/3.7.6.md](versionen/3.7.6.md)

## Version 3.7.5 – 3D-Flug: Bedienelemente blenden aus

- Die Bedienelemente blenden sich beim Abspielen aus; ein Tipp auf die Karte bringt sie zurück.

Einzelheiten: [docs/versionen/3.7.5.md](versionen/3.7.5.md)

## Version 3.7.4 – 3D-Video ohne weiße Flächen

- Vor der Aufnahme lädt ein Schnelldurchlauf alle Kartenkacheln und Höhendaten vor.

Einzelheiten: [docs/versionen/3.7.4.md](versionen/3.7.4.md)

## Version 3.7.3 – 3D-Flug: Foto oben links

- Das beim Vorbeifliegen eingeblendete Foto steht oben links unter der Titelleiste.

Einzelheiten: [docs/versionen/3.7.3.md](versionen/3.7.3.md)

## Version 3.7.2 – Nebenseiten geschützt, Liniensymbole

- Freigabe-Seite, Diashow und Passwort-Zurücksetzen laufen unter der Content-Security-Policy.
- Liniensymbole statt Emojis; bessere Lesbarkeit im Dunkelmodus.

Einzelheiten: [docs/versionen/3.7.2.md](versionen/3.7.2.md)

## Version 3.7.0 – neue Startseite

- **Startseite:** Aufmacher „Zuletzt unterwegs“ mit Foto oder Streckenform, Wegweiser-Zahlen, Puls-Hinweis und Blättern durch die letzten Touren; „Dein Jahr“ mit Vergleich zum Vorjahr bis zum heutigen Tag, Monatsbalken und Zielen; die letzten Touren als Karten; „An diesem Tag“ und Erinnerungen.
- **Statistik → Übersicht:** Die bisherige Übersicht (alle Zahlen, Jahre, Sportarten, Ziele, Diagramme, Bestwerte) ist jetzt der erste Reiter der Statistik.

## Version 3.6.0 – neues Erscheinungsbild, aufgeräumtes Menü, Entwicklermodus

- **Menü:** sechs Hauptpunkte (Übersicht, Karte, Touren, Reisen, Fotos, Statistik). „Statistik“ fasst Auswertung und Rekorde zusammen (oben umschaltbar). Die Verwaltung liegt hinter dem Zahnrad rechts oben; „Prüfen & Aufräumen“ ist ein Reiter der Verwaltung.
- **Erscheinungsbild:** Abschnitte als ruhige Flächen statt Linien, einheitliche Knöpfe und Eingaben, Gelb nur noch für die Hauptaktion und die Wegweiser; gezeichnete Symbole statt Emojis in der Handy-Leiste und im Tour-Menü. Der Backup-Hinweis erscheint nur noch auf der Startseite und in der Verwaltung.
- **Entwicklermodus:** Selbsttest, App-Test, die Suche nach verlorenen Aufzeichnungen und der Token-Test sind ausgeblendet; das Protokoll zeigt nur die letzten Zeilen. Einschalten: Verwaltung → Übersicht → „Entwickleransichten anzeigen“ (gilt pro Browser).

## Version 3.5.1 – Pulskurve geglättet, Stile aufgeräumt

- **Pulskurve:** geglättet (gleitender Mittelwert); Messlücken (Pausen) erscheinen als weicher, gestrichelter Übergang statt als harte Gerade. Kennzahlen und Zonen rechnen weiter mit den Rohwerten.
- **Stile:** Rund 600 Inline-Stilangaben in den Vorlagen sind durch Hilfsklassen ersetzt (pixelgleich, per Bildvergleich über 59 Ansichten geprüft). Schriftgrößen folgen einer festen Skala (12–44 px); ein Test verhindert Abweichungen.

## Version 3.5.0 – Aufräumen und Absichern

- **Puls vollständig:** Backup enthält die Pulsdateien, Betrachter-Konten sehen die Pulskarte, die Spur-Korrektur behält den Puls, der GPX-Export enthält Zeit und Puls. Maximalpuls einstellbar (Verwaltung → „Heimatort und Puls“).
- **Schutz-Header:** `nosniff`, Schutz vor Einbettung, Referrer-Policy für alle Antworten; für die Hauptoberfläche eine Content-Security-Policy ohne Inline-JavaScript.
- **Einheitliche Oberfläche:** Gleiche Abstände zwischen Abschnitten, ein Einzug für Überschrift und Inhalt auf dem Handy, gleich hohe Eingaben und Knöpfe, Verwaltungs-Reiter zum Wischen, vollständige Menüleiste auch auf schmaleren Bildschirmen; die Einrichtungs- und Fehlerseite der Android-App im selben Erscheinungsbild.
- **Test-Image:** Ein manuell gestarteter Docker-Build erzeugt nur noch den Tag `test` (`ghcr.io/hilde0407/meine-touren:test`); `latest` ändert sich erst mit einer veröffentlichten Version.

## Version 3.4.6 – Puls aus FIT-Dateien

Der FIT-Import (Garmin, Suunto, Wahoo u. a., auch über das Garmin-Konto) übernimmt jetzt die Herzfrequenz. Bereits importierte Touren bekommen sie nicht nachträglich; Dateien erneut zu importieren, wird als Duplikat übersprungen (die Tour vorher löschen, wenn der Puls gewünscht ist).

## Version 3.4.0 – Puls und bessere 3D-Kamera

- **Herzfrequenz direkt von der Uhr:** Der Zepp-Import (Verwaltung → Import) übernimmt jetzt auch den Puls und speichert ihn im GPX (`gpxtpx:hr`). GPX/TCX-Dateien mit Puls (z. B. aus Gadgetbridge) werden ebenfalls verstanden. Weder Komoot noch Strava werden benötigt.
- **Pulskarte in der Tourseite:** Verlauf, Ø/Max/Min und Zeit in fünf Pulszonen. Maximalpuls standardmäßig 185 bpm (Einstellung `hr_max`) oder der höchste gemessene Wert. Bereits importierte Touren: Verwaltung → Zepp-Import → „Puls nachladen“ ergänzt den Puls nachträglich (Touren, Notizen und Fotos bleiben unverändert). Auch „Zepp-Import starten“ gleicht jetzt ab: Für jedes Zepp-Training, zu dem es schon eine Tour gibt (gleicher Start oder gleiche Strecke – auch aus Komoot oder GPX-Dateien), wird der Puls ergänzt.
- **3D-Flug:** Im Modus „Kamera folgt“ weicht die Neigung Bergen automatisch aus (Auswahl „Neigung: automatisch“; feste Werte bleiben möglich). Der Reiseflug („3D-Flug über alles“) fliegt die Touren nacheinander ab: zwischen zwei Touren steigt die Kamera auf, überfliegt die Lücke mit sanft an- und abschwellendem Tempo und sinkt über der nächsten Tour wieder ab.

## Version 3.3.0 – Heimatort

In der **Verwaltung** gibt es das Feld **Heimatort**: Ort oder Adresse suchen (OpenStreetMap), Treffer anklicken, „Einstellungen speichern“. Touren in der Nähe (bis etwa 60 km) zählen dann nicht als Reise. Ohne Eintrag erkennt die App den Heimatort wie bisher aus deinen Touren. Die Android-App nutzt dieselbe Oberfläche; in **Mein Tourentagebuch** 1.2 ersetzt die Ortssuche die Eingabe von Koordinaten.

## Version 3.2.0 – Erzählung teilen, Kommentare für Besucher, Orte im Rückblick

- **Diashow mit Kommentaren:** Beim „Diashow senden“ gibt es die Option „Besucher dürfen Fotos kommentieren“. Die Diashow-Seite zeigt dann 💬 an jedem Foto; Gäste schreiben ohne Konto (Name optional, am Autor steht „(Gast)“, höchstens 5 Kommentare pro Minute und Link, 500 Zeichen). Der Besitzer sieht und löscht die Kommentare in der Erzählung. Ohne die Option sieht und schreibt niemand Kommentare. Schnittstellen: `GET|POST /api/public/<Token>/comments`. Bedenke: Das ist nur sinnvoll, wenn der Server von außen erreichbar ist (Funnel, siehe README).
- **Erzählung teilen und drucken:** Auf der Erzählungsseite erzeugt „🔗 Teilen (mit Kommentaren)“ den Diashow-Link (30 Tage, Kommentare erlaubt) und kopiert ihn; „🖨 Drucken“ druckt die Zeitleiste mit Ortsnamen, Fotos und Kommentaren oder speichert sie als PDF. Kommentare stehen jetzt auch als Text unter den Fotos der Zeitleiste.
- **Orte im Jahresrückblick:** Seite und PDF zeigen „Orte des Jahres“ (Startorte mit Touren und Kilometern, Zahl der Regionen und Länder).
- **3D-Flug mit Multitouch:** In der freien Kamera zoomen zwei Finger (spreizen/zusammenziehen), drehen die Ansicht (verdrehen) und kippen sie (beide Finger nach oben/unten). Jede eigene Bewegung schaltet „Kamera folgt“ automatisch auf „Kamera frei“.
- **Fotostandorte in der Erzählung:** Jedes Foto erscheint als 📷 an seinem Aufnahmeort; ohne GPS im Foto wird die Stelle aus der Aufnahmezeit auf der Strecke berechnet. Klick zeigt das Foto, ein weiterer Klick öffnet es groß mit Kommentaren.
- **Docker-Image** (siehe README, Abschnitt Docker), Tourseite ohne Aufblitzen der Einzelknöpfe.
- **Fotos aus der App:** „Fotos hinzufügen …“ auf der Tourseite funktioniert in der Android-App bereits über die Dateiauswahl des Handys; Fotos während der Aufzeichnung gibt es über die Kamera im Aufnahme-Panel.

## Version 3.1.0 – Kommentare zu Fotos

In der **Erzählung** (Tourseite → „📖 Erzählung“) lässt sich jedes Foto anklicken: Es öffnet sich groß, darunter stehen die Kommentare (mit Name und Zeit) und ein Eingabefeld. Kommentare lassen sich löschen; die Zahl der Kommentare erscheint als 💬 am Vorschaubild. Schnittstelle: `GET /api/tours/<id>/comments`, `GET|POST /api/photos/<id>/comments`, `DELETE /api/comments/<id>`. Beim Löschen eines Fotos verschwinden seine Kommentare. Außerdem erscheint bei Komoot-Touren der Knopf „⬇ GPX“ nicht mehr doppelt. Die Knöpfe der Tourseite sind jetzt auch am Rechner nach Themen in drei Menüs sortiert: **Ansehen** (Erzählung, 3D-Flug, Tourblatt), **Teilen & Export** (Link/Diashow senden, Links verwalten, GPX) und **Bearbeiten** (alles, was die Tour verändert, gegliedert in Beschriften, Strecke und Höhen, Abgleich und Upload, Entfernen). In der Erzählung steht unter jeder Station der **Ortsname** (📌, aus OpenStreetMap, zwischengespeichert; ohne Internet bleibt die Zeile leer).

## Version 3.0.0 – die App begleitet die ganze Tour

Server 3.0.0 / App 3.0.0 fassen die Etappen 2.10–2.13 zusammen: **Offline-Speicher** in der App (auch ohne HTTPS), **Live-Ansicht** beim Aufzeichnen (nächste Abbiegung, Rest, Ankunft, Höhenprofil mit Standort), **Wegpunkte** mit Schnellnotiz und die **Erzählung** zur Tour, **Wetterwarnung** unterwegs und der **Live-Standort-Link** für Kontakte – alles in Deutsch, Englisch, Französisch und Spanisch. Die Einzelheiten stehen in den folgenden Abschnitten.

## Version 2.13.0 – Wetterwarnung und Live-Standort-Link (Server 2.13 / App 2.9)

Während einer Aufzeichnung fragt die App alle 15 Minuten beim Server die Vorhersage für den Standort ab (`/api/weather/alert`, Open-Meteo, 10 Minuten Zwischenspeicher je 0,1°-Zelle) und warnt per Benachrichtigung und Sprachansage vor Gewitter (bis 4 h), Starkregen, Sturmböen ab 60 km/h, Schnee/Frost und Temperatursturz ab 8 Grad (je bis 3 h voraus); jede Warnart höchstens einmal pro Stunde, abschaltbar im Aufzeichnen-Dialog. Unter *Aufzeichnen* erstellt „📡 Live-Standort für Kontakt teilen“ einen Link (3 Stunden bis 3 Tage, ohne Konto, jederzeit widerrufbar über `DELETE /api/live/link/<Token>`), der den letzten gemeldeten Standort auf einer Karte zeigt (Seite `/pub/live/<Token>`, aktualisiert alle 20 s). Voraussetzung: *Verwaltung → Standort teilen* ist nicht „Aus“, die Serveradresse ist HTTPS und für den Kontakt erreichbar (öffentliche Adresse, z. B. Tailscale Funnel); die Basisadresse stammt aus „Öffentliche Adresse“ (E-Mail-Einstellungen) oder der aufgerufenen Adresse.

## Version 2.12.0 – Offline, Live-Ansicht und Wegpunkte (Server 2.10–2.12 / App 2.7–2.8)

Die App speichert alles, was sie vom Server lädt (Seiten, Daten, Strecken, kleine Fotos, Kartenkacheln), auf dem Handy und zeigt es ohne Verbindung weiter an (Hinweisband „Offline“); unter *Verwaltung → Offline-Nutzung* lädt „Alle Touren offline“ Daten und Strecken aller Touren vor. Beim Aufzeichnen mit Route zeigt die Live-Ansicht die nächste Abbiegung, Rest-Kilometer, geschätzte Ankunft und das Höhenprofil mit dem eigenen Standort (das Profil wird beim Laden der Route einmal berechnet und auf dem Handy gemerkt); zusätzlich gibt es die Ansagen „Halbzeit“ und „Noch fünf Kilometer“. Mit **📍 Wegpunkt setzen** hält man unterwegs per Schnellnotiz (Rast, Aussicht, Quelle, Gabelung …) oder eigenem Text einen Ort fest; die Wegpunkte gehen als GPX-`wpt` mit der Tour auf den Server und erscheinen dort als Liste und Marker. **📖 Erzählung** (Tourseite) fügt Start, Wegpunkte, Foto-Gruppen und Ziel zu einer Zeitleiste mit Karte zusammen.

## Version 2.9.0 – Sprachansagen auf der Strecke (Server 2.8.0 / App 2.6.0; mehrsprachig ab Server 2.9.0 / App 2.6.1)

Vor dem Start unter *Aufzeichnen* eine **geplante Tour** (Verwaltung der Tourplanung) oder eine **frühere Tour zum Nachgehen** als „Route mit Sprachansagen“ wählen. Die App erkennt die Abbiegestellen selbst aus der Strecke und sagt sie in der Sprache der Oberfläche an (Deutsch, Englisch, Französisch oder Spanisch) – auch bei ausgeschaltetem Bildschirm und über Kopfhörer:
- „In 100 Metern rechts abbiegen“, kurz vorher „Jetzt rechts abbiegen“ (bei höherem Tempo früher); liegen zwei Abbiegungen dicht beieinander: „…, danach links abbiegen“. Leichte Richtungswechsel heißen „leicht links halten“, enge „scharf links abbiegen“, Spitzkehren „Kehre nach links“.
- „Du bist vom Weg abgekommen“ (mehr als 40 m neben der Strecke, bei schlechtem GPS entsprechend mehr) mit Abstand zur Route, alle 90 s wiederholt; „Wieder auf dem Weg“, sobald du zurück bist.
- „Noch ein Kilometer bis zum Ziel“ und „Du hast das Ziel erreicht“.
- Ist die Route beim Start noch weit weg, sagt die App das einmal und beginnt die Führung erst, wenn du auf der Strecke bist. Rundwege (Start = Ziel) werden richtig behandelt.
- Während der Aufnahme lassen sich die Ansagen mit einem Haken ein- und ausschalten; *Testansage* prüft Lautstärke und Stimme. Die Strecke erscheint blau auf der Karte der Aufzeichnung und wird nach dem Beenden wieder entfernt.
- Die Ansagen nutzen die Sprachausgabe von Android (Einstellungen → Sprachausgabe; für eine gute deutsche Stimme ggf. „Sprachdaten installieren“). Es gibt keine Kartendaten-Navigation: Die Abbiegungen kommen aus der Form der Strecke, es werden keine Wegnamen genannt.

## Version 2.7.4 – Fotos aus der App in einer anderen Zeitzone (Server 2.7.4 / App 2.5.1)

Die App schickt mit jedem Foto-Upload die Zeitzone des Telefons mit. Hat die Kamera keine Zeitzone ins Foto geschrieben, trägt der Server sie nach. Vorher wurde die Aufnahmezeit als Ortszeit des Servers gedeutet – war das Handy z. B. auf den Kanaren (UTC+0) und der Server in Deutschland, lag das Foto eine Stunde neben der Tour und wurde nicht zugeordnet.

## Version 2.7.3 – Abgelaufene Diashow-Links

Wer einen abgelaufenen oder zurückgezogenen Link öffnet, sieht eine verständliche Seite statt einer Fehlermeldung: bei Ablauf mit dem Datum und dem Hinweis, einen neuen Link anzufordern, sonst mit dem Hinweis auf einen abgeschnittenen oder zurückgezogenen Link.

## Version 2.7.1 – Fotos auf der Karte

Der Knopf „Fotos“ zeigt jetzt auch Fotos ohne eigenen Aufnahmeort (GPS): ihre Position wird aus der Aufnahmezeit auf dem Track der Tour berechnet und als blassere Punkte gezeigt („Position aus der Uhrzeit berechnet“). Fotos mit GPS bleiben unverändert. Der Knopf zeigt die Anzahl, z. B. „Fotos (312)“.

## Version 2.7.0 – Info und Heimatorte

Im Menü „Mehr“ (Handy) bzw. im Benutzermenü (Computer) zeigt „Info“ die laufende Version der Android-App und des Servers sowie die Ersteller (Volker Hildebrand und Claude).

**Heimatorte:** Orte, an denen du dich allgemein aufhältst (Zuhause, Zweitwohnsitz, Stammgebiet), erkennt die App selbst – ein Gebiet von etwa 30 km, in dem sehr viele Touren (mindestens 8 und 10 % aller) über mindestens 8 verschiedene Monate gestartet wurden. Touren dort zählen nie als Reise; ein Urlaubsort, den man nur ab und zu besucht, bleibt eine Reise.

## Version 2.6.1 – Reisen: nur noch echte Reisen

Unter „Reisen“ stehen nur noch echte Reisen: Touren weit weg von zu Hause an mindestens **4 Tagen** am Stück. Wochenend- und Kurzausflüge (auch in Hessen) erscheinen dort nicht mehr; sie bleiben als normale Touren erhalten und lassen sich über Tags/Alben gruppieren. Eine Reise, die du selbst bearbeitet hast (Name/Zeitraum), bleibt immer sichtbar. Mehrere Reisen im selben Bundesland bekommen eindeutige Namen („Hessen – Rhön (Mai 2024)“). Die Mindestdauer steht in der Einstellung `trip_min_days` (Standard 4).

## Version 2.6.0 – E-Mail, Passwort vergessen und Zwei-Faktor-Anmeldung

- **E-Mail-Adresse:** Beim Einrichten und beim Anlegen jedes Benutzers ist jetzt eine E-Mail-Adresse Pflicht. Bestehende Benutzer tragen sie unter „Konto & Freigaben“ nach (Bestätigung mit dem Passwort); Administratoren können sie dort auch für andere ändern.
- **E-Mail-Versand einrichten (Verwaltung → Automatik & Meldungen → „E-Mail-Versand“):** SMTP-Server, Port, Verschlüsselung, Benutzername und Passwort deines E-Mail-Anbieters (bei Yahoo, GMX, Gmail meist ein eigenes „App-Passwort“), Absenderadresse und die öffentliche Adresse der App (`https://…ts.net`), die in den Link der Mail kommt. Mit „Testmail an mich senden“ prüfen. Das Passwort liegt nur in der Systemdatenbank und wird nie wieder angezeigt.
- **Passwort vergessen:** Auf der Anmeldeseite „Passwort vergessen?“ → E-Mail-Adresse oder Name → Link per Mail (eine Stunde gültig, nur einmal benutzbar, höchstens 3 pro Stunde und Konto). Die Antwort ist immer gleich, man erfährt also nicht, ob eine Adresse bekannt ist. Nach dem Ändern werden alle Anmeldungen beendet und eine Hinweismail geschickt. Ohne eingerichteten Mailversand erscheint ein Hinweis, den Administrator zu bitten.
- **Zwei-Faktor-Anmeldung (Konto & Freigaben → „Zwei-Faktor-Anmeldung“):** jederzeit ein- und ausschaltbar. Einschalten: QR-Code mit einer Authenticator-App scannen (Google/Microsoft Authenticator, Aegis, 2FAS, Bitwarden …) und den Code bestätigen; danach werden 8 **Wiederherstellungscodes** einmalig angezeigt. Anmeldung: Name und Passwort, dann der 6-stellige Code (oder ein Wiederherstellungscode). Ausschalten und neue Wiederherstellungscodes brauchen Passwort **und** Code. Ein Code gilt nur einmal, nach 5 Fehlversuchen muss man neu beginnen. Geht das Handy verloren und es gibt keine Codes mehr, setzt ein Administrator die Zwei-Faktor-Anmeldung unter „Benutzer verwalten“ zurück.
- Hinweise: Das Zurücksetzen des Passworts umgeht die Zwei-Faktor-Anmeldung nicht. Betrachter-Zugänge (nur ansehen) haben keine Zwei-Faktor-Einstellung. Der QR-Code wird mit der mitgelieferten Bibliothek *qrcode-generator* (MIT) lokal erzeugt, es wird nichts nach außen geschickt.

## Version 2.5.2 – Aufgeräumte Tour-Ansicht am Handy

Statt elf Einzelknöpfen gibt es zwei große Knöpfe. „Teilen & Senden“ enthält Link senden, Diashow senden, Links verwalten, GPX-Datei und Tourblatt; „Bearbeiten“ enthält Umbenennen, Tags, Streckenfarbe, Höhen und Track korrigieren, Hochladen, Komoot-Abgleich und (abgesetzt, rot) Löschen – jeweils mit kurzer Erklärung. Am Computer bleibt alles unverändert.

## Version 2.5.1 – Diashow-Links genauer

„Diashow senden“ fragt vorher nach den Fotos (alle oder nur die besten 20/50) und der Gültigkeit (7 Tage, 30 Tage, unbegrenzt). Abgelaufene Links zeigen „nicht mehr gültig“, auch die Fotos sind dann gesperrt. In „Tour teilen“ steht je Link, bis wann er gilt und wie oft die Diashow angesehen wurde. Die Diashow zeigt die Uhrzeit des Fotos und hat einen Tempo-Knopf (3/5/8 s).

## Version 2.5.0 – Diashow per WhatsApp teilen, fester App-Schlüssel

In der Tour gibt es neben „Senden“ den Knopf „Diashow senden“. Er erzeugt einen Link, der ohne Benutzerkonto funktioniert, und öffnet das Teilen-Menü (WhatsApp, Signal, E-Mail …). Wer den Link öffnet, sieht die Fotos der Tour als Vollbild-Diashow (automatischer Wechsel alle 5 s, Wischen, Pause, Vollbild, Karte mit dem Track). WhatsApp zeigt in der Vorschau Titel und erstes Foto. Es werden nur die Fotos dieser einen Tour freigegeben (keine Konten, keine anderen Touren); ausgeblendete Fotos fehlen. Der Link lässt sich unter „Teilen“ der Tour (Eintrag „Diashow“) widerrufen. Betrachter können keine Links erzeugen.

**Fester App-Schlüssel (App 2.5.0):** Die APK wird jetzt immer mit demselben, im Repository liegenden Schlüssel (`android/app/mt-debug.jks`) signiert. Neue Versionen lassen sich dadurch **über die alte installieren, ohne zu deinstallieren** – die Aufzeichnungs-Backups auf dem Handy bleiben erhalten. *Einmalig* muss die bisherige App noch deinstalliert werden, weil sie mit einem anderen Schlüssel signiert war. Wer sicherer signieren will, hinterlegt wie bisher die vier GitHub-Secrets (siehe „APK bauen“); diese haben Vorrang. Hinweis: Der Schlüssel liegt öffentlich im Repository – das ist für eine privat genutzte App in Ordnung, ersetzt aber keine geheime Signatur.

**Testliste Fotos und Aufzeichnung (vor einer langen Tour, ca. 10 Minuten):**
1. Aufzeichnung starten, 2 Fotos aufnehmen (Modus „sofort“): Foto erscheint nach kurzer Zeit in der Tour, ohne Fehlermeldung.
2. Flugmodus an, ein Foto aufnehmen: Foto bleibt in „Wartende Fotos“; Flugmodus aus → wird hochgeladen.
3. Modus „am Ende“, Foto aufnehmen, Aufzeichnung beenden: Track und Foto kommen zusammen an.
4. Während der Aufnahme eine andere App öffnen und zurückkehren: Aufzeichnung läuft weiter, kein Punkteverlust.
5. „Beenden“ nur kurz antippen: nichts passiert; lange halten: Aufzeichnung stoppt.
6. In der Galerie prüfen, ob die Kopie der Fotos vorhanden ist.
Bei Fehlern: „Diagnose senden / kopieren“ (Verwaltung → Handy & App → Android-App) und mir schicken.

## Version 2.4.1 – Verwaltung neu geordnet

Sieben Reiter, jeder Bereich ist eine gleich gestaltete Karte: Übersicht (Zustand, Updates, Selbsttest, Protokoll), Touren holen (Komoot, Zepp, Uhren und Dateien, Wanderführer), Hochladen & Planen (Strava/Komoot-Upload, Tourplanung), Fotos, Automatik & Meldungen, Handy & App (Android-App, Standort teilen, verlorene Aufzeichnungen, App auf dem Startbildschirm) und Sicherung & Zugang. Das Protokoll ist eingeklappt; „Einstellungen speichern“ bleibt unten auf jedem Reiter erreichbar.

## Version 2.4.0 – Foto aufnehmen in der Android-App

Während einer Aufzeichnung gibt es den Knopf „📷 Foto aufnehmen“ (öffnet die Kamera-App; das Foto bekommt Aufnahmezeit und GPS-Position und landet zusätzlich in der Galerie unter „Meine Touren“). Vor dem Start wählst du, ob Fotos **sofort** auf den Server geladen werden (bei fehlender Verbindung wird automatisch erneut versucht) oder **gesammelt am Ende**, beim Speichern der Tour. Die Aufzeichnungsseite zeigt Zeit, Strecke, Auf- und Abstieg, aktuelle und höchste Höhe, Tempo, Durchschnitt und GPS-Genauigkeit. **Beenden** geht nur noch durch Gedrückthalten (1,5 Sekunden), versehentliches Antippen beendet nichts mehr. Auf der Karte steht beim eigenen Standort und beim Live-Standort der Benutzername. Fotos der Aufzeichnung kommen über `/api/rec-photos` in den Foto-Eingang und werden automatisch der Tour zugeordnet.

## Version 2.3.2 – Fehlerkorrektur: verlorene App-Aufzeichnungen

Bis 2.3.1 landeten Aufzeichnungen aus der Android-App (und Dateien über „Teilen“) bei mehreren Benutzern im Altbestand statt im eigenen Konto: der Server meldete „gespeichert“, die Tour war aber nirgends zu sehen. Ab 2.3.2 landen sie im richtigen Konto. Bereits verlorene Aufzeichnungen der letzten 30 Tage holt Verwaltung → „Verlorene App-Aufzeichnungen suchen“ (nur Administratoren) ins eigene Konto.

## Version 2.3.1 – Betrachter strenger, Sicherung der Aufzeichnungen

**Betrachter strenger:** Ein Betrachter darf nur Daten abrufen: keine PDFs (Tourblatt, Reise, Jahresrückblick), kein Umbenennen, keine Höhen- oder Zeitkorrektur, keine Foto-Änderungen, keine Notizen/Bewertungen/Tags, kein Teilen-Link. Erlaubt sind der GPX-Download einer Tour, die Diashow und die Fotos in der Tour und auf der Karte. Der Server erlaubt für diese Rolle nur eine feste Liste von Abfragen; die Oberfläche blendet die Bedienelemente zusätzlich aus.

**Sicherung der Aufzeichnungen (App 2.3.1):** Jede beendete Aufzeichnung wird vor dem Aufräumen zusätzlich auf dem Handy gesichert (die letzten 10). Unter „Aufzeichnen“ erscheinen sie als „Gesicherte Aufzeichnungen“ und lassen sich mit einem Tippen erneut auf den Server speichern. Ein Name ist nie nötig: bleibt das Feld leer, vergibt der Server einen automatischen Namen.

## Version 2.3.0 – Betrachter und Standort

Unter Konto & Freigaben → „Neuer Benutzer“ gibt es die Rolle **Betrachter (nur ansehen)**. Ein Betrachter sieht die Touren, Fotos, Reisen, Auswertung und die Karte des gewählten Benutzers, kann aber nichts ändern, nichts hochladen und hat weder Verwaltung noch Einstellungen (der Server lehnt alles außer Ansehen mit „403“ ab). Unter Verwaltung → „Standort teilen“ wird festgelegt, ob die zuletzt gemeldete Position des Besitzers sichtbar ist (Aus / nur während einer Aufzeichnung / immer). Die Android-App meldet sie während einer Aufzeichnung alle 30 Sekunden (dafür die neue APK installieren); auf der Karte erscheint sie als roter Punkt mit „vor x Min.“. Der Knopf „⌖ Ich“ zeigt jedem Benutzer den eigenen Standort als blauen Punkt. Es wird nur die letzte Position gespeichert. Die mobile Karte füllt jetzt den Platz zwischen Kopfzeile und Tab-Leiste, und „Mehr“ trennt die Hauptpunkte (Reisen, Auswertung, Geteilte Fotos) von Einstellungen & Prüfung.

## Version 2.2.1 – Reisen: mindestens zwei Kalendertage

Als Reise zählen nur Gruppen über mindestens zwei Kalendertage. Tagesausflüge sind keine Reise, auch mit mehreren Aufzeichnungen am selben Tag. Eine fälschlich erkannte Reise lässt sich auf ihrer Seite mit „Keine Reise“ aus der Liste entfernen. Unten in der Reisenliste steht „Entfernte Reisen“ zum Wiederherstellen. Die Touren selbst bleiben immer erhalten.

## Version 2.2.0 – Teilen und Smartphone-Ansicht

Auf Tourseite, Reise und Jahresrückblick gibt es „Senden“. In der App öffnet es das Android-Auswahlmenü (WhatsApp, Signal, E-Mail …). Bei einer Tour wird dafür ein Link ohne Anmeldung erzeugt (Anfang und Ende ausgeblendet). Der Link funktioniert für Empfänger nur, wenn der Server von außen erreichbar ist (z. B. Tailscale Funnel). Die Übersicht und die Filterleiste der Tourenliste sind auf dem Handy deutlich kompakter.

## Version 2.1.0 – Push-Meldungen

Trage in der Verwaltung unter „Benachrichtigung“ eine ntfy-Adresse ein (z. B. `https://ntfy.sh/mein-geheimes-thema`). Dann kommen Warnungen und neue Touren (Aufzeichnung, Teilen-Menü, Import) als Meldung. In der Android-App: Verwaltung → Android-App → „ntfy-App holen“, danach „In ntfy abonnieren“. Das Abschalten der Tour-Meldungen geht im selben Panel.

## Version 2.0.0 – Android-App

Native Android-App als „Hülle“ um die Weboberfläche mit GPS-Aufzeichnung, Teilen-Menü und PDF-Downloads. Beschreibung, APK-Bau und Hinweise stehen in der README im Abschnitt „Android-App“.

## Version 1.15

* **PDF-Berichte neu gestaltet:** Tourblatt, Reisebericht und Jahresrückblick haben jetzt einen farbigen Kopf mit Titel (auf Wunsch mit Titelfoto), Kennzahlen-Karten, Kartenbild mit Rahmen, Höhenprofil mit höchstem Punkt, Tabellen mit Zebra-Streifen und Tageszeilen, abgerundete Fotos mit Aufnahmezeit, Notiz und Bewertung (Tourblatt), Monatsdiagramm und Sportarten-Anteile (Jahresrückblick) sowie „Seite x von y“ in der Fußzeile.
* **Offline-Hinweis:** Ohne Verbindung zeigt die App oben einen gelben Hinweis; zuletzt gesehene Touren und Karten bleiben sichtbar (installierte App über HTTPS).

## Version 1.14

* **Teilen mit Meine Touren (Android):** Ist die App auf dem Handy installiert, erscheint sie im Teilen-Menü. GPX-, FIT-, TCX- und ZIP-Dateien (z. B. aus Garmin Connect oder Komoot) werden sofort als Tour übernommen, Fotos aus der Galerie landen im Eingang und werden im Hintergrund den Touren zugeordnet. Danach zeigt eine Ergebnisseite, was importiert wurde.
* **Handy-Installation:** Verwaltung → Übersicht → „Auf dem Handy“ erklärt die Installation, bietet „App installieren“ und zeigt, ob die Verbindung gesichert ist. Neu im Manifest: Verknüpfungen (Touren, Karte, Tour planen, Reisen) per langem Druck auf das App-Symbol.

## Version 1.13.1

* **Echte PDF-Berichte:** Tourblatt, Reisebericht und Jahresrückblick haben „⬇ PDF herunterladen“: Der Server erstellt eine fertige, saubere PDF-Datei (Text als Text, Karte mit Strecke, Höhenprofil als Grafik, Fotos, Statistik-Tabellen, Seitenzahlen) statt eines Bildschirmfotos. „Drucken“ bleibt als zusätzliche Möglichkeit. Fotos an/aus und Anzahl gelten auch hier. Neues Python-Paket: `reportlab` (wird beim Update automatisch installiert). Die Karte entsteht aus dem Kachel-Zwischenspeicher bzw. lädt fehlende Kacheln von OpenTopoMap; ohne Internet erscheint die Strecke auf heller Fläche.

## Version 1.13

* **Reisen bearbeiten:** In der Reise gibt es „✎ Reise bearbeiten“: Name und Zeitraum lassen sich ändern. Ein größerer Zeitraum nimmt alle Touren dieser Tage auf, ein kleinerer lässt Touren weg; Kilometer, Aufstieg und Statistik passen sich an. „Zurücksetzen“ stellt die automatische Erkennung wieder her.
* **Reisebericht als PDF:** „📄 Reisebericht (PDF)“ in der Reise öffnet eine druckbare Seite mit Karte (Tage in Farben), Statistik nach Aktivität, Tag-für-Tag-Liste und den besten Fotos. Als Datei über „⬇ PDF herunterladen“ (auch am Handy).
* **Fotos im PDF wählbar:** In Tourblatt, Reisebericht und Jahresrückblick lässt sich über „Fotos im PDF“ einstellen, ob Fotos dabei sind und wie viele (3 bis 24). Die Wahl gilt appweit und wird gespeichert.

## Version 1.12.2

* **Tourplanung komplett abschaltbar:** Ist „Tourplanung“ unter Verwaltung → „Touren & Quellen“ aus, sind neben den Schaltflächen und der Seite auch alle Planungs-Schnittstellen der App gesperrt.

## Version 1.12.1

* **Update aus der Oberfläche:** Nach dem Neustart wartet das Update-Skript bis zu 90 Sekunden auf den Dienst (vorher 2 Sekunden – bei großen Datenbanken ein falscher „fehlgeschlagen“-Alarm). Bei einem Fehler zeigt die Oberfläche jetzt die echte Ursache statt eines allgemeinen Hinweises; das vollständige Protokoll liegt unter `/var/lib/meine-touren/update.log`.

## Version 1.12

* **Tourplanung ein- und ausschaltbar:** Unter Verwaltung → „Touren & Quellen“ → „Tourplanung“. Ist sie aus, verschwinden alle „Tour planen“-Schaltflächen. Ist sie an, wählst du den Routing-Dienst: **brouter.de** (öffentlich), **eigener BRouter auf diesem Server** (mit Installationsbefehl direkt in der Oberfläche) oder **anderer BRouter-Server im Netz**. „Verbindung testen“ prüft die Adresse und meldet fehlende Karten-Kacheln.
* **Statistik nach Aktivität** bei Reisen, Alben und Etappen: je Sportart Touren, Kilometer, Aufstieg, Abstieg, Stunden, Ø km/h und längste Tour, dazu eine Gesamtzeile; die Kennzahlen oben zeigen jetzt auch den Gesamtabstieg.

## Version 1.11.1

* **Notizfeld:** Die Box wuchs beim Tippen mit jedem Zeichen weiter. Jetzt richtet sich die Höhe nach dem Text und nie darunter nach der gemerkten/gezogenen Größe.

## Version 1.11

* **Planung über bekannte Wege:** Die Punkte der Tourplanung werden jetzt über Wege und Straßen aus OpenStreetMap verbunden (Dienst [BRouter](https://brouter.de), Profil je nach Sportart: Wandern/Ski/Schneeschuh „hiking-mountain“, Rennrad „fastbike“, MTB „mtb“, sonst „trekking“). Gestrichelt gezeichnet wird eine gerade Linie, wo kein Weg gefunden wurde. Ein Klick auf einen Abschnitt wählt ihn aus; **„Alternativen anzeigen“** zeigt bis zu drei weitere Routen mit Länge und Aufstieg, ein Klick auf eine Alternative übernimmt sie. „Wegen folgen“ lässt sich ausschalten (gerade Linien; geladene GPX-Strecken und Wanderführer-Touren werden nie umgeroutet). Gespeicherte Pläne merken sich Punkte und gewählte Alternativen.
  **Datenschutz:** Zum Verbinden werden die Koordinaten der geplanten Punkte an brouter.de gesendet. Wer das nicht möchte, trägt unter Verwaltung → „Touren & Quellen“ → „Routenplanung“ die Adresse eines eigenen BRouter-Servers ein oder schaltet „Wegen folgen“ aus.

## Version 1.10

* **Touren planen:** Unter „Touren“ (und in der Wunschliste) führt „🗺 Tour planen“ zur Planung. Punkte in die Karte klicken (ziehen, Rechtsklick entfernt) oder eine **GPX-Datei laden** oder eine Tour aus dem **Wanderführer** übernehmen. Die App zeigt Länge, Auf- und Abstieg, höchsten Punkt und das Höhenprofil (Höhen aus dem Geländemodell) und schätzt die **Zeit nach deinem eigenen Tempo**: Aus deinen bisherigen Touren der Sportart wird gelernt, wie lange du je Kilometer und Höhenmeter brauchst (Gesamtzeit inklusive Pausen, mit Spanne). Bei zu wenig Archiv gelten Standardwerte. Pläne lassen sich mit Notiz speichern, wieder laden, löschen und als GPX herunterladen. Die Punkte werden geradlinig verbunden (kein Wege-Routing) – für Wege entlang von Pfaden also dicht klicken oder eine fertige GPX-Strecke laden.

## Version 1.9

* **Schneller Start der Übersicht:** Die Seite wartet nicht mehr auf die Streckenlinien und die „Wie oft gelaufen?“-Auswertung – beides wird nachgereicht (Mini-Strecken erscheinen kurz danach, 🔁 ebenso). Der Server hält die Streckenlinien fertig im Speicher (mit ETag, bei unveränderten Daten antwortet er nur noch „304“), rechnet die Wiederholungs-Auswertung nur neu, wenn sich Touren oder Strecken ändern (nicht mehr bei jeder Datenbankänderung), und erzeugt die Vorschaubilder der Übersicht nach dem Start im Hintergrund vor (gedrosselt, alle 3 Stunden nachgeholt).
* **Wetter und Schneelage:** Zur Tour zeigt die Wetterzeile bei Schnee zusätzlich Schneehöhe, Neuschnee der 3 Tage davor und Schneefall während der Tour (Open-Meteo, grobe Modelldaten). Ältere Wetterdaten werden dafür einmal nachgeladen.
* **Vergleich dieser Strecke:** Bei wiederholten Strecken zeigt ein Balkenvergleich alle Begehungen mit Dauer und Tempo, Bestzeit mit 🏆 und „x. schnellste von n“.
* **Tagebuch:** Eigene Bewertung mit 1–5 Sternen je Tour (★ in der Tourliste, Filter „Alle Bewertungen / ab ★★★ …“). Die Notiz zur Tour gibt es jetzt auch bei lokalen Touren; die Notizbox **merkt sich ihre Größe** und wächst mit dem Text, sodass er ganz lesbar ist.
* **Sicherheitsnotiz** bei Skitouren, Skifahren, Schneeschuh und Bergtouren: Lawinenwarnstufe 1–5, Gruppe, mitgeführte Notfallausrüstung (LVS, Sonde, Schaufel, Helm, Airbag …) und Notiz. Reine Dokumentation, kein Lawinenlagebericht.
* **Ziele je Sportart-Gruppe:** Ziele können jetzt auch für „Alle Rad-Sportarten“, „Alle Ski-Sportarten“, „Zu Fuß“ oder „Laufen und Langlauf“ gelten. Ohne Ziele im neuen Jahr bietet die Übersicht „Ziele aus dem Vorjahr übernehmen“ an.
* **Oberflächenpasswort in der Oberfläche:** Unter Verwaltung → „Sicherung & Zugang“ lässt sich das gemeinsame Passwort jetzt setzen, ändern und aufheben (nur Betrieb ohne Benutzerverwaltung; gespeichert wird nur ein Hash). Ein per `UI_PASSWORD` festgelegtes Passwort bleibt weiter möglich, ist dann aber nur dort änderbar.

## Version 1.8

* **Kennzahlen passend zur Sportart:** Unter den Grunddaten einer Tour steht eine zweite Zeile mit Werten, die zur Sportart passen – Wandern/Bergtour/Schneeschuh: Gehzeit, Pausen, Steigrate (m/h), steilster Abschnitt; Rad: Ø in Bewegung, Höchsttempo, Pausen, Anteil bergauf/bergab; Skitour/Skifahren: Aufstiegs- und Abfahrtszeit, Abfahrtshöhenmeter, Höchsttempo, steilster Abschnitt und Anteil der Strecke über 30°; Laufen: Pace. Die Werte werden aus den Streckenpunkten berechnet (GPS-Rauschen wird geglättet).
* **Steigung auf der Karte:** Der Knopf „⛰ Steigung“ direkt auf der Tourkarte färbt die Strecke nach Steilheit ein (mit Legende). Bei Skitouren und Schneeschuh-Touren sind Abschnitte über 30° Hangneigung violett markiert.
* **Jahreszeit:** In der Tourliste filtert „Sommerhalbjahr (Mai–Okt) / Winterhalbjahr (Nov–Apr)“. Touren auf der Wunschliste haben eine beste Jahreszeit (ganzjährig / Sommer / Winter); passt sie zur aktuellen Jahreszeit, steht „passt jetzt“ dabei.
* **Ausrüstung:** Unter „Auswertung“ legst du Rad, Schuhe, Ski … an (Name, Art, Sportarten, Zeitraum, optional „Wechsel-Hinweis ab … km“). Die App zählt Kilometer, Höhenmeter und Touren automatisch mit und warnt mit „bald wechseln“ (ab 90 %) und „Wechsel fällig“. Im Tourdetail steht die zugeordnete Ausrüstung; mit ✎ lässt sie sich für diese eine Tour ändern („automatisch nach Sportart und Datum“ oder eigene Auswahl).

## Version 1.7.3

* **Diashow mit Vollbild auf Touchgeräten:** Oben rechts erscheinen Knöpfe für Vollbild (⛶), Pause und Schließen; sie blenden sich nach 3 Sekunden aus und kommen per Tippen in die Bildmitte zurück. Tippen links/rechts oder Wischen blättert, der Bildschirm bleibt während der Diashow an (wo der Browser das erlaubt). Am Computer weiterhin Leertaste, Pfeiltasten und F. **iPhone:** Safari erlaubt dort keinen Vollbildmodus für Webseiten – die Seite zeigt einen Hinweis; mit „Zum Home-Bildschirm“ öffnet die App ohne Browserleiste (iPad und Android unterstützen Vollbild direkt).

## Version 1.7.2

* **Fehlerbehebung Updates (seit 1.7.0):** Durch die neue Reiter-Verwaltung wurde der Update-Bereich verschoben und doppelt angelegt; „Jetzt prüfen“ löste einen Fehler aus. Behoben. Außerdem nennt der Update-Bereich jetzt den Grund, wenn GitHub nicht erreichbar ist (z. B. keine Verbindung, Anfragelimit).

## Version 1.7.1

* **Unbenutzte Fotos aufräumen:** Auf der Seite „Fotos“ gibt es „🧹 Unbenutzte Fotos aufräumen …“, solange Fotos keiner Tour zugeordnet sind. Der Dialog zeigt Anzahl, Speicherplatz und eine Stichprobe und lässt dich **Jahre auswählen**; erst danach ist „Löschen“ möglich. Gelöscht werden nur die Kopien in der Fotobibliothek der App, nie Originale; die Fotos tauchen beim nächsten Import nicht wieder auf. Zum Zeitpunkt des Löschens wird neu geprüft, welche Fotos noch ohne Tour sind.

## Version 1.7

* **Verwaltung neu geordnet:** Statt einer langen Seite mit Klappbereichen gibt es fünf Reiter nach Aufgaben – *Übersicht* (Zustand, Updates, Protokoll, Selbsttest), *Touren & Quellen* (Komoot, Zepp, Garmin/Suunto/Dateien, Strava, Wanderführer), *Fotos*, *Automatik* und *Sicherung & Zugang* (Backup, Zugriffsschutz, Offline). „Einstellungen speichern“ bleibt auf jedem Reiter unten sichtbar. Der zuletzt gewählte Reiter wird gemerkt; Adressen wie `#/admin?tab=fotos` führen direkt hin.
* **Wie oft gelaufen?** Die App erkennt Touren, die dieselbe Strecke gehen (Länge ±20 %, mindestens 85 % der Strecke innerhalb von 60 m, auch in Gegenrichtung). In der Tourliste steht dann „🔁 3×“, im Tourdetail „Diese Strecke bist du schon 3-mal gegangen – das war das 2. Mal“ mit Links zu den anderen Begehungen.

## Version 1.6.3

* **Foto-Import, Kartenvorschau:** Aufnahmezeiten ohne Zeitzonenangabe werden in der Zeitzone des Servers gelesen, nicht in der des Browsers. Auf Reisen (Browser in anderer Zeitzone als der Server) stimmte sonst die Vorschau „x von y Fotos liegen auf der Strecke“ nicht. Der eigentliche Import war nicht betroffen.
* Automatische Tests auf GitHub: zwei fehlerhafte Annahmen in den Tests korrigiert (Dateireihenfolge, Backup-Ordner).

## Version 1.6.2

* **Fehlerbehebung Reisen:** Die Titelfotos der Mehrtagestouren fehlten bei Reihen, deren Fotos nicht unter den ersten 5000 Fotos der Bibliothek lagen. Die Kachel holt sich jetzt je Tour ein Foto direkt vom Server (`/api/tour-covers`).

## Version 1.6.1

* **Fehlerbehebung Höhenprofil:** Die gelben Foto-Marker erschienen nicht, wenn die Fotos keine GPS-Position haben (Zuordnung über die Aufnahmezeit rechnete mit falscher Zeitbasis). Jetzt werden sie über die Zeit richtig platziert.

## Version 1.6

* **Beste Fotos einer Tour:** Im Tourdetail wählt „⭐ Beste Fotos“ aus allen Fotos die 10 besten. Berücksichtigt werden Sternebewertungen aus Lightroom (aus der Datei oder einer gleichnamigen `.xmp`-Begleitdatei; „abgelehnt“ fällt heraus), die Schärfe (unscharfe Fotos fallen heraus) und die Verteilung über die Tour. Dazu gibt es „Diashow der besten“; das Tourblatt nutzt dieselbe Auswahl (6 Fotos). Ohne Sternebewertung entscheidet die Schärfe. Die Schärfe wird beim ersten Mal berechnet (bei vielen Fotos ein paar Sekunden) und gespeichert.

## Version 1.5

* **Kamerauhr-Hinweis:** Prüfen → „Kamerauhr“ zeigt Touren der letzten 90 Tage, bei denen die Foto-Zeiten nicht zum Aufnahmeort passen (Kamerauhr/Zeitzone falsch). „Korrigieren“ verschiebt die Fotos um die erkannte Differenz, „Ignorieren“ merkt sich die Tour.
* **Mehrtagestouren aufräumen:** Reisen → „＋ Mehrtagestour bilden …“ benennt Touren eines Zeitraums auf einen Schlag („Name – Tag N“); in der Gesamtansicht benennt „✎ Reihe umbenennen“ alle Etappen gemeinsam. Die Kacheln unter Reisen zeigen ein Foto aus der Mitte der Reihe.
* **Tourblatt:** Im Tourdetail „📄 Tourblatt“ – eine druckbare Seite mit Kennzahlen, Karte, Höhenprofil und bis zu 6 Fotos (Drucken → als PDF speichern).
* **Höhenprofil mit Fotos:** Gelbe Punkte im Profil markieren, wo ein Foto entstanden ist; Klick öffnet das Foto, der Mauszeiger darüber zeigt die Stelle auf der Karte.
* **Wunschliste:** Auswertung → Wanderführer: Touren aus den hinterlegten Wanderführern vormerken, mit Länge (und Aufstieg, wenn die GPX-Datei Höhen enthält). Bereits gegangene Touren sind markiert. Für schon früher hochgeladene Führer fehlt der Aufstieg, bis die GPX-Dateien erneut hochgeladen werden.
* **Jahresziele mit Prognose:** zusätzlich zur Hochrechnung das voraussichtliche Erreichungsdatum, bei Rückstand die nötige Wochenleistung.
* **Touren teilen (Familie):** Freigegebene Touren anderer Benutzer lassen sich unter „Geteilte Fotos“ samt Strecke und passenden Fotos in die eigene Sammlung übernehmen (als Kopie; der Besitzer behält seine Tour unverändert).
* **Offline-Nutzung:** Die Web-App merkt sich zuletzt geladene Daten, Karten und kleine Fotos; ohne Verbindung erscheint ein Hinweisband. Verwaltung → „Für Offline vorbereiten“ lädt die letzten 8 Touren samt Kartenkacheln vorab. Voraussetzung ist HTTPS (oder localhost). Beim Abmelden wird der Daten-Zwischenspeicher gelöscht.

## Version 1.4

* **Ursache statt Vermutung:** Unter Prüfen → Unplausible Touren steht bei jeder Tour, woran es liegt (nicht aufgezeichnete Zeiten, GPS-Ausreißer, Fahrt-Abschnitte, GPS-Zittern – oder „Track unauffällig, vermutlich falsche Sportart“) und der Knopf „🧹 Track korrigieren“ ist entsprechend hervorgehoben.
* **Zeit aus Foto-Positionen:** Liegen Fotos mit GPS-Position auf dem Track (mindestens drei, im Zeitablauf passend), kann die App daraus die Zeit entlang der ganzen Strecke ableiten – Pausen eingeschlossen, genauer als eine Schätzung. Option im Dialog „Track korrigieren“.
* **Mehrtagestouren:** Touren mit Namen wie „Alpenüberquerung E5 – Tag 6“ (auch „Etappe“, „Day“, „Stage“, „Jour“, „Día“) werden gruppiert: unter Reisen als eigene Karten, im Tourdetail als Hinweis mit Gesamtansicht (Karte, Summen, Fotos, 3D-Flug). Es braucht mindestens zwei verschiedene Tagesnummern.
* **Übersetzungen** (EN/FR/ES) deutlich erweitert (Dashboard, Tourdetail, Prüfen, Fotos, Verwaltungsüberschriften); sehr lange Erklärtexte der Verwaltung sind weiterhin deutsch.
* **Selbsttest** (Verwaltung → Wartung & Sicherheit) prüft zusätzlich Datenbank-Integrität, Schreibrechte der Foto-/Eingangs-/Backup-/Streckenordner, Stichproben der Foto-Dateien, HEIC-Unterstützung, auffällige Touren, Erreichbarkeit der GitHub-Update-Prüfung und den Update-Weg. Nach einem Update auf dem Server lohnt sich ein Durchlauf.

## Version 1.3

* **Zeit nachträglich verschieben:** im Fotoraster Fotos auswählen → **„Zeit verschieben …“** (Stunden/Minuten, wahlweise nur Auswahl, ganzer Aufnahmetag oder alle noch nicht zugeordneten Fotos); die Zuordnung zu Touren wird danach neu berechnet. Ist die Strecke mit Zeitstempeln vorhanden, schlägt **„Zeit per GPS prüfen“** den Versatz vor.
* **Fehlerliste beim Import:** Fotos, die nicht gelesen oder hochgeladen werden konnten, stehen einzeln mit Grund da.
* **HEIC/HEIF (iPhone):** werden beim Import in JPEG umgewandelt, wenn das optionale Paket `pillow-heif` installiert ist (`pip install pillow-heif`; die Startskripte und `install.sh` versuchen es selbst). Ohne das Paket nennt die Fehlerliste den Grund.
* **Kartenvorschau** im Importfenster: pro Aufnahmetag die Strecke der Tour und die Fotostandorte.
* **„Jetzt sichern“** direkt in der Hinweisleiste und unter Verwaltung → Zustand.
* **Mac-Update per Doppelklick:** `mac/Meine-Touren-aktualisieren.command` lädt die neueste Version von GitHub und ersetzt die Programmdateien (Daten bleiben unberührt, die alte Fassung liegt in `.vorher/`).
* **Englische, französische und spanische Oberfläche (Beta):** Sprachauswahl (DE/EN/FR/ES) oben rechts; Standard nach Browsersprache. Die Übersetzung läuft über Wörterbücher (`app/static/js/00-i18n.js` für Englisch, `00-i18n-data.js` für Französisch und Spanisch; Zeilen „deutsch|übersetzung“ zum Ergänzen) und ist noch nicht vollständig – nicht Übersetztes bleibt deutsch; Meldungen vom Server sind überwiegend deutsch. Datums- und Zahlenformate wechseln mit.
* **Demo-Modus:** `mac/Meine-Touren-Demo.command` bzw. `windows/Meine-Touren-Demo.bat` (oder `python -m app.demo`) startet die App auf Port 8090 mit 14 erfundenen Touren und 15 Beispielfotos in einem eigenen Datenordner (`~/Meine-Touren-Demo`) – ohne eigene Daten, ohne Konten, ohne Netzwerk. Gut zum Ausprobieren und für Screenshots. Echte Daten werden nie angefasst.
