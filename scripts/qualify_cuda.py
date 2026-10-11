"""Produce an Auto admission receipt only after fit parity and >=1.5x throughput."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import json
import os
from pathlib import Path
from time import perf_counter

import numpy as np

from app.services.analysis.fit_worker import FitWorkerPool
from trajectory.contracts import TrajectoryFitRequest
from trajectory.gpu_qualification import environment
from trajectory.native_kernel import native_module
from trajectory.sim import SimConfig, simulate_ballistic


def cases():
    requests = []
    for noise, outliers in ((0, 0), (0.01, 0), (0.02, 0.03)):
        for seed in range(5):
            requests.append(
                TrajectoryFitRequest(
                    simulate_ballistic(
                        SimConfig(
                            noise_ft=noise,
                            outlier_prob=outliers,
                            seed=seed,
                        )
                    ),
                    0,
                    correlation_id=f"qualify-{noise}-{seed}",
                )
            )
    return requests


def fits(requests, backend, workers):
    with FitWorkerPool(workers) as pool:
        pool.warm()
        pool.fit(replace(requests[0], compute_backend=backend))
        start = perf_counter()
        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(pool.fit, [replace(request, compute_backend=backend) for request in requests]))
        return perf_counter() - start, results


def parity(left, right):
    if left.diagnostics.failure_codes != right.diagnostics.failure_codes:
        return False
    if (left.plate_crossing_t_ns is None) != (right.plate_crossing_t_ns is None):
        return False
    if left.plate_crossing_t_ns is not None:
        if abs(left.plate_crossing_t_ns - right.plate_crossing_t_ns) > 100000:
            return False
        if not np.allclose(left.plate_crossing_xyz_ft, right.plate_crossing_xyz_ft, atol=0.001, rtol=0):
            return False
    if bool(left.samples) != bool(right.samples):
        return False
    if left.samples:
        a, b = left.samples[0], right.samples[0]
        speeds = [np.linalg.norm([sample.Vx, sample.Vy, sample.Vz]) * 15 / 22 for sample in (a, b)]
        if abs(speeds[0] - speeds[1]) > 0.01:
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1, choices=range(1, 9))
    args = parser.parse_args()
    module = native_module()
    if (module is None or not getattr(module, "cuda_available", False)) and not os.environ.get(
        "PITCHTRACKER_NUMERICAL_WORKER"
    ):
        parser.error("Install a CUDA build of the native extension and a compatible NVIDIA driver")
    requests = cases()
    reference_seconds, reference = fits(requests, "cpu", args.workers)
    cuda_seconds, cuda = fits(requests, "cuda", args.workers)
    passed = all(
        parity(a, b) and b.diagnostics.performance.get("effective_backend") == "cuda" for a, b in zip(reference, cuda)
    )
    ratio = reference_seconds / cuda_seconds
    receipt = {
        "schema_version": "cuda_qualification.v1",
        "environment": cuda[0].diagnostics.performance.get("gpu_environment")
        or (environment(module) if module is not None and getattr(module, "cuda_available", False) else None),
        "fit_parity_passed": passed,
        "sample_counts": sorted({len(r.observations) for r in requests}),
        "throughput_speedup": ratio,
        "workers": args.workers,
        "cases": len(requests),
        "auto_eligible": passed and ratio >= 1.5,
        "physical_claim_eligible": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
