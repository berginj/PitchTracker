"""Statistics panel widget for broadcast view mode."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary


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
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the widget UI."""
        layout = QtWidgets.QVBoxLayout()

        # Title
        title = QtWidgets.QLabel("Latest Pitch Stats")
        font = title.font()
        font.setPointSize(14)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Speed display (large, prominent)
        self._speed_label = QtWidgets.QLabel("Speed: -- mph")
        font = self._speed_label.font()
        font.setPointSize(18)
        font.setBold(True)
        self._speed_label.setFont(font)
        self._speed_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._speed_label.setStyleSheet("color: #2196F3;")  # Blue
        layout.addWidget(self._speed_label)

        # H-break
        self._h_break_label = QtWidgets.QLabel("H-Break: -- in")
        font = self._h_break_label.font()
        font.setPointSize(12)
        self._h_break_label.setFont(font)
        self._h_break_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._h_break_label)

        # V-break
        self._v_break_label = QtWidgets.QLabel("V-Break: -- in")
        font = self._v_break_label.font()
        font.setPointSize(12)
        self._v_break_label.setFont(font)
        self._v_break_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._v_break_label)

        # Result
        self._result_label = QtWidgets.QLabel("Result: --")
        font = self._result_label.font()
        font.setPointSize(14)
        font.setBold(True)
        self._result_label.setFont(font)
        self._result_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._result_label)

        # Separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # Recent pitches title
        recent_title = QtWidgets.QLabel("Recent Pitches")
        font = recent_title.font()
        font.setPointSize(12)
        font.setBold(True)
        recent_title.setFont(font)
        layout.addWidget(recent_title)

        # Recent pitches list
        self._recent_list = QtWidgets.QListWidget()
        self._recent_list.setMaximumHeight(300)
        layout.addWidget(self._recent_list, 1)

        layout.addStretch()
        self.setLayout(layout)

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

        # H-break (run_in)
        h_break = pitch.run_in
        if h_break >= 0:
            self._h_break_label.setText(f"H-Break: +{h_break:.1f} in")
        else:
            self._h_break_label.setText(f"H-Break: {h_break:.1f} in")

        # V-break (rise_in)
        v_break = pitch.rise_in
        if v_break >= 0:
            self._v_break_label.setText(f"V-Break: +{v_break:.1f} in")
        else:
            self._v_break_label.setText(f"V-Break: {v_break:.1f} in")

        # Result (color-coded)
        if pitch.is_strike:
            self._result_label.setText("Result: STRIKE")
            self._result_label.setStyleSheet("color: #4CAF50;")  # Green
        else:
            self._result_label.setText("Result: BALL")
            self._result_label.setStyleSheet("color: #FF5722;")  # Red

    def update_recent_list(self, recent_pitches: List["PitchSummary"]) -> None:
        """Update recent pitches list.

        Args:
            recent_pitches: List of recent pitches (last 10 recommended)
        """
        self._recent_list.clear()

        # Show last 10 pitches, newest first
        display_pitches = recent_pitches[-10:][::-1]

        for i, pitch in enumerate(display_pitches):
            # Format: "#1: 85.3 mph - STRIKE"
            pitch_num = len(recent_pitches) - i
            speed_str = f"{pitch.speed_mph:.1f}" if pitch.speed_mph else "--"
            result_str = "STRIKE" if pitch.is_strike else "BALL"

            item_text = f"#{pitch_num}: {speed_str} mph - {result_str}"

            # Color code by result
            item = QtWidgets.QListWidgetItem(item_text)
            if pitch.is_strike:
                item.setForeground(QtGui.QColor("#4CAF50"))  # Green
            else:
                item.setForeground(QtGui.QColor("#FF5722"))  # Red

            self._recent_list.addItem(item)

    def clear(self) -> None:
        """Clear all displays."""
        self._speed_label.setText("Speed: -- mph")
        self._h_break_label.setText("H-Break: -- in")
        self._v_break_label.setText("V-Break: -- in")
        self._result_label.setText("Result: --")
        self._result_label.setStyleSheet("")  # Reset color
        self._recent_list.clear()


__all__ = ["StatsPanelWidget"]
