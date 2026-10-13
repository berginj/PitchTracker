"""Legacy calibration keeps Qt thread ownership until native completion."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import Mock

from PySide6 import QtCore

from ui.setup.setup_window import SetupWindow
from ui.setup.wizard_spec import WizardStep


def test_legacy_window_close_waits_for_running_calibration(qtbot, tmp_path, monkeypatch):
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/default.yaml").write_bytes(
        (Path(__file__).resolve().parents[1] / "configs/default.yaml").read_bytes()
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("ui.setup.steps.camera_step.CameraStep._refresh_devices", lambda self: None)
    started = threading.Event()
    release = threading.Event()
    result = Mock()

    class Tooling:
        def run_calibration(self, request):
            started.set()
            assert release.wait(2.0)
            return result

    monkeypatch.setattr("ui.setup.steps.calibration_worker.get_tooling_service", lambda: Tooling())
    window = SetupWindow("opencv")
    qtbot.addWidget(window)
    step = window._widget_by_step[WizardStep.CALIBRATION]
    step._captures = [(None, None)] * step._min_captures
    window.show()
    step._run_calibration()
    worker = step._calibration_worker
    assert started.wait(1.0)
    assert step.is_busy()
    window.close()
    assert window.isVisible()
    assert worker.isInterruptionRequested()
    # Result callbacks never mark a running QThread as safe to destroy.
    assert step.is_busy()
    release.set()
    qtbot.waitUntil(lambda: not window.isVisible(), timeout=3000)
    assert worker.wait(0)
    assert not step.is_busy()
    assert step._calibration_worker is None
    result.to_payload.assert_not_called()


def test_result_delivery_does_not_clear_busy_before_native_thread_finished(qtbot, tmp_path, monkeypatch):
    (tmp_path / "configs").mkdir()
    (tmp_path / "configs/default.yaml").write_bytes(
        (Path(__file__).resolve().parents[1] / "configs/default.yaml").read_bytes()
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("ui.setup.steps.camera_step.CameraStep._refresh_devices", lambda self: None)
    result_sent = threading.Event()
    release = threading.Event()

    class Worker(QtCore.QThread):
        result_ready = QtCore.Signal(dict)
        error = QtCore.Signal(dict)

        def __init__(self, *args, **kwargs):
            super().__init__()

        def run(self):
            self.result_ready.emit({})
            result_sent.set()
            release.wait(2.0)

    monkeypatch.setattr("ui.setup.steps.calibration_step_calibration_run.CalibrationWorker", Worker)
    window = SetupWindow("opencv")
    qtbot.addWidget(window)
    step = window._widget_by_step[WizardStep.CALIBRATION]
    step._captures = [(None, None)] * step._min_captures
    # The result content is irrelevant; observe thread ownership around its delivery.
    monkeypatch.setattr(step, "_on_calibration_complete", lambda result: None)
    step._run_calibration()
    assert result_sent.wait(1.0)
    qtbot.wait(10)
    assert step.is_busy()
    release.set()
    qtbot.waitUntil(lambda: not step.is_busy(), timeout=3000)
    assert step._calibration_worker is None
