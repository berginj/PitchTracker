"""Five-stage navigation, explicit capture, autosave, and field interaction."""

import pytest
from PySide6 import QtWidgets

from contracts.setup_capture import SetupCapturePurpose
from ui.setup.guided_steps import GUIDED_SETUP_SPEC, build_guided_setup_widgets
from ui.setup.stereo_setup_window import StereoSetupWindow
from tests.test_guided_setup_workflow import _new_workflow, _capture, _calibration, _complete


@pytest.fixture
def workflow(tmp_path):
    return _new_workflow(tmp_path)


def test_guided_window_constructs_without_opening_cameras(qtbot, workflow, monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("Camera discovery/capture must be explicit")
    monkeypatch.setattr("ui.setup.guided_cameras.list_uvc_devices", forbidden)
    monkeypatch.setattr("app.services.capture.setup_capture.SupervisedSetupCaptureService.submit", forbidden)
    window = StereoSetupWindow(
        widget_factory=lambda: build_guided_setup_widgets(workflow), specs=GUIDED_SETUP_SPEC,
    )
    qtbot.addWidget(window)
    assert window._content_stack.count() == 5
    assert not workflow.state["changed"]
    window.resize(1024, 768)
    window.show()
    qtbot.waitUntil(window.isVisible)
    assert window._next_button.isVisible()


def test_camera_setting_saves_on_finished_edit(qtbot, workflow):
    from ui.setup.guided_cameras import CamerasStage
    stage = CamerasStage(workflow)
    qtbot.addWidget(stage)
    stage.refresh()
    exposure = stage.widgets["exposure_us"]
    exposure.setValue(3600)
    exposure.editingFinished.emit()
    assert workflow.config.camera.exposure_us == 3600
    assert "Saved" in stage.status.text()
    assert workflow.state["changed"]


def test_current_paired_clicks_and_coordinate_edits_save_targets(qtbot, workflow, tmp_path):
    from ui.setup.guided_field import FieldStage
    workflow.assign("left", "right")
    workflow.accept_calibration(_calibration(workflow, tmp_path), generated=True)
    workflow.apply_capture_result(_capture(workflow, tmp_path, SetupCapturePurpose.FIELD_PAIR))
    stage = FieldStage(workflow)
    qtbot.addWidget(stage)
    stage.capture_ready(None)
    stage.add_target()
    stage.target_clicked("left", [640., 360.])
    stage.target_clicked("right", [540., 360.])
    stage.table.item(0, 1).setText("2")
    stage.table.item(0, 2).setText("3")
    stage.table.item(0, 3).setText("0")
    target = workflow.state["targets"][0]
    assert target["left_pixel"] == [640., 360.]
    assert target["right_pixel"] == [540., 360.]
    assert target["field_xyz_ft"] == [2., 3., 0.]
    assert target["confirmed_sides"] == ["left", "right"]
    assert target["source_pair"]["left"]["file"].endswith(".png")
    stage.mode.setCurrentIndex(1)
    stage.region_drawn("left", (10, 10, 300, 200), True)
    assert workflow.state["regions"]["lane_by_camera"]["left"]
    assert "right" not in workflow.state["regions"]["lane_by_camera"]


def test_fresh_completed_flow_publishes_through_finish(qtbot, workflow, tmp_path, monkeypatch):
    _complete(workflow, tmp_path)
    messages = []
    monkeypatch.setattr("ui.setup.stereo_setup_window.show_message_dialog", lambda *args, **_kwargs: messages.append(args))
    window = StereoSetupWindow(
        widget_factory=lambda: build_guided_setup_widgets(workflow), specs=GUIDED_SETUP_SPEC,
    )
    qtbot.addWidget(window)
    for _ in range(4):
        window._go_next()
    assert window._machine.current.value == "ready"
    window._finish_wizard()
    assert workflow.rigs.load_active().effective_config_file
    assert messages[-1][1] == "Stereo Setup Complete"


def test_failed_save_is_visible_and_cannot_finish(qtbot, workflow, monkeypatch):
    from ui.setup.guided_cameras import CamerasStage
    stage = CamerasStage(workflow)
    qtbot.addWidget(stage)
    stage.refresh()
    monkeypatch.setattr("app.services.setup_workflow.service.save_state",
                        lambda *_args: (_ for _ in ()).throw(OSError("disk full")))
    stage.save("gain", 3.0)
    assert "disk full" in stage.status.text()
    assert not workflow.readiness().permits_recording
    assert workflow.config.camera.gain == 0


def test_reentering_stage_displays_state_without_capture(qtbot, workflow, monkeypatch):
    from ui.setup.guided_images import ImagesStage
    stage = ImagesStage(workflow)
    qtbot.addWidget(stage)
    monkeypatch.setattr(stage, "capture", lambda *_args: (_ for _ in ()).throw(AssertionError("unexpected capture")))
    stage.on_enter()
    stage.on_exit()
    stage.on_enter()


def test_coaching_rig_controls_are_read_only_and_do_not_probe(qtbot, workflow, monkeypatch):
    from app.services.rig_profile_models import RigProfile
    from ui.coaching.dialogs.settings_dialog import SettingsDialog
    profile = RigProfile.from_config("test", workflow.config, backend="sim", left_serial="A", right_serial="B")
    monkeypatch.setattr("ui.device_utils.probe_opencv_indices",
                        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("No native probing in settings")))
    dialog = SettingsDialog(current_left_camera="A", current_right_camera="B", rig_profile=profile,
                            current_compute_backend="auto")
    qtbot.addWidget(dialog)
    assert not dialog._resolution_combo.isEnabled()
    assert not dialog._left_camera_combo.isEnabled()
    assert not dialog._right_camera_combo.isEnabled()
    assert dialog._compute_combo.isEnabled()
    assert dialog._compute_combo.currentData() == "auto"
    assert any(button.text() == "Open setup" for button in dialog.findChildren(QtWidgets.QPushButton))


def test_busy_capture_cannot_switch_rig_or_edit_parameters(qtbot, workflow):
    from ui.setup.guided_cameras import CamerasStage
    stage = CamerasStage(workflow)
    qtbot.addWidget(stage)
    stage.set_busy(True)
    assert not stage.rig.isEnabled()
    assert not stage.left.isEnabled()
    assert not stage.widgets["gain"].isEnabled()
    assert not stage.color.isEnabled()
    assert not stage.widgets["flip_left"].isEnabled()
    stage.set_busy(False)
    assert stage.rig.isEnabled()
    assert stage.widgets["gain"].isEnabled()
    assert stage.color.isEnabled()
    assert stage.widgets["flip_left"].isEnabled()
