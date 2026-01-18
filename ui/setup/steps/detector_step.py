"""Step 4: Detector Tuning - Test and validate detection settings."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from configs.settings import load_config
from ui.setup.steps.base_step import BaseStep


class DetectorStep(BaseStep):
    """Step 4: Detector tuning and validation.

    Workflow:
    1. Show current detector configuration
    2. Provide test button to verify detection works
    3. Allow user to switch between classical and ML detection
    4. Display basic statistics
    """

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._config_path = Path("configs/default.yaml")
        self._config = load_config(self._config_path)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build detector configuration UI."""
        layout = QtWidgets.QVBoxLayout()

        # Instructions
        instructions = QtWidgets.QLabel(
            "Detector Configuration:\n\n"
            "The system is configured to detect baseballs using either:\n"
            "• Classical detection (blob detection with thresholds)\n"
            "• ML detection (trained neural network model)\n\n"
            "The detector settings can be tuned in the Coaching App during live sessions."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("font-size: 11pt; padding: 10px; background-color: #e3f2fd; border-radius: 5px;")
        layout.addWidget(instructions)

        # Current configuration display
        config_group = self._build_config_display()
        layout.addWidget(config_group)

        # Detection mode selection
        mode_group = self._build_mode_selection()
        layout.addWidget(mode_group)

        # Ball type selection group
        ball_type_group = self._build_ball_type_selection()
        layout.addWidget(ball_type_group)

        # Status/Tips
        tips_group = QtWidgets.QGroupBox("Tips")
        tips_text = QtWidgets.QLabel(
            "• Classical detection works best with consistent lighting\n"
            "• ML detection is more robust but requires a trained model\n"
            "• Detection thresholds can be adjusted during coaching sessions\n"
            "• The Coaching App provides real-time detection feedback"
        )
        tips_text.setWordWrap(True)
        tips_layout = QtWidgets.QVBoxLayout()
        tips_layout.addWidget(tips_text)
        tips_group.setLayout(tips_layout)
        layout.addWidget(tips_group)

        layout.addStretch()

        self.setLayout(layout)

    def _build_config_display(self) -> QtWidgets.QGroupBox:
        """Build current configuration display."""
        group = QtWidgets.QGroupBox("Current Configuration")

        # Detector mode
        mode_label = QtWidgets.QLabel("Detection Mode:")
        mode_label.setStyleSheet("font-weight: bold;")

        detector_config = self._config.detector
        mode = detector_config.type
        self._mode_value = QtWidgets.QLabel(mode.upper() if mode else "CLASSICAL")
        self._mode_value.setStyleSheet("font-size: 12pt; color: #2196F3;")

        # Ball type
        ball_label = QtWidgets.QLabel("Ball Type:")
        ball_label.setStyleSheet("font-weight: bold;")

        ball_type = self._config.ball.type
        self._ball_value = QtWidgets.QLabel(ball_type.upper() if ball_type else "BASEBALL")
        self._ball_value.setStyleSheet("font-size: 12pt; color: #2196F3;")

        # Layout
        grid = QtWidgets.QGridLayout()
        grid.addWidget(mode_label, 0, 0)
        grid.addWidget(self._mode_value, 0, 1)
        grid.addWidget(ball_label, 1, 0)
        grid.addWidget(self._ball_value, 1, 1)
        grid.setColumnStretch(1, 1)

        group.setLayout(grid)
        return group

    def _build_mode_selection(self) -> QtWidgets.QGroupBox:
        """Build detection mode selection."""
        group = QtWidgets.QGroupBox("Detection Mode (Optional)")

        # Mode selection
        self._classical_radio = QtWidgets.QRadioButton("Classical (Blob Detection)")
        self._ml_radio = QtWidgets.QRadioButton("ML (Neural Network)")

        # Set current mode
        current_mode = self._config.detector.type
        if current_mode == "ml":
            self._ml_radio.setChecked(True)
        else:
            self._classical_radio.setChecked(True)

        # Info labels
        classical_info = QtWidgets.QLabel("  ↳ Fast, good for controlled environments")
        classical_info.setStyleSheet("color: #666; font-size: 9pt;")

        ml_info = QtWidgets.QLabel("  ↳ Robust, works in varied conditions (requires model)")
        ml_info.setStyleSheet("color: #666; font-size: 9pt;")

        # Apply button
        apply_button = QtWidgets.QPushButton("Apply Mode")
        apply_button.clicked.connect(self._apply_mode)

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._classical_radio)
        layout.addWidget(classical_info)
        layout.addWidget(self._ml_radio)
        layout.addWidget(ml_info)
        layout.addWidget(apply_button)

        group.setLayout(layout)
        return group

    def _build_ball_type_selection(self) -> QtWidgets.QGroupBox:
        """Build ball type selection."""
        group = QtWidgets.QGroupBox("Ball Type (Required)")

        # Ball type selection
        self._baseball_radio = QtWidgets.QRadioButton("Baseball")
        self._softball_radio = QtWidgets.QRadioButton("Softball")

        # Set current ball type
        current_ball_type = self._config.ball.type
        if current_ball_type == "softball":
            self._softball_radio.setChecked(True)
        else:
            self._baseball_radio.setChecked(True)

        # Info labels
        baseball_info = QtWidgets.QLabel("  ↳ Standard baseball (2.9\" diameter)")
        baseball_info.setStyleSheet("color: #666; font-size: 9pt;")

        softball_info = QtWidgets.QLabel("  ↳ Softball (3.5-3.8\" diameter)")
        softball_info.setStyleSheet("color: #666; font-size: 9pt;")

        # Apply button
        apply_ball_button = QtWidgets.QPushButton("Apply Ball Type")
        apply_ball_button.clicked.connect(self._apply_ball_type)

        # Layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._baseball_radio)
        layout.addWidget(baseball_info)
        layout.addWidget(self._softball_radio)
        layout.addWidget(softball_info)
        layout.addWidget(apply_ball_button)

        group.setLayout(layout)
        return group

    def get_title(self) -> str:
        """Return step title."""
        return "Detector Tuning"

    def validate(self) -> tuple[bool, str]:
        """Validate detector configuration.

        Detector step is always valid - configuration is optional.
        """
        return True, ""

    def is_skippable(self) -> bool:
        """Detector tuning can always be skipped."""
        return True

    def on_enter(self) -> None:
        """Called when step becomes active."""
        # Reload config to show latest settings
        self._config = load_config(self._config_path)
        self._update_display()

    def on_exit(self) -> None:
        """Called when leaving step."""
        pass

    def _update_display(self) -> None:
        """Update configuration display."""
        mode = self._config.detector.type
        self._mode_value.setText(mode.upper() if mode else "CLASSICAL")

        ball_type = self._config.ball.type
        self._ball_value.setText(ball_type.upper() if ball_type else "BASEBALL")

    def _apply_mode(self) -> None:
        """Apply selected detection mode."""
        # Determine selected mode
        if self._ml_radio.isChecked():
            new_mode = "ml"
        else:
            new_mode = "classical"

        try:
            # Update config file
            import yaml

            data = yaml.safe_load(self._config_path.read_text())
            data.setdefault("detector", {})
            data["detector"]["type"] = new_mode

            self._config_path.write_text(yaml.safe_dump(data, sort_keys=False))

            # Reload config
            self._config = load_config(self._config_path)
            self._update_display()

            QtWidgets.QMessageBox.information(
                self,
                "Mode Applied",
                f"Detection mode set to: {new_mode.upper()}\n\n"
                "The new mode will be used in coaching sessions.",
            )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Apply Error",
                f"Failed to apply detection mode:\n{str(e)}",
            )

    def _apply_ball_type(self) -> None:
        """Apply selected ball type."""
        # Determine selected ball type
        if self._softball_radio.isChecked():
            new_ball_type = "softball"
        else:
            new_ball_type = "baseball"

        try:
            # Update config file
            import yaml

            data = yaml.safe_load(self._config_path.read_text())
            data.setdefault("ball", {})
            data["ball"]["type"] = new_ball_type

            self._config_path.write_text(yaml.safe_dump(data, sort_keys=False))

            # Reload config
            self._config = load_config(self._config_path)
            self._update_display()

            QtWidgets.QMessageBox.information(
                self,
                "Ball Type Applied",
                f"Ball type set to: {new_ball_type.upper()}\n\n"
                "The system will use the appropriate ball diameter for tracking.",
            )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Apply Error",
                f"Failed to apply ball type:\n{str(e)}",
            )
