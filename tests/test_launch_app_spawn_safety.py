"""Regression tests for Windows multiprocessing entry-point safety."""

from __future__ import annotations

import importlib.util
import shutil


def test_launch_app_import_has_no_filesystem_side_effects(tmp_path):
    """Spawn-style imports must not clear caches or change directories."""
    source = __import__("launch_app").__file__
    copied_launcher = tmp_path / "launch_app.py"
    shutil.copyfile(source, copied_launcher)

    cache_dir = tmp_path / "__pycache__"
    cache_dir.mkdir()
    marker = cache_dir / "marker.pyc"
    marker.write_bytes(b"test")

    spec = importlib.util.spec_from_file_location("__mp_main__", copied_launcher)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    assert marker.exists()
