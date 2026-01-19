"""Video display widget for review mode."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets


class VideoDisplayWidget(QtWidgets.QLabel):
    """Widget for displaying video frames.

    Displays video frames with automatic scaling to fit widget size
    while maintaining aspect ratio. Supports manual annotation by clicking.

    Signals:
        annotation_added: Emitted when user clicks to add annotation (float x, float y)

    Example:
        >>> display = VideoDisplayWidget()
        >>> display.set_frame(frame_array)
        >>> display.annotation_added.connect(lambda x, y: print(f"Click at {x}, {y}"))
    """

    # Signal for manual annotations
    annotation_added = QtCore.Signal(float, float)

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

        # Manual annotations
        self._annotations: list = []  # List of (x, y) tuples
        self._annotation_mode = False

    def set_frame(self, frame: np.ndarray, detections: Optional[list] = None) -> None:
        """Set and display a video frame with optional detection overlays.

        Args:
            frame: Video frame as numpy array (BGR or grayscale)
            detections: Optional list of Detection objects to overlay
        """
        self._current_frame = frame
        self._detections = detections or []

        # Draw detections on frame if provided
        display_frame = frame.copy()
        if self._detections:
            display_frame = self._draw_detections_on_frame(display_frame, self._detections)

        # Draw annotations on frame if any
        if self._annotations:
            display_frame = self._draw_annotations_on_frame(display_frame, self._annotations)

        self._current_pixmap = self._frame_to_pixmap(display_frame)

        if self._current_pixmap:
            # Scale to fit widget while maintaining aspect ratio
            scaled = self._current_pixmap.scaled(
                self.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            self.setPixmap(scaled)

    def set_annotation_mode(self, enabled: bool) -> None:
        """Enable or disable manual annotation mode.

        Args:
            enabled: True to enable annotation mode, False to disable
        """
        self._annotation_mode = enabled

        if enabled:
            self.setCursor(QtCore.Qt.CursorShape.CrossCursor)
            self.setToolTip("Click to mark ball location")
        else:
            self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
            self.setToolTip("")

    def add_manual_annotation(self, x: float, y: float) -> None:
        """Add a manual annotation marker.

        Args:
            x: X coordinate in frame coordinates
            y: Y coordinate in frame coordinates
        """
        self._annotations.append((x, y))

        # Redraw frame with annotation
        if self._current_frame is not None:
            frame = self._draw_detections_on_frame(self._current_frame.copy(), self._detections)
            frame = self._draw_annotations_on_frame(frame, self._annotations)
            self._current_pixmap = self._frame_to_pixmap(frame)

            if self._current_pixmap:
                scaled = self._current_pixmap.scaled(
                    self.size(),
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation,
                )
                self.setPixmap(scaled)

    def clear_annotations(self) -> None:
        """Clear all manual annotations."""
        self._annotations.clear()

        # Redraw frame without annotations
        if self._current_frame is not None:
            frame = self._draw_detections_on_frame(self._current_frame.copy(), self._detections)
            self._current_pixmap = self._frame_to_pixmap(frame)

            if self._current_pixmap:
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
        self._annotations = []
        super().clear()
        self.setText("No Video Loaded")

    def mousePressEvent(self, event: QtGui.QMouseEvent) -> None:
        """Handle mouse press event for manual annotation.

        Args:
            event: Mouse event
        """
        if not self._annotation_mode or self._current_frame is None:
            return

        # Get click position relative to widget
        click_pos = event.position()

        # Convert widget coordinates to frame coordinates
        if self.pixmap():
            pixmap = self.pixmap()
            widget_width = self.width()
            widget_height = self.height()
            pixmap_width = pixmap.width()
            pixmap_height = pixmap.height()

            # Calculate offset and scale
            scale_x = self._current_frame.shape[1] / pixmap_width
            scale_y = self._current_frame.shape[0] / pixmap_height

            # Center alignment offset
            offset_x = (widget_width - pixmap_width) / 2
            offset_y = (widget_height - pixmap_height) / 2

            # Convert to pixmap coordinates
            pixmap_x = click_pos.x() - offset_x
            pixmap_y = click_pos.y() - offset_y

            # Check if click is within pixmap bounds
            if 0 <= pixmap_x < pixmap_width and 0 <= pixmap_y < pixmap_height:
                # Convert to frame coordinates
                frame_x = pixmap_x * scale_x
                frame_y = pixmap_y * scale_y

                # Add annotation
                self.add_manual_annotation(frame_x, frame_y)

                # Emit signal
                self.annotation_added.emit(frame_x, frame_y)

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
    def _draw_annotations_on_frame(frame: np.ndarray, annotations: list) -> np.ndarray:
        """Draw manual annotation markers on frame.

        Args:
            frame: Video frame
            annotations: List of (x, y) tuples

        Returns:
            Frame with annotation markers drawn
        """
        # Ensure frame is color for drawing
        if len(frame.shape) == 2:
            frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)

        # Draw X marker for each annotation (orange/blue color to distinguish from detections)
        for x, y in annotations:
            center = (int(x), int(y))
            size = 10

            # Draw X marker (orange)
            cv2.line(frame, (center[0] - size, center[1] - size),
                    (center[0] + size, center[1] + size), (0, 165, 255), 2)
            cv2.line(frame, (center[0] + size, center[1] - size),
                    (center[0] - size, center[1] + size), (0, 165, 255), 2)

            # Draw circle around it
            cv2.circle(frame, center, 15, (0, 165, 255), 2)

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
