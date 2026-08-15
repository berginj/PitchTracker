"""Characterization tests for CameraFrameRouter — callback exceptions and routing."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, Mock

import numpy as np
from app.pipeline.camera_frame_router import CameraFrameRouter, _validate_frame
from contracts import Frame


def _make_frame(width=640, height=480):
    """Create a valid test frame."""
    return Frame(
        camera_id="test",
        frame_index=0,
        t_capture_monotonic_ns=time.monotonic_ns(),
        image=np.ones((height, width), dtype=np.uint8) * 128,
        width=width,
        height=height,
        pixfmt="GRAY8",
    )


class TestValidateFrame:
    """Test frame validation logic."""

    def test_none_frame_invalid(self):
        assert _validate_frame("left", None) is False

    def test_none_image_invalid(self):
        frame = Mock(spec=Frame)
        frame.image = None
        frame.width = 640
        frame.height = 480
        assert _validate_frame("test", frame) is False

    def test_zero_dimensions_invalid(self):
        frame = Mock(spec=Frame)
        frame.image = np.zeros((1, 1), dtype=np.uint8)
        frame.width = 0
        frame.height = 480
        assert _validate_frame("test", frame) is False

    def test_all_zero_image_invalid(self):
        frame = Mock(spec=Frame)
        frame.image = np.zeros((480, 640), dtype=np.uint8)
        frame.width = 640
        frame.height = 480
        assert _validate_frame("test", frame) is False

    def test_valid_frame(self):
        frame = _make_frame()
        assert _validate_frame("left", frame) is True


class TestCallbackExceptions:
    """Frame callback exceptions must not crash the capture loop."""

    def test_callback_exception_does_not_crash_loop(self):
        """If frame callback raises, loop continues delivering frames."""
        router = CameraFrameRouter()
        delivered = []
        call_count = [0]

        def bad_callback(label, frame):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("callback explosion")
            delivered.append(frame)

        router.set_frame_callback(bad_callback)
        router.set_preview_callback(lambda label, frame: None)

        # Create a fake camera that delivers 3 frames then stops
        frames = [_make_frame() for _ in range(3)]
        frame_iter = iter(frames)

        camera = MagicMock()

        def read_side_effect(timeout_ms=200):
            try:
                return next(frame_iter)
            except StopIteration:
                # Signal router to stop
                router._capture_running = False
                raise TimeoutError("done")

        camera.read_frame.side_effect = read_side_effect

        # Run loop directly (not threaded, for determinism)
        stop = threading.Event()
        router._capture_running = True
        router._capture_loop("left", camera, stop)

        # Should have received frames 2 and 3 despite callback crash on 1
        assert len(delivered) == 2

    def test_preview_callback_receives_valid_frames(self):
        """Preview callback is called for each valid frame."""
        router = CameraFrameRouter()
        preview_frames = []
        router.set_preview_callback(lambda label, frame: preview_frames.append((label, frame)))

        frames = [_make_frame(), _make_frame()]
        frame_iter = iter(frames)
        camera = MagicMock()

        def read_side_effect(timeout_ms=200):
            try:
                return next(frame_iter)
            except StopIteration:
                router._capture_running = False
                raise TimeoutError("done")

        camera.read_frame.side_effect = read_side_effect
        stop = threading.Event()
        router._capture_running = True
        router._capture_loop("right", camera, stop)

        assert len(preview_frames) == 2
        assert all(label == "right" for label, _ in preview_frames)
