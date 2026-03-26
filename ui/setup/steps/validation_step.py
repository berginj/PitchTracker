"""Step 5: System validation - verify system configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtWidgets

from ui.setup.steps.base_step import BaseStep
from ui.themes import (
    apply_standard_layout,
    build_notice,
    get_style_manager,
    style_status_label,
)


class ValidationStep(BaseStep):
    """Step 5: System validation and readiness check."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build validation UI."""
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        instructions, _ = build_notice(
            "Verify that configuration, stereo calibration, ROI files, and detector settings are ready before leaving setup.",
            tone="info",
        )
        layout.addWidget(instructions)

        self._checklist = QtWidgets.QGroupBox("Configuration Status")
        self._checklist_layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(self._checklist_layout, margins=(8, 8, 8, 8), spacing=10)
        self._checklist.setLayout(self._checklist_layout)
        layout.addWidget(self._checklist)

        self._summary_label = QtWidgets.QLabel()
        style_status_label(self._summary_label, "info", "Validation has not run yet.")
        layout.addWidget(self._summary_label)

        refresh_button = QtWidgets.QPushButton("Refresh Status")
        refresh_button.setMinimumHeight(40)
        refresh_button.clicked.connect(self._run_validation)
        self._style_manager.style_button(refresh_button, "primary")
        layout.addWidget(refresh_button)

        layout.addStretch()
        self.setLayout(layout)

    def get_title(self) -> str:
        return "System Validation"

    def validate(self) -> tuple[bool, str]:
        """Validate system is ready."""
        issues = []
        if not Path("configs/default.yaml").exists():
            issues.append("Configuration file missing")
        if not Path("calibration/stereo_calibration.npz").exists():
            issues.append("Stereo calibration missing")
        if not Path("rois/shared_rois.json").exists():
            issues.append("ROI configuration missing")

        if issues:
            return False, "System not ready:\n- " + "\n- ".join(issues)
        return True, ""

    def is_skippable(self) -> bool:
        return False

    def on_enter(self) -> None:
        self._run_validation()

    def on_exit(self) -> None:
        pass

    def _run_validation(self) -> None:
        """Run system validation checks."""
        for i in reversed(range(self._checklist_layout.count())):
            widget = self._checklist_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        checks = [
            ("Configuration File", self._check_config()),
            ("Stereo Calibration", self._check_calibration()),
            ("ROI Configuration", self._check_rois()),
            ("Detector Settings", self._check_detector()),
        ]

        all_passed = True
        for name, (passed, details) in checks:
            item = self._create_check_item(name, passed, details)
            self._checklist_layout.addWidget(item)
            if not passed:
                all_passed = False

        if all_passed:
            style_status_label(
                self._summary_label,
                "success",
                "System configuration complete. All required components are ready for coaching and export.",
            )
        else:
            style_status_label(
                self._summary_label,
                "warning",
                "Configuration is incomplete. Review the items above before leaving setup.",
            )

    def _create_check_item(self, name: str, passed: bool, details: str) -> QtWidgets.QWidget:
        """Create a checklist item widget."""
        widget = QtWidgets.QFrame()
        widget.setProperty("surface", "subtle")
        self._style_manager.polish(widget)

        layout = QtWidgets.QHBoxLayout(widget)
        apply_standard_layout(layout, margins=(12, 10, 12, 10), spacing=12)

        state_label = QtWidgets.QLabel("Ready" if passed else "Needs Attention")
        style_status_label(state_label, "success" if passed else "warning")

        name_label = QtWidgets.QLabel(name)
        self._style_manager.style_label(name_label, "sectionTitle")

        details_label = QtWidgets.QLabel(details)
        details_label.setWordWrap(True)
        self._style_manager.style_label(details_label, "muted")

        text_layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(text_layout, margins=(0, 0, 0, 0), spacing=4)
        text_layout.addWidget(name_label)
        text_layout.addWidget(details_label)

        layout.addWidget(state_label, 0)
        layout.addLayout(text_layout, 1)
        return widget

    def _check_config(self) -> tuple[bool, str]:
        config_path = Path("configs/default.yaml")
        if config_path.exists():
            return True, f"Found at {config_path}"
        return False, "Configuration file not found"

    def _check_calibration(self) -> tuple[bool, str]:
        calib_file = Path("calibration/stereo_calibration.npz")
        if calib_file.exists():
            return True, f"Found at {calib_file}"

        import yaml

        config_path = Path("configs/default.yaml")
        if config_path.exists():
            try:
                data = yaml.safe_load(config_path.read_text())
                stereo = data.get("stereo", {})
                if stereo.get("baseline_ft") and stereo.get("focal_length_px"):
                    return True, "Calibration parameters are present in config"
            except Exception:
                pass

        return False, "Stereo calibration not found"

    def _check_rois(self) -> tuple[bool, str]:
        roi_path = Path("rois/shared_rois.json")
        if roi_path.exists():
            try:
                import json

                data = json.loads(roi_path.read_text())
                if data.get("lane") and data.get("plate"):
                    return True, "Lane and plate ROIs configured"
                if data.get("lane"):
                    return False, "Lane ROI found, plate ROI missing"
                if data.get("plate"):
                    return False, "Plate ROI found, lane ROI missing"
            except Exception:
                pass
        return False, "ROI configuration not found"

    def _check_detector(self) -> tuple[bool, str]:
        config_path = Path("configs/default.yaml")
        if config_path.exists():
            try:
                import yaml

                data = yaml.safe_load(config_path.read_text())
                detection = data.get("detection", {})
                detector_type = detection.get("detector_type", "classical")
                return True, f"Detector mode: {detector_type.upper()}"
            except Exception:
                pass

        return True, "Using default detector settings"
