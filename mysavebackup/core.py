"""GUI-independent, read-only source discovery and verified backup operations."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
import hashlib
import json
import os
import re
import shutil
import uuid

@dataclass
class Game:
    name: str
    sources: list[Path] = field(default_factory=list)
    installation: str = ''
    app_id: str = ''

EXCLUDED = {'user.reg', 'userdef.reg', 'steam_autocloud.vdf', 'remotecache.vdf',
            'graphicsconfig.xml', 'dltb_settings.dat', 'config.ini', 'statsutility.bin',
            'enhancedinputusersettings.sav', 'globalusersettings.sav',
            'embarkoptionsavegame.sav', 'embarksavegameclientkeybindings.sav'}

def candidate(path: Path) -> bool:
    name = path.name.lower()
    return name not in EXCLUDED and not name.startswith('preferences-') and path.suffix.lower() not in {'.log', '.reg', '.vdf', '.cachedmsg'}

def source_files(source: Path):
    """Never traverse symlinks, including linked subdirectories and files."""
    if source.is_symlink():
        return
    if source.is_file():
        if candidate(source):
            yield source
        return
    if not source.is_dir():
        return
    def fail(error):
        raise error
    for current, dirs, files in os.walk(source, followlinks=False, onerror=fail):
        dirs[:] = sorted(d for d in dirs if not (Path(current)/d).is_symlink())
        for name in sorted(files):
            p = Path(current)/name
            if not p.is_symlink() and p.is_file() and candidate(p):
                yield p

def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for data in iter(lambda: f.read(1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()

def slug(name):
    return re.sub(r'[^\w .()\-]', '_', name).strip(' .')[:100] or 'Spiel'

def discover(seed_file: Path, home: Path | None = None) -> list[Game]:
    home = home or Path.home()
    games = []
    if seed_file.exists():
        for g in json.loads(seed_file.read_text()):
            games.append(Game(g['name'], [Path(p) for p in g['sources']],
                              g.get('installation', ''), g.get('app_id', '')))
    roots = [home/'.local/share/Steam', home/'.steam/steam',
             home/'.var/app/com.valvesoftware.Steam/data/Steam']
    for r in list(roots):
        f = r/'steamapps/libraryfolders.vdf'
        if f.exists():
            roots.extend(Path(p.replace('\\\\','\\')) for p in
                         re.findall(r'"path"\s+"([^"]+)"', f.read_text(errors='replace'), re.I))
    roots = sorted({r.resolve() for r in roots if r.is_dir()})
    by_id = {g.app_id:g for g in games if g.app_id}
    for r in roots:
        for acf in (r/'steamapps').glob('appmanifest_*.acf'):
            data = dict(re.findall(r'"([^"\n]+)"\s+"([^"\n]*)"', acf.read_text(errors='replace')))
            aid, name = data.get('appid',''), data.get('name','')
            folder = r/'steamapps/common'/data.get('installdir','')
            if not aid or not name or not folder.is_dir():
                continue
            if name.lower().startswith(('proton ', 'steam linux runtime', 'steamworks common')):
                continue
            if aid not in by_id:
                normalized = lambda s: re.sub(r'[^a-z0-9]', '', s.casefold())
                match = next((g for g in games if normalized(g.name) == normalized(name)
                              or (g.installation and Path(g.installation).resolve() == folder.resolve())), None)
                if match is not None:
                    match.app_id = aid
                    by_id[aid] = match
            if aid not in by_id:
                game = Game(name, installation=str(folder), app_id=aid)
                games.append(game)
                by_id[aid] = game
            else:
                by_id[aid].installation = str(folder)
    for game in games:
        if game.app_id:
            for r in roots:
                # Remote directories are specific to this game, not the entire account.
                game.sources.extend((r/'userdata').glob(f'*/{game.app_id}/remote'))
                users = r/'steamapps/compatdata'/game.app_id/'pfx/drive_c/users'
                if users.is_dir():
                    for current, dirs, _ in os.walk(users, followlinks=False):
                        dirs[:] = [d for d in dirs if not (Path(current)/d).is_symlink()
                                   and d.lower() not in ('cache','webcache','logs','temp')]
                        for d in list(dirs):
                            if d.lower() in ('savegames','savegame','saves','save','saved games'):
                                game.sources.append(Path(current)/d)
                                dirs.remove(d)
        existing = sorted({p.resolve() for p in game.sources if p.exists() and not p.is_symlink()},
                          key=lambda p: (len(p.parts), str(p)))
        game.sources = []
        for p in existing:
            if not any(p.is_relative_to(parent) for parent in game.sources):
                if next(source_files(p), None) is not None:
                    game.sources.append(p)
    return sorted(games, key=lambda g: g.name.casefold())

def backup(games: list[Game], destination: Path, progress=lambda text: None) -> Path:
    if not games:
        raise ValueError('Bitte mindestens ein Spiel auswählen.')
    destination = destination.expanduser().resolve()
    for game in games:
        for source in game.sources:
            if source.is_symlink():
                raise ValueError(f'Verknüpfung als Quelle nicht erlaubt: {source}')
            s = source.resolve()
            if destination == s or destination.is_relative_to(s):
                raise ValueError('Das Backup-Ziel darf nicht im Originalordner liegen.')
    destination.mkdir(parents=True, exist_ok=True)
    run = destination/(datetime.now().strftime('%Y-%m-%d_%H-%M-%S')+'_'+uuid.uuid4().hex[:6])
    run.mkdir()
    manifest = {'format': 'mysavebackup', 'version': 1, 'status': 'running',
                'created': datetime.now().astimezone().isoformat(), 'files': [], 'errors': []}
    try:
        for number, game in enumerate(games, 1):
            progress(f'{number}/{len(games)} · {game.name}')
            game_dir = run/f'{number:02d} - {slug(game.name)}'
            (game_dir/'Backup').mkdir(parents=True)
            (game_dir/'Originalordner').mkdir()
            visited = set()
            for i, source in enumerate(game.sources, 1):
                # Re-check before use: never modify or follow source links.
                if source.is_symlink() or not source.exists():
                    raise ValueError(f'Quelle nicht mehr verfügbar: {source}')
                base = source if source.is_dir() else source.parent
                label = f'{i:02d} - {slug(base.name)}'
                (game_dir/'Originalordner'/label).symlink_to(base, target_is_directory=True)
                for src in source_files(source):
                    if src in visited:
                        continue
                    visited.add(src)
                    dst = game_dir/'Backup'/label/src.relative_to(base)
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    before = src.stat()
                    first_hash = hash_file(src)
                    shutil.copy2(src, dst)
                    after = src.stat()
                    if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size) or hash_file(dst) != first_hash or hash_file(src) != first_hash:
                        raise RuntimeError(f'Datei während der Sicherung verändert: {src}')
                    manifest['files'].append({'game':game.name, 'source':str(src),
                        'backup':str(dst.relative_to(run)), 'sha256':first_hash, 'bytes':after.st_size})
        if not manifest['files']:
            raise ValueError('Keine sicherbaren Dateien gefunden.')
        manifest['status'] = 'complete'
    except Exception as exc:
        manifest['status'] = 'incomplete'
        manifest['errors'].append(str(exc))
        raise
    finally:
        (run/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
        (run/'HINWEISE.txt').write_text('Backup enthält eigenständige Kopien. Originalordner enthält Links zu den echten Spielstandordnern.\nÄnderungen über diese Links verändern Originale.\nmanifest.json dokumentiert Herkunft, Prüfsummen und Erfolg. Bei status=incomplete ist die Sicherung unvollständig.\nZum Wiederherstellen Spiel und Launcher schließen und ausgewählte Dateien an den unter source angegebenen Ort kopieren.\n')
    return run

def inspect_backup(folder: Path) -> dict:
    """Verification and duplicate preview only; no deletion or source access."""
    folder = folder.resolve()
    manifest = json.loads((folder/'manifest.json').read_text())
    if manifest.get('format') != 'mysavebackup' or manifest.get('version') != 1:
        raise ValueError('Kein unterstütztes MySaveBackup-Backup.')
    seen = {}; duplicates = []; errors = []
    for row in manifest['files']:
        p = folder/row['backup']
        if not p.resolve().is_relative_to(folder) or any(x.is_symlink() for x in [p,*p.parents] if x.is_relative_to(folder)):
            errors.append(f'Unsicherer Pfad: {row["backup"]}'); continue
        if not p.is_file() or hash_file(p) != row['sha256']:
            errors.append(f'Fehlt oder verändert: {row["backup"]}'); continue
        key = (row['game'], row['sha256'], row['bytes'])
        if key in seen and p.read_bytes() == (folder/seen[key]).read_bytes():
            duplicates.append({'copy':row['backup'], 'keep':seen[key]})
        else:
            seen[key] = row['backup']
    return {'files':len(manifest['files']), 'status':manifest['status'],
            'errors':errors, 'duplicates':duplicates}
