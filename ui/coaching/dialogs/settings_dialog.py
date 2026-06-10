"""Settings dialog for coaching app configuration."""

from __future__ import annotations

from typing import Optional

from PySide6 import QtWidgets

from configs.app_state import load_state, save_state
from ui.themes import (
    apply_standard_layout,
    build_dialog_header,
    build_notice,
    get_style_manager,
    polish_form_controls,
    show_message_dialog,
    style_dialog_button_box,
)


class SettingsDialog(QtWidgets.QDialog):
    """Dialog for coaching app settings."""

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
        self.resize(560, 560)

        self._style_manager = get_style_manager()
        self._current_width = current_width
        self._current_height = current_height
        self._current_fps = current_fps
        self._current_left = current_left_camera
        self._current_right = current_right_camera
        self._current_mound_distance = current_mound_distance
        self._current_ball_type = current_ball_type
        self._current_color_mode = current_color_mode

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
        apply_standard_layout(layout)

        layout.addWidget(
            build_dialog_header(
                "Coaching App Settings",
                "Adjust capture quality, camera assignments, and mound distance without leaving coaching mode.",
            )
        )
        layout.addWidget(self._build_resolution_group())
        layout.addWidget(self._build_camera_group())
        layout.addWidget(self._build_distance_group())

        warning_frame, _ = build_notice(
            "Changing capture settings restarts camera capture. Stop any active recording first.",
            tone="warning",
        )
        layout.addWidget(warning_frame)
        layout.addStretch()

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self._accept)
        button_box.rejected.connect(self.reject)
        style_dialog_button_box(
            button_box,
            primary=QtWidgets.QDialogButtonBox.StandardButton.Ok,
            ghost=(QtWidgets.QDialogButtonBox.StandardButton.Cancel,),
        )
        layout.addWidget(button_box)

        self.setLayout(layout)
        polish_form_controls(self)

        # Set logical tab order
        QtWidgets.QWidget.setTabOrder(self._resolution_combo, self._color_mode_checkbox)
        QtWidgets.QWidget.setTabOrder(self._color_mode_checkbox, self._left_camera_combo)
        QtWidgets.QWidget.setTabOrder(self._left_camera_combo, self._right_camera_combo)
        QtWidgets.QWidget.setTabOrder(self._right_camera_combo, self._custom_distance_spin)

    def _build_resolution_group(self) -> QtWidgets.QGroupBox:
        """Build resolution selection group."""
        group = QtWidgets.QGroupBox("Recording Resolution")

        self._resolution_combo = QtWidgets.QComboBox()
        self._resolution_combo.setAccessibleName("Resolution")
        for label, width, height, fps in self.RESOLUTIONS:
            self._resolution_combo.addItem(label, (width, height, fps))

        for i in range(self._resolution_combo.count()):
            width, height, fps = self._resolution_combo.itemData(i)
            if width == self._current_width and height == self._current_height and fps == self._current_fps:
                self._resolution_combo.setCurrentIndex(i)
                break

        self._color_mode_checkbox = QtWidgets.QCheckBox("Capture Color Video")
        self._color_mode_checkbox.setAccessibleName("Color Mode")
        self._color_mode_checkbox.setChecked(self._current_color_mode)
        self._color_mode_checkbox.setToolTip(
            "Enable to capture color video (YUYV format).\n"
            "Disable for grayscale capture.\n"
            "Color video requires substantially more disk space."
        )

        info_label = QtWidgets.QLabel(
            "Higher resolutions improve clarity but increase CPU load and storage usage. "
            "1280x720 @ 60fps is a good default for most sessions."
        )
        info_label.setWordWrap(True)
        self._style_manager.style_label(info_label, "muted")

        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout, margins=(8, 8, 8, 8), spacing=10)
        layout.addWidget(QtWidgets.QLabel("Select Resolution"))
        layout.addWidget(self._resolution_combo)
        layout.addWidget(self._color_mode_checkbox)
        layout.addWidget(info_label)
        group.setLayout(layout)
        return group

    def _build_camera_group(self) -> QtWidgets.QGroupBox:
        """Build camera assignment group."""
        from ui.device_utils import probe_opencv_indices

        group = QtWidgets.QGroupBox("Camera Assignment")

        indices = probe_opencv_indices(max_index=10, use_cache=True)

        left_label = QtWidgets.QLabel("Left Camera")
        self._left_camera_combo = QtWidgets.QComboBox()
        self._left_camera_combo.setAccessibleName("Left Camera")
        right_label = QtWidgets.QLabel("Right Camera")
        self._right_camera_combo = QtWidgets.QComboBox()
        self._right_camera_combo.setAccessibleName("Right Camera")

        if indices:
            for index in indices:
                self._left_camera_combo.addItem(f"Camera {index}", str(index))
                self._right_camera_combo.addItem(f"Camera {index}", str(index))

            for i in range(self._left_camera_combo.count()):
                if self._left_camera_combo.itemData(i) == self._current_left:
                    self._left_camera_combo.setCurrentIndex(i)
                if self._right_camera_combo.itemData(i) == self._current_right:
                    self._right_camera_combo.setCurrentIndex(i)
        else:
            self._left_camera_combo.addItem("No cameras found — check USB connections", "")
            self._right_camera_combo.addItem("No cameras found — check USB connections", "")

        swap_button = QtWidgets.QPushButton("Swap Left / Right")
        swap_button.setAccessibleName("Swap Cameras")
        swap_button.clicked.connect(self._swap_cameras)
        swap_button.setToolTip("Quickly swap left and right camera assignments.")
        self._style_manager.style_button(swap_button, "ghost")

        layout = QtWidgets.QGridLayout()
        apply_standard_layout(layout, margins=(8, 8, 8, 8), spacing=10)
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

        softball_label = QtWidgets.QLabel("Softball")
        self._style_manager.style_label(softball_label, "sectionTitle")
        baseball_label = QtWidgets.QLabel("Baseball")
        self._style_manager.style_label(baseball_label, "sectionTitle")

        softball_buttons = QtWidgets.QHBoxLayout()
        softball_buttons.setSpacing(10)
        softball_35_btn = QtWidgets.QPushButton("35 ft")
        softball_40_btn = QtWidgets.QPushButton("40 ft")
        softball_43_btn = QtWidgets.QPushButton("43 ft")
        softball_35_btn.clicked.connect(lambda: self._set_distance(35.0))
        softball_40_btn.clicked.connect(lambda: self._set_distance(40.0))
        softball_43_btn.clicked.connect(lambda: self._set_distance(43.0))
        for button in (softball_35_btn, softball_40_btn, softball_43_btn):
            self._style_manager.style_button(button, "ghost")
            softball_buttons.addWidget(button)

        baseball_buttons = QtWidgets.QHBoxLayout()
        baseball_buttons.setSpacing(10)
        baseball_40_btn = QtWidgets.QPushButton("40 ft (Youth)")
        baseball_50_btn = QtWidgets.QPushButton("50 ft (HS)")
        baseball_60_btn = QtWidgets.QPushButton("60.5 ft (MLB)")
        baseball_40_btn.clicked.connect(lambda: self._set_distance(40.0))
        baseball_50_btn.clicked.connect(lambda: self._set_distance(50.0))
        baseball_60_btn.clicked.connect(lambda: self._set_distance(60.5))
        for button in (baseball_40_btn, baseball_50_btn, baseball_60_btn):
            self._style_manager.style_button(button, "ghost")
            baseball_buttons.addWidget(button)

        current_label = QtWidgets.QLabel("Current Distance")
        self._distance_display = QtWidgets.QLabel(f"{self._current_mound_distance:.1f} ft")
        self._style_manager.style_label(self._distance_display, "metricAccent")

        custom_label = QtWidgets.QLabel("Custom")
        self._custom_distance_spin = QtWidgets.QDoubleSpinBox()
        self._custom_distance_spin.setAccessibleName("Custom Baseline Distance")
        self._custom_distance_spin.setRange(20.0, 100.0)
        self._custom_distance_spin.setValue(self._current_mound_distance)
        self._custom_distance_spin.setSuffix(" ft")
        self._custom_distance_spin.setSingleStep(0.5)
        self._custom_distance_spin.valueChanged.connect(self._set_distance)

        layout = QtWidgets.QGridLayout()
        apply_standard_layout(layout, margins=(8, 8, 8, 8), spacing=10)
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
        if abs(self._custom_distance_spin.value() - distance) > 1e-6:
            self._custom_distance_spin.setValue(distance)

    def _swap_cameras(self) -> None:
        """Swap left and right camera selections."""
        left_index = self._left_camera_combo.currentIndex()
        right_index = self._right_camera_combo.currentIndex()
        self._left_camera_combo.setCurrentIndex(right_index)
        self._right_camera_combo.setCurrentIndex(left_index)

    def _accept(self) -> None:
        """Validate and accept dialog."""
        width, height, fps = self._resolution_combo.currentData()
        left_camera = self._left_camera_combo.currentData()
        right_camera = self._right_camera_combo.currentData()

        if not left_camera or not right_camera:
            show_message_dialog(
                self,
                "Missing Cameras",
                "Please select both left and right cameras.",
                tone="warning",
            )
            return

        if left_camera == right_camera:
            show_message_dialog(
                self,
                "Same Camera Selected",
                "Left and right cameras must be different.",
                tone="warning",
            )
            return

        mound_distance = self._custom_distance_spin.value()
        color_mode = self._color_mode_checkbox.isChecked()

        settings_changed = (
            width != self._current_width
            or height != self._current_height
            or fps != self._current_fps
            or left_camera != self._current_left
            or right_camera != self._current_right
            or mound_distance != self._current_mound_distance
            or color_mode != self._current_color_mode
        )

        self.width = width
        self.height = height
        self.fps = fps
        self.left_camera = left_camera
        self.right_camera = right_camera
        self.mound_distance_ft = mound_distance
        self.color_mode = color_mode
        self.settings_changed = settings_changed

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
