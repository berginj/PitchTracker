"""Tests for pitch observation diagnostics."""

from __future__ import annotations

from typing import Optional

import pytest

from app.pipeline.analysis.observation_diagnostics import summarize_observations
from contracts import StereoObservation


def _obs(t_ns: int, z: float, confidence: float = 1.0, depth_sigma_ft: Optional[float] = None) -> StereoObservation:
    covariance = None
    if depth_sigma_ft is not None:
        covariance = ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, depth_sigma_ft**2))
    return StereoObservation(
        t_ns=t_ns,
        left=(0.0, 0.0),
        right=(0.0, 0.0),
        X=0.0,
        Y=0.0,
        Z=z,
        quality=1.0,
        covariance=covariance,
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
    assert stats["observation_mean_depth_sigma_ft"] is None
    assert stats["observation_max_depth_sigma_ft"] is None
    assert stats["observation_quality_status"] == "REJECT"
    assert stats["observation_rejection_reasons"] == ["INSUFFICIENT_OBSERVATIONS"]
    assert stats["observation_warning_reasons"] == []


def test_summarize_observations_reports_depth_uncertainty_from_covariance() -> None:
    stats = summarize_observations(
        [
            _obs(0, 50.0, 1.0, depth_sigma_ft=1.0),
            _obs(10_000_000, 49.0, 0.8, depth_sigma_ft=2.0),
            _obs(20_000_000, 48.0, 0.7),
        ]
    )

    assert stats["observation_mean_depth_sigma_ft"] == pytest.approx(1.5)
    assert stats["observation_max_depth_sigma_ft"] == pytest.approx(2.0)
    assert stats["observation_quality_status"] == "REJECT"
    assert stats["observation_rejection_reasons"] == ["INSUFFICIENT_OBSERVATIONS"]


def test_summarize_observations_passes_healthy_observation_set() -> None:
    stats = summarize_observations(
        [
            _obs(0, 50.0, 1.0, depth_sigma_ft=1.0),
            _obs(10_000_000, 47.0, 0.9, depth_sigma_ft=1.2),
            _obs(20_000_000, 44.0, 0.8, depth_sigma_ft=1.1),
            _obs(30_000_000, 41.0, 0.9, depth_sigma_ft=1.0),
        ]
    )

    assert stats["observation_quality_status"] == "PASS"
    assert stats["observation_rejection_reasons"] == []
    assert stats["observation_warning_reasons"] == []


def test_summarize_observations_warns_on_marginal_depth_uncertainty_and_gap() -> None:
    stats = summarize_observations(
        [
            _obs(0, 50.0, 0.8, depth_sigma_ft=1.0),
            _obs(10_000_000, 47.0, 0.8, depth_sigma_ft=2.0),
            _obs(20_000_000, 44.0, 0.8, depth_sigma_ft=4.5),
            _obs(90_000_000, 41.0, 0.8, depth_sigma_ft=2.0),
        ]
    )

    assert stats["observation_quality_status"] == "WARN"
    assert stats["observation_rejection_reasons"] == []
    assert stats["observation_warning_reasons"] == ["HIGH_DEPTH_UNCERTAINTY", "LARGE_OBSERVATION_GAP"]


def test_summarize_observations_rejects_low_confidence_and_high_depth_uncertainty() -> None:
    stats = summarize_observations(
        [
            _obs(0, 50.0, 0.2, depth_sigma_ft=1.0),
            _obs(10_000_000, 47.0, 0.3, depth_sigma_ft=9.0),
            _obs(20_000_000, 44.0, 0.2, depth_sigma_ft=2.0),
            _obs(30_000_000, 41.0, 0.3, depth_sigma_ft=1.0),
        ]
    )

    assert stats["observation_quality_status"] == "REJECT"
    assert stats["observation_rejection_reasons"] == ["LOW_OBSERVATION_CONFIDENCE", "HIGH_DEPTH_UNCERTAINTY"]


def test_summarize_observations_handles_empty_input() -> None:
    stats = summarize_observations([])

    assert stats["observation_count"] == 0
    assert stats["observation_duration_ms"] == 0.0
    assert stats["observation_rate_hz"] == 0.0
    assert stats["observation_mean_depth_sigma_ft"] is None
    assert stats["observation_max_depth_sigma_ft"] is None
    assert stats["observation_quality_status"] == "REJECT"
    assert stats["observation_rejection_reasons"] == ["NO_OBSERVATIONS"]
