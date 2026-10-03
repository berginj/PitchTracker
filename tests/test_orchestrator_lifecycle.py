"""Failure-injection tests for orchestrator lifecycle boundaries."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.orchestrator.lifecycle import (
    resume_recording_pipeline, shutdown_pipeline, start_capture_runtime,
    stop_capture_runtime, stop_recording_pipeline,
)


def _runtime_fake() -> MagicMock:
    fake = MagicMock()
    fake._event_coordinator = MagicMock()
    fake._capture_service = MagicMock()
    fake._pitch_tracker = MagicMock()
    fake._active_rig_profile = MagicMock()
    fake._detection_started = False
    fake._capturing = False
    fake._propagate_session_id = MagicMock()
    return fake


def test_capture_start_failure_unsubscribes_and_stops_partial_capture() -> None:
    fake = _runtime_fake()
    fake._capture_service.start_capture.side_effect = RuntimeError("camera open failed")

    with pytest.raises(RuntimeError, match="camera open failed"):
        start_capture_runtime(fake, MagicMock(), "left", "right")

    fake._capture_service.stop_capture.assert_called_once_with()
    fake._event_coordinator.unsubscribe.assert_called_once_with()
    fake._propagate_session_id.assert_called_once_with(None)
    assert fake._capturing is False


def test_recording_stop_retains_state_when_writer_fails() -> None:
    fake = _runtime_fake()
    fake._recording_active = True
    fake._recording_paused = True
    fake._recording_service = MagicMock()
    fake._analysis_service = MagicMock()
    fake._recording_service.stop_session.side_effect = OSError("writer close failed")

    with pytest.raises(OSError, match="writer close failed"):
        stop_recording_pipeline(fake)

    fake._analysis_service.stop_analysis.assert_called_once_with()
    fake._propagate_session_id.assert_not_called()
    assert fake._recording_active is True
    assert fake._recording_stopping is True


def test_analysis_failure_pauses_writers_and_shutdown_retries() -> None:
    fake = _runtime_fake()
    fake._recording_active = True
    fake._analysis_service.stop_analysis.side_effect = [RuntimeError("still draining"), None]
    fake.stop_recording.side_effect = lambda: stop_recording_pipeline(fake)
    with pytest.raises(RuntimeError, match="still draining"):
        shutdown_pipeline(fake)
    fake._recording_service.pause_session.assert_called_once_with()
    fake._recording_service.stop_session.assert_not_called()
    fake._propagate_session_id.assert_not_called()
    assert fake._recording_active
    shutdown_pipeline(fake)
    fake._recording_service.stop_session.assert_called_once_with()
    assert not fake._recording_active


def test_stop_finalizes_tracker_before_draining_analysis() -> None:
    fake = _runtime_fake()
    steps: list[str] = []
    fake._recording_active = True
    fake._detection_started = True
    fake._event_coordinator.suspend_tracking.side_effect = lambda: steps.append("fence")
    fake._detection_service.stop_detection.side_effect = lambda: steps.append("detection")
    fake._pitch_tracker.force_end.side_effect = lambda: steps.append("pitch_end")
    fake._analysis_service.stop_analysis.side_effect = lambda: steps.append("analysis_drain")
    fake._recording_service.stop_session.side_effect = lambda: steps.append("recording_stop")
    stop_recording_pipeline(fake)
    assert steps == ["fence", "detection", "pitch_end", "analysis_drain", "recording_stop"]


def test_capture_rollback_failure_remains_owned_for_retry() -> None:
    fake = _runtime_fake()
    fake._capture_service.start_capture.side_effect = RuntimeError("open failed")
    fake._capture_service.stop_capture.side_effect = [RuntimeError("reader alive"), None]
    with pytest.raises(RuntimeError, match="open failed"):
        start_capture_runtime(fake, MagicMock(), "left", "right")
    assert fake._capturing and fake._capture_stopping
    stop_capture_runtime(fake)
    assert not fake._capturing and not fake._capture_stopping


def test_partial_detection_resume_rolls_back_to_paused_consumers() -> None:
    fake = _runtime_fake()
    fake._recording_active = True
    fake._recording_paused = True
    fake._recording_stopping = False
    fake._detection_service.start_detection.side_effect = RuntimeError("partial start")
    with pytest.raises(RuntimeError, match="partial start"):
        resume_recording_pipeline(fake)
    fake._detection_service.stop_detection.assert_called_once_with()
    fake._recording_service.pause_session.assert_called_once_with()
    fake._analysis_service.pause_analysis.assert_called_once_with()
    fake._event_coordinator.suspend_tracking.assert_called_once_with()
    assert fake._recording_active and fake._recording_paused
    assert not fake._detection_started and not fake._recording_stopping


def test_resume_rollback_failure_retains_detection_until_stop_retry() -> None:
    fake = _runtime_fake()
    fake._recording_active = True
    fake._recording_paused = True
    fake._detection_service.start_detection.side_effect = RuntimeError("partial start")
    fake._detection_service.stop_detection.side_effect = [RuntimeError("worker alive"), None]
    with pytest.raises(RuntimeError, match="partial start"):
        resume_recording_pipeline(fake)
    assert fake._recording_active and fake._recording_stopping and fake._detection_started
    stop_recording_pipeline(fake)
    assert not fake._recording_active and not fake._detection_started
