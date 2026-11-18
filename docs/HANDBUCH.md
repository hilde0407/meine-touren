# Meine Touren – Handbuch

**Für Anwenderinnen und Anwender · Stand: Version 3.33.0**

Dieses Handbuch erklärt Schritt für Schritt, wie du mit **Meine Touren** arbeitest: Touren holen und importieren, ansehen, auswerten, mit Fotos verbinden, die Seiten nach deinem Geschmack gestalten und Links sicher teilen. Es richtet sich an Menschen, die die App benutzen – nicht an Entwickler.

* Eine kürzere Fassung mit Bildern findest du in der [Kurzanleitung](ANLEITUNG.md), die Installation steht ausführlich in der [README](../README.md).
* Dieses Handbuch gibt es auch als **PDF**: [Handbuch-Meine-Touren.pdf](Handbuch-Meine-Touren.pdf).
* Alle Bilder zeigen **Beispieldaten** (Demo-Modus, erfundene Touren). Die Texte auf den Knöpfen sind so geschrieben, wie du sie in der App siehst.

> **Hinweis zu den Bildern:** In den Aufnahmen fehlen die Kartenkacheln (OpenStreetMap), deshalb ist der Kartenhintergrund grau. In der echten App siehst du dort die Karte. Die Fotos der Beispieltouren sind einfache Farbverläufe mit Bergsilhouette.

<a id="inhalt"></a>

## Inhaltsverzeichnis

1. [Einführung und Überblick](#k1)
2. [Installation und Start](#k2)
3. [Erste Schritte: Konto, Rollen, Sprache, Hell und Dunkel](#k3)
4. [Touren importieren und holen](#k4)
5. [Die Übersicht](#k5)
6. [Touren-Liste, Filter und Suche](#k6)
7. [Das Tourdetail](#k7)
8. [Die Karte](#k8)
9. [Reisen und Mehrtagestouren](#k9)
10. [Fotos und Diashow](#k10)
11. [Statistik, Rekorde, Puls und Auswertung](#k11)
12. [Der Jahresrückblick](#k12)
13. [Seiten anpassen: Bausteine, Ansichten, Vorlagen, eigene Kennzahlen](#k13)
14. [Freigabe und Teilen](#k14)
15. [Die Verwaltung](#k15)
16. [Die Android-App](#k16)
17. [Mein Tourentagebuch (Begleit-App)](#k17)
18. [Tipps, Tastenkürzel, Fehlersuche und häufige Fragen](#k18)
19. [Datenschutz und Sicherheit](#k19)
20. [Glossar](#glossar)

---

<a id="k1"></a>

## 1. Einführung und Überblick

**Zweck:** Meine Touren ist dein **privates Tourenarchiv zum Selbsthosten**. Wanderungen, Radtouren, Läufe und andere Aktivitäten liegen bei dir – auf deinem Rechner, Server oder NAS – mit Karte, Höhenprofil, Statistik und Fotos. Es gibt keine Cloud, in der deine Daten liegen müssen.

**Was die App kann (Auswahl):**

* Touren aus Dateien (GPX, FIT, TCX, ZIP) und aus Zepp, Garmin, Suunto und anderen Uhren übernehmen, dazu Komoot-Touren. Strava und Komoot kannst du auch zum Hochladen nutzen – aber nur, wenn du das ausdrücklich willst.
* Jede Tour mit Karte, Höhenprofil, Fotos entlang der Strecke, Pulsverlauf, Geschwindigkeit, Tourblatt (PDF) und 3D-Flug.
* Fotos automatisch über die Aufnahmezeit den Touren zuordnen, Diashow, Erinnerungen.
* Statistik, Rekorde, Pulszonen, Jahresziele, Jahresrückblick.
* Reisen und Mehrtagestouren werden erkannt und bekommen eine eigene Seite samt Reisebericht.
* **Alle Seiten sind anpassbar** („Seite anpassen“): Bausteine verschieben, ausblenden, in der Breite ändern, hinzufügen; mehrere Ansichten und Vorlagen; eigene Kennzahlen.
* Teilen per Link ohne Konto – du bestimmst, was gezeigt wird, und kannst jeden Link widerrufen.
* Mehrere Benutzer mit getrennten Daten, Oberfläche auf Deutsch, Englisch, Französisch und Spanisch, Hell- und Dunkeldarstellung, Handy-Ansicht, Android-App.

**Aufbau der Oberfläche:** Oben steht die Menüleiste mit **Übersicht · Karte · Touren · Reisen · Fotos · Statistik**, dazu das Suchfeld („Suchen … ( / )“), das Zahnrad für die **Verwaltung**, das Benutzermenü und die Sprachauswahl.

![Übersicht mit Menüleiste, letzter Tour, „Dein Jahr“ und Erinnerungen](handbuch/bilder/01-uebersicht.png)

*Abbildung 1: Die Übersicht. Oben die Menüleiste, darunter „Zuletzt unterwegs“, „Dein Jahr 2026“, der Bereich „Touren holen“, die letzten Touren und „Erinnerungen“.*

**Tipp:** Wenn du erst einmal nur schauen willst, was die App kann: Der **Demo-Modus** (siehe [Kapitel 2](#k2)) legt Beispieltouren an, ohne deine echten Daten anzufassen.

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k2"></a>

## 2. Installation und Start

**Zweck:** Meine Touren läuft als kleiner Webserver. Du öffnest ihn im Browser. Wie du ihn installierst, hängt davon ab, wo er laufen soll. Die vollständigen Befehle stehen in der [README](../README.md) – hier der Überblick.

| Wo soll es laufen? | Kurz gesagt | Wo steht die Anleitung? |
|---|---|---|
| **Proxmox VE** (empfohlen) | Ein Befehl auf dem Proxmox-Host legt einen Debian-Container an und installiert alles. Danach `http://<Container-IP>/` öffnen. | README: „Installation auf Proxmox VE“ |
| **Debian/Ubuntu-Server** | Repository holen, `bash deploy/install.sh` ausführen. Erreichbar unter `http://<IP>/` bzw. `http://<IP>:8080/`. | README: „Manuelle Installation“ |
| **Docker** (auch Raspberry Pi, Synology, QNAP) | `docker-compose.yml` kopieren, `docker compose up -d`, dann `http://<Server>:8080` öffnen. Die Daten liegen im Ordner `./daten`. | README: „Docker“ |
| **NAS (TrueNAS SCALE)** | Als „Custom App“ mit der Compose-Datei; ausführliche Schritte inklusive Tailscale und Zwei-Faktor-Anmeldung. | [docs/truenas-scale.md](truenas-scale.md) |
| **Windows-PC** | Python installieren, im Ordner `windows` die Datei `Meine-Touren-lokal.bat` doppelklicken. Der Browser öffnet `http://localhost:8080`. | README: „Lokal auf Windows“ |
| **Mac** | Im Ordner `mac` die Datei `Meine-Touren-lokal.command` doppelklicken (beim ersten Mal Rechtsklick → Öffnen). | README: „Lokal auf dem Mac“ |

**Der erste Start:**

1. Öffne die Adresse deiner Installation im Browser.
2. Beim ersten Besuch legst du den **Administrator** an (Name, E-Mail-Adresse, Passwort mit mindestens 8 Zeichen) – siehe [Kapitel 3](#k3).
3. Lade deine ersten Touren: [Kapitel 4](#k4).

**Ausprobieren ohne eigene Daten (Demo-Modus):** Unter Windows startet `windows\Meine-Touren-Demo.bat`, auf dem Mac `mac/Meine-Touren-Demo.command` die App mit Beispieltouren und -fotos; auf anderen Systemen geht es mit `MT_DEMO=1 python3 -m app.demo`. Die Beispieldaten liegen in einem temporären Ordner; echte Daten werden nie angefasst. In der Verwaltung erscheint dann der Hinweis „Demo-Modus: Alle Touren und Fotos hier sind Beispieldaten.“

**Aktualisieren:**

* Proxmox: im Container `meine-touren-update github` oder auf dem Host das Skript erneut starten und „Update“ wählen.
* Docker: `docker compose pull && docker compose up -d`.
* Windows und Mac: Updates lassen sich in der Oberfläche installieren; die App startet danach selbst neu (Windows) bzw. es gibt `Meine-Touren-aktualisieren.command` (Mac).
* Vor jedem Update legt die App automatisch eine Sicherung an. Mehr dazu in [Kapitel 15](#k15).

**Von außen erreichbar machen:** Für den Zugriff von unterwegs empfiehlt die README **Tailscale** (privates Netz, kein offener Router-Port). Mehr dazu in [Kapitel 19](#k19).

**Hinweis:** Fehlt das Internet, funktionieren die Seiten weiter, es fehlen aber Kartenkacheln, Höhen- und Wetterdaten sowie Ortsnamen (siehe [Kapitel 19](#k19)).

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k3"></a>

## 3. Erste Schritte: Konto, Rollen, Sprache, Hell und Dunkel

### 3.1 Benutzer einrichten

Solange noch keine Benutzerverwaltung eingerichtet ist, zeigt das Benutzermenü oben rechts „Noch keine Benutzerverwaltung“. Dann ist die Oberfläche für jeden im Netzwerk offen. Für den Alltag solltest du die Benutzerverwaltung einschalten.

1. Klicke oben rechts auf **Benutzer**.
2. Wähle **Benutzer einrichten …**.
3. Trage Name, E-Mail-Adresse und Passwort ein (mindestens 8 Zeichen, zweimal). Die E-Mail-Adresse dient zum Zurücksetzen des Passworts.
4. Klicke auf **Einrichten**. Mit **Später** schließt du den Dialog, ohne etwas zu ändern.

![Benutzermenü mit „Benutzer einrichten …“](handbuch/bilder/43-benutzermenue.png)

*Abbildung 2: Das Benutzermenü, solange noch kein Konto eingerichtet ist.*

![Dialog „Benutzerverwaltung einrichten“](handbuch/bilder/44-benutzer-einrichten.png)

*Abbildung 3: „Benutzerverwaltung einrichten“. Du legst jetzt den ersten Benutzer an; er wird Administrator. Alle bisherigen Touren, Fotos und Einstellungen gehören danach ihm.*

Wenn du dich später anmeldest, ersetzt das Benutzermenü diese Einträge durch „Konto & Freigaben“, „Geteilte Fotos“, „Info“ und „Abmelden“.

### 3.2 Rollen

Es gibt drei Rollen:

| Rolle | Darf … |
|---|---|
| **Administrator** | alles, auch Benutzer anlegen und verwalten, Updates installieren. |
| **Benutzer** | seine eigenen Touren, Fotos, Notizen, Ziele und Einstellungen verwalten. Jeder Benutzer hat eigene Daten und sein eigenes Komoot-Konto. |
| **Betrachter** („nur ansehen“) | die Touren, Fotos, Reisen, Auswertungen und die Karte eines gewählten Benutzers ansehen, aber nichts ändern, nichts hochladen und keine Links erzeugen. |

Administratoren legen Benutzer unter **Konto & Freigaben → Benutzer verwalten → Neuer Benutzer** an (Name, E-Mail, Passwort, Rolle). Dort können sie auch Passwörter setzen, E-Mail-Adressen ändern und die Zwei-Faktor-Anmeldung zurücksetzen.

### 3.3 Konto & Freigaben

Im Benutzermenü findest du **Konto & Freigaben**. Dort:

* **Passwort ändern.**
* **Zwei-Faktor-Anmeldung** ein- oder ausschalten (QR-Code mit einer Authenticator-App scannen, danach werden einmalig acht Wiederherstellungscodes angezeigt – gut aufbewahren).
* **Ansicht:** Automatisch, Smartphone-Ansicht oder Computer-Ansicht (gilt nur auf diesem Gerät).
* **Fotos freigeben:** Andere Benutzer dürfen deine ganze Fotobibliothek oder nur die Fotos einer Tour sehen und in ihre Bibliothek übernehmen. Deine Originale bleiben bei dir.

Auf der Anmeldeseite gibt es **Passwort vergessen?**. Das funktioniert, wenn der Administrator unter *Verwaltung → Automatik & Meldungen* den E-Mail-Versand eingerichtet hat.

### 3.4 Sprache

Oben rechts wählst du die Sprache: **DE**, **EN**, **FR** oder **ES**. Die Wahl gilt sofort.

### 3.5 Hell und Dunkel

Die App folgt der **Einstellung deines Geräts** (hell oder dunkel). Einen eigenen Schalter dafür gibt es nicht – stelle am Rechner oder Handy die Darstellung um, und die App zieht nach.

![Dunkle Darstellung der Übersicht](handbuch/bilder/51-dunkelmodus-uebersicht.png)

*Abbildung 4: Dieselbe Übersicht in der dunklen Darstellung.*

![Dunkle Darstellung des Tourdetails](handbuch/bilder/52-dunkelmodus-tour.png)

*Abbildung 5: Das Tourdetail im Dunkelmodus.*

### 3.6 Smartphone- oder Computer-Ansicht

Bis zu einer Breite von etwa 760 Pixeln schaltet die App automatisch in die Handy-Ansicht (Menü unten am Rand). Du kannst das unter „Konto & Freigaben → Ansicht“ oder im Menü **Mehr** (Handy) festlegen. Mehr dazu in [Kapitel 18](#k18).

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k4"></a>

## 4. Touren importieren und holen

**Zweck:** Deine Touren kommen aus vielen Quellen. Alles, was du holst, wird **lokal** als Tour gespeichert (Karte, Statistik, Fotozuordnung), mit Prüfung auf Doppelte. Hochgeladen wird nie von allein.

Alle Wege findest du unter **Verwaltung → Touren holen** („Woher deine Touren kommen: Komoot, Zepp, Uhren und Dateien, dazu Wanderführer.“).

![Verwaltung, Reiter „Touren holen“](handbuch/bilder/38-verwaltung-touren-holen.png)

*Abbildung 6: Der Reiter „Touren holen“ mit „Meine Geräte“, Komoot, Zepp-Import, „Garmin, Suunto & andere Uhren“ und „Wanderführer“.*

### 4.1 Dateien importieren (funktioniert für jeden Hersteller)

1. *Verwaltung → Touren holen* und nach unten zu **Garmin, Suunto & andere Uhren (Import)** gehen, Bereich **Dateien importieren**.
2. **Choose Files** (bzw. „Dateien auswählen“, je nach Browsersprache) anklicken und eine oder mehrere **FIT-, GPX-, TCX- oder ZIP-Dateien** wählen. Eine ZIP-Datei darf viele Aktivitäten enthalten, auch den kompletten Garmin-Export.
3. Optional: **Probelauf** ankreuzen – dann wird nur geprüft und berichtet, nichts gespeichert.
4. **Importieren** anklicken.

Dateien ohne GPS (Schlaf, Alltag, Indoor) werden übersprungen und gezählt. Doppelte werden erkannt.

![Bereich „Garmin, Suunto & andere Uhren“ mit Anleitung „So kommst du an die Dateien“](handbuch/bilder/40-import-dateien.png)

*Abbildung 7: Der Datei-Import samt aufgeklapptem Abschnitt „So kommst du an die Dateien“. Rechts neben der Dateiauswahl stehen die Haken „Komoot“ und „Strava“ (zusätzlich dorthin hochladen) – sie sind nur auswählbar, wenn das jeweilige Konto verbunden ist.*

**So kommst du an die Dateien** (laut Hinweis in der App):

* **Garmin, alles auf einmal:** auf garmin.com/account/datamanagement „Daten exportieren“ anfordern; Garmin schickt nach ein bis zwei Tagen eine ZIP-Datei per E-Mail. Diese ZIP importierst du.
* **Garmin, einzelne Aktivität:** connect.garmin.com → Aktivität öffnen → Zahnrad → „Original exportieren“ (FIT in einer ZIP) oder „Als GPX exportieren“.
* **Suunto:** Suunto-App → Training öffnen → ⋮ → Exportieren → FIT (alle Daten) oder GPX. Trainings ohne GPS lassen sich nur als FIT exportieren und werden hier übersprungen.
* **Andere Hersteller** (Polar, Coros, Wahoo, Amazfit …) exportieren ebenfalls FIT oder GPX – das geht genauso. Für Polar gibt es keine Konto-Anbindung, nur den Dateiweg.
* **Sehr große ZIP-Dateien** (über 1 GB): statt Hochladen in den Eingangsordner `inbox/touren` legen. Sie werden automatisch übernommen und danach nach „erledigt“ verschoben.
* **Handy-Aufzeichnung:** Die Android-App sendet Aufzeichnungen selbst; GPX/FIT/TCX/ZIP aus anderen Apps schickst du über das Teilen-Menü (siehe [Kapitel 16](#k16)).

### 4.2 Zepp (Amazfit)

Unter **Zepp-Import (optional)** holst du GPS-Trainings aus deinem Zepp-Konto (als GPX). Ausgewählte Trainings werden lokal als Tour gespeichert.

1. Klappe **Zepp-Zugang / Token holen** auf.
2. Trage E-Mail und Passwort ein (nur wenn dein Konto ein Zepp-Passwort hat) oder ein **Token** (für Mi-, Google- und Apple-Konten). Für das Token gibt es dort eine Anleitung mit einem Lesezeichen, das du in die Lesezeichenleiste ziehst.
3. Speichere die Einstellungen und klicke auf **Zepp-Import starten**.

Weitere Knöpfe im selben Bereich: **Höhenmeter neu berechnen**, **Puls nachladen**, **Touren den Uhren zuordnen**, **Messwerte nachladen**, **Höhe aus Uhr abgleichen**. Der Zepp-Token wird täglich mitgeprüft.

### 4.3 Garmin- und Suunto-Konto (experimentell)

* **Garmin-Konto:** Anmeldung wie im Browser über ein optionales Zusatzpaket (`garminconnect`, braucht Python 3.12 oder neuer). Ist es nicht installiert, steht dort „Nicht verfügbar“ – dann bleibt der Dateiweg.
* **Suunto-Konto:** Suunto vergibt seinen Cloud-Zugang nur an Firmen und Organisationen. Wer keinen hat, nutzt den Dateiweg.
* Ist deine Uhr in Garmin Connect oder der Suunto-App mit **Komoot** verbunden, kommen die Touren ohnehin über „Komoot aktualisieren“.

> Garmin und Suunto sind bisher nur mit nachgebauten Testdaten geprüft, nicht mit echten Geräten. Rückmeldungen sind willkommen (siehe README, „Hilfe gesucht“).

### 4.4 Komoot

Im Bereich **Komoot (optional)** trägst du E-Mail und Passwort ein.

* **Komoot aktualisieren** lädt neue Touren und deren Strecken und liest die Fotos ein.
* **Nur Touren**, **Strecken lokal sichern**, **Regionen bestimmen** und **Komoot-Test** sind Teilschritte.
* Es wird nichts zu Komoot hochgeladen und nie etwas dort gelöscht.

Komoot und Zepp bieten Privatpersonen keine offizielle Schnittstelle; die Anbindungen nutzen inoffizielle Aufrufe und können sich jederzeit ändern.

### 4.5 Der Knopf „Touren holen“ auf der Übersicht

Auf der Übersicht gibt es den Bereich **Touren holen** und oben in der Kopfzeile einen Schnell-Knopf. Beschriftung und Funktion richten sich nach den Konten, die du verbunden hast:

* Ist **Zepp**, **Garmin** oder **Suunto** verbunden, heißt der Knopf z. B. „Zepp-Import starten“, „Garmin-Import starten“ oder „Suunto-Import starten“. Bei mehreren Konten gibt es je Konto eine Zeile und **Alle holen** (nacheinander, nie gleichzeitig). Fortschritt („Tour 3 von 12“) und Ergebnis des letzten Laufs werden angezeigt.
* Ist ein Gerät angelegt, aber das Konto noch nicht verbunden, heißt der Knopf z. B. **Zepp einrichten** und führt in die Verwaltung (so wie in Abbildung 1).
* Für **Polar**, Handy-Aufzeichnung und andere Geräte ohne Konto-Anbindung steht nur ein Link „Touren per Datei importieren“.
* Den Schnell-Knopf in der Kopfzeile kannst du unter „Seite anpassen“ (nur Übersicht) mit dem Schalter „Schnell-Knopf zum Touren holen in der Kopfzeile“ abschalten. Es gibt außerdem den Baustein „Touren-Knopf“ für das Raster.

### 4.6 Meine Geräte

Ganz oben in „Touren holen“ stehen **Meine Geräte**: deine Uhren und Handys mit eigenem Namen. Der Name erscheint bei jeder Tour als „Quelle“; welche Messwerte eine Tour zeigt, richtet sich danach, was das Gerät wirklich geliefert hat. Mit **+ Gerät anlegen**, **Geräte aus Zepp ermitteln** und **Touren automatisch zuordnen** richtest du das ein; **Genauigkeit auswerten** meldet auffällige Touren.

### 4.7 Wanderführer

Unter **Wanderführer (z. B. Rother)** lädst du die GPX-Dateien deiner Wanderführer hoch. Folgt eine Tour einer dieser Strecken, wird der Tourtitel aus dem Buch beim Umbenennen vorgeschlagen.

### 4.8 Hochladen (nur auf deinen Wunsch)

Der Reiter **Hochladen & Planen** nimmt die Zugänge zu **Strava** (eigene App anlegen, Client-ID und -Secret eintragen, „Mit Strava verbinden“) und Komoot auf. Hochgeladen wird einzeln (Tour → **Bearbeiten → Hochladen**) oder gesammelt, immer nur ausdrücklich. Dort stellst du auch die **Tourplanung** ein (Routing über einen BRouter-Dienst; öffentlich, auf dem eigenen Server oder im Netz).

### 4.9 Fotos importieren

Fotos kommen separat – siehe [Kapitel 10](#k10).

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k5"></a>

## 5. Die Übersicht

**Zweck:** Die Startseite zeigt auf einen Blick, wo du zuletzt warst und wie dein Jahr läuft.

Von oben nach unten (in der Standardeinstellung):

1. **Zuletzt unterwegs:** die letzte Tour mit Strecke, Kilometern, Höhenmetern, Dauer und – wenn vorhanden – dem Puls. Mit den Pfeilen blätterst du durch die jüngsten Touren. **Tour ansehen** öffnet das Tourdetail, **3D-Flug** fliegt die Strecke im Gelände ab.
2. **Dein Jahr 2026:** Touren, Kilometer, Höhenmeter und Stunden mit Monatssäulen und Vergleich zum Vorjahr bis zum selben Tag („–17 % gegenüber 2025 bis heute“). Darunter stehen deine Jahresziele mit Fortschritt (z. B. „243 / 400 km“). **Zur Statistik** führt weiter.
3. **Touren holen:** der Import-Bereich ([Abschnitt 4.5](#k4)).
4. **Zuletzt unterwegs:** Kacheln der letzten Touren; **Alle 27 Touren** öffnet die Liste.
5. **Erinnerungen:** eine Auswahl deiner Fotos mit Link **Zufalls-Diashow**.

Über **Seite anpassen** und **Ansichten** gestaltest du die Übersicht selbst ([Kapitel 13](#k13)).

![Übersicht](handbuch/bilder/01-uebersicht.png)

*Abbildung 8: Die Übersicht (siehe auch Abbildung 1).*

**Hinweis-Bausteine:** Im Katalog gibt es Bausteine, die sich nur zeigen, wenn es einen Anlass gibt – etwa „Jahresziel in Gefahr“, „Meilenstein erreicht“, „Lange Pause“, „Rekord-Tour“, „Wochenziel“, „Erholungshinweis“ oder „Datensicherung“. Ist nichts los, sind sie unsichtbar und brauchen keinen Platz.

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k6"></a>

## 6. Touren-Liste, Filter und Suche

**Zweck:** Alle Aktivitäten in einer sortier- und filterbaren Liste.

**Schritt für Schritt:**

1. Klicke in der Menüleiste auf **Touren**.
2. Jede Zeile zeigt Streckenform, Name, Datum, Sportart, Fotos, Bewertung sowie Kilometer, Höhenmeter („m auf“) und Dauer („Std.“). Ein Klick öffnet die Tour.
3. Oben filterst du:
   * **Name suchen** – Textfeld,
   * **Alle Jahre**, **Alle Sportarten**,
   * Zeitraum im Jahr: **Ganzjährig**, **Sommerhalbjahr (Mai–Okt)** oder Winterhalbjahr,
   * **Alle Bewertungen** (ab ★★★★★, ★★★★ …),
   * **Alle Regionen**, **Alle Tags**,
   * Sortierung: **Neueste zuerst**, Älteste zuerst, Längste Strecke und weitere.
4. **Tour planen** öffnet die Tourplanung (Voraussetzung: die Funktion ist unter *Verwaltung → Hochladen & Planen* eingeschaltet).

![Touren-Liste](handbuch/bilder/02-touren-liste.png)

*Abbildung 9: Die Liste aller Touren.*

![Filter der Touren-Liste hervorgehoben](handbuch/bilder/03-touren-filter.png)

*Abbildung 10: Die Filter (rot umrandet) – hier ist „Wandern“ gewählt, daher steht oben „24 Touren, 416 km“.*

### Die Suche

Das Suchfeld ganz oben („Suchen … ( / )“) durchsucht Tournamen, Notizen, Sportart, Datum, Monat, Jahr, Orte, Landkreis, Bundesland, Land und Tags. Drücke die Taste **/**, um es sofort anzuspringen.

Die Suche ist **akzent- und apostroph-unabhängig**: „reunion“ findet „Réunion“, „strasse“ findet „Straße“, „munstertal“ findet „Münstertal“. Das gilt für das Suchfeld der Kopfzeile, den Namensfilter der Liste, die Auswertung nach Regionen und die Bausteine-Suche in „Seite anpassen“.

![Suchergebnis für „munstertal“](handbuch/bilder/53-suche-ohne-akzente.png)

*Abbildung 11: „munstertal“ ohne Umlaut findet „Herbstwanderung Münstertal“.*

![Namensfilter „Dolomiten“ in der Liste](handbuch/bilder/04-touren-suche.png)

*Abbildung 12: Der Namensfilter der Liste („Dolomiten“) zeigt die fünf Etappen der Hüttenwanderung.*

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k7"></a>

## 7. Das Tourdetail

**Zweck:** Alles zu einer Tour an einem Ort. Das Beispiel hier ist „Dolomiten Tag 3 Rosengarten – Sella“.

### 7.1 Kopf, Kennzahlen, Notiz, Bewertung

Oben stehen Sportart, Datum und Name. Rechts oben gehst du mit **Vorherige** und **Nächste** durch die Touren. Darunter:

* drei Knöpfe: **Ansehen**, **Teilen & Export**, **Bearbeiten** (Abschnitt 7.7),
* eine Marke wie „lokal gespeichert“,
* ein Feld **Notiz zur Tour** (Wetter, Begleitung, Einkehr …) – du tippst, es wird gespeichert,
* **Tags** und – bei Mehrtagestouren – ein Hinweis mit Link zur Gesamtansicht,
* **Meine Bewertung** mit fünf Sternen (das ✕ löscht sie),
* die **Kennzahlen**: Strecke, Aufstieg, Abstieg, Dauer, Tempo im Schnitt, Höchster Punkt, Neuland.

![Tourdetail, oberer Teil](handbuch/bilder/05-tour-oben.png)

*Abbildung 13: Der obere Teil des Tourdetails.*

### 7.2 Karte

Der Abschnitt **Karte** zeigt die Strecke mit Start (grün) und Ziel (rot) und Fotos als Marker. Darüber stehen Gehzeit, Pausen, Steigrate und steilster Abschnitt. Mit **+/−** zoomst du, mit dem Schichten-Symbol wechselst du die Kartenart, und **Steigung** färbt die Strecke nach Steilheit.

![Karte der Tour](handbuch/bilder/06-tour-karte.png)

*Abbildung 14: Der Abschnitt „Karte“ (die Kartenkacheln fehlen in dieser Aufnahme).*

### 7.3 Höhenprofil

Das **Höhenprofil** zeigt die Höhe über der Strecke. Die **gelben Punkte** sind Fotos – anklicken öffnet sie. Hat die Tour Pulsdaten, liegt der Puls als rote Linie darüber.

![Höhenprofil mit Fotopunkten und Puls](handbuch/bilder/07-tour-hoehenprofil.png)

*Abbildung 15: Höhenprofil mit Foto-Punkten (gelb) und Puls (rot).*

### 7.4 Puls

Der Abschnitt **Herzfrequenz** erscheint, wenn das Gerät den Puls geliefert hat: Durchschnitt, Maximum, Minimum, Verlauf und die **Pulszonen** Z1 bis Z5 (Sehr leicht, Leicht, Moderat, Hart, Maximal) mit den Zeiten je Zone. Die Zonen richten sich nach deinem Maximalpuls (Standard 185 bpm; einstellbar unter *Verwaltung → Übersicht → Heimatort und Puls*).

![Herzfrequenz mit Pulszonen](handbuch/bilder/08-tour-puls.png)

*Abbildung 16: Herzfrequenz und Pulszonen.*

### 7.5 Geschwindigkeit und Auswertung dieser Tour

Unter **Auswertung dieser Tour** findest du **Analyse** (Bewegungszeit, Pausen), **Tempo nach Steigung** (bergauf, eben, bergab) und **Messwerte**. **Detaillierte Auswertung ansehen ›** öffnet die Seite mit allen Messwerten, z. B. dem **Geschwindigkeitsverlauf** (Ø, Ø in Bewegung, Maximum) und dem Tempo (Pace). Ein Stern (*) hinter einem Wert bedeutet: aus GPS-Strecke und Zeit berechnet, kein Messwert des Geräts. Welche Messwerte da sind, hängt vom Gerät ab.

![Detaillierte Auswertung einer Tour](handbuch/bilder/17-tour-auswertung.png)

*Abbildung 17: Die detaillierte Auswertung mit dem Geschwindigkeitsverlauf. Mit „Ändern“ legst du fest, womit die Tour aufgezeichnet wurde.*

### 7.6 Fotos der Tour

Der Abschnitt **Fotos** zeigt die der Tour zugeordneten Fotos mit Uhrzeit. Die Knöpfe:

* **Fotos bearbeiten**,
* **Fotos hinzufügen …**,
* **Zeit per GPS prüfen** (korrigiert falsche Kamerauhren),
* **⭐ Beste Fotos**,
* **Fotos ausrichten** (Perlenkette, siehe [Kapitel 10](#k10)),
* **Diashow**.

![Fotos der Tour](handbuch/bilder/09-tour-fotos.png)

*Abbildung 18: Fotos der Tour mit ihren Knöpfen.*

### 7.7 Die drei Menüs: Ansehen, Teilen & Export, Bearbeiten

**Ansehen** bietet:

* **Erzählung** – Zeitleiste mit Wegpunkten, Fotos und Kommentaren (mit **Teilen (mit Kommentaren)** und **Drucken**),
* **3D-Flug** – die Strecke im 3D-Gelände abfliegen,
* **Tourblatt** – druckbare Seite mit Karte, Profil und Fotos (**PDF herunterladen**, **Drucken**, Haken „Fotos im PDF“).

![Menü „Tour ansehen“](handbuch/bilder/10-menue-ansehen.png)

*Abbildung 19: Das Menü „Tour ansehen“.*

![Erzählung der Tour](handbuch/bilder/14-tour-erzaehlung.png)

*Abbildung 20: „Erzählung“: Start, Fotos mit Uhrzeit und Puls, Ziel.*

![Tourblatt](handbuch/bilder/15-tourblatt.png)

*Abbildung 21: Das Tourblatt – oben die Knöpfe „PDF herunterladen“ und „Drucken“.*

> **3D-Flug:** Er braucht WebGL im Browser sowie Gelände- und Kartendaten aus dem Internet. In der Umgebung, in der die Bilder dieses Handbuchs entstanden sind, gab es diese Daten nicht; deshalb ist hier kein Bild des 3D-Flugs abgebildet.

**Teilen & Export** bietet **Link senden**, **Diashow senden**, **Diashow-Link**, **Links verwalten** und **GPX-Datei laden** (Strecke als GPX herunterladen). Mehr in [Kapitel 14](#k14).

![Menü „Teilen & Export“](handbuch/bilder/11-menue-teilen.png)

*Abbildung 22: Das Menü „Teilen & Export“.*

**Bearbeiten** bietet:

* **Umbenennen**, **Tags & Alben** (Schlagworte),
* **Streckenfarbe** (Farbe und Breite auf der Karte),
* **Höhen korrigieren** (mit Geländemodell neu berechnen), **Höhe aus Uhr abgleichen (Zepp)**,
* **Track korrigieren** (Fehlpunkte und Pausen bereinigen; das Original bleibt erhalten),
* **Hochladen** (zu Strava, Komoot … – nur auf deinen Wunsch),
* **Tour löschen** (rot, abgesetzt; entfernt die Tour nur aus Meine Touren).

![Menü „Tour bearbeiten“](handbuch/bilder/12-menue-bearbeiten.png)

*Abbildung 23: Das Menü „Tour bearbeiten“.*

### 7.8 Tourseite selbst gestalten

Auch das Tourdetail besteht aus Bausteinen. Unter den Kennzahlen stehen **Seite anpassen** und **Ansichten** – siehe [Kapitel 13](#k13).

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k8"></a>

## 8. Die Karte

**Zweck:** Alle Touren auf einer Karte – zum Beispiel, um zu sehen, wo du überall warst.

Oben schwebt eine Leiste mit Bedienelementen:

* **Standort** – zeigt deine Position (Browser fragt nach Erlaubnis),
* **Alle Jahre** – Jahr wählen, daneben die Zahl der Touren,
* **Wandern / Radtour …** – Sportarten ein- und ausschalten (jede hat ihre Farbe),
* **Strecken**, **Heatmap**, **Fotos** – Darstellungsarten: Strecken einzeln, Heatmap (Häufigkeit), Fotos als Marker (bei Fotos ohne eigenen Aufnahmeort wird die Position aus der Aufnahmezeit berechnet und blasser gezeigt),
* **Touren im Ausschnitt** – listet die Touren des gerade sichtbaren Kartenausschnitts.

![Karte mit allen Touren](handbuch/bilder/18-karte.png)

*Abbildung 24: Alle Touren, nach Sportart gefärbt (Wandern grün, Radtour orange).*

![Karte als Heatmap mit hervorgehobenen Bedienelementen](handbuch/bilder/19-karte-optionen.png)

*Abbildung 25: Die Bedienelemente (rot umrandet); hier ist „Heatmap“ eingeschaltet.*

**Hinweis:** Karten und Tourdetails arbeiten mit den **lokal gespeicherten Strecken**; nur die Kartenkacheln kommen aus dem Internet. Für unterwegs ohne Netz kannst du Touren und Kacheln **offline vorbereiten** ([Kapitel 15](#k15)).

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k9"></a>

## 9. Reisen und Mehrtagestouren

**Zweck:** Mehrtägige Unternehmungen weit weg von zu Hause werden automatisch erkannt und als Einheit dargestellt.

### 9.1 Wann ist etwas eine Reise?

* **Reise:** Touren **weit weg von zu Hause** (mehr als etwa 60 km) an **mindestens vier Tagen** am Stück. Wochenend- und Kurzausflüge erscheinen hier nicht; sie bleiben normale Touren.
* **Heimatort:** Die App erkennt ihn selbst aus deinen Touren. Du kannst ihn unter *Verwaltung → Übersicht → Heimatort und Puls* festlegen (Ort oder Adresse suchen, „Suchen“, Treffer anklicken, „Einstellungen speichern“). Touren in der Nähe zählen dann nie als Reise.
* **Mehrtagestour:** Tourenreihen mit Namen wie „… Tag 3“ oder „… Etappe 2“ werden zusammengefasst. Mit **＋ Mehrtagestour bilden …** legst du eine selbst an.

### 9.2 Die Reisen-Übersicht

Menü **Reisen**. Die Seite besteht aus den Abschnitten **Mehrtagestouren**, **Reisen**, **Alben und Tags** und (zugeklappt) **Entfernte Reisen**. Jede Reise ist eine Kachel mit Zeitraum, Zahl der Touren, Kilometern und Höhenmetern.

![Reisen-Übersicht](handbuch/bilder/29-reisen.png)

*Abbildung 26: Die Reisen-Übersicht mit der Mehrtagestour „Dolomiten“, der Reise „Dolomiten-Hüttenweg“ und den Tags.*

> **Auffälligkeit in Version 3.33.0:** Die Kacheln für „Alben & Tags“ erscheinen derzeit unterhalb der Reisen-Kachel statt in der eigenen Karte „Alben und Tags“ (diese ist leer). Das ist ein reines Darstellungsproblem; die Inhalte sind vollständig.

### 9.3 Die Reise-Seite

Ein Klick auf die Reise öffnet die Seite mit:

* **Kennzahlen** (Touren, Strecke, Aufstieg, Abstieg, Unterwegs, Tage),
* **Statistik nach Aktivität**,
* **3D-Flug und Offline-Karte** (**3D-Flug über alles**, **Karte offline speichern**),
* **Karte** mit den Tagen in verschiedenen Farben,
* **Fotos** der Reise,
* **Touren** (Liste der Etappen).

Oben stehen **Reisebericht (PDF)**, **Senden**, **Reise bearbeiten** (Name und Zeitraum ändern) und **Keine Reise** (aus der Liste entfernen; die Touren bleiben). Die automatisch erkannte Region heißt zunächst „Reise“ oder wie das Bundesland; mit „Reise bearbeiten“ gibst du ihr einen eigenen Namen wie hier „Dolomiten-Hüttenweg“.

![Reise-Seite](handbuch/bilder/30-reise-seite.png)

*Abbildung 27: Die Reise-Seite „Dolomiten-Hüttenweg“ (fünf Tage, 80 km).*

### 9.4 Das Reiseblatt

**Reisebericht (PDF)** öffnet das Reiseblatt mit Karte, Statistik und Fotos. Dort stellst du ein, ob Fotos im PDF erscheinen und wie viele, und klickst **PDF herunterladen** oder **Drucken**.

![Reiseblatt](handbuch/bilder/31-reiseblatt.png)

*Abbildung 28: Das Reiseblatt (Reisebericht).*

### 9.5 Reisen anpassen

Reise-Seite und Reisen-Übersicht sind wie alle Seiten anpassbar ([Kapitel 13](#k13)). Zusätzliche Bausteine: Reise-Kennzahlen, Kilometer je Tag, Reise-Diashow, Reisen-Kennzahlen und Reisen je Jahr. Das Layout gilt für alle Reisen.

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k10"></a>

## 10. Fotos und Diashow

### 10.1 Fotos importieren

**Zweck:** Fotos werden über die **Aufnahmezeit** (und den Aufnahmeort, wenn vorhanden) automatisch der passenden Tour zugeordnet.

**Schritt für Schritt:**

1. Menü **Fotos → Fotos importieren …** (auch in der Verwaltung unter *Fotos* und im Tourdetail unter **Fotos hinzufügen …**).
2. Einen Ordner oder einzelne Fotos auswählen – oder einfach ins Fenster ziehen.
3. Die App zeigt **je Aufnahmetag**, welcher Tour die Fotos zugeordnet werden. Pro Tag kannst du ändern: „nach Uhrzeit“, andere Tour, „ohne Tour“ oder „nicht importieren“.
4. Starten; danach steht da, wie viele Fotos Touren zugeordnet wurden.

Die Bilder werden **im Browser verkleinert**, nur die kleinen Dateien gehen über das Netz; Originale werden nie verändert.

**Weitere Wege** (Verwaltung → Fotos): der **Foto-Eingang** – Fotos einfach in den Eingangsordner kopieren (scp, rsync oder SMB-Freigabe); sie werden automatisch verkleinert, mit Aufnahmezeit übernommen und Touren zugeordnet (Prüfung alle 5 Minuten). Dazu **Bibliothek neu einlesen** und SMB-Ordner bzw. ein Mac-Skript.

![Verwaltung, Reiter „Fotos“](handbuch/bilder/41-verwaltung-fotos.png)

*Abbildung 29: Der Reiter „Fotos“ in der Verwaltung.*

**Falsche Kamerauhr?** Beim Import erkennt die App Zeitverschiebungen an Fotos mit Aufnahmeort und bietet eine minutengenaue Korrektur an. Bei bereits importierten Fotos prüft **Zeit per GPS prüfen** im Tourdetail die Uhrzeiten und korrigiert sie nach Rückfrage. **Fotos zuordnen** auf der Fotos-Seite ordnet nachträglich zu.

### 10.2 Die Fotos-Seite

Menü **Fotos**: oben **Fotos zuordnen**, **Fotos importieren …**, **Diashow 2025** (für das gewählte Jahr) und **Zufall**. Darunter Reiter je Jahr. Die Fotos sind nach Tour gruppiert; jede Gruppe hat einen eigenen Knopf **Diashow**. Ein Klick auf ein Foto öffnet die Großansicht.

![Fotos-Seite](handbuch/bilder/20-fotos.png)

*Abbildung 30: Fotos nach Touren, Reiter für 2026 und 2025. Die Knöpfe „Diashow 2025“ und „Zufall“ sind hervorgehoben.*

![Foto in der Großansicht](handbuch/bilder/21-foto-grossansicht.png)

*Abbildung 31: Die Großansicht. Mit ← und → blätterst du, Esc schließt.*

### 10.3 Fotos auf der Strecke ausrichten („Perlenkette“)

Stimmt die Position eines Fotos nicht: Im Tourdetail auf **Fotos ausrichten** klicken, auf der Karte **ein** Foto an die Stelle ziehen, an der es sicher entstand – alle anderen Fotos wandern im gleichen zeitlichen Abstand wie auf einer Perlenkette mit. **Speichern** verschiebt die Aufnahmezeiten dauerhaft (wahlweise auch die anderen Fotos desselben Tages); **Original-Zeiten** nimmt jede Verschiebung zurück. Voraussetzung: Die Strecke enthält Zeitstempel.

### 10.4 Diashow

Die Diashow läuft im Vollbild: automatischer Wechsel (3, 5 oder 8 Sekunden), unten Tourname, Datum und Uhrzeit, Position („1/30“).

* **Leertaste:** Pause · **← →:** blättern · **F:** Vollbild.
* Auf Touchgeräten erscheinen oben rechts Knöpfe für Teilen (📤), Pause, Vollbild und Schließen; sie blenden sich aus und kommen per Tippen zurück. Wischen blättert.

![Diashow](handbuch/bilder/22-diashow.png)

*Abbildung 32: Die Diashow des Jahres 2025 (30 Fotos).*

**Diashow teilen:** In einer Tour über **Teilen & Export → Diashow senden** bzw. **Diashow-Link**; für ein ganzes Jahr oder alle Fotos über den Teilen-Knopf in der Diashow. Der Link braucht beim Empfänger **kein Konto**. Beim Tour-Link wählst du vorher, welche Fotos (alle oder nur die besten) und die Gültigkeit (7 Tage, 30 Tage, unbegrenzt). Der **Diashow-Link für ein Jahr oder alle Fotos gilt 24 Stunden** und enthält bis zu 300 der besten Fotos; abgelehnte und ausgeblendete Fotos fehlen. Der Link zeigt nur Fotos, ihre Aufnahmezeit und den Tournamen – keine Karte, keine Orte, keine Notizen, keine Strecken, keine Kommentare.

### 10.5 Erinnerungen

Die Kachel **Erinnerungen** (Übersicht und Statistik) zeigt Fotos aus deinem Archiv. Über **Seite anpassen → Erinnerungen → Einstellungen** (Zahnrad) legst du fest:

* **Welche Fotos:** zufällig, beste Fotos, „an diesem Tag in früheren Jahren“ oder neueste; optional nach Aktivität und Zeitraum gefiltert; 3, 6, 9 oder 12 Stück.
* **Darstellung:** Raster, Streifen (seitlich wischen) oder Einzelbild-Show (blättert selbst).
* **Anzeige:** Titel, Bildunterschrift, „Neu mischen“, Link „Diashow starten“.

Die Kachel lässt sich mehrfach mit unterschiedlichen Einstellungen hinzufügen.

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k11"></a>

## 11. Statistik, Rekorde, Puls und Auswertung

**Zweck:** Zahlen und Diagramme über alle deine Touren. Menü **Statistik**, vier Reiter: **Übersicht**, **Auswertung**, **Rekorde**, **Puls**.

### 11.1 Übersicht

Oben steht der **globale Filter**, der für alle Bausteine der Seite gilt:

* **Gesamt** oder ein einzelnes Jahr (2026, 2025 …),
* Zeitraum: **Laufendes Jahr**, **Letzte 12 Monate**, **Letzte 90 Tage**, **Von–bis …**,
* Aktivität: **Alle Sportarten**, **Wandern**, **Radtour** …

Daneben **Jahresrückblick 2026** ([Kapitel 12](#k12)). Die Bausteine:

* **Kennzahlen** (Touren, Strecke, Aufstieg, Unterwegs, pro Tour im Schnitt),
* **Ziele** – ein Ziel anlegen: **Ziel hinzufügen**, Messgröße (Kilometer, Höhenmeter, Touren, Stunden), Sportart, **Zielwert**, **Speichern**. Die App zeigt Fortschritt, Prognose zum Jahresende und ob du im Plan liegst,
* **Kilometer pro Jahr** (ein Klick auf einen Balken öffnet das Jahr) und **Kilometer im Jahresverlauf** (mit Vorjahreslinie),
* **Sportarten**, **Bestwerte gesamt**, **Aktivität im Jahr** (Kalender-Heatmap),
* **Dein typisches Tempo** (bergauf, eben, bergab; mit **Schätzen** für eine Tour, die du planst),
* **Erinnerungen**.

![Statistik, Übersicht](handbuch/bilder/23-statistik.png)

*Abbildung 33: Statistik → Übersicht. Der globale Filter (rot) wirkt auf alle Bausteine.*

### 11.2 Auswertung

Die Auswertung zeigt Orte, Gipfel, Leistung, Wetter und Neuland: **Häufigste Startorte** (braucht „Regionen bestimmen“ in der Verwaltung), **Gipfel & Pässe** („Gipfel bestimmen“), **Wanderführer-Fortschritt**, **Leistung über die Jahre** (Tempo, Höhenmeter pro Stunde), **Wetter** („Wetter für alle Touren laden“) und **Neuland** (Anteil der Strecke, der auf keiner früheren Tour lag; „Größte Entdeckungen“). Einige Abschnitte sind leer, bis du die genannten Auswertungen gestartet hast – sie brauchen Internet (Ortsnamen, Gipfel, Wetter).

![Statistik, Auswertung](handbuch/bilder/24-statistik-auswertung.png)

*Abbildung 34: Auswertung. In dieser Demo wurden Regionen, Gipfel und Wetter noch nicht bestimmt; die Abschnitte bieten deshalb die entsprechenden Knöpfe an.*

### 11.3 Rekorde

Rekorde mit Vergleichen („um die Erde“, „Mount Everest bergauf“), **Bestwerte gesamt** (längste Strecke, meiste Höhenmeter, längste Dauer), **Höchste Punkte**, **Nach Wochentag** und **Je Sportart**. Oben wählst du die Aktivität.

![Statistik, Rekorde](handbuch/bilder/25-statistik-rekorde.png)

*Abbildung 35: Rekorde.*

### 11.4 Puls

Wenn deine Touren Pulsdaten haben: **Zeit in den Pulszonen** je Jahr, **Durchschnittspuls je Tour** (ein Punkt je Tour, Antippen öffnet sie) und **Die anstrengendsten Touren** (Anteil der Zeit in Zone 4 und 5). Der Maximalpuls für die Zonen steht in der Verwaltung ([Abschnitt 15.1](#k15)).

![Statistik, Puls](handbuch/bilder/26-statistik-puls.png)

*Abbildung 36: Puls mit Pulszonen und den anstrengendsten Touren.*

### 11.5 Statistik anpassen

Die Statistik besteht aus Bausteinen wie die anderen Seiten: **Seite anpassen** und **Ansichten** ([Kapitel 13](#k13)).

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k12"></a>

## 12. Der Jahresrückblick

**Zweck:** Dein Tourenjahr als Seite zum Anschauen, Drucken und Teilen.

**Öffnen:** Statistik → Knopf **Jahresrückblick 2026** (Jahr passt sich an). Die Seite zeigt:

* das Jahr groß, darunter Touren, Kilometer, Höhenmeter, Stunden, Tage unterwegs und den Vergleich zum Vorjahr,
* **Kilometer pro Monat** (stärkster Monat hervorgehoben) und **Sportarten**,
* **Die fünf stärksten Touren**,
* **Fotos des Jahres** mit Knopf **Diashow**.

Oben: **‹ Übersicht**, „Fotos im PDF“ (mit Anzahl), **PDF herunterladen**, **Drucken**, **Senden**, **Als Link teilen**.

![Jahresrückblick](handbuch/bilder/27-jahresrueckblick.png)

*Abbildung 37: Der Jahresrückblick 2026.*

### Als Link teilen

1. **Als Link teilen** anklicken.
2. **Jahr** und **Aktivität** (alle oder nur eine, z. B. Wandern) wählen.
3. Unter **Was wird gezeigt?** auswählen: **Kennzahlen**, **Rekorde**, **Heatmap** (Kalender, kein Kartenbild), **Beste Fotos**. Die Zeile „Dieser Link zeigt: …“ fasst es zusammen.
4. **Link gültig** wählen (z. B. 30 Tage).
5. **Link erstellen.** Der Link lässt sich ohne Konto öffnen und sauber als PDF speichern oder drucken („Drucken / Als PDF speichern“ auf der Seite).

![Dialog „Jahresrückblick teilen“](handbuch/bilder/28-rueckblick-teilen.png)

*Abbildung 38: „Jahresrückblick teilen“. Was du nicht wählst, schickt der Server gar nicht erst mit.*

**Was nie geteilt wird:** Strecken und Koordinaten (auch keine Start- oder Heimatorte, keine Ortsnamen), Notizen, Wegpunkte, Puls, Wetter, Uhr-Rohdaten, Gerät und Ausrüstung. Rekorde nennen nur Tourname und Datum – darauf weist der Dialog hin.

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k13"></a>

## 13. Seiten anpassen: Bausteine, Ansichten, Vorlagen, eigene Kennzahlen

**Zweck:** Tourseite, Übersicht, Statistik, Reise-Seite und Reisen-Übersicht bestehen aus **Bausteinen**. Du bestimmst, welche es gibt, wo sie stehen und wie breit sie sind. Ohne Anpassung sieht alles aus wie gewohnt. Die Einstellung wird je Benutzer gespeichert; Betrachter sehen den Standard.

### 13.1 Den Bearbeitungsmodus einschalten

1. Auf der Seite **Seite anpassen** anklicken (rechts über den Bausteinen).
2. Jeder Baustein bekommt einen gestrichelten Rahmen und eine Kopfzeile mit Steuerelementen. Unten erscheint eine Leiste mit **Rückgängig** und **Wiederholen**, dem Umschalter **Anordnung für: Desktop | Handy** sowie **Ansichten**, **Baustein hinzufügen**, **Standard wiederherstellen**, **Als neue Ansicht speichern …**, **Verwerfen** und **Fertig**.
3. **Fertig** übernimmt alles. **Verwerfen** lässt alles wie vorher.

In der Kopfzeile jedes Bausteins:

* der **Griff** (⋮⋮) zum Ziehen – auch mit Tastatur: Pfeiltasten verschieben, Home und End springen an den Anfang bzw. das Ende,
* vier **Breiten**: ganze Breite, zwei Drittel, halbe Breite, ein Drittel (auf breiten Bildschirmen stehen kleine Bausteine nebeneinander),
* **↑ ↓** zum Verschieben, **Ausblenden** (der Baustein ist weg, aber nicht gelöscht – im Bearbeitungsmodus holst du ihn zurück),
* **Einstellungen** (Zahnrad), falls der Baustein einstellbar ist,
* **Standardmäßig offen:** ob der Baustein beim Öffnen der Seite aufgeklappt ist,
* **Duplizieren** (bei Bausteinen, die mehrfach vorkommen dürfen) und **In Gruppe …** (bei schmalen Bausteinen im Menü „⋯“).

![Bearbeitungsmodus der Statistikseite](handbuch/bilder/32-seite-anpassen.png)

*Abbildung 39: Statistik im Bearbeitungsmodus. Die untere Leiste (rot) enthält die Hauptfunktionen.*

### 13.2 Bausteine hinzufügen

1. **Baustein hinzufügen** anklicken.
2. Im Katalog nach Kategorie filtern – **Alle**, **Statistik**, **Zahlen**, **Grafiken**, **Rückblick**, **Planung**, **Touren holen**, **Hinweise**, **Eigene Kennzahlen** (je nach Seite gibt es unterschiedliche) – oder mit **Bausteine suchen …** nach einem Wort.
3. Bei **Hinzufügen** bekommst du den Baustein ans Seitenende; verschiebe ihn dann an die richtige Stelle. Die Vorschau im Katalog zeigt Beispielwerte.

Bausteine gelten nicht nur für eine Seite: „Dein Jahr“ kannst du z. B. auch auf der Tourseite einsetzen, und mehrere Exemplare mit verschiedenen Filtern (Aktivität, Zeitraum, Kennzahlen, Titel) sind möglich.

![Katalog „Baustein hinzufügen“](handbuch/bilder/33-baustein-hinzufuegen.png)

*Abbildung 40: Der Katalog (hier für die Statistik): Kategorien, Suche und Vorschau mit Beispielwerten.*

### 13.3 Eigene Kennzahlen

Mit einer eigenen Kennzahl rechnest du selbst aus, was du wissen willst – ohne Programmieren.

1. **Seite anpassen → Baustein hinzufügen → Eigene Kennzahlen → Erstellen** (Übersicht und Statistik).
2. Optional: **Mit einer Vorlage starten**, z. B. „Höhenmeter je km“, „Touren pro Monat“, „Längste Wanderung“, „Ziel: 1000 km im Jahr“, „Durchschnittstempo“, „Größter Aufstieg“.
3. **Name und Symbol** vergeben (Emoji, optional).
4. **Was wird gerechnet?** – **Messgröße** (Anzahl Touren, Strecke, Aufstieg, Abstieg, Dauer, Gehzeit, Durchschnittspuls, Höchstpuls, Geschwindigkeit, Steigung, Höhenmeter je Kilometer) und **Rechenart** (Summe, Durchschnitt, Maximum, Minimum, Anzahl, Rekord mit Tourname, Durchschnitt pro Monat). Optional **Formel: durch eine zweite Kennzahl teilen**, z. B. Aufstieg geteilt durch Strecke.
5. **Filter:** Aktivität, Zeitraum (Laufendes Jahr, Letzte 12 Monate, Letzte 90 Tage, Gesamte Zeit, Bestimmtes Jahr, Eigener Bereich), Schlagwort, Mindeststrecke.
6. **Anzeige** – vier einklappbare Gruppen:
   * **Ziel:** ein Zielwert (z. B. 1000 km im Jahr) erzeugt einen Fortschrittsbalken mit Prozent und dem Rest bis zum Ziel. Mit **„Im Plan?“** vergleicht die Kachel deinen Stand mit einem gleichmäßigen Soll (Tag des Jahres bzw. Anteil deines Bereichs) und sagt in Worten **Vor dem Plan**, **Im Plan** oder **Hinter dem Plan**; eine dünne Marke im Balken zeigt das Soll. Es gibt keine Warnfarbe, jede Aussage steht als Text. Das Soll gibt es für Summe und Anzahl ohne Formel bei laufendem Jahr, bestimmtem Jahr und eigenem Bereich.
   * **Vergleich:** zeigt einen Pfeil (**↑ ↓ →**) mit Prozent und Differenz, zum Beispiel „↑ +23,1 % (+15 km)“. Du wählst, womit verglichen wird: **Zeitraum davor**, **Vorjahr** (gleicher Zeitraum bis zum selben Tag) oder **Vormonat** (einen Monat früher). Der Pfeil bewertet nichts: Ob mehr gut ist, hängt von der Kennzahl ab. Für „Gesamte Zeit“ gibt es keinen Vergleich.
   * **Verlauf:** eine kleine Grafik der Wochen- (bis 98 Tage), Monats- oder Jahreswerte als **Linie (Sparkline)**, als **Säulen** oder **Aus**.
   * **Antippen:** Tippst du auf die Kachel oder auf „Touren anzeigen ›“, öffnet sich die Tourenliste mit den Filtern der Kennzahl (Aktivität, Zeitraum, Schlagwort, Mindeststrecke); bei einem Rekord öffnet sich die Rekordtour. Oben in der Liste steht, was gefiltert ist, mit „Filter aufheben“. Lässt sich etwas nicht genau abbilden (z. B. nur Touren mit Pulsdaten), steht ein Hinweis dabei.
7. Die **Vorschau** oben zeigt Wert, Trend, Verlauf und Ziel sofort. **Hinzufügen** übernimmt die Kennzahl als Baustein.

Es zählen nur Touren, die die jeweilige Angabe haben (z. B. Puls); fehlende Angaben werden nie als 0 gerechnet.

![Eigene Kennzahl erstellen, Vorlagenliste](handbuch/bilder/34-eigene-kennzahl.png)

*Abbildung 41: „Eigene Kennzahl erstellen“ mit den Startvorlagen.*

![Eigene Kennzahl aus der Vorlage „Höhenmeter je km“](handbuch/bilder/35-eigene-kennzahl-vorlage.png)

*Abbildung 42: Die Vorlage „Höhenmeter je km“: Vorschau (36,7 m/km, Vergleich zum Vorjahr), Name, Messgröße, Formel.*

![Eigene Kennzahl, untere Hälfte des Dialogs](handbuch/bilder/35b-eigene-kennzahl-unten.png)

*Abbildung 43: Der untere Teil des Dialogs: Filter, Zeitraum, Anzeige, Ziel, „Hinzufügen“.*

### 13.4 Ansichten

Eine **Ansicht** ist eine gespeicherte Anordnung der Seite, z. B. „Wandern“, „Rad“ oder „Kompakt“. Es gibt immer die **Standardansicht**.

* **Ansichten** (Knopf oben auf der Seite oder in der Leiste) öffnet die Liste. Die gerade **angezeigte** Ansicht ist markiert.
* Je Ansicht: **Umbenennen**, **Duplizieren**, **Exportieren**, **Teilen …** (Layoutcode und Link, siehe 13.11).
* Neu: **Neue Ansicht**, **Aus Vorlage …**, **Importieren …**.
* Im Bearbeitungsmodus speichert **Als neue Ansicht speichern …** den aktuellen Stand unter einem Namen.

![Dialog „Ansichten“](handbuch/bilder/56-ansichten.png)

*Abbildung 44: Der Dialog „Ansichten“ der Statistik.*

### 13.5 Vorlagen

**Aus Vorlage …** zeigt fertige Anordnungen, die du als **neue Ansicht übernehmen** kannst – deine bisherigen Ansichten bleiben unberührt. Für die Statistik sind das z. B. **Jahresrückblick**, **Training** (Belastung, typisches Tempo, Streckenlängen) und **Kompakt**. Für die Übersicht gibt es u. a. eine Vorlage mit Hinweisen; für Reisen fünf eigene Vorlagen.

![Dialog „Vorlage wählen“](handbuch/bilder/36-vorlagen.png)

*Abbildung 45: „Vorlage wählen“ für die Statistik.*

### 13.6 Export und Import des Layouts

* **Exportieren** speichert eine Ansicht als Datei – zum Sichern oder für ein anderes Gerät oder Konto.
* **Importieren …** liest eine solche Datei wieder ein (oder einen Layoutcode, siehe 13.11). Ungültige Dateien werden mit einer Fehlermeldung abgelehnt.

### 13.7 Standard wiederherstellen

**Standard wiederherstellen** (untere Leiste im Bearbeitungsmodus) setzt die Seite auf die ursprüngliche Anordnung zurück. Deine gespeicherten Ansichten bleiben dabei bestehen. Mit **Rückgängig** (13.8) holst du den Stand zurück, wenn es zu schnell ging.

### 13.8 Bausteine duplizieren, Rückgängig und Wiederholen

**Duplizieren:** In der Kopfzeile eines Bausteins (bei schmalen Bausteinen im Menü „⋯“) legt **Duplizieren** eine Kopie mit denselben Einstellungen direkt dahinter an. Sie heißt „… (Kopie)“, bekommt den Fokus und steht in derselben Gruppe wie das Original. Das gibt es nur bei Bausteinen, die mehrfach vorkommen dürfen (im Katalog erkennst du sie daran, dass „Noch einmal hinzufügen“ möglich ist) und nicht für feste Abschnitte der Seite. Je Seite sind höchstens 40 Bausteine möglich; ist das Limit erreicht, sagt dir ein Hinweis, warum nichts passiert.

**Rückgängig und Wiederholen:** Die Knöpfe **Rückgängig** und **Wiederholen** in der Leiste (auf dem Handy mit Text, Pfeilsymbol) nehmen die letzten Änderungen zurück bzw. stellen sie wieder her: verschieben, Breite, ausblenden, hinzufügen, entfernen, duplizieren, Einstellungen, Gruppen, Handy-Anordnung und „Standard wiederherstellen“. Mit der Tastatur: **Strg+Z** (Mac: **Cmd+Z**) und **Strg+Umschalt+Z** (auch Strg+Y). Die Kürzel gelten nur im Bearbeitungsmodus und nicht in Eingabefeldern oder Dialogen. Es werden die letzten 50 Schritte gemerkt; **Fertig**, **Verwerfen**, das Verlassen der Seite und der Wechsel der Ansicht beginnen einen neuen Verlauf. Vorlesehilfen hören jeden Schritt („Rückgängig: …“). Ein ausgegrauter Knopf bedeutet: nichts mehr da.

### 13.9 Gruppen

Eine **Gruppe** bündelt mehrere Bausteine zu einem einklappbaren Abschnitt mit eigenem Titel, z. B. „Rückblick“ oder „Training“.

1. Im Bearbeitungsmodus im Menü eines Bausteins **In Gruppe …** wählen, dann **In eine neue Gruppe** oder eine bestehende Gruppe. Oder den Baustein am Griff **über eine Gruppe ziehen** (die Gruppe zeigt, dass er hineinkommt); aus der Gruppe heraus ziehst du ihn auf dieselbe Weise.
2. In der Kopfzeile der Gruppe: **Umbenennen** (Titel bis 60 Zeichen; ohne Titel heißt sie „Gruppe 1“ usw.), **Standardmäßig offen**, **↑ ↓** (die Gruppe wandert als ein Block) und **Gruppe lösen** (die Bausteine bleiben auf der Seite).
3. **Aus Gruppe lösen** im Menü eines Bausteins nimmt ihn heraus. Mit den Pfeiltasten am Griff verlässt ein Baustein am Rand die Gruppe.

Außerhalb des Bearbeitungsmodus klappst du eine Gruppe mit einem Klick auf ihre Überschrift auf oder zu; der Zustand wird je Benutzer gemerkt, „Standardmäßig offen“ legt fest, wie die Gruppe beim ersten Öffnen aussieht. Im Bearbeitungsmodus sind alle Gruppen offen. Grenzen: höchstens 10 Gruppen je Seite und 30 Bausteine je Gruppe, keine Gruppen in Gruppen, und der Einstieg in die Auswertung sowie die Köpfe der Reise- und Fotos-Seite lassen sich nicht gruppieren. Die Karte hat keine Gruppen. Gruppen gehören zur Ansicht und werden mit Ansichten, Vorlagen (z. B. „Mit Gruppe“), Export und Import weitergegeben.

### 13.10 Eigene Handy-Anordnung

Auf schmalen Bildschirmen (Ansicht „Handy“, bis 760 Pixel Breite) willst du vielleicht eine andere Reihenfolge oder weniger Bausteine als am Computer.

1. Im Bearbeitungsmodus in der Leiste **Anordnung für: Handy** wählen. Die Seite erscheint in einem schmalen Rahmen, einspaltig, so wie sie auf dem Handy aussieht.
2. Jetzt verschiebst und blendest du aus wie gewohnt – das gilt nur für das Handy. Die erste Änderung legt die Handy-Anordnung an; der Hinweis in der Leiste sagt, ob es schon eine gibt.
3. **Desktop** schaltet zurück; **Handy-Anordnung zurücksetzen** entfernt sie, dann gilt wieder die Desktop-Reihenfolge.

Ohne eigene Handy-Anordnung gilt überall die Desktop-Reihenfolge, wie bisher. Auf einem Handy startet der Umschalter bei „Handy“. Breite, Einstellungen und Gruppen sind für beide gleich; die Karte hat keine eigene Handy-Anordnung.

### 13.11 Ansichten teilen: Layoutcode und Link

Eine Ansicht lässt sich auch als kurzer Text weitergeben, zum Beispiel in einer Nachricht.

* **Ansichten → bei der Ansicht Teilen …** zeigt den **Layoutcode** (beginnt mit `MTA1.`). **Code kopieren** und **Link kopieren** legen ihn in die Zwischenablage; ist das nicht möglich, ist der Code markiert und du kopierst ihn mit Strg+C.
* Wer den Code bekommt, fügt ihn bei **Ansichten → Importieren … → Layoutcode oder Link einfügen** ein und wählt **Code prüfen**. Ein geöffneter Link führt auf der anderen Installation (angemeldet) zur passenden Seite und öffnet den Import mit dem Code.
* Dann wie beim Import einer Datei: Name wählen, **Als neue Ansicht importieren** oder eine bestehende Ansicht ersetzen. Vorher wird nichts gespeichert.

**Was steckt im Code?** Nur die Anordnung und die Einstellungen der Bausteine, auch eigene Titel und Notizen, die du dort eingegeben hast. Keine Touren, Fotos, Orte oder Zugangsdaten, und der Code gibt keinen Zugriff auf deine Daten. Der Server prüft jeden Code streng wie eine Datei (nur erlaubte Felder, Größen und Bausteine); beschädigte oder zu große Codes werden abgelehnt. Betrachter können keine Ansichten importieren.

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k14"></a>

## 14. Freigabe und Teilen

**Zweck:** Du kannst Touren, Diashows und den Jahresrückblick **per Link ohne Konto** teilen. Du entscheidest, was gezeigt wird, und kannst jeden Link jederzeit widerrufen.

### 14.1 Eine Tour teilen

1. Tour öffnen → **Teilen & Export → Link senden**.
2. **Voreinstellung** wählen: **Komplett**, **Nur Karte und Fotos**, **Alles außer Notizen**, **Alles zeigen**.
3. Unter **Was wird gezeigt?** einzelne Bausteine ein- und ausschalten: **Karte**, **Höhenprofil**, **Kennzahlen**, **Fotos**, **Notiz und Beschreibung**, **Wegpunkte**, **Pulsverlauf**, **Wetter**. Die Zeile „Dieser Link zeigt: …“ fasst es zusammen.
4. **Anfang und Ende der Strecke ausblenden (300 m)** ist vorgewählt – sinnvoll, damit dein Zuhause nicht zu erkennen ist.
5. **Link gültig:** 7 Tage, 30 Tage oder unbegrenzt.
6. **Link erstellen.** Auf Handys öffnet sich das Teilen-Menü (WhatsApp, Signal, E-Mail …).

![Dialog „Tour teilen“](handbuch/bilder/13-teilen-dialog.png)

*Abbildung 46: „Tour teilen“. Hier: „Nur Karte und Fotos“, Anfang und Ende ausgeblendet, 30 Tage gültig.*

**Was Empfänger sehen:** Name und Datum der Tour stehen immer im Kopf; dazu genau die gewählten Bausteine.

![Geteilte Tour im Browser des Empfängers](handbuch/bilder/54-geteilte-tour.png)

*Abbildung 47: Die geteilte Seite, die ein Empfänger ohne Konto sieht: Karte und Fotos (die Kartenkacheln fehlen in dieser Aufnahme).*

### 14.2 Was wird nie geteilt?

* **Nie Teil eines Tour-Links:** Auswertung, Uhr-Daten, Vergleiche, Gerät, Ausrüstung, Sicherheit.
* **Nie Teil eines Rückblick-Links:** Strecken und Koordinaten, Orte, Notizen, Wegpunkte, Puls, Wetter, Uhr-Rohdaten, Gerät, Ausrüstung.
* **Nie Teil eines Diashow-Links:** Koordinaten, Orte, Notizen, Strecken, Uhr-Daten; es gibt keine Kommentare.
* **Nur Gewähltes verlässt den Server.** Was du abwählst, wird gar nicht erst geliefert – auch nicht versteckt.
* Wegpunkt-Texte erscheinen nur, wenn zusätzlich „Notiz und Beschreibung“ gewählt ist. Bevor du „Notiz“ wählst, prüfe, ob die Notiz öffentlich sein darf.
* Betrachter dürfen keine Links erzeugen.

### 14.3 Freigegebene Links verwalten

Im Benutzermenü **Freigegebene Links** (oder in der Verwaltung der Knopf **Freigegebene Links verwalten**) siehst du alle Links mit Typ, Inhalt („Zeigt: …“), Erstellungsdatum und Gültigkeit. Filter: **Alle**, **Diashows**, **Tourlinks**, **Rückblicke**, **Abgelaufen**. Pro Link:

* **Kopieren** und **Öffnen**,
* **PDF** (bei Rückblicken),
* **Laufzeit ändern …**,
* **Auswahl ändern** – die Änderung gilt sofort für den bestehenden Link,
* **Widerrufen** – der Link zeigt danach „nicht mehr gültig“.

![Freigegebene Links](handbuch/bilder/42-freigegebene-links.png)

*Abbildung 48: „Freigegebene Links“ mit Tourlink und Jahresrückblick. Die Adresse zeigt die Demo-Installation; bei dir steht dort die Adresse deiner Installation.*

### 14.4 Wichtig für Links nach draußen

Damit Empfänger ohne Konto einen Link öffnen können, muss deine Installation **von außen erreichbar** sein (z. B. Tailscale Funnel oder ein Reverse-Proxy mit HTTPS). Im Heimnetz oder nur im Tailnet kann niemand sonst den Link öffnen. Die Risiken dazu stehen im Abschnitt „Tailscale Funnel“ der [README](../README.md) und in [Kapitel 19](#k19).

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k15"></a>

## 15. Die Verwaltung

**Zweck:** Einrichtung, Wartung und Sicherung. Öffne sie mit dem **Zahnrad** oben (auf dem Handy: **Mehr → Verwaltung**). Die Verwaltung hat acht Reiter und oben die Knöpfe **Freigegebene Links verwalten** und – rechts oben – die Versionsangabe („Version: 3.33.0“).

| Reiter | Inhalt |
|---|---|
| **Übersicht** | Zustand, Updates, Protokoll, Heimatort und Puls, Entwicklermodus |
| **Touren holen** | Meine Geräte, Komoot, Zepp, Garmin/Suunto/andere Uhren, Wanderführer ([Kapitel 4](#k4)) |
| **Hochladen & Planen** | Strava und Komoot (Upload), Tourplanung |
| **Fotos** | Fotobibliothek, Import, Foto-Eingang, Bildeinstellungen |
| **Automatik & Meldungen** | tägliche Aktualisierung, Benachrichtigung (Webhook/ntfy), E-Mail-Versand |
| **Handy & App** | Standort teilen, App auf dem Startbildschirm, Android-App |
| **Sicherung & Zugang** | Sicherung, Umzugspaket, Zugriffsschutz, Offline-Nutzung |
| **Prüfen & Aufräumen** | auffällige Touren, Aufräumen (eigene Seite) |

Die Verwaltung wird **Administratoren** angezeigt. **Einstellungen speichern** am Ende jedes Reiters speichert die Eingaben.

### 15.1 Übersicht: Zustand, Updates, Heimatort

* **Zustand:** Haken oder Warnzeichen für Komoot-Zugang, letztes Backup, Datenbank, freien Speicher, Touren ohne Strecke und Fotos ohne Tour.
* **Updates:** zeigt die installierte und die neueste Version auf GitHub. **Jetzt prüfen** fragt sofort nach; „Regelmäßig (alle 6 Stunden) auf neue Versionen prüfen“ kannst du einschalten. Administratoren installieren neue Versionen auf den meisten Installationen per Knopfdruck; bei Docker nennt die App nur den Befehl. Vor jedem Update gibt es automatisch eine Sicherung.
* **Protokoll:** Meldungen der Hintergrundarbeiten.
* **Heimatort und Puls:** Heimatort suchen und festlegen; **Maximalpuls (bpm)** für die Pulszonen (leer = 185 bzw. der höchste gemessene Wert).
* **Entwicklermodus:** blendet Ansichten zur Fehlersuche ein (Selbsttest, vollständiges Protokoll …). Im Alltag nicht nötig.

![Verwaltung, Reiter „Übersicht“](handbuch/bilder/37-verwaltung-uebersicht.png)

*Abbildung 49: „Übersicht“: Zustand, Updates, Protokoll, Heimatort und Puls. Der gelbe Hinweis oben erscheint nur im Demo-Modus.*

### 15.2 Hochladen & Planen

**Portale (Upload):** Strava (Client-ID und -Secret aus strava.com/settings/api, „Mit Strava verbinden“) und Komoot. **Tourplanung:** Funktion an/aus und wo der Routing-Dienst BRouter läuft (öffentlich über brouter.de – dann werden die Koordinaten der geplanten Punkte dorthin gesendet –, auf dem eigenen Server oder im Netz).

![Verwaltung, Reiter „Hochladen & Planen“](handbuch/bilder/46-verwaltung-hochladen.png)

*Abbildung 50: Portale und Tourplanung.*

### 15.3 Fotos

Siehe [Abschnitt 10.1](#k10).

### 15.4 Automatik & Meldungen

* **Täglich aktualisieren** (Komoot, Routen, Fotos) an oder aus, dazu die Uhrzeit.
* **Benachrichtigung (optional):** Trage eine Webhook-Adresse ein (z. B. ntfy oder Gotify). Bei Warnungen (Zepp-Token, Backup, Job-Fehler, Speicher) wird dort eine Textnachricht abgeliefert; optional auch bei neuen Touren. **Testnachricht senden** prüft die Adresse.
* **E-Mail-Versand:** SMTP-Zugang für „Passwort vergessen“ und Zwei-Faktor-Hinweise.

### 15.5 Handy & App

**Standort teilen** (Aus / Nur während einer Aufzeichnung / Immer, wenn die Karte meinen Standort zeigt; **Letzten Standort löschen**) und **Auf dem Handy**: Meine Touren lässt sich wie eine App auf dem Startbildschirm installieren. Danach erscheint sie im Teilen-Menü von Android. Voraussetzung ist eine gesicherte Verbindung (HTTPS); ohne Installation hilft in Chrome ⋮ → „Zum Startbildschirm hinzufügen“.

![Verwaltung, Reiter „Handy & App“](handbuch/bilder/45-verwaltung-handy-app.png)

*Abbildung 51: Der Reiter „Handy & App“.*

### 15.6 Sicherung & Zugang

* **Sicherung:** Täglich um 03:40 Uhr wird die Datenbank (Touren, Notizen, Ziele, Zuordnungen) gesichert, die letzten 14 bleiben erhalten. **Backup jetzt herunterladen** und **Jetzt sichern** (oben) legen sofort eine an. Passwörter und Tokens sind im Download nicht enthalten; **Fotos und Routen sind nicht enthalten** – sichere diese Ordner zusätzlich. Wiederherstellen: `meine-touren-restore <Datei>` auf dem Server.
* **Umzug auf einen neuen Server:** **Umzugspaket erstellen** enthält alles (alle Benutzer, Touren, Fotos, Strecken, Freigabelinks, gespeicherte Zugangsdaten samt Schlüssel). Das Paket enthält Passwörter und Schlüssel – gut aufbewahren; es kann groß werden.
* **Zugriffsschutz:** Ohne Benutzerverwaltung kannst du die Oberfläche mit einem Passwort schützen („Passwort setzen“, der Browser fragt danach; Benutzername beliebig). Besser ist die Benutzerverwaltung ([Kapitel 3](#k3)).
* **Offline-Nutzung:** **Für Offline vorbereiten** lädt die letzten 8 Touren mit Strecke, einigen Fotos und den Kartenkacheln auf dieses Gerät; **Alle Touren offline (Daten und Strecken)** lädt alle Strecken.

![Verwaltung, Reiter „Sicherung & Zugang“](handbuch/bilder/39-verwaltung-sicherung.png)

*Abbildung 52: Sicherung, Umzugspaket, Zugriffsschutz und Offline-Nutzung.*

### 15.7 Prüfen & Aufräumen

Hier findest du auffällige Touren (zum Beispiel unplausible Tempi) und Aufräum-Werkzeuge. Touren, die nur wegen Lücken oder Pausen auffallen, kannst du als **geprüft** markieren.

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k16"></a>

## 16. Die Android-App

**Zweck:** Eine kleine native Android-App als „Hülle“ um die Weboberfläche. Sie kann, was eine Webseite nicht kann.

**Was sie bietet:**

* **GPS-Aufzeichnung** im Hintergrund (auch bei ausgeschaltetem Bildschirm). Menüpunkt **● Aufzeichnen** (erscheint nur in der App): Sportart wählen, Start, live Zeit, Strecke, Höhenmeter und Karte, Pause, Beenden, dann **Auf den Server speichern**. Wird der Server nicht erreicht, bleibt die Aufzeichnung auf dem Handy erhalten. **Beenden** geht nur durch Gedrückthalten (etwa 1,5 Sekunden).
* **Fotos aufnehmen** während der Aufzeichnung (sofort hochladen oder gesammelt am Ende).
* **Sprachansagen** auf der Strecke, wenn du vor dem Start eine geplante Tour oder eine frühere Tour als Route wählst: Abbiegungen, Abweichung vom Weg, Restkilometer, Ziel. Sie nutzen die Sprachausgabe von Android; es gibt keine Kartennavigation mit Wegnamen.
* **Offline-Speicher:** Was die App vom Server lädt, bleibt auf dem Handy und wird ohne Verbindung weiter angezeigt (Hinweisband „Offline“).
* **Wegpunkte** unterwegs (Schnellnotiz wie Rast oder Aussicht), **Wetterwarnung** und ein **Live-Standort-Link** für Kontakte.
* **Teilen-Menü:** GPX, FIT, TCX, ZIP und Fotos aus anderen Apps (Garmin, Komoot, Galerie …) direkt an Meine Touren senden.
* **PDF-Downloads** landen im Download-Ordner.
* **Vollbild-Diashow:** Die Diashow der Seite lässt sich in der App im Vollbild zeigen.
* **Info** (Menü „Mehr“): Version von App und Server.

**Installation:**

1. Die APK wird auf GitHub gebaut (Actions → „Android-App“) und bei einer Veröffentlichung an das Release angehängt. Ohne Signierschlüssel entsteht eine Debug-APK; sie lässt sich ebenfalls installieren („Aus unbekannten Quellen“ erlauben).
2. Beim ersten Start gibst du die **Serveradresse** ein (auch `http://192.168.178.230` ist möglich). Sie lässt sich in der Verwaltung ändern.
3. Neue Versionen lassen sich über die alte installieren; die App wird immer mit demselben Schlüssel signiert.

**Wichtig:**

* Hersteller wie Xiaomi, Samsung oder Huawei beenden Hintergrunddienste teils aggressiv. Schalte für die App die **Akku-Optimierung** aus (Verwaltung → Handy & App → Android-App → „Akku-Einstellungen“) und mache vor einer langen Tour eine kurze Testrunde.
* Android installiert die App als „richtige“ App nur bei einer gesicherten Adresse (**HTTPS**), z. B. über Tailscale. Bei `http://192.168…` entsteht nur eine Verknüpfung ohne Teilen-Menü – das Teilen-Menü der nativen App funktioniert aber auch über HTTP.
* Bei Problemen hilft **Diagnose senden / kopieren** (Verwaltung → Handy & App → Android-App).

### Die Weboberfläche am Handy

Auch im Handy-Browser passt sich die Oberfläche an: unten die Leiste mit **Übersicht**, **Karte**, **Touren**, **Fotos** und **Mehr**.

<p align="center">
<img src="handbuch/bilder/47-handy-uebersicht.png" width="230" alt="Handy: Übersicht">
<img src="handbuch/bilder/48-handy-touren.png" width="230" alt="Handy: Touren-Liste">
<img src="handbuch/bilder/49-handy-tour.png" width="230" alt="Handy: Tourdetail">
</p>

*Abbildung 53: Handy-Ansicht (390 px breit): Übersicht, Touren-Liste, Tourdetail.*

<p align="center">
<img src="handbuch/bilder/50-handy-hoehenprofil.png" width="230" alt="Handy: Höhenprofil und Herzfrequenz">
<img src="handbuch/bilder/55-handy-mehr.png" width="230" alt="Handy: Menü Mehr">
</p>

*Abbildung 54: Höhenprofil und Herzfrequenz am Handy; rechts das Menü „Mehr“ mit Reisen, Statistik, Verwaltung und der Wahl „Automatisch / Smartphone / Computer“.*

**Tour am Handy:** Statt vieler einzelner Knöpfe gibt es drei große: **Ansehen**, **Teilen & Export**, **Bearbeiten**.

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k17"></a>

## 17. Mein Tourentagebuch (Begleit-App)

**Mein Tourentagebuch** ist eine **eigenständige Android-App**, die ganz ohne Server auskommt: Touren, Fotos, Aufzeichnung, Planung und Routing liegen **lokal auf dem Handy**. Sie ist ein separates Projekt ([hilde0407/mein-tourentagebuch](https://github.com/hilde0407/mein-tourentagebuch)) und nicht Teil von Meine Touren.

Laut Projektbeschreibung kann sie unter anderem: Touren mit Karte und Höhenprofil, Fotos (automatisch den Touren zugeordnet), GPS-Aufzeichnung mit Sprachansagen, Tourplanung mit Routing, Import aus Dateien (GPX, FIT, TCX, ZIP) sowie aus Komoot, Strava und Zepp, eine Statistik und eine Sicherung. Wer unterwegs lieber ohne Server arbeitet, nutzt sie; Meine Touren ist das Archiv für den eigenen Server. Alles Weitere steht in der Beschreibung des Projekts auf GitHub.

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k18"></a>

## 18. Tipps, Tastenkürzel, Fehlersuche und häufige Fragen

### 18.1 Tastenkürzel

| Taste | Wirkung |
|---|---|
| **/** | Suchfeld oben anspringen (nicht in Eingabefeldern) |
| **← →** | In der Foto-Großansicht und in der Diashow blättern |
| **Esc** | Foto-Großansicht oder Dialog schließen |
| **Leertaste** | Diashow anhalten und fortsetzen |
| **F** | Diashow im Vollbild |
| **Pfeiltasten** am Griff (⋮⋮) | Baustein im Bearbeitungsmodus verschieben |
| **Home / End** am Griff | Baustein an den Anfang bzw. das Ende setzen |
| **Strg+Z / Cmd+Z**, **Strg+Umschalt+Z** | Im Bearbeitungsmodus Änderung zurücknehmen bzw. wiederholen (nicht in Eingabefeldern) |
| **Tab** | Durch Knöpfe und Felder gehen; Dialoge halten den Fokus bei sich |

### 18.2 Tipps

* **Jahresziele** setzen (Statistik → Ziele): Prognose und „im Plan“ motivieren.
* **Notiz und Bewertung** direkt in der Tour eintragen – sie sind später auch in Suche und Filter nutzbar.
* **Tags** ordnen Touren zu Alben (Bearbeiten → Tags & Alben).
* **Ansichten** nutzen: eine Ansicht für „Wandern“, eine für „Rad“, eine kompakte fürs Handy.
* **Neuland** zeigt dir, wie viel einer Tour wirklich neu war.
* **Auffällige Touren** (Seilbahn, Auto) bereinigt „Track korrigieren“; das Original lässt sich wiederherstellen.
* **Backup prüfen:** Der Zustand in der Verwaltung zeigt, wann die letzte Sicherung war. Fotos und Routen sind nicht in der Sicherung – sichere sie zusätzlich.

### 18.3 Fehlersuche

| Problem | Ursache und Lösung |
|---|---|
| **Die Karte ist grau.** | Die Kartenkacheln kommen aus dem Internet. Prüfe die Verbindung des Servers und des Browsers. Offline helfen vorbereitete Touren („Für Offline vorbereiten“). |
| **Ein Foto liegt bei keiner Tour.** | Die Aufnahmezeit passt nicht (falsche Kamerauhr, Zeitzone). Im Tourdetail **Zeit per GPS prüfen**, oder auf der Fotos-Seite **Fotos zuordnen**. Fotos mehr als 10 km neben der Strecke werden nicht zugeordnet. |
| **Eine Reise fehlt.** | Reisen brauchen mindestens vier Tage weit weg von zu Hause. Prüfe den **Heimatort** (Verwaltung → Übersicht). Mit **＋ Mehrtagestour bilden …** legst du eine von Hand an. |
| **Zepp-Import bricht ab.** | Der Token kann abgelaufen sein. In der Verwaltung unter „Zepp-Zugang / Token holen“ neu holen. Zepp und Komoot haben keine offizielle Schnittstelle. |
| **„Garmin-Konto: Nicht verfügbar“.** | Das Zusatzpaket fehlt. Nutze den Dateiweg (Kapitel 4). |
| **Statistik „Auswertung“ ist leer.** | Regionen, Gipfel oder Wetter müssen erst bestimmt werden (Knöpfe in den Abschnitten). Sie brauchen Internet. |
| **Pulszonen wirken falsch.** | Maximalpuls in der Verwaltung (Heimatort und Puls) eintragen. |
| **Das Teilen-Menü der Android-App fehlt in der Web-App.** | Installation als App braucht HTTPS. Siehe Kapitel 16. |
| **Ein Link zeigt „nicht mehr gültig“.** | Er ist abgelaufen oder widerrufen. Erzeuge einen neuen oder verlängere ihn unter „Laufzeit ändern …“. |
| **Eine Seite sieht nach dem Anpassen falsch aus.** | **Seite anpassen → Standard wiederherstellen**, oder eine andere Ansicht wählen. |
| **Nach einem Update fehlt etwas.** | Browser-Seite neu laden (Strg+F5). Die App zwischenspeichert Seiten. |
| **Server nicht erreichbar.** | Läuft der Dienst? Beim Proxmox- oder Debian-Setup: `journalctl -u meine-touren -f`. Bei Docker: `docker compose logs`. |

### 18.4 Häufige Fragen

**Werden meine Touren bei Komoot, Zepp oder Strava verändert?** Nein. Es wird nie etwas dort gelöscht; Hochladen geschieht nur auf ausdrücklichen Wunsch.

**Kann ich Meine Touren ohne Internet benutzen?** Die Seiten und deine gespeicherten Strecken ja; Karten, Höhen, Wetter und Ortsnamen brauchen Internet. Mit „Für Offline vorbereiten“ speicherst du Touren samt Kartenkacheln auf dem Gerät.

**Wie viele Benutzer gibt es?** Beliebig viele; jeder hat eigene Daten. Betrachter sehen die Daten eines gewählten Benutzers nur lesend.

**Geht das Handbuch auch auf Englisch?** Die Oberfläche gibt es auf Deutsch, Englisch, Französisch und Spanisch; dieses Handbuch ist auf Deutsch.

**Wie lösche ich eine Tour?** Tour → **Bearbeiten → Tour löschen**. Sie wird nur aus Meine Touren entfernt, nie bei Komoot oder Zepp.

**Wie ziehe ich auf einen neuen Server um?** Verwaltung → Sicherung & Zugang → **Umzugspaket erstellen**, auf dem neuen Server installieren, dann `meine-touren-restore <Paket>`.

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="k19"></a>

## 19. Datenschutz und Sicherheit

**Grundsatz:** Deine Daten liegen **lokal** bei dir. Es gibt keine Cloud und keinen Zwang, einen Dienst zu nutzen. Strecken, Fotos, Notizen und Datenbank liegen im Datenordner deiner Installation und sind Teil deiner Sicherung (Fotos und Routen separat sichern).

**Was ins Internet geht:**

* **Kartenkacheln** (OpenStreetMap u. a.), **Höhen- und Wetterdaten** (Open-Meteo) und **Ortsnamen** (Nominatim, Overpass). Dabei erfahren diese Dienste, welche Gegend du ansiehst. Beachte die Nutzungsrichtlinien.
* **Komoot, Zepp, Garmin, Strava** nur, wenn du sie einrichtest und nutzt. Hochgeladen wird nur auf ausdrücklichen Wunsch.
* **Tourplanung:** Nutzt du den öffentlichen BRouter (brouter.de), werden die Koordinaten der geplanten Punkte dorthin gesendet. Mit eigenem BRouter bleibt alles bei dir.
* **Update-Prüfung** fragt bei GitHub nach der neuesten Version.

**Zugang schützen:**

* Schalte die **Benutzerverwaltung** ein (Kapitel 3), nutze lange, einmalige Passwörter und – wo möglich – die **Zwei-Faktor-Anmeldung**.
* Betreibe die App im Heimnetz oder hinter einem VPN. Für den Zugriff von unterwegs empfiehlt die README **Tailscale** (`tailscale serve`): Die Adresse ist nur für deine eigenen Geräte erreichbar, und es ist kein Router-Port offen. Das Zertifikat ist gültig, die App installierbar.
* **Tailscale Funnel** macht die Adresse für jeden im Internet erreichbar – nötig nur, wenn Empfänger ohne Tailscale einen Link öffnen sollen. Dann ist die **ganze Anmeldeseite öffentlich**. Schalte Funnel nur zeitweise ein, nutze starke Passwörter und halte die Software aktuell. Die Risiken stehen ausführlich in der [README](../README.md) (Abschnitt „Tailscale Funnel“).
* Öffne die App nie ungeschützt ins Internet; hinter einem Reverse-Proxy vertraut sie den `X-Forwarded-*`-Headern.

**Teilen mit Bedacht:**

* Tour-Links blenden standardmäßig Anfang und Ende (300 m) aus. Lass das so, wenn du von zu Hause startest.
* Wähle beim Teilen nur, was der Empfänger sehen soll; was du nicht wählst, verlässt den Server nicht.
* Widerrufe Links, die nicht mehr gebraucht werden (**Freigegebene Links**).
* Der **Live-Standort-Link** zeigt den zuletzt gemeldeten Punkt; er läuft nach der gewählten Zeit ab und lässt sich widerrufen.

**Sicherheitslücken melden:** Bitte nicht als öffentliches Issue, sondern auf GitHub im Reiter **Security → Report a vulnerability** (siehe `SECURITY.md`).

**Rechtliches:** Das Projekt steht in keiner Verbindung zu Komoot, Strava, Zepp/Huami, Garmin, Suunto, Proxmox oder community-scripts. Alle Marken gehören ihren Inhabern. Lizenz: MIT.

[↑ Inhaltsverzeichnis](#inhalt)

---

<a id="glossar"></a>

## 20. Glossar

| Begriff | Bedeutung |
|---|---|
| **Ansicht** | Eine gespeicherte Anordnung einer anpassbaren Seite (z. B. „Wandern“). |
| **Baustein** | Ein Abschnitt einer Seite, den du verschieben, ausblenden, einklappen und in der Breite ändern kannst. |
| **BRouter** | Routing-Dienst für die Tourplanung. |
| **Eigene Kennzahl** | Ein von dir zusammengestellter Wert (z. B. Höhenmeter je km). |
| **Erzählung** | Die Tour als Zeitleiste mit Start, Fotos und Ziel. |
| **FIT / GPX / TCX** | Dateiformate für aufgezeichnete Aktivitäten. |
| **Foto-Eingang** | Ordner, in dem abgelegte Fotos automatisch übernommen werden. |
| **Funnel** | Tailscale-Funktion, die die App im Internet öffentlich erreichbar macht. |
| **Heatmap** | Darstellung, wo (Karte) oder wann (Kalender) du am häufigsten unterwegs warst. |
| **Heimatort** | Ort, von dem aus Touren nicht als Reise zählen. |
| **Mehrtagestour** | Mehrere Touren mit Namen wie „… Tag 3“, zusammengefasst. |
| **Neuland** | Anteil einer Tour, der auf keiner früheren Tour lag. |
| **Perlenkette** | Ausrichten von Fotos: Ein Foto wird verschoben, die anderen folgen im Zeitabstand. |
| **Pulszonen (Z1–Z5)** | Bereiche der Herzfrequenz in Prozent des Maximalpulses. |
| **Reise** | Touren weit weg von zu Hause an mindestens vier Tagen am Stück. |
| **Tailscale / Tailnet** | Privates Netz deiner Geräte, über das du die App von unterwegs erreichst. |
| **Tourblatt / Reiseblatt** | Druckbare Seite einer Tour bzw. Reise (PDF). |
| **Umzugspaket** | Vollständige Sicherung samt Fotos und Schlüsseln für den Umzug auf einen neuen Server. |
| **Vorlage** | Fertige Anordnung einer Seite, die du als neue Ansicht übernehmen kannst. |
| **Widerrufen** | Einen geteilten Link sofort ungültig machen. |

[↑ Inhaltsverzeichnis](#inhalt)
