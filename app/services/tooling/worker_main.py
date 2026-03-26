"""Worker entry point for process-backed tooling tasks."""

from __future__ import annotations

import contextlib
import io
import json
import sys
import traceback
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Callable


def _json_safe(value: Any) -> Any:
    """Convert values to JSON-safe structures."""
    if is_dataclass(value):
        return _json_safe(asdict(value))
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "item") and callable(getattr(value, "item")):
        try:
            return value.item()
        except Exception:  # noqa: BLE001 - fall through to raw value
            return value
    return value


def _handle_validate_environment(_payload: dict[str, Any]) -> dict[str, Any]:
    from startup_validator import validate_environment

    errors, warnings = validate_environment()
    return {"errors": errors, "warnings": warnings}


def _handle_build_training_report(payload: dict[str, Any]) -> dict[str, Any]:
    from contracts.tooling import TrainingReportRequest, TrainingReportResult
    from record.training_report import build_training_report

    request = TrainingReportRequest.from_payload(payload)
    result = build_training_report(
        session_dir=request.session_dir,
        config_path=request.config_path,
        roi_path=request.roi_path,
        stride=request.stride,
        skip_detection=request.skip_detection,
        skip_brightness=request.skip_brightness,
        source=request.source,
        report_id=request.report_id,
        created_utc=request.created_utc,
    )
    return TrainingReportResult(payload=result).to_payload()


def _handle_run_calibration(payload: dict[str, Any]) -> dict[str, Any]:
    from calib.quick_calibrate import (
        _calibrate,
        _parse_pattern,
        _save_calibration_file,
        _write_config,
        quick_calibrate,
    )
    from contracts.tooling import CalibrationRequest, CalibrationResult

    request = CalibrationRequest.from_payload(payload)
    pattern_size = _parse_pattern(request.pattern)
    if request.mode.lower() == "quick":
        updates = quick_calibrate(
            left_paths=list(request.left_paths),
            right_paths=list(request.right_paths),
            pattern_size=pattern_size,
            square_mm=request.square_mm,
        )
    else:
        updates = _calibrate(
            left_paths=list(request.left_paths),
            right_paths=list(request.right_paths),
            pattern_size=pattern_size,
            square_mm=request.square_mm,
        )

    if request.write_updates:
        _write_config(request.config_path, updates)
        _save_calibration_file(updates)

    return CalibrationResult.from_updates(updates).to_payload()


def _handle_analyze_alignment(payload: dict[str, Any]) -> dict[str, Any]:
    import cv2
    from analysis.camera_alignment import analyze_alignment, predict_calibration_quality
    from contracts.tooling import AlignmentAnalysisRequest, AlignmentAnalysisResult

    request = AlignmentAnalysisRequest.from_payload(payload)
    left_img = cv2.imread(str(request.left_image_path), cv2.IMREAD_COLOR)
    right_img = cv2.imread(str(request.right_image_path), cv2.IMREAD_COLOR)
    if left_img is None:
        raise FileNotFoundError(f"Could not load left image: {request.left_image_path}")
    if right_img is None:
        raise FileNotFoundError(f"Could not load right image: {request.right_image_path}")

    alignment = analyze_alignment(left_img, right_img, max_features=request.max_features)
    prediction = predict_calibration_quality(alignment)
    result = AlignmentAnalysisResult(
        alignment=_json_safe(asdict(alignment)),
        prediction=_json_safe(prediction),
    )
    return result.to_payload()


HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any]]] = {
    "validate_environment": _handle_validate_environment,
    "build_training_report": _handle_build_training_report,
    "run_calibration": _handle_run_calibration,
    "analyze_alignment": _handle_analyze_alignment,
}


def main() -> None:
    request = json.load(sys.stdin)
    task = str(request["task"])
    payload = dict(request.get("payload", {}))
    stdout_buffer = io.StringIO()
    stderr_buffer = io.StringIO()

    try:
        handler = HANDLERS[task]
    except KeyError as exc:
        response = {"ok": False, "error": f"Unknown tooling task: {task}"}
        print(json.dumps(response))
        raise SystemExit(1) from exc

    try:
        with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
            result = handler(payload)
        response = {
            "ok": True,
            "result": _json_safe(result),
            "stdout": stdout_buffer.getvalue(),
            "stderr": stderr_buffer.getvalue(),
        }
    except Exception as exc:  # noqa: BLE001 - return serialized worker failures
        response = {
            "ok": False,
            "error": str(exc),
            "stdout": stdout_buffer.getvalue(),
            "stderr": stderr_buffer.getvalue(),
            "traceback": traceback.format_exc(),
        }

    print(json.dumps(response))


if __name__ == "__main__":
    main()
