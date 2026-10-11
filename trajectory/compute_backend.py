"""Conservative GPU admission and transparent CPU fallback."""

from time import perf_counter

import numpy as np


class QualifiedEvaluator:
    def __init__(self, module, inputs, backend, concurrency=1):
        self.module, self.inputs, self.backend = module, inputs, backend
        self.concurrency = concurrency
        self.gpu = None
        self.checked = False
        self.performance = {
            "effective_backend": "cpu_native",
            "requested_backend": backend,
            "implementation_version": module.version,
        }

    def evaluate(self, parameters):
        if not self.checked:
            self.checked = True
            if self.backend in {"cuda", "auto"}:
                self._qualify(parameters)
        if self.gpu is not None:
            try:
                residual, jacobian = self.gpu.evaluate(parameters[None, :])
                return residual[0], jacobian[0]
            except (RuntimeError, ValueError) as exc:
                self.gpu = None
                self.performance.update(effective_backend="cpu_native", fallback_reason=f"CUDA failed: {exc}")
        return self.module.evaluate(parameters, *self.inputs)

    def _qualify(self, parameters):
        if not getattr(self.module, "cuda_available", False):
            self.performance["fallback_reason"] = "CUDA extension/device unavailable"
            return
        if self.backend == "auto":
            from trajectory.gpu_qualification import auto_admitted

            if not auto_admitted(self.module, len(self.inputs[0]), self.concurrency):
                self.performance["fallback_reason"] = "Auto requires end-to-end batch qualification; CPU selected"
                return
        try:
            times, positions, weights, wind, k0, sigma, prior = self.inputs
            gpu = self.module.CudaEvaluator(
                times[None, :], positions[None, :, :], weights[None, :, :, :], wind[None, :], k0, sigma, prior
            )
            reference = self.module.evaluate(parameters, *self.inputs)
            candidate = gpu.evaluate(parameters[None, :])
            if not all(np.allclose(a, b[0], rtol=1e-10, atol=1e-9) for a, b in zip(reference, candidate)):
                raise ValueError("CUDA residual/Jacobian parity failed")
            started = perf_counter()
            for _ in range(5):
                self.module.evaluate(parameters, *self.inputs)
            cpu_time = perf_counter() - started
            started = perf_counter()
            for _ in range(5):
                gpu.evaluate(parameters[None, :])
            gpu_time = perf_counter() - started
            ratio = cpu_time / max(gpu_time, 1e-12)
            self.performance.update(
                cuda_device=self.module.cuda_device(), cuda_kernel_speedup=ratio, qualification="kernel_parity_only"
            )
            # A one-fit kernel benchmark cannot establish whole-study throughput.
            if self.backend == "auto":
                self.performance["qualification"] = "end_to_end_receipt_and_runtime_kernel_parity"
            self.gpu = gpu
            self.performance["effective_backend"] = "cuda"
        except (RuntimeError, ValueError) as exc:
            self.performance["fallback_reason"] = f"CUDA qualification failed: {exc}"
