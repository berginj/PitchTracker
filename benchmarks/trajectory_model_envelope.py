"""Bounded independent model-limit sweep; never a physical accuracy report.

Run: python -m benchmarks.trajectory_model_envelope
Ground truth uses solve_ivp, not the fitter's RK4 model. Synthetic ball labels
and covariance geometries describe assumptions, not qualified hardware/balls.
"""

from dataclasses import asdict, dataclass, replace
from itertools import product
import json
from time import perf_counter

import numpy as np
from scipy.integrate import solve_ivp

from contracts import StereoObservation
from trajectory.contracts import TrajectoryFitRequest
from trajectory.physics import PhysicsDragFitter


@dataclass(frozen=True)
class EnvelopeScenario:
    name: str = "control"
    truth_drag_ft_inverse: float = 0.0015
    ball_model: str = "synthetic_drag_control"
    noise_sigma_ft: float = 0.005
    noise_seed: int = 7
    covariance_axis_scales: tuple[float, float, float] = (1.0, 1.0, 1.0)
    timing_jitter_s: float = 0.0
    fps: int = 60
    visibility_start_s: float = 0.0
    initial_x_ft: float = 0.0
    initial_y_ft: float = 3.0
    optimizer_drag_seed_ft_inverse: float = 0.002
    drag_prior_enabled: bool = False
    drag_prior_sigma_ft_inverse: float = 0.002


def _independent_truth(mph: float, duration_s: float, transverse_ft_s2: float, scenario: EnvelopeScenario):
    speed = mph * 22 / 15
    end = duration_s + scenario.visibility_start_s

    def dynamics(_t, state):
        velocity = state[3:]
        acceleration = -scenario.truth_drag_ft_inverse * np.linalg.norm(velocity) * velocity
        return np.r_[velocity, acceleration + [transverse_ft_s2, -32.174, 0.0]]

    def plate(_t, state):
        return state[2]

    truth = solve_ivp(
        dynamics, (0.0, max(end + 0.5, 1.5)),
        [scenario.initial_x_ft, scenario.initial_y_ft, speed * end * 0.9, 0.0, 0.0, -speed],
        dense_output=True, events=plate, rtol=1e-11, atol=1e-12,
    )
    times = np.linspace(scenario.visibility_start_s, end, max(7, round(duration_s * scenario.fps) + 1))
    states = truth.sol(times)
    crossing = truth.y_events[0][0, :3] if len(truth.y_events[0]) else None
    return times, states, crossing


def _synthetic_observations(times: np.ndarray, states: np.ndarray, scenario: EnvelopeScenario) -> list[StereoObservation]:
    rng = np.random.default_rng(scenario.noise_seed)
    sigmas = scenario.noise_sigma_ft * np.array(scenario.covariance_axis_scales)
    positions = states[:3].T + rng.normal(0.0, sigmas, (len(times), 3))
    timestamps = times + rng.normal(0.0, scenario.timing_jitter_s, len(times))
    # Jitter is intentionally kept independent of spatial covariance; its bias
    # is not hidden inside a declared positional noise model.
    covariance = (
        (float(sigmas[0]**2), 0.0, 0.0),
        (0.0, float(sigmas[1]**2), 0.0),
        (0.0, 0.0, float(sigmas[2]**2)),
    )
    return [
        StereoObservation(
            round(float(t) * 1e9), (0.0, 0.0), (0.0, 0.0), float(xyz[0]), float(xyz[1]), float(xyz[2]),
            1.0, covariance=covariance, confidence=1.0,
        )
        for t, xyz in zip(timestamps, positions)
    ]


def evaluate_case(
    mph: float, duration_s: float, transverse_ft_s2: float, *, scenario: EnvelopeScenario | None = None,
) -> dict:
    scenario = scenario or EnvelopeScenario()
    times, states, truth_crossing = _independent_truth(mph, duration_s, transverse_ft_s2, scenario)
    observations = _synthetic_observations(times, states, scenario)
    request = TrajectoryFitRequest(
        observations, 0.0, max_iter=100,
        drag_k0=scenario.optimizer_drag_seed_ft_inverse,
        drag_sigma=scenario.drag_prior_sigma_ft_inverse,
        drag_prior_enabled=scenario.drag_prior_enabled,
    )
    started = perf_counter()
    result = PhysicsDragFitter().fit_trajectory(request)
    elapsed = perf_counter() - started
    measured = (
        float(np.linalg.norm([result.samples[0].Vx, result.samples[0].Vy, result.samples[0].Vz])) * 15 / 22
        if result.samples else None
    )
    true_observed_speed = float(np.linalg.norm(states[3:, 0])) * 15 / 22
    plate_error = (
        np.array(result.plate_crossing_xyz_ft) - truth_crossing
        if result.plate_crossing_xyz_ft is not None and truth_crossing is not None else None
    )
    return {
        "input_speed_mph": mph, "truth_first_observed_speed_mph": true_observed_speed,
        "window_s": duration_s, "unmodeled_transverse_ft_s2": transverse_ft_s2,
        "scenario": asdict(scenario), "sample_count": len(observations),
        "eligible": not result.diagnostics.failure_codes and result.plate_crossing_xyz_ft is not None,
        "speed_error_mph_even_if_rejected": None if measured is None else measured - true_observed_speed,
        "plate_position_bias_ft_even_if_rejected": plate_error.tolist() if plate_error is not None else None,
        "plate_position_error_ft_even_if_rejected": float(np.linalg.norm(plate_error)) if plate_error is not None else None,
        "truth_plate_xyz_ft": truth_crossing.tolist() if truth_crossing is not None else None,
        "fitted_drag_ft_inverse": result.diagnostics.drag_param,
        "conditional_speed_std_mph": result.diagnostics.speed_std_assuming_model_mph,
        "rmse_3d_ft": result.diagnostics.rmse_3d_ft,
        "failure_codes": [code.value for code in result.diagnostics.failure_codes],
        "fit_seconds_excluding_startup": elapsed,
    }


def sweep_cases() -> list[tuple[float, float, float, EnvelopeScenario]]:
    """Small declared controls plus one-factor perturbations, not a full grid."""
    cases = [(mph, window, lift, EnvelopeScenario()) for mph, window, lift in product(
        (30.0, 60.0, 90.0), (0.1, 0.3), (0.0, 30.0),
    )]
    perturbations = [
        replace(EnvelopeScenario(), name="noise_seed_19", noise_seed=19),
        replace(EnvelopeScenario(), name="noise_seed_43", noise_seed=43),
        replace(EnvelopeScenario(), name="larger_spatial_noise", noise_sigma_ft=0.02),
        replace(EnvelopeScenario(), name="anisotropic_geometry", covariance_axis_scales=(1.0, 1.0, 4.0)),
        replace(EnvelopeScenario(), name="lateral_geometry", initial_x_ft=1.5, initial_y_ft=4.0),
        replace(EnvelopeScenario(), name="drag_seed_only", optimizer_drag_seed_ft_inverse=0.02),
        replace(EnvelopeScenario(), name="opt_in_drag_prior", optimizer_drag_seed_ft_inverse=0.02, drag_prior_enabled=True),
        replace(EnvelopeScenario(), name="broader_drag_prior", optimizer_drag_seed_ft_inverse=0.02,
                drag_prior_enabled=True, drag_prior_sigma_ft_inverse=0.01),
        replace(EnvelopeScenario(), name="synthetic_higher_drag_ball", truth_drag_ft_inverse=0.003,
                ball_model="synthetic_higher_drag_control"),
        replace(EnvelopeScenario(), name="cropped_window", visibility_start_s=0.08),
        replace(EnvelopeScenario(), name="30fps", fps=30),
        replace(EnvelopeScenario(), name="120fps", fps=120),
        replace(EnvelopeScenario(), name="0.5ms_timing_jitter", timing_jitter_s=0.0005),
        replace(EnvelopeScenario(), name="2ms_timing_jitter", timing_jitter_s=0.002),
    ]
    cases.extend((60.0, 0.3, 0.0, scenario) for scenario in perturbations)
    cases.extend((60.0, window, 0.0, EnvelopeScenario(name="window_coverage")) for window in (0.05, 0.5))
    return cases


def main() -> None:
    cases = [evaluate_case(mph, window, lift, scenario=scenario) for mph, window, lift, scenario in sweep_cases()]
    print(json.dumps({
        "schema_version": "synthetic_model_envelope.v2", "physical_claim_eligible": False,
        "truth": "independent scipy solve_ivp; quadratic drag plus optional constant transverse force",
        "limitations": "28 declared synthetic cases; no physical confidence intervals or validated camera/ball envelope",
        "cases": cases,
    }, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
