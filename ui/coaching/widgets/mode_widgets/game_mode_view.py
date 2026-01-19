"""Game mode view for coaching UI."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from PySide6 import QtWidgets

from ui.coaching.widgets.games.around_world_game import AroundWorldGame
from ui.coaching.widgets.games.speed_challenge_game import SpeedChallengeGame
from ui.coaching.widgets.games.target_scoring_game import TargetScoringGame
from ui.coaching.widgets.games.tic_tac_toe_game import TicTacToeGame
from ui.coaching.widgets.mode_widgets.base_mode_widget import BaseModeWidget

if TYPE_CHECKING:
    from contracts import Frame
    from app.pipeline_service import PitchSummary
    from ui.coaching.game_state_manager import GameStateManager

logger = logging.getLogger(__name__)


class GameModeWidget(BaseModeWidget):
    """Mode 3: Game Mode.

    Interactive games for pitch practice:
    - Tic-Tac-Toe (vs AI)
    - Target Scoring (zone points + streaks)
    - Around the World (hit all 9 zones)
    - Speed Challenge (velocity + location targets)
    """

    def __init__(
        self,
        game_state_manager: "GameStateManager",
        parent: Optional[QtWidgets.QWidget] = None
    ):
        """Initialize game mode.

        Args:
            game_state_manager: Game state manager for score persistence
            parent: Parent widget
        """
        super().__init__(parent)
        self._game_state_mgr = game_state_manager
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the widget UI."""
        layout = QtWidgets.QVBoxLayout()

        # Title and game selector
        selector_layout = QtWidgets.QHBoxLayout()

        title = QtWidgets.QLabel("GAME MODE")
        font = title.font()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        selector_layout.addWidget(title)

        selector_layout.addStretch()

        selector_layout.addWidget(QtWidgets.QLabel("Select Game:"))
        self._game_selector = QtWidgets.QComboBox()
        self._game_selector.addItems([
            "Tic-Tac-Toe",
            "Target Scoring",
            "Around the World",
            "Speed Challenge"
        ])
        self._game_selector.currentIndexChanged.connect(self._on_game_selected)
        selector_layout.addWidget(self._game_selector)

        layout.addLayout(selector_layout)

        # Stacked widget for games
        self._game_stack = QtWidgets.QStackedWidget()

        # Create all 4 games
        self._tic_tac_toe = TicTacToeGame(self._game_state_mgr)
        self._target_scoring = TargetScoringGame(self._game_state_mgr)
        self._around_world = AroundWorldGame(self._game_state_mgr)
        self._speed_challenge = SpeedChallengeGame(self._game_state_mgr)

        self._game_stack.addWidget(self._tic_tac_toe)
        self._game_stack.addWidget(self._target_scoring)
        self._game_stack.addWidget(self._around_world)
        self._game_stack.addWidget(self._speed_challenge)

        layout.addWidget(self._game_stack, 1)

        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.setLayout(layout)

    def _on_game_selected(self, index: int) -> None:
        """Handle game selection change.

        Args:
            index: Selected game index
        """
        self._game_stack.setCurrentIndex(index)
        game_names = ["Tic-Tac-Toe", "Target Scoring", "Around the World", "Speed Challenge"]
        logger.debug(f"Game mode: Selected {game_names[index]}")

    def update_pitch_data(self, recent_pitches: List["PitchSummary"]) -> None:
        """Update visualization with new pitch data.

        Args:
            recent_pitches: List of recent pitch summaries
        """
        if not recent_pitches:
            return

        # Forward latest pitch to active game
        latest_pitch = recent_pitches[-1]
        current_game = self._game_stack.currentWidget()
        if current_game:
            current_game.process_pitch(latest_pitch)

    def update_camera_frames(
        self,
        left_frame: Optional["Frame"],
        right_frame: Optional["Frame"]
    ) -> None:
        """Update camera preview frames.

        Game mode doesn't display camera (focus is on game).

        Args:
            left_frame: Left camera frame (unused)
            right_frame: Right camera frame (unused)
        """
        # Game mode doesn't display camera
        pass

    def clear(self) -> None:
        """Clear all visualizations."""
        # Reset all games
        self._tic_tac_toe.reset_game()
        self._target_scoring.reset_game()
        self._around_world.reset_game()
        self._speed_challenge.reset_game()
        logger.debug("Game mode: Cleared all games")

    def get_mode_name(self) -> str:
        """Return display name for this mode.

        Returns:
            Mode name
        """
        return "Game Mode"


__all__ = ["GameModeWidget"]
