"""Characterization tests for detection thread-pool collaboration boundaries."""

import threading
import time

from app.pipeline.detection.threading_pool import DetectionThreadPool
from contracts import Frame


def _frame(camera: str, index: int) -> Frame:
    return Frame(camera, index, index, None, 640, 480, "GRAY8")


def test_worker_pool_preserves_per_camera_order_and_single_inflight() -> None:
    active = 0
    max_active = 0
    lock = threading.Lock()
    completed = threading.Event()
    stereo_order: list[int] = []
    pool = DetectionThreadPool(mode="worker_pool", worker_count=4)

    def detect(_label, _frame):
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.01)
        with lock:
            active -= 1
        return []

    def stereo(_label, frame, _detections):
        stereo_order.append(frame.frame_index)
        if len(stereo_order) == 6:
            completed.set()

    pool.set_detect_callback(detect)
    pool.set_stereo_callback(stereo)
    pool.start(queue_size=6)
    for index in range(6):
        pool.enqueue_frame("left", _frame("left", index))

    assert completed.wait(timeout=3.0)
    pool.stop()
    assert max_active == 1
    assert stereo_order == list(range(6))
    assert pool.get_runtime_stats()["frame_conservation"]["balanced"] is True


def test_missing_stereo_callback_is_terminal_and_counted_as_failure() -> None:
    outcome = threading.Event()
    statuses: list[str] = []
    pool = DetectionThreadPool()
    pool.set_detect_callback(lambda _label, _frame: [])
    pool.set_frame_decision_callbacks(
        lambda _event: None,
        lambda event: (statuses.append(event.status), outcome.set()),
    )
    pool.start(queue_size=1)
    pool.enqueue_frame("left", _frame("left", 1))

    assert outcome.wait(timeout=2.0)
    pool.stop()
    assert statuses == ["RESULT_PROCESSING_FAILED"]
    stats = pool.get_runtime_stats()
    assert stats["results"]["attempts"] == 0
    assert stats["frame_conservation"]["terminal_outcomes"] == {"RESULT_PROCESSING_FAILED": 1}
