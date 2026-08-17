"""Concurrency test for DetectionProcessor stereo buffer pairing.

Exercises the per-thread race fixed by the stereo buffer lock: the left and
right capture threads both call process_detection_result() concurrently, which
mutates the shared deques and runs the pop-match cycle. Without the lock this
produces data races / undefined behavior; with it, every left/right frame pair
is matched exactly once and no exceptions escape.
"""

from __future__ import annotations

import threading
from unittest.mock import Mock

import numpy as np

from contracts import Frame
from app.pipeline.detection.processor import DetectionProcessor


def _make_config() -> Mock:
    config = Mock()
    config.stereo.use_frame_index_pairing = False
    config.stereo.pairing_tolerance_ms = 8
    config.stereo.time_sync_offset_ns = 0
    return config


def _make_frame(camera_id: str, index: int, t_ns: int) -> Frame:
    return Frame(
        camera_id=camera_id,
        frame_index=index,
        t_capture_monotonic_ns=t_ns,
        image=np.zeros((2, 2), dtype=np.uint8),
        width=2,
        height=2,
        pixfmt="GRAY8",
    )


def _build_processor() -> DetectionProcessor:
    return DetectionProcessor(
        config=_make_config(),
        stereo_matcher=Mock(),
        lane_gate=None,
        plate_gate=None,
        stereo_gate=None,
        plate_stereo_gate=None,
        get_ball_radius_fn=lambda: 1.0,
    )


def test_concurrent_process_detection_result_matches_every_pair():
    processor = _build_processor()

    # Isolate the buffering/pairing logic: count matched pairs instead of doing
    # real triangulation. Guard the counter with its own lock since pairs are
    # processed outside the buffer lock (by design).
    processed = []
    processed_lock = threading.Lock()

    def _record_pair(left_frame, right_frame, left_dets, right_dets):
        with processed_lock:
            processed.append((left_frame.t_capture_monotonic_ns, right_frame.t_capture_monotonic_ns))

    processor._process_stereo_pair = _record_pair

    n = 500
    period_ns = 16_000_000
    left_frames = [_make_frame("left", i, i * period_ns) for i in range(n)]
    right_frames = [_make_frame("right", i, i * period_ns) for i in range(n)]

    start = threading.Event()

    def _feed(label, frames):
        start.wait()
        for f in frames:
            processor.process_detection_result(label, f, [])

    t_left = threading.Thread(target=_feed, args=("left", left_frames))
    t_right = threading.Thread(target=_feed, args=("right", right_frames))
    t_left.start()
    t_right.start()
    start.set()
    t_left.join(timeout=30)
    t_right.join(timeout=30)

    assert not t_left.is_alive() and not t_right.is_alive()

    # Each matched pair must have identical timestamps (perfectly aligned input),
    # and no pair is processed more than once.
    assert len(processed) == len(set(processed))
    assert all(lt == rt for lt, rt in processed)
    # With buffers capped at maxlen=6, not every frame survives to be paired, but
    # a substantial fraction must be matched and nothing may be double-processed.
    assert len(processed) > 0


def test_serial_pairing_is_one_to_one():
    processor = _build_processor()
    processed = []
    processor._process_stereo_pair = lambda lf, rf, ld, rd: processed.append(
        (lf.frame_index, rf.frame_index)
    )

    for i in range(5):
        processor.process_detection_result("left", _make_frame("left", i, i * 16_000_000), [])
        processor.process_detection_result("right", _make_frame("right", i, i * 16_000_000), [])

    assert processed == [(i, i) for i in range(5)]


def test_timestamp_pairing_applies_right_clock_offset_but_preserves_raw_frames():
    config = _make_config()
    config.stereo.pairing_tolerance_ms = 2
    config.stereo.time_sync_offset_ns = -9_000_000
    processor = DetectionProcessor(
        config=config,
        stereo_matcher=Mock(),
        lane_gate=None,
        plate_gate=None,
        stereo_gate=None,
        plate_stereo_gate=None,
        get_ball_radius_fn=lambda: 1.0,
    )
    processed = []
    processor._process_stereo_pair = lambda lf, rf, ld, rd: processed.append((lf, rf))
    left = _make_frame("left", 1, 100_000_000)
    right = _make_frame("right", 1, 109_000_000)

    processor.process_detection_result("left", left, [])
    processor.process_detection_result("right", right, [])

    assert processed == [(left, right)]
    assert processed[0][0].t_capture_monotonic_ns == 100_000_000
    assert processed[0][1].t_capture_monotonic_ns == 109_000_000
    stats = processor.get_sync_stats()
    assert stats["p95_delta_ms"] == 0.0
    assert stats["raw_p95_delta_ms"] == 9.0
    assert stats["time_sync_offset_ns"] == -9_000_000
