"""Detection shutdown retains blocked callbacks and fences restart generations."""

from __future__ import annotations

import threading
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest

from app.events.event_bus import EventBus
from app.pipeline.detection.threading_pool import DetectionThreadPool
from app.services.detection.implementation import DetectionServiceImpl
from configs.settings import load_config
from contracts import Frame
from exceptions import DetectionError


def _frame():
    return Frame("fake", 1, 1, np.ones((2, 2), dtype=np.uint8), 2, 2, "GRAY8")


@pytest.mark.parametrize("mode", ["per_camera", "worker_pool"])
def test_blocked_detector_retains_threads_until_retry_and_cannot_revive_old_generation(mode):
    pool = DetectionThreadPool(mode=mode)
    entered = threading.Event()
    release = threading.Event()
    outcomes = []

    def detect(label, frame):
        entered.set()
        assert release.wait(2.0)
        return []

    pool.set_detect_callback(detect)
    pool.set_stereo_callback(lambda *args: None)
    pool.set_frame_decision_callbacks(lambda event: None, outcomes.append)
    pool.start()
    pool.enqueue_frame("left", _frame())
    assert entered.wait(0.5)
    owned = pool._owned_threads()
    epoch = pool._run_epoch
    try:
        with pytest.raises(DetectionError, match="still stopping"):
            pool.stop(timeout=0.01)
        assert any(thread.is_alive() for thread in pool._owned_threads())
        with pytest.raises(DetectionError, match="still stopping"):
            pool.start()
        assert pool._run_epoch == epoch
        assert len(outcomes) == 1
        assert outcomes[0].status == "CANCELLED_ON_STOP"
    finally:
        release.set()
        for thread in owned:
            thread.join(0.5)
        pool.stop()
    assert not pool._owned_threads()
    assert len(outcomes) == 1
    pool.set_detect_callback(lambda *args: [])
    pool.start()
    pool.stop()
    assert pool._run_epoch == epoch + 1


def test_service_stop_releases_callback_lock_and_retries_while_not_running():
    config = load_config(Path(__file__).resolve().parents[1] / "configs/default.yaml")
    service = DetectionServiceImpl(EventBus(), config)
    pool = Mock()
    processor = Mock()
    service._thread_pool = pool
    service._processor = processor
    service._running = True
    exited = threading.Event()

    def stop():
        def callback():
            with service._lock:
                exited.set()
        thread = threading.Thread(target=callback)
        thread.start()
        assert exited.wait(0.5)
        thread.join()
        raise DetectionError("injected worker still stopping")

    pool.stop.side_effect = stop
    with pytest.raises(DetectionError, match="injected"):
        service.stop_detection()
    assert not service._running
    assert service._stopping
    processor.flush_pairing_buffers.assert_not_called()
    with pytest.raises(DetectionError, match="still stopping"):
        service.start_detection()
    assert service._processor is processor
    pool.stop.side_effect = None
    service.stop_detection()
    assert pool.stop.call_count == 2
    assert not service._stopping
    processor.flush_pairing_buffers.assert_called_once()
