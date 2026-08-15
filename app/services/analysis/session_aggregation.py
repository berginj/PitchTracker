"""Session-level pitch aggregation and heatmap maintenance.

Thread-safety: All methods assume the caller holds the service lock.
"""

from __future__ import annotations

from collections import deque
from typing import List, Optional

from app.contracts import PitchSummary, SessionSummary, measurement_is_usable
from contracts import StereoObservation
from log_config.logger import get_logger

logger = get_logger(__name__)


class SessionAggregator:
    """Maintains running session summary, heatmap, and recent pitch paths."""

    def __init__(self, max_recent: int = 10) -> None:
        self._session_summary: Optional[SessionSummary] = None
        self._pitch_summaries: List[PitchSummary] = []
        self._recent_pitch_paths: deque[List[StereoObservation]] = deque(maxlen=max_recent)
        self._terminal_pitch_ids: set[str] = set()

    def reset(self, session_id: str) -> None:
        """Reset aggregation state for a new session."""
        self._session_summary = SessionSummary(
            session_id=session_id,
            pitch_count=0,
            strikes=0,
            balls=0,
            heatmap=[[0] * 3 for _ in range(3)],
            pitches=[],
        )
        self._pitch_summaries = []
        self._recent_pitch_paths.clear()
        self._terminal_pitch_ids.clear()

    def is_duplicate(self, pitch_id: str) -> bool:
        """Return True if pitch_id already has a terminal result."""
        return pitch_id in self._terminal_pitch_ids

    def aggregate(
        self,
        pitch_id: str,
        summary: PitchSummary,
        observations: List[StereoObservation],
    ) -> SessionSummary:
        """Add a terminal pitch summary to the running session aggregation.

        Returns the updated SessionSummary. Caller must verify duplicate check
        before calling.
        """
        measurement_usable = measurement_is_usable(summary)
        current = self._session_summary or SessionSummary(
            session_id="current",
            pitch_count=0,
            strikes=0,
            balls=0,
            heatmap=[[0] * 3 for _ in range(3)],
            pitches=[],
        )
        new_heatmap = [row[:] for row in current.heatmap]
        if (
            measurement_usable
            and summary.zone_row is not None
            and summary.zone_col is not None
            and 0 <= summary.zone_row < len(new_heatmap)
            and 0 <= summary.zone_col < len(new_heatmap[summary.zone_row])
        ):
            new_heatmap[summary.zone_row][summary.zone_col] += 1

        self._pitch_summaries.append(summary)
        self._recent_pitch_paths.append(list(observations))
        self._session_summary = SessionSummary(
            session_id=current.session_id,
            pitch_count=current.pitch_count + 1,
            strikes=current.strikes + (1 if measurement_usable and summary.is_strike else 0),
            balls=current.balls + (1 if measurement_usable and not summary.is_strike else 0),
            heatmap=new_heatmap,
            pitches=[*current.pitches, summary],
        )
        self._terminal_pitch_ids.add(pitch_id)
        return self._session_summary

    @property
    def session_summary(self) -> SessionSummary:
        if self._session_summary is None:
            return SessionSummary(
                session_id="none",
                pitch_count=0,
                strikes=0,
                balls=0,
                heatmap=[[0] * 3 for _ in range(3)],
                pitches=[],
            )
        return self._session_summary

    @property
    def recent_pitch_paths(self) -> List[List[StereoObservation]]:
        return list(self._recent_pitch_paths)
