#!/usr/bin/env python3
"""Clear all Python bytecode cache files."""

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
print("Python cache cleared! Now restart your application.")
