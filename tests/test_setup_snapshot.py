from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from app.services.rig_profile_models import RigProfile
from app.services.setup_snapshot import assemble_setup_snapshot
from calib.capture_qualification import CaptureQualification
from configs.settings import load_config
from contracts import QualityAssessment
from contracts.setup import StereoCalibrationProfile
from contracts.setup_snapshot import assess_setup_snapshot_payload
from ui.setup.camera_select_view import DiscoveredCamera


def _profile(config) -> RigProfile:
    profile = RigProfile.from_config(
        "rig-snapshot",
        config,
        backend="uvc",
        left_serial="left",
        right_serial="right",
    )
    return replace(
        profile,
        stereo_profile=StereoCalibrationProfile(
            baseline_in=19.5,
            rms_reprojection_px=0.2,
            epipolar_error_px=0.1,
            image_width=1280,
            image_height=720,
            source="charuco",
            production_ready=True,
        ),
        field_transform={
            "matrix_4x4": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
            "rms_residual_ft": 0.01,
            "max_rms_residual_ft": 0.1,
            "fixture_id": "fixture",
        },
        control_settings={
            **profile.control_settings,
            "readback": {
                "left": {"readback_verified": True},
                "right": {"readback_verified": True},
            },
        },
    )


def test_assembler_builds_complete_content_addressed_snapshot(tmp_path: Path, monkeypatch) -> None:
    import app.services.setup_snapshot as module

    monkeypatch.setattr(module, "_source_revision", lambda: ("a" * 40, False))
    config_path = Path(__file__).parent.parent / "configs" / "default.yaml"
    config = load_config(config_path)
    profile = _profile(config)
    calibration = tmp_path / "stereo_calibration.npz"
    roi = tmp_path / "roi.json"
    calibration.write_bytes(b"calibration")
    roi.write_text("{}", encoding="utf-8")
    mode = {"width": 1280, "height": 720, "fps": 60, "pixfmt": "GRAY8"}
    assessment = QualityAssessment("qualification", "capture", "ESTIMATED")
    qualification = CaptureQualification(
        mode,
        mode,
        60,
        60,
        60,
        60,
        60.0,
        60.0,
        0.1,
        0.1,
        0.2,
        0.3,
        0.0,
        0.0,
        True,
        assessment,
    )
    cameras = (
        DiscoveredCamera(
            "left", "Left", recognized=True, global_shutter=True, model="GS", instance_id="USB\\1",
            device_path="path-left", usb_controller="controller", driver_version="1", firmware_version="1",
        ),
        DiscoveredCamera(
            "right", "Right", recognized=True, global_shutter=True, model="GS", instance_id="USB\\2",
            device_path="path-right", usb_controller="controller", driver_version="1", firmware_version="1",
        ),
    )

    snapshot = assemble_setup_snapshot(
        profile=profile,
        config=config,
        config_path=config_path,
        cameras=cameras,
        capture_qualification=qualification,
        capture_diagnostics={"modes": {"left": mode, "right": mode}},
        calibration_path=calibration,
        roi_path=roi,
    )

    assert snapshot.assessment.configuration_evidence_complete is True
    assert snapshot.verify_fingerprint() is True
    assert snapshot.sections["cameras"]["left"]["driver_version"] == "1"
    assert snapshot.sections["validation"]["validated_configuration_ready"] is False


def test_snapshot_tampering_and_missing_capture_fail_closed(tmp_path: Path, monkeypatch) -> None:
    import app.services.setup_snapshot as module

    monkeypatch.setattr(module, "_source_revision", lambda: ("a" * 40, False))
    config_path = Path(__file__).parent.parent / "configs" / "default.yaml"
    config = load_config(config_path)
    profile = _profile(config)
    calibration = tmp_path / "calibration.npz"
    roi = tmp_path / "roi.json"
    calibration.write_bytes(b"calibration")
    roi.write_text("{}", encoding="utf-8")
    cameras = (
        DiscoveredCamera("left", "Left", recognized=True, global_shutter=True),
        DiscoveredCamera("right", "Right", recognized=True, global_shutter=True),
    )
    snapshot = assemble_setup_snapshot(
        profile=profile,
        config=config,
        config_path=config_path,
        cameras=cameras,
        capture_qualification=None,
        capture_diagnostics={},
        calibration_path=calibration,
        roi_path=roi,
    )
    assert snapshot.assessment.configuration_evidence_complete is False
    payload = snapshot.to_payload()
    payload["sections"]["rig"]["backend"] = "tampered"
    tampered = assess_setup_snapshot_payload(payload)
    assert tampered.configuration_evidence_complete is False
    assert "SETUP_SNAPSHOT_FINGERPRINT_MISMATCH" in tampered.blockers
