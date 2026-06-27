from contracts.setup import (
    SYNC_VERDICT_GOOD,
    SYNC_VERDICT_POOR,
    SYNC_VERDICT_UNKNOWN,
    SyncCheckResult,
)
from ui.setup.sync_check_view import present_sync_check, unknown_sync_result


def _result(verdict: str, passed: bool, recommendation: str = "") -> SyncCheckResult:
    return SyncCheckResult(
        sample_count=24,
        unpaired_count=1,
        mean_delta_ms=1.25,
        p95_delta_ms=2.5,
        max_delta_ms=3.0,
        jitter_ms=0.4,
        max_motion_in=3.2,
        tolerance_ms=8.0,
        max_speed_mph=60.0,
        verdict=verdict,
        passed=passed,
        recommendation=recommendation,
    )


def test_present_sync_check_good_result_shows_success_and_pass() -> None:
    view = present_sync_check(_result(SYNC_VERDICT_GOOD, True))

    assert view.headline == "Synchronization: GOOD"
    assert view.tone == "success"
    assert view.rows[-1].label == "Result"
    assert view.rows[-1].value == "PASS"
    assert view.rows[-1].tone == "success"


def test_present_sync_check_poor_result_shows_error_fail_and_warning() -> None:
    recommendation = "Reduce exposure latency."
    view = present_sync_check(_result(SYNC_VERDICT_POOR, False, recommendation))

    assert view.headline == "Synchronization: POOR"
    assert view.tone == "error"
    assert view.rows[-1].label == "Result"
    assert view.rows[-1].value == "FAIL"
    assert view.rows[-1].tone == "error"
    assert view.warnings == [recommendation]


def test_unknown_sync_result_is_unknown_and_not_passed() -> None:
    result = unknown_sync_result()

    assert result.verdict == SYNC_VERDICT_UNKNOWN
    assert result.passed is False
    assert result.sample_count == 0
    assert result.recommendation
