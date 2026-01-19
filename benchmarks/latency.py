"""Detection latency benchmark.

Measures time from frame capture to detection result.
Target: <20ms p95 latency for real-time responsiveness.
"""

import time
import numpy as np
from typing import List, Tuple
from collections import deque

from app.pipeline.detection.threading_pool import DetectionThreadPool
from contracts import Frame
from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig, FilterConfig


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


def calculate_percentiles(latencies: List[float]) -> dict:
    """Calculate latency percentiles."""
    if not latencies:
        return {}

    sorted_latencies = sorted(latencies)
    n = len(sorted_latencies)

    return {
        "min": sorted_latencies[0],
        "p50": sorted_latencies[int(n * 0.50)],
        "p75": sorted_latencies[int(n * 0.75)],
        "p90": sorted_latencies[int(n * 0.90)],
        "p95": sorted_latencies[int(n * 0.95)],
        "p99": sorted_latencies[int(n * 0.99)] if n >= 100 else sorted_latencies[-1],
        "max": sorted_latencies[-1],
        "mean": sum(sorted_latencies) / n,
    }


def benchmark_detection_latency(
    num_frames: int = 1000, width: int = 1280, height: int = 720
) -> dict:
    """Benchmark detection latency distribution.

    Args:
        num_frames: Number of frames to process
        width: Frame width in pixels
        height: Frame height in pixels

    Returns:
        Dictionary with latency statistics
    """
    print(f"\n{'='*60}")
    print(f"Detection Latency Benchmark")
    print(f"{'='*60}")
    print(f"Configuration:")
    print(f"  Frames: {num_frames}")
    print(f"  Resolution: {width}x{height}")
    print(f"{'='*60}\n")

    # Create detector
    filter_config = FilterConfig()
    detector_config = DetectorConfig(filters=filter_config)
    detector = ClassicalDetector(detector_config)

    # Track latencies
    latencies_ms = []
    results_queue = deque(maxlen=num_frames)

    def detect_with_timing(label: str, frame: Frame):
        """Detector wrapper that measures latency."""
        start_time = time.perf_counter()
        detections = detector.detect(frame)
        end_time = time.perf_counter()

        latency_ms = (end_time - start_time) * 1000
        results_queue.append(latency_ms)

        return detections

    # Create detection pool
    pool = DetectionThreadPool()
    pool.set_detect_callback(detect_with_timing)
    pool.start(queue_size=6)

    # Warm-up
    print("Warming up...")
    for i in range(10):
        timestamp = int(time.time() * 1e9) + i * 16_666_667
        frame = create_test_frame(width, height, timestamp)
        pool.enqueue_frame("left", frame)
    time.sleep(0.5)
    results_queue.clear()

    # Benchmark
    print(f"Processing {num_frames} frames and measuring latency...")
    start_ns = int(time.time() * 1e9)

    for i in range(num_frames):
        timestamp = start_ns + i * 16_666_667
        frame = create_test_frame(width, height, timestamp)
        pool.enqueue_frame("left", frame)

        # Throttle input to not overwhelm queue
        if i % 100 == 0:
            time.sleep(0.05)

    # Wait for all processing to complete
    time.sleep(2.0)

    # Stop pool
    pool.stop()

    # Collect results
    latencies_ms = list(results_queue)

    if not latencies_ms:
        print("❌ ERROR: No latency measurements collected")
        return {}

    # Calculate statistics
    stats = calculate_percentiles(latencies_ms)

    results = {
        "frames_measured": len(latencies_ms),
        "resolution": f"{width}x{height}",
        **stats,
    }

    # Print results
    print(f"\n{'='*60}")
    print(f"Results:")
    print(f"{'='*60}")
    print(f"  Frames Measured: {len(latencies_ms)}")
    print(f"  Resolution: {width}x{height}")
    print(f"\n  Latency Statistics (milliseconds):")
    print(f"    Min:  {stats['min']:>8.2f} ms")
    print(f"    P50:  {stats['p50']:>8.2f} ms (median)")
    print(f"    P75:  {stats['p75']:>8.2f} ms")
    print(f"    P90:  {stats['p90']:>8.2f} ms")
    print(f"    P95:  {stats['p95']:>8.2f} ms")
    print(f"    P99:  {stats['p99']:>8.2f} ms")
    print(f"    Max:  {stats['max']:>8.2f} ms")
    print(f"    Mean: {stats['mean']:>8.2f} ms")
    print(f"\n  Target: <20ms p95 latency")
    print(f"  Status: {'✅ PASS' if stats['p95'] < 20 else '⚠️ ABOVE TARGET'}")
    print(f"{'='*60}\n")

    return results


def benchmark_latency_under_load(
    num_frames: int = 500, width: int = 1280, height: int = 720
) -> dict:
    """Benchmark latency under sustained high load."""
    print(f"\n{'='*60}")
    print(f"Latency Under Load Benchmark")
    print(f"{'='*60}")
    print(f"Testing latency stability under continuous high throughput")
    print(f"{'='*60}\n")

    # Create detector
    filter_config = FilterConfig()
    detector_config = DetectorConfig(filters=filter_config)
    detector = ClassicalDetector(detector_config)

    # Track latencies
    latencies_ms = []

    def detect_with_timing(label: str, frame: Frame):
        start_time = time.perf_counter()
        detections = detector.detect(frame)
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        latencies_ms.append(latency_ms)
        return detections

    # Create detection pool
    pool = DetectionThreadPool()
    pool.set_detect_callback(detect_with_timing)
    pool.start(queue_size=6)

    # Send frames as fast as possible (no throttling)
    print(f"Flooding pipeline with {num_frames} frames...")
    start_ns = int(time.time() * 1e9)

    for i in range(num_frames):
        timestamp = start_ns + i * 16_666_667
        frame = create_test_frame(width, height, timestamp)
        pool.enqueue_frame("left", frame)

    # Wait for processing
    time.sleep(3.0)

    # Stop pool
    pool.stop()

    # Calculate statistics
    stats = calculate_percentiles(latencies_ms)

    # Print results
    print(f"\n{'='*60}")
    print(f"Results (Under Load):")
    print(f"{'='*60}")
    print(f"  Frames Measured: {len(latencies_ms)}")
    print(f"\n  Latency Statistics:")
    print(f"    P50:  {stats['p50']:>8.2f} ms")
    print(f"    P95:  {stats['p95']:>8.2f} ms")
    print(f"    P99:  {stats['p99']:>8.2f} ms")
    print(f"    Max:  {stats['max']:>8.2f} ms")
    print(f"\n  Max latency under load should be reasonable")
    print(f"  Status: {'✅ GOOD' if stats['max'] < 100 else '⚠️ HIGH LATENCY SPIKES'}")
    print(f"{'='*60}\n")

    return stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Detection latency benchmark")
    parser.add_argument(
        "--frames",
        type=int,
        default=1000,
        help="Number of frames to process (default: 1000)",
    )
    parser.add_argument(
        "--width", type=int, default=1280, help="Frame width (default: 1280)"
    )
    parser.add_argument(
        "--height", type=int, default=720, help="Frame height (default: 720)"
    )
    parser.add_argument(
        "--under-load",
        action="store_true",
        help="Test latency under high load",
    )

    args = parser.parse_args()

    # Run normal latency benchmark
    benchmark_detection_latency(
        num_frames=args.frames, width=args.width, height=args.height
    )

    # Optionally run under-load test
    if args.under_load:
        benchmark_latency_under_load(
            num_frames=args.frames // 2, width=args.width, height=args.height
        )
