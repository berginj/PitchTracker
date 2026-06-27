"""Tests for the Qt-free focus/exposure lock view-model (ui.setup.focus_lock_view)."""

from __future__ import annotations

import numpy as np

from calib.stereo_setup.focus_lock import (
    ExposureLockInput,
    ExposureValues,
    evaluate_exposure_lock,
    evaluate_focus_lock,
)
from contracts.setup import LOCK_VERDICT_UNLOCKED, FocusLockResult
from ui.setup.focus_lock_view import (
    FocusExposureSnapshot,
    present_focus_lock,
    unknown_focus_snapshot,
)


def _locked_snapshot() -> FocusExposureSnapshot:
    image = np.random.default_rng(0).integers(0, 255, (64, 64), dtype=np.uint8)
    exposure_input = ExposureLockInput(
        applied=ExposureValues(exposure_us=3000.0, gain=2.0, white_balance_k=4500.0),
        readback=ExposureValues(exposure_us=3000.0, gain=2.0, white_balance_k=4500.0),
        auto_exposure_disabled=True,
        auto_white_balance_disabled=True,
    )
    return FocusExposureSnapshot(
        focus_left=evaluate_focus_lock("left", image, autofocus_disabled=True),
        focus_right=evaluate_focus_lock("right", image, autofocus_disabled=True),
        exposure_left=evaluate_exposure_lock("left", exposure_input),
        exposure_right=evaluate_exposure_lock("right", exposure_input),
    )


def test_present_formats_locked_snapshot_as_success():
    view = present_focus_lock(_locked_snapshot())

    assert view.headline == "Focus & exposure: LOCKED"
    assert view.tone == "success"
    labels = {row.label: row.value for row in view.rows}
    assert labels["Result"] == "PASS"
    result_row = next(r for r in view.rows if r.label == "Result")
    assert result_row.tone == "success"


def test_present_unlocked_focus_sets_error_and_warning():
    snapshot = _locked_snapshot()
    failed_focus = FocusLockResult(
        camera_id="left",
        sharpness=0.0,
        sharpness_threshold=100.0,
        autofocus_disabled=False,
        verdict=LOCK_VERDICT_UNLOCKED,
        passed=False,
        recommendation="Disable autofocus before calibrating.",
    )
    view = present_focus_lock(
        FocusExposureSnapshot(
            focus_left=failed_focus,
            focus_right=snapshot.focus_right,
            exposure_left=snapshot.exposure_left,
            exposure_right=snapshot.exposure_right,
        )
    )

    assert view.headline == "Focus & exposure: NOT LOCKED"
    assert view.tone == "error"
    assert "Disable autofocus before calibrating." in view.warnings


def test_unknown_focus_snapshot_is_not_passed():
    snapshot = unknown_focus_snapshot()
    assert snapshot.focus_left.passed is False
    assert snapshot.focus_right.passed is False
    assert snapshot.exposure_left.passed is False
    assert snapshot.exposure_right.passed is False

    view = present_focus_lock(snapshot)
    assert next(r for r in view.rows if r.label == "Result").value == "FAIL"
