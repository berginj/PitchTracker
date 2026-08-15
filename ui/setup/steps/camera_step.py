"""Camera discovery and selection step."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from ui.device_utils import DEFAULT_OPENCV_MAX_INDEX, current_serial, probe_opencv_indices, probe_uvc_devices
from ui.setup.steps.base_step import BaseStep
from ui.themes import (
    apply_standard_layout,
    build_notice,
    get_style_manager,
    style_preview_surface,
    style_status_label,
)


class CameraDiscoverySignals(QtCore.QObject):
    """Signals emitted by a camera discovery worker."""

    finished_signal = QtCore.Signal(list)
    error_signal = QtCore.Signal(str)


def _safe_emit_finished(signals: CameraDiscoverySignals, devices: list) -> None:
    """Emit finished_signal, silently absorbing RuntimeError from deleted C++."""
    try:
        signals.finished_signal.emit(devices)
    except RuntimeError:
        pass


def _safe_emit_error(signals: CameraDiscoverySignals, message: str) -> None:
    """Emit error_signal, silently absorbing RuntimeError from deleted C++."""
    try:
        signals.error_signal.emit(message)
    except RuntimeError:
        pass


class CameraDiscoveryWorker(QtCore.QRunnable):
    """Probe USB/UVC devices on the application thread pool."""

    def __init__(self, backend: str):
        super().__init__()
        self._backend = backend
        self.signals = CameraDiscoverySignals()

    def run(self) -> None:
        try:
            if self._backend == "opencv":
                devices = probe_opencv_indices(max_index=DEFAULT_OPENCV_MAX_INDEX, parallel=False, use_cache=False)
            else:
                devices = probe_uvc_devices()
        except Exception as exc:  # noqa: BLE001
            _safe_emit_error(self.signals, str(exc))
            return
        _safe_emit_finished(self.signals, devices or [])


class CameraStep(BaseStep):
    """Camera discovery, selection, and preview step."""

    def __init__(self, backend: str = "uvc"):
        super().__init__()
        self._style_manager = get_style_manager()
        self._backend = backend
        self._left_serial: Optional[str] = None
        self._right_serial: Optional[str] = None
        self._left_camera: Optional[object] = None
        self._right_camera: Optional[object] = None
        self._preview_timer: Optional[QtCore.QTimer] = None

        self._build_ui()
        self._setup_preview_timer()

    def get_title(self) -> str:
        return "Camera Setup"

    def get_description(self) -> str:
        return "Discover and select left and right cameras for stereo tracking."

    def _set_status_message(self, message: str, tone: str = "info") -> None:
        """Update the step status label."""
        style_status_label(self._status_label, tone, message)

    def _build_ui(self) -> None:
        """Build camera selection UI."""
        instructions, _ = build_notice(
            "Connect both cameras, refresh the device list, and choose distinct left and right assignments before continuing.",
            tone="info",
        )

        backend_group = QtWidgets.QGroupBox("Camera Backend")
        backend_layout = QtWidgets.QHBoxLayout()
        backend_layout.setSpacing(10)

        self._uvc_radio = QtWidgets.QRadioButton("UVC (USB Video Class)")
        self._opencv_radio = QtWidgets.QRadioButton("OpenCV (Simple Indices)")

        if self._backend == "uvc":
            self._uvc_radio.setChecked(True)
        else:
            self._opencv_radio.setChecked(True)

        self._uvc_radio.toggled.connect(lambda checked: self._switch_backend("uvc") if checked else None)
        self._opencv_radio.toggled.connect(lambda checked: self._switch_backend("opencv") if checked else None)

        backend_layout.addWidget(self._uvc_radio)
        backend_layout.addWidget(self._opencv_radio)
        backend_layout.addStretch()

        backend_help = QtWidgets.QLabel("If UVC fails, switch to OpenCV backend which uses simple camera indices.")
        self._style_manager.style_label(backend_help, "muted")

        backend_vlayout = QtWidgets.QVBoxLayout()
        apply_standard_layout(backend_vlayout, margins=(8, 8, 8, 8), spacing=8)
        backend_vlayout.addLayout(backend_layout)
        backend_vlayout.addWidget(backend_help)
        backend_group.setLayout(backend_vlayout)

        device_group = QtWidgets.QGroupBox("Camera Selection")
        device_layout = QtWidgets.QFormLayout()
        apply_standard_layout(device_layout, margins=(8, 8, 8, 8), spacing=10)

        self._left_combo = QtWidgets.QComboBox()
        self._left_combo.setMinimumWidth(300)
        self._left_combo.setAccessibleName("Left camera selection")
        self._left_combo.currentTextChanged.connect(self._on_left_changed)

        self._right_combo = QtWidgets.QComboBox()
        self._right_combo.setMinimumWidth(300)
        self._right_combo.setAccessibleName("Right camera selection")
        self._right_combo.currentTextChanged.connect(self._on_right_changed)

        self._refresh_button = QtWidgets.QPushButton("Refresh Devices")
        self._refresh_button.setAccessibleName("Refresh camera device list")
        self._refresh_button.clicked.connect(self._refresh_devices)
        self._style_manager.style_button(self._refresh_button, "primary")

        device_layout.addRow("Left Camera", self._left_combo)
        device_layout.addRow("Right Camera", self._right_combo)
        device_layout.addRow("", self._refresh_button)
        device_group.setLayout(device_layout)

        preview_group = QtWidgets.QGroupBox("Camera Preview")
        preview_layout = QtWidgets.QHBoxLayout()
        apply_standard_layout(preview_layout, margins=(8, 8, 8, 8), spacing=12)

        self._left_preview = QtWidgets.QLabel("Left Camera Preview\n\nSelect a camera to see live preview")
        self._left_preview.setMinimumSize(200, 150)
        self._left_preview.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._left_preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        style_preview_surface(self._left_preview)
        self._left_preview.setScaledContents(False)

        self._right_preview = QtWidgets.QLabel("Right Camera Preview\n\nSelect a camera to see live preview")
        self._right_preview.setMinimumSize(200, 150)
        self._right_preview.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._right_preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        style_preview_surface(self._right_preview)
        self._right_preview.setScaledContents(False)

        preview_layout.addWidget(self._left_preview)
        preview_layout.addWidget(self._right_preview)
        preview_group.setLayout(preview_layout)

        self._status_label = QtWidgets.QLabel("Click Refresh Devices to begin.")
        style_status_label(self._status_label, "info")

        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)
        layout.addWidget(instructions)
        layout.addWidget(backend_group)
        layout.addWidget(device_group)
        layout.addWidget(preview_group, 1)
        layout.addWidget(self._status_label)
        self.setLayout(layout)

    def _switch_backend(self, backend: str) -> None:
        """Switch camera backend."""
        self._backend = backend
        self._left_combo.clear()
        self._right_combo.clear()
        self._left_serial = None
        self._right_serial = None
        self._set_status_message(
            f"Backend changed to {backend.upper()}. Refresh devices to discover cameras.",
            "info",
        )

    def _refresh_devices(self) -> None:
        """Discover available cameras in a background thread."""
        if getattr(self, "_discovery_worker", None) is not None:
            return
        self._set_status_message("Searching for cameras...", "info")
        self._refresh_button.setEnabled(False)
        self._show_loading(True)

        self._discovery_worker = CameraDiscoveryWorker(self._backend)
        self._discovery_worker.signals.finished_signal.connect(self._on_discovery_complete)
        self._discovery_worker.signals.error_signal.connect(self._on_discovery_error)
        QtCore.QThreadPool.globalInstance().start(self._discovery_worker)

    def _show_loading(self, visible: bool) -> None:
        """Show or hide the loading indicator."""
        if not hasattr(self, "_loading_frame"):
            from ui.themes.dialog_helpers import build_loading_indicator

            self._loading_frame, self._loading_label, self._loading_bar = build_loading_indicator(
                "Probing USB devices...", self
            )
            self._loading_bar.setRange(0, 0)
            self.layout().insertWidget(self.layout().count() - 1, self._loading_frame)
        self._loading_frame.setVisible(visible)

    def _on_discovery_complete(self, devices: list) -> None:
        """Handle device discovery results on the main thread."""
        self._show_loading(False)
        self._refresh_button.setEnabled(True)
        self._discovery_worker = None

        self._left_combo.clear()
        self._right_combo.clear()

        if not devices:
            self._set_status_message("No cameras found. Check connections and try again.", "error")
            return

        self._left_combo.addItem("(Select Camera)", None)
        self._right_combo.addItem("(Select Camera)", None)

        if self._backend == "opencv":
            for index in devices:
                label = f"Camera {index}"
                self._left_combo.addItem(label, str(index))
                self._right_combo.addItem(label, str(index))
        else:
            for device in devices:
                serial = device.get("serial", "")
                friendly_name = device.get("friendly_name", "")
                label = f"{serial} - {friendly_name}" if serial and friendly_name else (friendly_name or serial)
                self._left_combo.addItem(label, serial)
                self._right_combo.addItem(label, serial)

        self._set_status_message(
            f"Found {len(devices)} camera(s). Select left and right cameras above.",
            "success",
        )

    def _on_discovery_error(self, message: str) -> None:
        """Handle device discovery failure on the main thread."""
        self._show_loading(False)
        self._refresh_button.setEnabled(True)
        self._discovery_worker = None
        self._set_status_message(f"Error discovering cameras: {message}", "error")

    def _on_left_changed(self, text: str) -> None:
        """Handle left camera selection change."""
        if text and text != "(Select Camera)":
            self._left_serial = current_serial(self._left_combo)
            self._open_left_camera()
            self._update_status()
        else:
            self._close_left_camera()
            self._left_serial = None

    def _on_right_changed(self, text: str) -> None:
        """Handle right camera selection change."""
        if text and text != "(Select Camera)":
            self._right_serial = current_serial(self._right_combo)
            self._open_right_camera()
            self._update_status()
        else:
            self._close_right_camera()
            self._right_serial = None

    def _update_status(self) -> None:
        """Update status based on selections."""
        if self._left_serial and self._right_serial:
            if self._left_serial == self._right_serial:
                self._set_status_message("Left and right cameras must be different.", "warning")
            else:
                self._set_status_message("Both cameras selected. Click Next to continue.", "success")

    def validate(self) -> tuple[bool, str]:
        """Validate camera selections."""
        if not self._left_serial or self._left_serial == "(Select Camera)":
            return False, "Please select a left camera."
        if not self._right_serial or self._right_serial == "(Select Camera)":
            return False, "Please select a right camera."
        if self._left_serial == self._right_serial:
            return False, "Left and right cameras must be different."
        return True, ""

    def get_left_serial(self) -> Optional[str]:
        return self._left_serial

    def get_right_serial(self) -> Optional[str]:
        return self._right_serial

    def get_backend(self) -> str:
        return self._backend

    def on_enter(self) -> None:
        if self._preview_timer is not None and not self._preview_timer.isActive():
            self._preview_timer.start(33)
        if self._left_serial and self._left_camera is None:
            self._open_left_camera()
        if self._right_serial and self._right_camera is None:
            self._open_right_camera()
        if self._left_combo.count() == 0:
            self._refresh_devices()

    def on_exit(self) -> None:
        self._stop_resources()

    def _stop_resources(self) -> None:
        """Stop timers and close cameras — safe to call multiple times."""
        if self._preview_timer is not None:
            self._preview_timer.stop()
        self._close_left_camera()
        self._close_right_camera()

    def get_left_camera(self) -> Optional[str]:
        return self._left_serial

    def get_right_camera(self) -> Optional[str]:
        return self._right_serial

    def _setup_preview_timer(self) -> None:
        """Setup timer for camera preview updates."""
        self._preview_timer = QtCore.QTimer()
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_timer.start(33)

    def _open_left_camera(self) -> None:
        """Open and start previewing left camera."""
        self._close_left_camera()
        if not self._left_serial:
            return

        try:
            from configs.settings import load_config
            from pathlib import Path

            config = load_config(Path("configs/default.yaml"))
            width = config.camera.width
            height = config.camera.height
            fps = 30
            flip_left = config.camera.flip_left
            rotation_left = getattr(config.camera, "rotation_left", 0.0)

            if self._backend == "opencv":
                from capture.opencv_backend import OpenCVCamera

                camera = OpenCVCamera()
                camera.open(self._left_serial)
                camera.set_mode(width, height, fps, "YUYV", flip_180=flip_left, rotation_correction=rotation_left)
            else:
                from capture.uvc_backend import UvcCamera

                camera = UvcCamera()
                camera.open(self._left_serial)
                camera.set_mode(width, height, fps, "YUYV", flip_180=flip_left, rotation_correction=rotation_left)

            self._left_camera = camera
            self._left_preview.setText("Opening camera...")
        except Exception as exc:
            self._left_preview.setText(f"Error opening camera:\n{exc}")
            self._left_camera = None

    def _open_right_camera(self) -> None:
        """Open and start previewing right camera."""
        self._close_right_camera()
        if not self._right_serial:
            return

        try:
            from configs.settings import load_config
            from pathlib import Path

            config = load_config(Path("configs/default.yaml"))
            width = config.camera.width
            height = config.camera.height
            fps = 30
            flip_right = config.camera.flip_right
            rotation_right = getattr(config.camera, "rotation_right", 0.0)

            if self._backend == "opencv":
                from capture.opencv_backend import OpenCVCamera

                camera = OpenCVCamera()
                camera.open(self._right_serial)
                camera.set_mode(width, height, fps, "YUYV", flip_180=flip_right, rotation_correction=rotation_right)
            else:
                from capture.uvc_backend import UvcCamera

                camera = UvcCamera()
                camera.open(self._right_serial)
                camera.set_mode(width, height, fps, "YUYV", flip_180=flip_right, rotation_correction=rotation_right)

            self._right_camera = camera
            self._right_preview.setText("Opening camera...")
        except Exception as exc:
            self._right_preview.setText(f"Error opening camera:\n{exc}")
            self._right_camera = None

    def _close_left_camera(self) -> None:
        """Close left camera."""
        if self._left_camera is not None:
            try:
                self._left_camera.close()
            except Exception:
                pass
            self._left_camera = None
            self._left_preview.setText("Left Camera Preview")

    def _close_right_camera(self) -> None:
        """Close right camera."""
        if self._right_camera is not None:
            try:
                self._right_camera.close()
            except Exception:
                pass
            self._right_camera = None
            self._right_preview.setText("Right Camera Preview")

    def _update_preview(self) -> None:
        """Update camera preview displays."""
        if self._left_camera is not None:
            try:
                frame = self._left_camera.read_frame(timeout_ms=100)
                pixmap = self._frame_to_pixmap(frame.image)
                self._left_preview.setPixmap(pixmap)
            except Exception:
                pass

        if self._right_camera is not None:
            try:
                frame = self._right_camera.read_frame(timeout_ms=100)
                pixmap = self._frame_to_pixmap(frame.image)
                self._right_preview.setPixmap(pixmap)
            except Exception:
                pass

    def _frame_to_pixmap(self, image: np.ndarray) -> QtGui.QPixmap:
        """Convert frame to QPixmap with focus quality overlay."""
        from detect.utils import compute_focus_score

        focus_score = compute_focus_score(image)
        if focus_score >= 200:
            color = (46, 204, 113)
            status = "GOOD"
        elif focus_score >= 100:
            color = (243, 156, 18)
            status = "FAIR"
        else:
            color = (231, 76, 60)
            status = "POOR"

        if image.ndim == 2:
            display_img = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            display_img = image.copy()

        text = f"Focus: {focus_score:.0f} ({status})"
        cv2.putText(
            display_img,
            text,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
            cv2.LINE_AA,
        )

        height, width, channels = display_img.shape
        bytes_per_line = channels * width
        rgb_image = cv2.cvtColor(display_img, cv2.COLOR_BGR2RGB)
        qimage = QtGui.QImage(
            rgb_image.data,
            width,
            height,
            bytes_per_line,
            QtGui.QImage.Format_RGB888,
        )

        pixmap = QtGui.QPixmap.fromImage(qimage)
        return pixmap.scaled(
            self._left_preview.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
