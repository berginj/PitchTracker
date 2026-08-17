"""Background camera discovery used by the setup camera step."""

from __future__ import annotations

from PySide6 import QtCore

from ui.device_utils import (
    DEFAULT_OPENCV_MAX_INDEX,
    probe_opencv_indices,
    probe_uvc_devices,
)


class CameraDiscoverySignals(QtCore.QObject):
    """Signals emitted by a camera discovery worker."""

    finished_signal = QtCore.Signal(list)
    error_signal = QtCore.Signal(str)


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
        self.signals = CameraDiscoverySignals()

    def run(self) -> None:
        try:
            if self._backend == "opencv":
                devices: list[object] = list(
                    probe_opencv_indices(
                        max_index=DEFAULT_OPENCV_MAX_INDEX,
                        parallel=False,
                        use_cache=False,
                    )
                )
            else:
                devices = list(probe_uvc_devices())
        except Exception as exc:  # noqa: BLE001
            _safe_emit_error(self.signals, str(exc))
            return
        _safe_emit_finished(self.signals, devices or [])


__all__ = ["CameraDiscoveryWorker"]
