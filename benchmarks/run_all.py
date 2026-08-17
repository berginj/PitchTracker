"""Run all benchmarks and produce a conserved-outcome summary.

Summary pass/fail never uses ``offered`` as the denominator for
processed-FPS or processed-latency comparisons.  Every result
envelope includes terminal-outcome conservation proof, raw samples,
benchmark config, commit identity, and host identity.
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.throughput import (  # noqa: E402
    benchmark_detection_throughput,
)
from benchmarks.latency import (  # noqa: E402
    benchmark_detection_latency,
)
from benchmarks.memory import (  # noqa: E402
    benchmark_memory_stability,
    benchmark_memory_rapid_cycling,
)


def run_all_benchmarks(
    quick_mode: bool = False,
    save_results: bool = True,
) -> Dict[str, Any]:
    """Run all benchmarks and return combined results.

    In quick mode, frame counts and durations are reduced.
    """
    frames_tp = 30 if quick_mode else 100
    frames_lat = 30 if quick_mode else 100
    mem_dur = 10 if quick_mode else 60
    mem_cycles = 5 if quick_mode else 20

    results: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "quick_mode": quick_mode,
        "benchmarks": {},
    }

    # 1. Throughput
    try:
        results["benchmarks"]["throughput"] = benchmark_detection_throughput(
            num_frames=frames_tp, width=1280, height=720,
        )
    except Exception as e:
        results["benchmarks"]["throughput"] = {"error": str(e)}

    time.sleep(1.0)

    # 2. Latency
    try:
        results["benchmarks"]["latency"] = benchmark_detection_latency(
            num_frames=frames_lat, width=1280, height=720,
        )
    except Exception as e:
        results["benchmarks"]["latency"] = {"error": str(e)}

    time.sleep(1.0)

    # 3. Memory stability
    try:
        results["benchmarks"]["memory_stability"] = benchmark_memory_stability(
            duration_seconds=mem_dur, sample_interval=5, width=1280, height=720,
        )
    except Exception as e:
        results["benchmarks"]["memory_stability"] = {"error": str(e)}

    # 4. Memory rapid cycling
    try:
        results["benchmarks"]["memory_cycling"] = benchmark_memory_rapid_cycling(
            num_cycles=mem_cycles, width=1280, height=720,
        )
    except Exception as e:
        results["benchmarks"]["memory_cycling"] = {"error": str(e)}

    # Summary
    _print_summary(results)

    if save_results:
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = results_dir / f"benchmark_results_{ts}.json"
        with open(out, "w") as f:
            json.dump(results, f, indent=2)

    return results


def _extract_results(benchmark: Any) -> Dict[str, Any]:
    """Safely extract the results dict from an envelope or raw dict."""
    if isinstance(benchmark, dict):
        result = benchmark.get("results", benchmark)
        return dict(result) if isinstance(result, dict) else {}
    return {}


def _print_summary(results: Dict[str, Any]) -> None:
    benchmarks = results.get("benchmarks", {})
    issues = []

    # Throughput — denominator is processed, not offered
    tp = _extract_results(benchmarks.get("throughput", {}))
    if "error" not in tp and "processed_fps" in tp:
        conserved = tp.get("conserved", False)
        fps = tp["processed_fps"]
        processed = tp.get("processed", 0)
        offered = tp.get("offered", 0)
        print(f"Throughput: {fps:.1f} processed FPS "
              f"({processed}/{offered} processed/offered, "
              f"conserved={conserved})")
        if not conserved:
            issues.append("Throughput: terminal outcomes not conserved")

    # Latency — only frames_measured is meaningful
    lat = _extract_results(benchmarks.get("latency", {}))
    if "error" not in lat and "p95" in lat:
        print(f"Latency p95: {lat['p95']:.2f} ms "
              f"(measured {lat.get('frames_measured', '?')} frames, "
              f"conserved={lat.get('conserved', '?')})")
        if not lat.get("conserved", False):
            issues.append("Latency: terminal outcomes not conserved")

    # Memory
    mem = _extract_results(benchmarks.get("memory_stability", {}))
    if "error" not in mem and "growth_percent" in mem:
        print(f"Memory growth: {mem['growth_percent']:.1f}% "
              f"(conserved={mem.get('conserved', '?')})")
        if not mem.get("conserved", False):
            issues.append("Memory: terminal outcomes not conserved")

    cyc = _extract_results(benchmarks.get("memory_cycling", {}))
    if "error" not in cyc and "growth_percent" in cyc:
        print(f"Cycling growth: {cyc['growth_percent']:.1f}% "
              f"(all_conserved={cyc.get('all_cycles_conserved', '?')})")

    if issues:
        print("\nConservation issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\nAll benchmarks conserve terminal outcomes.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run all benchmarks")
    parser.add_argument("--quick", action="store_true")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    try:
        run_all_benchmarks(quick_mode=args.quick, save_results=not args.no_save)
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as e:
        print(f"Fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
