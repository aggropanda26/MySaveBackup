"""Previewed restores with verified recovery copies; never invoked by scanning."""
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
import json
import os
import shutil
import tempfile
import uuid
from .core import hash_file

@dataclass(frozen=True)
class Change:
    target: Path
    payload: Path | None
    before_hash: str | None
    after_hash: str | None

    @property
    def action(self):
        if self.payload is None: return 'Entfernen (bei Wiederherstellung neu angelegt)'
        return 'Ersetzen' if self.before_hash is not None else 'Neu anlegen'

@dataclass(frozen=True)
class RestorePlan:
    game: str
    backup: Path
    allowed: tuple[Path, ...]
    changes: tuple[Change, ...]


def plain_path(path):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise ValueError(f'Kein sicherer absoluter Pfad: {path}')
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError(f'Verknüpfung im Pfad wird nicht überschrieben: {path}')
    return path


def inside(root, relative):
    rel = Path(relative)
    if rel.is_absolute() or '..' in rel.parts or not rel.parts:
        raise ValueError('Unsicherer Dateipfad in der Sicherung.')
    path = plain_path(root/rel)
    if not path.is_relative_to(root): raise ValueError('Datei liegt außerhalb der Sicherung.')
    return path


def current_hash(path):
    plain_path(path)
    if not path.exists(): return None
    if not path.is_file(): raise ValueError(f'Ziel ist keine normale Datei: {path}')
    return hash_file(path)


def check_target(path, allowed, backup):
    path = plain_path(path)
    if not any(path == source or path.is_relative_to(source) for source in allowed):
        raise ValueError(f'Ziel gehört zu keinem lokal bekannten Spielstandordner: {path}')
    if path == backup or path.is_relative_to(backup):
        raise ValueError('Die Sicherung selbst darf nicht überschrieben werden.')
    return path


def load_manifest(folder):
    folder = plain_path(Path(folder).absolute())
    m = json.loads(plain_path(folder/'manifest.json').read_text())
    if m.get('format') != 'mysavebackup' or m.get('version') != 1 or m.get('status') != 'complete':
        raise ValueError('Nur vollständig erstellte MySaveBackup-Sicherungen werden unterstützt.')
    if not isinstance(m.get('files'), list): raise ValueError('Ungültiges Backup-Manifest.')
    return folder, m


def backup_games(folder):
    _, manifest = load_manifest(folder)
    return sorted({row['game'] for row in manifest['files']})


def prepare_restore(folder, game, allowed_sources):
    folder, manifest = load_manifest(folder)
    allowed = tuple(plain_path(Path(p).absolute()) for p in allowed_sources)
    if not allowed: raise ValueError('Keine lokal bekannten Speicherorte für dieses Spiel. Bitte zuerst Spiele suchen oder den originalen Spielstandordner manuell hinzufügen.')
    changes = []; seen = set(); matched = False
    for row in manifest['files']:
        if row['game'] != game: continue
        matched = True
        target = check_target(Path(row['source']), allowed, folder)
        if target in seen: raise ValueError(f'Doppeltes Wiederherstellungsziel: {target}')
        seen.add(target)
        payload = inside(folder, row['backup'])
        if not payload.is_file() or payload.stat().st_size != row['bytes'] or hash_file(payload) != row['sha256']:
            raise ValueError(f'Backup-Datei fehlt oder ist verändert: {payload}')
        before = current_hash(target)
        if before != row['sha256']:
            changes.append(Change(target, payload, before, row['sha256']))
    if not matched: raise ValueError('Spiel ist in dieser Sicherung nicht enthalten.')
    return RestorePlan(game, folder, allowed, tuple(changes))


def verify_change(change, allowed, backup):
    check_target(change.target, allowed, backup)
    if current_hash(change.target) != change.before_hash:
        raise ValueError(f'Spielstand seit der Vorschau verändert. Bitte erneut prüfen: {change.target}')
    if change.payload is not None:
        plain_path(change.payload)
        if not change.payload.is_file() or hash_file(change.payload) != change.after_hash:
            raise ValueError(f'Sicherungsdatei seit der Vorschau verändert: {change.payload}')


def write_json(path, data):
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temp.replace(path)


def atomic_copy(source, destination, expected_hash):
    plain_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.mysavebackup-', dir=destination.parent)
    os.close(fd)
    temp = Path(name)
    try:
        shutil.copy2(source, temp)
        if hash_file(temp) != expected_hash: raise OSError('Kopierprüfung fehlgeschlagen.')
        plain_path(destination)
        os.replace(temp, destination)
    finally:
        temp.unlink(missing_ok=True)


def execute_restore(plan, recovery_root, progress=lambda text: None):
    if not plan.changes: raise ValueError('Alle Dateien entsprechen bereits der Sicherung.')
    recovery_root = plain_path(Path(recovery_root).expanduser().absolute())
    if recovery_root == plan.backup or recovery_root.is_relative_to(plan.backup):
        raise ValueError('Sicherheitskopie muss außerhalb des ausgewählten Backups liegen.')
    for source in plan.allowed:
        if recovery_root == source or recovery_root.is_relative_to(source):
            raise ValueError('Sicherheitskopie darf nicht im Spielstandordner liegen.')
    for change in plan.changes: verify_change(change, plan.allowed, plan.backup)
    recovery_root.mkdir(parents=True, exist_ok=True)
    recovery = recovery_root/(datetime.now().strftime('%Y-%m-%d_%H-%M-%S')+'_'+uuid.uuid4().hex[:8])
    recovery.mkdir()
    journal = {'format':'mysavebackup-recovery','version':1,'game':plan.game,
               'created':datetime.now().astimezone().isoformat(),'status':'preparing',
               'backup':str(plan.backup),'changes':[],'completed':[]}
    try:
        # Copy and verify every affected current file before touching any original.
        for i, change in enumerate(plan.changes):
            progress(f'Sicherheitskopie {i+1}/{len(plan.changes)}')
            verify_change(change, plan.allowed, plan.backup)
            before = f'before/{i:06d}' if change.before_hash is not None else None
            staged = f'incoming/{i:06d}' if change.payload is not None else None
            if before:
                p=recovery/before;p.parent.mkdir(exist_ok=True)
                shutil.copy2(change.target,p)
                if hash_file(p)!=change.before_hash or current_hash(change.target)!=change.before_hash:
                    raise ValueError(f'Spielstand während Sicherheitskopie verändert: {change.target}')
            if staged:
                p=recovery/staged;p.parent.mkdir(exist_ok=True)
                shutil.copy2(change.payload,p)
                if hash_file(p)!=change.after_hash: raise ValueError('Backup-Datei während Vorbereitung verändert.')
            journal['changes'].append({'target':str(change.target),'before':before,
                'before_hash':change.before_hash,'after_hash':change.after_hash,'incoming':staged})
        journal['status']='prepared';write_json(recovery/'recovery.json',journal)
        for change in plan.changes: verify_change(change, plan.allowed, plan.backup)
        for i, change in enumerate(plan.changes):
            progress(f'Wiederherstellen {i+1}/{len(plan.changes)} · {plan.game}')
            verify_change(change, plan.allowed, plan.backup)
            if change.payload is None:
                change.target.unlink()
            else:
                atomic_copy(recovery/journal['changes'][i]['incoming'],change.target,change.after_hash)
            journal['completed'].append(i)
            write_json(recovery/'recovery.json',journal)
        journal['status']='complete';write_json(recovery/'recovery.json',journal)
        return {'recovery':str(recovery),'files':len(plan.changes),'game':plan.game}
    except Exception as exc:
        journal['status']='incomplete';journal['error']=str(exc)
        try: write_json(recovery/'recovery.json',journal)
        except OSError: pass
        raise RuntimeError(f'Wiederherstellung nicht vollständig: {exc}\nSicherheitskopie: {recovery}\nGegebenenfalls „Wiederherstellung rückgängig“ verwenden.') from exc


def prepare_undo(folder, allowed_sources):
    folder=plain_path(Path(folder).absolute())
    journal=json.loads(plain_path(folder/'recovery.json').read_text())
    if journal.get('format')!='mysavebackup-recovery' or journal.get('version')!=1 or journal.get('status') not in ('complete','incomplete','prepared'):
        raise ValueError('Keine abgeschlossene oder fehlgeschlagene Wiederherstellung.')
    allowed=tuple(plain_path(Path(p).absolute()) for p in allowed_sources)
    changes=[];seen=set()
    for row in journal['changes']:
        target=check_target(Path(row['target']),allowed,folder)
        if target in seen: raise ValueError('Doppeltes Ziel in der Sicherheitskopie.')
        seen.add(target)
        now=current_hash(target)
        # Unchanged entries from a partial restore need no action.
        if now==row['before_hash']: continue
        if now!=row['after_hash']:
            raise ValueError(f'Seit der Wiederherstellung neuer oder veränderter Spielstand; Rücknahme abgebrochen: {target}')
        payload=inside(folder,row['before']) if row['before'] else None
        if payload is not None and (not payload.is_file() or hash_file(payload)!=row['before_hash']):
            raise ValueError(f'Sicherheitskopie fehlt oder ist verändert: {payload}')
        if payload is None and row['before_hash'] is not None: raise ValueError('Ungültige Sicherheitskopie.')
        changes.append(Change(target,payload,now,row['before_hash']))
    return RestorePlan(journal['game'],folder,allowed,tuple(changes))
