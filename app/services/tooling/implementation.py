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
    TrainingReportRequest,
    TrainingReportResult,
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

        stdout = completed.stdout.strip()
        stderr = completed.stderr.strip()
        if not stdout:
            details = stderr or f"worker exited with code {completed.returncode}"
            raise RuntimeError(f"{task} produced no response: {details}")

        try:
            response = json.loads(stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"{task} returned invalid JSON: {exc}\nstdout:\n{stdout}\nstderr:\n{stderr}"
            ) from exc

        if not response.get("ok", False):
            error_text = str(response.get("error", f"{task} failed"))
            worker_stdout = response.get("stdout")
            worker_stderr = response.get("stderr")
            worker_traceback = response.get("traceback")

            details: list[str] = [error_text]
            if worker_stdout:
                details.append(f"worker stdout:\n{worker_stdout}")
            if worker_stderr:
                details.append(f"worker stderr:\n{worker_stderr}")
            if worker_traceback:
                details.append(f"worker traceback:\n{worker_traceback}")
            raise RuntimeError("\n\n".join(details))

        return dict(response["result"])


_default_tooling_service: ToolingService | None = None


def get_tooling_service() -> ToolingService:
    """Return the default tooling service singleton."""
    global _default_tooling_service
    if _default_tooling_service is None:
        _default_tooling_service = SubprocessToolingService()
    return _default_tooling_service
