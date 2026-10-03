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
    _blocking_probe.started.set()
    _blocking_probe.event.wait(timeout=5.0)
    return [{"serial": "FAKE001", "friendly_name": "Fake Camera"}]


@requires_pytest_qt
def test_destroy_camera_step_during_discovery(qtbot: "QtBot") -> None:
    """Destroying CameraStep while discovery runs must not crash."""
    from ui.setup.steps.camera_step import CameraStep

    _blocking_probe.event = threading.Event()
    _blocking_probe.started = threading.Event()

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
        assert _blocking_probe.started.wait(1.0)

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


@requires_pytest_qt
def test_backend_switch_discards_queued_results_then_probes_new_backend(qtbot: "QtBot") -> None:
    from ui.setup.steps.camera_step import CameraStep

    started = threading.Event()
    release = threading.Event()

    def blocked(**kwargs):
        started.set()
        release.wait(2.0)
        return [{"serial": "stale", "friendly_name": "Old Camera"}]

    with (
        patch("ui.setup.steps.camera_discovery_worker.probe_uvc_devices", side_effect=blocked),
        patch("ui.setup.steps.camera_discovery_worker.probe_opencv_indices", return_value=[9]) as opencv,
    ):
        step = CameraStep("uvc")
        qtbot.addWidget(step)
        step._refresh_devices()
        assert started.wait(1.0)
        old = step._discovery_worker
        # Simulate a result queued just before the backend switch cancels it.
        producer = threading.Thread(
            target=lambda: old.signals.finished_signal.emit(
                [{"serial": "stale", "friendly_name": "Old Camera"}]
            )
        )
        producer.start()
        producer.join()
        step._switch_backend("opencv")
        release.set()
        qtbot.waitUntil(lambda: not step.is_busy(), timeout=3000)
        assert old.wait(0)
        opencv.assert_called_once()
        assert step._left_combo.count() == 2
        assert step._left_combo.itemText(1) == "Camera 9"
        step.on_exit()


@requires_pytest_qt
@pytest.mark.parametrize("closing", [False, True])
def test_exit_during_backend_switch_does_not_restart_discovery(qtbot: "QtBot", closing: bool) -> None:
    from ui.setup.steps.camera_step import CameraStep

    started = threading.Event()

    def blocked(**kwargs):
        started.set()
        assert kwargs["cancel_event"].wait(2.0)
        return []

    with (
        patch("ui.setup.steps.camera_discovery_worker.probe_uvc_devices", side_effect=blocked),
        patch("ui.setup.steps.camera_discovery_worker.probe_opencv_indices", return_value=[]) as opencv,
    ):
        step = CameraStep("uvc")
        qtbot.addWidget(step)
        step._refresh_devices()
        assert started.wait(1.0)
        step._switch_backend("opencv")
        if closing:
            step.cancel_pending()
        else:
            step.on_exit()
        qtbot.waitUntil(lambda: not step.is_busy(), timeout=3000)
        opencv.assert_not_called()
        if not closing:
            assert not step._preview_timer.isActive()
        assert step._left_combo.count() == 0
