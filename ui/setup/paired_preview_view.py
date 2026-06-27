"""Qt-free view-model for the setup paired-preview step (step 2).

Two concerns, both free of PySide6 so they can be unit-tested off-screen:

* :func:`empty_preview_snapshot` produces a clear no-live-preview
  :class:`PairedPreviewSnapshot` for the wizard's initial state.
* :func:`present_paired_preview` formats a snapshot into a headline, a flat list
  of labelled rows, and a finding list that the Qt widget renders verbatim.

Keeping the preview grading and formatting here (not in the widget) means the
wizard's paired-preview gate is testable with synthetic snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass

from ui.setup.quality_report_view import ReportRow, ReportView


@dataclass(frozen=True)
class PairedPreviewSnapshot:
    """Render-ready state captured from the left/right preview streams."""

    left_ok: bool = False
    right_ok: bool = False
    paired_within_tolerance: bool = False
    left_frame_index: int = -1
    right_frame_index: int = -1
    pair_offset_ms: float = 0.0
    frames_observed: int = 0


def empty_preview_snapshot() -> PairedPreviewSnapshot:
    """An honest no-live-preview snapshot used when no provider is attached."""
    return PairedPreviewSnapshot()


def grade_preview(snapshot: PairedPreviewSnapshot) -> tuple[bool, str]:
    """Return whether the preview is ready and the most relevant failure reason."""
    if snapshot.left_ok and snapshot.right_ok and snapshot.paired_within_tolerance and snapshot.frames_observed > 0:
        return True, ""

    if snapshot.frames_observed <= 0 or (not snapshot.left_ok and not snapshot.right_ok):
        return False, "No frames received from either camera."
    if not snapshot.left_ok:
        return False, "Left camera not delivering frames."
    if not snapshot.right_ok:
        return False, "Right camera not delivering frames."
    return False, "Left/right frames not pairing within tolerance."


def present_paired_preview(snapshot: PairedPreviewSnapshot) -> ReportView:
    """Format a paired-preview snapshot into a headline, labelled rows, and findings."""
    passed, reason = grade_preview(snapshot)
    if passed:
        tone = "success"
        headline = "Paired preview: ready"
    elif snapshot.frames_observed <= 0:
        tone = "error"
        headline = "Paired preview: no frames"
    else:
        tone = "warning"
        headline = "Paired preview: attention needed"

    rows = [
        ReportRow(
            "Left stream",
            f"OK (frame {snapshot.left_frame_index})" if snapshot.left_ok else "no frames",
            tone="success" if snapshot.left_ok else "error",
        ),
        ReportRow(
            "Right stream",
            f"OK (frame {snapshot.right_frame_index})" if snapshot.right_ok else "no frames",
            tone="success" if snapshot.right_ok else "error",
        ),
        ReportRow("Pair offset", f"{snapshot.pair_offset_ms:.1f} ms"),
        ReportRow(
            "Pairing",
            "within tolerance" if snapshot.paired_within_tolerance else "out of tolerance",
            tone="success" if snapshot.paired_within_tolerance else "error",
        ),
        ReportRow("Frames observed", str(snapshot.frames_observed)),
    ]
    findings = [] if passed else [reason]
    return ReportView(headline=headline, tone=tone, rows=rows, warnings=findings)


__all__ = [
    "PairedPreviewSnapshot",
    "empty_preview_snapshot",
    "grade_preview",
    "present_paired_preview",
]
