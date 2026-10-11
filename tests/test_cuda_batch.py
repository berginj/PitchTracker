"""Shared scheduling with a CPU-backed CUDA fake, plus real worker protocol."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event, Lock
import sys
from time import monotonic

import numpy as np
import pytest

from app.services.analysis.fit_worker import Cancellation, PersistentFitWorker
from app.services.analysis.gpu_dispatcher import GPUFitDispatcher
from trajectory.contracts import FailureCode, TrajectoryFitRequest
from trajectory.cuda_batch import fit_cuda_batch
from trajectory.native_kernel import native_module
from trajectory.physics import PhysicsDragFitter
from trajectory.sim import SimConfig, simulate_ballistic


def requests(count=3):
    return [
        TrajectoryFitRequest(
            simulate_ballistic(SimConfig(outlier_prob=0, noise_ft=0.01, seed=index)),
            0,
            compute_backend="cuda",
            correlation_id=f"batch-{index}",
        )
        for index in range(count)
    ]


def test_shared_resident_batch_preserves_independent_optimizer_results():
    native = native_module()
    if native is None:
        pytest.skip("Optional native extension required")
    shapes = []

    class Resident:
        def __init__(self, times, positions, weights, wind, k0, sigma, prior):
            self.inputs = [
                (times[index], positions[index], weights[index], wind[index], k0, sigma, prior)
                for index in range(len(times))
            ]

        def evaluate(self, parameters):
            shapes.append(parameters.shape)
            values = [native.evaluate(row, *inputs) for row, inputs in zip(parameters, self.inputs)]
            return np.stack([value[0] for value in values]), np.stack([value[1] for value in values])

    class Module:
        cuda_available = True
        version = "test"
        CudaEvaluator = Resident
        evaluate = staticmethod(native.evaluate)

    inputs = requests()
    result = fit_cuda_batch(inputs, Module())
    baseline = [PhysicsDragFitter().fit_trajectory(replace(request, compute_backend="cpu")) for request in inputs]
    assert shapes and all(shape == (3, 7) for shape in shapes)
    for left, right in zip(result, baseline):
        assert left.diagnostics.failure_codes == right.diagnostics.failure_codes
        np.testing.assert_allclose(left.plate_crossing_xyz_ft, right.plate_crossing_xyz_ft, atol=1e-9)
        assert left.diagnostics.performance["cuda_batch_size"] == 3
        assert left.diagnostics.performance["effective_backend"] == "cuda"


def test_batch_worker_protocol_is_supervised_even_without_cuda():
    worker = PersistentFitWorker()
    try:
        worker.warm()
        results = worker.fit_batch(requests(2), Event())
        assert len(results) == 2
        assert all(result.samples for result in results)
    finally:
        worker.close()


def test_preobjective_rejection_does_not_deadlock_batch_peers():
    native = native_module()
    if native is None:
        pytest.skip("Optional native extension required")

    class Module:
        cuda_available = True
        version = "test"
        evaluate = staticmethod(native.evaluate)

    inputs = requests(2)
    inputs[0] = replace(inputs[0], observations=[])
    # The rejected member releases registration; the peer degrades to CPU.
    results = fit_cuda_batch(inputs, Module())
    assert results[0].diagnostics.failure_codes == [FailureCode.INSUFFICIENT_POINTS]
    assert results[1].samples
    assert results[1].diagnostics.performance["effective_backend"] == "cpu_native"


def test_unexpected_cuda_initialization_error_releases_all_optimizers():
    native = native_module()
    if native is None:
        pytest.skip("Optional native extension required")

    class Module:
        cuda_available = True
        version = "test"
        evaluate = staticmethod(native.evaluate)

        @staticmethod
        def CudaEvaluator(*args):
            raise OSError("Device unavailable")

    results = fit_cuda_batch(requests(2), Module())
    assert all(result.samples for result in results)
    assert all(result.diagnostics.performance["effective_backend"] == "cpu_native" for result in results)


def test_dispatcher_batches_admission_without_losing_correlation(monkeypatch):
    sizes = []
    lock = Lock()

    def batch(worker, group, cancel):
        with lock:
            sizes.append(len(group))
        return [PhysicsDragFitter().fit_trajectory(replace(request, compute_backend="cpu")) for request in group]

    monkeypatch.setattr(PersistentFitWorker, "fit_batch", batch)
    dispatcher = GPUFitDispatcher(3)
    try:
        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(lambda request: dispatcher.fit(request, Cancellation(Event())), requests()))
        assert sum(sizes) == 3
        assert any(size > 1 for size in sizes)
        assert all(result.samples for result in results)
    finally:
        dispatcher.close()


def test_shared_worker_hang_is_bounded_and_reaped():
    dispatcher = GPUFitDispatcher(2)
    dispatcher.worker.command = [
        sys.executable,
        "-u",
        "-c",
        'import time; print(\'{"message_type":"ready"}\', flush=True); time.sleep(30)',
    ]
    started = monotonic()
    try:
        result = dispatcher.fit(replace(requests(1)[0], deadline_seconds=0.3), Cancellation(Event()))
        assert result.diagnostics.failure_codes == [FailureCode.DEADLINE_EXCEEDED]
    finally:
        dispatcher.close()
    assert dispatcher.worker.process is None
    assert monotonic() - started < 4


def test_single_worker_blocked_input_write_is_bounded_and_reaped():
    worker = PersistentFitWorker([
        sys.executable, "-u", "-c",
        'import time; print(\'{"message_type":"ready"}\', flush=True); time.sleep(30)',
    ])
    started = monotonic()
    try:
        result = worker.fit(replace(requests(1)[0], deadline_seconds=0.3))
        assert result.diagnostics.failure_codes == [FailureCode.DEADLINE_EXCEEDED]
    finally:
        worker.close()
    assert worker.process is None
    assert monotonic() - started < 4
