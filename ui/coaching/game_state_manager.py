"""Persist game scores and leaderboards."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


class GameStateManager:
    """Manage persistent storage of game scores and leaderboards.

    Stores scores in JSON format at configs/game_scores.json.
    Tracks both session scores and all-time high scores.
    """

    def __init__(self, scores_file: Path = Path("configs/game_scores.json")):
        """Initialize game state manager.

        Args:
            scores_file: Path to scores JSON file
        """
        self._scores_file = scores_file
        self._scores = self._load_scores()

    def _load_scores(self) -> Dict:
        """Load scores from disk.

        Returns:
            Dictionary of game scores
        """
        if not self._scores_file.exists():
            # Create default structure
            return {
                "tic_tac_toe": {
                    "high_score_wins": 0,
                    "total_games": 0,
                    "history": []
                },
                "target_scoring": {
                    "high_score": 0,
                    "total_games": 0,
                    "history": []
                },
                "around_world": {
                    "best_pitches": 999,  # Lower is better
                    "total_games": 0,
                    "history": []
                },
                "speed_challenge": {
                    "high_score_targets": 0,
                    "total_games": 0,
                    "history": []
                }
            }

        try:
            return json.loads(self._scores_file.read_text())
        except Exception as e:
            logger.error(f"Failed to load game scores: {e}")
            return self._load_scores()  # Return defaults

    def _save_scores(self) -> None:
        """Save scores to disk."""
        try:
            # Ensure directory exists
            self._scores_file.parent.mkdir(parents=True, exist_ok=True)

            # Write atomically (temp file + rename)
            temp_file = self._scores_file.with_suffix(".tmp")
            temp_file.write_text(json.dumps(self._scores, indent=2))
            temp_file.replace(self._scores_file)

            logger.debug(f"Saved game scores to {self._scores_file}")
        except Exception as e:
            logger.error(f"Failed to save game scores: {e}")

    def save_game_score(
        self,
        game_name: str,
        score: int,
        timestamp: float = None
    ) -> None:
        """Save score for a game.

        Args:
            game_name: Game identifier (tic_tac_toe, target_scoring, etc.)
            score: Score to save
            timestamp: Time of score (default: now)
        """
        if timestamp is None:
            timestamp = time.time()

        if game_name not in self._scores:
            logger.warning(f"Unknown game: {game_name}")
            return

        game_data = self._scores[game_name]

        # Add to history
        game_data["history"].append({
            "score": score,
            "timestamp": timestamp
        })

        # Increment total games
        game_data["total_games"] = game_data.get("total_games", 0) + 1

        # Update high score (game-specific logic)
        if game_name == "tic_tac_toe":
            # Wins counter
            current_high = game_data.get("high_score_wins", 0)
            if score > current_high:
                game_data["high_score_wins"] = score
        elif game_name == "around_world":
            # Lower is better (fewest pitches)
            current_best = game_data.get("best_pitches", 999)
            if score < current_best:
                game_data["best_pitches"] = score
        else:
            # Higher is better (target_scoring, speed_challenge)
            current_high = game_data.get("high_score", 0)
            if score > current_high:
                game_data["high_score"] = score

        # Keep last 100 scores
        if len(game_data["history"]) > 100:
            game_data["history"] = game_data["history"][-100:]

        # Save to disk
        self._save_scores()

    def get_high_score(self, game_name: str) -> int:
        """Get all-time high score for a game.

        Args:
            game_name: Game identifier

        Returns:
            High score, or 0/999 if no scores
        """
        if game_name not in self._scores:
            return 0

        game_data = self._scores[game_name]

        if game_name == "tic_tac_toe":
            return game_data.get("high_score_wins", 0)
        elif game_name == "around_world":
            return game_data.get("best_pitches", 999)
        else:
            return game_data.get("high_score", 0)

    def get_session_scores(
        self,
        game_name: str,
        session_start: float
    ) -> List[int]:
        """Get scores from current session.

        Args:
            game_name: Game identifier
            session_start: Session start timestamp

        Returns:
            List of scores since session start
        """
        if game_name not in self._scores:
            return []

        history = self._scores[game_name].get("history", [])
        return [
            s["score"]
            for s in history
            if s["timestamp"] >= session_start
        ]

    def get_total_games(self, game_name: str) -> int:
        """Get total games played.

        Args:
            game_name: Game identifier

        Returns:
            Total games played
        """
        if game_name not in self._scores:
            return 0
        return self._scores[game_name].get("total_games", 0)


__all__ = ["GameStateManager"]
