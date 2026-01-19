"""Target scoring game for coaching mode."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ui.coaching.widgets.games.base_game import BaseGame

if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary
    from ui.coaching.game_state_manager import GameStateManager


class TargetScoringGame(BaseGame):
    """Zone-based scoring with corner multipliers and streak bonuses."""

    # Point values per zone (corners worth more)
    ZONE_POINTS = [
        [5, 3, 5],  # Top row
        [3, 1, 3],  # Middle row
        [5, 3, 5]   # Bottom row
    ]

    def __init__(
        self,
        game_state_manager: "GameStateManager",
        parent: Optional[QtWidgets.QWidget] = None
    ):
        """Initialize target scoring game."""
        super().__init__(game_state_manager, parent)
        self._total_score = 0
        self._streak = 0
        self._build_ui()

    def _build_ui(self) -> None:
        """Build game UI."""
        layout = QtWidgets.QVBoxLayout()

        # Title
        title = QtWidgets.QLabel("TARGET SCORING")
        font = title.font()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Score display
        self._score_label = QtWidgets.QLabel("Score: 0")
        font = self._score_label.font()
        font.setPointSize(24)
        font.setBold(True)
        self._score_label.setFont(font)
        self._score_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._score_label.setStyleSheet("color: #2196F3;")
        layout.addWidget(self._score_label)

        # Streak display
        self._streak_label = QtWidgets.QLabel("Streak: 0")
        font = self._streak_label.font()
        font.setPointSize(14)
        self._streak_label.setFont(font)
        self._streak_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._streak_label)

        # Zone grid display
        self._grid_widget = QtWidgets.QWidget()
        self._grid_widget.setMinimumSize(300, 300)
        layout.addWidget(self._grid_widget, 1)

        # Instructions
        instructions = QtWidgets.QLabel("Corners = 5pts, Edges = 3pts, Middle = 1pt\nStreak bonus: +1pt per consecutive strike")
        instructions.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Reset button
        reset_btn = QtWidgets.QPushButton("Reset Score")
        reset_btn.clicked.connect(self.reset_game)
        layout.addWidget(reset_btn)

        layout.addStretch()
        self.setLayout(layout)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Paint the grid with point values."""
        super().paintEvent(event)

        painter = QtGui.QPainter(self._grid_widget)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        width = self._grid_widget.width()
        height = self._grid_widget.height()
        cell_width = width // 3
        cell_height = height // 3

        # Draw grid
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black, 2))
        for i in range(4):
            painter.drawLine(i * cell_width, 0, i * cell_width, height)
            painter.drawLine(0, i * cell_height, width, i * cell_height)

        # Draw point values
        font = painter.font()
        font.setPointSize(20)
        font.setBold(True)
        painter.setFont(font)

        for row in range(3):
            for col in range(3):
                points = self.ZONE_POINTS[row][col]
                x = col * cell_width
                y = row * cell_height

                # Color code by value
                if points == 5:
                    painter.setPen(QtGui.QColor(244, 67, 54))  # Red
                elif points == 3:
                    painter.setPen(QtGui.QColor(255, 152, 0))  # Orange
                else:
                    painter.setPen(QtGui.QColor(76, 175, 80))  # Green

                painter.drawText(
                    QtCore.QRect(x, y, cell_width, cell_height),
                    QtCore.Qt.AlignmentFlag.AlignCenter,
                    f"{points}"
                )

    def process_pitch(self, pitch: "PitchSummary") -> None:
        """Process pitch - award points."""
        if not pitch.is_strike:
            self._streak = 0
            self._streak_label.setText(f"Streak: {self._streak}")
            return

        if pitch.zone_row is None or pitch.zone_col is None:
            return

        base_points = self.ZONE_POINTS[pitch.zone_row][pitch.zone_col]
        self._streak += 1
        bonus = self._streak - 1
        total_points = base_points + bonus

        self._total_score += total_points
        self.save_score(self._total_score)

        self._score_label.setText(f"Score: {self._total_score}")
        self._streak_label.setText(f"Streak: {self._streak} (+{bonus} bonus)")

    def reset_game(self) -> None:
        """Reset game."""
        self._total_score = 0
        self._streak = 0
        self._score_label.setText("Score: 0")
        self._streak_label.setText("Streak: 0")

    def get_game_name(self) -> str:
        """Get game name."""
        return "target_scoring"


__all__ = ["TargetScoringGame"]
