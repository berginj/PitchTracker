"""Read-only calibration report generation."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import numpy as np
import yaml

from calib.runtime_status import REQUIRED_MATRIX_KEYS


PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"

DEFAULT_MAX_RMS_PX = 2.0
DEFAULT_BASELINE_TOLERANCE_IN = 1.0
MM_PER_INCH = 25.4


def build_calibration_report(
    calibration_path: Path,
    config_path: Optional[Path] = None,
    measured_baseline_in: Optional[float] = None,
    max_rms_px: float = DEFAULT_MAX_RMS_PX,
    baseline_tolerance_in: float = DEFAULT_BASELINE_TOLERANCE_IN,
) -> dict[str, Any]:
    """Build a machine-readable report for a saved stereo calibration.

    The report intentionally does not mutate any files. It grades only what is
    present in the NPZ/config artifacts; field-target validation and visual
    diagnostics are later stages in the workback plan.
    """
    calibration_path = Path(calibration_path)
    config_path = Path(config_path) if config_path is not None else None

    findings: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []

    if not calibration_path.exists():
        return _finish(
            {
                "status": FAIL,
                "production_ready": False,
                "calibration_path": str(calibration_path),
                "config_path": str(config_path) if config_path else None,
                "checks": {},
                "metrics": {},
                "warnings": warnings,
                "errors": [f"Calibration file not found: {calibration_path}"],
                "findings": findings,
            }
        )

    try:
        data = np.load(calibration_path, allow_pickle=True)
    except Exception as exc:
        return _finish(
            {
                "status": FAIL,
                "production_ready": False,
                "calibration_path": str(calibration_path),
                "config_path": str(config_path) if config_path else None,
                "checks": {},
                "metrics": {},
                "warnings": warnings,
                "errors": [f"Calibration file could not be loaded: {exc}"],
                "findings": findings,
            }
        )

    keys = set(data.files)
    missing = [key for key in REQUIRED_MATRIX_KEYS if key not in keys]
    checks: dict[str, Any] = {
        "required_matrix_keys_present": not missing,
        "missing_matrix_keys": missing,
    }
    metrics: dict[str, Any] = {}

    if missing:
        errors.append(f"Calibration file is missing required matrix arrays: {', '.join(missing)}")

    calibration_mode_present = "calibration_mode" in keys
    calibration_mode = _npz_str(data, "calibration_mode", "UNKNOWN").upper()
    production_flag = _npz_bool(data, "production_ready")
    production_flag_present = "production_ready" in keys and production_flag is not None
    checks["calibration_mode_explicit"] = calibration_mode_present
    checks["full_calibration_mode"] = calibration_mode == "FULL"
    checks["production_ready_flag_explicit"] = production_flag_present
    checks["production_ready_flag"] = production_flag is True
    metrics["calibration_mode"] = calibration_mode

    if not calibration_mode_present:
        errors.append("Calibration mode metadata is missing; legacy artifacts are diagnostic-only.")
    elif calibration_mode == "QUICK":
        errors.append("Quick calibration is diagnostic-only and must not drive production tracking.")
    elif calibration_mode != "FULL":
        errors.append(f"Calibration mode {calibration_mode!r} is not FULL.")
    if not production_flag_present:
        errors.append("Explicit production_ready metadata is missing; legacy artifacts are diagnostic-only.")
    elif production_flag is not True:
        errors.append("Calibration is not marked production-ready.")

    rms = _npz_float(data, "rms_error_px")
    metrics["rms_error_px"] = rms
    rms_valid = rms is not None and np.isfinite(rms) and rms >= 0
    checks["rms_present_and_finite"] = rms_valid
    checks["rms_within_threshold"] = rms_valid and rms <= max_rms_px
    checks["max_rms_px"] = float(max_rms_px)
    if not rms_valid:
        errors.append("RMS reprojection error is missing, non-finite, or negative.")
    elif rms > max_rms_px:
        errors.append(f"RMS reprojection error {rms:.3f}px exceeds threshold {max_rms_px:.3f}px.")

    per_image_stats = _per_image_error_stats(data)
    metrics["per_image_error_stats"] = per_image_stats
    declared_sample_count = _npz_positive_int(data, "num_images_used") or _npz_positive_int(data, "num_images")
    evidence_sample_count = declared_sample_count or int(per_image_stats["count"])
    metrics["declared_sample_count"] = declared_sample_count
    metrics["evidence_sample_count"] = evidence_sample_count
    checks["calibration_sample_evidence_present"] = evidence_sample_count > 0
    if evidence_sample_count <= 0:
        errors.append("Calibration sample/evidence metadata is missing or empty.")
    if per_image_stats["count"] == 0:
        warnings.append("Per-image reprojection errors are missing.")

    baseline_in = _baseline_in(data)
    metrics["baseline_in"] = baseline_in
    if baseline_in is None:
        warnings.append("Baseline could not be derived from calibration.")
    elif measured_baseline_in is not None:
        diff = abs(baseline_in - float(measured_baseline_in))
        metrics["measured_baseline_in"] = float(measured_baseline_in)
        metrics["baseline_difference_in"] = diff
        checks["baseline_matches_measured"] = diff <= baseline_tolerance_in
        checks["baseline_tolerance_in"] = float(baseline_tolerance_in)
        if diff > baseline_tolerance_in:
            errors.append(
                f"Calibration baseline {baseline_in:.2f}in differs from measured "
                f"{float(measured_baseline_in):.2f}in by {diff:.2f}in."
            )

    image_size = _image_size(data)
    metrics["image_size"] = image_size
    checks["image_size_present"] = image_size is not None
    if image_size is None:
        errors.append("Calibration image size metadata is missing or invalid.")
    config_image_size = _config_image_size(config_path)
    if config_image_size is not None:
        metrics["config_image_size"] = config_image_size
        checks["image_size_matches_config"] = image_size == config_image_size
        if image_size != config_image_size:
            errors.append(f"Calibration image size {image_size} does not match config image size {config_image_size}.")

    quality_rating = _npz_str(data, "quality_rating", "UNKNOWN")
    metrics["quality_rating"] = quality_rating
    if quality_rating.upper() == "POOR":
        errors.append("Calibration quality rating is POOR.")

    if "F" not in keys:
        warnings.append("Fundamental matrix F is missing; runtime may recompute it from R/T.")
    checks["fundamental_matrix_present"] = "F" in keys
    checks["essential_matrix_present"] = "E" in keys

    if not errors:
        findings.append("Calibration artifact is acceptable for production geometry gates available in this report.")

    return _finish(
        {
            "status": FAIL if errors else WARN if warnings else PASS,
            "production_ready": bool(production_flag is True and calibration_mode == "FULL" and not errors),
            "calibration_path": str(calibration_path),
            "config_path": str(config_path) if config_path else None,
            "checks": checks,
            "metrics": metrics,
            "warnings": warnings,
            "errors": errors,
            "findings": findings,
        }
    )


def _finish(report: dict[str, Any]) -> dict[str, Any]:
    report["schema_version"] = "calibration_report.v1"
    return report


def _npz_str(data: Any, key: str, default: str) -> str:
    if key not in data:
        return default
    value = data[key]
    try:
        if hasattr(value, "item"):
            value = value.item()
    except Exception:
        pass
    return str(value)


def _npz_float(data: Any, key: str) -> Optional[float]:
    if key not in data:
        return None
    try:
        return float(data[key])
    except Exception:
        return None


def _npz_bool(data: Any, key: str) -> Optional[bool]:
    if key not in data:
        return None
    try:
        value = data[key]
        if hasattr(value, "item"):
            value = value.item()
        if isinstance(value, (bool, np.bool_)):
            return bool(value)
        if isinstance(value, (int, np.integer)) and value in {0, 1}:
            return bool(value)
        if isinstance(value, str) and value.strip().lower() in {"true", "false"}:
            return value.strip().lower() == "true"
        return None
    except Exception:
        return None


def _npz_positive_int(data: Any, key: str) -> int:
    if key not in data:
        return 0
    try:
        value = int(np.asarray(data[key]).item())
        return value if value > 0 else 0
    except Exception:
        return 0


def _baseline_in(data: Any) -> Optional[float]:
    baseline_ft = _npz_float(data, "baseline_ft")
    if baseline_ft is not None:
        return baseline_ft * 12.0
    if "T" not in data:
        return None
    try:
        tvec = np.asarray(data["T"], dtype=np.float64).reshape(3)
        return float(np.linalg.norm(tvec) / MM_PER_INCH)
    except Exception:
        return None


def _image_size(data: Any) -> Optional[list[int]]:
    if "img_size" not in data:
        return None
    try:
        raw = np.asarray(data["img_size"]).reshape(-1)
        if raw.size < 2:
            return None
        width, height = int(raw[0]), int(raw[1])
        if width <= 0 or height <= 0:
            return None
        return [width, height]
    except Exception:
        return None


def _config_image_size(config_path: Optional[Path]) -> Optional[list[int]]:
    if config_path is None or not config_path.exists():
        return None
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        camera = data.get("camera", {})
        width = camera.get("width")
        height = camera.get("height")
        if width is None or height is None:
            return None
        return [int(width), int(height)]
    except Exception:
        return None


def _per_image_error_stats(data: Any) -> dict[str, Optional[float] | int]:
    if "per_image_errors" not in data:
        return {"count": 0, "mean_combined_rms_px": None, "max_combined_rms_px": None}
    try:
        raw = data["per_image_errors"]
        values: list[float] = []
        for item in raw.tolist() if hasattr(raw, "tolist") else list(raw):
            if isinstance(item, dict):
                value = item.get("combined_rms")
            else:
                value = None
            if value is not None:
                values.append(float(value))
        if not values:
            return {"count": 0, "mean_combined_rms_px": None, "max_combined_rms_px": None}
        arr = np.asarray(values, dtype=np.float64)
        return {
            "count": int(arr.size),
            "mean_combined_rms_px": float(np.mean(arr)),
            "max_combined_rms_px": float(np.max(arr)),
        }
    except Exception:
        return {"count": 0, "mean_combined_rms_px": None, "max_combined_rms_px": None}
