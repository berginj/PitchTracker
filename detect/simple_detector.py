"""Simple detector implementation for simulated pipeline runs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from contracts import Detection, Frame

from .detector import Detector, DetectorHealth


@dataclass(frozen=True)
class CenterDetector(Detector):
    radius_px: float = 6.0
    confidence: float = 0.8

    def detect(self, frame: Frame) -> List[Detection]:
        return [
            Detection(
                camera_id=frame.camera_id,
                frame_index=frame.frame_index,
                t_capture_monotonic_ns=frame.t_capture_monotonic_ns,
                u=frame.width / 2.0,
                v=frame.height / 2.0,
                radius_px=self.radius_px,
                confidence=self.confidence,
            )
        ]

    def health(self) -> DetectorHealth:
        return DetectorHealth(false_positive_rate_hz=0.0, last_detection_ns=0)
