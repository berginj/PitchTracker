from __future__ import annotations

import threading

from app.services.recording.worker import BoundedRecordingWorker


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


def test_submit_control_executes_in_fifo_order() -> None:
    """Control commands execute in FIFO order relative to data items."""
    order: list[str] = []
    worker = BoundedRecordingWorker(lambda item: order.append(f"data:{item}"), max_queue=16)
    worker.start()
    worker.submit("a")
    worker.submit("b")
    worker.submit_control(lambda: order.append("ctrl:1"))
    worker.submit("c")
    worker.stop(drain=True)
    assert order == ["data:a", "data:b", "ctrl:1", "data:c"]


def test_submit_control_returns_false_when_worker_not_running() -> None:
    worker = BoundedRecordingWorker(lambda _: None, max_queue=4)
    assert worker.submit_control(lambda: None) is False


def test_start_pitch_returns_promptly_while_frame_work_is_slow() -> None:
    """Prove start_pitch (via submit_control + event.wait) does NOT block
    the publisher thread while slow frame processing is underway.

    Simulates the recording service pattern: a slow handler processes frames,
    then a control command fires, and the caller gets the result promptly —
    all while a concurrent publisher keeps submitting without blocking.
    """
    processed: list[str] = []
    gate = threading.Event()

    def slow_handler(item: str) -> None:
        if item.startswith("slow"):
            gate.wait(2.0)
        processed.append(item)

    worker = BoundedRecordingWorker(slow_handler, max_queue=32)
    worker.start()

    # Queue slow frames that will block the worker
    for i in range(3):
        worker.submit(f"slow-{i}")

    # Submit a control command (like pitch-start) that fires after slow work
    ctrl_done = threading.Event()
    ctrl_order_snapshot: list[str] = []

    def pitch_start_ctrl() -> None:
        ctrl_order_snapshot.extend(processed)
        ctrl_done.set()

    assert worker.submit_control(pitch_start_ctrl) is True

    # Meanwhile, a publisher thread keeps submitting — must NOT block
    publisher_blocked = threading.Event()

    def publisher() -> None:
        for i in range(5):
            worker.submit(f"fast-{i}")
        publisher_blocked.set()

    t = threading.Thread(target=publisher)
    t.start()
    # Publisher should complete almost instantly (not blocked by slow work)
    assert publisher_blocked.wait(0.5), "Publisher thread was blocked!"
    t.join(timeout=1.0)

    # Release the slow frames
    gate.set()

    # Control command should complete promptly after slow frames drain
    assert ctrl_done.wait(5.0), "Control command never executed"
    # Verify ordering: all 3 slow frames processed BEFORE control command
    assert ctrl_order_snapshot == ["slow-0", "slow-1", "slow-2"]

    worker.stop(drain=True, timeout=5.0)
    # All items processed
    assert len(processed) == 8  # 3 slow + 5 fast


def test_control_command_preserves_exact_preroll_ordering() -> None:
    """Simulate pre-roll: N frames, then a control command snapshots them.

    The control command must see exactly the frames submitted before it,
    in order, and none of the frames submitted after it.
    """
    pre_roll: list[int] = []
    snapshot: list[int] = []
    done = threading.Event()

    def handler(item: int) -> None:
        pre_roll.append(item)

    worker = BoundedRecordingWorker(handler, max_queue=32)
    worker.start()

    # Pre-roll frames
    for i in range(10):
        worker.submit(i)

    # Pitch-start control command
    def take_snapshot() -> None:
        snapshot.extend(pre_roll)
        done.set()

    worker.submit_control(take_snapshot)

    # Post-pitch frames (should NOT appear in snapshot)
    for i in range(100, 105):
        worker.submit(i)

    assert done.wait(5.0)
    assert snapshot == list(range(10))

    worker.stop(drain=True, timeout=5.0)
    assert pre_roll == list(range(10)) + list(range(100, 105))


def test_stop_control_preserves_frames_already_queued_for_pitch() -> None:
    """Frames before a stop control remain in the active pitch."""
    pitch_active = True
    pitch_frames: list[int] = []
    stop_snapshot: list[int] = []
    done = threading.Event()

    def handler(frame_index: int) -> None:
        if pitch_active:
            pitch_frames.append(frame_index)

    worker = BoundedRecordingWorker(handler, max_queue=16)
    worker.start()
    for frame_index in range(5):
        worker.submit(frame_index)

    def stop_pitch() -> None:
        nonlocal pitch_active
        stop_snapshot.extend(pitch_frames)
        pitch_active = False
        done.set()

    assert worker.submit_control(stop_pitch)
    for frame_index in range(5, 8):
        worker.submit(frame_index)

    assert done.wait(2.0)
    assert worker.stop(drain=True, timeout=2.0)
    assert stop_snapshot == list(range(5))
    assert pitch_frames == list(range(5))
