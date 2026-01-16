"""Step 6: Export Package - Generate calibration summary and complete setup."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from ui.setup.steps.base_step import BaseStep


class ExportStep(BaseStep):
    """Step 6: Export calibration package and complete setup.

    Workflow:
    1. Generate calibration summary report
    2. Show completion status
    3. Provide next steps for user
    4. Offer to launch Coaching App
    """

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        """Build export UI."""
        layout = QtWidgets.QVBoxLayout()

        # Completion message
        completion = QtWidgets.QLabel(
            "🎉 Setup Complete!\n\n"
            "Your PitchTracker system is now fully configured and ready to use."
        )
        completion.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        completion.setWordWrap(True)
        completion.setStyleSheet(
            "font-size: 16pt; font-weight: bold; padding: 20px; "
            "background-color: #c8e6c9; color: #2e7d32; border-radius: 10px;"
        )
        layout.addWidget(completion)

        # Configuration summary
        summary_group = self._build_summary()
        layout.addWidget(summary_group)

        # Next steps
        next_steps_group = self._build_next_steps()
        layout.addWidget(next_steps_group)

        # Export button
        export_button = QtWidgets.QPushButton("📋 Generate Summary Report")
        export_button.setMinimumHeight(50)
        export_button.setStyleSheet("font-size: 12pt; background-color: #2196F3; color: white;")
        export_button.clicked.connect(self._generate_report)
        layout.addWidget(export_button)

        layout.addStretch()

        self.setLayout(layout)

    def _build_summary(self) -> QtWidgets.QGroupBox:
        """Build configuration summary."""
        group = QtWidgets.QGroupBox("Configuration Summary")

        self._summary_text = QtWidgets.QTextEdit()
        self._summary_text.setReadOnly(True)
        self._summary_text.setMaximumHeight(200)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._summary_text)
        group.setLayout(layout)
        return group

    def _build_next_steps(self) -> QtWidgets.QGroupBox:
        """Build next steps instructions."""
        group = QtWidgets.QGroupBox("Next Steps")

        steps_text = QtWidgets.QLabel(
            "1. Launch the Coaching App:\n"
            "   • Run: python test_coaching_app.py\n"
            "   • Or use the main application launcher\n\n"
            "2. Start a coaching session:\n"
            "   • Click 'Start Session'\n"
            "   • Select pitcher and configure settings\n"
            "   • Begin recording pitches!\n\n"
            "3. Monitor and review:\n"
            "   • View real-time metrics during session\n"
            "   • Review session summary after completion\n"
            "   • Export data for analysis"
        )
        steps_text.setWordWrap(True)
        steps_text.setStyleSheet("font-size: 10pt; padding: 10px;")

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(steps_text)
        group.setLayout(layout)
        return group

    def get_title(self) -> str:
        """Return step title."""
        return "Export & Complete"

    def validate(self) -> tuple[bool, str]:
        """Export step is always valid."""
        return True, ""

    def is_skippable(self) -> bool:
        """Export step cannot be skipped."""
        return False

    def on_enter(self) -> None:
        """Called when step becomes active."""
        # Generate and display summary
        self._update_summary()

    def on_exit(self) -> None:
        """Called when leaving step."""
        pass

    def _update_summary(self) -> None:
        """Update configuration summary display."""
        summary_lines = []

        # Configuration file
        config_path = Path("configs/default.yaml")
        if config_path.exists():
            summary_lines.append(f"✅ Configuration: {config_path}")
        else:
            summary_lines.append("❌ Configuration: Not found")

        # Calibration
        calib_file = Path("calibration/stereo_calibration.npz")
        if calib_file.exists():
            summary_lines.append(f"✅ Stereo Calibration: {calib_file}")
        else:
            # Check config for calibration params
            try:
                import yaml
                data = yaml.safe_load(config_path.read_text())
                stereo = data.get("stereo", {})
                if stereo.get("baseline_ft"):
                    summary_lines.append(
                        f"✅ Stereo Calibration: In config "
                        f"(baseline={stereo['baseline_ft']:.3f}ft)"
                    )
                else:
                    summary_lines.append("❌ Stereo Calibration: Not configured")
            except Exception:
                summary_lines.append("❌ Stereo Calibration: Not configured")

        # ROIs
        roi_path = Path("rois/shared_rois.json")
        if roi_path.exists():
            try:
                import json
                data = json.loads(roi_path.read_text())
                if data.get("lane") and data.get("plate"):
                    summary_lines.append(f"✅ ROIs: Lane and Plate configured")
                else:
                    summary_lines.append("⚠️ ROIs: Incomplete configuration")
            except Exception:
                summary_lines.append("❌ ROIs: Error reading file")
        else:
            summary_lines.append("❌ ROIs: Not configured")

        # Detector
        try:
            import yaml
            data = yaml.safe_load(config_path.read_text())
            detection = data.get("detection", {})
            detector_type = detection.get("detector_type", "classical")
            summary_lines.append(f"✅ Detector: {detector_type.upper()}")
        except Exception:
            summary_lines.append("✅ Detector: Classical (default)")

        # Display summary
        self._summary_text.setText("\n".join(summary_lines))

    def _generate_report(self) -> None:
        """Generate and save summary report."""
        try:
            # Generate report content
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
            report_lines = [
                "PitchTracker Setup Report",
                "=" * 50,
                f"Generated: {timestamp}",
                "",
                "Configuration Status:",
                "-" * 50,
            ]

            # Add configuration details
            config_path = Path("configs/default.yaml")
            if config_path.exists():
                report_lines.append(f"✅ Configuration File: {config_path}")

                # Parse config
                import yaml
                data = yaml.safe_load(config_path.read_text())

                # Stereo calibration
                stereo = data.get("stereo", {})
                if stereo:
                    report_lines.append("\nStereo Calibration:")
                    report_lines.append(f"  • Baseline: {stereo.get('baseline_ft', 'N/A')} ft")
                    report_lines.append(f"  • Focal Length: {stereo.get('focal_length_px', 'N/A')} px")
                    report_lines.append(f"  • Principal Point: ({stereo.get('cx', 'N/A')}, {stereo.get('cy', 'N/A')})")

                # Detection
                detection = data.get("detection", {})
                if detection:
                    report_lines.append("\nDetection Settings:")
                    report_lines.append(f"  • Mode: {detection.get('detector_type', 'classical').upper()}")

                # Tracking
                tracking = data.get("tracking", {})
                if tracking:
                    report_lines.append("\nTracking Settings:")
                    report_lines.append(f"  • Ball Type: {tracking.get('ball_type', 'baseball').upper()}")

            # ROIs
            roi_path = Path("rois/shared_rois.json")
            if roi_path.exists():
                report_lines.append(f"\n✅ ROI Configuration: {roi_path}")
            else:
                report_lines.append("\n❌ ROI Configuration: Not found")

            # Save report
            report_path = Path("setup_report.txt")
            report_path.write_text("\n".join(report_lines))

            QtWidgets.QMessageBox.information(
                self,
                "Report Generated",
                f"Setup report saved to:\n{report_path.absolute()}\n\n"
                "You can now close this wizard and start using the Coaching App!",
            )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self,
                "Export Error",
                f"Failed to generate report:\n{str(e)}",
            )
