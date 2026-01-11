"""Lane gating for stereo matches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from detect.lane import LaneGate
from stereo.association import StereoMatch


@dataclass(frozen=True)
class StereoLaneGate:
    lane_gate: LaneGate

    def filter_matches(self, matches: Iterable[StereoMatch]) -> List[StereoMatch]:
        allowed: List[StereoMatch] = []
        for match in matches:
            detections = [match.left, match.right]
            if len(self.lane_gate.filter_detections(detections)) == 2:
                allowed.append(match)
        return allowed
