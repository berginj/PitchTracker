"""Tests for structured calibration error payloads."""

from exceptions import (
    CalibrationExecutionError,
    CalibrationInputError,
    CalibrationPersistenceError,
)
from ui.setup.steps.calibration_errors import build_calibration_error_payload


def test_build_calibration_error_payload_for_input_error() -> None:
    payload = build_calibration_error_payload(CalibrationInputError("missing image pair"))

    assert payload["kind"] == "input"
    assert payload["title"] == "Calibration Input Error"
    assert payload["tone"] == "warning"


def test_build_calibration_error_payload_for_save_error() -> None:
    payload = build_calibration_error_payload(CalibrationPersistenceError("config write failed"))

    assert payload["kind"] == "persistence"
    assert payload["title"] == "Calibration Save Error"
    assert payload["tone"] == "error"


def test_build_calibration_error_payload_for_execution_error() -> None:
    payload = build_calibration_error_payload(CalibrationExecutionError("corner detection failed"))

    assert payload["kind"] == "execution"
    assert payload["title"] == "Calibration Failed"
    assert payload["tone"] == "error"
