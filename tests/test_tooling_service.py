"""Tests for the subprocess-backed tooling service."""

from __future__ import annotations

import json
import subprocess

import pytest

from app.services.tooling import SubprocessToolingService
from contracts.tooling import EnvironmentValidationResult


def test_validate_environment_uses_json_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run(command, **kwargs):  # noqa: ANN001 - matches subprocess.run surface
        captured["command"] = command
        captured["input"] = kwargs["input"]
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {
                    "ok": True,
                    "result": {"errors": [], "warnings": ["camera missing"]},
                    "stdout": "",
                    "stderr": "",
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    service = SubprocessToolingService(python_executable="python")
    result = service.validate_environment()

    assert isinstance(result, EnvironmentValidationResult)
    assert result.errors == []
    assert result.warnings == ["camera missing"]
    assert captured["command"] == ["python", "-m", "app.services.tooling.worker_main"]
    assert json.loads(str(captured["input"])) == {
        "task": "validate_environment",
        "payload": {},
    }


def test_validate_environment_raises_with_worker_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_run(command, **kwargs):  # noqa: ANN001 - matches subprocess.run surface
        return subprocess.CompletedProcess(
            command,
            1,
            stdout=json.dumps(
                {
                    "ok": False,
                    "error": "dependency check failed",
                    "stdout": "partial log",
                    "stderr": "trace line",
                    "traceback": "Traceback...",
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    service = SubprocessToolingService(python_executable="python")

    with pytest.raises(RuntimeError) as exc_info:
        service.validate_environment()

    message = str(exc_info.value)
    assert "dependency check failed" in message
    assert "worker stdout" in message
    assert "worker stderr" in message
    assert "worker traceback" in message
