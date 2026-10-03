"""Frozen state lives outside installed resources and preserves legacy evidence."""

import os
from pathlib import Path
import subprocess
import sys

import pytest

from app import runtime_paths


def _frozen_paths(monkeypatch, tmp_path):
    install = tmp_path / "install"
    resources = install / "_internal"
    defaults = resources / "defaults" / "configs"
    defaults.mkdir(parents=True)
    for name in runtime_paths.DEFAULT_CONFIGS:
        (defaults / name).write_text(f"bundled-{name}")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(resources), raising=False)
    monkeypatch.setattr(sys, "executable", str(install / "PitchTracker.exe"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user"))
    monkeypatch.delenv("PITCHTRACKER_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    return install, resources, tmp_path / "user" / "PitchTracker"


def test_frozen_bootstrap_migrates_without_overwrite_or_path_rewrites(monkeypatch, tmp_path):
    install, resources, state = _frozen_paths(monkeypatch, tmp_path)
    legacy = resources / "configs"
    legacy.mkdir()
    custom = 'recording:\n  output_dir: "D:/operator-selected/session-data"\n'
    (legacy / "default.yaml").write_text(custom)
    (install / "calibration").mkdir()
    (install / "calibration" / "rig.npz").write_bytes(b"private calibration")
    (install / "recordings").mkdir()
    (install / "recordings" / "pitch.bin").write_bytes(b"private recording")
    runtime_paths.prepare_frozen_runtime()
    assert Path.cwd() == state
    assert (state / "configs" / "default.yaml").read_text() == custom
    assert (state / "configs" / "snapdragon.yaml").read_text() == "bundled-snapdragon.yaml"
    assert (state / "calibration" / "rig.npz").read_bytes() == b"private calibration"
    assert (state / "recordings" / "pitch.bin").read_bytes() == b"private recording"
    assert (legacy / "default.yaml").read_text() == custom
    assert (install / "recordings" / "pitch.bin").exists()
    # Upgraded resource defaults and stale legacy files must not override state.
    (resources / "defaults" / "configs" / "default.yaml").write_text("new default")
    (legacy / "default.yaml").write_text("stale legacy")
    runtime_paths.prepare_frozen_runtime()
    assert (state / "configs" / "default.yaml").read_text() == custom


def test_explicit_state_is_isolated_from_legacy_operator_files(monkeypatch, tmp_path):
    install, _resources, _state = _frozen_paths(monkeypatch, tmp_path)
    legacy = install / "configs"
    legacy.mkdir()
    (legacy / "private-athletes.json").write_text("private")
    selected = tmp_path / "isolated"
    monkeypatch.setenv("PITCHTRACKER_DATA_DIR", str(selected))
    runtime_paths.prepare_frozen_runtime()
    assert Path.cwd() == selected
    assert not (selected / "configs" / "private-athletes.json").exists()


def test_source_bootstrap_keeps_caller_cwd_and_creates_no_state(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PITCHTRACKER_DATA_DIR", str(tmp_path / "ignored"))
    runtime_paths.prepare_frozen_runtime()
    assert Path.cwd() == tmp_path
    assert runtime_paths.state_root() == tmp_path
    assert not (tmp_path / "ignored").exists()


def test_state_inside_installation_or_relative_override_is_rejected(monkeypatch, tmp_path):
    install, _resources, _state = _frozen_paths(monkeypatch, tmp_path)
    for selected in (str(install / "runtime"), "relative"):
        monkeypatch.setenv("PITCHTRACKER_DATA_DIR", selected)
        with pytest.raises(ValueError):
            runtime_paths.prepare_frozen_runtime()
    assert not (install / "runtime").exists()


def test_migration_does_not_follow_foreign_symlink(monkeypatch, tmp_path):
    install, _resources, state = _frozen_paths(monkeypatch, tmp_path)
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "private.txt").write_text("private")
    try:
        (install / "data").symlink_to(foreign, target_is_directory=True)
    except OSError:
        pytest.skip("Creating a Windows symlink requires operator privileges")
    runtime_paths.prepare_frozen_runtime()
    assert not (state / "data" / "private.txt").exists()


def test_frozen_logging_import_uses_state_before_launcher_import(tmp_path):
    root = Path(__file__).resolve().parents[1]
    install = tmp_path / "install"
    resources = install / "_internal"
    defaults = resources / "defaults" / "configs"
    defaults.mkdir(parents=True)
    for name in runtime_paths.DEFAULT_CONFIGS:
        (defaults / name).write_text("default")
    state = tmp_path / "writable"
    code = (
        "import sys,os; "
        f"sys.path.insert(0,{str(root)!r}); sys.frozen=True; sys._MEIPASS={str(resources)!r}; "
        f"sys.executable={str(install / 'PitchTracker.exe')!r}; "
        "from app.runtime_paths import prepare_frozen_runtime; prepare_frozen_runtime(); "
        "from log_config.logger import logs_dir; from updater import UPDATE_SETTINGS_PATH; "
        f"assert str(logs_dir)=={str(state / 'logs')!r}; "
        f"assert str(UPDATE_SETTINGS_PATH)=={str(state / 'configs' / 'update_settings.json')!r}"
    )
    environment = dict(os.environ, PITCHTRACKER_DATA_DIR=str(state))
    subprocess.run([sys.executable, "-c", code], cwd=tmp_path, env=environment, check=True,
                   capture_output=True, text=True)
    assert not (install / "logs").exists()
