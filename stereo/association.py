"""Stereo association and triangulation interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple

from contracts import Detection, StereoObservation


@dataclass(frozen=True)
class StereoMatch:
    left: Detection
    right: Detection
    epipolar_error_px: float
    score: float


class StereoMatcher(ABC):
    @abstractmethod
    def match(
        self, left: Detection, right: Detection
    ) -> Optional[StereoMatch]:
        """Return a match if detections satisfy epipolar and quality constraints."""

    @abstractmethod
    def triangulate(self, match: StereoMatch) -> StereoObservation:
        """Triangulate a 3D observation from a matched pair."""

    @abstractmethod
    def pair_timestamp(
        self, left_ns: int, right_ns: int
    ) -> Tuple[int, bool]:
        """Return paired timestamp and whether within tolerance."""
