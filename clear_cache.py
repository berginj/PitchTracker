#!/usr/bin/env python3
"""Clear all Python bytecode cache files.

NOTE: As of recent versions, launcher.py automatically clears cache on startup,
so you typically don't need to run this script manually.

Use this script when:
- Running tests or scripts directly (not via launcher.py)
- Troubleshooting persistent cache issues
- You want to disable auto-clearing (set PITCHTRACKER_NO_CACHE_CLEAR=1)
"""

import pathlib
import shutil

# Remove all .pyc files
pyc_count = 0
for p in pathlib.Path('.').rglob('*.pyc'):
    try:
        p.unlink()
        pyc_count += 1
    except Exception as e:
        print(f"Could not delete {p}: {e}")

# Remove all __pycache__ directories
cache_count = 0
for p in pathlib.Path('.').rglob('__pycache__'):
    try:
        shutil.rmtree(p)
        cache_count += 1
    except Exception as e:
        print(f"Could not delete {p}: {e}")

print(f"Cleared {pyc_count} .pyc files and {cache_count} __pycache__ directories")
if pyc_count > 0 or cache_count > 0:
    print("Python cache cleared!")
else:
    print("Cache already clean (launcher.py clears cache automatically on startup).")
