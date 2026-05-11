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


def describe_runtime_calibration(
    calib_path: Path = Path("calibration/stereo_calibration.npz"),
    config_path: Path = Path("configs/default.yaml"),
) -> dict:
    """Describe whether runtime will use calibrated matrices or scalar fallback."""
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
            return {
                "ok": True,
                "mode": "full_matrix",
                "message": _matrix_message(quality, rms, calib_path),
                "path": str(calib_path),
                "quality_rating": quality,
                "rms_error_px": rms,
            }
        except Exception as exc:
            return {
                "ok": False,
                "mode": "invalid_matrix_file",
                "message": f"Calibration file could not be loaded: {exc}",
                "path": str(calib_path),
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
    }


def _matrix_message(quality: str, rms: Optional[float], path: Path) -> str:
    if rms is None:
        return f"Full matrix calibration found at {path} (quality: {quality})."
    return f"Full matrix calibration found at {path} (quality: {quality}, RMS {rms:.3f} px)."


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
