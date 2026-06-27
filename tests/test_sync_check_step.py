import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys  # noqa: E402

import pytest  # noqa: E402
from PySide6 import QtWidgets  # noqa: E402

from contracts.setup import SYNC_VERDICT_GOOD, SYNC_VERDICT_POOR, SyncCheckResult  # noqa: E402
from ui.setup.steps.sync_check_step import SyncCheckStep  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)


def _result(verdict: str, passed: bool, recommendation: str = "") -> SyncCheckResult:
    return SyncCheckResult(
        sample_count=20,
        unpaired_count=0,
        mean_delta_ms=1.0,
        p95_delta_ms=2.0,
        max_delta_ms=2.5,
        jitter_ms=0.3,
        max_motion_in=2.6,
        tolerance_ms=8.0,
        max_speed_mph=60.0,
        verdict=verdict,
        passed=passed,
        recommendation=recommendation,
    )


def test_sync_check_step_renders_good_result_and_validates(qapp: QtWidgets.QApplication) -> None:
    widget = SyncCheckStep(result_provider=lambda: _result(SYNC_VERDICT_GOOD, True))

    widget.on_enter()

    assert widget._metrics_form.rowCount() == 8
    assert widget.validate() == (True, "")
    assert widget.get_title() == "Synchronization"


def test_sync_check_step_failed_result_validates_false_and_refresh_replaces_rows(
    qapp: QtWidgets.QApplication,
) -> None:
    results = [
        _result(SYNC_VERDICT_POOR, False, "Fix camera timing."),
        _result(SYNC_VERDICT_POOR, False, "Still failing."),
    ]
    widget = SyncCheckStep(result_provider=lambda: results.pop(0))

    widget.on_enter()
    valid, message = widget.validate()

    assert valid is False
    assert message
    assert widget._metrics_form.rowCount() == 8

    widget.refresh()

    assert widget._metrics_form.rowCount() == 8
