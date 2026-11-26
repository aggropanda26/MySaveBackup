import os
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import tempfile
import unittest
from pathlib import Path
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
