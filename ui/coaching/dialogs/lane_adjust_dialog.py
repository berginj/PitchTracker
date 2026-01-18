"""Lane ROI adjustment dialog for coaching app."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from configs.roi_io import load_rois, save_rois
from ui.geometry import Rect
from ui.widgets.roi_label import RoiLabel


class LaneAdjustDialog(QtWidgets.QDialog):
    """Dialog for adjusting lane ROI in coaching mode.

    Allows user to view current lane ROI and draw a new rectangle
    to redefine the pitching lane region.
    """

    def __init__(
        self,
        camera_service,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Adjust Lane ROI")
        self.resize(900, 700)

        self._camera_service = camera_service
        self._roi_path = Path("configs/roi.json")

        # ROI state
        self._lane_polygon: Optional[list[tuple[int, int]]] = None
        self._new_lane_polygon: Optional[list[tuple[int, int]]] = None
        self._preview_rect: Optional[Rect] = None
        self._is_editing = False

        # Load existing ROI
        self._load_existing_roi()

        self._build_ui()

        # Preview timer
        self._preview_timer = QtCore.QTimer()
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_timer.start(33)  # ~30 FPS

    def _build_ui(self) -> None:
        """Build dialog UI."""
        layout = QtWidgets.QVBoxLayout()

        # Title and instructions
        title = QtWidgets.QLabel("Adjust Lane ROI")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; padding: 10px;")
        layout.addWidget(title)

        instructions = QtWidgets.QLabel(
            "The lane ROI defines where ball detections are tracked.\n\n"
            "Current lane is shown in GREEN. To adjust:\n"
            "1. Click 'Edit Lane ROI' button\n"
            "2. Drag a rectangle around the pitcher's lane\n"
            "3. Click 'Save' to apply changes"
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("font-size: 10pt; padding: 10px; background-color: #e3f2fd; border-radius: 5px;")
        layout.addWidget(instructions)

        # Camera preview with ROI overlay
        preview_group = QtWidgets.QGroupBox("Left Camera - Lane ROI Editor")
        self._roi_view = RoiLabel(on_rect_update=self._on_rect_update)
        self._roi_view.setMinimumSize(640, 480)
        self._roi_view.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._roi_view.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._roi_view.setStyleSheet("background-color: #f5f5f5;")

        preview_layout = QtWidgets.QVBoxLayout()
        preview_layout.addWidget(self._roi_view)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group, 1)

        # Controls
        controls_layout = QtWidgets.QHBoxLayout()

        self._edit_button = QtWidgets.QPushButton("📐 Edit Lane ROI")
        self._edit_button.setMinimumHeight(40)
        self._edit_button.setCheckable(True)
        self._edit_button.clicked.connect(self._toggle_edit_mode)

        self._reset_button = QtWidgets.QPushButton("🔄 Reset to Current")
        self._reset_button.setMinimumHeight(40)
        self._reset_button.clicked.connect(self._reset_roi)
        self._reset_button.setEnabled(False)

        controls_layout.addWidget(self._edit_button, 2)
        controls_layout.addWidget(self._reset_button, 1)
        layout.addLayout(controls_layout)

        # Status
        self._status_label = QtWidgets.QLabel("Current lane ROI loaded. Click 'Edit Lane ROI' to adjust.")
        self._status_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")
        layout.addWidget(self._status_label)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self._save_button = QtWidgets.QPushButton("Save Changes")
        self._save_button.setMinimumHeight(40)
        self._save_button.clicked.connect(self._save_and_accept)
        self._save_button.setEnabled(False)

        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.setMinimumHeight(40)
        cancel_button.clicked.connect(self.reject)

        button_layout.addWidget(self._save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _load_existing_roi(self) -> None:
        """Load existing lane ROI from config."""
        try:
            if self._roi_path.exists():
                rois = load_rois(self._roi_path)
                lane = rois.get("lane")
                if lane:
                    self._lane_polygon = lane
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Load Error",
                f"Failed to load existing lane ROI:\n{e}\n\nYou can still draw a new one.",
            )

    def _update_preview(self) -> None:
        """Update camera preview with ROI overlay."""
        try:
            # Get preview frame from camera service
            left_frame, _ = self._camera_service.get_preview_frames()
            if left_frame is None:
                return

            # Draw ROI overlays
            annotated = self._draw_roi_overlays(left_frame.image.copy())

            # Update view
            self._update_view(annotated)

            # Update image size for coordinate mapping
            height, width = left_frame.image.shape[:2]
            self._roi_view.set_image_size(width, height)

        except Exception:
            pass

    def _draw_roi_overlays(self, image: np.ndarray) -> np.ndarray:
        """Draw ROI overlays on image."""
        # Convert grayscale to BGR for colored overlays
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        # Draw original lane ROI (green)
        if self._lane_polygon and not self._is_editing:
            pts = np.array(self._lane_polygon, np.int32)
            cv2.polylines(image, [pts], True, (0, 255, 0), 2)
            cv2.putText(image, "LANE (current)", tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Draw new lane ROI (blue) if defined
        if self._new_lane_polygon:
            pts = np.array(self._new_lane_polygon, np.int32)
            cv2.polylines(image, [pts], True, (255, 0, 0), 2)
            cv2.putText(image, "LANE (new)", tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        # Draw preview rectangle (yellow) if in edit mode
        if self._preview_rect and self._is_editing:
            x, y, w, h = self._preview_rect
            color = (0, 255, 255)  # Yellow
            cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
            cv2.putText(image, "LANE (preview)", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

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

    def _toggle_edit_mode(self) -> None:
        """Toggle lane ROI editing mode."""
        self._is_editing = self._edit_button.isChecked()

        if self._is_editing:
            self._roi_view.set_mode("lane")
            self._status_label.setText("🖱 Drag a rectangle around the pitcher's lane.")
            self._status_label.setStyleSheet("color: blue; font-weight: bold; padding: 5px;")
        else:
            self._roi_view.set_mode(None)
            self._status_label.setText("Edit mode disabled. Click 'Edit Lane ROI' to continue editing.")
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

            # Save as new lane polygon
            self._new_lane_polygon = polygon
            self._status_label.setText("✓ New lane ROI defined! Click 'Save Changes' to apply.")
            self._status_label.setStyleSheet("color: green; font-weight: bold; padding: 5px;")

            # Enable save and reset buttons
            self._save_button.setEnabled(True)
            self._reset_button.setEnabled(True)

            # Exit edit mode
            self._is_editing = False
            self._edit_button.setChecked(False)
            self._roi_view.set_mode(None)
            self._preview_rect = None

        else:
            # Preview - store rect for visualization
            self._preview_rect = rect

    def _reset_roi(self) -> None:
        """Reset to original lane ROI."""
        self._new_lane_polygon = None
        self._preview_rect = None
        self._save_button.setEnabled(False)
        self._reset_button.setEnabled(False)
        self._status_label.setText("Reset to current lane ROI.")
        self._status_label.setStyleSheet("color: #666; font-style: italic; padding: 5px;")

    def _save_and_accept(self) -> None:
        """Save new lane ROI and close dialog."""
        if self._new_lane_polygon is None:
            QtWidgets.QMessageBox.warning(
                self,
                "No Changes",
                "No new lane ROI has been defined.",
            )
            return

        try:
            # Load existing ROIs (to preserve plate ROI)
            rois = load_rois(self._roi_path) if self._roi_path.exists() else {}
            plate = rois.get("plate")

            # Save with new lane ROI
            self._roi_path.parent.mkdir(parents=True, exist_ok=True)
            save_rois(self._roi_path, self._new_lane_polygon, plate)

            QtWidgets.QMessageBox.information(
                self,
                "Lane ROI Saved",
                "Lane ROI has been updated successfully.\n\n"
                "Note: You may need to restart the session for changes to take effect.",
            )

            self.accept()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Save Error",
                f"Failed to save lane ROI:\n{e}",
            )

    def closeEvent(self, event) -> None:
        """Handle dialog close."""
        self._preview_timer.stop()
        event.accept()
