"""Independent truth, not the fitter's own propagator, defines correctness."""

from dataclasses import replace

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from contracts import StereoObservation
from trajectory.contracts import FailureCode, TrajectoryFitRequest
from trajectory.physics import PhysicsDragFitter
from trajectory.confidence import ConfidenceScorer


def independent_track(mph=60.0, duration=0.1, drag=0.0015, lift=0.0, sigma=None):
    def dynamics(t, state):
        velocity = state[3:]
        return np.r_[velocity, -drag * np.linalg.norm(velocity) * velocity + np.array([lift, -32.174, 0.0])]

    times = np.linspace(0.0, duration, max(7, round(duration * 60) + 1))
    speed = mph * 22 / 15
    truth = solve_ivp(
        dynamics,
        (0.0, duration),
        [0.0, 3.0, speed * duration * 0.9, 0.0, 0.0, -speed],
        t_eval=times,
        rtol=1e-11,
        atol=1e-12,
    )
    covariance = tuple(tuple(float(x) for x in row) for row in np.eye(3) * sigma**2) if sigma else None
    return [
        StereoObservation(
            round(float(t) * 1e9),
            (0.0, 0.0),
            (0.0, 0.0),
            *map(float, point),
            quality=1.0,
            confidence=1.0,
            covariance=covariance,
        )
        for t, point in zip(times, truth.y[:3].T)
    ]


@pytest.mark.parametrize("mph", [30.0, 60.0, 90.0])
@pytest.mark.parametrize("duration", [0.1, 0.3])
@pytest.mark.parametrize("seed", [0.002, 0.02])
def test_speed_is_recovered_without_prior_bias(mph, duration, seed):
    request = TrajectoryFitRequest(independent_track(mph, duration), 0.0, drag_k0=seed, max_iter=100)
    result = PhysicsDragFitter().fit_trajectory(request)
    assert not result.diagnostics.failure_codes
    speed = np.linalg.norm([result.samples[0].Vx, result.samples[0].Vy, result.samples[0].Vz]) * 15 / 22
    assert speed == pytest.approx(mph, abs=0.01)
    assert result.expected_plate_error_ft is None
    assert result.diagnostics.observation_noise_basis == "assumed_or_partial"


def test_equal_position_residual_does_not_imply_equal_velocity_identifiability():
    fitter = PhysicsDragFitter()
    precise = fitter.fit_trajectory(TrajectoryFitRequest(independent_track(sigma=0.001), 0.0))
    uncertain = fitter.fit_trajectory(TrajectoryFitRequest(independent_track(sigma=1.0), 0.0))
    assert not precise.diagnostics.failure_codes
    assert FailureCode.SPEED_UNIDENTIFIABLE in uncertain.diagnostics.failure_codes
    assert uncertain.confidence == 0.0
    assert precise.expected_plate_error_ft is uncertain.expected_plate_error_ft is None


def test_unmodeled_transverse_acceleration_is_a_model_limit():
    observations = independent_track(duration=0.3, lift=30.0, sigma=0.001)
    result = PhysicsDragFitter().fit_trajectory(TrajectoryFitRequest(observations, 0.0, max_iter=100))
    assert FailureCode.MODEL_MISMATCH in result.diagnostics.failure_codes
    assert result.confidence == 0.0


def test_nonconverged_and_invalid_tracks_are_not_confident():
    request = TrajectoryFitRequest(independent_track(), 0.0, max_iter=1)
    result = PhysicsDragFitter().fit_trajectory(request)
    assert FailureCode.OPT_DID_NOT_CONVERGE in result.diagnostics.failure_codes
    assert result.confidence == 0.0
    repeated = [replace(obs, t_ns=0) for obs in request.observations]
    result = PhysicsDragFitter().fit_trajectory(replace(request, observations=repeated))
    assert FailureCode.INVALID_INPUT in result.diagnostics.failure_codes


def test_residuals_do_not_manufacture_physical_uncertainty():
    scorer = ConfidenceScorer()
    for residual in [0.001, 0.2, 1.0]:
        assert scorer.expected_plate_error_ft(residual, ((0.0, 2.5, 0.0), 1)) is None
