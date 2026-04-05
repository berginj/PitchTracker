"""Background worker for setup calibration."""

from __future__ import annotations

from pathlib import Path
from typing import List

from PySide6 import QtCore

from app.services.tooling import get_tooling_service
from contracts.tooling import CalibrationRequest
from exceptions import (
    CalibrationExecutionError,
    CalibrationInputError,
    CalibrationPersistenceError,
)
from ui.setup.steps.calibration_errors import build_calibration_error_payload


class CalibrationWorker(QtCore.QThread):
    """Background worker for running calibration."""

    finished = QtCore.Signal(dict)  # Emits calibration results
    error = QtCore.Signal(dict)  # Emits structured error payload

    def __init__(
        self,
        left_paths: List[Path],
        right_paths: List[Path],
        pattern: str,
        square_mm: float,
        config_path: Path,
        quick_mode: bool = False,
    ):
        super().__init__()
        self.left_paths = left_paths
        self.right_paths = right_paths
        self.pattern = pattern
        self.square_mm = square_mm
        self.config_path = config_path
        self.quick_mode = quick_mode

    def run(self):
        """Run calibration in background thread."""
        try:
            result = get_tooling_service().run_calibration(
                CalibrationRequest(
                    left_paths=tuple(self.left_paths),
                    right_paths=tuple(self.right_paths),
                    pattern=self.pattern,
                    square_mm=self.square_mm,
                    config_path=self.config_path,
                    mode="quick" if self.quick_mode else "full",
                    write_updates=True,
                )
            )
            self.finished.emit(result.to_payload())
        except (
            CalibrationInputError,
            CalibrationPersistenceError,
            CalibrationExecutionError,
        ) as exc:
            self.error.emit(build_calibration_error_payload(exc))
        except Exception as exc:
            self.error.emit(build_calibration_error_payload(exc))
