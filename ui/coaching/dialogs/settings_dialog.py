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
        ("1280x720 @ 60fps (High)", 1280, 720, 60),
        ("1920x1080 @ 30fps (Very High)", 1920, 1080, 30),
        ("1920x1080 @ 60fps (Ultra)", 1920, 1080, 60),
    ]

    def __init__(
        self,
        current_width: int = 640,
        current_height: int = 480,
        current_fps: int = 30,
        current_left_camera: str = "0",
        current_right_camera: str = "1",
        current_mound_distance: float = 50.0,
        current_ball_type: str = "baseball",
        current_color_mode: bool = True,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Coaching App Settings")
        self.resize(550, 500)

        # Current settings
        self._current_width = current_width
        self._current_height = current_height
        self._current_fps = current_fps
        self._current_left = current_left_camera
        self._current_right = current_right_camera
        self._current_mound_distance = current_mound_distance
        self._current_ball_type = current_ball_type
        self._current_color_mode = current_color_mode

        # Result values
        self.width = current_width
        self.height = current_height
        self.fps = current_fps
        self.left_camera = current_left_camera
        self.right_camera = current_right_camera
        self.mound_distance_ft = current_mound_distance
        self.color_mode = current_color_mode
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

        # Mound distance settings
        distance_group = self._build_distance_group()
        layout.addWidget(distance_group)

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

        # Color mode checkbox
        self._color_mode_checkbox = QtWidgets.QCheckBox("Capture Color Video")
        self._color_mode_checkbox.setChecked(self._current_color_mode)
        self._color_mode_checkbox.setToolTip(
            "Enable to capture color video (YUYV format)\n"
            "Disable for grayscale (GRAY8 format)\n"
            "Note: Color video requires ~3x more disk space"
        )

        # Resolution info
        info = QtWidgets.QLabel(
            "Higher resolutions provide better quality but require more disk space and CPU.\n"
            "Recommended: 1280x720 @ 60fps for most coaching sessions."
        )
        info.setStyleSheet("color: #666; font-size: 9pt; font-style: italic;")
        info.setWordWrap(True)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel("Select Resolution:"))
        layout.addWidget(self._resolution_combo)
        layout.addWidget(self._color_mode_checkbox)
        layout.addWidget(info)

        group.setLayout(layout)
        return group

    def _build_camera_group(self) -> QtWidgets.QGroupBox:
        """Build camera assignment group."""
        from ui.device_utils import probe_opencv_indices

        group = QtWidgets.QGroupBox("Camera Assignment")

        # Get available cameras
        # Use max_index=10 to check more camera indices (0-9)
        # USE CACHE for faster settings dialog opening
        indices = probe_opencv_indices(max_index=10, use_cache=True)

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

    def _build_distance_group(self) -> QtWidgets.QGroupBox:
        """Build mound distance preset group."""
        group = QtWidgets.QGroupBox("Plate-to-Mound Distance")

        # Distance presets for softball and baseball
        softball_label = QtWidgets.QLabel("Softball:")
        softball_label.setStyleSheet("font-weight: bold;")

        softball_buttons = QtWidgets.QHBoxLayout()
        softball_35_btn = QtWidgets.QPushButton("35 ft")
        softball_40_btn = QtWidgets.QPushButton("40 ft")
        softball_43_btn = QtWidgets.QPushButton("43 ft")

        softball_35_btn.clicked.connect(lambda: self._set_distance(35.0))
        softball_40_btn.clicked.connect(lambda: self._set_distance(40.0))
        softball_43_btn.clicked.connect(lambda: self._set_distance(43.0))

        softball_buttons.addWidget(softball_35_btn)
        softball_buttons.addWidget(softball_40_btn)
        softball_buttons.addWidget(softball_43_btn)

        baseball_label = QtWidgets.QLabel("Baseball:")
        baseball_label.setStyleSheet("font-weight: bold;")

        baseball_buttons = QtWidgets.QHBoxLayout()
        baseball_40_btn = QtWidgets.QPushButton("40 ft (Youth)")
        baseball_50_btn = QtWidgets.QPushButton("50 ft (HS)")
        baseball_60_btn = QtWidgets.QPushButton("60.5 ft (MLB)")

        baseball_40_btn.clicked.connect(lambda: self._set_distance(40.0))
        baseball_50_btn.clicked.connect(lambda: self._set_distance(50.0))
        baseball_60_btn.clicked.connect(lambda: self._set_distance(60.5))

        baseball_buttons.addWidget(baseball_40_btn)
        baseball_buttons.addWidget(baseball_50_btn)
        baseball_buttons.addWidget(baseball_60_btn)

        # Current distance display
        current_label = QtWidgets.QLabel("Current Distance:")
        self._distance_display = QtWidgets.QLabel(f"{self._current_mound_distance:.1f} ft")
        self._distance_display.setStyleSheet("font-weight: bold; font-size: 12pt; color: #2196F3;")

        # Custom distance input
        custom_label = QtWidgets.QLabel("Custom:")
        self._custom_distance_spin = QtWidgets.QDoubleSpinBox()
        self._custom_distance_spin.setRange(20.0, 100.0)
        self._custom_distance_spin.setValue(self._current_mound_distance)
        self._custom_distance_spin.setSuffix(' ft')
        self._custom_distance_spin.setSingleStep(0.5)
        self._custom_distance_spin.valueChanged.connect(self._set_distance)

        layout = QtWidgets.QGridLayout()
        layout.addWidget(softball_label, 0, 0)
        layout.addLayout(softball_buttons, 0, 1, 1, 2)
        layout.addWidget(baseball_label, 1, 0)
        layout.addLayout(baseball_buttons, 1, 1, 1, 2)
        layout.addWidget(current_label, 2, 0)
        layout.addWidget(self._distance_display, 2, 1)
        layout.addWidget(custom_label, 3, 0)
        layout.addWidget(self._custom_distance_spin, 3, 1)

        group.setLayout(layout)
        return group

    def _set_distance(self, distance: float) -> None:
        """Update distance display and spinbox."""
        self._distance_display.setText(f"{distance:.1f} ft")
        self._custom_distance_spin.setValue(distance)

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

        # Get mound distance
        mound_distance = self._custom_distance_spin.value()

        # Get color mode
        color_mode = self._color_mode_checkbox.isChecked()

        # Check if settings changed
        settings_changed = (
            width != self._current_width
            or height != self._current_height
            or fps != self._current_fps
            or left_camera != self._current_left
            or right_camera != self._current_right
            or mound_distance != self._current_mound_distance
            or color_mode != self._current_color_mode
        )

        # Set result values
        self.width = width
        self.height = height
        self.fps = fps
        self.left_camera = left_camera
        self.right_camera = right_camera
        self.mound_distance_ft = mound_distance
        self.color_mode = color_mode
        self.settings_changed = settings_changed

        # Save to app state for persistence
        state = load_state()
        state["coaching_width"] = width
        state["coaching_height"] = height
        state["coaching_fps"] = fps
        state["last_left_camera"] = left_camera
        state["last_right_camera"] = right_camera
        state["mound_distance_ft"] = mound_distance
        state["coaching_color_mode"] = color_mode
        save_state(state)

        self.accept()
