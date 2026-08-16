"""Subprocess-backed tooling service implementation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from contracts.tooling import (
    AlignmentAnalysisRequest,
    AlignmentAnalysisResult,
    CalibrationRequest,
    CalibrationResult,
    EnvironmentValidationResult,
    PhysicalValidationRequest,
    PhysicalValidationResult,
    TrainingReportRequest,
    TrainingReportResult,
)
from exceptions import (
    CalibrationExecutionError,
    CalibrationInputError,
    CalibrationPersistenceError,
)

from .interface import ToolingService


class SubprocessToolingService(ToolingService):
    """Execute heavyweight tooling tasks in one-shot worker subprocesses."""

    def __init__(
        self,
        python_executable: str | None = None,
        project_root: Path | None = None,
    ) -> None:
        self._python_executable = python_executable or sys.executable
        self._project_root = project_root or Path(__file__).resolve().parents[3]

    def validate_environment(self) -> EnvironmentValidationResult:
        payload = self._run_task("validate_environment", {})
        return EnvironmentValidationResult.from_payload(payload)

    def build_training_report(self, request: TrainingReportRequest) -> TrainingReportResult:
        payload = self._run_task(
            "build_training_report",
            request.to_payload(),
            timeout_seconds=300,
        )
        return TrainingReportResult.from_payload(payload)

    def run_calibration(self, request: CalibrationRequest) -> CalibrationResult:
        payload = self._run_task(
            "run_calibration",
            request.to_payload(),
            timeout_seconds=300,
        )
        return CalibrationResult.from_payload(payload)

    def analyze_alignment(self, request: AlignmentAnalysisRequest) -> AlignmentAnalysisResult:
        payload = self._run_task(
            "analyze_alignment",
            request.to_payload(),
            timeout_seconds=120,
        )
        return AlignmentAnalysisResult.from_payload(payload)

    def validate_physical_dataset(self, request: PhysicalValidationRequest) -> PhysicalValidationResult:
        payload = self._run_task(
            "validate_physical_dataset",
            request.to_payload(),
            timeout_seconds=300,
        )
        return PhysicalValidationResult.from_payload(payload)

    def _run_task(
        self,
        task: str,
        payload: dict[str, Any],
        timeout_seconds: int = 60,
    ) -> dict[str, Any]:
        command = [
            self._python_executable,
            "-m",
            "app.services.tooling.worker_main",
        ]
        request_envelope = {"task": task, "payload": payload}

        try:
            completed = subprocess.run(
                command,
                input=json.dumps(request_envelope),
                capture_output=True,
                text=True,
                encoding="utf-8",
                cwd=str(self._project_root),
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            self._raise_task_error(
                task,
                f"{task} timed out after {timeout_seconds} seconds",
                error_type=exc.__class__.__name__,
            )

        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        if not stdout:
            details = stderr or f"worker exited with code {completed.returncode}"
            self._raise_task_error(
                task,
                f"{task} produced no response: {details}",
                error_type="NoWorkerResponse",
            )

        try:
            response = json.loads(stdout)
        except json.JSONDecodeError as exc:
            self._raise_task_error(
                task,
                f"{task} returned invalid JSON: {exc}\nstdout:\n{stdout}\nstderr:\n{stderr}",
                error_type=exc.__class__.__name__,
            )

        if not response.get("ok", False):
            error_text = str(response.get("error", f"{task} failed"))
            error_type = response.get("error_type")
            worker_stdout = response.get("stdout")
            worker_stderr = response.get("stderr")
            worker_traceback = response.get("traceback")

            error_details: list[str] = [error_text]
            if worker_stdout:
                error_details.append(f"worker stdout:\n{worker_stdout}")
            if worker_stderr:
                error_details.append(f"worker stderr:\n{worker_stderr}")
            if worker_traceback:
                error_details.append(f"worker traceback:\n{worker_traceback}")
            self._raise_task_error(
                task,
                "\n\n".join(error_details),
                error_type=str(error_type) if error_type else None,
            )

        return dict(response["result"])

    def _raise_task_error(
        self,
        task: str,
        message: str,
        *,
        error_type: str | None = None,
    ) -> None:
        """Raise task-specific exceptions for worker failures."""
        if task != "run_calibration":
            raise RuntimeError(message)

        calibration_error_type = (error_type or "").lower()
        if calibration_error_type in {"valueerror", "filenotfounderror"}:
            raise CalibrationInputError(message)
        if calibration_error_type in {
            "permissionerror",
            "oserror",
            "isadirectoryerror",
            "notadirectoryerror",
        }:
            raise CalibrationPersistenceError(message)
        raise CalibrationExecutionError(message)


_default_tooling_service: ToolingService | None = None


def get_tooling_service() -> ToolingService:
    """Return the default tooling service singleton."""
    global _default_tooling_service
    if _default_tooling_service is None:
        _default_tooling_service = SubprocessToolingService()
    return _default_tooling_service
