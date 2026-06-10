"""Step 6: Export package - generate setup summary and complete setup."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from ui.setup.steps.base_step import BaseStep
from ui.themes import (
    apply_standard_layout,
    build_notice,
    get_style_manager,
    show_message_dialog,
    style_status_label,
)


class ExportStep(BaseStep):
    """Step 6: Export calibration package and complete setup."""

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build export UI."""
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        self._completion_label = QtWidgets.QLabel()
        self._completion_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        style_status_label(
            self._completion_label,
            "success",
            "Setup Complete\n\nYour PitchTracker system is configured and ready to use.",
        )
        layout.addWidget(self._completion_label)

        layout.addWidget(self._build_summary())
        layout.addWidget(self._build_next_steps())

        export_button = QtWidgets.QPushButton("Generate Summary Report")
        export_button.setMinimumHeight(self._style_manager.theme.button_height_lg)
        export_button.clicked.connect(self._generate_report)
        self._style_manager.style_button(export_button, "primary")
        layout.addWidget(export_button)

        layout.addStretch()
        self.setLayout(layout)

    def _build_summary(self) -> QtWidgets.QGroupBox:
        """Build configuration summary."""
        group = QtWidgets.QGroupBox("Configuration Summary")
        self._summary_text = QtWidgets.QTextEdit()
        self._summary_text.setReadOnly(True)
        self._summary_text.setMaximumHeight(220)

        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout, margins=(8, 8, 8, 8), spacing=10)
        layout.addWidget(self._summary_text)
        group.setLayout(layout)
        return group

    def _build_next_steps(self) -> QtWidgets.QGroupBox:
        """Build next steps instructions."""
        group = QtWidgets.QGroupBox("Next Steps")
        steps_notice, _ = build_notice(
            "Launch the coaching app, start a session, and verify live metrics with a short test recording.",
            tone="info",
        )
        steps_text = QtWidgets.QLabel(
            "1. Launch the coaching app using the launcher or `python -m ui.qt_app --backend opencv`.\n"
            "2. Start a session, select a pitcher, and confirm both cameras.\n"
            "3. Record a short test sequence and review the session summary.\n"
            "4. Export data or revisit setup if any measurement looks off."
        )
        steps_text.setWordWrap(True)
        self._style_manager.style_label(steps_text, "muted")

        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout, margins=(8, 8, 8, 8), spacing=10)
        layout.addWidget(steps_notice)
        layout.addWidget(steps_text)
        group.setLayout(layout)
        return group

    def get_title(self) -> str:
        return "Export & Complete"

    def validate(self) -> tuple[bool, str]:
        return True, ""

    def is_skippable(self) -> bool:
        return False

    def on_enter(self) -> None:
        self._update_summary()

    def on_exit(self) -> None:
        pass

    def _update_summary(self) -> None:
        """Update configuration summary display."""
        summary_lines = []
        config_path = Path("configs/default.yaml")
        if config_path.exists():
            summary_lines.append(f"[ready] Configuration: {config_path}")
        else:
            summary_lines.append("[missing] Configuration: not found")

        calib_file = Path("calibration/stereo_calibration.npz")
        if calib_file.exists():
            summary_lines.append(f"[ready] Stereo Calibration: {calib_file}")
        else:
            try:
                import yaml

                data = yaml.safe_load(config_path.read_text())
                stereo = data.get("stereo", {})
                if stereo.get("baseline_ft"):
                    summary_lines.append(
                        f"[ready] Stereo Calibration: in config (baseline={stereo['baseline_ft']:.3f} ft)"
                    )
                else:
                    summary_lines.append("[missing] Stereo Calibration: not configured")
            except Exception:
                summary_lines.append("[missing] Stereo Calibration: not configured")

        roi_path = Path("rois/shared_rois.json")
        if roi_path.exists():
            try:
                import json

                data = json.loads(roi_path.read_text())
                if data.get("lane") and data.get("plate"):
                    summary_lines.append("[ready] ROIs: lane and plate configured")
                else:
                    summary_lines.append("[warning] ROIs: incomplete configuration")
            except Exception:
                summary_lines.append("[missing] ROIs: error reading file")
        else:
            summary_lines.append("[missing] ROIs: not configured")

        try:
            import yaml

            data = yaml.safe_load(config_path.read_text())
            detection = data.get("detection", {})
            detector_type = detection.get("detector_type", "classical")
            summary_lines.append(f"[ready] Detector: {detector_type.upper()}")
        except Exception:
            summary_lines.append("[ready] Detector: CLASSICAL (default)")

        self._summary_text.setText("\n".join(summary_lines))

    def _generate_report(self) -> None:
        """Generate and save summary report."""
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            report_lines = [
                "PitchTracker Setup Report",
                "=" * 50,
                f"Generated: {timestamp}",
                "",
                "Configuration Status:",
                "-" * 50,
            ]

            config_path = Path("configs/default.yaml")
            if config_path.exists():
                report_lines.append(f"[ready] Configuration File: {config_path}")

                import yaml

                data = yaml.safe_load(config_path.read_text())

                stereo = data.get("stereo", {})
                if stereo:
                    report_lines.append("\nStereo Calibration:")
                    report_lines.append(f"  - Baseline: {stereo.get('baseline_ft', 'N/A')} ft")
                    report_lines.append(f"  - Focal Length: {stereo.get('focal_length_px', 'N/A')} px")
                    report_lines.append(f"  - Principal Point: ({stereo.get('cx', 'N/A')}, {stereo.get('cy', 'N/A')})")

                detection = data.get("detection", {})
                if detection:
                    report_lines.append("\nDetection Settings:")
                    report_lines.append(f"  - Mode: {detection.get('detector_type', 'classical').upper()}")

                tracking = data.get("tracking", {})
                if tracking:
                    report_lines.append("\nTracking Settings:")
                    report_lines.append(f"  - Ball Type: {tracking.get('ball_type', 'baseball').upper()}")

            roi_path = Path("rois/shared_rois.json")
            if roi_path.exists():
                report_lines.append(f"\n[ready] ROI Configuration: {roi_path}")
            else:
                report_lines.append("\n[missing] ROI Configuration: not found")

            report_path = Path("setup_report.txt")
            report_path.write_text("\n".join(report_lines))

            show_message_dialog(
                self,
                "Report Generated",
                f"Setup report saved to:\n{report_path.absolute()}",
                tone="success",
            )
        except Exception as exc:
            show_message_dialog(
                self,
                "Export Error",
                f"Failed to generate report:\n{exc}",
                tone="error",
            )
