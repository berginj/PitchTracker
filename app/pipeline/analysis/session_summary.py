"""Session summary management and aggregation."""

from __future__ import annotations

import logging
from collections import deque
from typing import List

from contracts import StereoObservation

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session state and aggregates pitch summaries.

    Tracks pitches within a session and maintains recent pitch paths
    for visualization and analysis.
    """

    def __init__(self, session_name: str):
        """Initialize session manager.

        Args:
            session_name: Name of the session
        """
        self._session_name = session_name
        self._pitches = []
        self._recent_paths = deque(maxlen=12)

    def add_pitch(self, summary, observations: List[StereoObservation]) -> None:
        """Add pitch to session.

        Args:
            summary: PitchSummary object
            observations: List of stereo observations for the pitch
        """
        self._pitches.append(summary)
        if observations:
            self._recent_paths.append(list(observations))

    def get_summary(self):
        """Get session summary.

        Returns:
            SessionSummary object
        """
        # Import here to avoid circular dependency
        from app.pipeline.utils import build_session_summary

        return build_session_summary(self._session_name, self._pitches)

    def get_pitches(self):
        """Get all pitches in session.

        Returns:
            List of PitchSummary objects
        """
        return list(self._pitches)

    def get_recent_paths(self):
        """Get recent pitch paths.

        Returns:
            Deque of observation lists
        """
        return self._recent_paths

    def reset(self) -> None:
        """Reset session state."""
        self._pitches = []
        self._recent_paths.clear()
