"""Simple tracker using last two observations for velocity."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from contracts import StereoObservation, TrackSample
from track.tracker import TrackState, Tracker


@dataclass
class _TrackMemory:
    last_observation: Optional[StereoObservation] = None
    last_sample: Optional[TrackSample] = None
    track_id: str = "track-1"
    quality_flags: int = 0


class SimpleTracker(Tracker):
    def __init__(self) -> None:
        self._memory = _TrackMemory()

    def update(self, observation: Optional[StereoObservation]) -> TrackState:
        if observation is None:
            return TrackState(
                track_id=self._memory.track_id,
                samples=[],
                last_update_ns=0,
                quality_flags=self._memory.quality_flags,
            )
        last_obs = self._memory.last_observation
        if last_obs is None:
            sample = TrackSample(
                t_ns=observation.t_ns,
                X=observation.X,
                Y=observation.Y,
                Z=observation.Z,
                Vx=0.0,
                Vy=0.0,
                Vz=0.0,
            )
        else:
            dt = (observation.t_ns - last_obs.t_ns) / 1e9
            if dt <= 0:
                dt = 1e-6
            sample = TrackSample(
                t_ns=observation.t_ns,
                X=observation.X,
                Y=observation.Y,
                Z=observation.Z,
                Vx=(observation.X - last_obs.X) / dt,
                Vy=(observation.Y - last_obs.Y) / dt,
                Vz=(observation.Z - last_obs.Z) / dt,
            )
        self._memory.last_observation = observation
        self._memory.last_sample = sample
        return TrackState(
            track_id=self._memory.track_id,
            samples=[sample],
            last_update_ns=observation.t_ns,
            quality_flags=self._memory.quality_flags,
        )
