"""Repeated display/detection reads must resolve to the same encoded frame."""

from unittest.mock import MagicMock

import numpy as np

from app.review.video_reader import VideoReader


def test_repeated_read_does_not_advance_decoder_or_mutate_cache():
    reader = VideoReader()
    left, right = MagicMock(), MagicMock()
    reader._left_capture, reader._right_capture = left, right
    reader._total_frames = 3
    for capture in (left, right):
        capture.read.return_value = True, np.ones((2, 2, 3), dtype=np.uint8)
    first, _ = reader.read_frames()
    first[:] = 0
    second, _ = reader.read_frames()
    assert second.min() == 1
    assert left.read.call_count == right.read.call_count == 1
    assert reader.seek_to_frame(1)
    reader.read_frames()
    assert left.read.call_count == right.read.call_count == 2
    assert reader.current_frame_index == 1
    assert reader.step_forward()
    assert not reader.step_forward()
