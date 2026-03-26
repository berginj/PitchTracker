"""Step 3: ROI configuration - define lane and plate regions."""

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
from ui.themes import (
    apply_standard_layout,
    build_notice,
    get_style_manager,
    show_message_dialog,
    style_preview_surface,
    style_status_label,
)
from ui.widgets.roi_label import RoiLabel


class RoiStep(BaseStep):
    """Step 3: ROI (Region of Interest) configuration."""

    def __init__(
        self,
        backend: str = "uvc",
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._backend = backend
        self._left_camera: Optional[CameraDevice] = None
        self._left_serial: Optional[str | int] = None

        self._lane_polygon: Optional[list[tuple[int, int]]] = None
        self._plate_polygon: Optional[list[tuple[int, int]]] = None
        self._current_mode: Optional[str] = None
        self._preview_rect: Optional[Rect] = None
        self._roi_path = Path("rois/shared_rois.json")

        self._build_ui()

        self._preview_timer = QtCore.QTimer()
        self._preview_timer.timeout.connect(self._update_preview)

    def _build_ui(self) -> None:
        """Build ROI configuration UI."""
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        instructions, _ = build_notice(
            "Edit lane and plate regions from the left camera view. Each rectangle is saved as soon as you finish drawing it.",
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

        self._lane_button = QtWidgets.QPushButton("Edit Lane ROI")
        self._lane_button.setMinimumHeight(40)
        self._lane_button.setCheckable(True)
        self._lane_button.clicked.connect(lambda: self._set_mode("lane"))
        self._style_manager.style_button(self._lane_button, "primary")

        self._plate_button = QtWidgets.QPushButton("Edit Plate ROI")
        self._plate_button.setMinimumHeight(40)
        self._plate_button.setCheckable(True)
        self._plate_button.clicked.connect(lambda: self._set_mode("plate"))
        self._style_manager.style_button(self._plate_button, "primary")

        self._clear_button = QtWidgets.QPushButton("Clear Current")
        self._clear_button.setMinimumHeight(40)
        self._clear_button.clicked.connect(self._clear_current_roi)
        self._style_manager.style_button(self._clear_button, "ghost")

        controls_layout.addWidget(self._lane_button, 2)
        controls_layout.addWidget(self._plate_button, 2)
        controls_layout.addWidget(self._clear_button, 1)
        layout.addLayout(controls_layout)

        self._status_label = QtWidgets.QLabel("No camera preview yet.")
        style_status_label(self._status_label, "info")
        layout.addWidget(self._status_label)

        self.setLayout(layout)

    def get_title(self) -> str:
        return "ROI Configuration"

    def validate(self) -> tuple[bool, str]:
        if self._lane_polygon is None:
            return False, "Lane ROI not configured. Draw a rectangle for the pitcher lane."
        if self._plate_polygon is None:
            return False, "Plate ROI not configured. Draw a rectangle for the plate area."
        return True, ""

    def is_skippable(self) -> bool:
        return self._roi_path.exists()

    def on_enter(self) -> None:
        if self._left_serial and not self._left_camera:
            self._open_camera()
        if self._left_camera:
            self._preview_timer.start(33)

    def on_exit(self) -> None:
        self._preview_timer.stop()
        self._set_mode(None)
        self._close_camera()

    def set_camera_serial(self, left_serial: str) -> None:
        self._left_serial = left_serial

    def _open_camera(self) -> None:
        """Open left camera device."""
        try:
            if self._backend == "opencv":
                from capture.opencv_backend import OpenCVCamera

                left_serial_str = str(self._left_serial)
                try:
                    if left_serial_str.isdigit():
                        left_index = int(left_serial_str)
                    else:
                        left_index = int(left_serial_str.split()[-1])
                    if left_index < 0:
                        raise ValueError(f"Camera index must be non-negative, got: {left_index}")
                except (ValueError, IndexError):
                    show_message_dialog(
                        self,
                        "Camera Open Error",
                        f"Invalid camera serial format: '{left_serial_str}'. Expected a numeric index.",
                        tone="error",
                    )
                    return

                self._left_camera = OpenCVCamera()
                self._left_camera.open(left_index)
                self._left_camera.set_mode(640, 480, 30, "GRAY8")
            else:
                from capture import UvcCamera

                self._left_camera = UvcCamera()
                self._left_camera.open(self._left_serial)
                self._left_camera.set_mode(640, 480, 30, "GRAY8")

            style_status_label(self._status_label, "success", "Camera preview active. Select an ROI to edit.")
        except Exception as exc:
            style_status_label(self._status_label, "error", f"Camera error: {exc}")

    def _close_camera(self) -> None:
        if self._left_camera:
            try:
                self._left_camera.stop()
                self._left_camera.close()
            except Exception:
                pass
            finally:
                self._left_camera = None

            import gc

            gc.collect()

    def _update_preview(self) -> None:
        if not self._left_camera:
            return

        try:
            frame = self._left_camera.read_frame(timeout_ms=1000)
            if frame is None:
                return

            annotated = self._draw_roi_overlays(frame.image.copy())
            self._update_view(annotated)

            height, width = frame.image.shape[:2]
            self._roi_view.set_image_size(width, height)
        except Exception:
            pass

    def _draw_roi_overlays(self, image: np.ndarray) -> np.ndarray:
        if self._lane_polygon:
            pts = np.array(self._lane_polygon, np.int32)
            cv2.polylines(image, [pts], True, (0, 255, 0), 2)
            cv2.putText(image, "LANE", tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        if self._plate_polygon:
            pts = np.array(self._plate_polygon, np.int32)
            cv2.polylines(image, [pts], True, (255, 0, 0), 2)
            cv2.putText(image, "PLATE", tuple(pts[0]), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 0, 0), 2)

        if self._preview_rect and self._current_mode:
            x, y, w, h = self._preview_rect
            color = (0, 255, 255)
            cv2.rectangle(image, (x, y), (x + w, y + h), color, 2)
            label = "LANE (preview)" if self._current_mode == "lane" else "PLATE (preview)"
            cv2.putText(image, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)

        return image

    def _update_view(self, image: np.ndarray) -> None:
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

    def _set_mode(self, mode: Optional[str]) -> None:
        self._current_mode = mode
        self._preview_rect = None
        self._lane_button.setChecked(mode == "lane")
        self._plate_button.setChecked(mode == "plate")
        self._roi_view.set_mode(mode)

        if mode == "lane":
            style_status_label(self._status_label, "info", "Draw a rectangle around the pitcher lane.")
        elif mode == "plate":
            style_status_label(self._status_label, "info", "Draw a rectangle around the home plate area.")
        else:
            style_status_label(self._status_label, "info", "Select an ROI to edit.")

    def _on_rect_update(self, rect: Rect, is_final: bool) -> None:
        x, y, w, h = rect
        if is_final:
            polygon = [
                (x, y),
                (x + w, y),
                (x + w, y + h),
                (x, y + h),
            ]

            if self._current_mode == "lane":
                self._lane_polygon = polygon
                self._save_rois()
                style_status_label(self._status_label, "success", "Lane ROI saved.")
                self._set_mode(None)
            elif self._current_mode == "plate":
                self._plate_polygon = polygon
                self._save_rois()
                style_status_label(self._status_label, "success", "Plate ROI saved.")
                self._set_mode(None)

            self._preview_rect = None
        else:
            self._preview_rect = rect

    def _clear_current_roi(self) -> None:
        if self._current_mode == "lane":
            self._lane_polygon = None
            self._save_rois()
            style_status_label(self._status_label, "warning", "Lane ROI cleared.")
        elif self._current_mode == "plate":
            self._plate_polygon = None
            self._save_rois()
            style_status_label(self._status_label, "warning", "Plate ROI cleared.")
        else:
            style_status_label(self._status_label, "info", "Select an ROI to clear.")

    def _save_rois(self) -> None:
        try:
            self._roi_path.parent.mkdir(parents=True, exist_ok=True)
            save_rois(self._roi_path, self._lane_polygon, self._plate_polygon)
        except Exception as exc:
            show_message_dialog(
                self,
                "Save Error",
                f"Failed to save ROIs:\n{exc}",
                tone="error",
            )
