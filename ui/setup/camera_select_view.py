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
from typing import Optional, Tuple

from contracts.catalog import SIDE_LEFT, SIDE_RIGHT, SIDE_UNASSIGNED
from ui.setup.quality_report_view import ReportRow, ReportView


@dataclass(frozen=True)
class DiscoveredCamera:
    """A discovered physical camera with setup-wizard assignment state."""

    hardware_id: str
    friendly_name: str
    side: str = SIDE_UNASSIGNED
    recognized: bool = False
    global_shutter: bool = False
    model: str = ""
    supported_modes: Tuple[Tuple[int, int, int], ...] = ()
    controls: Tuple[str, ...] = ()
    sync_capable: Optional[bool] = None
    instance_id: Optional[str] = None
    device_path: Optional[str] = None
    usb_controller: Optional[str] = None
    driver_version: Optional[str] = None
    firmware_version: Optional[str] = None
    capability_score: int = 0
    recommended_side: str = SIDE_UNASSIGNED
    recommendation_reason: str = ""
    previously_validated: bool = False
    validated_profile_id: str = ""


@dataclass(frozen=True)
class CameraSelectionSnapshot:
    """A renderable snapshot of discovered camera assignments."""

    cameras: Tuple[DiscoveredCamera, ...] = ()
    recommended_left_id: str = ""
    recommended_right_id: str = ""
    recommendation_source: str = ""
    recommendation_reason: str = ""


def empty_camera_selection() -> CameraSelectionSnapshot:
    """Return the honest no-hardware default used before discovery runs."""
    return CameraSelectionSnapshot()


def grade_selection(snapshot: CameraSelectionSnapshot) -> tuple[bool, str]:
    """Validate that distinct physical cameras are assigned left and right.

    Camera technology is a production-eligibility concern, not a discovery
    concern.  Allow an operator to continue setup with an unrecognized or
    rolling-shutter UVC pair for diagnostic capture; the persisted setup
    snapshot remains fail-closed because it requires recognized global-shutter
    cameras.
    """
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
    compatibility_warnings = _production_compatibility_warnings(snapshot) if passed else []
    tone = _headline_tone(snapshot, passed, bool(compatibility_warnings))
    if not passed:
        headline = "Camera selection: incomplete"
    elif compatibility_warnings:
        headline = "Camera selection: diagnostic only"
    else:
        headline = "Camera selection: ready"

    rows = [_camera_row(camera) for camera in snapshot.cameras]
    if snapshot.recommended_left_id and snapshot.recommended_right_id:
        rows.append(
            ReportRow(
                "Recommended pair",
                f"{snapshot.recommended_left_id} / {snapshot.recommended_right_id} ({snapshot.recommendation_source})",
                tone="success",
            )
        )
    rows.append(
        ReportRow(
            "Result",
            "PASS (DIAGNOSTIC ONLY)" if compatibility_warnings else "PASS" if passed else "FAIL",
            tone="warning" if compatibility_warnings else "success" if passed else "error",
        )
    )
    warnings = compatibility_warnings if passed else [reason]
    return ReportView(headline=headline, tone=tone, rows=rows, warnings=warnings)


def _headline_tone(
    snapshot: CameraSelectionSnapshot,
    passed: bool,
    diagnostic_only: bool = False,
) -> str:
    if diagnostic_only:
        return "warning"
    if passed:
        return "success"
    return "error" if not snapshot.cameras else "warning"


def _production_compatibility_warnings(snapshot: CameraSelectionSnapshot) -> list[str]:
    selected = [
        camera
        for camera in snapshot.cameras
        if camera.side in {SIDE_LEFT, SIDE_RIGHT}
    ]
    unsupported = [
        camera
        for camera in selected
        if not camera.recognized or not camera.global_shutter
    ]
    if not unsupported:
        return []
    labels = ", ".join(camera.friendly_name or camera.hardware_id for camera in unsupported)
    return [
        "Diagnostic setup is allowed, but production measurement remains blocked "
        f"until both cameras are recognized global-shutter models: {labels}."
    ]


def _camera_row(camera: DiscoveredCamera) -> ReportRow:
    label = camera.friendly_name or camera.hardware_id
    side = camera.side or "unassigned"
    recommendation = (
        f"; recommended {camera.recommended_side}"
        if camera.recommended_side in {SIDE_LEFT, SIDE_RIGHT}
        else ""
    )
    if camera.recognized and camera.global_shutter:
        validation = ", previously validated" if camera.previously_validated else ""
        value = f"{side} (recognized global shutter{validation}{recommendation})"
    elif camera.recognized:
        value = f"{side} (recognized, not global shutter; diagnostic only{recommendation})"
    else:
        value = f"{side} (unrecognized; diagnostic only{recommendation})"
    return ReportRow(label, value)


__all__ = [
    "CameraSelectionSnapshot",
    "DiscoveredCamera",
    "empty_camera_selection",
    "grade_selection",
    "present_camera_selection",
]
