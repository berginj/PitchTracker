"""Independent synthetic model-limit sweep; never a physical accuracy report.

Run: python -m benchmarks.trajectory_model_envelope
Emits JSON to stdout. Ground truth uses solve_ivp, not the fitted RK4 model.
"""

from itertools import product
import json
from time import perf_counter

import numpy as np
from scipy.integrate import solve_ivp

from contracts import StereoObservation
from trajectory.contracts import TrajectoryFitRequest
from trajectory.physics import PhysicsDragFitter


def evaluate_case(mph: float, duration_s: float, transverse_ft_s2: float) -> dict:
    speed = mph * 22 / 15

    def dynamics(_t, state):
        velocity = state[3:]
        return np.r_[velocity, -0.0015 * np.linalg.norm(velocity) * velocity + [transverse_ft_s2, -32.174, 0.0]]

    times = np.linspace(0.0, duration_s, max(7, round(duration_s * 60) + 1))
    truth = solve_ivp(
        dynamics,
        (0.0, duration_s),
        [0.0, 3.0, speed * duration_s * 0.9, 0.0, 0.0, -speed],
        t_eval=times,
        dense_output=True,
        rtol=1e-11,
        atol=1e-12,
    )
    # Known synthetic isotropic noise scale, not a camera-system uncertainty.
    sigma_ft = 0.005
    rng = np.random.default_rng(7)
    positions = truth.y[:3].T + rng.normal(0.0, sigma_ft, (len(times), 3))
    covariance = ((sigma_ft**2, 0.0, 0.0), (0.0, sigma_ft**2, 0.0), (0.0, 0.0, sigma_ft**2))
    observations = [
        StereoObservation(
            round(float(t) * 1e9), (0.0, 0.0), (0.0, 0.0), float(xyz[0]), float(xyz[1]), float(xyz[2]),
            1.0, covariance=covariance, confidence=1.0
        )
        for t, xyz in zip(times, positions)
    ]
    started = perf_counter()
    result = PhysicsDragFitter().fit_trajectory(TrajectoryFitRequest(observations, 0.0, max_iter=100))
    elapsed = perf_counter() - started
    measured = (
        float(np.linalg.norm([result.samples[0].Vx, result.samples[0].Vy, result.samples[0].Vz])) * 15 / 22
        if result.samples
        else None
    )
    return {
        "input_speed_mph": mph,
        "window_s": duration_s,
        "unmodeled_transverse_ft_s2": transverse_ft_s2,
        "noise_sigma_ft": sigma_ft,
        "noise_seed": 7,
        "sample_count": len(observations),
        "eligible": not result.diagnostics.failure_codes and result.plate_crossing_xyz_ft is not None,
        "speed_error_mph_even_if_rejected": None if measured is None else measured - mph,
        "rmse_3d_ft": result.diagnostics.rmse_3d_ft,
        "failure_codes": [code.value for code in result.diagnostics.failure_codes],
        "fit_seconds_excluding_startup": elapsed,
    }


def main() -> None:
    cases = [evaluate_case(*case) for case in product((30.0, 60.0, 90.0), (0.1, 0.3), (0.0, 30.0))]
    print(
        json.dumps(
            {
                "schema_version": "synthetic_model_envelope.v1",
                "physical_claim_eligible": False,
                "truth": "independent scipy solve_ivp; quadratic drag plus optional constant transverse force",
                "limitations": "12 fixed-seed synthetic cases, not a validated physical envelope",
                "cases": cases,
            },
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
