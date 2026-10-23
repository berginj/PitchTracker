"""Large focus rendering, capture admission and retained cancellation."""

import numpy as np
import pytest
from PySide6 import QtCore, QtWidgets

from app.services.setup_workflow.runtime_access import admission_status
from tests.test_guided_setup_workflow import _new_workflow
from ui.setup.focus_assistant import FocusAssistantDialog
from ui.setup.guided_base import display_image
from ui.setup.guided_cameras import CamerasStage
from ui.setup.focus_preview_controller import FocusPreviewController
from contracts.setup_capture import SetupCapturePurpose
from contracts.focus_preview import FocusPreviewFrame
from contracts.timing import TimestampEvidence
from tests.test_focus_guidance import target
import time


@pytest.fixture
def dialog(qtbot):
    widget = FocusAssistantDialog()
    qtbot.addWidget(widget)
    return widget


def test_thumbnail_preserves_source_aspect_ratio(qtbot):
    label = QtWidgets.QLabel()
    qtbot.addWidget(label)
    label.resize(600, 100)
    display_image(label, np.zeros((600, 960, 3), dtype=np.uint8), keep_aspect=True)
    assert label.pixmap().size() == QtCore.QSize(160, 100)


def test_field_image_scaling_keeps_existing_pixel_mapping(qtbot):
    label = QtWidgets.QLabel()
    qtbot.addWidget(label)
    label.resize(600, 100)
    display_image(label, np.zeros((600, 960, 3), dtype=np.uint8))
    assert label.pixmap().size() == QtCore.QSize(600, 100)


@pytest.mark.parametrize("size", [(800, 600), (1366, 768)])
def test_focus_image_uses_available_space_without_stretching(qtbot, dialog, size):
    dialog.resize(*size)
    dialog.set_images({"left": np.zeros((600, 960, 3), dtype=np.uint8)})
    dialog.show()
    qtbot.waitExposed(dialog)
    transform = dialog.view.transform()
    assert transform.m11() == pytest.approx(transform.m22())
    assert dialog.view.viewport().height() >= 200
    assert dialog.refresh.isVisible()
    assert dialog.refresh.geometry().right() < dialog.width()
    assert dialog.view.image_item.pixmap().size() == QtCore.QSize(960, 600)


def test_switching_and_zooming_keep_source_pixels(dialog):
    dialog.set_images({"left": np.zeros((60, 96, 3), dtype=np.uint8),
                       "right": np.full((120, 192, 3), 255, dtype=np.uint8)})
    dialog.side.setCurrentIndex(1)
    dialog.zoom.setCurrentIndex(2)
    assert dialog.view.image_item.pixmap().size() == QtCore.QSize(192, 120)
    assert dialog.view.transform().m11() == 2
    assert dialog.view.transform().m22() == 2
    assert "unavailable" in dialog.sharpness.text()


def test_live_preview_is_explicit_and_never_restarts_on_each_frame(qtbot, dialog):
    requests = []
    dialog.capture_requested.connect(lambda: requests.append(True))
    assert not requests
    dialog.request_capture()
    assert len(requests) == 1
    dialog.set_busy(True)
    dialog.request_capture()
    assert len(requests) == 1
    assert dialog._health_timer.isActive()
    dialog.set_busy(False)
    assert len(requests) == 1
    assert not dialog._health_timer.isActive()


def test_close_waits_for_capture_cancellation(qtbot, dialog):
    cancellations = []
    dialog.cancel_requested.connect(lambda: cancellations.append(True))
    dialog.show()
    dialog.set_busy(True)
    dialog.reject()
    assert cancellations == [True]
    assert dialog.isVisible()
    dialog.set_busy(False)
    qtbot.waitUntil(lambda: not dialog.isVisible())


def test_failure_requires_explicit_restart(dialog):
    dialog.set_busy(True)
    dialog.show_failure("Camera disconnected; reconnect and refresh.")
    dialog.set_busy(False)
    assert not dialog._health_timer.isActive()
    assert "disconnected" in dialog.status.text()


def test_focus_refresh_flows_through_supervised_service(qtbot, tmp_path):
    workflow = _new_workflow(tmp_path)
    workflow.assign("sim-left", "sim-right")
    stage = CamerasStage(workflow)
    qtbot.addWidget(stage)
    stage.open_focus_assistant()
    viewer = stage._focus_dialog
    assert viewer is not None
    assert "latest_pair" not in workflow.state
    viewer.request_capture()
    qtbot.waitUntil(lambda: not viewer.view.image_item.pixmap().isNull(), timeout=30000)
    assert stage.is_busy()
    assert "latest_pair" not in workflow.state
    assert not viewer.view.image_item.pixmap().isNull()
    assert workflow.state["captures"] == []
    assert workflow.state["checks"] == {}
    assert admission_status(workflow.rigs.base_dir).setup_owned
    viewer.reject()
    qtbot.waitUntil(lambda: stage._focus_dialog is None)
    assert not admission_status(workflow.rigs.base_dir).setup_owned


def test_failed_live_start_preserves_an_existing_setup_capture(qtbot, tmp_path):
    workflow = _new_workflow(tmp_path)
    workflow.assign("sim-left", "sim-right")
    workflow.build_capture_request(SetupCapturePurpose.FOCUS)
    controller = FocusPreviewController(workflow)
    try:
        controller.start()
        assert admission_status(workflow.rigs.base_dir).setup_owned
        assert not controller.timer.isActive()
    finally:
        workflow.release_capture()


def test_keyboard_selects_and_moves_focus_target(qtbot, dialog):
    dialog.set_images({"left": target(1)})
    dialog.show()
    dialog.view.setFocus()
    qtbot.keyClick(dialog.view, QtCore.Qt.Key.Key_Return)
    initial = dialog._guides["left"].target
    assert initial is not None
    qtbot.keyClick(dialog.view, QtCore.Qt.Key.Key_Right)
    assert dialog._guides["left"].target[0] == pytest.approx(initial[0] + 0.02)


def test_stale_frame_discards_turn_comparisons_and_cannot_start_another(dialog):
    dialog.set_busy(True)
    dialog.select_target(0.5, 0.5)
    for index in range(8):
        dialog.accept_frame(FocusPreviewFrame(
            "left", "sim-left", index, time.monotonic_ns(), target(1), TimestampEvidence(),
        ))
    dialog.test_turn("clockwise")
    assert dialog._guides["left"].advice.score is not None
    dialog.accept_frame(FocusPreviewFrame(
        "left", "sim-left", 9, time.monotonic_ns() - 2_000_000_000, target(1), TimestampEvidence(),
    ))
    assert dialog._guides["left"].advice.score is None
    dialog.test_turn("counterclockwise")
    assert dialog._guides["left"].advice.score is None
    dialog.set_busy(False)


def test_live_frames_preserve_zoomed_pan_position(qtbot, dialog):
    dialog.resize(800, 600)
    dialog.set_images({"left": np.zeros((600, 960, 3), dtype=np.uint8)})
    dialog.show()
    dialog.zoom.setCurrentIndex(3)
    dialog.view.centerOn(750, 400)
    before = dialog.view.mapToScene(dialog.view.viewport().rect().center())
    dialog.view.set_image(np.full((600, 960, 3), 20, dtype=np.uint8))
    after = dialog.view.mapToScene(dialog.view.viewport().rect().center())
    assert after == before
