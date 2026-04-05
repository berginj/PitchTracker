"""Alignment comparison and restart helpers."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from app.services.tooling import get_tooling_service
from capture import CameraDevice
from contracts.tooling import CalibrationRequest
from exceptions import (
    CalibrationExecutionError,
    CalibrationInputError,
    CalibrationPersistenceError,
)
from log_config.logger import get_logger
from ui.setup.steps.calibration_errors import build_calibration_error_payload
from ui.setup.steps.calibration_worker import CalibrationWorker
from ui.themes import (
    apply_standard_layout,
    ask_confirmation,
    build_notice,
    get_style_manager,
    polish_form_controls,
    show_choice_dialog,
    show_message_dialog,
    style_message_panel,
    style_preview_surface,
    style_progress_bar,
    style_status_label,
)

logger = get_logger(__name__)


class CalibrationStepAlignmentCompareMixin:
    def _compare_with_preset(self) -> None:
        """Compare current alignment with a saved preset (side-by-side)."""
        if not hasattr(self, '_alignment_results') or self._alignment_results is None:
            show_message_dialog(
                self,
                "No Current Alignment",
                "Run an alignment check first before comparing.",
                tone="warning",
            )
            return

        try:
            from analysis.camera_alignment import (
                list_alignment_presets,
                load_alignment_preset,
                compare_with_preset
            )

            # Get list of available presets
            presets = list_alignment_presets()

            if not presets:
                show_message_dialog(
                    self,
                    "No Presets Found",
                    "No saved alignment presets found.\n\n"
                    "Save a preset first to enable comparison.",
                    tone="info",
                )
                return

            # Show selection dialog
            preset_names = [f"{p['name']} ({p['quality_score']}% - {p['saved_at'][:10]})"
                           for p in presets]

            preset_choice, ok = QtWidgets.QInputDialog.getItem(
                self,
                "Compare with Preset",
                "Select a preset to compare with current alignment:",
                preset_names,
                0,
                False
            )

            if ok and preset_choice:
                # Extract preset name
                preset_name = preset_choice.split(" (")[0]

                # Load preset
                preset_data = load_alignment_preset(preset_name)
                if not preset_data:
                    show_message_dialog(
                        self,
                        "Load Failed",
                        f"Could not load preset '{preset_name}'",
                        tone="warning",
                    )
                    return

                # Perform comparison
                comparison = compare_with_preset(self._alignment_results, preset_data)

                # Build comparison display
                trend_color = self._theme.accent_success if comparison["trend"] == "BETTER" else (
                    self._theme.accent_error if comparison["trend"] == "WORSE" else self._theme.accent_warning
                )

                comparison_html = f"""
                <h3>Alignment Comparison</h3>
                <p><b>Current vs. Preset:</b> {comparison['preset_name']} ({comparison['preset_date']})</p>
                <div style='text-align: center; padding: 15px; background-color: {trend_color}20;
                            border: 2px solid {trend_color}; border-radius: 8px; margin: 10px 0;'>
                    <div style='font-size: 32pt;'>{comparison['trend_emoji']}</div>
                    <div style='font-size: 16pt; font-weight: bold; color: {trend_color};'>
                        {comparison['trend']}
                    </div>
                    <div style='font-size: 12pt; margin-top: 5px;'>
                        Score: {comparison['current_score']}% vs {comparison['preset_score']}%
                        ({comparison['score_delta']:+.0f})
                    </div>
                </div>
                <hr>
                <h4>Detailed Comparison:</h4>
                <table style='width: 100%;'>
                    <tr style='background-color: {self._theme.surface_glass};'>
                        <th>Metric</th>
                        <th>Current</th>
                        <th>Preset</th>
                        <th>Δ</th>
                        <th>Status</th>
                    </tr>
                """

                for metric_name, metric_label in [
                    ("focal", "Focal Length"),
                    ("toin", "Toe-in"),
                    ("vertical", "Vertical"),
                    ("rotation", "Rotation")
                ]:
                    delta_data = comparison["deltas"][metric_name]
                    status_emoji = "✓" if delta_data["better"] else "⚠️"
                    status_color = self._theme.accent_success if delta_data["better"] else self._theme.accent_warning

                    comparison_html += f"""
                    <tr>
                        <td><b>{metric_label}</b></td>
                        <td>{delta_data['current']:.2f}</td>
                        <td>{delta_data['preset']:.2f}</td>
                        <td>{delta_data['delta']:+.2f}</td>
                        <td style='color: {status_color}; font-weight: bold;'>{status_emoji}</td>
                    </tr>
                    """

                comparison_html += "</table>"

                # Show in dialog
                dialog = QtWidgets.QDialog(self)
                dialog.setWindowTitle("Alignment Comparison")
                dialog.resize(650, 500)

                layout = QtWidgets.QVBoxLayout()

                text = QtWidgets.QTextEdit()
                text.setReadOnly(True)
                text.setHtml(comparison_html)
                layout.addWidget(text)

                close_btn = QtWidgets.QPushButton("Close")
                close_btn.clicked.connect(dialog.accept)
                layout.addWidget(close_btn)

                dialog.setLayout(layout)
                dialog.exec()

        except Exception as e:
            show_message_dialog(
                self,
                "Comparison Failed",
                f"Failed to compare with preset:\n{str(e)}",
                tone="error",
            )

    def _restart_cameras_after_correction(self) -> None:
        """Restart cameras after applying alignment corrections."""
        try:
            # Stop preview
            self._preview_timer.stop()

            # Close cameras
            self._close_cameras()

            # Wait briefly
            QtCore.QTimer.singleShot(500, self._reopen_cameras_after_correction)

        except Exception:
            logger.exception("Failed to restart cameras after applying alignment corrections")

    def _reopen_cameras_after_correction(self) -> None:
        """Reopen cameras after applying corrections."""
        try:
            # Reopen with corrections applied
            self._open_cameras()

            # Restart preview
            self._preview_timer.start(33)  # 30 FPS

            # Update UI
            self._alignment_status_label.setText(
                self._alignment_status_label.text().replace(
                    "Rotation correction applied",
                    "Rotation correction applied ✓ (cameras restarted)"
                )
            )

        except Exception as e:
            show_message_dialog(
                self,
                "Camera Error",
                f"Failed to restart cameras after applying corrections:\n{str(e)}",
                tone="error",
            )
