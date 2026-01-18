"""Step 3: ROI Configuration - Define lane and plate regions."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from capture import CameraDevice
from configs.roi_io import save_rois
from ui.geometry import Rect
from ui.setup.steps.base_step import BaseStep
from ui.widgets.roi_label import RoiLabel


class RoiStep(BaseStep):
    """Step 3: ROI (Region of Interest) configuration.

    Workflow:
    1. Show live preview from left camera
    2. Draw lane ROI rectangle
    3. Draw plate ROI rectangle
    4. Save ROIs to shared file
    """

    def __init__(
        self,
        backend: str = "uvc",
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._backend = backend
        self._left_camera: Optional[CameraDevice] = None
        self._left_serial: Optional[str] = None

        # ROI state
        self._lane_polygon: Optional[list[tuple[int, int]]] = None
        self._plate_polygon: Optional[list[tuple[int, int]]] = None
        self._current_mode: Optional[str] = None  # "lane" or "plate"
        self._preview_rect: Optional[Rect] = None

        # ROI file path
        self._roi_path = Path("rois/shared_rois.json")

        self._build_ui()

        # Preview timer
        self._preview_timer = QtCore.QTimer()
        self._preview_timer.timeout.connect(self._update_preview)

    def _build_ui(self) -> None:
        """Build ROI configuration UI."""
        layout = QtWidgets.QVBoxLayout()

        # Instructions
        instructions = QtWidgets.QLabel(
            "ROI Configuration:\n\n"
            "1. Click 'Edit Lane ROI' and drag a rectangle around the pitcher's lane\n"
            "2. Click 'Edit Plate ROI' and drag a rectangle around the home plate area\n"
            "3. ROIs are saved automatically when drawing is complete"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("font-size: 11pt; padding: 10px; background-color: #e3f2fd; border-radius: 5px;")
        layout.addWidget(instructions)

        # Camera preview with ROI drawing
        preview_group = QtWidgets.QGroupBox("Left Camera - ROI Editor")
        self._roi_view = RoiLabel(on_rect_update=self._on_rect_update)
        self._roi_view.setMinimumSize(640, 480)
        self._roi_view.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._roi_view.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._roi_view.setStyleSheet("background-color: #f5f5f5;")

        preview_layout = QtWidgets.QVBoxLayout()
        preview_layout.addWidget(self._roi_view)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group, 1)

        # ROI controls
        controls_layout = QtWidgets.QHBoxLayout()

        self._lane_button = QtWidgets.QPushButton("📐 Edit Lane ROI")
        self._lane_button.setMinimumHeight(40)
        self._lane_button.setCheckable(True)
        self._lane_button.clicked.connect(lambda: self._set_mode("lane"))

        self._plate_button = QtWidgets.QPushButton("📐 Edit Plate ROI")
        self._plate_button.setMinimumHeight(40)
        self._plate_button.setCheckable(True)
        self._plate_button.clicked.connect(lambda: self._set_mode("plate"))

        self._clear_button = QtWidgets.QPushButton("🗑 Clear Current")
        self._clear_button.setMinimumHeight(40)
        self._clear_button.clicked.connect(self._clear_current_roi)

        controls_layout.addWidget(self._lane_button, 2)
        controls_layout.addWidget(self._plate_button, 2)
        controls_layout.addWidget(self._clear_button, 1)
        layout.addLayout(controls_layout)

        # Status
        self._status_label = QtWidgets.QLabel("No camera preview yet.")
        self._status_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        layout.addWidget(self._status_label)

        self.setLayout(layout)

    def get_title(self) -> str:
        """Return step title."""
        return "ROI Configuration"

    def validate(self) -> tuple[bool, str]:
        """Validate ROI configuration."""
        if self._lane_polygon is None:
            return False, "Lane ROI not configured. Click 'Edit Lane ROI' and draw a rectangle."

        if self._plate_polygon is None:
            return False, "Plate ROI not configured. Click 'Edit Plate ROI' and draw a rectangle."

        return True, ""

    def is_skippable(self) -> bool:
        """ROI configuration can be skipped if already exists."""
        return self._roi_path.exists()

    def on_enter(self) -> None:
        """Called when step becomes active."""
        # Open camera if serial is set
        if self._left_serial and not self._left_camera:
            self._open_camera()

        # Start preview timer
        if self._left_camera:
            self._preview_timer.start(33)  # ~30 FPS

    def on_exit(self) -> None:
        """Called when leaving step."""
        # Stop preview timer
        self._preview_timer.stop()

        # Disable drawing mode
        self._set_mode(None)

        # Close camera
        self._close_camera()

    def set_camera_serial(self, left_serial: str) -> None:
        """Set left camera serial from Step 1."""
        self._left_serial = left_serial

    def _open_camera(self) -> None:
        """Open left camera device."""
        try:
            if self._backend == "opencv":
                from capture.opencv_backend import OpenCVCamera

                # Extract index from "Camera N" format
                left_index = int(self._left_serial.split()[-1])
                self._left_camera = OpenCVCamera(index=left_index)

            else:  # uvc
                from capture import UvcCamera

                self._left_camera = UvcCamera()
                self._left_camera.open(self._left_serial)
                self._left_camera.set_mode(640, 480, 120, "GRAY8")

            # Start camera
            self._left_camera.start()

            self._status_label.setText("Camera preview active. Select an ROI to edit.")
            self._status_label.setStyleSheet("color: green; font-weight: bold; padding: 5px;")

        except Exception as e:
            self._status_label.setText(f"Camera error: {str(e)}")
            self._status_label.setStyleSheet("color: red; font-weight: bold; padding: 5px;")

    def _close_camera(self) -> None:
        """Close camera device."""
        if self._left_camera:
            try:
                self._left_camera.stop()
                self._left_camera = None
            except Exception:
                pass

    def _update_preview(self) -> None:
        """Update camera preview with ROI overlays."""
        if not self._left_camera:
            return

        try:
            # Get frame
            frame = self._left_camera.read()
            if frame is None:
                return

            # Draw ROI overlays
            annotated = self._draw_roi_overlays(frame.image.copy())

            # Update view
            self._update_view(annotated)

            # Update image size for coordinate mapping
            height, width = frame.image.shape[:2]
            self._roi_view.set_image_size(width, height)

        except Exception:
            pass

    def _draw_roi_overlays(self, image: np.ndarray) -> np.ndarray:
        """Draw ROI overlays on image."""
        # Draw lane ROI (green)
        if self._lane_polygon:
            pts = np.array(self._lane_polygon, np.int32)
            cv2.polylines(image, [pts], True, (0, 255, 0), 2)
            cv2.putText(image, "LANE", tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Draw plate ROI (blue)
        if self._plate_polygon:
            pts = np.array(self._plate_polygon, np.int32)
            cv2.polylines(image, [pts], True, (255, 0, 0), 2)
            cv2.putText(image, "PLATE", tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

        # Draw preview rectangle (yellow) if in edit mode
        if self._preview_rect and self._current_mode:
            x, y, w, h = self._preview_rect
            color = (0, 255, 255)  # Yellow
            cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
            label = "LANE (preview)" if self._current_mode == "lane" else "PLATE (preview)"
            cv2.putText(image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        return image

    def _update_view(self, image: np.ndarray) -> None:
        """Update QLabel with image."""
        try:
            # Convert to QPixmap
            if len(image.shape) == 3:
                image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
                height, width, channels = image_rgb.shape
                bytes_per_line = channels * width
                q_image = QtGui.QImage(
                    image_rgb.data,
                    width,
                    height,
                    bytes_per_line,
                    QtGui.QImage.Format.Format_RGB888,
                )
            else:
                height, width = image.shape
                bytes_per_line = width
                q_image = QtGui.QImage(
                    image.data,
                    width,
                    height,
                    bytes_per_line,
                    QtGui.QImage.Format.Format_Grayscale8,
                )

            pixmap = QtGui.QPixmap.fromImage(q_image)
            scaled = pixmap.scaled(
                self._roi_view.size(),
                QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            )
            self._roi_view.setPixmap(scaled)

        except Exception:
            pass

    def _set_mode(self, mode: Optional[str]) -> None:
        """Set ROI editing mode."""
        self._current_mode = mode
        self._preview_rect = None

        # Update button states
        self._lane_button.setChecked(mode == "lane")
        self._plate_button.setChecked(mode == "plate")

        # Update ROI label mode
        self._roi_view.set_mode(mode)

        # Update status
        if mode == "lane":
            self._status_label.setText("🖱 Draw a rectangle around the pitcher's lane.")
            self._status_label.setStyleSheet("color: blue; font-weight: bold; padding: 5px;")
        elif mode == "plate":
            self._status_label.setText("🖱 Draw a rectangle around the home plate area.")
            self._status_label.setStyleSheet("color: blue; font-weight: bold; padding: 5px;")
        else:
            self._status_label.setText("Select an ROI to edit.")
            self._status_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")

    def _on_rect_update(self, rect: Rect, is_final: bool) -> None:
        """Handle ROI rectangle update from RoiLabel."""
        x, y, w, h = rect

        if is_final:
            # Convert rectangle to polygon (4 corners)
            polygon = [
                (x, y),  # Top-left
                (x + w, y),  # Top-right
                (x + w, y + h),  # Bottom-right
                (x, y + h),  # Bottom-left
            ]

            # Save to appropriate ROI
            if self._current_mode == "lane":
                self._lane_polygon = polygon
                self._save_rois()
                self._status_label.setText("✓ Lane ROI saved!")
                self._status_label.setStyleSheet("color: green; font-weight: bold; padding: 5px;")
                # Exit edit mode
                self._set_mode(None)

            elif self._current_mode == "plate":
                self._plate_polygon = polygon
                self._save_rois()
                self._status_label.setText("✓ Plate ROI saved!")
                self._status_label.setStyleSheet("color: green; font-weight: bold; padding: 5px;")
                # Exit edit mode
                self._set_mode(None)

            self._preview_rect = None

        else:
            # Preview - store rect for visualization
            self._preview_rect = rect

    def _clear_current_roi(self) -> None:
        """Clear currently selected ROI."""
        if self._current_mode == "lane":
            self._lane_polygon = None
            self._save_rois()
            self._status_label.setText("Lane ROI cleared.")
        elif self._current_mode == "plate":
            self._plate_polygon = None
            self._save_rois()
            self._status_label.setText("Plate ROI cleared.")
        else:
            self._status_label.setText("Select an ROI to clear.")

    def _save_rois(self) -> None:
        """Save ROIs to file."""
        try:
            # Ensure directory exists
            self._roi_path.parent.mkdir(parents=True, exist_ok=True)

            # Save ROIs
            save_rois(self._roi_path, self._lane_polygon, self._plate_polygon)

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save ROIs:\n{str(e)}",
            )
