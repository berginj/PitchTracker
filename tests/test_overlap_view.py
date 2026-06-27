from contracts.setup import (
    OVERLAP_VERDICT_GOOD,
    OVERLAP_VERDICT_POOR,
    StereoOverlapResult,
)
from ui.setup.overlap_view import present_overlap, unknown_overlap_result


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


def test_present_good_overlap_result_success_pass() -> None:
    view = present_overlap(_overlap_result(OVERLAP_VERDICT_GOOD, True))

    assert view.headline == "Stereo overlap: GOOD"
    assert view.tone == "success"
    assert view.rows[-1].label == "Result"
    assert view.rows[-1].value == "PASS"
    assert view.rows[-1].tone == "success"


def test_present_poor_overlap_result_error_fail_warning() -> None:
    recommendation = "Re-aim the cameras."
    view = present_overlap(_overlap_result(OVERLAP_VERDICT_POOR, False, recommendation))

    assert view.headline == "Stereo overlap: POOR"
    assert view.tone == "error"
    assert view.rows[-1].value == "FAIL"
    assert view.rows[-1].tone == "error"
    assert view.warnings == [recommendation]


def test_unknown_overlap_result_not_passed() -> None:
    result = unknown_overlap_result()

    assert result.passed is False
    assert result.verdict == OVERLAP_VERDICT_POOR
    assert result.recommendation
