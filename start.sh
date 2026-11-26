#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$(readlink -f -- "$0")")"
if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv --system-site-packages .venv
fi
if ! .venv/bin/python -c 'import PySide6' 2>/dev/null; then
    echo 'PySide6 fehlt. Unter Arch: sudo pacman -S python-pyside6'
    exit 1
fi
exec .venv/bin/python -m mysavebackup
