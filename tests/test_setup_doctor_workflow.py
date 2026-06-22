from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.services.rig_profile import PASS, CRITICAL, RigProfile, RigProfileService
from app.services.setup_doctor import STAGE_NAMES, SetupDoctorWorkflow
from configs.settings import load_config


def _config():
    return load_config(Path(__file__).parent.parent / "configs" / "default.yaml")


def _write_calibration(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        mtx_left=np.eye(3),
        mtx_right=np.eye(3),
        dist_left=np.zeros(5),
        dist_right=np.zeros(5),
        R=np.eye(3),
        T=np.array([[304.8], [0.0], [0.0]]),
        img_size=np.array([1280, 720]),
        quality_rating="GOOD",
        rms_error_px=0.4,
        calibration_mode="FULL",
    )


def _write_roi(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "lane_by_camera": {
                    "left_cam": [[10, 10], [110, 10], [110, 100], [10, 100]],
                    "right_cam": [[20, 10], [120, 10], [120, 100], [20, 100]],
                },
                "plate": [[30, 30], [90, 30], [90, 70], [30, 70]],
            }
        ),
        encoding="utf-8",
    )


def _activate_proven_profile(tmp_path: Path) -> RigProfileService:
    service = RigProfileService(base_dir=tmp_path / "calibration" / "rigs")
    profile = RigProfile.from_config(
        "rig_active",
        _config(),
        backend="sim",
        left_serial="left_cam",
        right_serial="right_cam",
        quality_metrics={
            "calibration_mode": "FULL",
            "camera_stability_status": "PASS",
            "stability_samples": 120,
            "dropped_frame_ratio": 0.0,
            "alignment_quality": "GOOD",
            "convergence_std_px": 2.0,
            "scale_mismatch_pct": 1.0,
            "overlap_score": 0.82,
            "valid_pose_pairs": 12,
            "rejected_pose_pairs": 1,
        },
        diagnostics={"source": "setup_doctor"},
    )
    profile = RigProfile.from_dict(
        {
            **profile.to_dict(),
            "board_metadata": {
                "pattern": "charuco_7x5",
                "square_size_mm": 30.0,
                "marker_dictionary": "DICT_4X4_50",
            },
        }
    )
    profile_dir = service.profile_dir(profile.profile_id)
    _write_calibration(profile_dir / profile.calibration_file)
    _write_roi(profile_dir / profile.roi_file)
    service.save(profile, activate=True)
    return service


def test_setup_doctor_workflow_passes_and_saves_report(tmp_path: Path) -> None:
    service = _activate_proven_profile(tmp_path)
    workflow = SetupDoctorWorkflow(
        service,
        config=_config(),
        backend="sim",
        left_serial="left_cam",
        right_serial="right_cam",
    )

    report = workflow.run_all()
    report_path = workflow.save_report(report)
    data = json.loads(report_path.read_text(encoding="utf-8"))

    assert report.overall_state == PASS
    assert len(report.stage_results) == len(STAGE_NAMES)
    assert report_path == tmp_path / "calibration/rigs/rig_active/setup_report.json"
    assert data["overall_state"] == PASS


def test_setup_doctor_camera_identity_stage_can_be_critical(tmp_path: Path) -> None:
    service = _activate_proven_profile(tmp_path)
    workflow = SetupDoctorWorkflow(
        service,
        config=_config(),
        backend="sim",
        left_serial="wrong_left",
        right_serial="right_cam",
    )

    result = workflow.run_stage("Camera identity")

    assert result.state == CRITICAL
    assert any("Left camera serial mismatch" in item for item in result.details)
