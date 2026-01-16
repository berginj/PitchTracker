"""Camera management for capture lifecycle and frame acquisition."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Callable, Optional, Tuple

from capture import CameraDevice, SimulatedCamera, UvcCamera
from capture.opencv_backend import OpenCVCamera
from configs.settings import AppConfig
from contracts import Frame
from exceptions import (
    CameraConfigurationError,
    CameraConnectionError,
    PitchTrackerError,
)

from .initialization import PipelineInitializer

logger = logging.getLogger(__name__)


class CameraManager:
    """Manages camera lifecycle, capture threads, and frame acquisition.

    Handles opening/closing cameras, configuring them, starting/stopping
    capture threads, and providing preview frames. Uses callback pattern
    to notify parent when frames are captured.
    """

    def __init__(self, backend: str, initializer: PipelineInitializer):
        """Initialize camera manager.

        Args:
            backend: Camera backend ("uvc", "opencv", or "sim")
            initializer: PipelineInitializer for camera configuration
        """
        self._backend = backend
        self._initializer = initializer

        # Camera instances
        self._left: Optional[CameraDevice] = None
        self._right: Optional[CameraDevice] = None
        self._left_id: Optional[str] = None
        self._right_id: Optional[str] = None

        # Capture threading
        self._capture_running = False
        self._left_thread: Optional[threading.Thread] = None
        self._right_thread: Optional[threading.Thread] = None

        # Latest frames for preview
        self._left_latest: Optional[Frame] = None
        self._right_latest: Optional[Frame] = None
        self._latest_lock = threading.Lock()

        # Callback for frame captured events
        self._on_frame_captured: Optional[Callable[[str, Frame], None]] = None

    def set_frame_callback(self, callback: Callable[[str, Frame], None]) -> None:
        """Set callback for frame captured events.

        Args:
            callback: Function to call when frame is captured, receives (label, frame)
        """
        self._on_frame_captured = callback

    def start_capture(
        self,
        config: AppConfig,
        left_serial: str,
        right_serial: str,
    ) -> None:
        """Start capture on both cameras.

        Opens cameras, configures them, and starts capture threads.

        Args:
            config: Application configuration
            left_serial: Left camera serial number
            right_serial: Right camera serial number

        Raises:
            CameraConnectionError: If cameras fail to open
            CameraConfigurationError: If camera configuration fails
        """
        logger.info(f"Starting capture with left={left_serial}, right={right_serial}")

        try:
            self._left_id = left_serial
            self._right_id = right_serial

            # Build camera objects
            try:
                self._left = self._build_camera()
                self._right = self._build_camera()
                logger.debug("Camera objects built successfully")
            except Exception as exc:
                logger.error(f"Failed to build camera objects: {exc}")
                raise CameraConnectionError(
                    f"Failed to initialize camera objects: {exc}"
                ) from exc

            # Open left camera
            try:
                logger.debug(f"Opening left camera: {left_serial}")
                self._left.open(left_serial)
            except Exception as exc:
                logger.error(f"Failed to open left camera {left_serial}: {exc}")
                raise CameraConnectionError(
                    f"Failed to open left camera {left_serial}: {exc}"
                ) from exc

            # Open right camera
            try:
                logger.debug(f"Opening right camera: {right_serial}")
                self._right.open(right_serial)
            except Exception as exc:
                logger.error(f"Failed to open right camera {right_serial}: {exc}")
                # Clean up left camera before raising
                try:
                    self._left.close()
                except Exception:
                    pass
                raise CameraConnectionError(
                    f"Failed to open right camera {right_serial}: {exc}"
                ) from exc

            # Configure cameras
            try:
                logger.debug("Configuring left camera")
                PipelineInitializer.configure_camera(self._left, config)
                logger.debug("Configuring right camera")
                PipelineInitializer.configure_camera(self._right, config)
            except Exception as exc:
                logger.error(f"Failed to configure cameras: {exc}")
                self._cleanup_cameras()
                raise CameraConfigurationError(
                    f"Failed to configure cameras: {exc}"
                ) from exc

            # Start capture threads
            try:
                logger.debug("Starting capture threads")
                self._start_capture_threads()
            except Exception as exc:
                logger.error(f"Failed to start capture threads: {exc}")
                self._cleanup_cameras()
                raise CameraConnectionError(
                    f"Failed to start capture threads: {exc}"
                ) from exc

            logger.info("Capture started successfully")

        except (CameraConnectionError, CameraConfigurationError):
            # Re-raise our custom exceptions
            raise
        except Exception as exc:
            # Catch any unexpected errors
            logger.exception("Unexpected error during capture start")
            self._cleanup_cameras()
            raise CameraConnectionError(
                f"Unexpected error starting capture: {exc}"
            ) from exc

    def stop_capture(self) -> None:
        """Stop capture on both cameras.

        Stops capture threads and closes cameras. Best-effort cleanup,
        does not raise exceptions.
        """
        logger.info("Stopping capture")

        try:
            self._capture_running = False

            # Stop capture threads
            if self._left_thread is not None:
                try:
                    self._left_thread.join(timeout=1.0)
                    if self._left_thread.is_alive():
                        logger.warning("Left capture thread did not stop within timeout")
                    self._left_thread = None
                except Exception as exc:
                    logger.warning(f"Error joining left capture thread: {exc}")

            if self._right_thread is not None:
                try:
                    self._right_thread.join(timeout=1.0)
                    if self._right_thread.is_alive():
                        logger.warning("Right capture thread did not stop within timeout")
                    self._right_thread = None
                except Exception as exc:
                    logger.warning(f"Error joining right capture thread: {exc}")

            # Close cameras
            if self._left is not None:
                try:
                    self._left.close()
                    logger.debug("Left camera closed")
                except Exception as exc:
                    logger.error(f"Error closing left camera: {exc}")
                finally:
                    self._left = None

            if self._right is not None:
                try:
                    self._right.close()
                    logger.debug("Right camera closed")
                except Exception as exc:
                    logger.error(f"Error closing right camera: {exc}")
                finally:
                    self._right = None

            logger.info("Capture stopped successfully")

        except Exception as exc:
            logger.exception("Unexpected error during capture stop")
            # Don't raise - we want stop to be best-effort cleanup

    def get_preview_frames(self) -> Tuple[Frame, Frame]:
        """Get latest preview frames from both cameras.

        Returns:
            Tuple of (left_frame, right_frame)

        Raises:
            CameraConnectionError: If capture is not started
            PitchTrackerError: If frames are not yet available
        """
        if self._left is None or self._right is None:
            logger.error("Attempted to get preview frames but capture not started")
            raise CameraConnectionError(
                "Capture not started. Call start_capture() first."
            )

        try:
            with self._latest_lock:
                left_frame = self._left_latest
                right_frame = self._right_latest
        except Exception as exc:
            logger.error(f"Error accessing preview frames: {exc}")
            raise PitchTrackerError(
                f"Error accessing frame buffer: {exc}"
            ) from exc

        if left_frame is None or right_frame is None:
            # This is normal during startup - cameras haven't produced frames yet
            raise PitchTrackerError("Waiting for first camera frames. Please wait...")

        return left_frame, right_frame

    def get_stats(self):
        """Get camera statistics.

        Returns:
            Dictionary with left/right camera stats, or empty dict if not capturing
        """
        if self._left is None or self._right is None:
            return {}

        from .utils import stats_to_dict

        return {
            "left": stats_to_dict(self._left.get_stats()),
            "right": stats_to_dict(self._right.get_stats()),
        }

    def is_capturing(self) -> bool:
        """Check if capture is currently running.

        Returns:
            True if capture is running, False otherwise
        """
        return self._capture_running

    def get_camera_ids(self) -> Tuple[Optional[str], Optional[str]]:
        """Get current camera serial numbers.

        Returns:
            Tuple of (left_id, right_id)
        """
        return self._left_id, self._right_id

    def _build_camera(self) -> CameraDevice:
        """Build camera instance based on backend.

        Returns:
            CameraDevice instance
        """
        if self._backend == "opencv":
            return OpenCVCamera()
        if self._backend == "sim":
            return SimulatedCamera()
        return UvcCamera()

    def _start_capture_threads(self) -> None:
        """Start capture threads for both cameras."""
        if self._left is None or self._right is None:
            return

        self._capture_running = True
        self._left_thread = threading.Thread(
            target=self._capture_loop,
            args=("left", self._left),
            daemon=True,
        )
        self._right_thread = threading.Thread(
            target=self._capture_loop,
            args=("right", self._right),
            daemon=True,
        )
        self._left_thread.start()
        self._right_thread.start()

    def _capture_loop(self, label: str, camera: CameraDevice) -> None:
        """Main capture loop for a camera.

        Continuously reads frames from camera and:
        1. Updates latest frame for preview
        2. Calls frame callback if set

        Args:
            label: Camera label ("left" or "right")
            camera: Camera device to read from
        """
        while self._capture_running:
            try:
                frame = camera.read_frame(timeout_ms=200)
            except Exception:
                continue

            # Update latest frame for preview
            with self._latest_lock:
                if label == "left":
                    self._left_latest = frame
                else:
                    self._right_latest = frame

            # Notify parent via callback
            if self._on_frame_captured:
                self._on_frame_captured(label, frame)

    def _cleanup_cameras(self) -> None:
        """Clean up camera resources on error."""
        try:
            if self._left is not None:
                self._left.close()
                self._left = None
        except Exception as exc:
            logger.warning(f"Error closing left camera during cleanup: {exc}")

        try:
            if self._right is not None:
                self._right.close()
                self._right = None
        except Exception as exc:
            logger.warning(f"Error closing right camera during cleanup: {exc}")
