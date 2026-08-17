"""Cancelable background worker for setup camera discovery."""

from __future__ import annotations

import threading

from PySide6 import QtCore

from ui.device_utils import DEFAULT_OPENCV_MAX_INDEX, probe_opencv_indices, probe_uvc_devices


class CameraDiscoverySignals(QtCore.QObject):
    """Signals emitted by a camera discovery worker."""

    finished_signal = QtCore.Signal(list)
    error_signal = QtCore.Signal(str)


def _safe_emit_finished(signals: CameraDiscoverySignals, devices: list) -> None:
    """Emit a result unless Qt already deleted the receiver."""
    try:
        signals.finished_signal.emit(devices)
    except RuntimeError:
        pass


def _safe_emit_error(signals: CameraDiscoverySignals, message: str) -> None:
    """Emit an error unless Qt already deleted the receiver."""
    try:
        signals.error_signal.emit(message)
    except RuntimeError:
        pass


class CameraDiscoveryWorker(QtCore.QRunnable):
    """Probe camera devices with explicit cancellation and completion."""

    def __init__(self, backend: str):
        super().__init__()
        self._backend = backend
        self._cancel_event = threading.Event()
        self._finished_event = threading.Event()
        self.signals = CameraDiscoverySignals()

    def cancel(self) -> None:
        """Request cancellation of the active discovery operation."""
        self._cancel_event.set()

    def wait(self, timeout_seconds: float) -> bool:
        """Wait for the discovery operation to finish."""
        return self._finished_event.wait(timeout_seconds)

    def run(self) -> None:
        try:
            devices = self._discover()
        except Exception as exc:  # noqa: BLE001
            if not self._cancel_event.is_set():
                _safe_emit_error(self.signals, str(exc))
        else:
            if not self._cancel_event.is_set():
                _safe_emit_finished(self.signals, devices or [])
        finally:
            self._finished_event.set()

    def _discover(self) -> list:
        if self._backend == "opencv":
            return probe_opencv_indices(
                max_index=DEFAULT_OPENCV_MAX_INDEX,
                parallel=False,
                use_cache=False,
                cancel_event=self._cancel_event,
            )
        return probe_uvc_devices(cancel_event=self._cancel_event)
