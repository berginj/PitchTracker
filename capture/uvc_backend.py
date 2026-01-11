"""UVC capture backend placeholder."""

from __future__ import annotations

from typing import Optional

from contracts import Frame

from .camera_device import CameraDevice, CameraStats


class UvcCamera(CameraDevice):
    def __init__(self) -> None:
        self._serial: Optional[str] = None

    def open(self, serial: str) -> None:
        self._serial = serial
        raise NotImplementedError("UVC backend not implemented yet.")

    def set_mode(self, width: int, height: int, fps: int, pixfmt: str) -> None:
        raise NotImplementedError("UVC backend not implemented yet.")

    def set_controls(
        self,
        exposure_us: int,
        gain: float,
        wb_mode: Optional[str],
        wb: Optional[int],
    ) -> None:
        raise NotImplementedError("UVC backend not implemented yet.")

    def read_frame(self, timeout_ms: int) -> Frame:
        raise NotImplementedError("UVC backend not implemented yet.")

    def get_stats(self) -> CameraStats:
        raise NotImplementedError("UVC backend not implemented yet.")

    def close(self) -> None:
        raise NotImplementedError("UVC backend not implemented yet.")
