"""Offscreen smoke tests for the Step 8 persist-profile widget."""

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from contracts.setup import StereoCalibrationProfile  # noqa: E402
from ui.setup.steps.persist_profile_step import PersistProfileStep  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    yield app


def _profile() -> StereoCalibrationProfile:
    return StereoCalibrationProfile(
        baseline_in=9.0,
        rms_reprojection_px=0.3,
        epipolar_error_px=0.0,
        image_width=1280,
        image_height=720,
        source="charuco",
        production_ready=True,
        calibration_file="stereo_calibration.npz",
    )


def test_widget_renders_profile(qapp):
    widget = PersistProfileStep(profile_provider=_profile)
    widget.on_enter()

    assert widget._metrics_form.rowCount() == 5
    assert widget.validate() == (True, "")
    assert widget.get_title() == "Persist Profile"


def test_persist_callback_path(qapp):
    widget = PersistProfileStep(profile_provider=_profile, persist_callback=lambda p: "rig-123")
    widget.on_enter()

    widget._persist()

    assert widget._persisted is True


def test_none_provider_blocks_validation(qapp):
    widget = PersistProfileStep(profile_provider=lambda: None)
    widget.on_enter()

    valid, message = widget.validate()

    assert valid is False
    assert message


def test_refresh_does_not_accumulate_rows(qapp):
    widget = PersistProfileStep(profile_provider=_profile)

    widget.on_enter()
    assert widget._metrics_form.rowCount() == 5
    widget.refresh()
    assert widget._metrics_form.rowCount() == 5
