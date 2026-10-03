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
            if not orchestrator._recording_active:
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
        rollback_failed = False
        try:
            orchestrator._capture_service.stop_capture()
        except Exception:
            rollback_failed = True
            logger.exception("Capture rollback failed")
        coordinator.unsubscribe()
        orchestrator._detection_started = False
        orchestrator._capturing = rollback_failed
        orchestrator._capture_stopping = rollback_failed
        orchestrator._propagate_session_id(None)
        raise


def stop_capture_runtime(orchestrator: Any) -> None:
    """Retain capture ownership when a reader or reconnect has not terminated."""
    if not orchestrator._capturing:
        return
    orchestrator._capture_stopping = True
    if orchestrator._capture_service is not None:
        orchestrator._capture_service.stop_capture()
    if orchestrator._detection_started and orchestrator._detection_service is not None:
        orchestrator._detection_service.stop_detection()
        orchestrator._detection_started = False
    orchestrator._event_coordinator.unsubscribe()
    orchestrator._capturing = False
    orchestrator._capture_stopping = False


def stop_recording_pipeline(orchestrator: Any) -> Any:
    """Finalize producers and retain failed stops until every owner is terminal."""
    if orchestrator._recording_service is None:
        raise RuntimeError("Recording service not initialized")
    orchestrator._recording_stopping = True
    suspend_recording_pipeline(orchestrator)
    try:
        if orchestrator._analysis_service is not None:
            orchestrator._analysis_service.stop_analysis()
    except Exception:
        # Close pitch writers independently, but keep terminal-result delivery
        # and session ownership while accepted analysis is still completing.
        try:
            orchestrator._recording_service.pause_session()
        except Exception:
            logger.exception("Failed to pause writers during analysis stop failure")
        raise
    bundle = orchestrator._recording_service.stop_session()
    orchestrator._recording_active = False
    orchestrator._recording_paused = False
    orchestrator._recording_stopping = False
    orchestrator._propagate_session_id(None)
    return bundle


def suspend_recording_pipeline(orchestrator: Any) -> None:
    """Fence new pitch input before finalizing the current tracker snapshot."""
    orchestrator._event_coordinator.suspend_tracking()
    if orchestrator._recording_service is not None:
        orchestrator._recording_service.suspend_inputs()
    if orchestrator._detection_started and orchestrator._detection_service is not None:
        orchestrator._detection_service.stop_detection()
        orchestrator._detection_started = False
    if orchestrator._pitch_tracker is not None:
        orchestrator._pitch_tracker.force_end()


def pause_recording_pipeline(orchestrator: Any) -> None:
    """Drain accepted pitch analysis before pausing recording subscriptions."""
    suspend_recording_pipeline(orchestrator)
    if orchestrator._analysis_service is not None:
        orchestrator._analysis_service.pause_analysis()
    orchestrator._recording_service.pause_session()
    orchestrator._recording_paused = True


def resume_recording_pipeline(orchestrator: Any) -> None:
    """Restore consumers before input, rolling partial resumes back to pause."""
    try:
        orchestrator._recording_service.resume_session()
        if orchestrator._analysis_service is not None:
            orchestrator._analysis_service.resume_analysis()
        orchestrator._event_coordinator.resume_tracking()
        orchestrator._detection_started = True
        orchestrator._detection_service.start_detection()
    except Exception:
        try:
            pause_recording_pipeline(orchestrator)
        except Exception:
            orchestrator._recording_stopping = True
            logger.exception("Resume rollback failed; session stop remains retryable")
        raise
    orchestrator._recording_paused = False
