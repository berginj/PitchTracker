"""Camera abstraction for pitch tracking capture backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

from contracts import Frame


@dataclass(frozen=True)
class CameraStats:
    fps_avg: float
    fps_instant: float
    jitter_p95_ms: float
    dropped_frames: int
    queue_depth: int
    capture_latency_ms: float


class CameraDevice(ABC):
    @abstractmethod
    def open(self, serial: str) -> None:
        """Open a camera by serial number."""

    @abstractmethod
    def set_mode(self, width: int, height: int, fps: int, pixfmt: str) -> None:
        """Configure resolution, frame rate, and pixel format."""

    @abstractmethod
    def set_controls(
        self,
        exposure_us: int,
        gain: float,
        wb_mode: Optional[str],
        wb: Optional[int],
    ) -> None:
        """Set manual controls for exposure, gain, and white balance."""

    @abstractmethod
    def read_frame(self, timeout_ms: int) -> Frame:
        """Read a frame or raise a timeout error."""

    @abstractmethod
    def get_stats(self) -> CameraStats:
        """Return capture diagnostics."""

    @abstractmethod
    def close(self) -> None:
        """Close the camera."""
