"""Session start dialog for pitcher selection and configuration."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from configs.app_state import load_state
from configs.settings import AppConfig


class SessionStartDialog(QtWidgets.QDialog):
    """Dialog for starting a new coaching session.

    Allows user to:
    - Select pitcher from saved list
    - Set session name (auto-generated with timestamp)
    - Quick settings (batter height, ball type)
    - Verify calibration is loaded
    """

    def __init__(
        self,
        config: AppConfig,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Start New Session")
        self.resize(500, 400)

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

        # Title
        title = QtWidgets.QLabel("Start New Coaching Session")
        title.setStyleSheet("font-size: 16pt; font-weight: bold; padding: 10px;")
        layout.addWidget(title)

        # Pitcher selection
        pitcher_group = self._build_pitcher_group()
        layout.addWidget(pitcher_group)

        # Session name
        session_group = self._build_session_group()
        layout.addWidget(session_group)

        # Camera selection
        camera_group = self._build_camera_group()
        layout.addWidget(camera_group)

        # Quick settings
        settings_group = self._build_settings_group()
        layout.addWidget(settings_group)

        # Calibration status
        calibration_status = self._build_calibration_status()
        layout.addWidget(calibration_status)

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

    def _build_pitcher_group(self) -> QtWidgets.QGroupBox:
        """Build pitcher selection group."""
        group = QtWidgets.QGroupBox("Pitcher")

        # Load saved pitchers
        saved_pitchers = self._load_saved_pitchers()

        # Pitcher dropdown
        self._pitcher_combo = QtWidgets.QComboBox()
        self._pitcher_combo.addItem("(Select Pitcher)")
        self._pitcher_combo.addItems(saved_pitchers)
        self._pitcher_combo.addItem("+ Add New Pitcher")
        self._pitcher_combo.currentTextChanged.connect(self._on_pitcher_changed)

        # New pitcher name input (hidden by default)
        self._new_pitcher_input = QtWidgets.QLineEdit()
        self._new_pitcher_input.setPlaceholderText("Enter pitcher name")
        self._new_pitcher_input.hide()
        self._new_pitcher_input.textChanged.connect(self._on_new_pitcher_changed)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel("Select Pitcher:"))
        layout.addWidget(self._pitcher_combo)
        layout.addWidget(self._new_pitcher_input)

        group.setLayout(layout)
        return group

    def _build_session_group(self) -> QtWidgets.QGroupBox:
        """Build session name group."""
        group = QtWidgets.QGroupBox("Session Name")

        self._session_name_input = QtWidgets.QLineEdit()
        self._session_name_input.textChanged.connect(self._on_session_name_changed)

        # Auto-generate button
        auto_button = QtWidgets.QPushButton("Auto-Generate")
        auto_button.clicked.connect(self._generate_session_name)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel("Session Name:"))

        name_layout = QtWidgets.QHBoxLayout()
        name_layout.addWidget(self._session_name_input, 3)
        name_layout.addWidget(auto_button, 1)
        layout.addLayout(name_layout)

        group.setLayout(layout)
        return group

    def _build_camera_group(self) -> QtWidgets.QGroupBox:
        """Build camera selection group."""
        from ui.device_utils import probe_uvc_devices, probe_opencv_indices

        group = QtWidgets.QGroupBox("Cameras")

        # Left camera
        left_label = QtWidgets.QLabel("Left Camera:")
        self._left_camera_combo = QtWidgets.QComboBox()

        # Right camera
        right_label = QtWidgets.QLabel("Right Camera:")
        self._right_camera_combo = QtWidgets.QComboBox()

        # Populate cameras (try UVC first, fallback to OpenCV)
        devices = probe_uvc_devices()
        if devices:
            for device in devices:
                label = f"{device['serial']} - {device['friendly_name']}"
                self._left_camera_combo.addItem(label, device["serial"])
                self._right_camera_combo.addItem(label, device["serial"])
        else:
            # Fallback to OpenCV indices
            indices = probe_opencv_indices()
            for index in indices:
                label = f"Camera {index}"
                self._left_camera_combo.addItem(label, str(index))
                self._right_camera_combo.addItem(label, str(index))

        # Load last used cameras from app state and pre-select them
        state = load_state()
        last_left = state.get("last_left_camera")
        last_right = state.get("last_right_camera")

        if last_left:
            # Find and select the last left camera by serial
            for i in range(self._left_camera_combo.count()):
                if self._left_camera_combo.itemData(i) == last_left:
                    self._left_camera_combo.setCurrentIndex(i)
                    break
        elif len(devices) >= 2 or len(probe_opencv_indices()) >= 2:
            # Fallback: select first camera if no saved state
            self._left_camera_combo.setCurrentIndex(0)

        if last_right:
            # Find and select the last right camera by serial
            for i in range(self._right_camera_combo.count()):
                if self._right_camera_combo.itemData(i) == last_right:
                    self._right_camera_combo.setCurrentIndex(i)
                    break
        elif len(devices) >= 2 or len(probe_opencv_indices()) >= 2:
            # Fallback: select second camera if no saved state
            self._right_camera_combo.setCurrentIndex(1)

        layout = QtWidgets.QGridLayout()
        layout.addWidget(left_label, 0, 0)
        layout.addWidget(self._left_camera_combo, 0, 1)
        layout.addWidget(right_label, 1, 0)
        layout.addWidget(self._right_camera_combo, 1, 1)

        group.setLayout(layout)
        return group

    def _build_settings_group(self) -> QtWidgets.QGroupBox:
        """Build quick settings group."""
        group = QtWidgets.QGroupBox("Quick Settings")

        # Batter height
        batter_label = QtWidgets.QLabel("Batter Height (inches):")
        self._batter_height_spin = QtWidgets.QDoubleSpinBox()
        self._batter_height_spin.setRange(48.0, 84.0)
        self._batter_height_spin.setValue(self._batter_height_in)
        self._batter_height_spin.setSuffix(' in')
        self._batter_height_spin.valueChanged.connect(self._on_batter_height_changed)

        # Ball type
        ball_label = QtWidgets.QLabel("Ball Type:")
        self._ball_type_combo = QtWidgets.QComboBox()
        self._ball_type_combo.addItems(["baseball", "softball"])
        self._ball_type_combo.setCurrentText(self._ball_type)
        self._ball_type_combo.currentTextChanged.connect(self._on_ball_type_changed)

        layout = QtWidgets.QGridLayout()
        layout.addWidget(batter_label, 0, 0)
        layout.addWidget(self._batter_height_spin, 0, 1)
        layout.addWidget(ball_label, 1, 0)
        layout.addWidget(self._ball_type_combo, 1, 1)

        group.setLayout(layout)
        return group

    def _build_calibration_status(self) -> QtWidgets.QWidget:
        """Build calibration status indicator with quality metrics."""
        from calib.quick_calibrate import load_calibration_quality

        widget = QtWidgets.QWidget()

        # Check if calibration exists and load quality
        calibration_file = Path("calibration/stereo_calibration.npz")
        has_calibration = calibration_file.exists()
        quality = load_calibration_quality() if has_calibration else None

        if not has_calibration:
            icon = "⚠"
            color = "#FF9800"
            message = "No calibration found"
            label = QtWidgets.QLabel(f"{icon} {message}")
            label.setStyleSheet(f"color: {color}; font-weight: bold; padding: 5px;")
            help_label = QtWidgets.QLabel("Run Setup Wizard first to calibrate the system.")
            help_label.setStyleSheet("color: #666; font-style: italic;")

            layout = QtWidgets.QVBoxLayout()
            layout.addWidget(label)
            layout.addWidget(help_label)
        elif quality:
            # Show quality rating with appropriate color
            rating = quality["rating"]
            rms = quality["rms_error_px"]
            description = quality["description"]

            if rating == "EXCELLENT":
                icon = "🟢"
                color = "#4CAF50"
            elif rating == "GOOD":
                icon = "🟢"
                color = "#4CAF50"
            elif rating == "ACCEPTABLE":
                icon = "🟡"
                color = "#FF9800"
            else:  # POOR
                icon = "🔴"
                color = "#F44336"

            label = QtWidgets.QLabel(f"{icon} Calibration: {rating}")
            label.setStyleSheet(f"color: {color}; font-weight: bold; padding: 5px;")

            detail_label = QtWidgets.QLabel(f"RMS Error: {rms:.3f} px - {description}")
            detail_label.setStyleSheet("color: #666; font-size: 10pt;")

            layout = QtWidgets.QVBoxLayout()
            layout.addWidget(label)
            layout.addWidget(detail_label)
        else:
            # Old calibration without quality metrics
            icon = "✓"
            color = "#4CAF50"
            message = "Calibration loaded (quality unknown)"
            label = QtWidgets.QLabel(f"{icon} {message}")
            label.setStyleSheet(f"color: {color}; font-weight: bold; padding: 5px;")

            help_label = QtWidgets.QLabel("Re-calibrate to get quality metrics.")
            help_label.setStyleSheet("color: #666; font-style: italic;")

            layout = QtWidgets.QVBoxLayout()
            layout.addWidget(label)
            layout.addWidget(help_label)

        widget.setLayout(layout)
        return widget

    def _load_saved_pitchers(self) -> list[str]:
        """Load saved pitchers from data directory."""
        # TODO: Load from actual pitcher database/file
        # For now, return sample list
        return [
            "John Doe",
            "Jane Smith",
            "Mike Johnson",
        ]

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
        # Validate pitcher
        if not self._pitcher_name:
            QtWidgets.QMessageBox.warning(
                self,
                "Missing Pitcher",
                "Please select or enter a pitcher name.",
            )
            return

        # Validate session name
        if not self._session_name:
            QtWidgets.QMessageBox.warning(
                self,
                "Missing Session Name",
                "Please enter a session name.",
            )
            return

        # Check calibration quality
        from calib.quick_calibrate import load_calibration_quality

        calibration_file = Path("calibration/stereo_calibration.npz")
        if not calibration_file.exists():
            reply = QtWidgets.QMessageBox.question(
                self,
                "No Calibration",
                "No calibration found. Session may not work correctly.\n\n"
                "Continue anyway?",
                QtWidgets.QMessageBox.StandardButton.Yes
                | QtWidgets.QMessageBox.StandardButton.No,
            )
            if reply == QtWidgets.QMessageBox.StandardButton.No:
                return
        else:
            # Check calibration quality
            quality = load_calibration_quality()
            if quality and quality["rating"] == "POOR":
                reply = QtWidgets.QMessageBox.warning(
                    self,
                    "Poor Calibration Quality",
                    f"Calibration quality is POOR (RMS: {quality['rms_error_px']:.3f} px)\n\n"
                    f"{quality['description']}\n\n"
                    "This may result in inaccurate measurements.\n"
                    "Re-calibrate for better results?\n\n"
                    "Continue anyway?",
                    QtWidgets.QMessageBox.StandardButton.Yes
                    | QtWidgets.QMessageBox.StandardButton.No,
                )
                if reply == QtWidgets.QMessageBox.StandardButton.No:
                    return

        # Get camera serials
        left_serial = self._left_camera_combo.currentData()
        right_serial = self._right_camera_combo.currentData()

        if not left_serial or not right_serial:
            QtWidgets.QMessageBox.warning(
                self,
                "Missing Cameras",
                "Please select both left and right cameras.",
            )
            return

        # Set result values
        self.pitcher_name = self._pitcher_name
        self.session_name = self._session_name
        self.batter_height_in = self._batter_height_in
        self.ball_type = self._ball_type
        self.left_serial = left_serial
        self.right_serial = right_serial

        self.accept()
