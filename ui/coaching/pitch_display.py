"""Pitch and metrics presentation for CoachWindow.

Handles preview updates, metrics polling, quality diagnostics, and
strike-zone overlay config propagation.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, cast

from PySide6 import QtWidgets

from ui.coaching.widgets.mode_widgets import BaseModeWidget

if TYPE_CHECKING:
    from ui.coaching.coach_window import CoachWindow

logger = logging.getLogger(__name__)


class PitchDisplay:
    """Manages pitch metrics display and preview updates."""

    def __init__(self, host: "CoachWindow") -> None:
        self._host = host

    def update_preview(self) -> None:
        """Update camera preview frames."""
        h = self._host
        if not h._service.is_capturing():
            return

        try:
            left_frame, right_frame = h._service.get_preview_frames()
            current_mode = h._mode_stack.currentWidget()
            if current_mode is None:
                raise RuntimeError("Coaching mode stack contains an unsupported widget")
            mode = cast(BaseModeWidget, current_mode)
            mode.update_camera_frames(left_frame, right_frame)
        except Exception as e:
            logger.error(f"Preview update failed: {e}", exc_info=True)

    def on_pitch_started(self, pitch_index: int, pitch_data) -> None:
        """Handle pitch started signal (main Qt thread)."""
        logger.info(f"Pitch {pitch_index} started (main thread)")
        self._host._set_status_message(f"Pitch {pitch_index} detected.", "info")

    def on_pitch_ended(self, pitch_data) -> None:
        """Handle pitch ended signal (main Qt thread)."""
        logger.info("Pitch ended (main thread)")
        h = self._host
        if h._session_active and not h._session_paused:
            h._set_status_message("Recording in progress. Ready to track pitches.", "success")

    def update_metrics(self) -> None:
        """Update pitch metrics display."""
        h = self._host
        if not h._session_active or h._session_paused:
            return

        try:
            self.update_quality_health()
            summary = h._service.get_session_summary()
            session_pitches = list(summary.pitches)
            new_pitches = [
                pitch
                for pitch in session_pitches
                if pitch.pitch_id not in h._processed_pitch_ids
            ]
            h._pitch_snapshot = session_pitches

            if h._pitch_count != summary.pitch_count:
                h._pitch_count = summary.pitch_count
                h._last_pitch_count = summary.pitch_count
                h._pitch_count_label.setText(f"Pitches: {h._pitch_count}")

            if new_pitches:
                for pitch in new_pitches:
                    h._session_tracker.add_pitch(pitch)
                    h._processed_pitch_ids.add(pitch.pitch_id)

                current_mode = h._mode_stack.currentWidget()
                if current_mode is None:
                    raise RuntimeError("Coaching mode stack contains an unsupported widget")
                mode = cast(BaseModeWidget, current_mode)
                mode.update_pitch_data(session_pitches, new_pitches=new_pitches)
                h._fatigue_indicator.update_pitches(session_pitches)

        except Exception as e:
            logger.error(f"Metrics update failed: {e}", exc_info=True)

    def update_quality_health(self) -> None:
        h = self._host
        diagnostics = h._service.get_quality_diagnostics()
        quality = diagnostics.get("quality") or {}
        status = str(quality.get("status") or "UNAVAILABLE")
        tone = {
            "VALIDATED": "success",
            "ESTIMATED": "info",
            "DEGRADED": "warning",
            "UNAVAILABLE": "warning",
            "REJECTED": "error",
        }.get(status, "info")
        h._quality_indicator.setText(f"Quality: {status.lower()}")
        h._style_manager.style_status_indicator(h._quality_indicator, tone)

    def show_quality_diagnostics(self) -> None:
        """Show full evidence dialog."""
        h = self._host
        diagnostics = h._service.get_quality_diagnostics()
        dialog = QtWidgets.QDialog(h)
        dialog.setWindowTitle("Tracking diagnostics")
        dialog.resize(760, 560)
        layout = QtWidgets.QVBoxLayout(dialog)
        explanation = QtWidgets.QLabel(
            "Detailed capture and tracking evidence. These values support setup and "
            "troubleshooting; they are intentionally hidden during normal coaching."
        )
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        details = QtWidgets.QPlainTextEdit()
        details.setReadOnly(True)
        details.setPlainText(json.dumps(diagnostics, indent=2, default=str))
        layout.addWidget(details, 1)
        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)
        dialog.exec()

    def apply_strike_zone_overlay_config(self, batter_height_in: float) -> None:
        """Push active strike-zone config into overlay-capable modes."""
        h = self._host
        h._strike_zone_overlay_config = h._strike_zone_overlay_config.with_batter_height(
            batter_height_in
        )
        for mode in (h._broadcast_mode, h._progression_mode, h._game_mode):
            mode.set_strike_zone_config(h._strike_zone_overlay_config)
