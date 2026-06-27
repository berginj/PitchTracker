import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6 import QtWidgets  # noqa: E402

from ui.setup.charuco_finetune_view import CharucoStatus  # noqa: E402
from ui.setup.steps.charuco_finetune_step import CharucoFinetuneStep  # noqa: E402


@pytest.fixture
def qapp():
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication([])
    return app


def _status(fine_tuned: bool) -> CharucoStatus:
    return CharucoStatus(
        calibration_present=True,
        fine_tuned=fine_tuned,
        calibration_mode="FULL" if fine_tuned else "QUICK",
        rms_reprojection_px=0.5,
        baseline_in=60.0,
    )


def test_charuco_finetune_step_renders_fine_tuned_status(qapp):
    widget = CharucoFinetuneStep(status_provider=lambda: _status(True))

    widget.on_enter()

    assert widget._metrics_form.rowCount() == 5
    assert widget.validate() == (True, "")
    assert widget.is_optional() is True
    assert widget.get_title() == "ChArUco Fine-Tune"


def test_charuco_finetune_step_optional_status_does_not_block_or_accumulate_rows(qapp):
    widget = CharucoFinetuneStep(status_provider=lambda: _status(False))

    widget.on_enter()
    widget.refresh()

    assert widget._metrics_form.rowCount() == 5
    assert widget.validate() == (True, "")
