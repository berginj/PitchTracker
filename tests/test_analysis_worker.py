from __future__ import annotations

from app.services.analysis.worker import BoundedAnalysisWorker
import threading


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
