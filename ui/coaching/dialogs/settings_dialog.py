"""Settings dialog for coaching app configuration."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets

from configs.app_state import load_state, save_state


class SettingsDialog(QtWidgets.QDialog):
    """Dialog for coaching app settings.

    Allows user to:
    - Change recording resolution
    - Swap left/right camera assignments
    - Configure camera indices
    """

    # Available resolution presets
    RESOLUTIONS = [
        ("640x480 @ 30fps (Low)", 640, 480, 30),
        ("1280x720 @ 30fps (Medium)", 1280, 720, 30),
        ("1920x1080 @ 30fps (High)", 1920, 1080, 30),
        ("1920x1080 @ 60fps (Very High)", 1920, 1080, 60),
    ]

    def __init__(
        self,
        current_width: int = 640,
        current_height: int = 480,
        current_fps: int = 30,
        current_left_camera: str = "0",
        current_right_camera: str = "1",
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Coaching App Settings")
        self.resize(500, 350)

        # Current settings
        self._current_width = current_width
        self._current_height = current_height
        self._current_fps = current_fps
        self._current_left = current_left_camera
        self._current_right = current_right_camera

        # Result values
        self.width = current_width
        self.height = current_height
        self.fps = current_fps
        self.left_camera = current_left_camera
        self.right_camera = current_right_camera
        self.settings_changed = False

        self._build_ui()

    def _build_ui(self) -> None:
        """Build dialog UI."""
        layout = QtWidgets.QVBoxLayout()

        # Title
        title = QtWidgets.QLabel("Coaching App Settings")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; padding: 10px;")
        layout.addWidget(title)

        # Resolution settings
        resolution_group = self._build_resolution_group()
        layout.addWidget(resolution_group)

        # Camera settings
        camera_group = self._build_camera_group()
        layout.addWidget(camera_group)

        # Warning about restarting
        warning = QtWidgets.QLabel(
            "⚠ Changing settings will restart the camera capture.\n"
            "Stop any active recording before changing settings."
        )
        warning.setStyleSheet("color: #FF9800; padding: 10px;")
        layout.addWidget(warning)

        layout.addStretch()

        # Buttons
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok
            | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        self.setLayout(layout)

    def _build_resolution_group(self) -> QtWidgets.QGroupBox:
        """Build resolution selection group."""
        group = QtWidgets.QGroupBox("Recording Resolution")

        self._resolution_combo = QtWidgets.QComboBox()

        # Add resolution options
        for label, width, height, fps in self.RESOLUTIONS:
            self._resolution_combo.addItem(label, (width, height, fps))

        # Select current resolution
        for i in range(self._resolution_combo.count()):
            width, height, fps = self._resolution_combo.itemData(i)
            if width == self._current_width and height == self._current_height and fps == self._current_fps:
                self._resolution_combo.setCurrentIndex(i)
                break

        # Resolution info
        info = QtWidgets.QLabel(
            "Higher resolutions provide better quality but require more disk space and CPU.\n"
            "Recommended: 640x480 for most coaching sessions."
        )
        info.setStyleSheet("color: #666; font-size: 9pt; font-style: italic;")
        info.setWordWrap(True)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel("Select Resolution:"))
        layout.addWidget(self._resolution_combo)
        layout.addWidget(info)

        group.setLayout(layout)
        return group

    def _build_camera_group(self) -> QtWidgets.QGroupBox:
        """Build camera assignment group."""
        from ui.device_utils import probe_opencv_indices

        group = QtWidgets.QGroupBox("Camera Assignment")

        # Get available cameras
        # Use max_index=8 to check more camera indices (0-7)
        indices = probe_opencv_indices(max_index=8, use_cache=False)

        # Left camera
        left_label = QtWidgets.QLabel("Left Camera:")
        self._left_camera_combo = QtWidgets.QComboBox()

        # Right camera
        right_label = QtWidgets.QLabel("Right Camera:")
        self._right_camera_combo = QtWidgets.QComboBox()

        if indices:
            for index in indices:
                self._left_camera_combo.addItem(f"Camera {index}", str(index))
                self._right_camera_combo.addItem(f"Camera {index}", str(index))

            # Select current cameras
            for i in range(self._left_camera_combo.count()):
                if self._left_camera_combo.itemData(i) == self._current_left:
                    self._left_camera_combo.setCurrentIndex(i)
                if self._right_camera_combo.itemData(i) == self._current_right:
                    self._right_camera_combo.setCurrentIndex(i)
        else:
            self._left_camera_combo.addItem("No cameras found", "")
            self._right_camera_combo.addItem("No cameras found", "")

        # Swap button
        swap_button = QtWidgets.QPushButton("↔ Swap Left/Right")
        swap_button.clicked.connect(self._swap_cameras)
        swap_button.setToolTip("Quickly swap left and right camera assignments")

        layout = QtWidgets.QGridLayout()
        layout.addWidget(left_label, 0, 0)
        layout.addWidget(self._left_camera_combo, 0, 1)
        layout.addWidget(right_label, 1, 0)
        layout.addWidget(self._right_camera_combo, 1, 1)
        layout.addWidget(swap_button, 2, 0, 1, 2)

        group.setLayout(layout)
        return group

    def _swap_cameras(self) -> None:
        """Swap left and right camera selections."""
        left_index = self._left_camera_combo.currentIndex()
        right_index = self._right_camera_combo.currentIndex()

        self._left_camera_combo.setCurrentIndex(right_index)
        self._right_camera_combo.setCurrentIndex(left_index)

    def _accept(self) -> None:
        """Validate and accept dialog."""
        # Get resolution
        width, height, fps = self._resolution_combo.currentData()

        # Get cameras
        left_camera = self._left_camera_combo.currentData()
        right_camera = self._right_camera_combo.currentData()

        if not left_camera or not right_camera:
            QtWidgets.QMessageBox.warning(
                self,
                "Missing Cameras",
                "Please select both left and right cameras.",
            )
            return

        if left_camera == right_camera:
            QtWidgets.QMessageBox.warning(
                self,
                "Same Camera Selected",
                "Left and right cameras must be different.",
            )
            return

        # Check if settings changed
        settings_changed = (
            width != self._current_width
            or height != self._current_height
            or fps != self._current_fps
            or left_camera != self._current_left
            or right_camera != self._current_right
        )

        # Set result values
        self.width = width
        self.height = height
        self.fps = fps
        self.left_camera = left_camera
        self.right_camera = right_camera
        self.settings_changed = settings_changed

        # Save to app state for persistence
        state = load_state()
        state["coaching_width"] = width
        state["coaching_height"] = height
        state["coaching_fps"] = fps
        state["last_left_camera"] = left_camera
        state["last_right_camera"] = right_camera
        save_state(state)

        self.accept()
