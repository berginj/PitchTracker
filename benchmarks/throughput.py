"""Frame processing throughput benchmark with terminal-outcome conservation.

Every offered frame is tracked to exactly one terminal outcome:
  processed, failed, dropped (input or result queue), or cancelled.
Completion is determined by waiting for all terminal outcomes via a
condition variable with a configurable deadline — not a fixed sleep.

``offered == processed + failed + dropped + cancelled``

Throughput FPS is ``processed / elapsed`` (not ``offered / elapsed``).
"""

import threading
import time
from typing import Any, Dict, List

import numpy as np

from app.pipeline.detection.threading_pool import DetectionThreadPool
from benchmarks.bench_config import BenchmarkConfig, build_result_envelope
from contracts import Frame
from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig, FilterConfig

_TERMINAL_STATUSES = frozenset({
    "PROCESSING_COMPLETE",
    "INPUT_QUEUE_DROPPED",
    "RESULT_QUEUE_DROPPED",
    "DETECTOR_FAILED",
    "RESULT_PROCESSING_FAILED",
    "CANCELLED_ON_STOP",
})


def create_test_frame(
    width: int, height: int, timestamp_ns: int,
    camera_id: str = "bench", frame_index: int = 0,
) -> Frame:
    """Create a synthetic frame with random pixel data."""
    image = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    return Frame(
        camera_id=camera_id,
        frame_index=frame_index,
        t_capture_monotonic_ns=timestamp_ns,
        image=image,
        width=width,
        height=height,
        pixfmt="bgr24",
    )


class _OutcomeCollector:
    """Thread-safe collector using a single Condition for all state.

    Mutation, threshold check, and wait all use the same Condition
    to eliminate missed-wakeup races.
    """

    def __init__(self, expected: int) -> None:
        self._cond = threading.Condition()
        self._expected = expected
        self._outcomes: Dict[str, int] = {}
        self._total = 0

    def on_outcome(self, event) -> None:
        with self._cond:
            status = event.status
            self._outcomes[status] = self._outcomes.get(status, 0) + 1
            self._total += 1
            if self._total >= self._expected:
                self._cond.notify_all()

    def wait(self, timeout: float) -> bool:
        """Wait until all expected outcomes arrive or timeout."""
        deadline = time.monotonic() + timeout
        with self._cond:
            while self._total < self._expected:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._cond.wait(timeout=remaining)
        return True

    @property
    def snapshot(self) -> Dict[str, int]:
        with self._cond:
            return dict(self._outcomes)

    @property
    def total(self) -> int:
        with self._cond:
            return self._total


def benchmark_detection_throughput(
    num_frames: int = 100,
    width: int = 1280,
    height: int = 720,
    queue_size: int = 6,
    deadline_seconds: float = 30.0,
) -> Dict[str, Any]:
    """Benchmark detection throughput with terminal-outcome conservation.

    Returns a result envelope with config, identity, and raw samples.
    Throughput FPS uses processed count as the numerator, not offered.
    """
    config = BenchmarkConfig(
        name="throughput",
        params={
            "num_frames": num_frames,
            "width": width,
            "height": height,
            "queue_size": queue_size,
            "deadline_seconds": deadline_seconds,
        },
    )

    detector = ClassicalDetector(DetectorConfig(filters=FilterConfig()))
    pool = DetectionThreadPool()
    pool.set_detect_callback(lambda label, frame: detector.detect(frame))
    pool.set_stereo_callback(lambda label, frame, dets: None)

    collector = _OutcomeCollector(num_frames)
    pool.set_frame_decision_callbacks(
        opportunity_callback=lambda _: None,
        outcome_callback=collector.on_outcome,
    )
    pool.start(queue_size=queue_size)

    # No warm-up phase: the classical detector is stateless and any
    # JIT/allocation warm-up is part of the real measurement.  A warm-up
    # that does not await its own terminal conservation is invalid.

    start_ns = time.perf_counter_ns()
    base_ts = int(time.time() * 1e9)
    for i in range(num_frames):
        ts = base_ts + i * 16_666_667
        pool.enqueue_frame("left", create_test_frame(width, height, ts))

    # Wait for terminal conservation — no fixed sleep as completion
    conserved = collector.wait(deadline_seconds)
    elapsed_ns = time.perf_counter_ns() - start_ns
    pool.stop()

    outcomes = collector.snapshot
    offered = num_frames
    processed = outcomes.get("PROCESSING_COMPLETE", 0)
    failed = outcomes.get("DETECTOR_FAILED", 0)
    dropped = (
        outcomes.get("INPUT_QUEUE_DROPPED", 0)
        + outcomes.get("RESULT_QUEUE_DROPPED", 0)
    )
    cancelled = outcomes.get("CANCELLED_ON_STOP", 0)
    other = collector.total - processed - failed - dropped - cancelled
    elapsed_s = elapsed_ns / 1e9
    processed_fps = processed / elapsed_s if elapsed_s > 0 else 0.0

    results = {
        "offered": offered,
        "processed": processed,
        "failed": failed,
        "dropped": dropped,
        "cancelled": cancelled,
        "other": other,
        "terminal_total": collector.total,
        "conserved": offered == collector.total,
        "conserved_within_deadline": conserved,
        "elapsed_seconds": elapsed_s,
        "processed_fps": processed_fps,
        "resolution": f"{width}x{height}",
        "terminal_outcomes": outcomes,
    }

    return build_result_envelope(
        benchmark_config=config, results=results,
    )


def benchmark_multiple_resolutions(
    num_frames: int = 50,
) -> List[Dict[str, Any]]:
    """Run throughput at multiple resolutions."""
    resolutions = [
        (640, 480, "VGA"),
        (1280, 720, "HD 720p"),
        (1920, 1080, "Full HD 1080p"),
    ]
    results = []
    for w, h, name in resolutions:
        r = benchmark_detection_throughput(num_frames=num_frames, width=w, height=h)
        r["results"]["resolution_name"] = name
        results.append(r)
    return results


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Throughput benchmark")
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--all-resolutions", action="store_true")
    args = parser.parse_args()

    out: object
    if args.all_resolutions:
        out = benchmark_multiple_resolutions(num_frames=args.frames)
    else:
        out = benchmark_detection_throughput(
            num_frames=args.frames, width=args.width, height=args.height,
        )
    print(json.dumps(out, indent=2))
