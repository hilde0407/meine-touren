# Meine Touren auf TrueNAS Scale – mit Tailscale, Funnel und 2FA

Getestet mit TrueNAS Community Edition (Apps auf Docker-Basis, 24.10 oder neuer). Menünamen können je nach Version leicht abweichen.

## Was am Ende läuft

Zwei Container in **einer** TrueNAS-App: ein Tailscale-Container und die Touren-App. Die Touren-App teilt sich das Netzwerk des Tailscale-Containers (`network_mode: service:tailscale`). Es gibt **keine Port-Weiterleitung im Router** und keinen offenen Port auf der TrueNAS. Von außen kommt man nur über `https://<name>.<dein-tailnet>.ts.net`.

Reihenfolge: erst alles privat im Tailnet zum Laufen bringen, dann 2FA einrichten, **erst danach** Funnel einschalten.

In dieser Anleitung stehen `datapool` für den Namen deines Pools und `<dein-tailnet>` für den Namen deines Tailnets (zu sehen unter DNS in der Tailscale-Konsole, z. B. `tail1a2b3c`). Beides ersetzt du.

## 1. Tailscale vorbereiten (Admin-Konsole)

Alles unter https://login.tailscale.com/admin.

1. **MagicDNS** einschalten: *DNS* → MagicDNS aktivieren.
2. **HTTPS-Zertifikate** einschalten: *DNS* → *HTTPS Certificates*. Ohne das gibt es weder HTTPS über `tailscale serve` noch Funnel.
3. **Funnel erlauben:** *Access controls*, im Abschnitt `nodeAttrs` ergänzen und speichern:

   ```json
   "nodeAttrs": [
     { "target": ["autogroup:member"], "attr": ["funnel"] }
   ]
   ```
4. **Auth-Key erzeugen:** *Settings* → *Keys* → *Generate auth key*. *Reusable* aus, *Ephemeral* **aus**, Ablauf 90 Tage. Der Schlüssel (`tskey-auth-…`) wird nur beim ersten Anmelden gebraucht.
5. **Alten Eintrag entfernen:** Gibt es unter *Machines* schon einen Rechner mit dem gewünschten Namen (z. B. von einer früheren Installation), bekommt der neue den Zusatz `-1` oder den Namen des Hostrechners. Alten Eintrag löschen oder einen anderen `TS_HOSTNAME` wählen. Die Adresse steht später im Protokoll des Tailscale-Containers und in der Konsole bei *Machines*; **dieser** Name ist die Adresse, die auch für Funnel gilt.

## 2. Ordner (Datasets) anlegen

*Datasets* → unter dem Pool ein Dataset `touren` anlegen (Vorgabe „Generic“). Darin drei Unterordner, am einfachsten in der TrueNAS-Shell (*System* → *Shell*):

```
mkdir -p /mnt/datapool/touren/{data,tailscale,config}
chown 568:568 /mnt/datapool/touren/data
```

Der Name `touren` ist frei wählbar; manche Namen (z. B. `apps`) können mit TrueNAS-eigenen Bereichen kollidieren. Nicht unter `/mnt/.ix-apps/` arbeiten – das gehört dem System.

Datei `/mnt/datapool/touren/config/serve.json` anlegen, zunächst mit **Funnel aus**:

```json
{
  "TCP": { "443": { "HTTPS": true } },
  "Web": {
    "${TS_CERT_DOMAIN}:443": {
      "Handlers": { "/": { "Proxy": "http://127.0.0.1:8080" } }
    }
  },
  "AllowFunnel": { "${TS_CERT_DOMAIN}:443": false }
}
```

## 3. App installieren

*Apps* → *Discover Apps* → *Custom App* → *Install via YAML*. Anwendungsname `meine-touren`. Einfügen (Pool, Auth-Key und ggf. Zeitzone anpassen):

```yaml
services:
  tailscale:
    image: tailscale/tailscale:latest
    hostname: meine-touren
    restart: unless-stopped
    environment:
      TS_AUTHKEY: tskey-auth-HIER-EINFUEGEN
      TS_HOSTNAME: meine-touren
      TS_STATE_DIR: /var/lib/tailscale
      TS_USERSPACE: "true"
      TS_SERVE_CONFIG: /config/serve.json
    volumes:
      - /mnt/datapool/touren/tailscale:/var/lib/tailscale
      - /mnt/datapool/touren/config:/config:ro
    # Optional: Zugriff im Heimnetz ohne Tailscale. Den Port NIEMALS im Router freigeben.
    ports:
      - "30080:8080"

  meine-touren:
    image: ghcr.io/hilde0407/meine-touren:latest
    restart: unless-stopped
    network_mode: service:tailscale
    depends_on:
      - tailscale
    environment:
      PUID: "568"
      PGID: "568"
      TZ: Europe/Berlin
    volumes:
      - /mnt/datapool/touren/data:/data
```

`TS_USERSPACE: "true"` braucht weder `/dev/net/tun` noch Zusatzrechte – das ist besonders sinnvoll, wenn die TrueNAS selbst eine virtuelle Maschine ist.

Nach dem Start im Protokoll des Containers `tailscale` prüfen, dass er angemeldet ist („Switching ipn state … Running“), und das Zertifikat ausgestellt wurde („got cert“). Danach die Zeile `TS_AUTHKEY` aus der YAML **entfernen** (App bearbeiten, speichern). Den Ordner `tailscale` nicht löschen, sonst meldet sich der Container als neues Gerät an.

Host-Ports für Apps liegen ab 9000 (typisch 30000+); 80 und 443 gehören der TrueNAS-Oberfläche.

## 4. Erster Test (noch ohne Funnel)

1. Im Heimnetz: `http://<TrueNAS-IP>:30080/api/version` → `{"version":"…"}`.
2. Mit dem Handy im Mobilfunk **mit aktivem Tailscale**: `https://<name>.<dein-tailnet>.ts.net`. Anmeldeseite mit gültigem Zertifikat.
3. Beim ersten Aufruf das Administrator-Konto anlegen, mit langem Passwort (im Passwortmanager speichern).

## 5. Zwei-Faktor-Anmeldung (2FA) – vor Funnel

Die App unterstützt zeitbasierte Einmalcodes (TOTP) mit jeder Authenticator-App.

1. In der App anmelden → Einstellungen → Konto/Sicherheit → Zwei-Faktor-Anmeldung einschalten.
2. QR-Code scannen, den sechsstelligen Code eingeben.
3. Die **8 Wiederherstellungscodes** (jeder gilt einmal) ausdrucken oder im Passwortmanager ablegen, nicht nur auf dem Handy.
4. Abmelden und im privaten Fenster testen: Nach dem Passwort muss der Code verlangt werden.

Wichtig:

- 2FA gilt **pro Konto**; es lässt sich nicht für alle erzwingen. Jeder Benutzer mit Schreibrechten muss es selbst einschalten.
- **Betrachter-Konten haben keine 2FA.** Unter Funnel sind sie nur durch das Passwort geschützt – am besten keine anlegen, solange Funnel an ist, sondern Freigabe-Links für einzelne Touren nutzen.
- Nach 5 falschen Codes muss man neu anmelden; ein Administrator kann 2FA eines Kontos unter *Benutzer verwalten* zurücksetzen.
- Passwort: nach 6 Fehlversuchen in 5 Minuten wird die Kombination aus Name und Adresse kurz gesperrt.

## 6. Funnel einschalten

Erst wenn 2FA für alle Konten mit Schreibrechten läuft.

1. In `serve.json` die letzte Zeile auf `"${TS_CERT_DOMAIN}:443": true` ändern.
2. App stoppen und wieder starten (der Tailscale-Container liest die Datei beim Start).
3. Im Protokoll von `tailscale` erscheint „Hostinfo.IngressEnabled changed to true“.
4. Test **ohne Tailscale** (Handy im Mobilfunk, Tailscale-App aus): die Adresse muss die Anmeldeseite zeigen. Direkt nach dem ersten Einschalten kann es einige Minuten dauern, bis der Name im öffentlichen DNS ankommt.

Funnel darf nur die Ports 443, 8443 und 10000 nutzen; hier wird 443 verwendet.

**Test der Sperre:** Im Mobilfunk (ohne Tailscale) 6-mal mit falschem Passwort anmelden, danach mit dem normalen Gerät aus einem anderen Netz. Klappt das, wird die Absenderadresse richtig erkannt. Wenn nicht, zählt die Sperre alle Besucher als einen Absender.

## 7. Einstellungen in der App

- *Standort teilen*: **Aus** lassen.
- *Öffentliche Adresse* (E-Mail-Einstellungen): die Funnel-Adresse eintragen, damit Links in E-Mails stimmen.
- Freigabe-Links (`/s/…`) sind für jeden mit dem Link sichtbar: befristen und nach Gebrauch löschen.

## 8. Fehlersuche

| Beobachtung | Ursache / Lösung |
|---|---|
| Image wird nicht geladen | In der TrueNAS-Shell `ping -c2 ghcr.io` und `docker pull ghcr.io/hilde0407/meine-touren:latest`. Schlägt die Namensauflösung fehl: DNS prüfen. Antwortet ein zweiter DNS-Server nicht, entfernen oder ersetzen (*Netzwerk* → *Globale Konfiguration*). |
| Tailscale-Protokoll: „TUN“-Fehler | `TS_USERSPACE: "true"` gesetzt? Dann braucht es weder Tun noch NET_ADMIN. |
| „auth key invalid/expired“ | Neuen Schlüssel erzeugen, einmal eintragen, danach wieder entfernen. Ordner `tailscale` vorher leeren, wenn der Rechner in der Konsole gelöscht wurde. |
| Rechner heißt anders als `TS_HOSTNAME` | Name war schon vergeben (Schritt 1.5). Die tatsächliche Adresse steht bei *Machines* und im Protokoll („Fetching TLS certificate … für <Name>.ts.net“). |
| Zertifikatsfehler / „HTTPS not enabled“ | Schritt 1.2 fehlt. Danach Container neu starten. |
| Funnel-Adresse geht nicht, privat schon | Schritt 1.3 (`funnel`-Attribut) fehlt, `AllowFunnel` steht noch auf `false`, oder die **falsche Adresse** (siehe oben) wird aufgerufen. |
| Port 30080 antwortet nicht im LAN | App läuft? Port belegt → anderen ab 9000 wählen. Test von der TrueNAS: `curl http://127.0.0.1:30080/api/version`. |

## 9. Sicherheit unter Funnel

- Kein Port im Router freigeben, auch nicht 30080. Die App vertraut den Weiterleitungs-Kopfzeilen (`X-Forwarded-For`), das ist nur sicher, wenn sie ausschließlich über Tailscale erreichbar ist.
- Die Anmeldeseite ist dann öffentlich: langes Passwort, 2FA bei allen Schreibkonten, keine Betrachter-Konten, Wiederherstellungscodes sicher aufbewahren.
- Regelmäßig aktualisieren (siehe unten) und den Ordner `data` (Datenbank, Fotos) per Snapshot sichern.

## 10. Update

App stoppen, in der TrueNAS-Shell `docker pull ghcr.io/hilde0407/meine-touren:latest`, App starten. Vorher einen Snapshot des Datasets `touren` anlegen. (`:latest` wird nicht in jedem Fall automatisch neu geladen.)

## 11. Funnel wieder ausschalten

In `serve.json` `"AllowFunnel"` auf `false`, App neu starten. Die Seite bleibt über das Tailnet erreichbar, aber nicht mehr öffentlich.
