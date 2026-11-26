# MySaveBackup

Die App wurde mit KI erstellt.

Eine erste Desktop-App für Spielstand-Backups unter Arch Linux. Python erledigt die Dateiarbeit, PySide6 stellt die Oberfläche bereit.

## Für deinen Benutzer installieren

Im Projektordner ausführen:

```bash
./install.sh
```

Die Installation braucht kein sudo und lädt nichts herunter. Falls PySide6 fehlt, zuerst `sudo pacman -S python python-pyside6` ausführen. Danach findest du **MySaveBackup** im Anwendungsmenü.

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

Beim ersten Start entsteht eine lokale Python-Umgebung in `.venv`. Auf diesem Rechner ist PySide6 bereits vorhanden. Auf einem anderen Arch-Rechner werden `python` und `python-pyside6` benötigt. Es werden beim Start keine Pakete heruntergeladen.

1. **Spiele suchen** anklicken.
2. Spiele aufklappen und gefundene Speicherorte prüfen. Ein einzelner Klick auf einen unterstrichenen Spielstandpfad öffnet dessen Ordner direkt im Dateimanager. Spiele ohne erkannte Dateien können über **Spielstandordner hinzufügen** ergänzt werden.
3. Zielordner auswählen und **Ausgewählte Spiele sichern** anklicken. Die Auswahl bleibt beim Filtern bestehen.
4. **Letztes Backup öffnen** öffnet die geprüfte Sicherung.
5. **Backup und Duplikate prüfen** liest einen Sicherungsordner mit `manifest.json`. Diese erste Version zeigt Duplikate nur an und löscht nichts.

Während eines Vorgangs kann das Fenster erst nach Abschluss geschlossen werden. Spiele möglichst vor dem Sichern beenden. Änderungen während des Kopierens werden als Fehler gemeldet; ein konsistenter Snapshot eines laufenden Spiels ist nicht garantiert.

Beim ersten Start erscheint „Sorry nur Ki Slop“. Die Einblendung lässt sich sofort über **Schließen** entfernen und blockiert keine Funktionen. Nach dem Schließen erscheint sie für diesen Benutzer nicht erneut; die Auswahl liegt unter `~/.config/mysavebackup/first-start-dismissed`.

## Was schon funktioniert

- Steam-Bibliotheken, einschließlich zusätzlicher Laufwerke und Flatpak, lesen.
- Bekannte Spielstandpfade aus unserer vorherigen Suche über `local_sources.json` einbeziehen.
- Weitere Spielstandordner manuell hinzufügen; gespeichert unter `~/.config/mysavebackup/manual-sources.json`.
- Eigenständige Backup-Kopien pro Spiel und Speicherort erstellen.
- SHA-256-Prüfsummen prüfen, Originalpfade im Manifest dokumentieren.
- Originalordner-Verknüpfungen erstellen; Quellen beim Sichern nur lesen.
- Byte-identische Duplikate innerhalb eines Spiels anzeigen.

## Grenzen dieser ersten Version

Die automatische Suche erkennt noch nicht jedes Spiel oder jeden Launcher. Die mitgelieferte `local_sources.json` ist eine lokale Startkonfiguration für diesen Rechner, keine allgemeine Spieldatenbank. Nicht eindeutig bestimmbare Begleitdateien bleiben erhalten. Einige klar benannte Einstellungen, Protokolle und Steam-Verwaltungsdateien werden ausgelassen; registrybasierte Spielstände werden noch nicht unterstützt. Prüfe die angezeigten Quellen vor dem Backup.

Symbolische Links innerhalb der Quellordner werden nicht verfolgt. Die Original-Verknüpfungen im Backup führen dagegen zu den echten Ordnern: Änderungen über den Dateimanager wirken dort auf die Originale.

Eine automatische Bereinigung und Wiederherstellung sind noch nicht eingebaut. Bei Fehlern bleibt eine als `incomplete` markierte Sicherung zur Diagnose erhalten. Nur `status: complete` bestätigt einen erfolgreichen Durchlauf. Backups auf derselben Festplatte schützen nicht vor deren Ausfall.

## Projekt verstehen

- `mysavebackup/gui.py`: Fenster, Schaltflächen, Hintergrundaufgaben.
- `mysavebackup/core.py`: Suche, Kopieren, Prüfsummen und Duplikatprüfung; ohne Qt-Abhängigkeit.
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
