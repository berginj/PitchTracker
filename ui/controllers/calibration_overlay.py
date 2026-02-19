"""Calibration overlay controller.

Extracted from MainWindow to reduce god class complexity.
Manages checkerboard and fiducial (AprilTag) detection for calibration overlays.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

import cv2
import numpy as np

from detect.fiducials import FiducialDetection, detect_apriltags
from log_config.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class CalibrationOverlayController:
    """Manages calibration overlay detection.

    Responsibilities:
    - Checkerboard pattern detection for camera calibration
    - Fiducial (AprilTag) detection for plate plane estimation
    - Frame striding to reduce CPU load
    """

    def __init__(
        self,
        target_pattern: tuple[int, int] = (9, 6),
        target_stride: int = 5,
        fiducial_stride: int = 5,
        fiducial_ids: Optional[dict[str, int]] = None,
    ):
        """Initialize calibration overlay controller.

        Args:
            target_pattern: Checkerboard inner corner dimensions (cols, rows)
            target_stride: Process every N frames for checkerboard
            fiducial_stride: Process every N frames for fiducials
            fiducial_ids: Mapping of fiducial names to IDs (e.g., {"plate": 0, "rubber": 1})
        """
        # Target (checkerboard) detection state
        self._show_target = False
        self._target_found = False
        self._target_corners: Optional[list[tuple[float, float]]] = None
        self._target_pattern = target_pattern
        self._target_stride = target_stride
        self._target_frame_index = 0

        # Fiducial (AprilTag) detection state
        self._show_fiducials = False
        self._fiducial_detections: list[FiducialDetection] = []
        self._fiducial_error: Optional[str] = None
        self._fiducial_stride = fiducial_stride
        self._fiducial_frame_index = 0
        self._fiducial_ids = fiducial_ids or {"plate": 0, "rubber": 1}

        logger.debug("CalibrationOverlayController initialized")

    @property
    def show_target(self) -> bool:
        """Whether target overlay is enabled."""
        return self._show_target

    @property
    def target_found(self) -> bool:
        """Whether checkerboard was found in last detection."""
        return self._target_found

    @property
    def target_corners(self) -> Optional[list[tuple[float, float]]]:
        """Detected checkerboard corner coordinates."""
        return self._target_corners

    @property
    def show_fiducials(self) -> bool:
        """Whether fiducial overlay is enabled."""
        return self._show_fiducials

    @property
    def fiducial_detections(self) -> list[FiducialDetection]:
        """List of detected fiducials."""
        return self._fiducial_detections

    @property
    def fiducial_error(self) -> Optional[str]:
        """Error message from fiducial detection, if any."""
        return self._fiducial_error

    @property
    def fiducial_ids(self) -> dict[str, int]:
        """Mapping of fiducial names to IDs."""
        return self._fiducial_ids

    def set_target_overlay(self, enabled: bool) -> None:
        """Enable or disable target (checkerboard) overlay.

        Args:
            enabled: Whether to enable the overlay
        """
        self._show_target = enabled
        self._target_found = False
        self._target_corners = None
        self._target_frame_index = 0
        logger.debug(f"Target overlay {'enabled' if enabled else 'disabled'}")

    def set_fiducial_overlay(self, enabled: bool) -> None:
        """Enable or disable fiducial (AprilTag) overlay.

        Args:
            enabled: Whether to enable the overlay
        """
        self._show_fiducials = enabled
        self._fiducial_detections = []
        self._fiducial_error = None
        self._fiducial_frame_index = 0
        logger.debug(f"Fiducial overlay {'enabled' if enabled else 'disabled'}")

    def _to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """Convert image to grayscale if needed.

        Args:
            image: Input image (grayscale or color)

        Returns:
            Grayscale image
        """
        if image.ndim == 2:
            return image
        return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def process_target_detection(
        self, frame_image: np.ndarray
    ) -> Optional[list[tuple[float, float]]]:
        """Process frame for checkerboard detection.

        Only processes every N frames based on stride setting.

        Args:
            frame_image: Camera frame to process

        Returns:
            List of corner coordinates if found, None otherwise
        """
        if not self._show_target:
            return None

        self._target_frame_index += 1
        if self._target_frame_index % self._target_stride == 0:
            gray = self._to_grayscale(frame_image)
            found, corners = cv2.findChessboardCorners(gray, self._target_pattern)
            self._target_found = bool(found)
            if found and corners is not None:
                self._target_corners = [
                    (float(pt[0][0]), float(pt[0][1])) for pt in corners
                ]
            else:
                self._target_corners = None

        return self._target_corners

    def process_fiducial_detection(
        self, frame_image: np.ndarray
    ) -> Optional[list[FiducialDetection]]:
        """Process frame for fiducial (AprilTag) detection.

        Only processes every N frames based on stride setting.

        Args:
            frame_image: Camera frame to process

        Returns:
            List of fiducial detections, or None if overlay disabled
        """
        if not self._show_fiducials:
            return None

        self._fiducial_frame_index += 1
        if self._fiducial_frame_index % self._fiducial_stride == 0:
            gray = self._to_grayscale(frame_image)
            detections, error = detect_apriltags(gray)
            self._fiducial_detections = detections
            self._fiducial_error = error

        return self._fiducial_detections

    def process_frame(
        self, frame_image: np.ndarray
    ) -> tuple[Optional[list[tuple[float, float]]], Optional[list[FiducialDetection]]]:
        """Process frame for all calibration overlays.

        Args:
            frame_image: Camera frame to process

        Returns:
            Tuple of (checkerboard_corners, fiducial_detections)
        """
        checkerboard = self.process_target_detection(frame_image)
        fiducials = self.process_fiducial_detection(frame_image)
        return checkerboard, fiducials
