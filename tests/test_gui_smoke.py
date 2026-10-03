"""Explicit source/frozen GUI smoke without physical capture or update network."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


def _smoke(executable: Path, tmp_path: Path, *, source: bool):
    report = tmp_path / "smoke.json"
    root = Path(__file__).resolve().parents[1]
    command = [str(executable)]
    if source:
        command.append(str(root / "launcher.py"))
    command += ["--gui-smoke-report", str(report)]
    environment = dict(os.environ, QT_QPA_PLATFORM="offscreen", PITCHTRACKER_DATA_DIR=str(tmp_path / "state"))
    result = subprocess.run(command, cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=60)
    payload = json.loads(report.read_text()) if report.exists() else {}
    assert result.returncode == 0, f"{payload}\n{result.stderr or result.stdout}"
    assert payload["ok"], payload
    assert payload["backend"] == "sim"
    assert payload["workflows"] == ["LauncherWindow", "CoachWindow", "StereoSetupWindow", "ReviewWindow"]


def test_source_gui_workflows_render_and_close(tmp_path):
    _smoke(Path(sys.executable), tmp_path, source=True)


def test_frozen_gui_workflows_render_and_close(tmp_path):
    directory = os.environ.get("PITCHTRACKER_PACKAGED_DIR")
    if not directory:
        pytest.skip("Set PITCHTRACKER_PACKAGED_DIR for GUI artifact qualification")
    executable = Path(directory).resolve() / "PitchTracker.exe"
    assert executable.is_file()
    _smoke(executable, tmp_path, source=False)
