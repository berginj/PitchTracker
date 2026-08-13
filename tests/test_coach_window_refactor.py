"""Characterization tests for the refactored CoachWindow modules.

Covers construction/teardown, session start/stop, mode switching,
pitch updates, error paths, and accessible primary actions.
"""

from __future__ import annotations

import importlib.util
import os
from types import SimpleNamespace
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_PYTEST_QT = importlib.util.find_spec("pytestqt") is not None

requires_pytest_qt = pytest.mark.skipif(
    not HAS_PYTEST_QT,
    reason="pytest-qt not installed",
)


# --------------------------------------------------------------------------
# Construction & teardown
# --------------------------------------------------------------------------


@requires_pytest_qt
def test_coach_window_construction_creates_delegates(qtbot: "QtBot") -> None:
    """CoachWindow must instantiate session_ctrl and pitch_display delegates."""
    from ui.coaching.coach_window import CoachWindow

    window = CoachWindow(backend="sim")
    qtbot.addWidget(window)
    assert hasattr(window, "_session_ctrl")
    assert hasattr(window, "_pitch_display")


@requires_pytest_qt
def test_coach_window_facade_under_500_lines(qtbot: "QtBot") -> None:
    """The refactored facade file must stay under 500 lines."""
    from pathlib import Path

    facade = Path("ui/coaching/coach_window.py")
    lines = facade.read_text(encoding="utf-8").splitlines()
    assert len(lines) <= 500, f"coach_window.py is {len(lines)} lines, must be <=500"


# --------------------------------------------------------------------------
# Session start/stop (via controller)
# --------------------------------------------------------------------------


@requires_pytest_qt
def test_start_recording_requires_capture(qtbot: "QtBot") -> None:
    """start_recording must reject when cameras are not running."""
    from ui.coaching.coach_window import CoachWindow

    window = CoachWindow(backend="sim")
    qtbot.addWidget(window)
    window._service.is_capturing = MagicMock(return_value=False)

    with patch("ui.coaching.session_controller.show_message_dialog") as mock_dlg:
        window._start_recording()
        mock_dlg.assert_called_once()
        assert "not running" in mock_dlg.call_args[0][2].lower()


@requires_pytest_qt
def test_end_session_resets_ui_state(qtbot: "QtBot") -> None:
    """After ending a session, buttons and labels must reset."""
    from ui.coaching.coach_window import CoachWindow

    window = CoachWindow(backend="sim")
    qtbot.addWidget(window)

    # Simulate active session
    window._session_active = True
    window._session_name = "Test"
    window._pitch_count = 5
    window._service.stop_recording = MagicMock()
    window._service.get_last_session_summary = MagicMock(return_value=None)

    with patch("ui.coaching.session_controller.ask_confirmation", return_value=True):
        window._end_session()

    assert not window._session_active
    assert window._setup_button.isEnabled()
    assert not window._end_button.isEnabled()


# --------------------------------------------------------------------------
# Mode switching
# --------------------------------------------------------------------------


@requires_pytest_qt
def test_mode_selector_switches_stack(qtbot: "QtBot") -> None:
    """Changing mode selector must update the stacked widget index."""
    from ui.coaching.coach_window import CoachWindow

    window = CoachWindow(backend="sim")
    qtbot.addWidget(window)

    window._mode_selector.setCurrentIndex(1)
    assert window._mode_stack.currentIndex() == 1

    window._mode_selector.setCurrentIndex(2)
    assert window._mode_stack.currentIndex() == 2


# --------------------------------------------------------------------------
# Pitch updates
# --------------------------------------------------------------------------


def test_pitch_display_update_metrics_processes_new_pitches() -> None:
    """PitchDisplay.update_metrics must forward new pitches to mode widget."""
    from dataclasses import dataclass

    @dataclass(frozen=True)
    class FakePitch:
        pitch_id: str

    mode = MagicMock()
    tracker = MagicMock()
    fatigue = MagicMock()

    host = SimpleNamespace(
        _session_active=True,
        _session_paused=False,
        _service=MagicMock(),
        _processed_pitch_ids=set(),
        _pitch_snapshot=[],
        _pitch_count=0,
        _last_pitch_count=0,
        _pitch_count_label=MagicMock(),
        _session_tracker=tracker,
        _mode_stack=MagicMock(currentWidget=MagicMock(return_value=mode)),
        _fatigue_indicator=fatigue,
        _quality_indicator=MagicMock(),
        _style_manager=MagicMock(),
    )
    host._service.get_session_summary.return_value = SimpleNamespace(
        pitch_count=2, pitches=[FakePitch("p1"), FakePitch("p2")]
    )
    host._service.get_quality_diagnostics.return_value = {"quality": {"status": "ESTIMATED"}}

    from ui.coaching.pitch_display import PitchDisplay

    display = PitchDisplay(host)
    display.update_metrics()

    assert mode.update_pitch_data.called
    assert tracker.add_pitch.call_count == 2


# --------------------------------------------------------------------------
# Error handling
# --------------------------------------------------------------------------


@requires_pytest_qt
def test_pause_error_shows_dialog(qtbot: "QtBot") -> None:
    """Pause failure must display an error dialog, not crash."""
    from ui.coaching.coach_window import CoachWindow

    window = CoachWindow(backend="sim")
    qtbot.addWidget(window)
    window._session_active = True
    window._session_paused = False
    window._service.pause_recording = MagicMock(side_effect=RuntimeError("fail"))

    with patch("ui.coaching.session_controller.show_message_dialog") as mock_dlg:
        window._pause_session()
        mock_dlg.assert_called_once()
        assert "error" in mock_dlg.call_args[1].get("tone", "")

    # Reset so teardown close doesn't trigger blocking dialog
    window._session_active = False


# --------------------------------------------------------------------------
# Accessibility: primary actions have accessible names
# --------------------------------------------------------------------------


@requires_pytest_qt
def test_primary_buttons_have_accessible_names(qtbot: "QtBot") -> None:
    """All primary control buttons must have non-empty accessible names."""
    from ui.coaching.coach_window import CoachWindow

    window = CoachWindow(backend="sim")
    qtbot.addWidget(window)

    buttons = [
        window._setup_button,
        window._start_recording_button,
        window._pause_button,
        window._end_button,
        window._settings_button,
        window._lane_button,
        window._review_button,
        window._help_button,
    ]
    for btn in buttons:
        assert btn.accessibleName(), f"Button '{btn.text()}' missing accessible name"
