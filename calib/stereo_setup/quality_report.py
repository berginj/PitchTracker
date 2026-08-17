"""Aggregate setup-step verdicts into a durable CalibrationQualityReport.

This is the pure-logic core of setup step 9 (quality report). It takes the
typed results produced by the earlier steps -- sync check, focus/exposure
locks, overlap validation, coarse rectification -- plus the final stereo
calibration metrics, and folds them into a single graded
:class:`~contracts.setup.CalibrationQualityReport`.

Keeping the grading here (Qt-free, no I/O) lets the wizard's final verdict be
unit-tested with synthetic step results, which is the whole point of the
rebuild: prove the rig is acceptable *before* any pitch-tracking logic runs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Sequence

from contracts.setup import (
    QUALITY_GRADE_EXCELLENT,
    QUALITY_GRADE_FAIL,
    QUALITY_GRADE_GOOD,
    QUALITY_GRADE_MARGINAL,
    CalibrationQualityReport,
    CoarseRectificationResult,
    ExposureLockResult,
    FocusLockResult,
    StereoOverlapResult,
    SyncCheckResult,
)

# Metric thresholds (pixels). A grade is the *worst* bucket either metric lands
# in; exceeding the MARGINAL bound on either metric is a FAIL.
_EXCELLENT_PX = 0.5
_GOOD_PX = 1.0
_MARGINAL_PX = 2.0


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _metric_grade(rms_px: float, epipolar_px: float) -> str:
    """Grade from the worse of the two reprojection/epipolar metrics."""
    worst = max(rms_px, epipolar_px)
    if worst <= _EXCELLENT_PX:
        return QUALITY_GRADE_EXCELLENT
    if worst <= _GOOD_PX:
        return QUALITY_GRADE_GOOD
    if worst <= _MARGINAL_PX:
        return QUALITY_GRADE_MARGINAL
    return QUALITY_GRADE_FAIL


def _collect_warnings(
    sync: Optional[SyncCheckResult],
    overlap: Optional[StereoOverlapResult],
    rectification: Optional[CoarseRectificationResult],
    focus_locks: Sequence[FocusLockResult],
    exposure_locks: Sequence[ExposureLockResult],
    require_steps: bool = True,
) -> tuple[List[str], bool]:
    """Gather operator-facing warnings and whether every step passed.

    Returns (warnings, all_steps_passed). A missing step is surfaced as a
    warning; when ``require_steps`` is True it also fails the rig (the operator
    cannot earn a passing grade without running the validation steps). When
    ``require_steps`` is False (metrics-only summary), a missing step is a
    warning only and does not by itself fail the rig.
    """
    warnings: List[str] = []
    all_passed = True

    def _note(result, label: str) -> None:
        nonlocal all_passed
        if result is None:
            if require_steps:
                all_passed = False
            warnings.append(f"{label} step was not run.")
            return
        if not result.passed:
            all_passed = False
            detail = getattr(result, "recommendation", "") or ""
            warnings.append(f"{label} did not pass." + (f" {detail}" if detail else ""))

    _note(sync, "Sync check")
    _note(overlap, "Overlap validation")
    _note(rectification, "Coarse rectification")

    for lock in focus_locks:
        if not lock.passed:
            all_passed = False
            detail = lock.recommendation or ""
            warnings.append(f"Focus lock failed for {lock.camera_id}." + (f" {detail}" if detail else ""))
    for exposure_lock in exposure_locks:
        if not exposure_lock.passed:
            all_passed = False
            detail = exposure_lock.recommendation or ""
            warnings.append(
                f"Exposure lock failed for {exposure_lock.camera_id}." + (f" {detail}" if detail else "")
            )

    return warnings, all_passed


def build_quality_report(
    *,
    rms_reprojection_px: float,
    epipolar_error_px: float,
    baseline_in: float,
    sync: Optional[SyncCheckResult] = None,
    overlap: Optional[StereoOverlapResult] = None,
    rectification: Optional[CoarseRectificationResult] = None,
    focus_locks: Optional[Sequence[FocusLockResult]] = None,
    exposure_locks: Optional[Sequence[ExposureLockResult]] = None,
    extra_warnings: Optional[Sequence[str]] = None,
    require_steps: bool = True,
) -> CalibrationQualityReport:
    """Aggregate step verdicts + final metrics into a graded report.

    The grade is driven by the reprojection/epipolar metrics, but a rig only
    ``passes`` when the metric grade is not FAIL *and* every step that was run
    passed. Steps that were not run (None) are surfaced as warnings.

    Args:
        rms_reprojection_px: Final stereo RMS reprojection error, pixels.
        epipolar_error_px: Final mean epipolar error, pixels.
        baseline_in: Estimated baseline, inches.
        sync: Optional sync-check result.
        overlap: Optional overlap-validation result.
        rectification: Optional coarse-rectification result.
        focus_locks: Optional per-camera focus-lock results.
        exposure_locks: Optional per-camera exposure-lock results.
        extra_warnings: Additional warnings to fold in (e.g. quick-mode notice).
        require_steps: When True (default), a not-run validation step fails the
            rig. Set False for a metrics-only end-of-setup summary, where a
            not-run step is a warning only and the grade follows the metrics.

    Returns:
        A frozen :class:`CalibrationQualityReport`.
    """
    focus_list = list(focus_locks or [])
    exposure_list = list(exposure_locks or [])

    metric_grade = _metric_grade(rms_reprojection_px, epipolar_error_px)
    warnings, all_steps_passed = _collect_warnings(
        sync, overlap, rectification, focus_list, exposure_list, require_steps=require_steps
    )
    if extra_warnings:
        warnings.extend(extra_warnings)

    passed = metric_grade != QUALITY_GRADE_FAIL and all_steps_passed
    # A failed step downgrades the headline grade to FAIL even when the raw
    # metrics look fine, so the operator is never told a broken rig is "GOOD".
    grade = metric_grade if all_steps_passed else QUALITY_GRADE_FAIL

    return CalibrationQualityReport(
        grade=grade,
        rms_reprojection_px=rms_reprojection_px,
        epipolar_error_px=epipolar_error_px,
        baseline_in=baseline_in,
        passed=passed,
        sync=sync,
        overlap=overlap,
        rectification=rectification,
        focus_locks=focus_list,
        exposure_locks=exposure_list,
        warnings=warnings,
        created_utc=_utc_now_iso(),
    )


__all__ = ["build_quality_report"]
