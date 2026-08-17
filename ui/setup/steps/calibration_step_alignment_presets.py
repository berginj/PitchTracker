"""Alignment preset save and load helpers."""

from __future__ import annotations

from ui.setup.steps.calibration_step_mixin_host import CalibrationStepMixinHost


from PySide6 import QtWidgets

from log_config.logger import get_logger
from ui.themes import (
    show_message_dialog,
)

logger = get_logger(__name__)


class CalibrationStepAlignmentPresetsMixin(CalibrationStepMixinHost):
    def _save_alignment_preset(self) -> None:
        """Save current alignment as a preset."""
        if not hasattr(self, "_alignment_results") or self._alignment_results is None:
            show_message_dialog(
                self,
                "No Alignment Available",
                "Run an alignment check first before saving a preset.",
                tone="warning",
            )
            return

        try:
            from datetime import datetime
            from analysis.camera_alignment import save_alignment_preset

            # Prompt for preset name
            default_name = f"preset_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            preset_name, ok = QtWidgets.QInputDialog.getText(
                self,
                "Save Alignment Preset",
                "Enter a name for this preset:\n(e.g., 'baseline_good', 'after_adjustment')",
                QtWidgets.QLineEdit.EchoMode.Normal,
                default_name,
            )

            if ok and preset_name:
                # Save preset
                save_alignment_preset(
                    self._alignment_results,
                    preset_name,
                    str(self._left_serial or "Unknown"),
                    str(self._right_serial or "Unknown"),
                )

                show_message_dialog(
                    self,
                    "Preset Saved",
                    f"Alignment preset '{preset_name}' saved successfully!\n\n"
                    f"Quality Score: {self._alignment_results.get_quality_score()}%\n"
                    f"You can load this preset later for comparison.",
                    tone="success",
                )

        except Exception as e:
            show_message_dialog(
                self,
                "Save Failed",
                f"Failed to save alignment preset:\n{str(e)}",
                tone="error",
            )

    def _load_alignment_preset(self) -> None:
        """Load a saved alignment preset and display it."""
        try:
            from analysis.camera_alignment import list_alignment_presets, load_alignment_preset

            # Get list of available presets
            presets = list_alignment_presets()

            if not presets:
                show_message_dialog(
                    self,
                    "No Presets Found",
                    "No saved alignment presets found.\n\n"
                    "Save a preset first by running an alignment check "
                    "and clicking 'Save Preset'.",
                    tone="info",
                )
                return

            # Show selection dialog
            preset_names = [f"{p['name']} ({p['quality_score']}% - {p['saved_at'][:10]})" for p in presets]

            preset_choice, ok = QtWidgets.QInputDialog.getItem(
                self, "Load Alignment Preset", "Select a preset to view:", preset_names, 0, False
            )

            if ok and preset_choice:
                # Extract preset name (before the parenthesis)
                preset_name = preset_choice.split(" (")[0]

                # Load preset data
                preset_data = load_alignment_preset(preset_name)
                if not preset_data:
                    show_message_dialog(
                        self,
                        "Load Failed",
                        f"Could not load preset '{preset_name}'",
                        tone="warning",
                    )
                    return

                # Display preset details
                metrics = preset_data["metrics"]
                info_text = (
                    f"<h3>Preset: {preset_data['preset_name']}</h3>"
                    f"<p><b>Saved:</b> {preset_data['saved_at'][:19]}<br>"
                    f"<b>Cameras:</b> {preset_data['left_camera']} / {preset_data['right_camera']}<br>"
                    f"<b>Quality Score:</b> {preset_data['quality_score']}% ({preset_data['quality_rating']})</p>"
                    f"<hr>"
                    f"<h4>Metrics:</h4>"
                    f"<table>"
                    f"<tr><td><b>Focal Length Diff:</b></td><td>{metrics['focal_diff_percent']:.2f}%</td></tr>"
                    f"<tr><td><b>Toe-in:</b></td><td>{metrics['toin_std_px']:.2f} px</td></tr>"
                    f"<tr><td><b>Vertical Offset:</b></td><td>{metrics['vertical_mean_px']:.2f} px</td></tr>"
                    f"<tr><td><b>Rotation:</b></td><td>{metrics['rotation_deg']:.2f}°</td></tr>"
                    f"<tr><td><b>Feature Matches:</b></td><td>{metrics['num_matches']}</td></tr>"
                    f"</table>"
                )

                # Show in dialog
                dialog = QtWidgets.QDialog(self)
                dialog.setWindowTitle("Alignment Preset Details")
                dialog.resize(500, 400)

                layout = QtWidgets.QVBoxLayout()

                text = QtWidgets.QTextEdit()
                text.setReadOnly(True)
                text.setHtml(info_text)
                layout.addWidget(text)

                close_btn = QtWidgets.QPushButton("Close")
                close_btn.clicked.connect(dialog.accept)
                layout.addWidget(close_btn)

                dialog.setLayout(layout)
                dialog.exec()

        except Exception as e:
            show_message_dialog(
                self,
                "Load Failed",
                f"Failed to load preset:\n{str(e)}",
                tone="error",
            )
