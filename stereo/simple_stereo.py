"""Simple rectified stereo matcher and triangulation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from contracts import StereoObservation
from stereo.association import StereoMatch, StereoMatcher


@dataclass(frozen=True)
class StereoGeometry:
    baseline_ft: float
    focal_length_px: float
    cx: float
    cy: float
    epipolar_epsilon_px: float
    z_min_ft: float = 3.0
    z_max_ft: float = 80.0
    time_sync_offset_ns: int = 0


class SimpleStereoMatcher(StereoMatcher):
    def __init__(self, geometry: StereoGeometry) -> None:
        self._geometry = geometry
        self._time_sync_offset_ns = int(getattr(geometry, "time_sync_offset_ns", 0))

    def match(self, left, right) -> Optional[StereoMatch]:
        if abs(left.v - right.v) > self._geometry.epipolar_epsilon_px:
            return None
        return StereoMatch(
            left=left,
            right=right,
            epipolar_error_px=abs(left.v - right.v),
            score=min(left.confidence, right.confidence),
        )

    def triangulate(self, match: StereoMatch) -> StereoObservation:
        disparity = match.left.u - match.right.u
        if abs(disparity) < 0.5:
            disparity = 0.5 if disparity >= 0 else -0.5
        z_ft = (self._geometry.focal_length_px * self._geometry.baseline_ft) / disparity
        x_ft = (match.left.u - self._geometry.cx) * z_ft / self._geometry.focal_length_px
        y_ft = (match.left.v - self._geometry.cy) * z_ft / self._geometry.focal_length_px
        in_range = self._geometry.z_min_ft <= z_ft <= self._geometry.z_max_ft
        quality = 1.0 if in_range else 0.0
        timestamp_ns, _ = self.pair_timestamp(match.left.t_capture_monotonic_ns, match.right.t_capture_monotonic_ns)
        return StereoObservation(
            t_ns=timestamp_ns,
            left=(match.left.u, match.left.v),
            right=(match.right.u, match.right.v),
            X=float(x_ft),
            Y=float(y_ft),
            Z=float(z_ft),
            quality=quality,
            confidence=match.score if in_range else 0.0,
        )

    def pair_timestamp(self, left_ns: int, right_ns: int) -> Tuple[int, bool]:
        if self._time_sync_offset_ns != 0:
            right_ns_adj = int(right_ns + self._time_sync_offset_ns)
            return (left_ns + right_ns_adj) // 2, True
        mid = (left_ns + right_ns) // 2
        return mid, False
