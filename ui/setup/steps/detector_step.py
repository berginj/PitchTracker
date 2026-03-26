"""Step 4: Detector tuning - test and validate detection settings."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtWidgets

from configs.settings import load_config
from ui.setup.steps.base_step import BaseStep
from ui.themes import apply_standard_layout, build_notice, get_style_manager, show_message_dialog


class DetectorStep(BaseStep):
    """Step 4: Detector tuning and validation."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._config_path = Path("configs/default.yaml")
        self._config = load_config(self._config_path)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build detector configuration UI."""
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        instructions, _ = build_notice(
            "Detector settings can be tuned here, but live coaching remains the best place to validate behavior under real conditions.",
            tone="info",
        )
        layout.addWidget(instructions)
        layout.addWidget(self._build_config_display())
        layout.addWidget(self._build_mode_selection())
        layout.addWidget(self._build_ball_type_selection())

        tips_group = QtWidgets.QGroupBox("Tips")
        tips_text = QtWidgets.QLabel(
            "- Classical detection works best with stable lighting.\n"
            "- ML detection is more robust but depends on a trained model.\n"
            "- Live sessions provide the clearest detector feedback.\n"
            "- You can continue even if you leave these settings at defaults."
        )
        tips_text.setWordWrap(True)
        self._style_manager.style_label(tips_text, "muted")
        tips_layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(tips_layout, margins=(8, 8, 8, 8), spacing=8)
        tips_layout.addWidget(tips_text)
        tips_group.setLayout(tips_layout)
        layout.addWidget(tips_group)

        layout.addStretch()
        self.setLayout(layout)

    def _build_config_display(self) -> QtWidgets.QGroupBox:
        """Build current configuration display."""
        group = QtWidgets.QGroupBox("Current Configuration")

        mode_label = QtWidgets.QLabel("Detection Mode")
        self._style_manager.style_label(mode_label, "sectionTitle")
        detector_config = self._config.detector
        mode = detector_config.type
        self._mode_value = QtWidgets.QLabel(mode.upper() if mode else "CLASSICAL")
        self._style_manager.style_label(self._mode_value, "metricAccent")

        ball_label = QtWidgets.QLabel("Ball Type")
        self._style_manager.style_label(ball_label, "sectionTitle")
        ball_type = self._config.ball.type
        self._ball_value = QtWidgets.QLabel(ball_type.upper() if ball_type else "BASEBALL")
        self._style_manager.style_label(self._ball_value, "metricAccent")

        grid = QtWidgets.QGridLayout()
        apply_standard_layout(grid, margins=(8, 8, 8, 8), spacing=10)
        grid.addWidget(mode_label, 0, 0)
        grid.addWidget(self._mode_value, 0, 1)
        grid.addWidget(ball_label, 1, 0)
        grid.addWidget(self._ball_value, 1, 1)
        grid.setColumnStretch(1, 1)
        group.setLayout(grid)
        return group

    def _build_mode_selection(self) -> QtWidgets.QGroupBox:
        """Build detection mode selection."""
        group = QtWidgets.QGroupBox("Detection Mode")
        self._classical_radio = QtWidgets.QRadioButton("Classical (Blob Detection)")
        self._ml_radio = QtWidgets.QRadioButton("ML (Neural Network)")

        current_mode = self._config.detector.type
        if current_mode == "ml":
            self._ml_radio.setChecked(True)
        else:
            self._classical_radio.setChecked(True)

        classical_info = QtWidgets.QLabel("Fast and lightweight for controlled environments.")
        classical_info.setWordWrap(True)
        self._style_manager.style_label(classical_info, "muted")

        ml_info = QtWidgets.QLabel("More robust in varied conditions when a trained model is available.")
        ml_info.setWordWrap(True)
        self._style_manager.style_label(ml_info, "muted")

        apply_button = QtWidgets.QPushButton("Apply Mode")
        apply_button.clicked.connect(self._apply_mode)
        self._style_manager.style_button(apply_button, "primary")

        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout, margins=(8, 8, 8, 8), spacing=8)
        layout.addWidget(self._classical_radio)
        layout.addWidget(classical_info)
        layout.addWidget(self._ml_radio)
        layout.addWidget(ml_info)
        layout.addWidget(apply_button)
        group.setLayout(layout)
        return group

    def _build_ball_type_selection(self) -> QtWidgets.QGroupBox:
        """Build ball type selection."""
        group = QtWidgets.QGroupBox("Ball Type")
        self._baseball_radio = QtWidgets.QRadioButton("Baseball")
        self._softball_radio = QtWidgets.QRadioButton("Softball")

        current_ball_type = self._config.ball.type
        if current_ball_type == "softball":
            self._softball_radio.setChecked(True)
        else:
            self._baseball_radio.setChecked(True)

        baseball_info = QtWidgets.QLabel("Standard baseball diameter.")
        softball_info = QtWidgets.QLabel("Softball diameter used for trajectory and zone math.")
        for label in (baseball_info, softball_info):
            label.setWordWrap(True)
            self._style_manager.style_label(label, "muted")

        apply_ball_button = QtWidgets.QPushButton("Apply Ball Type")
        apply_ball_button.clicked.connect(self._apply_ball_type)
        self._style_manager.style_button(apply_ball_button, "primary")

        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout, margins=(8, 8, 8, 8), spacing=8)
        layout.addWidget(self._baseball_radio)
        layout.addWidget(baseball_info)
        layout.addWidget(self._softball_radio)
        layout.addWidget(softball_info)
        layout.addWidget(apply_ball_button)
        group.setLayout(layout)
        return group

    def get_title(self) -> str:
        return "Detector Tuning"

    def validate(self) -> tuple[bool, str]:
        return True, ""

    def is_skippable(self) -> bool:
        return True

    def on_enter(self) -> None:
        self._config = load_config(self._config_path)
        self._update_display()

    def on_exit(self) -> None:
        pass

    def _update_display(self) -> None:
        mode = self._config.detector.type
        self._mode_value.setText(mode.upper() if mode else "CLASSICAL")
        ball_type = self._config.ball.type
        self._ball_value.setText(ball_type.upper() if ball_type else "BASEBALL")

    def _apply_mode(self) -> None:
        if self._ml_radio.isChecked():
            new_mode = "ml"
        else:
            new_mode = "classical"

        try:
            import yaml

            data = yaml.safe_load(self._config_path.read_text())
            data.setdefault("detector", {})
            data["detector"]["type"] = new_mode
            self._config_path.write_text(yaml.safe_dump(data, sort_keys=False))

            self._config = load_config(self._config_path)
            self._update_display()

            show_message_dialog(
                self,
                "Mode Applied",
                f"Detection mode set to {new_mode.upper()}.",
                tone="success",
            )
        except Exception as exc:
            show_message_dialog(
                self,
                "Apply Error",
                f"Failed to apply detection mode:\n{exc}",
                tone="error",
            )

    def _apply_ball_type(self) -> None:
        if self._softball_radio.isChecked():
            new_ball_type = "softball"
        else:
            new_ball_type = "baseball"

        try:
            import yaml

            data = yaml.safe_load(self._config_path.read_text())
            data.setdefault("ball", {})
            data["ball"]["type"] = new_ball_type
            self._config_path.write_text(yaml.safe_dump(data, sort_keys=False))

            self._config = load_config(self._config_path)
            self._update_display()

            show_message_dialog(
                self,
                "Ball Type Applied",
                f"Ball type set to {new_ball_type.upper()}.",
                tone="success",
            )
        except Exception as exc:
            show_message_dialog(
                self,
                "Apply Error",
                f"Failed to apply ball type:\n{exc}",
                tone="error",
            )
