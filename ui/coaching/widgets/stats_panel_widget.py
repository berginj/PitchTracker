"""Statistics panel widget for broadcast view mode."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ui.themes import apply_standard_layout, get_style_manager

if TYPE_CHECKING:
    from app.contracts import PitchSummary


class StatsPanelWidget(QtWidgets.QWidget):
    """Statistics panel showing latest pitch data and recent pitch list.

    Displays speed, break, result for latest pitch, plus scrollable list
    of recent pitches.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        """Initialize stats panel widget.

        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the widget UI."""
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        # Title
        title = QtWidgets.QLabel("Latest Pitch Stats")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._style_manager.style_label(title, "sectionTitle")
        layout.addWidget(title)

        # Speed display (large, prominent)
        self._speed_label = QtWidgets.QLabel("Speed: -- mph")
        self._speed_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._style_manager.style_label(self._speed_label, "metricAccent")
        layout.addWidget(self._speed_label)

        # H-break
        self._h_break_label = QtWidgets.QLabel("H-Break: -- in")
        self._h_break_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._style_manager.style_label(self._h_break_label, "muted")
        layout.addWidget(self._h_break_label)

        # V-break
        self._v_break_label = QtWidgets.QLabel("V-Break: -- in")
        self._v_break_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._style_manager.style_label(self._v_break_label, "muted")
        layout.addWidget(self._v_break_label)

        # Result
        self._result_label = QtWidgets.QLabel("Result: --")
        self._result_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._style_manager.style_label(self._result_label, "sectionTitle")
        layout.addWidget(self._result_label)

        # Separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # Recent pitches title
        recent_title = QtWidgets.QLabel("Recent Pitches")
        self._style_manager.style_label(recent_title, "eyebrow")
        layout.addWidget(recent_title)

        # Recent pitches list
        self._recent_list = QtWidgets.QListWidget()
        self._recent_list.setMaximumHeight(300)
        layout.addWidget(self._recent_list, 1)

        layout.addStretch()
        self.setLayout(layout)
        self.setProperty("surface", "card")
        self._style_manager.polish(self)

    def update_latest_pitch(self, pitch: "PitchSummary") -> None:
        """Update display with latest pitch data.

        Args:
            pitch: Latest pitch summary
        """
        # Speed
        if pitch.speed_mph is not None:
            self._speed_label.setText(f"Speed: {pitch.speed_mph:.1f} mph")
        else:
            self._speed_label.setText("Speed: -- mph")

        # The legacy run/rise fields are raw endpoint displacement today, not
        # validated induced break. Keep them in diagnostics but do not present
        # them to a coach under a stronger physical label.
        movement_validated = bool((pitch.quality_diagnostics or {}).get("movement_validated"))
        if movement_validated:
            h_break = pitch.run_in
            v_break = pitch.rise_in
            self._h_break_label.setText(f"H-Break: {h_break:+.1f} in")
            self._v_break_label.setText(f"V-Break: {v_break:+.1f} in")
        else:
            self._h_break_label.setText("H-Break: unavailable")
            self._v_break_label.setText("V-Break: unavailable")
            detail = "Raw endpoint displacement is available in Diagnostics; induced break is not validated."
            self._h_break_label.setToolTip(detail)
            self._v_break_label.setToolTip(detail)

        # Result (color-coded)
        if pitch.measurement_status in {"REJECTED", "UNAVAILABLE"}:
            self._result_label.setText("Result: UNAVAILABLE")
            self._style_manager.style_status_indicator(self._result_label, "warning")
        elif pitch.is_strike:
            self._result_label.setText("Result: STRIKE")
            self._style_manager.style_status_indicator(self._result_label, "success")
        else:
            self._result_label.setText("Result: BALL")
            self._style_manager.style_status_indicator(self._result_label, "error")

    def update_recent_list(self, recent_pitches: List["PitchSummary"]) -> None:
        """Update recent pitches list.

        Args:
            recent_pitches: List of recent pitches (last 10 recommended)
        """
        self._recent_list.clear()

        # Show last 10 pitches, newest first
        display_pitches = recent_pitches[-10:][::-1]

        theme = self._style_manager.theme

        for i, pitch in enumerate(display_pitches):
            # Format: "#1: 85.3 mph - STRIKE"
            pitch_num = len(recent_pitches) - i
            speed_str = f"{pitch.speed_mph:.1f}" if pitch.speed_mph else "--"
            if pitch.measurement_status in {"REJECTED", "UNAVAILABLE"}:
                result_str = str(pitch.measurement_status)
            else:
                result_str = "STRIKE" if pitch.is_strike else "BALL"

            item_text = f"#{pitch_num}: {speed_str} mph - {result_str}"

            # Color code by result using theme colors
            item = QtWidgets.QListWidgetItem(item_text)
            if pitch.is_strike:
                item.setForeground(QtGui.QColor(theme.accent_success))
            else:
                item.setForeground(QtGui.QColor(theme.accent_error))

            self._recent_list.addItem(item)

    def clear(self) -> None:
        """Clear all displays."""
        self._speed_label.setText("Speed: -- mph")
        self._h_break_label.setText("H-Break: -- in")
        self._v_break_label.setText("V-Break: -- in")
        self._h_break_label.setToolTip("")
        self._v_break_label.setToolTip("")
        self._result_label.setText("Result: --")
        self._style_manager.style_label(self._result_label, "sectionTitle")
        self._recent_list.clear()


__all__ = ["StatsPanelWidget"]
