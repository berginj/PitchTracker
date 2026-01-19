"""Video display widget for review mode."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets


class VideoDisplayWidget(QtWidgets.QLabel):
    """Widget for displaying video frames.

    Displays video frames with automatic scaling to fit widget size
    while maintaining aspect ratio.

    Example:
        >>> display = VideoDisplayWidget()
        >>> display.set_frame(frame_array)
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize video display widget.

        Args:
            parent: Optional parent widget
        """
        super().__init__(parent)

        # Configure label
        self.setMinimumSize(640, 480)
        self.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #2b2b2b; color: #888;")
        self.setText("No Video Loaded")

        # Store current frame
        self._current_frame: Optional[np.ndarray] = None
        self._current_pixmap: Optional[QtGui.QPixmap] = None

        # Detections to overlay
        self._detections: list = []

    def set_frame(self, frame: np.ndarray, detections: Optional[list] = None) -> None:
        """Set and display a video frame with optional detection overlays.

        Args:
            frame: Video frame as numpy array (BGR or grayscale)
            detections: Optional list of Detection objects to overlay
        """
        self._current_frame = frame
        self._detections = detections or []

        # Draw detections on frame if provided
        if self._detections:
            frame = self._draw_detections_on_frame(frame.copy(), self._detections)

        self._current_pixmap = self._frame_to_pixmap(frame)

        if self._current_pixmap:
            # Scale to fit widget while maintaining aspect ratio
            scaled = self._current_pixmap.scaled(
                self.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)

    def clear(self) -> None:
        """Clear the display."""
        self._current_frame = None
        self._current_pixmap = None
        self._detections = []
        super().clear()
        self.setText("No Video Loaded")

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """Handle resize event - rescale current frame.

        Args:
            event: Resize event
        """
        super().resizeEvent(event)

        # Rescale current pixmap if we have one
        if self._current_pixmap:
            scaled = self._current_pixmap.scaled(
                self.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)

    @staticmethod
    def _draw_detections_on_frame(frame: np.ndarray, detections: list) -> np.ndarray:
        """Draw detection circles on frame.

        Args:
            frame: Video frame
            detections: List of Detection objects

        Returns:
            Frame with detection circles drawn
        """
        # Ensure frame is color for drawing
        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

        # Draw circles for each detection
        for detection in detections:
            center = (int(detection.u), int(detection.v))
            radius = max(5, int(detection.radius_px))

            # Draw circle (green for new detections)
            cv2.circle(frame, center, radius, (0, 255, 0), 2)

            # Draw center point
            cv2.circle(frame, center, 2, (0, 255, 0), -1)

        return frame

    @staticmethod
    def _frame_to_pixmap(frame: np.ndarray) -> Optional[QtGui.QPixmap]:
        """Convert numpy frame to QPixmap.

        Args:
            frame: Video frame as numpy array

        Returns:
            QPixmap for display, or None if conversion fails
        """
        try:
            # Ensure frame is uint8
            if frame.dtype != np.uint8:
                frame = frame.astype(np.uint8)

            # Convert BGR to RGB if color
            if len(frame.shape) == 3 and frame.shape[2] == 3:
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Create QImage
            height, width = frame.shape[:2]

            if len(frame.shape) == 3:
                # Color image
                bytes_per_line = 3 * width
                q_image = QtGui.QImage(
                    frame.data,
                    width,
                    height,
                    bytes_per_line,
                    QtGui.QImage.Format.Format_RGB888,
                )
            else:
                # Grayscale image
                bytes_per_line = width
                q_image = QtGui.QImage(
                    frame.data,
                    width,
                    height,
                    bytes_per_line,
                    QtGui.QImage.Format.Format_Grayscale8,
                )

            return QtGui.QPixmap.fromImage(q_image)

        except Exception as e:
            print(f"Failed to convert frame to pixmap: {e}")
            return None
