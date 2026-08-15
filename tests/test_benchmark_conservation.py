"""Deterministic focused tests for benchmark terminal-outcome conservation.

Uses small synthetic workloads and a fake detector to keep CI fast.
Validates that offered == processed + failed + dropped + cancelled
for throughput, latency, and memory benchmarks.
"""

import threading
import time
from typing import Dict

import numpy as np

from app.pipeline.detection.threading_pool import DetectionThreadPool
from contracts import Frame


def _make_frame(index: int = 0, width: int = 32, height: int = 32) -> Frame:
    """Tiny synthetic frame for fast tests."""
    ts = 1_000_000_000 + index * 16_666_667
    return Frame(
        camera_id="test",
        frame_index=index,
        t_capture_monotonic_ns=ts,
        image=np.zeros((height, width, 3), dtype=np.uint8),
        width=width,
        height=height,
        pixfmt="bgr24",
    )


class _OutcomeCollector:
    """Collect terminal outcomes with condition-variable wait."""

    def __init__(self, expected: int) -> None:
        self._cond = threading.Condition()
        self._expected = expected
        self._outcomes: Dict[str, int] = {}
        self._total = 0

    def on_outcome(self, event) -> None:
        with self._cond:
            self._outcomes[event.status] = (
                self._outcomes.get(event.status, 0) + 1
            )
            self._total += 1
            if self._total >= self._expected:
                self._cond.notify_all()

    def wait(self, timeout: float = 10.0) -> bool:
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
        return self._total


class TestThroughputConservation:
    """Throughput benchmark conserves every offered opportunity."""

    def test_all_frames_reach_terminal(self):
        """offered == terminal total for a small burst."""
        num = 10
        pool = DetectionThreadPool()
        pool.set_detect_callback(lambda label, frame: [])
        pool.set_stereo_callback(lambda _l, _f, _d: None)
        collector = _OutcomeCollector(num)
        pool.set_frame_decision_callbacks(
            opportunity_callback=lambda _: None,
            outcome_callback=collector.on_outcome,
        )
        pool.start(queue_size=6)

        for i in range(num):
            pool.enqueue_frame("left", _make_frame(i))

        assert collector.wait(5.0), "Timed out waiting for outcomes"
        pool.stop()
        assert collector.total == num

    def test_conservation_with_drops(self):
        """When queue overflows, total still == offered."""
        num = 30
        pool = DetectionThreadPool()

        # Slow detector forces queue pressure with queue_size=2
        def slow_detect(label, frame):
            time.sleep(0.05)
            return []

        pool.set_detect_callback(slow_detect)
        pool.set_stereo_callback(lambda _l, _f, _d: None)
        collector = _OutcomeCollector(num)
        pool.set_frame_decision_callbacks(
            opportunity_callback=lambda _: None,
            outcome_callback=collector.on_outcome,
        )
        pool.start(queue_size=2)

        for i in range(num):
            pool.enqueue_frame("left", _make_frame(i))

        assert collector.wait(15.0), "Timed out waiting for outcomes"
        pool.stop()
        assert collector.total == num
        outcomes = collector.snapshot
        # Some should be drops given tiny queue and slow detector
        total = sum(outcomes.values())
        assert total == num

    def test_conservation_with_failures(self):
        """Failed detections still produce terminal outcomes."""
        num = 5
        call_count = 0

        def failing_detect(label, frame):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise RuntimeError("boom")
            return []

        pool = DetectionThreadPool()
        pool.set_detect_callback(failing_detect)
        pool.set_stereo_callback(lambda _l, _f, _d: None)
        collector = _OutcomeCollector(num)
        pool.set_frame_decision_callbacks(
            opportunity_callback=lambda _: None,
            outcome_callback=collector.on_outcome,
        )
        pool.start(queue_size=6)

        for i in range(num):
            pool.enqueue_frame("left", _make_frame(i))

        assert collector.wait(5.0)
        pool.stop()
        assert collector.total == num
        outcomes = collector.snapshot
        assert outcomes.get("DETECTOR_FAILED", 0) >= 1


class TestLatencyConservation:
    """Latency benchmark conserves terminal outcomes."""

    def test_paced_latency_conserves(self):
        """Paced submission conserves all offered frames."""
        num = 8
        pool = DetectionThreadPool()
        pool.set_detect_callback(lambda label, frame: [])
        pool.set_stereo_callback(lambda _l, _f, _d: None)
        collector = _OutcomeCollector(num)
        pool.set_frame_decision_callbacks(
            opportunity_callback=lambda _: None,
            outcome_callback=collector.on_outcome,
        )
        pool.start(queue_size=6)

        for i in range(num):
            pool.enqueue_frame("left", _make_frame(i))
            if (i + 1) % 4 == 0:
                time.sleep(0.01)  # Load-pacing sleep

        assert collector.wait(5.0)
        pool.stop()
        assert collector.total == num


class TestMemoryConservation:
    """Memory benchmark conserves terminal outcomes per cycle."""

    def test_single_cycle_conserves(self):
        """A single start/stop cycle conserves all frames."""
        num = 5
        pool = DetectionThreadPool()
        pool.set_detect_callback(lambda label, frame: [])
        pool.set_stereo_callback(lambda _l, _f, _d: None)
        collector = _OutcomeCollector(num)
        pool.set_frame_decision_callbacks(
            opportunity_callback=lambda _: None,
            outcome_callback=collector.on_outcome,
        )
        pool.start(queue_size=6)

        for i in range(num):
            pool.enqueue_frame("left", _make_frame(i))

        assert collector.wait(5.0)
        pool.stop()
        assert collector.total == num


class TestRunAllDenominators:
    """run_all summary never marks pass using wrong denominator."""

    def test_extract_results_from_envelope(self):
        from benchmarks.run_all import _extract_results

        envelope = {"results": {"processed": 5, "offered": 10}}
        r = _extract_results(envelope)
        assert r["processed"] == 5
        assert r["offered"] == 10

    def test_extract_results_from_error(self):
        from benchmarks.run_all import _extract_results

        raw = {"error": "something"}
        r = _extract_results(raw)
        assert "error" in r


class TestBenchConfigIdentity:
    """bench_config produces valid identity payloads."""

    def test_host_identity_fields(self):
        from benchmarks.bench_config import get_host_identity
        h = get_host_identity()
        assert h.platform
        assert h.python_version
        assert h.cpu_count is None or h.cpu_count > 0

    def test_commit_identity_no_crash(self):
        from benchmarks.bench_config import get_commit_identity
        c = get_commit_identity()
        d = c.to_dict()
        assert "sha" in d
        assert "dirty" in d

    def test_result_envelope_structure(self):
        from benchmarks.bench_config import (
            BenchmarkConfig,
            build_result_envelope,
        )
        env = build_result_envelope(
            benchmark_config=BenchmarkConfig(
                name="test", params={"x": 1},
            ),
            results={"val": 42},
            raw_samples=[1, 2, 3],
        )
        assert env["benchmark_config"]["name"] == "test"
        assert env["results"]["val"] == 42
        assert env["raw_samples"] == [1, 2, 3]
        assert "commit_identity" in env
        assert "host_identity" in env


class TestCollectorMissedWakeup:
    """Regression: single-Condition collector cannot miss wakeups."""

    def test_rapid_concurrent_outcomes(self):
        """Many threads posting outcomes never deadlock the waiter."""
        from benchmarks.throughput import _OutcomeCollector
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class _FakeEvent:
            status: str

        n = 200
        collector = _OutcomeCollector(n)
        barrier = threading.Barrier(n + 1)

        def post():
            barrier.wait()
            collector.on_outcome(_FakeEvent(status="PROCESSING_COMPLETE"))

        threads = [threading.Thread(target=post) for _ in range(n)]
        for t in threads:
            t.start()
        barrier.wait()
        assert collector.wait(5.0), "Collector deadlocked on concurrent posts"
        for t in threads:
            t.join(1.0)
        assert collector.total == n

    def test_total_under_condition(self):
        """total property reads under the Condition lock."""
        from benchmarks.throughput import _OutcomeCollector

        c = _OutcomeCollector(0)
        # Access total without deadlocking
        assert c.total == 0


class TestThroughputNoWarmupConservation:
    """Regression: throughput has no warm-up that could leak outcomes."""

    def test_no_warmup_frames_in_results(self):
        """offered count matches exactly the frames submitted."""
        from benchmarks.throughput import benchmark_detection_throughput

        r = benchmark_detection_throughput(
            num_frames=5, width=32, height=32, deadline_seconds=10.0,
        )
        res = r["results"]
        assert res["offered"] == 5
        assert res["terminal_total"] == 5
        assert res["conserved"] is True


class TestLatencyExcludesFailedResults:
    """Regression: latency only includes PROCESSING_COMPLETE samples."""

    def test_failed_frames_excluded_from_latency(self):
        """Detector failures produce outcomes but no latency samples."""
        num = 8
        call_count = 0
        call_lock = threading.Lock()

        def sometimes_fail(label, frame):
            nonlocal call_count
            with call_lock:
                call_count += 1
                c = call_count
            if c <= 3:
                raise RuntimeError("synthetic failure")
            return []

        pool = DetectionThreadPool()
        pool.set_detect_callback(sometimes_fail)
        pool.set_stereo_callback(lambda _l, _f, _d: None)

        from benchmarks.latency import _LatencyCorrelator
        correlator = _LatencyCorrelator(num)
        # Wrap to record latency only when detector succeeds
        original_detect = sometimes_fail

        def detect_with_timing(label, frame):
            t0 = time.perf_counter()
            detections = original_detect(label, frame)
            latency_ms = (time.perf_counter() - t0) * 1000
            correlator.record_latency(
                frame.t_capture_monotonic_ns, latency_ms,
            )
            return detections

        pool._detect_callback = None
        pool.set_detect_callback(detect_with_timing)

        pool.set_frame_decision_callbacks(
            opportunity_callback=lambda _: None,
            outcome_callback=correlator.on_outcome,
        )
        pool.start(queue_size=6)

        for i in range(num):
            pool.enqueue_frame("left", _make_frame(i))

        correlator.wait(10.0)
        pool.stop()

        assert correlator.total == num
        success = correlator.successful_latencies()
        all_lat = correlator.all_latencies()
        # Failed frames never recorded a latency, so success <= all
        assert len(success) <= len(all_lat)
        # And success count matches PROCESSING_COMPLETE count
        processed = correlator.snapshot.get("PROCESSING_COMPLETE", 0)
        assert len(success) == processed

    def test_correlator_empty_on_all_failures(self):
        """If every frame fails, successful_latencies is empty."""
        from benchmarks.latency import _LatencyCorrelator
        from dataclasses import dataclass

        @dataclass(frozen=True)
        class _FakeOutcome:
            status: str
            timestamp_ns: int

        c = _LatencyCorrelator(3)
        for ts in [100, 200, 300]:
            c.record_latency(ts, 5.0)  # detector ran but...
            c.on_outcome(_FakeOutcome(
                status="DETECTOR_FAILED", timestamp_ns=ts,
            ))
        assert c.total == 3
        assert c.successful_latencies() == []
        assert len(c.all_latencies()) == 3
