"""GPU selection cannot silently bypass parity or end-to-end admission."""

import json
from types import SimpleNamespace

import numpy as np

from trajectory.compute_backend import QualifiedEvaluator
from trajectory.gpu_qualification import auto_admitted, environment


def fake_module():
    def evaluate(parameters, *inputs):
        return np.asarray([parameters.sum()]), np.ones((1, 7))

    class GPU:
        failed = False
        mismatch = False

        def __init__(self, *inputs):
            pass

        def evaluate(self, parameters):
            if self.failed:
                raise RuntimeError("device lost")
            residual, jacobian = evaluate(parameters[0])
            return residual[None, :] + int(self.mismatch), jacobian[None, :, :]

    return SimpleNamespace(
        version="test", cuda_available=True, evaluate=evaluate, CudaEvaluator=GPU, cuda_device=lambda: "test-device"
    )


def inputs():
    return np.zeros(1), np.zeros((1, 3)), np.zeros((1, 3, 3)), np.zeros(3), 0.002, 0.002, False


def test_unavailable_cuda_falls_back_with_diagnostics():
    module = fake_module()
    module.cuda_available = False
    evaluator = QualifiedEvaluator(module, inputs(), "cuda")
    evaluator.evaluate(np.ones(7))
    assert evaluator.performance["effective_backend"] == "cpu_native"
    assert "unavailable" in evaluator.performance["fallback_reason"]


def test_cuda_parity_failure_rejects_backend():
    module = fake_module()
    module.CudaEvaluator.mismatch = True
    evaluator = QualifiedEvaluator(module, inputs(), "cuda")
    evaluator.evaluate(np.ones(7))
    assert evaluator.gpu is None
    assert "parity failed" in evaluator.performance["fallback_reason"]


def test_device_loss_recomputes_on_cpu():
    module = fake_module()
    evaluator = QualifiedEvaluator(module, inputs(), "cuda")
    evaluator.evaluate(np.ones(7))
    assert evaluator.performance["effective_backend"] == "cuda"
    evaluator.gpu.failed = True
    residual, _ = evaluator.evaluate(np.ones(7) * 2)
    np.testing.assert_array_equal(residual, [14])
    assert evaluator.performance["effective_backend"] == "cpu_native"
    assert "device lost" in evaluator.performance["fallback_reason"]


def test_auto_kernel_parity_alone_is_insufficient(monkeypatch):
    monkeypatch.delenv("PITCHTRACKER_CUDA_QUALIFICATION", raising=False)
    evaluator = QualifiedEvaluator(fake_module(), inputs(), "auto")
    evaluator.evaluate(np.ones(7))
    assert evaluator.gpu is None
    assert "end-to-end" in evaluator.performance["fallback_reason"]


def test_auto_receipt_is_bound_to_workload_and_build(tmp_path, monkeypatch):
    class Module:
        __file__ = str(tmp_path / "kernel.pyd")

        def cuda_device(self):
            return "device/driver-1"

    module = Module()
    (tmp_path / "kernel.pyd").write_bytes(b"test")
    receipt = {
        "schema_version": "cuda_qualification.v1",
        "environment": environment(module),
        "fit_parity_passed": True,
        "throughput_speedup": 1.6,
        "sample_counts": [60],
        "workers": 1,
    }
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(receipt))
    monkeypatch.setenv("PITCHTRACKER_CUDA_QUALIFICATION", str(path))
    assert auto_admitted(module, 60)
    assert not auto_admitted(module, 61)
    assert not auto_admitted(module, 60, 2)
    receipt["throughput_speedup"] = 1.49
    path.write_text(json.dumps(receipt))
    assert not auto_admitted(module, 60)
    receipt["throughput_speedup"] = 2
    receipt["environment"]["device"] = "other driver"
    path.write_text(json.dumps(receipt))
    assert not auto_admitted(module, 60)
