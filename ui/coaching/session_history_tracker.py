"""Track session-wide statistics for progression visualization."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, List, Optional, Tuple

from app.contracts import measurement_is_usable

if TYPE_CHECKING:
    from app.contracts import PitchSummary


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
        usable = measurement_is_usable(pitch)
        self._pitches.append(
            {
                "velocity": pitch.speed_mph if usable else None,
                "is_strike": pitch.is_strike if usable else None,
                "usable": usable,
                "timestamp": time.time(),
                "zone_row": pitch.zone_row,
                "zone_col": pitch.zone_col,
            }
        )

    def get_velocity_history(self) -> List[Tuple[int, float]]:
        """Get velocity history for all pitches.

        Returns:
            List of (pitch_index, velocity_mph) tuples
        """
        return [(i, p["velocity"]) for i, p in enumerate(self._pitches) if p["velocity"] is not None]

    def get_strike_accuracy_history(self) -> List[Tuple[int, float]]:
        """Get rolling strike accuracy history.

        Calculates strike percentage over a rolling window.

        Returns:
            List of (pitch_index, strike_percentage) tuples
        """
        result = []
        for i in range(len(self._pitches)):
            start = max(0, i - self._window_size + 1)
            window = self._pitches[start : i + 1]
            classified = [p for p in window if p["usable"]]
            if classified:
                strikes = sum(1 for p in classified if p["is_strike"])
                result.append((i, strikes / len(classified)))
        return result

    def get_fastest_pitch(self) -> Optional[float]:
        """Get fastest pitch velocity in session.

        Returns:
            Maximum measured velocity in mph, or None if none is available
        """
        velocities = [p["velocity"] for p in self._pitches if p["velocity"] is not None]
        return max(velocities) if velocities else None

    def get_strike_ball_ratio(self) -> Tuple[int, int, float]:
        """Get strike/ball counts and ratio.

        Returns:
            Tuple of (strikes, balls, strike_percentage)
        """
        classified = [p for p in self._pitches if p["usable"]]
        if not classified:
            return (0, 0, 0.0)

        strikes = sum(1 for p in classified if p["is_strike"])
        balls = len(classified) - strikes
        percentage = strikes / len(classified)

        return (strikes, balls, percentage)

    def get_unclassified_count(self) -> int:
        """Return pitches retained as evidence but excluded from claims."""

        return sum(1 for pitch in self._pitches if not pitch["usable"])

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
