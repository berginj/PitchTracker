"""Tests for tooling-service exception mapping."""

from pathlib import Path

import pytest

from app.services.tooling.implementation import SubprocessToolingService
from exceptions import (
    CalibrationExecutionError,
    CalibrationInputError,
    CalibrationPersistenceError,
)


def test_calibration_value_error_maps_to_input_error() -> None:
    service = SubprocessToolingService(project_root=Path.cwd())

    with pytest.raises(CalibrationInputError):
        service._raise_task_error("run_calibration", "bad pattern", error_type="ValueError")


def test_calibration_os_error_maps_to_persistence_error() -> None:
    service = SubprocessToolingService(project_root=Path.cwd())

    with pytest.raises(CalibrationPersistenceError):
        service._raise_task_error("run_calibration", "write failed", error_type="OSError")


def test_unknown_calibration_failure_maps_to_execution_error() -> None:
    service = SubprocessToolingService(project_root=Path.cwd())

    with pytest.raises(CalibrationExecutionError):
        service._raise_task_error("run_calibration", "worker crashed", error_type="RuntimeError")
