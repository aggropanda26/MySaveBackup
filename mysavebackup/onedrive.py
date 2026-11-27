"""OneDrive personal accounts: MSAL, Secret Service, verified backup archives."""
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
import fcntl
import hashlib
import json
import os
import shutil
import stat
import tempfile
import time
import uuid
import zipfile
from urllib.parse import quote, urlparse
from .restore import load_manifest, inside, plain_path

CLIENT_ID = '3aa3a3de-809e-48ac-8bb3-b6b44d618607'
SCOPES = ['Files.ReadWrite.AppFolder', 'User.Read']
GRAPH = 'https://graph.microsoft.com/v1.0'
CHUNK = 10 * 1024 * 1024  # Multiple of 320 KiB, below Graph's 60 MiB limit.
MAX_ARCHIVE = 20 * 1024**3

class CloudError(RuntimeError):
    pass


def check_cancel(cancel):
    if cancel and cancel.is_set():
        raise CloudError('Cloud-Vorgang abgebrochen. Das lokale Backup bleibt erhalten.')


class Vault:
    """Use Secret Service explicitly; never fall back to a plaintext keyring."""
    def __init__(self):
        try:
            from keyring.backends.SecretService import Keyring
            self.backend = Keyring()
            if self.backend.priority <= 0:
                raise RuntimeError()
        except Exception:
            raise CloudError('Linux-Schlüsselbund nicht verfügbar. Bitte Secret Service (z. B. KWallet oder GNOME Keyring) starten und entsperren. Es werden keine Tokens unverschlüsselt gespeichert.') from None

    def read(self):
        try:
            return self.backend.get_password('MySaveBackup.OneDrive', CLIENT_ID)
        except Exception:
            raise CloudError('OneDrive-Zugang konnte nicht aus dem Schlüsselbund gelesen werden.') from None

    def write(self, value):
        try:
            self.backend.set_password('MySaveBackup.OneDrive', CLIENT_ID, value)
        except Exception:
            raise CloudError('OneDrive-Zugang konnte nicht im Schlüsselbund gespeichert werden.') from None

    def delete(self):
        try:
            if self.read() is not None:
                self.backend.delete_password('MySaveBackup.OneDrive', CLIENT_ID)
        except Exception:
            raise CloudError('OneDrive-Zugang konnte nicht aus dem Schlüsselbund entfernt werden.') from None


@contextmanager
def auth_lock(config):
    config = Path(config)
    config.mkdir(parents=True, exist_ok=True)
    path = config/'onedrive.lock'
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise CloudError('OneDrive wird gerade in einem anderen App-Fenster verwendet.') from None
        yield
    finally:
        os.close(fd)


def access_token(config, interactive=False, progress=lambda _: None):
    try:
        import msal
    except ImportError:
        raise CloudError('OneDrive-Komponenten fehlen. App mit ./install.sh --with-onedrive aktualisieren.') from None
    with auth_lock(config):
        vault = Vault()
        cache = msal.SerializableTokenCache()
        try:
            stored = vault.read()
            if stored: cache.deserialize(stored)
            app = msal.PublicClientApplication(CLIENT_ID, authority='https://login.microsoftonline.com/consumers',
                                              token_cache=cache, timeout=30)
            if interactive:
                # Replace an old account only when the new login succeeds.
                fresh = msal.SerializableTokenCache()
                app = msal.PublicClientApplication(CLIENT_ID, authority='https://login.microsoftonline.com/consumers',
                                                  token_cache=fresh, timeout=30)
                progress('Bitte im Browser bei Microsoft anmelden (Zeitlimit: 3 Minuten).')
                result = app.acquire_token_interactive(scopes=SCOPES, prompt='select_account', timeout=180)
                cache = fresh
            else:
                accounts = app.get_accounts()
                result = app.acquire_token_silent(SCOPES, account=accounts[0]) if accounts else None
            if not result or 'access_token' not in result:
                raise CloudError('Microsoft-Anmeldung abgebrochen, abgelaufen oder erneut erforderlich. Bitte „Mit OneDrive verbinden“ verwenden.')
            # Do not expose raw MSAL errors, claims or tokens to the UI/log.
            vault.write(cache.serialize())
            claims = result.get('id_token_claims', {})
            return result['access_token'], claims.get('preferred_username') or claims.get('name') or 'Microsoft-Konto'
        except CloudError:
            raise
        except Exception:
            raise CloudError('Microsoft-Anmeldung fehlgeschlagen. Internetverbindung und App-Registrierung prüfen und erneut verbinden.') from None


def disconnect(config):
    with auth_lock(config): Vault().delete()
    return 'Lokale OneDrive-Verbindung entfernt. Bereits hochgeladene Backups bleiben erhalten.'


def pack_backup(folder, archive, progress=lambda _: None, cancel=None):
    folder, manifest = load_manifest(folder)
    if not manifest['files']:
        raise CloudError('Dieses Backup enthält keine Dateien.')
    if sum(row['bytes'] for row in manifest['files']) > MAX_ARCHIVE or len(manifest['files']) > 99999:
        raise CloudError('Backup überschreitet das Cloud-Limit (20 GiB / 99.999 Dateien).')
    seen = {'manifest.json'}
    with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as out:
        for i, row in enumerate(manifest['files'], 1):
            check_cancel(cancel)
            source = inside(folder, row['backup'])
            if not source.is_file(): raise CloudError('Backup enthält keine normale Datei.')
            relative = source.relative_to(folder).as_posix()
            if relative in seen:
                raise CloudError('Doppelter Dateipfad im Backup-Manifest.')
            seen.add(relative)
            progress(f'Cloud-Archiv prüfen: {i}/{len(manifest["files"])} Dateien')
            digest = hashlib.sha256(); size = 0
            with source.open('rb') as src, out.open(relative, 'w', force_zip64=True) as dst:
                while data := src.read(1024 * 1024):
                    check_cancel(cancel); digest.update(data); size += len(data)
                    if size > row['bytes']: raise CloudError('Backup-Datei ist größer als im Manifest angegeben.')
                    dst.write(data)
            if size != row['bytes'] or digest.hexdigest() != row['sha256']:
                raise CloudError('Backup ist beschädigt oder wurde während der Vorbereitung verändert. Kein Upload gestartet.')
        # Only manifest-listed copies are included; never follow Originalordner links.
        out.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
    if Path(archive).stat().st_size > MAX_ARCHIVE:
        raise CloudError('Cloud-Archiv überschreitet das Limit dieser Version (20 GiB).')


def unpack_backup(archive, destination, progress=lambda _: None, cancel=None):
    destination = plain_path(Path(destination).expanduser().absolute())
    destination.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.onedrive-download-', dir=destination))
    try:
        with zipfile.ZipFile(archive) as src:
            infos = src.infolist()
            if len(infos) > 100000 or sum(i.file_size for i in infos) > MAX_ARCHIVE:
                raise CloudError('Entpacktes Backup ist zu groß (maximal 20 GiB / 100.000 Einträge).')
            names = set()
            for info in infos:
                check_cancel(cancel)
                path = PurePosixPath(info.filename)
                if (path.is_absolute() or '..' in path.parts or '\\' in info.filename
                        or not path.parts or info.filename in names
                        or stat.S_ISLNK(info.external_attr >> 16)):
                    raise CloudError('Unsicherer Dateipfad im Cloud-Archiv.')
                names.add(info.filename)
                target = staging.joinpath(*path.parts)
                if info.is_dir(): target.mkdir(parents=True, exist_ok=True); continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with src.open(info) as data, target.open('xb') as out:
                    while chunk := data.read(1024 * 1024):
                        check_cancel(cancel); out.write(chunk)
        _, manifest = load_manifest(staging)
        expected = {'manifest.json'}
        for i, row in enumerate(manifest['files'], 1):
            check_cancel(cancel)
            file = inside(staging, row['backup']); name = file.relative_to(staging).as_posix()
            if name in expected: raise CloudError('Doppelter Dateipfad im Cloud-Manifest.')
            expected.add(name); digest = hashlib.sha256()
            with file.open('rb') as stream:
                while chunk := stream.read(1024 * 1024):
                    check_cancel(cancel); digest.update(chunk)
            if digest.hexdigest() != row['sha256'] or file.stat().st_size != row['bytes']:
                raise CloudError('Prüfsumme des heruntergeladenen Backups stimmt nicht.')
            progress(f'Download prüfen: {i}/{len(manifest["files"])} Dateien')
        actual = {p.relative_to(staging).as_posix() for p in staging.rglob('*') if p.is_file()}
        if not manifest['files'] or actual != expected:
            raise CloudError('Cloud-Archiv enthält unerwartete Dateien oder keine Spielstände.')
        final = destination/('OneDrive_'+time.strftime('%Y-%m-%d_%H-%M-%S')+'_'+uuid.uuid4().hex[:8])
        staging.rename(final)
        return str(final)
    finally:
        if staging.exists(): shutil.rmtree(staging)


class Graph:
    def __init__(self, token, cancel=None, session=None):
        import requests
        self.requests = requests
        self.session = session or requests.Session()
        self.token = token
        self.cancel = cancel

    def close(self): self.session.close()

    def request(self, method, url, authenticated=True, **kwargs):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise CloudError('Ungültige OneDrive-Adresse.')
        if authenticated and (parsed.hostname != 'graph.microsoft.com' or parsed.port not in (None,443)):
            raise CloudError('Anmeldung darf nur an Microsoft Graph gesendet werden.')
        headers = dict(kwargs.pop('headers', {}))
        if authenticated: headers['Authorization'] = 'Bearer '+self.token
        for attempt in range(3):
            check_cancel(self.cancel)
            try:
                response = self.session.request(method, url, headers=headers, timeout=(15,45), allow_redirects=False, **kwargs)
            except self.requests.RequestException:
                if attempt == 2:
                    raise CloudError('OneDrive-Verbindung unterbrochen. Bitte erneut versuchen; lokales Backup bleibt erhalten.') from None
                continue
            if response.status_code in (429,500,502,503,504) and attempt < 2:
                try: delay = min(15, max(1, int(response.headers.get('Retry-After','2'))))
                except ValueError: delay = 2
                response.close()
                if self.cancel: self.cancel.wait(delay)
                else: time.sleep(delay)
                continue
            if response.status_code >= 400:
                status = response.status_code; response.close()
                messages = {401:'Anmeldung abgelaufen. Bitte OneDrive erneut verbinden.',
                            403:'OneDrive verweigert den Zugriff. App-Ordner-Berechtigung und Zustimmung prüfen.',
                            404:'Cloud-Datei oder Upload-Sitzung nicht mehr verfügbar.',
                            409:'Cloud-Dateiname bereits vorhanden. Bitte erneut versuchen.',
                            507:'OneDrive-Speicher ist voll.'}
                raise CloudError(messages.get(status, f'OneDrive-Anfrage fehlgeschlagen (HTTP {status}). Bitte erneut versuchen.'))
            return response
        raise CloudError('OneDrive ist momentan nicht erreichbar.')

    def json(self, method, path, **kwargs):
        with self.request(method, GRAPH+path, **kwargs) as response:
            if response.status_code not in (200,201,202):
                raise CloudError('Unerwartete Antwort von OneDrive.')
            return response.json()

    def app_folder(self):
        return self.json('GET', '/me/drive/special/approot')['id']

    def listing(self):
        folder = quote(self.app_folder(), safe='')
        url = GRAPH+f'/me/drive/items/{folder}/children?$select=id,name,size,file&$top=200'
        items = []
        while url:
            with self.request('GET',url) as response: data = response.json()
            for item in data.get('value',[]):
                if 'file' in item and item['name'].startswith('MySaveBackup_') and item['name'].endswith('.zip'):
                    items.append(item)
            url = data.get('@odata.nextLink')
            if len(items) > 10000: raise CloudError('Zu viele Cloud-Backups. Bitte alte Einträge in OneDrive verwalten.')
        return sorted(items, key=lambda i:i['name'], reverse=True)

    def upload(self, archive, progress=lambda _:None):
        folder = quote(self.app_folder(), safe='')
        name = 'MySaveBackup_'+time.strftime('%Y-%m-%d_%H-%M-%S')+'_'+uuid.uuid4().hex+'.zip'
        size = Path(archive).stat().st_size
        session = self.json('POST', f'/me/drive/items/{folder}:/{name}:/createUploadSession',
                            json={'item':{'name':name,'@microsoft.graph.conflictBehavior':'fail'}})
        url = session['uploadUrl']
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise CloudError('Ungültige OneDrive-Uploadadresse.')
        # Upload URLs are preauthenticated. Never attach the Graph bearer token.
        try:
            with Path(archive).open('rb') as source:
                offset = 0
                while offset < size:
                    check_cancel(self.cancel); source.seek(offset); chunk = source.read(CHUNK)
                    end = offset+len(chunk)-1
                    with self.request('PUT',url,authenticated=False,data=chunk,
                                      headers={'Content-Length':str(len(chunk)), 'Content-Range':f'bytes {offset}-{end}/{size}'}) as response:
                        data = response.json()
                        if response.status_code in (200,201):
                            if data.get('size') != size or not data.get('id'):
                                raise CloudError('OneDrive bestätigt nicht die erwartete Archivgröße.')
                            progress('Upload abgeschlossen: 100 %')
                            return data
                        if response.status_code != 202:
                            raise CloudError('Unerwarteter OneDrive-Uploadstatus.')
                        next_offset = int(data['nextExpectedRanges'][0].split('-')[0])
                        if next_offset != end+1:
                            raise CloudError('Uploadfortschritt ist uneindeutig. Bitte Upload erneut starten.')
                        offset = next_offset
                        progress(f'OneDrive-Upload: {offset*100//size} %')
            raise CloudError('OneDrive hat den Upload nicht abschließend bestätigt.')
        except Exception:
            # Best effort cancel of this uncommitted upload only, no cloud-file deletion.
            try:
                response=self.session.delete(url,timeout=10,allow_redirects=False);response.close()
            except Exception: pass
            raise

    def download(self, item, archive, progress=lambda _:None):
        # Verify membership in our app folder before accessing a selected item.
        if item['id'] not in {i['id'] for i in self.listing()}:
            raise CloudError('Backup ist nicht mehr im OneDrive-App-Ordner vorhanden.')
        path = '/me/drive/items/'+quote(item['id'],safe='')
        with self.request('GET',GRAPH+path+'/content') as response:
            if response.status_code != 302:
                raise CloudError('OneDrive hat keine Download-Adresse geliefert.')
            url = response.headers['Location']
        with self.request('GET',url,authenticated=False,stream=True) as response:
            if response.status_code != 200: raise CloudError('Cloud-Download konnte nicht gestartet werden.')
            total = 0
            with Path(archive).open('wb') as out:
                for chunk in response.iter_content(1024*1024):
                    check_cancel(self.cancel); total += len(chunk)
                    if total > MAX_ARCHIVE: raise CloudError('Cloud-Archiv ist zu groß (maximal 20 GiB).')
                    out.write(chunk);progress(f'OneDrive-Download: {total//1024//1024} MiB')
            if total != item['size']: raise CloudError('Cloud-Download unvollständig oder Datei inzwischen verändert.')


def run_cloud(config, action, progress=lambda _:None, cancel=None, folder=None, item=None, destination=None):
    """Worker entry point: sanitize exceptions before they reach GUI logs."""
    graph = None
    try:
        if action == 'disconnect': return disconnect(config)
        token, label = access_token(config, interactive=action=='connect', progress=progress)
        check_cancel(cancel)
        if action == 'connect': return label
        graph = Graph(token, cancel)
        if action == 'list': return graph.listing()
        with tempfile.TemporaryDirectory(prefix='mysavebackup-cloud-') as tmp:
            archive = Path(tmp)/'backup.zip'
            if action == 'upload':
                pack_backup(folder,archive,progress,cancel)
                return graph.upload(archive,progress)['name']
            if action == 'download':
                graph.download(item,archive,progress)
                return unpack_backup(archive,destination,progress,cancel)
        raise CloudError('Unbekannter Cloud-Vorgang.')
    except CloudError:
        raise
    except Exception:
        raise CloudError('Cloud-Vorgang fehlgeschlagen. Netzwerk, freien Speicher und Backup prüfen. Lokale Originalspielstände wurden nicht verändert.') from None
    finally:
        if graph: graph.close()
