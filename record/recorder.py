"""Recording interfaces for pitch capture and replay."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterable

from contracts import Detection, Frame, PitchMetrics, TrackSample


@dataclass(frozen=True)
class RecordingBundle:
    pitch_id: str
    frames: Iterable[Frame]
    detections: Iterable[Detection]
    track: Iterable[TrackSample]
    metrics: PitchMetrics


class Recorder(ABC):
    @abstractmethod
    def start(self) -> None:
        """Start recording."""

    @abstractmethod
    def stop(self) -> None:
        """Stop recording."""

    @abstractmethod
    def save(self, bundle: RecordingBundle) -> None:
        """Persist a recording bundle."""
