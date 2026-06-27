"""Qt-free view-model for the setup ChArUco fine-tune step (step 7).

Two concerns, both free of PySide6 so they can be unit-tested off-screen:

* :func:`load_charuco_status` reads the persisted calibration metrics
  (``calibration/report.json``) and determines whether FULL ChArUco
  fine-tuning has already been applied.
* :func:`present_charuco_finetune` formats that status into a headline, a flat
  list of labelled rows, and a warning list that the Qt widget renders verbatim.

Keeping the file I/O and formatting here (not in the widget) means the wizard's
optional fine-tune status is testable with synthetic reports and temp directories.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from calib.charuco import DEFAULT_DICTIONARY_ID, MARKER_RATIO
from ui.setup.quality_report_view import ReportRow, ReportView

_FEET_TO_INCHES = 12.0

_DICTIONARY_NAMES = {
    DEFAULT_DICTIONARY_ID: "DICT_6X6_250",
}

_OPTIONAL_WARNING = (
    "ChArUco fine-tuning is optional. The targetless calibration is usable; running a ChArUco (FULL) "
    "calibration can improve intrinsics and scale accuracy. Print and mount the ChArUco board, then run a full "
    "calibration."
)


@dataclass(frozen=True)
class CharucoStatus:
    """Persisted ChArUco fine-tune status for display."""

    calibration_present: bool
    fine_tuned: bool
    calibration_mode: str
    rms_reprojection_px: float
    baseline_in: float


def load_charuco_status(calib_dir: Path = Path("calibration")) -> CharucoStatus:
    """Read persisted calibration status and detect whether FULL fine-tuning ran."""
    report_path = Path(calib_dir) / "report.json"
    if not report_path.exists():
        return _missing_status()

    try:
        metrics = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return _missing_status()

    mode = str(metrics.get("calibration_mode", "")).upper()
    rms = _as_float(metrics.get("rms_error_px"))
    baseline_in = _as_float(metrics.get("baseline_ft")) * _FEET_TO_INCHES
    return CharucoStatus(
        calibration_present=True,
        fine_tuned=mode == "FULL",
        calibration_mode=mode,
        rms_reprojection_px=rms,
        baseline_in=baseline_in,
    )


def board_dictionary_name() -> str:
    """Return the readable name of the configured ChArUco dictionary."""
    return _DICTIONARY_NAMES.get(DEFAULT_DICTIONARY_ID, str(DEFAULT_DICTIONARY_ID))


def present_charuco_finetune(status: CharucoStatus) -> ReportView:
    """Format a ChArUco status into a headline, labelled rows, and warnings."""
    if status.fine_tuned:
        headline = "ChArUco fine-tuning: applied"
        tone = "success"
    elif status.calibration_present:
        headline = "ChArUco fine-tuning: not applied (optional)"
        tone = "info"
    else:
        headline = "ChArUco fine-tuning: no calibration yet (optional)"
        tone = "info"

    rows = [
        ReportRow("Board dictionary", board_dictionary_name()),
        ReportRow("Marker ratio", f"{MARKER_RATIO:.2f}"),
        ReportRow("Calibration mode", status.calibration_mode or "none"),
        ReportRow("RMS reprojection", f"{status.rms_reprojection_px:.2f} px"),
        ReportRow("Baseline", f"{status.baseline_in:.2f} in"),
    ]
    warnings = [] if status.fine_tuned else [_OPTIONAL_WARNING]
    return ReportView(headline=headline, tone=tone, rows=rows, warnings=warnings)


def _missing_status() -> CharucoStatus:
    return CharucoStatus(
        calibration_present=False,
        fine_tuned=False,
        calibration_mode="",
        rms_reprojection_px=0.0,
        baseline_in=0.0,
    )


def _as_float(value: object) -> float:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return result if result == result else 0.0  # drop NaN


__all__ = [
    "CharucoStatus",
    "load_charuco_status",
    "board_dictionary_name",
    "present_charuco_finetune",
]
