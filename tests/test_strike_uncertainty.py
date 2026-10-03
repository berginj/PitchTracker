"""Boundary sensitivity uses declared evidence without creating physical claims."""

from dataclasses import replace

import numpy as np
import pytest

from contracts import StereoObservation
from contracts.timing import TimestampEvidence
from metrics.strike_zone import build_strike_zone, is_strike


ZONE = build_strike_zone(0.0, 17.0, 17.0, 66.0, 0.5, 0.27)
TIMING = TimestampEvidence("verified_timing_model", "host_monotonic", "exposure_midpoint", 0, "synthetic-test")


def track(x=0.0, sigma=0.001):
    covariance = tuple(tuple(float(value) for value in row) for row in np.eye(3) * sigma**2)
    return [StereoObservation(i * 20_000_000, (0.0, 0.0), (0.0, 0.0), x, 2.5, z, 1.0, covariance)
            for i, z in enumerate((0.4, -0.7, -1.8))]


def test_declared_large_covariance_makes_a_boundary_strike_unavailable():
    near_edge = 17 / 24 + 1.45 / 12 * 0.8
    precise = is_strike(track(near_edge), ZONE, 1.45, timing_evidence=TIMING)
    uncertain = is_strike(track(near_edge, 0.1), ZONE, 1.45, timing_evidence=TIMING)
    assert precise.available and precise.is_strike
    assert not uncertain.available
    assert uncertain.reason == "STRIKE_BOUNDARY_UNCERTAIN"


def test_known_uncertainty_preserves_clear_inside_and_far_outside_geometry():
    strike = is_strike(track(sigma=0.02), ZONE, 1.45, timing_evidence=TIMING)
    ball = is_strike(track(x=2.0, sigma=0.02), ZONE, 1.45, timing_evidence=TIMING)
    assert strike.available and strike.is_strike
    assert ball.available and not ball.is_strike
    assert "conditional" in strike.basis


def test_declared_acquisition_uncertainty_contributes_motion_sensitivity():
    boundary = 17 / 24 + 1.45 / 12 * 0.8
    delayed = replace(TIMING, acquisition_uncertainty_ns=2_000_000)
    result = is_strike(track(boundary), ZONE, 1.45, timing_evidence=delayed)
    assert not result.available
    assert result.reason == "STRIKE_BOUNDARY_UNCERTAIN"


def test_legacy_unknown_evidence_retains_explicitly_estimated_geometry():
    result = is_strike([replace(obs, covariance=None) for obs in track()], ZONE, 1.45)
    assert result.available and result.is_strike
    assert result.reason == "COVARIANCE_UNKNOWN+ACQUISITION_TIMING_UNKNOWN"
    assert "conditional" in result.basis


def test_declared_timing_uncertainty_needs_a_motion_estimate():
    result = is_strike([track()[0]], ZONE, 1.45, timing_evidence=replace(TIMING, acquisition_uncertainty_ns=1_000_000))
    assert not result.available and result.reason == "TIMING_SENSITIVITY_UNAVAILABLE"


def test_relative_timestamp_epoch_can_be_negative():
    observations = [replace(obs, t_ns=obs.t_ns - 100_000_000) for obs in track()]
    result = is_strike(observations, ZONE, 1.45)
    assert result.available and result.is_strike


@pytest.mark.parametrize("covariance", [
    ((1.0, 0.0), (0.0, 1.0)), ((-1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    ((1.0, 1.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    ((float("nan"), 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
])
def test_invalid_covariance_cannot_become_a_positive_call(covariance):
    result = is_strike([replace(track()[0], covariance=covariance)], ZONE, 1.45)
    assert not result.available and result.reason == "INVALID_COVARIANCE"


@pytest.mark.parametrize("timestamps", [(0, 0, 1), (2, 1, 3), (None, 1, 2), (False, 1, 2), (0.5, 1, 2)])
def test_invalid_timestamps_cannot_become_a_positive_call(timestamps):
    result = is_strike([replace(obs, t_ns=t) for obs, t in zip(track(), timestamps)], ZONE, 1.45)
    assert not result.available and result.reason == "INVALID_TIMESTAMPS"
