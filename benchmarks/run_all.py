"""Run all performance benchmarks and generate comprehensive report.

This script runs all three benchmark suites:
1. Throughput - Frame processing FPS
2. Latency - Detection latency distribution (p50, p95, p99)
3. Memory - Memory stability over time

Results are saved to benchmarks/results/ directory.
"""

import sys
import time
import json
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.throughput import benchmark_detection_throughput, benchmark_multiple_resolutions
from benchmarks.latency import benchmark_detection_latency, benchmark_latency_under_load
from benchmarks.memory import benchmark_memory_stability, benchmark_memory_rapid_cycling


def run_all_benchmarks(
    quick_mode: bool = False,
    save_results: bool = True,
) -> dict:
    """Run all performance benchmarks.

    Args:
        quick_mode: Run shorter tests for faster results
        save_results: Save results to JSON file

    Returns:
        Dictionary containing all benchmark results
    """
    print("\n" + "=" * 80)
    print(" " * 20 + "PITCHTRACKER PERFORMANCE BENCHMARK SUITE")
    print("=" * 80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    if quick_mode:
        print("\nRunning in QUICK MODE (reduced test duration)")

    print("\n" + "=" * 80)

    results = {
        "timestamp": datetime.now().isoformat(),
        "quick_mode": quick_mode,
        "benchmarks": {},
    }

    # 1. Throughput Benchmarks
    print("\n" + "#" * 80)
    print("# BENCHMARK 1: FRAME PROCESSING THROUGHPUT")
    print("#" * 80)

    try:
        if quick_mode:
            # Quick mode: Single resolution, fewer frames
            throughput_result = benchmark_detection_throughput(
                num_frames=500,
                width=1280,
                height=720,
            )
            results["benchmarks"]["throughput"] = {
                "single_resolution": throughput_result,
            }
        else:
            # Full mode: Multiple resolutions
            throughput_results = benchmark_multiple_resolutions()
            results["benchmarks"]["throughput"] = {
                "multiple_resolutions": throughput_results,
            }
    except Exception as e:
        print(f"\n❌ ERROR in throughput benchmark: {e}")
        results["benchmarks"]["throughput"] = {"error": str(e)}

    time.sleep(2.0)  # Cool down between benchmarks

    # 2. Latency Benchmarks
    print("\n" + "#" * 80)
    print("# BENCHMARK 2: DETECTION LATENCY")
    print("#" * 80)

    try:
        if quick_mode:
            # Quick mode: Fewer frames
            latency_result = benchmark_detection_latency(
                num_frames=500,
                width=1280,
                height=720,
            )
            results["benchmarks"]["latency"] = {
                "normal": latency_result,
            }
        else:
            # Full mode: Normal + under load
            latency_result = benchmark_detection_latency(
                num_frames=1000,
                width=1280,
                height=720,
            )

            latency_load_result = benchmark_latency_under_load(
                num_frames=500,
                width=1280,
                height=720,
            )

            results["benchmarks"]["latency"] = {
                "normal": latency_result,
                "under_load": latency_load_result,
            }
    except Exception as e:
        print(f"\n❌ ERROR in latency benchmark: {e}")
        results["benchmarks"]["latency"] = {"error": str(e)}

    time.sleep(2.0)  # Cool down between benchmarks

    # 3. Memory Stability Benchmarks
    print("\n" + "#" * 80)
    print("# BENCHMARK 3: MEMORY STABILITY")
    print("#" * 80)

    try:
        if quick_mode:
            # Quick mode: Shorter duration
            memory_result = benchmark_memory_stability(
                duration_seconds=60,  # 1 minute
                sample_interval=10,
                width=1280,
                height=720,
            )
            results["benchmarks"]["memory"] = {
                "stability": memory_result,
            }
        else:
            # Full mode: Extended stability test + rapid cycling
            memory_result = benchmark_memory_stability(
                duration_seconds=300,  # 5 minutes
                sample_interval=10,
                width=1280,
                height=720,
            )

            memory_cycling_result = benchmark_memory_rapid_cycling(
                num_cycles=100,
                width=1280,
                height=720,
            )

            results["benchmarks"]["memory"] = {
                "stability": memory_result,
                "rapid_cycling": memory_cycling_result,
            }
    except Exception as e:
        print(f"\n❌ ERROR in memory benchmark: {e}")
        results["benchmarks"]["memory"] = {"error": str(e)}

    # Print Summary
    print("\n" + "=" * 80)
    print(" " * 30 + "SUMMARY REPORT")
    print("=" * 80)

    print_summary_report(results)

    # Save results
    if save_results:
        results_dir = Path(__file__).parent / "results"
        results_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        results_file = results_dir / f"benchmark_results_{timestamp}.json"

        with open(results_file, "w") as f:
            json.dump(results, f, indent=2)

        print(f"\n✅ Results saved to: {results_file}")

    print("\n" + "=" * 80)
    print(f"Completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80 + "\n")

    return results


def print_summary_report(results: dict):
    """Print a summary of all benchmark results."""
    benchmarks = results.get("benchmarks", {})

    # Throughput Summary
    print("\n1. THROUGHPUT RESULTS:")
    throughput = benchmarks.get("throughput", {})
    if "error" in throughput:
        print(f"   ❌ Error: {throughput['error']}")
    elif "single_resolution" in throughput:
        result = throughput["single_resolution"]
        fps = result.get("fps", 0)
        status = "✅ PASS" if fps >= 60 else "❌ BELOW TARGET"
        print(f"   Resolution: {result.get('resolution', 'N/A')}")
        print(f"   FPS: {fps:.2f}")
        print(f"   Target: 60 FPS minimum")
        print(f"   Status: {status}")
    elif "multiple_resolutions" in throughput:
        print(f"   {'Resolution':<15} {'FPS':>10} {'Status':>15}")
        print(f"   {'-' * 45}")
        for result in throughput["multiple_resolutions"]:
            resolution = result.get("resolution_name", result.get("resolution", "N/A"))
            fps = result.get("fps", 0)
            status = "✅ PASS" if fps >= 60 else "⚠️ BELOW TARGET"
            print(f"   {resolution:<15} {fps:>10.2f} {status:>15}")

    # Latency Summary
    print("\n2. LATENCY RESULTS:")
    latency = benchmarks.get("latency", {})
    if "error" in latency:
        print(f"   ❌ Error: {latency['error']}")
    elif "normal" in latency:
        result = latency["normal"]
        p95 = result.get("p95", 0)
        status = "✅ PASS" if p95 < 20 else "⚠️ ABOVE TARGET"
        print(f"   P50 (median): {result.get('p50', 0):.2f} ms")
        print(f"   P95: {p95:.2f} ms")
        print(f"   P99: {result.get('p99', 0):.2f} ms")
        print(f"   Target: <20ms p95 latency")
        print(f"   Status: {status}")

        if "under_load" in latency:
            load_result = latency["under_load"]
            max_latency = load_result.get("max", 0)
            load_status = "✅ GOOD" if max_latency < 100 else "⚠️ HIGH LATENCY SPIKES"
            print(f"\n   Under Load:")
            print(f"   P95: {load_result.get('p95', 0):.2f} ms")
            print(f"   Max: {max_latency:.2f} ms")
            print(f"   Status: {load_status}")

    # Memory Summary
    print("\n3. MEMORY STABILITY RESULTS:")
    memory = benchmarks.get("memory", {})
    if "error" in memory:
        print(f"   ❌ Error: {memory['error']}")
    elif "stability" in memory:
        result = memory["stability"]
        if result:  # Check if result is not empty
            growth_pct = result.get("growth_percent", 0)

            if growth_pct < 10:
                status = "✅ PASS (memory stable)"
            elif growth_pct < 20:
                status = "⚠️ WARNING (moderate growth)"
            else:
                status = "❌ FAIL (possible memory leak)"

            print(f"   Duration: {result.get('duration_seconds', 0)} seconds")
            print(f"   Initial Memory: {result.get('initial_memory_mb', 0):.1f} MB")
            print(f"   Final Memory: {result.get('final_memory_mb', 0):.1f} MB")
            print(f"   Growth: +{result.get('growth_mb', 0):.1f} MB (+{growth_pct:.1f}%)")
            print(f"   Target: <10% growth")
            print(f"   Status: {status}")

            if "rapid_cycling" in memory:
                cycling_result = memory["rapid_cycling"]
                cycling_growth_pct = cycling_result.get("growth_percent", 0)
                cycling_status = "✅ PASS" if cycling_growth_pct < 5 else "⚠️ POSSIBLE LEAK"
                print(f"\n   Rapid Cycling ({cycling_result.get('cycles', 0)} cycles):")
                print(f"   Growth: +{cycling_result.get('growth_mb', 0):.1f} MB (+{cycling_growth_pct:.1f}%)")
                print(f"   Status: {cycling_status}")
        else:
            print("   ⚠️ psutil not available - memory benchmarks skipped")

    # Overall Assessment
    print("\n" + "=" * 80)
    print("OVERALL ASSESSMENT:")
    print("=" * 80)

    all_passed = True
    issues = []

    # Check throughput
    if "throughput" in benchmarks and "error" not in benchmarks["throughput"]:
        if "single_resolution" in benchmarks["throughput"]:
            fps = benchmarks["throughput"]["single_resolution"].get("fps", 0)
            if fps < 60:
                all_passed = False
                issues.append(f"Throughput below target: {fps:.2f} FPS < 60 FPS")
        elif "multiple_resolutions" in benchmarks["throughput"]:
            for result in benchmarks["throughput"]["multiple_resolutions"]:
                fps = result.get("fps", 0)
                if fps < 60:
                    resolution = result.get("resolution_name", result.get("resolution", "N/A"))
                    all_passed = False
                    issues.append(f"Throughput below target at {resolution}: {fps:.2f} FPS < 60 FPS")

    # Check latency
    if "latency" in benchmarks and "error" not in benchmarks["latency"]:
        if "normal" in benchmarks["latency"]:
            p95 = benchmarks["latency"]["normal"].get("p95", 0)
            if p95 >= 20:
                all_passed = False
                issues.append(f"Latency above target: p95 {p95:.2f} ms >= 20 ms")

    # Check memory
    if "memory" in benchmarks and "error" not in benchmarks["memory"]:
        if "stability" in benchmarks["memory"]:
            result = benchmarks["memory"]["stability"]
            if result:  # Not empty dict
                growth_pct = result.get("growth_percent", 0)
                if growth_pct >= 20:
                    all_passed = False
                    issues.append(f"Memory leak detected: {growth_pct:.1f}% growth >= 20%")
                elif growth_pct >= 10:
                    issues.append(f"⚠️ Moderate memory growth: {growth_pct:.1f}%")

    if all_passed and not issues:
        print("✅ ALL BENCHMARKS PASSED")
        print("\nThe system meets all performance targets:")
        print("  • Throughput: ≥60 FPS")
        print("  • Latency: <20ms p95")
        print("  • Memory: <10% growth")
    elif all_passed and issues:
        print("✅ ALL CRITICAL BENCHMARKS PASSED")
        print("\nWarnings:")
        for issue in issues:
            print(f"  • {issue}")
    else:
        print("⚠️ SOME BENCHMARKS BELOW TARGET")
        print("\nIssues found:")
        for issue in issues:
            print(f"  • {issue}")
        print("\nRecommendation: Investigate performance bottlenecks")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run all performance benchmarks")
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Run in quick mode (shorter tests, faster results)",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save results to file",
    )

    args = parser.parse_args()

    try:
        run_all_benchmarks(
            quick_mode=args.quick,
            save_results=not args.no_save,
        )
    except KeyboardInterrupt:
        print("\n\n⚠️ Benchmark interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error running benchmarks: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
