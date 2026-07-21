"""Fault-oriented tests for supervised setup capture."""

from __future__ import annotations

import hashlib
import sys
import time
from pathlib import Path

import pytest

from app.services.capture.setup_capture import SupervisedSetupCaptureService
from contracts.setup_capture import (
    SetupCaptureFailureCode,
    SetupCapturePurpose,
    SetupCaptureRequest,
    SetupCaptureResult,
    SetupCaptureState,
    SetupFrameRecord,
)
from ui.setup.providers import LiveSetupContext


def _request(
    correlation_id: str,
    *,
    deadline_ms: int = 5_000,
    backend: str = "sim",
    purpose: SetupCapturePurpose = SetupCapturePurpose.PREVIEW,
    frames: int = 2,
) -> SetupCaptureRequest:
    config_path = Path("configs/default.yaml").resolve()
    return SetupCaptureRequest(
        correlation_id=correlation_id,
        purpose=purpose,
        left_camera_id="sim-left",
        right_camera_id="sim-right",
        config_path=config_path,
        requested_frames_per_camera=frames,
        overall_deadline_ms=deadline_ms,
        backend=backend,
        config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
        assignment_generation=3,
    )


def _blocking_command() -> list[str]:
    return [sys.executable, "-c", "import sys,time; sys.stdin.read(); time.sleep(60)"]


def test_request_round_trip_preserves_evidence_binding() -> None:
    request = _request("round-trip")

    rebuilt = SetupCaptureRequest.from_payload(request.to_payload())

    assert rebuilt == request


def test_disposable_worker_captures_simulated_pair(tmp_path: Path) -> None:
    service = SupervisedSetupCaptureService(artifact_root=tmp_path / "jobs")
    request = _request("sim-success")

    job = service.submit(request)

    assert job.wait(10.0)
    assert job.state == SetupCaptureState.SUCCEEDED
    assert job.result is not None
    assert len(job.result.left_frames) == 2
    assert len(job.result.right_frames) == 2
    assert job.result.correlation_id == request.correlation_id
    assert not job.process_alive
    job.cleanup_artifacts()


def test_context_reduces_process_backed_focus_artifacts(tmp_path: Path) -> None:
    from app.services.catalog import CameraCatalogService

    catalog = CameraCatalogService(catalog_path=tmp_path / "catalog.json")
    devices = lambda: [
        {"serial": "sim-left", "friendly_name": "Sim Left"},
        {"serial": "sim-right", "friendly_name": "Sim Right"},
    ]
    context = LiveSetupContext(
        catalog=catalog,
        list_devices=devices,
        setup_capture_backend="sim",
    )
    context.assign("sim-left", "sim-right")
    request = context.build_capture_request(SetupCapturePurpose.FOCUS, frames=1)
    service = SupervisedSetupCaptureService(artifact_root=tmp_path / "jobs")

    job = service.submit(request)

    assert job.wait(10.0)
    assert job.result is not None
    focus = context.apply_capture_result(job.result)
    assert focus is context.last_focus
    assert context.last_left_frames[-1].image is not None
    assert context.last_right_frames[-1].image is not None
    assert context.last_capture_diagnostics["requested_frames_per_camera"] == 1
    assert context.last_capture_diagnostics["read_error_rate"] == {"left": 0.0, "right": 0.0}
    job.cleanup_artifacts()


def test_operator_cancel_reaps_forever_blocked_worker(tmp_path: Path) -> None:
    service = SupervisedSetupCaptureService(
        artifact_root=tmp_path / "jobs",
        worker_command=_blocking_command(),
    )
    job = service.submit(_request("cancel-blocked"))
    started = time.monotonic()

    assert job.cancel()
    assert job.wait(2.0)

    assert time.monotonic() - started < 2.0
    assert job.state == SetupCaptureState.CANCELLED
    assert job.terminal is not None
    assert job.terminal.failure_code == SetupCaptureFailureCode.CANCELLED_BY_OPERATOR
    assert not job.process_alive


def test_parent_deadline_reaps_forever_blocked_worker(tmp_path: Path) -> None:
    service = SupervisedSetupCaptureService(
        artifact_root=tmp_path / "jobs",
        worker_command=_blocking_command(),
    )
    started = time.monotonic()
    job = service.submit(_request("timeout-blocked", deadline_ms=150))

    assert job.wait(2.0)

    assert time.monotonic() - started < 1.5
    assert job.state == SetupCaptureState.TIMED_OUT
    assert job.terminal is not None
    assert job.terminal.failure_code == SetupCaptureFailureCode.DEADLINE_EXCEEDED
    assert not job.process_alive


def test_context_rejects_stale_assignment_without_mutating_evidence() -> None:
    context = LiveSetupContext(catalog=None)
    sentinel = object()
    context.last_sync = sentinel
    config_path = context.config_path.resolve()
    record = SetupFrameRecord("left", 1, 1, 10, 10, "GRAY8")
    result = SetupCaptureResult(
        correlation_id="stale",
        purpose=SetupCapturePurpose.SYNC,
        assignment_generation=context.assignment_generation + 1,
        started_monotonic_ns=1,
        completed_monotonic_ns=2,
        requested_frames_per_camera=1,
        left_frames=(record,),
        right_frames=(record,),
        config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
    )

    with pytest.raises(RuntimeError, match="stale setup capture"):
        context.apply_capture_result(result)

    assert context.last_sync is sentinel
    assert context.last_left_frames == []
    assert context.last_right_frames == []


def test_context_rolls_back_when_result_artifacts_cannot_be_reduced() -> None:
    context = LiveSetupContext(catalog=None)
    sentinel_frames = [object()]
    context.last_left_frames = sentinel_frames
    config_path = context.config_path.resolve()
    result = SetupCaptureResult(
        correlation_id="missing-images",
        purpose=SetupCapturePurpose.FOCUS,
        assignment_generation=context.assignment_generation,
        started_monotonic_ns=1,
        completed_monotonic_ns=2,
        requested_frames_per_camera=1,
        left_frames=(SetupFrameRecord("left", 1, 1, 10, 10, "GRAY8"),),
        right_frames=(SetupFrameRecord("right", 1, 1, 10, 10, "GRAY8"),),
        config_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
    )

    with pytest.raises(RuntimeError, match="missing its image artifact"):
        context.apply_capture_result(result)

    assert context.last_left_frames is sentinel_frames
    assert context.last_right_frames == []
