# Tests

Rund 1690 Tests: schnelle Tests des Servers (in-process, `TestClient`) und Browsertests mit Playwright/Chromium (`*_ui.py`, `test_browser.py` u. a.).

## Starten

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium

python scripts/test.py                                   # schneller Kern (Standard), parallel, mit --reruns 2 (wie die CI bei jedem Push)
python scripts/test.py --voll                            # volle Suite (Kern + alle übrigen Browsertests) – vor dem Veröffentlichen
python scripts/test.py --rest                            # nur die Tests außerhalb des Kerns
python scripts/test.py tests/test_gruppen_ui.py -k link  # Auswahl: alle genannten Tests (ohne Kern-Filter); weitere Argumente gehen an pytest
MT_TEST_WORKERS=1 python scripts/test.py                 # seriell (Fehlersuche)
MT_TEST_RERUNS=0 python scripts/test.py                  # ohne Wiederholung: Flakes sichtbar machen
MT_TEST_TIMEOUT=0 python scripts/test.py                 # ohne Zeitgrenze je Test (Standard 600 s: ein hängender Test scheitert und wird wiederholt, statt den Lauf anzuhalten)
MT_CPU_THROTTLE=6 python -m pytest -q tests/test_x_ui.py # Stresstest: CPU der Browserseiten um Faktor 6 bremsen
```

`python -m pytest -q tests` geht weiterhin (seriell, ohne Wiederholung, alles); `python -m pytest -m "not voll" tests` ist der Kern. Parallel immer mit `--dist loadfile` (ganze Dateien je Worker): die Browsertests starten ihren Server
je Datei einmal (`scope="module"`), einzelne Tests einer Datei teilen sich Datenbank und Server und räumen per `clean`-Fixture auf.

## Kern und volle Suite

Die volle Suite braucht in der CI rund 17–20 Minuten, fast alles davon sind Browsertests. Deshalb gibt es zwei Töpfe:

| Topf | Inhalt | Wann |
| --- | --- | --- |
| **Kern** (`-m "not voll"`, `scripts/test.py`) | alle Server-, Unit-, Format- und Stiltests (ohne Browser) **und** eine Stichprobe von Browsertests mit `@pytest.mark.kern`: je Hauptseite ein Rauchtest (alle Ansichten ohne JavaScript-Fehler, Tourseite, Tourenliste mit Fotos, Statistik, Verwaltung, Aufzeichnen im Browser und in der App, Foto-Streifen, Wanderführer, Übersicht mit Bildern, Seite anpassen, Karte, Betrachter) | jeder Push und Pull-Request (Workflow „Tests“), lokal im Alltag |
| **voll** (ohne `-m`, `scripts/test.py --voll`) | Kern + alle übrigen Browsertests (`-m voll`) | vor jedem Veröffentlichen (Workflow „Veröffentlichen“ ruft „Tests (voll)“ auf; schlägt sie fehl, entsteht keine Veröffentlichung), nachts bei neuen Commits, wöchentlich (Montag, dazu Windows), manuell (Actions → „Tests“ oder „Tests (voll)“), und bei einem Push mit `[voll]` in der Commit-Nachricht. Windows unverändert: wöchentlich, manuell oder `[windows]`. |

**Einordnung neuer Tests – automatisch:** Tests ohne Browser landen immer im Kern. Browsertests werden an ihrem Quelltext erkannt (Testfunktion, ihre Fixtures und die Hilfsfunktionen, die sie aufruft:
`playwright`, `sync_playwright`, `.goto(`, `.new_page(`, `chromium`) und bekommen in `conftest.py` den Marker `voll` – außer sie tragen `@pytest.mark.kern`.
Warum so und nicht „ohne Marker = Kern“: Neue Browsertests würden den Kern sonst still wachsen lassen, bis er wieder so langsam ist wie die volle Suite; und eine Marker-Pflicht für über 800 Browsertests wäre fehleranfällig.
Kein Test kann verloren gehen: die volle Suite ist immer „alles“, und sie läuft vor jedem Veröffentlichen. Zwei Sicherungen:

* Startet ein Test einen Browser, ohne als Browsertest erkannt worden zu sein, schlägt er mit einem Hinweis fehl (dann `@pytest.mark.browser` setzen) – der Kern wird nie unbemerkt langsam.
* `tests/test_testsuite_kern.py` prüft: Kern + Rest = alle gesammelten Tests (keine Lücke, keine Doppelung), jede Hauptseite hat eine Stichprobe im Kern, Skript und Workflows nutzen die Töpfe richtig.

Eine neue Hauptseite oder ein neues großes Feature bekommt **einen** schnellen Rauchtest mit `@pytest.mark.kern` (und einen Eintrag in `test_jede_hauptseite_hat_eine_stichprobe_im_kern`); alles Übrige läuft in der vollen Suite.
Eine Stichprobe soll schnell sein (eine vorhandene Datei mit ohnehin gestartetem Server bevorzugen, wenige Sekunden je Test).

## Aufbau

* `conftest.py` – ein Playwright und ein Chromium je Prozess (Worker) statt je Test; `sync_playwright()` und `pw.chromium.launch()` in den Tests liefern den gemeinsamen Browser,
  `b.close()` schließt nur die eigenen Kontexte, nach jedem Test werden alle offenen Kontexte geschlossen. Jeder Kontext bekommt den Zähler für `quiet` (siehe unten).
* `helpers_ui.py` – gemeinsame Hilfen (siehe nächster Abschnitt).
* `test_core.py` – Testumgebung der Server-Tests (`fresh`-Fixture; `DATA_DIR`/`PHOTOS_DIR` je xdist-Worker eigen).
* Browsertests starten ihren Server als Unterprozess auf einem freien Port (`port 0`) mit eigenem `DATA_DIR` unter `tmp_path_factory`; nie feste Ports oder feste Pfade verwenden.

## Hilfen (`tests/helpers_ui.py`)

| Hilfe | Wofür |
| --- | --- |
| `quiet(pg, cap, quiet_ms)` | wartet, bis keine fetch/XHR-Anfrage mehr läuft und sich das DOM `quiet_ms` (300 ms) nicht geändert hat, höchstens `cap` ms. Ersatz für `wait_for_timeout(cap)` nach Navigation/Klick |
| `settled(pg)` | `quiet` plus Schriften geladen und stabile Seitenhöhe – vor Messungen (Boxen, Abstände) und Screenshots |
| `open_details(pg, sel, open)` | `<details>` explizit auf offen/zu setzen und warten (kein Umkehren durch Klick) |
| `toggle_details(pg, sel, open)` | dasselbe per Klick auf die Zusammenfassung, für Tests, die das Klicken prüfen; wartet erst auf Ruhe und klickt nur, wenn der Zustand nicht passt |
| `wait_route(pg, "#/tour/")` | auf die Route warten |
| `set_lang(pg, "en")` | Sprache umstellen und auf das Neuzeichnen warten |
| `eager_images(pg)` | `loading=lazy`-Bilder sofort laden und abwarten (für Messungen/Screenshots) |
| `press_until_gone(pg, "Escape", ".dlg")` | Taste wiederholen, bis ein Dialog weg ist (ein einzelner Druck kann vor dem Fokus verpuffen) |
| `free_port()`, `wait_http(url)` | freier Port, Warten auf den Server |

## Regeln gegen Flakes

1. **Nie nur schlafen.** Nach jeder Aktion auf einen Zustand warten: `expect(loc).to_...(timeout=15000)`, `wait_for_function("() => ...", timeout=15000)` (nur Pfeilfunktionen als Strings, die CSP verbietet `eval`-Strings),
   `wait_route`. Ist nur „fertig aufgebaut“ gemeint, `quiet`/`settled` statt `wait_for_timeout`. Ein fester Schlaf ist nur erlaubt, wenn die Zeit selbst getestet wird (Diashow-Takt, Ablauf einer Zurückstellung).
2. **`wait_for_load_state("networkidle")` hilft nach dem ersten Laden nicht** (Hash-Navigation, Nachladen per fetch: der Zustand ist schon „erreicht“) – `quiet` verwenden.
3. **Auf-/Zuklappbares nie „prüfen und klicken“.** Zustand setzen (`open_details`) oder mit `toggle_details` herstellen; Seiten bauen Bausteine beim Nachladen neu auf und setzen den gemerkten Zustand zurück.
4. **Messen erst nach `settled`**; vor `bounding_box()`, Abständen, Scrollhöhen und Screenshots. Karten (Leaflet): auf die Größe der Karte warten, `quiet` mit `quiet_ms` > 350 (entprellte `moveend`-Nachlader).
5. **Lazy Bilder** vor Messungen mit `eager_images` laden.
6. **Abgefangene Antworten (`page.route`) dürfen nicht von Hintergrundabfragen der Seite verbraucht werden**: Antwortfolgen erst nach dem auslösenden Klick/Start scharf schalten (Beispiel `Fake.start_script` in `test_zepp_uebersicht_ui.py`).
7. **Eine Taste/ein Klick kann verpuffen, solange der Dialog noch aufgebaut wird**: erst `quiet`, bei Dialogen `press_until_gone`.
8. **Zeit und Datum**: Testdaten relativ zu „heute“ bauen (`now - N * 86400`), nie feste Kalenderdaten als Erwartung; Erwartungen mit Jahr aus `date.today()` ableiten; nicht von der Tageszeit abhängen.
9. **Keine Zustandslecks**: Server und Datenbank sind je Datei gemeinsam – jeder Test stellt seinen Ausgangszustand selbst her (`clean`-Fixture, `PUT` des Layouts) und verlässt sich nicht auf die Reihenfolge. Keine festen Pfade/Ports; `tmp_path`/`tmp_path_factory`, Port 0.
10. **Screenshots** nur mit der jeweiligen Umgebungsvariable (`TS_SHOTS`, `MT_SHOTS`, …), nie standardmäßig.

## Flakes untersuchen

* `MT_CPU_THROTTLE=6` verlangsamt die Seiten im Browser (Wettläufe zeigen sich auch auf schnellen Rechnern); dazu den Test mehrfach laufen lassen, z. B. `for i in $(seq 10); do MT_CPU_THROTTLE=6 python -m pytest -q tests/test_x_ui.py -k name || break; done`.
* `MT_TEST_RERUNS=0 python scripts/test.py ...` zeigt auch Tests, die erst im zweiten Versuch bestehen (die CI wiederholt fehlgeschlagene Tests bis zu 2-mal und meldet sie dann als bestanden).
* Beim Parallellauf bleibt eine Datei immer in einem Worker; scheitert etwas nur parallel, mit `MT_TEST_WORKERS=1` gegenprüfen.  Bisher gibt es keinen Test, der nicht parallel zu anderen Dateien laufen darf; käme einer dazu, ihn mit `@pytest.mark.xdist_group("serial")` kennzeichnen und die CI auf `--dist loadgroup` umstellen.
