"""Track session-wide statistics for progression visualization."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, List, Tuple

if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary


class SessionHistoryTracker:
    """Track session metrics for progression view.

    Maintains in-memory history of pitches during active session for
    real-time trend visualization.
    """

    def __init__(self, window_size: int = 10):
        """Initialize session history tracker.

        Args:
            window_size: Rolling window size for accuracy trends
        """
        self._pitches: List[dict] = []
        self._window_size = window_size

    def add_pitch(self, pitch: "PitchSummary") -> None:
        """Add pitch to history.

        Args:
            pitch: Pitch summary to add
        """
        self._pitches.append({
            "velocity": pitch.speed_mph or 0.0,
            "is_strike": pitch.is_strike,
            "timestamp": time.time(),
            "zone_row": pitch.zone_row,
            "zone_col": pitch.zone_col,
        })

    def get_velocity_history(self) -> List[Tuple[int, float]]:
        """Get velocity history for all pitches.

        Returns:
            List of (pitch_index, velocity_mph) tuples
        """
        return [(i, p["velocity"]) for i, p in enumerate(self._pitches)]

    def get_strike_accuracy_history(self) -> List[Tuple[int, float]]:
        """Get rolling strike accuracy history.

        Calculates strike percentage over a rolling window.

        Returns:
            List of (pitch_index, strike_percentage) tuples
        """
        result = []
        for i in range(len(self._pitches)):
            start = max(0, i - self._window_size + 1)
            window = self._pitches[start:i+1]
            strikes = sum(1 for p in window if p["is_strike"])
            accuracy = strikes / len(window) if window else 0.0
            result.append((i, accuracy))
        return result

    def get_fastest_pitch(self) -> float:
        """Get fastest pitch velocity in session.

        Returns:
            Maximum velocity in mph, or 0.0 if no pitches
        """
        if not self._pitches:
            return 0.0
        return max(p["velocity"] for p in self._pitches)

    def get_strike_ball_ratio(self) -> Tuple[int, int, float]:
        """Get strike/ball counts and ratio.

        Returns:
            Tuple of (strikes, balls, strike_percentage)
        """
        if not self._pitches:
            return (0, 0, 0.0)

        strikes = sum(1 for p in self._pitches if p["is_strike"])
        balls = len(self._pitches) - strikes
        percentage = strikes / len(self._pitches) if self._pitches else 0.0

        return (strikes, balls, percentage)

    def get_pitch_count(self) -> int:
        """Get total pitch count.

        Returns:
            Number of pitches in history
        """
        return len(self._pitches)

    def clear(self) -> None:
        """Clear history.

        Called when starting a new session.
        """
        self._pitches.clear()


__all__ = ["SessionHistoryTracker"]
