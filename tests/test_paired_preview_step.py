import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys  # noqa: E402

import pytest  # noqa: E402
from PySide6 import QtWidgets  # noqa: E402

from ui.setup.paired_preview_view import PairedPreviewSnapshot  # noqa: E402
from ui.setup.steps.paired_preview_step import PairedPreviewStep  # noqa: E402


@pytest.fixture(scope="module")
def qapp() -> QtWidgets.QApplication:
    return QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)


def _passing_snapshot() -> PairedPreviewSnapshot:
    return PairedPreviewSnapshot(
        left_ok=True,
        right_ok=True,
        paired_within_tolerance=True,
        left_frame_index=12,
        right_frame_index=13,
        pair_offset_ms=1.2,
        frames_observed=5,
    )


def test_paired_preview_step_renders_passing_provider_and_validates(qapp: QtWidgets.QApplication) -> None:
    widget = PairedPreviewStep(snapshot_provider=_passing_snapshot)

    widget.on_enter()

    assert widget.is_complete() is True
    assert widget.validate() == (True, "")
    assert widget.get_title() == "Paired Preview"


def test_paired_preview_step_default_provider_renders_and_fails(qapp: QtWidgets.QApplication) -> None:
    widget = PairedPreviewStep()

    widget.on_enter()
    valid, message = widget.validate()

    assert widget.is_complete() is False
    assert valid is False
    assert message == "No frames received from either camera."


def test_paired_preview_step_metrics_rows_render(qapp: QtWidgets.QApplication) -> None:
    widget = PairedPreviewStep(snapshot_provider=_passing_snapshot)

    widget.on_enter()

    assert widget._metrics_form.rowCount() == 5


def test_paired_preview_step_refresh_replaces_metrics_rows(qapp: QtWidgets.QApplication) -> None:
    snapshots = [
        PairedPreviewSnapshot(left_ok=True, right_ok=False, left_frame_index=1, frames_observed=1),
        _passing_snapshot(),
    ]
    widget = PairedPreviewStep(snapshot_provider=lambda: snapshots.pop(0))

    widget.on_enter()
    assert widget.validate()[0] is False
    assert widget._metrics_form.rowCount() == 5

    widget.refresh()

    assert widget.validate() == (True, "")
    assert widget._metrics_form.rowCount() == 5
