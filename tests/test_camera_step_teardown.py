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
from unittest.mock import patch

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


def _blocking_probe(_use_cache=False, cancel_event=None, **_kw):
    """Fake probe that blocks until the worker requests cancellation."""
    _blocking_probe.started.set()
    if cancel_event is not None:
        cancel_event.wait(timeout=5.0)
        _blocking_probe.cancelled.set()
    return [{"serial": "FAKE001", "friendly_name": "Fake Camera"}]


@requires_pytest_qt
def test_destroy_camera_step_during_discovery(qtbot: "QtBot") -> None:
    """Destroying CameraStep while discovery runs must not crash."""
    from ui.setup.steps.camera_step import CameraStep

    _blocking_probe.started = threading.Event()
    _blocking_probe.cancelled = threading.Event()

    with patch(
        "ui.setup.camera_discovery_worker.probe_uvc_devices",
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
        assert _blocking_probe.started.wait(timeout=1.0)

    step.close()
    QtWidgets.QApplication.processEvents()
    assert _blocking_probe.cancelled.wait(timeout=1.0)
    assert step._discovery_worker is None

    # Destroy the widget after its owned worker has stopped.
    step.deleteLater()
    QtWidgets.QApplication.processEvents()

    assert QtCore.QThreadPool.globalInstance().waitForDone(3000)
    QtWidgets.QApplication.processEvents()


@requires_pytest_qt
def test_backend_switch_cancels_active_discovery(qtbot: "QtBot") -> None:
    """Switching backend cancels and awaits the previous discovery."""
    from ui.setup.steps.camera_step import CameraStep

    _blocking_probe.started = threading.Event()
    _blocking_probe.cancelled = threading.Event()

    with patch(
        "ui.setup.camera_discovery_worker.probe_uvc_devices",
        side_effect=_blocking_probe,
    ):
        step = CameraStep(backend="uvc")
        qtbot.addWidget(step)
        step._refresh_devices()
        assert _blocking_probe.started.wait(timeout=1.0)

        step._switch_backend("opencv")

    assert _blocking_probe.cancelled.wait(timeout=1.0)
    assert step._discovery_worker is None


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
