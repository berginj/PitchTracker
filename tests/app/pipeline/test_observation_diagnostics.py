"""Tests for pitch observation diagnostics."""

from __future__ import annotations

from app.pipeline.analysis.observation_diagnostics import summarize_observations
from contracts import StereoObservation


def _obs(t_ns: int, z: float, confidence: float = 1.0) -> StereoObservation:
    return StereoObservation(
        t_ns=t_ns,
        left=(0.0, 0.0),
        right=(0.0, 0.0),
        X=0.0,
        Y=0.0,
        Z=z,
        quality=1.0,
        confidence=confidence,
    )


def test_summarize_observations_reports_timing_and_coverage() -> None:
    stats = summarize_observations(
        [
            _obs(20_000_000, 48.0, 0.8),
            _obs(0, 50.0, 1.0),
            _obs(10_000_000, 49.0, 0.6),
        ]
    )

    assert stats["observation_count"] == 3
    assert stats["observation_duration_ms"] == 20.0
    assert stats["observation_rate_hz"] == 150.0
    assert stats["observation_max_gap_ms"] == 10.0
    assert stats["observation_z_span_ft"] == 2.0
    assert abs(stats["observation_mean_confidence"] - 0.8) < 0.001


def test_summarize_observations_handles_empty_input() -> None:
    stats = summarize_observations([])

    assert stats["observation_count"] == 0
    assert stats["observation_duration_ms"] == 0.0
    assert stats["observation_rate_hz"] == 0.0
