"""Game widgets for game mode."""

from ui.coaching.widgets.games.around_world_game import AroundWorldGame
from ui.coaching.widgets.games.base_game import BaseGame
from ui.coaching.widgets.games.speed_challenge_game import SpeedChallengeGame
from ui.coaching.widgets.games.target_scoring_game import TargetScoringGame
from ui.coaching.widgets.games.tic_tac_toe_game import TicTacToeGame

__all__ = [
    "BaseGame",
    "TicTacToeGame",
    "TargetScoringGame",
    "AroundWorldGame",
    "SpeedChallengeGame",
]
