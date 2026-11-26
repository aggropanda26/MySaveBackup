import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from mysavebackup.core import Game, backup, inspect_backup, discover

class BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.source=self.root/'source';self.source.mkdir()
        (self.source/'slot.sav').write_bytes(b'my progress')
        self.game=Game('Test',[self.source])

    def test_verified_copies_duplicates_and_original_unchanged(self):
        (self.source/'slot-copy.sav').write_bytes(b'my progress')
        (self.source/'other.sav').write_bytes(b'older progress')
        (self.source/'steam_autocloud.vdf').write_text('metadata')
        before={p.name:p.read_bytes() for p in self.source.iterdir()}
        out=backup([self.game],self.root/'backups')
        report=inspect_backup(out)
        self.assertEqual(report['files'],3)
        self.assertEqual(len(report['duplicates']),1)
        self.assertFalse(report['errors'])
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.source.iterdir()})
        self.assertTrue((out/'01 - Test/Originalordner/01 - source').is_symlink())

    def test_destination_inside_source_rejected(self):
        with self.assertRaises(ValueError):backup([self.game],self.source/'backup')
        self.assertFalse((self.source/'backup').exists())

    def test_symlinks_not_followed(self):
        outside=self.root/'private';outside.mkdir();(outside/'secret.sav').write_text('secret')
        (self.source/'linked').symlink_to(outside,target_is_directory=True)
        (self.source/'linked.sav').symlink_to(outside/'secret.sav')
        out=backup([self.game],self.root/'backups')
        self.assertEqual(inspect_backup(out)['files'],1)

    def test_tamper_is_detected(self):
        out=backup([self.game],self.root/'backups')
        next((out/'01 - Test/Backup').rglob('*.sav')).write_text('changed')
        self.assertEqual(len(inspect_backup(out)['errors']),1)

    def test_copy_failure_writes_incomplete_manifest(self):
        with patch('mysavebackup.core.shutil.copy2',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):backup([self.game],self.root/'backups')
        manifest=next((self.root/'backups').glob('*/manifest.json'))
        self.assertEqual(json.loads(manifest.read_text())['status'],'incomplete')

    def test_inspector_rejects_path_escape(self):
        out=backup([self.game],self.root/'backups')
        p=out/'manifest.json';m=json.loads(p.read_text());m['files'][0]['backup']='../../secret'
        p.write_text(json.dumps(m))
        self.assertEqual(len(inspect_backup(out)['errors']),1)

    def test_discovery_deduplicates_nested_sources(self):
        nested=self.source/'nested';nested.mkdir();(nested/'a.sav').write_text('progress')
        seed=self.root/'seed.json'
        seed.write_text(json.dumps([{'name':'Game','sources':[str(self.source),str(nested)]}]))
        games=discover(seed,self.root/'empty-home')
        self.assertEqual(games[0].sources,[self.source])

if __name__=='__main__': unittest.main()
