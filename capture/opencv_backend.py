"""OpenCV-based camera backend."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

import cv2

from contracts import Frame

from .camera_device import CameraDevice, CameraStats


@dataclass
class _Stats:
    last_frame_ns: int = 0
    frames: int = 0
    dropped: int = 0
    fps_avg: float = 0.0
    fps_instant: float = 0.0


class OpenCVCamera(CameraDevice):
    def __init__(self) -> None:
        self._serial: Optional[str] = None
        self._capture: Optional[cv2.VideoCapture] = None
        self._stats = _Stats()
        self._width = 0
        self._height = 0
        self._fps = 0
        self._pixfmt = "GRAY8"

    def open(self, serial: str) -> None:
        self._serial = serial
        index = int(serial)
        self._capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not self._capture.isOpened():
            raise RuntimeError(f"Failed to open camera index {index}.")

    def set_mode(self, width: int, height: int, fps: int, pixfmt: str) -> None:
        if self._capture is None:
            raise RuntimeError("Camera not opened.")
        self._width = width
        self._height = height
        self._fps = fps
        self._pixfmt = pixfmt
        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._capture.set(cv2.CAP_PROP_FPS, fps)

    def set_controls(
        self,
        exposure_us: int,
        gain: float,
        wb_mode: Optional[str],
        wb: Optional[int],
    ) -> None:
        if self._capture is None:
            raise RuntimeError("Camera not opened.")
        if exposure_us > 0:
            self._capture.set(cv2.CAP_PROP_EXPOSURE, float(exposure_us) / 1_000_000.0)
        self._capture.set(cv2.CAP_PROP_GAIN, gain)
        if wb_mode is None:
            self._capture.set(cv2.CAP_PROP_AUTO_WB, 0)
            if wb is not None:
                self._capture.set(cv2.CAP_PROP_WB_TEMPERATURE, wb)

    def read_frame(self, timeout_ms: int) -> Frame:
        if self._capture is None:
            raise RuntimeError("Camera not opened.")
        ok, frame = self._capture.read()
        if not ok:
            self._stats.dropped += 1
            raise TimeoutError("Failed to read frame.")
        if self._pixfmt == "GRAY8":
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        now_ns = time.monotonic_ns()
        if self._stats.last_frame_ns:
            delta_s = (now_ns - self._stats.last_frame_ns) / 1e9
            if delta_s > 0:
                self._stats.fps_instant = 1.0 / delta_s
                self._stats.fps_avg = (
                    (self._stats.fps_avg * self._stats.frames) + self._stats.fps_instant
                ) / (self._stats.frames + 1)
        self._stats.frames += 1
        self._stats.last_frame_ns = now_ns
        return Frame(
            camera_id=self._serial or "0",
            frame_index=self._stats.frames,
            t_capture_monotonic_ns=now_ns,
            image=frame,
            width=frame.shape[1],
            height=frame.shape[0],
            pixfmt=self._pixfmt,
        )

    def get_stats(self) -> CameraStats:
        return CameraStats(
            fps_avg=self._stats.fps_avg,
            fps_instant=self._stats.fps_instant,
            jitter_p95_ms=0.0,
            dropped_frames=self._stats.dropped,
            queue_depth=0,
            capture_latency_ms=0.0,
        )

    def close(self) -> None:
        if self._capture is not None:
            self._capture.release()
            self._capture = None
