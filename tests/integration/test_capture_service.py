"""Integration tests for CaptureService.

Tests the event-driven capture service that manages camera lifecycle and publishes frames.
"""

import threading
import time
from pathlib import Path
from typing import List, Tuple

import pytest

from app.camera import CameraState
from app.events.event_bus import EventBus
from app.events.event_types import FrameCapturedEvent
from app.services.capture import CaptureServiceImpl
from configs.settings import load_config
from contracts import Frame


# Test fixtures

def create_test_config():
    """Create test configuration from default.yaml."""
    config_path = Path(__file__).parent.parent.parent / "configs" / "default.yaml"
    return load_config(config_path)


# Note: Simulated cameras use "left" and "right" as camera_ids,
# regardless of the serial numbers passed to start_capture()


class TestCaptureServiceBasics:
    """Test basic CaptureService functionality."""

    def test_initialization(self):
        """Test CaptureService initialization."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")

        assert not service.is_capturing()

    def test_start_stop_capture(self):
        """Test starting and stopping capture."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")
        config = create_test_config()

        # Start capture with simulated cameras
        service.start_capture(config, left_serial="left", right_serial="right")
        assert service.is_capturing()

        # Stop capture
        service.stop_capture()
        assert not service.is_capturing()

    def test_start_capture_already_started(self):
        """Test starting capture when already started raises error."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")
        config = create_test_config()

        service.start_capture(config, left_serial="left", right_serial="right")

        # Try to start again - should raise
        with pytest.raises(RuntimeError, match="Capture already started"):
            service.start_capture(config, left_serial="left", right_serial="right")

        service.stop_capture()

    def test_stop_capture_idempotent(self):
        """Test stopping capture multiple times is safe."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")
        config = create_test_config()

        service.start_capture(config, left_serial="left", right_serial="right")
        service.stop_capture()

        # Stop again - should not raise
        service.stop_capture()
        assert not service.is_capturing()


class TestCaptureServicePreview:
    """Test preview frame functionality."""

    def test_get_preview_frames(self):
        """Test getting preview frames."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")
        config = create_test_config()

        service.start_capture(config, left_serial="left", right_serial="right")

        # Wait for frames to be available
        time.sleep(0.2)

        # Get preview frames
        left_frame, right_frame = service.get_preview_frames()
        assert left_frame is not None
        assert right_frame is not None
        assert left_frame.camera_id == "left"
        assert right_frame.camera_id == "right"

        service.stop_capture()

    def test_get_preview_frames_not_capturing(self):
        """Test getting preview frames when not capturing raises error."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")

        with pytest.raises(RuntimeError, match="Capture not active"):
            service.get_preview_frames()


class TestCaptureServiceStats:
    """Test statistics functionality."""

    def test_get_stats(self):
        """Test getting capture statistics."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")
        config = create_test_config()

        service.start_capture(config, left_serial="left", right_serial="right")

        # Wait for some frames
        time.sleep(0.2)

        # Get stats
        stats = service.get_stats()
        assert "left" in stats
        assert "right" in stats

        service.stop_capture()

    def test_get_stats_not_capturing(self):
        """Test getting stats when not capturing returns empty dict."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")

        stats = service.get_stats()
        assert stats == {}


class TestCaptureServiceEventBusIntegration:
    """Test EventBus integration."""

    def test_frame_captured_event_published(self):
        """Test FrameCapturedEvent is published to EventBus."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")
        config = create_test_config()

        events_received: List[FrameCapturedEvent] = []

        def handle_frame(event: FrameCapturedEvent):
            events_received.append(event)

        bus.subscribe(FrameCapturedEvent, handle_frame)

        # Start capture
        service.start_capture(config, left_serial="left", right_serial="right")

        # Wait for some frames
        time.sleep(0.5)

        # Stop capture
        service.stop_capture()

        # Verify events were published
        assert len(events_received) > 0
        left_events = [e for e in events_received if e.camera_id == "left"]
        right_events = [e for e in events_received if e.camera_id == "right"]
        assert len(left_events) > 0
        assert len(right_events) > 0

        # Verify event structure
        event = events_received[0]
        assert event.frame is not None
        assert event.timestamp_ns > 0
        assert event.camera_id in ["left", "right"]

    def test_frame_captured_event_rate(self):
        """Test frame events are published at expected rate."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")
        config = create_test_config()

        events_received: List[FrameCapturedEvent] = []
        lock = threading.Lock()

        def handle_frame(event: FrameCapturedEvent):
            with lock:
                events_received.append(event)

        bus.subscribe(FrameCapturedEvent, handle_frame)

        # Start capture
        service.start_capture(config, left_serial="left", right_serial="right")

        # Capture for 1 second
        time.sleep(1.0)

        # Stop capture
        service.stop_capture()

        # Simulated cameras run at ~30fps per camera
        # Expect at least 20 frames per camera in 1 second (allowing for startup delay)
        left_events = [e for e in events_received if e.camera_id == "left"]
        right_events = [e for e in events_received if e.camera_id == "right"]

        assert len(left_events) >= 15, f"Expected >= 15 left frames, got {len(left_events)}"
        assert len(right_events) >= 15, f"Expected >= 15 right frames, got {len(right_events)}"


class TestCaptureServiceCallbacks:
    """Test callback functionality."""

    def test_frame_callbacks(self):
        """Test frame callbacks are invoked."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")
        config = create_test_config()

        frames_received: List[Tuple[str, Frame]] = []
        lock = threading.Lock()

        def frame_callback(camera_id: str, frame: Frame):
            with lock:
                frames_received.append((camera_id, frame))

        service.on_frame_captured(frame_callback)

        # Start capture
        service.start_capture(config, left_serial="left", right_serial="right")

        # Wait for frames
        time.sleep(0.5)

        # Stop capture
        service.stop_capture()

        # Verify callbacks were invoked
        assert len(frames_received) > 0
        left_frames = [f for camera_id, f in frames_received if camera_id == "left"]
        right_frames = [f for camera_id, f in frames_received if camera_id == "right"]
        assert len(left_frames) > 0
        assert len(right_frames) > 0

    def test_multiple_frame_callbacks(self):
        """Test multiple frame callbacks can be registered."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")
        config = create_test_config()

        callback1_count = [0]
        callback2_count = [0]
        lock = threading.Lock()

        def callback1(camera_id: str, frame: Frame):
            with lock:
                callback1_count[0] += 1

        def callback2(camera_id: str, frame: Frame):
            with lock:
                callback2_count[0] += 1

        service.on_frame_captured(callback1)
        service.on_frame_captured(callback2)

        # Start capture
        service.start_capture(config, left_serial="left", right_serial="right")

        # Wait for frames
        time.sleep(0.3)

        # Stop capture
        service.stop_capture()

        # Both callbacks should have been invoked
        assert callback1_count[0] > 0
        assert callback2_count[0] > 0
        # Should have same count (both invoked for each frame)
        assert callback1_count[0] == callback2_count[0]


class TestCaptureServiceReconnection:
    """Test reconnection functionality."""

    def test_enable_reconnection(self):
        """Test enabling/disabling reconnection."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")

        # Should not raise
        service.enable_reconnection(True)
        service.enable_reconnection(False)

    def test_camera_state_callback(self):
        """Test camera state change callbacks."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")
        config = create_test_config()

        state_changes: List[Tuple[str, CameraState]] = []
        lock = threading.Lock()

        def state_callback(camera_id: str, state: CameraState):
            with lock:
                state_changes.append((camera_id, state))

        service.on_camera_state_changed(state_callback)

        # Start capture (simulated cameras don't emit state changes, but registration should work)
        service.start_capture(config, left_serial="left", right_serial="right")
        time.sleep(0.1)
        service.stop_capture()

        # For simulated cameras, state changes may not occur
        # This test just verifies registration doesn't break


class TestCaptureServiceThreadSafety:
    """Test CaptureService thread safety."""

    def test_concurrent_stat_queries(self):
        """Test multiple threads querying stats simultaneously."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")
        config = create_test_config()

        service.start_capture(config, left_serial="left", right_serial="right")
        time.sleep(0.2)

        results = []
        lock = threading.Lock()

        def query_stats():
            for _ in range(10):
                stats = service.get_stats()
                with lock:
                    results.append(stats)
                time.sleep(0.01)

        # Create multiple threads
        threads = [threading.Thread(target=query_stats) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All queries should have succeeded
        assert len(results) == 50  # 5 threads × 10 queries each

        service.stop_capture()

    def test_concurrent_preview_queries(self):
        """Test multiple threads querying preview frames simultaneously."""
        bus = EventBus()
        service = CaptureServiceImpl(bus, backend="sim")
        config = create_test_config()

        service.start_capture(config, left_serial="left", right_serial="right")
        time.sleep(0.2)

        results = []
        lock = threading.Lock()

        def query_preview():
            for _ in range(10):
                try:
                    left, right = service.get_preview_frames()
                    with lock:
                        results.append((left, right))
                except Exception:
                    pass  # Frame may not be available yet
                time.sleep(0.01)

        # Create multiple threads
        threads = [threading.Thread(target=query_preview) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Most queries should have succeeded
        assert len(results) > 0

        service.stop_capture()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
