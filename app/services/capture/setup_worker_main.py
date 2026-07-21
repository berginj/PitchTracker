"""One-shot camera-owning worker for stereo setup capture.

This process is deliberately disposable.  If a DirectShow/OpenCV call stalls,
the parent terminates this process rather than attempting to kill a Python
thread that owns a native camera handle.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np

from contracts.setup_capture import (
    SetupCaptureFailureCode,
    SetupCapturePurpose,
    SetupCaptureRequest,
    SetupCaptureResult,
    SetupFrameRecord,
)


class SetupCaptureWorkerError(RuntimeError):
    def __init__(self, code: SetupCaptureFailureCode, message: str):
        super().__init__(message)
        self.code = code


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item") and callable(getattr(value, "item")):
        try:
            return value.item()
        except Exception:  # noqa: BLE001 - best-effort JSON conversion
            return str(value)
    return value


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _camera_factory(backend: str):
    if backend == "sim":
        from capture.simulated_camera import SimulatedCamera

        return SimulatedCamera
    if backend == "opencv":
        from capture.opencv_backend import OpenCVCamera

        return OpenCVCamera
    from capture.uvc_backend import UvcCamera

    return UvcCamera


def _record(frame, image_path: Path | None = None) -> SetupFrameRecord:
    return SetupFrameRecord(
        camera_id=str(frame.camera_id),
        frame_index=int(frame.frame_index),
        t_capture_monotonic_ns=int(frame.t_capture_monotonic_ns),
        width=int(frame.width),
        height=int(frame.height),
        pixfmt=str(frame.pixfmt),
        image_path=image_path,
    )


def _capture(request: SetupCaptureRequest) -> SetupCaptureResult:
    from app.pipeline.initialization import PipelineInitializer
    from configs.settings import load_config

    if request.artifact_dir is None:
        raise SetupCaptureWorkerError(
            SetupCaptureFailureCode.INVALID_RESULT,
            "artifact_dir is required for setup capture",
        )
    artifact_dir = request.artifact_dir.resolve()
    artifact_dir.mkdir(parents=True, exist_ok=True)

    config_path = request.config_path.resolve()
    if not config_path.is_file():
        raise SetupCaptureWorkerError(
            SetupCaptureFailureCode.CAMERA_CONFIG_FAILED,
            f"configuration file does not exist: {config_path}",
        )
    config_digest = _file_sha256(config_path)
    if request.config_sha256 and config_digest != request.config_sha256:
        raise SetupCaptureWorkerError(
            SetupCaptureFailureCode.INVALID_RESULT,
            "configuration changed after the setup capture request was created",
        )

    config = load_config(config_path)
    camera_type = _camera_factory(request.backend)
    left = camera_type()
    right = camera_type()
    left_frames: list[Any] = []
    right_frames: list[Any] = []
    errors_by_side = {"left": 0, "right": 0}
    modes: dict[str, dict[str, Any]] = {}
    controls: dict[str, dict[str, Any]] = {}
    started_ns = time.monotonic_ns()

    try:
        try:
            left.open(request.left_camera_id)
            right.open(request.right_camera_id)
        except Exception as exc:
            raise SetupCaptureWorkerError(
                SetupCaptureFailureCode.CAMERA_OPEN_FAILED,
                f"failed to open setup cameras: {exc}",
            ) from exc
        try:
            PipelineInitializer.configure_camera(left, config, is_left=True)
            PipelineInitializer.configure_camera(right, config, is_left=False)
        except Exception as exc:
            raise SetupCaptureWorkerError(
                SetupCaptureFailureCode.CAMERA_CONFIG_FAILED,
                f"failed to configure setup cameras: {exc}",
            ) from exc

        modes = {
            "left": _json_safe(left.get_mode() or {}),
            "right": _json_safe(right.get_mode() or {}),
        }

        def _burst(camera, side: str) -> list[Any]:
            captured: list[Any] = []
            for _ in range(request.requested_frames_per_camera):
                try:
                    # This is an advisory backend timeout.  The parent process
                    # deadline is the hard interruption boundary.
                    captured.append(camera.read_frame(1000))
                except Exception:  # noqa: BLE001 - retain partial burst evidence
                    errors_by_side[side] += 1
            return captured

        with ThreadPoolExecutor(max_workers=2, thread_name_prefix="setup-capture") as executor:
            left_future = executor.submit(_burst, left, "left")
            right_future = executor.submit(_burst, right, "right")
            left_frames = left_future.result()
            right_frames = right_future.result()

        if not left_frames or not right_frames:
            raise SetupCaptureWorkerError(
                SetupCaptureFailureCode.INSUFFICIENT_FRAMES,
                "setup capture did not receive at least one frame from each camera",
            )
        controls = {
            "left": _json_safe(left.get_controls() or {}),
            "right": _json_safe(right.get_controls() or {}),
        }
    finally:
        # Normal completion uses backend cleanup.  A driver-level stall here is
        # still bounded because the parent owns the process deadline.
        try:
            left.close()
        except Exception:  # noqa: BLE001 - parent retains terminal diagnostics
            pass
        try:
            right.close()
        except Exception:  # noqa: BLE001
            pass

    left_records = [_record(frame) for frame in left_frames]
    right_records = [_record(frame) for frame in right_frames]
    if request.purpose in {
        SetupCapturePurpose.FOCUS,
        SetupCapturePurpose.OVERLAP,
        SetupCapturePurpose.RECTIFY,
    }:
        left_path = artifact_dir / "left_last.npy"
        right_path = artifact_dir / "right_last.npy"
        np.save(left_path, left_frames[-1].image, allow_pickle=False)
        np.save(right_path, right_frames[-1].image, allow_pickle=False)
        left_records[-1] = replace(left_records[-1], image_path=left_path)
        right_records[-1] = replace(right_records[-1], image_path=right_path)

    result = SetupCaptureResult(
        correlation_id=request.correlation_id,
        purpose=request.purpose,
        assignment_generation=request.assignment_generation,
        started_monotonic_ns=started_ns,
        completed_monotonic_ns=time.monotonic_ns(),
        requested_frames_per_camera=request.requested_frames_per_camera,
        left_frames=tuple(left_records),
        right_frames=tuple(right_records),
        modes=modes,
        controls=controls,
        errors_by_side=errors_by_side,
        config_sha256=config_digest,
        artifact_dir=artifact_dir,
    )
    temp_manifest = artifact_dir / "result.json.tmp"
    manifest = artifact_dir / "result.json"
    temp_manifest.write_text(json.dumps(result.to_payload(), sort_keys=True), encoding="utf-8")
    temp_manifest.replace(manifest)
    return result


def main() -> None:
    request_envelope = json.load(sys.stdin)
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()
    try:
        request = SetupCaptureRequest.from_payload(dict(request_envelope["payload"]))
        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
            result = _capture(request)
        response = {
            "ok": True,
            "result": result.to_payload(),
            "stdout": stdout_buffer.getvalue(),
            "stderr": stderr_buffer.getvalue(),
        }
    except Exception as exc:  # noqa: BLE001 - serialize worker failures
        code = getattr(exc, "code", SetupCaptureFailureCode.WORKER_CRASHED)
        response = {
            "ok": False,
            "error": str(exc),
            "error_type": exc.__class__.__name__,
            "failure_code": code.value if isinstance(code, SetupCaptureFailureCode) else str(code),
            "stdout": stdout_buffer.getvalue(),
            "stderr": stderr_buffer.getvalue(),
            "traceback": traceback.format_exc(),
        }
    print(json.dumps(_json_safe(response)))


if __name__ == "__main__":
    main()
