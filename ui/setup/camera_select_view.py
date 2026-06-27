"""Qt-free view-model for the setup camera-selection step (step 1).

Two concerns, both free of PySide6 so they can be unit-tested off-screen:

* :func:`empty_camera_selection` produces a clear no-hardware
  :class:`CameraSelectionSnapshot` for the wizard's initial state.
* :func:`present_camera_selection` formats the discovered cameras into a
  headline, a flat list of labelled rows, and a warning list that the Qt widget
  renders verbatim.

Keeping selection grading and formatting here (not in the widget) means the
wizard's camera-selection gate is testable with synthetic snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from contracts.catalog import SIDE_LEFT, SIDE_RIGHT, SIDE_UNASSIGNED
from ui.setup.quality_report_view import ReportRow, ReportView


@dataclass(frozen=True)
class DiscoveredCamera:
    """A discovered physical camera with setup-wizard assignment state."""

    hardware_id: str
    friendly_name: str
    side: str = SIDE_UNASSIGNED
    recognized: bool = False


@dataclass(frozen=True)
class CameraSelectionSnapshot:
    """A renderable snapshot of discovered camera assignments."""

    cameras: Tuple[DiscoveredCamera, ...] = ()


def empty_camera_selection() -> CameraSelectionSnapshot:
    """Return the honest no-hardware default used before discovery runs."""
    return CameraSelectionSnapshot()


def grade_selection(snapshot: CameraSelectionSnapshot) -> tuple[bool, str]:
    """Validate that distinct physical cameras are assigned left and right."""
    if not snapshot.cameras:
        return False, "No cameras discovered."

    left = [camera for camera in snapshot.cameras if camera.side == SIDE_LEFT]
    right = [camera for camera in snapshot.cameras if camera.side == SIDE_RIGHT]

    if not left:
        return False, "Left camera not assigned."
    if not right:
        return False, "Right camera not assigned."
    if len(left) != 1:
        return False, "Select exactly one left camera."
    if len(right) != 1:
        return False, "Select exactly one right camera."

    left_id = left[0].hardware_id
    right_id = right[0].hardware_id
    if not left_id or not right_id:
        return False, "Camera hardware id is missing."
    if left_id == right_id:
        return False, "Left and right are the same device."

    return True, ""


def present_camera_selection(snapshot: CameraSelectionSnapshot) -> ReportView:
    """Format camera selection into a headline, labelled rows, and warnings."""
    passed, reason = grade_selection(snapshot)
    tone = _headline_tone(snapshot, passed)
    headline = "Camera selection: ready" if passed else "Camera selection: incomplete"

    rows = [_camera_row(camera) for camera in snapshot.cameras]
    rows.append(
        ReportRow(
            "Result",
            "PASS" if passed else "FAIL",
            tone="success" if passed else "error",
        )
    )
    warnings = [] if passed else [reason]
    return ReportView(headline=headline, tone=tone, rows=rows, warnings=warnings)


def _headline_tone(snapshot: CameraSelectionSnapshot, passed: bool) -> str:
    if passed:
        return "success"
    return "error" if not snapshot.cameras else "warning"


def _camera_row(camera: DiscoveredCamera) -> ReportRow:
    label = camera.friendly_name or camera.hardware_id
    side = camera.side or "unassigned"
    value = f"{side} (recognized)" if camera.recognized else side
    return ReportRow(label, value)


__all__ = [
    "CameraSelectionSnapshot",
    "DiscoveredCamera",
    "empty_camera_selection",
    "grade_selection",
    "present_camera_selection",
]
