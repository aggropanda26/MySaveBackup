import json
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import patch, Mock
import zipfile
from mysavebackup.core import backup, Game
from mysavebackup.onedrive import (pack_backup, unpack_backup, Graph, CloudError,
                                  run_cloud, access_token, Vault, CHUNK, GRAPH)

class Response:
    def __init__(self, code=200, data=None, headers=None, content=b''):
        self.status_code=code;self.data=data or {};self.headers=headers or {};self.content=content
    def json(self): return self.data
    def close(self): pass
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
    def iter_content(self,*args):yield self.content

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'original';self.source.mkdir()
        (self.source/'slot.sav').write_bytes(b'game-progress')
        self.backup=backup([Game('Test',[self.source])],self.root/'backups')
        self.archive=self.root/'backup.zip'
    def test_round_trip_only_manifest_files(self):
        (self.backup/'unrelated-token.txt').write_text('private')
        pack_backup(self.backup,self.archive)
        with zipfile.ZipFile(self.archive) as z:
            self.assertEqual(len(z.namelist()),2)
            self.assertNotIn('unrelated-token.txt',z.namelist())
            self.assertFalse(any('Originalordner' in n for n in z.namelist()))
        downloaded=Path(unpack_backup(self.archive,self.root/'downloads'))
        manifest=json.loads((downloaded/'manifest.json').read_text())
        self.assertEqual((downloaded/manifest['files'][0]['backup']).read_bytes(),b'game-progress')
        self.assertEqual((self.source/'slot.sav').read_bytes(),b'game-progress')
    def test_corrupt_backup_no_upload(self):
        manifest=json.loads((self.backup/'manifest.json').read_text())
        (self.backup/manifest['files'][0]['backup']).write_text('bad')
        with self.assertRaises(CloudError):pack_backup(self.backup,self.archive)
    def test_source_link_rejected(self):
        manifest=json.loads((self.backup/'manifest.json').read_text())
        p=self.backup/manifest['files'][0]['backup'];p.unlink();p.symlink_to(self.source/'slot.sav')
        with self.assertRaises(ValueError):pack_backup(self.backup,self.archive)
    def test_incomplete_backup_rejected(self):
        p=self.backup/'manifest.json';m=json.loads(p.read_text());m['status']='incomplete';p.write_text(json.dumps(m))
        with self.assertRaises(ValueError):pack_backup(self.backup,self.archive)
    def test_zip_traversal_and_unexpected_files_rejected(self):
        for name in ('../outside','/absolute','folder\\escape'):
            with zipfile.ZipFile(self.archive,'w') as z:z.writestr(name,b'bad')
            with self.assertRaises(CloudError):unpack_backup(self.archive,self.root/'downloads')
            self.assertEqual(list((self.root/'downloads').iterdir()),[])
        pack_backup(self.backup,self.archive)
        with zipfile.ZipFile(self.archive,'a') as z:z.writestr('extra',b'bad')
        with self.assertRaises(CloudError):unpack_backup(self.archive,self.root/'downloads')
    def test_cancel_leaves_no_download_and_original_unchanged(self):
        pack_backup(self.backup,self.archive);cancel=Event();cancel.set()
        with self.assertRaises(CloudError):unpack_backup(self.archive,self.root/'downloads',cancel=cancel)
        self.assertEqual(list((self.root/'downloads').iterdir()),[])
        self.assertEqual((self.source/'slot.sav').read_bytes(),b'game-progress')
    def test_hash_failure_removes_download(self):
        pack_backup(self.backup,self.archive)
        with zipfile.ZipFile(self.archive) as z:entries={n:z.read(n) for n in z.namelist()}
        name=next(n for n in entries if n!='manifest.json');entries[name]=b'changed'
        with zipfile.ZipFile(self.archive,'w') as z:
            for n,data in entries.items():z.writestr(n,data)
        with self.assertRaises(CloudError):unpack_backup(self.archive,self.root/'downloads')
        self.assertEqual(list((self.root/'downloads').iterdir()),[])

class GraphTests(unittest.TestCase):
    def test_upload_chunks_without_bearer_and_confirmed_size(self):
        session=Mock();size=CHUNK+5
        session.request.side_effect=[Response(data={'id':'app'}),Response(data={'uploadUrl':'https://upload.example/session'}),
            Response(202,{'nextExpectedRanges':[str(CHUNK)+'-']}),Response(201,{'id':'file','size':size,'name':'result.zip'})]
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'file';p.write_bytes(b'x'*size)
            result=Graph('secret',session=session).upload(p)
        self.assertEqual(result['id'],'file')
        calls=session.request.call_args_list
        self.assertEqual(calls[1].kwargs['json'], {'item': {'@microsoft.graph.conflictBehavior': 'fail'}})
        self.assertIn('MySaveBackup_', calls[1].args[1])
        self.assertEqual(calls[0].kwargs['headers']['Authorization'],'Bearer secret')
        for call in calls[2:]:self.assertNotIn('Authorization',call.kwargs['headers'])
        self.assertEqual(calls[2].kwargs['headers']['Content-Range'],f'bytes 0-{CHUNK-1}/{size}')
        self.assertEqual(calls[3].kwargs['headers']['Content-Range'],f'bytes {CHUNK}-{size-1}/{size}')
    def test_auth_not_forwarded_to_other_host(self):
        session=Mock()
        with self.assertRaises(CloudError):Graph('secret',session=session).request('GET','https://example.com/data')
        session.request.assert_not_called()
    def test_server_error_is_redacted(self):
        session=Mock();session.request.return_value=Response(403,{'error':'private-secret'})
        with self.assertRaises(CloudError) as cm:Graph('secret',session=session).json('GET','/me')
        self.assertNotIn('private-secret',str(cm.exception))
    def test_retry_throttled_request(self):
        session=Mock();session.request.side_effect=[Response(429,headers={'Retry-After':'0'}),Response(data={'id':'app'})]
        cancel=Mock();cancel.is_set.return_value=False
        self.assertEqual(Graph('secret',cancel,session).app_folder(),'app')
        self.assertEqual(session.request.call_count,2)
    def test_listing_pagination(self):
        session=Mock();session.request.side_effect=[Response(data={'id':'app'}),
            Response(data={'value':[{'id':'1','name':'MySaveBackup_a.zip','size':3,'file':{}}], '@odata.nextLink':GRAPH+'/page2'}),
            Response(data={'value':[{'id':'2','name':'other.zip','file':{}}]})]
        self.assertEqual(len(Graph('secret',session=session).listing()),1)
    def test_unknown_exception_never_leaks_token(self):
        with patch('mysavebackup.onedrive.access_token',side_effect=RuntimeError('secret-token')):
            with self.assertRaises(CloudError) as cm:run_cloud('/unused','connect')
        self.assertNotIn('secret-token',str(cm.exception))
    def test_download_does_not_forward_auth(self):
        session=Mock();session.request.side_effect=[Response(302,headers={'Location':'https://download.example/private'}),Response(302,headers={'Location':'https://cdn.example/file'}),Response(content=b'abc')]
        graph=Graph('secret',session=session)
        with tempfile.TemporaryDirectory() as d,patch.object(graph,'listing',return_value=[{'id':'item'}]):
            p=Path(d)/'archive';graph.download({'id':'item','size':3},p)
            self.assertEqual(p.read_bytes(),b'abc')
        for call in session.request.call_args_list[1:]:
            self.assertNotIn('Authorization',call.kwargs['headers'])

class AuthTests(unittest.TestCase):
    def test_success_saved_in_vault_and_login_scopes(self):
        try:import msal
        except ImportError:self.skipTest('Optional MSAL dependency absent')
        with tempfile.TemporaryDirectory() as d,patch('mysavebackup.onedrive.Vault') as vault,patch('msal.PublicClientApplication') as app:
            vault.return_value.read.return_value=None
            app.return_value.acquire_token_interactive.return_value={'access_token':'secret','id_token_claims':{'name':'Test'}}
            token,label=access_token(d,True)
            self.assertEqual(label,'Test');vault.return_value.write.assert_called_once()
            self.assertIn('Files.ReadWrite.AppFolder',app.return_value.acquire_token_interactive.call_args.kwargs['scopes'])
            self.assertFalse(list(Path(d).glob('*.json')))
    def test_failed_login_preserves_existing_cache(self):
        try:import msal
        except ImportError:self.skipTest('Optional MSAL dependency absent')
        with tempfile.TemporaryDirectory() as d,patch('mysavebackup.onedrive.Vault') as vault,patch('msal.PublicClientApplication') as app:
            vault.return_value.read.return_value=None;app.return_value.acquire_token_interactive.return_value={'error_description':'secret'}
            with self.assertRaises(CloudError):access_token(d,True)
            vault.return_value.write.assert_not_called()
    def test_missing_keyring_fails_without_plaintext_fallback(self):
        with patch('keyring.backends.SecretService.Keyring',side_effect=RuntimeError('private')):
            with self.assertRaises(CloudError) as cm:Vault()
        self.assertNotIn('private',str(cm.exception))
