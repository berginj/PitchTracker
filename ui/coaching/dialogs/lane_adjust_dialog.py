"""Lane ROI adjustment dialog for coaching app."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from configs.roi_io import load_rois, save_rois
from ui.geometry import Rect
from ui.themes import (
    apply_standard_layout,
    build_dialog_header,
    build_notice,
    get_style_manager,
    polish_form_controls,
    show_message_dialog,
    style_preview_surface,
    style_status_label,
)
from ui.widgets.roi_label import RoiLabel


class LaneAdjustDialog(QtWidgets.QDialog):
    """Dialog for adjusting lane ROI in coaching mode."""

    def __init__(
        self,
        camera_service,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Adjust Lane ROI")
        self.resize(920, 760)

        self._style_manager = get_style_manager()
        self._camera_service = camera_service
        self._roi_path = Path("configs/roi.json")

        self._lane_polygon: Optional[list[tuple[int, int]]] = None
        self._new_lane_polygon: Optional[list[tuple[int, int]]] = None
        self._preview_rect: Optional[Rect] = None
        self._is_editing = False

        self._load_existing_roi()
        self._build_ui()

        self._preview_timer = QtCore.QTimer()
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_timer.start(33)

    def _build_ui(self) -> None:
        """Build dialog UI."""
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)
        layout.addWidget(
            build_dialog_header(
                "Adjust Lane ROI",
                "Refine the tracked pitching lane on the left camera view without leaving the coaching session.",
            )
        )

        instructions, _ = build_notice(
            "Current lane ROI is shown in green. Enable edit mode, drag a new rectangle, then save the change.",
            tone="info",
        )
        layout.addWidget(instructions)

        preview_group = QtWidgets.QGroupBox("Left Camera Preview")
        self._roi_view = RoiLabel(on_rect_update=self._on_rect_update)
        self._roi_view.setMinimumSize(640, 480)
        self._roi_view.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._roi_view.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        style_preview_surface(self._roi_view)

        preview_layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(preview_layout, margins=(8, 8, 8, 8), spacing=10)
        preview_layout.addWidget(self._roi_view)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group, 1)

        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.setSpacing(10)

        self._edit_button = QtWidgets.QPushButton("Edit Lane ROI")
        self._edit_button.setMinimumHeight(self._style_manager.theme.button_height_md)
        self._edit_button.setCheckable(True)
        self._edit_button.clicked.connect(self._toggle_edit_mode)
        self._style_manager.style_button(self._edit_button, "primary")

        self._reset_button = QtWidgets.QPushButton("Reset to Current")
        self._reset_button.setMinimumHeight(self._style_manager.theme.button_height_md)
        self._reset_button.clicked.connect(self._reset_roi)
        self._reset_button.setEnabled(False)
        self._style_manager.style_button(self._reset_button, "ghost")

        controls_layout.addWidget(self._edit_button, 2)
        controls_layout.addWidget(self._reset_button, 1)
        layout.addLayout(controls_layout)

        self._status_label = QtWidgets.QLabel()
        style_status_label(
            self._status_label,
            "info",
            "Current lane ROI loaded. Enable edit mode to adjust it.",
        )
        layout.addWidget(self._status_label)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(10)
        button_layout.addStretch()

        self._save_button = QtWidgets.QPushButton("Save Changes")
        self._save_button.setMinimumHeight(self._style_manager.theme.button_height_md)
        self._save_button.clicked.connect(self._save_and_accept)
        self._save_button.setEnabled(False)
        self._style_manager.style_button(self._save_button, "success")

        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.setMinimumHeight(self._style_manager.theme.button_height_md)
        cancel_button.clicked.connect(self.reject)
        self._style_manager.style_button(cancel_button, "ghost")

        button_layout.addWidget(self._save_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)
        polish_form_controls(self)

    def _load_existing_roi(self) -> None:
        """Load existing lane ROI from config."""
        try:
            if self._roi_path.exists():
                rois = load_rois(self._roi_path)
                lane = rois.get("lane")
                if lane:
                    self._lane_polygon = lane
        except Exception as exc:
            show_message_dialog(
                self,
                "Load Error",
                f"Failed to load existing lane ROI:\n{exc}\n\nYou can still draw a new one.",
                tone="warning",
            )

    def _update_preview(self) -> None:
        """Update camera preview with ROI overlay."""
        try:
            left_frame, _ = self._camera_service.get_preview_frames()
            if left_frame is None:
                return

            annotated = self._draw_roi_overlays(left_frame.image.copy())
            self._update_view(annotated)

            height, width = left_frame.image.shape[:2]
            self._roi_view.set_image_size(width, height)
        except Exception:
            pass

    def _draw_roi_overlays(self, image: np.ndarray) -> np.ndarray:
        """Draw ROI overlays on image."""
        if len(image.shape) == 2:
            image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)

        if self._lane_polygon and not self._is_editing:
            pts = np.array(self._lane_polygon, np.int32)
            cv2.polylines(image, [pts], True, (0, 255, 0), 2)
            cv2.putText(image, "LANE (current)", tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        if self._new_lane_polygon:
            pts = np.array(self._new_lane_polygon, np.int32)
            cv2.polylines(image, [pts], True, (255, 0, 0), 2)
            cv2.putText(image, "LANE (new)", tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

        if self._preview_rect and self._is_editing:
            x, y, w, h = self._preview_rect
            color = (0, 255, 255)
            cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
            cv2.putText(image, "LANE (preview)", (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        return image

    def _update_view(self, image: np.ndarray) -> None:
        """Update QLabel with image."""
        try:
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
                q_image = QtGui.QImage(
                    image.data,
                    width,
                    height,
                    width,
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
            style_status_label(
                self._status_label,
                "info",
                "Drag a rectangle around the pitcher lane, then release to stage the new ROI.",
            )
        else:
            self._roi_view.set_mode(None)
            style_status_label(
                self._status_label,
                "info",
                "Edit mode disabled. Enable edit mode to continue adjusting the lane ROI.",
            )

    def _on_rect_update(self, rect: Rect, is_final: bool) -> None:
        """Handle ROI rectangle update from RoiLabel."""
        x, y, w, h = rect
        if is_final:
            polygon = [
                (x, y),
                (x + w, y),
                (x + w, y + h),
                (x, y + h),
            ]
            self._new_lane_polygon = polygon
            style_status_label(
                self._status_label,
                "success",
                "New lane ROI staged. Save changes to apply it.",
            )
            self._save_button.setEnabled(True)
            self._reset_button.setEnabled(True)
            self._is_editing = False
            self._edit_button.setChecked(False)
            self._roi_view.set_mode(None)
            self._preview_rect = None
        else:
            self._preview_rect = rect

    def _reset_roi(self) -> None:
        """Reset to original lane ROI."""
        self._new_lane_polygon = None
        self._preview_rect = None
        self._save_button.setEnabled(False)
        self._reset_button.setEnabled(False)
        style_status_label(self._status_label, "info", "Reset to the currently saved lane ROI.")

    def _save_and_accept(self) -> None:
        """Save new lane ROI and close dialog."""
        if self._new_lane_polygon is None:
            show_message_dialog(
                self,
                "No Changes",
                "No new lane ROI has been defined.",
                tone="warning",
            )
            return

        try:
            rois = load_rois(self._roi_path) if self._roi_path.exists() else {}
            plate = rois.get("plate")
            self._roi_path.parent.mkdir(parents=True, exist_ok=True)
            save_rois(self._roi_path, self._new_lane_polygon, plate)

            show_message_dialog(
                self,
                "Lane ROI Saved",
                "Lane ROI was updated successfully.\n\nRestart the session if the new lane does not appear immediately.",
                tone="success",
            )
            self.accept()
        except Exception as exc:
            show_message_dialog(
                self,
                "Save Error",
                f"Failed to save lane ROI:\n{exc}",
                tone="error",
            )

    def closeEvent(self, event) -> None:
        """Handle dialog close."""
        self._preview_timer.stop()
        event.accept()
