"""Test CameraStep teardown race with CameraDiscoveryWorker.

Verifies that destroying a CameraStep (or its parent window) while a
CameraDiscoveryWorker is still running on the thread pool does not crash
via RuntimeError from emitting through a deleted QObject.

Also verifies CameraStep cleanup stops the preview timer and cameras.
"""

from __future__ import annotations

import importlib.util
import os
import threading
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from PySide6 import QtCore, QtWidgets

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot  # noqa: F401

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_PYTEST_QT = importlib.util.find_spec("pytestqt") is not None

requires_pytest_qt = pytest.mark.skipif(
    not HAS_PYTEST_QT,
    reason="pytest-qt not installed",
)


def _blocking_probe(_use_cache=False, **_kw):
    """Fake probe that blocks until released."""
    # Wait up to 5s for release event (set by test)
    _blocking_probe.event.wait(timeout=5.0)
    return [{"serial": "FAKE001", "friendly_name": "Fake Camera"}]


@requires_pytest_qt
def test_destroy_camera_step_during_discovery(qtbot: "QtBot") -> None:
    """Destroying CameraStep while discovery runs must not crash."""
    from ui.setup.steps.camera_step import CameraStep

    _blocking_probe.event = threading.Event()

    with patch(
        "ui.setup.steps.camera_discovery_worker.probe_uvc_devices",
        side_effect=_blocking_probe,
    ):
        step = CameraStep(backend="uvc")
        qtbot.addWidget(step)
        step.show()
        qtbot.waitExposed(step)

        # Trigger discovery (worker now blocked)
        step._refresh_devices()

        # Ensure worker is actually scheduled
        QtWidgets.QApplication.processEvents()

    # Destroy the widget while worker is still blocked
    step.close()
    step.deleteLater()
    QtWidgets.QApplication.processEvents()

    # Release the worker — emit will encounter deleted signals object
    _blocking_probe.event.set()

    # Drain the global thread pool so the worker finishes
    QtCore.QThreadPool.globalInstance().waitForDone(3000)

    # Process any pending signals — must not crash
    QtWidgets.QApplication.processEvents()


@requires_pytest_qt
def test_camera_step_cleanup_stops_timer(qtbot: "QtBot") -> None:
    """CameraStep._stop_resources stops preview timer."""
    from ui.setup.steps.camera_step import CameraStep

    step = CameraStep(backend="opencv")
    qtbot.addWidget(step)

    assert step._preview_timer is not None
    assert step._preview_timer.isActive()

    step._stop_resources()

    assert not step._preview_timer.isActive()


@requires_pytest_qt
def test_camera_step_on_exit_stops_timer(qtbot: "QtBot") -> None:
    """CameraStep.on_exit stops preview timer and cameras."""
    from ui.setup.steps.camera_step import CameraStep

    step = CameraStep(backend="opencv")
    qtbot.addWidget(step)

    assert step._preview_timer.isActive()

    step.on_exit()

    assert not step._preview_timer.isActive()


@requires_pytest_qt
def test_camera_step_on_enter_reopens_selected_cameras(qtbot: "QtBot") -> None:
    """Back navigation restarts preview without discarding camera selection."""
    from ui.setup.steps.camera_step import CameraStep

    step = CameraStep(backend="opencv")
    qtbot.addWidget(step)
    step._left_serial = "left-selected"
    step._right_serial = "right-selected"
    step._left_camera = MagicMock()
    step._right_camera = MagicMock()

    step.on_exit()

    assert not step._preview_timer.isActive()
    assert step._left_camera is None
    assert step._right_camera is None
    with (
        patch.object(step, "_open_left_camera") as open_left,
        patch.object(step, "_open_right_camera") as open_right,
        patch.object(step, "_refresh_devices"),
    ):
        step.on_enter()

    assert step._preview_timer.isActive()
    assert step._left_serial == "left-selected"
    assert step._right_serial == "right-selected"
    open_left.assert_called_once_with()
    open_right.assert_called_once_with()
