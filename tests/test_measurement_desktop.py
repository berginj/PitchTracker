"""Desktop study editing and retained-worker cancellation regressions."""

from concurrent.futures import CancelledError
import json
from threading import Event
from types import SimpleNamespace

import pytest

from PySide6 import QtWidgets

from tests.test_physical_validation_v2 import _dataset, _protocol
from ui.review.measurement_validation import MeasurementValidationDialog
from ui.tooling_task import ToolingTaskDialog


def test_shadow_case_edit_invalidates_previous_evaluation(qtbot, tmp_path, monkeypatch):
    protocol = _protocol()
    dataset = _dataset(protocol, phase="shadow")
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(dataset.to_payload()))
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    dialog = MeasurementValidationDialog(parent, tmp_path)
    qtbot.addWidget(dialog)
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *_args: (str(path), ""))
    dialog.import_dataset()
    dialog.protocol_editor.setPlainText(json.dumps(protocol.to_payload()))
    assert dialog.request().dataset == json.loads(json.dumps(dataset.to_payload()))
    dialog.workspace = {"previous": True}
    dialog.cases.item(0, 7).setText("89.5")
    assert dialog.workspace is None
    assert dialog.request().dataset["cases"][0]["reference_speed_mph"] == 89.5


def test_confirmation_cases_cannot_be_added_or_edited(qtbot, tmp_path, monkeypatch):
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(_dataset(_protocol()).to_payload()))
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    dialog = MeasurementValidationDialog(parent, tmp_path)
    qtbot.addWidget(dialog)
    monkeypatch.setattr(QtWidgets.QFileDialog, "getOpenFileName", lambda *_args: (str(path), ""))
    dialog.import_dataset()
    assert dialog.metadata_editor.isReadOnly()
    assert dialog.cases.editTriggers() == QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers
    count = dialog.cases.rowCount()
    dialog.add_case()
    assert dialog.cases.rowCount() == count
    assert "read-only" in dialog.output.toPlainText()


def test_rejection_retains_running_worker_until_terminal_exit(qtbot):
    started = Event()
    release = Event()

    def blocked(cancel):
        started.set()
        release.wait(5)
        if cancel.is_set():
            raise CancelledError()
        return {"late": True}

    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    dialog = ToolingTaskDialog(parent, "Test worker", blocked)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.worker.start()
    try:
        qtbot.waitUntil(started.is_set)
        dialog.reject()
        assert dialog.worker.cancel_event.is_set()
        assert dialog.isVisible()
        assert dialog.busy
        release.set()
        qtbot.waitUntil(lambda: not dialog.busy)
        assert not dialog.worker.isRunning()
        assert not dialog.isVisible()
    finally:
        release.set()
        dialog.worker.wait(5000)


def test_review_menu_exposes_measurement_validation(qtbot):
    from ui.review.review_window import ReviewWindow

    window = ReviewWindow()
    qtbot.addWidget(window)
    actions = window.menuBar().actions()
    tools = next(action.menu() for action in actions if action.text() == "&Tools")
    assert any("Measurement Validation" in action.text() for action in tools.actions())


def test_parent_close_cancels_and_waits_for_worker(qtbot):
    started, release = Event(), Event()

    def blocked(cancel):
        started.set()
        release.wait(5)
        return "discarded result"

    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    parent.show()
    dialog = ToolingTaskDialog(parent, "Export", blocked)
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.worker.start()
    try:
        qtbot.waitUntil(started.is_set)
        parent.close()
        assert parent.isVisible()
        assert dialog.worker.cancel_event.is_set()
        assert dialog.busy
        release.set()
        qtbot.waitUntil(lambda: not parent.isVisible())
        assert not dialog.worker.isRunning()
    finally:
        release.set()
        dialog.worker.wait(5000)


@pytest.mark.parametrize("camera_type", ["webcam", "industrial"])
def test_unknown_autofocus_is_displayed_without_classification_guess(qtbot, camera_type):
    from ui.setup.steps.calibration_step_lifecycle import CalibrationStepLifecycleMixin

    type_label = QtWidgets.QLabel()
    stability_label = QtWidgets.QLabel()
    qtbot.addWidget(type_label)
    qtbot.addWidget(stability_label)
    warnings = []
    host = SimpleNamespace(
        _camera_capabilities=SimpleNamespace(
            camera_type=camera_type, has_autofocus=None, focal_stability_score=90, recommendations=[]
        ),
        _camera_type_label=type_label,
        _camera_stability_label=stability_label,
        _set_camera_type_state=lambda *_args: None,
        _set_camera_stability_state=lambda *_args: None,
        _set_webcam_warning=warnings.append,
    )
    CalibrationStepLifecycleMixin._update_camera_type_display(host)
    assert "Autofocus: unknown" in type_label.text()
    assert "Fixed Focus" not in type_label.text()
    assert warnings == [None]


@pytest.mark.parametrize("enum_value", [True, False])
def test_recent_pitch_labels_render_durable_measurement_status(qtbot, enum_value):
    from contracts.quality import MeasurementStatus
    from ui.coaching.widgets.stats_panel_widget import StatsPanelWidget

    panel = StatsPanelWidget()
    qtbot.addWidget(panel)
    status = MeasurementStatus.REJECTED if enum_value else "REJECTED"
    panel.update_recent_list([SimpleNamespace(speed_mph=None, measurement_status=status, is_strike=False)])
    assert "REJECTED" in panel._recent_list.item(0).text()
    assert "MeasurementStatus" not in panel._recent_list.item(0).text()


def test_desktop_evaluation_invokes_real_tooling_and_preserves_imports(qtbot, tmp_path):
    from tests.test_research_tooling import _session

    root = _session(tmp_path / "session")
    protocol = _protocol()
    dataset = _dataset(protocol, phase="shadow")
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    dialog = MeasurementValidationDialog(parent, root)
    qtbot.addWidget(dialog)
    dialog.protocol_editor.setPlainText(json.dumps(protocol.to_payload()))
    metadata = dataset.to_payload()
    cases = metadata.pop("cases")
    dialog.metadata_editor.setPlainText(json.dumps(metadata))
    dialog._case_extras = list(cases)
    dialog.cases.setRowCount(len(cases))
    for row, case in enumerate(cases):
        dialog._set_case(row, case)
    before = (root / "manifest.json").read_bytes()
    dialog.evaluate()
    assert dialog.workspace is not None, dialog.output.toPlainText()
    assert dialog.workspace["evaluation"]["metrics"]["accepted_count"] == 1
    assert dialog.workspace["physical_claim_eligible"] is False
    assert (root / "manifest.json").read_bytes() == before
