"""Offscreen smoke tests for the canonical StereoSetupWindow."""

from __future__ import annotations

import os
import sys
import time

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from ui.setup.state_machine import DEFAULT_SETUP_SPEC, SetupStep  # noqa: E402
from ui.setup.stereo_setup_window import StereoSetupWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    yield app


def test_stereo_setup_window_starts_on_first_canonical_step(qapp):
    window = StereoSetupWindow()
    try:
        assert window._content_stack.count() == 10
        assert window._machine.current == DEFAULT_SETUP_SPEC[0].step
    finally:
        window.close()


def test_stereo_setup_window_first_step_navigation_state(qapp):
    window = StereoSetupWindow()
    try:
        assert not window._back_button.isEnabled()
        assert not window._next_button.isHidden()
        assert window._finish_button.isHidden()
        assert window._content_scroll.widget() is window._content_stack
    finally:
        window.close()


def test_stereo_setup_window_machine_reaches_final_step(qapp):
    window = StereoSetupWindow()
    try:
        while True:
            step = window._machine.current
            if step == SetupStep.CHARUCO_FINE_TUNE and window._machine.can_skip():
                window._machine.skip()
                continue

            window._widget_by_step[step].set_complete(True)
            window._machine.mark_complete(step, True)
            if window._machine.can_advance():
                window._machine.advance()
            else:
                break

        window._show_current()

        assert window._machine.current == SetupStep.QUALITY_REPORT
        assert window._machine.can_finish()
    finally:
        window.close()


def test_stereo_setup_window_last_step_navigation_state(qapp):
    window = StereoSetupWindow()
    try:
        for spec in DEFAULT_SETUP_SPEC:
            step = spec.step
            if step == SetupStep.CHARUCO_FINE_TUNE and window._machine.can_skip():
                window._machine.skip()
                continue
            window._widget_by_step[step].set_complete(True)
            window._machine.mark_complete(step, True)
            if window._machine.can_advance():
                window._machine.advance()

        window._show_current()

        assert not window._finish_button.isHidden()
        assert window._next_button.isHidden()
    finally:
        window.close()


def test_stereo_setup_window_disables_navigation_while_step_is_busy(qapp):
    window = StereoSetupWindow()
    try:
        step = window._current_widget()
        step.set_busy(True)
        qapp.processEvents()

        assert not window._next_button.isEnabled()
        assert not window._skip_button.isEnabled()

        step.set_busy(False)
        qapp.processEvents()
        assert window._next_button.isEnabled()
    finally:
        window.close()


def test_stereo_setup_window_restores_back_navigation_after_capture_stops(qapp):
    window = StereoSetupWindow()
    try:
        first_step = window._machine.current
        window._widget_by_step[first_step].set_complete(True)
        window._machine.mark_complete(first_step, True)
        window._machine.advance()
        window._show_current()

        current = window._current_widget()
        current.set_busy(True)
        assert not window._back_button.isEnabled()

        current.set_busy(False)
        assert window._back_button.isEnabled()
    finally:
        window.close()


def test_stereo_setup_window_cancels_busy_step_before_close(qapp):
    window = StereoSetupWindow()
    step = window._current_widget()
    cancel_calls: list[bool] = []

    def cancel_pending() -> bool:
        cancel_calls.append(True)
        step.set_busy(False)
        return True

    step.cancel_pending = cancel_pending  # type: ignore[method-assign]
    step.set_busy(True)
    window.show()
    window.close()

    deadline = time.monotonic() + 1.0
    while window.isVisible() and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)

    assert cancel_calls
    assert not window.isVisible()
