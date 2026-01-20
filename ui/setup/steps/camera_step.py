"""Camera discovery and selection step."""

from __future__ import annotations

from typing import Optional

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from ui.device_utils import current_serial, probe_opencv_indices, probe_uvc_devices
from ui.setup.steps.base_step import BaseStep


class CameraStep(BaseStep):
    """Camera discovery, selection, and preview step.

    Allows user to:
    - Discover available cameras (UVC or OpenCV)
    - Select left and right cameras
    - Preview both camera feeds
    - Verify cameras are operational
    """

    def __init__(self, backend: str = "uvc"):
        super().__init__()
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

    def _build_ui(self) -> None:
        """Build camera selection UI."""
        # Instructions
        instructions = QtWidgets.QLabel(
            "<h2>Camera Setup</h2>"
            "<p>Connect both cameras and click 'Refresh Devices' to discover them.</p>"
            "<p>Select which camera should be 'Left' and which should be 'Right' based on your physical setup.</p>"
        )
        instructions.setWordWrap(True)

        # Backend selection
        backend_group = QtWidgets.QGroupBox("Camera Backend")
        backend_layout = QtWidgets.QHBoxLayout()

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

        backend_help = QtWidgets.QLabel(
            "If cameras fail with UVC, try OpenCV backend which uses simple camera indices (0, 1, 2...)"
        )
        backend_help.setStyleSheet("color: #666; font-size: 9pt; font-style: italic;")

        backend_vlayout = QtWidgets.QVBoxLayout()
        backend_vlayout.addLayout(backend_layout)
        backend_vlayout.addWidget(backend_help)
        backend_group.setLayout(backend_vlayout)

        # Device selection
        device_group = QtWidgets.QGroupBox("Camera Selection")
        device_layout = QtWidgets.QFormLayout()

        self._left_combo = QtWidgets.QComboBox()
        self._left_combo.setMinimumWidth(300)
        self._left_combo.currentTextChanged.connect(self._on_left_changed)

        self._right_combo = QtWidgets.QComboBox()
        self._right_combo.setMinimumWidth(300)
        self._right_combo.currentTextChanged.connect(self._on_right_changed)

        self._refresh_button = QtWidgets.QPushButton("Refresh Devices")
        self._refresh_button.clicked.connect(self._refresh_devices)

        device_layout.addRow("Left Camera:", self._left_combo)
        device_layout.addRow("Right Camera:", self._right_combo)
        device_layout.addRow("", self._refresh_button)

        device_group.setLayout(device_layout)

        # Preview section with live camera feeds
        preview_group = QtWidgets.QGroupBox("Camera Preview (with Focus Quality)")
        preview_layout = QtWidgets.QHBoxLayout()

        self._left_preview = QtWidgets.QLabel("Left Camera Preview\n\nSelect a camera to see live preview")
        self._left_preview.setMinimumSize(400, 300)
        self._left_preview.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._left_preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._left_preview.setStyleSheet("background-color: #2c3e50; color: white; font-size: 10pt;")
        self._left_preview.setScaledContents(False)

        self._right_preview = QtWidgets.QLabel("Right Camera Preview\n\nSelect a camera to see live preview")
        self._right_preview.setMinimumSize(400, 300)
        self._right_preview.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._right_preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._right_preview.setStyleSheet("background-color: #2c3e50; color: white; font-size: 10pt;")
        self._right_preview.setScaledContents(False)

        preview_layout.addWidget(self._left_preview)
        preview_layout.addWidget(self._right_preview)

        preview_group.setLayout(preview_layout)

        # Status
        self._status_label = QtWidgets.QLabel("Click 'Refresh Devices' to begin.")
        self._status_label.setStyleSheet("color: #666; font-style: italic;")

        # Main layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(instructions)
        layout.addWidget(backend_group)
        layout.addWidget(device_group)
        layout.addWidget(preview_group, 1)  # Preview takes most space
        layout.addWidget(self._status_label)

        self.setLayout(layout)

    def _switch_backend(self, backend: str) -> None:
        """Switch camera backend."""
        self._backend = backend
        # Clear current selections
        self._left_combo.clear()
        self._right_combo.clear()
        self._left_serial = None
        self._right_serial = None
        self._status_label.setText(f"Backend changed to {backend.upper()}. Click 'Refresh Devices' to discover cameras.")
        self._status_label.setStyleSheet("color: #666; font-style: italic;")

    def _refresh_devices(self) -> None:
        """Discover available cameras."""
        self._status_label.setText("Searching for cameras...")
        QtWidgets.QApplication.processEvents()

        # Clear current selections
        self._left_combo.clear()
        self._right_combo.clear()

        try:
            if self._backend == "opencv":
                # OpenCV backend - find indices
                indices = probe_opencv_indices(max_index=5)

                if not indices:
                    self._status_label.setText("⚠️ No cameras found. Check connections and try again.")
                    self._status_label.setStyleSheet("color: red; font-weight: bold;")
                    return

                # Add placeholder
                self._left_combo.addItem("(Select Camera)", None)
                self._right_combo.addItem("(Select Camera)", None)

                # Add camera indices with proper data
                for i in indices:
                    label = f"Camera {i}"
                    self._left_combo.addItem(label, str(i))
                    self._right_combo.addItem(label, str(i))

                self._status_label.setText(f"✓ Found {len(indices)} camera(s). Select left and right cameras above.")
                self._status_label.setStyleSheet("color: green;")
            else:
                # UVC backend - find devices with serial numbers
                devices = probe_uvc_devices()

                if not devices:
                    self._status_label.setText("⚠️ No cameras found. Check connections and try again.")
                    self._status_label.setStyleSheet("color: red; font-weight: bold;")
                    return

                # Add placeholder
                self._left_combo.addItem("(Select Camera)", None)
                self._right_combo.addItem("(Select Camera)", None)

                # Add UVC devices with proper data
                for device in devices:
                    serial = device.get("serial", "")
                    friendly_name = device.get("friendly_name", "")
                    label = f"{serial} - {friendly_name}" if serial and friendly_name else (friendly_name or serial)
                    self._left_combo.addItem(label, serial)
                    self._right_combo.addItem(label, serial)

                self._status_label.setText(f"✓ Found {len(devices)} camera(s). Select left and right cameras above.")
                self._status_label.setStyleSheet("color: green;")

        except Exception as e:
            self._status_label.setText(f"⚠️ Error discovering cameras: {e}")
            self._status_label.setStyleSheet("color: red; font-weight: bold;")

    def _on_left_changed(self, text: str) -> None:
        """Handle left camera selection change."""
        if text and text != "(Select Camera)":
            # Get the actual serial/identifier from combo data
            self._left_serial = current_serial(self._left_combo)
            self._open_left_camera()
            self._update_status()
        else:
            self._close_left_camera()
            self._left_serial = None

    def _on_right_changed(self, text: str) -> None:
        """Handle right camera selection change."""
        if text and text != "(Select Camera)":
            # Get the actual serial/identifier from combo data
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
                self._status_label.setText("⚠️ Warning: Left and right cameras must be different!")
                self._status_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                self._status_label.setText("✓ Both cameras selected. Click 'Next' to continue.")
                self._status_label.setStyleSheet("color: green;")

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
        """Get selected left camera serial/identifier."""
        return self._left_serial

    def get_right_serial(self) -> Optional[str]:
        """Get selected right camera serial/identifier."""
        return self._right_serial

    def get_backend(self) -> str:
        """Get camera backend type."""
        return self._backend

    def on_enter(self) -> None:
        """Called when step becomes active."""
        # Auto-refresh on first entry if no devices yet
        if self._left_combo.count() == 0:
            self._refresh_devices()

    def on_exit(self) -> None:
        """Called when leaving step."""
        # Stop camera previews and close cameras
        self._close_left_camera()
        self._close_right_camera()

    def get_left_camera(self) -> Optional[str]:
        """Get selected left camera identifier."""
        return self._left_serial

    def get_right_camera(self) -> Optional[str]:
        """Get selected right camera identifier."""
        return self._right_serial

    def _setup_preview_timer(self) -> None:
        """Setup timer for camera preview updates."""
        self._preview_timer = QtCore.QTimer()
        self._preview_timer.timeout.connect(self._update_preview)
        self._preview_timer.start(33)  # ~30 fps

    def _open_left_camera(self) -> None:
        """Open and start previewing left camera."""
        self._close_left_camera()  # Close existing if any

        if not self._left_serial:
            return

        try:
            if self._backend == "opencv":
                from capture.opencv_backend import OpenCVCamera
                camera = OpenCVCamera()
                camera.open(self._left_serial)
                camera.set_mode(640, 480, 30, "YUYV")
            else:
                from capture.uvc_backend import UvcCamera
                camera = UvcCamera()
                camera.open(self._left_serial)
                camera.set_mode(640, 480, 30, "YUYV")

            self._left_camera = camera
            self._left_preview.setText("Opening camera...")
        except Exception as e:
            self._left_preview.setText(f"Error opening camera:\n{str(e)}")
            self._left_camera = None

    def _open_right_camera(self) -> None:
        """Open and start previewing right camera."""
        self._close_right_camera()  # Close existing if any

        if not self._right_serial:
            return

        try:
            if self._backend == "opencv":
                from capture.opencv_backend import OpenCVCamera
                camera = OpenCVCamera()
                camera.open(self._right_serial)
                camera.set_mode(640, 480, 30, "YUYV")
            else:
                from capture.uvc_backend import UvcCamera
                camera = UvcCamera()
                camera.open(self._right_serial)
                camera.set_mode(640, 480, 30, "YUYV")

            self._right_camera = camera
            self._right_preview.setText("Opening camera...")
        except Exception as e:
            self._right_preview.setText(f"Error opening camera:\n{str(e)}")
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
        # Update left camera preview
        if self._left_camera is not None:
            try:
                frame = self._left_camera.read_frame(timeout_ms=100)
                pixmap = self._frame_to_pixmap(frame.image)
                self._left_preview.setPixmap(pixmap)
            except Exception as e:
                # Don't show errors on every frame - just skip
                pass

        # Update right camera preview
        if self._right_camera is not None:
            try:
                frame = self._right_camera.read_frame(timeout_ms=100)
                pixmap = self._frame_to_pixmap(frame.image)
                self._right_preview.setPixmap(pixmap)
            except Exception as e:
                # Don't show errors on every frame - just skip
                pass

    def _frame_to_pixmap(self, image: np.ndarray) -> QtGui.QPixmap:
        """Convert frame to QPixmap with focus quality overlay.

        Args:
            image: Camera frame (grayscale or BGR color)

        Returns:
            QPixmap ready for display with focus score overlay
        """
        from detect.utils import compute_focus_score

        # Compute focus score
        focus_score = compute_focus_score(image)

        # Determine color based on focus quality
        if focus_score >= 200:
            color = (46, 204, 113)  # Green
            status = "GOOD"
        elif focus_score >= 100:
            color = (243, 156, 18)  # Orange
            status = "FAIR"
        else:
            color = (231, 76, 60)  # Red
            status = "POOR"

        # Convert to BGR if grayscale
        if image.ndim == 2:
            display_img = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
        else:
            display_img = image.copy()

        # Add focus score overlay
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

        # Convert to QPixmap
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

        # Scale to fit preview label
        pixmap = QtGui.QPixmap.fromImage(qimage)
        return pixmap.scaled(
            self._left_preview.size(),
            QtCore.Qt.AspectRatioMode.KeepAspectRatio,
            QtCore.Qt.TransformationMode.SmoothTransformation,
        )
