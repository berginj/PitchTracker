"""Lifecycle helpers for the pipeline orchestrator."""

from __future__ import annotations

from typing import Any, Optional

from log_config.logger import get_logger

logger = get_logger(__name__)


def shutdown_pipeline(orchestrator: Any) -> None:
    """Stop recording/capture independently and clear producer metadata."""
    recording_error: Optional[Exception] = None
    try:
        if orchestrator._recording_active:
            orchestrator.stop_recording()
    except Exception as exc:  # pragma: no cover - failure-injection path
        recording_error = exc
        logger.exception("Failed to stop recording during pipeline shutdown")
    finally:
        try:
            orchestrator.stop_capture()
        finally:
            orchestrator._event_coordinator.unsubscribe()
            orchestrator._propagate_session_id(None)
    if recording_error is not None:
        raise recording_error


def start_capture_runtime(orchestrator: Any, config: Any, left_serial: str, right_serial: str) -> None:
    """Subscribe runtime consumers and start capture with rollback on failure."""
    coordinator = orchestrator._event_coordinator
    coordinator.set_pitch_tracker(orchestrator._pitch_tracker)
    coordinator.set_rig_profile(orchestrator._active_rig_profile)
    coordinator.set_config(config)
    coordinator.subscribe()
    try:
        orchestrator._capture_service.start_capture(config, left_serial, right_serial)
        orchestrator._capturing = True
        logger.info("Capture started")
    except Exception:
        try:
            orchestrator._capture_service.stop_capture()
        except Exception:
            logger.exception("Capture rollback failed")
        coordinator.unsubscribe()
        orchestrator._detection_started = False
        orchestrator._capturing = False
        orchestrator._propagate_session_id(None)
        raise


def stop_recording_pipeline(orchestrator: Any) -> Any:
    """Stop analysis/session and clear recording metadata even on failure."""
    if orchestrator._recording_service is None:
        raise RuntimeError("Recording service not initialized")
    try:
        if orchestrator._analysis_service is not None:
            orchestrator._analysis_service.stop_analysis()
        return orchestrator._recording_service.stop_session()
    finally:
        orchestrator._recording_active = False
        orchestrator._recording_paused = False
        orchestrator._propagate_session_id(None)
