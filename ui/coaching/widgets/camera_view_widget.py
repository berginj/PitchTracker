"""Camera view widget with L/R toggle for coaching UI."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from ui.coaching.widgets.heat_map import StrikeZoneOverlay

if TYPE_CHECKING:
    from contracts import Frame

logger = logging.getLogger(__name__)


class CameraViewWidget(QtWidgets.QWidget):
    """Single camera view with left/right toggle.

    Provides a unified camera display that can switch between left and right
    camera feeds. Includes strike zone overlay and camera selection controls.
    """

    # Signal emitted when camera selection changes
    camera_changed = QtCore.Signal(str)  # "left" or "right"

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
        min_width: int = 640,
        min_height: int = 480
    ):
        """Initialize camera view widget.

        Args:
            parent: Parent widget
            min_width: Minimum width for camera display
            min_height: Minimum height for camera display
        """
        super().__init__(parent)

        self._active_camera = "left"
        self._left_frame: Optional[Frame] = None
        self._right_frame: Optional[Frame] = None

        # Build UI
        self._build_ui(min_width, min_height)

    def _build_ui(self, min_width: int, min_height: int) -> None:
        """Build the widget UI.

        Args:
            min_width: Minimum camera display width
            min_height: Minimum camera display height
        """
        # Camera display label
        self._camera_label = QtWidgets.QLabel("Camera Preview")
        self._camera_label.setMinimumSize(min_width, min_height)
        self._camera_label.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._camera_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._camera_label.setStyleSheet("background-color: #f5f5f5;")
        self._camera_label.setScaledContents(False)  # Maintain aspect ratio

        # Strike zone overlay
        self._strike_zone = StrikeZoneOverlay(self._camera_label)
        self._strike_zone.setGeometry(self._camera_label.geometry())

        # Camera toggle controls
        toggle_widget = self._build_toggle_controls()

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._camera_label, 1)
        layout.addWidget(toggle_widget, 0)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

    def _build_toggle_controls(self) -> QtWidgets.QWidget:
        """Build camera toggle controls.

        Returns:
            Widget containing toggle buttons
        """
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout()

        # Radio button group for exclusive selection
        self._left_radio = QtWidgets.QRadioButton("Left Camera")
        self._right_radio = QtWidgets.QRadioButton("Right Camera")

        self._left_radio.setChecked(True)  # Default to left

        # Connect signals
        self._left_radio.toggled.connect(self._on_camera_toggle)

        # Add to layout
        layout.addWidget(self._left_radio)
        layout.addWidget(self._right_radio)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _on_camera_toggle(self, checked: bool) -> None:
        """Handle camera toggle.

        Args:
            checked: True if left radio is checked
        """
        new_camera = "left" if checked else "right"

        if new_camera != self._active_camera:
            self._active_camera = new_camera
            self._update_display()
            self.camera_changed.emit(new_camera)

    def set_active_camera(self, camera: str) -> None:
        """Set active camera programmatically.

        Args:
            camera: Camera to activate ("left" or "right")
        """
        if camera not in ("left", "right"):
            logger.warning(f"Invalid camera: {camera}")
            return

        if camera == "left":
            self._left_radio.setChecked(True)
        else:
            self._right_radio.setChecked(True)

        # Radio button signal will trigger _on_camera_toggle

    def get_active_camera(self) -> str:
        """Get currently active camera.

        Returns:
            Active camera ("left" or "right")
        """
        return self._active_camera

    def update_frames(
        self,
        left_frame: Optional[Frame],
        right_frame: Optional[Frame]
    ) -> None:
        """Update both camera frames.

        Args:
            left_frame: Left camera frame
            right_frame: Right camera frame
        """
        self._left_frame = left_frame
        self._right_frame = right_frame
        self._update_display()

    def update_pitch_location(self, norm_x: float, norm_y: float) -> None:
        """Update pitch location on strike zone overlay.

        Args:
            norm_x: Normalized X coordinate (0.0-1.0)
            norm_y: Normalized Y coordinate (0.0-1.0)
        """
        self._strike_zone.set_latest_pitch(norm_x, norm_y)

    def clear_pitch_location(self) -> None:
        """Clear pitch location marker."""
        self._strike_zone.clear_latest_pitch()

    def _update_display(self) -> None:
        """Update displayed frame based on active camera."""
        frame = self._left_frame if self._active_camera == "left" else self._right_frame

        if frame is None:
            return

        try:
            # Convert frame to QPixmap
            pixmap = self._frame_to_pixmap(frame.image)

            if pixmap and not pixmap.isNull():
                # Scale to fit label while maintaining aspect ratio
                scaled = pixmap.scaled(
                    self._camera_label.size(),
                    QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                    QtCore.Qt.TransformationMode.SmoothTransformation
                )
                self._camera_label.setPixmap(scaled)

                # Update overlay geometry
                self._strike_zone.setGeometry(self._camera_label.geometry())
        except Exception as e:
            logger.error(f"Failed to update camera display: {e}", exc_info=True)

    def _frame_to_pixmap(self, image: np.ndarray) -> Optional[QtGui.QPixmap]:
        """Convert numpy frame to QPixmap.

        Args:
            image: BGR numpy array (H, W, 3)

        Returns:
            QPixmap or None if conversion fails
        """
        try:
            # Convert BGR to RGB
            if len(image.shape) == 3 and image.shape[2] == 3:
                rgb_image = image[:, :, ::-1].copy()
            else:
                # Grayscale - convert to RGB
                rgb_image = np.stack([image, image, image], axis=2)

            h, w, ch = rgb_image.shape

            # Create QImage
            bytes_per_line = ch * w
            q_image = QtGui.QImage(
                rgb_image.data,
                w,
                h,
                bytes_per_line,
                QtGui.QImage.Format.Format_RGB888
            )

            # Convert to QPixmap
            return QtGui.QPixmap.fromImage(q_image)

        except Exception as e:
            logger.error(f"Frame to pixmap conversion failed: {e}")
            return None

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        """Handle resize event.

        Args:
            event: Resize event
        """
        super().resizeEvent(event)

        # Update overlay geometry when widget resizes
        self._strike_zone.setGeometry(self._camera_label.geometry())
        self._update_display()


__all__ = ["CameraViewWidget"]
