"""Native numerical parity and supervised-worker lifecycle regressions."""

from dataclasses import replace
import sys
from threading import Thread
from time import monotonic, sleep

import numpy as np
import pytest

from app.services.analysis.fit_worker import FitWorkerPool, PersistentFitWorker
from trajectory.contracts import FailureCode, TrajectoryFitRequest
from trajectory.native_kernel import native_module
from trajectory.physics import PhysicsDragFitter, _residuals
from trajectory.physics_estimation import observation_whiteners
from trajectory.sim import SimConfig, simulate_ballistic


@pytest.mark.parametrize("prior,wind", [(False, None), (True, (3.0, -1.0, 2.0))])
def test_native_residual_and_jacobian_preserve_discrete_physics(prior, wind):
    module = native_module()
    if module is None:
        pytest.skip("Optional native extension not installed")
    observations = simulate_ballistic(SimConfig(outlier_prob=0, noise_ft=0.01))[:25]
    request = TrajectoryFitRequest(observations, 0, drag_prior_enabled=prior, wind_ft_s=wind)
    times = np.asarray([(obs.t_ns - observations[0].t_ns) / 1e9 for obs in observations])
    positions = np.asarray([(obs.X, obs.Y, obs.Z) for obs in observations])
    weights, _ = observation_whiteners(request)
    params = np.asarray([0.5, 5, 55, 1, -2, -110, 0.002])
    args = (times, positions, weights, np.asarray(wind or (0, 0, 0), dtype=float), 0.002, 0.002, prior)
    residual, jacobian = module.evaluate(params, *args)

    def reference(p):
        return _residuals(
            np.r_[p, 0], times, positions, 0.002, 0.002, 0, 0.001, wind, whiteners=weights, drag_prior_enabled=prior
        )

    np.testing.assert_allclose(residual, reference(params), rtol=1e-10, atol=1e-9)
    for column in range(7):
        h = 1e-6 if column < 6 else 1e-7
        offset = np.zeros(7)
        offset[column] = h
        derivative = (reference(params + offset) - reference(params - offset)) / (2 * h)
        np.testing.assert_allclose(jacobian[:, column], derivative, rtol=2e-5, atol=2e-5)


@pytest.mark.parametrize("noise,outliers", [(0, 0), (0.01, 0), (0.02, 0.03)])
def test_native_fit_matches_reference_decisions(noise, outliers):
    if native_module() is None:
        pytest.skip("Optional native extension not installed")
    request = TrajectoryFitRequest(simulate_ballistic(SimConfig(noise_ft=noise, outlier_prob=outliers)), 0)
    fitter = PhysicsDragFitter()
    reference = fitter.fit_trajectory(replace(request, compute_backend="reference"))
    compiled = fitter.fit_trajectory(request)
    assert compiled.diagnostics.failure_codes == reference.diagnostics.failure_codes
    assert (compiled.plate_crossing_t_ns is None) == (reference.plate_crossing_t_ns is None)
    if compiled.plate_crossing_t_ns is not None:
        assert abs(compiled.plate_crossing_t_ns - reference.plate_crossing_t_ns) <= 100000
        np.testing.assert_allclose(compiled.plate_crossing_xyz_ft, reference.plate_crossing_xyz_ft, atol=0.001, rtol=0)
    left, right = compiled.samples[0], reference.samples[0]

    def speed(sample):
        return np.linalg.norm([sample.Vx, sample.Vy, sample.Vz]) * 15 / 22

    assert abs(speed(left) - speed(right)) <= 0.01


def test_persistent_deadline_reaps_and_restarts():
    worker = PersistentFitWorker([sys.executable, "-u", "-c", "import time; time.sleep(30)"])
    started = monotonic()
    result = worker.fit(TrajectoryFitRequest([], 0, deadline_seconds=0.2))
    assert result.diagnostics.failure_codes == [FailureCode.DEADLINE_EXCEEDED]
    assert worker.process is None
    assert monotonic() - started < 3
    worker.command = None
    result = worker.fit(TrajectoryFitRequest([], 0, correlation_id="restart"))
    process = worker.process
    assert result.diagnostics.failure_codes == [FailureCode.INSUFFICIENT_POINTS]
    worker.close()
    assert process.poll() is not None


def test_pool_shutdown_interrupts_an_inflight_native_hang():
    pool = FitWorkerPool()
    pool.workers[0].command = [sys.executable, "-u", "-c", "import time; time.sleep(30)"]
    errors = []

    def run():
        try:
            pool.fit(TrajectoryFitRequest([], 0, deadline_seconds=30))
        except Exception as exc:
            errors.append(type(exc).__name__)

    thread = Thread(target=run)
    thread.start()
    deadline = monotonic() + 3
    while pool.workers[0].process is None and monotonic() < deadline:
        sleep(0.01)
    process = pool.workers[0].process
    pool.close()
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert errors == ["CancelledError"]
    assert process.poll() is not None


def test_warm_fits_reuse_a_process():
    with FitWorkerPool() as pool:
        pool.warm()
        request = TrajectoryFitRequest([], 0, correlation_id="first")
        first = pool.fit(request)
        second = pool.fit(replace(request, correlation_id="second"))
        assert first.diagnostics.performance["worker_pid"] == second.diagnostics.performance["worker_pid"]
