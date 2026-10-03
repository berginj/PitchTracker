"""Importing source launchers must leave caller state and bytecode alone."""

from pathlib import Path
import shutil
import subprocess
import sys

import pytest


@pytest.mark.parametrize("module", ["launch_app", "launcher"])
def test_import_preserves_cwd_sys_path_and_existing_cache(tmp_path: Path, module: str) -> None:
    root = Path(__file__).resolve().parents[1]
    copied_root = tmp_path / "source"
    copied_root.mkdir()
    shutil.copyfile(root / f"{module}.py", copied_root / f"{module}.py")
    cache = copied_root / "__pycache__"
    cache.mkdir()
    marker = cache / "existing.pyc"
    marker.write_bytes(b"existing bytecode")
    code = (
        "import os,sys,runpy; "
        f"sys.path.insert(0, {str(root)!r}); "
        "cwd=os.getcwd(); paths=list(sys.path); "
        f"runpy.run_path({str(copied_root / f'{module}.py')!r}, run_name='import_test'); "
        "assert os.getcwd() == cwd; assert sys.path == paths"
    )
    subprocess.run([sys.executable, "-c", code], cwd=tmp_path, check=True, capture_output=True, text=True)
    assert marker.read_bytes() == b"existing bytecode"
