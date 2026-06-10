#!/usr/bin/env python3
"""PitchTracker Application Launcher

This script properly sets up the Python path and launches the PitchTracker application.

Usage:
    python launch_app.py
"""

import os
import sys
import shutil
import importlib
from pathlib import Path


def _ensure_project_root_on_sys_path(project_root: Path) -> None:
    """Insert the project root once, normalized for Windows path casing."""
    normalized_root = os.path.normcase(str(project_root))
    for entry in sys.path:
        if os.path.normcase(entry) == normalized_root:
            return
    sys.path.insert(0, str(project_root))


def _clear_import_caches_before_launcher_import(project_root: Path) -> None:
    """Remove project bytecode caches before importing launcher modules.

    This runs before importing ``launcher`` so stale ``.pyc`` files cannot keep
    an older startup path alive.
    """
    for pyc_path in project_root.rglob("*.pyc"):
        try:
            pyc_path.unlink()
        except OSError:
            pass

    for cache_dir in project_root.rglob("__pycache__"):
        try:
            shutil.rmtree(cache_dir)
        except OSError:
            pass

    importlib.invalidate_caches()


# Add project root to Python path and set working directory
project_root = Path(__file__).parent.resolve()
_ensure_project_root_on_sys_path(project_root)
os.chdir(project_root)
_clear_import_caches_before_launcher_import(project_root)

# Import and run launcher
if __name__ == "__main__":
    from launcher import main

    sys.exit(main())
