"""Detection interfaces and results."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List

from contracts import Detection, Frame


@dataclass(frozen=True)
class DetectorHealth:
    false_positive_rate_hz: float
    last_detection_ns: int


class Detector(ABC):
    @abstractmethod
    def detect(self, frame: Frame) -> List[Detection]:
        """Return detections for a single frame."""

    @abstractmethod
    def health(self) -> DetectorHealth:
        """Return rolling detector health stats."""
