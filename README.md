# Radio LoLa

Ein Radio für den Reachy Mini Wireless. Es läuft als App direkt auf dem Roboter und wird mit einer kleinen
Android-App ein- und ausgeschaltet. Einen PC braucht man nur einmal zum Installieren.

So geht es im Alltag:

1. Roboter einschalten und etwa eine Minute warten.
2. Auf dem Handy die App **Radio LoLa** öffnen. Oben steht, ob der Roboter erreichbar ist.
3. **Radio starten** drücken. Der Roboter wacht auf, die Antennen fahren in die Grundstellung, dann spielt das Radio.
4. Bedienen wie gewohnt über die Antennen:
   - die rechte Antenne des Roboters (von vorn gesehen **links**) sucht Sender, dazwischen rauscht es,
   - die linke Antenne des Roboters (von vorn gesehen **rechts**) stellt die Lautstärke: oben ist leise, gegen den
     Uhrzeigersinn wird es lauter.
5. In der Handy-App stehen die Sender untereinander; der gerade hörbare ist mit ▶ markiert. Darunter liegt ein
   Lautstärkeregler mit **Stumm**-Knopf. Er wirkt zusätzlich zur Lautstärke-Antenne (Antenne × Handy) und bleibt
   auch nach einem Neustart des Radios so eingestellt. Regler und Markierung gehen nur, solange das Radio läuft;
   sonst zeigt die App die zuletzt gemeldete Senderliste blass an.
6. **Radio stoppen** drücken. Die Antennen fahren nacheinander heim, die Motoren werden wieder eingeschaltet.

**Nicht gleichzeitig mit LoLa benutzen.**

## a) Android-App herunterladen

**https://github.com/Moe-Joe86/Radio-LoLa/releases/latest/download/Radio-LoLa.apk**

Den Link auf dem Handy öffnen. Android fragt beim ersten Mal, ob der Browser Apps installieren darf: auf
**Einstellungen** tippen, **Dieser Quelle vertrauen** (oder „Unbekannte Apps installieren“) einschalten, zurück,
**Installieren**. Eine neuere APK lässt sich genauso über die alte installieren.

In der App steht oben die Adresse des Roboters, vorgegeben ist `reachy-mini.local`. Manche Handys finden diesen
Namen nicht; dann bleibt „Roboter nicht erreichbar“ stehen. In dem Fall die IP-Adresse des Roboters eintragen
(z. B. `192.168.178.50`). Die IP findet man in der Geräteliste des Routers (Fritz!Box: `fritz.box` im Browser öffnen,
**Heimnetz** → **Netzwerk**, Eintrag „reachy-mini“). Die App merkt sich die Eingabe.

## b) Das Radio auf dem Roboter installieren

Einmal nötig, und noch einmal nach jeder Änderung (zum Beispiel an der Senderliste). Man braucht einen PC oder Mac im
selben WLAN wie der Roboter.

1. Den Roboter einschalten und etwa eine Minute warten.
2. Am PC ein Befehlsfenster öffnen:
   - **Windows:** unten auf die Windows-Taste (Start) klicken, `PowerShell` tippen, auf **Windows PowerShell**
     klicken.
   - **Mac:** **Finder** → **Programme** → **Dienstprogramme** → **Terminal** doppelklicken.
3. In das Fenster genau das tippen und dann die **Eingabetaste** drücken:

   ```
   ssh pollen@reachy-mini.local
   ```

   Kommt „Could not resolve hostname“, statt `reachy-mini.local` die IP-Adresse des Roboters nehmen
   (siehe oben, z. B. `ssh pollen@192.168.178.50`).
4. Nur beim allerersten Mal fragt das Fenster „Are you sure you want to continue connecting (yes/no)?“:
   `yes` tippen, **Eingabetaste**.
5. Bei „password:“ das Passwort `root` tippen (man sieht beim Tippen nichts, das ist normal), **Eingabetaste**.
   Das Passwort steht so in Pollens Anleitung. Wer es geändert hat, nimmt sein eigenes.
6. Jetzt steht vorn etwas wie `pollen@reachy-mini:~ $`. Diese Zeile kopieren, ins Fenster einfügen (Windows:
   **Rechtsklick** ins Fenster; Mac: **⌘ + V**) und die **Eingabetaste** drücken:

   ```
   curl -fsSL https://github.com/Moe-Joe86/Radio-LoLa/releases/latest/download/installieren.sh | bash
   ```

7. Warten, bis **„Radio LoLa: FERTIG“** erscheint. Das dauert meist unter einer Minute, beim allerersten Mal bis zu
   etwa zehn Minuten, falls der Roboter seine App-Umgebung erst anlegen muss.
   - Steht stattdessen „installiert, aber der Daemon listet sie noch nicht“: den Roboter einmal aus- und wieder
     einschalten.
   - Steht eine Fehlermeldung da: das Fenster offen lassen und die letzten Zeilen abfotografieren.
8. `exit` tippen, **Eingabetaste**, Fenster schließen.
9. Auf dem Handy die App öffnen und **Radio starten** drücken.

Der Weg folgt Pollens Doku („Offline / manual deployment for a Wireless unit“ in
[Building & Publishing Apps](https://github.com/pollen-robotics/reachy_mini/blob/main/docs/source/SDK/apps.md)):
Apps des Roboters liegen in `/venvs/apps_venv`, der Daemon findet sie dort von selbst. Den App-Store von
Reachy Mini Control braucht das Radio nicht.

### Sender ändern

Die Senderliste und die Grenzwerte stehen in
[`roboter_app/radio_lola/einstellungen.toml`](roboter_app/radio_lola/einstellungen.toml). Auf GitHub die Datei
öffnen, oben rechts auf den **Stift** klicken, ändern, **Commit changes…** und noch einmal **Commit changes**
drücken. Nach etwa fünf Minuten ist ein neues Release gebaut (unter **Actions** wird der Lauf grün); dann die Schritte
2 bis 8 oben wiederholen. Ist in der Datei etwas falsch, startet das Radio nicht und die Handy-App zeigt den Grund.

## c) Was geprüft ist und was erst am Roboter zu testen ist

### Geprüft

- **Bauweise der App** nach Pollens Doku (Quelltext der offiziellen Doku im Repo `pollen-robotics/reachy_mini`,
  Stand 16. Oktober 2026, Paket `reachy_mini` 1.12.0): Gerüst mit Pollens `reachy-mini-app-assistant create`
  erzeugt, Klasse `ReachyMiniApp` mit `run(reachy_mini, stop_event)`, Einstiegspunkt `reachy_mini_apps`.
- **Start und Stopp über den Daemon**, mit Pollens Daemon 1.12.0 im Attrappen-Modus (`--mockup-sim`, ohne Hardware)
  auf demselben Weg wie die Handy-App: Der Daemon findet die App, `start-app/radio_lola` startet sie, das SDK verbindet
  sich lokal, die Antennen fahren nacheinander heim, der Roboter wird geweckt. `stop-current-app` schickt SIGINT, die
  App fährt die Antennen nacheinander heim (von 401° / −172° aus), schaltet die Motoren ein und endet sauber nach
  3,7 s. Eine fehlerhafte Einstellung endet im Zustand „error“ mit lesbarer Meldung; danach lehnt der Daemon neue
  Starts ab, bis einmal gestoppt wird – die Handy-App macht das von selbst.
- **Bewegungen direkt über das SDK**: Der REST-Umweg ist weg. Im Daemon-Code ist `enable_motors()` dasselbe wie der
  frühere REST-Aufruf `set_mode/enabled`, und `goto_target` wartet, bis die Bewegung fertig ist.
- **Empfang**: GStreamer-Teil mit echter MP3 über HTTP getestet (lokaler Test-Server): Ton kommt als 16 kHz mono an,
  nach Ende des Streams verbindet er neu.
- **Rechenlast** des Mischens (Rauschen, Lautstärke): 38 µs je Tonblock von 64 ms auf einem PC, also unter 0,1 %.
- **Installationsskript**: auf einem PC durchgespielt, auch der Fall ohne vorhandene App-Umgebung.
- **Tests ohne Hardware**: 114 Python-Tests (Abstimmung, Heimweg, Strom, Einstellungen, Steuerung, Ablauf mit
  Attrappen-Roboter) und 8 Tests der Handy-App-Logik; laufen bei jedem Push auf GitHub.
- **Pfade der Handy-App** aus dem Daemon-Code und der Doku: `GET /api/apps/current-app-status`,
  `POST /api/apps/start-app/radio_lola`, `POST /api/apps/stop-current-app`. Senderliste, Lautstärke und Stumm laufen
  über den Webserver der Radio-App auf Port 8042 (`GET /radio`, `POST /radio/lautstaerke`, `POST /radio/stumm`),
  den Pollens App-Gerüst für App-Einstellungen vorsieht; im Attrappen-Modus des Daemons geprüft. Den Lautstärke-Weg
  des Daemons nehme ich nicht: Er spielt bei jeder Änderung einen Testton.

### Erst am echten Roboter zu testen

- Ob die Sender auf dem Roboter spielen. Aus meiner Umgebung waren die Radio-Server gesperrt; die vier
  voreingestellten Adressen (Deutschlandfunk, Deutschlandfunk Kultur, Deutschlandfunk Nova, WDR 2) sind bekannte
  Adressen, aber ungetestet. Ob GStreamer auf dem Roboter HTTPS-Streams und MP3/AAC entschlüsseln kann, ist nicht
  gemessen; das Radio schreibt beim Start ins Protokoll, falls etwas fehlt („GStreamer kann auf diesem Roboter
  nicht: …“). MP3-Sender sind die sicherere Wahl.
- Ob es auf dem Raspberry Pi 4 ohne Aussetzer läuft. Vermutung: ja, das Mischen kostet fast nichts, das Entschlüsseln
  eines MP3-Streams wenige Prozent eines Kerns. Klangqualität: Das SDK spielt mit 16 kHz, das klingt eher nach
  Küchenradio als nach HiFi.
- Ob das Wecken und die Heimfahrt am echten Roboter so aussehen wie am 15. Oktober gemessen (im Attrappen-Modus
  stimmen nur die Befehle, nicht die Mechanik).
- Ob dein Handy `reachy-mini.local` findet (sonst IP eintragen, siehe oben).

## Aufbau

| Ordner | Inhalt |
|---|---|
| `roboter_app/` | die Reachy-Mini-App (Gerüst von Pollens Assistent), Installationsskript |
| `tests/` | Python-Tests ohne Hardware, Attrappe des SDK in `tests/conftest.py` |
| `android/` | die Android-App (Kotlin, ein Bildschirm) |
| `.github/workflows/ausliefern.yml` | testet bei jedem Push; auf `main` zusätzlich Release mit APK und Roboter-Paket |

Tests lokal: `uv run pytest`, Prüfung: `uv run ruff check .`
