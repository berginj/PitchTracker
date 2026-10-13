"""Opt-in qualification of an independently packaged numerical worker."""

from concurrent.futures import CancelledError
from dataclasses import replace
import os
from pathlib import Path
from threading import Event, Timer
from time import monotonic

import pytest
import psutil

from app.services.analysis.fit_worker import FitWorkerPool, PersistentFitWorker
from contracts import StereoObservation
from scripts.qualify_cuda import cases, parity
from trajectory.contracts import FailureCode, TrajectoryFitRequest
from trajectory.physics import PhysicsDragFitter


@pytest.fixture
def external_worker(monkeypatch):
    path = os.environ.get("PITCHTRACKER_QUALIFICATION_WORKER")
    if not path:
        pytest.skip("Set PITCHTRACKER_QUALIFICATION_WORKER to the numerical-only executable")
    assert Path(path).is_file()
    monkeypatch.setenv("PITCHTRACKER_NUMERICAL_WORKER", str(Path(path).resolve()))


def test_packaged_worker_preserves_reference_decisions(external_worker):
    fitter = PhysicsDragFitter()
    with FitWorkerPool() as pool:
        pool.warm()
        assert pool.workers[0].capabilities["native"]
        first_pid = None
        for request in cases():
            reference = fitter.fit_trajectory(replace(request, compute_backend="reference"))
            result = pool.fit(request)
            assert parity(reference, result), request.correlation_id
            assert result.diagnostics.performance["effective_backend"] == "cpu_native"
            pid = result.diagnostics.performance["worker_pid"]
            if first_pid is None:
                first_pid = pid
            assert pid == first_pid


def test_cpu_bundle_has_explicit_gpu_fallback_and_missing_ray_support(external_worker):
    request = cases()[0]
    with FitWorkerPool() as pool:
        pool.warm()
        assert not pool.workers[0].capabilities["cuda"]
        reference = pool.fit(request)
        for backend in ("cuda", "auto"):
            result = pool.fit(replace(request, compute_backend=backend))
            assert parity(reference, result)
            assert result.diagnostics.performance["effective_backend"] == "cpu_native"
            assert result.diagnostics.performance["fallback_reason"]
        rays = pool.fit(replace(request, mode="ray_graph"))
        assert rays.diagnostics.failure_codes == [FailureCode.CAMERA_MODEL_MISSING]


def test_packaged_worker_cancellation_reaps_and_recovers(external_worker):
    worker = PersistentFitWorker()
    cancel = Event()
    worker.warm()
    process = worker.process
    child_pid = worker.capabilities["worker_pid"]
    observations = [
        StereoObservation(i * 1_000_000, (0., 0.), (0., 0.), 0., 2.5, 60 - i * 0.012, 1.)
        for i in range(8000)
    ]
    timer = Timer(0.05, cancel.set)
    timer.start()
    started = monotonic()
    try:
        with pytest.raises(CancelledError):
            worker.fit(TrajectoryFitRequest(observations, 0., deadline_seconds=5), cancel)
        assert process.poll() is not None
        # Windows can retain a terminated process object/PID while handles are
        # open. Waiting for its exit proves termination without relying on PID
        # disappearance or accidentally accepting a still-running child.
        try:
            psutil.Process(child_pid).wait(timeout=1)
        except psutil.NoSuchProcess:
            pass
        assert monotonic() - started < 3
        assert worker.process is None
        recovered = worker.fit(cases()[0])
        assert recovered.diagnostics.performance["effective_backend"] == "cpu_native"
    finally:
        timer.cancel()
        worker.close()
