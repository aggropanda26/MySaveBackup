import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('sync_changelog', ROOT/'tools/sync_changelog.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)

class ChangelogTests(unittest.TestCase):
    def test_readme_matches_installed_changelog_source(self):
        self.assertEqual((ROOT/'README.md').read_text(encoding='utf-8'), sync.rendered_readme(ROOT))

if __name__ == '__main__':
    unittest.main()
