from __future__ import annotations

from types import SimpleNamespace

from PySide6 import QtWidgets

from app.contracts import PitchSummary, SessionSummary, measurement_is_usable
from ui.coaching.session_history_tracker import SessionHistoryTracker
from ui.coaching.widgets.mode_widgets.broadcast_view import BroadcastViewWidget
from ui.coaching.widgets.mode_widgets.game_mode_view import GameModeWidget
from ui.dialogs.session_summary_dialog import SessionSummaryDialog


def _pitch(
    pitch_id: str,
    *,
    status: str = "ESTIMATED",
    strike: bool = False,
    speed: float | None = None,
    zone: tuple[int, int] | None = None,
) -> PitchSummary:
    row, col = zone if zone is not None else (None, None)
    return PitchSummary(
        pitch_id=pitch_id,
        t_start_ns=1,
        t_end_ns=2,
        is_strike=strike,
        zone_row=row,
        zone_col=col,
        run_in=0.0,
        rise_in=0.0,
        speed_mph=speed,
        rotation_rpm=None,
        sample_count=12,
        trajectory_plate_x_ft=0.1 if zone is not None else None,
        trajectory_plate_y_ft=2.5 if zone is not None else None,
        measurement_status=status,
    )


def test_measurement_is_usable_centralizes_rejected_and_unavailable_gate() -> None:
    assert measurement_is_usable(_pitch("estimated")) is True
    assert measurement_is_usable(_pitch("degraded", status="DEGRADED")) is True
    assert measurement_is_usable(_pitch("rejected", status="REJECTED")) is False
    assert measurement_is_usable(_pitch("unavailable", status="UNAVAILABLE")) is False


def test_session_history_excludes_unclassified_and_missing_speed_from_claims() -> None:
    tracker = SessionHistoryTracker(window_size=3)
    tracker.add_pitch(_pitch("strike", strike=True, speed=91.0))
    tracker.add_pitch(_pitch("rejected", status="REJECTED", strike=False, speed=105.0))
    tracker.add_pitch(_pitch("ball", strike=False, speed=None))

    assert tracker.get_velocity_history() == [(0, 91.0)]
    assert tracker.get_fastest_pitch() == 91.0
    assert tracker.get_strike_ball_ratio() == (1, 1, 0.5)
    assert tracker.get_unclassified_count() == 1
    assert tracker.get_strike_accuracy_history()[-1] == (2, 0.5)


def test_session_history_reports_no_speed_as_unavailable_not_zero() -> None:
    tracker = SessionHistoryTracker()
    tracker.add_pitch(_pitch("missing-speed", strike=True, speed=None))

    assert tracker.get_velocity_history() == []
    assert tracker.get_fastest_pitch() is None


def test_session_summary_recomputes_classification_and_heatmap_from_usable_pitches(qapp) -> None:
    pitches = [
        _pitch("strike", strike=True, speed=90.0, zone=(0, 0)),
        _pitch("rejected", status="REJECTED", strike=True, speed=99.0, zone=(2, 2)),
        _pitch("ball", strike=False, speed=None),
    ]
    # Deliberately incorrect legacy aggregates prove the dialog does not trust
    # rejected pitches that upstream summaries may still classify.
    summary = SessionSummary(
        session_id="session",
        pitch_count=3,
        strikes=2,
        balls=1,
        heatmap=[[1, 0, 0], [0, 0, 0], [0, 0, 1]],
        pitches=pitches,
    )
    dialog = SessionSummaryDialog(None, summary, lambda _summary: None, lambda _kind: None)

    labels = [label.text() for label in dialog.findChildren(QtWidgets.QLabel)]
    assert "Unclassified" in labels
    unclassified_index = labels.index("Unclassified")
    assert "1" in labels[unclassified_index + 1 :]
    assert "50%" in labels

    tables = dialog.findChildren(QtWidgets.QTableWidget)
    heatmap = next(table for table in tables if table.columnCount() == 3)
    details = next(table for table in tables if table.columnCount() == 8)
    assert heatmap.item(0, 0).text() == "1"
    assert heatmap.item(2, 2).text() == "0"
    assert details.item(1, 1).text() == "Unclassified"
    assert details.item(1, 2).text() == "-"

    dialog.close()


def test_rejected_latest_pitch_clears_broadcast_plate_overlay() -> None:
    camera = SimpleNamespace(
        cleared=0,
        clear_pitch_location=lambda: setattr(camera, "cleared", camera.cleared + 1),
    )
    stats = SimpleNamespace(update_latest_pitch=lambda _pitch: None, update_recent_list=lambda _pitches: None)
    view = SimpleNamespace(_camera_widget=camera, _stats_panel=stats)
    rejected = _pitch("rejected", status="REJECTED", strike=True, zone=(1, 1))

    BroadcastViewWidget.update_pitch_data(view, [rejected], new_pitches=[rejected])

    assert camera.cleared == 1


def test_game_mode_ignores_unclassified_and_speedless_speed_attempts() -> None:
    game = SimpleNamespace(processed=[])
    game.process_pitch = game.processed.append
    game.get_game_name = lambda: "speed_challenge"
    game_stack = SimpleNamespace(currentWidget=lambda: game)
    view = SimpleNamespace(_game_stack=game_stack)
    pitches = [
        _pitch("rejected", status="REJECTED", strike=True, speed=90.0, zone=(0, 0)),
        _pitch("missing", strike=True, speed=None, zone=(0, 0)),
        _pitch("usable", strike=True, speed=90.0, zone=(0, 0)),
    ]

    GameModeWidget.update_pitch_data(view, pitches, new_pitches=pitches)

    assert game.processed == [pitches[-1]]
