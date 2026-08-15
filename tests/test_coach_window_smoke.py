"""Smoke test for CoachWindow construction and teardown with sim backend.

Verifies UI-001 fix: all four coaching game widgets use the free-function
``apply_standard_layout`` instead of the nonexistent
``StyleManager.apply_standard_layout`` method.

Also verifies that close/delete stops observable timers.
"""

from __future__ import annotations

import importlib.util
import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

HAS_PYTEST_QT = importlib.util.find_spec("pytestqt") is not None

requires_pytest_qt = pytest.mark.skipif(
    not HAS_PYTEST_QT,
    reason="pytest-qt not installed",
)


@requires_pytest_qt
def test_coach_window_constructs_with_sim_backend(qtbot: "QtBot") -> None:
    """CoachWindow(backend='sim') must not raise during construction."""
    from ui.coaching.coach_window import CoachWindow

    window = CoachWindow(backend="sim")
    qtbot.addWidget(window)
    assert window.windowTitle()


@requires_pytest_qt
def test_coach_window_close_stops_timers(qtbot: "QtBot") -> None:
    """Closing CoachWindow must stop preview and metrics timers."""
    from ui.coaching.coach_window import CoachWindow

    window = CoachWindow(backend="sim")
    qtbot.addWidget(window)
    window.show()
    qtbot.waitExposed(window)

    assert window._preview_timer.isActive()
    assert window._metrics_timer.isActive()

    window.close()

    assert not window._preview_timer.isActive(), "preview timer still active after close"
    assert not window._metrics_timer.isActive(), "metrics timer still active after close"
