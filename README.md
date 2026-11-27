# MySaveBackup

<img src="assets/icon.png" alt="MySaveBackup Neon-Panda-Icon mit transparentem Hintergrund" width="160">

Die App wurde mit KI erstellt.

Eine erste Desktop-App für Spielstand-Backups unter Arch Linux. Python erledigt die Dateiarbeit, PySide6 stellt die Oberfläche bereit.

## Direkt von GitHub installieren oder aktualisieren (Arch Linux)

Einmalig die benötigten Pakete installieren:

```bash
sudo pacman -S --needed git python python-pyside6
```

Das Repository ist öffentlich. Eine GitHub-Anmeldung und die GitHub CLI sind nicht erforderlich.

Danach installiert dieser Befehl den aktuellen Stand von `main`. Derselbe Befehl aktualisiert eine vorhandene Installation; die App vorher schließen:

```bash
bash -c 'set -e; msb_tmp=$(mktemp -d); cleanup() { rm -rf -- "$msb_tmp"; }; trap cleanup EXIT; git clone --depth 1 --branch main https://github.com/aggropanda26/MySaveBackup.git "$msb_tmp/repo"; bash "$msb_tmp/repo/install.sh"'
```

Der Befehl lädt das Repository in einen temporären Ordner, führt den vorhandenen Benutzer-Installer aus und entfernt danach nur diesen temporären Download. Die App erscheint im Anwendungsmenü und startet auch über `~/.local/bin/mysavebackup`. Einstellungen und vorhandene Backups bleiben erhalten. Spielstände und lokale Pfadlisten werden nicht aus GitHub geladen; auf einem neuen Rechner zuerst **Spiele suchen** verwenden und fehlende Ordner ergänzen.

Nur die Paketinstallation benötigt sudo. Den Installationsbefehl selbst als normaler Benutzer ausführen. Schlägt der Download fehl, startet der Installer nicht.

## OneDrive direkt verbinden (optional)

MySaveBackup unterstützt persönliche Microsoft-/OneDrive-Konten. Die Anmeldung erfolgt im Systembrowser mit Microsofts MSAL-Bibliothek und PKCE. Ein eigener Cloud-Synchronisationsclient ist nicht nötig. Google Drive, Dropbox und geschäftliche Microsoft-Konten sind in dieser Version noch nicht angebunden.

Im Projektordner installieren oder aktualisieren:

```bash
./install.sh --with-onedrive
```

Beim oben gezeigten GitHub-Installationsbefehl entsprechend am Ende `bash "$msb_tmp/repo/install.sh" --with-onedrive` verwenden. Der Zusatz lädt MSAL, keyring, SecretStorage und requests von PyPI in `~/.local/share/mysavebackup/cloud-venv`. System-Python-Pakete werden dabei nicht überschrieben. Die vorhandene Cloud-Umgebung wird bei normalen App-Updates weiterverwendet. Nach einem System-Python-Upgrade bei Bedarf erneut mit `--with-onedrive` installieren.

Für die sichere Anmeldung muss im Desktop ein entsperrbarer Secret-Service-Schlüsselbund laufen, beispielsweise KWallet oder GNOME Keyring. Es gibt keinen Rückfall auf unverschlüsselte Token-Dateien. Ohne Schlüsselbund bleiben lokale Backups nutzbar. Beim Start aus dem Quellcode statt der installierten App die optionalen Pakete in der Projektumgebung installieren: `.venv/bin/python -m pip install '.[onedrive]'` (nach dem ersten `./start.sh`).

1. **Mit OneDrive verbinden** anklicken und im Browser bei Microsoft anmelden. Die Anmeldung endet spätestens nach drei Minuten; ein Browser-Abbruch kann bis dahin auf das Zeitlimit warten. Nach erfolgreicher Anmeldung erscheint das Konto in der App.
2. **Backup hochladen** wählen, einen vollständigen Backup-Ordner auswählen und die Übertragung bestätigen. Es erfolgt kein automatischer Upload beim lokalen Sichern.
3. Die App erstellt ein ZIP nur aus den im Manifest aufgeführten, per SHA-256 geprüften Spielstandkopien und dem Manifest. Originalordner-Verknüpfungen und zusätzliche Dateien werden nicht eingepackt. Das Manifest enthält Spielnamen und ursprüngliche lokale Pfade. Das ZIP wird per HTTPS übertragen und ist nicht zusätzlich passwortverschlüsselt.
4. **Cloud-Backups** listet die von MySaveBackup benannten ZIP-Archive im App-Ordner auf. Ein ausgewähltes Archiv wird in einen neuen lokalen Ordner heruntergeladen, sicher entpackt und geprüft. Danach über **Backup wiederherstellen** die vorhandene Vorschau und Sicherheitskopie verwenden. Ein Download verändert keine Originalspielstände.
5. **Verbindung trennen** entfernt den lokalen MSAL-Cache aus dem Schlüsselbund. Cloud-Backups bleiben erhalten. Die Microsoft-Zustimmung lässt sich zusätzlich unter [Microsoft-Kontoberechtigungen](https://account.live.com/consent/Manage) widerrufen.

Die Zugriffsrechte sind `Files.ReadWrite.AppFolder` (eigener OneDrive-App-Ordner) und `User.Read` (Profil). Die App registriert sich als öffentlicher Desktop-Client ohne Clientschlüssel; die Client-ID im Quellcode ist öffentlich. OAuth-Tokens liegen ausschließlich im Secret-Service-Schlüsselbund unter `MySaveBackup.OneDrive`. Eine lokale Sperrdatei `~/.config/mysavebackup/onedrive.lock` koordiniert gleichzeitige Anmeldungen und enthält keine Tokens.

Uploads erfolgen in Abschnitten mit Fortschrittsanzeige. Vorübergehende Netzwerk-/Serverfehler werden begrenzt erneut versucht. **Transfer abbrechen** beendet den Vorgang zwischen Dateiblöcken bzw. nach einer laufenden Netzwerkanfrage. Nach einem endgültigen Fehler den Upload erneut starten; eine Wiederaufnahme nach App-Neustart wird noch nicht unterstützt. Ein Fehler während der letzten Serverantwort kann trotz Fehlermeldung bereits einen fertigen Cloud-Eintrag hinterlassen; vor einem erneuten Versuch die Cloud-Liste prüfen. Erfolgreiche Uploads werden anhand der OneDrive-Abschlussantwort und Archivgröße bestätigt; eine vollständige Rückleseprüfung erfolgt beim Download.

Limit dieser Version: höchstens 20 GiB Archivgröße und 20 GiB entpackte Daten, maximal 99.999 Spielstanddateien. Packen und Download benötigen zusätzlichen lokalen Speicher. Lokale Backups bleiben bei Cloud-Fehlern erhalten. Temporäre Archive werden nach Abschluss oder behandelten Fehlern entfernt; nach einem Prozess-/Systemabsturz können temporäre Dateien zurückbleiben.

Entwicklerkonfiguration: Client-ID `3aa3a3de-809e-48ac-8bb3-b6b44d618607`, Kontotyp persönliche Microsoft-Konten, Desktop-Umleitungsadresse `http://localhost`, delegierte Graph-Berechtigungen wie oben. Automatisierte Cloud-Tests simulieren Microsoft-Antworten. Am 27.11.2026 wurden Upload, Auflistung und Download mit SHA-256-Prüfung zusätzlich mit einem echten persönlichen OneDrive-Konto und künstlichen Testdaten erfolgreich geprüft.

Quellen: [MSAL-Anmeldung](https://learn.microsoft.com/en-us/entra/msal/python/getting-started/acquiring-tokens), [OneDrive-App-Ordner](https://learn.microsoft.com/graph/onedrive-sharepoint-appfolder), [Upload-Sitzungen](https://learn.microsoft.com/en-us/graph/api/driveitem-createuploadsession?view=graph-rest-1.0).

## Für deinen Benutzer installieren

Im Projektordner ausführen:

```bash
./install.sh
```

Die Standardinstallation braucht kein sudo und lädt nichts herunter. Die optionale OneDrive-Installation lädt Python-Abhängigkeiten von PyPI. Falls PySide6 fehlt, zuerst `sudo pacman -S python python-pyside6` ausführen. Danach findest du **MySaveBackup** im Anwendungsmenü.

Direkt starten:

```bash
~/.local/bin/mysavebackup
```

Wenn `~/.local/bin` in deinem PATH steht, reicht `mysavebackup`. Der Installer ändert keine Shell-Konfiguration.

Die Anwendung liegt unter `~/.local/share/mysavebackup`, der Menüeintrag unter `~/.local/share/applications/mysavebackup.desktop`. Die lokale Spielekonfiguration wird, sofern vorhanden, mitkopiert. Eigene Quellen unter `~/.config/mysavebackup` und vorhandene Backups bleiben erhalten. Nach Quellcode-Änderungen die App schließen und `./install.sh` erneut ausführen, um die installierte Kopie zu aktualisieren.

## Ohne Installation aus dem Projekt starten

Im Projektordner ein Terminal öffnen und ausführen:

```bash
./start.sh
```

Beim ersten Start entsteht eine lokale Python-Umgebung in `.venv`. Dafür müssen `python` und `python-pyside6` installiert sein. Es werden beim Start keine Pakete heruntergeladen.

1. **Spiele suchen** anklicken.
2. Spiele aufklappen und gefundene Speicherorte prüfen. Ein einzelner Klick auf einen unterstrichenen Spielstandpfad öffnet dessen Ordner direkt im Dateimanager. Spiele ohne erkannte Dateien können über **Spielstandordner hinzufügen** ergänzt werden.
3. Zielordner auswählen und **Ausgewählte Spiele sichern** anklicken. Die Auswahl bleibt beim Filtern bestehen.
4. **Letztes Backup öffnen** öffnet die geprüfte Sicherung.
5. **Backup und Duplikate prüfen** liest einen Sicherungsordner mit `manifest.json`. Diese erste Version zeigt Duplikate nur an und löscht nichts.

Während eines Vorgangs kann das Fenster erst nach Abschluss geschlossen werden. Spiele möglichst vor dem Sichern beenden. Änderungen während des Kopierens werden als Fehler gemeldet; ein konsistenter Snapshot eines laufenden Spiels ist nicht garantiert.

Beim ersten Start erscheint „Sorry nur Ki Slop“. Die Einblendung lässt sich sofort über **Schließen** entfernen und blockiert keine Funktionen. Nach dem Schließen erscheint sie für diesen Benutzer nicht erneut; die Auswahl liegt unter `~/.config/mysavebackup/first-start-dismissed`.

## Spielstände wiederherstellen

1. **Spiele suchen** ausführen, damit die lokalen Speicherorte bekannt sind.
2. **Backup wiederherstellen** anklicken, einen vollständigen MySaveBackup-Ordner mit `manifest.json` und das Spiel auswählen.
3. Die Vorschau zeigt jede zu ersetzende oder neu anzulegende Datei mit Originalpfad. Identische Dateien werden ausgelassen; zusätzliche Originaldateien bleiben erhalten.
4. Spiel und Launcher schließen, die Änderungen ausdrücklich bestätigen und **Jetzt wiederherstellen** anklicken. Steam Cloud kann beim nächsten Start einen anderen Stand synchronisieren.

Vor der ersten Änderung kopiert und prüft die App alle betroffenen vorhandenen Spielstände. Die Sicherheitskopie liegt im eingestellten Backup-Ziel unter `Vor-Wiederherstellung/<Zeitstempel-ID>`; der genaue Pfad erscheint im Protokoll. Fehlende oder beschädigte Backup-Dateien sowie unbekannte Zielpfade werden abgelehnt. Für nicht erkannte Spiele den Originalordner unter demselben Spielnamen manuell ergänzen. Alte Sicherungen ohne MySaveBackup-Manifest werden nicht unterstützt.

Über **Wiederherstellung rückgängig** den Sicherheitskopie-Ordner mit `recovery.json` auswählen und die Vorschau bestätigen. Dabei werden zuvor vorhandene Dateien zurückkopiert und nur durch diese Wiederherstellung neu angelegte Dateien entfernt. Auch die Rücknahme erstellt zuerst eine Sicherheitskopie. Wurden Spielstände inzwischen weiter verändert, bricht die Rücknahme ab, damit neuer Fortschritt erhalten bleibt.

Dateien werden einzeln ersetzt. Ein Fehler oder Abbruch kann deshalb einen teilweise wiederhergestellten Stand hinterlassen. Der gemeldete Sicherheitskopie-Ordner ermöglicht die Rücknahme bereits ausgeführter Änderungen. Sicherheitskopien bis zur erfolgreichen Prüfung im Spiel aufbewahren. Die App prüft Dateiinhalte per SHA-256; ob ein Spiel den Stand inhaltlich laden kann, muss im Spiel geprüft werden.

## Spielcover

Nach der Spielsuche lädt die App die Cover automatisch im Hintergrund. Verwendet werden Steams öffentliche Bildserver (`shared.fastly.steamstatic.com`), die auch SteamDB für Bilder einbindet. SteamDB selbst wird nicht automatisiert ausgelesen; [SteamDB verweist dafür auf Steam](https://steamdb.info/faq/#does-steamdb-have-an-api).

Bereits von Steam lokal gespeicherte Cover werden ebenfalls erkannt und ohne Download verwendet. Geladene Cover werden unter `~/.cache/mysavebackup/covers` gespeichert (bei gesetztem `XDG_CACHE_HOME` entsprechend dort) und beim nächsten Start ohne erneuten Download angezeigt. Bei fehlender Internetverbindung bleiben bereits gespeicherte Cover sichtbar. Fehlende Bilder erhalten einen Platzhalter; die App bleibt bedienbar. Wenn das Hochformat-Cover fehlt, wird ein Steam-Headerbild versucht.

Fehlt eine Zuordnung oder ist sie falsch, Spiel auswählen und **Cover zuordnen** anklicken. Dort die Steam-App-ID oder den SteamDB-Link des Spiels eintragen. Die Zuordnung liegt unter `~/.config/mysavebackup/cover-ids.json` und verändert keine Spielstandpfade. Spiele ohne Steam-Eintrag oder ohne bereitgestelltes Bild behalten einen Platzhalter.

An den Bildserver wird nur die jeweilige App-ID im Bildpfad gesendet, keine Spielstände oder lokalen Pfade. Cover und deren Cache werden nicht in Spielstand-Backups aufgenommen. Cover bleiben Eigentum der jeweiligen Rechteinhaber.

## Was schon funktioniert

- Steam-Bibliotheken, einschließlich zusätzlicher Laufwerke und Flatpak, lesen.
- Optionale lokale Spielstandpfade aus `local_sources.json` einbeziehen; diese Datei wird nicht im Repository mitgeliefert.
- Weitere Spielstandordner manuell hinzufügen; gespeichert unter `~/.config/mysavebackup/manual-sources.json`.
- Eigenständige Backup-Kopien pro Spiel und Speicherort erstellen.
- SHA-256-Prüfsummen prüfen, Originalpfade im Manifest dokumentieren.
- Originalordner-Verknüpfungen erstellen; Quellen beim Sichern nur lesen.
- Byte-identische Duplikate innerhalb eines Spiels anzeigen.
- Spielstände mit Dateivorschau, Bestätigung und geprüfter Sicherheitskopie wiederherstellen und die Wiederherstellung rückgängig machen.

## Grenzen dieser ersten Version

Die automatische Suche erkennt noch nicht jedes Spiel oder jeden Launcher. Eine optionale `local_sources.json` kann eigene Spielstandpfade ergänzen. Sie bleibt lokal und gehört nicht zum öffentlichen Repository; sie ist keine allgemeine Spieldatenbank. Nicht eindeutig bestimmbare Begleitdateien bleiben erhalten. Einige klar benannte Einstellungen, Protokolle und Steam-Verwaltungsdateien werden ausgelassen; registrybasierte Spielstände werden noch nicht unterstützt. Prüfe die angezeigten Quellen vor dem Backup.

Symbolische Links innerhalb der Quellordner werden nicht verfolgt. Die Original-Verknüpfungen im Backup führen dagegen zu den echten Ordnern: Änderungen über den Dateimanager wirken dort auf die Originale.

Eine automatische Bereinigung ist noch nicht eingebaut. Bei Fehlern bleibt eine als `incomplete` markierte Sicherung zur Diagnose erhalten. Nur `status: complete` bestätigt einen erfolgreichen Durchlauf. Backups auf derselben Festplatte schützen nicht vor deren Ausfall.

## Projekt verstehen

- `mysavebackup/gui.py`: Fenster, Schaltflächen, Hintergrundaufgaben.
- `mysavebackup/core.py`: Suche, Kopieren, Prüfsummen und Duplikatprüfung; ohne Qt-Abhängigkeit.
- `mysavebackup/restore.py`: Wiederherstellung, Sicherheitskopien und Rücknahme; ohne Qt-Abhängigkeit.
- `tests/test_core.py`: Tests mit künstlichen Spielständen, ohne Änderungen an echten Spielständen.
- `local_sources.json`: lokale Spielnamen und Originalpfade. Nicht öffentlich teilen, ohne private Pfade zu entfernen.

Tests starten:

```bash
python3 -m unittest discover -s tests -v
```

## Später Rust ergänzen

Die Oberfläche ruft klar getrennte Kernfunktionen auf. Das Backup-Manifest verwendet JSON mit `format` und `version`. Ein Rust-Modul oder ein Rust-Kommandozeilenprogramm kann später diese Funktionen ersetzen, während die Qt-Oberfläche erhalten bleibt. Dafür definieren wir bei der Migration eine versionierte JSON-Schnittstelle; Python-Dataclasses selbst sind keine sprachunabhängige Schnittstelle.

Qt-Referenz für die verwendeten Hintergrundaufgaben: https://doc.qt.io/qtforpython-6/PySide6/QtCore/QThread.html

## Änderungsverlauf

`CHANGELOG.txt` wird bei jeder Installation und Aktualisierung nach `~/.local/share/mysavebackup/CHANGELOG.txt` kopiert. Sie ist die gemeinsame Quelle für den folgenden Verlauf. Nach Änderungen `python3 tools/sync_changelog.py` ausführen; `--check` prüft die Übereinstimmung ohne Dateien zu ändern.

<!-- CHANGELOG:START -->
```text
MySaveBackup – Änderungsverlauf
Neueste Änderungen zuerst. Datumsangaben: Europe/Vienna.

2026-11-27 – OneDrive-Uploadfehler behoben
- Upload-Sitzung ohne redundanten Dateinamen im Anfragekörper erstellen; die bisherige Kombination führte beim getesteten persönlichen OneDrive-Konto zu HTTP 400.
- Eindeutigen Dateinamen im Zielpfad und Schutz vor Überschreiben beibehalten; Regressionstest ergänzt.
- Zusätzliche HTTPS-Weiterleitungen beim OneDrive-Download ohne Weitergabe des Anmeldungstokens unterstützen.
- Upload, Auflistung und Download mit Prüfsummenvergleich im echten OneDrive-Konto mit künstlichen Daten erfolgreich geprüft; Testdateien anschließend entfernt.

2026-11-27 – Direkte OneDrive-Anbindung
- Persönliche Microsoft-Konten im Browser verbinden; Anmeldung mit MSAL/PKCE und Token-Speicherung ausschließlich im Linux-Schlüsselbund.
- Geprüfte Backups nach Bestätigung als ZIP in den eigenen OneDrive-App-Ordner hochladen; Fortschritt, Abbruch und begrenzte Wiederholungen bei Netzwerkfehlern ergänzen.
- Cloud-Backups auflisten, herunterladen und vor der bestehenden Wiederherstellung auf sichere Pfade und Prüfsummen prüfen.
- Lokale Verbindung trennen, ohne Cloud-Backups zu löschen; keine Originalordner-Verknüpfungen oder zusätzlichen Dateien hochladen.
- Optionalen Installer-Schalter --with-onedrive für isolierte Python-Abhängigkeiten ergänzen; Einrichtung und Grenzen dokumentieren.

2026-11-26 – Anleitung für das öffentliche Repository
- Installation und Updates per git clone ohne GitHub-Anmeldung oder GitHub CLI beschrieben.
- Rechnerbezogene Hinweise korrigiert und lokale Spielstandkonfiguration als optional und nicht mitgeliefert gekennzeichnet.

2026-11-26 – Wiederherstellung und Rücknahme
- Einzelne Spiele aus vollständigen MySaveBackup-Sicherungen wiederherstellen, mit Dateivorschau und ausdrücklicher Bestätigung.
- Aktuelle Spielstände vor Änderungen vollständig kopieren und per Prüfsumme verifizieren; Sicherheitskopien unter Vor-Wiederherstellung ablegen.
- Wiederherstellungen rückgängig machen; seitdem veränderte Spielstände vor unbeabsichtigtem Überschreiben schützen.
- Beschädigte Sicherungen, unbekannte Ziele und symbolische Links ablehnen; zusätzliche Originaldateien erhalten.
- Fehlerfälle, Rücknahme und GUI-Ablauf mit künstlichen Spielständen testen.

2026-11-26 – Transparentes App-Icon
- Schachbrett-Hintergrund der neuen Neon-Panda-Vorlage entfernt und durch echte PNG-Transparenz ersetzt.
- Menü-, Fenster- und README-Icon auf die freigestellte Version aktualisiert.

2026-11-26 – Neues App-Icon
- Vom Nutzer bereitgestelltes Neon-Panda-Bild als PNG-App-Icon übernommen.
- Menüeintrag und Programmfenster verwenden das neue Icon; der Installer liefert es bei Updates mit.

2026-11-26 – Spielcover
- Spieleliste um Cover erweitert, die automatisch im Hintergrund von Steams Bildservern geladen werden (derselben Bildquelle wie bei SteamDB).
- Vorhandene Bilder aus Steams lokalem Bibliothekscache werden ebenfalls erkannt.
- Lokaler Cover-Cache für spätere und Offline-Starts; begrenzte parallele Downloads, Zeitlimit und Ersatzbild bei fehlenden Covern.
- „Cover zuordnen“ akzeptiert eine Steam-App-ID oder einen SteamDB-Spiellink, ohne Spielstandpfade zu ändern.
- Cover-Downloads und Cache bleiben getrennt von Spielständen und Backups.

2026-11-26 – Spielstandpfade direkt öffnen
- Ein einzelner Klick auf einen Spielstandpfad in der aufgeklappten Spieleliste öffnet den Ordner im Dateimanager.
- Bei einzelnen Spielstanddateien wird deren übergeordneter Ordner geöffnet; fehlende Speicherorte werden angezeigt.

2026-11-26 – Hinweis beim ersten Start
- Sofort schließbare Einblendung „Sorry nur Ki Slop“ ergänzt, ohne Wartezeit oder Sperre der Oberfläche.
- Nach dem Schließen wird der Hinweis für diesen Benutzer dauerhaft ausgeblendet, auch nach App-Updates.

2026-11-26 – Hinweis zur Erstellung
- README um den Hinweis „Die App wurde mit KI erstellt.“ ergänzt.

2026-11-26 – Änderungsverlauf
- CHANGELOG.txt als gemeinsame Quelle für den Änderungsverlauf ergänzt.
- Installer liefert den aktuellen Verlauf bei Installation und Update mit.
- README zeigt denselben Verlauf; Synchronisierung und Tests prüfen die Übereinstimmung.
- Projektregel: Änderungen künftig immer im Änderungsverlauf dokumentieren.

2026-11-26 – Benutzerinstallation
- install.sh installiert die App ohne sudo und ohne Downloads für den eigenen Benutzer.
- Startbefehl mysavebackup, Anwendungsmenü-Eintrag und Icon ergänzt.
- Erneutes Installieren aktualisiert die App und erhält Einstellungen und Backups.
- Installations-, Update- und Starttests ergänzt; fremde Installationsziele werden abgelehnt.

2026-11-26 – Erste Version 0.1.0
- Python-/PySide6-Oberfläche mit Spieleliste, Ordnerauswahl und Hintergrundaufgaben erstellt.
- Steam-Bibliotheken, bekannte Spielstandpfade und manuell ergänzte Ordner unterstützt.
- Backups nach Spiel und Speicherort mit SHA-256-Prüfung und Herkunftsmanifest erstellt.
- Verknüpfungen zu Originalordnern und eine reine Duplikatvorschau ergänzt.
- Originalspielstände werden beim Sichern nur gelesen. Automatische Bereinigung und Wiederherstellung sind noch nicht enthalten.
```
<!-- CHANGELOG:END -->
