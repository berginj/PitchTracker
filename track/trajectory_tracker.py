"""Timestamped trajectory tracker for live stereo observations."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from contracts import StereoObservation, TrackSample
from track.tracker import TrackState, Tracker


@dataclass
class _TrajectoryMemory:
    observations: deque[StereoObservation] = field(default_factory=lambda: deque(maxlen=24))
    track_id: str = "track-1"
    quality_flags: int = 0


class TimestampedTrajectoryTracker(Tracker):
    """Fit a short timestamped trajectory window instead of differencing two points."""

    def __init__(self, max_observations: int = 24) -> None:
        self._memory = _TrajectoryMemory(observations=deque(maxlen=max_observations))

    def update(self, observation: Optional[StereoObservation]) -> TrackState:
        if observation is None:
            return TrackState(
                track_id=self._memory.track_id,
                samples=[],
                last_update_ns=0,
                quality_flags=self._memory.quality_flags,
            )

        self._memory.observations.append(observation)
        sample = self._fit_latest_sample()
        return TrackState(
            track_id=self._memory.track_id,
            samples=[sample],
            last_update_ns=observation.t_ns,
            quality_flags=self._memory.quality_flags,
        )

    def _fit_latest_sample(self) -> TrackSample:
        observations = sorted(self._memory.observations, key=lambda obs: obs.t_ns)
        latest = observations[-1]
        if len(observations) < 3:
            return _last_two_sample(observations)

        t0 = observations[0].t_ns
        times = np.array([(obs.t_ns - t0) / 1e9 for obs in observations], dtype=float)
        if np.any(np.diff(times) <= 0):
            return _last_two_sample(observations)

        latest_t = times[-1]
        positions = {
            "X": np.array([obs.X for obs in observations], dtype=float),
            "Y": np.array([obs.Y for obs in observations], dtype=float),
            "Z": np.array([obs.Z for obs in observations], dtype=float),
        }
        values: dict[str, tuple[float, float, float]] = {}
        degree = 2 if len(observations) >= 4 else 1
        for axis, samples in positions.items():
            coeffs = np.polyfit(times, samples, degree)
            if degree == 2:
                a, b, c = coeffs
                pos = a * latest_t * latest_t + b * latest_t + c
                vel = 2.0 * a * latest_t + b
                acc = 2.0 * a
            else:
                b, c = coeffs
                pos = b * latest_t + c
                vel = b
                acc = 0.0
            values[axis] = (float(pos), float(vel), float(acc))

        return TrackSample(
            t_ns=latest.t_ns,
            X=values["X"][0],
            Y=values["Y"][0],
            Z=values["Z"][0],
            Vx=values["X"][1],
            Vy=values["Y"][1],
            Vz=values["Z"][1],
            Ax=values["X"][2],
            Ay=values["Y"][2],
            Az=values["Z"][2],
        )


def _last_two_sample(observations: list[StereoObservation]) -> TrackSample:
    latest = observations[-1]
    if len(observations) == 1:
        return TrackSample(latest.t_ns, latest.X, latest.Y, latest.Z, 0.0, 0.0, 0.0)
    previous = observations[-2]
    dt = max((latest.t_ns - previous.t_ns) / 1e9, 1e-6)
    return TrackSample(
        t_ns=latest.t_ns,
        X=latest.X,
        Y=latest.Y,
        Z=latest.Z,
        Vx=(latest.X - previous.X) / dt,
        Vy=(latest.Y - previous.Y) / dt,
        Vz=(latest.Z - previous.Z) / dt,
    )
