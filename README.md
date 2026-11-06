# Meine Touren

**Dein privates Tourenarchiv zum Selbsthosten** – Wanderungen, Radtouren und Co. mit Karte, Höhenprofil, Statistik und Fotos. Die Strecken liegen **lokal** bei dir; Komoot, Zepp und Strava sind optionale Anbindungen zum Laden und Hochladen.

> *English in short:* self-hosted tour archive (hikes, rides …) with maps, elevation profiles, stats and photos. Tracks are stored locally; Komoot/Zepp import and Komoot/Strava upload are optional. UI language: German. One-line install for Proxmox VE below.

**Bebilderte Kurzanleitung: [docs/ANLEITUNG.md](docs/ANLEITUNG.md)**

## Installation auf Proxmox VE (empfohlen)

Auf dem **Proxmox-Host** (Shell) ausführen – der Assistent legt einen Debian-13-Container an und installiert alles darin:

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/hilde0407/meine-touren/main/ct/meine-touren.sh)"
```

Standard: unprivilegierter LXC, 2 Kerne, 2 GB RAM, 20 GB Disk (die komprimierten Fotos brauchen je nach Menge 4–8 GB), Port 80. „Advanced“ im Assistenten erlaubt eigene IP, Speicher usw. Danach `http://<Container-IP>/` öffnen – beim ersten Besuch legst du den Administrator an.

Das Skript nutzt – wie die Skripte von [community-scripts.org](https://community-scripts.org/) – deren Container-Engine. Sie lädt die Engine von `community-scripts/core` und sendet auf Wunsch anonyme Diagnosedaten (im Assistenten abwählbar); der eigentliche Installer liegt in diesem Repository (`install/meine-touren-install.sh`).

**Aktualisieren:** im Container `meine-touren-update github` – oder auf dem Proxmox-Host das Skript erneut starten und „Update“ wählen. Vor jedem Update wird automatisch ein Backup angelegt.

## Manuelle Installation (jeder Debian/Ubuntu-Server)

```bash
apt update && apt install -y git
git clone https://github.com/hilde0407/meine-touren.git && cd meine-touren
bash deploy/install.sh
```

Installiert Python-venv, nginx, den Systemdienst `meine-touren` und ein tägliches Backup (03:40 Uhr, 14 Stück in `/var/backups/meine-touren`). Programm: `/opt/meine-touren`, Daten: `/var/lib/meine-touren`, Einstellungen: `/etc/meine-touren.env`. Direkt ohne nginx: `http://<IP>:8080/`. Protokoll: `journalctl -u meine-touren -f`.

## Funktionen

* **Übersicht, Karte, Touren:** letzte Tour mit Karte und Fotos (zum Durchzappen), Jahresstatistik, Bestwerte, Kalender, „An diesem Tag“; alle Touren auf einer Karte; Tourseite mit Höhenprofil, Fotos an der Strecke, 3D-Flug und Diashow; Streckenfarbe frei wählbar.
* **Lokale Strecken:** Karten und Tourdetails arbeiten nur mit gespeicherten Daten. Original-GPX lokaler Touren liegen im Datenordner und sind im Backup.
* **Import:** Zepp-Trainings (GPS als GPX), **Garmin, Suunto und andere Uhren** (FIT/GPX/TCX/ZIP, Garmin-Konto), Komoot-Touren und -Strecken, Fotos (Browser-Upload mit Verkleinerung, Eingangsordner, SMB, Mac-Skript).
* **Upload (nur auf ausdrücklichen Wunsch):** Komoot und Strava, einzeln oder gesammelt, mit Doppelten-Prüfung und Probelauf. GPX-Download jeder Tour.
* **Fotos:** automatisch über die Aufnahmezeit den Touren zugeordnet, manuelle Korrektur mit Zeitversatz, Karte mit Foto-Markern; Fotos lassen sich auf der Strecke „wie eine Perlenkette“ ausrichten.
* **Updates:** regelmäßige Prüfung auf GitHub, Installation per Knopfdruck (Administratoren), vorher automatische Sicherung.
* **Komfort:** Namensvorschläge aus Kartendaten/Wanderführern (z. B. Rother-GPX), Höhenkorrektur mit Geländemodell, Regionen-Suche, Rekorde, Alben/Reisen, Auswertung (Tempo, Wetter, Neuland), öffentliche Teilen-Links (widerrufbar), Webhook-Benachrichtigung, PWA.
* **Mehrere Benutzer:** getrennte Touren, Fotos und Einstellungen je Benutzer; Fotos pro Bibliothek oder Tour für einzelne Benutzer oder alle freigeben.
* **Smartphone-Ansicht:** automatisch ab ≤ 760 px, umschaltbar.

## Einrichten

1. `http://<IP>/` öffnen → Administrator anlegen (mind. 8 Zeichen Passwort).
2. *Verwaltung → Import*: Komoot-Zugang eintragen (optional) und „Komoot aktualisieren“, und/oder Zepp-Zugang bzw. GPX-Dateien importieren.
3. *Verwaltung → Upload-Portale → Strava*: eigene Strava-App anlegen (strava.com/settings/api), Client-ID/-Secret eintragen, „Mit Strava verbinden“.
4. Fotos: *Verwaltung → Fotos → „Ordner auswählen und hochladen …“* (im Browser verkleinert) oder `mac/fotos_senden.sh`.

## Daten, Backup, Update

* Pro Benutzer: `/var/lib/meine-touren/users/<Kennung>/` (Datenbank `komoot_hub.sqlite` – historischer Dateiname, Strecken, Fotos, `tracks/`). Gemeinsam: `system.sqlite` (Benutzer, Anmeldungen, Freigaben), `tilecache/`.
* Backups: `/var/backups/meine-touren/<Kennung>/…zip` (Datenbank + lokale GPX + System-Datenbank; Fotos nicht). Wiederherstellen: `meine-touren-restore <datei.zip>`.
* **Bestehende Installation unter dem alten Namen „komoot-hub“** bleibt mit ihren Pfaden und Befehlen (`komoot-hub-update` …) erhalten; die Skripte erkennen das selbst.

## Hinweise

* Komoot und Zepp bieten keine offizielle Schnittstelle für Privatpersonen; die Anbindungen nutzen inoffizielle Aufrufe und können jederzeit brechen. Prüfe die Nutzungsbedingungen der Dienste. Strava wird über die offizielle API angebunden.
* Dieses Projekt steht in keiner Verbindung zu Komoot, Strava, Zepp/Huami, Proxmox oder community-scripts. Alle Marken gehören ihren Inhabern.
* Es wird nie etwas bei Komoot, Zepp oder im Originalfotoordner gelöscht.
* Die Oberfläche braucht Internet für Kartenkacheln (OpenStreetMap u. a.), Höhen-/Wetterdaten und Ortsnamen (Open-Meteo, Nominatim, Overpass). Bitte die jeweiligen Nutzungsrichtlinien beachten.
* Läuft im Heimnetz; für Zugriff von außen ein VPN oder Reverse-Proxy mit HTTPS davorschalten.

## Entwicklung

```bash
pip install -r requirements.txt pytest httpx
python -m pytest -q tests
DATA_DIR=/tmp/mt uvicorn app.main:app --port 8080
```

Quellen/Lizenzen: Zepp-Anmeldung nach *huami-token* (MIT), Spurdekodierung nach *Mi-Fit-and-Zepp-workout-exporter* (MIT) und *MiFitDataExport*; Karten mit Leaflet (BSD-2) und MapLibre GL (BSD-3), Schrift Barlow (SIL OFL) – im Paket enthalten. Proxmox-Skripte im Stil von [community-scripts](https://github.com/community-scripts/ProxmoxVE) (MIT). Lizenz dieses Projekts: [MIT](LICENSE).

## Foto-Zeit-Abgleich (Mac, optional)

`mac/foto_zeit_abgleich.py` korrigiert die Aufnahmezeit exportierter JPEGs (z. B. aus Lightroom) anhand der RAW-Originale (ARW).
Festplatten nacheinander einlesen (`index /Volumes/Platte1`), dann `check` (nur Bericht) bzw. `fix` für den JPEG-Ordner; `undo` macht den letzten Lauf rückgängig. Nur Python 3 nötig. Details: `python3 mac/foto_zeit_abgleich.py -h`.


## Lokal auf Windows

Für Tests oder den Einsatz auf einem einzelnen PC (der Dauerbetrieb gehört weiterhin auf einen Server).

1. Python 3.10 oder neuer installieren: `winget install Python.Python.3.12`
2. ZIP/Release entpacken und im Ordner `windows` die Datei `Meine-Touren-lokal.bat` doppelklicken. Beim ersten Start wird alles eingerichtet (eigene Python-Umgebung unter `%LOCALAPPDATA%\meine-touren-venv`).
3. Der Browser öffnet sich auf `http://localhost:8080` (anderer Port: `Meine-Touren-lokal.bat 9000`).

Daten liegen in `%USERPROFILE%\Meine-Touren-Daten` (Umgebungsvariable `MT_DATA` ändert das), die Fotoquelle ist standardmäßig „Eigene Bilder“ (`MT_FOTOS`). Updates lassen sich in der Oberfläche installieren; das Fenster startet die App danach selbst neu. Die automatischen Tests laufen bei jedem Commit auch auf Windows (GitHub Actions); unter **Windows 11** wurde Version 1.7.3 praktisch erprobt, es wurden keine Fehler gefunden (Stand 6. November 2026).

## Lokal auf dem Mac

Ohne Server: ZIP entpacken, im Ordner `mac` die Datei `Meine-Touren-lokal.command` per Doppelklick starten
(beim ersten Mal Rechtsklick → Öffnen). Sie richtet eine Python-Umgebung ein (Python ≥ 3.10, z. B. `brew install python`),
startet die App auf <http://127.0.0.1:8080> und öffnet den Browser. Die Daten liegen getrennt vom Server in
`~/Meine-Touren-Daten` (anderer Ort: Umgebungsvariable `MT_DATA`). Die Mac-Version nutzt dieselben Funktionen
(Komoot/Zepp-Import, Auswertung, Karte); Fotos per Browser-Upload oder Ordner einlesen.

### Foto-Werkzeuge für den Mac (Ordner `mac/`)

- `foto_auswahl.py` – wählt aus Lightroom-Fotos je Tag die besten aus und exportiert sie als druckfertige JPEGs nach `Aktivitäten/Jahr/Monat/Tag`.
- `foto_zeit_katalog.py` – ergänzt fehlende Aufnahmezeiten in exportierten JPEGs aus dem Lightroom-Katalog (`--undo` macht den letzten Lauf rückgängig).
- `foto_gps.py` – ergänzt GPS in den JPEGs aus den Strecken von „Meine Touren“: Die Aufnahmezeit wird mit den Tourzeiten verglichen, die Position auf der Strecke interpoliert. Probelauf ohne Option, `--anwenden` schreibt, `--undo` macht rückgängig. Fotos außerhalb jeder Tour (± 10 min) bleiben ohne GPS und stehen in `ohne_gps.txt`.

### Daten in eine neue Installation übernehmen

Den Datenordner der alten Installation (Standard `/var/lib/meine-touren`, enthält `system.sqlite` und `users/`) auf die neue Installation kopieren, **bevor** sie zum ersten Mal gestartet wird – oder bei gestoppter App – und die Rechte dem Dienstbenutzer geben. Einzelne Benutzer lassen sich über den Ordner `users/<name>` mitnehmen; Sicherungen (`*.zip`) enthalten dieselben Daten und können in der Verwaltung zurückgespielt werden.

### Foto-Auswahl in Meine Touren übernehmen

Die exportierten Fotos aus `Aktivitäten/` lassen sich über den Eingangsordner (`inbox/` des Benutzers, Standard `~/Meine-Touren-Daten/users/<Name>/inbox`) importieren: Dateien dorthin kopieren, Meine Touren erkennt sie nach wenigen Minuten selbst und ordnet sie den Touren zu. Alternativ in der Verwaltung „Fotos aus Ordner übernehmen“ (Ordner wählen).

`foto_gps.py` kennt zusätzlich `--tagesort` (Fotos ohne Tour erhalten die mittlere Position der GPS-Fotos desselben Tagesordners) und `--orte datei.csv` (Zeilen `JJJJ-MM-TT;Breite;Länge`, auch `JJJJ-MM` oder `JJJJ`).

### Garmin, Suunto und andere Uhren

**Verwaltung → „Garmin, Suunto & andere Uhren“.** Alles landet als *lokale* Tour (mit Doppelten-Prüfung gegen vorhandene Touren); zu Komoot/Strava wird nur auf ausdrücklichen Wunsch hochgeladen.

1. **Dateien (funktioniert immer, für jeden Hersteller):** FIT-, GPX-, TCX- oder ZIP-Dateien importieren. Eine ZIP darf beliebig viele Aktivitäten enthalten, auch verschachtelt – also genau das, was Garmin als Gesamtexport schickt. FIT-Dateien werden ohne Zusatzpaket gelesen (Sportart, GPS, Höhe); Dateien ohne GPS (Schlaf, Alltag, Indoor) werden übersprungen und gezählt.
   * *Garmin, alles:* [garmin.com/account/datamanagement](https://www.garmin.com/account/datamanagement/) → „Daten exportieren“ (Garmin schickt nach 1–2 Tagen eine ZIP per E-Mail).
   * *Garmin, einzeln:* Garmin Connect → Aktivität → ⚙ → „Original exportieren“ oder GPX.
   * *Suunto:* Suunto-App → Training → ⋮ → Exportieren → FIT oder GPX.
   * *Große ZIP-Dateien* (über 1 GB) statt per Browser einfach in den Ordner `inbox/touren/` des Benutzers legen; sie werden automatisch übernommen und nach `erledigt/` verschoben.
2. **Garmin-Konto (experimentell):** Anmeldung wie im Browser mit E-Mail und Passwort (inkl. Zwei-Faktor-Code) über das optionale Paket [`garminconnect`](https://github.com/cyberjunky/python-garminconnect) (braucht Python ≥ 3.12; `install.sh` versucht es zu installieren, sonst `pip install -r requirements-optional.txt` im venv). Das Passwort wird nicht gespeichert, nur der Anmelde-Schlüssel (verschlüsselt). Garmin bietet Privatpersonen **keine offizielle Schnittstelle**; die Anmeldung kann sich ändern oder zeitweise mit HTTP 429 gebremst werden – der Dateiweg bleibt davon unberührt. Optional: nur ab einem Datum, täglich automatisch.
3. **Suunto-Konto (nur mit API-Zugang):** Suunto vergibt seine Cloud-API ausschließlich an Firmen/Organisationen ([Partnerprogramm](https://apizone.suunto.com/how-to-start)), nicht an Privatpersonen. Wer einen Zugang hat, trägt Client-ID, Client-Secret und Subscription-Key ein und verbindet per OAuth.
4. **Über Komoot:** Garmin Connect und die Suunto-App können direkt mit Komoot verbunden werden; dann erscheinen die Touren ohnehin über „Komoot aktualisieren“.

> Garmin- und Suunto-Anbindung konnten vom Autor mangels Uhren nicht gegen echte Konten getestet werden; die Tests laufen gegen nachgebaute Antworten, der FIT-Leser gegen eine unabhängig erzeugte FIT-Datei. Rückmeldungen und Beispiel-Dateien sind willkommen.

### Fotos importieren und zuordnen

**Fotos → „Fotos importieren …“** (auch in der Verwaltung und im Tourdetail unter „Fotos hinzufügen …“): Ordner oder einzelne Fotos auswählen oder einfach ins Fenster ziehen. Die App liest Aufnahmezeit und Aufnahmeort aus den Bildern und zeigt vorab **je Aufnahmetag**, welcher Tour die Fotos zugeordnet werden; pro Tag lässt sich die Auswahl ändern („nach Uhrzeit“, andere Tour, „ohne Tour“, „nicht importieren“). Ein Klick startet den Import, danach steht da, wie viele Fotos Touren zugeordnet wurden.

Die Zuordnung nutzt Zeit **und** Ort: Überlappen sich Touren, entscheidet der Abstand des Fotos zur Strecke; ein Foto, das weit (über 10 km) von der Strecke aufgenommen wurde, wird nicht zugeordnet. Geht die Kamerauhr falsch (Zeitzone, nie gestellt), erkennt die App das an den Fotos mit Aufnahmeort und bietet beim Import eine **minutengenaue Zeitkorrektur** an; bei bereits importierten Fotos prüft **„Zeit per GPS prüfen“** im Tourdetail die Uhrzeiten und korrigiert sie nach Rückfrage.

### Fotos auf der Strecke ausrichten

Im Tourdetail öffnet **„📍 Fotos ausrichten“** die Karte im Ausrichtungsmodus: Ein Foto wird auf die Stelle der Strecke gezogen, an der man sicher ist, dass es dort entstand; alle anderen Fotos wandern wie auf einer Perlenkette im gleichen zeitlichen Abstand mit (mit Uhrzeit-Beschriftung). „Speichern“ verschiebt die Aufnahmezeiten dauerhaft um diesen Betrag (wahlweise auch die anderen Fotos desselben Tages); „Original-Zeiten“ nimmt jede Verschiebung zurück. Voraussetzung: die Strecke enthält Zeitstempel.

### Neu in Version 1.3

* **Zeit nachträglich verschieben:** im Fotoraster Fotos auswählen → **„Zeit verschieben …“** (Stunden/Minuten, wahlweise nur Auswahl, ganzer Aufnahmetag oder alle noch nicht zugeordneten Fotos); die Zuordnung zu Touren wird danach neu berechnet. Ist die Strecke mit Zeitstempeln vorhanden, schlägt **„Zeit per GPS prüfen“** den Versatz vor.
* **Fehlerliste beim Import:** Fotos, die nicht gelesen oder hochgeladen werden konnten, stehen einzeln mit Grund da.
* **HEIC/HEIF (iPhone):** werden beim Import in JPEG umgewandelt, wenn das optionale Paket `pillow-heif` installiert ist (`pip install pillow-heif`; die Startskripte und `install.sh` versuchen es selbst). Ohne das Paket nennt die Fehlerliste den Grund.
* **Kartenvorschau** im Importfenster: pro Aufnahmetag die Strecke der Tour und die Fotostandorte.
* **„Jetzt sichern“** direkt in der Hinweisleiste und unter Verwaltung → Zustand.
* **Mac-Update per Doppelklick:** `mac/Meine-Touren-aktualisieren.command` lädt die neueste Version von GitHub und ersetzt die Programmdateien (Daten bleiben unberührt, die alte Fassung liegt in `.vorher/`).
* **Englische, französische und spanische Oberfläche (Beta):** Sprachauswahl (DE/EN/FR/ES) oben rechts; Standard nach Browsersprache. Die Übersetzung läuft über Wörterbücher (`app/static/js/00-i18n.js` für Englisch, `00-i18n-data.js` für Französisch und Spanisch; Zeilen „deutsch|übersetzung“ zum Ergänzen) und ist noch nicht vollständig – nicht Übersetztes bleibt deutsch; Meldungen vom Server sind überwiegend deutsch. Datums- und Zahlenformate wechseln mit.
* **Demo-Modus:** `mac/Meine-Touren-Demo.command` bzw. `windows/Meine-Touren-Demo.bat` (oder `python -m app.demo`) startet die App auf Port 8090 mit 14 erfundenen Touren und 15 Beispielfotos in einem eigenen Datenordner (`~/Meine-Touren-Demo`) – ohne eigene Daten, ohne Konten, ohne Netzwerk. Gut zum Ausprobieren und für Screenshots. Echte Daten werden nie angefasst.

### GPS-Track korrigieren (ab 1.3.1)

Im Tourdetail öffnet **„🧹 Track korrigieren“** (und in Prüfen → Unplausible Touren der gleichnamige Knopf, bei ausgeblendeten Touren „Einblenden & Track korrigieren“) eine Karte mit den Auffälligkeiten:

* **Ausreißer** (rot): Punkte, die mit unmöglichem Tempo vom Weg wegspringen und dann zurückkehren. Sie werden aus dem Track gelöscht, die Länge sinkt entsprechend.
* **Schnelle Abschnitte** (orange): längere Stücke dauerhaft über dem zur Sportart passenden Tempo (Wandern ab 9 km/h, Laufen 20, Rad 45), z. B. Seilbahn, Bus oder Auto. Pro Abschnitt wählbar: als Fahrt aus **Strecke und Dauer** herausrechnen (der Weg bleibt sichtbar) oder behalten.

Das Original bleibt erhalten (**„Original wiederherstellen“**). Bei Komoot-Touren gilt die Korrektur nur hier und bleibt beim Abgleich erhalten, solange Komoot die Länge nicht selbst ändert. Ohne Zeitstempel im Track lassen sich nur große Sprünge erkennen.

### Neu in Version 1.4

* **Ursache statt Vermutung:** Unter Prüfen → Unplausible Touren steht bei jeder Tour, woran es liegt (nicht aufgezeichnete Zeiten, GPS-Ausreißer, Fahrt-Abschnitte, GPS-Zittern – oder „Track unauffällig, vermutlich falsche Sportart“) und der Knopf „🧹 Track korrigieren“ ist entsprechend hervorgehoben.
* **Zeit aus Foto-Positionen:** Liegen Fotos mit GPS-Position auf dem Track (mindestens drei, im Zeitablauf passend), kann die App daraus die Zeit entlang der ganzen Strecke ableiten – Pausen eingeschlossen, genauer als eine Schätzung. Option im Dialog „Track korrigieren“.
* **Mehrtagestouren:** Touren mit Namen wie „Alpenüberquerung E5 – Tag 6“ (auch „Etappe“, „Day“, „Stage“, „Jour“, „Día“) werden gruppiert: unter Reisen als eigene Karten, im Tourdetail als Hinweis mit Gesamtansicht (Karte, Summen, Fotos, 3D-Flug). Es braucht mindestens zwei verschiedene Tagesnummern.
* **Übersetzungen** (EN/FR/ES) deutlich erweitert (Dashboard, Tourdetail, Prüfen, Fotos, Verwaltungsüberschriften); sehr lange Erklärtexte der Verwaltung sind weiterhin deutsch.
* **Selbsttest** (Verwaltung → Wartung & Sicherheit) prüft zusätzlich Datenbank-Integrität, Schreibrechte der Foto-/Eingangs-/Backup-/Streckenordner, Stichproben der Foto-Dateien, HEIC-Unterstützung, auffällige Touren, Erreichbarkeit der GitHub-Update-Prüfung und den Update-Weg. Nach einem Update auf dem Server lohnt sich ein Durchlauf.

### Neu in Version 1.5

* **Kamerauhr-Hinweis:** Prüfen → „Kamerauhr“ zeigt Touren der letzten 90 Tage, bei denen die Foto-Zeiten nicht zum Aufnahmeort passen (Kamerauhr/Zeitzone falsch). „Korrigieren“ verschiebt die Fotos um die erkannte Differenz, „Ignorieren“ merkt sich die Tour.
* **Mehrtagestouren aufräumen:** Reisen → „＋ Mehrtagestour bilden …“ benennt Touren eines Zeitraums auf einen Schlag („Name – Tag N“); in der Gesamtansicht benennt „✎ Reihe umbenennen“ alle Etappen gemeinsam. Die Kacheln unter Reisen zeigen ein Foto aus der Mitte der Reihe.
* **Tourblatt:** Im Tourdetail „📄 Tourblatt“ – eine druckbare Seite mit Kennzahlen, Karte, Höhenprofil und bis zu 6 Fotos (Drucken → als PDF speichern).
* **Höhenprofil mit Fotos:** Gelbe Punkte im Profil markieren, wo ein Foto entstanden ist; Klick öffnet das Foto, der Mauszeiger darüber zeigt die Stelle auf der Karte.
* **Wunschliste:** Auswertung → Wanderführer: Touren aus den hinterlegten Wanderführern vormerken, mit Länge (und Aufstieg, wenn die GPX-Datei Höhen enthält). Bereits gegangene Touren sind markiert. Für schon früher hochgeladene Führer fehlt der Aufstieg, bis die GPX-Dateien erneut hochgeladen werden.
* **Jahresziele mit Prognose:** zusätzlich zur Hochrechnung das voraussichtliche Erreichungsdatum, bei Rückstand die nötige Wochenleistung.
* **Touren teilen (Familie):** Freigegebene Touren anderer Benutzer lassen sich unter „Geteilte Fotos“ samt Strecke und passenden Fotos in die eigene Sammlung übernehmen (als Kopie; der Besitzer behält seine Tour unverändert).
* **Offline-Nutzung:** Die Web-App merkt sich zuletzt geladene Daten, Karten und kleine Fotos; ohne Verbindung erscheint ein Hinweisband. Verwaltung → „Für Offline vorbereiten“ lädt die letzten 8 Touren samt Kartenkacheln vorab. Voraussetzung ist HTTPS (oder localhost). Beim Abmelden wird der Daten-Zwischenspeicher gelöscht.

### Neu in Version 1.6

* **Beste Fotos einer Tour:** Im Tourdetail wählt „⭐ Beste Fotos“ aus allen Fotos die 10 besten. Berücksichtigt werden Sternebewertungen aus Lightroom (aus der Datei oder einer gleichnamigen `.xmp`-Begleitdatei; „abgelehnt“ fällt heraus), die Schärfe (unscharfe Fotos fallen heraus) und die Verteilung über die Tour. Dazu gibt es „Diashow der besten“; das Tourblatt nutzt dieselbe Auswahl (6 Fotos). Ohne Sternebewertung entscheidet die Schärfe. Die Schärfe wird beim ersten Mal berechnet (bei vielen Fotos ein paar Sekunden) und gespeichert.

### Version 1.6.1

* **Fehlerbehebung Höhenprofil:** Die gelben Foto-Marker erschienen nicht, wenn die Fotos keine GPS-Position haben (Zuordnung über die Aufnahmezeit rechnete mit falscher Zeitbasis). Jetzt werden sie über die Zeit richtig platziert.

### Version 1.6.2

* **Fehlerbehebung Reisen:** Die Titelfotos der Mehrtagestouren fehlten bei Reihen, deren Fotos nicht unter den ersten 5000 Fotos der Bibliothek lagen. Die Kachel holt sich jetzt je Tour ein Foto direkt vom Server (`/api/tour-covers`).

### Version 1.7.3

* **Diashow mit Vollbild auf Touchgeräten:** Oben rechts erscheinen Knöpfe für Vollbild (⛶), Pause und Schließen; sie blenden sich nach 3 Sekunden aus und kommen per Tippen in die Bildmitte zurück. Tippen links/rechts oder Wischen blättert, der Bildschirm bleibt während der Diashow an (wo der Browser das erlaubt). Am Computer weiterhin Leertaste, Pfeiltasten und F. **iPhone:** Safari erlaubt dort keinen Vollbildmodus für Webseiten – die Seite zeigt einen Hinweis; mit „Zum Home-Bildschirm“ öffnet die App ohne Browserleiste (iPad und Android unterstützen Vollbild direkt).

### Version 1.7.2

* **Fehlerbehebung Updates (seit 1.7.0):** Durch die neue Reiter-Verwaltung wurde der Update-Bereich verschoben und doppelt angelegt; „Jetzt prüfen“ löste einen Fehler aus. Behoben. Außerdem nennt der Update-Bereich jetzt den Grund, wenn GitHub nicht erreichbar ist (z. B. keine Verbindung, Anfragelimit).

### Version 1.7.1

* **Unbenutzte Fotos aufräumen:** Auf der Seite „Fotos“ gibt es „🧹 Unbenutzte Fotos aufräumen …“, solange Fotos keiner Tour zugeordnet sind. Der Dialog zeigt Anzahl, Speicherplatz und eine Stichprobe und lässt dich **Jahre auswählen**; erst danach ist „Löschen“ möglich. Gelöscht werden nur die Kopien in der Fotobibliothek der App, nie Originale; die Fotos tauchen beim nächsten Import nicht wieder auf. Zum Zeitpunkt des Löschens wird neu geprüft, welche Fotos noch ohne Tour sind.

### Neu in Version 1.7

* **Verwaltung neu geordnet:** Statt einer langen Seite mit Klappbereichen gibt es fünf Reiter nach Aufgaben – *Übersicht* (Zustand, Updates, Protokoll, Selbsttest), *Touren & Quellen* (Komoot, Zepp, Garmin/Suunto/Dateien, Strava, Wanderführer), *Fotos*, *Automatik* und *Sicherung & Zugang* (Backup, Zugriffsschutz, Offline). „Einstellungen speichern“ bleibt auf jedem Reiter unten sichtbar. Der zuletzt gewählte Reiter wird gemerkt; Adressen wie `#/admin?tab=fotos` führen direkt hin.
* **Wie oft gelaufen?** Die App erkennt Touren, die dieselbe Strecke gehen (Länge ±20 %, mindestens 85 % der Strecke innerhalb von 60 m, auch in Gegenrichtung). In der Tourliste steht dann „🔁 3×“, im Tourdetail „Diese Strecke bist du schon 3-mal gegangen – das war das 2. Mal“ mit Links zu den anderen Begehungen.

### Version 1.6.3

* **Foto-Import, Kartenvorschau:** Aufnahmezeiten ohne Zeitzonenangabe werden in der Zeitzone des Servers gelesen, nicht in der des Browsers. Auf Reisen (Browser in anderer Zeitzone als der Server) stimmte sonst die Vorschau „x von y Fotos liegen auf der Strecke“ nicht. Der eigentliche Import war nicht betroffen.
* Automatische Tests auf GitHub: zwei fehlerhafte Annahmen in den Tests korrigiert (Dateireihenfolge, Backup-Ordner).

### Updates aus der Oberfläche

Die App prüft alle 6 Stunden auf GitHub, ob eine neuere Version veröffentlicht ist (abschaltbar), und weist Administratoren darauf hin (Hinweisleiste, Verwaltung → Updates, optional Webhook). **„Installieren“** legt zuerst eine Sicherung für jeden Benutzer an und installiert dann:

* *Proxmox/Server:* Die App läuft ohne Root-Rechte und schreibt nur die gewünschte **Versionsnummer** nach `<Datenordner>/update-request`. Der kleine Systemdienst `<name>-update.path` (wird von `install.sh` eingerichtet) startet daraufhin `<name>-update auto` als root, das die Version `vX.Y.Z` selbst von GitHub lädt, prüft, dass sie neuer ist, und wie gewohnt installiert. Die App kann also keinen eigenen Programmcode einschleusen. **Einmalig** muss ein bestehender Container noch von Hand auf diese Version gebracht werden (`meine-touren-update github`); danach klappt es per Knopfdruck. Ablauf und Fehler stehen unter `journalctl -u meine-touren-update`.
* *Mac-Testversion:* Die App ersetzt ihre Programmdateien (alte Fassung in `.vorher/`) und startet über `Meine-Touren-lokal.command` neu.

### Verwaltung → Zustand

Die Verwaltung zeigt oben eine Zustandsprüfung (Komoot-Zugang, Backup, Datenbankgröße, freier Speicher, Touren ohne Strecke, Fotos ohne Tour) und – siehe unten – auf neuere Versionen auf GitHub.

### Zugangsdaten verschlüsselt

Komoot-Passwort, Strava- und Zepp-Zugangsdaten liegen verschlüsselt (AES-256-GCM) in der Datenbank. Der Schlüssel steht in `<Datenordner>/secret.key` (wird beim ersten Start angelegt, nur für den Dienstbenutzer lesbar) oder – wenn gesetzt – in der Umgebungsvariable `MT_SECRET_KEY`. Die Schlüsseldatei ist absichtlich **nicht** Teil der Sicherungen. Wer eine Sicherung auf einem neuen Rechner einspielt, kopiert `secret.key` mit oder gibt die Zugangsdaten danach in der Verwaltung neu ein. Vorhandene Klartext-Einträge älterer Versionen werden beim ersten Lesen automatisch verschlüsselt.

## Für Entwickler

- Oberfläche ohne Build-Schritt: `app/static/js/01-grundlagen.js` … `12-start.js` werden in dieser Reihenfolge von `index.html` geladen (gemeinsamer globaler Bereich). Formatierung mit Prettier (`.prettierrc`): `npx prettier --write app/static/js/*.js`.
- Tests: `python -m pytest -q tests` – darunter Browsertests mit Playwright (`pip install playwright && python -m playwright install chromium`), die jede Ansicht mit Beispieldaten öffnen und auf JavaScript-Fehler prüfen.
