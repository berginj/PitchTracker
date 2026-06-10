"""Session start dialog for pitcher selection and configuration."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from PySide6 import QtWidgets

from configs.app_state import load_state
from configs.settings import AppConfig
from ui.themes import (
    apply_standard_layout,
    ask_confirmation,
    build_dialog_header,
    build_notice,
    get_style_manager,
    polish_form_controls,
    show_message_dialog,
    style_dialog_button_box,
)


class SessionStartDialog(QtWidgets.QDialog):
    """Dialog for starting a new coaching session."""

    def __init__(
        self,
        config: AppConfig,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Start New Session")
        self.resize(540, 560)

        self._style_manager = get_style_manager()
        self._config = config
        self._pitcher_name = ""
        self._session_name = ""
        self._batter_height_in = config.strike_zone.batter_height_in
        self._ball_type = config.ball.type

        # Result values
        self.pitcher_name = ""
        self.session_name = ""
        self.batter_height_in = 0.0
        self.ball_type = ""
        self.left_serial = ""
        self.right_serial = ""

        self._build_ui()
        self._generate_session_name()

    def _build_ui(self) -> None:
        """Build dialog UI."""
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)
        layout.addWidget(
            build_dialog_header(
                "Start New Coaching Session",
                "Choose a pitcher, confirm both cameras, and set quick session defaults before recording.",
            )
        )
        layout.addWidget(self._build_pitcher_group())
        layout.addWidget(self._build_session_group())
        layout.addWidget(self._build_camera_group())
        layout.addWidget(self._build_settings_group())
        layout.addWidget(self._build_calibration_status())
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

        # Set logical tab order for keyboard navigation
        QtWidgets.QWidget.setTabOrder(self._pitcher_combo, self._new_pitcher_input)
        QtWidgets.QWidget.setTabOrder(self._new_pitcher_input, self._session_name_input)
        QtWidgets.QWidget.setTabOrder(self._session_name_input, self._left_camera_combo)
        QtWidgets.QWidget.setTabOrder(self._left_camera_combo, self._right_camera_combo)
        QtWidgets.QWidget.setTabOrder(self._right_camera_combo, self._batter_height_spin)
        QtWidgets.QWidget.setTabOrder(self._batter_height_spin, self._ball_type_combo)

    def _build_pitcher_group(self) -> QtWidgets.QGroupBox:
        """Build pitcher selection group."""
        group = QtWidgets.QGroupBox("Pitcher")

        saved_pitchers = self._load_saved_pitchers()

        self._pitcher_combo = QtWidgets.QComboBox()
        self._pitcher_combo.setAccessibleName("Pitcher")
        self._pitcher_combo.addItem("(Select Pitcher)")
        self._pitcher_combo.addItems(saved_pitchers)
        self._pitcher_combo.addItem("+ Add New Pitcher")
        self._pitcher_combo.currentTextChanged.connect(self._on_pitcher_changed)

        self._new_pitcher_input = QtWidgets.QLineEdit()
        self._new_pitcher_input.setAccessibleName("New Pitcher Name")
        self._new_pitcher_input.setPlaceholderText("Enter pitcher name")
        self._new_pitcher_input.hide()
        self._new_pitcher_input.textChanged.connect(self._on_new_pitcher_changed)

        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout, margins=(8, 8, 8, 8), spacing=10)
        layout.addWidget(QtWidgets.QLabel("Select Pitcher"))
        layout.addWidget(self._pitcher_combo)
        layout.addWidget(self._new_pitcher_input)
        group.setLayout(layout)
        return group

    def _build_session_group(self) -> QtWidgets.QGroupBox:
        """Build session name group."""
        group = QtWidgets.QGroupBox("Session Name")

        self._session_name_input = QtWidgets.QLineEdit()
        self._session_name_input.setAccessibleName("Session Name")
        self._session_name_input.textChanged.connect(self._on_session_name_changed)

        auto_button = QtWidgets.QPushButton("Auto-Generate")
        auto_button.setAccessibleName("Generate Session Name")
        auto_button.clicked.connect(self._generate_session_name)
        self._style_manager.style_button(auto_button, "ghost")

        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout, margins=(8, 8, 8, 8), spacing=10)
        layout.addWidget(QtWidgets.QLabel("Session Name"))

        name_layout = QtWidgets.QHBoxLayout()
        name_layout.setSpacing(10)
        name_layout.addWidget(self._session_name_input, 3)
        name_layout.addWidget(auto_button, 1)
        layout.addLayout(name_layout)

        group.setLayout(layout)
        return group

    def _build_camera_group(self) -> QtWidgets.QGroupBox:
        """Build camera selection group with saved camera defaults."""
        from ui.device_utils import (
            is_arducam_device,
            probe_opencv_indices,
            probe_uvc_devices,
        )

        group = QtWidgets.QGroupBox("Cameras")

        left_label = QtWidgets.QLabel("Left Camera")
        self._left_camera_combo = QtWidgets.QComboBox()
        self._left_camera_combo.setAccessibleName("Left Camera")

        right_label = QtWidgets.QLabel("Right Camera")
        self._right_camera_combo = QtWidgets.QComboBox()
        self._right_camera_combo.setAccessibleName("Right Camera")

        state = load_state()
        last_left = state.get("last_left_camera")
        last_right = state.get("last_right_camera")

        uvc_devices = probe_uvc_devices(use_cache=True)
        uvc_by_index = {i: dev for i, dev in enumerate(uvc_devices)}
        indices = probe_opencv_indices(max_index=10, use_cache=True)
        arducam_indices: list[int] = []

        if indices:
            for index in indices:
                friendly_name = None
                if index in uvc_by_index:
                    friendly_name = uvc_by_index[index].get("friendly_name", "")
                    if is_arducam_device(friendly_name):
                        arducam_indices.append(index)

                suffix_left = " (Last Used)" if str(index) == last_left else ""
                suffix_right = " (Last Used)" if str(index) == last_right else ""
                if friendly_name:
                    left_label_text = f"{friendly_name}{suffix_left}"
                    right_label_text = f"{friendly_name}{suffix_right}"
                else:
                    left_label_text = f"Camera {index}{suffix_left}"
                    right_label_text = f"Camera {index}{suffix_right}"

                self._left_camera_combo.addItem(left_label_text, str(index))
                self._right_camera_combo.addItem(right_label_text, str(index))
        else:
            self._left_camera_combo.addItem("No cameras found — check USB connections", "")
            self._right_camera_combo.addItem("No cameras found — check USB connections", "")

        if last_left:
            for i in range(self._left_camera_combo.count()):
                if self._left_camera_combo.itemData(i) == last_left:
                    self._left_camera_combo.setCurrentIndex(i)
                    break
        elif arducam_indices:
            first_arducam = str(arducam_indices[0])
            for i in range(self._left_camera_combo.count()):
                if self._left_camera_combo.itemData(i) == first_arducam:
                    self._left_camera_combo.setCurrentIndex(i)
                    break
        elif self._left_camera_combo.count() >= 2:
            self._left_camera_combo.setCurrentIndex(0)

        if last_right:
            for i in range(self._right_camera_combo.count()):
                if self._right_camera_combo.itemData(i) == last_right:
                    self._right_camera_combo.setCurrentIndex(i)
                    break
        elif len(arducam_indices) >= 2:
            second_arducam = str(arducam_indices[1])
            for i in range(self._right_camera_combo.count()):
                if self._right_camera_combo.itemData(i) == second_arducam:
                    self._right_camera_combo.setCurrentIndex(i)
                    break
        elif self._right_camera_combo.count() >= 2:
            self._right_camera_combo.setCurrentIndex(1)

        refresh_button = QtWidgets.QPushButton("Refresh Cameras")
        refresh_button.setAccessibleName("Refresh Camera List")
        refresh_button.clicked.connect(self._refresh_cameras)
        refresh_button.setToolTip("Refresh camera list if cameras are not showing correctly.")
        self._style_manager.style_button(refresh_button, "ghost")

        layout = QtWidgets.QGridLayout()
        apply_standard_layout(layout, margins=(8, 8, 8, 8), spacing=10)
        layout.addWidget(left_label, 0, 0)
        layout.addWidget(self._left_camera_combo, 0, 1)
        layout.addWidget(right_label, 1, 0)
        layout.addWidget(self._right_camera_combo, 1, 1)
        layout.addWidget(refresh_button, 2, 0, 1, 2)
        group.setLayout(layout)
        return group

    def _refresh_cameras(self) -> None:
        """Refresh camera list."""
        from ui.device_utils import clear_device_cache

        clear_device_cache()
        show_message_dialog(
            self,
            "Refresh Cameras",
            "Camera cache cleared. Close and reopen this dialog to see the updated list.",
            tone="info",
        )

    def _build_settings_group(self) -> QtWidgets.QGroupBox:
        """Build quick settings group."""
        group = QtWidgets.QGroupBox("Quick Settings")

        batter_label = QtWidgets.QLabel("Batter Height (inches)")
        self._batter_height_spin = QtWidgets.QDoubleSpinBox()
        self._batter_height_spin.setAccessibleName("Batter Height")
        self._batter_height_spin.setRange(48.0, 84.0)
        self._batter_height_spin.setValue(self._batter_height_in)
        self._batter_height_spin.setSuffix(" in")
        self._batter_height_spin.valueChanged.connect(self._on_batter_height_changed)

        ball_label = QtWidgets.QLabel("Ball Type")
        self._ball_type_combo = QtWidgets.QComboBox()
        self._ball_type_combo.setAccessibleName("Ball Type")
        self._ball_type_combo.addItems(["baseball", "softball"])
        self._ball_type_combo.setCurrentText(self._ball_type)
        self._ball_type_combo.currentTextChanged.connect(self._on_ball_type_changed)

        layout = QtWidgets.QGridLayout()
        apply_standard_layout(layout, margins=(8, 8, 8, 8), spacing=10)
        layout.addWidget(batter_label, 0, 0)
        layout.addWidget(self._batter_height_spin, 0, 1)
        layout.addWidget(ball_label, 1, 0)
        layout.addWidget(self._ball_type_combo, 1, 1)
        group.setLayout(layout)
        return group

    def _build_calibration_status(self) -> QtWidgets.QWidget:
        """Build calibration status indicator with quality metrics."""
        from calib.runtime_status import describe_runtime_calibration
        from calib.quick_calibrate import load_calibration_quality

        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout, margins=(0, 0, 0, 0), spacing=8)

        status = describe_runtime_calibration()
        calibration_file = Path("calibration/stereo_calibration.npz")
        has_calibration = status["mode"] == "full_matrix"
        quality = load_calibration_quality() if has_calibration else None

        if status["mode"] == "missing":
            notice, _ = build_notice(
                "No calibration found. Run the setup wizard before starting a production session.",
                tone="warning",
            )
            detail_label = QtWidgets.QLabel("You can continue, but measurements may be inaccurate.")
            self._style_manager.style_label(detail_label, "muted")
            layout.addWidget(notice)
            layout.addWidget(detail_label)
        elif status["mode"] == "scalar_fallback":
            notice, _ = build_notice(
                "Calibration is using simplified scalar fallback.",
                tone="warning",
            )
            detail_label = QtWidgets.QLabel(status["message"])
            self._style_manager.style_label(detail_label, "muted")
            layout.addWidget(notice)
            layout.addWidget(detail_label)
        elif status["mode"] == "invalid_matrix_file":
            notice, _ = build_notice(
                "Calibration file is invalid.",
                tone="error",
            )
            detail_label = QtWidgets.QLabel(status["message"])
            self._style_manager.style_label(detail_label, "muted")
            layout.addWidget(notice)
            layout.addWidget(detail_label)
        elif quality:
            rating = quality["rating"]
            rms = quality["rms_error_px"]
            description = quality["description"]
            tone = "success" if rating in {"EXCELLENT", "GOOD"} else ("warning" if rating == "ACCEPTABLE" else "error")

            notice, _ = build_notice(f"Calibration quality: {rating}", tone=tone)
            detail_label = QtWidgets.QLabel(f"RMS error: {rms:.3f} px. {description}")
            self._style_manager.style_label(detail_label, "muted")
            layout.addWidget(notice)
            layout.addWidget(detail_label)
        else:
            notice, _ = build_notice(
                "Calibration loaded. Quality metrics are not available for this file.",
                tone="info",
            )
            detail_label = QtWidgets.QLabel("Run a new calibration to capture quality diagnostics.")
            self._style_manager.style_label(detail_label, "muted")
            layout.addWidget(notice)
            layout.addWidget(detail_label)

        widget.setLayout(layout)
        return widget

    def _load_saved_pitchers(self) -> list[str]:
        """Load saved pitchers from pitcher profiles directory."""
        try:
            from analysis.pattern_detection.pitcher_profile import PitcherProfileManager

            profile_manager = PitcherProfileManager()
            saved_pitchers = profile_manager.list_profiles()
            if not saved_pitchers:
                return ["John Doe", "Jane Smith", "Mike Johnson"]
            return sorted(saved_pitchers)
        except Exception:
            return ["John Doe", "Jane Smith", "Mike Johnson"]

    def _generate_session_name(self) -> None:
        """Auto-generate session name with timestamp."""
        timestamp = time.strftime("%Y-%m-%d-%H%M%S")
        self._session_name = f"Practice-{timestamp}"
        self._session_name_input.setText(self._session_name)

    def _on_pitcher_changed(self, text: str) -> None:
        """Handle pitcher selection change."""
        if text == "+ Add New Pitcher":
            self._new_pitcher_input.show()
            self._new_pitcher_input.setFocus()
            self._pitcher_name = ""
        elif text == "(Select Pitcher)":
            self._new_pitcher_input.hide()
            self._pitcher_name = ""
        else:
            self._new_pitcher_input.hide()
            self._pitcher_name = text

    def _on_new_pitcher_changed(self, text: str) -> None:
        """Handle new pitcher name input."""
        self._pitcher_name = text

    def _on_session_name_changed(self, text: str) -> None:
        """Handle session name change."""
        self._session_name = text

    def _on_batter_height_changed(self, value: float) -> None:
        """Handle batter height change."""
        self._batter_height_in = value

    def _on_ball_type_changed(self, text: str) -> None:
        """Handle ball type change."""
        self._ball_type = text

    def _accept(self) -> None:
        """Validate and accept dialog."""
        if not self._pitcher_name:
            show_message_dialog(
                self,
                "Missing Pitcher",
                "Please select or enter a pitcher name.",
                tone="warning",
            )
            return

        if not self._session_name:
            show_message_dialog(
                self,
                "Missing Session Name",
                "Please enter a session name.",
                tone="warning",
            )
            return

        from calib.quick_calibrate import load_calibration_quality

        calibration_file = Path("calibration/stereo_calibration.npz")
        if not calibration_file.exists():
            if not ask_confirmation(
                self,
                "No Calibration",
                "No calibration was found. Session measurements may not work correctly.\n\nContinue anyway?",
                tone="warning",
            ):
                return
        else:
            quality = load_calibration_quality()
            if quality and quality["rating"] == "POOR":
                if not ask_confirmation(
                    self,
                    "Poor Calibration Quality",
                    f"Calibration quality is POOR (RMS: {quality['rms_error_px']:.3f} px)\n\n"
                    f"{quality['description']}\n\n"
                    "This may result in inaccurate measurements.\n"
                    "Re-calibrate for better results?\n\n"
                    "Continue anyway?",
                    tone="warning",
                ):
                    return

        left_serial = self._left_camera_combo.currentData()
        right_serial = self._right_camera_combo.currentData()
        if not left_serial or not right_serial:
            show_message_dialog(
                self,
                "Missing Cameras",
                "Please select both left and right cameras.",
                tone="warning",
            )
            return

        self.pitcher_name = self._pitcher_name
        self.session_name = self._session_name
        self.batter_height_in = self._batter_height_in
        self.ball_type = self._ball_type
        self.left_serial = left_serial
        self.right_serial = right_serial
        self.accept()
