"""OpenCV-based camera backend."""

from __future__ import annotations

import logging
import time
import warnings
from dataclasses import dataclass
from typing import Optional

import cv2

from contracts import Frame
from exceptions import CameraConnectionError

from .camera_device import CameraDevice, CameraStats
from .timeout_utils import RetryPolicy, retry_on_failure, run_with_timeout

logger = logging.getLogger(__name__)


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
        self._flip_180 = False
        self._rotation_correction = 0.0  # Degrees to rotate for alignment correction

    @retry_on_failure(
        policy=RetryPolicy(
            max_attempts=3,
            base_delay=0.5,
            max_delay=2.0,
            retry_on=(CameraConnectionError, RuntimeError),
        )
    )
    def open(self, serial: str) -> None:
        """Open camera by index.

        Args:
            serial: Camera index as string (e.g., "0", "1")

        Raises:
            ValueError: If serial is not a valid index
            CameraConnectionError: If camera fails to open within timeout
            RuntimeError: If camera opens but reports not opened

        Note:
            - Uses 5 second timeout to prevent hanging
            - Retries up to 3 times with exponential backoff
            - Logs all attempts for debugging
        """
        # Ensure serial is a string (might be int from some code paths)
        serial_str = str(serial)
        self._serial = serial_str
        logger.info(f"Opening OpenCV camera index {serial_str}")

        if not serial_str.isdigit():
            logger.error(f"Invalid camera index: {serial_str}")
            raise ValueError(
                "OpenCVCamera only supports index-based devices. "
                "Use UvcCamera for serial-based selection."
            )

        warnings.warn(
            "OpenCVCamera is index-based and not stable for multi-camera rigs. "
            "Use UvcCamera with serials for production.",
            RuntimeWarning,
        )

        index = int(serial_str)

        def _open_camera():
            """Inner function for timeout wrapper."""
            capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            if not capture.isOpened():
                capture.release()
                raise CameraConnectionError(
                    f"Failed to open camera index {index} - camera may be in use or not found",
                    camera_id=serial,
                )
            return capture

        try:
            self._capture = run_with_timeout(
                _open_camera,
                timeout_seconds=5.0,
                error_message=f"OpenCV camera {index} open timed out",
            )
            logger.info(f"Successfully opened OpenCV camera index {serial}")

        except Exception as e:
            logger.error(f"Failed to open OpenCV camera index {serial}: {e}")
            self._capture = None
            raise

    def set_mode(self, width: int, height: int, fps: int, pixfmt: str, flip_180: bool = False, rotation_correction: float = 0.0) -> None:
        """Configure camera resolution, framerate, and pixel format.

        Args:
            width: Frame width in pixels
            height: Frame height in pixels
            fps: Target frames per second
            pixfmt: Pixel format ("GRAY8", "RGB24", etc.)
            flip_180: Rotate frame 180° (for upside-down camera mount)
            rotation_correction: Degrees to rotate for alignment correction (e.g., -3.7)

        Raises:
            RuntimeError: If camera not opened
        """
        if self._capture is None:
            logger.error(f"Cannot set_mode on camera {self._serial}: not opened")
            raise RuntimeError("Camera not opened.")

        logger.info(f"Camera {self._serial}: Configuring {width}x{height} @ {fps}fps ({pixfmt})")

        self._width = width
        self._height = height
        self._fps = fps
        self._pixfmt = pixfmt
        self._flip_180 = flip_180
        self._rotation_correction = rotation_correction

        self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self._capture.set(cv2.CAP_PROP_FPS, fps)

        # Force color mode if not GRAY8 (some cameras default to grayscale)
        if pixfmt != "GRAY8":
            # Set FOURCC to MJPG for color, or try to disable monochrome mode
            # Different cameras respond to different settings
            try:
                self._capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
            except Exception:
                pass  # Ignore if camera doesn't support this

            # Try to explicitly enable color (DirectShow specific)
            try:
                self._capture.set(cv2.CAP_PROP_MONOCHROME, 0)
            except Exception:
                pass  # Ignore if not supported

        # Verify settings were applied (DirectShow may silently ignore)
        actual_width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = int(self._capture.get(cv2.CAP_PROP_FPS))

        if actual_width != width or actual_height != height:
            logger.warning(
                f"Camera {self._serial}: Requested {width}x{height} but got {actual_width}x{actual_height}"
            )

        if actual_fps != fps:
            logger.warning(
                f"Camera {self._serial}: Requested {fps}fps but got {actual_fps}fps"
            )

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

        # Apply 180° rotation if camera mounted upside down
        if self._flip_180:
            frame = cv2.rotate(frame, cv2.ROTATE_180)

        # Apply rotation correction for alignment (if configured)
        if abs(self._rotation_correction) > 0.1:  # Only rotate if >0.1 degrees
            h, w = frame.shape[:2]
            center = (w // 2, h // 2)
            M = cv2.getRotationMatrix2D(center, self._rotation_correction, 1.0)
            frame = cv2.warpAffine(frame, M, (w, h))

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
        """Close camera and release resources.

        Note:
            - Idempotent - safe to call multiple times
            - Adds small delay to ensure DirectShow cleanup
            - Uses timeout to prevent hanging on release
        """
        if self._capture is None:
            logger.debug(f"Camera {self._serial}: Already closed")
            return

        logger.info(f"Camera {self._serial}: Closing")

        try:
            def _release():
                if self._capture is not None:
                    self._capture.release()

            # Release with timeout to prevent hanging
            run_with_timeout(
                _release,
                timeout_seconds=2.0,
                error_message=f"Camera {self._serial} release timed out",
            )

            # Small delay to ensure DirectShow cleanup completes
            time.sleep(0.1)

            logger.info(f"Camera {self._serial}: Closed successfully")

        except Exception as e:
            logger.error(f"Camera {self._serial}: Error during close: {e}")

        finally:
            # Always clear capture reference
            self._capture = None
