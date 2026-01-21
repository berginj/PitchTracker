"""Integration tests for RecordingService.

Tests the event-driven recording service that manages session and pitch recording.
"""

import json
import shutil
import tempfile
import threading
import time
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pytest

from app.events.event_bus import EventBus
from app.events.event_types import (
    FrameCapturedEvent,
    ObservationDetectedEvent,
    PitchStartEvent,
    PitchEndEvent
)
from app.services.recording import RecordingServiceImpl
from configs.settings import AppConfig, load_config
from contracts import Frame, StereoObservation


# Test fixtures

def create_test_config() -> AppConfig:
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


def create_test_observation(timestamp_ns: int) -> StereoObservation:
    """Create test stereo observation."""
    return StereoObservation(
        t_ns=timestamp_ns,
        left=np.array([320.0, 240.0]),
        right=np.array([310.0, 240.0]),
        X=1.0,
        Y=2.0,
        Z=5.0,
        quality=0.95,
        confidence=0.9
    )


class TestRecordingServiceBasics:
    """Test basic RecordingService functionality."""

    def test_initialization(self):
        """Test RecordingService initialization."""
        bus = EventBus()
        service = RecordingServiceImpl(bus)

        assert not service.is_recording_session()
        assert not service.is_recording_pitch()
        assert service.get_session_dir() is None
        assert service.get_pitch_dir() is None

    def test_start_stop_session(self):
        """Test starting and stopping a session."""
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = create_test_config()

        # Create temp directory for recordings
        temp_dir = Path(tempfile.mkdtemp())
        try:
            service.set_record_directory(temp_dir)

            # Start session
            warning = service.start_session("test_session", config)
            assert warning == ""  # No disk space warning
            assert service.is_recording_session()
            assert service.get_session_dir() is not None
            assert service.get_session_dir().exists()

            # Stop session
            bundle = service.stop_session()
            assert not service.is_recording_session()
            assert service.get_session_dir() is None

        finally:
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_start_session_already_active(self):
        """Test starting session when already active raises error."""
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = create_test_config()

        temp_dir = Path(tempfile.mkdtemp())
        try:
            service.set_record_directory(temp_dir)
            service.start_session("session1", config)

            # Try to start another session - should raise
            with pytest.raises(RuntimeError, match="Session already active"):
                service.start_session("session2", config)

        finally:
            service.stop_session()
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_stop_session_not_active(self):
        """Test stopping session when not active raises error."""
        bus = EventBus()
        service = RecordingServiceImpl(bus)

        with pytest.raises(RuntimeError, match="No session active"):
            service.stop_session()


class TestRecordingServicePitch:
    """Test pitch recording functionality."""

    def test_start_stop_pitch(self):
        """Test starting and stopping a pitch."""
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = create_test_config()

        temp_dir = Path(tempfile.mkdtemp())
        try:
            service.set_record_directory(temp_dir)
            service.start_session("test_session", config)

            # Start pitch
            service.start_pitch("pitch_001")
            assert service.is_recording_pitch()
            assert service.get_pitch_dir() is not None
            assert service.get_pitch_dir().exists()

            # Stop pitch
            pitch_dir = service.stop_pitch()
            assert pitch_dir is not None
            assert not service.is_recording_pitch()
            assert service.get_pitch_dir() is None

        finally:
            service.stop_session()
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_start_pitch_no_session(self):
        """Test starting pitch without session raises error."""
        bus = EventBus()
        service = RecordingServiceImpl(bus)

        with pytest.raises(RuntimeError, match="No session active"):
            service.start_pitch("pitch_001")

    def test_start_pitch_already_active(self):
        """Test starting pitch when already active raises error."""
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = create_test_config()

        temp_dir = Path(tempfile.mkdtemp())
        try:
            service.set_record_directory(temp_dir)
            service.start_session("test_session", config)
            service.start_pitch("pitch_001")

            # Try to start another pitch - should raise
            with pytest.raises(RuntimeError, match="Pitch already active"):
                service.start_pitch("pitch_002")

        finally:
            service.stop_session()
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestRecordingServiceFrames:
    """Test frame recording functionality."""

    def test_record_frame(self):
        """Test recording frames to session."""
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = create_test_config()

        temp_dir = Path(tempfile.mkdtemp())
        try:
            service.set_record_directory(temp_dir)
            service.start_session("test_session", config)

            # Record frames
            for i in range(10):
                frame_left = create_test_frame("left", i, i * 1000000)
                frame_right = create_test_frame("right", i, i * 1000000)
                service.record_frame("left", frame_left)
                service.record_frame("right", frame_right)

            # Stop session
            service.stop_session()

            # Verify session video files exist
            session_dir = list(temp_dir.glob("test_session_*"))[0]
            assert (session_dir / "session_left.avi").exists()
            assert (session_dir / "session_right.avi").exists()
            assert (session_dir / "session_left_timestamps.csv").exists()
            assert (session_dir / "session_right_timestamps.csv").exists()

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_record_frame_no_session(self):
        """Test recording frame without session raises error."""
        bus = EventBus()
        service = RecordingServiceImpl(bus)

        frame = create_test_frame("left", 0, 0)
        with pytest.raises(RuntimeError, match="No session active"):
            service.record_frame("left", frame)


class TestRecordingServiceEventBusIntegration:
    """Test EventBus integration."""

    def test_frame_captured_event(self):
        """Test FrameCapturedEvent triggers recording."""
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = create_test_config()

        temp_dir = Path(tempfile.mkdtemp())
        try:
            service.set_record_directory(temp_dir)
            service.start_session("test_session", config)

            # Publish FrameCapturedEvent
            for i in range(5):
                event_left = FrameCapturedEvent(
                    camera_id="left",
                    frame=create_test_frame("left", i, i * 1000000),
                    timestamp_ns=i * 1000000
                )
                event_right = FrameCapturedEvent(
                    camera_id="right",
                    frame=create_test_frame("right", i, i * 1000000),
                    timestamp_ns=i * 1000000
                )
                bus.publish(event_left)
                bus.publish(event_right)

            # Stop session
            service.stop_session()

            # Verify frames were recorded
            session_dir = list(temp_dir.glob("test_session_*"))[0]
            assert (session_dir / "session_left.avi").exists()
            assert (session_dir / "session_right.avi").exists()

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_pitch_start_event(self):
        """Test PitchStartEvent triggers pitch recording."""
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = create_test_config()

        temp_dir = Path(tempfile.mkdtemp())
        try:
            service.set_record_directory(temp_dir)
            service.start_session("test_session", config)

            # Publish PitchStartEvent
            event = PitchStartEvent(
                pitch_id="pitch_001",
                pitch_index=1,
                timestamp_ns=1000000000
            )
            bus.publish(event)

            # Verify pitch recording started
            assert service.is_recording_pitch()
            assert service.get_pitch_dir() is not None

            # Stop session
            service.stop_session()

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_observation_detected_event(self):
        """Test ObservationDetectedEvent records observation."""
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = create_test_config()

        temp_dir = Path(tempfile.mkdtemp())
        try:
            service.set_record_directory(temp_dir)
            service.start_session("test_session", config)
            service.start_pitch("pitch_001")

            # Publish ObservationDetectedEvent
            obs = create_test_observation(1000000000)
            event = ObservationDetectedEvent(
                observation=obs,
                timestamp_ns=1000000000,
                confidence=0.9
            )
            bus.publish(event)

            # Stop pitch and session
            service.stop_pitch()
            service.stop_session()

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestRecordingServicePreRoll:
    """Test pre-roll buffer functionality."""

    def test_pre_roll_buffer(self):
        """Test pre-roll frames are buffered and written to pitch."""
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = create_test_config()

        temp_dir = Path(tempfile.mkdtemp())
        try:
            service.set_record_directory(temp_dir)
            service.start_session("test_session", config)

            # Record frames BEFORE pitch starts (these should be buffered)
            for i in range(30):
                frame_left = create_test_frame("left", i, i * 1000000)
                frame_right = create_test_frame("right", i, i * 1000000)
                service.record_frame("left", frame_left)
                service.record_frame("right", frame_right)

            # Start pitch (should flush pre-roll buffer)
            service.start_pitch("pitch_001")

            # Record more frames AFTER pitch starts
            for i in range(30, 60):
                frame_left = create_test_frame("left", i, i * 1000000)
                frame_right = create_test_frame("right", i, i * 1000000)
                service.record_frame("left", frame_left)
                service.record_frame("right", frame_right)

            # Stop pitch and session
            service.stop_pitch()
            service.stop_session()

            # Verify pitch videos include pre-roll frames
            session_dir = list(temp_dir.glob("test_session_*"))[0]
            pitch_dir = session_dir / "pitch_001"
            assert pitch_dir.exists()
            assert (pitch_dir / "left.avi").exists()
            assert (pitch_dir / "right.avi").exists()

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestRecordingServiceCallbacks:
    """Test recording event callbacks."""

    def test_callbacks(self):
        """Test recording event callbacks are invoked."""
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = create_test_config()

        events_received: List[Tuple[str, str]] = []

        def callback(event_type: str, data: str):
            events_received.append((event_type, data))

        service.on_recording_event(callback)

        temp_dir = Path(tempfile.mkdtemp())
        try:
            service.set_record_directory(temp_dir)

            # Start session
            service.start_session("test_session", config)
            assert len(events_received) == 1
            assert events_received[0][0] == "session_started"

            # Start pitch
            service.start_pitch("pitch_001")
            assert len(events_received) == 2
            assert events_received[1][0] == "pitch_started"

            # Stop pitch
            service.stop_pitch()
            assert len(events_received) == 3
            assert events_received[2][0] == "pitch_ended"

            # Stop session
            service.stop_session()
            assert len(events_received) == 4
            assert events_received[3][0] == "session_ended"

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestRecordingServiceThreadSafety:
    """Test RecordingService thread safety."""

    def test_concurrent_frame_recording(self):
        """Test multiple threads recording frames simultaneously."""
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = create_test_config()

        temp_dir = Path(tempfile.mkdtemp())
        try:
            service.set_record_directory(temp_dir)
            service.start_session("test_session", config)

            def record_frames(camera_id: str, count: int):
                for i in range(count):
                    frame = create_test_frame(camera_id, i, i * 1000000)
                    service.record_frame(camera_id, frame)

            # Create threads for left and right cameras
            thread_left = threading.Thread(target=record_frames, args=("left", 50))
            thread_right = threading.Thread(target=record_frames, args=("right", 50))

            thread_left.start()
            thread_right.start()

            thread_left.join()
            thread_right.join()

            # Stop session
            service.stop_session()

            # Verify session videos exist
            session_dir = list(temp_dir.glob("test_session_*"))[0]
            assert (session_dir / "session_left.avi").exists()
            assert (session_dir / "session_right.avi").exists()

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])
