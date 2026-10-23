"""UX-07: recorded semantics, offline Help, keyboard access and small viewports."""

from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pytest
from PySide6 import QtCore, QtWidgets

from app.contracts import PitchSummary, SessionSummary
from contracts.measurements import SpeedMeasurement
from ui.analytics.session_dashboard import SessionDashboard
from ui.analytics.comparison_dashboard import ComparisonDashboard
from ui.analytics.comparison_data import export_comparison_csv, load_pitcher_stats
from ui.themes import get_style_manager
from ui.workspace.secondary import WorkspaceHelpDialog, WorkspaceSettingsDialog


def pitch(identity="one", **changes):
    return replace(PitchSummary(identity, 1, 2, True, 0, 0, 0, 0, 70, None, 10,
                                vision_speed=SpeedMeasurement(70, "vision_fit", "first_observed")), **changes)


def test_analytics_retains_failed_rows_and_chart_gaps(qtbot):
    dashboard = SessionDashboard()
    qtbot.addWidget(dashboard)
    pitches = [pitch(), pitch("rejected", measurement_status="REJECTED", speed_mph=99),
               pitch("no-call", strike_call_available=False, zone_row=2, zone_col=2),
               pitch("ball", is_strike=False, speed_mph=72, zone_row=None, zone_col=None)]
    dashboard.load_session("Selected session", "Recorded player", pitches)
    assert dashboard._strike_pct_card.value_label.text() == "50"
    assert "2/4 calls (1 strikes, 1 balls)" in dashboard._coverage.text()
    assert "3/4 speeds" in dashboard._coverage.text()
    assert dashboard._table.rowCount() == 4
    assert dashboard._table.item(1, 1).text() == "Unavailable"
    assert dashboard._table.item(1, 3).text() == "REJECTED"
    assert dashboard._table.item(2, 3).text() == "Unavailable"
    # Canonical bottom-left and top-right are not normalized from 1-based indices.
    assert dashboard._heat_map_grid.item(2, 0).text() == "1"
    assert dashboard._heat_map_grid.item(0, 2).text() == "1"
    line = dashboard._velocity_figure.axes[0].lines[0]
    assert list(line.get_xdata()) == [1, 2, 3, 4]
    assert np.isnan(line.get_ydata()[1])
    assert dashboard._avg_velocity_card.value_label.text() == "Unavailable"  # unmatched source/reference on pitch 4
    assert dashboard._pitches == pitches  # presentation never edits summaries


@pytest.mark.parametrize("pitches", [[], [pitch(measurement_status="UNAVAILABLE")]])
def test_no_eligible_results_are_never_zero_speed_or_ball_rate(qtbot, pitches):
    dashboard = SessionDashboard()
    qtbot.addWidget(dashboard)
    dashboard.load_session("Empty or unavailable", "", pitches)
    assert dashboard._avg_velocity_card.value_label.text() == "Unavailable"
    assert dashboard._strike_pct_card.value_label.text() == "Unavailable"
    assert "0 balls" in dashboard._coverage.text()


def test_missing_chart_dependency_keeps_table(qtbot, monkeypatch):
    monkeypatch.setattr("ui.analytics.session_dashboard.HAS_MATPLOTLIB", False)
    dashboard = SessionDashboard()
    qtbot.addWidget(dashboard)
    dashboard.load_session("Partial", "", [pitch()])
    assert dashboard._table.item(0, 1).text() == "70.0"
    assert "matplotlib" in dashboard._tabs.widget(0).text()


def test_comparison_has_no_fabricated_measurements_and_exports_unavailable(qtbot, tmp_path):
    source = Mock()
    source._load_summaries_for_pitcher.return_value = []
    stats = load_pitcher_stats(source, "missing", "Missing recorded player")
    dashboard = ComparisonDashboard()
    qtbot.addWidget(dashboard)
    assert not dashboard._add_btn.isEnabled()
    assert not dashboard._export_btn.isEnabled()
    dashboard.add_pitcher(stats)
    assert dashboard._table.item(0, 3).text() == "Unavailable"
    assert dashboard._export_btn.isEnabled()
    target = tmp_path / "comparison.csv"
    export_comparison_csv(target, [stats])
    assert "Unavailable" in target.read_text()
    dashboard.remove_pitcher("missing")
    assert not dashboard._clear_btn.isEnabled()


def test_failed_comparison_load_is_recoverable(qtbot):
    dashboard = ComparisonDashboard()
    qtbot.addWidget(dashboard)
    dashboard.set_available_pitchers([("player", "Recorded player")])
    dashboard._pitcher_combo.setCurrentIndex(1)
    dashboard._trend_analyzer = Mock()
    dashboard._trend_analyzer._load_summaries_for_pitcher.side_effect = OSError("Synthetic read failure")
    dashboard._add_btn.click()
    assert "Synthetic read failure" in dashboard._notice.text()
    assert dashboard._table.rowCount() == 0


def test_help_opens_selected_local_guide_and_relative_links(qtbot, tmp_path):
    (tmp_path / "GUIDED_SETUP.md").write_text("# Saved rig setup\n[Next](next.md)")
    (tmp_path / "next.md").write_text("# Second guide\nExplicit camera actions")
    dialog = WorkspaceHelpDialog(page="setup", docs_root=tmp_path)
    qtbot.addWidget(dialog)
    assert "Saved rig setup" in dialog.content.toPlainText()
    dialog.content.anchorClicked.emit(QtCore.QUrl("next.md"))
    assert "Explicit camera actions" in dialog.content.toPlainText()
    dialog.topics.setCurrentIndex(0)
    assert "Guide unavailable" in dialog.content.toPlainText()
    dialog.topics.setCurrentIndex(1)
    assert "Saved rig setup" in dialog.content.toPlainText()


def test_help_all_default_topics_are_available(qtbot):
    dialog = WorkspaceHelpDialog()
    qtbot.addWidget(dialog)
    for index in range(dialog.topics.count()):
        dialog.topics.setCurrentIndex(index)
        assert "Guide unavailable" not in dialog.content.toPlainText()
        assert len(dialog.content.toPlainText()) > 100


def test_settings_requires_explicit_setup_action(qtbot):
    parent = QtWidgets.QWidget()
    qtbot.addWidget(parent)
    open_setup = Mock()
    dialog = WorkspaceSettingsDialog(parent, QtWidgets.QWidget(), open_setup)
    qtbot.addWidget(dialog)
    open_setup.assert_not_called()
    dialog.setup_button.click()
    open_setup.assert_called_once()
    assert dialog.result() == QtWidgets.QDialog.DialogCode.Accepted


@pytest.mark.parametrize("size", [(1366, 768), (1024, 768), (800, 600)])
def test_secondary_views_reach_small_viewports_without_theme_leak(qtbot, size):
    from ui.review.pipeline_comparison_dialog import PipelineComparisonDialog
    from ui.review.fit_batch_dialog import FitBatchDialog
    from ui.dialogs.pattern_analysis_dialog import PatternAnalysisDialog
    from ui.analytics.comparison_dashboard import ComparisonDashboardDialog
    from ui.dialogs.session_summary_dialog import SessionSummaryDialog

    sm = get_style_manager()
    original = sm.mode
    sm.set_mode("setup")
    try:
        summary = SessionSummary("synthetic", 1, 1, 0, [[0] * 3 for _ in range(3)], [pitch()])
        widgets = [SessionDashboard(), WorkspaceHelpDialog(), PipelineComparisonDialog(),
                   FitBatchDialog(None), PatternAnalysisDialog(None, Path("synthetic-session")),
                   ComparisonDashboardDialog(), SessionSummaryDialog(None, summary, Mock(), Mock())]
        for widget in widgets:
            qtbot.addWidget(widget)
            widget.resize(*size)
            widget.show()
            qtbot.wait(5)
            assert widget.width() <= size[0], type(widget).__name__
            assert widget.height() <= size[1], type(widget).__name__
            for button in widget.findChildren(QtWidgets.QPushButton):
                if button.isVisibleTo(widget) and not button.objectName().startswith("qt_"):
                    assert button.accessibleName(), (type(widget).__name__, button.text())
                    assert int(button.focusPolicy()) & int(QtCore.Qt.FocusPolicy.TabFocus)
            if isinstance(widget, (PipelineComparisonDialog, FitBatchDialog)):
                scroll = widget.findChild(QtWidgets.QScrollArea)
                assert scroll is not None
                close = next(b for b in widget.findChildren(QtWidgets.QPushButton) if b.text() == "Close")
                position = close.mapTo(widget, QtCore.QPoint())
                assert widget.rect().contains(QtCore.QRect(position, close.size()))
            widget.hide()
        assert sm.mode == "setup"
    finally:
        sm.set_mode(original)
