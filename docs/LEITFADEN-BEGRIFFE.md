# Leitfaden: Begriffe und Bedienlogik (Meine Touren und Mein Tourentagebuch)

Stand 25.11.2026. Gilt für beide Apps, für alle sichtbaren Texte (Knöpfe, Überschriften, Hinweise, Meldungen, Tooltips, aria-label), das Handbuch und die Versionsnotizen. Von Volker entschieden sind die mit ★ markierten Punkte; der Rest folgt dem, was in den Apps heute überwiegt (Inventur vom 25.11.2026: /home/claude/inventur-meine-touren.md, /home/claude/inventur-tagebuch.md).

Interne Bezeichner (Dateinamen, Funktionen, Einstellungsschlüssel, API-Pfade, Element-IDs) bleiben unverändert. Begriffe fremder Dienste bleiben, wie der Dienst sie nennt (Strava „Aktivitäten“, Suunto „Workouts“ nur, wenn der Dienst genau so genannt wird).

## 1. Begriffe: ein Wort je Sache

| Sache | So heißt es | Nicht mehr |
| --- | --- | --- |
| Art der Tour ★ | Sportart, Sportarten | Aktivität, Sport |
| Tour per GPS mitschreiben ★ | aufzeichnen, Aufzeichnung („Tour aufzeichnen“, „Aufzeichnung läuft“) | aufnehmen, Aufnahme, Tracking (für GPS) |
| Foto oder Video machen | aufnehmen, Aufnahme | – |
| Stichwort an einer Tour ★ | Schlagwort, Schlagwörter („Schlagwörter & Alben“) | Tag, Tags, Label, Schlagworte |
| Beste Werte ★ | Bestwerte | Rekorde |
| Gegangene oder gefahrene Tour | Tour | Training, Workout, Aktivität (außer als Name eines Dienstes) |
| Linie auf der Karte, GPS-Daten | Strecke (die Linie), GPS-Track nur für die Datei bzw. das Korrigieren | Route für Gegangenes |
| Tour, die noch bevorsteht | geplante Tour; die Funktion heißt „Planung“ | Plan, Pläne (für die Tour selbst) |
| Soll bei Zielen | „im Soll“ | „im Plan“ |
| Messwert Länge | Strecke | Distanz, Länge |
| Messwert Höhe nach oben | Aufstieg | Höhenmeter, Anstieg, hm |
| Messwert Zeit gesamt | Dauer | Zeit, Gesamtzeit, Zeit unterwegs, Stunden unterwegs |
| Messwert Zeit ohne Pausen | Bewegungszeit | Zeit in Bewegung |
| Geschätzte Zeit einer geplanten Tour | Gehzeit (zu Fuß) bzw. Fahrzeit | – |
| Tage mit mindestens einer Tour | aktive Tage | Tage mit Tour |
| Bild aus der Kamera | Foto | Bild (außer „Titelbild“, „Bild teilen“ für erzeugte Grafiken) |
| Daten vom Portal oder von der Uhr | holen („Touren holen“) | laden, einlesen, abgleichen (dafür) |
| Daten aus einer Datei | importieren | laden, einlesen |
| Vorhandenes vergleichen und angleichen (Tagebuch ↔ Meine Touren, Komoot) | abgleichen, Abgleich | Sync, synchronisieren |
| Höhe einer Tour verbessern | „Höhe korrigieren“ (Quelle im Untertitel: „aus der Uhr“, „aus dem Geländemodell“) | „Höhe aus Uhr abgleichen“, „Höhen korrigieren“ |
| Datei erzeugen | exportieren („Als GPX exportieren“, „Als PDF exportieren“) | „Als GPX speichern“, „GPX-Datei laden“ |
| Kopie aller Daten | Sicherung, sichern, wiederherstellen | Backup, Datensicherung |
| Einstellungsbereich | Meine Touren: „Verwaltung“; Tagebuch: „Einstellungen“ (Seitentitel gleich dem Menüpunkt) | gemischte Titel |
| Teil einer Seite, den man anordnen kann | Baustein | Abschnitt, Kachel, Widget (für dasselbe) |
| Gespeicherte Anordnung einer Seite | Ansicht | Seitenlayout, Layout |
| Zusammenfassung von Sportarten ★ | Statistik-Gruppe („Name = A + B + C“) | „zusammengefasst“, „Gruppe“ ohne Zusatz |
| Mehrere Bausteine unter einer Überschrift | Bausteingruppe | „Gruppe“ ohne Zusatz |
| Sportarten für die Aufzeichnung | Favoriten-Sportarten | „Favoriten“ ohne Zusatz |
| Tour mit Stern | Lieblingstour bzw. Bewertung (Sterne) | Favorit |
| Startbildschirm | Meine Touren: „Übersicht“; Tagebuch: „Start“ (Seitentitel gleich dem Reiter) | Dashboard |
| Erster Reiter der Verwaltung (Meine Touren) | „Allgemein“ | „Übersicht“ (doppelt belegt) |
| Jahresauswertung | Jahresrückblick | Rückblick ohne „Jahres“ (wenn das Jahr gemeint ist) |
| Zeitraum ohne Grenze | „Gesamte Zeit“ | „Alle Jahre“, „Gesamt“ |
| Alle Sportarten im Filter | „Alle Sportarten“ | „Alle“, „alle Sportarten“ |
| Verbindung zu einem Dienst beenden | „Verbindung trennen“; Zustand „Verbunden mit …“ | „Trennen“, „Abmelden“, „Angemeldet als“ |

## 2. Bedienlogik: eine Regel je Muster

1. **Dialogknöpfe:** links „Abbrechen“ (unauffällig), rechts die Hauptaktion (hervorgehoben, bei Gefahr rot). Die Hauptaktion nennt, was passiert: „Speichern“, „Löschen“, „Exportieren“, „Holen“. Nicht mehr: „OK“, „Übernehmen“, „Anwenden“. „Fertig“ nur zum Verlassen eines Modus ohne Speichern-Schritt (Filter, „Seite anpassen“). Jedes Bearbeiten-Blatt hat „Abbrechen“ und „Speichern“ (nicht nur ✕). Keine Browser-Fenster (`prompt`, `confirm`, `alert`), nur eigene Dialoge.
2. **Löschen und Entfernen:** „Löschen“ = Daten sind weg; „Entfernen“ = nur eine Zuordnung endet (Tour aus Album, Sportart aus Gruppe). Löschen fragt immer nach: Titel als Frage mit Fragezeichen und dem Namen der Sache, Knopf „Löschen“ (rot). Der Text sagt, was verloren geht und ob es sich zurückholen lässt. Entfernen fragt nicht nach, bietet aber wo möglich „Rückgängig“ an.
3. **Zurücksetzen:** heißt überall „Standard wiederherstellen“, mit Rückfrage.
4. **Speichern in Einstellungen:** Schalter und Auswahlen speichern sofort; Texteingaben und Listen-Editoren (Gruppen, Favoriten, Ziele) haben „Speichern“. Innerhalb eines Bereichs nur ein Weg. Meine Touren behält die Leiste „Einstellungen speichern“ für die Formularfelder der Verwaltung; was sofort speichert, steht dort nicht in demselben Abschnitt wie Felder, die die Leiste brauchen, oder ist als „wird sofort gespeichert“ gekennzeichnet.
5. **Rückmeldungen:** Erfolg „<Sache> gespeichert“ (ohne ✓, ohne Punkt; ebenso „gelöscht“, „exportiert“, „geholt“, „wiederhergestellt“). Fehler „<Vorgang> nicht möglich: <Grund>“. Läuft schon: „<Vorgang> läuft schon“. Im Tagebuch als Toast, in Meine Touren als Meldung an der Stelle der Aktion.
6. **Sportart wählen ★, zwei feste Muster:** *Filtern* (Statistik, Karte, Tourenliste, Bausteine): Chips, zuerst „Alle Sportarten“, dann die Statistik-Gruppen, dann die Sportarten in Katalog-Reihenfolge mit Kategorie-Überschrift, nur Sportarten mit Touren, Farbpunkt = Streckenfarbe. *Zuweisen* (Tour, Ziel, Planung, Aufzeichnen): Favoriten-Sportarten zuerst, dann „Mehr …“ mit allen Sportarten nach Kategorien; die zuletzt benutzte ist vorgewählt. Je Muster eine gemeinsame Funktion.
7. **Zeitraum wählen:** überall dieselbe Liste und Reihenfolge: „Gesamte Zeit“, dann die Jahre absteigend (dazu, wo vorhanden, „Letzte 12 Monate“, „Letzte 90 Tage“, „Eigener Zeitraum“).
8. **Wiederkehrende Aktionen an einer Tour:** gleiche Namen und Reihenfolge in Knopfleiste und Menü: Bearbeiten, Schlagwörter & Alben, Teilen, Exportieren, Löschen (zuletzt, rot). Menüpunkte, die einen weiteren Dialog öffnen, enden auf „ …“.
9. **Wegangaben in Hinweisen:** „Verwaltung → <Reiter> → <Bereich>“ bzw. „Mehr → Einstellungen → <Bereich>“, mit genau den Namen, die dort stehen.
10. **Schreibweisen:** Auslassung „ …“ (mit Leerzeichen davor), Anführungszeichen „…“, Pfeil „→“. Knöpfe beginnen groß. Einheiten und Datum nur über die zentrale Formatfunktion: km, m, „Std.“ und „Min.“; Datum TT.MM.JJJJ, auch bei Eingaben. Mehrzahl ausschreiben statt „Foto(s)“. Symbole an Knöpfen: je App ein System (Tagebuch SVG-Symbole, keine Emoji in Knöpfen; Meine Touren wie bisher, aber dieselbe Aktion immer mit demselben Symbol).

## 3. Regeln für künftige Änderungen
- Neue Texte prüfen: steht die Sache in Tabelle 1, gilt das Wort dort.
- Beide Apps bekommen für dieselbe Funktion denselben Namen und dasselbe Bedienmuster.
- Je App prüft ein Test die verbotenen Wörter aus Tabelle 1 in sichtbaren Texten (mit einer kurzen Ausnahmeliste für Dienstnamen).
