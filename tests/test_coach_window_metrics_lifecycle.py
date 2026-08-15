from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import ui.coaching.session_controller as session_controller_module
from ui.coaching.coach_window import CoachWindow
from ui.coaching.pitch_display import PitchDisplay
from ui.coaching.session_controller import SessionController
from ui.coaching.widgets.mode_widgets.game_mode_view import GameModeWidget
from ui.coaching.widgets.mode_widgets.session_progression_view import SessionProgressionWidget


@dataclass(frozen=True)
class _Pitch:
    pitch_id: str
    trajectory_plate_x_ft: float | None = None
    trajectory_plate_y_ft: float | None = None
    measurement_status: str = "ESTIMATED"
    speed_mph: float | None = 88.0


class _Label:
    def __init__(self, text: str = "") -> None:
        self._text = text

    def setText(self, text: str) -> None:
        self._text = text

    def text(self) -> str:
        return self._text


class _Button:
    def __init__(self, enabled: bool = True, text: str = "") -> None:
        self.enabled = enabled
        self.text = text

    def setEnabled(self, enabled: bool) -> None:
        self.enabled = enabled

    def setText(self, text: str) -> None:
        self.text = text


class _Indicator:
    def __init__(self) -> None:
        self.hidden = False

    def hide(self) -> None:
        self.hidden = True


class _Tracker:
    def __init__(self) -> None:
        self.pitches = []

    def add_pitch(self, pitch) -> None:
        self.pitches.append(pitch)


class _Mode:
    def __init__(self) -> None:
        self.calls = []

    def update_pitch_data(self, pitches, *, new_pitches=None) -> None:
        self.calls.append((list(pitches), list(new_pitches or [])))


class _Stack:
    def __init__(self, widget) -> None:
        self.widget = widget

    def currentWidget(self):
        return self.widget


class _Fatigue:
    def __init__(self) -> None:
        self.calls = []

    def update_pitches(self, pitches) -> None:
        self.calls.append(list(pitches))


class _SummaryService:
    def __init__(self, pitches) -> None:
        self.set_pitches(pitches)

    def set_pitches(self, pitches) -> None:
        self.summary = SimpleNamespace(pitch_count=len(pitches), pitches=list(pitches))

    def get_session_summary(self):
        return self.summary

    def get_recent_pitches(self):
        raise AssertionError("capped recent-pitch history must not drive session polling")


def _metrics_window(service: _SummaryService):
    mode = _Mode()
    tracker = _Tracker()
    fatigue = _Fatigue()
    window = SimpleNamespace(
        _session_active=True,
        _session_paused=False,
        _service=service,
        _processed_pitch_ids=set(),
        _pitch_snapshot=[],
        _pitch_count=0,
        _last_pitch_count=0,
        _pitch_count_label=_Label(),
        _session_tracker=tracker,
        _mode_stack=_Stack(mode),
        _fatigue_indicator=fatigue,
        _quality_indicator=_Label(),
        _style_manager=SimpleNamespace(
            style_status_indicator=lambda widget, tone: None
        ),
    )
    service.get_quality_diagnostics = lambda: {"quality": {"status": "ESTIMATED"}}
    window._pitch_display = PitchDisplay(window)
    return window, mode, tracker, fatigue


def test_metrics_poll_processes_a_burst_without_skipping_pitches() -> None:
    first = [_Pitch("pitch_1")]
    service = _SummaryService(first)
    window, mode, tracker, _fatigue = _metrics_window(service)

    CoachWindow._update_metrics(window)
    service.set_pitches([*first, _Pitch("pitch_2"), _Pitch("pitch_3")])
    CoachWindow._update_metrics(window)

    assert [pitch.pitch_id for pitch in tracker.pitches] == ["pitch_1", "pitch_2", "pitch_3"]
    assert [pitch.pitch_id for pitch in mode.calls[-1][1]] == ["pitch_2", "pitch_3"]
    assert window._pitch_count_label.text() == "Pitches: 3"


def test_metrics_poll_uses_full_summary_beyond_recent_ten_pitch_cap() -> None:
    pitches = [_Pitch(f"pitch_{index}") for index in range(1, 13)]
    service = _SummaryService(pitches)
    window, mode, tracker, _fatigue = _metrics_window(service)

    CoachWindow._update_metrics(window)

    assert window._pitch_count == 12
    assert len(tracker.pitches) == 12
    assert len(mode.calls[0][1]) == 12
    assert window._pitch_count_label.text() == "Pitches: 12"


def test_unchanged_metrics_tick_does_not_replay_mode_or_game_attempt() -> None:
    service = _SummaryService([_Pitch("pitch_1")])
    window, mode, tracker, fatigue = _metrics_window(service)

    CoachWindow._update_metrics(window)
    CoachWindow._update_metrics(window)

    assert len(mode.calls) == 1
    assert len(tracker.pitches) == 1
    assert len(fatigue.calls) == 1

    game = SimpleNamespace(processed=[])
    game.process_pitch = game.processed.append
    game.get_game_name = lambda: "tic_tac_toe"
    game_view = SimpleNamespace(_game_stack=_Stack(game))
    pitches = [_Pitch("pitch_1"), _Pitch("pitch_2")]
    GameModeWidget.update_pitch_data(game_view, pitches, new_pitches=[pitches[-1]])
    GameModeWidget.update_pitch_data(game_view, pitches, new_pitches=[])
    assert game.processed == [pitches[-1]]


def test_progression_render_does_not_append_to_shared_tracker() -> None:
    class _ProgressionTracker:
        def add_pitch(self, _pitch) -> None:
            raise AssertionError("view must not append to CoachWindow-owned history")

        def get_fastest_pitch(self):
            return 88.0

        def get_velocity_history(self):
            return [88.0]

        def get_strike_ball_ratio(self):
            return 1, 0, 1.0

        def get_strike_accuracy_history(self):
            return [(0, 1.0)]

        def get_unclassified_count(self):
            return 0

        def get_pitch_count(self):
            return 1

    sink = SimpleNamespace(update_data=lambda _value: None)
    progression = SimpleNamespace(
        _session_tracker=_ProgressionTracker(),
        _fastest_widget=SimpleNamespace(set_speed=lambda _value: None, clear=lambda: None),
        _velocity_chart=sink,
        _strike_gauge=SimpleNamespace(set_percentage=lambda _value: None),
        _classification_label=_Label(),
        _accuracy_chart=sink,
        _camera_widget=SimpleNamespace(clear_pitch_location=lambda: None),
    )

    SessionProgressionWidget.update_pitch_data(progression, [_Pitch("pitch_1")])


def _end_window(service):
    statuses = []
    window = SimpleNamespace(
        _service=service,
        _session_name="bullpen",
        _pitcher_name="pitcher",
        _pitch_count=2,
        _session_active=True,
        _session_paused=True,
        _session_label=_Label("Session: bullpen"),
        _pitcher_label=_Label("Pitcher: pitcher"),
        _pitch_count_label=_Label("Pitches: 2"),
        _recording_indicator=_Indicator(),
        _setup_button=_Button(False),
        _start_recording_button=_Button(False),
        _pause_button=_Button(True, "Resume"),
        _end_button=_Button(True),
        _set_status_message=lambda message, tone: statuses.append((message, tone)),
        _statuses=statuses,
    )
    window._session_ctrl = SessionController(window)
    return window


def test_end_session_reads_summary_only_after_successful_stop(qapp, monkeypatch) -> None:
    order = []
    summary = SimpleNamespace(pitch_count=3, strikes=2, balls=1)

    class _Service:
        def stop_recording(self):
            order.append("stop")

        def get_last_session_summary(self):
            assert order == ["stop"]
            order.append("summary")
            return summary

        def get_session_summary(self):
            raise AssertionError("pre-drain summary must not be read")

    messages = []
    monkeypatch.setattr(session_controller_module, "ask_confirmation", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        session_controller_module,
        "show_message_dialog",
        lambda *args, **kwargs: messages.append((args, kwargs)),
    )
    window = _end_window(_Service())

    CoachWindow._end_session(window)

    assert order == ["stop", "summary"]
    assert window._session_active is False
    assert window._session_paused is False
    assert "Pitches: 3" in messages[-1][0][2]


def test_end_session_failure_preserves_active_paused_ui(qapp, monkeypatch) -> None:
    class _Service:
        def stop_recording(self):
            raise RuntimeError("writer still draining")

        def get_last_session_summary(self):
            raise AssertionError("failed stop has no final summary")

    messages = []
    monkeypatch.setattr(session_controller_module, "ask_confirmation", lambda *args, **kwargs: True)
    monkeypatch.setattr(
        session_controller_module,
        "show_message_dialog",
        lambda *args, **kwargs: messages.append((args, kwargs)),
    )
    window = _end_window(_Service())

    CoachWindow._end_session(window)

    assert window._session_active is True
    assert window._session_paused is True
    assert window._session_label.text() == "Session: bullpen"
    assert window._setup_button.enabled is False
    assert window._pause_button.text == "Resume"
    assert window._statuses[-1][1] == "error"
    assert "still active" in messages[-1][0][2]


def test_estimated_quality_uses_neutral_tone() -> None:
    styled = []
    indicator = _Label()
    window = SimpleNamespace(
        _service=SimpleNamespace(
            get_quality_diagnostics=lambda: {"quality": {"status": "ESTIMATED"}}
        ),
        _quality_indicator=indicator,
        _style_manager=SimpleNamespace(
            style_status_indicator=lambda widget, tone: styled.append((widget, tone))
        ),
    )
    window._pitch_display = PitchDisplay(window)

    CoachWindow._update_quality_health(window)

    assert indicator.text() == "Quality: estimated"
    assert styled == [(indicator, "info")]
