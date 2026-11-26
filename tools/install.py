"""Install this checkout for the current user without sudo or network access."""
from pathlib import Path
import argparse
import importlib.util
import os
import shlex
import shutil
import subprocess
import sys

MARKER = 'MySaveBackup user installation v1\n'

def desktop_quote(value):
    # Desktop Exec quoting has its own escaping rules, separate from shell syntax.
    value = value.replace('\\', '\\\\').replace('"', '\\"').replace('`', '\\`').replace('$', '\\$')
    return '"' + value.replace('%', '%%') + '"'

def install(source, home):
    if importlib.util.find_spec('PySide6') is None:
        raise RuntimeError('PySide6 fehlt. Bitte zuerst: sudo pacman -S python python-pyside6')
    app = home / '.local/share/mysavebackup'
    binary = home / '.local/bin/mysavebackup'
    desktop = home / '.local/share/applications/mysavebackup.desktop'
    icon = app / 'icon.svg'
    marker = app / '.mysavebackup-installation'
    if app.resolve() == source.resolve():
        raise RuntimeError('Bitte install.sh aus dem Projektordner ausführen.')
    targets = (app, binary, desktop)
    for target in targets:
        if target.is_symlink() or any(p.is_symlink() for p in target.parents if p != home.parent):
            raise RuntimeError(f'Installationspfad enthält eine Verknüpfung: {target}')
    if app.exists() and (not marker.is_file() or marker.read_text() != MARKER):
        raise RuntimeError(f'Fremder Ordner wird nicht überschrieben: {app}')
    if binary.exists() and '# MySaveBackup launcher' not in binary.read_text():
        raise RuntimeError(f'Vorhandener Startbefehl wird nicht überschrieben: {binary}')
    if desktop.exists() and 'X-MySaveBackup-Managed=true' not in desktop.read_text():
        raise RuntimeError(f'Vorhandener Menüeintrag wird nicht überschrieben: {desktop}')
    # Validate input before creating or updating anything.
    for name in ('mysavebackup/__main__.py', 'mysavebackup/gui.py', 'assets/icon.svg'):
        if not (source / name).is_file():
            raise RuntimeError(f'Projektdatei fehlt: {name}')
    app.mkdir(parents=True, exist_ok=True)
    marker.write_text(MARKER)
    shutil.copytree(source/'mysavebackup', app/'mysavebackup', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(source/'assets/icon.svg', icon)
    if (source/'local_sources.json').is_file():
        shutil.copy2(source/'local_sources.json', app/'local_sources.json')
        (app/'local_sources.json').chmod(0o600)
    if (source/'README.md').is_file():
        shutil.copy2(source/'README.md', app/'README.md')
    binary.parent.mkdir(parents=True, exist_ok=True)
    python = shlex.quote(sys.executable)
    binary.write_text('#!/usr/bin/env bash\n# MySaveBackup launcher\nset -euo pipefail\n'
                      + 'cd -- ' + shlex.quote(str(app)) + '\n'
                      + 'exec ' + python + ' -m mysavebackup "$@"\n')
    binary.chmod(0o755)
    desktop.parent.mkdir(parents=True, exist_ok=True)
    desktop.write_text('[Desktop Entry]\nType=Application\nVersion=1.0\nName=MySaveBackup\n'
                      'Comment=Spielstände sichern und Backups prüfen\n'
                      + 'Exec=' + desktop_quote(str(binary)) + '\n'
                      + 'Icon=' + str(icon).replace('\\','\\\\') + '\n'
                      'Terminal=false\nCategories=Utility;\nKeywords=backup;save;spielstand;steam;\n'
                      'X-MySaveBackup-Managed=true\n')
    if shutil.which('update-desktop-database'):
        result = subprocess.run(['update-desktop-database', str(desktop.parent)],
                                capture_output=True, text=True)
        if result.returncode:
            print('Hinweis: Menü-Cache konnte nicht aktualisiert werden.', file=sys.stderr)
    print(f'Installiert: {app}\nMenüeintrag: MySaveBackup\nStart: {binary}')
    if str(binary.parent) not in os.environ.get('PATH', '').split(os.pathsep):
        print('Für den Kurzaufruf mysavebackup muss ~/.local/bin im PATH sein.\n'
              'Bis dahin den Menüeintrag oder den vollständigen Startpfad verwenden.')
    return app

def main():
    parser = argparse.ArgumentParser(description='MySaveBackup für den eigenen Benutzer installieren oder aktualisieren.')
    parser.parse_args()
    if os.geteuid() == 0:
        parser.exit(1, 'Bitte ohne sudo als normaler Benutzer starten.\n')
    try:
        install(Path(__file__).resolve().parents[1], Path.home())
    except (OSError, RuntimeError) as exc:
        parser.exit(1, f'Installation fehlgeschlagen: {exc}\n')

if __name__ == '__main__':
    main()
