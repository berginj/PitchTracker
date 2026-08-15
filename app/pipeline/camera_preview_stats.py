"""Camera preview frame state and statistics."""

from __future__ import annotations

import logging
import threading
from typing import Optional, Tuple

from contracts import Frame
from exceptions import CameraConnectionError, PitchTrackerError

logger = logging.getLogger(__name__)


class CameraPreviewStats:
    """Thread-safe storage for latest preview frames and camera statistics."""

    def __init__(self) -> None:
        """Initialize preview state."""
        self._left_latest: Optional[Frame] = None
        self._right_latest: Optional[Frame] = None
        self._latest_lock = threading.Lock()

    def update_frame(self, label: str, frame: Frame) -> None:
        """Update latest preview frame for a camera.

        Args:
            label: Camera label ("left" or "right")
            frame: Latest validated frame
        """
        with self._latest_lock:
            if label == "left":
                self._left_latest = frame
            else:
                self._right_latest = frame

    def get_preview_frames(self, cameras_active: bool) -> Tuple[Frame, Frame]:
        """Get latest preview frames from both cameras.

        Args:
            cameras_active: Whether cameras are currently open

        Returns:
            Tuple of (left_frame, right_frame)

        Raises:
            CameraConnectionError: If capture is not started
            PitchTrackerError: If frames are not yet available
        """
        if not cameras_active:
            logger.error("Attempted to get preview frames but capture not started")
            raise CameraConnectionError("Capture not started. Call start_capture() first.")

        try:
            with self._latest_lock:
                left_frame = self._left_latest
                right_frame = self._right_latest
        except Exception as exc:
            logger.error(f"Error accessing preview frames: {exc}")
            raise PitchTrackerError(f"Error accessing frame buffer: {exc}") from exc

        if left_frame is None or right_frame is None:
            raise PitchTrackerError("Waiting for first camera frames. Please wait...")

        return left_frame, right_frame

    @staticmethod
    def get_stats(left_camera, right_camera) -> dict:
        """Get camera statistics.

        Args:
            left_camera: Left camera device (or None)
            right_camera: Right camera device (or None)

        Returns:
            Dictionary with left/right camera stats, or empty dict
        """
        if left_camera is None or right_camera is None:
            return {}

        from .utils import stats_to_dict

        return {
            "left": stats_to_dict(left_camera.get_stats()),
            "right": stats_to_dict(right_camera.get_stats()),
        }
