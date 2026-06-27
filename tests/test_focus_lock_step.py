"""Offscreen smoke tests for the Step 4 focus/exposure lock widget."""

from __future__ import annotations

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from contracts.setup import (  # noqa: E402
    LOCK_VERDICT_LOCKED,
    LOCK_VERDICT_UNLOCKED,
    ExposureLockResult,
    FocusLockResult,
)
from ui.setup.focus_lock_view import FocusExposureSnapshot  # noqa: E402
from ui.setup.steps.focus_lock_step import FocusLockStep  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    yield app


def _focus(camera_id: str, passed: bool) -> FocusLockResult:
    return FocusLockResult(
        camera_id=camera_id,
        sharpness=250.0 if passed else 0.0,
        sharpness_threshold=100.0,
        autofocus_disabled=passed,
        verdict=LOCK_VERDICT_LOCKED if passed else LOCK_VERDICT_UNLOCKED,
        passed=passed,
        recommendation="" if passed else "Focus is not locked.",
    )


def _exposure(camera_id: str, passed: bool) -> ExposureLockResult:
    return ExposureLockResult(
        camera_id=camera_id,
        exposure_us=3000.0 if passed else 0.0,
        gain=2.0 if passed else 0.0,
        white_balance_k=4500.0 if passed else 0.0,
        auto_exposure_disabled=passed,
        auto_white_balance_disabled=passed,
        readback_verified=passed,
        verdict=LOCK_VERDICT_LOCKED if passed else LOCK_VERDICT_UNLOCKED,
        passed=passed,
        recommendation="" if passed else "Exposure is not locked.",
    )


def _snapshot(passed: bool) -> FocusExposureSnapshot:
    return FocusExposureSnapshot(
        focus_left=_focus("left", passed),
        focus_right=_focus("right", passed),
        exposure_left=_exposure("left", passed),
        exposure_right=_exposure("right", passed),
    )


def test_widget_renders_passing_snapshot(qapp):
    widget = FocusLockStep(snapshot_provider=lambda: _snapshot(True))
    widget.on_enter()

    assert widget._metrics_form.rowCount() >= 6
    assert widget.validate() == (True, "")
    assert widget.get_title() == "Focus & Exposure"


def test_widget_renders_failing_snapshot_and_refresh_clears(qapp):
    widget = FocusLockStep(snapshot_provider=lambda: _snapshot(False))

    widget.on_enter()
    assert widget._metrics_form.rowCount() >= 6
    valid, message = widget.validate()
    assert valid is False
    assert message
    row_count = widget._metrics_form.rowCount()
    widget.refresh()
    assert widget._metrics_form.rowCount() == row_count
