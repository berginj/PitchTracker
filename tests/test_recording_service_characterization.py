"""Characterization tests for RecordingService refactoring boundaries.

Covers: start rollback, pitch FIFO boundaries, session/pitch metadata
finalization, stop/pause/error cleanup, and frame writer stats.
"""

from __future__ import annotations

import shutil
import tempfile
import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import numpy as np
import pytest

from app.events.event_bus import EventBus
from app.services.recording import RecordingServiceImpl
from configs.settings import AppConfig, load_config
from contracts import Frame


def _config() -> AppConfig:
    return load_config(Path(__file__).parent.parent / "configs" / "default.yaml")


def _frame(camera_id: str = "left", index: int = 0, t_ns: int = 0) -> Frame:
    return Frame(
        camera_id=camera_id,
        frame_index=index,
        t_capture_monotonic_ns=t_ns,
        image=np.zeros((64, 64, 3), dtype=np.uint8),
        width=64,
        height=64,
        pixfmt="BGR3",
    )


_AMPLE_SPACE = SimpleNamespace(total=500 * 1024**3, used=0, free=200 * 1024**3)


def _disk_patch():
    return patch(
        "app.pipeline.recording.session_recorder.shutil.disk_usage",
        return_value=_AMPLE_SPACE,
    )


def _has_codec() -> bool:
    import cv2

    temp_dir = Path(tempfile.mkdtemp())
    try:
        path = temp_dir / "probe.avi"
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


requires_codec = pytest.mark.skipif(
    not _has_codec(),
    reason="No video codec available",
)

_RECORDING_THREAD_NAMES = {"recording-frame-writer", "DiskSpaceMonitor"}


def _recording_threads() -> list[threading.Thread]:
    """Return live non-daemon threads with recording-related names."""
    return [
        t for t in threading.enumerate()
        if t.is_alive() and t.name in _RECORDING_THREAD_NAMES
    ]


def _stop_service(service: RecordingServiceImpl) -> None:
    """Ensure service worker and session are fully stopped."""
    try:
        if service.is_recording_session():
            service.stop_session()
    except Exception:
        pass
    service._frame_worker.stop(drain=False, timeout=2.0)


class TestStartRollback:
    """start_session cleans up state on failure."""

    def test_rollback_on_session_recorder_failure(self):
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = _config()

        with patch(
            "app.services.recording.session_lifecycle.SessionRecorder",
            side_effect=RuntimeError("boom"),
        ):
            with pytest.raises(RuntimeError, match="boom"):
                service.start_session("s1", config)

        assert not service.is_recording_session()
        assert service.get_session_dir() is None
        assert service._frame_worker._thread is None or not service._frame_worker._thread.is_alive()
        assert _recording_threads() == []

    @requires_codec
    def test_rollback_leaves_no_subscriptions(self):
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = _config()
        temp_dir = Path(tempfile.mkdtemp())

        try:
            service.set_record_directory(temp_dir)
            with patch(
                "app.services.recording.session_lifecycle.SessionEvidenceJournal",
                side_effect=RuntimeError("journal fail"),
            ):
                with pytest.raises(RuntimeError):
                    service.start_session("s1", config)

            assert not service._subscribed
            assert _recording_threads() == []
        finally:
            _stop_service(service)
            shutil.rmtree(temp_dir, ignore_errors=True)


@requires_codec
class TestPitchFIFOBoundaries:
    """Pitch start/stop happen in FIFO order relative to frames."""

    def test_frames_before_pitch_start_go_to_preroll_not_pitch(self):
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = _config()
        temp_dir = Path(tempfile.mkdtemp())

        try:
            service.set_record_directory(temp_dir)
            with _disk_patch():
                service.start_session("s1", config)

            for i in range(5):
                service.record_frame("left", _frame("left", i, i * 1_000_000))

            service.start_pitch("pitch_001")
            assert service.is_recording_pitch()

            for i in range(5, 10):
                service.record_frame("left", _frame("left", i, i * 1_000_000))

            pitch_dir = service.stop_pitch()
            assert pitch_dir is not None

            service.stop_session()
        finally:
            _stop_service(service)
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_frames_after_pitch_stop_not_in_pitch(self):
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = _config()
        temp_dir = Path(tempfile.mkdtemp())

        try:
            service.set_record_directory(temp_dir)
            with _disk_patch():
                service.start_session("s1", config)

            service.start_pitch("pitch_001")
            service.record_frame("left", _frame("left", 0, 0))
            service.stop_pitch()
            assert not service.is_recording_pitch()

            service.record_frame("left", _frame("left", 1, 1_000_000))
            service.stop_session()
        finally:
            _stop_service(service)
            shutil.rmtree(temp_dir, ignore_errors=True)


@requires_codec
class TestSessionPitchMetadataFinalization:
    """Session and pitch lifecycle metadata is captured correctly."""

    def test_session_stop_includes_event_metadata(self):
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = _config()
        temp_dir = Path(tempfile.mkdtemp())

        try:
            service.set_record_directory(temp_dir)
            with _disk_patch():
                service.start_session("test_meta", config, mode="coaching")
            service.set_manual_speed_mph(85.0)
            service.set_calibration_context("profile_1", {"type": "quick"})
            bundle = service.stop_session()
            assert bundle.session_dir is not None
        finally:
            _stop_service(service)
            shutil.rmtree(temp_dir, ignore_errors=True)


@requires_codec
class TestStopPauseErrorCleanup:
    """Cleanup on stop, pause, and error paths."""

    def test_pause_clears_preroll_and_stops_pitch(self):
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = _config()
        temp_dir = Path(tempfile.mkdtemp())

        try:
            service.set_record_directory(temp_dir)
            with _disk_patch():
                service.start_session("s1", config)

            for i in range(3):
                service.record_frame("left", _frame("left", i, i * 1_000_000))

            service.start_pitch("p1")
            service.pause_session()
            assert service.is_paused()
            assert not service.is_recording_pitch()

            assert len(service._pre_roll_buffer["left"]) == 0

            service.resume_session()
            assert not service.is_paused()

            service.stop_session()
        finally:
            _stop_service(service)
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_stop_session_with_active_pitch_cleans_up(self):
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = _config()
        temp_dir = Path(tempfile.mkdtemp())

        try:
            service.set_record_directory(temp_dir)
            with _disk_patch():
                service.start_session("s1", config)

            service.start_pitch("p1")
            service.record_frame("left", _frame("left", 0, 0))
            bundle = service.stop_session()
            assert not service.is_recording_session()
            assert not service.is_recording_pitch()
            assert bundle.session_dir is not None
        finally:
            _stop_service(service)
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_resume_without_pause_is_noop(self):
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = _config()
        temp_dir = Path(tempfile.mkdtemp())

        try:
            service.set_record_directory(temp_dir)
            with _disk_patch():
                service.start_session("s1", config)
            service.resume_session()
            service.stop_session()
        finally:
            _stop_service(service)
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestFrameWriterStats:
    """get_frame_writer_stats reports accurate metrics."""

    def test_stats_after_submissions(self):
        bus = EventBus()
        service = RecordingServiceImpl(bus)

        stats = service.get_frame_writer_stats()
        assert stats["submitted"] == 0
        assert stats["drop_policy"] == "drop_newest"

    @requires_codec
    def test_stats_count_after_recording(self):
        bus = EventBus()
        service = RecordingServiceImpl(bus)
        config = _config()
        temp_dir = Path(tempfile.mkdtemp())

        try:
            service.set_record_directory(temp_dir)
            with _disk_patch():
                service.start_session("s1", config)

            for i in range(3):
                service.record_frame("left", _frame("left", i, i * 1_000_000))

            service.stop_session()
            stats = service.get_frame_writer_stats()
            assert stats["submitted"] >= 3
            assert stats["dropped"] == 0
        finally:
            _stop_service(service)
            shutil.rmtree(temp_dir, ignore_errors=True)


class TestNoThreadLeaks:
    """Final check: no recording worker threads survive the test suite."""

    def test_no_leaked_recording_threads(self):
        leaked = _recording_threads()
        assert leaked == [], f"Leaked threads: {[t.name for t in leaked]}"
