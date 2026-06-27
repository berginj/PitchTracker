"""Offscreen smoke tests for the Step 6 rectification widget."""

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from contracts.setup import CoarseRectificationResult  # noqa: E402
from ui.setup.steps.rectify_step import RectifyStep  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    yield app


def _result(converged: bool, passed: bool) -> CoarseRectificationResult:
    identity = tuple(float(v) for v in (1, 0, 0, 0, 1, 0, 0, 0, 1))
    return CoarseRectificationResult(
        fundamental_matrix=tuple(0.0 for _ in range(9)),
        left_homography=identity,
        right_homography=identity,
        epipolar_error_before_px=4.5,
        epipolar_error_after_px=0.75,
        inlier_matches=42,
        converged=converged,
        passed=passed,
        recommendation="Adjust camera overlap and retry.",
    )


def test_widget_renders_passing_result(qapp):
    result = _result(converged=True, passed=True)
    widget = RectifyStep(result_provider=lambda: result)
    widget.on_enter()

    assert widget._metrics_form.rowCount() == 6
    assert widget.validate() == (True, "")
    assert widget.get_title() == "Rectification"


def test_widget_renders_failing_result_and_refresh_clears(qapp):
    result = _result(converged=False, passed=False)
    widget = RectifyStep(result_provider=lambda: result)

    widget.on_enter()
    is_valid, message = widget.validate()
    assert is_valid is False
    assert message
    assert widget._metrics_form.rowCount() == 6
    # Re-render with the same result — form should not accumulate rows.
    widget.refresh()
    assert widget._metrics_form.rowCount() == 6
