"""Qt-free view-model for the setup coarse-rectification step (step 6).

Formats the targetless coarse rectification result into a headline, a flat list
of labelled rows, and a warning list that the Qt widget renders verbatim.

Keeping the formatting here (not in the widget) means the wizard's coarse
rectification verdict is testable with synthetic results off-screen.
"""

from __future__ import annotations

from contracts.setup import CoarseRectificationResult
from ui.setup.quality_report_view import ReportRow, ReportView


def present_rectification(result: CoarseRectificationResult) -> ReportView:
    """Format a coarse rectification result into a headline, labelled rows, and warnings."""
    if not result.converged:
        headline = "Coarse rectification: DID NOT CONVERGE"
        tone = "error"
    elif result.passed:
        headline = "Coarse rectification: PASS"
        tone = "success"
    else:
        headline = "Coarse rectification: MARGINAL"
        tone = "warning"

    improvement_px = result.epipolar_error_before_px - result.epipolar_error_after_px
    rows = [
        ReportRow(
            "Converged",
            "yes" if result.converged else "no",
            tone="success" if result.converged else "error",
        ),
        ReportRow("Inlier matches", str(result.inlier_matches)),
        ReportRow("Epipolar error before", f"{result.epipolar_error_before_px:.2f} px"),
        ReportRow("Epipolar error after", f"{result.epipolar_error_after_px:.2f} px"),
        ReportRow("Improvement", f"{improvement_px:.2f} px"),
        ReportRow(
            "Result",
            "PASS" if result.passed else "FAIL",
            tone="success" if result.passed else "error",
        ),
    ]
    warnings = [result.recommendation] if result.recommendation else []
    return ReportView(headline=headline, tone=tone, rows=rows, warnings=warnings)


def unknown_rectification_result() -> CoarseRectificationResult:
    """A FAIL result used when coarse rectification has not been run yet."""
    identity = tuple(float(v) for v in (1, 0, 0, 0, 1, 0, 0, 0, 1))
    return CoarseRectificationResult(
        fundamental_matrix=tuple(0.0 for _ in range(9)),
        left_homography=identity,
        right_homography=identity,
        epipolar_error_before_px=0.0,
        epipolar_error_after_px=0.0,
        inlier_matches=0,
        converged=False,
        passed=False,
        recommendation="Rectification has not been run yet. Validate overlap, then run coarse rectification.",
    )


__all__ = [
    "present_rectification",
    "unknown_rectification_result",
]
