import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from mysavebackup.core import Game, backup
from mysavebackup.restore import prepare_restore, execute_restore, prepare_undo

class RestoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.source=self.root/'saves';self.source.mkdir()
        self.file=self.source/'slot.sav';self.file.write_text('old')
        self.folder=Path(backup([Game('Test',[self.source])],self.root/'backups',lambda _:None))
        self.file.write_text('new');self.recovery=self.root/'recovery'
    def plan(self): return prepare_restore(self.folder,'Test',[self.source])
    def test_preview_restore_and_undo(self):
        extra=self.source/'extra.sav';extra.write_text('keep')
        plan=self.plan();self.assertEqual(self.file.read_text(),'new')
        result=execute_restore(plan,self.recovery)
        self.assertEqual(self.file.read_text(),'old');self.assertEqual(extra.read_text(),'keep')
        execute_restore(prepare_undo(result['recovery'],[self.source]),self.recovery)
        self.assertEqual(self.file.read_text(),'new');self.assertEqual(extra.read_text(),'keep')
    def test_missing_file_and_undo(self):
        self.file.unlink()
        result=execute_restore(self.plan(),self.recovery)
        self.assertEqual(self.file.read_text(),'old')
        execute_restore(prepare_undo(result['recovery'],[self.source]),self.recovery)
        self.assertFalse(self.file.exists())
    def test_changed_since_preview(self):
        plan=self.plan();self.file.write_text('later')
        with self.assertRaises(ValueError):execute_restore(plan,self.recovery)
        self.assertEqual(self.file.read_text(),'later')
    def test_changed_since_restore(self):
        result=execute_restore(self.plan(),self.recovery);self.file.write_text('later')
        with self.assertRaises(ValueError):prepare_undo(result['recovery'],[self.source])
        self.assertEqual(self.file.read_text(),'later')
    def test_untrusted_target(self):
        with self.assertRaises(ValueError):prepare_restore(self.folder,'Test',[self.root/'other'])
    def test_corrupt_payload(self):
        plan=self.plan();plan.changes[0].payload.write_text('bad')
        with self.assertRaises(ValueError):self.plan()
        self.assertEqual(self.file.read_text(),'new')
    def test_symlink_target(self):
        other=self.root/'other';other.write_text('untouched');self.file.unlink();self.file.symlink_to(other)
        with self.assertRaises(ValueError):self.plan()
        self.assertEqual(other.read_text(),'untouched')
    def test_safety_copy_failure(self):
        with patch('mysavebackup.restore.shutil.copy2',side_effect=OSError('disk full')):
            with self.assertRaises(RuntimeError):execute_restore(self.plan(),self.recovery)
        self.assertEqual(self.file.read_text(),'new')
    def test_partial_failure_can_be_undone(self):
        import mysavebackup.restore as restore
        second=self.source/'second.sav';second.write_text('old2')
        self.file.write_text('old')
        folder=Path(backup([Game('Test',[self.source])],self.root/'backups',lambda _:None))
        self.file.write_text('new');second.write_text('new2')
        original=restore.atomic_copy;calls=[]
        def fail_second(*args):
            calls.append(args)
            if len(calls)==2:raise OSError('disk full')
            return original(*args)
        with patch('mysavebackup.restore.atomic_copy',side_effect=fail_second):
            with self.assertRaises(RuntimeError):execute_restore(prepare_restore(folder,'Test',[self.source]),self.recovery)
        recovery=next(self.recovery.iterdir())
        execute_restore(prepare_undo(recovery,[self.source]),self.recovery)
        self.assertEqual(self.file.read_text(),'new');self.assertEqual(second.read_text(),'new2')
