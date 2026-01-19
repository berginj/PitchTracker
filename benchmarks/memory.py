"""Memory stability benchmark.

Monitors memory usage over extended operation to detect leaks.
Target: Memory growth <10% over 30 minutes of operation.
"""

import time
import gc
import numpy as np
from typing import List, Tuple

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False
    print("Warning: psutil not available. Install with: pip install psutil")

from app.pipeline.detection.threading_pool import DetectionThreadPool
from contracts import Frame
from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig, FilterConfig


def get_memory_mb() -> float:
    """Get current process memory usage in MB."""
    if not PSUTIL_AVAILABLE:
        return 0.0
    process = psutil.Process()
    return process.memory_info().rss / (1024 * 1024)


def create_test_frame(width: int, height: int, timestamp_ns: int) -> Frame:
    """Create a test frame with random data."""
    image = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    return Frame(
        image=image,
        t_capture_monotonic_ns=timestamp_ns,
        t_capture_utc_ns=timestamp_ns,
        t_received_monotonic_ns=timestamp_ns,
        width=width,
        height=height,
        camera_id="benchmark",
    )


def benchmark_memory_stability(
    duration_seconds: int = 300,
    sample_interval: int = 10,
    width: int = 1280,
    height: int = 720,
) -> dict:
    """Benchmark memory stability over extended operation.

    Args:
        duration_seconds: How long to run (default: 300s = 5 minutes)
        sample_interval: How often to sample memory (seconds)
        width: Frame width in pixels
        height: Frame height in pixels

    Returns:
        Dictionary with memory statistics
    """
    if not PSUTIL_AVAILABLE:
        print("❌ ERROR: psutil not available. Cannot run memory benchmark.")
        print("Install with: pip install psutil")
        return {}

    print(f"\n{'='*60}")
    print(f"Memory Stability Benchmark")
    print(f"{'='*60}")
    print(f"Configuration:")
    print(f"  Duration: {duration_seconds} seconds ({duration_seconds/60:.1f} minutes)")
    print(f"  Sample Interval: {sample_interval} seconds")
    print(f"  Resolution: {width}x{height}")
    print(f"{'='*60}\n")

    # Create detector
    filter_config = FilterConfig()
    detector_config = DetectorConfig(filters=filter_config)
    detector = ClassicalDetector(detector_config)

    # Create detection pool
    pool = DetectionThreadPool()
    pool.set_detect_callback(lambda label, frame: detector.detect(frame))
    pool.start(queue_size=6)

    # Warm-up
    print("Warming up pipeline...")
    for i in range(50):
        timestamp = int(time.time() * 1e9) + i * 16_666_667
        frame = create_test_frame(width, height, timestamp)
        pool.enqueue_frame("left", frame)
    time.sleep(1.0)

    # Force garbage collection and measure initial memory
    gc.collect()
    time.sleep(0.5)
    initial_memory = get_memory_mb()

    print(f"Initial memory: {initial_memory:.1f} MB")
    print(f"Starting {duration_seconds}s stability test...")
    print()

    # Track memory samples
    memory_samples = [(0, initial_memory)]
    start_time = time.time()
    last_sample = start_time
    frame_count = 0

    # Run for specified duration
    while time.time() - start_time < duration_seconds:
        # Send frames continuously
        timestamp = int(time.time() * 1e9)
        frame = create_test_frame(width, height, timestamp)
        pool.enqueue_frame("left", frame)
        frame_count += 1

        # Sample memory at intervals
        if time.time() - last_sample >= sample_interval:
            gc.collect()
            current_memory = get_memory_mb()
            elapsed = time.time() - start_time
            growth_mb = current_memory - initial_memory
            growth_pct = (growth_mb / initial_memory) * 100

            memory_samples.append((elapsed, current_memory))
            print(
                f"  [{elapsed:>6.0f}s] Memory: {current_memory:>7.1f} MB "
                f"(+{growth_mb:>5.1f} MB, +{growth_pct:>5.1f}%)"
            )

            last_sample = time.time()

        # Throttle slightly to avoid overwhelming
        time.sleep(0.01)

    # Final measurement
    gc.collect()
    time.sleep(0.5)
    final_memory = get_memory_mb()

    # Stop pool
    pool.stop()

    # Calculate statistics
    memory_values = [m for _, m in memory_samples]
    memory_growth_mb = final_memory - initial_memory
    memory_growth_pct = (memory_growth_mb / initial_memory) * 100
    max_memory = max(memory_values)
    max_growth_mb = max_memory - initial_memory
    max_growth_pct = (max_growth_mb / initial_memory) * 100

    results = {
        "duration_seconds": duration_seconds,
        "frames_processed": frame_count,
        "initial_memory_mb": initial_memory,
        "final_memory_mb": final_memory,
        "max_memory_mb": max_memory,
        "growth_mb": memory_growth_mb,
        "growth_percent": memory_growth_pct,
        "max_growth_mb": max_growth_mb,
        "max_growth_percent": max_growth_pct,
        "samples": memory_samples,
    }

    # Print results
    print(f"\n{'='*60}")
    print(f"Results:")
    print(f"{'='*60}")
    print(f"  Duration: {duration_seconds} seconds")
    print(f"  Frames Processed: {frame_count:,}")
    print(f"\n  Memory Usage:")
    print(f"    Initial:  {initial_memory:>8.1f} MB")
    print(f"    Final:    {final_memory:>8.1f} MB")
    print(f"    Max:      {max_memory:>8.1f} MB")
    print(f"\n  Memory Growth:")
    print(f"    Final:    +{memory_growth_mb:>7.1f} MB (+{memory_growth_pct:>5.1f}%)")
    print(f"    Peak:     +{max_growth_mb:>7.1f} MB (+{max_growth_pct:>5.1f}%)")
    print(f"\n  Target: <10% growth over test duration")

    if memory_growth_pct < 10:
        print(f"  Status: ✅ PASS (memory stable)")
    elif memory_growth_pct < 20:
        print(f"  Status: ⚠️ WARNING (moderate growth)")
    else:
        print(f"  Status: ❌ FAIL (possible memory leak)")

    print(f"{'='*60}\n")

    return results


def benchmark_memory_rapid_cycling(
    num_cycles: int = 100, width: int = 1280, height: int = 720
) -> dict:
    """Benchmark memory with rapid start/stop cycles.

    Tests for memory leaks during repeated initialization/cleanup.

    Args:
        num_cycles: Number of start/stop cycles
        width: Frame width
        height: Frame height

    Returns:
        Dictionary with memory statistics
    """
    if not PSUTIL_AVAILABLE:
        print("❌ ERROR: psutil not available")
        return {}

    print(f"\n{'='*60}")
    print(f"Memory Rapid Cycling Benchmark")
    print(f"{'='*60}")
    print(f"Testing for leaks during repeated start/stop cycles")
    print(f"  Cycles: {num_cycles}")
    print(f"{'='*60}\n")

    # Initial memory
    gc.collect()
    initial_memory = get_memory_mb()
    print(f"Initial memory: {initial_memory:.1f} MB")
    print(f"Running {num_cycles} start/stop cycles...\n")

    memory_samples = []

    for i in range(num_cycles):
        # Create and start pool
        filter_config = FilterConfig()
        detector_config = DetectorConfig(filters=filter_config)
        detector = ClassicalDetector(detector_config)

        pool = DetectionThreadPool()
        pool.set_detect_callback(lambda label, frame: detector.detect(frame))
        pool.start(queue_size=6)

        # Process a few frames
        for j in range(10):
            timestamp = int(time.time() * 1e9) + j * 16_666_667
            frame = create_test_frame(width, height, timestamp)
            pool.enqueue_frame("left", frame)

        time.sleep(0.05)

        # Stop pool
        pool.stop()

        # Sample memory every 10 cycles
        if (i + 1) % 10 == 0:
            gc.collect()
            current_memory = get_memory_mb()
            growth_mb = current_memory - initial_memory
            growth_pct = (growth_mb / initial_memory) * 100

            memory_samples.append(current_memory)
            print(
                f"  Cycle {i+1:>3}/{num_cycles}: Memory: {current_memory:>7.1f} MB "
                f"(+{growth_mb:>5.1f} MB, +{growth_pct:>5.1f}%)"
            )

    # Final measurement
    gc.collect()
    time.sleep(0.5)
    final_memory = get_memory_mb()

    memory_growth_mb = final_memory - initial_memory
    memory_growth_pct = (memory_growth_mb / initial_memory) * 100

    # Print results
    print(f"\n{'='*60}")
    print(f"Results:")
    print(f"{'='*60}")
    print(f"  Cycles: {num_cycles}")
    print(f"  Initial Memory: {initial_memory:.1f} MB")
    print(f"  Final Memory: {final_memory:.1f} MB")
    print(f"  Growth: +{memory_growth_mb:.1f} MB (+{memory_growth_pct:.1f}%)")
    print(f"\n  Target: <5% growth after {num_cycles} cycles")
    print(f"  Status: {'✅ PASS' if memory_growth_pct < 5 else '⚠️ POSSIBLE LEAK'}")
    print(f"{'='*60}\n")

    return {
        "cycles": num_cycles,
        "initial_memory_mb": initial_memory,
        "final_memory_mb": final_memory,
        "growth_mb": memory_growth_mb,
        "growth_percent": memory_growth_pct,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Memory stability benchmark")
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Test duration in seconds (default: 300 = 5 minutes)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=10,
        help="Memory sample interval in seconds (default: 10)",
    )
    parser.add_argument(
        "--width", type=int, default=1280, help="Frame width (default: 1280)"
    )
    parser.add_argument(
        "--height", type=int, default=720, help="Frame height (default: 720)"
    )
    parser.add_argument(
        "--rapid-cycling",
        action="store_true",
        help="Run rapid start/stop cycling test",
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=100,
        help="Number of rapid cycles (default: 100)",
    )

    args = parser.parse_args()

    if args.rapid_cycling:
        benchmark_memory_rapid_cycling(num_cycles=args.cycles, width=args.width, height=args.height)
    else:
        benchmark_memory_stability(
            duration_seconds=args.duration,
            sample_interval=args.interval,
            width=args.width,
            height=args.height,
        )
