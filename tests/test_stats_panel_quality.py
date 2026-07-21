from __future__ import annotations

from app.contracts import PitchSummary
from ui.coaching.widgets.stats_panel_widget import StatsPanelWidget


def _summary(**updates) -> PitchSummary:
    payload = dict(
        pitch_id="p1",
        t_start_ns=1,
        t_end_ns=2,
        is_strike=True,
        zone_row=1,
        zone_col=1,
        run_in=8.0,
        rise_in=12.0,
        speed_mph=80.0,
        rotation_rpm=None,
        sample_count=10,
        measurement_status="ESTIMATED",
        quality_diagnostics={"movement_validated": False},
    )
    payload.update(updates)
    return PitchSummary(**payload)


def test_unvalidated_break_is_not_presented_as_coaching_metric(qtbot) -> None:
    widget = StatsPanelWidget()
    qtbot.addWidget(widget)
    widget.update_latest_pitch(_summary())
    assert widget._h_break_label.text() == "H-Break: unavailable"
    assert widget._v_break_label.text() == "V-Break: unavailable"


def test_unavailable_pitch_does_not_present_strike_claim(qtbot) -> None:
    widget = StatsPanelWidget()
    qtbot.addWidget(widget)
    widget.update_latest_pitch(_summary(measurement_status="UNAVAILABLE"))
    assert widget._result_label.text() == "Result: UNAVAILABLE"
