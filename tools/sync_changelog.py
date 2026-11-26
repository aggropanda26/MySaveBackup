"""Synchronize the README changelog from CHANGELOG.txt."""
from pathlib import Path
import argparse
import re

START = '<!-- CHANGELOG:START -->'
END = '<!-- CHANGELOG:END -->'

def rendered_readme(root):
    readme = (root/'README.md').read_text(encoding='utf-8')
    changelog = (root/'CHANGELOG.txt').read_text(encoding='utf-8').rstrip()
    if readme.count(START) != 1 or readme.count(END) != 1:
        raise ValueError('README muss genau einen Änderungsverlauf-Abschnitt enthalten.')
    before, rest = readme.split(START, 1)
    _, after = rest.split(END, 1)
    fence = '`' * max(3, max((len(s)+1 for s in re.findall(r'`+',changelog)),default=3))
    return before + START + '\n' + fence + 'text\n' + changelog + '\n' + fence + '\n' + END + after

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    expected = rendered_readme(root)
    if args.check:
        if (root/'README.md').read_text(encoding='utf-8') != expected:
            parser.exit(1, 'README ist veraltet: python3 tools/sync_changelog.py ausführen.\n')
        print('Änderungsverlauf und README stimmen überein.')
    else:
        (root/'README.md').write_text(expected, encoding='utf-8')
        print('README-Änderungsverlauf aktualisiert.')

if __name__ == '__main__':
    main()
