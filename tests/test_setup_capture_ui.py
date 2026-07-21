"""Qt responsiveness tests for setup capture operations."""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtWidgets  # noqa: E402

from app.services.capture.setup_capture import SupervisedSetupCaptureService  # noqa: E402
from contracts.setup_capture import SetupCapturePurpose, SetupCaptureRequest  # noqa: E402
from ui.setup.setup_capture_controller import SetupCaptureOperation  # noqa: E402
from ui.setup.steps.paired_preview_step import PairedPreviewStep  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    yield app


def _spin(qapp, predicate, timeout: float = 2.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        qapp.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 20)
        if predicate():
            return True
        time.sleep(0.005)
    return bool(predicate())


def test_blocked_capture_keeps_qt_responsive_and_cancelable(qapp, tmp_path: Path) -> None:
    command = [sys.executable, "-c", "import sys,time; sys.stdin.read(); time.sleep(60)"]
    service = SupervisedSetupCaptureService(
        artifact_root=tmp_path / "jobs",
        worker_command=command,
    )
    request = SetupCaptureRequest(
        correlation_id="ui-blocked",
        purpose=SetupCapturePurpose.PREVIEW,
        left_camera_id="left",
        right_camera_id="right",
        config_path=Path("configs/default.yaml").resolve(),
        requested_frames_per_camera=1,
        overall_deadline_ms=5_000,
        backend="sim",
    )
    operation = SetupCaptureOperation(service, lambda: request, lambda result: result)
    step = PairedPreviewStep(operation=operation)
    cancelled = []
    operation.cancelled.connect(cancelled.append)

    step.on_enter()
    assert step.is_busy()
    assert not step._refresh_button.isEnabled()
    assert not step._cancel_button.isHidden()

    timer_fired: list[bool] = []
    QtCore.QTimer.singleShot(20, lambda: timer_fired.append(True))
    assert _spin(qapp, lambda: bool(timer_fired), timeout=0.5)
    assert step.is_busy()

    assert step.cancel_pending()
    assert _spin(qapp, lambda: not step.is_busy(), timeout=2.0)
    assert cancelled
    assert step._refresh_button.isEnabled()
    assert step._cancel_button.isHidden()
