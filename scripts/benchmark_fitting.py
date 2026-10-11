"""Repeatable synthetic fitting latency/parity report; no physical accuracy claim."""

import argparse
from dataclasses import replace
import json
from pathlib import Path
from time import perf_counter

import numpy as np

from app.services.analysis.fit_batch import implementation_fingerprint
from app.services.analysis.fit_worker import FitWorkerPool
from trajectory.contracts import TrajectoryFitRequest
from trajectory.physics import PhysicsDragFitter
from trajectory.sim import SimConfig, simulate_ballistic


def measure(operation, repeats):
    times, results = [], []
    for _ in range(repeats):
        start = perf_counter()
        results.append(operation())
        times.append((perf_counter() - start) * 1000)
    return {"runs_ms": times, "p50_ms": float(np.median(times)), "p95_ms": float(np.percentile(times, 95))}, results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.repeats <= 100:
        parser.error("repeats must be between 1 and 100")
    request = TrajectoryFitRequest(
        simulate_ballistic(SimConfig(noise_ft=0.01, outlier_prob=0)), 0, correlation_id="benchmark"
    )
    fitter = PhysicsDragFitter()
    reference, baseline = measure(
        lambda: fitter.fit_trajectory(replace(request, compute_backend="reference")), args.repeats
    )
    compiled, optimized = measure(lambda: fitter.fit_trajectory(request), args.repeats)
    with FitWorkerPool() as pool:
        start = perf_counter()
        pool.warm()
        warmup_ms = (perf_counter() - start) * 1000
        worker, _ = measure(lambda: pool.fit(request), args.repeats)
    differences = []
    for left, right in zip(baseline, optimized):
        crossing_error = None
        if left.plate_crossing_xyz_ft is not None and right.plate_crossing_xyz_ft is not None:
            crossing_error = float(np.max(np.abs(np.asarray(left.plate_crossing_xyz_ft) - right.plate_crossing_xyz_ft)))
        differences.append(
            {
                "same_failure_codes": left.diagnostics.failure_codes == right.diagnostics.failure_codes,
                "plate_max_abs_error_ft": crossing_error,
            }
        )
    report = {
        "schema_version": "fitting_benchmark.v1",
        "scope": "synthetic_stereo_60_observations",
        "physical_claim_eligible": False,
        "implementation": implementation_fingerprint(),
        "reference": reference,
        "cpu": compiled,
        "warm_worker": worker,
        "worker_warmup_ms": warmup_ms,
        "speedup_p50": reference["p50_ms"] / compiled["p50_ms"],
        "differences": differences,
        "effective_backend": optimized[-1].diagnostics.performance,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("reference", "cpu", "warm_worker", "speedup_p50")}, indent=2))


if __name__ == "__main__":
    main()
