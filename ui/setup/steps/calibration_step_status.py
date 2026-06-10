"""Shared UI state helpers for the calibration step."""

from __future__ import annotations


from PySide6 import QtCore, QtWidgets

from log_config.logger import get_logger
from ui.themes import (
    style_message_panel,
    style_progress_bar,
    style_status_label,
)

logger = get_logger(__name__)


class CalibrationStepStatusMixin:
    def _set_capture_progress_state(self, count: int, *, ready: bool) -> None:
        """Update capture progress label styling."""
        text = f"Progress: {count}/{self._min_captures} poses captured"
        if ready:
            text += " Ready"
        tone = "success" if ready else "warning"
        style_status_label(self._capture_count_label, tone, text)
        if hasattr(self, "_capture_progress_bar"):
            style_progress_bar(self._capture_progress_bar, tone)

    def _set_detection_status(
        self,
        label: QtWidgets.QLabel,
        *,
        detected: bool,
        waiting_text: str = "Waiting for board...",
    ) -> None:
        """Update left/right board detection status chips."""
        if detected:
            style_status_label(label, "success", "Ready")
        else:
            style_status_label(label, "info", waiting_text)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

    def _set_focus_status(self, label: QtWidgets.QLabel, text: str, tone: str) -> None:
        """Update focus indicator styling."""
        style_status_label(label, tone, text)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

    def _set_camera_type_state(self, text: str, tone: str) -> None:
        style_status_label(self._camera_type_label, tone, text)

    def _set_camera_stability_state(self, text: str, tone: str) -> None:
        style_status_label(self._camera_stability_label, tone, text)

    def _set_pattern_info_state(self, text: str, tone: str) -> None:
        style_status_label(self._pattern_info_label, tone, text)

    def _set_baseline_state(self, text: str, tone: str, tooltip: str) -> None:
        style_status_label(self._baseline_inches_label, tone, text)
        self._baseline_inches_label.setToolTip(tooltip)

    def _set_alignment_state(self, text: str, tone: str = "info") -> None:
        style_message_panel(self._alignment_status_label, tone, text)

    def _set_quality_gauge_state(self, text: str, tone: str = "info") -> None:
        style_message_panel(self._quality_gauge, tone, text)
        self._quality_gauge.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

    def _set_results_state(self, text: str, tone: str) -> None:
        style_message_panel(self._results_text, tone, text)

    def _set_webcam_warning(self, text: str | None) -> None:
        """Show or hide the shared webcam warning banner."""
        if text:
            self._webcam_warning_label.setText(text)
            self._webcam_warning.show()
        else:
            self._webcam_warning.hide()

    def _tone_for_alignment_quality(self, quality: str) -> str:
        """Map alignment quality labels to shared semantic tones."""
        return {
            "EXCELLENT": "success",
            "GOOD": "success",
            "ACCEPTABLE": "warning",
            "POOR": "warning",
            "CRITICAL": "error",
        }.get(quality, "info")

    def _tone_for_quality_score(self, score: float) -> str:
        """Map numeric quality score to shared semantic tones."""
        if score >= 75:
            return "success"
        if score >= 40:
            return "warning"
        return "error"

    def _tone_for_calibration_rating(self, rating: str) -> str:
        """Map calibration rating labels to shared semantic tones."""
        return {
            "EXCELLENT": "success",
            "GOOD": "success",
            "ACCEPTABLE": "warning",
            "POOR": "error",
        }.get(rating, "info")
