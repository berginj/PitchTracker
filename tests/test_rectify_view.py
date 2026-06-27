"""Tests for the Qt-free rectification view-model (ui.setup.rectify_view)."""

from __future__ import annotations

from contracts.setup import CoarseRectificationResult
from ui.setup.rectify_view import present_rectification, unknown_rectification_result


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


def test_present_formats_converged_passing_result():
    view = present_rectification(_result(converged=True, passed=True))

    assert view.headline == "Coarse rectification: PASS"
    assert view.tone == "success"
    labels = {row.label: row.value for row in view.rows}
    assert labels["Converged"] == "yes"
    assert labels["Inlier matches"] == "42"
    assert labels["Epipolar error before"] == "4.50 px"
    assert labels["Epipolar error after"] == "0.75 px"
    assert labels["Improvement"] == "3.75 px"
    assert labels["Result"] == "PASS"
    result_row = next(r for r in view.rows if r.label == "Result")
    assert result_row.tone == "success"


def test_present_marks_converged_failing_result_as_marginal():
    view = present_rectification(_result(converged=True, passed=False))

    assert view.headline == "Coarse rectification: MARGINAL"
    assert view.tone == "warning"
    result_row = next(r for r in view.rows if r.label == "Result")
    assert result_row.value == "FAIL"
    assert result_row.tone == "error"


def test_present_marks_non_converged_result_as_error():
    view = present_rectification(_result(converged=False, passed=False))

    assert view.headline == "Coarse rectification: DID NOT CONVERGE"
    assert view.tone == "error"
    converged_row = next(r for r in view.rows if r.label == "Converged")
    assert converged_row.value == "no"
    assert converged_row.tone == "error"


def test_unknown_rectification_result_is_not_passed_or_converged():
    result = unknown_rectification_result()

    assert result.passed is False
    assert result.converged is False
    assert result.recommendation
