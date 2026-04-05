"""Structured calibration error helpers for the setup wizard."""

from __future__ import annotations

from typing import Any

from exceptions import (
    CalibrationExecutionError,
    CalibrationInputError,
    CalibrationPersistenceError,
)


def build_calibration_error_payload(exc: Exception) -> dict[str, Any]:
    """Convert calibration exceptions into UI-friendly payloads."""
    if isinstance(exc, CalibrationInputError):
        return {
            "kind": "input",
            "title": "Calibration Input Error",
            "tone": "warning",
            "message": str(exc),
        }
    if isinstance(exc, CalibrationPersistenceError):
        return {
            "kind": "persistence",
            "title": "Calibration Save Error",
            "tone": "error",
            "message": str(exc),
        }
    if isinstance(exc, CalibrationExecutionError):
        return {
            "kind": "execution",
            "title": "Calibration Failed",
            "tone": "error",
            "message": str(exc),
        }
    return {
        "kind": "unexpected",
        "title": "Calibration Error",
        "tone": "error",
        "message": str(exc),
    }
