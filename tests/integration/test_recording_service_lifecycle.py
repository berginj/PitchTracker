"""Integration tests for RecordingService lifecycle behavior."""

import shutil
import tempfile
import threading
from pathlib import Path
from typing import List, Tuple

import cv2
import numpy as np
import pytest

from app.events.event_bus import EventBus
from app.services.recording import RecordingServiceImpl
from configs.settings import AppConfig, load_config
from contracts import Frame


def has_video_writer_codec() -> bool:
    """Return whether this environment can open an OpenCV video writer."""
    temp_dir = Path(tempfile.mkdtemp())
    try:
        path = temp_dir / "codec_probe.avi"
        for codec_name in ("H264", "avc1", "XVID", "MP4V", "MJPG"):
            fourcc = cv2.VideoWriter_fourcc(*codec_name)
            writer = cv2.VideoWriter(str(path), fourcc, 30.0, (64, 64), True)
            try:
                if writer.isOpened():
                    return True
            finally:
                writer.release()
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
    return False


requires_video_codec = pytest.mark.skipif(
    not has_video_writer_codec(),
    reason="OpenCV cannot open any configured video writer codec in this environment",
)


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
        pixfmt="BGR3",
    )


@requires_video_codec
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
            for i in range(30):
                frame_left = create_test_frame("left", i, i * 1000000)
                frame_right = create_test_frame("right", i, i * 1000000)
                service.record_frame("left", frame_left)
                service.record_frame("right", frame_right)
            service.start_pitch("pitch_001")
            for i in range(30, 60):
                frame_left = create_test_frame("left", i, i * 1000000)
                frame_right = create_test_frame("right", i, i * 1000000)
                service.record_frame("left", frame_left)
                service.record_frame("right", frame_right)
            service.stop_pitch()
            service.stop_session()
            session_dir = list(temp_dir.glob("test_session_*"))[0]
            pitch_dir = session_dir / "pitch_001"
            assert pitch_dir.exists()
            assert (pitch_dir / "left.avi").exists()
            assert (pitch_dir / "right.avi").exists()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


@requires_video_codec
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
            service.start_session("test_session", config)
            assert len(events_received) == 1
            assert events_received[0][0] == "session_started"
            service.start_pitch("pitch_001")
            assert len(events_received) == 2
            assert events_received[1][0] == "pitch_started"
            service.stop_pitch()
            assert len(events_received) == 3
            assert events_received[2][0] == "pitch_ended"
            service.stop_session()
            assert len(events_received) == 4
            assert events_received[3][0] == "session_ended"
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)


@requires_video_codec
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

            thread_left = threading.Thread(target=record_frames, args=("left", 50))
            thread_right = threading.Thread(target=record_frames, args=("right", 50))
            thread_left.start()
            thread_right.start()
            thread_left.join()
            thread_right.join()
            service.stop_session()
            session_dir = list(temp_dir.glob("test_session_*"))[0]
            assert (session_dir / "session_left.avi").exists()
            assert (session_dir / "session_right.avi").exists()
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
