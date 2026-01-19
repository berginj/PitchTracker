"""Base class for all coaching games."""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING, Optional

from PySide6 import QtWidgets
from PySide6.QtCore import QObject

if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary
    from ui.coaching.game_state_manager import GameStateManager


# Combined metaclass for Qt + ABC
class QABCMeta(type(QObject), ABCMeta):
    """Metaclass that combines Qt's metaclass with ABCMeta."""
    pass


class BaseGame(QtWidgets.QWidget, metaclass=QABCMeta):
    """Abstract base class for all coaching games.

    All games must inherit from this class and implement the required methods.
    """

    def __init__(
        self,
        game_state_manager: "GameStateManager",
        parent: Optional[QtWidgets.QWidget] = None
    ):
        """Initialize base game.

        Args:
            game_state_manager: Game state manager for score persistence
            parent: Parent widget
        """
        super().__init__(parent)
        self._state_mgr = game_state_manager
        self._session_score = 0
        self._session_start_time = 0.0

    @abstractmethod
    def process_pitch(self, pitch: "PitchSummary") -> None:
        """Process incoming pitch and update game state.

        Args:
            pitch: Pitch summary with zone location and metrics
        """
        pass

    @abstractmethod
    def reset_game(self) -> None:
        """Reset game to initial state.

        Called when starting a new game or after completion.
        """
        pass

    @abstractmethod
    def get_game_name(self) -> str:
        """Return game identifier for leaderboard.

        Returns:
            Game name (e.g., "tic_tac_toe", "target_scoring")
        """
        pass

    def save_score(self, score: int) -> None:
        """Save score to persistent storage.

        Args:
            score: Score to save
        """
        import time
        self._state_mgr.save_game_score(
            game_name=self.get_game_name(),
            score=score,
            timestamp=time.time()
        )

    def get_high_score(self) -> int:
        """Get all-time high score for this game.

        Returns:
            High score
        """
        return self._state_mgr.get_high_score(self.get_game_name())

    def get_total_games(self) -> int:
        """Get total games played.

        Returns:
            Total games played
        """
        return self._state_mgr.get_total_games(self.get_game_name())


__all__ = ["BaseGame"]
