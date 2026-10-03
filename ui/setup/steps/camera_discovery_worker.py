"""Background camera discovery used by the setup camera step."""

from __future__ import annotations

import threading

from PySide6 import QtCore

from log_config.logger import get_logger

from ui.device_utils import (
    DEFAULT_OPENCV_MAX_INDEX,
    probe_opencv_indices,
    probe_uvc_devices,
)


logger = get_logger(__name__)


class CameraDiscoverySignals(QtCore.QObject):
    """Signals emitted by a camera discovery worker."""

    finished_signal = QtCore.Signal(list)
    error_signal = QtCore.Signal(str)
    terminal_signal = QtCore.Signal()


def _safe_emit_finished(signals: CameraDiscoverySignals, devices: list[object]) -> None:
    try:
        signals.finished_signal.emit(devices)
    except RuntimeError:
        pass


def _safe_emit_error(signals: CameraDiscoverySignals, message: str) -> None:
    try:
        signals.error_signal.emit(message)
    except RuntimeError:
        pass


class CameraDiscoveryWorker(QtCore.QRunnable):
    """Probe USB/UVC devices on the application thread pool."""

    def __init__(self, backend: str):
        super().__init__()
        self._backend = backend
        self._cancel_event = threading.Event()
        self._done_event = threading.Event()
        self.signals = CameraDiscoverySignals()

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def wait(self, timeout_seconds: float | None = None) -> bool:
        return self._done_event.wait(timeout_seconds)

    def run(self) -> None:
        try:
            if self.is_cancelled():
                return
            if self._backend == "opencv":
                devices: list[object] = list(
                    probe_opencv_indices(
                        max_index=DEFAULT_OPENCV_MAX_INDEX,
                        parallel=False,
                        use_cache=False,
                        cancel_event=self._cancel_event,
                    )
                )
            else:
                devices = list(probe_uvc_devices(use_cache=False, cancel_event=self._cancel_event))
            if not self.is_cancelled():
                _safe_emit_finished(self.signals, devices or [])
        except Exception as exc:  # noqa: BLE001
            logger.exception("Camera discovery failed for backend {}", self._backend)
            if not self.is_cancelled():
                _safe_emit_error(self.signals, str(exc))
        finally:
            self._done_event.set()
            try:
                self.signals.terminal_signal.emit()
            except RuntimeError:
                # The owner may already have been destroyed; no UI remains to notify.
                pass


__all__ = ["CameraDiscoveryWorker"]
