from __future__ import annotations

from app.services.recording.worker import BoundedRecordingWorker
import threading


def test_recording_worker_drains_and_reports_writes() -> None:
    written = []
    worker = BoundedRecordingWorker(written.append, max_queue=4)
    worker.start()
    assert worker.submit(("left", 1)) is True
    assert worker.stop(drain=True) is True
    assert written == [("left", 1)]
    stats = worker.stats()
    assert stats.written == 1
    assert stats.failed == 0


def test_recording_worker_does_not_accept_work_across_stalled_generation() -> None:
    entered = threading.Event()
    release = threading.Event()

    def handler(_item) -> None:
        entered.set()
        release.wait(1.0)

    worker = BoundedRecordingWorker(handler, max_queue=1)
    assert worker.submit("before-start") is False
    assert worker.start() is True
    assert worker.submit("first") is True
    assert entered.wait(0.5)
    assert worker.stop(timeout=0.01) is False
    assert worker.start() is False
    assert worker.submit("stale") is False
    release.set()
    assert worker.stop(timeout=1.0) is True
    assert worker.start() is True
    assert worker.submit("fresh") is True
    assert worker.stop(timeout=1.0) is True
