"""Step 5: System Validation - Verify system configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from ui.setup.steps.base_step import BaseStep


class ValidationStep(BaseStep):
    """Step 5: System validation and readiness check.

    Workflow:
    1. Check all required components are configured
    2. Display status for each component
    3. Provide recommendations for any issues
    4. Validate system is ready for coaching sessions
    """

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build validation UI."""
        layout = QtWidgets.QVBoxLayout()

        # Instructions
        instructions = QtWidgets.QLabel(
            "System Validation:\n\n"
            "Verifying that all required components are properly configured..."
        )
        instructions.setWordWrap(True)
        instructions.setStyleSheet("font-size: 11pt; padding: 10px; background-color: #e3f2fd; border-radius: 5px;")
        layout.addWidget(instructions)

        # Validation checklist
        self._checklist = QtWidgets.QGroupBox("Configuration Status")
        self._checklist_layout = QtWidgets.QVBoxLayout()
        self._checklist.setLayout(self._checklist_layout)
        layout.addWidget(self._checklist)

        # Summary
        self._summary_label = QtWidgets.QLabel()
        self._summary_label.setWordWrap(True)
        self._summary_label.setStyleSheet("font-size: 11pt; padding: 10px; border-radius: 5px;")
        layout.addWidget(self._summary_label)

        # Refresh button
        refresh_button = QtWidgets.QPushButton("🔄 Refresh Status")
        refresh_button.setMinimumHeight(40)
        refresh_button.clicked.connect(self._run_validation)
        layout.addWidget(refresh_button)

        layout.addStretch()

        self.setLayout(layout)

    def get_title(self) -> str:
        """Return step title."""
        return "System Validation"

    def validate(self) -> tuple[bool, str]:
        """Validate system is ready.

        System must have calibration and ROIs configured.
        """
        issues = []

        # Check calibration
        if not Path("configs/default.yaml").exists():
            issues.append("Configuration file missing")

        if not Path("calibration/stereo_calibration.npz").exists():
            issues.append("Stereo calibration missing")

        # Check ROIs
        if not Path("rois/shared_rois.json").exists():
            issues.append("ROI configuration missing")

        if issues:
            return False, "System not ready:\n• " + "\n• ".join(issues)

        return True, ""

    def is_skippable(self) -> bool:
        """Validation cannot be skipped."""
        return False

    def on_enter(self) -> None:
        """Called when step becomes active."""
        # Run validation automatically
        self._run_validation()

    def on_exit(self) -> None:
        """Called when leaving step."""
        pass

    def _run_validation(self) -> None:
        """Run system validation checks."""
        # Clear existing checklist
        for i in reversed(range(self._checklist_layout.count())):
            widget = self._checklist_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # Perform checks
        checks = [
            ("Configuration File", self._check_config()),
            ("Stereo Calibration", self._check_calibration()),
            ("ROI Configuration", self._check_rois()),
            ("Detector Settings", self._check_detector()),
        ]

        # Display results
        all_passed = True
        for name, (passed, details) in checks:
            item = self._create_check_item(name, passed, details)
            self._checklist_layout.addWidget(item)
            if not passed:
                all_passed = False

        # Update summary
        if all_passed:
            self._summary_label.setText(
                "✅ System Configuration Complete!\n\n"
                "All components are properly configured. You can now proceed to export "
                "the calibration package or start using the Coaching App."
            )
            self._summary_label.setStyleSheet(
                "font-size: 11pt; padding: 10px; background-color: #c8e6c9; "
                "color: #2e7d32; border-radius: 5px; font-weight: bold;"
            )
        else:
            self._summary_label.setText(
                "⚠️ Configuration Incomplete\n\n"
                "Some required components are not configured. Please go back to complete "
                "the missing steps before proceeding."
            )
            self._summary_label.setStyleSheet(
                "font-size: 11pt; padding: 10px; background-color: #fff9c4; "
                "color: #f57c00; border-radius: 5px; font-weight: bold;"
            )

    def _create_check_item(self, name: str, passed: bool, details: str) -> QtWidgets.QWidget:
        """Create a checklist item widget."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5)

        # Status icon
        icon = "✅" if passed else "❌"
        icon_label = QtWidgets.QLabel(icon)
        icon_label.setStyleSheet("font-size: 16pt;")

        # Name
        name_label = QtWidgets.QLabel(name)
        name_label.setStyleSheet("font-size: 11pt; font-weight: bold;")

        # Details
        details_label = QtWidgets.QLabel(details)
        details_label.setStyleSheet("font-size: 9pt; color: #666;")

        layout.addWidget(icon_label)
        layout.addWidget(name_label, 1)
        layout.addWidget(details_label, 2)

        widget.setLayout(layout)
        return widget

    def _check_config(self) -> tuple[bool, str]:
        """Check configuration file exists."""
        config_path = Path("configs/default.yaml")
        if config_path.exists():
            return True, f"Found at {config_path}"
        return False, "Configuration file not found"

    def _check_calibration(self) -> tuple[bool, str]:
        """Check stereo calibration exists."""
        calib_file = Path("calibration/stereo_calibration.npz")
        if calib_file.exists():
            return True, f"Found at {calib_file}"

        # Check if calibration is in config
        import yaml
        config_path = Path("configs/default.yaml")
        if config_path.exists():
            try:
                data = yaml.safe_load(config_path.read_text())
                stereo = data.get("stereo", {})
                if stereo.get("baseline_ft") and stereo.get("focal_length_px"):
                    return True, "Calibration parameters in config"
            except Exception:
                pass

        return False, "Stereo calibration not found"

    def _check_rois(self) -> tuple[bool, str]:
        """Check ROI configuration exists."""
        roi_path = Path("rois/shared_rois.json")
        if roi_path.exists():
            try:
                import json
                data = json.loads(roi_path.read_text())
                if data.get("lane") and data.get("plate"):
                    return True, "Lane and plate ROIs configured"
                elif data.get("lane"):
                    return False, "Lane ROI found, plate ROI missing"
                elif data.get("plate"):
                    return False, "Plate ROI found, lane ROI missing"
            except Exception:
                pass

        return False, "ROI configuration not found"

    def _check_detector(self) -> tuple[bool, str]:
        """Check detector settings."""
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
