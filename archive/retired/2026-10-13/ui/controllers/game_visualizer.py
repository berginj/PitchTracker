"""Game visualization and tic-tac-toe game controller.

Extracted from MainWindow to reduce god class complexity.
Manages plate map visualization and tic-tac-toe game logic.
"""

from __future__ import annotations

import random
from typing import Optional, Callable, TYPE_CHECKING

from log_config.logger import get_logger

if TYPE_CHECKING:
    from configs.settings import AppConfig
    from ui.widgets import PlateMapWidget
    from PySide6 import QtWidgets

logger = get_logger(__name__)


def _tic_tac_toe_winner(board: list[list[str]]) -> Optional[str]:
    """Check for tic-tac-toe winner.

    Returns:
        "X" if X wins, "O" if O wins, "draw" if draw, None if game ongoing.
    """
    # Check rows
    for row in board:
        if row[0] == row[1] == row[2] != "":
            return row[0]
    # Check columns
    for c in range(3):
        if board[0][c] == board[1][c] == board[2][c] != "":
            return board[0][c]
    # Check diagonals
    if board[0][0] == board[1][1] == board[2][2] != "":
        return board[0][0]
    if board[0][2] == board[1][1] == board[2][0] != "":
        return board[0][2]
    # Check draw
    if all(board[r][c] != "" for r in range(3) for c in range(3)):
        return "draw"
    return None


class GameVisualizer:
    """Manages plate map visualization and tic-tac-toe game.

    Responsibilities:
    - Tic-tac-toe game state management
    - Target mode for pitch practice
    - Plate map updates
    - Game score tracking
    """

    def __init__(
        self,
        plate_map: "PlateMapWidget",
        status_label: "QtWidgets.QLabel",
        score_label: "QtWidgets.QLabel",
        streak_label: "QtWidgets.QLabel",
        get_config: Callable[[], "AppConfig"],
        get_pitch_paths: Callable[[], list],
        build_strike_zone: Callable,
    ):
        """Initialize game visualizer.

        Args:
            plate_map: Plate map widget for visualization
            status_label: Label for game status messages
            score_label: Label for score display
            streak_label: Label for streak display
            get_config: Callback to get current config
            get_pitch_paths: Callback to get recent pitch paths
            build_strike_zone: Function to build strike zone from config
        """
        self._plate_map = plate_map
        self._status_label = status_label
        self._score_label = score_label
        self._streak_label = streak_label
        self._get_config = get_config
        self._get_pitch_paths = get_pitch_paths
        self._build_strike_zone = build_strike_zone

        # Game state
        self._board: list[list[str]] = [["", "", ""], ["", "", ""], ["", "", ""]]
        self._score_x = 0
        self._score_o = 0
        self._round = 0
        self._streak = 0

        # Target mode state
        self._target_mode = False
        self._target_cell: Optional[tuple[int, int]] = None

        # Last pitch tracking
        self._last_pitch_id: Optional[str] = None
        self._recent_pitch_paths: list = []

        logger.debug("GameVisualizer initialized")

    @property
    def board(self) -> list[list[str]]:
        """Get current tic-tac-toe board."""
        return self._board

    @property
    def target_mode(self) -> bool:
        """Check if target mode is enabled."""
        return self._target_mode

    def update_plate_map_zone(self) -> None:
        """Update strike zone on plate map."""
        config = self._get_config()
        zone = self._build_strike_zone(
            plate_z_ft=config.metrics.plate_plane_z_ft,
            plate_width_in=config.strike_zone.plate_width_in,
            plate_length_in=config.strike_zone.plate_length_in,
            batter_height_in=config.strike_zone.batter_height_in,
            top_ratio=config.strike_zone.top_ratio,
            bottom_ratio=config.strike_zone.bottom_ratio,
        )
        self._plate_map.set_zone(zone)

    def update_plate_map(self, summary) -> None:
        """Update plate map with recent pitch data.

        Args:
            summary: Session summary with pitch data
        """
        paths = self._get_pitch_paths()
        self._recent_pitch_paths = paths
        self._plate_map.set_pitch_paths(paths)

        if summary.pitches:
            last_pitch = summary.pitches[-1]
            if last_pitch.pitch_id != self._last_pitch_id:
                self._last_pitch_id = last_pitch.pitch_id
                if self._target_mode:
                    self._apply_target_mode(last_pitch)
                else:
                    self._apply_pitch_to_tic_tac_toe(last_pitch)
                self._plate_map.set_board(self._board)
                self._update_game_labels()
            crossing = self._pitch_crossing_xy(last_pitch)
            self._plate_map.set_crossing_point(crossing)
        else:
            self._plate_map.set_crossing_point(None)

    def _pitch_crossing_xy(self, pitch) -> Optional[tuple[float, float]]:
        """Extract (x, y) crossing point from pitch.

        Args:
            pitch: Pitch result object

        Returns:
            (x, y) tuple if available, None otherwise
        """
        if pitch is None:
            return None
        x = getattr(pitch, "trajectory_plate_x_ft", None)
        y = getattr(pitch, "trajectory_plate_y_ft", None)
        if x is not None and y is not None:
            return (x, y)
        return None

    def _apply_pitch_to_tic_tac_toe(self, pitch) -> None:
        """Apply pitch to tic-tac-toe game.

        Args:
            pitch: Pitch result with zone_row and zone_col
        """
        row = pitch.zone_row
        col = pitch.zone_col
        if row is not None and col is not None:
            r = max(1, min(3, row)) - 1
            c = max(1, min(3, col)) - 1
            if self._board[r][c] == "":
                self._board[r][c] = "X"
            else:
                self._mark_ai()
        else:
            self._mark_ai()

        winner = _tic_tac_toe_winner(self._board)
        if winner:
            self._round += 1
            if winner == "X":
                self._score_x += 1
                self._streak += 1
                self._status_label.setText("Win! Keep the streak alive.")
            elif winner == "O":
                self._score_o += 1
                self._streak = 0
                self._status_label.setText("AI takes the round.")
            else:
                self._streak = 0
                self._status_label.setText("Draw round.")
            self._board = [["", "", ""], ["", "", ""], ["", "", ""]]

    def _mark_ai(self) -> None:
        """Mark a random empty cell for the AI."""
        empty = [(r, c) for r in range(3) for c in range(3) if self._board[r][c] == ""]
        if not empty:
            return
        r, c = random.choice(empty)
        self._board[r][c] = "O"

    def reset_game(self) -> None:
        """Reset tic-tac-toe game to initial state."""
        self._board = [["", "", ""], ["", "", ""], ["", "", ""]]
        self._score_x = 0
        self._score_o = 0
        self._round = 0
        self._streak = 0
        self._status_label.setText("Ready.")
        self._plate_map.set_board(self._board)
        self._target_cell = None
        self._plate_map.set_target_cell(None)
        self._update_game_labels()
        logger.info("Game reset")

    def _update_game_labels(self) -> None:
        """Update game score and streak labels."""
        self._score_label.setText(f"Score X:{self._score_x}  O:{self._score_o}  R:{self._round}")
        self._streak_label.setText(f"Streak: {self._streak}")

    def set_target_mode(self, enabled: bool) -> None:
        """Enable or disable target mode.

        Args:
            enabled: True to enable target mode
        """
        self._target_mode = enabled
        if enabled:
            self._target_cell = self._random_target_cell()
            self._status_label.setText("Hit the highlighted target.")
            self._plate_map.set_target_cell(self._target_cell)
            logger.info("Target mode enabled")
        else:
            self._target_cell = None
            self._plate_map.set_target_cell(None)
            logger.info("Target mode disabled")

    def _apply_target_mode(self, pitch) -> None:
        """Apply pitch in target mode.

        Args:
            pitch: Pitch result with zone_row and zone_col
        """
        if not self._target_mode or self._target_cell is None:
            return

        row = pitch.zone_row
        col = pitch.zone_col
        if row is None or col is None:
            self._streak = 0
            self._status_label.setText("Missed. New target.")
        else:
            cell = (max(1, min(3, row)) - 1, max(1, min(3, col)) - 1)
            if cell == self._target_cell:
                self._score_x += 1
                self._streak += 1
                self._status_label.setText("Target hit!")
            else:
                self._streak = 0
                self._status_label.setText("Missed. New target.")

        self._round += 1
        self._target_cell = self._random_target_cell()
        self._plate_map.set_target_cell(self._target_cell)
        self._update_game_labels()

    def _random_target_cell(self) -> tuple[int, int]:
        """Generate random target cell.

        Returns:
            (row, col) tuple for target cell
        """
        return (random.randint(0, 2), random.randint(0, 2))
