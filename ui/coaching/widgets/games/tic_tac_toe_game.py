"""Tic-Tac-Toe game for coaching mode."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ui.coaching.widgets.games.base_game import BaseGame
from ui.themes import get_style_manager, show_message_dialog

if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary
    from ui.coaching.game_state_manager import GameStateManager


class TicTacToeGame(BaseGame):
    """3x3 Tic-Tac-Toe game - pitcher vs AI or solo patterns."""

    def __init__(self, game_state_manager: "GameStateManager", parent: Optional[QtWidgets.QWidget] = None):
        """Initialize tic-tac-toe game.

        Args:
            game_state_manager: Game state manager
            parent: Parent widget
        """
        super().__init__(game_state_manager, parent)
        self._style_manager = get_style_manager()
        self._grid = [[None] * 3 for _ in range(3)]  # None, 'X', or 'O'
        self._wins = 0
        self._losses = 0
        self._build_ui()

    def _build_ui(self) -> None:
        """Build game UI."""
        layout = QtWidgets.QVBoxLayout()

        # Title
        title = QtWidgets.QLabel("TIC-TAC-TOE")
        self._style_manager.style_label(title, "pageTitle")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Score display
        self._score_label = QtWidgets.QLabel("Wins: 0 | Losses: 0")
        self._style_manager.style_label(self._score_label, "sectionTitle")
        self._score_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._score_label)

        # Grid display
        self._grid_widget = QtWidgets.QWidget()
        self._grid_widget.setMinimumSize(300, 300)
        layout.addWidget(self._grid_widget, 1)

        # Instructions
        instructions = QtWidgets.QLabel("Hit zones to play X. AI plays O.")
        self._style_manager.style_label(instructions, "muted")
        instructions.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Reset button
        reset_btn = QtWidgets.QPushButton("New Game")
        reset_btn.clicked.connect(self.reset_game)
        self._style_manager.style_button(reset_btn, "ghost")
        layout.addWidget(reset_btn)

        layout.addStretch()
        self._style_manager.apply_standard_layout(layout)
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

        # Draw grid lines
        painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.black, 2))
        for i in range(1, 3):
            painter.drawLine(i * cell_width, 0, i * cell_width, height)
            painter.drawLine(0, i * cell_height, width, i * cell_height)

        # Draw X's and O's
        theme = self._style_manager.get_theme()
        for row in range(3):
            for col in range(3):
                x = col * cell_width
                y = row * cell_height
                mark = self._grid[row][col]

                if mark == "X":
                    painter.setPen(QtGui.QPen(QtGui.QColor(theme.accent_info), 4))
                    painter.drawLine(x + 20, y + 20, x + cell_width - 20, y + cell_height - 20)
                    painter.drawLine(x + cell_width - 20, y + 20, x + 20, y + cell_height - 20)
                elif mark == "O":
                    painter.setPen(QtGui.QPen(QtGui.QColor(theme.accent_error), 4))
                    painter.drawEllipse(x + 20, y + 20, cell_width - 40, cell_height - 40)

    def process_pitch(self, pitch: "PitchSummary") -> None:
        """Process pitch - mark zone if valid."""
        if pitch.zone_row is None or pitch.zone_col is None:
            return
        if not pitch.is_strike:
            return

        row, col = pitch.zone_row, pitch.zone_col

        # Place X if empty
        if self._grid[row][col] is None:
            self._grid[row][col] = "X"
            self.update()

            # Check win
            if self._check_win("X"):
                self._wins += 1
                self.save_score(self._wins)
                self._update_score()
                show_message_dialog(self, "Winner!", "You win!", tone="success")
                self.reset_game()
            elif self._is_full():
                show_message_dialog(self, "Tie", "Game tied!", tone="info")
                self.reset_game()
            else:
                # AI move
                self._ai_move()

    def _ai_move(self) -> None:
        """Simple AI move - random empty cell."""
        empty_cells = [(r, c) for r in range(3) for c in range(3) if self._grid[r][c] is None]
        if empty_cells:
            row, col = random.choice(empty_cells)
            self._grid[row][col] = "O"
            self.update()

            if self._check_win("O"):
                self._losses += 1
                self._update_score()
                show_message_dialog(self, "Loss", "AI wins!", tone="warning")
                self.reset_game()
            elif self._is_full():
                show_message_dialog(self, "Tie", "Game tied!", tone="info")
                self.reset_game()

    def _check_win(self, mark: str) -> bool:
        """Check if mark has won."""
        # Rows
        for row in self._grid:
            if all(cell == mark for cell in row):
                return True
        # Cols
        for col in range(3):
            if all(self._grid[row][col] == mark for row in range(3)):
                return True
        # Diagonals
        if all(self._grid[i][i] == mark for i in range(3)):
            return True
        if all(self._grid[i][2 - i] == mark for i in range(3)):
            return True
        return False

    def _is_full(self) -> bool:
        """Check if grid is full."""
        return all(cell is not None for row in self._grid for cell in row)

    def _update_score(self) -> None:
        """Update score display."""
        self._score_label.setText(f"Wins: {self._wins} | Losses: {self._losses}")

    def reset_game(self) -> None:
        """Reset game."""
        self._grid = [[None] * 3 for _ in range(3)]
        self.update()

    def get_game_name(self) -> str:
        """Get game name."""
        return "tic_tac_toe"


__all__ = ["TicTacToeGame"]
