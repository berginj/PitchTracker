"""Qt-free view-model for the setup overlap validation step (step 5).

Two concerns, both free of PySide6 so they can be unit-tested off-screen:

* :func:`present_overlap` formats a stereo overlap result into a headline, a
  flat list of labelled rows, and a warning list that the Qt widget renders
  verbatim.
* :func:`unknown_overlap_result` provides a clear initial FAIL result before a
  synchronized stereo pair has been validated.

Keeping the formatting here (not in the widget) means the wizard's overlap
verdict is testable with synthetic results and no camera hardware.
"""

from __future__ import annotations

from contracts.setup import (
    OVERLAP_VERDICT_GOOD,
    OVERLAP_VERDICT_POOR,
    OVERLAP_VERDICT_WARN,
    StereoOverlapResult,
)
from ui.setup.quality_report_view import ReportRow, ReportView

# Verdict -> UI tone token used by StyleManager status helpers.
_OVERLAP_TONE = {
    OVERLAP_VERDICT_GOOD: "success",
    OVERLAP_VERDICT_WARN: "warning",
    OVERLAP_VERDICT_POOR: "error",
}


def present_overlap(result: StereoOverlapResult) -> ReportView:
    """Format an overlap result into a headline, labelled rows, and warnings."""
    tone = _OVERLAP_TONE.get(result.verdict, "info")
    headline = f"Stereo overlap: {result.verdict}"

    rows = [
        ReportRow("Keypoints L/R", f"{result.keypoints_left} / {result.keypoints_right}"),
        ReportRow("Raw matches", str(result.raw_matches)),
        ReportRow("Inlier matches", str(result.inlier_matches)),
        ReportRow("Inlier ratio", f"{result.inlier_ratio:.0%}"),
        ReportRow("Overlap score", f"{result.overlap_score:.0%}"),
        ReportRow("Mean match distance", f"{result.mean_match_distance_px:.2f} px"),
        ReportRow(
            "Result",
            "PASS" if result.passed else "FAIL",
            tone="success" if result.passed else "error",
        ),
    ]
    warnings = [result.recommendation] if result.recommendation else []
    return ReportView(headline=headline, tone=tone, rows=rows, warnings=warnings)


def unknown_overlap_result() -> StereoOverlapResult:
    """A FAIL result used when overlap has not been validated."""
    return StereoOverlapResult(
        keypoints_left=0,
        keypoints_right=0,
        raw_matches=0,
        inlier_matches=0,
        inlier_ratio=0.0,
        overlap_score=0.0,
        mean_match_distance_px=0.0,
        verdict=OVERLAP_VERDICT_POOR,
        passed=False,
        recommendation="Overlap has not been validated yet. Capture a synchronized pair to run the check.",
    )


__all__ = [
    "present_overlap",
    "unknown_overlap_result",
]
