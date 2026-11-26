import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('installer',Path(__file__).resolve().parents[1]/'tools/install.py')
installer=importlib.util.module_from_spec(spec);spec.loader.exec_module(installer)

class InstallerTests(unittest.TestCase):
    def test_install_update_and_launch(self):
        with tempfile.TemporaryDirectory() as tmp:
            base=Path(tmp);source=base/'source';source.mkdir()
            shutil.copytree(Path(__file__).resolve().parents[1]/'mysavebackup',source/'mysavebackup')
            shutil.copytree(Path(__file__).resolve().parents[1]/'assets',source/'assets')
            (source/'local_sources.json').write_text('[]')
            (source/'CHANGELOG.txt').write_text('Erste Installation\n')
            home=base/'User with spaces';home.mkdir()
            app=installer.install(source,home)
            binary=home/'.local/bin/mysavebackup';desktop=home/'.local/share/applications/mysavebackup.desktop'
            self.assertTrue(os.access(binary,os.X_OK))
            self.assertEqual((app/'icon.png').read_bytes(), (source/'assets/icon.png').read_bytes())
            self.assertIn('Icon='+str(app/'icon.png'), desktop.read_text())
            subprocess.run(['bash','-n',str(binary)],check=True)
            if shutil.which('desktop-file-validate'):
                subprocess.run(['desktop-file-validate',str(desktop)],check=True)
            self.assertEqual((app/'local_sources.json').read_text(),'[]')
            self.assertEqual((app/'CHANGELOG.txt').read_text(), 'Erste Installation\n')
            (source/'CHANGELOG.txt').write_text('Aktualisierte Version\n')
            # Updating preserves user config and backup contents.
            config=home/'.config/mysavebackup';config.mkdir(parents=True)
            (config/'manual-sources.json').write_text('[]')
            backup=home/'Backups';backup.mkdir();(backup/'slot.sav').write_text('saved')
            installer.install(source,home)
            self.assertEqual((app/'CHANGELOG.txt').read_text(), 'Aktualisierte Version\n')
            self.assertEqual((backup/'slot.sav').read_text(),'saved')
            self.assertEqual((config/'manual-sources.json').read_text(),'[]')
            env=dict(os.environ,QT_QPA_PLATFORM='offscreen',HOME=str(home))
            process=subprocess.Popen([str(binary)],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
            try:
                with self.assertRaises(subprocess.TimeoutExpired):process.communicate(timeout=2)
            finally:
                process.terminate();process.communicate(timeout=5)

    def test_unrelated_destination_not_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);app=home/'.local/share/mysavebackup';app.mkdir(parents=True)
            file=app/'important';file.write_text('keep')
            with self.assertRaises(RuntimeError):installer.install(Path(__file__).parent,home)
            self.assertEqual(file.read_text(),'keep')

    def test_link_destination_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);(home/'.local/share').mkdir(parents=True)
            target=home/'target';target.mkdir()
            (home/'.local/share/mysavebackup').symlink_to(target)
            with self.assertRaises(RuntimeError):installer.install(Path(__file__).parent,home)
            self.assertEqual(list(target.iterdir()),[])

if __name__=='__main__':unittest.main()
