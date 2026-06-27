import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from contracts.setup import (  # noqa: E402
    OVERLAP_VERDICT_GOOD,
    OVERLAP_VERDICT_POOR,
    StereoOverlapResult,
)
from ui.setup.steps.overlap_step import OverlapStep  # noqa: E402


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication(sys.argv)


def _overlap_result(verdict: str, passed: bool, recommendation: str = "") -> StereoOverlapResult:
    return StereoOverlapResult(
        keypoints_left=120,
        keypoints_right=118,
        raw_matches=64,
        inlier_matches=42,
        inlier_ratio=0.65625,
        overlap_score=0.42,
        mean_match_distance_px=1.25,
        verdict=verdict,
        passed=passed,
        recommendation=recommendation,
    )


def test_overlap_step_good_result_renders_and_validates(qapp) -> None:
    widget = OverlapStep(result_provider=lambda: _overlap_result(OVERLAP_VERDICT_GOOD, True))

    widget.on_enter()

    assert widget._metrics_form.rowCount() == 7
    assert widget.validate() == (True, "")
    assert widget.get_title() == "Overlap"


def test_overlap_step_fail_result_validation_message(qapp) -> None:
    widget = OverlapStep(result_provider=lambda: _overlap_result(OVERLAP_VERDICT_POOR, False, "Re-aim the cameras."))

    widget.on_enter()

    valid, message = widget.validate()
    assert valid is False
    assert message


def test_overlap_step_refresh_does_not_accumulate_rows(qapp) -> None:
    results = [
        _overlap_result(OVERLAP_VERDICT_POOR, False, "Re-aim the cameras."),
        _overlap_result(OVERLAP_VERDICT_GOOD, True),
    ]
    widget = OverlapStep(result_provider=lambda: results.pop(0))

    widget.refresh()
    widget.refresh()

    assert widget._metrics_form.rowCount() == 7
    assert widget.validate() == (True, "")
