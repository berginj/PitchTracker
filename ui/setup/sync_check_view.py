"""Qt-free view-model for the setup synchronization-check step (step 3).

Two concerns, both free of PySide6 so they can be unit-tested off-screen:

* :func:`unknown_sync_result` produces a clear not-yet-measured
  :class:`~contracts.setup.SyncCheckResult` for the wizard's initial state.
* :func:`present_sync_check` formats a result into a headline, a flat list of
  labelled rows, and a warning list that the Qt widget renders verbatim.

Keeping the fallback state and formatting here (not in the widget) means the
wizard's synchronization verdict is testable with synthetic reports.
"""

from __future__ import annotations

from contracts.setup import (
    SYNC_VERDICT_GOOD,
    SYNC_VERDICT_POOR,
    SYNC_VERDICT_UNKNOWN,
    SYNC_VERDICT_WARN,
    SyncCheckResult,
)
from ui.setup.quality_report_view import ReportRow, ReportView

# Verdict -> UI tone token used by StyleManager status helpers.
_SYNC_TONE = {
    SYNC_VERDICT_GOOD: "success",
    SYNC_VERDICT_WARN: "warning",
    SYNC_VERDICT_POOR: "error",
    SYNC_VERDICT_UNKNOWN: "info",
}


def present_sync_check(result: SyncCheckResult) -> ReportView:
    """Format a synchronization result into a headline, labelled rows, and warnings."""
    tone = _SYNC_TONE.get(result.verdict, "info")
    headline = f"Synchronization: {result.verdict}"

    rows = [
        ReportRow("Paired frames", str(result.sample_count)),
        ReportRow("Unpaired frames", str(result.unpaired_count)),
        ReportRow("Mean skew", f"{result.mean_delta_ms:.2f} ms"),
        ReportRow("P95 skew", f"{result.p95_delta_ms:.2f} ms"),
        ReportRow("Max skew", f"{result.max_delta_ms:.2f} ms"),
        ReportRow("Jitter", f"{result.jitter_ms:.2f} ms"),
        ReportRow(f"Ball motion @ {result.max_speed_mph:.0f} mph", f"{result.max_motion_in:.1f} in"),
        ReportRow(
            "Result",
            "PASS" if result.passed else "FAIL",
            tone="success" if result.passed else "error",
        ),
    ]
    warnings = [result.recommendation] if result.recommendation else []
    return ReportView(headline=headline, tone=tone, rows=rows, warnings=warnings)


def unknown_sync_result() -> SyncCheckResult:
    """An UNKNOWN result used when synchronization has not been measured."""
    return SyncCheckResult(
        sample_count=0,
        unpaired_count=0,
        mean_delta_ms=0.0,
        p95_delta_ms=0.0,
        max_delta_ms=0.0,
        jitter_ms=0.0,
        max_motion_in=0.0,
        tolerance_ms=0.0,
        max_speed_mph=60.0,
        verdict=SYNC_VERDICT_UNKNOWN,
        passed=False,
        recommendation="Synchronization has not been measured yet. Capture paired frames to run the check.",
    )


__all__ = [
    "present_sync_check",
    "unknown_sync_result",
]
