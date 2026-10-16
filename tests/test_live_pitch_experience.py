"""Coach-facing feedback geometry, provenance, validity and stable navigation."""

from dataclasses import replace

import pytest
from PySide6 import QtCore, QtGui, QtWidgets

from contracts.measurements import SpeedMeasurement
from scripts.capture_ux_baseline import synthetic_pitches
from tests import test_workspace_navigation as navigation
from ui.coaching.widgets.stats_panel_widget import StatsPanelWidget
from ui.themes import get_style_manager

workspace = navigation.workspace


@pytest.mark.parametrize("size", [(1366, 768), (1024, 768), (800, 600)])
@pytest.mark.parametrize("status", ["ESTIMATED", "UNAVAILABLE", "REJECTED", "DEGRADED"])
def test_latest_feedback_and_controls_fit(workspace, qtbot, size, status):
    window, _pipeline = workspace
    for filename in ("segoeui.ttf", "segoeuib.ttf"):
        QtGui.QFontDatabase.addApplicationFont(f"C:/Windows/Fonts/{filename}")
    get_style_manager().apply_to_app(QtWidgets.QApplication.instance())
    live = window.page("live")
    pitches = synthetic_pitches()
    pitches[-1] = replace(pitches[-1], measurement_status=status,
                          observation_warning_reasons=["Partial tracking coverage"] if status == "DEGRADED" else None,
                          observation_rejection_reasons=["Insufficient tracking evidence"] if status in {"REJECTED", "UNAVAILABLE"} else None)
    live._broadcast_mode.update_pitch_data(pitches)
    window.resize(*size)
    qtbot.wait(20)
    assert window.size() == QtCore.QSize(*size)
    panel = live._broadcast_mode._stats_panel
    for widget in (window._primary, panel._speed_label, panel._result_label, panel._source_label, panel._location_label):
        point = widget.mapTo(window, QtCore.QPoint())
        assert window.rect().contains(QtCore.QRect(point, widget.size())), widget.text()
        if isinstance(widget, QtWidgets.QLabel):
            assert widget.height() >= widget.heightForWidth(widget.width()), widget.text()
    assert live.centralWidget().horizontalScrollBar().maximum() == 0


def test_speed_provenance_matches_selected_measurement(qtbot):
    panel = StatsPanelWidget()
    qtbot.addWidget(panel)
    pitch = replace(synthetic_pitches()[0], speed_mph=85., speed_source="vision_fit",
                    vision_speed=SpeedMeasurement(85., "vision_fit", "plate_plane", 0.),
                    external_speed=SpeedMeasurement(91., "radar", "unspecified"))
    panel.update_latest_pitch(pitch)
    assert "85.0 mph" in panel._speed_label.text()
    assert "vision fit" in panel._source_label.text() and "plate plane" in panel._source_label.text()
    assert "radar" not in panel._source_label.text()


@pytest.mark.parametrize("status", ["REJECTED", "UNAVAILABLE"])
def test_ineligible_pitch_clears_claims_and_marker(workspace, status):
    window, _pipeline = workspace
    view = window.page("live")._broadcast_mode
    pitch = synthetic_pitches()[0]
    view.update_pitch_data([pitch])
    rejected = replace(pitch, measurement_status=status, observation_rejection_reasons=["Insufficient tracking evidence"])
    view.update_pitch_data([pitch, rejected])
    assert view._camera_widget._strike_zone._latest_pitch is None
    assert view._stats_panel._speed_label.text() == "Speed: unavailable"
    assert "vision fit" in view._stats_panel._source_label.text()
    assert view._stats_panel._location_label.text() == "Plate location: unavailable"
    assert "Insufficient tracking evidence" in view._stats_panel._quality_label.text()
    assert status in view._stats_panel._recent_list.item(0).text()


def test_unknown_call_and_nonfinite_location_do_not_make_marker(workspace):
    window, _pipeline = workspace
    view = window.page("live")._broadcast_mode
    pitch = synthetic_pitches()[0]
    for changed in (replace(pitch, strike_call_available=False, strike_call_reason="Boundary uncertainty"),
                    replace(pitch, trajectory_plate_x_ft=float("nan"))):
        view.update_pitch_data([changed])
        assert view._camera_widget._strike_zone._latest_pitch is None


def test_recent_selection_survives_updates_without_focus_change(qtbot):
    panel = StatsPanelWidget()
    qtbot.addWidget(panel)
    pitches = [replace(synthetic_pitches()[0], pitch_id=f"pitch_{i}") for i in range(15)]
    panel.update_recent_list(pitches)
    assert panel._recent_list.count() == 10
    assert panel._recent_list.item(0).data(QtCore.Qt.ItemDataRole.UserRole) == "pitch_14"
    panel._recent_list.setCurrentRow(2)
    selected = panel._recent_list.currentItem().data(QtCore.Qt.ItemDataRole.UserRole)
    item = panel._recent_list.currentItem()
    panel.update_recent_list(pitches)
    assert panel._recent_list.currentItem() is item
    panel.update_recent_list(pitches + [replace(pitches[-1], pitch_id="pitch_15")])
    assert panel._recent_list.currentItem().data(QtCore.Qt.ItemDataRole.UserRole) == selected


def test_view_switch_preserves_camera_and_snapshot(workspace):
    window, _pipeline = workspace
    live = window.page("live")
    live._broadcast_mode.set_camera_selection("right")
    live._pitch_snapshot = synthetic_pitches()
    for index, label in enumerate(("Latest Pitch", "Session Trends", "Games")):
        assert live._mode_selector.itemText(index) == label
        live._mode_selector.setCurrentIndex(index)
        assert live._mode_stack.currentWidget().get_current_camera_selection() == "right"
    live._mode_selector.setCurrentIndex(0)
    assert live._broadcast_mode._camera_widget.get_active_camera() == "right"


def test_preview_resizes_with_keyboard_and_advanced_admission(workspace, qtbot):
    window, pipeline = workspace
    live = window.page("live")
    splitter = live._broadcast_mode._splitter
    qtbot.wait(10)
    before = splitter.sizes()
    qtbot.keyClick(splitter.handle(1), QtCore.Qt.Key.Key_Right)
    assert splitter.sizes() != before
    pipeline.set_status(capture_phase="live", recording_phase="recording", pending_operation="pause_recording")
    assert all(not action.isEnabled() for action, button in live._advanced_actions)
    assert not live._diagnostics_button.isVisibleTo(window)
    assert not live._detector_trial_button.isVisibleTo(window)
