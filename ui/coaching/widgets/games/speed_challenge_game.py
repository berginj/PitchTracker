"""Speed Challenge game for coaching mode."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ui.coaching.widgets.games.base_game import BaseGame
from ui.themes import apply_standard_layout, get_style_manager, show_message_dialog

if TYPE_CHECKING:
    from app.contracts import PitchSummary
    from ui.coaching.game_state_manager import GameStateManager


class SpeedChallengeGame(BaseGame):
    """Velocity + location targets with difficulty levels."""

    DIFFICULTY_LEVELS = {
        "Easy": {"min_speed": 40, "tolerance": 3},
        "Medium": {"min_speed": 50, "tolerance": 2},
        "Hard": {"min_speed": 60, "tolerance": 1},
    }

    def __init__(self, game_state_manager: "GameStateManager", parent: Optional[QtWidgets.QWidget] = None):
        """Initialize speed challenge game."""
        super().__init__(game_state_manager, parent)
        self._style_manager = get_style_manager()
        self._difficulty = "Easy"
        self._current_target: dict[str, int] | None = None
        self._completed_targets = 0
        self._build_ui()
        self._generate_target()

    def _build_ui(self) -> None:
        """Build game UI."""
        layout = QtWidgets.QVBoxLayout()

        title = QtWidgets.QLabel("SPEED CHALLENGE")
        self._style_manager.style_label(title, "pageTitle")
        title.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        # Difficulty selector
        diff_layout = QtWidgets.QHBoxLayout()
        diff_label = QtWidgets.QLabel("Difficulty:")
        self._style_manager.style_label(diff_label, "muted")
        diff_layout.addWidget(diff_label)
        self._diff_combo = QtWidgets.QComboBox()
        self._diff_combo.addItems(["Easy", "Medium", "Hard"])
        self._diff_combo.currentTextChanged.connect(self._on_difficulty_changed)
        diff_layout.addWidget(self._diff_combo)
        diff_layout.addStretch()
        layout.addLayout(diff_layout)

        # Target display
        self._target_label = QtWidgets.QLabel("Target: -- mph, Zone --")
        self._style_manager.style_label(self._target_label, "sectionTitle")
        self._target_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._target_label)

        # Score display
        self._score_label = QtWidgets.QLabel("Targets Hit: 0")
        self._style_manager.style_label(self._score_label, "sectionTitle")
        self._score_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._score_label)

        # Grid display
        self._grid_widget = QtWidgets.QWidget()
        self._grid_widget.setMinimumSize(300, 300)
        layout.addWidget(self._grid_widget, 1)

        instructions = QtWidgets.QLabel("Hit target zone at target speed (±tolerance)")
        self._style_manager.style_label(instructions, "muted")
        instructions.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(instructions)

        reset_btn = QtWidgets.QPushButton("New Target")
        reset_btn.clicked.connect(self._generate_target)
        self._style_manager.style_button(reset_btn, "ghost")
        layout.addWidget(reset_btn)

        layout.addStretch()
        apply_standard_layout(layout)
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

        # Highlight target zone
        if self._current_target:
            theme = self._style_manager.get_theme()
            row, col = self._current_target["zone_row"], self._current_target["zone_col"]
            x = col * cell_width
            y = row * cell_height
            warning_color = QtGui.QColor(theme.accent_warning)
            warning_color.setAlpha(150)
            painter.fillRect(x + 2, y + 2, cell_width - 4, cell_height - 4, warning_color)

    def _generate_target(self) -> None:
        """Generate random target."""
        config = self.DIFFICULTY_LEVELS[self._difficulty]
        self._current_target = {
            "speed": config["min_speed"] + random.randint(0, 20),
            "zone_row": random.randint(0, 2),
            "zone_col": random.randint(0, 2),
        }
        self._target_label.setText(
            f"Target: {self._current_target['speed']} mph, "
            f"Zone [{self._current_target['zone_row']},{self._current_target['zone_col']}]"
        )
        self.update()

    def _on_difficulty_changed(self, difficulty: str) -> None:
        """Handle difficulty change."""
        self._difficulty = difficulty
        self._generate_target()

    def process_pitch(self, pitch: "PitchSummary") -> None:
        """Process pitch."""
        if not self._current_target or not pitch.is_strike:
            return

        speed_mph = pitch.speed_mph or 0
        config = self.DIFFICULTY_LEVELS[self._difficulty]

        # Check speed
        speed_ok = abs(speed_mph - self._current_target["speed"]) <= config["tolerance"]

        # Check zone
        zone_ok = (
            pitch.zone_row == self._current_target["zone_row"] and pitch.zone_col == self._current_target["zone_col"]
        )

        if speed_ok and zone_ok:
            self._completed_targets += 1
            self.save_score(self._completed_targets)
            self._score_label.setText(f"Targets Hit: {self._completed_targets}")
            show_message_dialog(self, "Hit!", "Target achieved!", tone="success")
            self._generate_target()

    def reset_game(self) -> None:
        """Reset game."""
        self._completed_targets = 0
        self._score_label.setText("Targets Hit: 0")
        self._generate_target()

    def get_game_name(self) -> str:
        """Get game name."""
        return "speed_challenge"


__all__ = ["SpeedChallengeGame"]
