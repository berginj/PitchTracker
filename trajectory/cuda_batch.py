"""One resident CUDA context serves concurrent independent SciPy optimizers."""

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import replace
import logging
import queue
from threading import Event, Lock, Thread
from time import monotonic

import numpy as np

from trajectory.native_kernel import evaluator_factory, native_module

logger = logging.getLogger(__name__)


class BatchEvaluator:
    def __init__(self, count, module):
        self.count, self.module = count, module
        self.inputs: list[tuple | None] = [None] * count
        self.parameters = np.zeros((count, 7))
        self.pending: queue.Queue = queue.Queue()
        self.lock = Lock()
        self.registered = Event()
        self.stopped = Event()
        self.error = None
        self.thread = Thread(target=self._run, name="resident-cuda-batch", daemon=True)
        self.thread.start()

    def register(self, index, inputs, request):
        with self.lock:
            self.inputs[index] = inputs
            if all(value is not None for value in self.inputs):
                self.registered.set()
        return BatchRow(self, index, inputs, request)

    def skip(self, index):
        # A domain failure before objective construction must release peers.
        with self.lock:
            if self.inputs[index] is None:
                self.error = RuntimeError("A batch member was ineligible before GPU registration")
                self.registered.set()

    def evaluate(self, index, parameters):
        future: Future = Future()
        if self.stopped.is_set():
            raise RuntimeError("GPU batch stopped")
        self.pending.put((index, parameters.copy(), future))
        return future.result()

    def _run(self):
        while not self.registered.wait(0.05):
            if self.stopped.is_set():
                return
        gpu = None
        try:
            if self.error is None:
                values = [value for value in self.inputs if value is not None]
                if len(values) != self.count:
                    raise RuntimeError("GPU batch registration is incomplete")
                times, positions, weights, wind = [np.stack([row[column] for row in values]) for column in range(4)]
                k0, sigma, prior = values[0][4:]
                gpu = self.module.CudaEvaluator(times, positions, weights, wind, k0, sigma, prior)
        except Exception as exc:
            logger.warning("Resident CUDA initialization failed", exc_info=True)
            self.error = RuntimeError(str(exc))
        while not self.stopped.is_set() or not self.pending.empty():
            try:
                first = self.pending.get(timeout=0.05)
            except queue.Empty:
                continue
            jobs = [first]
            deadline = monotonic() + 0.001
            while len(jobs) < self.count and monotonic() < deadline:
                try:
                    jobs.append(self.pending.get(timeout=max(deadline - monotonic(), 0.00001)))
                except queue.Empty:
                    break
            try:
                if self.error is not None:
                    raise RuntimeError(str(self.error))
                assert gpu is not None
                for index, parameters, _ in jobs:
                    self.parameters[index] = parameters
                residual, jacobian = gpu.evaluate(self.parameters)
                for index, _, future in jobs:
                    future.set_result((residual[index].copy(), jacobian[index].copy()))
            except Exception as exc:
                logger.warning("Resident CUDA evaluation failed", exc_info=True)
                self.error = RuntimeError(str(exc))
                for _, _, future in jobs:
                    future.set_exception(self.error)

    def close(self):
        self.stopped.set()
        self.registered.set()
        self.thread.join()


class BatchRow:
    def __init__(self, owner, index, inputs, request):
        self.owner, self.index, self.inputs = owner, index, inputs
        self.first = True
        self.failed = False
        self.performance = {
            "effective_backend": "cuda",
            "requested_backend": request.compute_backend,
            "cuda_batch_size": owner.count,
            "implementation_version": owner.module.version,
            "qualification": "runtime_kernel_parity",
        }

    def evaluate(self, parameters):
        if not self.failed:
            try:
                result = self.owner.evaluate(self.index, parameters)
                if self.first:
                    reference = self.owner.module.evaluate(parameters, *self.inputs)
                    if not all(np.allclose(a, b, rtol=1e-10, atol=1e-9) for a, b in zip(reference, result)):
                        raise ValueError("CUDA batch residual/Jacobian parity failed")
                    self.first = False
                return result
            except (RuntimeError, ValueError) as exc:
                self.failed = True
                self.performance.update(effective_backend="cpu_native", fallback_reason=str(exc))
        return self.owner.module.evaluate(parameters, *self.inputs)


def fit_cuda_batch(requests, module=None):
    from trajectory.registry import TrajectoryFitterRegistry
    from trajectory.gpu_qualification import auto_admitted

    module = module or native_module()
    admitted = module is not None and getattr(module, "cuda_available", False)
    if any(request.compute_backend == "auto" for request in requests):
        admitted = admitted and auto_admitted(module, len(requests[0].observations), len(requests))
    if not admitted:
        return [TrajectoryFitterRegistry().create(request.mode).fit_trajectory(request) for request in requests]
    owner = BatchEvaluator(len(requests), module)

    def fit(index):
        request = replace(requests[index], compute_concurrency=len(requests))
        token = evaluator_factory.set(lambda _module, inputs, _request: owner.register(index, inputs, request))
        try:
            return TrajectoryFitterRegistry().create(request.mode).fit_trajectory(request)
        finally:
            owner.skip(index)
            evaluator_factory.reset(token)

    try:
        with ThreadPoolExecutor(max_workers=len(requests), thread_name_prefix="gpu-optimizer") as executor:
            return list(executor.map(fit, range(len(requests))))
    finally:
        owner.close()
