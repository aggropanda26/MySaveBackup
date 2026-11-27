import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QEventLoop, QTimer, Qt
from mysavebackup.gui import Window
from mysavebackup.core import Game, inspect_backup

class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def test_background_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            base=Path(temp);source=base/'source';source.mkdir();(source/'slot.sav').write_text('progress')
            window=Window();window.games=[Game('GUI Test',[source])];window.populate()
            self.assertEqual(window.tree.topLevelItem(0).checkState(0),Qt.CheckState.Checked)
            window.destination.setText(str(base/'backups'))
            window.make_backup()
            loop=QEventLoop()
            window.worker.finished.connect(loop.quit)
            QTimer.singleShot(10000,loop.quit);loop.exec()
            self.assertIsNotNone(window.last_backup)
            self.assertEqual(inspect_backup(window.last_backup)['errors'],[])
            self.assertIsNone(window.worker)
            self.assertEqual((source/'slot.sav').read_text(),'progress')
            window.close()

    def test_first_start_notice_dismissed_permanently(self):
        with tempfile.TemporaryDirectory() as temp:
            config=Path(temp)/'config'
            window=Window(config_dir=config);window.show()
            self.app.processEvents()
            self.assertTrue(window.first_start_banner.isVisible())
            self.assertTrue(window.dismiss_first_start_button.isEnabled())
            self.assertTrue(window.scan_button.isEnabled())
            window.dismiss_first_start_button.click()
            self.assertFalse(window.first_start_banner.isVisible())
            self.assertTrue((config/'first-start-dismissed').is_file())
            window.close()
            reopened=Window(config_dir=config);reopened.show()
            self.app.processEvents()
            self.assertFalse(reopened.first_start_banner.isVisible())
            reopened.close()

    def test_notice_closes_even_if_config_cannot_be_written(self):
        with tempfile.TemporaryDirectory() as temp:
            window=Window(config_dir=Path(temp)/'config');window.show()
            with patch.object(Path, 'touch', side_effect=PermissionError('read-only')):
                window.dismiss_first_start_button.click()
            self.assertFalse(window.first_start_banner.isVisible())
            self.assertTrue(window.scan_button.isEnabled())
            window.close()

    def test_single_click_on_source_opens_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); source=root/'Save Games'; source.mkdir()
            window=Window(config_dir=root/'config')
            window.games=[Game('Test',[source])];window.populate();window.show()
            game=window.tree.topLevelItem(0);game.setExpanded(True)
            self.app.processEvents()
            with patch('mysavebackup.gui.QDesktopServices.openUrl', return_value=True) as opened:
                QTest.mouseClick(window.tree.viewport(), Qt.MouseButton.LeftButton,
                                 pos=window.tree.visualItemRect(game.child(0)).center())
                self.assertEqual(opened.call_count,1)
                self.assertEqual(opened.call_args.args[0].toLocalFile(),str(source))
                opened.reset_mock()
                QTest.mouseClick(window.tree.viewport(), Qt.MouseButton.LeftButton,
                                 pos=window.tree.visualItemRect(game).center())
                opened.assert_not_called()
            window.close()

    def test_file_source_opens_parent_and_missing_source_does_not_open(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp); file=root/'slot.sav';file.write_text('save')
            window=Window(config_dir=root/'config')
            with patch('mysavebackup.gui.QDesktopServices.openUrl', return_value=True) as opened:
                window.open_source_path(file)
                self.assertEqual(opened.call_args.args[0].toLocalFile(),str(root))
                opened.reset_mock();window.open_source_path(root/'missing')
                opened.assert_not_called()
            window.close()

    def test_restore_confirmation_required_and_cancel_no_write(self):
        from mysavebackup.gui import RestoreDialog
        from mysavebackup.restore import prepare_restore
        from mysavebackup.core import backup
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'saves';source.mkdir();slot=source/'slot.sav';slot.write_text('old')
            folder=backup([Game('Test',[source])],root/'backups',lambda _:None);slot.write_text('new')
            plan=prepare_restore(folder,'Test',[source]);window=Window(config_dir=root/'config')
            dialog=RestoreDialog(plan,root/'recovery',window)
            self.assertFalse(dialog.apply_button.isEnabled())
            dialog.confirmation.setChecked(True);self.assertTrue(dialog.apply_button.isEnabled())
            dialog.reject()
            with patch('mysavebackup.gui.RestoreDialog.exec',return_value=0),patch('mysavebackup.gui.execute_restore') as execute:
                window.confirm_restore(plan);execute.assert_not_called()
            self.assertEqual(slot.read_text(),'new');window.close()

    def test_restore_preview_worker_then_execution(self):
        from mysavebackup.restore import prepare_restore
        from mysavebackup.core import backup
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);source=root/'saves';source.mkdir();slot=source/'slot.sav';slot.write_text('old')
            folder=backup([Game('Test',[source])],root/'backups',lambda _:None);slot.write_text('new')
            window=Window(config_dir=root/'config');window.destination.setText(str(root/'backups'))
            with patch('mysavebackup.gui.RestoreDialog.exec',return_value=1):
                window.start('prepare_restore',lambda _:prepare_restore(folder,'Test',[source]))
                import time
                deadline=time.monotonic()+5
                while window.last_recovery is None and time.monotonic()<deadline:
                    self.app.processEvents();QTest.qWait(10)
                self.app.processEvents()
            self.assertIsNotNone(window.last_recovery);self.assertIsNone(window.worker)
            self.assertEqual(slot.read_text(),'old');window.close()

    def test_cloud_upload_requires_confirmation(self):
        from PySide6.QtWidgets import QMessageBox
        with tempfile.TemporaryDirectory() as d:
            window=Window(config_dir=Path(d)/'config')
            with patch('mysavebackup.gui.QFileDialog.getExistingDirectory',return_value=d),patch('mysavebackup.gui.QMessageBox.question',return_value=QMessageBox.StandardButton.No),patch.object(window,'start_cloud') as start:
                window.upload_cloud();start.assert_not_called()
            window.close()

    def test_cloud_connect_runs_in_background(self):
        with tempfile.TemporaryDirectory() as d:
            window=Window(config_dir=Path(d)/'config')
            with patch('mysavebackup.gui.run_cloud',return_value='Testkonto'):
                window.connect_cloud()
                self.assertFalse(window.cloud_upload.isEnabled())
                loop=QEventLoop();window.worker.finished.connect(loop.quit)
                QTimer.singleShot(5000,loop.quit);loop.exec()
            self.assertIn('Testkonto',window.cloud_status.text())
            self.assertTrue(window.cloud_upload.isEnabled());window.close()
