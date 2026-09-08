from __future__ import annotations

from app.services.analysis.worker import BoundedAnalysisWorker
import threading
import time


def test_analysis_worker_processes_and_reports_items() -> None:
    processed = []
    worker = BoundedAnalysisWorker(processed.append, max_queue=2)
    worker.start()
    assert worker.submit("pitch-1") is True
    worker.stop(drain=True)
    assert processed == ["pitch-1"]
    assert worker.stats().completed == 1


def test_analysis_worker_stop_is_bounded_when_handler_stalls() -> None:
    entered = threading.Event()
    release = threading.Event()

    def handler(_item) -> None:
        entered.set()
        release.wait(1.0)

    worker = BoundedAnalysisWorker(handler, max_queue=1)
    worker.start()
    worker.submit("pitch")
    assert entered.wait(0.5)
    assert worker.stop(drain=True, timeout=0.01) is False
    existing = worker._thread
    assert worker.start() is False
    assert worker._thread is existing
    assert worker.submit("stale") is False
    release.set()
    assert worker.stop(drain=True, timeout=1.0) is True
    assert worker.start() is True
    assert worker.submit("fresh") is True
    assert worker.stop(drain=True, timeout=1.0) is True


def test_analysis_worker_rejects_submission_outside_live_generation() -> None:
    worker = BoundedAnalysisWorker(lambda _item: None, max_queue=1)
    assert worker.submit("before-start") is False
    assert worker.start() is True
    assert worker.stop() is True
    assert worker.submit("after-stop") is False


def test_analysis_worker_reports_queue_age_and_service_latency() -> None:
    entered, release = threading.Event(), threading.Event()

    def handler(_item):
        entered.set()
        assert release.wait(2.0)

    worker = BoundedAnalysisWorker(handler, max_queue=2)
    assert worker.start()
    try:
        assert worker.submit("first")
        assert entered.wait(1.0)
        assert worker.submit("second")
        time.sleep(0.02)
        stats = worker.stats()
        assert stats.queue_depth == 1
        assert stats.oldest_queued_age_ms >= 10.0
    finally:
        release.set()
        assert worker.stop(timeout=2.0)
    stats = worker.stats()
    assert stats.queue_depth == 0
    assert stats.oldest_queued_age_ms == 0.0
    assert stats.latency_sample_count == 2
    assert stats.service_latency_p95_ms >= 10.0
    assert stats.last_queue_wait_ms >= 10.0
