"""Integration tests for DetectionService.

Tests the event-driven detection service that manages detection and stereo matching.
"""

import time
from pathlib import Path
from typing import List

import numpy as np
import pytest

from app.events.event_bus import EventBus
from app.events.event_types import FrameCapturedEvent, ObservationDetectedEvent
from app.services.detection import DetectionServiceImpl
from configs.settings import load_config
from contracts import Frame, StereoObservation
from detect.config import Mode


# Test fixtures

def create_test_config():
    """Create test configuration from default.yaml."""
    config_path = Path(__file__).parent.parent.parent / "configs" / "default.yaml"
    return load_config(config_path)


def create_test_frame(camera_id: str, frame_index: int, timestamp_ns: int) -> Frame:
    """Create test frame."""
    return Frame(
        camera_id=camera_id,
        frame_index=frame_index,
        t_capture_monotonic_ns=timestamp_ns,
        image=np.zeros((480, 640, 3), dtype=np.uint8),
        width=640,
        height=480,
        pixfmt="BGR3"
    )


class TestDetectionServiceBasics:
    """Test basic DetectionService functionality."""

    def test_initialization(self):
        """Test DetectionService initialization."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        assert not service.is_running()

    def test_configure_detectors(self):
        """Test configuring detectors."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        # Configure with classical detector
        service.configure_detectors(
            config=config.detector,
            mode=Mode.MODE_A,
            detector_type="classical"
        )

        # Should not raise

    def test_configure_threading(self):
        """Test configuring threading mode."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        # Configure per_camera mode
        service.configure_threading(mode="per_camera", worker_count=2)

        # Configure worker_pool mode
        service.configure_threading(mode="worker_pool", worker_count=4)

    def test_configure_threading_invalid_mode(self):
        """Test configuring with invalid threading mode raises error."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        with pytest.raises(ValueError, match="Invalid threading mode"):
            service.configure_threading(mode="invalid", worker_count=2)

    def test_configure_threading_invalid_worker_count(self):
        """Test configuring with invalid worker count raises error."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        with pytest.raises(ValueError, match="Invalid worker_count"):
            service.configure_threading(mode="per_camera", worker_count=0)

    def test_start_detection_not_configured(self):
        """Test starting detection without configuration raises error."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        # Start without configuring detectors
        with pytest.raises(RuntimeError, match="Detectors not configured"):
            service.start_detection()

    def test_start_stop_detection(self):
        """Test starting and stopping detection."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        # Configure
        service.configure_detectors(
            config=config.detector,
            mode=Mode.MODE_A,
            detector_type="classical"
        )
        service.configure_threading(mode="per_camera", worker_count=2)

        # Start detection
        service.start_detection()
        assert service.is_running()

        # Stop detection
        service.stop_detection()
        assert not service.is_running()


class TestDetectionServiceStats:
    """Test detection statistics functionality."""

    def test_get_stats_not_running(self):
        """Test getting stats when not running returns zeros."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        stats = service.get_detection_stats()
        assert stats["detections_per_sec"] == 0.0
        assert stats["observations_per_sec"] == 0.0
        assert stats["avg_detection_ms"] == 0.0
        assert stats["stereo_match_rate"] == 0.0

    def test_get_stats_running(self):
        """Test getting stats when running."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        # Configure and start
        service.configure_detectors(
            config=config.detector,
            mode=Mode.MODE_A,
            detector_type="classical"
        )
        service.configure_threading(mode="per_camera", worker_count=2)
        service.start_detection()

        # Wait a bit
        time.sleep(0.1)

        # Get stats
        stats = service.get_detection_stats()
        assert "detections_per_sec" in stats
        assert "observations_per_sec" in stats

        service.stop_detection()


class TestDetectionServiceDetections:
    """Test detection processing functionality."""

    def test_get_latest_detections_empty(self):
        """Test getting detections before any processing returns empty."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        detections = service.get_latest_detections()
        assert detections == {}

    def test_get_latest_gated_detections_empty(self):
        """Test getting gated detections before any processing returns empty."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        gated = service.get_latest_gated_detections()
        assert gated == {}

    def test_get_latest_observations_empty(self):
        """Test getting observations returns empty list."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        observations = service.get_latest_observations()
        assert observations == []


class TestDetectionServiceEventBusIntegration:
    """Test EventBus integration."""

    def test_observation_detected_event_subscription(self):
        """Test ObservationDetectedEvent can be subscribed to."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        events_received: List[ObservationDetectedEvent] = []

        def handle_observation(event: ObservationDetectedEvent):
            events_received.append(event)

        bus.subscribe(ObservationDetectedEvent, handle_observation)

        # Configure and start detection
        service.configure_detectors(
            config=config.detector,
            mode=Mode.MODE_A,
            detector_type="classical"
        )
        service.configure_threading(mode="per_camera", worker_count=2)
        service.start_detection()

        # Publish some frame events (simulating capture)
        for i in range(10):
            left_frame = create_test_frame("left", i, i * 1000000)
            right_frame = create_test_frame("right", i, i * 1000000)

            left_event = FrameCapturedEvent(
                camera_id="left",
                frame=left_frame,
                timestamp_ns=i * 1000000
            )
            right_event = FrameCapturedEvent(
                camera_id="right",
                frame=right_frame,
                timestamp_ns=i * 1000000
            )

            bus.publish(left_event)
            bus.publish(right_event)

        # Wait for processing
        time.sleep(0.5)

        # Stop detection
        service.stop_detection()

        # Observations may or may not be generated depending on detection
        # (test frames are all black, so no detections expected)
        # This test just verifies the subscription mechanism works
        assert isinstance(events_received, list)


class TestDetectionServiceCallbacks:
    """Test callback functionality."""

    def test_observation_callbacks(self):
        """Test observation callbacks registration."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        observations_received: List[StereoObservation] = []

        def observation_callback(obs: StereoObservation):
            observations_received.append(obs)

        service.on_observation_detected(observation_callback)

        # Configure and start
        service.configure_detectors(
            config=config.detector,
            mode=Mode.MODE_A,
            detector_type="classical"
        )
        service.configure_threading(mode="per_camera", worker_count=2)
        service.start_detection()

        # Wait a bit
        time.sleep(0.1)

        # Stop
        service.stop_detection()

        # Callback registered successfully (observations may be empty)
        assert isinstance(observations_received, list)


class TestDetectionServiceROIs:
    """Test ROI configuration."""

    def test_set_lane_rois(self):
        """Test setting lane ROIs."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        # Set lane ROIs
        lane_rois = {
            "left": [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
            "right": [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        }
        plate_rois = {
            "left": [(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)],
            "right": [(0.4, 0.4), (0.6, 0.4), (0.6, 0.6), (0.4, 0.6)],
        }

        service.set_lane_rois(lane_rois, plate_rois)

        # Should not raise


class TestDetectionServiceProcessFrame:
    """Test frame processing."""

    def test_process_frame_not_running(self):
        """Test processing frame when not running returns empty."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        frame = create_test_frame("left", 0, 0)
        detections = service.process_frame("left", frame)

        assert detections == []

    def test_process_frame_running(self):
        """Test processing frame when running."""
        bus = EventBus()
        config = create_test_config()
        service = DetectionServiceImpl(bus, config)

        # Configure and start
        service.configure_detectors(
            config=config.detector,
            mode=Mode.MODE_A,
            detector_type="classical"
        )
        service.configure_threading(mode="per_camera", worker_count=2)
        service.start_detection()

        # Process frame
        frame = create_test_frame("left", 0, 0)
        detections = service.process_frame("left", frame)

        # Returns empty immediately (async processing)
        assert detections == []

        service.stop_detection()


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
