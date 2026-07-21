import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys  # noqa: E402

import pytest  # noqa: E402
from PySide6 import QtWidgets  # noqa: E402

from contracts.catalog import SIDE_LEFT, SIDE_RIGHT  # noqa: E402
from ui.setup.camera_select_view import CameraSelectionSnapshot, DiscoveredCamera  # noqa: E402
from ui.setup.steps.camera_select_step import CameraSelectStep  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)


def _passing_snapshot() -> CameraSelectionSnapshot:
    return CameraSelectionSnapshot(
        cameras=(
            DiscoveredCamera("left-serial", "Left Camera", SIDE_LEFT, recognized=True, global_shutter=True),
            DiscoveredCamera("right-serial", "Right Camera", SIDE_RIGHT, recognized=True, global_shutter=True),
        )
    )


def test_camera_select_step_renders_passing_snapshot_and_validates(qapp: QtWidgets.QApplication) -> None:
    widget = CameraSelectStep(snapshot_provider=_passing_snapshot)

    widget.on_enter()

    assert widget.is_complete() is True
    assert widget.validate() == (True, "")
    assert widget.get_title() == "Select Cameras"


def test_camera_select_step_default_empty_provider_renders_and_fails(qapp: QtWidgets.QApplication) -> None:
    widget = CameraSelectStep()

    widget.on_enter()
    valid, message = widget.validate()

    assert valid is False
    assert message == "No cameras discovered."
    assert widget.is_complete() is False


def test_camera_select_step_renders_metrics_rows(qapp: QtWidgets.QApplication) -> None:
    widget = CameraSelectStep(snapshot_provider=_passing_snapshot)

    widget.on_enter()

    assert widget._metrics_form.rowCount() == 3


def test_camera_select_step_refresh_replaces_rows_and_completion(qapp: QtWidgets.QApplication) -> None:
    snapshots = [
        CameraSelectionSnapshot(cameras=(DiscoveredCamera("left-serial", "Left Camera", SIDE_LEFT),)),
        _passing_snapshot(),
    ]
    widget = CameraSelectStep(snapshot_provider=lambda: snapshots.pop(0))

    widget.on_enter()
    valid, message = widget.validate()

    assert valid is False
    assert message == "Right camera not assigned."
    assert widget.is_complete() is False
    assert widget._metrics_form.rowCount() == 2

    widget.refresh()

    assert widget.validate() == (True, "")
    assert widget.is_complete() is True
    assert widget._metrics_form.rowCount() == 3


def test_camera_select_step_preselects_recommended_pair(qapp: QtWidgets.QApplication) -> None:
    snapshot = CameraSelectionSnapshot(
        cameras=(
            DiscoveredCamera("first", "First", recognized=True, global_shutter=True),
            DiscoveredCamera("second", "Second", recognized=True, global_shutter=True),
            DiscoveredCamera("third", "Third", recognized=True, global_shutter=True),
        ),
        recommended_left_id="third",
        recommended_right_id="first",
        recommendation_source="capability_score",
        recommendation_reason="best pair",
    )
    assignments = []
    widget = CameraSelectStep(
        snapshot_provider=lambda: snapshot,
        assignment_callback=lambda left, right: assignments.append((left, right)),
    )

    widget.on_enter()

    assert widget._left_combo.currentData() == "third"
    assert widget._right_combo.currentData() == "first"
