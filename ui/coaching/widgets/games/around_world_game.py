"""Around the World game for coaching mode."""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ui.coaching.widgets.games.base_game import BaseGame

if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary
    from ui.coaching.game_state_manager import GameStateManager


class AroundWorldGame(BaseGame):
    """Hit all 9 zones in sequence - fewest pitches wins."""

    # Clockwise sequence around perimeter + center
    SEQUENCE = [
        (0, 0), (0, 1), (0, 2),  # Top row
        (1, 2), (2, 2),           # Right side
        (2, 1), (2, 0),           # Bottom row
        (1, 0), (1, 1)            # Left side + center
    ]

    def __init__(
        self,
        game_state_manager: "GameStateManager",
        parent: Optional[QtWidgets.QWidget] = None
    ):
        """Initialize around the world game."""
        super().__init__(game_state_manager, parent)
        self._current_index = 0
        self._pitch_count = 0
        self._build_ui()

    def _build_ui(self) -> None:
        """Build game UI."""
        layout = QtWidgets.QVBoxLayout()

        title = QtWidgets.QLabel("AROUND THE WORLD")
        font = title.font()
        font.setPointSize(18)
        font.setBold(True)
        title.setFont(font)
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Progress display
        self._progress_label = QtWidgets.QLabel(f"Target: 1/{len(self.SEQUENCE)}")
        font = self._progress_label.font()
        font.setPointSize(16)
        font.setBold(True)
        self._progress_label.setFont(font)
        self._progress_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._progress_label)

        # Pitch counter
        self._pitch_label = QtWidgets.QLabel("Pitches: 0")
        font = self._pitch_label.font()
        font.setPointSize(14)
        self._pitch_label.setFont(font)
        self._pitch_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._pitch_label)

        # Grid display
        self._grid_widget = QtWidgets.QWidget()
        self._grid_widget.setMinimumSize(300, 300)
        layout.addWidget(self._grid_widget, 1)

        instructions = QtWidgets.QLabel("Hit zones in order. Target zone glows yellow.")
        instructions.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        reset_btn = QtWidgets.QPushButton("Restart")
        reset_btn.clicked.connect(self.reset_game)
        layout.addWidget(reset_btn)

        layout.addStretch()
        self.setLayout(layout)

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Paint the grid."""
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

        # Mark completed zones (green check)
        for i in range(self._current_index):
            row, col = self.SEQUENCE[i]
            x = col * cell_width
            y = row * cell_height
            painter.fillRect(x + 2, y + 2, cell_width - 4, cell_height - 4, QtGui.QColor(76, 175, 80, 100))
            painter.setPen(QtGui.QColor(76, 175, 80))
            font = painter.font()
            font.setPointSize(20)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(QtCore.QRect(x, y, cell_width, cell_height), QtCore.Qt.AlignmentFlag.AlignCenter, "✓")

        # Highlight current target (yellow)
        if self._current_index < len(self.SEQUENCE):
            row, col = self.SEQUENCE[self._current_index]
            x = col * cell_width
            y = row * cell_height
            painter.fillRect(x + 2, y + 2, cell_width - 4, cell_height - 4, QtGui.QColor(255, 235, 59, 150))

    def process_pitch(self, pitch: "PitchSummary") -> None:
        """Process pitch."""
        self._pitch_count += 1
        self._pitch_label.setText(f"Pitches: {self._pitch_count}")

        if pitch.zone_row is None or pitch.zone_col is None or not pitch.is_strike:
            return

        target_row, target_col = self.SEQUENCE[self._current_index]
        if pitch.zone_row == target_row and pitch.zone_col == target_col:
            self._current_index += 1
            self._progress_label.setText(f"Target: {self._current_index + 1}/{len(self.SEQUENCE)}")
            self.update()

            if self._current_index >= len(self.SEQUENCE):
                self.save_score(self._pitch_count)
                QtWidgets.QMessageBox.information(self, "Complete!", f"Finished in {self._pitch_count} pitches!")
                self.reset_game()

    def reset_game(self) -> None:
        """Reset game."""
        self._current_index = 0
        self._pitch_count = 0
        self._progress_label.setText(f"Target: 1/{len(self.SEQUENCE)}")
        self._pitch_label.setText("Pitches: 0")
        self.update()

    def get_game_name(self) -> str:
        """Get game name."""
        return "around_world"


__all__ = ["AroundWorldGame"]
