"""Qt-free view-model for the setup quality-report step (step 9).

Two concerns, both free of PySide6 so they can be unit-tested off-screen:

* :func:`load_calibration_quality_report` reads the persisted calibration
  metrics (``calibration/report.json``) and folds them into a metrics-only
  :class:`~contracts.setup.CalibrationQualityReport` via
  :func:`~calib.stereo_setup.quality_report.build_quality_report`.
* :func:`present_quality_report` formats a report into a headline, a flat list
  of labelled rows, and a warning list that the Qt widget renders verbatim.

Keeping the file I/O and formatting here (not in the widget) means the wizard's
final verdict is testable with synthetic reports and temp directories.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from calib.stereo_setup.quality_report import build_quality_report
from contracts.setup import (
    QUALITY_GRADE_EXCELLENT,
    QUALITY_GRADE_FAIL,
    QUALITY_GRADE_GOOD,
    QUALITY_GRADE_MARGINAL,
    CalibrationQualityReport,
)

_FEET_TO_INCHES = 12.0

# Grade -> UI tone token used by StyleManager status helpers.
_GRADE_TONE = {
    QUALITY_GRADE_EXCELLENT: "success",
    QUALITY_GRADE_GOOD: "success",
    QUALITY_GRADE_MARGINAL: "warning",
    QUALITY_GRADE_FAIL: "error",
}


@dataclass(frozen=True)
class ReportRow:
    """A single labelled metric row for display."""

    label: str
    value: str
    tone: str = "neutral"


@dataclass(frozen=True)
class ReportView:
    """Render-ready view of a CalibrationQualityReport."""

    headline: str
    tone: str
    rows: List[ReportRow] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


def load_calibration_quality_report(
    calib_dir: Path = Path("calibration"),
) -> CalibrationQualityReport:
    """Build a metrics-only quality report from persisted calibration output.

    The quick/full calibration path persists RMS reprojection error and the
    baseline (in feet) to ``report.json`` but does not measure epipolar error,
    so epipolar is reported as 0.0 with an explanatory warning. When no metrics
    file exists the report is a clear FAIL telling the operator to calibrate.

    Args:
        calib_dir: Directory containing ``report.json``.

    Returns:
        A :class:`CalibrationQualityReport` graded on the available metrics.
    """
    report_path = Path(calib_dir) / "report.json"
    if not report_path.exists():
        return _no_calibration_report(report_path)

    try:
        metrics = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return _no_calibration_report(report_path, detail=f"could not be read: {exc}")

    rms = _as_float(metrics.get("rms_error_px"))
    baseline_in = _as_float(metrics.get("baseline_ft")) * _FEET_TO_INCHES

    extra_warnings: List[str] = [
        "Epipolar error is not measured in this calibration mode; showing reprojection RMS only."
    ]
    if str(metrics.get("calibration_mode", "")).upper() == "QUICK":
        extra_warnings.append("Quick calibration is diagnostic-only and is not production-ready.")

    return build_quality_report(
        rms_reprojection_px=rms,
        epipolar_error_px=0.0,
        baseline_in=baseline_in,
        extra_warnings=extra_warnings,
        require_steps=False,
    )


def present_quality_report(report: CalibrationQualityReport) -> ReportView:
    """Format a report into a headline, labelled rows, and warnings."""
    tone = _GRADE_TONE.get(report.grade, "info")
    headline = f"Calibration quality: {report.grade}"

    epipolar_value = "not measured" if report.epipolar_error_px <= 0.0 else f"{report.epipolar_error_px:.2f} px"
    rows = [
        ReportRow("RMS reprojection error", f"{report.rms_reprojection_px:.2f} px"),
        ReportRow("Epipolar error", epipolar_value),
        ReportRow("Baseline", f"{report.baseline_in:.2f} in"),
        ReportRow(
            "Result",
            "PASS" if report.passed else "FAIL",
            tone="success" if report.passed else "error",
        ),
    ]
    return ReportView(headline=headline, tone=tone, rows=rows, warnings=list(report.warnings))


def _no_calibration_report(report_path: Path, detail: str = "was not found") -> CalibrationQualityReport:
    """A FAIL report used when calibration metrics are unavailable."""
    return CalibrationQualityReport(
        grade=QUALITY_GRADE_FAIL,
        rms_reprojection_px=0.0,
        epipolar_error_px=0.0,
        baseline_in=0.0,
        passed=False,
        warnings=[f"Calibration metrics {detail} ({report_path}). Run calibration first."],
    )


def _as_float(value: object) -> float:
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0
    return result if result == result else 0.0  # drop NaN


__all__ = [
    "ReportRow",
    "ReportView",
    "load_calibration_quality_report",
    "present_quality_report",
]
