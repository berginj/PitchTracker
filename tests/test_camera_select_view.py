from contracts.catalog import SIDE_LEFT, SIDE_RIGHT, SIDE_UNASSIGNED
from ui.setup.camera_select_view import (
    CameraSelectionSnapshot,
    DiscoveredCamera,
    empty_camera_selection,
    grade_selection,
    present_camera_selection,
)


def _camera(
    hardware_id: str,
    friendly_name: str,
    side: str = SIDE_UNASSIGNED,
    recognized: bool = False,
) -> DiscoveredCamera:
    return DiscoveredCamera(
        hardware_id=hardware_id,
        friendly_name=friendly_name,
        side=side,
        recognized=recognized,
    )


def test_grade_selection_passes_with_distinct_left_and_right() -> None:
    snapshot = CameraSelectionSnapshot(
        cameras=(
            _camera("left-serial", "Left Camera", SIDE_LEFT),
            _camera("right-serial", "Right Camera", SIDE_RIGHT),
        )
    )

    assert grade_selection(snapshot) == (True, "")


def test_grade_selection_fails_for_empty_snapshot() -> None:
    assert grade_selection(empty_camera_selection()) == (False, "No cameras discovered.")


def test_grade_selection_fails_when_left_missing() -> None:
    snapshot = CameraSelectionSnapshot(cameras=(_camera("right-serial", "Right Camera", SIDE_RIGHT),))

    assert grade_selection(snapshot) == (False, "Left camera not assigned.")


def test_grade_selection_fails_when_right_missing() -> None:
    snapshot = CameraSelectionSnapshot(cameras=(_camera("left-serial", "Left Camera", SIDE_LEFT),))

    assert grade_selection(snapshot) == (False, "Right camera not assigned.")


def test_grade_selection_fails_when_same_device_is_assigned_to_both_sides() -> None:
    snapshot = CameraSelectionSnapshot(
        cameras=(
            _camera("same-serial", "Camera Left", SIDE_LEFT),
            _camera("same-serial", "Camera Right", SIDE_RIGHT),
        )
    )

    assert grade_selection(snapshot) == (False, "Left and right are the same device.")


def test_present_camera_selection_success_uses_success_tone_and_rows() -> None:
    snapshot = CameraSelectionSnapshot(
        cameras=(
            _camera("left-serial", "Left Camera", SIDE_LEFT, recognized=True),
            _camera("right-serial", "Right Camera", SIDE_RIGHT),
        )
    )

    view = present_camera_selection(snapshot)

    assert view.headline == "Camera selection: ready"
    assert view.tone == "success"
    assert view.rows[0].label == "Left Camera"
    assert view.rows[0].value == "left (recognized)"
    assert view.rows[-1].value == "PASS"
    assert view.warnings == []


def test_present_camera_selection_failure_uses_error_tone_for_empty_snapshot() -> None:
    view = present_camera_selection(empty_camera_selection())

    assert view.headline == "Camera selection: incomplete"
    assert view.tone == "error"
    assert view.rows[-1].value == "FAIL"
    assert view.warnings == ["No cameras discovered."]


def test_present_camera_selection_failure_uses_warning_tone_for_partial_assignment() -> None:
    snapshot = CameraSelectionSnapshot(cameras=(_camera("left-serial", "Left Camera", SIDE_LEFT),))

    view = present_camera_selection(snapshot)

    assert view.tone == "warning"
    assert view.warnings == ["Right camera not assigned."]
