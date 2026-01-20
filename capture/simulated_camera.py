"""Simulated camera backend for pipeline testing."""

from __future__ import annotations

import time
from typing import Optional

import numpy as np

from contracts import Frame

from .camera_device import CameraDevice, CameraStats


class SimulatedCamera(CameraDevice):
    def __init__(self) -> None:
        self._serial: Optional[str] = None
        self._width = 0
        self._height = 0
        self._fps = 0
        self._pixfmt = "GRAY8"
        self._frame_index = 0
        self._last_frame_time = time.monotonic()

    def open(self, serial: str) -> None:
        self._serial = serial

    def set_mode(self, width: int, height: int, fps: int, pixfmt: str) -> None:
        self._width = width
        self._height = height
        self._fps = fps
        self._pixfmt = pixfmt

    def set_controls(
        self,
        exposure_us: int,
        gain: float,
        wb_mode: Optional[str],
        wb: Optional[int],
    ) -> None:
        return None

    def read_frame(self, timeout_ms: int) -> Frame:
        if self._fps > 0:
            target_delay = 1.0 / self._fps
            now = time.monotonic()
            elapsed = now - self._last_frame_time
            if elapsed < target_delay:
                time.sleep(target_delay - elapsed)
        self._last_frame_time = time.monotonic()
        self._frame_index += 1

        # Generate image based on pixel format
        if self._pixfmt == "GRAY8":
            # Grayscale: 2D array (height, width)
            image = np.zeros((self._height, self._width), dtype=np.uint8)
        elif self._pixfmt in ("YUYV", "MJPG"):
            # Color formats: 3D array (height, width, 3) in BGR format
            # Generate a simple color pattern for testing (dark blue-gray)
            image = np.zeros((self._height, self._width, 3), dtype=np.uint8)
            image[:, :, 0] = 40  # Blue channel
            image[:, :, 1] = 30  # Green channel
            image[:, :, 2] = 20  # Red channel
        else:
            # Unknown format, default to grayscale
            image = np.zeros((self._height, self._width), dtype=np.uint8)

        return Frame(
            camera_id=self._serial or "sim",
            frame_index=self._frame_index,
            t_capture_monotonic_ns=time.monotonic_ns(),
            image=image,
            width=self._width,
            height=self._height,
            pixfmt=self._pixfmt,
        )

    def get_stats(self) -> CameraStats:
        return CameraStats(
            fps_avg=float(self._fps),
            fps_instant=float(self._fps),
            jitter_p95_ms=0.0,
            dropped_frames=0,
            queue_depth=0,
            capture_latency_ms=0.0,
        )

    def close(self) -> None:
        return None
