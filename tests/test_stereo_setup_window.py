"""Offscreen smoke tests for the canonical StereoSetupWindow."""

from __future__ import annotations

import os
import sys

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
        assert window._content_stack.count() == 9
        assert window._machine.current == DEFAULT_SETUP_SPEC[0].step
    finally:
        window.close()


def test_stereo_setup_window_first_step_navigation_state(qapp):
    window = StereoSetupWindow()
    try:
        assert not window._back_button.isEnabled()
        assert not window._next_button.isHidden()
        assert window._finish_button.isHidden()
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
