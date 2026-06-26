"""Offscreen smoke tests for the Step 9 quality-report widget."""

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtWidgets  # noqa: E402

from contracts.setup import (  # noqa: E402
    CalibrationQualityReport,
    QUALITY_GRADE_FAIL,
    QUALITY_GRADE_GOOD,
)
from ui.setup.steps.quality_report_step import QualityReportStep  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    yield app


def _report(grade, passed, warnings):
    return CalibrationQualityReport(
        grade=grade,
        rms_reprojection_px=0.4,
        epipolar_error_px=0.0,
        baseline_in=9.0,
        passed=passed,
        warnings=warnings,
    )


def test_widget_renders_passing_report(qapp):
    report = _report(QUALITY_GRADE_GOOD, True, ["Epipolar not measured."])
    widget = QualityReportStep(report_provider=lambda: report)
    widget.on_enter()

    assert widget._metrics_form.rowCount() == 4
    assert widget.validate() == (True, "")
    assert widget.get_title() == "Quality Report"


def test_widget_renders_failing_report_and_refresh_clears(qapp):
    states = [
        _report(QUALITY_GRADE_FAIL, False, ["Calibration report not found."]),
        _report(QUALITY_GRADE_GOOD, True, []),
    ]
    widget = QualityReportStep(report_provider=lambda: states.pop(0))

    widget.on_enter()
    assert widget._metrics_form.rowCount() == 4
    # Re-render with a different report — form should not accumulate rows.
    widget.refresh()
    assert widget._metrics_form.rowCount() == 4
