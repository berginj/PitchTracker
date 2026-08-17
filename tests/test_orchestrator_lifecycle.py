"""Failure-injection tests for orchestrator lifecycle boundaries."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.orchestrator.lifecycle import start_capture_runtime, stop_recording_pipeline


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


def test_recording_stop_clears_state_when_writer_fails() -> None:
    fake = _runtime_fake()
    fake._recording_active = True
    fake._recording_paused = True
    fake._recording_service = MagicMock()
    fake._analysis_service = MagicMock()
    fake._recording_service.stop_session.side_effect = OSError("writer close failed")

    with pytest.raises(OSError, match="writer close failed"):
        stop_recording_pipeline(fake)

    fake._analysis_service.stop_analysis.assert_called_once_with()
    fake._propagate_session_id.assert_called_once_with(None)
    assert fake._recording_active is False
    assert fake._recording_paused is False
