"""Tests for timestamped trajectory tracker."""

from __future__ import annotations

from contracts import StereoObservation
from track.trajectory_tracker import TimestampedTrajectoryTracker


def _obs(t_ns: int, z: float) -> StereoObservation:
    return StereoObservation(
        t_ns=t_ns,
        left=(0.0, 0.0),
        right=(0.0, 0.0),
        X=0.0,
        Y=0.0,
        Z=z,
        quality=1.0,
        confidence=1.0,
    )


def test_timestamped_trajectory_tracker_fits_velocity_from_window() -> None:
    tracker = TimestampedTrajectoryTracker()
    for i in range(5):
        # 60 mph is 88 ft/s, moving toward smaller Z.
        state = tracker.update(_obs(i * 10_000_000, 50.0 - 88.0 * i * 0.01))

    sample = state.samples[-1]
    assert abs(sample.Vz + 88.0) < 0.5
    assert sample.Az is not None
