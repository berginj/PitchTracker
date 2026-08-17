"""Simulated camera backend for pipeline testing."""

from __future__ import annotations

import time
from typing import Any, Optional

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
        self._flip_180 = False
        self._rotation_correction = 0.0
        self._vertical_offset_px = 0
        self._frame_index = 0
        self._last_frame_time = time.monotonic()
        self._controls: dict[str, Any] = {
            "exposure_us": 0,
            "gain": 0.0,
            "wb_mode": None,
            "wb": None,
        }

    def open(self, serial: str) -> None:
        self._serial = serial

    def set_mode(
        self,
        width: int,
        height: int,
        fps: int,
        pixfmt: str,
        flip_180: bool = False,
        rotation_correction: float = 0.0,
        vertical_offset_px: int = 0,
    ) -> None:
        self._width = width
        self._height = height
        self._fps = fps
        self._pixfmt = pixfmt
        self._flip_180 = flip_180
        self._rotation_correction = rotation_correction
        self._vertical_offset_px = vertical_offset_px

    def set_controls(
        self,
        exposure_us: int,
        gain: float,
        wb_mode: Optional[str],
        wb: Optional[int],
    ) -> None:
        self._controls = {
            "exposure_us": exposure_us,
            "gain": gain,
            "wb_mode": wb_mode,
            "wb": wb,
            "auto_exposure_disabled": True,
            "auto_white_balance_disabled": wb_mode is None,
            "autofocus_disabled": True,
            "readback_verified": True,
        }

    def get_mode(self):
        return {"width": self._width, "height": self._height, "fps": self._fps, "pixfmt": self._pixfmt}

    def get_controls(self):
        return dict(self._controls)

    def get_capability_observation(self):
        if self._serial is None:
            return None
        from contracts.capability_observation import build_simulated_observation

        return build_simulated_observation(
            camera_id=self._serial or "sim",
            requested_mode={
                "width": self._width,
                "height": self._height,
                "fps": self._fps,
                "pixfmt": self._pixfmt,
            },
            controls=self._controls,
        )

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
            image: np.ndarray = np.zeros((self._height, self._width), dtype=np.uint8)
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

        # Apply 180° rotation if camera mounted upside down
        if self._flip_180:
            import cv2

            image = cv2.rotate(image, cv2.ROTATE_180)

        if abs(self._rotation_correction) > 0.1 or self._vertical_offset_px:
            import cv2

            h, w = image.shape[:2]
            if abs(self._rotation_correction) > 0.1:
                center = (w // 2, h // 2)
                matrix = cv2.getRotationMatrix2D(center, self._rotation_correction, 1.0)
                image = cv2.warpAffine(image, matrix, (w, h))
            if self._vertical_offset_px:
                matrix = np.asarray(
                    [[1, 0, 0], [0, 1, -self._vertical_offset_px]], dtype=np.float32
                )
                image = cv2.warpAffine(image, matrix, (w, h))

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
