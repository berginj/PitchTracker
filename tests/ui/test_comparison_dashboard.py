"""Characterization tests for pitcher comparison composition."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from PySide6 import QtWidgets

from ui.analytics.comparison_dashboard import ComparisonDashboard, PitcherStats
from ui.analytics.comparison_data import export_comparison_csv, load_pitcher_stats


def _stats(pitcher_id: str = "pitcher-1", name: str = "Pitcher One") -> PitcherStats:
    return PitcherStats(
        pitcher_id=pitcher_id,
        display_name=name,
        sessions_count=2,
        total_pitches=40,
        avg_velocity=72.5,
        max_velocity=76.0,
        velocity_std=1.25,
        avg_strike_pct=0.625,
        avg_consistency=0.8,
        velocity_by_type={},
    )


def test_summary_aggregation_preserves_dashboard_metrics():
    source = MagicMock()
    source._load_summaries_for_pitcher.return_value = [
        SimpleNamespace(
            avg_velocity_mph=70.0,
            max_velocity_mph=75.0,
            strike_percentage=0.5,
            consistency_score=0.7,
            total_pitches=20,
        ),
        SimpleNamespace(
            avg_velocity_mph=74.0,
            max_velocity_mph=78.0,
            strike_percentage=0.7,
            consistency_score=0.9,
            total_pitches=25,
        ),
    ]

    stats = load_pitcher_stats(source, "pitcher-1", "Pitcher One")

    assert stats.sessions_count == 2
    assert stats.total_pitches == 45
    assert stats.avg_velocity == 72.0
    assert stats.max_velocity == 78.0
    assert stats.avg_strike_pct == 0.6
    assert stats.avg_consistency == 0.8


def test_dashboard_add_remove_is_idempotent_and_accessible(qtbot):
    dashboard = ComparisonDashboard()
    qtbot.addWidget(dashboard)
    stats = _stats()

    dashboard.add_pitcher(stats)
    dashboard.add_pitcher(stats)

    assert list(dashboard._pitcher_stats) == ["pitcher-1"]
    assert len(dashboard._pitcher_cards) == 1
    card = dashboard._pitcher_cards["pitcher-1"]
    assert card.stats is stats
    remove_button = card.findChild(QtWidgets.QPushButton, "comparison_card_remove")
    assert remove_button.accessibleName() == "Remove Pitcher One from comparison"

    dashboard.remove_pitcher("pitcher-1")
    assert dashboard._pitcher_stats == {}
    assert dashboard._pitcher_cards == {}


def test_dashboard_loads_selected_pitcher_name(qtbot):
    dashboard = ComparisonDashboard()
    qtbot.addWidget(dashboard)
    dashboard.set_available_pitchers([("pitcher-1", "Pitcher One")])
    dashboard._trend_analyzer = MagicMock()
    dashboard._trend_analyzer._load_summaries_for_pitcher.return_value = []

    stats = dashboard._load_pitcher_stats("pitcher-1")

    assert stats.pitcher_id == "pitcher-1"
    assert stats.display_name == "Pitcher One"
    assert stats.total_pitches == 0


def test_csv_export_keeps_stable_columns_and_values():
    output = Path("test_comparison_dashboard_export.csv")
    try:
        export_comparison_csv(output, [_stats()])
        rows = output.read_text(encoding="utf-8").splitlines()
    finally:
        output.unlink(missing_ok=True)

    assert rows[0] == (
        "Pitcher,Sessions,Total Pitches,Avg Velocity (mph),Max Velocity (mph),"
        "Velocity Std,Strike %,Consistency %"
    )
    assert rows[1] == "Pitcher One,2,40,72.5,76.0,1.25,62.5,80.0"


def test_dashboard_export_reports_success_without_changing_data(qtbot):
    dashboard = ComparisonDashboard()
    qtbot.addWidget(dashboard)
    dashboard.add_pitcher(_stats())

    with (
        patch("ui.analytics.comparison_dashboard.export_comparison_csv") as export,
        patch("ui.analytics.comparison_dashboard.show_message_dialog") as message,
    ):
        dashboard.export_comparison(Path("comparison.csv"))

    export.assert_called_once()
    message.assert_called_once()
    assert list(dashboard._pitcher_stats) == ["pitcher-1"]
