"""Pitch metrics computation interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from contracts import PitchMetrics, TrackSample


class MetricsComputer(ABC):
    @abstractmethod
    def compute(self, samples: Iterable[TrackSample]) -> PitchMetrics:
        """Compute pitch metrics from a track sample sequence."""
