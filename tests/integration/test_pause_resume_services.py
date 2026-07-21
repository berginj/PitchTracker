"""Integration tests for pause/resume behavior across services."""

import shutil
import tempfile
import time
from pathlib import Path

from app.events.event_bus import EventBus
from app.events.event_types import (
    FrameCapturedEvent,
    PitchEndEvent,
)
from app.services.analysis import AnalysisServiceImpl
from app.services.orchestrator import PipelineOrchestrator
from app.services.recording import RecordingServiceImpl
from configs.settings import load_config
from contracts import Frame, StereoObservation


def _config():
    return load_config(Path(__file__).parent.parent.parent / "configs" / "default.yaml")


def _frame(camera_id: str, frame_index: int, timestamp_ns: int) -> Frame:
    import numpy as np

    return Frame(
        camera_id=camera_id,
        frame_index=frame_index,
        t_capture_monotonic_ns=timestamp_ns,
        image=np.zeros((32, 32, 3), dtype=np.uint8),
        width=32,
        height=32,
        pixfmt="BGR3",
    )


def _pitch_observations(base_timestamp_ns: int) -> list[StereoObservation]:
    observations: list[StereoObservation] = []
    for index in range(12):
        timestamp_ns = base_timestamp_ns + index * 10_000_000
        z_ft = 60.0 - (43.0 * index / 11.0)
        observations.append(
            StereoObservation(
                t_ns=timestamp_ns,
                left=(10.0 + index, 10.0),
                right=(12.0 + index, 10.0),
                X=0.15 * index / 11.0,
                Y=3.1 + 0.05 * index / 11.0,
                Z=z_ft,
                quality=0.9,
                confidence=0.9,
            )
        )
    return observations


def test_recording_service_pause_resume_updates_event_subscriptions() -> None:
    bus = EventBus()
    service = RecordingServiceImpl(bus)
    temp_dir = Path(tempfile.mkdtemp())

    try:
        service.set_record_directory(temp_dir)
        service.start_session("test_session", _config())

        assert bus.get_subscriber_count(FrameCapturedEvent) == 1
        assert not service.is_paused()

        service.pause_session()

        assert bus.get_subscriber_count(FrameCapturedEvent) == 0
        assert service.is_paused()

        service.resume_session()

        assert bus.get_subscriber_count(FrameCapturedEvent) == 1
        assert not service.is_paused()
    finally:
        try:
            service.stop_session()
        except Exception:
            pass
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_analysis_service_pause_resume_preserves_existing_summary() -> None:
    bus = EventBus()
    service = AnalysisServiceImpl(bus, _config())
    service.start_analysis()

    event = PitchEndEvent(
        pitch_id="pitch_001",
        observations=_pitch_observations(1_000_000_000),
        timestamp_ns=1_120_000_000,
        duration_ns=120_000_000,
    )
    bus.publish(event)
    assert service.wait_for_idle(timeout=300)
    assert service.get_session_summary().pitch_count == 1

    service.pause_analysis()
    bus.publish(
        PitchEndEvent(
            pitch_id="pitch_002",
            observations=_pitch_observations(2_000_000_000),
            timestamp_ns=2_120_000_000,
            duration_ns=120_000_000,
        )
    )
    time.sleep(0.05)
    assert service.get_session_summary().pitch_count == 1

    service.resume_analysis()
    bus.publish(
        PitchEndEvent(
            pitch_id="pitch_003",
            observations=_pitch_observations(3_000_000_000),
            timestamp_ns=3_120_000_000,
            duration_ns=120_000_000,
        )
    )
    assert service.wait_for_idle(timeout=300)
    assert service.get_session_summary().pitch_count == 2


def test_pipeline_orchestrator_pause_resume_keeps_preview_alive() -> None:
    orchestrator = PipelineOrchestrator(backend="sim")
    config = _config()
    temp_dir = Path(tempfile.mkdtemp())

    try:
        orchestrator.set_record_directory(temp_dir)
        orchestrator.start_capture(config, left_serial="left", right_serial="right")
        time.sleep(0.2)
        orchestrator.start_recording(session_name="pause_test")

        orchestrator.pause_recording()
        assert orchestrator.is_recording_paused() is True

        left_frame, right_frame = orchestrator.get_preview_frames()
        assert left_frame is not None
        assert right_frame is not None

        orchestrator.resume_recording()
        assert orchestrator.is_recording_paused() is False
    finally:
        try:
            orchestrator.stop_recording()
        except Exception:
            pass
        orchestrator.stop_capture()
        shutil.rmtree(temp_dir, ignore_errors=True)
