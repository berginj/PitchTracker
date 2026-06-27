import json

from ui.setup.charuco_finetune_view import (
    CharucoStatus,
    board_dictionary_name,
    load_charuco_status,
    present_charuco_finetune,
)


def test_load_charuco_status_full_report(tmp_path):
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "calibration_mode": "FULL",
                "rms_error_px": 0.42,
                "baseline_ft": 5.5,
            }
        ),
        encoding="utf-8",
    )

    status = load_charuco_status(tmp_path)

    assert status.calibration_present is True
    assert status.fine_tuned is True
    assert status.calibration_mode == "FULL"
    assert status.rms_reprojection_px == 0.42
    assert status.baseline_in == 66.0


def test_load_charuco_status_quick_report(tmp_path):
    report_path = tmp_path / "report.json"
    report_path.write_text(
        json.dumps(
            {
                "calibration_mode": "QUICK",
                "rms_error_px": 1.25,
                "baseline_ft": 4.0,
            }
        ),
        encoding="utf-8",
    )

    status = load_charuco_status(tmp_path)

    assert status.calibration_present is True
    assert status.fine_tuned is False
    assert status.calibration_mode == "QUICK"
    assert status.rms_reprojection_px == 1.25
    assert status.baseline_in == 48.0


def test_load_charuco_status_missing_report(tmp_path):
    status = load_charuco_status(tmp_path)

    assert status.calibration_present is False
    assert status.fine_tuned is False
    assert status.calibration_mode == ""
    assert status.rms_reprojection_px == 0.0
    assert status.baseline_in == 0.0


def test_present_charuco_finetune_success_has_no_warnings():
    status = CharucoStatus(
        calibration_present=True,
        fine_tuned=True,
        calibration_mode="FULL",
        rms_reprojection_px=0.4,
        baseline_in=60.0,
    )

    view = present_charuco_finetune(status)

    assert view.headline == "ChArUco fine-tuning: applied"
    assert view.tone == "success"
    assert view.warnings == []
    assert len(view.rows) == 5


def test_present_charuco_finetune_optional_warning_and_dictionary_name():
    status = CharucoStatus(
        calibration_present=True,
        fine_tuned=False,
        calibration_mode="QUICK",
        rms_reprojection_px=0.8,
        baseline_in=58.0,
    )

    view = present_charuco_finetune(status)

    assert board_dictionary_name() == "DICT_6X6_250"
    assert view.headline == "ChArUco fine-tuning: not applied (optional)"
    assert view.tone == "info"
    assert len(view.warnings) == 1
    assert "optional" in view.warnings[0]
