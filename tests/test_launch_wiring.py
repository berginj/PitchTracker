"""Offscreen smoke tests for launcher-to-stereo-setup wiring."""

from __future__ import annotations

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

import launcher  # noqa: E402
from ui.setup.providers import build_live_stereo_step_widgets  # noqa: E402
from ui.setup.state_machine import DEFAULT_SETUP_SPEC  # noqa: E402
from ui.setup.stereo_setup_window import StereoSetupWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    yield app


def test_launcher_exposes_stereo_setup_entry_point(qapp, monkeypatch):
    monkeypatch.setattr(launcher.QtCore.QTimer, "singleShot", lambda *_args: None)

    window = launcher.LauncherWindow()
    try:
        assert hasattr(window, "_launch_stereo_setup")
        assert window._setup_button.accessibleName() == "Launch Setup and Calibration"
    finally:
        window.close()


def test_stereo_setup_live_factory_builds_first_step_without_hardware(qapp):
    window = StereoSetupWindow(
        widget_factory=lambda: build_live_stereo_step_widgets(catalog=None, list_devices=lambda: [])
    )
    try:
        assert window._machine.current == DEFAULT_SETUP_SPEC[0].step
        assert window._content_stack.currentIndex() == 0
    finally:
        window.close()
