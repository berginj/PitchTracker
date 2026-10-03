"""Discovery cancellation must reap children and leave reusable state."""

from __future__ import annotations

import subprocess
import threading
from unittest.mock import Mock, patch

import pytest

from capture import device_discovery
from ui import device_utils
from ui.setup.steps.camera_discovery_worker import CameraDiscoveryWorker


@pytest.mark.parametrize("kind", ["pnp", "opencv"])
def test_cancel_interrupts_and_reaps_active_discovery_child(kind):
    cancel = threading.Event()
    process = Mock()
    process.poll.return_value = None

    def blocked(*args, **kwargs):
        cancel.set()
        raise subprocess.TimeoutExpired("discovery", 0.05)

    if kind == "pnp":
        calls = []

        def communicate(**kwargs):
            calls.append(kwargs)
            if kwargs:
                return blocked()
            return "", ""

        process.communicate.side_effect = communicate
        with patch("capture.device_discovery.subprocess.Popen", return_value=process) as popen:
            assert device_discovery.list_uvc_devices(cancel) == []
        assert popen.call_count == 1  # No Image fallback after cancellation.
        assert len(calls) == 2
    else:
        def wait(**kwargs):
            if kwargs:
                return blocked()
            return -1

        process.wait.side_effect = wait
        with patch("ui.device_utils.subprocess.Popen", return_value=process):
            assert device_utils._probe_single_index(0, cancel_event=cancel) is None
        assert process.wait.call_count == 2
    process.kill.assert_called_once_with()


@pytest.mark.parametrize("kind", ["pnp", "opencv"])
def test_precancelled_discovery_never_launches_children(kind):
    cancel = threading.Event()
    cancel.set()
    with patch("subprocess.Popen") as popen:
        if kind == "pnp":
            assert device_discovery.list_uvc_devices(cancel) == []
        else:
            assert device_utils.probe_opencv_indices(cancel_event=cancel) == []
        popen.assert_not_called()


@pytest.mark.parametrize("kind", ["uvc", "opencv"])
def test_cancelled_discovery_does_not_replace_cached_results(kind):
    device_utils.clear_device_cache()
    cancel = threading.Event()
    if kind == "uvc":
        target = "ui.device_utils.list_uvc_devices"
        probe = device_utils.probe_uvc_devices
        expected = [{"serial": "real", "friendly_name": "Camera"}]
    else:
        target = "ui.device_utils._probe_single_index"
        probe = device_utils.probe_opencv_indices
        expected = [0]

    def cancelled(*args, **kwargs):
        cancel.set()
        return [] if kind == "uvc" else None

    options = {} if kind == "uvc" else {"max_index": 1}
    with patch(target, side_effect=cancelled):
        assert probe(cancel_event=cancel, **options) == []
    with patch(target, return_value=expected if kind == "uvc" else 0) as fresh:
        assert probe(**options) == expected
        fresh.assert_called_once()
    device_utils.clear_device_cache()


def test_worker_cancel_suppresses_results_and_errors_but_reports_terminal_state():
    worker = CameraDiscoveryWorker("uvc")
    devices = []
    errors = []
    terminal = []
    worker.signals.finished_signal.connect(devices.append)
    worker.signals.error_signal.connect(errors.append)
    worker.signals.terminal_signal.connect(lambda: terminal.append(True))

    def probe(**kwargs):
        worker.cancel()
        return [{"serial": "stale", "friendly_name": "Camera"}]

    with patch("ui.setup.steps.camera_discovery_worker.probe_uvc_devices", side_effect=probe):
        worker.run()
    assert worker.wait(0)
    assert not devices
    assert not errors
    assert terminal == [True]
