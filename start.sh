#!/usr/bin/env sh
set -eu
cd -- "$(dirname -- "$0")"
for candidate in .venv/bin/python venv/bin/python python3.12 python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
        exec "$candidate" launch.py "$@"
    fi
done
echo "Python is missing. Install Python 3.12; see docs/setup.md." >&2
exit 1
