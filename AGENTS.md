# MySaveBackup-Projektregeln

- Bei jeder inhaltlichen Projektänderung CHANGELOG.txt mit Datum (Europe/Vienna) und verständlicher Beschreibung aktualisieren; neueste Einträge zuerst.
- CHANGELOG.txt ist die gemeinsame Quelle. Danach `python3 tools/sync_changelog.py` ausführen, damit die README denselben Verlauf enthält.
- Der Installer muss CHANGELOG.txt bei Installation und Aktualisierung mitliefern.
- Vor einem GitHub-Upload `python3 tools/sync_changelog.py --check` und passende Tests ausführen. Changelog und README zusammen mit den Änderungen hochladen.
- Keine lokalen Spielstände, Backups, Zugangsdaten oder local_sources.json auf GitHub hochladen.
