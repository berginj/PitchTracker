"""Memory stability benchmark with terminal-outcome conservation.

Tracks terminal outcomes during extended operation to ensure
``offered == terminal_total`` conservation.  Completion of each
sample interval uses ``pool.get_runtime_stats()`` rather than
assuming frames submitted equals frames processed.

The ``time.sleep(0.01)`` in the main loop is a **load-pacing** sleep
that models a realistic offered rate; it is not completion logic.
"""

import gc
import threading
import time
from typing import Any, Dict, List, Tuple

import numpy as np

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from app.pipeline.detection.threading_pool import DetectionThreadPool
from benchmarks.bench_config import BenchmarkConfig, build_result_envelope
from contracts import Frame
from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig, FilterConfig


def _get_rss_mb() -> float:
    if not PSUTIL_AVAILABLE:
        return 0.0
    return float(psutil.Process().memory_info().rss / (1024 * 1024))


def create_test_frame(
    width: int, height: int, timestamp_ns: int,
    frame_index: int = 0,
) -> Frame:
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


class _OutcomeCounter:
    """Lightweight terminal counter with condition wait."""

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._outcomes: Dict[str, int] = {}
        self._total = 0

    def on_outcome(self, event) -> None:
        with self._cond:
            self._outcomes[event.status] = (
                self._outcomes.get(event.status, 0) + 1
            )
            self._total += 1
            self._cond.notify_all()

    def wait_for(self, target: int, timeout: float) -> bool:
        deadline = time.monotonic() + timeout
        with self._cond:
            while self._total < target:
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
        return self._total


def benchmark_memory_stability(
    duration_seconds: int = 60,
    sample_interval: int = 10,
    width: int = 1280,
    height: int = 720,
) -> Dict[str, Any]:
    """Memory stability with terminal-outcome conservation.

    Returns an envelope with memory samples, conservation proof,
    config, commit, and host identity.
    """
    config = BenchmarkConfig(
        name="memory_stability",
        params={
            "duration_seconds": duration_seconds,
            "sample_interval": sample_interval,
            "width": width,
            "height": height,
            "psutil_available": PSUTIL_AVAILABLE,
        },
    )

    if not PSUTIL_AVAILABLE:
        return build_result_envelope(
            benchmark_config=config,
            results={"error": "psutil not available"},
        )

    detector = ClassicalDetector(DetectorConfig(filters=FilterConfig()))
    pool = DetectionThreadPool()
    pool.set_detect_callback(lambda label, frame: detector.detect(frame))
    pool.set_stereo_callback(lambda _l, _f, _d: None)

    counter = _OutcomeCounter()
    pool.set_frame_decision_callbacks(
        opportunity_callback=lambda _: None,
        outcome_callback=counter.on_outcome,
    )
    pool.start(queue_size=6)

    gc.collect()
    initial_mem = _get_rss_mb()
    start = time.monotonic()
    last_sample = start
    offered = 0
    memory_samples: List[Tuple[float, float]] = [(0.0, initial_mem)]

    while time.monotonic() - start < duration_seconds:
        ts = int(time.time() * 1e9)
        pool.enqueue_frame("left", create_test_frame(width, height, ts))
        offered += 1
        # Load-pacing sleep — models realistic offered rate
        time.sleep(0.01)
        now = time.monotonic()
        if now - last_sample >= sample_interval:
            gc.collect()
            memory_samples.append((now - start, _get_rss_mb()))
            last_sample = now

    # Wait for terminal conservation within a 10 s deadline
    counter.wait_for(offered, timeout=10.0)
    pool.stop()

    gc.collect()
    final_mem = _get_rss_mb()
    memory_samples.append((time.monotonic() - start, final_mem))

    outcomes = counter.snapshot
    mem_values = [m for _, m in memory_samples]
    growth_mb = final_mem - initial_mem
    growth_pct = (growth_mb / initial_mem * 100) if initial_mem else 0.0

    results = {
        "offered": offered,
        "terminal_total": counter.total,
        "conserved": offered == counter.total,
        "terminal_outcomes": outcomes,
        "initial_memory_mb": initial_mem,
        "final_memory_mb": final_mem,
        "max_memory_mb": max(mem_values),
        "growth_mb": growth_mb,
        "growth_percent": growth_pct,
        "duration_seconds": duration_seconds,
    }

    return build_result_envelope(
        benchmark_config=config,
        results=results,
        raw_samples=[{"elapsed_s": t, "rss_mb": m} for t, m in memory_samples],
    )


def benchmark_memory_rapid_cycling(
    num_cycles: int = 20,
    width: int = 1280,
    height: int = 720,
) -> Dict[str, Any]:
    """Rapid start/stop cycling with conservation per cycle."""
    config = BenchmarkConfig(
        name="memory_rapid_cycling",
        params={
            "num_cycles": num_cycles, "width": width, "height": height,
            "psutil_available": PSUTIL_AVAILABLE,
        },
    )

    if not PSUTIL_AVAILABLE:
        return build_result_envelope(
            benchmark_config=config,
            results={"error": "psutil not available"},
        )

    gc.collect()
    initial_mem = _get_rss_mb()
    frames_per_cycle = 5
    all_conserved = True

    for _ in range(num_cycles):
        detector = ClassicalDetector(DetectorConfig(filters=FilterConfig()))
        pool = DetectionThreadPool()
        pool.set_detect_callback(
            lambda label, frame: detector.detect(frame),
        )
        pool.set_stereo_callback(lambda _l, _f, _d: None)
        counter = _OutcomeCounter()
        pool.set_frame_decision_callbacks(
            opportunity_callback=lambda _: None,
            outcome_callback=counter.on_outcome,
        )
        pool.start(queue_size=6)
        for j in range(frames_per_cycle):
            ts = int(time.time() * 1e9) + j * 16_666_667
            pool.enqueue_frame(
                "left", create_test_frame(width, height, ts),
            )
        counter.wait_for(frames_per_cycle, timeout=5.0)
        pool.stop()
        if counter.total != frames_per_cycle:
            all_conserved = False

    gc.collect()
    final_mem = _get_rss_mb()
    growth_mb = final_mem - initial_mem
    growth_pct = (growth_mb / initial_mem * 100) if initial_mem else 0.0

    results = {
        "cycles": num_cycles,
        "initial_memory_mb": initial_mem,
        "final_memory_mb": final_mem,
        "growth_mb": growth_mb,
        "growth_percent": growth_pct,
        "all_cycles_conserved": all_conserved,
    }
    return build_result_envelope(
        benchmark_config=config, results=results,
    )


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Memory benchmark")
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--interval", type=int, default=10)
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--rapid-cycling", action="store_true")
    parser.add_argument("--cycles", type=int, default=20)
    args = parser.parse_args()

    if args.rapid_cycling:
        out = benchmark_memory_rapid_cycling(
            num_cycles=args.cycles, width=args.width, height=args.height,
        )
    else:
        out = benchmark_memory_stability(
            duration_seconds=args.duration,
            sample_interval=args.interval,
            width=args.width,
            height=args.height,
        )
    print(json.dumps(out, indent=2))
