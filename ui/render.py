"""UI renderer interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from contracts import Detection, Frame, StereoObservation, TrackSample


class Renderer(ABC):
    @abstractmethod
    def render_frames(self, frames: Iterable[Frame]) -> None:
        """Render rectified frames."""

    @abstractmethod
    def render_detections(self, detections: Iterable[Detection]) -> None:
        """Overlay detections on the UI."""

    @abstractmethod
    def render_tracks(self, track: Iterable[TrackSample]) -> None:
        """Render 3D trajectory visualization."""

    @abstractmethod
    def render_matches(self, observations: Iterable[StereoObservation]) -> None:
        """Render matched stereo observations."""
