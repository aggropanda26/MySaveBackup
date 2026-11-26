# MySaveBackup

<img src="assets/icon.png" alt="MySaveBackup Neon-Panda-Icon mit transparentem Hintergrund" width="160">

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
- Bekannte Spielstandpfade aus unserer vorherigen Suche über `local_sources.json` einbeziehen.
- Weitere Spielstandordner manuell hinzufügen; gespeichert unter `~/.config/mysavebackup/manual-sources.json`.
- Eigenständige Backup-Kopien pro Spiel und Speicherort erstellen.
- SHA-256-Prüfsummen prüfen, Originalpfade im Manifest dokumentieren.
- Originalordner-Verknüpfungen erstellen; Quellen beim Sichern nur lesen.
- Byte-identische Duplikate innerhalb eines Spiels anzeigen.
- Spielstände mit Dateivorschau, Bestätigung und geprüfter Sicherheitskopie wiederherstellen und die Wiederherstellung rückgängig machen.

## Grenzen dieser ersten Version

Die automatische Suche erkennt noch nicht jedes Spiel oder jeden Launcher. Die mitgelieferte `local_sources.json` ist eine lokale Startkonfiguration für diesen Rechner, keine allgemeine Spieldatenbank. Nicht eindeutig bestimmbare Begleitdateien bleiben erhalten. Einige klar benannte Einstellungen, Protokolle und Steam-Verwaltungsdateien werden ausgelassen; registrybasierte Spielstände werden noch nicht unterstützt. Prüfe die angezeigten Quellen vor dem Backup.

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
