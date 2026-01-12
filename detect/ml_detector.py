"""Stub ML detector for future model integration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from contracts import Detection, Frame
from detect.detector import Detector, DetectorHealth


@dataclass(frozen=True)
class MlDetector(Detector):
    model_path: Optional[str] = None

    def detect(self, frame: Frame) -> List[Detection]:
        return []

    def health(self) -> DetectorHealth:
        return DetectorHealth(false_positive_rate_hz=0.0, last_detection_ns=0)
