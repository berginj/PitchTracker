"""Tracking interfaces and track state containers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

from contracts import StereoObservation, TrackSample


@dataclass(frozen=True)
class TrackState:
    track_id: str
    samples: List[TrackSample]
    last_update_ns: int
    quality_flags: int


class Tracker(ABC):
    @abstractmethod
    def update(
        self, observation: Optional[StereoObservation]
    ) -> TrackState:
        """Update tracker with a new observation (or None if missing)."""
