"""Cold imports and direct setup use only the supported runtime surfaces."""

from pathlib import Path
import subprocess
import sys

from launcher_support import parse_args


def test_setup_option_preserves_backend_and_configuration():
    args = parse_args(["--setup", "--backend", "opencv", "--config", "rig.yaml"])
    assert args.setup and args.backend == "opencv" and args.config == Path("rig.yaml")


def test_cold_imports_do_not_load_retired_desktop_or_setup():
    code = """
import sys
import ui
from ui.setup.state_machine import SetupStateMachine
assert 'ui.main_window' not in sys.modules
assert 'ui.setup.setup_window' not in sys.modules
assert 'ui.setup.stereo_steps' not in sys.modules
assert 'app.pipeline_service' not in sys.modules
assert not any(name.startswith('PySide6') for name in sys.modules)
assert len(SetupStateMachine().steps) == 5
from ui.coaching import CoachWindow
from ui.review import ReviewWindow
from ui.setup import StereoSetupWindow
assert CoachWindow and ReviewWindow and StereoSetupWindow
assert not any(name.startswith('ui.controllers') for name in sys.modules)
"""
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=Path(__file__).parents[1],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_setup_launch_opens_the_canonical_workflow_without_background_validation(monkeypatch):
    import launcher
    from unittest.mock import patch
    import pytest

    opened = []

    class App:
        def __getattr__(self, name):
            return (lambda: 0) if name == "exec" else (lambda *args: None)

    class Window:
        def __init__(self, **kwargs):
            assert kwargs["background_tasks"] is False
            assert kwargs["backend"] == "sim"

        def show(self):
            pass

        def _launch_stereo_setup(self):
            opened.append("guided")
    monkeypatch.setattr(launcher, "LauncherWindow", Window)
    monkeypatch.setattr(launcher, "prepare_launcher_environment", lambda: None)
    monkeypatch.setattr(launcher, "create_required_directories", lambda: None)
    monkeypatch.setattr(launcher.get_style_manager(), "apply_to_app", lambda app: None)
    with patch.object(launcher.QtWidgets, "QApplication", lambda args: App()):
        with pytest.raises(SystemExit) as result:
            launcher.main(["--setup", "--backend", "sim"])
    assert result.value.code == 0 and opened == ["guided"]
