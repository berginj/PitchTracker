"""Stereo association and triangulation interfaces."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple

from contracts import Detection, StereoObservation


@dataclass(frozen=True)
class PairTiming:
    """Raw and corrected timestamps for one stereo frame pair.

    ``right_offset_ns`` is added to the raw right-camera timestamp. Raw
    capture timestamps remain unchanged so diagnostics can distinguish clock
    bias from the residual skew after correction.
    """

    raw_left_ns: int
    raw_right_ns: int
    adjusted_left_ns: int
    adjusted_right_ns: int
    right_offset_ns: int

    @property
    def timestamp_ns(self) -> int:
        return (self.adjusted_left_ns + self.adjusted_right_ns) // 2

    @property
    def raw_skew_ns(self) -> int:
        return abs(self.raw_left_ns - self.raw_right_ns)

    @property
    def adjusted_skew_ns(self) -> int:
        return abs(self.adjusted_left_ns - self.adjusted_right_ns)

    @property
    def offset_applied(self) -> bool:
        return self.right_offset_ns != 0


def pair_timing(left_ns: int, right_ns: int, right_offset_ns: int = 0) -> PairTiming:
    """Apply the configured right-camera offset without mutating raw times."""
    left = int(left_ns)
    right = int(right_ns)
    offset = int(right_offset_ns)
    return PairTiming(
        raw_left_ns=left,
        raw_right_ns=right,
        adjusted_left_ns=left,
        adjusted_right_ns=right + offset,
        right_offset_ns=offset,
    )


@dataclass(frozen=True)
class StereoMatch:
    left: Detection
    right: Detection
    epipolar_error_px: float
    score: float


class StereoMatcher(ABC):
    @abstractmethod
    def match(self, left: Detection, right: Detection) -> Optional[StereoMatch]:
        """Return a match if detections satisfy epipolar and quality constraints."""

    @abstractmethod
    def triangulate(self, match: StereoMatch) -> StereoObservation:
        """Triangulate a 3D observation from a matched pair."""

    @abstractmethod
    def pair_timestamp(self, left_ns: int, right_ns: int) -> Tuple[int, bool]:
        """Return paired timestamp and whether within tolerance."""
