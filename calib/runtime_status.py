"""Runtime calibration status helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import numpy as np
import yaml


REQUIRED_MATRIX_KEYS = (
    "mtx_left",
    "mtx_right",
    "dist_left",
    "dist_right",
    "R",
    "T",
    "img_size",
)

DEFAULT_CALIBRATION_PATH = Path("calibration/stereo_calibration.npz")
DEFAULT_CONFIG_PATH = Path("configs/default.yaml")


def describe_runtime_calibration(
    calib_path: Path = DEFAULT_CALIBRATION_PATH,
    config_path: Path = DEFAULT_CONFIG_PATH,
) -> dict:
    """Describe whether runtime will use calibrated matrices or scalar fallback."""
    profile_id = None
    if calib_path == DEFAULT_CALIBRATION_PATH:
        try:
            from app.services.rig_profile import RigProfileService

            service = RigProfileService(config_path=config_path)
            profile = service.load_active()
            if profile is not None:
                profile_id = profile.profile_id
                calib_path = service.calibration_path(profile)
        except Exception:
            profile_id = None

    if calib_path.exists():
        try:
            data = np.load(calib_path, allow_pickle=True)
            missing = [key for key in REQUIRED_MATRIX_KEYS if key not in data]
            if missing:
                return {
                    "ok": False,
                    "mode": "invalid_matrix_file",
                    "message": f"Calibration file is missing matrix data: {', '.join(missing)}",
                    "path": str(calib_path),
                }
            quality = str(data["quality_rating"]) if "quality_rating" in data else "UNKNOWN"
            rms = _optional_float(data, "rms_error_px")
            calibration_mode = _calibration_mode(calib_path, data)
            return {
                "ok": True,
                "mode": "full_matrix",
                "calibration_mode": calibration_mode,
                "message": _matrix_message(quality, rms, calib_path, calibration_mode),
                "path": str(calib_path),
                "profile_id": profile_id,
                "quality_rating": quality,
                "rms_error_px": rms,
                "production_ready": calibration_mode != "QUICK",
            }
        except Exception as exc:
            return {
                "ok": False,
                "mode": "invalid_matrix_file",
                "message": f"Calibration file could not be loaded: {exc}",
                "path": str(calib_path),
                "profile_id": profile_id,
            }

    scalar = _load_scalar_config(config_path)
    if scalar is not None:
        return {
            "ok": True,
            "mode": "scalar_fallback",
            "message": (
                "Only scalar stereo values are present. Runtime will use simplified rectified geometry; "
                "run calibration to generate full matrix calibration."
            ),
            "path": str(config_path),
            **scalar,
        }
    return {
        "ok": False,
        "mode": "missing",
        "message": "Stereo calibration not found.",
            "path": str(calib_path),
            "profile_id": profile_id,
        }


def _matrix_message(quality: str, rms: Optional[float], path: Path, calibration_mode: str) -> str:
    mode_note = "quick diagnostic calibration" if calibration_mode == "QUICK" else "full matrix calibration"
    if rms is None:
        return f"{mode_note.capitalize()} found at {path} (quality: {quality})."
    return f"{mode_note.capitalize()} found at {path} (quality: {quality}, RMS {rms:.3f} px)."


def _optional_float(data, key: str) -> Optional[float]:
    if key not in data:
        return None
    try:
        return float(data[key])
    except Exception:
        return None


def _load_scalar_config(config_path: Path) -> Optional[dict]:
    if not config_path.exists():
        return None
    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
        stereo = data.get("stereo", {})
        baseline = stereo.get("baseline_ft")
        focal = stereo.get("focal_length_px")
        if baseline and focal:
            return {
                "baseline_ft": float(baseline),
                "focal_length_px": float(focal),
            }
    except Exception:
        return None
    return None


def _calibration_mode(calib_path: Path, data) -> str:
    if "calibration_mode" in data:
        try:
            value = data["calibration_mode"]
            if hasattr(value, "item"):
                value = value.item()
            return str(value).upper()
        except Exception:
            return "UNKNOWN"
    report_path = calib_path.with_name("report.json")
    if report_path.exists():
        try:
            report = yaml.safe_load(report_path.read_text(encoding="utf-8"))
            mode = str((report or {}).get("calibration_mode") or "").upper()
            if mode:
                return mode
        except Exception:
            pass
    return "FULL"
