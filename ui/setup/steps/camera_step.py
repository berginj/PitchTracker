"""Camera discovery and selection step."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtWidgets

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

        self._build_ui()

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

        # Preview section (placeholder for now)
        preview_group = QtWidgets.QGroupBox("Camera Preview")
        preview_layout = QtWidgets.QHBoxLayout()

        self._left_preview = QtWidgets.QLabel("Left Camera Preview")
        self._left_preview.setMinimumSize(400, 300)
        self._left_preview.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._left_preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._left_preview.setStyleSheet("background-color: #f0f0f0;")

        self._right_preview = QtWidgets.QLabel("Right Camera Preview")
        self._right_preview.setMinimumSize(400, 300)
        self._right_preview.setFrameStyle(QtWidgets.QFrame.Shape.Box)
        self._right_preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._right_preview.setStyleSheet("background-color: #f0f0f0;")

        preview_layout.addWidget(self._left_preview)
        preview_layout.addWidget(self._right_preview)

        preview_group.setLayout(preview_layout)

        # Status
        self._status_label = QtWidgets.QLabel("Click 'Refresh Devices' to begin.")
        self._status_label.setStyleSheet("color: #666; font-style: italic;")

        # Main layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(instructions)
        layout.addWidget(device_group)
        layout.addWidget(preview_group, 1)  # Preview takes most space
        layout.addWidget(self._status_label)

        self.setLayout(layout)

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
            self._left_preview.setText(f"Left Camera:\n{text}\n\n(Preview not yet implemented)")
            self._update_status()

    def _on_right_changed(self, text: str) -> None:
        """Handle right camera selection change."""
        if text and text != "(Select Camera)":
            # Get the actual serial/identifier from combo data
            self._right_serial = current_serial(self._right_combo)
            self._right_preview.setText(f"Right Camera:\n{text}\n\n(Preview not yet implemented)")
            self._update_status()

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
        # Stop any camera previews (when implemented)
        pass

    def get_left_camera(self) -> Optional[str]:
        """Get selected left camera identifier."""
        return self._left_serial

    def get_right_camera(self) -> Optional[str]:
        """Get selected right camera identifier."""
        return self._right_serial
