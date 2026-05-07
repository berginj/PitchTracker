"""Tests for track/simple_tracker.py and track/tracker.py."""

from __future__ import annotations

import pytest
from contracts import StereoObservation, TrackSample
from track.simple_tracker import SimpleTracker
from track.tracker import TrackState


@pytest.fixture
def tracker():
    return SimpleTracker()


def _obs(t_ns: int, x: float, y: float, z: float) -> StereoObservation:
    """Helper to build a StereoObservation with minimal required fields."""
    return StereoObservation(
        t_ns=t_ns,
        left=(0.0, 0.0),
        right=(0.0, 0.0),
        X=x, Y=y, Z=z,
        quality=1.0,
    )


class TestSimpleTracker:
    def test_first_observation_zero_velocity(self, tracker):
        state = tracker.update(_obs(1_000_000_000, 1.0, 2.0, 3.0))
        assert isinstance(state, TrackState)
        assert len(state.samples) == 1
        sample = state.samples[0]
        assert sample.Vx == 0.0
        assert sample.Vy == 0.0
        assert sample.Vz == 0.0
        assert sample.X == 1.0
        assert sample.Y == 2.0
        assert sample.Z == 3.0

    def test_two_observations_computes_velocity(self, tracker):
        tracker.update(_obs(1_000_000_000, 0.0, 0.0, 0.0))
        state = tracker.update(_obs(2_000_000_000, 10.0, 0.0, 0.0))
        sample = state.samples[0]
        assert sample.Vx == pytest.approx(10.0, abs=0.01)
        assert sample.Vy == pytest.approx(0.0, abs=0.01)
        assert sample.Vz == pytest.approx(0.0, abs=0.01)

    def test_none_observation_returns_empty_samples(self, tracker):
        state = tracker.update(None)
        assert isinstance(state, TrackState)
        assert len(state.samples) == 0

    def test_none_after_observation_returns_empty(self, tracker):
        tracker.update(_obs(1_000_000_000, 1.0, 2.0, 3.0))
        state = tracker.update(None)
        assert len(state.samples) == 0

    def test_zero_dt_does_not_crash(self, tracker):
        tracker.update(_obs(1_000_000_000, 0.0, 0.0, 0.0))
        state = tracker.update(_obs(1_000_000_000, 5.0, 0.0, 0.0))
        assert len(state.samples) == 1
        # dt clamped to 1e-6, so velocity is large but finite
        assert state.samples[0].Vx != float('inf')

    def test_negative_dt_does_not_crash(self, tracker):
        tracker.update(_obs(2_000_000_000, 0.0, 0.0, 0.0))
        state = tracker.update(_obs(1_000_000_000, 5.0, 0.0, 0.0))
        assert len(state.samples) == 1

    def test_multiple_sequential_observations(self, tracker):
        for i in range(5):
            state = tracker.update(_obs((i + 1) * 1_000_000_000, float(i), 0.0, 0.0))
        assert len(state.samples) == 1
        assert state.last_update_ns == 5_000_000_000

    def test_track_state_fields(self, tracker):
        state = tracker.update(_obs(1_000_000_000, 1.0, 2.0, 3.0))
        assert state.track_id == "track-1"
        assert state.last_update_ns == 1_000_000_000
        assert state.quality_flags == 0

    def test_velocity_direction(self, tracker):
        tracker.update(_obs(0, 0.0, 0.0, 50.0))
        state = tracker.update(_obs(1_000_000_000, 0.0, 0.0, 0.0))
        sample = state.samples[0]
        assert sample.Vz == pytest.approx(-50.0, abs=0.01)

    def test_samples_are_track_sample_type(self, tracker):
        state = tracker.update(_obs(1_000_000_000, 1.0, 2.0, 3.0))
        for sample in state.samples:
            assert isinstance(sample, TrackSample)
