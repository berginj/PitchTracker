"""Qt-free view-model for the setup persist-profile step (step 8).

Two concerns, both free of PySide6 so they can be unit-tested off-screen:

* :func:`build_stereo_profile_from_report` reads the persisted calibration
  metrics (``calibration/report.json``) and folds them into a durable
  :class:`~contracts.setup.StereoCalibrationProfile`.
* :func:`present_persist_preview` formats a profile into a headline, a flat list
  of labelled rows, and a warning list that the Qt widget renders verbatim.

Keeping the file I/O and formatting here (not in the widget) means the wizard's
profile preview is testable with synthetic reports and temp directories.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from contracts.setup import StereoCalibrationProfile
from contracts.versioning import APP_VERSION, SCHEMA_VERSION
from ui.setup.quality_report_view import ReportRow, ReportView

_FEET_TO_INCHES = 12.0


def build_stereo_profile_from_report(
    calib_dir: Path = Path("calibration"),
) -> Optional[StereoCalibrationProfile]:
    """Build a stereo calibration profile from persisted calibration output."""
    report_path = Path(calib_dir) / "report.json"
    if not report_path.exists():
        return None

    try:
        metrics = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None

    image_size = metrics.get("image_size", [])
    image_width = _image_size_value(image_size, 0)
    image_height = _image_size_value(image_size, 1)
    calibration_mode = str(metrics.get("calibration_mode", "")).upper()

    return StereoCalibrationProfile(
        baseline_in=_as_float(metrics.get("baseline_ft")) * _FEET_TO_INCHES,
        rms_reprojection_px=_as_float(metrics.get("rms_error_px")),
        epipolar_error_px=0.0,
        image_width=image_width,
        image_height=image_height,
        source="charuco" if calibration_mode == "FULL" else "quick",
        production_ready=calibration_mode != "QUICK",
        calibration_file="stereo_calibration.npz",
        created_utc=datetime.now(timezone.utc).isoformat(),
        app_version=APP_VERSION,
        schema_version=SCHEMA_VERSION,
    )


def present_persist_preview(profile: Optional[StereoCalibrationProfile]) -> ReportView:
    """Format a stereo calibration profile into a headline, labelled rows, and warnings."""
    if profile is None:
        return ReportView(
            headline="No calibration available to persist",
            tone="error",
            rows=[],
            warnings=["No calibration metrics were found. Run calibration before persisting a profile."],
        )

    rows = [
        ReportRow("Baseline", f"{profile.baseline_in:.2f} in"),
        ReportRow("RMS reprojection", f"{profile.rms_reprojection_px:.2f} px"),
        ReportRow("Source", profile.source),
        ReportRow(
            "Production ready",
            "yes" if profile.production_ready else "no",
            tone="success" if profile.production_ready else "error",
        ),
        ReportRow("Calibration file", profile.calibration_file),
    ]
    warnings = []
    if not profile.production_ready:
        warnings.append("This is a diagnostic-only (quick) calibration; it will be saved but is not production-ready.")
    return ReportView(
        headline="Profile ready to persist",
        tone="success" if profile.production_ready else "warning",
        rows=rows,
        warnings=warnings,
    )


def _image_size_value(image_size: object, index: int) -> int:
    if not isinstance(image_size, (list, tuple)) or len(image_size) <= index:
        return 0
    return int(_as_float(image_size[index]))


def _as_float(value: object) -> float:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return result if result == result else 0.0  # drop NaN


__all__ = [
    "build_stereo_profile_from_report",
    "present_persist_preview",
]
