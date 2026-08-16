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
