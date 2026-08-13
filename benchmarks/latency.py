"""Detection latency benchmark with terminal-outcome conservation.

Measures per-frame detector-call latency only for frames that reach
PROCESSING_COMPLETE.  Each detector invocation records its latency
keyed by the frame's ``t_capture_monotonic_ns``; the outcome callback
correlates terminal status so only successful processing latencies
are included in the reported distribution.

Completion is determined by a condition-variable deadline, not a
fixed sleep.

Pacing sleeps in ``benchmark_detection_latency`` intentionally model
the offered load rate so the queue is not overwhelmed.  They are
**not** completion logic and are documented as load-pacing.
"""

import threading
import time
from typing import Any, Dict, List, Optional

import numpy as np

from app.pipeline.detection.threading_pool import DetectionThreadPool
from benchmarks.bench_config import BenchmarkConfig, build_result_envelope
from contracts import Frame
from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig, FilterConfig


def create_test_frame(
    width: int, height: int, timestamp_ns: int,
    frame_index: int = 0,
) -> Frame:
    """Create a synthetic test frame."""
    image = np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
    return Frame(
        camera_id="bench",
        frame_index=frame_index,
        t_capture_monotonic_ns=timestamp_ns,
        image=image,
        width=width,
        height=height,
        pixfmt="bgr24",
    )


def _percentiles(values: List[float]) -> Dict[str, float]:
    """Compute standard percentiles from a sorted list."""
    if not values:
        return {}
    s = sorted(values)
    n = len(s)
    return {
        "min": s[0],
        "p50": s[int(n * 0.50)],
        "p75": s[int(n * 0.75)],
        "p90": s[int(n * 0.90)],
        "p95": s[int(n * 0.95)],
        "p99": s[int(n * 0.99)] if n >= 100 else s[-1],
        "max": s[-1],
        "mean": sum(s) / n,
    }


class _LatencyCorrelator:
    """Correlates detector invocation latencies with terminal outcomes.

    The detect callback stores ``(timestamp_ns, latency_ms)`` for every
    invocation.  The outcome callback records which opportunity_ids
    reached PROCESSING_COMPLETE.  After the run, only latencies whose
    ``timestamp_ns`` matches a successful outcome are included.
    """

    def __init__(self, expected: int) -> None:
        self._cond = threading.Condition()
        self._expected = expected
        self._outcomes: Dict[str, int] = {}
        self._total = 0
        # Map timestamp_ns -> latency_ms from detector callback
        self._latency_by_ts: Dict[int, float] = {}
        self._latency_lock = threading.Lock()
        # Set of timestamp_ns values confirmed PROCESSING_COMPLETE
        self._success_ts: List[int] = []

    def record_latency(self, timestamp_ns: int, latency_ms: float) -> None:
        """Called from the detector callback thread."""
        with self._latency_lock:
            self._latency_by_ts[timestamp_ns] = latency_ms

    def on_outcome(self, event) -> None:
        with self._cond:
            self._outcomes[event.status] = (
                self._outcomes.get(event.status, 0) + 1
            )
            self._total += 1
            if event.status == "PROCESSING_COMPLETE":
                self._success_ts.append(event.timestamp_ns)
            if self._total >= self._expected:
                self._cond.notify_all()

    def wait(self, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self._cond:
            while self._total < self._expected:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False
                self._cond.wait(timeout=remaining)
        return True

    def successful_latencies(self) -> List[float]:
        """Return latencies only for PROCESSING_COMPLETE outcomes."""
        with self._latency_lock:
            return [
                self._latency_by_ts[ts]
                for ts in self._success_ts
                if ts in self._latency_by_ts
            ]

    def all_latencies(self) -> List[float]:
        """Return all recorded detector invocation latencies."""
        with self._latency_lock:
            return list(self._latency_by_ts.values())

    @property
    def snapshot(self) -> Dict[str, int]:
        with self._cond:
            return dict(self._outcomes)

    @property
    def total(self) -> int:
        with self._cond:
            return self._total


def benchmark_detection_latency(
    num_frames: int = 100,
    width: int = 1280,
    height: int = 720,
    deadline_seconds: float = 30.0,
    pace_interval: Optional[float] = 0.05,
    pace_batch: int = 20,
) -> Dict[str, Any]:
    """Benchmark detection latency with terminal-outcome conservation.

    Only latencies from frames that reached PROCESSING_COMPLETE are
    included in the reported distribution.  ``pace_interval`` is a
    **load-pacing sleep**, not completion logic.
    """
    config = BenchmarkConfig(
        name="latency",
        params={
            "num_frames": num_frames,
            "width": width,
            "height": height,
            "deadline_seconds": deadline_seconds,
            "pace_interval": pace_interval,
            "pace_batch": pace_batch,
        },
    )

    detector = ClassicalDetector(DetectorConfig(filters=FilterConfig()))
    correlator = _LatencyCorrelator(num_frames)

    def detect_with_timing(label: str, frame: Frame):
        t0 = time.perf_counter()
        detections = detector.detect(frame)
        latency_ms = (time.perf_counter() - t0) * 1000
        correlator.record_latency(frame.t_capture_monotonic_ns, latency_ms)
        return detections

    pool = DetectionThreadPool()
    pool.set_detect_callback(detect_with_timing)
    pool.set_stereo_callback(lambda _l, _f, _d: None)

    pool.set_frame_decision_callbacks(
        opportunity_callback=lambda _: None,
        outcome_callback=correlator.on_outcome,
    )
    pool.start(queue_size=6)

    base_ts = int(time.time() * 1e9)
    for i in range(num_frames):
        ts = base_ts + i * 16_666_667
        pool.enqueue_frame(
            "left", create_test_frame(width, height, ts, frame_index=i),
        )
        # Load-pacing sleep — intentionally slows offered rate
        if pace_interval and (i + 1) % pace_batch == 0:
            time.sleep(pace_interval)

    conserved = correlator.wait(deadline_seconds)
    pool.stop()

    outcomes = correlator.snapshot
    processed = outcomes.get("PROCESSING_COMPLETE", 0)
    success_latencies = correlator.successful_latencies()
    stats = _percentiles(success_latencies)

    results = {
        "offered": num_frames,
        "processed": processed,
        "terminal_total": correlator.total,
        "conserved": num_frames == correlator.total,
        "conserved_within_deadline": conserved,
        "frames_measured": len(success_latencies),
        "resolution": f"{width}x{height}",
        "terminal_outcomes": outcomes,
        **stats,
    }

    return build_result_envelope(
        benchmark_config=config,
        results=results,
        raw_samples=success_latencies,
    )


def benchmark_latency_under_load(
    num_frames: int = 50,
    width: int = 1280,
    height: int = 720,
    deadline_seconds: float = 30.0,
) -> Dict[str, Any]:
    """Latency under flood load (no pacing sleep)."""
    return benchmark_detection_latency(
        num_frames=num_frames,
        width=width,
        height=height,
        deadline_seconds=deadline_seconds,
        pace_interval=None,
        pace_batch=1,
    )


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Latency benchmark")
    parser.add_argument("--frames", type=int, default=100)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--under-load", action="store_true")
    args = parser.parse_args()

    out = benchmark_detection_latency(
        num_frames=args.frames, width=args.width, height=args.height,
    )
    print(json.dumps(out, indent=2))

    if args.under_load:
        load = benchmark_latency_under_load(
            num_frames=args.frames // 2, width=args.width, height=args.height,
        )
        print(json.dumps(load, indent=2))
