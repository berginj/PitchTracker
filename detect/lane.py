"""Lane region-of-interest gating."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

from contracts import Detection

Point = Tuple[float, float]


@dataclass(frozen=True)
class LaneRoi:
    polygon: Sequence[Point]

    def contains(self, point: Point) -> bool:
        if len(self.polygon) < 3:
            return False
        x, y = point
        inside = False
        j = len(self.polygon) - 1
        for i in range(len(self.polygon)):
            xi, yi = self.polygon[i]
            xj, yj = self.polygon[j]
            intersects = (yi > y) != (yj > y) and (
                x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi
            )
            if intersects:
                inside = not inside
            j = i
        return inside


@dataclass(frozen=True)
class LaneGate:
    roi_by_camera: dict[str, LaneRoi]

    def filter_detections(self, detections: Iterable[Detection]) -> List[Detection]:
        allowed: List[Detection] = []
        for detection in detections:
            roi = self.roi_by_camera.get(detection.camera_id)
            if roi is None:
                continue
            if roi.contains((detection.u, detection.v)):
                allowed.append(detection)
        return allowed
