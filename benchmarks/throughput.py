"""Frame processing throughput benchmark.

Measures frames per second (FPS) through the detection pipeline.
Target: 60 FPS minimum for real-time processing.
"""

import time
import numpy as np
from typing import List, Tuple

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


def benchmark_detection_throughput(
    num_frames: int = 1000,
    width: int = 1280,
    height: int = 720,
    queue_size: int = 6,
) -> dict:
    """Benchmark detection pipeline throughput.

    Args:
        num_frames: Number of frames to process
        width: Frame width in pixels
        height: Frame height in pixels
        queue_size: Detection queue size

    Returns:
        Dictionary with benchmark results
    """
    print(f"\n{'='*60}")
    print(f"Frame Processing Throughput Benchmark")
    print(f"{'='*60}")
    print(f"Configuration:")
    print(f"  Frames: {num_frames}")
    print(f"  Resolution: {width}x{height}")
    print(f"  Queue Size: {queue_size}")
    print(f"{'='*60}\n")

    # Create detector
    filter_config = FilterConfig()
    detector_config = DetectorConfig(filters=filter_config)
    detector = ClassicalDetector(detector_config)

    # Create detection pool
    pool = DetectionThreadPool()
    pool.set_detect_callback(lambda label, frame: detector.detect(frame))
    pool.start(queue_size=queue_size)

    # Generate test frames
    print("Generating test frames...")
    frames = []
    start_ns = int(time.time() * 1e9)
    for i in range(num_frames):
        timestamp = start_ns + i * 16_666_667  # ~60 FPS spacing
        frames.append(create_test_frame(width, height, timestamp))

    # Warm-up (process first 10 frames)
    print("Warming up pipeline...")
    for frame in frames[:10]:
        pool.enqueue_frame("left", frame)
    time.sleep(0.5)

    # Benchmark
    print(f"Processing {num_frames} frames...")
    benchmark_start = time.perf_counter()

    for frame in frames:
        pool.enqueue_frame("left", frame)

    # Wait for processing to complete
    time.sleep(1.0)

    benchmark_end = time.perf_counter()
    elapsed = benchmark_end - benchmark_start

    # Stop pool
    pool.stop()

    # Calculate metrics
    fps = num_frames / elapsed
    frame_time_ms = (elapsed / num_frames) * 1000

    results = {
        "frames_processed": num_frames,
        "elapsed_seconds": elapsed,
        "fps": fps,
        "frame_time_ms": frame_time_ms,
        "resolution": f"{width}x{height}",
        "queue_size": queue_size,
    }

    # Print results
    print(f"\n{'='*60}")
    print(f"Results:")
    print(f"{'='*60}")
    print(f"  Frames Processed: {num_frames}")
    print(f"  Total Time: {elapsed:.2f} seconds")
    print(f"  Throughput: {fps:.2f} FPS")
    print(f"  Frame Time: {frame_time_ms:.2f} ms/frame")
    print(f"  Target: 60 FPS minimum")
    print(f"  Status: {'✅ PASS' if fps >= 60 else '❌ BELOW TARGET'}")
    print(f"{'='*60}\n")

    return results


def benchmark_multiple_resolutions() -> List[dict]:
    """Benchmark throughput at different resolutions."""
    resolutions = [
        (640, 480, "VGA"),
        (1280, 720, "HD 720p"),
        (1920, 1080, "Full HD 1080p"),
    ]

    results = []
    for width, height, name in resolutions:
        print(f"\n{'#'*60}")
        print(f"# Resolution: {name} ({width}x{height})")
        print(f"{'#'*60}")

        result = benchmark_detection_throughput(
            num_frames=500,  # Fewer frames for higher resolutions
            width=width,
            height=height,
        )
        result["resolution_name"] = name
        results.append(result)

        time.sleep(1.0)  # Cool down between tests

    return results


def print_summary(results: List[dict]) -> None:
    """Print summary table of all results."""
    print(f"\n{'='*60}")
    print(f"Throughput Benchmark Summary")
    print(f"{'='*60}")
    print(f"{'Resolution':<15} {'FPS':>10} {'ms/frame':>12} {'Status':>15}")
    print(f"{'-'*60}")

    for result in results:
        resolution = result.get("resolution_name", result["resolution"])
        fps = result["fps"]
        frame_time = result["frame_time_ms"]
        status = "✅ PASS" if fps >= 60 else "⚠️ BELOW TARGET"

        print(f"{resolution:<15} {fps:>10.2f} {frame_time:>12.2f} {status:>15}")

    print(f"{'='*60}\n")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Frame processing throughput benchmark")
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
        "--all-resolutions",
        action="store_true",
        help="Run benchmark at multiple resolutions",
    )

    args = parser.parse_args()

    if args.all_resolutions:
        results = benchmark_multiple_resolutions()
        print_summary(results)
    else:
        benchmark_detection_throughput(
            num_frames=args.frames, width=args.width, height=args.height
        )
