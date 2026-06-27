"""Qt-free view-model for the setup focus/exposure lock step (step 4).

Two concerns, both free of PySide6 so they can be unit-tested off-screen:

* :class:`FocusExposureSnapshot` bundles the left/right focus and exposure
  verdicts produced by the stereo setup focus-lock backend.
* :func:`present_focus_lock` formats the snapshot into a headline, a flat list
  of labelled rows, and a warning list that the Qt widget renders verbatim.

Keeping the formatting here (not in the widget) means the wizard's Step 4
verdict is testable with synthetic lock results and without camera hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from contracts.setup import (
    LOCK_VERDICT_LOCKED,
    LOCK_VERDICT_MARGINAL,
    LOCK_VERDICT_UNLOCKED,
    ExposureLockResult,
    FocusLockResult,
)
from ui.setup.quality_report_view import ReportRow, ReportView

# Lock verdict -> UI tone token used by StyleManager status helpers.
_LOCK_TONE = {
    LOCK_VERDICT_LOCKED: "success",
    LOCK_VERDICT_MARGINAL: "warning",
    LOCK_VERDICT_UNLOCKED: "error",
}


@dataclass(frozen=True)
class FocusExposureSnapshot:
    """A stereo snapshot of fixed-focus and exposure-lock results."""

    focus_left: FocusLockResult
    focus_right: FocusLockResult
    exposure_left: ExposureLockResult
    exposure_right: ExposureLockResult


def present_focus_lock(snapshot: FocusExposureSnapshot) -> ReportView:
    """Format a focus/exposure snapshot into a headline, rows, and warnings."""
    results = [
        snapshot.focus_left,
        snapshot.focus_right,
        snapshot.exposure_left,
        snapshot.exposure_right,
    ]
    passed = all(result.passed for result in results)
    headline = "Focus & exposure: LOCKED" if passed else "Focus & exposure: NOT LOCKED"
    tone = "success" if passed else _worst_tone(result.verdict for result in results)

    rows = [
        ReportRow(
            "Left sharpness",
            f"{snapshot.focus_left.sharpness:.0f} / {snapshot.focus_left.sharpness_threshold:.0f}",
            tone=_tone_for(snapshot.focus_left.verdict),
        ),
        ReportRow(
            "Right sharpness",
            f"{snapshot.focus_right.sharpness:.0f} / {snapshot.focus_right.sharpness_threshold:.0f}",
            tone=_tone_for(snapshot.focus_right.verdict),
        ),
        ReportRow(
            "Left exposure lock",
            snapshot.exposure_left.verdict,
            tone=_tone_for(snapshot.exposure_left.verdict),
        ),
        ReportRow(
            "Right exposure lock",
            snapshot.exposure_right.verdict,
            tone=_tone_for(snapshot.exposure_right.verdict),
        ),
        ReportRow(
            "Autofocus left",
            _auto_text(snapshot.focus_left.autofocus_disabled),
            tone="success" if snapshot.focus_left.autofocus_disabled else "error",
        ),
        ReportRow(
            "Autofocus right",
            _auto_text(snapshot.focus_right.autofocus_disabled),
            tone="success" if snapshot.focus_right.autofocus_disabled else "error",
        ),
        ReportRow(
            "Result",
            "PASS" if passed else "FAIL",
            tone="success" if passed else "error",
        ),
    ]
    return ReportView(headline=headline, tone=tone, rows=rows, warnings=_warnings_for(results))


def unknown_focus_snapshot() -> FocusExposureSnapshot:
    """A failing snapshot used before focus/exposure have been measured."""
    return FocusExposureSnapshot(
        focus_left=_unknown_focus_result("left"),
        focus_right=_unknown_focus_result("right"),
        exposure_left=_unknown_exposure_result("left"),
        exposure_right=_unknown_exposure_result("right"),
    )


def _tone_for(verdict: str) -> str:
    return _LOCK_TONE.get(verdict, "info")


def _worst_tone(verdicts) -> str:
    verdicts = list(verdicts)
    if LOCK_VERDICT_UNLOCKED in verdicts:
        return "error"
    if LOCK_VERDICT_MARGINAL in verdicts:
        return "warning"
    return "info"


def _auto_text(disabled: bool) -> str:
    return "off" if disabled else "ON"


def _warnings_for(results) -> List[str]:
    warnings: List[str] = []
    seen = set()
    for result in results:
        recommendation = result.recommendation.strip()
        if result.passed or not recommendation or recommendation in seen:
            continue
        warnings.append(recommendation)
        seen.add(recommendation)
    return warnings


def _unknown_focus_result(camera_id: str) -> FocusLockResult:
    return FocusLockResult(
        camera_id=camera_id,
        sharpness=0.0,
        sharpness_threshold=0.0,
        autofocus_disabled=False,
        verdict=LOCK_VERDICT_UNLOCKED,
        passed=False,
        recommendation="Focus not measured yet.",
    )


def _unknown_exposure_result(camera_id: str) -> ExposureLockResult:
    return ExposureLockResult(
        camera_id=camera_id,
        exposure_us=0.0,
        gain=0.0,
        white_balance_k=0.0,
        auto_exposure_disabled=False,
        auto_white_balance_disabled=False,
        readback_verified=False,
        verdict=LOCK_VERDICT_UNLOCKED,
        passed=False,
        recommendation="Exposure not measured yet.",
    )


__all__ = [
    "FocusExposureSnapshot",
    "present_focus_lock",
    "unknown_focus_snapshot",
]
