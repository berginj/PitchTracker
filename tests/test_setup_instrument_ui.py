"""Operator layout changes preserve setup evidence and capture ownership."""

import numpy as np
import os
from pathlib import Path
import pytest
from PySide6 import QtCore, QtWidgets

from contracts.setup_workflow import GuidedSetupStage
from tests.test_guided_setup_workflow import _new_workflow
from ui.setup.guided_base import display_image
from ui.setup.instrument_widgets import PreviewLabel
from ui.setup.stereo_setup_window import StereoSetupWindow
from ui.themes import get_style_manager


@pytest.fixture
def window(qtbot, tmp_path):
    widget = StereoSetupWindow(workflow=_new_workflow(tmp_path))
    qtbot.addWidget(widget)
    widget.show()
    return widget


def test_camera_tuning_is_collapsed_and_light_theme_does_not_edit_rig(window, qtbot):
    camera = window._current_widget()
    assert not camera.camera_controls.content.isVisible()
    assert not camera.saved_setup.content.isVisible()
    assert not camera.preview_button.isEnabled()
    assert camera.discover_button.property("variant") == "primary"
    assert camera.status.property("status") == "pending"
    assert window._step_labels[0].property("stepState") == "current"
    before = window.workflow.state
    global_background = get_style_manager().theme.background_dark
    viewport = window._content_scroll.viewport()
    assert viewport.palette().color(viewport.backgroundRole()).name() == global_background.lower()
    camera.camera_controls.toggle.click()
    assert camera.camera_controls.content.isVisible()
    qtbot.wait(1)
    assert window.workflow.state == before
    assert get_style_manager().theme.background_dark == global_background
    assert window.palette().color(window.backgroundRole()).lightness() > 200
    assert viewport.palette().color(viewport.backgroundRole()).name() == global_background.lower()


def test_capture_cancel_remains_reachable_and_keeps_busy_ownership(window):
    camera = window._current_widget()
    calls = []

    class Operation:
        busy = True

        def cancel(self):
            calls.append("cancel")
            return True
    camera.operation = Operation()
    camera.set_busy(True)
    assert camera.cancel_button.isVisible() and camera.cancel_button.isEnabled()
    assert not camera.left.isEnabled()
    assert not camera.camera_controls.toggle.isEnabled()
    camera.cancel_button.click()
    assert calls == ["cancel"]
    assert camera.is_busy()
    camera.set_busy(False)
    assert not camera.cancel_button.isVisible()
    assert camera.camera_controls.toggle.isEnabled()
    assert not camera.preview_button.isEnabled()
    camera.operation = None


def test_saved_pair_count_does_not_grant_calibration_pass(window, monkeypatch):
    # A collection count alone is not fit or camera-identity evidence.
    window.workflow._state["captures"] = [{} for _ in range(10)]
    for step in (GuidedSetupStage.CAMERAS, GuidedSetupStage.IMAGES):
        window._machine.mark_complete(step, True)
        window._machine.advance()
    window._show_current()
    calibration = window._current_widget()
    assert calibration.pair_progress.value() == 10
    assert calibration.fit_button.isEnabled()
    assert not calibration.validate()[0]
    assert calibration.status.property("status") == "pending"
    messages = []
    monkeypatch.setattr("ui.setup.stereo_setup_window.show_message_dialog", lambda *args, **kwargs: messages.append(args))
    window._go_next()
    assert messages and window._machine.current == GuidedSetupStage.CALIBRATION


def test_camera_edit_clears_the_previous_preview(window):
    camera = window._current_widget()
    display_image(camera.previews[0], np.zeros((180, 320, 3), dtype=np.uint8))
    assert not camera.previews[0].pixmap().isNull()
    camera.save("exposure_us", 3200)
    assert camera.previews[0].pixmap().isNull()
    assert camera.previews[0].text() == "Preview not started"


def test_board_edit_clears_invalidated_collection_previews(window):
    calibration = window._widget_by_step[GuidedSetupStage.CALIBRATION]
    window.workflow._state["captures"] = [{} for _ in range(10)]
    display_image(calibration.previews[0], np.zeros((180, 320, 3), dtype=np.uint8))
    calibration.columns.setValue(8)
    calibration.rows.setValue(6)
    calibration.square.setValue(30)
    calibration.board_changed()
    assert window.workflow.state["captures"] == []
    assert calibration.previews[0].pixmap().isNull()
    assert calibration.pair_progress.value() == 0
    assert not calibration.fit_button.isEnabled()


def test_previews_keep_frame_proportions_after_resize(qtbot):
    label = PreviewLabel()
    qtbot.addWidget(label)
    image = np.zeros((180, 320, 3), dtype=np.uint8)
    label.resize(420, 260)
    label.show()
    display_image(label, image)
    for width, height in ((420, 260), (230, 350), (500, 200)):
        label.resize(width, height)
        qtbot.wait(1)
        pixmap = label.pixmap()
        assert pixmap.width() / pixmap.height() == pytest.approx(320 / 180, abs=0.02)
        assert pixmap.width() <= label.contentsRect().width()
        assert pixmap.height() <= label.contentsRect().height()
    assert not image.any()


def test_small_window_keeps_actions_visible_and_stacks_camera_views(window, qtbot):
    window.resize(640, 640)
    qtbot.wait(100)
    assert window.width() <= 640
    assert window._step_indicator.width() == 64
    assert window._next_button.isVisible()
    views = window._current_widget().camera_views
    assert views.row.direction() == QtWidgets.QBoxLayout.Direction.TopToBottom, (
        window._content_scroll.viewport().size(), window._content_stack.size(),
        views.size(), window._current_widget().minimumSizeHint(),
    )
    assert window._content_scroll.horizontalScrollBar().maximum() == 0


@pytest.mark.parametrize("stage", ["cameras", "calibration"])
def test_setup_pilot_renders_light_appearance(window, qtbot, stage):
    if stage == "calibration":
        for step in (GuidedSetupStage.CAMERAS, GuidedSetupStage.IMAGES):
            window._machine.mark_complete(step, True)
            window._machine.advance()
        window._show_current()
    window.resize(1024, 768)
    qtbot.wait(20)
    current = window._current_widget()
    primary = current.capture_button if stage == "calibration" else current.discover_button
    viewport = window._content_scroll.viewport()
    action_rect = QtCore.QRect(primary.mapTo(viewport, QtCore.QPoint()), primary.size())
    assert viewport.rect().contains(action_rect)
    pixmap = window.grab()
    assert not pixmap.isNull()
    output = os.environ.get("PITCHTRACKER_SETUP_UI_PREVIEW_DIR")
    if output:
        directory = Path(output).resolve()
        root = Path(__file__).resolve().parents[1] / "validation_output"
        assert directory.is_relative_to(root.resolve())
        directory.mkdir(parents=True, exist_ok=True)
        assert pixmap.save(str(directory / f"{stage}-light.png"))
